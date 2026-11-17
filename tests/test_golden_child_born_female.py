"""The Golden Child May Be Born Female (50:50) -- A New Home, an option of "Change Sex and Gender Presentation"
(vv1_golden_child_born_female; the owner, 2026-11-16; native/vvfp_gender_presentation, A NEW HOME: THE GOLDEN
CHILD MAY BE BORN FEMALE).

Every Golden Child comes from the villager creator 0x43C350 with the family 0xC7.  It draws the newborn's sex as for
any newborn (0x43C5F1) and then forces a boy (`mov dword [esi+0x350], 1` at 0x43C7FB).  With the option's file in
the patcher's folder (and the presentation draws installed: the Golden Child is drawn a boy), "VVFP Gender
Presentation.dll" replaces that write with a call that keeps the drawn sex and points the English "The Golden Child"
message at "her powers" for a girl.  Run here on the stock executable in the emulator: the site's bytes, the sex
kept (and, without the file, forced as the game forces it), every register and the flags kept, the message's words,
a translation's entry left alone, and the creator's whole Golden Child block from its compare to its return.

The live effect in a running game is NOT verified here.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "src"))

from test_gender_presentation import have, stock_exe  # noqa: E402

try:
    from gender_presentation_emulation import Game
except ImportError:  # pragma: no cover - environment dependent
    Game = None

SITE, AFTER = 0x43C7FB, 0x43C805
BLOCK = 0x43C7AF                         # cmp dword [esi+0x36C], 0xC7 (the Golden Child's block)
ENTRY, STOCK_TEXT = 0x489264, 0x46F650
STOCK_BYTES = bytes.fromhex("C7865003000001000000")
FLAG = "VVFP Golden Child Born Female.txt"
REGS = ("eax", "ecx", "edx", "ebx", "ebp", "esi", "edi")


def game(flag: bool) -> "Game":
    g = Game(1, stock_exe(1), start=False)
    if flag:
        folder = g.p.exe_path.decode("latin-1").rsplit("\\", 1)[0] + "\\Virtual Villagers Fun Patcher Files"
        g.disk.folders.add(folder.lower())
        g.disk.files[(folder + "\\" + FLAG).lower()] = b"x"
    g.p.export("VvfpStartup", 1, 0)
    return g


def born(g: "Game", sex: int, start: int = SITE, family: int = 0xC7) -> dict:
    r = g.villager(3, "Lulu", female=sex == 2, age=100)
    g.p.put32(r + 0x36C, family)
    regs = {"eax": 0x64, "ecx": 0x33, "edx": 0x44, "ebx": 0x22, "ebp": 0x66, "esi": r, "edi": 3}
    g.run(start, regs=regs, until=AFTER, flags=0x246)
    assert g.p.reg("eip") == AFTER, hex(g.p.reg("eip"))
    out = {k: g.p.reg(k) for k in REGS}
    out["flags"] = g.p.reg("eflags") & 0x8D5
    out["sex"] = g.p.u32(r + 0x350)
    return out


def text_at(g: "Game", va: int) -> str:
    return g.p.cstring(va, 600)


@unittest.skipUnless(Game is not None and have(1), "unicorn/pefile/capstone, the stock A New Home or the DLL")
class GoldenChildBornFemale(unittest.TestCase):

    def test_without_the_file_nothing_changes(self):
        g = game(False)
        self.assertEqual(g.p.export("VvfpGoldenChildBornFemaleInstalled", 1), 0)
        self.assertEqual(g.p.read(SITE, 10), STOCK_BYTES)
        self.assertEqual(born(g, 2)["sex"], 1, "the game forces a boy")
        self.assertEqual(g.p.u32(ENTRY), STOCK_TEXT)

    def test_with_the_file_the_drawn_sex_is_kept(self):
        g = game(True)
        self.assertEqual(g.p.export("VvfpGoldenChildBornFemaleInstalled", 1), 1)
        self.assertEqual(g.p.read(SITE, 1), b"\xE8")
        self.assertEqual(g.p.read(SITE + 5, 5), b"\x90" * 5)
        self.assertEqual(born(g, 2)["sex"], 2, "a girl stays a girl")
        self.assertEqual(born(g, 1)["sex"], 1, "a boy stays a boy")

    def test_registers_and_flags_are_kept(self):
        stock = born(game(False), 1)
        ours = born(game(True), 1)
        self.assertEqual(ours, stock)

    def test_the_whole_golden_child_block(self):
        # from the block's compare: skills, health, head and body 0x13, the sex, the position
        for flag, sex, want in ((False, 2, 1), (True, 2, 2), (True, 1, 1)):
            with self.subTest(flag=flag, sex=sex):
                g = game(flag)
                r = g.villager(3, "Lulu", female=sex == 2, age=100)
                g.p.put32(r + 0x36C, 0xC7)
                g.run(BLOCK, regs={"esi": r, "edi": 3, "ebx": 0, "ebp": 0}, until=0x43C813)
                self.assertEqual(g.p.u32(r + 0x350), want)
                self.assertEqual(g.p.u32(r + 0x364), 0x13)
                self.assertEqual(g.p.u32(r + 0x344), 0x64)
        # another family never reaches the site
        g = game(True)
        r = g.villager(4, "Kai", female=True, age=100)
        g.p.put32(r + 0x36C, 7)
        g.run(BLOCK, regs={"esi": r, "edi": 4}, until=0x43C813)
        self.assertEqual(g.p.u32(r + 0x350), 2)

    def test_the_message_says_her_for_a_girl(self):
        g = game(True)
        stock = text_at(g, STOCK_TEXT)
        self.assertIn("or deny his powers! Behold the Golden Child!", stock)
        born(g, 2)
        self.assertNotEqual(g.p.u32(ENTRY), STOCK_TEXT)
        her = text_at(g, g.p.u32(ENTRY))
        self.assertEqual(her, stock.replace("or deny his powers!", "or deny her powers!"))
        born(g, 1)
        self.assertEqual(g.p.u32(ENTRY), STOCK_TEXT, "a boy: the game's own words again")
        # a translation's entry is never touched
        other = g.p.alloc(64)
        g.p.write(other, b"translated\0")
        g.p.put32(ENTRY, other)
        born(g, 2)
        self.assertEqual(g.p.u32(ENTRY), other)

    def test_the_row(self):
        row = json.loads((ROOT / "data" / "vv1_golden_child_born_female_feature.json").read_text(encoding="utf-8"))
        self.assertEqual(row["dependencies"], ["vv1_gender_presentation"])
        self.assertEqual(row["runtime_detours"][0]["va"], "0x43C7FB")
        self.assertEqual(row["runtime_detours"][0]["stock_bytes"], STOCK_BYTES.hex().upper())
        self.assertEqual(stock_exe(1)[0x3C7FB:0x3C7FB + 10], STOCK_BYTES)   # the file's own bytes (.text at 0x1000)


if __name__ == "__main__":
    unittest.main()
