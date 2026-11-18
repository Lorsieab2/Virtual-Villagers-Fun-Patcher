"""Fix Vanilla Bugs (The Tree of Life): after The Frog Rescue the frogs leap all along the river's blue water
("VVFP VV4 Frogs.dll"; the owner, 2026-11-17: "the frogs patch should spawn frogs all along the blue of the river
here").

The base game's world refresh (0x46D090) places its frog leaps after The Frog Rescue in its frog block
(0x46D3BF..0x46D4C5): one frog leaping right (effect 0x1B) at x 1029..1182, y 605..636, then two 50-in-100 chances of
one leaping left (0x1C) at x 950..1133, y 600..629 -- two small boxes on the right of the bottom stretch.  The
companion makes the same leaps with the same effect-maker arguments at corners picked from frog_water.h: every top
left corner at which every pixel of every one of a leap's 12 frames lies on the river's blue water as the game draws
it (scripts/build_vv4_frog_water.py, from the game's river, tree and frog pictures).

Proofs here:
  * the rows: the companion pinned in the Fix Vanilla Bugs row and started from the second startup word; the
    executable keeps only the two ripple-frame rows; its C table holds the stock block;
  * the water (with the game's pictures in research/game-images): the generated header is current; every listed
    corner's whole leap is on the drawn water (checked pixel by pixel here); the corners reach the curve on the left,
    the whole bottom stretch and the pool under the waterfall by the ladder; at low flow nothing fits;
  * emulation (unicorn, the stock executable and the shipped companion): the stock block leaps only in its boxes;
    with the companion every leap is at a listed corner with the base game's own arguments and chances, nothing at
    low flow, every register kept; a changed byte anywhere in the block installs nothing;
  * every public Tree of Life row, and 256 Villagers, leave the block's bytes stock in every population mode, so
    the companion goes in beside them.
The live effect in a running game is checked in the PR, not here.
"""
from __future__ import annotations

import hashlib
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts"))

import vv_fun_patcher as patcher  # noqa: E402

try:
    import pefile
    import unicorn  # noqa: F401
    from story_emulator import RETURN, Process
    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover
    HAVE_EMULATOR = False

try:
    import numpy as np
    import build_vv4_frog_water as water
    HAVE_ART = water.IMAGES.is_dir()
except ImportError:  # pragma: no cover - numpy / scipy / Pillow missing
    HAVE_ART = False

STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Tree of Life.exe"
HAVE_STOCK = STOCK.is_file()
DLL_NAME = "VVFP VV4 Frogs.dll"
DLL = ROOT / "assets" / "vv4_frogs" / DLL_NAME
SOURCE = ROOT / "native" / "vvfp_vv4_frogs" / "vvfp_vv4_frogs.c"
HEADER = ROOT / "native" / "vvfp_vv4_frogs" / "frog_water.h"
ROW = "vv4_fix_vanilla_bugs"
GATE, SITE, EXIT, BLOCK_END = 0x46D3BF, 0x46D3F7, 0x46D4C2, 0x46D4C6
RAND, MAKER, EFFECTS = 0x4036D0, 0x41CEC0, 0x4CE1C0
PUZZLE, PAUSED, FLOW = 0x438960, 0x41DBC0, 0x4396E0
RIPPLE_ROWS = [(0xB9F0C, "09", "0C"), (0xB9F1C, "09", "0C")]
MODES = ("stock", "collection_progression", "immediate_fixed")


def _row() -> dict:
    return next(p.raw for p in patcher.load_fun_patches() if p.id == ROW)


def _runs() -> dict[tuple[int, int], list[tuple[int, int, int]]]:
    """frog_water.h's sets as {(flow, frog): [(y, x0, x1), ...]}."""
    text = HEADER.read_text(encoding="utf-8")
    body = text.split("FROG_RUNS[")[1].split("};")[0]
    runs = [tuple(map(int, m)) for m in re.findall(r"\{(-?\d+), (-?\d+), (-?\d+)\}", body)]
    sets = text.split("FROG_SETS[")[1].split("};")[0]
    out = {}
    for flow, frog, first, count, total in re.findall(r"\{(\d+), 0x([0-9A-F]+), (\d+), (\d+), (\d+)\}", sets):
        chosen = runs[int(first):int(first) + int(count)]
        assert sum(b - a + 1 for _, a, b in chosen) == int(total)
        out[(int(flow), int(frog, 16))] = chosen
    return out


class TheRow(unittest.TestCase):
    def test_the_row_ships_and_starts_the_companion(self) -> None:
        r = _row()
        files = {f["destination"]: f["sha256"] for f in r["companion_files"]}
        self.assertEqual(files.get(DLL_NAME), hashlib.sha256(DLL.read_bytes()).hexdigest().upper())
        self.assertIn(DLL_NAME, patcher.STARTUP_LOADER_COMPANIONS_2)
        startup = (ROOT / "native" / "shared" / "startup_companions_2.h").read_text(encoding="utf-8")
        self.assertIn(f'"{DLL_NAME}"', startup)
        detours = [(int(d["va"], 16), d["stock_bytes"]) for d in r["runtime_detours"] if DLL_NAME in d["installed_by"]]
        self.assertEqual(detours, [(SITE, "56689A0000")])
        self.assertIn("all along the blue water of the river", r["description"])
        self.assertIn("runs low", r["description"])

    def test_only_the_ripple_rows_stay_in_the_executable(self) -> None:
        frog_area = [p for p in _row()["patches"] if GATE - 0x400000 <= int(p["offset"], 16) < BLOCK_END - 0x400000]
        self.assertEqual(frog_area, [])
        ripple = [(int(p["offset"], 16), p["before"], p["after"]) for p in _row()["patches"]
                  if int(p["offset"], 16) in (0xB9F0C, 0xB9F1C)]
        self.assertEqual(ripple, RIPPLE_ROWS)

    @unittest.skipUnless(HAVE_STOCK, "needs the stock executable")
    def test_the_c_table_is_the_stock_block(self) -> None:
        source = SOURCE.read_text(encoding="utf-8")
        table = source.split("FROG_BLOCK[0x46D4C6 - VV4_GATE] = {")[1].split("};")[0]
        stock = STOCK.read_bytes()[GATE - 0x400000:BLOCK_END - 0x400000]
        self.assertEqual(bytes(int(b, 16) for b in re.findall(r"0x([0-9A-F]{2})", table)), stock)
        self.assertEqual(stock[SITE - GATE:SITE - GATE + 5].hex().upper(), "56689A0000")
        self.assertEqual(stock[EXIT - GATE:].hex().upper(), "83C408C3")


@unittest.skipUnless(HAVE_ART, "needs numpy, scipy, Pillow and the game's pictures (research/game-images)")
class TheWater(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runs = _runs()
        cls.water = {flow: water.water_mask(flow) for flow in water.RIVER}

    def test_the_header_is_current(self) -> None:
        self.assertEqual(water.main(["--check"]), 0)

    def test_every_corner_puts_the_whole_leap_on_the_water(self) -> None:
        for (flow, frog), runs in self.runs.items():
            ys, xs = np.nonzero(water.footprint(frog))
            self.assertGreater(len(ys), 300)
            wet = self.water[flow]
            for y, x0, x1 in runs:
                for x in range(x0, x1 + 1):
                    self.assertTrue(wet[ys + y, xs + x].all(), (flow, hex(frog), x, y))

    def test_the_water_is_only_the_river_round_the_island(self) -> None:
        wet = self.water[2]
        ys, xs = np.nonzero(wet)
        # within the strong river picture, below the tree's canopy, left of the ladder's rocks
        self.assertGreaterEqual(xs.min(), 0x27F)
        self.assertLess(xs.max(), 1400)
        self.assertLess(ys.max(), 0x127 + 387)
        # none of the waterfall's face or the stream above it
        self.assertFalse(wet[:540, 1230:].any())

    def test_the_corners_reach_all_along_the_river(self) -> None:
        for frog in (0x1B, 0x1C):
            corners = [(x, y) for y, x0, x1 in self.runs[(2, frog)] for x in (x0, x1)]
            with self.subTest(frog=hex(frog)):
                # the curve on the left, up towards the waterfall's side
                self.assertTrue(any(x < 700 and y < 600 for x, y in corners))
                # the bottom stretch, from its left end to the ladder
                for left in range(700, 1200, 50):
                    self.assertTrue(any(left <= x < left + 50 and y >= 580 for x, y in corners), left)
                # the pool under the waterfall, by the ladder
                self.assertTrue(any(x + 60 > 1300 and y >= 520 for x, y in corners))
                # far more places than the base game's box (0x1B: 154 x 32)
                self.assertGreater(sum(x1 - x0 + 1 for _, x0, x1 in self.runs[(2, frog)]), 10000)

    def test_at_low_flow_no_leap_fits(self) -> None:
        self.assertNotIn((1, 0x1B), self.runs)
        self.assertNotIn((1, 0x1C), self.runs)
        heights = [int(self.water[1][:, x].sum()) for x in range(700, 1201, 50)]
        self.assertLess(max(heights), 27)       # a leap's frames span 27 rows (7..33)


def _frog_process(exe: bytes, *, with_dll: bool, flow: int, rolls: list[int]) -> tuple[Process, list, list]:
    p = Process(exe, DLL if with_dll else None)
    if with_dll:
        p.export("VvfpStartup", 4, 0)
    leaps, rand_calls = [], []
    p.stub(PUZZLE, lambda m: (1, 4))
    p.stub(PAUSED, lambda m: (0, 0))
    p.stub(FLOW, lambda m: (flow, 0))

    def rand(m):
        n = m.arg(0)
        value = rolls[len(rand_calls) % len(rolls)] % n
        rand_calls.append((n, value))
        return (value, 0)

    def maker(m):
        leaps.append((m.reg("ecx"), [m.arg(i) for i in range(8)]))
        return (len(leaps), 0x20)

    p.stub(RAND, rand)
    p.stub(MAKER, maker)
    return p, leaps, rand_calls


@unittest.skipUnless(HAVE_EMULATOR and HAVE_STOCK and DLL.is_file(), "needs unicorn, pefile, the stock executable")
class TheBlock(unittest.TestCase):
    def _run(self, p: Process) -> dict:
        kept = {"ebx": 0x1111, "esi": 0x2222, "edi": 0x3333, "ebp": 0x4444}
        p.call(GATE, [RETURN, RETURN], regs=kept)
        return {name: p.reg(name) for name in kept} | {"kept": kept}

    def test_the_stock_block_leaps_only_in_its_boxes(self) -> None:
        stock = STOCK.read_bytes()
        for rolls in ([0], [10_000], [7, 49, 3, 49, 9], [31, 77, 12, 50, 6, 50]):
            p, leaps, _ = _frog_process(stock, with_dll=False, flow=2, rolls=rolls)
            self._run(p)
            self.assertGreaterEqual(len(leaps), 1)
            for ecx, (frog, x, y, *rest) in leaps:
                self.assertEqual(ecx, EFFECTS)
                self.assertEqual(rest, [0, 0, 0xFFFFFFFF, 5, 0])
                if frog == 0x1B:
                    self.assertTrue(1029 <= x <= 1182 and 605 <= y <= 636)
                else:
                    self.assertTrue(950 <= x <= 1133 and 600 <= y <= 629)

    def test_the_companion_leaps_at_listed_corners_with_the_games_own_arguments(self) -> None:
        sets = _runs()
        allowed = {frog: {(x, y) for y, x0, x1 in runs for x in range(x0, x1 + 1)}
                   for (flow, frog), runs in sets.items() if flow == 2}
        seen = {0x1B: set(), 0x1C: set()}
        for seed in range(40):
            rolls = [seed * 7919 + 13, (seed * 37) % 100, seed * 104729 + 1, (seed * 53 + 11) % 100, seed * 31337]
            p, leaps, rand_calls = _frog_process(STOCK.read_bytes(), with_dll=True, flow=2, rolls=rolls)
            state = self._run(p)
            for name, value in state["kept"].items():
                self.assertEqual(state[name], value, name)
            # one leaping right, then each 50-in-100 chance of one leaping left, as the base game
            self.assertEqual(leaps[0][1][0], 0x1B)
            chances = [value for n, value in rand_calls if n == 100]
            self.assertEqual(len(chances), 2)
            self.assertEqual(sum(1 for _, a in leaps if a[0] == 0x1C), sum(1 for v in chances if v < 50))
            self.assertEqual(len(leaps), 1 + sum(1 for v in chances if v < 50))
            for ecx, (frog, x, y, *rest) in leaps:
                self.assertEqual(ecx, EFFECTS)
                self.assertEqual(rest, [0, 0, 0xFFFFFFFF, 5, 0])
                self.assertIn((x, y), allowed[frog])
                seen[frog].add((x, y))
        # the leaps spread out along the river, not into one box
        for frog, points in seen.items():
            xs = [x for x, _ in points]
            self.assertGreater(max(xs) - min(xs), 300, hex(frog))

    def test_no_leap_at_low_flow(self) -> None:
        p, leaps, _ = _frog_process(STOCK.read_bytes(), with_dll=True, flow=1, rolls=[0])
        self._run(p)
        self.assertEqual(leaps, [])

    def test_a_changed_byte_in_the_block_installs_nothing(self) -> None:
        pe = pefile.PE(str(STOCK), fast_load=True)
        for va in (GATE, SITE, SITE + 1, 0x46D440, EXIT, BLOCK_END - 1):
            with self.subTest(va=hex(va)):
                data = bytearray(STOCK.read_bytes())
                data[pe.get_offset_from_rva(va - 0x400000)] ^= 0xFF
                p = Process(bytes(data), DLL)
                p.export("VvfpStartup", 4, 0)
                self.assertEqual(p.export("VvfpVv4FrogsInstalled"), 0)
                self.assertEqual(p.read(SITE, 5), bytes(data[pe.get_offset_from_rva(SITE - 0x400000):][:5]))
        p = Process(STOCK.read_bytes(), DLL)
        p.export("VvfpStartup", 3, 0)
        self.assertEqual(p.export("VvfpVv4FrogsInstalled"), 0)
        p.export("VvfpStartup", 4, 0)
        self.assertEqual(p.export("VvfpVv4FrogsInstalled"), 1)
        self.assertEqual(p.read(SITE, 1), b"\xE9")


@unittest.skipUnless(HAVE_STOCK, "needs the stock executable")
class TheRenders(unittest.TestCase):
    def test_every_vv4_row_and_256_villagers_leave_the_block_stock(self) -> None:
        build = next(b for b in patcher.load_builds() if b.id == "vv4")
        public = [p.id for p in patcher.load_public_fun_patches()
                  if p.game_id == "vv4" and p.id not in patcher.ALTERNATIVE_FUN_PATCH_IDS
                  and p.id not in patcher.EXPERIMENTAL_FUN_PATCH_IDS]
        stock = STOCK.read_bytes()[GATE - 0x400000:BLOCK_END - 0x400000]
        for mode in MODES:
            for ids in (public, [ROW, "vv4_population_256"], public + ["vv4_population_256"]):
                with self.subTest(mode=mode, n=len(ids)):
                    data, _ = patcher.render_patched_bytes(STOCK, build, mode,
                                                           patcher.resolve_fun_patch_ids(ids, game_id="vv4"))
                    data = bytes(data)
                    pe = pefile.PE(data=data, fast_load=True) if HAVE_EMULATOR else None
                    offset = pe.get_offset_from_rva(GATE - 0x400000) if pe else GATE - 0x400000
                    self.assertEqual(data[offset:offset + len(stock)], stock)
                    for off, _before, after in RIPPLE_ROWS:
                        self.assertEqual(data[off:off + 1].hex().upper(), after)


if __name__ == "__main__":
    unittest.main()
