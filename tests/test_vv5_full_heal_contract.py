from __future__ import annotations

import copy
import sys
import unittest
from dataclasses import replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from build_vv5_full_heal_contract import (  # noqa: E402
    ACTIVE_BASE_SHA256,
    ACTIVE_PAYLOAD_SHA256,
    FULL_HEAL_MODEL_SHA256,
    build_manifest,
    validate_manifest,
)
from build_vv5_ui_confirmation_candidate import build_manifest as build_ui_manifest  # noqa: E402
from canonical_source_hash import CANONICAL_SOURCE_HASH_RULE, canonical_source_bytes  # noqa: E402
from vv5_full_heal import (  # noqa: E402
    CANCEL_RESULTS,
    IDOK,
    NO_DEDUCTION,
    UNKNOWN_CHARGE,
    PRICE,
    FullHealDryRun,
    FullHealSnapshot,
    FullHealSlot,
    dry_run,
    execute,
    message_contract,
    record_contract,
    success_message,
    transaction_contract,
)


def make_record(index: int, **changes: object) -> dict[str, object]:
    record = {
        "identity": f"villager-{index}",
        "record_pointer": f"ptr-{index}",
        "active": 1,
        "faction": 0,
        "health": 100,
        "sick": False,
    }
    record.update(changes)
    return record


def make_store() -> list[dict[str, object] | None]:
    return [make_record(index) for index in range(150)]


def resolver_for(store: list[dict[str, object] | None]):
    return lambda index: store[index]


def callbacks(store: list[dict[str, object] | None], funds: list[int], people: list[int], events: list[str], *, health_outcome="success", clear_outcome="success", stat_outcome="success", deduct_outcome="success"):
    def health(index: int, pointer: str, target: int):
        events.append("health")
        if health_outcome != "success":
            return health_outcome
        assert store[index] is not None
        assert store[index]["record_pointer"] == pointer
        store[index]["health"] = target
        return "success"

    def clear(index: int, pointer: str):
        events.append("clear")
        if clear_outcome != "success":
            return clear_outcome
        assert store[index] is not None
        assert store[index]["record_pointer"] == pointer
        store[index]["sick"] = False
        return "success"

    def stat(index: int, pointer: str):
        events.append("stat")
        if stat_outcome == "success":
            people[0] += 1
        return stat_outcome

    def deduct(price: int):
        events.append("deduct")
        if deduct_outcome == "success":
            funds[0] -= price
        return deduct_outcome

    return health, clear, stat, deduct


def snapshot(store, funds, people, *, selected_index=0, selected_pointer="ptr-0"):
    return FullHealSnapshot(
        selected_index, selected_pointer, dry_run(resolver_for(store)), funds[0], people[0]
    )


class ReadLog(dict[str, object]):
    def __init__(self, *args, reads: list[str], **kwargs):
        super().__init__(*args, **kwargs)
        self.reads = reads

    def __getitem__(self, key: str) -> object:
        self.reads.append(key)
        return super().__getitem__(key)


class VV5FullHealContractTests(unittest.TestCase):
    def test_source_hash_rule_is_checkout_independent(self) -> None:
        lf = b"alpha\nbeta\n"
        self.assertEqual(canonical_source_bytes(lf), canonical_source_bytes(lf.replace(b"\n", b"\r\n")))
        self.assertEqual(canonical_source_bytes(lf), canonical_source_bytes(lf.replace(b"\n", b"\r")))
        self.assertIn("normalized to LF", CANONICAL_SOURCE_HASH_RULE)
        self.assertNotEqual(canonical_source_bytes(lf), canonical_source_bytes(lf.rstrip(b"\n")))
        with self.assertRaises(ValueError):
            canonical_source_bytes(b"\xff")
        self.assertEqual(canonical_source_bytes(b"text\n"), canonical_source_bytes(b"\xef\xbb\xbftext\n"))

    def test_record_gate_is_faction_first_and_never_reads_unproved_field(self) -> None:
        reads: list[str] = []
        believer = ReadLog(make_record(0, health=50, sick=True), reads=reads)
        records = [believer] + [make_record(index) for index in range(1, 150)]
        result = dry_run(lambda index: records[index])
        self.assertEqual((result.sick_count, result.partial_count), (1, 1))
        self.assertLess(reads.index("faction"), reads.index("health"))
        self.assertLess(reads.index("health"), reads.index("sick"))

        heathen_reads: list[str] = []
        heathen = ReadLog(make_record(0, faction=1, health=50, sick=True), reads=heathen_reads)
        dry_run(lambda index: heathen if index == 0 else records[index])
        self.assertNotIn("health", heathen_reads)
        self.assertNotIn("sick", heathen_reads)

        dead_reads: list[str] = []
        dead = ReadLog(make_record(0, health=0, sick=True), reads=dead_reads)
        dry_run(lambda index: dead if index == 0 else records[index])
        self.assertNotIn("sick", dead_reads)

        with self.assertRaises(ValueError):
            dry_run(lambda index: {**make_record(index), "heathen_active": False})
        self.assertNotIn("0x1CE1", str(record_contract()))

    def test_dry_run_counts_sick_and_partial_overlap_without_reviving(self) -> None:
        records = make_store()
        records[0] = make_record(0, health=50, sick=True)
        records[1] = make_record(1, health=100, sick=True)
        records[2] = make_record(2, health=20, sick=False)
        records[3] = make_record(3, health=0, sick=True)
        records[4] = make_record(4, faction=1, health=20, sick=True)
        result = dry_run(resolver_for(records))
        self.assertEqual((result.sick_count, result.partial_count), (2, 2))
        self.assertEqual(result.slots[3].health, 0)
        self.assertIsNone(result.slots[3].sick)
        self.assertIsNone(result.slots[4].health)
        self.assertIsNone(result.slots[4].sick)

    def test_messages_use_required_phrases_and_singular_safe_grammar(self) -> None:
        self.assertIn("2 sick villagers were cured", success_message(2, 2))
        self.assertIn("2 partial-health villagers were restored to exactly 100", success_message(2, 2))
        self.assertIn("1 sick villager was cured", success_message(1, 1))
        self.assertIn("1 partial-health villager was restored to exactly 100", success_message(1, 1))
        self.assertEqual(message_contract()["label"], "Full Heal / Cure All")
        self.assertEqual(transaction_contract()["confirmation_results"], {"idok": IDOK, "cancel": list(CANCEL_RESULTS)})

    def test_complete_transaction_postverifies_counts_and_deducts_once(self) -> None:
        records = make_store()
        records[0] = make_record(0, health=50, sick=True)
        records[1] = make_record(1, health=100, sick=True)
        records[2] = make_record(2, health=20, sick=False)
        funds = [100_000]
        people = [40]
        events: list[str] = []
        health, clear, stat, deduct = callbacks(records, funds, people, events)
        result = execute(
            resolver_for(records),
            100_000,
            IDOK,
            selected_index=0, selected_pointer="ptr-0", people_cured=40,
            before_snapshot=lambda: snapshot(records, [100_000], [40]),
            postverify_snapshot=lambda: snapshot(records, funds, people),
            after_snapshot=lambda: snapshot(records, funds, people),
            health_setter=health,
            sickness_clearer=clear,
            people_cured_incrementer=stat,
            deduct=deduct,
        )
        self.assertEqual(result.status, "committed")
        self.assertEqual((result.predicted_sick, result.predicted_partial), (2, 2))
        self.assertEqual((result.actual_sick, result.actual_partial), (2, 2))
        self.assertEqual(result.funds, 70_000)
        self.assertTrue(result.charged)
        self.assertTrue(result.charge_verified)
        self.assertEqual(result.charge_truth, "verified")
        self.assertEqual(events.count("deduct"), 1)
        self.assertEqual(records[0]["health"], 100)
        self.assertFalse(records[0]["sick"])
        self.assertFalse(records[1]["sick"])
        self.assertEqual(records[2]["health"], 100)

    def test_cancel_noop_and_insufficient_are_no_charge(self) -> None:
        records = make_store()
        records[0] = make_record(0, health=50, sick=True)
        funds = [100_000]
        people = [0]
        calls = {"deduct": 0}

        def forbidden(*args):
            calls["deduct"] += 1
            return "success"

        common = dict(
            selected_index=0, selected_pointer="ptr-0", people_cured=0,
            before_snapshot=lambda: snapshot(records, funds, people),
            postverify_snapshot=lambda: snapshot(records, funds, people),
            after_snapshot=lambda: snapshot(records, funds, people),
            health_setter=lambda *args: "success",
            sickness_clearer=lambda *args: "success",
            people_cured_incrementer=lambda *args: "success",
            deduct=forbidden,
        )
        cancelled = execute(resolver_for(records), 100_000, 0, **common)
        self.assertEqual(cancelled.status, "cancelled")
        self.assertIn(NO_DEDUCTION, cancelled.message)
        insufficient = execute(resolver_for(records), PRICE - 1, IDOK, **common)
        self.assertEqual(insufficient.status, "insufficient_funds")
        self.assertIn(NO_DEDUCTION, insufficient.message)
        records[0] = make_record(0, health=100, sick=False)
        no_change = execute(resolver_for(records), 100_000, IDOK, **common)
        self.assertEqual(no_change.status, "no_change")
        self.assertIn(NO_DEDUCTION, no_change.message)
        self.assertEqual(calls["deduct"], 0)

    def test_reacquire_and_funds_require_exact_types_and_full_snapshot(self) -> None:
        records = make_store()
        records[0] = make_record(0, health=50, sick=True)
        initial = dry_run(resolver_for(records))
        stale_slots = list(initial.slots)
        stale_slots[0] = replace(stale_slots[0], record_pointer="ptr-replaced")
        stale = FullHealDryRun(initial.sick_count, initial.partial_count, tuple(stale_slots))
        common = dict(
            selected_index=0, selected_pointer="ptr-0", people_cured=0,
            postverify_snapshot=lambda: FullHealSnapshot(0, "ptr-0", stale, 100_000, 1),
            after_snapshot=lambda: FullHealSnapshot(0, "ptr-0", stale, 70_000, 1),
            health_setter=lambda *args: "success",
            sickness_clearer=lambda *args: "success",
            people_cured_incrementer=lambda *args: "success",
            deduct=lambda price: "success",
        )
        result = execute(resolver_for(records), 100_000, IDOK, before_snapshot=lambda: FullHealSnapshot(0, "ptr-replaced", stale, 100_000, 0), **common)
        self.assertEqual(result.status, "recheck_failed")
        self.assertFalse(result.charge_attempted)
        with self.assertRaises(TypeError):
            execute(resolver_for(records), 100_000, True, before_snapshot=lambda: FullHealSnapshot(0, "ptr-0", initial, 100_000, 0), **common)
        with self.assertRaises(TypeError):
            FullHealSnapshot(0, "ptr-0", initial, True, 0)

    def test_partial_and_unknown_paths_disclose_effects_and_never_retry_charge(self) -> None:
        records = make_store()
        records[0] = make_record(0, health=50, sick=True)
        funds = [100_000]
        people = [0]
        events: list[str] = []
        health, clear, stat, deduct = callbacks(records, funds, people, events, health_outcome="unknown")
        unknown = execute(
            resolver_for(records), 100_000, IDOK,
            selected_index=0, selected_pointer="ptr-0", people_cured=0,
            before_snapshot=lambda: snapshot(records, funds, people),
            postverify_snapshot=lambda: snapshot(records, funds, people),
            after_snapshot=lambda: snapshot(records, funds, people),
            health_setter=health, sickness_clearer=clear,
            people_cured_incrementer=stat, deduct=deduct,
        )
        self.assertEqual(unknown.status, "partial_unknown")
        self.assertFalse(unknown.charge_attempted)
        self.assertEqual(unknown.charge_truth, "unknown")
        self.assertIn("Rollback status is unknown", unknown.message)
        self.assertNotIn(NO_DEDUCTION, unknown.message)

        records[0]["health"] = 100
        records[0]["sick"] = False
        funds = [100_000]
        people = [0]
        events = []
        health, clear, stat, deduct = callbacks(records, funds, people, events, deduct_outcome="unknown")
        records[1] = make_record(1, health=50, sick=False)
        charge_unknown = execute(
            resolver_for(records), 100_000, IDOK,
            selected_index=0, selected_pointer="ptr-0", people_cured=0,
            before_snapshot=lambda: snapshot(records, [100_000], [0]),
            postverify_snapshot=lambda: snapshot(records, funds, people),
            after_snapshot=lambda: snapshot(records, funds, people),
            health_setter=health, sickness_clearer=clear,
            people_cured_incrementer=stat, deduct=deduct,
        )
        self.assertEqual(charge_unknown.status, "charge_unknown")
        self.assertTrue(charge_unknown.charge_attempted)
        self.assertFalse(charge_unknown.charge_verified)
        self.assertEqual(charge_unknown.charge_truth, "unknown")
        self.assertIn("charge is unknown", charge_unknown.message)

    def test_strict_snapshot_schema_and_complete_postverify(self) -> None:
        records = make_store()
        records[0] = make_record(0, health=50, sick=True)
        initial = dry_run(resolver_for(records))
        with self.assertRaises(TypeError):
            FullHealSnapshot(True, "ptr-0", initial, 100_000, 0)
        with self.assertRaises(ValueError):
            FullHealSnapshot(150, "ptr-0", initial, 100_000, 0)
        with self.assertRaises(ValueError):
            FullHealDryRun(99, 1, initial.slots)
        with self.assertRaises(ValueError):
            FullHealSlot(0, None, None, 1, 0, None, None)

        funds, people, events = [100_000], [0], []
        health, clear, stat, deduct = callbacks(records, funds, people, events)
        result = execute(
            resolver_for(records), 100_000, IDOK,
            selected_index=0, selected_pointer="ptr-0", people_cured=0,
            before_snapshot=lambda: snapshot(records, [100_000], [0]),
            postverify_snapshot=lambda: snapshot(records, funds, people),
            after_snapshot=lambda: FullHealSnapshot(0, "ptr-0", dry_run(resolver_for(records)), funds[0], people[0] - 1),
            health_setter=health, sickness_clearer=clear,
            people_cured_incrementer=stat, deduct=deduct,
        )
        self.assertEqual(result.status, "charge_unknown")
        self.assertFalse(result.charge_verified)
        self.assertNotIn(NO_DEDUCTION, result.message)

    def test_callback_exception_and_deduction_truth_are_readback_only(self) -> None:
        records = make_store()
        records[0] = make_record(0, health=50, sick=False)
        funds, people = [100_000], [0]

        def mutates_then_raises(index, pointer, target):
            records[index]["health"] = target
            raise RuntimeError("unproven callback failure")

        common = dict(
            selected_index=0, selected_pointer="ptr-0", people_cured=0,
            before_snapshot=lambda: snapshot(records, [100_000], [0]),
            postverify_snapshot=lambda: snapshot(records, funds, people),
            after_snapshot=lambda: snapshot(records, funds, people),
            sickness_clearer=lambda *_: "success",
            people_cured_incrementer=lambda *_: "success",
            deduct=lambda _: "failure",
        )
        partial = execute(resolver_for(records), 100_000, IDOK, health_setter=mutates_then_raises, **common)
        self.assertEqual(partial.status, "partial_unknown")
        self.assertEqual(partial.native_effects, "may_have_occurred")
        self.assertEqual(partial.charge_truth, "unknown")
        self.assertNotIn(NO_DEDUCTION, partial.message)

        records[0] = make_record(0, health=50, sick=False)
        funds[0] = 100_000
        def deduct_reports_failure(price):
            funds[0] -= price
            return "failure"
        committed = execute(
            resolver_for(records), 100_000, IDOK,
            selected_index=0, selected_pointer="ptr-0", people_cured=0,
            before_snapshot=lambda: snapshot(records, [100_000], [0]),
            postverify_snapshot=lambda: snapshot(records, funds, people),
            after_snapshot=lambda: snapshot(records, funds, people),
            health_setter=lambda index, pointer, target: records[index].__setitem__("health", target) or "success",
            sickness_clearer=lambda *_: "success",
            people_cured_incrementer=lambda *_: "success",
            deduct=deduct_reports_failure,
        )
        self.assertEqual(committed.status, "committed")
        self.assertTrue(committed.charge_verified)
        self.assertEqual(committed.charge_truth, "verified")

    def test_null_and_raising_snapshot_or_resolver_callbacks_fail_closed(self) -> None:
        records = make_store()
        records[0] = make_record(0, health=50, sick=False)
        funds, people = [100_000], [0]
        health, clear, stat, deduct = callbacks(records, funds, people, [])
        common = dict(
            selected_index=0, selected_pointer="ptr-0", people_cured=0,
            postverify_snapshot=lambda: snapshot(records, funds, people),
            after_snapshot=lambda: snapshot(records, funds, people),
            health_setter=health, sickness_clearer=clear,
            people_cured_incrementer=stat, deduct=deduct,
        )
        null_before = execute(
            resolver_for(records), 100_000, IDOK,
            before_snapshot=lambda: None,
            **common,
        )
        self.assertEqual(null_before.status, "recheck_failed")
        self.assertEqual(null_before.charge_truth, "unknown")
        self.assertEqual(null_before.native_effects, "may_have_occurred")
        self.assertNotIn(NO_DEDUCTION, null_before.message)

        null_postverify = execute(
            resolver_for(records), 100_000, IDOK,
            before_snapshot=lambda: snapshot(records, [100_000], [0]),
            postverify_snapshot=lambda: None,
            **{key: value for key, value in common.items() if key != "postverify_snapshot"},
        )
        self.assertEqual(null_postverify.status, "partial_unknown")
        self.assertEqual(null_postverify.charge_truth, "unknown")
        self.assertNotIn(NO_DEDUCTION, null_postverify.message)

        def exploding_resolver(index: int):
            raise RuntimeError("resolver")

        invalid = execute(
            exploding_resolver, 100_000, IDOK,
            before_snapshot=lambda: None,
            **common,
        )
        self.assertEqual(invalid.status, "invalid_state")
        self.assertEqual(invalid.charge_truth, "unknown")
        self.assertNotIn(NO_DEDUCTION, invalid.message)

    def test_manifest_is_strict_disabled_and_composes_ui_chain_without_native_output(self) -> None:
        manifest = build_manifest()
        self.assertFalse(manifest["enabled"])
        self.assertTrue(manifest["catalog_hidden"])
        self.assertFalse(manifest["catalog_enabled"])
        self.assertTrue(manifest["expanded_fail_closed"])
        self.assertEqual(manifest["runtime_status"], "pending; no package or player validation")
        self.assertEqual(manifest["native_routing"]["patches"], [])
        self.assertEqual(manifest["native_routing"]["emitted_hooks"], [])
        self.assertEqual(manifest["composition_guard"]["full_heal"]["owned_range"], [])
        self.assertEqual(manifest["source"]["active_base_sha256"], ACTIVE_BASE_SHA256)
        self.assertEqual(manifest["source"]["active_payload_sha256"], ACTIVE_PAYLOAD_SHA256)
        self.assertEqual(manifest["source"]["model_sha256"], FULL_HEAL_MODEL_SHA256)
        self.assertEqual(manifest["source"]["source_hash_rule"], CANONICAL_SOURCE_HASH_RULE)
        self.assertEqual(build_ui_manifest()["individual_actions"].keys(), {"youth", "full_mastery", "running", "age_18"})

        for field, value in (("enabled", True), ("catalog_hidden", False), ("catalog_enabled", True), ("expanded_fail_closed", False)):
            mutated = copy.deepcopy(manifest)
            mutated[field] = value
            with self.assertRaises(ValueError):
                validate_manifest(mutated)
        for path in (("source", "active_base_sha256"), ("source", "model_sha256"), ("composition_guard", "stock_sha256"), ("composition_guard", "full_mastery", "map_sha256"), ("composition_guard", "running", "parent_hash")):
            mutated = copy.deepcopy(manifest)
            target = mutated
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = "0" * 64
            with self.assertRaises(ValueError):
                validate_manifest(mutated)
        unknown = copy.deepcopy(manifest)
        unknown["unexpected"] = True
        with self.assertRaises(ValueError):
            validate_manifest(unknown)
        polluted = copy.deepcopy(manifest)
        polluted["record_contract"]["unexpected"] = True
        with self.assertRaises(ValueError):
            validate_manifest(polluted)


if __name__ == "__main__":
    unittest.main()
