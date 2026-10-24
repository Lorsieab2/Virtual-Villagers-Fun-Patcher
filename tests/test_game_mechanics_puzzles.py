"""The Game Mechanics window's village start and puzzle lines (src/vv_game_mechanics.py later_puzzle_lines,
hours_puzzle_lines, GameClock.moment), and the owner's 2026-10-23 wording changes in all five games: the crab,
brown and red mushrooms, the Golden Child and The Lost Children's birds.  The committed real saves
(tests/fixtures/rename_tribe) are copied and changed byte by byte at the offsets each module documents."""
from __future__ import annotations

import gzip
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_game_mechanics as gm  # noqa: E402
import vv_game_mechanics_vv1 as vv1  # noqa: E402
import vv_game_mechanics_vv2 as vv2  # noqa: E402
import vv_game_mechanics_vv3 as vv3  # noqa: E402
import vv_game_mechanics_vv4 as vv4  # noqa: E402
import vv_game_mechanics_vv5 as vv5  # noqa: E402
import vv_tribe_rename  # noqa: E402
from test_game_mechanics import EPOCH, FIXTURES, Folder, make_save  # noqa: E402

NOW = EPOCH + 3_000_000


def fixture(name: str) -> bytearray:
    return bytearray(gzip.decompress((FIXTURES / f"{name}.ldw.gz").read_bytes()))


class Pages(unittest.TestCase):
    def page(self, game: int, data: bytes, features=None, now=NOW) -> list[gm.Fact]:
        base = next(item.base for item in vv_tribe_rename.GAMES if item.number == game)
        folder = Folder(self, base)
        (folder.path / f"{base}1.ldw").write_bytes(bytes(data))
        games = [folder.game(features)] if features is not None else []
        return gm.read(folder.path, game, 1, games, now=now)

    def puzzles(self, facts) -> list[str]:
        return [f.text for f in facts if f.group == gm.PUZZLES]


class LaterGames(Pages):
    """The Secret City, The Tree of Life and New Believers: {progress, solve time} on the game clock."""

    def test_vv3_solved_before_and_after_the_clocks_base(self) -> None:
        clock = (6, 0, 100_000, 50_000)
        data = bytearray(make_save(clock=clock, created=40_000))
        buf = 12 + vv3.PUZZLES + 4
        struct.pack_into("<ii", data, buf + 8 * 0, 1, 69)              # The First Chief, before the base
        struct.pack_into("<ii", data, buf + 8 * 9, 1, 50_600)          # The Orchard, after it
        struct.pack_into("<ii", data, buf + 8 * 3, 699, 0)             # The Roster of the Dead: one short
        facts = self.page(3, data, now=EPOCH + 100_000)
        lines = self.puzzles(facts)
        started = gm.when(EPOCH + 40_000)
        self.assertEqual(lines[0], "Puzzles solved: 3 of 16.")       # with The Bee Hive the fixture solves
        self.assertIn(f"The First Chief: solved when the village was 1 minute 9 seconds old, counted on Normal speed "
                      f"(started {started}; the save keeps no real date before {gm.when(EPOCH + 100_000)}).", lines)
        self.assertIn(f"The Orchard: solved at {gm.when(EPOCH + 100_000 + 600)}.", lines)
        self.assertIn("The Roster of the Dead: not yet solved.", lines)
        self.assertIn("The Bee Hive: solved (the game kept no time for it).", lines)
        self.assertEqual(len(lines), 17)
        self.assertIn(f"The village was started at {started}.", [f.text for f in facts if f.group == "Other"])
        self.assertTrue(all(f.confirmed for f in facts if f.group == gm.PUZZLES))

    def test_no_village_start_in_the_save(self) -> None:
        facts = self.page(3, make_save(created=0))
        self.assertIn("When the village was started is not in this save.", [f.text for f in facts])
        self.assertNotIn("(started ", gm.render(facts))

    def later(self, game: int, module, entries: int, name: str, pid: int) -> None:
        data = fixture(f"vv{game}-huttest-1")
        rate, before, wall, base = struct.unpack_from("<4i", data, module.CLOCK)
        origin = struct.unpack_from("<q", data, 8)[0]
        struct.pack_into("<i", data, module.CLOCK + 12, 10_000)        # the base after the solve time below
        struct.pack_into("<ii", data, entries + 8 * pid, 5_000, 90)
        facts = self.page(game, data)
        lines = self.puzzles(facts)
        self.assertTrue(lines[0].startswith("Puzzles solved: "), lines[0])
        line = next(x for x in lines if x.startswith(name + ": "))
        self.assertIn("solved when the village was 1 minute 30 seconds old, counted on Normal speed", line)
        self.assertIn(f"the save keeps no real date before {gm.when(origin + wall)}", line)
        created = struct.unpack_from("<i", data, module.STATS)[0]
        self.assertIn(f"The village was started at {gm.when(origin + created)}.", [f.text for f in facts])
        # After the base: a real date.
        struct.pack_into("<ii", data, entries + 8 * pid, 5_000, 10_060)
        line = next(x for x in self.puzzles(self.page(game, data)) if x.startswith(name + ": "))
        self.assertIn(f"solved at {gm.when(origin + wall + 60 * gm.speed_base(vv_speed(game, data)) / 6)}", line)

    def test_vv4(self) -> None:
        self.later(4, vv4, vv4.PUZZLE_ENTRIES, "The Stream", 1)

    def test_vv5(self) -> None:
        self.later(5, vv5, vv5.PROJECTS, "The Prison Break", 2)

    def test_vv5_heathen_parent_only_with_its_patch(self) -> None:
        data = fixture("vv5-huttest-1")
        on = self.puzzles(self.page(5, data, features=[vv5.HEATHEN_PARENT]))
        off = self.puzzles(self.page(5, data, features=[]))
        self.assertTrue(on[0].endswith(" of 17."), on[0])
        self.assertTrue(off[0].endswith(" of 16."), off[0])
        self.assertTrue(any(x.startswith("The Heathen Parent: ") for x in on))
        self.assertFalse(any(x.startswith("The Heathen Parent: ") for x in off))

    def test_thresholds_are_the_games_own(self) -> None:
        exe = ROOT / "inputs" / "vv3-stock-copy" / "Virtual Villagers - The Secret City.exe"
        if not exe.is_file():
            self.skipTest("the stock Secret City executable is not here")
        import pefile
        pe = pefile.PE(str(exe), fast_load=True)
        raw = pe.get_data(0x49D230 - pe.OPTIONAL_HEADER.ImageBase, 64)
        self.assertEqual(list(struct.unpack("<16i", raw)), [vv3.PUZZLE_THRESHOLDS[n] for n in range(16)])


def vv_speed(game: int, data: bytes) -> int:
    import vv_save_backup
    return vv_save_backup.save_speed(game, bytes(data))[1]


class HoursGames(Pages):
    """A New Home and The Lost Children: a solved byte and the whole hours since the village was started."""

    def hours(self, game: int, module, s: int) -> None:
        data = fixture(f"vv{game}-huttest-1")
        first, second = module.PUZZLES[0], module.PUZZLES[1]
        data[first[1] + s] = 1
        struct.pack_into("<i", data, first[2] + s, 7)
        data[second[1] + s] = 0
        facts = self.page(game, data)
        lines = self.puzzles(facts)
        start = next(f.text for f in facts if f.text.startswith("The village was started at "))
        line = next(x for x in lines if x.startswith(first[0] + ": "))
        self.assertIn("solved 7 hours after the village was started: between ", line)
        self.assertIn(f"{second[0]}: not yet solved.", lines)
        self.assertTrue(lines[0].startswith("Puzzles solved: "))
        self.assertTrue(start.endswith("."))
        struct.pack_into("<i", data, first[2] + s, 1)
        line = next(x for x in self.puzzles(self.page(game, data)) if x.startswith(first[0] + ": "))
        self.assertIn("solved within 2 hours of the village's start, by ", line)

    def test_vv1(self) -> None:
        self.hours(1, vv1, 4)

    def test_an_impossible_time_keeps_the_page(self) -> None:
        """A solved flag with a garbage hours value (about 2^31) once made the date raise and the whole page become
        error text: the puzzle is shown solved with the value named, and the rest of the page stays."""
        for game, module, s in ((1, vv1, 4), (2, vv2, vv2.S)):
            with self.subTest(game=game):
                data = fixture(f"vv{game}-huttest-1")
                name, flag, at = module.PUZZLES[0]
                data[flag + s] = 1
                struct.pack_into("<i", data, at + s, 0x7FFFFFF0)
                facts = self.page(game, data)
                line = next(x for x in self.puzzles(facts) if x.startswith(name + ": "))
                self.assertEqual(line, f"{name}: solved (the hours the save holds for it, {0x7FFFFFF0:,}, are not a "
                                       "possible time).")
                self.assertTrue(any(f.group == "Food sources" for f in facts))
        data = bytearray(make_save())
        struct.pack_into("<ii", data, 12 + vv3.PUZZLES + 4, 1, 0x7FFFFFF0)
        facts = self.page(3, data, now=EPOCH + 100_000)
        self.assertIn(f"The First Chief: solved (the time the save holds for it, {0x7FFFFFF0:,}, is not one the game's "
                      "clock reached).", self.puzzles(facts))
        self.assertTrue(any(f.group == "Food sources" for f in facts))

    def test_vv2(self) -> None:
        self.hours(2, vv2, vv2.S)


class Wording(Pages):
    def text(self, game: int, features=None) -> str:
        return gm.render(self.page(game, fixture(f"vv{game}-huttest-1"), features=features))

    def test_the_big_catch_is_a_crab(self) -> None:
        self.assertIn("a 10% chance of catching a crab, worth 55 food", self.text(3))
        self.assertIn("a 21% chance of catching a crab, worth 55 food", self.text(1))
        for game in (1, 3):
            self.assertNotIn("big catch", self.text(game))

    def test_brown_and_red_mushrooms(self) -> None:
        self.assertIn("a brown mushroom worth 8 food, or 1 in 20 a red (rare) mushroom worth 45", self.text(1))
        self.assertIn("a brown mushroom worth 6 food, or 1 in 10 a red (rare) mushroom worth 35", self.text(2))
        self.assertIn("92% are brown mushrooms worth 6 food, 8% red (rare) mushrooms worth 35", self.text(3))
        self.assertIn("brown 92% worth 6 food, red (rare) 8% worth 35", self.text(4))
        self.assertIn("brown 92% worth 6 food, red (rare) 8% worth 35", self.text(5))

    def test_the_golden_child_never_starves(self) -> None:
        text = self.text(1)
        self.assertIn("he never eats, never starves, never falls sick, never dies of old age", text)
        self.assertNotIn("going without food", text)
        self.assertIn("The Golden Child neither eats nor starves", text)
        line = next(f for f in vv1.HIDDEN_LINES if f[0].startswith("Work injuries"))
        self.assertFalse(line[1])                       # not settled by the code: UNCONFIRMED

    def test_the_lost_childrens_birds(self) -> None:
        data = fixture("vv2-huttest-1")
        s = vv2.S
        for scarer, allowance, dam, expect in ((1, 0, 1, "The birds: kept away by The Scarecrow."),
                                               (0, 250, 1, "The birds: 250 more food of crop harvest before they find"),
                                               (0, 0, 1, "The birds: they have found the field"),
                                               (0, 0, 0, "The birds: they come only once the dam is built")):
            with self.subTest(scarer=scarer, allowance=allowance, dam=dam):
                data[vv2.SCARER + s] = scarer
                data[vv2.DAM + s] = dam
                struct.pack_into("<i", data, vv2.ALLOWANCE + s, allowance)
                facts = self.page(2, data)
                parent = next(i for i, f in enumerate(facts) if f.text.startswith("The birds: "))
                self.assertTrue(facts[parent].text.startswith(expect), facts[parent].text)
                self.assertFalse(facts[parent].confirmed)         # a static reading: UNCONFIRMED
                subs = [f.text for f in facts[parent + 1:parent + 5]]
                self.assertTrue(all(f.sub for f in facts[parent + 1:parent + 5]))
                self.assertTrue(subs[0].startswith("A new village allows 1,000 food of crop harvest"))
                self.assertIn("Only The Scarecrow stops it", subs[2])
                self.assertIn("Birds found your field", subs[3])

    def test_the_scarecrow_flag_is_a_byte(self) -> None:
        data = fixture("vv2-huttest-1")
        data[vv2.SCARER + vv2.S] = 0
        data[vv2.SCARER + vv2.S + 1] = 7                 # the byte after it is not the flag
        text = gm.render(self.page(2, data))
        self.assertNotIn("kept away by The Scarecrow", text)


class Bullets(unittest.TestCase):
    def test_render(self) -> None:
        text = gm.render([gm.Fact("Food sources", "Tree 1: Mango", gm.SAVE),
                          gm.Fact("Food sources", "Planted at x.", False, sub=True),
                          gm.Fact("Other", "Fine.", gm.SAVE)])
        self.assertEqual(text, f"Food sources\n{gm.BULLET}Tree 1: Mango\n{gm.SUB_BULLET}{gm.UNCONFIRMED}  Planted at x."
                               f"\n\nOther\n{gm.BULLET}Fine.")


if __name__ == "__main__":
    unittest.main()
