from __future__ import annotations

import json
import unittest
from pathlib import Path


BINDING = Path(__file__).resolve().parents[1] / "data/candidates/vv3_individual_grant_running_binding.json"


class VV3RunningBindingContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.binding = json.loads(BINDING.read_text(encoding="utf-8"))

    def test_exact_build_record_identity_and_bound(self) -> None:
        self.assertEqual(self.binding["exact_build"]["sha256"], "8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503")
        self.assertEqual(self.binding["exact_build"]["size"], 831488)
        record = self.binding["record_identity"]
        self.assertEqual(record["first_record_va"], "0x59E124")
        self.assertEqual(record["stride"], "0x1F8C")
        self.assertEqual(record["selected_index"]["bound_exclusive"], 150)

    def test_complete_configured_physical_like_dislike_arrays(self) -> None:
        slots = self.binding["preference_slots"]
        self.assertIn("complete configured physical Like and Dislike arrays", slots["scan"])
        self.assertEqual(slots["like"]["count"], len(slots["like"]["offsets"]))
        self.assertEqual(slots["dislike"]["count"], len(slots["dislike"]["offsets"]))
        self.assertGreaterEqual(slots["like"]["count"], 3)
        self.assertGreaterEqual(slots["dislike"]["count"], 3)
        self.assertEqual(slots["like"]["offsets"], ["0xFB4", "0xFB8", "0xFBC"])
        self.assertEqual(slots["dislike"]["offsets"], ["0xFC0", "0xFC4", "0xFC8"])
        self.assertFalse(slots["like"]["extra_persisted_slots_proven"])
        self.assertFalse(slots["dislike"]["extra_persisted_slots_proven"])

    def test_running_and_atomic_preference_semantics(self) -> None:
        self.assertEqual(self.binding["running"]["id"], 38)
        semantics = self.binding["transaction_contract"]["semantics"]
        already = semantics["already_running"]
        self.assertEqual(already["preference_writes"], 0)
        self.assertEqual(already["charge"], 0)
        self.assertEqual(already["action"], "whole-record skip")
        self.assertIn("duplicate Running Likes", " ".join(already["preserve"]))
        self.assertIn("every Dislike", " ".join(already["preserve"]))

        destination = semantics["destination"]
        self.assertIn("first physical Like", destination["condition"])
        self.assertIn("first physical -1 Like only", destination["write"])
        self.assertEqual(destination["running_like_writes"], 1)
        self.assertTrue(destination["dislike_clear_allowed"])

        no_destination = semantics["no_destination"]
        self.assertEqual(no_destination["preference_writes"], 0)
        self.assertEqual(no_destination["charge"], 0)
        self.assertFalse(no_destination["dislike_clear"])
        self.assertIn("Dislikes unchanged", no_destination["preserve"])

        cleared = semantics["dislike_clear"]
        self.assertIn("only after a destination", cleared["condition"])
        self.assertTrue(cleared["clear_every_running_dislike"])
        self.assertTrue(cleared["unrelated_slots_preserved"])

    def test_transaction_text_and_rollback_limit_are_present(self) -> None:
        contract = self.binding["transaction_contract"]
        transaction_text = " ".join(contract["steps"]) + " " + contract["transaction_text"]
        for term in ("dry-run", "confirm", "reacquire", "postverify", "one charge"):
            self.assertIn(term, transaction_text)
        self.assertIn("rollback", self.binding["rollback_limit"].lower())
        self.assertEqual(contract["price"], 40000)
        self.assertEqual(contract["action"], "Buy")
        self.assertEqual(contract["message_box"]["accept_result"], 1)
        self.assertEqual(contract["message_box"]["cancel_result"], 2)

    def test_eligibility_abi_and_catalog_are_fail_closed(self) -> None:
        self.assertIn("active +0xF10 != 0", self.binding["eligibility"]["gate"])
        self.assertIn("signed health +0xE78 > 0", self.binding["eligibility"]["gate"])
        abi = self.binding["native_abi"]
        self.assertEqual(abi["status"], "unproved")
        self.assertFalse(abi["complete_preference_write_abi_proved"])
        self.assertTrue(abi["fail_closed"])
        self.assertEqual(self.binding["status"], "STOP")
        self.assertFalse(self.binding["enabled"])
        self.assertFalse(self.binding["catalog_enabled"])
        self.assertTrue(self.binding["catalog_hidden"])

    def test_vv5_faction_gate_is_explicitly_not_applicable(self) -> None:
        gate = self.binding["vv5_faction_gate"]
        self.assertFalse(gate["applicable"])
        self.assertIn("+0x1CEC != 0", gate["text"])
        self.assertIn("+0x1CE1", gate["text"])


if __name__ == "__main__":
    unittest.main()
