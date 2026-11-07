"""Game Mechanics: the time needed while catching up for each technology level (src/vv_game_mechanics_tech_time.py).

The owner (2026-11-06): "Time needed for next technology: (technology name) (level) from cheapest to most
expensive" and the time for each technology and level while catching up.  This file needs no exe: it pins the
sorting, the cumulative cost of later levels, the rate arithmetic of each game and that every game's page shows
the lines (the rules' addresses are in the module docstring).
"""
from __future__ import annotations

import gzip
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_game_mechanics as gm  # noqa: E402
import vv_game_mechanics_tech_time as tt  # noqa: E402
import vv_tribe_rename  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "rename_tribe"
NOW = 1_790_000_000 + 3_000_000
NEXT = "Time needed for next technology"
EACH = "Time needed for each technology and level"


def page(name: str) -> list[gm.Fact]:
    number, slot = int(name[2]), int(name[-1])
    base = next(item.base for item in vv_tribe_rename.GAMES if item.number == number)
    root = Path(tempfile.mkdtemp(prefix="gmtt"))
    try:
        (root / base).mkdir()
        (root / base / f"{base}{slot}.ldw").write_bytes(gzip.decompress((FIXTURES / f"{name}.ldw.gz").read_bytes()))
        return gm.read(root / base, number, slot, [], now=NOW)
    finally:
        shutil.rmtree(root, True)


CHOSEN_50 = 0.83096 * 0.9            # the chooser at skill 50


class Rate(unittest.TestCase):
    def test_each_game_at_research_50(self) -> None:
        start = {1: {"Science": 1}, 2: {"Science": 1}, 3: {"Science": 1, "Magic": 0},
                 4: {"Science": 1, "Learning": 1}, 5: {"Science": 1, "Learning": 1}}
        want = {1: 5 * CHOSEN_50 * 0.81 * 7, 2: 4 * CHOSEN_50 * 0.84 * 7, 3: 4 * CHOSEN_50 * 0.84 * 7,
                4: 4 * CHOSEN_50 * 0.84 * 7, 5: 4 * CHOSEN_50 * 0.84 * 7}
        for game in range(1, 6):
            with self.subTest(game=game):
                self.assertAlmostEqual(tt.per_unit(game, start[game]), want[game])

    def test_science_divisors_while_catching_up(self) -> None:
        for game, divisors in ((1, (7, 5, 3)), (2, (7, 6, 4)), (3, (7, 7, 5)), (4, (7, 7, 5)), (5, (7, 7, 5))):
            for level, d in zip((1, 2, 3), divisors):
                self.assertEqual(tt.per_success(game, {"Science": level}, 50, 0.0), 50 // d)

    def test_what_raises_the_gain(self) -> None:
        self.assertEqual(tt.per_success(3, {"Science": 1, "Magic": 1}, 50, 0.0), 8)       # Magic 1: +1
        self.assertAlmostEqual(tt.per_success(2, {"Science": 1}, 50, 0.0, fire=True), 7.1)
        self.assertEqual(tt.per_success(1, {"Science": 1}, 50, 0.0, fire=True), 7)         # no fire bonus
        # Learning 3 in The Tree of Life: 50 + 34 + 30 passes always.
        self.assertAlmostEqual(tt.per_unit(4, {"Science": 1, "Learning": 3}), 4 * CHOSEN_50 * 1.0 * 7)
        self.assertAlmostEqual(tt.per_unit(1, {"Science": 1}, never_fails=True), 5 * CHOSEN_50 * 7)
        self.assertAlmostEqual(tt.per_unit(4, {"Science": 1}, lab=5.5), 4 * CHOSEN_50 * 0.84 * 12.5)

    def test_lab_bonus_from_the_collectible_counts(self) -> None:
        import struct
        import vv_game_mechanics_life as life
        for game, owned, mean in ((4, range(12, 24), 5.5), (5, range(0, 24), 5.5), (5, range(0, 1), 0.0)):
            data = bytearray(life.COLLECTIBLES_AT[game] + 48 * 4)
            for k in owned:
                struct.pack_into("<i", data, life.COLLECTIBLES_AT[game] + 4 * k, 1)
            self.assertEqual(tt.lab_bonus(game, bytes(data)), mean)


class Goals(unittest.TestCase):
    def test_next_levels_cheapest_first(self) -> None:
        levels = {"Science": 1, "Medicine": 1, "Learning": 1, "Construction": 1, "Food Mastery": 1, "Dendrology": 3}
        found = tt.goals(4, levels, 4_500, lambda owned: 10.0, False)
        self.assertEqual([(g.name, g.level) for g in found], [("Food Mastery", 2), ("Learning", 2),
                                                             ("Construction", 2), ("Medicine", 2), ("Science", 2)])
        self.assertEqual([g.needed for g in found], [0, 0, 500, 500, 3_500])
        self.assertEqual(found[-1].units, 350.0)

    def test_a_later_level_needs_the_levels_below_and_its_rate_follows_science(self) -> None:
        rate = lambda owned: tt.per_unit(1, owned)  # noqa: E731
        levels = {"Science": 1}
        (two, three) = tt.goals(1, levels, 0, rate, True)
        self.assertEqual((two.needed, three.needed), (12_000, 162_000))
        self.assertEqual(tt.sum_cost(three, levels, 1), 162_000)
        first = 12_000 / rate({"Science": 1})
        self.assertAlmostEqual(three.units, first + 150_000 / rate({"Science": 2}))

    def test_factions_shut_each_other_out(self) -> None:
        self.assertNotIn("Magic", tt.buyable(3, {"Nature": 1, "Magic": 0, "Science": 1}))
        self.assertIn("Magic", tt.buyable(3, {"Nature": 1, "Magic": 0}, both_factions=True))
        self.assertEqual(tt.buyable(4, {"Science": 3, "Medicine": 2}), ["Medicine"])


class Closed(unittest.TestCase):
    def ctx(self, speed: int) -> SimpleNamespace:
        return SimpleNamespace(game=4, speed=speed, unit=60.0 * speed, speed_value=speed)

    def test_time_away_limits(self) -> None:
        ctx = self.ctx(gm.NORMAL)
        self.assertEqual(tt.closed_words(ctx, 10), "12 counted age units (1 hour 12 minutes of time away on Normal "
                         "speed), closed for at least 1 hour 12 minutes of real-life time in all (catch-ups needed: 1)")
        self.assertIn("at least 24 hours of real-life time in all (catch-ups needed: 1)", tt.closed_words(ctx, 100))
        # 24 counted hours are 240 age units on Normal, 238 of them with job turns.
        self.assertIn(f"{239 + 4:,} counted age units", tt.closed_words(ctx, 239))
        self.assertIn("(catch-ups needed: 2)", tt.closed_words(ctx, 239))


class Page(unittest.TestCase):
    def test_every_game_shows_the_sections(self) -> None:
        for name in ("vv1-huttest-1", "vv2-huttest-1", "vv3-huttest-1", "vv4-huttest-1", "vv5-huttest-1"):
            with self.subTest(name=name):
                texts = [f.text for f in page(name)]
                tech = next(i for i, t in enumerate(texts) if t.startswith("Tech points:"))
                self.assertTrue(texts[tech + 1].startswith(NEXT))
                self.assertTrue(any(t.startswith(EACH) for t in texts))
                self.assertTrue(any(t.startswith("Difficulty (Easy, Medium or Hard) changes none") for t in texts))
                self.assertIn("Who researches now is not kept in the save.", texts)

    def test_new_believers_waits_for_the_knowing_totem(self) -> None:
        texts = [f.text for f in page("vv5-huttest-1")]
        self.assertTrue(any("until The Knowing Totem is solved, and it is not solved yet" in t for t in texts))

    def test_a_level_still_to_earn_names_both_clocks(self) -> None:
        texts = [f.text for f in page("vv3-huttest-1")]
        line = next(t for t in texts if t.startswith("Science level 3: 161,000 tech points from level 1"))
        self.assertIn("counted age units", line)
        self.assertIn("of time away on Normal speed", line)
        self.assertIn("real-life time", line)


if __name__ == "__main__":
    unittest.main()
