from __future__ import annotations

import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv3_individual_mastery import (  # noqa: E402
    CANCEL_MESSAGE,
    DEPENDENCY_MESSAGE,
    FAILURE_MESSAGE,
    NOOP_MESSAGE,
    PRICE,
    apply_plan,
    plan_transaction,
)


MANIFEST = ROOT / "data" / "candidates" / "vv3_individual_full_mastery_candidate.json"
MAP = ROOT / "data" / "candidates" / "vv3_individual_full_mastery_candidate_map.json"


def record(values=(99, 100, 100, 100, 100), *, identity="v0", preference=4):
    return {
        "identity": identity,
        "active": True,
        "health": 1,
        "skills": {
            name: value
            for name, value in zip(
                ("farming", "parenting", "healing", "research", "building"), values
            )
        },
        "preferred_job": preference,
    }


class VV3IndividualMasteryCandidateTests(unittest.TestCase):
    def test_public_metadata_and_exact_contract(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        mapping = json.loads(MAP.read_text(encoding="utf-8"))
        self.assertTrue(manifest["enabled"])
        self.assertFalse(manifest["catalog_hidden"])
        self.assertTrue(manifest["catalog_enabled"])
        self.assertEqual(manifest["dependencies"], ["vv3_full_mastery_all_stage_a_candidate"])
        self.assertEqual(manifest["transaction"]["command"], 1)
        self.assertEqual(manifest["transaction"]["price"], PRICE)
        self.assertEqual(mapping["transaction"]["native_writer"], "0x455740")
        self.assertIn("0x462500", mapping["transaction"]["native_evaluator"])
        self.assertEqual(mapping["transaction"]["preferred_job"], "0xEC0 read-only snapshot")
        self.assertEqual(mapping["skill_order"], ["Farming", "Building", "Research", "Healing", "Parenting"])

    def test_dry_run_noop_cancel_and_confirmation_order(self):
        initial = record((100, 100, 100, 100, 100))
        plan = plan_transaction([initial], 0, 0, True, lambda: (0, [initial], 0))
        self.assertEqual(plan.status, "no_change")
        self.assertEqual(plan.message, NOOP_MESSAGE)
        plan = plan_transaction([record()], 0, PRICE, False, lambda: (0, [record()], PRICE))
        self.assertEqual(plan.status, "cancel")
        self.assertEqual(plan.message, CANCEL_MESSAGE)
        plan = plan_transaction([record()], 0, PRICE - 1, True, lambda: (0, [record()], PRICE - 1))
        self.assertEqual(plan.status, "insufficient")
        self.assertIn("No tech points have been deducted.", plan.message)

    def test_dependency_preflight_happens_before_record_reads(self):
        class ExplodingRecord(dict):
            def get(self, *_args, **_kwargs):
                raise AssertionError("record read before dependency preflight")

        plan = plan_transaction(
            [ExplodingRecord()], 0, PRICE, True, lambda: (0, [], PRICE), lambda: False
        )
        self.assertEqual(plan.status, "dependency")
        self.assertEqual(plan.message, DEPENDENCY_MESSAGE)

    def test_reacquire_requires_same_identity_and_preference_is_untouched(self):
        initial = record(identity="stable", preference=2)
        changed = record(identity="replacement", preference=2)
        plan = plan_transaction([initial], 0, PRICE, True, lambda: (0, [changed], PRICE))
        self.assertEqual(plan.status, "race")
        self.assertIn("No tech points have been deducted.", plan.message)
        changed_pref = record(identity="stable", preference=3)
        plan = plan_transaction([initial], 0, PRICE, True, lambda: (0, [changed_pref], PRICE))
        self.assertEqual(plan.status, "race")

    def test_changed_only_native_writes_evaluator_once_then_deduction(self):
        initial = record((98, 100, 97, 100, 100), identity="stable", preference=4)
        writer_calls = []
        evaluator_calls = []
        deduction_calls = []
        plan = plan_transaction(
            [initial],
            0,
            PRICE,
            True,
            lambda: (0, [deepcopy(initial)], PRICE),
        )
        self.assertEqual(plan.status, "commit")
        self.assertEqual([(c.skill_index, c.delta) for c in plan.calls], [(0, 2), (3, 3)])
        result = apply_plan(
            plan,
            lambda index, skill, delta: writer_calls.append((index, skill, delta)),
            lambda index: evaluator_calls.append(index),
            lambda amount: deduction_calls.append(amount),
        )
        self.assertEqual(result, "Full Mastery was granted.")
        self.assertEqual(writer_calls, [(0, 0, 2), (0, 3, 3)])
        self.assertEqual(evaluator_calls, [0])
        self.assertEqual(deduction_calls, [PRICE])

    def test_native_failure_is_no_charge_and_truthful(self):
        initial = record(identity="stable")
        plan = plan_transaction([initial], 0, PRICE, True, lambda: (0, [deepcopy(initial)], PRICE))
        deductions = []
        result = apply_plan(
            plan,
            lambda *_: (_ for _ in ()).throw(RuntimeError("native writer failure")),
            lambda *_: None,
            lambda amount: deductions.append(amount),
        )
        self.assertEqual(result, FAILURE_MESSAGE)
        self.assertEqual(deductions, [])

    def test_funds_recheck_dominates_first_write_and_final_deduction(self):
        initial = record(identity="stable")
        plan = plan_transaction([initial], 0, PRICE, True, lambda: (0, [deepcopy(initial)], PRICE))
        writes, deductions = [], []
        self.assertEqual(
            apply_plan(
                plan, lambda *_: writes.append(1), lambda *_: None,
                lambda amount: deductions.append(amount), lambda: False,
            ),
            "Not enough tech points.\r\nNo tech points have been deducted.",
        )
        self.assertEqual(writes, [])
        self.assertEqual(deductions, [])
        checks = iter((True, False))
        writes.clear()
        self.assertEqual(
            apply_plan(
                plan, lambda *_: writes.append(1), lambda *_: None,
                lambda amount: deductions.append(amount), lambda: next(checks),
            ),
            FAILURE_MESSAGE,
        )
        self.assertEqual(writes, [1])
        self.assertEqual(deductions, [])


if __name__ == "__main__":
    unittest.main()
