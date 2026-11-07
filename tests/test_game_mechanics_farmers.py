"""Game Mechanics: the Farmers needed lines (src/vv_game_mechanics_farmers.py, src/vv_game_mechanics_life.py).

The owner (2026-11-01): "The number of gatherers needed to supply the village with food should be worked out based
on catch-up mechanics. The trip time should be definitively measured", and the job is called Farming: the page
says farmers, never gatherers.  The trip times and catch-up rules themselves are re-measured from the stock exes
by tests/test_game_mechanics_farmers_vv1.py .. _vv5.py; this file needs no exe: it pins the arithmetic, that every
game's page shows the lines from the measured numbers, and the wording.
"""
from __future__ import annotations

import gzip
import math
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_game_mechanics as gm  # noqa: E402
import vv_game_mechanics_farmers as farmers  # noqa: E402
import vv_tribe_rename  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "rename_tribe"
NOW = 1_790_000_000 + 3_000_000
HEADER = "Farmers needed, each with Farming"


def page(name: str) -> list[gm.Fact]:
    number, slot = int(name[2]), int(name[-1])
    base = next(item.base for item in vv_tribe_rename.GAMES if item.number == number)
    root = Path(tempfile.mkdtemp(prefix="gmfa"))
    try:
        (root / base).mkdir()
        (root / base / f"{base}{slot}.ldw").write_bytes(gzip.decompress((FIXTURES / f"{name}.ldw.gz").read_bytes()))
        return gm.read(root / base, number, slot, [], now=NOW)
    finally:
        shutil.rmtree(root, True)


class Arithmetic(unittest.TestCase):
    def test_catch_up_and_live_supply(self) -> None:
        # The Secret City at Normal speed, 10 villagers eating 2 each age unit, Farming 50, 1,000 food.
        turns, supply = farmers.supplies(3, {"fruit picks": 3, "honey picks": 3, "fishing trips": 8}, gm.NORMAL,
                                         360.0, 1.0, 1000, 20.0)
        self.assertEqual(turns, 4)
        by = {s.trip.key: s for s in supply}
        import vv_game_mechanics_farmers_vv3 as vv3
        per_turn = vv3.catch_up_trips(50, 1000)
        fruit = by["fruit picks"]
        self.assertAlmostEqual(fruit.catch_up_unit, 4 * per_turn * 0.84 * 4)
        self.assertEqual(fruit.catch_up_needed, math.ceil(20.0 / fruit.catch_up_unit))
        self.assertAlmostEqual(fruit.live_hour, 3600 / vv3.LIVE_CYCLE["fruit picks"][50] * 3)
        self.assertEqual(fruit.live_needed, math.ceil(200.0 / fruit.live_hour))
        honey = by["honey picks"]
        self.assertAlmostEqual(honey.catch_up_unit, 4 * per_turn * 0.84 * 11 / 12 * 4)
        self.assertEqual(by["fishing trips"].catch_up_food, 8)
        self.assertEqual(by["fishing trips"].live_food, 8)

    def test_a_closed_source_is_left_out_and_fruit_never_catches_up(self) -> None:
        _, supply = farmers.supplies(4, {"blackberry picks": 0, "fish in the net": 4, "fruit stomps": 3}, gm.NORMAL,
                                     360.0, 1.0, 1000, 20.0)
        self.assertEqual([s.trip.key for s in supply], ["fish in the net", "fruit stomps"])
        fruit = supply[1]
        self.assertEqual((fruit.catch_up_unit, fruit.catch_up_needed), (0.0, None))
        self.assertIsNotNone(fruit.live_needed)

    def test_food_mastery_rounds_as_the_game(self) -> None:
        # The Tree of Life 0x41D920 / New Believers 0x41EB40: level 2 adds half rounded down, level 3 doubles.
        self.assertEqual([farmers.boosted(a, 1.5) for a in (3, 4, 35, 55)], [4, 6, 52, 82])
        self.assertEqual([farmers.boosted(a, 2.0) for a in (3, 35)], [6, 70])
        self.assertEqual(farmers.boosted(7, 1.0), 7)

    def test_all_sources_together_take_the_best_per_farmer_first(self) -> None:
        import vv_game_mechanics_life as life
        # A bush that regrows 5 (10 a farmer), the sea without limit (8 a farmer), eating 21: 0.5 on the bush, 2 at sea.
        used, short = life._shared([("Sea", 8.0, float("inf")), ("Bush", 10.0, 5.0)], 21.0)
        self.assertEqual([name for name, _ in used], ["Bush", "Sea"])
        self.assertAlmostEqual(used[0][1], 0.5)
        self.assertAlmostEqual(used[1][1], 2.0)
        self.assertEqual(short, 0.0)
        _, short = life._shared([("Bush", 10.0, 5.0)], 21.0)
        self.assertAlmostEqual(short, 16.0)

    def test_food_mastery_counts_the_food_a_unit_is_worth(self) -> None:
        # Codex on #712: a New Believers harvest takes 7 crops and credits 10 food at Food Mastery 2 (not 10.5), so
        # 20 crops regrown an age unit are 20 x 10 / 7 food, not 20 x 1.5.
        import vv_game_mechanics_life as life
        ctx = life.Context(village=None, speed_value=6, last=0.0, food=1000, low_food=500, extra_from=8000,
                           sources=[life.Source("Hydroponic Farm crops", 800, 800, 20.0)], mastery=1.5,
                           trips=[("crop harvests", 7, "Hydroponic Farm crops")])
        group, endless, units, units_on = life._farmed(ctx, "Hydroponic Farm crops")
        self.assertEqual((len(group), endless, units, units_on), (1, False, 20.0, 800))
        _, (crops,) = farmers.supplies(5, {"crop harvests": 7}, gm.NORMAL, 360.0, 1.5, 1000, 20.0)
        self.assertEqual(crops.catch_up_food, 10)
        self.assertAlmostEqual(units * crops.catch_up_food / 7, 20 * 10 / 7)

    def test_the_tree_of_lifes_net_counts_the_golden_fish(self) -> None:
        # Owner, 2026-11-07: the food figures account for the Golden Fish.  With s scale kinds found the net brings
        # 8 instead of 4 on (2s + 1)% of catches (0x433360), so a catch is worth 4 + 4 x (2s + 1) / 100 on average.
        src = (ROOT / "src" / "vv_game_mechanics_vv4.py").read_text(encoding="utf-8")
        self.assertIn("golden_share = 0.0 if scales == 0", src)
        self.assertIn("farmers_mod.boosted(8, multiplier_now)", src)
        _, (fish,) = farmers.supplies(4, {"fish in the net": 4 + 4 * 0.25}, gm.NORMAL, 360.0, 1.0, 1000, 20.0)
        self.assertAlmostEqual(fish.catch_up_food, 5.0)
        # Codex on #719: at Food Mastery 2 with all 12 scales a catch is 0.75 x 6 + 0.25 x 12 = 7.5, not 7.
        avg = (0.75 * farmers.boosted(4, 1.5) + 0.25 * farmers.boosted(8, 1.5)) / 1.5
        _, (fish,) = farmers.supplies(4, {"fish in the net": avg}, gm.NORMAL, 360.0, 1.5, 1000, 20.0)
        self.assertAlmostEqual(fish.catch_up_food, 7.5)
        self.assertEqual(farmers.boosted(5, 1.5), 7)          # one gain of 5 is still rounded down

    def test_food_mastery_and_speed(self) -> None:
        # The Lost Children's coconuts: live 8, 4 or 2 by speed; 4 while catching up; Food Mastery on both.
        for speed, food in ((gm.FAST, 8), (gm.NORMAL, 4), (gm.SLOW, 2)):
            _, (coconuts,) = farmers.supplies(2, {"coconut trips": 4}, speed, 60.0 * speed, 1.5, 1000, 10.0)
            self.assertEqual((coconuts.live_food, coconuts.catch_up_food), (food * 1.5, 6.0))

    def test_every_measured_trip_has_a_live_cycle_and_times_at_every_speed(self) -> None:
        for game in range(1, 6):
            turns, trips = farmers.game_trips(game)
            self.assertIn(turns, (4, 5))
            self.assertTrue(trips, game)
            for trip in trips:
                with self.subTest(game=game, trip=trip.key):
                    self.assertEqual(set(trip.live_seconds), {3, 6, 10})
                    for farming in (100, 50, 20):
                        self.assertGreater(farmers.live_cycle(game, trip, farming), trip.live_seconds[6] * 0.9)


class ThePage(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pages = {name: page(name) for name in ("vv1-huttest-1", "vv2-huttest-1", "vv3-huttest-1",
                                                     "vv4-huttest-1", "vv5-huttest-1")}
        cls.general = {game: gm.general(game, now=NOW) for game in range(1, 6)}

    def test_every_game_shows_the_farmers_needed(self) -> None:
        for name, facts in self.pages.items():
            with self.subTest(name):
                vitals = [f for f in facts if f.group == "Vital statistics"]
                header = [f for f in vitals if f.text.startswith(HEADER)]
                self.assertEqual(len(header), 1)
                self.assertEqual(header[0].verified, gm.RUNNING)
                lines = [f.text for f in vitals if " alone: while catching up" in f.text]
                self.assertTrue(lines)
                for text in lines:
                    self.assertRegex(text, r" alone: while catching up, [\d,]+ farmers? \(one brings")
                    # Each source says whether it can feed the village on its own, by its regrowth.
                    self.assertRegex(text, r"It (never runs out|regrows .* it can feed the village alone|cannot feed "
                                           r"the village alone)")
                self.assertEqual(sum(f.text.startswith("All food sources together: while catching up")
                                     for f in vitals), 1)
                self.assertEqual(sum(f.text.startswith("Difficulty: it changes what each villager eats")
                                     for f in vitals), 1)
                self.assertTrue(any(f.text.startswith("How it is worked out: farmers needed") for f in vitals))
                self.assertIn("Mushrooms are left out", header[0].text)

    def test_the_numbers_follow_the_formula(self) -> None:
        # A New Home's fixture: the eating line's figure and each source's line agree with supplies().
        facts = self.pages["vv1-huttest-1"]
        header = next(f.text for f in facts if f.text.startswith(HEADER))
        eaten = float(re.search(r"eats ([\d,.]+) food each counted age unit", header).group(1).replace(",", ""))
        checked = 0
        for f in facts:
            found = re.search(r"alone: while catching up, ([\d,]+) farmers? \(one brings ([\d,.]+) food each "
                              r"counted age unit", f.text)
            if found:
                need, brought = int(found.group(1).replace(",", "")), float(found.group(2).replace(",", ""))
                # Both figures are shown rounded to 0.1: the count lies between the two roundings' answers.
                low = math.ceil((eaten - 0.05) / (brought + 0.05) - 1e-9)
                high = math.ceil((eaten + 0.05) / (brought - 0.05) - 1e-9)
                self.assertTrue(low <= need <= high, f.text)
                checked += 1
        self.assertGreater(checked, 0)

    def test_the_trip_rules_are_in_food_earned_on_every_page(self) -> None:
        for game, facts in self.general.items():
            _, trips = farmers.game_trips(game)
            texts = [f.text for f in facts if f.group == farmers.GROUP]
            for trip in trips:
                with self.subTest(game=game, trip=trip.key):
                    line = next(t for t in texts if t.startswith(trip.key[0].upper() + trip.key[1:] + ": one whole trip"))
                    self.assertIn("real time, the same at every speed", line)
                    self.assertIn("A farmer left to the game's own choices brings food once every", line)

    def test_the_page_says_farmers_never_gatherers(self) -> None:
        for facts in list(self.pages.values()) + list(self.general.values()):
            for f in facts:
                self.assertNotRegex(f.text, r"(?i)\bgatherers?\b", f.text)

    def test_no_code_label_is_shown(self) -> None:
        # Module constants and helpers are never page words (the owner: code labels are not UI).
        for facts in self.general.values():
            for f in facts:
                if f.group == farmers.GROUP:
                    self.assertNotRegex(f.text, r"\b[A-Z]{2,}_[A-Z_]+\b|\b[a-z]+_[a-z_]+\(", f.text)


class WalkAndRedecisionClaims(unittest.TestCase):
    """Lines the farming emulation contradicted are corrected and stay so: adults walk at 100 (1 pixel a 33 ms
    frame), likers of running at 300, the elderly and dislikers at 40 -- measured by tests/farmers_emulation_vvN.py
    in every game -- and the game's 40-second re-decision sweep runs only after 40 seconds with no 2-second step
    (A New Home 0x42347A, The Secret City 0x46865F, The Tree of Life 0x43F962), never every 40 seconds."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.general = {game: gm.general(game, now=NOW) for game in range(1, 6)}

    def test_the_measured_walk_speeds_are_in_every_games_module(self) -> None:
        self.assertEqual(round(1000 / (1000 // 30), 1), 30.3)       # 1 pixel a 33 ms frame
        for game in range(1, 6):
            words = " ".join(farmers.game_module(game).__doc__.split())
            with self.subTest(game=game):
                self.assertRegex(words, r"(?:adult|believer) walks at 100 \(1 pixel a frame,? 30\.3 pixels a real-life second")

    def test_no_page_gives_another_normal_walk_speed(self) -> None:
        for game, facts in self.general.items():
            for f in facts:
                for found in re.finditer(r"speed 300 (?:\((\d+) otherwise|instead of (\d+))", f.text):
                    with self.subTest(game=game, line=f.text[:80]):
                        self.assertEqual(found.group(1) or found.group(2), "100")
                self.assertNotRegex(f.text, r"\b150 otherwise\b|instead of 150\)")
        vv4 = " ".join(f.text for f in self.general[4])
        self.assertIn("walks at speed 300 (100 otherwise) and one who dislikes it at 40", vv4)
        self.assertIn("30.3 pixels a real-life second at 100, 3 times that at 300 and 0.4 times at 40", vv4)
        self.assertIn("a walk at speed 300 (100 otherwise, 0x4659BF); disliked, 40 (0x465A06)",
                      " ".join(f.text for f in self.general[5]))

    def test_the_sweep_is_never_every_40_seconds(self) -> None:
        for game, facts in self.general.items():
            for f in facts:
                with self.subTest(game=game, line=f.text[:80]):
                    self.assertNotRegex(f.text, r"(?i)every 40 (?:real-life )?seconds?[^.]*(?:decide|refresh|sweep)"
                                                r"|(?:sweep|decides again)[^.]*every 40 (?:real-life )?seconds")
        expected = {1: "the idle sweep that has every idle villager decide again runs only when 40 real-life seconds",
                    3: "runs only when 40 real-life seconds pass without the village's 2-second step",
                    4: "refreshed only when 40 seconds of the game's clock"}
        for game, words in expected.items():
            with self.subTest(game=game):
                text = " ".join(f.text for f in self.general[game])
                self.assertIn(words, text)
                self.assertRegex(text, r"not (?:every 40 seconds )?in normal play")


if __name__ == "__main__":
    unittest.main()
