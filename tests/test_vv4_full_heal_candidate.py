import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv4_full_heal import (  # noqa: E402
    NO_DEDUCTION,
    apply_transaction,
    dry_run,
    plan_transaction,
    success_message,
    failure_message,
)


MANIFEST = ROOT / "data/candidates/vv4_full_heal_cure_all_candidate.json"
MAP = ROOT / "data/candidates/vv4_full_heal_cure_all_candidate_map.json"


class VV4FullHealCandidateTests(unittest.TestCase):
    def test_candidate_is_disabled_and_stock_only(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        artifact_map = json.loads(MAP.read_text(encoding="utf-8"))
        self.assertFalse(manifest["enabled"])
        self.assertTrue(manifest["catalog_hidden"])
        self.assertFalse(manifest["catalog_enabled"])
        self.assertEqual(manifest["supported_modes"], ["collection_progression", "immediate_fixed"])
        self.assertEqual(set(manifest["rejected_modes"]), {"experimental_expanded_256", "experimental_expanded_256_progression"})
        self.assertEqual(manifest["source"]["stock_sha256"], "6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220")
        self.assertEqual(artifact_map["parents"]["vv4fm_page_sha256"], "FD72C661B533117BF38D69E7EB855250A93927C831C265226930794C1EFDDB62")
        self.assertEqual(manifest["hook"]["hook_before_parent"], "E941FEFFFF9090")
        self.assertEqual(manifest["hook"]["hook_after"], "E9EC792B009090")
        self.assertEqual(manifest["hook"]["shim_bytes"], "83F8050F854C84D4FFE9F2000000")
        self.assertTrue(manifest["hook"]["unknown_until_recertified"])

    def test_dry_run_counts_overlap_and_uses_exact_150_resolutions(self):
        records = [{"active": 0, "status": 0, "health": 0, "sick": 0} for _ in range(150)]
        records[3] = {"active": 1, "status": 0, "health": 50, "sick": 1}
        records[8] = {"active": 1, "status": 0, "health": 100, "sick": 1}
        records[11] = {"active": 1, "status": 0, "health": 70, "sick": 0}
        records[12] = {"active": 1, "status": 1, "health": 20, "sick": 1}
        calls = []
        result = dry_run(lambda i: calls.append(i) or records[i])
        self.assertEqual(calls, list(range(150)))
        self.assertEqual((result.sick_count, result.partial_count), (2, 2))

    def test_noop_cancel_insufficient_and_success_messages_are_no_charge(self):
        records = [{"active": 1, "status": 0, "health": 100, "sick": 0} for _ in range(150)]
        noop = plan_transaction(lambda i: records[i], 1, True, lambda: (lambda i: records[i], 1))
        self.assertEqual(noop.status, "no_change")
        self.assertIn(NO_DEDUCTION, noop.message)
        records[0]["health"] = 80
        cancel = plan_transaction(lambda i: records[i], 1_000_000, False, lambda: (lambda i: records[i], 1_000_000))
        self.assertEqual(cancel.status, "cancel")
        self.assertIn(NO_DEDUCTION, cancel.message)
        insufficient = plan_transaction(lambda i: records[i], 0, True, lambda: (lambda i: records[i], 0))
        self.assertEqual(insufficient.status, "insufficient")
        self.assertIn(NO_DEDUCTION, insufficient.message)
        self.assertIn("Full Heal / Cure All cured 2", success_message(2, 3))
        self.assertIn(NO_DEDUCTION, failure_message(1, 2, "postverify"))

    def test_reacquisition_and_funds_follow_confirmation(self):
        records = [{"active": 1, "status": 0, "health": 100, "sick": 0} for _ in range(150)]
        records[1]["health"] = 50
        phases = []
        def reacquire():
            phases.append("reacquire")
            return (lambda i: records[i], 30_000)
        result = plan_transaction(lambda i: records[i], 30_000, True, reacquire)
        self.assertEqual(result.status, "commit")
        self.assertEqual(phases, ["reacquire"])
        self.assertEqual(result.deduction, 0)

    def test_apply_uses_native_callbacks_once_and_never_touches_health_100(self):
        records = [{"active": 1, "status": 0, "health": 100, "sick": 0} for _ in range(150)]
        records[2].update(health=40, sick=1)
        records[4].update(health=100, sick=1)
        plan = plan_transaction(lambda i: records[i], 30_000, True, lambda: (lambda i: records[i], 30_000))
        writes, clears, cured, deductions = [], [], [], []
        def set_health(index, reason, value):
            writes.append((index, reason, value))
            records[index]["health"] = value
            return True
        def clear(index):
            clears.append(index)
            records[index]["sick"] = 0
            return True
        result = apply_transaction(lambda i: records[i], plan, set_health, clear, lambda: cured.append(1), deductions.append)
        self.assertEqual(result.status, "success")
        self.assertEqual(writes, [(2, -1, 100)])
        self.assertEqual(clears, [2, 4])
        self.assertEqual(len(cured), 2)
        self.assertEqual(deductions, [30_000])

    def test_partial_failure_is_no_charge_and_reports_actual_counts(self):
        records = [{"active": 1, "status": 0, "health": 100, "sick": 0} for _ in range(150)]
        records[0].update(health=20, sick=1)
        plan = plan_transaction(lambda i: records[i], 30_000, True, lambda: (lambda i: records[i], 30_000))
        result = apply_transaction(lambda i: records[i], plan, lambda *_: False, lambda *_: False, lambda: None, lambda *_: (_ for _ in ()).throw(AssertionError("deduction")))
        self.assertEqual(result.status, "partial")
        self.assertIn(NO_DEDUCTION, result.message)

    def test_postverify_requires_predicted_counts_before_deduction(self):
        records = [{"active": 1, "status": 0, "health": 100, "sick": 0} for _ in range(150)]
        records[0].update(health=40)
        records[1].update(health=50)
        plan = plan_transaction(lambda i: records[i], 30_000, True, lambda: (lambda i: records[i], 30_000))
        calls = []

        def set_health(index, reason, value):
            records[index]["health"] = value
            if index == 0:
                # A later native-side change removes the second planned target.
                records[1]["health"] = 100
            return True

        result = apply_transaction(lambda i: records[i], plan, set_health, lambda *_: True, lambda: None, calls.append)
        self.assertEqual(result.status, "partial")
        self.assertEqual(calls, [])
        self.assertIn(NO_DEDUCTION, result.message)


if __name__ == "__main__":
    unittest.main()
