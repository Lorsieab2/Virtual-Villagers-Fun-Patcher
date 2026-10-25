"""A New Home's island events in the Game Mechanics window (src/vv_game_mechanics_events_vv1.py): the catalog's
odds and amounts against the stock executable's own code, its button words against the exe's string table, and
the rendering (patch lines only when the patch is in the game; the general rules page keeps every line)."""
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
import vv_game_mechanics_events_vv1 as vv1  # noqa: E402

GAME = 1


@unittest.skipUnless(exe.available(GAME), "the stock A New Home exe or capstone/pefile is absent")
class TheCodeSaysSo(unittest.TestCase):
    def setUp(self) -> None:
        self.exe = exe.exe(GAME)

    def assert_at(self, address: int, instruction: str) -> None:
        self.assertEqual(self.exe.instruction(address), instruction, hex(address))

    def test_the_family_weights(self) -> None:
        self.assert_at(0x423820, "cmp eax, 0x14")                       # 20% encounters
        self.assert_at(0x42382C, "cmp dword ptr [eax + 0x9e40], ebx")   # the first event is always one
        self.assert_at(0x423842, "cmp eax, 0x32")                       # then 50/50 island or crate
        self.assert_at(0x423876, "push 0xc")                            # 12 + rand(12) hours
        self.assert_at(0x423883, "add eax, 0xc")
        self.assert_at(0x423886, "imul eax, eax, 0xe10")

    def test_the_island_table_has_14_live_cases(self) -> None:
        self.assert_at(0x4284E7, "cmp edi, 0xe")
        checks = self.exe.bytes_at(0x4286A0, 15)
        handlers = self.exe.u32(0x428688, 6)
        self.assertEqual(handlers[checks[1]], 0x4284D6, "A Mighty Storm maps to the re-roll")
        self.assertEqual(sum(1 for c in checks if handlers[c] != 0x4284D6), vv1.ISLAND)

    def test_the_encounter_table_has_15_live_variants(self) -> None:
        self.assert_at(0x418930, "push 0x10")
        classes = self.exe.bytes_at(0x4189A4, 16)
        self.assertEqual(classes[5], 4, "The Furry Food's class is the re-roll")
        self.assertEqual(self.exe.u32(0x418990 + 16)[0], 0x418930)
        self.assertEqual(sum(1 for c in classes if c != 4), vv1.ENCOUNTER)

    def test_the_crate_draws(self) -> None:
        self.assert_at(0x42B014, "cmp eax, 0x21")
        self.assert_at(0x42B02D, "cmp eax, 0x43")
        self.assert_at(0x42B03C, "push 9")

    def test_a_sample_of_results(self) -> None:
        for address in (0x4194C4, 0x4196F5, 0x419961, 0x419C5E, 0x419E82):
            self.assert_at(address, "cmp eax, 0x32")                    # every 50/50 (51/49) roll
        self.assert_at(0x427CDA, "imul edi, edi, 0x384")                # 900 x n tech lost
        self.assert_at(0x428168, "imul edi, edi, 0x384")                # 900 x n tech gained
        self.assert_at(0x4281AE, "imul edi, edi, 0xc8")                 # 200 x n food
        self.assert_at(0x427F14, "imul ecx, ecx, 0xffffff38")           # -200 x n bush
        self.assert_at(0x427F90, "lea edi, [eax + eax*4]")              # 80 x n (x5, << 4)
        self.assert_at(0x428395, "imul edi, edi, 0x64")                 # 100 x n
        self.assert_at(0x428409, "imul ecx, ecx, 0x12c")                # 300 x n
        self.assert_at(0x4280C4, "imul eax, eax, -0xa")                 # 10 food a villager
        self.assert_at(0x419889, "push 0x4b")                           # 75% sick
        self.assert_at(0x419DB1, "add edx, -0x32")                      # -50 health
        self.assert_at(0x42C842, "add ecx, -0x28")                      # old fruit -40 / -70 / -110
        self.assert_at(0x42C777, "add ecx, -0x46")
        self.assert_at(0x42C6A2, "add ecx, -0x6e")
        self.assert_at(0x42CA5F, "push 5")                              # one of 5 skills
        self.assert_at(0x43C70C, "mov dword ptr [esi + 0x344], 0x5a")   # a new villager's 90 health

    def test_the_pickers_never_test_for_the_golden_child(self) -> None:
        listing = " ".join(f"{m} {o}" for _a, m, o in self.exe.disasm(0x43BCD0, 0x43BFE0))
        self.assertNotIn("0x36c", listing)
        self.assertNotIn("0xc7", listing)

    def test_burial_and_vanishing_clear_only_the_present_byte(self) -> None:
        self.assert_at(0x448F65, "mov byte ptr [ecx + edi + 0x28], 0")   # a skeleton picked up for burial
        self.assert_at(0x42E9C3, "mov byte ptr [edi + eax + 0x28], 0")   # an unburied body removed
        self.assert_at(0x41979D, "mov byte ptr [edx + eax + 0x28], bl")  # The Mysterious Face
        self.assert_at(0x41A272, "mov byte ptr [ecx + edx + 0x28], bl")  # The Book


class TheRendering(exe.CatalogChecks, unittest.TestCase):
    GAME = GAME
    CATALOG = vv1

    def test_the_patched_lines(self) -> None:
        patched = gm.render(events.facts(exe.village(GAME, {vv1.RESTORE, vv1.FIX})))
        self.assertIn("A Mighty Storm --", patched)
        self.assertIn("The Furry Food --", patched)
        self.assertIn('With the patcher\'s "Fix Vanilla Bugs" (in this game)', patched)

    def test_the_golden_child_line_is_the_owners(self) -> None:
        import vv_game_mechanics_vv1 as module
        line = next(text for text, ok in module.HIDDEN_LINES if "can die or be lost in island events" in text)
        self.assertEqual(dict(module.HIDDEN_LINES)[line], gm.OWNER)


if __name__ == "__main__":
    unittest.main()
