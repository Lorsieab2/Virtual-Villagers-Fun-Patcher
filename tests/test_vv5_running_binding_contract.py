import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BINDING = ROOT / "data" / "candidates" / "vv5_individual_grant_running_binding.json"


def load_binding() -> dict:
    return json.loads(BINDING.read_text(encoding="utf-8"))


class VV5RunningBindingContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = load_binding()

    def test_exact_build_record_layout_and_three_physical_arrays(self) -> None:
        self.assertEqual(self.raw["stock_fingerprint"], {
            "filename": "Virtual Villagers - New Believers.exe",
            "size": 991232,
            "sha256": "92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D",
        })
        self.assertEqual(self.raw["record_layout"]["stride"], "0x2F44")
        self.assertIn("same selected physical index and record pointer", self.raw["record_layout"]["identity"])
        self.assertEqual(self.raw["like_slots"]["offsets"], ["0x1F5C", "0x1F60", "0x1F64"])
        self.assertEqual(self.raw["dislike_slots"]["offsets"], ["0x1F68", "0x1F6C", "0x1F70"])
        for key in ("like_slots", "dislike_slots"):
            self.assertEqual(self.raw[key]["count"], 3)
            self.assertTrue(self.raw[key]["complete_physical_array"])
        self.assertEqual(self.raw["running_preference"]["id"], 38)

    def test_faction_gate_precedes_all_preference_access(self) -> None:
        gate = self.raw["eligibility_gate"]
        self.assertEqual(gate["preference_access_order"], "gate before any preference access")
        faction = next(item for item in gate["conditions"] if item["name"] == "current_faction")
        self.assertEqual(faction, {
            "name": "current_faction",
            "offset": "0x1CEC",
            "test": "== 0",
            "meaning": "current believer",
        })
        self.assertTrue(gate["current_faction_is_only_vv5_specific_gate"])
        self.assertNotIn("1CE1", gate["excluded_unproved_gates"])

    def test_preference_mutation_cases_are_zero_write_safe_and_ordered(self) -> None:
        tx = self.raw["transaction_contract"]
        cases = {case["name"]: case for case in tx["cases"]}
        running = cases["running_like_present"]
        self.assertEqual(running["writes"], 0)
        self.assertEqual(running["charge"], 0)
        self.assertTrue(running["whole_record_skip"])
        self.assertTrue(running["preserve_duplicate_likes"])
        self.assertTrue(running["preserve_all_dislikes"])

        destination = cases["destination_available"]
        self.assertEqual(destination["destination"], "first physical -1 Like only, in configured offset order")
        self.assertEqual(destination["like_writes"], 1)
        self.assertIn("only after the destination Like is proven", destination["clear_running_dislikes"])

        empty = cases["no_empty_like"]
        self.assertEqual(empty["writes"], 0)
        self.assertEqual(empty["charge"], 0)
        self.assertEqual(empty["dislikes"], "unchanged")
        self.assertTrue(tx["running_dislike_clear"]["requires_destination_proof"])
        self.assertIn("otherwise clear none", tx["running_dislike_clear"]["rule"])
        self.assertIn("preserve unrelated Like slots", tx["preservation"])
        self.assertIn("unrelated Dislike slots", tx["preservation"])

    def test_transaction_text_contains_all_safety_phases(self) -> None:
        tx = self.raw["transaction_contract"]
        text = json.dumps(tx).casefold()
        for phrase in ("dry-run", "confirmation", "reacquire", "postverify", "one native deduction", "rollback"):
            self.assertIn(phrase, text)
        self.assertIn("No tech points have been deducted.", tx["no_charge_text"])
        self.assertEqual(tx["rollback_limit"], self.raw["rollback_limit"])

    def test_native_abi_is_explicitly_fail_closed(self) -> None:
        proof = self.raw["native_abi_proof"]
        self.assertEqual(proof["status"], "unproved")
        self.assertTrue(proof["fail_closed"])
        self.assertFalse(proof["complete_preference_write_abi_proved"])
        self.assertIn("complete native preference-write ABI", proof["enablement_rule"])
        self.assertEqual(self.raw["status"], "STOP")
        self.assertFalse(self.raw["enabled"])
        self.assertFalse(self.raw["catalog_enabled"])
        self.assertTrue(self.raw["catalog_hidden"])


if __name__ == "__main__":
    unittest.main()
