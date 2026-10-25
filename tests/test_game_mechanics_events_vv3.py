"""The Secret City's island events in the Game Mechanics window (src/vv_game_mechanics_events_vv3.py): the catalog
against the stock executable's own code and string table, and its rendering."""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import island_event_exe as exe  # noqa: E402
import vv_game_mechanics as gm  # noqa: E402
import vv_game_mechanics_events_vv3 as vv3  # noqa: E402

GAME = 3


@unittest.skipUnless(exe.available(GAME), "the stock Secret City exe or capstone/pefile is absent")
class TheCodeSaysSo(unittest.TestCase):
    def setUp(self) -> None:
        self.exe = exe.exe(GAME)

    def assert_at(self, address: int, instruction: str) -> None:
        self.assertEqual(self.exe.instruction(address), instruction, hex(address))

    def test_amounts(self) -> None:
        self.assert_at(0x414B32, "push 0xf")                             # the tsunami: 15% each
        self.assert_at(0x414BF9, "push 0x32")                            # the science fair: 50% each ...
        self.assert_at(0x414BF5, "push 0xa")                             # ... +10 to 19
        self.assert_at(0x415487, "cmp eax, 0x4b")                        # the daredevil: 75% swoon
        self.assert_at(0x417237, "cmp eax, 0x32")                        # the medical emergency: 50%
        self.assert_at(0x415050, "push 0x1f4")                           # the miraculous bloom: honey 500

class Rendering(unittest.TestCase):
    def test_every_event_is_shown_with_real_life_units(self) -> None:
        facts = [f for f in gm.general(GAME) if f.group == "Island events"]
        text = " ".join(f.text for f in facts)
        for event in vv3.EVENTS:
            self.assertIn(event.title, text)
        for m in re.finditer(r"\b\d[\d,.]* (seconds?|minutes?|hours?)\b", text):
            self.assertRegex(text[max(0, m.start() - 60):m.end() + 60], r"real-life", m.group(0))


if __name__ == "__main__":
    unittest.main()
