"""A New Home (VV1): the farmers' trips and catch-up job turns, re-measured from the stock exe.

Pins src/vv_game_mechanics_farmers_vv1.py.  Everything that needs the stock executable runs its own code in
unicorn through tests/farmers_emulation_vv1.py (what is stubbed there: rand, the clock, and drawing / sound /
text only) and skips when the executable is not present (CI).  The map is the one the stock map builder
0x414590 makes for a new village's state, so no game data file is needed.

The full re-measurement of TRIP_SAMPLES (1,200 trips, a few minutes) runs only with VVFP_RELEASE=1.
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

import farmers_emulation_vv1 as fe  # noqa: E402
import vv_game_mechanics_farmers as farmers  # noqa: E402
import vv_game_mechanics_farmers_vv1 as vv1  # noqa: E402

NO_EXE = "the stock A New Home executable is not present (research/stock-executables)"
RELEASE = os.environ.get("VVFP_RELEASE") == "1"
SECONDS = fe.FRAME_MS / 1000.0
JOBS = {"berry picks": fe.BERRIES, "crop harvests": fe.CROPS, "catches": fe.FISH}
REWARDS = {"berry picks": 14, "crop harvests": 15, "catches": 16}

# rand(N) call sites, by the address the call returns to.
CHOOSER_BLANK, CHOOSER_PREF, CHOOSER_LAST = 0x439AF0, 0x439C3D, 0x439C90
CHOOSER_SKILLS = (0x439B32, 0x439B55, 0x439B7F, 0x439BA8, 0x439BFD)   # Farming, Parenting, Building, Healing, Research
FARMING_CHECK = 0x43D475            # the skill test 0x43D440, Farming: passes on rand(100) <= Farming + 30
BIG_CATCH = 0x43F4C0                # Farming 90 or more: the big catch on rand(100) <= 20
FISH_SPOT = 0x43F683                # rand(100) > 50: the far fishing spot
FAR_SPOT_X = 0x43F800               # the far spot's x: 3 x (436 + rand(110))
DISPATCH_FISH = 0x44731E            # Farming level 3, beach clean: fishing on rand(100) < 50
SICKNESS_GATE = 0x42EE64            # the life loop's sickness roll: rand(100) < 50 skips it
EXTRA_MEAL = 0x42ECF9               # 2 more food on rand(100) <= 75 (Medium above 2,000, or Hard)

FARMER = {name: 10 for name in fe.SKILLS}


def _farmer(**skills):
    return {**FARMER, **skills}


def _bin_trips(job: int, n: int, seed: int, farming: int = 89):
    """n back-to-back trips from where the previous one ended, the sources kept full and the skill fixed."""
    v = fe.Village(seed=seed)
    v.villager(skills=_farmer(farming=farming))
    v.run_trip(job)
    out = []
    for _ in range(n):
        v.w32(fe.STATE + fe.FIELD, 800)
        v.w32(fe.STATE + fe.BUSH, 100_000)
        v.w32(v.rec(0) + fe.SKILLS["farming"], farming)
        start = v.feet()
        seen = len(v.rewards)
        paid, done = v.run_trip(job)
        out.append((start, paid, done, [r for _, r in v.rewards[seen:]]))
    return out


def _at_bin(feet) -> bool:
    return 1204 <= feet[0] <= 1214 and 1132 <= feet[1] <= 1199


class ModuleTests(unittest.TestCase):
    """The module's own consistency; no executable needed."""

    def test_the_trips_pair_with_the_page(self):
        turns, trips = farmers.game_trips(1)
        self.assertEqual(turns, 5)
        self.assertEqual([t.key for t in trips], ["berry picks", "crop harvests", "catches"])
        for trip in trips:
            self.assertEqual(trip.success_offset, 31)
            self.assertEqual(trip.catch_up_trips_per_turn, vv1.FARMING_CHOSEN)
            self.assertIsNone(trip.live_food, "the page's own food a trip (the reward 0x43A230) applies")
            self.assertIsNone(trip.catch_up_food, "catch-up pays as live")
            self.assertEqual(set(trip.live_seconds), {3, 6, 10})
            self.assertEqual(len(set(trip.live_seconds.values())), 1, "the speed does not change a trip")
            low, high = trip.live_span[6]
            self.assertLess(low, trip.live_seconds[6])
            self.assertLess(trip.live_seconds[6], high)
            n, mean, lo, hi = vv1.TRIP_SAMPLES[trip.key]
            self.assertEqual((mean, lo, hi), (trip.live_seconds[6], low, high))

    def test_the_chooser_share_and_the_edge_loss(self):
        self.assertAlmostEqual(vv1.FARMING_CHOSEN, 0.85 * (0.84 + 0.16 * 0.86), places=12)
        self.assertAlmostEqual(vv1.farming_chosen(100), 0.83096)
        self.assertAlmostEqual(vv1.farming_chosen(40), 0.83096 * 0.8)
        self.assertEqual(vv1.farming_chosen(1), 0.0)
        self.assertAlmostEqual(vv1.FISH_EDGE_LOSS, 0.1974, places=4)


@unittest.skipUnless(fe.STOCK.is_file(), NO_EXE)
class LiveTripTests(unittest.TestCase):
    def test_a_trip_is_the_same_at_every_speed(self):
        # The runner, the walk and the waits never read the speed value (only the pause): frame for frame equal.
        for job in (fe.BERRIES, fe.FISH):
            got = []
            for speed in (3, 6, 10):
                v = fe.Village(seed=4, speed=speed)
                v.villager(skills=_farmer(farming=89))
                got.append([v.run_trip(job) for _ in range(2)])
            self.assertEqual(got[0], got[1])
            self.assertEqual(got[1], got[2])

    def test_trips_from_the_bin_fall_in_the_measured_span(self):
        for key, job in JOBS.items():
            low, high = next(t.live_span[6] for t in vv1.TRIPS if t.key == key)
            paid = []
            # A fifth of fishing trips are lost at the map's edge, and the next one starts there: more of them.
            for start, frames, _, rewards in _bin_trips(job, 12 if job == fe.FISH else 5, seed=14):
                if _at_bin(start) and frames >= 0:
                    self.assertEqual(rewards, [REWARDS[key]])
                    paid.append(frames * SECONDS)
            with self.subTest(source=key):
                self.assertGreaterEqual(len(paid), 3)
                for seconds in paid:
                    self.assertGreaterEqual(seconds, low - 1e-6)
                    self.assertLessEqual(seconds, high + 1e-6)

    @unittest.skipUnless(RELEASE, "release-only (slow): run with VVFP_RELEASE=1")
    def test_the_trip_samples_re_measure_exactly(self):
        for key, (n, mean, low, high) in vv1.TRIP_SAMPLES.items():
            job = fe.FISH if key == "big catches" else JOBS[key]
            seed, farming, reward = (13, 100, 17) if key == "big catches" else (11, 89, REWARDS[key])
            trips = _bin_trips(job, 400, seed=seed, farming=farming)
            paid = [frames * SECONDS for start, frames, _, rewards in trips
                    if _at_bin(start) and frames >= 0 and rewards == [reward]]
            with self.subTest(source=key):
                self.assertEqual(len(paid), n)
                self.assertEqual(round(statistics.mean(paid), 2), mean)
                self.assertEqual((round(min(paid), 2), round(max(paid), 2)), (low, high))

    def test_walk_speeds(self):
        # |vx| + |vy| per frame, in hundredths of a pixel (0x439CC0 truncates each part).
        for kwargs, speed in (({}, 100), ({"likes": (0x26,)}, 300), ({"age": 1001}, 40), ({"age": 1000}, 100)):
            v = fe.Village(seed=2)
            v.villager(skills=_farmer(farming=89), **kwargs)
            v.start_job(fe.BERRIES)
            step = abs(v.r32(v.rec(0) + 0xC)) + abs(v.r32(v.rec(0) + 0x10))
            with self.subTest(**kwargs):
                self.assertIn(step, (speed - 1, speed))

    def test_a_failed_farming_check_ends_the_trip_without_food(self):
        for value, paid in ((70, True), (71, False)):
            v = fe.Village(seed=6)
            v.villager(skills=_farmer(farming=40))
            v.by_caller[FARMING_CHECK] = value
            frames, _ = v.run_trip(fe.BERRIES)
            self.assertEqual(frames >= 0, paid, value)

    def test_far_fishing_spots_past_the_edge_lose_the_trip(self):
        for x_roll, paid in ((84, True), (85, False)):
            v = fe.Village(seed=8)
            v.villager(skills=_farmer(farming=89))
            v.by_caller.update({FISH_SPOT: 51, FAR_SPOT_X: x_roll})
            frames, _ = v.run_trip(fe.FISH)
            with self.subTest(x_roll=x_roll):
                self.assertEqual(frames >= 0, paid)
                if not paid:
                    self.assertEqual(v.feet()[0], 0x603 + 20, "stopped at the map's edge clamp 0x445F58")


@unittest.skipUnless(fe.STOCK.is_file(), NO_EXE)
class CatchUpTests(unittest.TestCase):
    def test_five_turns_a_unit_and_one_meal(self):
        # 10 uncounted units: the meal every unit, job turns for all but the last 2.
        for difficulty, extra, eaten in ((1, 0, 20), (2, 75, 40), (2, 76, 20), (0, 0, 20)):
            v = fe.Village(seed=1, food=1000)
            v.w32(fe.STATE + fe.DIFFICULTY, difficulty)
            v.villager(age=500, skills=_farmer(farming=60))
            v.w32(v.rec(0) + fe.PROC_AGE, 490)
            v.by_caller.update({SICKNESS_GATE: 0, EXTRA_MEAL: extra})
            turns = v.life_loop()
            with self.subTest(difficulty=difficulty, extra=extra):
                self.assertEqual(turns, [0] * 40)
                self.assertEqual(1000 - v.food(), eaten)
                self.assertEqual(v.r32(v.rec(0) + fe.PROC_AGE), 500)

    def test_no_turns_for_a_child(self):
        v = fe.Village(seed=1)
        v.villager(age=279)
        v.w32(v.rec(0) + fe.PROC_AGE, 269)
        v.by_caller[SICKNESS_GATE] = 0
        self.assertEqual(v.life_loop(), [])

    def _turn(self, level: int, source: int, farming: int, rolls: dict, bush: int = 1300):
        v = fe.Village(seed=3, farming_level=level, bush=bush)
        v.villager(skills=_farmer(farming=farming), source=source, preference=1)
        v.by_caller.update({CHOOSER_BLANK: 99, CHOOSER_SKILLS[0]: 99, CHOOSER_LAST: 0, FARMING_CHECK: 0, **rolls})
        food = v.food()
        v.catch_up_turn()
        return [r for _, r in v.rewards], v.food() - food

    def test_one_farming_turn_is_one_trip_paying_as_live(self):
        self.assertEqual(self._turn(1, 3, 100, {}), ([14], 1300 // 130))
        self.assertEqual(self._turn(1, 3, 100, {}, bush=50), ([14], 2), "at least 2")
        self.assertEqual(self._turn(2, 5, 100, {}, bush=50), ([15], 7))
        self.assertEqual(self._turn(3, 6, 89, {DISPATCH_FISH: 0}), ([16], 9))
        self.assertEqual(self._turn(3, 6, 90, {DISPATCH_FISH: 0, BIG_CATCH: 20}), ([17], 55))
        self.assertEqual(self._turn(3, 6, 90, {DISPATCH_FISH: 0, BIG_CATCH: 21}), ([16], 9))

    def test_the_farming_check(self):
        self.assertEqual(self._turn(1, 3, 40, {FARMING_CHECK: 70}), ([14], 10))
        self.assertEqual(self._turn(1, 3, 40, {FARMING_CHECK: 71}), ([], 0))
        self.assertEqual(self._turn(2, 5, 0, {FARMING_CHECK: 30, CHOOSER_LAST: 0}), ([], 0), "Farming 0: no job")
        self.assertEqual(self._turn(2, 5, 40, {CHOOSER_LAST: 79}, bush=50), ([15], 7))
        self.assertEqual(self._turn(2, 5, 40, {CHOOSER_LAST: 80}, bush=50), ([], 0), "(Farming + 40) in 100")

    def test_the_chooser_picks_farming_0_83096_of_turns(self):
        # Every class of each roll the chooser makes, weighted by its share of 100 (Farming 100, the others 10).
        share = Fraction(0)
        sites = (CHOOSER_BLANK, *CHOOSER_SKILLS, CHOOSER_PREF)
        classes = ((0, 15, 99, 85),) + ((0, 16, 99, 84),) * 5 + ((0, 86, 99, 14),)
        v = fe.Village(seed=3, farming_level=1, bush=100_000)
        v.villager(skills=_farmer(farming=100), source=3, preference=1)
        for pick in product((0, 1), repeat=len(sites)):
            weight = Fraction(1)
            for site, (low, low_w, high, high_w), which in zip(sites, classes, pick):
                v.by_caller[site] = (low, high)[which]
                weight *= Fraction((low_w, high_w)[which], 100)
            v.by_caller.update({CHOOSER_LAST: 0, FARMING_CHECK: 0})
            v.villager(skills=_farmer(farming=100), source=3, preference=1)
            seen = len(v.rewards)
            v.catch_up_turn()
            if [r for _, r in v.rewards[seen:]] == [14]:
                share += weight
        self.assertEqual(share, Fraction(83096, 100000))


@unittest.skipUnless(fe.STOCK.is_file(), NO_EXE)
class DispatcherTests(unittest.TestCase):
    def _where(self, level, source, rolls, bush=1000, field=800, beach=True):
        v = fe.Village(seed=3, farming_level=level, bush=bush, field=field, beach_clean=beach)
        v.villager(skills=_farmer(farming=100), source=source)
        jobs = []
        for job in (fe.BERRIES, fe.CROPS, fe.FISH, 0x445020):
            v.uc.hook_add(fe.UC_HOOK_CODE, lambda *_a, job=job: jobs.append(job), begin=job, end=job)
        v.by_caller.update(rolls)
        v.call(0x4472C0, fe.MGR, 0, 1)
        return jobs[:1]

    def test_the_set_source_is_kept(self):
        W = 0x445020
        self.assertEqual(self._where(1, 0, {}), [fe.BERRIES])
        self.assertEqual(self._where(1, 0, {}, bush=0), [])
        self.assertEqual(self._where(2, 3, {0x44741C: 99}), [fe.BERRIES])
        self.assertEqual(self._where(2, 5, {0x44741C: 0}), [fe.CROPS])
        self.assertEqual(self._where(2, 3, {}, bush=99), [fe.CROPS])
        self.assertEqual(self._where(2, 3, {}, field=0), [W])
        self.assertEqual(self._where(3, 6, {DISPATCH_FISH: 99}), [fe.FISH])
        self.assertEqual(self._where(3, 3, {DISPATCH_FISH: 49}), [fe.FISH])
        self.assertEqual(self._where(3, 3, {DISPATCH_FISH: 50, 0x44737A: 99}), [fe.BERRIES])
        self.assertEqual(self._where(3, 5, {DISPATCH_FISH: 50, 0x4473B0: 99}), [fe.CROPS])
        self.assertEqual(self._where(3, 6, {0x44737A: 99}, beach=False), [])


if __name__ == "__main__":
    unittest.main()
