"""The Tree of Life's island events in the Game Mechanics window (src/vv_game_mechanics_events_vv4.py): the catalog
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
import vv_game_mechanics_events_vv4 as vv4  # noqa: E402

GAME = 4


@unittest.skipUnless(exe.available(GAME), "the stock Tree of Life exe or capstone/pefile is absent")
class TheCodeSaysSo(unittest.TestCase):
    def setUp(self) -> None:
        self.exe = exe.exe(GAME)

    def assert_at(self, address: int, instruction: str) -> None:
        self.assertEqual(self.exe.instruction(address), instruction, hex(address))

    def test_amounts(self) -> None:
        self.assert_at(0x414730, "mov dword ptr [ecx + 8], 0x64")        # the mold: 100 food
        self.assert_at(0x414930, "mov dword ptr [ecx + 8], 0x12c")       # footprints: 300 food
        self.assert_at(0x414A00, "mov dword ptr [ecx + 8], 0x7d0")       # footprints: 2,000 tech
        self.assert_at(0x414B38, "add dword ptr [eax + 0x170f8], 0x15e")  # a closer look: 350 berries
        self.assert_at(0x414C6D, "push 0x32")                            # the wasps: 50% ...
        self.assert_at(0x414EC4, "push 0x14")                            # the glum tree: 20% sick
        self.assert_at(0x4152ED, "push 0x50")                            # the crab: 80% Healing
        self.assert_at(0x4158FD, "push -0x32")                           # the climber: -50 health
        self.assert_at(0x41585A, "mov dword ptr [esp + 4], 0xbb8")       # the calabash: +3,000
        self.assert_at(0x415D7F, "mov dword ptr [esp + 4], 0x1388")      # the sealed box: +5,000
        self.assert_at(0x416799, "cmp eax, 0x3c")                        # innovation: the 60% coin
        self.assert_at(0x416A6D, "push -0x4b")                           # tough lessons: -75 health

    def test_buttons_are_the_games(self) -> None:
        for sid, words in ((0x34E, "Run to the left side"), (0x392, "Swim back with the box"),
                           (0x3E3, "Teach kids sharing"), (0x3E9, "How should we care for our people?")):
            self.assertEqual(exe.text(GAME, sid), words)


class Rendering(unittest.TestCase):
    def test_every_event_is_shown_with_real_life_units(self) -> None:
        facts = [f for f in gm.general(GAME) if f.group == "Island events"]
        text = " ".join(f.text for f in facts)
        for event in vv4.EVENTS:
            self.assertIn(event.title, text)
        for m in re.finditer(r"\b\d[\d,.]* (seconds?|minutes?|hours?)\b", text):
            self.assertRegex(text[max(0, m.start() - 60):m.end() + 60], r"real-life", m.group(0))
        for dead in ("The Tsunami", "The Canoe from the Other Side", "The Medical Emergency", "The Return of Biggles"):
            self.assertNotIn(dead, text)


if __name__ == "__main__":
    unittest.main()
