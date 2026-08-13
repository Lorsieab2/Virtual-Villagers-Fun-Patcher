from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import discover_vv345_native_evidence as discovery


class NativeEvidenceDiscoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = json.loads(discovery.WORKFLOW.read_text(encoding="utf-8"))
        cls.manifest = json.loads(discovery.QUERY_MANIFEST.read_text(encoding="utf-8"))

    def test_canonical_workflow_reports_query_metadata_and_stop(self):
        report = discovery.build_report(self.workflow, self.manifest)

        self.assertEqual(report["status"], "STOP")
        self.assertTrue(report["read_only"])
        self.assertEqual(report["writes"], [])
        self.assertFalse(report["routes_enabled"])
        self.assertEqual([item["game"] for item in report["games"]], ["vv3", "vv4", "vv5"])

        expected_ids = [query["id"] for query in self.manifest["queries"]]
        for game in report["games"]:
            self.assertEqual(game["query_count"], 10)
            self.assertEqual(game["query_ids"], expected_ids)
            self.assertEqual(game["reviewed_ea_abi_status"], "ABSENT")
            self.assertEqual(game["status"], "STOP")
            self.assertEqual(len(game["candidate_query_metadata"]), 10)
            for query in game["candidate_query_metadata"]:
                self.assertIsNone(query["reviewed_function_start_ea"])
                self.assertIsNone(query["reviewed_function_end_ea"])
                self.assertIsNone(query["reviewed_file_offset"])
                self.assertIsNone(query["reviewed_raw_bytes"])
                self.assertIsNone(query["reviewed_registers"])
                self.assertIsNone(query["reviewed_stack_cleanup"])
                self.assertIsNone(query["reviewed_call_convention"])

    def test_declared_export_does_not_become_reviewed_evidence(self):
        workflow = copy.deepcopy(self.workflow)
        workflow["game_bindings"]["vv4"]["export"] = {
            "status": "RESOLVED",
            "artifact_path": "inputs/vv4-export.json",
            "artifact_sha256": "A" * 64,
            "resolved_rows": 10,
        }

        report = discovery.build_report(workflow, self.manifest)

        vv4 = next(item for item in report["games"] if item["game"] == "vv4")
        self.assertEqual(vv4["reviewed_ea_abi_status"], "DECLARED_BUT_UNVERIFIED")
        self.assertEqual(vv4["status"], "STOP")
        self.assertFalse(report["native_output"])
        self.assertFalse(report["routes_enabled"])

    def test_manifest_duplicate_query_fails_closed(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["queries"][1]["id"] = manifest["queries"][0]["id"]
        with self.assertRaises(discovery.DiscoveryError):
            discovery.build_report(self.workflow, manifest)

    def test_open_gate_fails_closed(self):
        workflow = copy.deepcopy(self.workflow)
        workflow["gates"]["native_output"] = True
        with self.assertRaises(discovery.DiscoveryError):
            discovery.build_report(workflow, self.manifest)


if __name__ == "__main__":
    unittest.main()
