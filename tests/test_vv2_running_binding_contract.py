from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BINDING = ROOT / "data" / "candidates" / "vv2_individual_grant_running_binding.json"


def load_binding() -> dict[str, object]:
    return json.loads(BINDING.read_text(encoding="utf-8"))


def plan(binding: dict[str, object], likes: list[int], dislikes: list[int]) -> dict[str, object]:
    slots = binding["preference_slots"]
    assert isinstance(slots, dict)
    running = int(slots["running_id"])
    empty = int(slots["empty_id"])
    assert len(likes) == int(slots["like_slots"]["count"])
    assert len(dislikes) == int(slots["dislike_slots"]["count"])
    if running in likes:
        return {"status": "no_change", "writes": [], "charge": 0, "likes": likes[:], "dislikes": dislikes[:]}
    destination = next((index for index, value in enumerate(likes) if value == empty), None)
    if destination is None:
        return {"status": "no_change", "writes": [], "charge": 0, "likes": likes[:], "dislikes": dislikes[:]}
    after_likes = likes[:]
    after_likes[destination] = running
    after_dislikes = dislikes[:]
    dislike_writes = []
    for index, value in enumerate(dislikes):
        if value == running:
            after_dislikes[index] = empty
            dislike_writes.append(index)
    return {
        "status": "candidate",
        "writes": [("like", destination)] + [("dislike", index) for index in dislike_writes],
        "charge": int(binding["transaction_contract"]["price"]),
        "likes": after_likes,
        "dislikes": after_dislikes,
    }


class VV2RunningBindingContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.binding = load_binding()

    def test_exact_build_record_and_complete_physical_arrays(self) -> None:
        raw = self.binding
        self.assertEqual(raw["game_id"], "vv2")
        self.assertEqual(raw["exact_build"]["sha256"], "46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677")
        self.assertEqual(raw["record_identity"]["record_stride"], "0xE48C")
        slots = raw["preference_slots"]
        self.assertEqual(slots["running_id"], 38)
        self.assertEqual(slots["empty_id"], -1)
        for name, first, last in (("like_slots", 0x5F0, 0x6E4), ("dislike_slots", 0x6E8, 0x7DC)):
            section = slots[name]
            self.assertEqual(section["count"], 62)
            self.assertEqual(section["slot_stride"], "0x4")
            self.assertEqual(int(section["base_offset"], 0), first)
            self.assertEqual(int(section["last_offset"], 0), last)
            self.assertEqual(first + 4 * (section["count"] - 1), last)
        self.assertIn("every configured physical slot", slots["scan_rule"])
        self.assertIn("never an early terminator", slots["scan_rule"])

    def test_existing_selected_path_and_account_evidence_are_explicit(self) -> None:
        raw = self.binding
        identity = raw["record_identity"]
        self.assertIn("+0x304F0", identity["selected_index"])
        self.assertIn("+0x10", identity["record_pool"])
        self.assertEqual(identity["physical_bound"], 256)
        apis = raw["native_apis"]
        self.assertIn("[ESI+0x0C]", apis["selected_villager_path"])
        self.assertEqual(apis["tech_account"]["balance_field"], "DWORD [state+0x2EADC]")
        self.assertIn("sub_426290", apis["tech_account"]["native_deduction"])
        self.assertIn("thiscall", apis["tech_account"]["native_deduction"])

    def test_already_running_is_whole_record_zero_write_skip(self) -> None:
        likes = [38, 38, 17] + [-1] * 59
        dislikes = [38, 91] + [-1] * 60
        result = plan(self.binding, likes, dislikes)
        self.assertEqual(result["status"], "no_change")
        self.assertEqual(result["writes"], [])
        self.assertEqual(result["charge"], 0)
        self.assertEqual(result["likes"], likes)
        self.assertEqual(result["dislikes"], dislikes)

    def test_first_physical_empty_like_is_destination_and_clears_running_dislikes(self) -> None:
        likes = [17, -1, 19] + [23] * 59
        dislikes = [38, 91, 38] + [-1] * 59
        result = plan(self.binding, likes, dislikes)
        self.assertEqual(result["status"], "candidate")
        self.assertEqual(result["writes"], [("like", 1), ("dislike", 0), ("dislike", 2)])
        self.assertEqual(result["charge"], 40000)
        self.assertEqual(result["likes"][1], 38)
        self.assertEqual(result["dislikes"][0], -1)
        self.assertEqual(result["dislikes"][2], -1)
        self.assertEqual(result["likes"][0], likes[0])
        self.assertEqual(result["likes"][2:], likes[2:])
        self.assertEqual(result["dislikes"][1], dislikes[1])
        self.assertEqual(result["dislikes"][3:], dislikes[3:])

    def test_full_likes_is_zero_write_no_charge_and_dislikes_unchanged(self) -> None:
        likes = [17] * 62
        dislikes = [38, 91] + [-1] * 60
        result = plan(self.binding, likes, dislikes)
        self.assertEqual(result["status"], "no_change")
        self.assertEqual(result["writes"], [])
        self.assertEqual(result["charge"], 0)
        self.assertEqual(result["likes"], likes)
        self.assertEqual(result["dislikes"], dislikes)

    def test_transaction_text_and_fail_closed_status(self) -> None:
        raw = self.binding
        transaction = raw["transaction_contract"]
        for key in ("dry_run", "confirm", "reacquire", "postverify", "one_charge", "rollback_limit"):
            self.assertTrue(transaction[key], key)
        self.assertIn("dry-run", transaction["dry_run"])
        self.assertIn("IDOK", transaction["confirm"])
        self.assertIn("reacquire", transaction["reacquire"])
        self.assertIn("read back", transaction["postverify"])
        self.assertIn("exactly once", transaction["one_charge"])
        self.assertIn("rollback", transaction["rollback_limit"].casefold())
        self.assertEqual(raw["native_apis"]["preference_write"]["status"], "UNPROVED")
        self.assertIn("FAIL-CLOSED STOP", raw["native_abi_proof_status"])
        self.assertFalse(raw["enabled"])
        self.assertFalse(raw["catalog_enabled"])
        self.assertTrue(raw["catalog_hidden"])
        self.assertEqual(raw["status"], "STOP")

    def test_vv5_faction_gate_is_explicitly_not_applicable(self) -> None:
        gate = self.binding["vv5_faction_gate"]
        self.assertFalse(gate["applies"])
        self.assertIn("not applicable", gate["status"])


if __name__ == "__main__":
    unittest.main()
