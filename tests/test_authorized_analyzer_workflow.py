import copy
import json
import unittest

from scripts.validate_authorized_analyzer_workflow import WORKFLOW, validate


class AuthorizedAnalyzerWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = json.loads(WORKFLOW.read_text(encoding="utf-8"))

    def test_canonical_workflow_is_stop(self):
        validate(self.document)

    def test_vv2_manifest_discrepancy_stays_unresolved(self):
        recon = self.document["vv2_manifest_reconciliation"]
        self.assertEqual(recon["available_manifest"]["query_count"], 48)
        self.assertEqual(recon["dedicated_manifest"]["expected_query_count"], 50)
        self.assertIsNone(recon["dedicated_manifest"]["path"])
        self.assertIsNone(recon["unresolved_query_ids"])
        self.assertEqual(recon["invented_rows"], [])

    def test_fake_vv2_rows_fail_closed(self):
        bad = copy.deepcopy(self.document)
        bad["vv2_manifest_reconciliation"]["dedicated_manifest"]["query_ids"] = ["invented"]
        with self.assertRaises(AssertionError):
            validate(bad)

    def test_inventory_mutation_fails_closed(self):
        bad = copy.deepcopy(self.document)
        bad["game_bindings"]["vv5"]["inventory_sha256"] = "0" * 64
        with self.assertRaises(AssertionError):
            validate(bad)

    def test_export_population_fails_closed(self):
        bad = copy.deepcopy(self.document)
        bad["game_bindings"]["vv3"]["export"]["resolved_rows"] = 1
        with self.assertRaises(AssertionError):
            validate(bad)

    def test_enablement_and_launch_flags_fail_closed(self):
        bad = copy.deepcopy(self.document)
        bad["workflow"]["launches_performed"] = 1
        with self.assertRaises(AssertionError):
            validate(bad)
        bad = copy.deepcopy(self.document)
        bad["gates"]["enabled"] = True
        with self.assertRaises(AssertionError):
            validate(bad)


if __name__ == "__main__":
    unittest.main()
