"""Up to 99 Cutting Tools/Soap/Cloth (The Tree of Life): "VVFP VV4 Supply Cap.dll".

The shipped DLL runs beside The Tree of Life's own code in unicorn (tests/farmers_emulation_vv4.py, the companion mapped
through tests/story_emulator.py's Process): the game's own produce routines (cutting tools 0x431400, cloth 0x436890),
its use-up 0x4369F0 and the tools' stack draw 0x431480 / the Clothing Hut's bolts 0x430C80.  Stood in for: the
achievement counter 0x412F90, the tip 0x44B890, the puzzle progress 0x438A30 and the sprite calls (pictures are not
the point).  "Stock" is the same village without the companion.  The live effect is NOT verified here.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts"))

import build_vv4_supply_cap_feature as builder  # noqa: E402

try:
    from unicorn import UC_HOOK_CODE

    import farmers_emulation_vv4 as fe

    HAVE_EMULATOR = fe.STOCK.is_file() and fe.CMAP.is_file()
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

TOOLS, TOOL_COUNT = 0x4D8614, 0x4D8618
CLOTH, CLOTH_COUNT = 0x4D8AC8, 0x4D8ACC
USE_UP, MAKE_TOOLS, MAKE_CLOTH = 0x4369F0, 0x431400, 0x436890
TOOL_DRAW, HUT_DRAW, HUT = 0x431480, 0x430C80, 0x4D82D8
REC_JOB = 0x1CE0


class Store:
    def __init__(self, patched: bool):
        self.v = fe.Village(dll=builder.DLL if patched else None)
        if patched:
            self.v.process.export("VvfpStartup", 4, 0)
            assert self.v.process.export("VvfpSupplyCapInstalled") == 1
        self.sprites = 0
        stubs = {0x412F90: 8, 0x44B890: 0xC, 0x438A30: 4, 0x44CCF0: 0, 0x44CD90: 0x10, 0x44C5E0: 4,
                 0x42FF80: 4}

        def stub(pop, at):
            if at == 0x44C5E0:
                self.sprites += 1
            self.v._ret(0, pop)
        for at, pop in stubs.items():
            self.v.uc.hook_add(UC_HOOK_CODE, lambda *_a, at=at, pop=pop: stub(pop, at), begin=at, end=at)
        self.rec = self.v.villager()

    def count(self, at: int) -> int:
        return self.v.r32(at)

    def make_tools(self) -> None:
        self.v.call(MAKE_TOOLS, TOOLS, self.rec)

    def make_cloth(self) -> None:
        self.v.w32(self.rec + REC_JOB, 0x7C)                  # the cloth's produce counts only for job 0x7C
        self.v.call(MAKE_CLOTH, CLOTH, self.rec)

    def tool_sprites(self, n: int) -> int:
        self.v.w32(TOOL_COUNT, n)
        self.sprites = 0
        self.v.call(TOOL_DRAW, TOOLS, 0)
        return self.sprites

    def bolt_sprites(self, n: int) -> int:
        self.v.w32(CLOTH_COUNT, n)
        self.sprites = 0
        self.v.call(HUT_DRAW, HUT, 0)
        return self.sprites


@unittest.skipUnless(HAVE_EMULATOR, "the stock executable, its map and unicorn are needed")
class SupplyCapTests(unittest.TestCase):
    def test_tools_and_cloth_rise_to_99_and_never_above(self) -> None:
        for patched, cap in ((True, 99), (False, 6)):
            with self.subTest(patched=patched):
                s = Store(patched)
                for make, at in ((s.make_tools, TOOL_COUNT), (s.make_cloth, CLOTH_COUNT)):
                    s.v.w32(at, 0)
                    seen = []
                    for _ in range(40):
                        make()
                        seen.append(s.count(at))
                    self.assertEqual(max(seen), cap)
                    self.assertEqual(seen[:3], [3, 6, min(9, cap)])
                    if patched:
                        self.assertNotIn(100, seen)

    def test_using_one_keeps_the_rest(self) -> None:
        for patched, after in ((True, 98), (False, 6)):
            with self.subTest(patched=patched):
                s = Store(patched)
                for obj, at in ((TOOLS, TOOL_COUNT), (CLOTH, CLOTH_COUNT)):
                    s.v.w32(at, 99)
                    s.v.call(USE_UP, obj, 1)
                    self.assertEqual(s.count(at), after)
                    s.v.w32(at, 0)
                    s.v.call(USE_UP, obj, 1)
                    self.assertEqual(s.count(at), 0)

    def test_the_stacks_look_as_with_6(self) -> None:
        for patched in (True, False):
            with self.subTest(patched=patched):
                s = Store(patched)
                for n in (0, 1, 4, 6):
                    self.assertEqual(s.tool_sprites(n), n)
                    self.assertEqual(s.bolt_sprites(n), n)
                for n in (7, 40, 99):
                    self.assertEqual(s.tool_sprites(n), 6 if patched else n)
                    self.assertEqual(s.bolt_sprites(n), 6 if patched else n)


class RowTests(unittest.TestCase):
    def test_the_row_is_the_builders(self) -> None:
        path = ROOT / "data" / f"{builder.ID}_feature.json"
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), builder.row(builder.sha(builder.DLL)))


if __name__ == "__main__":
    unittest.main()
