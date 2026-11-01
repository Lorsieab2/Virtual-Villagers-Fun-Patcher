"""The Secret City (VV3): the farmers' trips and catch-up job turns, re-measured from the stock exe.

Pins src/vv_game_mechanics_farmers_vv3.py.  Everything that needs the stock executable runs its own code in unicorn
through tests/farmers_emulation_vv3.py (what is stubbed there: rand, the clock, the game object block, the text
table, the settings / fopen, atexit and operator new) over the game's own map files, copied into
research/game-data/vv3 (cmap.dat, wpts.dat; never committed); it skips when either is missing (CI).

The full re-measurement of TRIP_SAMPLES (1,600 trips) and of one LIVE_CYCLE run (40 real-life hours of frames) runs
only with VVFP_RELEASE=1.
"""
from __future__ import annotations

import os
import statistics
import sys
import unittest
from fractions import Fraction
from itertools import product
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import farmers_emulation_vv3 as fe  # noqa: E402
import vv_game_mechanics_farmers as farmers  # noqa: E402
import vv_game_mechanics_farmers_vv3 as vv3  # noqa: E402

HAVE_GAME = fe.STOCK.is_file() and fe.CMAP.is_file() and fe.WPTS.is_file()
NO_GAME = "the stock Secret City executable or its map files are not present (research/)"
RELEASE = os.environ.get("VVFP_RELEASE") == "1"
SECONDS = fe.FRAME_MS / 1000.0
JOBS = {"fruit picks": fe.FRUIT_JOB, "honey picks": fe.HONEY_JOB, "fishing trips": fe.FISH_JOB}
SOURCE = {"fruit picks": "fruit", "honey picks": "honey", "fishing trips": "fish"}
SITES = {"fruit picks": 0x17, "honey picks": 0x15, "fishing trips": 0x1C}
PAY = {"fruit picks": 0x434AF1, "honey picks": 0x431C2F, "fishing trips": 0x458EEA}
CRAB_PAY = 0x458FE6

# rand(N) call sites, by the address the call returns to.
CHOOSER_BLANK, CHOOSER_PREF, CHOOSER_LAST = 0x45973F, 0x459858, 0x459879
CHOOSER_SKILLS = (0x459793, 0x4597AA, 0x4597CB, 0x4597EB, 0x459829)   # Farming, Parenting, Building, Healing, Research
FARMING_CHECK = 0x45A347            # the skill test 0x45A2C0, Farming: passes on rand(100) <= Farming + 33
SITE_STOP, SITE_GO = 0x45AAB1, 0x45AAC0   # the continuation 0x45AA90: rand(100) < 20 stops; rand(100) >= 40 goes on
HONEY_LAST_Y = 0x446F38             # the honey's last point: y 0x4F5 + rand(12)
CRAB = 0x4535A7                     # Farming 88 or more: the crab on rand(100) < 10
LOW_FOOD_MEAL = 0x460058            # at 500 food or less: the meal on rand(100) < 50
SICKNESS_GATE = 0x460287            # the aging loop's sickness roll: rand(100) < 50 skips it
EXTRA_MEAL = 0x4600BC               # 2 more food on rand(100) <= 75 (Medium at 8,000 or more, or Hard)

FARMER = {name: 10 for name in fe.SKILLS}


def _farmer(**skills):
    return {**FARMER, **skills}


def _bin_trips(key: str, n: int, seed: int, farming: int = 87):
    """n back-to-back trips from where the previous one ended, the sources kept full and the skill fixed; fruit
    visits the 3 trees in turn."""
    v = fe.Village(seed=seed)
    v.villager(skills=_farmer(farming=farming))
    v.run_trip(JOBS[key], 0)
    out = []
    for k in range(n):
        _refill(v)
        v.w32(v.rec(0) + fe.SKILLS["farming"], farming)
        seen = len(v.credits)
        paid, done = v.run_trip(JOBS[key], k % 3 if key == "fruit picks" else 0)
        out.append((k % 3, paid, done, [amount for _, amount, _ in v.credits[seen:]]))
    return out


def _refill(v, honey: int = 3000, fruit: int = 1000) -> None:
    v.w32(fe.FOOD, 1000)
    v.w32(fe.HONEY, honey)
    for tree in range(3):
        v.w32(fe.TREES + 0x30 + tree * 0x18, fruit)


class ModuleTests(unittest.TestCase):
    """The module's own consistency; no executable needed."""

    def test_the_trips_pair_with_the_page(self):
        turns, trips = farmers.game_trips(3)
        self.assertEqual(turns, 4)
        self.assertEqual([t.key for t in trips], ["fruit picks", "honey picks", "fishing trips"])
        for trip in trips:
            self.assertEqual(trip.success_offset, 34)
            self.assertEqual(trip.catch_up_trips_per_turn, vv3.CATCH_UP_TRIPS)
            self.assertEqual(set(trip.live_seconds), {3, 6, 10})
            self.assertEqual(len(set(trip.live_seconds.values())), 1, "the speed does not change a trip")
            n, mean, low, high = vv3.TRIP_SAMPLES[trip.key]
            self.assertEqual((trip.live_seconds[6], trip.live_span[6]), (mean, (low, high)))
        page = (ROOT / "src" / "vv_game_mechanics_vv3.py").read_text(encoding="utf-8")
        for trip in trips:
            self.assertIn(f'("{trip.key}", ', page, "the page's Context.trips names it")
        self.assertEqual(trips[0].live_food, {3: 7, 6: 3, 10: 2})
        self.assertEqual(trips[1].live_food, {3: 7, 6: 3, 10: 2})
        self.assertEqual(trips[2].live_food, {3: 11, 6: 8, 10: 5})
        self.assertEqual([t.catch_up_food for t in trips], [4, 4, 8])
        self.assertEqual(vv3.CATCH_UP_DELIVERED, {"honey picks": 11 / 12})

    def test_the_chooser_and_catch_up_shares(self):
        self.assertAlmostEqual(vv3.FARMING_CHOSEN, 0.85 * (0.84 + 0.16 * 0.86), places=12)
        self.assertAlmostEqual(vv3.farming_chosen(100), 0.83096)
        self.assertAlmostEqual(vv3.farming_chosen(20), 0.83096 * 0.6)
        self.assertEqual(vv3.farming_chosen(5), 0.0)
        self.assertAlmostEqual(vv3.CATCH_UP_TRIPS, 0.8 + 0.2 * 0.83096)
        self.assertAlmostEqual(vv3.catch_up_trips(100, food=9000), 0.48 + 0.52 * 0.83096)
        self.assertAlmostEqual(vv3.HONEY_DELIVERED, 11 / 12)

    def test_the_live_cycle_is_the_pooled_runs(self):
        seconds = int(vv3.LIVE_CYCLE_HOURS * 3600 * 1000 / fe.FRAME_MS) * SECONDS
        for (key, farming), runs in vv3.LIVE_CYCLE_RUNS.items():
            self.assertEqual(vv3.LIVE_CYCLE[key][farming], round(len(runs) * seconds / sum(runs), 1), (key, farming))
            low, high = sorted(seconds / n for n in runs)
            self.assertLess(high / low, 1.022, "the two seeds agree")


@unittest.skipUnless(HAVE_GAME, NO_GAME)
class LiveTripTests(unittest.TestCase):
    def test_a_trip_is_the_same_at_every_speed_and_pays_the_speed_rate(self):
        # The update, the walk and the waits never read the speed value (only the pause): frame for frame equal.
        got = {}
        for speed in (3, 6, 10):
            v = fe.Village(seed=4, speed=speed)
            v.villager(skills=_farmer(farming=87))
            trips = []
            for key in JOBS:
                seen = len(v.credits)
                trips.append((v.run_trip(JOBS[key], 1), [amount for _, amount, _ in v.credits[seen:]]))
            got[speed] = trips
        frames = {speed: [t[0] for t in trips] for speed, trips in got.items()}
        self.assertEqual(frames[3], frames[6])
        self.assertEqual(frames[6], frames[10])
        for speed in (3, 6, 10):
            fruit, honey, fish = (t[1] for t in got[speed])
            self.assertEqual(fruit, [vv3.FRUIT_LIVE_FOOD[speed]])
            self.assertEqual(honey, [vv3.FRUIT_LIVE_FOOD[speed]])
            self.assertEqual(fish, [vv3.FISH_LIVE_FOOD[speed]])

    def test_trips_from_the_bin_fall_in_the_measured_span(self):
        for key in JOBS:
            low, high = next(t.live_span[6] for t in vv3.TRIPS if t.key == key)
            with self.subTest(source=key):
                paid = [done * SECONDS for _, frames, done, _ in _bin_trips(key, 6, seed=14) if frames >= 0]
                self.assertGreaterEqual(len(paid), 4)
                for seconds in paid:
                    self.assertGreaterEqual(seconds, low - 1e-6)
                    self.assertLessEqual(seconds, high + 1e-6)

    def test_fruit_is_credited_at_the_tree_and_the_others_at_the_bin(self):
        v = fe.Village(seed=5)
        v.villager(skills=_farmer(farming=87))
        v.by_caller[HONEY_LAST_Y] = 0                       # the honey's last point inside the bin
        v.run_trip(fe.FRUIT_JOB, 0)
        for key in JOBS:
            paid, done = v.run_trip(JOBS[key], 2)
            with self.subTest(source=key):
                if key == "fruit picks":
                    self.assertLess(paid, done - 300, "the walk back comes after the credit")
                else:
                    self.assertGreaterEqual(paid, done - 3)
                self.assertEqual(v.region(*v.feet()), 0xE)

    @unittest.skipUnless(RELEASE, "release-only (slow): run with VVFP_RELEASE=1")
    def test_the_trip_samples_re_measure_exactly(self):
        for key in JOBS:
            trips = _bin_trips(key, 400, seed=11)
            paid = [(t, frames * SECONDS, done * SECONDS) for t, frames, done, _ in trips if frames >= 0]
            with self.subTest(source=key):
                self.assertEqual(len(paid), vv3.TRIP_SAMPLES[key][0])
                for samples, column in ((vv3.TRIP_SAMPLES, 2), (vv3.CREDIT_SAMPLES, 1)):
                    values = [row[column] for row in paid]
                    self.assertEqual((len(values), round(statistics.mean(values), 2), round(min(values), 2),
                                      round(max(values), 2)), samples[key])
                if key == "fruit picks":
                    for tree, sample in vv3.FRUIT_TREES.items():
                        values = [row[2] for row in paid if row[0] == tree]
                        self.assertEqual((len(values), round(statistics.mean(values), 2), round(min(values), 2),
                                          round(max(values), 2)), sample)
        trips = _bin_trips("fishing trips", 400, seed=13, farming=100)
        crabs = [done * SECONDS for _, frames, done, food in trips if food == [55]]
        self.assertEqual((len(crabs), round(statistics.mean(crabs), 2), round(min(crabs), 2), round(max(crabs), 2)),
                         vv3.TRIP_SAMPLES["crabs"])

    @unittest.skipUnless(RELEASE, "release-only (slow): run with VVFP_RELEASE=1")
    def test_a_live_cycle_run_replays(self):
        # 40 real-life hours of frames of the scheduler: the fruit picker at Farming 100, seed 1.
        v = fe.Village(seed=1)
        v.villager(skills=_farmer(farming=100), preference=0, site=0x17)
        paid = v.scheduler_cycle("fruit", 100, vv3.LIVE_CYCLE_HOURS)
        self.assertEqual(paid, {"fruit picks": vv3.LIVE_CYCLE_RUNS[("fruit picks", 100)][0]})

    def test_walk_speeds(self):
        # |vx| + |vy| per frame, in hundredths of a pixel (0x455A00 truncates each part).
        for kwargs, speed in (({}, 100), ({"likes": (0x26,)}, 300), ({"dislikes": (0x26,)}, 40),
                              ({"age": 1000}, 40), ({"age": 999}, 100)):
            v = fe.Village(seed=2)
            record = v.villager(skills=_farmer(farming=87), **kwargs)
            v.start_job(fe.FRUIT_JOB, 0)
            step = abs(v.r32(record + 0xEE8)) + abs(v.r32(record + 0xEEC))
            with self.subTest(**kwargs):
                self.assertIn(step, (speed - 1, speed))

    def test_a_failed_farming_check_ends_the_trip_without_food(self):
        for key in JOBS:
            for value, paid in ((73, True), (74, False)):
                v = fe.Village(seed=6)
                v.villager(skills=_farmer(farming=40))
                v.by_caller[FARMING_CHECK] = value
                frames, _ = v.run_trip(JOBS[key], 0)
                with self.subTest(source=key, roll=value):
                    self.assertEqual(frames >= 0, paid)

    def test_honey_dropped_below_the_bin_pays_nothing(self):
        for roll, paid in ((10, True), (11, False)):
            v = fe.Village(seed=8)
            v.villager(skills=_farmer(farming=87))
            v.by_caller[HONEY_LAST_Y] = roll
            frames, _ = v.run_trip(fe.HONEY_JOB, 0)
            with self.subTest(roll=roll):
                self.assertEqual(frames >= 0, paid)
                self.assertEqual(v.feet()[1], 0x4F5 + roll)
                self.assertEqual(v.region(*v.feet()) == 0xE, paid)
                self.assertEqual(v.r32(fe.HONEY), 3000 - 3 if paid else 3000)
        v = fe.Village(seed=8)
        self.assertTrue(all(v.region(x, 0x4F5 + roll) == 0xE for x in range(0x45C, 0x45C + 0x34) for roll in range(11)))
        self.assertFalse(any(v.region(x, 0x4F5 + 11) == 0xE for x in range(0x45C, 0x45C + 0x34)))

    def test_the_crab(self):
        for farming, roll, food in ((88, 9, [55]), (88, 10, [8]), (87, 0, [8])):
            v = fe.Village(seed=9)
            v.villager(skills=_farmer(farming=farming))
            v.by_caller[CRAB] = roll
            v.run_trip(fe.FISH_JOB, 0)
            with self.subTest(farming=farming, roll=roll):
                self.assertEqual([amount for _, amount, _ in v.credits], food)

    def test_a_tree_under_5_is_not_picked(self):
        for fruit, paid in ((5, True), (4, False)):
            v = fe.Village(seed=10, fruit=fruit)
            v.villager(skills=_farmer(farming=87))
            frames, _ = v.run_trip(fe.FRUIT_JOB, 0)
            self.assertEqual(frames >= 0, paid, fruit)


@unittest.skipUnless(HAVE_GAME, NO_GAME)
class CatchUpTests(unittest.TestCase):
    def test_four_turns_a_unit_and_one_meal(self):
        # 10 uncounted units: the meal every unit, job turns for all but the last 2.
        for difficulty, food, rolls, eaten in ((1, 1000, {}, 20), (2, 1000, {EXTRA_MEAL: 75}, 40),
                                               (2, 1000, {EXTRA_MEAL: 76}, 20), (0, 9000, {EXTRA_MEAL: 0}, 20),
                                               (1, 9000, {EXTRA_MEAL: 0}, 40), (1, 400, {LOW_FOOD_MEAL: 49}, 20),
                                               (1, 400, {LOW_FOOD_MEAL: 50}, 0)):
            v = fe.Village(seed=1, food=food, difficulty=difficulty)
            record = v.villager(age=500, skills=_farmer(farming=60))
            v.w32(record + fe.PROCESSED, 490)
            v.by_caller.update({SICKNESS_GATE: 0, **rolls})
            turns = v.aging_loop()
            with self.subTest(difficulty=difficulty, food=food, rolls=rolls):
                if difficulty != 2:             # (on Hard the sickness rolls elsewhere can make it sick: no turns)
                    self.assertEqual(turns, [record] * 32)
                self.assertEqual(food - v.food(), eaten)
                self.assertEqual(v.r32(record + fe.PROCESSED), 500)

    def test_no_turns_for_a_child_or_the_chief(self):
        for age, chief in ((279, False), (500, True)):
            v = fe.Village(seed=1)
            record = v.villager(age=age)
            v.uc.mem_write(record + fe.CHIEF, bytes([chief]))
            v.w32(record + fe.PROCESSED, age - 10)
            self.assertEqual(v.aging_loop(), [], (age, chief))

    def _turn(self, key: str, farming: int, rolls: dict, *, site: int | None = None, food: int = 1000,
              speed: int = 6):
        v = fe.Village(seed=3, speed=speed, food=food, honey=3000 if key == "honey picks" else 0,
                       fruit=1000 if key == "fruit picks" else 0)
        if key != "fishing trips":
            v.w32(fe.PUZZLES + 10 * 8, 0)
        v.villager(skills=_farmer(farming=farming), preference=0, site=SITES[key] if site is None else site)
        v.by_caller.update({FARMING_CHECK: 0, CHOOSER_BLANK: 99, CHOOSER_SKILLS[0]: 99, CHOOSER_LAST: 0,
                            HONEY_LAST_Y: 0, **rolls})
        v.catch_up_turn()
        return [amount for _, amount, _ in v.credits]

    def test_one_farming_turn_is_one_trip_at_the_catch_up_rate(self):
        for speed in (3, 6, 10):
            with self.subTest(speed=speed):
                self.assertEqual(self._turn("fruit picks", 100, {}, speed=speed), [4])
                self.assertEqual(self._turn("honey picks", 100, {}, speed=speed), [4])
                self.assertEqual(self._turn("fishing trips", 87, {}, speed=speed), [8])
        self.assertEqual(self._turn("fishing trips", 88, {CRAB: 9}), [55])
        self.assertEqual(self._turn("honey picks", 100, {HONEY_LAST_Y: 11}), [], "below the bin")

    def test_the_farming_check(self):
        for key in JOBS:
            with self.subTest(source=key):
                self.assertEqual(len(self._turn(key, 40, {FARMING_CHECK: 73})), 1)
                self.assertEqual(self._turn(key, 40, {FARMING_CHECK: 74}), [])

    def test_the_remembered_site(self):
        nothing = {CHOOSER_BLANK: 0}                        # the chooser gives no job
        for key in JOBS:
            with self.subTest(source=key):
                self.assertEqual(self._turn(key, 100, {**nothing, SITE_STOP: 19}), [], "rand(100) < 20 stops")
                self.assertEqual(len(self._turn(key, 100, {**nothing, SITE_STOP: 20, SITE_GO: 40})), 1)
                self.assertEqual(len(self._turn(key, 100, {**nothing, SITE_STOP: 20, SITE_GO: 39})), 1)
                self.assertEqual(self._turn(key, 100, {**nothing, SITE_STOP: 20, SITE_GO: 39}, food=8000), [])
                self.assertEqual(self._turn(key, 5, {**nothing, SITE_STOP: 99}), [], "Farming 6 or more")
                self.assertEqual(self._turn(key, 100, nothing, site=0), [], "no site: the chooser alone")

    def test_the_chooser_picks_farming_0_83096_of_turns(self):
        # Every class of each roll the chooser makes, weighted by its share of 100 (Farming 100, the others 10), with
        # no remembered site and only the fruit trees open.
        share = Fraction(0)
        sites = (CHOOSER_BLANK, *CHOOSER_SKILLS, CHOOSER_PREF)
        classes = ((0, 15, 99, 85),) + ((0, 16, 99, 84),) * 5 + ((0, 86, 99, 14),)
        v = fe.Village(seed=3, honey=0)
        v.w32(fe.PUZZLES + 10 * 8, 0)
        for pick in product((0, 1), repeat=len(sites)):
            weight = Fraction(1)
            for site, (low, low_w, high, high_w), which in zip(sites, classes, pick):
                v.by_caller[site] = (low, high)[which]
                weight *= Fraction((low_w, high_w)[which], 100)
            v.by_caller.update({CHOOSER_LAST: 0, FARMING_CHECK: 0})
            _refill(v, honey=0)
            v.villager(skills=_farmer(farming=100), preference=0)
            seen = len(v.credits)
            v.catch_up_turn()
            if [amount for _, amount, _ in v.credits[seen:]] == [4]:
                share += weight
        self.assertEqual(share, Fraction(83096, 100000))

    def test_the_last_roll_is_farming_plus_40(self):
        self.assertEqual(len(self._turn("fruit picks", 40, {CHOOSER_LAST: 79}, site=0)), 1)
        self.assertEqual(self._turn("fruit picks", 40, {CHOOSER_LAST: 80}, site=0), [])


if __name__ == "__main__":
    unittest.main()
