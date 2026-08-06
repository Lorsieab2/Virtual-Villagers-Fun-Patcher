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

    def test_vv5_running_candidate_is_isolated_and_disabled(self) -> None:
        raw = load("vv5_individual_running_candidate.json")
        self.assertFalse(raw["enabled"])
        self.assertTrue(raw["catalog_hidden"])
        self.assertFalse(raw["catalog_enabled"])
        self.assertEqual(raw["unsupported_patch_modes"], ["experimental_expanded_256", "experimental_expanded_256_progression"])
        self.assertEqual(raw["dependencies"], ["vv5_full_mastery_all_stage_a_candidate"])
        tx = raw["transaction_contract"]
        self.assertEqual({k: tx[k] for k in ("command", "price", "action", "repeatable", "ownership", "remove")},
                         {"command": 2, "price": 40000, "action": "Buy", "repeatable": True, "ownership": None, "remove": False})
        self.assertEqual(tx["likes"], ["record+0x1F5C", "record+0x1F60", "record+0x1F64"])
        self.assertIn("first physical -1", tx["dry_run"])
        self.assertIn("Dislikes", tx["forbidden_reads"])
        self.assertIn(NO_DEDUCTION, tx["no_deduction"])
        self.assertEqual(raw["parent_hashes"]["collection_progression"], "857E22D7C361B802508BF789C3CC486E42E76021F5AA579BB1D16CC6E0D017A0")
        self.assertEqual(raw["parent_hashes"]["immediate_fixed"], "E93822F752F730ECB751EBAA87021194C992984721B4370FF0015D5FC4BB2E9A")
        self.assertEqual(raw["pe_append_transaction"]["section"], ".vv5run")
        self.assertIsNone(raw["provenance"]["implementation_commit"])

    def test_vv5_running_builder_has_command2_and_no_dislikes_offsets(self) -> None:
        source = (ROOT / "scripts" / "build_vv5_full_mastery_candidate.py").read_text(encoding="utf-8")
        self.assertIn("cmp ebx, 2", source)
        self.assertIn("0x1F5C", source)
        self.assertIn("0x1F60", source)
        self.assertIn("0x1F64", source)
        self.assertIn("push -40000", source)
        self.assertNotIn("0x1F68", source)
        self.assertNotIn("0x1F6C", source)

    def test_vv5_running_emitted_helper_snapshots_all_likes_and_deducts_once(self) -> None:
        raw = load("vv5_individual_running_candidate_map.json")
        helper = bytes.fromhex(raw["slot"]["running_helper_bytes"])
        self.assertIn(bytes.fromhex("89 44 BD E0"), helper)
        self.assertIn(bytes.fromhex("3B 45 E0"), helper)
        self.assertIn(bytes.fromhex("3B 45 DC"), helper)
        self.assertIn(bytes.fromhex("3B 45 D8"), helper)
        self.assertEqual(helper.count(bytes.fromhex("68 C0 63 FF FF")), 1)
        self.assertNotIn(bytes.fromhex("1F68"), helper)


if __name__ == "__main__":
    unittest.main()
