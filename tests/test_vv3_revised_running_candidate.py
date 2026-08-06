from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class VV3RevisedRunningContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(
            (ROOT / "data/candidates/vv3_individual_grant_running_revised_candidate.json").read_text(encoding="utf-8")
        )
        cls.map = json.loads(
            (ROOT / "data/candidates/vv3_individual_grant_running_revised_candidate_map.json").read_text(encoding="utf-8")
        )

    def test_candidate_is_disabled_and_expanded_fail_closed(self) -> None:
        self.assertFalse(self.manifest["enabled"])
        self.assertTrue(self.manifest["catalog_hidden"])
        self.assertFalse(self.manifest["catalog_enabled"])
        self.assertFalse(self.map["candidate_enabled"])
        self.assertTrue(self.map["expanded_fail_closed"])
        self.assertEqual(self.map["status"], "STOP")

    def test_contract_covers_all_six_slots_and_preserves_duplicates(self) -> None:
        contract = self.manifest["transaction_contract"]
        self.assertEqual(contract["likes"]["offsets"], ["0xFB4", "0xFB8", "0xFBC"])
        self.assertEqual(contract["dislikes"]["offsets"], ["0xFC0", "0xFC4", "0xFC8"])
        self.assertEqual(contract["likes"]["running"], 38)
        self.assertEqual(contract["likes"]["empty"], -1)
        self.assertIn("snapshot all six", contract["scan"])
        self.assertIn("preserve every Like", contract["scan"])
        self.assertIn("clear every Running Dislike", contract["scan"])
        self.assertIn("first physical empty Like", contract["scan"])

    def test_transaction_gates_and_truthful_stop_are_explicit(self) -> None:
        contract = self.manifest["transaction_contract"]
        self.assertEqual(contract["price"], 40000)
        self.assertEqual(contract["action"], "Buy")
        self.assertIn("complete dry run", contract["transaction"])
        self.assertIn("MB_OKCANCEL confirmation", contract["transaction"])
        self.assertEqual(contract["message_box"]["accept_result"], 1)
        self.assertEqual(contract["message_box"]["cancel_result"], 2)
        self.assertIn("cmp eax,1", contract["message_box"]["mutation_dominance"])
        self.assertIn("one native deduction", contract["transaction"])
        self.assertEqual(contract["no_deduction_suffix"], "No tech points have been deducted.")
        self.assertEqual(self.manifest["emission"]["status"], "not emitted")
        self.assertIn("Native preference side effects", self.manifest["emission"]["reason"])

    def test_predecessor_is_withdrawn(self) -> None:
        predecessor = json.loads(
            (ROOT / "data/candidates/vv3_individual_grant_running_candidate.json").read_text(encoding="utf-8")
        )
        self.assertFalse(predecessor["enabled"])
        self.assertTrue(predecessor["catalog_hidden"])
        self.assertEqual(predecessor["revocation"]["superseded_by"], self.manifest["id"])


if __name__ == "__main__":
    unittest.main()
