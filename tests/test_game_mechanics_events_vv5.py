"""New Believers' island events in the Game Mechanics window (src/vv_game_mechanics_events_vv5.py): the catalog
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
import vv_game_mechanics_events_vv5 as vv5  # noqa: E402

GAME = 5


@unittest.skipUnless(exe.available(GAME), "the stock New Believers exe or capstone/pefile is absent")
class TheCodeSaysSo(unittest.TestCase):
    def setUp(self) -> None:
        self.exe = exe.exe(GAME)

    def assert_at(self, address: int, instruction: str) -> None:
        self.assertEqual(self.exe.instruction(address), instruction, hex(address))

    def test_amounts(self) -> None:
        self.assert_at(0x414A00, "mov dword ptr [ecx + 8], 0x64")        # the mold: 100 food
        self.assert_at(0x414C10, "mov dword ptr [ecx + 8], 0x12c")       # footprints: 300 food
        self.assert_at(0x414CE0, "mov dword ptr [ecx + 8], 0x7d0")       # footprints: 2,000 tech
        self.assert_at(0x414BD1, "push 0x14")                            # the vision: 20 + rand(20)
        self.assert_at(0x414EF0, "push 0x3e8")                           # the crystals: 2,000 + rand(1,000)
        self.assert_at(0x415070, "push 0x9c4")                           # the critter: -500 - rand(2,500)
        self.assert_at(0x414FB5, "add dword ptr [eax + 0x17d58], 0xc8")  # the river: noni +200
        self.assert_at(0x414E85, "mov dword ptr [eax + 0x17d5c], 0")     # the army ants: no crops
        self.assert_at(0x4152B0, "push -0x37")                           # the heathen barrel: Faith -55
        self.assert_at(0x415528, "cmp eax, 0x32")                        # the newcomer: a Research master
        self.assert_at(0x4156BD, "push -0xf")                            # the bed bugs: -15 health
        self.assert_at(0x4157AD, "push -0xa")                            # the mask: Faith -10
        self.assert_at(0x415DA2, "push -0x14")                           # doubt: -20 Divine Energy
        self.assert_at(0x416B2B, "mov dword ptr [ecx + 0x1b8c], 0x14a")  # the nectar: age 330
        self.assert_at(0x416993, "push 0x14")                            # the defector: Faith 20
        self.assert_at(0x41665C, "fstp dword ptr [eax + 0x1c70]")        # the ruse: Devotion 0

    def test_titles_and_buttons_are_the_games(self) -> None:
        for sid, words in ((0x39D, "Search for the bugs all night"), (0x3A3, "Put it on"),
                           (0x3F3, "Employ a clever ruse"), (0x412, "Drink it")):
            self.assertEqual(exe.text(GAME, sid), words)


class Rendering(unittest.TestCase):
    def test_every_event_is_shown_with_real_life_units(self) -> None:
        facts = [f for f in gm.general(GAME) if f.group == "Island events"]
        text = " ".join(f.text for f in facts)
        for event in vv5.EVENTS:
            self.assertIn(event.title, text)
        self.assertNotIn("belief", text.lower())
        for m in re.finditer(r"\b\d[\d,.]* (seconds?|minutes?|hours?)\b", text):
            self.assertRegex(text[max(0, m.start() - 60):m.end() + 60], r"real-life", m.group(0))
        for dead in ("The Stinging Wasps", "The Return of Biggles", "The Smelly Vial", "The Pretty Shell"):
            self.assertNotIn(dead, text)


if __name__ == "__main__":
    unittest.main()
