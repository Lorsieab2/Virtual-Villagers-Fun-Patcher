from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NO_DEDUCTION = "No tech points have been deducted."


def load(name: str) -> dict[str, object]:
    return json.loads((ROOT / "data" / "candidates" / name).read_text(encoding="utf-8"))


class IndividualBuyTransactionContractTests(unittest.TestCase):
    """Fail-closed contract checks for every currently exposed individual route."""

    def test_vv3_individual_running_has_complete_buy_contract(self) -> None:
        raw = load("vv3_individual_grant_running_candidate.json")
        tx = raw["transaction_contract"]
        self.assertEqual(
            {key: tx[key] for key in ("command", "price", "action", "repeatable", "ownership", "remove")},
            {"command": 2, "price": 40000, "action": "Buy", "repeatable": True, "ownership": None, "remove": False},
        )
        self.assertEqual(
            tx["passes"],
            [
                "complete initial three-DWORD Like snapshot/scan",
                "funds >= 40000",
                "OK/Cancel",
                "fresh singleton/index/record",
                "complete second scan and exact snapshot comparison",
                "fresh funds check",
                "verified single first-empty write of 38",
                "one native deduction",
            ],
        )
        messages = raw["result_messages"]
        self.assertEqual(messages["no_charge_suffix"], NO_DEDUCTION)
        self.assertIn(NO_DEDUCTION, messages["invalid_selection_text"])
        self.assertIn("canceled", messages["distinct"])
        self.assertIn("insufficient_funds", messages["distinct"])

    def test_vv5_selected_villager_route_has_complete_buy_contract(self) -> None:
        raw = load("vv5_full_mastery_all_candidate.json")
        tx = raw["transaction_contract"]["individual_transaction"]
        self.assertEqual(tx["price"], 100000)
        self.assertEqual(tx["route_offset"], "0xDB766")
        self.assertTrue(tx["reacquire_same_index"])
        self.assertIn("selected-Believer", raw["description"])
        self.assertIn("No tech points have been deducted.", tx["no_deduction_text"])
        self.assertIn("postverify", tx)
        self.assertIn("before 0x4237B0 deduction", tx["postverify"])

    def test_other_games_do_not_claim_an_unproven_individual_route(self) -> None:
        vv1 = load("vv1_full_mastery_all_candidate.json")
        vv2 = load("vv2_full_mastery_all_candidate.json")
        vv4 = load("vv4_full_heal_cure_all_candidate.json")
        self.assertNotIn("individual_transaction", vv1["transaction_contract"])
        self.assertNotIn("individual_transaction", vv2["transaction_contract"])
        self.assertNotIn("individual_transaction", vv4["transaction"])

    def test_vv5_no_charge_contract_is_not_silent(self) -> None:
        raw = load("vv5_full_mastery_all_candidate.json")
        text = json.dumps(raw)
        self.assertIn(NO_DEDUCTION, text)
        self.assertIn("reacquire_same_index", text)
        self.assertIn("postverify", text.casefold())


if __name__ == "__main__":
    unittest.main()
