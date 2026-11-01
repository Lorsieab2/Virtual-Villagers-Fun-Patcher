"""The Lost Children: Change Appearance's head look in the village, in EVERY pose (fixed in v1.35.86).

THE BUG.  The village compositor 0x445B50 picks an adult's young or old head sheet with an age compare in
each pose.  The swimming head's is `cmp ecx, 0x44C` (0x4469BA); every other pose loads the age into ECX
and compares `cmp ecx, ebx`, EBX holding 0x44C from 0x445C32.  "VVFP Head Look.dll" spliced only the
swimming compare, so in the village a villager set to Young still went grey at 55 and one set to Old kept
the young head -- except while swimming.

THE FIX.  The DLL now also splices the thirteen age LOADS before those `cmp ecx, ebx` (native/
vvfp_head_look/vvfp_head_look.c, VV2_SITES, `load` 1): the stub hands the game's own compare the
effective age (0 for Young, 1,100 for Old, the real age for Auto).

THE PROOF, here.  "VVFP Head Look.dll" is loaded and started (VvfpStartup) in Unicorn on the executable --
the stock one, and the one the patcher builds with every public The Lost Children patch -- with the look
kept in its own per-save file; then the game's own village compositor draws one villager record (the
harness of tests/test_pictures_vv2.py: the game's asset loader builds the atlases, every blit is
recorded).  For both sexes, adult ages either side of 55, Auto / Young / Old, and every state, frame,
direction and head facing the compositor knows (swimming included), the blits must be exactly Picture
Studio's plan with that look (src/vv_pictures_vv2.py), and the head must come from the old sheet exactly
when the look (or, under Auto, the age) says so.  Auto must also draw exactly what the stock game draws
without the DLL.

It needs the stock executable (research/stock-executables or inputs/vv2-stock-copy), the game's pictures
(research/game-images), the shipped DLL and Unicorn/pefile; without them it skips.
"""
from __future__ import annotations

import functools
import sys
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

try:
    import test_pictures_vv2 as pv2
    from head_look_emulation import DLL, Game
    import vv_pictures_common as common
    import vv_pictures_vv2 as v2
    HAVE = pv2.EMULATE and DLL.is_file()
except ImportError:  # pragma: no cover - environment dependent
    HAVE = False

AUTO, YOUNG, OLD = 0, 1, 2
NAME = b"Kalani\0"


class _Village(pv2.VillageEmulator if HAVE else object):
    """The compositor's emulator on a process that holds the Head Look DLL, the record table the DLL reads
    ([0x499F24]) being the compositor's own."""

    def __init__(self, exe: bytes) -> None:
        self.g = Game(2, exe)
        super().__init__(exe, process=self.g.p)
        self.g.p.put32(0x499F24, self.game)
        self.g.g["records"] = self.game

    def record(self, st, index: int = 0) -> int:
        rec = super().record(st, index)
        self.p.write(rec + 0x564, NAME)          # the villager's name: the look follows the villager
        return rec

    def look(self, st, look: int) -> None:
        self.record(st)
        self.g.later()
        self.g.p.export("VvfpHeadLookSet", 2, self.game, look)
        self.g.later()
        assert self.g.p.export("VvfpHeadLookGet", 2, self.game) == look


@functools.lru_cache(maxsize=None)
def _patched() -> bytes:
    import test_head_look as hl
    return hl.rendered(2, "immediate_fixed")


def _states():
    for male in (True, False):
        for age in (280, 1099, 1100, 2400):
            for state in (0, 1, 2, 3, 5, 8, 9, 10):
                frames = range(8) if state in (0, 5, 9) else range(4)
                for frame in frames:
                    for direction in range(4):
                        if state not in (0, 5, 9, 2) and direction:
                            continue
                        yield v2.State(male=male, age=age, head=(age + frame) % 30, body=(frame * 7) % 30,
                                       state=state, frame=frame, direction=direction, facing=(frame + direction) % 7,
                                       height=frame * 3, variant=frame)
            yield v2.State(male=male, age=age, head=5, body=2, terrain=v2.DEEP_WATER, facing=3)    # swimming


def _old_head(blits) -> bool:
    heads = [b[0] for b in blits if "_heads" in b[0]]
    assert len(heads) == 1, heads
    return heads[0].endswith("_heads_old.png")


class _Base:
    EXE = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.v = _Village(cls.exe())
        cls.stock = pv2.VillageEmulator(pv2.STOCK.read_bytes())

    def test_the_dll_is_installed(self) -> None:
        self.assertEqual(self.v.g.p.export("VvfpHeadLookInstalled", 2), 1)

    def test_every_pose_follows_the_look(self) -> None:
        n = 0
        for look in (AUTO, YOUNG, OLD):
            for male in (True, False):
                # The look is kept once (it follows the villager: name, sex and parents), then every pose.
                self.v.look(v2.State(male=male, age=600), look)
                for st in (s for s in _states() if s.male == male):
                    with self.subTest(look=look, st=st):
                        blits = self.v.draw(st)
                        self.assertEqual(pv2._plan_keys(replace(st, look=look)), blits)
                        want_old = {YOUNG: False, OLD: True}.get(look, st.age >= v2.OLD_AGE)
                        self.assertEqual(_old_head(blits), want_old)
                        if look == AUTO:
                            self.assertEqual(self.stock.draw(st), blits)
                        n += 1
        self.assertGreater(n, 1000)

    def test_children_keep_the_young_head(self) -> None:
        for look in (YOUNG, OLD):
            self.v.look(v2.State(male=False, age=150), look)
            for state in (0, 1, 2, 10):
                st = v2.State(male=False, age=150, head=4, body=6, state=state, frame=1)
                blits = self.v.draw(st)
                self.assertFalse(_old_head(blits))
                self.assertEqual(pv2._plan_keys(replace(st, look=look)), blits)


@unittest.skipUnless(HAVE, "the stock The Lost Children, its pictures, the Head Look DLL and Unicorn are needed")
class StockGameWithTheDll(_Base, unittest.TestCase):
    @staticmethod
    def exe() -> bytes:
        return pv2.STOCK.read_bytes()


@unittest.skipUnless(HAVE, "the stock The Lost Children, its pictures, the Head Look DLL and Unicorn are needed")
class PatchedGameWithTheDll(_Base, unittest.TestCase):
    """Every public The Lost Children patch, as the patcher renders it."""

    @staticmethod
    def exe() -> bytes:
        try:
            return _patched()
        except Exception as exc:  # noqa: BLE001 -- the patcher could not build it here
            raise unittest.SkipTest(f"the patched executable could not be built ({exc})")


if __name__ == "__main__":
    unittest.main()
