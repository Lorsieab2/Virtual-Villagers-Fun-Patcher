"""The Lost Children's island events and Gong of Wonder in the Game Mechanics window
(src/vv_game_mechanics_events_vv2.py): the catalog against the stock executable's own code and string table, and
its rendering."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import island_event_exe as exe  # noqa: E402
import vv_game_mechanics as gm  # noqa: E402
import vv_game_mechanics_events as events  # noqa: E402
import vv_game_mechanics_events_vv2 as vv2  # noqa: E402

GAME = 2


@unittest.skipUnless(exe.available(GAME), "the stock Lost Children exe or capstone/pefile is absent")
class TheCodeSaysSo(unittest.TestCase):
    def setUp(self) -> None:
        self.exe = exe.exe(GAME)

    def assert_at(self, address: int, instruction: str) -> None:
        self.assertEqual(self.exe.instruction(address), instruction, hex(address))

    def test_the_tables(self) -> None:
        self.assert_at(0x433604, "cmp eax, 0x1b")                        # 28 single-result bodies
        bodies = self.exe.u32(0x4344F4, 28)
        self.assertEqual(bodies[4], 0x4344ED, "case 4 has no body")
        self.assert_at(0x4204C7, "cmp eax, 0x14")                        # 21 two-choice results
        self.assertEqual(len(set(self.exe.u32(0x422264, 21))), 21)
        self.assertEqual(len(self.exe.u32(0x439D0C, 8)), vv2.SACK)

    def test_the_amount_factors(self) -> None:
        self.assert_at(0x4335AE, "cmp eax, 0x32")                        # single-result: x3 above 50 ...
        self.assert_at(0x4335C9, "cmp eax, 0x32")                        # ... and the x2 test repeats 50
        self.assert_at(0x41F72E, "cmp eax, 0x32")                        # two-choice: x3 above 50
        self.assert_at(0x41F749, "cmp eax, 0x19")                        # x2 above 25

    def test_a_sample_of_results(self) -> None:
        self.assert_at(0x43364C, "shr esi, 2")                           # the parrot takes a quarter
        self.assert_at(0x43369C, "mov eax, 0x2ee")                       # the flood leaves 750
        self.assert_at(0x433DF7, "push 0x50")                            # the Epidemic 80%
        self.assert_at(0x433D0F, "push 0x3c")                            # Rats! -60 health
        self.assert_at(0x433D13, "push 0x28")                            # ... at 40%
        self.assert_at(0x433E62, "cmp esi, 8")                           # A Dangerous Mission: 8 leave
        self.assert_at(0x4344E4, "push 0x23")                            # the Mother Parrot 35%
        self.assert_at(0x420A86, "cmp eax, 0x32")                        # the voices 50/50
        self.assert_at(0x421B95, "push 6")                               # the hole: 1 in 6
        self.assert_at(0x421E7D, "mov dword ptr [ecx + 0x2ea94], 2")     # the spyglass kept
        self.assert_at(0x421345, "push 0x14")                            # the dragonflies 20%
        self.assert_at(0x44D467, "mov dword ptr [esi + 0x52c], ebx")     # a statue's health 0

    def test_the_gong(self) -> None:
        self.assert_at(0x461B58, "add eax, 0x15180")                     # a rest of 86,400 seconds
        self.assert_at(0x44E8A4, "push 0x64")
        self.assert_at(0x44EBBE, "push 0x64")
        self.assert_at(0x44ECDD, "add eax, 0x3c")                        # luck: the next event in 60 s


class TheRendering(exe.CatalogChecks, unittest.TestCase):
    GAME = GAME
    CATALOG = vv2

    def test_the_patched_lines(self) -> None:
        patched = gm.render(events.facts(exe.village(GAME, {vv2.RESTORE, vv2.FIX, vv2.GONG_FIX})))
        self.assertIn("The Mosquito Swarm --", patched)
        self.assertIn('With the patcher\'s "Fix Vanilla Bugs" (in this game)', patched)
        self.assertIn("they add 30 to the coconut trees", patched)
        # The green vial: the normal game's man's 0 to 28 first, the fix's 0 to 29 only with the row.
        vial = "a man gets one of heads 0 to 29 too"
        self.assertIn(vial, patched)
        self.assertLess(patched.index("a man gets one of heads 0 to 28"), patched.index(vial))
        self.assertNotIn(vial, gm.render(events.facts(exe.village(GAME, {vv2.RESTORE}))))

    def test_the_gong_heading(self) -> None:
        general = gm.render(gm.general(GAME))
        self.assertIn("Gong of Wonder --", general)


if __name__ == "__main__":
    unittest.main()
