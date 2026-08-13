from __future__ import annotations

import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fullscreen_owner_transition_evidence import STATIC_WRAPPERS, validate_contract
from vv_fun_patcher import source_text_sha256

CONTRACT_PATH = ROOT / "data/fullscreen_owner_transition_evidence.json"

class FullscreenOwnerTransitionEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    def test_committed_contract_is_structural_stop(self):
        result = validate_contract(self.contract)
        self.assertTrue(result.schema_valid, result.errors)
        self.assertFalse(result.evidence_complete)
        self.assertFalse(result.publication_allowed)

    def test_static_hashes_are_candidates_not_runtime_receipts(self):
        for game, expected in STATIC_WRAPPERS.items():
            record = self.contract["games"][game]
            self.assertEqual(record["static_wrapper_candidates"], expected)
            self.assertEqual(record["evidence_receipts"], [])
            self.assertEqual(record["gap_status"], "STOP")

    def test_all_routes_and_scenarios_are_pending(self):
        for game in self.contract["games"].values():
            self.assertEqual(len(game["routes"]), 5)
            for route in game["routes"]:
                self.assertEqual(route["status"], "pending")
                self.assertTrue(all(value is False for value in route["requirements"].values()))
                self.assertEqual(route["required_receipt_scenarios"]["windowed"], route["required_receipt_scenarios"]["fullscreen"])

    def test_adversarial_enablement_receipt_range_and_requirement_rejected(self):
        mutations = []
        enabled = copy.deepcopy(self.contract); enabled["flags"]["publication"] = True; mutations.append(enabled)
        receipt = copy.deepcopy(self.contract); receipt["games"]["vv3"]["routes"][0]["receipts"] = [{"synthetic": True}]; mutations.append(receipt)
        region = copy.deepcopy(self.contract); region["composition_regions"] = [{"start": "0x1", "end": "0x2"}]; mutations.append(region)
        proved = copy.deepcopy(self.contract); proved["games"]["vv4"]["routes"][1]["requirements"]["sdl_window_not_hwnd"] = True; mutations.append(proved)
        wrong_hash = copy.deepcopy(self.contract); wrong_hash["games"]["vv3"]["static_wrapper_candidates"]["page"] = "A" * 64; mutations.append(wrong_hash)
        duplicate = copy.deepcopy(self.contract); duplicate["games"]["vv5"]["routes"].append(copy.deepcopy(duplicate["games"]["vv5"]["routes"][0])); mutations.append(duplicate)
        for item in mutations:
            with self.subTest(errors=validate_contract(item).errors):
                self.assertFalse(validate_contract(item).schema_valid)
                self.assertFalse(validate_contract(item).publication_allowed)

    def test_clean_git_archive_and_windows_worktree_contract_match(self):
        blob = subprocess.run(["git", "show", "HEAD:data/fullscreen_owner_transition_evidence.json"], cwd=ROOT, capture_output=True)
        if blob.returncode == 0:
            self.assertEqual(source_text_sha256(blob.stdout), source_text_sha256(CONTRACT_PATH.read_bytes()))
        crlf = CONTRACT_PATH.read_text(encoding="utf-8").replace("\n", "\r\n").encode("utf-8")
        self.assertEqual(source_text_sha256(crlf), source_text_sha256(CONTRACT_PATH.read_bytes()))

if __name__ == "__main__":
    unittest.main()
