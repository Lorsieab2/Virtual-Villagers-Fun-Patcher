"""A villager's sex changed (native/shared/sex_change.h): "VVFP Cause of Death.dll" keeps them the same villager.

The save-to-save Village Roster (cod_roster.inc) matches every villager kept at the last save by an identity that
holds the sex, so a villager whose sex changed between two saves would be written as having left and arrived
("Unaccounted").  At the save the slot's "Sex Changes" log says whose sex changed (roster_sex_follow); an arrival
reported for a record (cod_arrivals.inc report_who) and New Believers' Former Heathens roster are carried in play
by the export VvfpVillagerSexChanged.

The test build of the DLL runs in the emulator beside The Secret City, The Tree of Life and New Believers rendered
with every patch (tests/test_cause_of_death.py), its files in an emulated file system:
  * a change, then the save: no Unaccounted record -- and without the log the same steps write "Left" and
    "Arrived" (so the log is what keeps them);
  * two villagers of the name: never a guess;
  * a change, then a death before the save: the Death record accounts for them, no "Left";
  * a birth (an arrival reported), then a change before the save: no "Arrived" -- and without the export there is.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

import test_cause_of_death as cod  # noqa: E402

SAVES = {"vv3": 0x427D71, "vv4": 0x41F13F, "vv5": 0x4245FF}
CREATOR = {"vv3": (0x456326, 0x456332), "vv4": (0x45F175, 0x45F181), "vv5": (0x468411, 0x46841A)}
LEFT = "Left the village with no Death or Disappeared record"
ARRIVED = "Arrived with no Birth record or known arrival"


class _Village:
    def __init__(self, game: str):
        self.game = game
        self.g, self.w = cod.later(game)
        self.g.slot = 1
        for i, (name, sex) in enumerate((("Kai", 0), ("Lani", 1), ("Moku", 0))):
            self.w.villager(i, name, 600 + i, 80)
            self.g.p.put32(self.w.record(i) + cod.SEX[game], sex)
        self.save()                                   # the first roster

    def save(self) -> None:
        self.g.saved_epilogue(SAVES[self.game], 1, 1)

    def flip(self, i: int, *, tell: bool = False) -> int:
        p, r = self.g.p, self.w.record(i)
        stride = self.w.l["stride"]
        before = p.alloc(stride)
        p.write(before, p.read(r, stride))
        p.put32(r + cod.SEX[self.game], 1 - p.u32(r + cod.SEX[self.game]))
        return p.export("VvfpVillagerSexChanged", int(self.game[-1]), 1, r, before) if tell else 0

    def log(self, text: bytes) -> None:
        """The slot's Sex Changes log, beside the roster in the save's own folder (per_save_data.h)."""
        (roster,) = [n for n in self.g.files if n.endswith("Villagers at Last Save - Save 1.dat")]
        folder = roster.rsplit("\\", 2)[0]
        self.g.files[folder + "\\Sex Changes\\Sex Changes - Save 1.txt"] = bytearray(text)
        self.g.dirs.add((folder + "\\Sex Changes").lower())

    def unaccounted(self) -> list[tuple[str, str]]:
        return sorted((e.get("Name", ""), e["What"]) for e in self.g.of_kind(cod.UNACCOUNTED))


class CauseOfDeathSexChange(unittest.TestCase):
    def games(self):
        if not cod.TEST_DLL.is_file():
            self.skipTest(cod.TEST_BUILD_ABSENT)
        found = [g for g in ("vv3", "vv4", "vv5") if cod.STOCK[g].is_file()]
        if not found:
            self.skipTest(cod.STOCK_ABSENT)
        return found

    def test_a_change_then_a_save_is_no_departure_or_arrival(self):
        for game in self.games():
            v = _Village(game)
            v.flip(1, tell=True)
            v.log(b"F\tM\tLani\r\n")
            v.save()
            self.assertEqual(v.unaccounted(), [], game)
            v.save()                                  # and the roster written now holds the new sex
            self.assertEqual(v.unaccounted(), [], game)

    def test_without_the_log_they_are_written_as_left_and_arrived(self):
        for game in self.games():
            v = _Village(game)
            v.flip(1, tell=True)
            v.save()
            self.assertEqual([w for _, w in v.unaccounted()], sorted([ARRIVED, LEFT]), game)

    def test_a_namesake_is_never_guessed(self):
        for game in self.games():
            v = _Village(game)
            v.w.villager(3, "Lani", 700, 80)          # a second Lani arrives before the save
            v.g.p.put32(v.w.record(3) + cod.SEX[game], 0)
            v.flip(1, tell=True)
            v.log(b"F\tM\tLani\r\n")
            v.save()
            self.assertIn(LEFT, [w for _, w in v.unaccounted()], game)

    def test_a_change_then_a_death_is_accounted_for_by_the_death(self):
        for game in self.games():
            v = _Village(game)
            v.flip(1, tell=True)
            v.log(b"F\tM\tLani\r\n")
            v.g.p.put32(v.w.record(1) + v.w.l["health"], 0)
            v.w.bury(1)
            self.assertEqual(len(v.g.of_kind(cod.DEATH)), 1, game)
            v.save()
            self.assertEqual(v.unaccounted(), [], game)

    def test_a_birth_then_a_change_before_the_save_is_still_reported(self):
        for game in self.games():
            for tell in (True, False):
                v = _Village(game)
                v.w.villager(5, "Newborn", 0, 100)
                start, stop = CREATOR[game]
                v.g.run(start, stop, esi=v.w.record(5), ebx=0)
                v.g.tick()                            # the first look after the creator
                self.assertEqual(v.flip(5, tell=tell), 1 if tell else 0, (game, tell))
                v.log(b"M\tF\tNewborn\r\n")
                v.g.tick()
                v.save()
                self.assertEqual(ARRIVED in [w for _, w in v.unaccounted()], not tell, (game, tell))

    def test_nothing_to_carry_and_another_slot(self):
        for game in self.games():
            v = _Village(game)
            self.assertEqual(v.flip(0, tell=True), 0, game)
            r = v.w.record(0)
            self.assertEqual(v.g.p.export("VvfpVillagerSexChanged", int(game[-1]), 2, r, r), 0, game)


if __name__ == "__main__":
    unittest.main()
