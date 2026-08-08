"""Static, JSON-only contract checks for the VV1 Running binding."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


BINDING_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "candidates"
    / "vv1_individual_grant_running_binding.json"
)


def load_binding() -> dict:
    with BINDING_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def static_plan(likes: list[int], dislikes: list[int], binding: dict) -> tuple[str, list[int], list[int], int]:
    """Model the closed slot rules without importing implementation code."""
    running = binding["exact_build"]["running_id"]
    empty = binding["slots"]["empty_value"]
    if running in likes:
        return "skip", likes[:], dislikes[:], 0
    destination = next((i for i, value in enumerate(likes) if value == empty), None)
    if destination is None:
        return "skip", likes[:], dislikes[:], 0
    after_likes = likes[:]
    after_dislikes = dislikes[:]
    after_likes[destination] = running
    for i, value in enumerate(after_dislikes):
        if value == running:
            after_dislikes[i] = empty
    return "commit", after_likes, after_dislikes, binding["transaction_contract"]["price"]


class VV1RunningBindingContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.binding = load_binding()
        cls.raw = BINDING_PATH.read_text(encoding="utf-8").lower()

    def test_exact_identity_and_complete_physical_arrays(self) -> None:
        b = self.binding
        self.assertEqual(b["game_id"], "vv1")
        self.assertEqual(b["exact_build"]["sha256"], "1EC790B927741081D5CE13A48FB76983A4FD4336EA08F89317872643760AF03D")
        self.assertEqual(b["record_identity"]["stride"], "0x3D8")
        self.assertEqual(b["record_identity"]["selected_index_offset"], "0xAD34")
        self.assertIn("world identity, selected index, record identity", b["record_identity"]["reacquire_requirement"])
        self.assertEqual(b["exact_build"]["running_id"], 38)
        self.assertEqual(b["slots"]["likes"]["count"], 4)
        self.assertEqual(b["slots"]["dislikes"]["count"], 4)
        self.assertEqual(len(b["slots"]["likes"]["offsets"]), 4)
        self.assertEqual(len(b["slots"]["dislikes"]["offsets"]), 4)
        self.assertEqual(b["slots"]["empty_value"], -1)

    def test_eligibility_gate_is_explicit(self) -> None:
        gate = self.binding["eligibility_gate"]
        self.assertIn("record+0x28 != 0", gate["active"])
        self.assertIn("record+0x344 > 0", gate["living"])
        self.assertIn("0..255", gate["selected_villager"])

    def test_running_like_is_whole_record_zero_write_skip(self) -> None:
        b = self.binding
        likes = [38, 4, 38, 9]
        dislikes = [38, 7, 38, -1]
        status, after_likes, after_dislikes, charge = static_plan(likes, dislikes, b)
        self.assertEqual((status, after_likes, after_dislikes, charge), ("skip", likes, dislikes, 0))

    def test_first_physical_empty_like_then_all_running_dislikes(self) -> None:
        b = self.binding
        likes = [11, -1, 12, 13]
        dislikes = [38, 6, 38, 8]
        status, after_likes, after_dislikes, charge = static_plan(likes, dislikes, b)
        self.assertEqual(status, "commit")
        self.assertEqual(after_likes, [11, 38, 12, 13])
        self.assertEqual(after_dislikes, [-1, 6, -1, 8])
        self.assertEqual(charge, 40000)

    def test_full_likes_are_zero_write_and_preserve_dislikes(self) -> None:
        b = self.binding
        likes = [1, 2, 3, 4]
        dislikes = [38, 6, 7, 38]
        result = static_plan(likes, dislikes, b)
        self.assertEqual(result, ("skip", likes, dislikes, 0))

    def test_contract_mentions_ordered_transaction_safety(self) -> None:
        required = (
            "dry-run",
            "confirmation",
            "reacquire",
            "postverify",
            "one_charge",
            "rollback_limit",
            "no charge",
            "no writes",
            "only after",
            "unrelated slots",
            "duplicate running likes",
        )
        for phrase in required:
            self.assertIn(phrase, self.raw)

    def test_native_abi_is_fail_closed_and_not_catalog_enabled(self) -> None:
        b = self.binding
        proof = b["native_abi_proof_status"]
        self.assertEqual(proof["overall"], "STOP")
        self.assertFalse(proof["preference_write"]["complete"])
        self.assertEqual(proof["preference_write"]["status"], "UNPROVED")
        self.assertEqual(proof["tech_account"]["status"], "UNPROVED")
        self.assertFalse(b["enabled"])
        self.assertFalse(b["catalog_enabled"])
        self.assertTrue(b["catalog_hidden"])
        self.assertEqual(b["status"], "STOP")

    def test_vv5_gate_is_explicitly_not_applicable_to_vv1(self) -> None:
        gate = self.binding["eligibility_gate"]["vv5_faction_gate"]
        self.assertFalse(gate["applicable"])
        if self.binding["game_id"] == "vv5":
            self.assertIn("+0x1CEC == 0", gate["required_if_vv5"])


if __name__ == "__main__":
    unittest.main()
