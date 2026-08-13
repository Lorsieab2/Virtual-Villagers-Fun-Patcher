from __future__ import annotations

import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from grant_running import (  # noqa: E402
    ALREADY_MESSAGE,
    DeductionOutcome,
    NO_SLOT_MESSAGE,
    RunningBinding,
    apply_plan as strict_apply_plan,
    binding_from_manifest,
    plan_transaction as strict_plan_transaction,
    scan_running,
)

ACCOUNT_ID = 0x2000


def plan_transaction(record_value, balance, confirmed, reacquire, current_binding, *, account_identity=ACCOUNT_ID):
    def strict_reacquire():
        result = reacquire()
        if isinstance(result, tuple) and len(result) == 2:
            return result[0], result[1], account_identity
        return result

    return strict_plan_transaction(
        record_value,
        balance,
        confirmed,
        strict_reacquire,
        current_binding,
        account_identity=account_identity,
    )


def apply_plan(
    plan,
    write_like,
    write_dislike,
    read_slots,
    deduct,
    restore_slot=None,
    read_balance=None,
):
    def strict_deduct(account_identity, amount):
        if account_identity != ACCOUNT_ID:
            raise AssertionError("deduction received the wrong account identity")
        return deduct(amount)

    return strict_apply_plan(
        plan,
        write_like,
        write_dislike,
        read_slots,
        strict_deduct,
        lambda: plan.record_identity,
        lambda: (ACCOUNT_ID, 100_000 if read_balance is None else read_balance()),
        restore_slot,
    )


def binding(*, enabled: bool = True) -> RunningBinding:
    """Synthetic model harness; this is not native ABI evidence."""
    return RunningBinding(
        "test",
        "A" * 64,
        0x100,
        (0x10, 0x14, 0x18),
        (0x1C, 0x20, 0x24),
        image_size=1,
        enabled=enabled,
        preference_write_abi_proven=enabled,
        deduction_abi_proven=enabled,
        eligibility_order_declared=enabled,
    )


def record(
    likes,
    dislikes,
    *,
    identity=1,
    selected_index=0,
    record_pointer=0x1000,
    active=1,
    health=1,
    faction=0,
):
    result = {
        "identity": identity,
        "selected_index": selected_index,
        "record_pointer": record_pointer,
        "active": active,
        "health": health,
        "faction": faction,
        "likes": list(likes),
        "dislikes": list(dislikes),
    }
    return result


class ReadProbe(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.reads = []

    def get(self, key, default=None):
        self.reads.append(key)
        return super().get(key, default)


class GrantRunningTests(unittest.TestCase):
    def test_already_running_is_whole_record_noop_and_preserves_duplicates(self):
        current = record((38, 38, 7), (38, 8, 38))
        before = deepcopy(current)
        plan = plan_transaction(current, 40_000, 1, lambda: (current, 40_000), binding())
        self.assertEqual((plan.status, plan.message), ("no_change", ALREADY_MESSAGE))
        self.assertEqual(current, before)
        self.assertEqual(scan_running(current, binding()).running_dislikes, (0, 2))

    def test_first_empty_like_is_selected_and_all_running_dislikes_are_planned(self):
        current = record((7, -1, 8), (38, 9, 38))
        plan = plan_transaction(current, 40_000, 1, lambda: (current, 40_000), binding())
        self.assertEqual(plan.status, "commit")
        self.assertEqual(plan.like_index, 1)
        self.assertEqual(plan.dislike_indices, (0, 2))
        self.assertEqual(plan.after_likes, (7, 38, 8))
        self.assertEqual(plan.after_dislikes, (-1, 9, -1))
        self.assertEqual(plan.record_identity, (1, 0, 0x1000))
        self.assertEqual(current["likes"], [7, -1, 8])
        self.assertEqual(current["dislikes"], [38, 9, 38])

    def test_no_empty_like_does_not_clear_dislikes(self):
        current = record((7, 8, 9), (38, 38, 6))
        plan = plan_transaction(current, 40_000, 1, lambda: (current, 40_000), binding())
        self.assertEqual((plan.status, plan.message), ("no_change", NO_SLOT_MESSAGE))
        self.assertEqual(plan.before_dislikes, (38, 38, 6))
        self.assertEqual(plan.after_dislikes, ())

    def test_cancel_and_reacquire_race_are_no_charge(self):
        current = record((7, -1, 8), (-1, 9, -1))
        self.assertEqual(
            plan_transaction(current, 40_000, 2, lambda: (current, 40_000), binding()).status,
            "cancel",
        )
        changed = record((7, 5, 8), (-1, 9, -1), identity=2)
        race = plan_transaction(current, 40_000, 1, lambda: (changed, 40_000), binding())
        self.assertEqual(race.status, "race")

    def test_reacquire_rejects_stale_identity_slot_and_funds(self):
        current = record((7, -1, 8), (-1, 9, -1))
        stale_identity = record((7, -1, 8), (-1, 9, -1), identity=2)
        self.assertEqual(
            plan_transaction(current, 40_000, 1, lambda: (stale_identity, 40_000), binding()).status,
            "race",
        )
        stale_slot = record((7, 6, 8), (-1, 9, -1))
        self.assertEqual(
            plan_transaction(current, 40_000, 1, lambda: (stale_slot, 40_000), binding()).status,
            "race",
        )
        self.assertEqual(
            plan_transaction(current, 40_000, 1, lambda: (current, 39_999), binding()).status,
            "insufficient",
        )

    def test_vv5_faction_gate_fails_closed_before_preference_scan(self):
        vv5 = RunningBinding("vv5", "B" * 64, 0x2F44, (0x10, 0x14, 0x18), (0x1C, 0x20, 0x24), image_size=1)
        heathen = record((38, -1, 7), (38, 8, -1), faction=1)
        self.assertFalse(scan_running(heathen, vv5).eligible)

    def test_health_and_faction_gates_precede_all_preference_reads(self):
        vv1 = binding()
        vv5 = RunningBinding("vv5", "B" * 64, 0x2F44, (0x10, 0x14, 0x18), (0x1C, 0x20, 0x24), image_size=1)
        cases = (
            (vv1, {"identity": None, "active": True, "health": 1, "faction": 0}),
            (vv1, {"active": False, "health": 1, "faction": 0}),
            (vv1, {"active": True, "health": 0, "faction": 0}),
            (vv5, {"active": True, "health": 1, "faction": 1}),
        )
        for current_binding, gates in cases:
            with self.subTest(game=current_binding.game_id, gates=gates):
                probe = ReadProbe(
                    record((38, -1, 7), (38, 8, -1), **gates)
                )
                self.assertFalse(scan_running(probe, current_binding).eligible)
                self.assertNotIn("likes", probe.reads)
                self.assertNotIn("dislikes", probe.reads)

    def test_eligibility_and_identity_fields_reject_coercions_and_out_of_range_values(self):
        vv1 = binding()
        cases = (
            ("active-bool", "active", True),
            ("active-float", "active", 1.0),
            ("active-string", "active", "1"),
            ("active-out-of-range", "active", 2),
            ("health-bool", "health", True),
            ("health-float", "health", 1.0),
            ("health-string", "health", "1"),
            ("health-out-of-range", "health", 0x80000000),
            ("identity-bool", "identity", True),
            ("identity-zero", "identity", 0),
            ("identity-string", "identity", "1"),
            ("selected-index-bool", "selected_index", True),
            ("selected-index-out-of-range", "selected_index", 256),
            ("selected-index-string", "selected_index", "0"),
            ("record-pointer-bool", "record_pointer", True),
            ("record-pointer-zero", "record_pointer", 0),
            ("record-pointer-string", "record_pointer", "4096"),
        )
        for label, key, value in cases:
            with self.subTest(case=label):
                candidate = ReadProbe(record((7, -1, 8), (38, 9, 38)))
                candidate[key] = value
                self.assertFalse(scan_running(candidate, vv1).eligible)
                self.assertNotIn("likes", candidate.reads)
                self.assertNotIn("dislikes", candidate.reads)

    def test_vv5_current_faction_is_the_only_current_believer_gate(self):
        vv5 = RunningBinding(
            "vv5",
            "B" * 64,
            0x2F44,
            (0x10, 0x14, 0x18),
            (0x1C, 0x20, 0x24),
            image_size=1,
            record_count=150,
        )
        for label, key, value in (
            ("faction-bool", "faction", False),
            ("faction-float", "faction", 0.0),
            ("faction-string", "faction", "0"),
        ):
            with self.subTest(case=label):
                candidate = ReadProbe(record((7, -1, 8), (38, 9, 38)))
                candidate[key] = value
                self.assertFalse(scan_running(candidate, vv5).eligible)
                self.assertNotIn("likes", candidate.reads)
                self.assertNotIn("dislikes", candidate.reads)
        candidate = record((7, -1, 8), (38, 9, 38))
        candidate["heathen_active"] = 1
        candidate["current_believer"] = 0
        self.assertTrue(scan_running(candidate, vv5).eligible)

    def test_confirmation_and_funds_accept_only_exact_results_and_ranges(self):
        current = record((7, -1, 8), (-1, 9, -1))
        for label, balance in (
            ("bool", True),
            ("float", 40_000.0),
            ("string", "40000"),
            ("negative", -1),
            ("above-dword", 0x1_0000_0000),
        ):
            with self.subTest(case=f"funds-{label}"):
                self.assertEqual(
                    plan_transaction(current, balance, 1, lambda: (current, 40_000), binding()).status,
                    "invalid-funds",
                )
        for result_value in (True, False, 1.0, "1", 3):
            with self.subTest(case=f"confirmation-{result_value!r}"):
                reacquired = []
                result = plan_transaction(
                    current,
                    40_000,
                    result_value,
                    lambda: reacquired.append(True),
                    binding(),
                )
                self.assertEqual(result.status, "invalid-confirmation")
                self.assertEqual(reacquired, [])
        self.assertEqual(
            plan_transaction(current, 40_000, 0, lambda: (current, 40_000), binding()).status,
            "cancel",
        )
        self.assertEqual(
            plan_transaction(current, 40_000, 2, lambda: (current, 40_000), binding()).status,
            "cancel",
        )
        for invalid_account in (True, 0, 1.0, "8192", 0x1_0000_0000):
            with self.subTest(account=invalid_account):
                result = strict_plan_transaction(
                    current,
                    40_000,
                    1,
                    lambda: (current, 40_000, ACCOUNT_ID),
                    binding(),
                    account_identity=invalid_account,
                )
                self.assertEqual(result.status, "invalid-account")
        self.assertEqual(
            strict_plan_transaction(
                current,
                40_000,
                1,
                lambda: (current, 40_000, ACCOUNT_ID + 1),
                binding(),
                account_identity=ACCOUNT_ID,
            ).status,
            "account-race",
        )

    def test_reacquire_exceptions_and_malformed_identity_are_structured_unknown(self):
        current = record((7, -1, 8), (-1, 9, -1))
        callbacks = (
            (lambda: (_ for _ in ()).throw(RuntimeError("reacquire failed")), "reacquire-unknown"),
            (lambda: [current, 40_000], "reacquire-unknown"),
            (lambda: (current, True), "reacquire-unknown"),
            (lambda: (record((7, -1, 8), (-1, 9, -1), record_pointer=0x1001), 40_000), "race"),
            (lambda: (record((7, -1, 8), (-1, 9, -1), selected_index=256), 40_000), "reacquire-unknown"),
        )
        for callback, expected_status in callbacks:
            with self.subTest(callback=repr(callback)):
                result = plan_transaction(current, 40_000, 1, callback, binding())
                self.assertEqual(result.status, expected_status)
                if expected_status == "reacquire-unknown":
                    self.assertIn("no tech points have been deducted", result.message.casefold())

    def test_preference_snapshots_reject_bool_float_and_numeric_string_values(self):
        cases = (
            ("likes-bool", "likes", [7, True, 8]),
            ("likes-float", "likes", [7, -1.0, 8]),
            ("likes-string", "likes", [7, "-1", 8]),
            ("dislikes-bool", "dislikes", [38, True, 38]),
            ("dislikes-float", "dislikes", [38, -1.0, 38]),
            ("dislikes-string", "dislikes", [38, "-1", 38]),
        )
        for label, key, values in cases:
            with self.subTest(case=label):
                current = record((7, -1, 8), (38, 9, 38))
                current[key] = values
                self.assertFalse(scan_running(current, binding()).eligible)

    def test_preference_readback_rejects_non_exact_ints_before_deduction(self):
        cases = (
            ("likes-bool", ([7, True, 8], [38, 9, 38])),
            ("likes-float", ([7, 38.0, 8], [38, 9, 38])),
            ("likes-string", ([7, "38", 8], [38, 9, 38])),
            ("dislikes-bool", ([7, 38, 8], [38, True, 38])),
            ("dislikes-float", ([7, 38, 8], [38, 9.0, 38])),
            ("dislikes-string", ([7, 38, 8], [38, "-1", 38])),
        )
        for label, snapshot in cases:
            with self.subTest(case=label):
                current = record((7, -1, 8), (38, 9, 38))
                plan = plan_transaction(current, 40_000, 1, lambda: (current, 40_000), binding())
                deductions = []
                result = apply_plan(
                    plan,
                    lambda index, value: None,
                    lambda index, value: None,
                    lambda snapshot=snapshot: snapshot,
                    lambda value: deductions.append(value),
                )
                self.assertFalse(result.charged)
                self.assertEqual(result.charge_status, "not-attempted")
                self.assertEqual(deductions, [])
                self.assertIn("No tech points have been deducted.", result.message)

    def test_exhaustive_first_empty_slot_permutation_for_every_configured_count(self):
        expected_slots = {"vv1": 4, "vv2": 62, "vv3": 3, "vv4": 3, "vv5": 3}
        checked = 0
        for game, slot_count in expected_slots.items():
            path = ROOT / "data" / "candidates" / f"{game}_individual_grant_running_binding.json"
            current_binding = binding_from_manifest(json.loads(path.read_text(encoding="utf-8")))
            self.assertEqual(current_binding.slot_count, slot_count)
            for empty_index in range(slot_count):
                with self.subTest(game=game, empty_index=empty_index):
                    likes = [7] * slot_count
                    likes[empty_index] = current_binding.empty_id
                    dislikes = [9] * slot_count
                    dislikes[0] = current_binding.running_id
                    dislikes[-1] = current_binding.running_id
                    current = record(likes, dislikes)
                    plan = plan_transaction(
                        current,
                        current_binding.price,
                        1,
                        lambda current=current: (current, current_binding.price),
                        current_binding,
                    )
                    self.assertEqual(plan.status, "commit")
                    self.assertEqual(plan.like_index, empty_index)
                    self.assertEqual(plan.dislike_indices, (0, slot_count - 1))
                    expected_likes = list(likes)
                    expected_likes[empty_index] = current_binding.running_id
                    expected_dislikes = list(dislikes)
                    expected_dislikes[0] = current_binding.empty_id
                    expected_dislikes[-1] = current_binding.empty_id
                    self.assertEqual(plan.after_likes, tuple(expected_likes))
                    self.assertEqual(plan.after_dislikes, tuple(expected_dislikes))
                    self.assertEqual(current["likes"], likes)
                    self.assertEqual(current["dislikes"], dislikes)
                    checked += 1
        self.assertEqual(checked, sum(expected_slots.values()))

    def test_all_running_dislikes_are_cleared_and_unrelated_duplicates_remain(self):
        current = record((7, -1, 7), (38, 9, 38))
        plan = plan_transaction(current, 40_000, 1, lambda: (current, 40_000), binding())
        self.assertEqual(plan.dislike_indices, (0, 2))
        self.assertEqual(plan.after_likes, (7, 38, 7))
        self.assertEqual(plan.after_dislikes, (-1, 9, -1))
        self.assertEqual(plan.after_likes.count(7), 2)
        self.assertEqual(plan.after_dislikes.count(9), 1)

    def test_disabled_binding_never_calls_native_callbacks(self):
        current = record((7, -1, 8), (38, 9, 38))
        plan = plan_transaction(current, 40_000, 1, lambda: (current, 40_000), binding(enabled=False))
        calls = []
        result = apply_plan(
            plan,
            lambda *_: calls.append("like"),
            lambda *_: calls.append("dislike"),
            lambda: ((7, -1, 8), (38, 9, 38)),
            lambda *_: calls.append("deduct"),
        )
        self.assertEqual(result.status, "disabled")
        self.assertEqual(calls, [])

    def test_current_game_binding_manifests_normalize_into_the_shared_model(self):
        expected_slots = {"vv1": 4, "vv2": 62, "vv3": 3, "vv4": 3, "vv5": 3}
        expected_records = {"vv1": 256, "vv2": 256, "vv3": 150, "vv4": 150, "vv5": 150}
        for game, slot_count in expected_slots.items():
            with self.subTest(game=game):
                path = ROOT / "data" / "candidates" / f"{game}_individual_grant_running_binding.json"
                raw = json.loads(path.read_text(encoding="utf-8"))
                normalized = binding_from_manifest(raw)
                self.assertEqual(normalized.game_id, game)
                self.assertEqual(normalized.slot_count, slot_count)
                self.assertEqual(normalized.record_count, expected_records[game])
                self.assertTrue(normalized.eligibility_order_declared)
                self.assertFalse(normalized.commit_enabled)
                self.assertEqual(raw["status"], "STOP")
                self.assertFalse(raw["enabled"])
                self.assertFalse(raw["catalog_enabled"])
                self.assertTrue(raw["catalog_hidden"])

    def test_running_binding_manifests_are_clean_archive_line_ending_independent(self):
        for game in ("vv1", "vv2", "vv3", "vv4", "vv5"):
            with self.subTest(game=game):
                path = ROOT / "data" / "candidates" / f"{game}_individual_grant_running_binding.json"
                source = path.read_bytes().replace(b"\r\n", b"\n")
                archive_binding = binding_from_manifest(json.loads(source.decode("utf-8")))
                windows_binding = binding_from_manifest(
                    json.loads(source.replace(b"\n", b"\r\n").decode("utf-8"))
                )
                self.assertEqual(archive_binding, windows_binding)
                self.assertFalse(archive_binding.commit_enabled)

    def test_postverify_failure_rolls_back_only_when_expected_state_is_still_present(self):
        state = {"likes": [7, -1, 8], "dislikes": [38, 9, 38]}
        plan_record = record(state["likes"], state["dislikes"])
        plan = plan_transaction(plan_record, 40_000, 1, lambda: (plan_record, 40_000), binding())
        calls = []
        reads = 0

        def read_slots():
            nonlocal reads
            reads += 1
            if reads == 2:
                return tuple(state["likes"]), (-1, 9, 38)
            return tuple(state["likes"]), tuple(state["dislikes"])

        result = apply_plan(
            plan,
            lambda index, value: state["likes"].__setitem__(index, value),
            lambda index, value: state["dislikes"].__setitem__(index, value),
            read_slots,
            lambda *_: calls.append(("deduct",)),
            lambda kind, index, value: state["likes" if kind == "like" else "dislikes"].__setitem__(index, value),
        )
        self.assertEqual(result.rollback, "complete")
        self.assertFalse(result.charged)
        self.assertNotIn(("deduct",), calls)
        self.assertEqual(state, {"likes": [7, -1, 8], "dislikes": [38, 9, 38]})

    def test_like_readback_precedes_every_dislike_callback(self):
        current = record((7, -1, 8), (38, 9, 38))
        plan = plan_transaction(current, 40_000, 1, lambda: (current, 40_000), binding())
        state = {"likes": [7, -1, 8], "dislikes": [38, 9, 38]}
        events = []

        def write_like(index, value):
            events.append("write-like")
            state["likes"][index] = value

        def write_dislike(index, value):
            self.assertEqual(state["likes"], [7, 38, 8])
            self.assertEqual(state["dislikes"], [38, 9, 38] if index == 0 else [-1, 9, 38])
            events.append(f"write-dislike-{index}")
            state["dislikes"][index] = value

        def read_slots():
            events.append("read")
            return tuple(state["likes"]), tuple(state["dislikes"])

        balance = [100_000]

        def deduct(_value):
            balance[0] -= 40_000
            return DeductionOutcome("charged")

        result = apply_plan(
            plan,
            write_like,
            write_dislike,
            read_slots,
            deduct,
            read_balance=lambda: balance[0],
        )
        self.assertEqual(result.status, "committed")
        self.assertEqual(events[:3], ["write-like", "read", "write-dislike-0"])
        self.assertEqual(result.charge_status, "charged")

    def test_each_native_callback_failure_is_uncharged_and_disclosed(self):
        failures = ("like", "dislike-0", "dislike-2", "deduct")
        for failure in failures:
            with self.subTest(failure=failure):
                current = record((7, -1, 8), (38, 9, 38))
                plan = plan_transaction(current, 40_000, 1, lambda: (current, 40_000), binding())
                state = {"likes": [7, -1, 8], "dislikes": [38, 9, 38]}
                dislike_calls = 0
                deductions = []

                def write_like(index, value):
                    if failure == "like":
                        raise RuntimeError("like callback failure")
                    state["likes"][index] = value

                def write_dislike(index, value):
                    nonlocal dislike_calls
                    dislike_calls += 1
                    if failure == f"dislike-{index}":
                        raise RuntimeError("dislike callback failure")
                    state["dislikes"][index] = value

                def read_slots():
                    return tuple(state["likes"]), tuple(state["dislikes"])

                def deduct(value):
                    if failure == "deduct":
                        raise RuntimeError("deduction callback failure")
                    deductions.append((value, DeductionOutcome("charged")))

                def restore_slot(kind, index, value):
                    state["likes" if kind == "like" else "dislikes"][index] = value

                result = apply_plan(
                    plan,
                    write_like,
                    write_dislike,
                    read_slots,
                    deduct,
                    restore_slot,
                    lambda: 100_000,
                )
                expected_status = "deduction-failed" if failure == "deduct" else "write-failed"
                self.assertEqual(result.status, expected_status)
                self.assertFalse(result.charged)
                self.assertIn("No tech points have been deducted.", result.message)
                self.assertEqual(result.rollback, "complete")
                self.assertEqual(
                    result.charge_status,
                    "not-charged" if failure == "deduct" else "not-attempted",
                )
                self.assertEqual(deductions, [])
                self.assertEqual(dislike_calls, 0 if failure == "like" else (1 if failure == "dislike-0" else 2))

    def test_rollback_failure_is_reported_as_partial_and_uncharged(self):
        current = record((7, -1, 8), (38, 9, 38))
        plan = plan_transaction(current, 40_000, 1, lambda: (current, 40_000), binding())
        state = {"likes": [7, -1, 8], "dislikes": [38, 9, 38]}

        def write_like(index, value):
            state["likes"][index] = value

        def write_dislike(index, value):
            state["dislikes"][index] = value

        def deduct(_value):
            raise RuntimeError("deduction callback failure")

        def restore_slot(_kind, _index, _value):
            raise RuntimeError("rollback callback failure")

        result = apply_plan(
            plan,
            write_like,
            write_dislike,
            lambda: (tuple(state["likes"]), tuple(state["dislikes"])),
            deduct,
            restore_slot,
            lambda: 100_000,
        )
        self.assertEqual(result.status, "deduction-failed")
        self.assertEqual(result.rollback, "partial")
        self.assertEqual(result.charge_status, "not-charged")
        self.assertFalse(result.charged)
        self.assertIn("No tech points have been deducted.", result.message)
        self.assertIn("retained per-slot effects may remain", result.message)

    def test_deduction_exception_after_balance_debit_is_reported_as_charged(self):
        current = record((7, -1, 8), (38, 9, 38))
        plan = plan_transaction(current, 40_000, 1, lambda: (current, 40_000), binding())
        state = {"likes": [7, -1, 8], "dislikes": [38, 9, 38]}
        balance = [100_000]

        def write_like(index, value):
            state["likes"][index] = value

        def write_dislike(index, value):
            state["dislikes"][index] = value

        def deduct(_value):
            balance[0] -= 40_000
            raise RuntimeError("deduction callback raised after charging")

        result = apply_plan(
            plan,
            write_like,
            write_dislike,
            lambda: (tuple(state["likes"]), tuple(state["dislikes"])),
            deduct,
            lambda *_: (_ for _ in ()).throw(RuntimeError("must not rollback committed preference state")),
            lambda: balance[0],
        )
        self.assertEqual(result.status, "committed")
        self.assertEqual(result.charge_status, "charged")
        self.assertTrue(result.charged)
        self.assertEqual(balance[0], 60_000)
        self.assertNotIn("No tech points have been deducted.", result.message)

    def test_deduction_without_balance_change_is_verified_not_charged(self):
        current = record((7, -1, 8), (38, 9, 38))
        plan = plan_transaction(current, 40_000, 1, lambda: (current, 40_000), binding())
        state = {"likes": [7, -1, 8], "dislikes": [38, 9, 38]}

        def write_like(index, value):
            state["likes"][index] = value

        def write_dislike(index, value):
            state["dislikes"][index] = value

        result = apply_plan(
            plan,
            write_like,
            write_dislike,
            lambda: (tuple(state["likes"]), tuple(state["dislikes"])),
            lambda _value: None,
            lambda kind, index, value: state["likes" if kind == "like" else "dislikes"].__setitem__(index, value),
        )
        self.assertEqual(result.status, "deduction-failed")
        self.assertEqual(result.charge_status, "not-charged")
        self.assertFalse(result.charged)
        self.assertIn("No tech points have been deducted.", result.message)

    def test_adapter_only_charged_outcome_cannot_override_unchanged_account_balance(self):
        current = record((7, -1, 8), (38, 9, 38))
        plan = plan_transaction(current, 40_000, 1, lambda: (current, 40_000), binding())
        state = {"likes": [7, -1, 8], "dislikes": [38, 9, 38]}
        deductions = []

        def restore(kind, index, value):
            state["likes" if kind == "like" else "dislikes"][index] = value

        result = apply_plan(
            plan,
            lambda index, value: state["likes"].__setitem__(index, value),
            lambda index, value: state["dislikes"].__setitem__(index, value),
            lambda: (tuple(state["likes"]), tuple(state["dislikes"])),
            lambda value: deductions.append(DeductionOutcome("charged")),
            restore,
        )
        self.assertEqual(result.status, "deduction-failed")
        self.assertEqual(result.charge_status, "not-charged")
        self.assertFalse(result.charged)
        self.assertEqual(len(deductions), 1)
        self.assertEqual(state, {"likes": [7, -1, 8], "dislikes": [38, 9, 38]})

    def test_balance_readback_rejects_bool_float_and_numeric_string(self):
        current = record((7, -1, 8), (38, 9, 38))
        plan = plan_transaction(current, 40_000, 1, lambda: (current, 40_000), binding())
        state = {"likes": [7, -1, 8], "dislikes": [38, 9, 38]}
        for invalid in (True, 100_000.0, "100000", -1, 0x1_0000_0000):
            with self.subTest(value=invalid):
                deductions = []
                result = apply_plan(
                    plan,
                    lambda index, value: state["likes"].__setitem__(index, value),
                    lambda index, value: state["dislikes"].__setitem__(index, value),
                    lambda: (tuple(state["likes"]), tuple(state["dislikes"])),
                    lambda value: deductions.append(value),
                    lambda kind, index, value: state["likes" if kind == "like" else "dislikes"].__setitem__(index, value),
                    lambda invalid=invalid: invalid,
                )
                self.assertEqual(result.status, "account-unknown")
                self.assertEqual(deductions, [])
                state = {"likes": [7, -1, 8], "dislikes": [38, 9, 38]}

    def test_balance_before_must_still_cover_the_price_before_deduction(self):
        current = record((7, -1, 8), (38, 9, 38))
        plan = plan_transaction(current, 40_000, 1, lambda: (current, 40_000), binding())
        state = {"likes": [7, -1, 8], "dislikes": [38, 9, 38]}
        deductions = []
        result = apply_plan(
            plan,
            lambda index, value: state["likes"].__setitem__(index, value),
            lambda index, value: state["dislikes"].__setitem__(index, value),
            lambda: (tuple(state["likes"]), tuple(state["dislikes"])),
            lambda value: deductions.append(value),
            lambda kind, index, value: state["likes" if kind == "like" else "dislikes"].__setitem__(index, value),
            lambda: 39_999,
        )
        self.assertEqual(result.status, "charge-preflight-failed")
        self.assertEqual(result.charge_status, "not-attempted")
        self.assertEqual(deductions, [])
        self.assertEqual(state, {"likes": [7, -1, 8], "dislikes": [38, 9, 38]})

    def test_identity_and_account_changes_fail_closed_at_every_apply_boundary(self):
        for boundary_call in (1, 2, 3, 4):
            for field in ("selected-index", "record-pointer", "account"):
                with self.subTest(boundary=boundary_call, field=field):
                    current = record((7, -1, 8), (38, 9, 38))
                    plan = strict_plan_transaction(
                        current,
                        100_000,
                        1,
                        lambda: (current, 100_000, ACCOUNT_ID),
                        binding(),
                        account_identity=ACCOUNT_ID,
                    )
                    state = {"likes": [7, -1, 8], "dislikes": [38, 9, 38]}
                    identity_calls = 0
                    account_calls = 0
                    deductions = []

                    def identity_callback():
                        nonlocal identity_calls
                        identity_calls += 1
                        if field == "selected-index" and identity_calls == boundary_call:
                            return 1, 1, 0x1000
                        if field == "record-pointer" and identity_calls == boundary_call:
                            return 1, 0, 0x1001
                        return 1, 0, 0x1000

                    def account_callback():
                        nonlocal account_calls
                        account_calls += 1
                        identity = ACCOUNT_ID + 1 if field == "account" and account_calls == boundary_call else ACCOUNT_ID
                        return identity, 100_000

                    result = strict_apply_plan(
                        plan,
                        lambda index, value: state["likes"].__setitem__(index, value),
                        lambda index, value: state["dislikes"].__setitem__(index, value),
                        lambda: (tuple(state["likes"]), tuple(state["dislikes"])),
                        lambda account, amount: deductions.append((account, amount)),
                        identity_callback,
                        account_callback,
                        lambda kind, index, value: state["likes" if kind == "like" else "dislikes"].__setitem__(index, value),
                    )
                    self.assertIn(result.status, {"identity-race", "account-race"})
                    self.assertEqual(deductions, [])
                    self.assertEqual(state, {"likes": [7, -1, 8], "dislikes": [38, 9, 38]})

    def test_account_change_after_deduction_is_unknown_not_verified_charge(self):
        current = record((7, -1, 8), (38, 9, 38))
        plan = strict_plan_transaction(
            current,
            100_000,
            1,
            lambda: (current, 100_000, ACCOUNT_ID),
            binding(),
            account_identity=ACCOUNT_ID,
        )
        state = {"likes": [7, -1, 8], "dislikes": [38, 9, 38]}
        balance = [100_000]
        account_calls = 0

        def read_account():
            nonlocal account_calls
            account_calls += 1
            return (ACCOUNT_ID + 1 if account_calls == 5 else ACCOUNT_ID), balance[0]

        def deduct(account, amount):
            self.assertEqual(account, ACCOUNT_ID)
            balance[0] -= amount
            return DeductionOutcome("charged")

        result = strict_apply_plan(
            plan,
            lambda index, value: state["likes"].__setitem__(index, value),
            lambda index, value: state["dislikes"].__setitem__(index, value),
            lambda: (tuple(state["likes"]), tuple(state["dislikes"])),
            deduct,
            lambda: (1, 0, 0x1000),
            read_account,
            lambda kind, index, value: state["likes" if kind == "like" else "dislikes"].__setitem__(index, value),
        )
        self.assertEqual(result.status, "charge-unknown")
        self.assertEqual(result.charge_status, "unknown")
        self.assertIsNone(result.charged)
        self.assertNotIn("No tech points have been deducted", result.message)

    def test_each_rollback_restore_reacquires_selection_pointer_and_account(self):
        cases = tuple(
            (field, restore_index)
            for field in ("selected-index", "record-pointer", "account")
            for restore_index in range(3)
        )
        for field, restore_index in cases:
            with self.subTest(field=field, restore_index=restore_index):
                current = record((7, -1, 8), (38, 9, 38))
                plan = strict_plan_transaction(
                    current,
                    100_000,
                    1,
                    lambda: (current, 100_000, ACCOUNT_ID),
                    binding(),
                    account_identity=ACCOUNT_ID,
                )
                state = {"likes": [7, -1, 8], "dislikes": [38, 9, 38]}
                identity_calls = 0
                account_calls = 0
                target_identity_call = 6 + restore_index
                target_account_call = 7 + restore_index

                def identity_callback():
                    nonlocal identity_calls
                    identity_calls += 1
                    if field == "selected-index" and identity_calls == target_identity_call:
                        return 1, 1, 0x1000
                    if field == "record-pointer" and identity_calls == target_identity_call:
                        return 1, 0, 0x1001
                    return 1, 0, 0x1000

                def account_callback():
                    nonlocal account_calls
                    account_calls += 1
                    identity = ACCOUNT_ID + 1 if field == "account" and account_calls == target_account_call else ACCOUNT_ID
                    return identity, 100_000

                result = strict_apply_plan(
                    plan,
                    lambda index, value: state["likes"].__setitem__(index, value),
                    lambda index, value: state["dislikes"].__setitem__(index, value),
                    lambda: (tuple(state["likes"]), tuple(state["dislikes"])),
                    lambda _account, _amount: DeductionOutcome("not-charged"),
                    identity_callback,
                    account_callback,
                    lambda kind, index, value: state["likes" if kind == "like" else "dislikes"].__setitem__(index, value),
                )
                self.assertEqual(result.status, "deduction-failed")
                self.assertEqual(result.rollback, "partial")
                self.assertIn("retained per-slot effects may remain", result.message)

    def test_identity_and_account_callback_exceptions_are_structured(self):
        current = record((7, -1, 8), (38, 9, 38))
        plan = strict_plan_transaction(
            current,
            100_000,
            1,
            lambda: (current, 100_000, ACCOUNT_ID),
            binding(),
            account_identity=ACCOUNT_ID,
        )
        for label, identity_callback, account_callback, expected in (
            (
                "identity",
                lambda: (_ for _ in ()).throw(RuntimeError("identity failure")),
                lambda: (ACCOUNT_ID, 100_000),
                "identity-unknown",
            ),
            (
                "account",
                lambda: (1, 0, 0x1000),
                lambda: (_ for _ in ()).throw(RuntimeError("account failure")),
                "account-unknown",
            ),
        ):
            with self.subTest(callback=label):
                writes = []
                result = strict_apply_plan(
                    plan,
                    lambda *_: writes.append("like"),
                    lambda *_: writes.append("dislike"),
                    lambda: ((7, -1, 8), (38, 9, 38)),
                    lambda *_: writes.append("deduct"),
                    identity_callback,
                    account_callback,
                )
                self.assertEqual(result.status, expected)
                self.assertEqual(writes, [])
                self.assertIn("No tech points have been deducted", result.message)

    def test_binding_validation_rejects_ambiguous_geometry_and_identity_types(self):
        path = ROOT / "data" / "candidates" / "vv2_individual_grant_running_binding.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        cases = (
            ("bad hash", lambda item: item["exact_build"].update(sha256="not-a-hash")),
            ("bad size type", lambda item: item["exact_build"].update(size="724992")),
            ("bad count type", lambda item: item["preference_slots"]["like_slots"].update(count="62")),
            ("bad physical bound type", lambda item: item["record_identity"].update(physical_bound="256")),
            ("zero physical bound", lambda item: item["record_identity"].update(physical_bound=0)),
            ("oversized physical bound", lambda item: item["record_identity"].update(physical_bound=257)),
            ("duplicate offsets", lambda item: item["preference_slots"]["dislike_slots"].update(base_offset="0x5F0")),
            ("misaligned offset", lambda item: item["preference_slots"]["like_slots"].update(base_offset="0x5F1")),
            ("missing ordering proof", lambda item: item.pop("eligibility_gate_order")),
        )
        for label, mutate in cases:
            with self.subTest(case=label):
                candidate = deepcopy(raw)
                mutate(candidate)
                with self.assertRaises(ValueError):
                    binding_from_manifest(candidate)

    def test_binding_validation_rejects_nonpositive_stride_and_overlapping_direct_offsets(self):
        path = ROOT / "data" / "candidates" / "vv3_individual_grant_running_binding.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        for label, mutate in (
            ("zero stride", lambda item: item["record_identity"].update(stride=0)),
            ("overlap", lambda item: item["preference_slots"]["dislike"].update(offsets=["0xFB4", "0xFC4", "0xFC8"])),
            ("count mismatch", lambda item: item["preference_slots"]["like"].update(count=2)),
        ):
            with self.subTest(case=label):
                candidate = deepcopy(raw)
                mutate(candidate)
                with self.assertRaises(ValueError):
                    binding_from_manifest(candidate)


if __name__ == "__main__":
    unittest.main()
