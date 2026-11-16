"""A villager's sex changed (native/shared/sex_change.h): "VVFP Head Look.dll" keeps their head look, in all five
games, through its own export VvfpVillagerSexChanged and through the save's "Sex Changes" log.

Each case runs the DLL itself in tests/story_emulator.py on the stock executable, with an emulated disk
(tests/head_look_emulation.py):
  * the change in play: the record's sex field flipped, the export told (the record and a copy as it was): the
    look stays on the villager, and the file written now names them by the new identity -- a reload with the new
    sex finds it;
  * the save not saved after the change (the owner Alt-F4s; a backup restored): the file names the new identity,
    the save the old sex.  With the slot's log naming the villager the look is found; without it, it is not (so
    the log is what finds it);
  * a later rename of the villager is still told as one (the stable part was carried too).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

import test_head_look as hl  # noqa: E402
from head_look_emulation import DOCS  # noqa: E402

AUTO, YOUNG, OLD = 0, 1, 2
SEXES = {1: (1, 2), 2: (1, 2), 3: (0, 1), 4: (0, 1), 5: (0, 1)}   # male, female
NAMES = ("Kai", "Lani", "Moku", "Nalu")


def log_file(slot: int) -> str:
    return (f"{DOCS}\\LDW\\Game\\Virtual Villagers Fun Patcher\\Save {slot}\\Data\\"
            f"Sex Changes\\Sex Changes - Save {slot}.txt").lower()


class _SexBase:
    GAME = 0

    def village(self, sexes, disk=None):
        g = hl.Game(self.GAME, hl.stock_exe(self.GAME))
        if disk is not None:
            g.disk.files = dict(disk.files)
            g.disk.folders = set(disk.folders)
        for i, name in enumerate(NAMES):
            g.villager(i, name, age=600, sex=sexes[i])
        return g

    def change(self, g, i):
        """The sex field flipped as sex_change.h writes it, and the DLL told."""
        male, female = SEXES[self.GAME]
        r = g.record(i)
        before = g.p.alloc(g.g["stride"])
        g.p.write(before, g.p.read(r, g.g["stride"]))
        now = g.p.u32(r + g.g["sex"])
        g.p.put32(r + g.g["sex"], male if now == female else female)
        return g.p.export("VvfpVillagerSexChanged", self.GAME, 1, r, before)

    def test_the_look_follows_a_sex_change_in_play(self):
        male, female = SEXES[self.GAME]
        g = self.village([male, female, male, female])
        self.assertEqual(g.set_look(1, OLD), 1)
        self.assertEqual(g.look(1), OLD)
        self.assertEqual(self.change(g, 1), 1)
        self.assertEqual(g.look(1), OLD)
        g.later()
        self.assertEqual(g.look(1), OLD)
        # The file names Lani by the new identity: a reload with the new sex finds the look.
        later = self.village([male, male, male, female], disk=g.disk)
        self.assertEqual(later.look(1), OLD)

    def test_the_log_finds_them_when_the_save_was_not_saved(self):
        male, female = SEXES[self.GAME]
        g = self.village([male, female, male, female])
        g.set_look(1, OLD)
        self.change(g, 1)
        g.look(1)
        # The save still holds the old sex.  Without the log the look is not found...
        lost = self.village([male, female, male, female], disk=g.disk)
        self.assertEqual(lost.look(1), AUTO)
        # ...with the slot's log naming Lani, it is.
        g.disk.files[log_file(1)] = b"F\tM\tLani\r\n"
        found = self.village([male, female, male, female], disk=g.disk)
        self.assertEqual(found.look(1), OLD)

    def test_another_villager_of_that_name_is_never_guessed(self):
        male, female = SEXES[self.GAME]
        g = self.village([male, female, male, female])
        g.set_look(1, OLD)
        self.change(g, 1)
        g.look(1)
        g.disk.files[log_file(1)] = b"F\tM\tLani\r\n"
        twin = hl.Game(self.GAME, hl.stock_exe(self.GAME))
        twin.disk.files = dict(g.disk.files)
        twin.disk.folders = set(g.disk.folders)
        for i, (name, sex) in enumerate(zip(("Kai", "Lani", "Moku", "Nalu", "Lani"),
                                            (male, female, male, female, female))):
            twin.villager(i, name, age=600, sex=sex)
        self.assertEqual(twin.look(1), AUTO)

    def test_a_later_rename_is_still_one(self):
        male, female = SEXES[self.GAME]
        g = self.village([male, female, male, female])
        g.set_look(1, OLD)
        self.change(g, 1)
        g.look(1)
        g.p.write(g.record(1) + g.g["name"], b"Leilani\0")
        self.assertEqual(g.look(1), OLD)

    def test_nothing_to_carry_is_not_an_error(self):
        male, female = SEXES[self.GAME]
        g = self.village([male, female, male, female])
        g.look(0)
        self.assertEqual(self.change(g, 0), 1)   # carried: the roster names Kai by his new identity
        self.assertEqual(g.p.export("VvfpVillagerSexChanged", 9, 1, g.record(0), g.record(0)), 0)


def _make(game: int):
    @unittest.skipUnless(hl.have(game), f"unicorn/pefile, the stock VV{game} or the DLL is missing")
    class Case(_SexBase, unittest.TestCase):
        GAME = game
    Case.__name__ = Case.__qualname__ = f"HeadLookSexChangeVV{game}"
    return Case


for _g in (1, 2, 3, 4, 5):
    globals()[f"HeadLookSexChangeVV{_g}"] = _make(_g)
del _g

if __name__ == "__main__":
    unittest.main()
