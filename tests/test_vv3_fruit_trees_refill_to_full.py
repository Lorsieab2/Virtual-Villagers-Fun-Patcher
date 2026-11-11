"""All Fruit Trees Refill to Full (The Secret City): vv3_fruit_trees_refill_to_full (data/builds.json).

The stock refill (0x434760) adds floor(elapsed x factor / 3600) to a tree once its timer is the interval old; the
patch turns the add at 0x4347EB (mov eax,[edi] / shr edx,0xB / add eax,edx) into mov eax,0x3E8 / nop / nop, so the
refill sets the tree to 1,000.  Everything here runs the patcher's rendered bytes in the emulator through the game's
own world update 0x435880 (tests/test_vv3_fruit_tree_timing.py's Village: only the clock and the planting puzzle's
check are stand-ins): stock and patched, Nature 0 and 1, with and without "Nature Level 1 Actually Replenishes Food
Sources Faster", in all three population modes and the 256 Villagers build, and with each fruit-tree timing companion
("All Fruit Trees Refill at the Same Time" / "Fruit Trees Take Turns Refilling"), which replace the loop and read the
same bytes.

The live effect in a running game is NOT verified here.
"""
from __future__ import annotations

import functools
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_fun_patcher as patcher  # noqa: E402
import vv_fun_patcher_gui as gui  # noqa: E402

try:
    import capstone
    import test_vv3_fruit_tree_timing as timing
    from test_vv3_fruit_tree_timing import BASE, Village
    import test_vv3_both_factions as both_factions

    HAVE_EMULATOR = timing.HAVE_EMULATOR and both_factions.have_stock() and all(d.is_file() for d in timing.DLLS.values())
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

FULL = "vv3_fruit_trees_refill_to_full"
NATURE = "vv3_nature_honey_refill"
TOGETHER, TURNS = "vv3_fruit_trees_refill_together", "vv3_fruit_trees_take_turns"
ADD_VA, ADD_STOCK, ADD_FULL = 0x4347EB, "8B07C1EA0B03C2", "B8E80300009090"
MODES = ("stock", "collection_progression", "immediate_fixed")
BUILDS = [(m, False) for m in MODES] + [("immediate_fixed", True)]


@functools.lru_cache(maxsize=None)
def render(mode: str, expanded: bool = False, *, full: bool = True, nature: bool = True) -> bytes:
    """The Secret City with this patch (and the Nature patch), as the patcher renders it; 256 Villagers when
    `expanded`."""
    build = {b.id: b for b in patcher.load_builds()}["vv3"]
    ids = ([FULL] if full else []) + ([NATURE] if nature else []) + (["vv3_population_256"] if expanded else [])
    data, _ = patcher.render_patched_bytes(both_factions.stock_exe(), build, mode, ids)
    return bytes(data)


def one_tree(image: bytes, companion: str | None = None, level: int = 0, fruit: int = 100) -> Village:
    v = Village(companion, image=image)
    v.nature(level)
    v.now = 500
    v.plant(0x500)
    v.set_fruit(fruit)
    return v


class TheRow(unittest.TestCase):
    def test_the_manifest_bytes(self) -> None:
        row = {p.id: p for p in patcher.load_fun_patches()}[FULL]
        self.assertEqual(row.raw["game_id"], "vv3")
        self.assertEqual([(e["offset"], e["before"], e["after"]) for e in row.raw["patches"]],
                         [("0x347EB", ADD_STOCK, ADD_FULL)])

    def test_defaults(self) -> None:
        # Off by default; Owner's Defaults ticks it (the owner, 2026-11-11); not a cheat.
        self.assertIn(FULL, gui.DEFAULT_OFF_FUN_PATCH_IDS)
        self.assertNotIn(FULL, gui.OWNERS_DEFAULT_OFF_FUN_PATCH_IDS)
        self.assertNotIn(FULL, gui.SELECT_ALL_OFF_FUN_PATCH_IDS)

    def test_the_description_states_the_timing_patches_in_bold(self) -> None:
        text = {p.id: p for p in patcher.load_fun_patches()}[FULL].raw["description"]
        self.assertIn("**Works with \"All Fruit Trees Refill at the Same Time\" and \"Fruit Trees Take Turns "
                      "Refilling\"", text)
        self.assertIn("Nature Level 1 Actually Replenishes Food Sources Faster", text)
        for other in (TOGETHER, TURNS):
            self.assertIn("All Fruit Trees Refill to Full", {p.id: p for p in patcher.load_fun_patches()}[other]
                          .raw["description"])


@unittest.skipUnless(HAVE_EMULATOR, "stock VV3 executable, the emulator or the companions not present")
class TheBytes(unittest.TestCase):
    def test_rendered_in_every_mode_and_the_256_build(self) -> None:
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        for mode, expanded in BUILDS:
            with self.subTest(mode=mode, expanded=expanded):
                v = Village(None, image=render(mode, expanded))
                code = v.p.read(ADD_VA, 7)
                self.assertEqual(code.hex().upper(), ADD_FULL)
                self.assertEqual([(i.mnemonic, i.op_str) for i in md.disasm(code, ADD_VA)],
                                 [("mov", "eax, 0x3e8"), ("nop", ""), ("nop", "")])
                # The Nature patch's own bytes (0x4347AA, 0x4347CD) are untouched by this one.
                self.assertEqual(v.p.read(0x4347AA, 1), b"\xE9")
                self.assertEqual(v.p.read(0x4347CD, 5).hex().upper(), "BD38000000")
        stock = Village(None, image=render("stock", full=False, nature=False))
        self.assertEqual(stock.p.read(ADD_VA, 7).hex().upper(), ADD_STOCK)


@unittest.skipUnless(HAVE_EMULATOR, "stock VV3 executable, the emulator or the companions not present")
class TheStockLoop(unittest.TestCase):
    """The game's own loop (no companion)."""

    def refill(self, image: bytes, level: int, at: int) -> tuple[int, int]:
        """The fruit one game second before the tree's refill is due and at it (100 fruit, planted at 500)."""
        v = one_tree(image, level=level)
        v.now = 500 + at - 1
        v.tick()
        before = v.fruit()[0]
        v.now = 500 + at
        v.tick()
        return before, v.fruit()[0]

    def test_stock_adds_the_share_and_the_patch_fills_to_1000(self) -> None:
        stock = render("stock", full=False, nature=False)
        self.assertEqual(self.refill(stock, 0, 10800), (100, 211))           # +111
        self.assertEqual(self.refill(stock, 1, 10800), (100, 226))           # +126 at Nature 1
        for mode, expanded in BUILDS:
            with self.subTest(mode=mode, expanded=expanded):
                image = render(mode, expanded)
                self.assertEqual(self.refill(image, 0, 10800), (100, 1000))
                # With the Nature patch, Nature 1 refills at 2 hours 15 minutes -- to full.
                self.assertEqual(self.refill(image, 1, 8100), (100, 1000))

    def test_without_the_nature_patch_nature_1_still_waits_3_hours(self) -> None:
        image = render("stock", nature=False)
        self.assertEqual(self.refill(image, 1, 8100), (100, 100))
        self.assertEqual(self.refill(image, 1, 10800), (100, 1000))

    def test_after_a_long_absence_one_refill_fills_it(self) -> None:
        for full, expected in ((False, 100 + (30 * 3600) * 37 // 3600), (True, 1000)):
            v = one_tree(render("stock", full=full, nature=False), fruit=0 if full else 100)
            v.now = 500 + 30 * 3600                                         # 30 hours away: one catch-up pass
            v.tick()
            self.assertEqual(v.fruit()[0], min(1000, expected))
        # A tree with 0 fruit and only just due: stock 111, the patch 1,000.
        v = one_tree(render("stock"), fruit=0)
        v.now = 500 + 10800
        v.tick()
        self.assertEqual(v.fruit()[0], 1000)

    def test_the_timer_and_the_interval_stay_stock(self) -> None:
        runs = []
        for full in (False, True):
            v = one_tree(render("stock", full=full))
            history = []
            for _ in range(300):
                v.now += 397
                v.tick()
                history.append(v.timers()[0])
                v.set_fruit(0)
            runs.append(history)
        self.assertEqual(runs[0], runs[1])


@unittest.skipUnless(HAVE_EMULATOR, "stock VV3 executable, the emulator or the companions not present")
class WithTheTimingPatches(unittest.TestCase):
    """Both timing companions replace the loop: they read 0x4347EB and fill to 1,000 too."""

    def plant_three(self, v: Village) -> None:
        for at, x in ((0, 0x500), (3000, 0x600), (6600, 0x700)):
            v.now = at
            v.plant(x, kind=len(v.fruit()))
        v.set_fruit(100, 100, 100)

    def test_they_install_over_the_patch_and_refuse_anything_else(self) -> None:
        for companion in (TOGETHER, TURNS):
            for mode, expanded in BUILDS:
                with self.subTest(companion=companion, mode=mode, expanded=expanded):
                    v = Village(companion, image=render(mode, expanded))
                    for va in timing.SITES:
                        self.assertEqual(v.p.read(va, 1), b"\xE9")
            # Neither the stock add nor the patch's mov: nothing at all is written.
            w = Village(companion, image=render("stock"), install=False)
            w.p.write(ADD_VA, b"\x90")
            w.p.export("VvfpStartup", 3, 0)
            for va, stock in timing.SITES.items():
                self.assertEqual(w.p.read(va, len(stock) // 2).hex().upper(), stock)

    def test_together_fills_every_tree_at_the_shared_refill(self) -> None:
        for mode, expanded in BUILDS:
            with self.subTest(mode=mode, expanded=expanded):
                v = Village(TOGETHER, image=render(mode, expanded))
                self.plant_three(v)
                gains = v.run(10800 + 60)
                self.assertEqual(timing.refill_times(gains), [10800])
                self.assertEqual(v.fruit(), [1000, 1000, 1000])
                v.set_fruit(5, 5, 5)
                gains = v.run(2 * 10800 + 60)
                self.assertEqual(timing.refill_times(gains), [21600])
                self.assertEqual(v.fruit(), [1000, 1000, 1000])

    def test_turns_fill_one_tree_an_hour(self) -> None:
        v = Village(TURNS, image=render("stock"))
        for x in (0x500, 0x600, 0x700):
            v.plant(x, kind=len(v.fruit()))
        v.set_fruit(0, 0, 0)
        gains = v.run(2 * 10800, eat=False)
        # Each refill fills one tree from 0 to 1,000; the refills come an hour apart.
        times = timing.refill_times(gains)
        self.assertTrue(all(b - a == 3600 for a, b in zip(times, times[1:])), times)
        self.assertTrue(all(g == 1000 for _, _, g in gains), gains)
        self.assertEqual(v.fruit(), [1000, 1000, 1000])

    def test_with_the_nature_patch_at_nature_1_the_interval_is_2h15(self) -> None:
        for companion in (TOGETHER, TURNS):
            with self.subTest(companion=companion):
                v = one_tree(render("stock"), companion, level=1)
                v.now = 500 + 8100 - 1
                v.tick()
                self.assertEqual(v.fruit(), [100])
                v.now = 500 + 8100
                v.tick()
                self.assertEqual(v.fruit(), [1000])

    def test_one_tree_is_the_patched_stock_loop_exactly(self) -> None:
        # With one tree there is nothing to line up: frame for frame the companion is the patched game's own loop.
        for companion in (TOGETHER, TURNS):
            for level in (0, 1):
                with self.subTest(companion=companion, nature=level):
                    runs = []
                    for which in (companion, None):
                        v = one_tree(render("stock"), which, level=level, fruit=0)
                        history = []
                        for step in range(300):
                            v.now += 397
                            v.tick()
                            history.append((v.fruit()[0], v.timers()[0]))
                            if step % 7 == 0:
                                v.set_fruit(max(0, v.fruit()[0] - 150))
                        runs.append(history)
                    self.assertEqual(runs[0], runs[1])
                    self.assertIn(1000, [f for f, _ in runs[0]])


class GameMechanicsPage(unittest.TestCase):
    """The Secret City's Game Mechanics page (src/vv_game_mechanics_vv3.py) with the patch in the game: every refill
    is to 1,000; without it the page is as before."""

    def read(self, data: bytes, features, now=None):
        import test_game_mechanics as page
        folder = page.Folder(self)
        folder.save(data, 1)
        return page.gm.read(folder.path, 3, 1, [folder.game(features)], now=now)

    def test_the_lines_with_and_without_the_patch(self) -> None:
        import test_game_mechanics as page
        clock = (6, 0, 100_000, 50_000)
        save = page.make_save(clock=clock, trees=[(1, 50_400, 51_000, 300)])
        on = self.read(save, [FULL], now=page.real(clock, 52_000))
        text = page.text_of(on)
        self.assertIn(f"Next refill due {page.gm.when(page.real(clock, 51_000 + 10_800))} (700 fruit).",
                      page.tree(on))
        self.assertIn("Fruit trees: each is refilled to 1,000 every 3 hours on Normal speed; Nature is level 0.", text)
        self.assertIn("\"All Fruit Trees Refill to Full\" is in the game: every fruit tree refill fills the tree to "
                      "1,000", text)
        self.assertNotIn("each gains 111 fruit", text)
        off = self.read(save, ["vv3_birth_control"], now=page.real(clock, 52_000))
        self.assertIn(f"Next refill due {page.gm.when(page.real(clock, 51_000 + 10_800))} (111 fruit).",
                      page.tree(off))
        self.assertNotIn("\"All Fruit Trees Refill to Full\" is in the game", page.text_of(off))
        self.assertIn("each gains 111 fruit", page.text_of(off))

    def test_time_away_and_paused(self) -> None:
        import test_game_mechanics as page
        clock = (6, 0, 100_000, 50_000)
        closed = self.read(page.make_save(clock=clock, trees=[(0, 1, 40_000, 100)]), [FULL],
                           now=page.real(clock, 50_000) + 20_000)
        self.assertTrue(any(line.startswith("The next time the village is played it gets 900 fruit")
                            for line in page.tree(closed)))
        paused = self.read(page.make_save(clock=(0, 6, 100_000, 50_000), speed=1005, trees=[(0, 1, 45_000, 10)]),
                           [FULL], now=page.EPOCH + 999_999)
        self.assertIn(f"Next refill (fills it to 1,000) after {page.gm.duration(5_800)} more of play once unpaused.",
                      page.tree(paused))

    def test_with_the_nature_patch(self) -> None:
        import test_game_mechanics as page
        on = self.read(page.make_save(techs=(1, 1, 1, 1, 1, 1, 0), trees=[(0, 1, 1, 0)]), [FULL, NATURE])
        self.assertIn("refills every 2 hours 15 minutes on Normal speed.", page.planted(on))
        self.assertIn("Fruit trees: each is refilled to 1,000 every 2 hours 15 minutes on Normal speed",
                      page.text_of(on))


if __name__ == "__main__":
    unittest.main()
