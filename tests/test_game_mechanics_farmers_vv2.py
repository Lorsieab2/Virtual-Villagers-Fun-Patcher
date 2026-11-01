"""The Lost Children (VV2): the farmers' trips and catch-up job turns, re-measured from the stock exe.

Pins src/vv_game_mechanics_farmers_vv2.py.  Everything that needs the stock executable runs its own code in
unicorn through tests/farmers_emulation_vv2.py (what is stubbed there: rand, the clock, and drawing / sound / text
only) and skips when the executable is not present (CI).  The map is the one the stock map builder 0x418660 makes
from a grown village's state (research/game-data/vv2/grown_village.ldw: the owner's slot 5 save, game data that is
never committed); those tests skip without it.

The full re-measurement of TRIP_SAMPLES (1,600 trips, several minutes) and a scheduler run run only with
VVFP_RELEASE=1.
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

import farmers_emulation_vv2 as fe  # noqa: E402
import vv_game_mechanics_farmers as farmers  # noqa: E402
import vv_game_mechanics_farmers_vv2 as vv2  # noqa: E402

NO_EXE = "the stock The Lost Children executable is not present (research/stock-executables)"
NO_SAVE = "the grown village's state is not present (research/game-data/vv2/grown_village.ldw)"
HAVE = fe.STOCK.is_file() and fe.GROWN.is_file()
RELEASE = os.environ.get("VVFP_RELEASE") == "1"
SECONDS = fe.FRAME_MS / 1000.0
KEYS = ("coconut trips", "crop trips", "fishing trips")
JOBS = {"coconut trips": fe.COCONUTS, "crop trips": fe.CROPS, "fishing trips": fe.FISH}
CALLBACKS = {"coconut trips": 27, "crop trips": 28, "fishing trips": 29}
BIG = 30

# rand(N) call sites, by the address the call returns to.
CHOOSER_BLANK, CHOOSER_PREF, CHOOSER_LAST = 0x449C73, 0x449DCA, 0x449E1B
CHOOSER_SKILLS = (0x449CB9, 0x449CDF, 0x449D0C, 0x449D38, 0x449D85)   # Farming, Parenting, Building, Healing, Research
FARMING_CHECK = 0x44E1D5            # the skill step 0x44E170: passes on rand(100) <= Farming + 33
BIG_CATCH = 0x450BF7                # Farming 88 or more: the big catch on rand(100) < 10
L3_FISH_EMPTY, L3_FISH, L3_COCO_EMPTY, L3_COCO = 0x45FC56, 0x45FC65, 0x45FCA2, 0x45FCB1
L2_FISH, L2_COCO, L2_COCO_EMPTY = 0x45FD2B, 0x45FD7E, 0x45FD9D
L1_FISH = 0x45FE05
EXTRA_MEAL = 0x43BB26               # 2 more food on rand(100) <= 75 (Medium above 4,000, or Hard)
NO_SICKNESS = {0x43B306: 5399, 0x43B327: 2459, 0x43B348: 1439, 0x43B38A: 999}   # the sickness rolls 0x43B2B0
LIKES_LEARNING, RUNNING = 0x27, 0x26

FARMER = {name: 10 for name in fe.SKILLS}


def _farmer(**skills):
    return {**FARMER, **skills}


def _village(**kw):
    return fe.Village(state=fe.grown_state(), **kw)


def _bin_trips(job: int, n: int, seed: int, farming: int = 87):
    """n back-to-back trips from where the previous one ended, the sources kept full and the skill fixed."""
    v = _village(seed=seed)
    v.villager(skills=_farmer(farming=farming))
    v.farming_fixed = farming
    v.run_trip(job)
    out = []
    for _ in range(n):
        v.w32(fe.STATE + fe.COCONUT_COUNT, 1500)
        v.w32(fe.STATE + fe.CROP_COUNT, 800)
        v.w32(fe.STATE + fe.ALLOWANCE, 100_000)
        v.w32(fe.STATE + fe.FOOD, 1000)
        start = v.feet()
        seen = len(v.rewards)
        paid, done = v.run_trip(job)
        out.append((start, paid, done, [r for _, r in v.rewards[seen:]]))
    return out


def _at_bin(feet) -> bool:
    """Where a trip ends: the food bin (coconuts and crops x 1130-1141, y 970-974; fishing at 1150, 992)."""
    return 1120 <= feet[0] <= 1160 and 965 <= feet[1] <= 1000


class ModuleTests(unittest.TestCase):
    """The module's own consistency; no executable needed."""

    def test_the_trips_pair_with_the_page(self):
        turns, trips = farmers.game_trips(2)
        self.assertEqual(turns, 4)
        self.assertEqual(tuple(t.key for t in trips), KEYS)
        page = (ROOT / "src" / "vv_game_mechanics_vv2.py").read_text(encoding="utf-8")
        for trip in trips:
            self.assertIn(f'("{trip.key}"', page, "the page's Context.trips names it")
            self.assertEqual(trip.success_offset, 34)
            self.assertEqual(trip.catch_up_trips_per_turn, vv2.FARMING_CHOSEN)
            self.assertEqual(trip.live_food, vv2.LIVE_FOOD[trip.key])
            self.assertEqual(trip.catch_up_food, vv2.CATCH_UP_FOOD[trip.key])
            self.assertEqual(set(trip.live_seconds), {3, 6, 10})
            self.assertEqual(len(set(trip.live_seconds.values())), 1, "the speed does not change a trip")
            low, high = trip.live_span[6]
            self.assertLess(low, trip.live_seconds[6])
            self.assertLess(trip.live_seconds[6], high)
            n, mean, lo, hi = vv2.TRIP_SAMPLES[trip.key]
            self.assertEqual((mean, lo, hi), (trip.live_seconds[6], low, high))
            self.assertEqual(set(vv2.LIVE_CYCLE[trip.key]), {100, 50, 20})
            self.assertTrue(all(s > trip.live_seconds[6] for s in vv2.LIVE_CYCLE[trip.key].values()))

    def test_the_page_food_matches_the_payoffs(self):
        # The page's Context.trips food by speed (Fast, Normal, Slow) is the payoffs' live food.
        self.assertEqual(vv2.LIVE_FOOD, {"coconut trips": {3: 8, 6: 4, 10: 2}, "crop trips": {3: 10, 6: 7, 10: 4},
                                         "fishing trips": {3: 11, 6: 8, 10: 5}})
        self.assertEqual(vv2.CATCH_UP_FOOD, {"coconut trips": 4, "crop trips": 7, "fishing trips": 8})

    def test_the_chooser_share(self):
        self.assertAlmostEqual(vv2.FARMING_CHOSEN, 0.85 * (0.84 + 0.16 * 0.86), places=12)
        self.assertAlmostEqual(vv2.farming_chosen(100), 0.83096)
        self.assertAlmostEqual(vv2.farming_chosen(40), 0.83096 * 0.8)
        self.assertEqual(vv2.farming_chosen(5), 0.0)
        self.assertAlmostEqual(vv2.farming_chosen(6), 0.83096 * 0.46)


@unittest.skipUnless(fe.STOCK.is_file(), NO_EXE)
@unittest.skipUnless(fe.GROWN.is_file(), NO_SAVE)
class LiveTripTests(unittest.TestCase):
    def test_a_trip_is_the_same_at_every_speed_and_pays_by_speed(self):
        # The update, the walk and the waits never read the speed value: frame for frame equal; the payoffs read it.
        for key, job in JOBS.items():
            got, food = [], []
            for speed in (3, 6, 10):
                v = _village(seed=4, speed=speed)
                v.villager(skills=_farmer(farming=87))
                got.append([v.run_trip(job) for _ in range(2)])
                food.append({a for _, a in v.food_log})
            with self.subTest(source=key):
                self.assertEqual(got[0], got[1])
                self.assertEqual(got[1], got[2])
                self.assertEqual(food, [{vv2.LIVE_FOOD[key][s]} for s in (3, 6, 10)])

    def test_trips_from_the_bin_fall_in_the_measured_span(self):
        for key, job in JOBS.items():
            low, high = next(t.live_span[6] for t in vv2.TRIPS if t.key == key)
            paid = []
            for start, frames, _, rewards in _bin_trips(job, 5, seed=14):
                if _at_bin(start) and frames >= 0:
                    self.assertEqual(rewards, [CALLBACKS[key]])
                    paid.append(frames * SECONDS)
            with self.subTest(source=key):
                self.assertEqual(len(paid), 5)
                for seconds in paid:
                    self.assertGreaterEqual(seconds, low - 0.005)    # the span is rounded to 0.01 s
                    self.assertLessEqual(seconds, high + 0.005)

    @unittest.skipUnless(RELEASE, "release-only (slow): run with VVFP_RELEASE=1")
    def test_the_trip_samples_re_measure_exactly(self):
        for key, (n, mean, low, high) in vv2.TRIP_SAMPLES.items():
            job = fe.FISH if key == "big catches" else JOBS[key]
            seed, farming, reward = (13, 100, BIG) if key == "big catches" else (11, 87, CALLBACKS[key])
            trips = _bin_trips(job, 400, seed=seed, farming=farming)
            paid = [frames * SECONDS for start, frames, _, rewards in trips
                    if _at_bin(start) and frames >= 0 and rewards == [reward]]
            with self.subTest(source=key):
                self.assertEqual(len(paid), n)
                self.assertEqual(round(statistics.mean(paid), 2), mean)
                self.assertEqual((round(min(paid), 2), round(max(paid), 2)), (low, high))

    def test_walk_speeds(self):
        # |vx| + |vy| per frame, in hundredths of a pixel (0x449E80 truncates each part); the speed at +0x60.
        # The grown village is at Medicine level 3: an elder from 1,321 age units (840 + 160 x 3).
        cases = (({}, 100), ({"likes": (RUNNING,)}, 300), ({"dislikes": (RUNNING,)}, 40), ({"age": 1321}, 40),
                 ({"age": 1320}, 100), ({"age": 279}, 300), ({"age": 279, "dislikes": (RUNNING,)}, 40),
                 ({"age": 1321, "likes": (RUNNING,)}, 40), ({"health": 5}, 100), ({"skills": _farmer(farming=0)}, 100))
        for kwargs, speed in cases:
            v = _village(seed=2)
            v.villager(**{"skills": _farmer(farming=87), **kwargs})
            v.start_job(fe.COCONUTS)
            step = abs(v.r32(v.rec(0) + 0xC)) + abs(v.r32(v.rec(0) + 0x10))
            with self.subTest(**{k: str(w) for k, w in kwargs.items()}):
                self.assertEqual(v.r32(v.rec(0) + 0x60), speed)
                self.assertIn(step, (speed - 1, speed))

    def test_the_farming_check(self):
        # Passes on rand(100) <= Farming + 33 (+ 66 liking learning); a failure ends the trip with no food.
        for farming, likes, value, paid in ((40, (), 73, True), (40, (), 74, False),
                                            (0, (LIKES_LEARNING,), 66, True), (0, (LIKES_LEARNING,), 67, False)):
            v = _village(seed=6)
            v.villager(skills=_farmer(farming=farming), likes=likes)
            v.by_caller[FARMING_CHECK] = value
            frames, _ = v.run_trip(fe.CROPS)
            with self.subTest(farming=farming, likes=likes, value=value):
                self.assertEqual(frames >= 0, paid)
                if not paid:
                    self.assertEqual(v.food_log, [])

    def test_the_big_catch(self):
        for farming, value, food in ((88, 9, 55), (88, 10, 8), (100, 0, 55), (87, 0, 8)):
            for speed in (3, 6, 10):
                v = _village(seed=8, speed=speed)
                v.villager(skills=_farmer(farming=farming))
                v.by_caller[BIG_CATCH] = value
                v.run_trip(fe.FISH)
                want = food if food == 55 else vv2.LIVE_FOOD["fishing trips"][speed]
                with self.subTest(farming=farming, value=value, speed=speed):
                    self.assertEqual([a for _, a in v.food_log], [want])

    def test_no_food_from_an_empty_field_or_fished_out_water(self):
        v = _village(seed=2, crops=0)
        v.villager(skills=_farmer(farming=87))
        self.assertEqual(v.run_trip(fe.WATER)[0], -1)
        v = _village(seed=2, fish=0, fishing_solved=False)
        v.villager(skills=_farmer(farming=87))
        self.assertEqual(v.run_trip(fe.FISH)[0], -1)
        self.assertEqual(v.food_log, [])

    @unittest.skipUnless(RELEASE, "release-only (slow): run with VVFP_RELEASE=1")
    def test_the_scheduler_at_farming_100(self):
        # 4 real-life hours of a Farming-preference farmer at Farming 100, coconuts pinned: within 5% of LIVE_CYCLE.
        v = _village(seed=21)
        v.villager(skills=_farmer(farming=100), preference=1, health=100)
        v.farming_fixed = 100
        v.by_caller.update({L3_FISH: 99, L3_COCO: 0})
        frames = int(4 * 3600 / SECONDS)
        for k in range(frames):
            if k % 300 == 0:
                v.w32(fe.STATE + fe.COCONUT_COUNT, 1500)
                v.w32(fe.STATE + fe.FOOD, 1000)
            v.step_frame()
        paid = sum(1 for _, r in v.rewards if r == 27)
        self.assertAlmostEqual(frames * SECONDS / paid, vv2.LIVE_CYCLE["coconut trips"][100],
                               delta=0.05 * vv2.LIVE_CYCLE["coconut trips"][100])


@unittest.skipUnless(fe.STOCK.is_file(), NO_EXE)
@unittest.skipUnless(fe.GROWN.is_file(), NO_SAVE)
class CatchUpTests(unittest.TestCase):
    def test_four_turns_a_unit_and_one_meal(self):
        # 10 uncounted units: the meal every unit, job turns for all but the last 2.
        for difficulty, food, extra, eaten in ((1, 1000, 0, 20), (1, 5000, 75, 40), (1, 5000, 76, 20),
                                               (2, 1000, 75, 40), (0, 5000, 0, 20)):
            v = _village(seed=1, food=food, difficulty=difficulty)
            v.villager(age=500, skills=_farmer(farming=60))
            v.w32(v.rec(0) + fe.PROC_AGE, 490)
            v.by_caller.update({**NO_SICKNESS, EXTRA_MEAL: extra})
            turns = v.life_loop()
            with self.subTest(difficulty=difficulty, food=food, extra=extra):
                self.assertEqual(turns, [0] * 32)
                self.assertEqual(food - v.food(), eaten)
                self.assertEqual(v.r32(v.rec(0) + fe.PROC_AGE), 500)

    def test_no_turns_for_a_child(self):
        v = _village(seed=1)
        v.villager(age=279)
        v.w32(v.rec(0) + fe.PROC_AGE, 269)
        v.by_caller.update(NO_SICKNESS)
        self.assertEqual(v.life_loop(), [])

    def _turn(self, *, speed=6, level=1, farming=100, rolls=None, fish=0, solved=False, dam=True, likes=()):
        v = _village(seed=3, speed=speed, farming_level=level, fish=fish, fishing_solved=solved, dam=dam)
        v.villager(skills=_farmer(farming=farming), preference=1, likes=likes)
        v.by_caller.update({CHOOSER_BLANK: 99, CHOOSER_SKILLS[0]: 99, CHOOSER_LAST: 0, FARMING_CHECK: 0,
                            **(rolls or {})})
        food = v.food()
        v.catch_up_turn()
        return [r for _, r in v.rewards], v.food() - food

    def test_one_farming_turn_is_one_trip_paying_the_catch_up_amount(self):
        for speed in (3, 6, 10):
            with self.subTest(speed=speed):
                self.assertEqual(self._turn(speed=speed, level=2, dam=False), ([27], 4), "coconuts")
                self.assertEqual(self._turn(speed=speed, level=1), ([28], 7), "crops")
                self.assertEqual(self._turn(speed=speed, level=1, fish=50, dam=False), ([29], 8), "fish")
                self.assertEqual(self._turn(speed=speed, level=1, fish=50, dam=False, rolls={BIG_CATCH: 9}),
                                 ([30], 55), "the big catch")

    def test_the_farming_check(self):
        self.assertEqual(self._turn(farming=40, rolls={FARMING_CHECK: 73}), ([28], 7))
        self.assertEqual(self._turn(farming=40, rolls={FARMING_CHECK: 74}), ([], 0))
        self.assertEqual(self._turn(farming=40, rolls={CHOOSER_LAST: 79}), ([28], 7))
        self.assertEqual(self._turn(farming=40, rolls={CHOOSER_LAST: 80}), ([], 0), "(Farming + 40) in 100")
        self.assertEqual(self._turn(farming=5, rolls={CHOOSER_PREF: 0, CHOOSER_LAST: 0}), ([], 0), "Farming 5: no job")

    def test_the_chooser_picks_farming_0_83096_of_turns(self):
        # Every class of each roll the chooser makes, weighted by its share of 100 (Farming 100, the others 10).
        share = Fraction(0)
        sites = (CHOOSER_BLANK, *CHOOSER_SKILLS, CHOOSER_PREF)
        classes = ((0, 15, 99, 85),) + ((0, 16, 99, 84),) * 5 + ((0, 86, 99, 14),)
        v = _village(seed=3, farming_level=1)
        for pick in product((0, 1), repeat=len(sites)):
            weight = Fraction(1)
            for site, (low, low_w, high, high_w), which in zip(sites, classes, pick):
                v.by_caller[site] = (low, high)[which]
                weight *= Fraction((low_w, high_w)[which], 100)
            v.by_caller.update({CHOOSER_LAST: 0, FARMING_CHECK: 0})
            v.w32(fe.STATE + fe.CROP_COUNT, 800)
            v.villager(skills=_farmer(farming=100), preference=1)
            seen = len(v.rewards)
            v.catch_up_turn()
            if [r for _, r in v.rewards[seen:]] == [28]:
                share += weight
        self.assertEqual(share, Fraction(83096, 100000))


@unittest.skipUnless(fe.STOCK.is_file(), NO_EXE)
@unittest.skipUnless(fe.GROWN.is_file(), NO_SAVE)
class DispatcherTests(unittest.TestCase):
    def _where(self, level, rolls, *, fish=0, solved=True, dam=True, coconuts=1500, crops=800, dislikes=()):
        v = _village(seed=3, farming_level=level, fish=fish, fishing_solved=solved, dam=dam, coconuts=coconuts,
                     crops=crops)
        v.villager(skills=_farmer(farming=100), dislikes=dislikes)
        jobs = []
        for job in (fe.COCONUTS, fe.CROPS, fe.FISH, fe.WATER):
            v.uc.hook_add(fe.UC_HOOK_CODE, lambda *_a, job=job: jobs.append(job), begin=job, end=job)
        v.by_caller.update(rolls)
        v.call(fe.DISPATCH, fe.MGR, 0, 1)
        return jobs[:1]

    def test_the_sources(self):
        C, F, K, W = fe.COCONUTS, fe.CROPS, fe.FISH, fe.WATER
        # Level 1: fishing on rand(100) > 50 while fish remain (Sustainable Fishing not looked at), always without
        # the dam; otherwise the field.
        self.assertEqual(self._where(1, {L1_FISH: 51}, fish=5), [K])
        self.assertEqual(self._where(1, {L1_FISH: 50}, fish=5), [F])
        self.assertEqual(self._where(1, {L1_FISH: 50}, fish=5, dam=False), [K])
        self.assertEqual(self._where(1, {}, fish=0, solved=True), [F])
        self.assertEqual(self._where(1, {}, fish=0, crops=0), [W])
        self.assertEqual(self._where(1, {}, fish=0, dam=False), [])
        # Level 2.
        self.assertEqual(self._where(2, {L2_FISH: 80}), [K])
        self.assertEqual(self._where(2, {L2_FISH: 81, L2_COCO: 51}), [C])
        self.assertEqual(self._where(2, {L2_FISH: 81, L2_COCO: 50}), [F])
        self.assertEqual(self._where(2, {L2_COCO: 50, L2_COCO_EMPTY: 49}, solved=False, crops=0), [C])
        self.assertEqual(self._where(2, {L2_COCO: 50, L2_COCO_EMPTY: 50}, solved=False, crops=0), [W])
        self.assertEqual(self._where(2, {L2_COCO: 0}, solved=False, dam=False), [C])
        self.assertEqual(self._where(2, {L2_COCO: 99}, solved=False, dislikes=(0x10,)), [F])
        self.assertEqual(self._where(2, {}, solved=False, coconuts=10), [F])
        # Level 3.
        self.assertEqual(self._where(3, {L3_FISH: 39}), [K])
        self.assertEqual(self._where(3, {L3_FISH: 40, L3_COCO: 24}), [C])
        self.assertEqual(self._where(3, {L3_FISH: 40, L3_COCO: 25}), [F])
        self.assertEqual(self._where(3, {L3_FISH_EMPTY: 79}, crops=0), [K])
        self.assertEqual(self._where(3, {L3_FISH_EMPTY: 80, L3_FISH: 39}, crops=0), [K])
        self.assertEqual(self._where(3, {L3_COCO_EMPTY: 74}, solved=False, crops=0), [C])
        self.assertEqual(self._where(3, {L3_COCO_EMPTY: 75, L3_COCO: 25}, solved=False, crops=0), [W])
        self.assertEqual(self._where(3, {L3_COCO: 25}, solved=False, dam=False), [])


if __name__ == "__main__":
    unittest.main()
