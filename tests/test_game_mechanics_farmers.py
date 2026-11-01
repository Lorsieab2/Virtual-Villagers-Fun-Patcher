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
HEADER = "Farmers needed to supply the village with food"


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
                lines = [f.text for f in vitals if ": while catching up" in f.text]
                self.assertTrue(lines)
                for text in lines:
                    self.assertRegex(text, r"while catching up, (farmers needed: [\d,]+ \(one brings|no farmer can)")
                self.assertTrue(any(f.text.startswith("How it is worked out: farmers needed") for f in vitals))

    def test_the_numbers_follow_the_formula(self) -> None:
        # A New Home's fixture: the eating line's figure and each source's line agree with supplies().
        facts = self.pages["vv1-huttest-1"]
        header = next(f.text for f in facts if f.text.startswith(HEADER))
        eaten = float(re.search(r"eats ([\d,.]+) food each counted age unit", header).group(1).replace(",", ""))
        checked = 0
        for f in facts:
            found = re.search(r"farmers needed: ([\d,]+) \(one brings ([\d,.]+) food each counted age unit", f.text)
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


if __name__ == "__main__":
    unittest.main()
