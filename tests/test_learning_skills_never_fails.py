"""Exact-build guard for the narrowly scoped skill-success branches."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from capstone import Cs, CS_ARCH_X86, CS_MODE_32

ROOT = Path(__file__).resolve().parents[1]

STOCK = {
    "vv1": ROOT / "research/stock-executables/Virtual Villagers - A New Home.exe",
    "vv2": ROOT / "research/stock-executables/Virtual Villagers - The Lost Children.exe",
    "vv3": ROOT / "research/stock-executables/Virtual Villagers - The Secret City.exe",
    "vv4": ROOT / "research/stock-executables/Virtual Villagers - The Tree of Life.exe",
    "vv5": ROOT / "research/stock-executables/Virtual Villagers - New Believers.exe",
}


class LearningSkillsNeverFailsTests(unittest.TestCase):
    def test_manifest_has_one_complete_entry_per_game(self) -> None:
        manifest = json.loads((ROOT / "data/builds.json").read_text(encoding="utf-8"))
        entries = {
            item["game_id"]: item
            for item in manifest["fun_patches"]
            if item["id"].endswith("_learning_never_fails")
        }
        self.assertEqual(set(entries), set(STOCK))
        self.assertEqual(len(entries["vv5"]["patches"]), 6)
        for game_id, entry in entries.items():
            self.assertEqual(entry["name"], "Learning Skills Never Fails")
            self.assertEqual(len(entry["patches"]), 5 if game_id != "vv5" else 6)
            for patch in entry["patches"]:
                self.assertNotEqual(patch["before"], patch["after"])

    def test_each_stock_executable_has_the_pinned_branch_preimage(self) -> None:
        manifest = json.loads((ROOT / "data/builds.json").read_text(encoding="utf-8"))
        for entry in manifest["fun_patches"]:
            if not entry["id"].endswith("_learning_never_fails"):
                continue
            data = STOCK[entry["game_id"]].read_bytes()
            for patch in entry["patches"]:
                offset = int(patch["offset"], 0)
                before = bytes.fromhex(patch["before"])
                after = bytes.fromhex(patch["after"])
                self.assertEqual(data[offset : offset + len(before)], before, patch)
                mutated = bytearray(data)
                mutated[offset : offset + len(before)] = after
                self.assertNotEqual(mutated, data)
                self.assertEqual(mutated[offset : offset + len(before)], after)
                self.assertNotEqual(mutated[offset : offset + len(before)], before)
                mutated[offset : offset + len(before)] = before
                self.assertEqual(mutated, data)

    def test_patch_bytes_decode_to_the_intended_control_flow(self) -> None:
        """Pin decoded branch targets, not merely byte-shaped replacements."""
        manifest = json.loads((ROOT / "data/builds.json").read_text(encoding="utf-8"))
        decoder = Cs(CS_ARCH_X86, CS_MODE_32)
        decoder.detail = True
        for entry in manifest["fun_patches"]:
            if not entry["id"].endswith("_learning_never_fails"):
                continue
            data = STOCK[entry["game_id"]].read_bytes()
            for patch in entry["patches"]:
                offset = int(patch["offset"], 0)
                before = bytes.fromhex(patch["before"])
                after = bytes.fromhex(patch["after"])
                address = 0x400000 + offset
                before_instructions = list(decoder.disasm(before, address))
                after_instructions = list(decoder.disasm(after, address))
                self.assertTrue(before_instructions, patch)
                self.assertTrue(after_instructions, patch)
                original = before_instructions[0]
                if entry["game_id"] == "vv1" and offset == 0x3D7F8:
                    self.assertEqual(original.mnemonic, "jg", patch)
                    self.assertEqual(after, b"\x90" * 6, patch)
                    self.assertTrue(all(instruction.mnemonic == "nop" for instruction in after_instructions), patch)
                    continue
                self.assertIn(original.mnemonic, {"jle", "jge"}, patch)
                replacement = after_instructions[0]
                self.assertEqual(replacement.mnemonic, "jmp", patch)
                self.assertEqual(replacement.operands[0].imm, original.operands[0].imm, patch)


if __name__ == "__main__":
    unittest.main()
