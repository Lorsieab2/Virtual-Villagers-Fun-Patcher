from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BINDING = ROOT / "data" / "candidates" / "vv4_individual_grant_running_binding.json"


def load_binding() -> dict[str, object]:
    return json.loads(BINDING.read_text(encoding="utf-8"))


def plan(binding: dict[str, object], likes: list[int], dislikes: list[int]) -> tuple[str, list[int], list[int], int]:
    preferences = binding["preferences"]
    transaction = binding["transaction_contract"]
    running = preferences["running_id"]
    empty = preferences["like_slots"]["empty_value"]
    policy = transaction["policy"]
    if running in likes and policy["running_like"]["zero_write_no_charge_whole_record_skip"]:
        return "skip_already_running", likes[:], dislikes[:], 0
    if empty not in likes and policy["destination"]["no_empty_like_zero_write_no_charge"]:
        return "skip_no_destination", likes[:], dislikes[:], 0
    destination = likes.index(empty)
    updated_likes = likes[:]
    updated_likes[destination] = running
    updated_dislikes = [
        empty if value == running else value
        for value in dislikes
    ]
    return "write", updated_likes, updated_dislikes, transaction["price"]


class VV4RunningBindingContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.binding = load_binding()

    def test_exact_build_and_fail_closed_catalog_state(self) -> None:
        self.assertEqual(self.binding["fingerprint"], {
            "input_name": "Virtual Villagers - The Tree of Life.exe",
            "size": 929792,
            "sha256": "6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220",
        })
        self.assertEqual(self.binding["status"], "STOP")
        self.assertFalse(self.binding["enabled"])
        self.assertFalse(self.binding["catalog_enabled"])
        self.assertTrue(self.binding["catalog_hidden"])

    def test_record_identity_stride_and_complete_physical_arrays(self) -> None:
        record = self.binding["record_identity"]
        self.assertEqual(record["selected_index"], "GameState+0x94640")
        self.assertEqual(record["validator"], "sub_467980")
        self.assertEqual(record["resolver"], "sub_466040")
        self.assertEqual(record["stride"], "0x2E3C")
        self.assertEqual(record["physical_index_range"], "0..149")

        preferences = self.binding["preferences"]
        self.assertEqual(preferences["running_id"], 38)
        for name, expected in (
            ("like_slots", [0x1E60, 0x1E64, 0x1E68]),
            ("dislike_slots", [0x1E6C, 0x1E70, 0x1E74]),
        ):
            slots = preferences[name]
            self.assertEqual(slots["count"], 3)
            self.assertEqual([int(offset, 0) for offset in slots["offsets"]], expected)
            self.assertEqual(slots["slot_stride"], "0x4")
        self.assertEqual(preferences["additional_persisted_slots"], {"proven": False, "like": [], "dislike": []})

    def test_eligibility_and_vv5_gate_are_explicit(self) -> None:
        self.assertEqual(self.binding["eligibility_gate"], [
            "selected index passes sub_467980 and is signed 0..149",
            "byte record+0x1CC4 != 0 (active)",
            "byte record+0x1CC7 == 0 (status gate)",
            "signed dword record+0x1C40 > 0 (living)",
        ])
        self.assertFalse(self.binding["vv5_faction_gate"]["applicable"])

    def test_running_like_is_whole_record_zero_write_skip(self) -> None:
        likes = [38, 38, 7]
        dislikes = [38, 9, -1]
        self.assertEqual(plan(self.binding, likes, dislikes), ("skip_already_running", likes, dislikes, 0))

    def test_first_empty_like_is_destination_and_clears_only_running_dislikes(self) -> None:
        likes = [7, -1, -1]
        dislikes = [38, 9, 11]
        status, updated_likes, updated_dislikes, charge = plan(self.binding, likes, dislikes)
        self.assertEqual((status, updated_likes, updated_dislikes, charge), ("write", [7, 38, -1], [-1, 9, 11], 40000))

    def test_no_empty_like_is_zero_write_and_preserves_dislikes(self) -> None:
        likes = [7, 8, 9]
        dislikes = [38, 9, 11]
        self.assertEqual(plan(self.binding, likes, dislikes), ("skip_no_destination", likes, dislikes, 0))

    def test_transaction_text_and_native_abi_are_fail_closed(self) -> None:
        transaction = self.binding["transaction_contract"]
        self.assertEqual({key: transaction[key] for key in ("command", "action", "price", "repeatable", "ownership", "remove")},
                         {"command": 2, "action": "Buy", "price": 40000, "repeatable": True, "ownership": None, "remove": False})
        text = json.dumps(self.binding).casefold()
        for phrase in ("dry-run", "confirm", "reacquire", "postverify", "one charge", "rollback limit", "no tech points have been deducted"):
            self.assertIn(phrase, text)
        abi = self.binding["native_abi_proof"]
        self.assertEqual(abi["status"], "UNPROVEN")
        self.assertEqual(abi["fail_closed"], "STOP")
        self.assertFalse(abi["complete_preference_write_abi_proven"])
        self.assertIn("sub_46AD80", self.binding["selected_villager_path"]["proven_native_writer"])
        self.assertIn("0x41E300", self.binding["selected_villager_path"]["proven_native_deduction"])


if __name__ == "__main__":
    unittest.main()
