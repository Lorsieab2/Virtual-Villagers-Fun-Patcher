from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from vv5_individual_transactions import (  # noqa: E402
    NO_DEDUCTION,
    VV5Villager,
    execute,
    transaction_contracts,
)
from build_vv5_ui_confirmation_candidate import (  # noqa: E402
    active_payload,
    bound_payload,
    CURRENT_DETAIL_HOOK_VA,
    DETAIL_NATIVE_HANDLER_VA,
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
        age_companion=12,
        age_timer=3,
        skills=(80.0, 100.0, 50.0, 100.0, 100.0, 90.0),
        likes=(11, -1, 11),
        dislikes=(38, 12, 38),
    )
    return replace(base, **changes)


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
                        "reacquire same selected index and record identity",
                        "recheck exact action snapshot and eligibility",
                        "mutate only the changed native fields",
                        "postverify action-specific native result",
                        "one native charge after successful postverify",
                    ],
                )
                self.assertEqual(contract["no_charge_suffix"], NO_DEDUCTION)
                self.assertIn("cancelled", contract["no_charge_results"])
                self.assertIn("recheck_failed", contract["no_charge_results"])
                self.assertIn("postverify_failed", contract["no_charge_results"])

    def test_youth_and_age18_charge_only_after_native_postverify(self) -> None:
        youth = execute(villager(), 100_000, "youth", 1)
        self.assertEqual(youth.status, "committed")
        self.assertTrue(youth.charged)
        self.assertEqual(youth.funds, 50_000)
        self.assertEqual(youth.villager.age, 100)
        self.assertEqual(youth.villager.age_companion, -108)
        # The native writer adjusts a non-zero timer by the same age delta.
        self.assertEqual(youth.villager.age_timer, -117)

        age18 = execute(villager(), 100_000, "age_18", 1)
        self.assertEqual(age18.status, "committed")
        self.assertTrue(age18.charged)
        self.assertEqual(age18.funds, 50_000)
        self.assertEqual(age18.villager.age, 360)
        self.assertEqual(age18.villager.age_companion, 152)

        no_op = execute(villager(age=100), 100_000, "youth", 1)
        self.assertEqual(no_op.status, "no_change")
        self.assertFalse(no_op.charged)
        self.assertEqual(no_op.funds, 100_000)
        self.assertIn(NO_DEDUCTION, no_op.message)

        cancelled = execute(villager(age=220), 100_000, "age_18", 0)
        self.assertEqual(cancelled.status, "cancelled")
        self.assertFalse(cancelled.charged)
        self.assertEqual(cancelled.villager, villager(age=220))

    def test_full_mastery_has_six_skill_postverify_and_no_charge_exits(self) -> None:
        committed = execute(villager(), 200_000, "full_mastery", 1)
        self.assertEqual(committed.status, "committed")
        self.assertTrue(committed.charged)
        self.assertEqual(committed.funds, 100_000)
        self.assertEqual(committed.villager.skills, (100.0,) * 6)

        invalid = execute(villager(skills=(101.0, 100.0, 100.0, 100.0, 100.0, 100.0)), 200_000, "full_mastery", 1)
        self.assertEqual(invalid.status, "invalid_skill")
        self.assertFalse(invalid.charged)
        self.assertIn(NO_DEDUCTION, invalid.message)

        failed = execute(villager(), 200_000, "full_mastery", 1, force_postverify_failure=True)
        self.assertEqual(failed.status, "postverify_failed")
        self.assertFalse(failed.charged)
        self.assertEqual(failed.funds, 200_000)
        self.assertEqual(failed.villager.skills, villager().skills)

    def test_running_snapshots_all_slots_preserves_duplicates_and_clears_dislikes(self) -> None:
        committed = execute(villager(), 100_000, "running", 1)
        self.assertEqual(committed.status, "committed")
        self.assertTrue(committed.charged)
        self.assertEqual(committed.funds, 60_000)
        self.assertEqual(committed.villager.likes, (11, 38, 11))
        self.assertEqual(committed.villager.dislikes, (-1, 12, -1))

        no_slot = execute(villager(likes=(11, 12, 13)), 100_000, "running", 1)
        self.assertEqual(no_slot.status, "no_empty_like")
        self.assertFalse(no_slot.charged)
        self.assertIn(NO_DEDUCTION, no_slot.message)

        already_clean = execute(villager(likes=(38, 12, 38), dislikes=(11, 12, 13)), 100_000, "running", 1)
        self.assertEqual(already_clean.status, "no_change")
        self.assertFalse(already_clean.charged)

    def test_reacquire_snapshot_mismatch_and_cancel_never_charge_or_mutate_candidate_fields(self) -> None:
        changed = execute(
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

        cancelled = execute(villager(), 100_000, "full_mastery", 0)
        self.assertEqual(cancelled.status, "cancelled")
        self.assertFalse(cancelled.charged)
        self.assertEqual(cancelled.villager, villager())
        self.assertIn(NO_DEDUCTION, cancelled.message)

        insufficient = execute(villager(), 99_999, "full_mastery", 1)
        self.assertEqual(insufficient.status, "insufficient_funds")
        self.assertFalse(insufficient.charged)
        self.assertIn(NO_DEDUCTION, insufficient.message)


if __name__ == "__main__":
    unittest.main()
