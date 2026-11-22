"""A villager's sex changed (native/shared/sex_change.h): "VVFP Faith Loss.dll" keeps their mark (New Believers).

A mark's identity (the name, likes and dislikes) holds no sex, so a sex change alone never loses it; but the parts
that follow a rename or a likes / dislikes change (the keep and the stable part) both hold the sex, so a rename
after the change, before any write, would lose it -- and the believer would be decided a second time.  The export
VvfpVillagerSexChanged takes those parts from the record now and writes the file.

The shipped DLL runs in the emulator beside New Believers rendered with the row (tests/test_faith_loss_marks.py).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

import test_faith_loss_marks as fl  # noqa: E402

SEX = 0x1B90


def change(g, rec: int) -> int:
    """The sex field flipped as sex_change.h writes it, and the DLL told (slot 1)."""
    before = g.p.alloc(fl.STRIDE)
    g.p.write(before, g.p.read(rec, fl.STRIDE))
    g.p.put32(rec + SEX, 1 - g.p.u32(rec + SEX))
    return g.p.export("VvfpVillagerSexChanged", 5, 1, rec, before)


@fl.skip_without_emulator
class FaithLossSexChange(unittest.TestCase):
    def marked_village(self, files, n=2):
        g = fl.Game(fl.rendered((fl.FAITH_LOSS,)), files, n=n)
        a = g.records[0]
        g.p.put32(a + fl.FAITH, 1)
        g.forced = [0, 99, 5]
        g.drift(a)                                          # a is marked
        self.assertEqual(g.marked(), 1)
        return g, a

    def test_a_sex_change_then_a_rename_keeps_the_mark(self):
        files = fl.Files()
        g, a = self.marked_village(files)
        self.assertEqual(change(g, a), 1)
        self.assertEqual(len(files.marks()), 1, "written at once")
        g.p.write(a + fl.NAME, b"Renamed Villager\0")       # renamed after the change, no write between
        g.p.put32(a + fl.AGE, 401)
        g.forced = [0, 99, 0]                               # a roll would make a Heathen: none is made
        g.drift(a)
        self.assertEqual((g.faith(a), g.heathen(a), g.decisions), (1, False, 1))

    def test_without_the_word_the_rename_loses_it(self):
        """What the export is for: the same steps, the DLL not told."""
        files = fl.Files()
        g, a = self.marked_village(files)
        g.p.put32(a + SEX, 1)
        g.p.write(a + fl.NAME, b"Renamed Villager\0")
        g.p.put32(a + fl.AGE, 401)
        g.forced = [0, 99, 0]
        g.drift(a)
        self.assertEqual(g.decisions, 2, "decided a second time")

    def test_a_sex_change_alone_keeps_the_mark_through_a_reload(self):
        """The save not saved after the change (or saved): the identity holds no sex, so either sex finds it."""
        files = fl.Files()
        g, a = self.marked_village(files)
        change(g, a)
        for sex in (0, 1):
            again = fl.Game(fl.rendered((fl.FAITH_LOSS,)), files, n=2)
            r = again.records[0]
            again.p.put32(r + SEX, sex)
            again.p.put32(r + fl.FAITH, 1)
            again.forced = [0, 99, 0]
            again.drift(r)
            self.assertEqual((again.heathen(r), again.decisions), (False, 0), f"sex {sex}")

    def test_nothing_to_carry_and_other_games(self):
        files = fl.Files()
        g, a = self.marked_village(files)
        b = g.records[1]
        self.assertEqual(change(g, b), 0, "b has no mark")
        self.assertEqual(g.p.export("VvfpVillagerSexChanged", 4, 1, a, a), 0)
        self.assertEqual(g.p.export("VvfpVillagerSexChanged", 5, 2, a, a), 0, "another slot's")
        self.assertEqual(g.marked(), 1)


if __name__ == "__main__":
    unittest.main()
