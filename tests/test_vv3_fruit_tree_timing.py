"""The Secret City's two fruit-tree schedules (docs/vv3-fruit-tree-timing.md):

  * All Fruit Trees Refill at the Same Time  ("VVFP VV3 Trees Refill Together.dll")
  * Fruit Trees Take Turns Refilling         ("VVFP VV3 Trees Take Turns.dll")

Everything here runs the shipped bytes: The Secret City as the patcher renders it (the
public catalog -- with the Nature patch and Fruit Counts When It Reaches the Food Bin -- in
all three population modes, and the 256 Villagers build) with the shipped companion mapped
beside it in an emulator (tests/story_emulator.py) and a small in-memory file system for its
per-save file.  The game's own routines run for real: the world objects' update 0x435880 (the
runner of every object's update, live and after catch-up and Time Warp alike), which calls
the trees' update 0x434760 through its vtable; the world objects' save 0x435790 and load
0x435710, which call the trees' saver 0x433EC0 and loader 0x433E40; the Nature level reader
0x426FC0; and the tail that removes a dead tree (0x43487F).  Only the clock (0x426590) and the
planting puzzle's check (0x4358D0) are stand-ins, each popping exactly what the real routine
pops.  "Stock" below is the same rendered executable without the companion.

The live effect in a running game is NOT verified here.
"""
from __future__ import annotations

import functools
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_fun_patcher as patcher  # noqa: E402

try:
    import pefile  # noqa: F401
    from story_emulator import Process
    import test_vv3_both_factions as both_factions   # its in-memory file system and real_pop

    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

TOGETHER = "vv3_fruit_trees_refill_together"
TURNS = "vv3_fruit_trees_take_turns"
DLLS = {
    TOGETHER: ROOT / "assets" / "fruit_trees" / "VVFP VV3 Trees Refill Together.dll",
    TURNS: ROOT / "assets" / "fruit_trees" / "VVFP VV3 Trees Take Turns.dll",
}
MODES = ("stock", "collection_progression", "immediate_fixed")
BUILDS = [(m, False) for m in MODES] + [("immediate_fixed", True)]   # + the 256 Villagers build

TREES = 0x5947E0
WORLD = 0x594990             # the world objects: count +0x138, objects from +0xD0
WORLD_UPDATE = 0x435880
WORLD_SAVE = 0x435790        # thiscall(out, size)
WORLD_LOAD = 0x435710        # thiscall(in)
CLOCK = 0x426590
PUZZLE_CHECK = 0x4358D0
TECH = 0x582618
SAVE_MANAGER = 0x4B309C      # the save manager singleton; its slot at +0x12F24
SITES = {0x43478A: "8B466433DB", 0x433E40: "538B5C24085556", 0x433EC0: "8BC1837C240860"}
SIDE = ("C:\\Docs\\LDW\\Game\\Virtual Villagers Fun Patcher\\Save {s}\\Data\\Fruit Trees\\"
        "Virtual Villagers 3 Fruit Tree Timers - Save {s}.dat")
T_STOCK, T_NATURE_PATCH = 10800, 8100
# The game clock at the tests' time 0 (a planted time of 0 reads as no tree, 0x4348AA).
BASE = 1_000_000


@functools.lru_cache(maxsize=None)
def render(mode: str, expanded: bool = False) -> bytes:
    """The public catalog of The Secret City (the two schedules ship no executable bytes, so
    the image is the same with either; the companion is mapped beside it)."""
    build = {b.id: b for b in patcher.load_builds()}["vv3"]
    ids = [p.id for p in patcher.load_public_fun_patches()
           if p.game_id == "vv3" and p.id not in (TOGETHER, TURNS)
           and (expanded or p.id not in patcher.EXPERIMENTAL_FUN_PATCH_IDS)]
    data, _ = patcher.render_patched_bytes(both_factions.stock_exe(), build, mode, ids)
    return bytes(data)


@functools.lru_cache(maxsize=None)
def render_without_nature(mode: str) -> bytes:
    build = {b.id: b for b in patcher.load_builds()}["vv3"]
    data, _ = patcher.render_patched_bytes(both_factions.stock_exe(), build, mode, [])
    return bytes(data)


class Village:
    """A rendered Secret City with (or without) one of the two companions."""

    def __init__(self, companion: str | None, mode: str = "stock", expanded: bool = False, *,
                 image: bytes | None = None, files: dict | None = None, slot: int = 1,
                 install: bool = True):
        exe = image if image is not None else render(mode, expanded)
        self.p = Process(exe, DLLS[companion] if companion else None)
        p = self.p
        self.now = 0

        def checked(va, fn):
            def run(q):
                value, pop = fn(q)
                if pop != both_factions.real_pop(va):
                    raise AssertionError(f"stand-in 0x{va:X} pops {pop}, the routine pops "
                                         f"{both_factions.real_pop(va)}")
                return value, pop
            p.stub(va, run)
        checked(CLOCK, lambda q: ((BASE + self.now) & 0xFFFFFFFF, 0))
        checked(PUZZLE_CHECK, lambda q: (1, 4))           # the planting puzzle: already solved
        # The objects as the game's constructors leave them: the trees (two vtables) are the
        # world's only object here.
        p.put32(TREES, 0x49D1D0)
        p.put32(TREES + 4, 0x49D1C4)
        p.put32(WORLD + 0x138, 1)
        p.put32(WORLD + 0xD0, TREES)
        manager = p.alloc(0x13000)
        p.put32(SAVE_MANAGER, manager)
        p.put32(manager + 0x12F24, slot)
        self.files = None
        if companion:
            self.files = both_factions.Files(p)
            if files is not None:
                self.files.files = files
            if install:
                p.export("VvfpStartup", 3, 0)

    # ---- the trees -------------------------------------------------------------------
    def nature(self, level: int) -> None:
        self.p.put32(TECH + 4 * 5, level)

    def count(self) -> int:
        return self.p.u32(TREES + 0x64)

    def rec(self, i: int) -> int:
        return TREES + 0x1C + 0x18 * i

    def plant(self, x: int, kind: int = 0) -> None:
        """A tree planted now, as the planting code writes it (0x434A0D..0x434A6D): its kind,
        planted time = the clock, its timer = the planted time, 1,000 fruit, one more tree."""
        n = self.count()
        r = self.rec(n)
        self.p.write(r, struct.pack("<6i", x, 0x300, BASE + self.now, BASE + self.now, kind, 1000))
        self.p.put32(TREES + 0x64, n + 1)

    def fruit(self) -> list[int]:
        return [struct.unpack("<i", self.p.read(self.rec(i) + 0x14, 4))[0] for i in range(self.count())]

    def set_fruit(self, *values: int) -> None:
        for i, v in enumerate(values):
            self.p.write(self.rec(i) + 0x14, struct.pack("<i", v))

    def timers(self) -> list[int]:
        return [self.p.u32(self.rec(i) + 0xC) for i in range(self.count())]

    def kill(self, i: int) -> None:
        """A dead tree: no position (the update's tail removes it, 0x43487F)."""
        self.p.write(self.rec(i), struct.pack("<2i", 0, 0))

    # ---- time ------------------------------------------------------------------------
    def tick(self) -> None:
        """One frame of the world: every object's update (0x435880 -> the trees' 0x434760)."""
        self.p.call(WORLD_UPDATE, [], ecx=WORLD)

    def run(self, until: int, step: int = 60, eat: bool = False):
        """Frames every `step` game seconds up to `until`; returns [(time, tree, gained)].
        With `eat`, every tree is picked bare after each frame, so the 1,000 cap never binds."""
        gains = []
        while self.now < until:
            self.now = min(self.now + step, until)
            before = self.fruit()
            self.tick()
            for i, (a, b) in enumerate(zip(before, self.fruit())):
                if b != a:
                    gains.append((self.now, i, b - a))
            if eat:
                self.set_fruit(*([0] * self.count()))
        return gains

    # ---- save and load ---------------------------------------------------------------
    def save(self) -> bytes:
        """The world objects' save (0x435790), the trees' saver (0x433EC0) among them."""
        out = self.p.alloc(0x1000)
        self.p.call(WORLD_SAVE, [out, 0x1000], ecx=WORLD)
        return self.p.read(out, 0xD4 + 0x60)

    def load(self, data: bytes) -> None:
        """The world objects' load (0x435710), the trees' loader (0x433E40) among them."""
        buf = self.p.alloc(0x1000)
        self.p.write(buf, data)
        self.p.call(WORLD_LOAD, [buf], ecx=WORLD)

    def side(self, slot: int = 1) -> bytes | None:
        return self.files.files.get(SIDE.format(s=slot).lower()) if self.files else None


def saved_timers(data: bytes) -> list[int]:
    count = struct.unpack_from("<i", data, 0xD4 + 0x5C)[0]
    return [struct.unpack_from("<I", data, 0xD4 + 0x14 + 0x18 * i + 0xC)[0] for i in range(count)]


def refill_times(gains) -> list[int]:
    return sorted({t for t, _, _ in gains})


def per_tree(gains, n: int) -> list[list[tuple[int, int]]]:
    out = [[] for _ in range(n)]
    for t, i, g in gains:
        out[i].append((t, g))
    return out


@unittest.skipUnless(HAVE_EMULATOR and both_factions.have_stock() and all(d.is_file() for d in DLLS.values()),
                     "stock VV3 executable, the emulator or the companions not present")
class FruitTreeTimingTests(unittest.TestCase):

    # ---- installing --------------------------------------------------------------------
    def test_installs_over_the_stock_bytes_all_or_none(self):
        for companion in DLLS:
            for mode, expanded in BUILDS:
                with self.subTest(mode=mode, expanded=expanded):
                    v = Village(companion, mode, expanded)
                    for va in SITES:
                        self.assertEqual(v.p.read(va, 1), b"\xE9", f"{companion} 0x{va:X}")
                    for va, stock in SITES.items():
                        # Any one site not stock: nothing at all is written.
                        w = Village(companion, mode, expanded, install=False)
                        w.p.write(va, b"\xCC")
                        w.p.export("VvfpStartup", 3, 0)
                        for other, other_stock in SITES.items():
                            if other != va:
                                self.assertEqual(w.p.read(other, len(other_stock) // 2).hex().upper(), other_stock)
                    # An interval test that is neither stock nor the Nature patch: nothing.
                    w = Village(companion, mode, expanded, install=False)
                    w.p.write(0x4347AA, b"\x90")
                    w.p.export("VvfpStartup", 3, 0)
                    for va, stock in SITES.items():
                        self.assertEqual(w.p.read(va, len(stock) // 2).hex().upper(), stock)
                    # Another game: nothing.
                    w = Village(companion, mode, expanded, install=False)
                    w.p.export("VvfpStartup", 4, 0)
                    for va, stock in SITES.items():
                        self.assertEqual(w.p.read(va, len(stock) // 2).hex().upper(), stock)

    def test_the_two_never_install_together(self):
        # The second companion finds the first one's jumps, not the stock bytes, and installs
        # nothing (the patcher never ships both; this is the run-time guard).
        v = Village(TOGETHER)
        before = {va: v.p.read(va, len(s) // 2) for va, s in SITES.items()}
        other = Process(render("stock"), DLLS[TURNS])
        for va, data in before.items():
            other.write(va, data)
        other.export("VvfpStartup", 3, 0)
        for va, data in before.items():
            self.assertEqual(other.read(va, len(data)), data)

    # ---- one tree is the stock game exactly --------------------------------------------
    def test_one_tree_is_the_stock_game(self):
        # With one tree there is nothing to line up: fruit and timer match the stock game
        # frame by frame, at Nature 0 and 1, with and without the Nature patch.
        images = [("catalog", render("stock")), ("no Nature patch", render_without_nature("stock"))]
        for companion in DLLS:
            for name, image in images:
                for level in (0, 1):
                    with self.subTest(companion=companion, image=name, nature=level):
                        runs = []
                        for which in (companion, None):
                            v = Village(which, image=image)
                            v.nature(level)
                            v.now = 500
                            v.plant(0x500)
                            v.set_fruit(0)
                            history = []
                            for step in range(400):
                                v.now += 397
                                v.tick()
                                history.append((v.fruit()[0], v.timers()[0]))
                                if step % 7 == 0:
                                    v.set_fruit(max(0, v.fruit()[0] - 150))
                            runs.append(history)
                        self.assertEqual(runs[0], runs[1])

    # ---- together ------------------------------------------------------------------------
    def test_three_trees_planted_apart_refill_at_the_same_moment(self):
        for mode, expanded in BUILDS:
            with self.subTest(mode=mode, expanded=expanded):
                v = Village(TOGETHER, mode, expanded)
                for at, x in ((0, 0x500), (3000, 0x600), (6600, 0x700)):
                    v.now = at
                    v.plant(x, kind=len(v.fruit()))
                v.set_fruit(100, 100, 100)
                gains = v.run(3 * T_STOCK + 60)
                # The first tree is due at 10,800: all three refill then, each paid for its own
                # time since planting; then every 10,800 s together, 111 each.
                self.assertEqual(refill_times(gains), [10800, 21600, 32400])
                first = {i: g for t, i, g in gains if t == 10800}
                self.assertEqual(first, {0: 10800 * 37 // 3600, 1: 7800 * 37 // 3600, 2: 4200 * 37 // 3600})
                for t in (21600, 32400):
                    self.assertEqual({i: g for tt, i, g in gains if tt == t}, {0: 111, 1: 111, 2: 111})
                # The trees' own timers are the stock game's.
                stock = Village(None, mode, expanded)
                for at, x in ((0, 0x500), (3000, 0x600), (6600, 0x700)):
                    stock.now = at
                    stock.plant(x, kind=len(stock.fruit()))
                stock.set_fruit(100, 100, 100)
                stock_gains = stock.run(3 * T_STOCK + 60)
                self.assertEqual(v.timers(), stock.timers())
                self.assertEqual(refill_times(stock_gains), [10800, 13800, 17400, 21600, 24600, 28200, 32400])

    def test_the_fruit_over_time_is_the_stock_games(self):
        # Five days, every tree picked bare after every frame (the cap never binds): each
        # tree's fruit, paid plus earned since its last refill, is the stock game's to within
        # the rounding of the refills (under one fruit each).
        for companion in DLLS:
            for mode, expanded in BUILDS:
                with self.subTest(mode=mode, expanded=expanded):
                    with self.subTest(companion=companion):
                        totals = []
                        for which in (companion, None):
                            v = Village(which, mode, expanded)
                            for at, x in ((0, 0x500), (1234, 0x600), (9000, 0x700)):
                                v.now = at
                                v.plant(x, kind=len(v.fruit()))
                            gains = v.run(5 * 86400, step=120, eat=True)
                            trees = per_tree(gains, 3)
                            earned = []
                            for i in range(3):
                                last = trees[i][-1][0]
                                earned.append((sum(g for _, g in trees[i]) + (v.now - last) * 37 / 3600,
                                               len(trees[i])))
                            totals.append(earned)
                        for (mine, refills), (stock, stock_refills) in zip(*totals):
                            self.assertLessEqual(abs(mine - stock), max(refills, stock_refills) + 1)

    # ---- in turns ------------------------------------------------------------------------
    def test_three_trees_take_turns_an_hour_apart(self):
        for mode, expanded in BUILDS:
            with self.subTest(mode=mode, expanded=expanded):
                v = Village(TURNS, mode, expanded)
                for x in (0x500, 0x600, 0x700):
                    v.plant(x, kind=len(v.fruit()))
                v.set_fruit(0, 0, 0)
                gains = v.run(3 * T_STOCK + 60)
                # Planted together: the first refills at 10,800, the others follow an hour apart
                # (paid for their longer wait), then one tree every hour, 111 each.
                self.assertEqual(refill_times(gains), [10800 + 3600 * k for k in range(7)])
                self.assertEqual([g for _, _, g in sorted(gains)][:3], [111, 14400 * 37 // 3600, 18000 * 37 // 3600])
                self.assertTrue(all(g == 111 for _, _, g in sorted(gains)[3:]))
                self.assertEqual(len({i for _, i, _ in gains}), 3)

    def test_turns_with_the_nature_patch_are_45_minutes_apart(self):
        v = Village(TURNS)
        v.nature(1)
        for x in (0x500, 0x600, 0x700):
            v.plant(x, kind=len(v.fruit()))
        v.set_fruit(0, 0, 0)
        gains = v.run(4 * T_NATURE_PATCH)
        times = refill_times(gains)
        self.assertEqual(times[:6], [8100 + 2700 * k for k in range(6)])
        self.assertTrue(all(g == 8100 * 56 // 3600 for t, _, g in gains if t >= 8100 * 2))

    # ---- planting and losing a tree ------------------------------------------------------
    def test_a_new_tree_joins_the_schedule(self):
        # Together: planted between refills, it refills with the others at their next one.
        v = Village(TOGETHER)
        for x in (0x500, 0x600):
            v.plant(x, kind=len(v.fruit()))
        v.run(10800)
        v.now = 15000
        v.plant(0x700, kind=2)
        v.set_fruit(0, 0, 0)       # (picked bare, to see every refill)
        gains = v.run(21600 + 60)
        self.assertEqual({i: g for t, i, g in gains if t == 21600},
                         {0: 111, 1: 111, 2: 6600 * 37 // 3600})
        self.assertEqual(refill_times(gains), [21600])
        # In turns: two trees 1 h 30 min apart, then three 1 h apart.
        v = Village(TURNS)
        for x in (0x500, 0x600):
            v.plant(x, kind=len(v.fruit()))
        v.set_fruit(0, 0)
        gains = v.run(30000)
        self.assertEqual(refill_times(gains), [10800, 16200, 21600, 27000])
        v.plant(0x700, kind=2)
        v.set_fruit(0, 0, 0)
        gains = v.run(30000 + 2 * T_STOCK)
        times = refill_times(gains)
        self.assertEqual([b - a for a, b in zip(times, times[1:])], [3600] * (len(times) - 1))
        self.assertEqual(len({i for _, i, _ in gains}), 3)

    def test_a_removed_tree_leaves_the_schedule(self):
        v = Village(TURNS)
        for x in (0x500, 0x600, 0x700):
            v.plant(x, kind=len(v.fruit()))
        v.set_fruit(0, 0, 0)
        v.run(20000)
        v.kill(2)
        v.tick()
        self.assertEqual(v.count(), 2, "the stock tail removed it")
        v.set_fruit(0, 0)
        gains = v.run(20000 + 3 * T_STOCK)
        times = refill_times(gains)
        self.assertEqual([b - a for a, b in zip(times, times[1:])], [5400] * (len(times) - 1))
        # Together: the two left go on together.
        v = Village(TOGETHER)
        for at, x in ((0, 0x500), (1800, 0x600), (3600, 0x700)):
            v.now = at
            v.plant(x, kind=len(v.fruit()))
        v.run(12000)
        v.kill(2)
        v.set_fruit(0, 0, 0)
        gains = v.run(12000 + 2 * T_STOCK)
        self.assertEqual(refill_times(gains), [21600, 32400])
        self.assertEqual({i for _, i, _ in gains}, {0, 1})

    # ---- catch-up and Time Warp ----------------------------------------------------------
    def test_catch_up_and_time_warp_pay_what_the_stock_game_pays(self):
        # The clock jumps by more than the interval (the time the game was closed, or a Time
        # Warp), so every tree is due, and the first frame after it pays for the whole time.  Each tree's fruit from planting to the jump is the
        # stock game's to within rounding (the companion paid part of it at its earlier shared
        # refill); a jump long enough to fill the trees leaves them full in both; the trees'
        # own timers are the stock game's.
        for companion in DLLS:
            for mode, expanded in BUILDS:
                with self.subTest(mode=mode, expanded=expanded):
                    for jump in (40000, 2 * 86400):
                        with self.subTest(companion=companion, jump=jump):
                            results = []
                            for which in (companion, None):
                                v = Village(which, mode, expanded)
                                for at, x in ((0, 0x480), (2400, 0x600), (6000, 0x700)):
                                    v.now = at
                                    v.plant(x, kind=len(v.fruit()))
                                v.set_fruit(0, 0, 0)
                                gains = v.run(12000, eat=True)
                                v.now += jump
                                v.tick()
                                paid = [sum(g for _, g in tree) for tree in per_tree(gains, 3)]
                                results.append(([a + b for a, b in zip(paid, v.fruit())], v.fruit(), v.timers()))
                            (total, fruit, timers), (stock_total, stock_fruit, stock_timers) = results
                            self.assertEqual(timers, stock_timers)
                            if jump * 37 // 3600 >= 1000:
                                self.assertEqual(fruit, [1000, 1000, 1000])
                                self.assertEqual(stock_fruit, [1000, 1000, 1000])
                            else:
                                for mine, stock in zip(total, stock_total):
                                    self.assertLessEqual(abs(mine - stock), 2)
        # In turns, after the jump the trees are spread out again.
        v = Village(TURNS)
        for x in (0x500, 0x600, 0x700):
            v.plant(x, kind=len(v.fruit()))
        v.now = 3 * 86400
        v.tick()
        v.set_fruit(0, 0, 0)
        times = refill_times(v.run(v.now + 2 * T_STOCK))
        self.assertEqual([b - a for a, b in zip(times, times[1:])], [3600] * (len(times) - 1))

    # ---- the save, the file, the load -----------------------------------------------------
    def _played(self, companion, files=None, mode="stock", expanded=False):
        v = Village(companion, mode, expanded, files=files)
        for at, x in ((0, 0x500), (2500, 0x600), (6000, 0x700)):
            v.now = at
            v.plant(x, kind=len(v.fruit()))
        v.set_fruit(0, 0, 0)
        v.run(30000)
        return v

    def test_the_save_holds_the_stock_timers_and_the_file_the_schedule(self):
        for companion in DLLS:
            for mode, expanded in BUILDS:
                with self.subTest(mode=mode, expanded=expanded):
                    with self.subTest(companion=companion):
                        v = self._played(companion, mode=mode, expanded=expanded)
                        stock = self._played(None, mode=mode, expanded=expanded)
                        data = v.save()
                        self.assertEqual(saved_timers(data), saved_timers(stock.save()))
                        self.assertIsNotNone(v.side(1))
                        # Loaded with the same companion: the schedule goes on exactly as it would have.
                        files = v.files.files
                        after = Village(companion, mode, expanded, files=files)
                        after.now = v.now
                        after.load(data)
                        self.assertEqual(after.fruit(), v.fruit())
                        expected = v.run(v.now + 2 * T_STOCK)
                        got = after.run(after.now + 2 * T_STOCK)
                        self.assertEqual(got, expected)

    def test_without_the_patch_the_save_goes_on_as_the_stock_game(self):
        v = self._played(TOGETHER)
        data = v.save()
        stock = self._played(None)
        loaded = Village(None)
        loaded.now = v.now
        loaded.load(data)
        stock.set_fruit(*loaded.fruit())
        self.assertEqual(loaded.timers(), stock.timers())
        self.assertEqual(loaded.run(v.now + 2 * T_STOCK), stock.run(v.now + 2 * T_STOCK))

    def test_switching_patches_starts_from_the_stock_timers(self):
        for first, second in ((TOGETHER, TURNS), (TURNS, TOGETHER)):
            with self.subTest(first=first):
                v = self._played(first)
                data = v.save()
                switched = Village(second, files=v.files.files)
                switched.now = v.now
                switched.load(data)
                fresh = Village(second)          # no file at all: the stock timers
                fresh.now = v.now
                fresh.load(data)
                self.assertEqual(switched.run(v.now + 2 * T_STOCK), fresh.run(v.now + 2 * T_STOCK))
                # The other patch's entries are dropped when this one saves.
                switched.save()
                self.assertEqual(struct.unpack_from("<I", switched.side(1), 16)[0], 1)

    def test_an_entry_is_used_only_by_the_save_it_was_written_with(self):
        v = self._played(TURNS)
        data = v.save()
        changed = bytearray(data)
        changed[0xD4 + 0x14 + 0x14] ^= 1        # tree 0's fruit, one more or less
        other = Village(TURNS, files=v.files.files)
        other.now = v.now
        other.load(bytes(changed))
        fresh = Village(TURNS)
        fresh.now = v.now
        fresh.load(bytes(changed))
        self.assertEqual(other.run(v.now + 2 * T_STOCK), fresh.run(v.now + 2 * T_STOCK))
        # Another slot's file is never read.
        elsewhere = Village(TURNS, files=v.files.files, slot=2)
        elsewhere.now = v.now
        elsewhere.load(data)
        fresh = Village(TURNS, slot=2)
        fresh.now = v.now
        fresh.load(data)
        self.assertEqual(elsewhere.run(v.now + 2 * T_STOCK), fresh.run(v.now + 2 * T_STOCK))

    def test_the_file_keeps_the_last_sixteen_saves(self):
        v = self._played(TOGETHER)
        for k in range(20):
            v.set_fruit(k, 0, 0)
            v.save()
        side = v.side(1)
        self.assertEqual(struct.unpack_from("<5I", side, 0)[:5], (0x54335656, 1, 3, 1, 16))

    def test_an_unreadable_file_is_never_replaced(self):
        v = self._played(TOGETHER)
        path = SIDE.format(s=1).lower()
        v.files.files[path] = b"locked bytes"
        v.files.locked.add(path)
        v.save()
        self.assertEqual(v.files.files[path], b"locked bytes")


class StartOverTests(unittest.TestCase):
    def test_start_over_deletes_the_file(self):
        source = (ROOT / "native" / "shared" / "save_reset.c").read_text(encoding="utf-8")
        self.assertIn('DATA_FORMAT("Fruit Trees", "Virtual Villagers 3 Fruit Tree Timers")', source)
        row = source[source.index("/* VV3 */"):source.index("/* VV4 */")]
        self.assertIn("FRUIT_TREES_FORMAT", row)
        for feature_id in (TOGETHER, TURNS):
            self.assertIn(feature_id, patcher.START_OVER_RESET_SIDECAR_OWNERS["vv3"])

    def test_each_row_ships_its_own_companion_started_by_the_loader(self):
        by_id = {p.id: p for p in patcher.load_public_fun_patches()}
        for feature_id, dll in DLLS.items():
            row = by_id[feature_id]
            self.assertEqual([c["destination"] for c in row.raw["companion_files"]], [dll.name])
            self.assertEqual(row.raw["patches"], [])
            self.assertIn(dll.name, patcher.STARTUP_LOADER_COMPANIONS)
            index = patcher.STARTUP_LOADER_COMPANIONS.index(dll.name)
            self.assertEqual(patcher._startup_loader_mask("vv3", [row]) & ~1, 1 << (index + 1))
        header = (ROOT / "native" / "shared" / "startup_companions.h").read_text(encoding="utf-8")
        for dll in DLLS.values():
            self.assertIn(f'"{dll.name}"', header)


if __name__ == "__main__":
    unittest.main()
