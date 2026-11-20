"""The work rush's busy state gives no skill (cie-v6-binary.md 42; the owner's rule of 2026-11-18): each game's rest
action runs to its end in the stock executable (tests/farmers_emulation_vvN.py: the real map, the villagers' update
frame by frame), and not one skill value changes -- while the same village's work action (the control) does change
one, so the check can see a skill gain.

  A New Home       "Sitting" 0x439D80 (index, 15)              control: Researching 0x442C10
  The Lost Children "Sitting" 0x44A1E0 (index, 15)             control: Researching 0x457CC0
  The Secret City  "Working 'til he/she drops!" (action 0x3A)  control: Fishing (action 0xB)
  The Tree of Life "Needs to sit down" (action 0x4F)           control: Harvesting blackberries (action 0x63)
  New Believers    "Needs to sit down" (action 0x55)           control: Harvesting noni (action 0x6C)
"""
from __future__ import annotations

import importlib
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

TRIPS = 10


def harness(game: int):
    try:
        fe = importlib.import_module(f"farmers_emulation_vv{game}")
    except Exception as e:                 # pragma: no cover
        raise unittest.SkipTest(f"no emulator: {e}")
    # New Believers' emulator reads its walk map and animations from research/game-data/vv5 (the game's own
    # Assets files, copied there, never committed) and says whether they are all there with available().
    if (not fe.STOCK.is_file() or (hasattr(fe, "CMAP") and not fe.CMAP.is_file())
            or (hasattr(fe, "available") and not fe.available())):
        raise unittest.SkipTest("needs the stock executable and research/game-data")
    return fe


class RestGivesNoSkill(unittest.TestCase):
    def skills(self, v, game: int, fe) -> list[float]:
        if game in (1, 2):
            return [v.r32(v.rec(0) + off) for off in fe.SKILLS.values()]
        if game == 3:
            return [struct.unpack("<i", v.uc.mem_read(v.rec(0) + off, 4))[0] for off in fe.SKILLS.values()]
        if game == 4:
            return [struct.unpack("<f", v.uc.mem_read(v.rec(0) + off, 4))[0] for off in fe.SKILLS.values()]
        return [struct.unpack("<f", v.uc.mem_read(fe.V0 + fe.SKILLS + 4 * k, 4))[0] for k in fe.SKILL.values()]

    def run_one(self, game: int, rest: bool) -> tuple[list, list]:
        fe = harness(game)
        v = fe.Village(seed=7)
        v.villager(skills={name: 50 for name in (fe.SKILLS if game != 5 else fe.SKILL)})
        before = self.skills(v, game, fe)
        for _ in range(TRIPS):
            if game == 1:
                (v.call(0x439D80, fe.MGR, 0, 15) if rest else v.start_job(0x442C10))
            elif game == 2:
                (v.call(0x44A1E0, fe.MGR, 0, 15) if rest else v.start_job(0x457CC0))
            elif game == 3:
                v.start_job(0x3A if rest else 0xB)
            elif game == 4:
                v.start(0x4F if rest else 0x63)
            else:
                v.start(0x55 if rest else 0x6C)
            for _f in range(30_000):
                v.step_frame()
                if (v.step_type() if game == 5 else v.queue_type()) == 0:
                    break
        return before, self.skills(v, game, fe)

    def test_rest_changes_no_skill_and_work_does(self):
        for game in (1, 2, 3, 4, 5):
            with self.subTest(game=game):
                try:
                    before, after = self.run_one(game, rest=True)
                except unittest.SkipTest as e:
                    self.skipTest(str(e))
                self.assertEqual(after, before, "the busy state gives no skill")
                before, after = self.run_one(game, rest=False)
                self.assertNotEqual(after, before, "the control: the job action does practise a skill")


if __name__ == "__main__":
    unittest.main()
