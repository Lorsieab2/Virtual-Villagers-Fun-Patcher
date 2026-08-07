from __future__ import annotations

import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from transaction_primitives_native_evidence import ACTION_FAMILIES, PRIMITIVES, validate_contract
from vv_fun_patcher import source_text_sha256

PATH = ROOT / "data/transaction_primitives_native_evidence.json"

class TransactionPrimitivesEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(PATH.read_text(encoding="utf-8"))

    def test_checked_in_contract_is_structural_stop(self):
        result = validate_contract(self.data)
        self.assertTrue(result.schema_valid, result.errors)
        self.assertFalse(result.evidence_complete)
        self.assertFalse(result.publication_allowed)
        self.assertEqual(self.data["action_families"], list(ACTION_FAMILIES))

    def test_every_primitive_row_is_null_stop(self):
        for game in self.data["games"].values():
            self.assertEqual(list(game["primitives"]), list(PRIMITIVES))
            for row in game["primitives"].values():
                self.assertEqual(row["status"], "STOP")
                self.assertTrue(all(value is None or value == [] for value in row["proof"].values()))
                self.assertFalse(row["direct_store_qualifies"])
                self.assertFalse(row["adjacent_skill_writer_qualifies"])

    def test_vv5_faction_is_first_and_1ce1_absent(self):
        vv5 = self.data["games"]["vv5"]
        self.assertEqual(vv5["eligibility_required_order"][0], "faction:+0x1CEC")
        self.assertNotIn("1CE1", json.dumps(self.data))

    def test_adversarial_enablement_direct_store_1ce1_order_and_synthetic_proof_fail(self):
        cases = []
        enabled = copy.deepcopy(self.data); enabled["flags"]["native_emission"] = True; cases.append(enabled)
        direct = copy.deepcopy(self.data); direct["games"]["vv3"]["primitives"]["age_mutation"]["direct_store_qualifies"] = True; cases.append(direct)
        bad_field = copy.deepcopy(self.data); bad_field["games"]["vv5"]["eligibility_required_order"][0] = "faction:+0x1CE1"; cases.append(bad_field)
        bad_order = copy.deepcopy(self.data); bad_order["games"]["vv5"]["eligibility_required_order"] = ["active", "faction:+0x1CEC", "living", "status"]; cases.append(bad_order)
        synthetic = copy.deepcopy(self.data); synthetic["games"]["vv4"]["primitives"]["funds_transaction"]["proof"]["function_va"] = "0x401000"; cases.append(synthetic)
        adjacent = copy.deepcopy(self.data); adjacent["games"]["vv3"]["primitives"]["preference_mutation"]["adjacent_skill_writer_qualifies"] = True; cases.append(adjacent)
        for case in cases:
            result = validate_contract(case)
            self.assertFalse(result.schema_valid, result.errors)
            self.assertFalse(result.publication_allowed)

    def test_clean_archive_and_windows_checkout_match(self):
        blob = subprocess.run(["git", "show", "HEAD:data/transaction_primitives_native_evidence.json"], cwd=ROOT, capture_output=True)
        if blob.returncode == 0:
            self.assertEqual(source_text_sha256(blob.stdout), source_text_sha256(PATH.read_bytes()))
        crlf = PATH.read_text(encoding="utf-8").replace("\n", "\r\n").encode("utf-8")
        self.assertEqual(source_text_sha256(crlf), source_text_sha256(PATH.read_bytes()))

if __name__ == "__main__":
    unittest.main()
