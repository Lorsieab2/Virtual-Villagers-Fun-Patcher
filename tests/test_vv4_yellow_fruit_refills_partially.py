"""Yellow Breadfruit Refills Partially Every Time (The Tree of Life): vv4_yellow_fruit_refills_partially.

With "Yellow Fruit Trees are No Longer Unlimited" ("VVFP VV4 Fruit Supply.dll") the tree is refilled to full every 40
age units.  This row ships one file, "VVFP VV4 Fruit Partial Refill.txt", in the patcher's folder; the companion sees
it at start and instead adds floor(units x 37 / 10) every 30 age units -- 111, The Secret City's fruit-tree pace (37
an hour, 3 hours on Normal) -- up to 1,000.  The shipped DLL runs beside The Tree of Life's own life tick in the
emulator (tests/test_vv4_yellow_fruit_trees_limited.py's Tree), with the flag present or not.

The live effect in a running game is NOT verified here.
"""
from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import patcher_files  # noqa: E402
import vv_fun_patcher as patcher  # noqa: E402
import vv_fun_patcher_gui as gui  # noqa: E402

try:
    import test_vv4_yellow_fruit_trees_limited as limited
    from test_vv4_yellow_fruit_trees_limited import identity, side, tree_file
    import farmers_emulation_vv4 as fe
    import test_vv3_both_factions as both_factions

    HAVE_EMULATOR = limited.HAVE_EMULATOR
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

ID = "vv4_yellow_fruit_refills_partially"
LIMITED = "vv4_yellow_fruit_trees_limited"
FEATURE = ROOT / "data" / f"{ID}_feature.json"
FLAG = "VVFP VV4 Fruit Partial Refill.txt"
FLAG_PATH = ("C:\\Games\\Village\\" + patcher_files.PATCHER_FILES_FOLDER + "\\" + FLAG).lower()


class Partial(limited.Tree if HAVE_EMULATOR else object):
    """A Tree of Life village with the fruit companion, the partial row's file there (`flag`) or not."""

    def __init__(self, flag: bool = True, *, files: dict | None = None, seed: int = 3, slot: int = 1):
        self.v = fe.Village(seed=seed, berries=0, solved=(6,), exe=None, dll=limited.DLL)
        self.patched = True
        self.files = both_factions.Files(self.v.process)
        if files is not None:
            self.files.files = files
        self.asked: list[str] = []

        def attributes(p):
            path = p.wstring(p.arg(0))
            self.asked.append(path)
            return (0x20 if flag and path.lower() == FLAG_PATH else 0xFFFFFFFF), 4

        self.v.process.api_handlers["GetFileAttributesW"] = attributes
        self.v.process.export("VvfpStartup", 4, 0)
        assert self.v.process.export("VvfpYellowFruitInstalled") == 1
        self.v.w32(fe.GAME + limited.SLOT_FIELD, slot)

    def units(self, n: int) -> None:
        """`n` age units of the reference villager (index 0), live, one life tick each."""
        r = self.v.rec(0)
        for _ in range(n):
            age = self.v.r32(r + fe.AGE) + 1
            self.v.w32(r + fe.AGE, age)
            self.v.w32(r + fe.PROC_AGE, age - 1)
            self.v.life_tick(count_turns=True)

    def catch_up(self, behind: int) -> None:
        """`behind` age units in one catch-up life tick (time away), no Cooking Pit bonus paid."""
        r = self.v.rec(0)
        age = self.v.r32(r + fe.AGE) + behind
        self.v.w32(r + fe.AGE, age)
        self.v.w32(r + fe.PROC_AGE, age - behind)
        self.v.by_caller[limited.BONUS_ROLL] = 99          # no bonus pays (rand(100) < Farming - 25 fails)
        self.v.life_tick(count_turns=True)
        assert self.v.r32(r + fe.PROC_AGE) == age


class TheRow(unittest.TestCase):
    def setUp(self) -> None:
        self.row = json.loads(FEATURE.read_text(encoding="utf-8"))

    def test_needs_the_limited_tree_and_ships_only_the_flag(self) -> None:
        self.assertEqual(self.row["dependencies"], [LIMITED])
        self.assertEqual(self.row["patches"], [])
        self.assertEqual([c["destination"] for c in self.row["companion_files"]], [FLAG])
        source = ROOT / self.row["companion_files"][0]["source"]
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest().upper(),
                         self.row["companion_files"][0]["sha256"])
        self.assertIn(FLAG, patcher_files.PATCHER_READS)
        self.assertIn(ID, {p.id for p in patcher.load_public_fun_patches()})
        # The patcher installs it in the patcher's folder, beside the companions.
        self.assertEqual(patcher_files.installed_relative_path(FLAG).as_posix(),
                         patcher_files.PATCHER_FILES_FOLDER + "/" + FLAG)

    def test_it_needs_the_limited_tree(self) -> None:
        # The window ticks a prerequisite with its dependent; a request without it is refused before anything is
        # written, and with it the selection builds.
        row = {p.id: p for p in patcher.load_public_fun_patches()}[ID]
        self.assertEqual(tuple(patcher._dependency_ids(row)), (LIMITED,))
        with self.assertRaises(patcher.PatcherError):
            patcher.resolve_fun_patch_ids([ID], game_id="vv4")
        self.assertEqual(set(patcher.resolve_fun_patch_ids([LIMITED, ID], game_id="vv4")), {LIMITED, ID})

    def test_the_description_states_the_dependency_in_bold(self) -> None:
        self.assertIn("**Needs \"Yellow Fruit Trees are No Longer Unlimited\": ticking this patch ticks it too",
                      self.row["description"])
        self.assertIn("111 fruit every 3 hours", self.row["description"])
        other = json.loads((ROOT / "data" / f"{LIMITED}_feature.json").read_text(encoding="utf-8"))["description"]
        self.assertIn("**With \"Yellow Breadfruit Refills Partially Every Time\" ticked too", other)

    def test_defaults(self) -> None:
        # Off by default and off in Owner's Defaults (the owner, 2026-11-11); Classic VV Difficulty does not need it.
        self.assertIn(ID, gui.DEFAULT_OFF_FUN_PATCH_IDS)
        self.assertIn(ID, gui.OWNERS_DEFAULT_OFF_FUN_PATCH_IDS)
        classic = json.loads((ROOT / "data" / "vv4_classic_vv_difficulty_feature.json").read_text(encoding="utf-8"))
        self.assertNotIn(ID, classic["dependencies"])


@unittest.skipUnless(HAVE_EMULATOR, "needs pefile, unicorn, the stock executable and research/game-data/vv4")
class TheRefill(unittest.TestCase):
    def test_the_flag_is_looked_for_by_full_path_in_the_patchers_folder(self) -> None:
        on, off = Partial(True), Partial(False)
        self.assertEqual(on.v.process.export("VvfpYellowFruitPartial"), 1)
        self.assertEqual(off.v.process.export("VvfpYellowFruitPartial"), 0)
        self.assertIn(FLAG_PATH, [p.lower() for p in on.asked])

    def test_111_every_30_units_on_time(self) -> None:
        t = Partial(files={side(): tree_file(0, roster=[identity("Ana")])})
        t.villager()
        t.units(29)
        self.assertEqual(t.left(), 0)
        t.units(1)
        self.assertEqual(t.left(), 111)
        t.units(30)
        self.assertEqual(t.left(), 222)
        t.units(29)
        self.assertEqual(t.left(), 222)
        t.units(1)
        self.assertEqual(t.left(), 333)

    def test_without_the_flag_it_is_the_refill_to_full(self) -> None:
        t = Partial(False, files={side(): tree_file(0, roster=[identity("Ana")])})
        t.villager()
        t.units(30)
        self.assertEqual(t.left(), 0)
        t.units(10)
        self.assertEqual(t.left(), 1000)

    def test_capped_at_1000(self) -> None:
        t = Partial(files={side(): tree_file(950, roster=[identity("Ana")])})
        t.villager()
        t.units(30)
        self.assertEqual(t.left(), 1000)
        t.units(30)
        self.assertEqual(t.left(), 1000)

    def test_time_away_counts_in_proportion(self) -> None:
        # 10 hours away on Normal (100 age units) in one catch-up: 3 refills of 111, 10 units carried over.
        t = Partial(files={side(): tree_file(0, roster=[identity("Ana")])})
        t.villager()
        t.catch_up(100)
        self.assertEqual(t.left(), 333)
        t.save()
        self.assertEqual(int.from_bytes(t.files.files[side()][20:24], "little"), 10)
        # A long absence (30 hours, 300 units: 10 refills, 1,110 fruit) fills it up to the cap and no further.
        long = Partial(files={side(): tree_file(0, roster=[identity("Ana")])})
        long.villager()
        long.catch_up(300)
        self.assertEqual(long.left(), 1000)

    def test_a_count_left_by_the_refill_to_full_is_paid_in_proportion(self) -> None:
        # A file written without this row, 35 units since the last refill: the next unit pays 36 units' share.
        t = Partial(files={side(): tree_file(100, units=35, roster=[identity("Ana")])})
        t.villager()
        t.units(1)
        self.assertEqual(t.left(), 100 + 36 * 37 // 10)
        t.save()
        self.assertEqual(int.from_bytes(t.files.files[side()][20:24], "little"), 0)

    def test_the_event_and_a_custom_island_event_are_unchanged(self) -> None:
        # A Custom Island Event's refill: to 1,000, the count running on.
        t = Partial(files={side(): tree_file(100, units=9, roster=[identity("Ana")])})
        t.villager()
        self.assertEqual(t.v.process.export("VvfpYellowFruitRefill"), 1)
        self.assertEqual(t.left(), 1000)
        t.save()
        self.assertEqual(int.from_bytes(t.files.files[side()][20:24], "little"), 9)
        # A Closer Look (Yellow Breadfruit): +350, up to 1,000.
        event = limited.YellowBreadfruitEvent()
        t = Partial(files={side(): tree_file(100, units=9, roster=[identity("Ana")])})
        t.villager()
        self.assertEqual(event.possible(t), 1)
        t.v.call(event.method(t, 12), event.obj(t))
        self.assertEqual(t.left(), 450)


class GameMechanicsPage(unittest.TestCase):
    """The Tree of Life's Game Mechanics page with both patches: 111 every 30 age units, not full every 40."""

    def setUp(self) -> None:
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write(self, data: bytes) -> None:
        path = self.folder / "Virtual Villagers Fun Patcher" / "Save 1" / "Data" / "Fruit Trees" / \
            "Virtual Villagers 4 Yellow Fruit Tree - Save 1.dat"
        path.parent.mkdir(parents=True)
        path.write_bytes(data)

    def test_the_lines(self) -> None:
        import test_game_mechanics_yellow_fruit as page
        import vv_game_mechanics_vv4 as vv4
        self.write(page.tree_file(412, units=20, roster=[page.identity("Ana")]))
        both = page.render(self.folder, frozenset({LIMITED, ID}), living={page.identity("Ana")})
        self.assertIn("the yellow fruit tree holds at most 1,000 fruit, gaining 111 fruit every 30 age units (with "
                      "\"Yellow Breadfruit Refills Partially Every Time\") (3 hours of real-life time on Normal speed;",
                      both)
        self.assertIn("The Cooking Pit fruit: 412 of 1,000; +111 every 30 age units", both)
        self.assertIn("412 of 1,000 fruit left (the trees show: 3 fruits on each tree); gains 111 fruit (up to 1,000) "
                      "after 10 more age units", both)
        self.assertIn("The yellow fruit tree gains 111 fruit every 30 age units", both)
        self.assertNotIn("refilled to full", both)
        only = page.render(self.folder, frozenset({LIMITED}), living={page.identity("Ana")})
        self.assertIn("refilled to full after 20 more age units", only)
        self.assertNotIn("gains 111 fruit", only)
        self.assertEqual(vv4.fruit_partial_gain(30), 111)

    def test_the_catch_up_bonus_cap_and_the_source(self) -> None:
        import test_game_mechanics_yellow_fruit as page
        big = [page.adult(f"V{i}", 100) for i in range(20)]
        both = page.render(self.folder, frozenset({LIMITED, ID}), people=big)
        # 111 fruit / 5 a bonus / 30 units = 0.74 bonuses a unit, 3.7 food at Food Mastery 1.
        self.assertIn("the tree gives 111 every 30 age units, so at most 3.7 food a unit on average", both)


if __name__ == "__main__":
    unittest.main()
