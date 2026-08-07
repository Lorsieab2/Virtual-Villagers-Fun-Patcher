from __future__ import annotations

import copy
import sys
import unittest
from dataclasses import replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from vv5_individual_transactions import (  # noqa: E402
    CANCEL_RESULTS,
    NO_DEDUCTION,
    VV5Villager,
    _postverify,
    _verify_reference_charge,
    dry_run,
    execute,
    transaction_contracts,
)
from build_vv5_ui_confirmation_candidate import (  # noqa: E402
    active_payload,
    bound_payload,
    build_manifest,
    ACTIVE_PAYLOAD_SHA256,
    CURRENT_DETAIL_HOOK_VA,
    CURRENT_DETAIL_HOOK_PREIMAGE,
    DETAIL_NATIVE_HANDLER_VA,
    DETAIL_NATIVE_TARGET_VA,
    validate_candidate_manifest,
    validate_cave_hook_overlaps,
    validate_detail_enablement,
)


def villager(**changes: object) -> VV5Villager:
    base = VV5Villager(
        index=7,
        identity="record-7",
        active=True,
        health=100,
        heathen_active=False,
        faction=0,
        age=220,
        record_pointer="ptr-7",
        age_companion=12,
        age_timer=3,
        skills=(80.0, 100.0, 50.0, 100.0, 100.0, 90.0),
        likes=(11, -1, 11),
        dislikes=(38, 12, 38),
    )
    return replace(base, **changes)


def reference_execute(v: VV5Villager, funds: int, action: str, confirm: int, **kwargs: object):
    kwargs.setdefault("before_reacquire", lambda current: current)
    kwargs.setdefault("before_funds_reacquire", lambda current: current)
    return execute(v, funds, action, confirm, **kwargs)


class VV5UIConfirmationCandidateTests(unittest.TestCase):
    def test_candidate_is_disabled_and_native_routing_binding_is_exact(self) -> None:
        original = active_payload()
        bound, changes = bound_payload()
        self.assertEqual(changes, [])
        self.assertEqual(bound, original)
        self.assertEqual(original[0x0B], 13)  # Tech event.
        self.assertEqual(original[0xCB], 13)  # Detail handler event.
        self.assertEqual(original[0x128], 13)  # Detail constructor event.
        self.assertEqual(DETAIL_NATIVE_HANDLER_VA, 0x44B560)
        self.assertEqual(CURRENT_DETAIL_HOOK_VA, 0x44BC20)
        manifest = build_manifest()
        self.assertFalse(manifest["enabled"])
        detail = manifest["native_routing"]["detail"]
        self.assertIsNone(detail["proposed_hook"])
        self.assertEqual(detail["evidence"]["preimage"], None)
        self.assertEqual(detail["candidate_caves"], [])
        self.assertEqual(detail["candidate_hooks"], [])
        self.assertEqual(detail["native_target"], "0x7B2600")
        self.assertEqual(manifest["native_routing"]["patches"], [])
        self.assertEqual(manifest["native_routing"]["emitted_hooks"], [])
        self.assertEqual(manifest["source"]["active_payload_sha256"], ACTIVE_PAYLOAD_SHA256)
        self.assertEqual(manifest["native_routing"]["tech"]["resource"], "0x6A")
        self.assertEqual(manifest["native_routing"]["detail"]["resource"], "0x6A")

    def test_all_four_actions_have_complete_disabled_contract(self) -> None:
        contracts = transaction_contracts()
        self.assertEqual(set(contracts), {"youth", "full_mastery", "running", "age_18"})
        for action, contract in contracts.items():
            with self.subTest(action=action):
                self.assertEqual(
                    contract["sequence"],
                    [
                        "complete dry-run",
                        "explicit IDOK/Cancel confirmation",
                        "reacquire same selected index and exact record pointer",
                        "recheck exact pre-confirmation snapshot and eligibility",
                        "reacquire and require exact pre-confirmation funds before any write",
                        "reference-model mutation only; native writer remains separately disabled",
                        "reference postverify only; native readback remains separately disabled",
                        "verify one reference charge outcome and exact funds delta",
                    ],
                )
                self.assertEqual(contract["record_reacquire"], "same selected index and exact record pointer")
                self.assertEqual(contract["pre_confirmation_snapshot"], "exact snapshot equality before any native write")
                self.assertEqual(contract["funds_reacquire"], "post-confirmation funds must equal the pre-confirmation amount immediately before any write")
                self.assertEqual(contract["required_callbacks"], ["before_reacquire", "before_funds_reacquire"])
                self.assertEqual(contract["confirmation_results"], {"idok": 1, "cancel": list(CANCEL_RESULTS)})
                self.assertIn("mandatory callable", contract["before_reacquire"])
                self.assertIn("mandatory callable", contract["before_funds_reacquire"])
                self.assertIn("final funds equal", contract["charge_verification"])
                self.assertIn("no native write", contract["native_effects"])
                self.assertEqual(contract["no_charge_suffix"], NO_DEDUCTION)
                self.assertIn("cancelled", contract["no_charge_results"])
                self.assertIn("recheck_failed", contract["no_charge_results"])
                self.assertIn("funds_recheck_failed", contract["no_charge_results"])
                self.assertIn("postverify_failed", contract["no_charge_results"])
                self.assertIn("charge_failed", contract["no_charge_results"])

    def test_youth_and_age18_charge_only_after_native_postverify(self) -> None:
        youth = reference_execute(villager(), 100_000, "youth", 1)
        self.assertEqual(youth.status, "committed")
        self.assertTrue(youth.charged)
        self.assertTrue(youth.charge_verified)
        self.assertFalse(youth.native_write_performed)
        self.assertFalse(youth.native_readback_verified)
        self.assertFalse(youth.rollback_performed)
        self.assertEqual(youth.funds, 50_000)
        self.assertEqual(youth.villager.age, 100)
        self.assertEqual(youth.villager.age_companion, -108)
        # The native writer adjusts a non-zero timer by the same age delta.
        self.assertEqual(youth.villager.age_timer, -117)

        age18 = reference_execute(villager(), 100_000, "age_18", 1)
        self.assertEqual(age18.status, "committed")
        self.assertTrue(age18.charged)
        self.assertTrue(age18.charge_verified)
        self.assertEqual(age18.funds, 50_000)
        self.assertEqual(age18.villager.age, 360)
        self.assertEqual(age18.villager.age_companion, 152)

        zero_timer_youth = reference_execute(villager(age_timer=0), 100_000, "youth", 1)
        self.assertEqual(zero_timer_youth.status, "committed")
        self.assertEqual(zero_timer_youth.villager.age_timer, 0)
        zero_timer_age18 = reference_execute(villager(age_timer=0), 100_000, "age_18", 1)
        self.assertEqual(zero_timer_age18.status, "committed")
        self.assertEqual(zero_timer_age18.villager.age_timer, 0)

        no_op = reference_execute(villager(age=100), 100_000, "youth", 1)
        self.assertEqual(no_op.status, "no_change")
        self.assertFalse(no_op.charged)
        self.assertEqual(no_op.funds, 100_000)
        self.assertIn(NO_DEDUCTION, no_op.message)

        cancelled = reference_execute(villager(age=220), 100_000, "age_18", 0)
        self.assertEqual(cancelled.status, "cancelled")
        self.assertFalse(cancelled.charged)
        self.assertEqual(cancelled.villager, villager(age=220))

    def test_full_mastery_has_six_skill_postverify_and_no_charge_exits(self) -> None:
        committed = reference_execute(villager(), 200_000, "full_mastery", 1)
        self.assertEqual(committed.status, "committed")
        self.assertTrue(committed.charged)
        self.assertTrue(committed.charge_verified)
        self.assertEqual(committed.funds, 100_000)
        self.assertEqual(committed.villager.skills, (100.0,) * 6)

        invalid = reference_execute(villager(skills=(101.0, 100.0, 100.0, 100.0, 100.0, 100.0)), 200_000, "full_mastery", 1)
        self.assertEqual(invalid.status, "invalid_skill")
        self.assertFalse(invalid.charged)
        self.assertIn(NO_DEDUCTION, invalid.message)

        failed = reference_execute(villager(), 200_000, "full_mastery", 1, force_postverify_failure=True)
        self.assertEqual(failed.status, "postverify_failed")
        self.assertFalse(failed.charged)
        self.assertEqual(failed.funds, 200_000)
        self.assertEqual(failed.villager.skills, villager().skills)

    def test_running_snapshots_all_slots_preserves_duplicates_and_clears_dislikes(self) -> None:
        committed = reference_execute(villager(), 100_000, "running", 1)
        self.assertEqual(committed.status, "committed")
        self.assertTrue(committed.charged)
        self.assertTrue(committed.charge_verified)
        self.assertEqual(committed.funds, 60_000)
        self.assertEqual(committed.villager.likes, (11, 38, 11))
        self.assertEqual(committed.villager.dislikes, (-1, 12, -1))

        existing_like_cleanup = reference_execute(
            villager(likes=(38, 11, 12), dislikes=(38, 13, 14)),
            100_000,
            "running",
            1,
        )
        self.assertEqual(existing_like_cleanup.status, "committed")
        self.assertTrue(existing_like_cleanup.charged)
        self.assertEqual(existing_like_cleanup.villager.likes, (38, 11, 12))
        self.assertEqual(existing_like_cleanup.villager.dislikes, (-1, 13, 14))

        no_slot = reference_execute(villager(likes=(11, 12, 13)), 100_000, "running", 1)
        self.assertEqual(no_slot.status, "no_empty_like")
        self.assertFalse(no_slot.charged)
        self.assertIn(NO_DEDUCTION, no_slot.message)

        already_clean = reference_execute(villager(likes=(38, 12, 38), dislikes=(11, 12, 13)), 100_000, "running", 1)
        self.assertEqual(already_clean.status, "no_change")
        self.assertFalse(already_clean.charged)

    def test_reacquire_snapshot_mismatch_and_cancel_never_charge_or_mutate_candidate_fields(self) -> None:
        changed = reference_execute(
            villager(),
            100_000,
            "full_mastery",
            1,
            before_reacquire=lambda current: replace(current, skills=(81.0,) + current.skills[1:]),
        )
        self.assertEqual(changed.status, "recheck_failed")
        self.assertFalse(changed.charged)
        self.assertEqual(changed.funds, 100_000)
        self.assertEqual(changed.villager.skills[0], 81.0)
        self.assertIn(NO_DEDUCTION, changed.message)

        cancelled = reference_execute(villager(), 100_000, "full_mastery", 0)
        self.assertEqual(cancelled.status, "cancelled")
        self.assertFalse(cancelled.charged)
        self.assertEqual(cancelled.villager, villager())
        self.assertIn(NO_DEDUCTION, cancelled.message)

        insufficient = reference_execute(villager(), 99_999, "full_mastery", 1)
        self.assertEqual(insufficient.status, "insufficient_funds")
        self.assertFalse(insufficient.charged)
        self.assertIn(NO_DEDUCTION, insufficient.message)

    def test_detail_enablement_requires_exact_evidence_and_rejects_legacy_bytes(self) -> None:
        missing = copy.deepcopy(build_manifest())
        missing["enabled"] = True
        missing["native_routing"]["detail"]["proposed_hook"] = {
            "va": "0x44B560",
            "raw_offset": "0xB560",
            "length": 8,
        }
        with self.assertRaisesRegex(ValueError, "preimage_va"):
            validate_detail_enablement(missing)

        legacy = copy.deepcopy(build_manifest())
        legacy["enabled"] = True
        legacy["native_routing"]["detail"]["proposed_hook"] = {
            "va": "0x44BC20",
            "raw_offset": "0x4BC20",
            "length": 8,
            "preimage": CURRENT_DETAIL_HOOK_PREIMAGE,
        }
        with self.assertRaisesRegex(ValueError, "0x44BC20"):
            validate_detail_enablement(legacy)

    def test_cave_and_hook_overlap_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "overlap"):
            validate_cave_hook_overlaps(
                [{"name": "candidate-cave", "start": "0x100", "end": "0x110"}],
                [{"name": "candidate-hook", "start": "0x10F", "end": "0x112"}],
                (),
            )
        with self.assertRaisesRegex(ValueError, "occupied raw range"):
            validate_cave_hook_overlaps(
                [],
                [{"name": "candidate-hook", "start": "0xDB100", "end": "0xDB105"}],
            )

    def test_manifest_route_and_composition_guards_reject_drift(self) -> None:
        route_drifts = {
            "message": ("native_routing", 7),
            "resource": ("detail", "0x53"),
            "dimensions": ("detail", [95, 39]),
            "local": ("detail", [138, 2]),
            "event": ("detail", 12),
            "factory": ("detail", "0x401CF0"),
            "ownership": ("detail", "0x40C681"),
        }
        for field, (route, value) in route_drifts.items():
            with self.subTest(field=field):
                route_drift = copy.deepcopy(build_manifest())
                if route == "native_routing":
                    route_drift["native_routing"][field] = value
                else:
                    route_drift["native_routing"][route][field] = value
                with self.assertRaisesRegex(ValueError, "message 8" if field == "message" else field):
                    validate_candidate_manifest(route_drift)

        composition_drift = copy.deepcopy(build_manifest())
        composition_drift["composition_guard"]["ranges"][1]["owner"] = "foreign"
        with self.assertRaisesRegex(ValueError, "range ownership"):
            validate_candidate_manifest(composition_drift)

        stock_drift = copy.deepcopy(build_manifest())
        stock_drift["native_transaction_bindings"]["writers"]["skill"]["va"] = "0x475731"
        with self.assertRaisesRegex(ValueError, "not exact"):
            validate_candidate_manifest(stock_drift)

        source_drift = copy.deepcopy(build_manifest())
        source_drift["stock_fingerprint"]["source_bound"] = True
        with self.assertRaisesRegex(ValueError, "presence and binding"):
            validate_candidate_manifest(source_drift)

        for path in (
            ("composition_guard", "full_mastery", "map_sha256"),
            ("composition_guard", "running", "map_sha256"),
            ("composition_guard", "running", "parent_hash"),
        ):
            with self.subTest(composition_field=path):
                composition_drift = copy.deepcopy(build_manifest())
                target = composition_drift
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = "0" * 64
                with self.assertRaises(ValueError):
                    validate_candidate_manifest(composition_drift)

    def test_transaction_rechecks_pointer_funds_and_timer_without_native_effects(self) -> None:
        pointer_changed = reference_execute(
            villager(),
            100_000,
            "full_mastery",
            1,
            before_reacquire=lambda current: replace(current, record_pointer="ptr-other"),
        )
        self.assertEqual(pointer_changed.status, "recheck_failed")
        self.assertFalse(pointer_changed.charged)
        self.assertFalse(pointer_changed.native_write_performed)

        funds_changed = reference_execute(
            villager(),
            100_000,
            "youth",
            1,
            before_funds_reacquire=lambda current: current - 1,
        )
        self.assertEqual(funds_changed.status, "funds_recheck_failed")
        self.assertFalse(funds_changed.charged)
        self.assertFalse(funds_changed.charge_verified)
        self.assertEqual(funds_changed.funds, 99_999)
        self.assertIn(NO_DEDUCTION, funds_changed.message)

        plan = dry_run(villager(), "youth")
        wrong_timer = replace(villager(), age=100, age_companion=-108, age_timer=3)
        self.assertFalse(_postverify(villager(), wrong_timer, plan))

        charge_failed = reference_execute(villager(), 100_000, "youth", 1, force_charge_failure=True)
        self.assertEqual(charge_failed.status, "charge_failed")
        self.assertFalse(charge_failed.charged)
        self.assertFalse(charge_failed.charge_verified)
        self.assertEqual(charge_failed.funds, 100_000)
        self.assertIn(NO_DEDUCTION, charge_failed.message)

    def test_transaction_callbacks_are_mandatory_and_strict(self) -> None:
        with self.assertRaises(TypeError):
            execute(villager(), 100_000, "youth", 1)
        with self.assertRaises(TypeError):
            reference_execute(villager(), 100_000, "youth", 1, before_reacquire=None)
        with self.assertRaises(TypeError):
            reference_execute(villager(), 100_000, "youth", 1, before_funds_reacquire=None)
        with self.assertRaises(TypeError):
            reference_execute(villager(), 100_000.0, "youth", 1)
        with self.assertRaises(TypeError):
            reference_execute(villager(), True, "youth", 1)
        with self.assertRaises(TypeError):
            reference_execute(villager(), 100_000, "youth", 1.0)
        with self.assertRaises(ValueError):
            reference_execute(villager(), 100_000, "youth", 3)
        with self.assertRaises(TypeError):
            reference_execute(villager(), 100_000, "youth", 1, before_reacquire=lambda current: None)
        with self.assertRaises(TypeError):
            reference_execute(villager(), 100_000, "youth", 1, before_funds_reacquire=lambda current: 100_000.0)
        with self.assertRaises(TypeError):
            reference_execute(villager(), 100_000, "youth", 1, before_funds_reacquire=lambda current: True)

    def test_reference_state_rejects_coercible_types_and_missing_identity(self) -> None:
        with self.assertRaises(TypeError):
            replace(villager(), index=7.0)
        with self.assertRaises(TypeError):
            replace(villager(), identity="")
        with self.assertRaises(TypeError):
            replace(villager(), record_pointer=None)
        with self.assertRaises(TypeError):
            replace(villager(), skills=(80, 100.0, 50.0, 100.0, 100.0, 90.0))
        with self.assertRaises(TypeError):
            replace(villager(), skills=(True, 100.0, 50.0, 100.0, 100.0, 90.0))
        with self.assertRaises(TypeError):
            replace(villager(), likes=(11.0, -1, 11))

    def test_reference_charge_verification_is_exact_arithmetic_only(self) -> None:
        self.assertTrue(_verify_reference_charge(100_000, 50_000, 50_000))
        self.assertFalse(_verify_reference_charge(100_000, 49_999, 50_000))
        self.assertFalse(_verify_reference_charge(True, 0, 1))

    def test_manifest_rejects_disabled_invariant_mutations_and_unknown_schema_keys(self) -> None:
        mutations = {
            "enabled": True,
            "catalog_hidden": False,
            "catalog_enabled": True,
            "expanded_fail_closed": False,
            "runtime_status": "runtime-ready",
            "native_patches": [{"offset": "0x44B560"}],
            "native_emitted_hooks": ["0x44B560"],
            "detail_native_target": "0x7B2601",
            "detail_target_evidence": "0x7B2601",
            "detail_status": "changed",
            "stock_status": "changed",
            "call_convention": ["changed ABI"],
        }
        for name, value in mutations.items():
            with self.subTest(mutation=name):
                mutated = copy.deepcopy(build_manifest())
                if name == "native_patches":
                    mutated["native_routing"]["patches"] = value
                elif name == "native_emitted_hooks":
                    mutated["native_routing"]["emitted_hooks"] = value
                elif name == "detail_native_target":
                    mutated["native_routing"]["detail"]["native_target"] = value
                elif name == "detail_target_evidence":
                    mutated["native_routing"]["detail"]["evidence"]["native_target_va"] = value
                elif name == "detail_status":
                    mutated["native_routing"]["detail"]["status"] = value
                elif name == "stock_status":
                    mutated["stock_fingerprint"]["status"] = value
                elif name == "call_convention":
                    mutated["native_routing"]["call_convention"] = value
                else:
                    mutated[name] = value
                with self.assertRaises(ValueError):
                    validate_candidate_manifest(mutated)

        unknown = copy.deepcopy(build_manifest())
        unknown["unexpected"] = True
        with self.assertRaisesRegex(ValueError, "schema mismatch"):
            validate_candidate_manifest(unknown)
        for path in (
            ("native_routing", "detail"),
            ("native_transaction_bindings",),
            ("composition_guard",),
            ("individual_actions", "youth"),
        ):
            with self.subTest(nested_schema=path):
                nested = copy.deepcopy(build_manifest())
                target = nested
                for key in path:
                    target = target[key]
                target["unexpected"] = True
                with self.assertRaises(ValueError):
                    validate_candidate_manifest(nested)

    def test_manifest_rejects_hash_abi_and_detail_target_drift(self) -> None:
        for field in ("active_base", "active_payload_sha256", "bound_payload_sha256"):
            with self.subTest(field=field):
                mutated = copy.deepcopy(build_manifest())
                mutated["source"][field] = "0" * 64
                with self.assertRaises(ValueError):
                    validate_candidate_manifest(mutated)

        binding = copy.deepcopy(build_manifest())
        binding["native_transaction_bindings"]["selected_index"]["manager_getter_va"] = "0x425951"
        with self.assertRaises(ValueError):
            validate_candidate_manifest(binding)

        detail = copy.deepcopy(build_manifest())
        detail["native_routing"]["detail"]["native_target"] = f"0x{DETAIL_NATIVE_TARGET_VA + 1:X}"
        with self.assertRaisesRegex(ValueError, "0x44B560 -> 0x7B2600"):
            validate_candidate_manifest(detail)

        payload = copy.deepcopy(build_manifest())
        self.assertEqual(payload["source"]["active_payload_sha256"], ACTIVE_PAYLOAD_SHA256)
        payload["source"]["active_payload_sha256"] = ACTIVE_PAYLOAD_SHA256.lower()
        with self.assertRaises(ValueError):
            validate_candidate_manifest(payload)

    def test_ranges_reject_bad_types_bounds_alignment_and_address_space(self) -> None:
        bad_entries = [
            {"name": "float", "start": 1.5, "end": 2},
            {"name": "bool", "start": True, "end": 2},
            {"name": "negative", "start": -1, "end": 2},
            {"name": "reversed", "start": 2, "end": 1},
            {"name": "unaligned", "start": 3, "end": 5, "alignment": 4},
            {"name": "space", "start": 3, "end": 5, "address_space": "image"},
        ]
        for entry in bad_entries:
            with self.subTest(entry=entry):
                with self.assertRaises(ValueError):
                    validate_cave_hook_overlaps([entry], [], ())


if __name__ == "__main__":
    unittest.main()
