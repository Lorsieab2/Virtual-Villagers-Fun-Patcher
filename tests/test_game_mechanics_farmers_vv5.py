"""New Believers (VV5): the farmers' trips and catch-up job turns, re-measured from the stock exe.

Pins src/vv_game_mechanics_farmers_vv5.py.  Everything that needs the stock executable runs its own code in unicorn
through tests/farmers_emulation_vv5.py (what is stubbed there: RNG, the real clock, the C runtime's plumbing, and
drawing / sound only) and skips when the executable or the game's data files (research/game-data/vv5: lcmap.dat,
wpts.dat, anims.dat, animpts.dat) are not present (CI).

The full re-measurements (TRIP_SAMPLES: 1,200 trips; one 8-hour LIVE_CYCLE run) run only with VVFP_RELEASE=1.
"""
from __future__ import annotations

import os
import re
import statistics
import sys
import unittest
from fractions import Fraction
from itertools import product
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import farmers_emulation_vv5 as fe  # noqa: E402
import vv_game_mechanics_farmers as farmers  # noqa: E402
import vv_game_mechanics_farmers_vv5 as vv5  # noqa: E402

NO_EXE = "the stock New Believers executable or its data files are not present (research/)"
RELEASE = os.environ.get("VVFP_RELEASE") == "1"
SECONDS = fe.FRAME_MS / 1000.0
JOBS = {"noni picks": fe.NONI, "crop harvests": fe.CROPS, "fish": fe.FISH}
PLAYER = {"noni picks": fe.PLAYER_NONI, "crop harvests": fe.PLAYER_CROPS, "fish": fe.PLAYER_FISH}

# rand(N) call sites, by the address the call returns to.
CHOOSER_BLANK, CHOOSER_PREF, CHOOSER_LAST = 0x46A3D1, 0x46A572, 0x46A5A0
CHOOSER_SKILLS = (0x46A425, 0x46A44A, 0x46A47F, 0x46A4AA, 0x46A506, 0x46A532)  # Farming, Parenting, Building, ...
KEPT_FIRST, KEPT_SECOND = 0x46BD1C, 0x46BD2B   # the player's job 0x46BCF0: rand(100) < 20; rand(100) < 40
FARMING_CHECK = 0x46B30A    # the skill check 0x46B270, Farming: passes on rand(100) <= Farming + 33
SOURCE_PICK = 0x46C628      # the dispatcher's rand(count of open sources)
EXTRA_MEAL = 0x472DE7       # 2 more food on rand(100) <= 75 (Medium at 8,000 or more, or Hard)

# One 8-hour LIVE_CYCLE run as measured (seed 31): paying trips from the source the believer was dropped on.
LIVE_COUNTS_SEED_31 = {("crop harvests", 100): 254}


def _bin_trips(job: int, n: int, seed: int, farming: int = 89, speed: int = 6, **villager):
    """n back-to-back trips from where the previous one ended, the sources kept full and the skill fixed."""
    v = fe.Village(seed=seed, speed=speed)
    v.villager(skills={"farming": farming}, **villager)
    v.run_trip(job)
    out = []
    for _ in range(n):
        v.w32(v.mgr + fe.NONI_LEFT, 1000)
        v.w32(v.mgr + fe.CROPS_LEFT, 800)
        v.wf(fe.V0 + fe.SKILLS, float(farming))
        start = v.feet()
        seen = len(v.food_log)
        paid, done = v.run_trip(job)
        out.append((start, paid, done, [c for _, _, c in v.food_log[seen:]]))
    return out


def _at_bin(feet) -> bool:
    return 1100 <= feet[0] <= 1220 and 1190 <= feet[1] <= 1240


class ModuleTests(unittest.TestCase):
    """The module's own consistency; no executable needed."""

    def test_the_trips_pair_with_the_page(self):
        turns, trips = farmers.game_trips(5)
        self.assertEqual(turns, 4)
        self.assertEqual([t.key for t in trips], ["noni picks", "crop harvests", "fish"])
        page = (ROOT / "src" / "vv_game_mechanics_vv5.py").read_text(encoding="utf-8")
        listed = re.search(r"trips=\[(.*?)\]\)", page, re.S).group(1)
        self.assertEqual(re.findall(r'\("([a-z ]+)"', listed), [t.key for t in trips])
        for trip in trips:
            self.assertEqual(trip.success_offset, 34)
            self.assertAlmostEqual(trip.catch_up_trips_per_turn, vv5.CATCH_UP_TRIPS)
            self.assertEqual(set(trip.live_seconds), {3, 6, 10})
            self.assertEqual(len(set(trip.live_seconds.values())), 1, "the speed does not change a trip")
            low, high = trip.live_span[6]
            self.assertLess(low, trip.live_seconds[6])
            self.assertLess(trip.live_seconds[6], high)
            n, mean, lo, hi = vv5.TRIP_SAMPLES[trip.key]
            self.assertEqual((mean, lo, hi), (trip.live_seconds[6], low, high))
            self.assertTrue(all(s > 0 for s in vv5.LIVE_CYCLE[trip.key].values()))
        crops = trips[1]
        self.assertEqual(crops.live_food, {3: 10, 6: 7, 10: 4})
        self.assertEqual(crops.catch_up_food, 7)
        self.assertIsNone(trips[0].live_food, "noni: the page's max(2, noni / 100)")
        self.assertIsNone(trips[2].live_food, "fish: the page's 4")

    def test_the_chooser_and_player_job_shares(self):
        self.assertAlmostEqual(vv5.FARMING_CHOSEN, 0.85 * (0.84 + 0.16 * 0.86), places=12)
        self.assertAlmostEqual(vv5.farming_chosen(100), 0.83096)
        self.assertAlmostEqual(vv5.farming_chosen(40), 0.83096 * 0.8)
        self.assertEqual(vv5.farming_chosen(5), 0.0)
        self.assertAlmostEqual(vv5.CATCH_UP_TRIPS, 0.8 + 0.2 * 0.83096 / 3)
        self.assertAlmostEqual(vv5.catch_up_trips(100, food=8000), 0.48 + 0.52 * 0.83096 / 3)
        self.assertEqual(vv5.catch_up_trips(5), 0.0)


@unittest.skipUnless(fe.available(), NO_EXE)
class LiveTripTests(unittest.TestCase):
    def test_a_trip_is_the_same_at_every_speed(self):
        # The update, the walk and the waits never read the speed value (only the pause): frame for frame equal.
        for job in (fe.NONI, fe.FISH):
            got = []
            for speed in (3, 6, 10):
                v = fe.Village(seed=4, speed=speed)
                v.villager(skills={"farming": 89})
                got.append([v.run_trip(job) for _ in range(2)])
            self.assertEqual(got[0], got[1])
            self.assertEqual(got[1], got[2])

    def test_trips_from_the_bin_fall_in_the_measured_span(self):
        for key, job in JOBS.items():
            low, high = vv5.TRIP_SAMPLES[key][2:]
            paid = []
            for start, frames, _, payoffs in _bin_trips(job, 5, seed=14):
                if _at_bin(start) and frames >= 0:
                    self.assertEqual([fe.PAYOFF[c] for c in payoffs], [job])
                    paid.append(frames * SECONDS)
            with self.subTest(source=key):
                self.assertGreaterEqual(len(paid), 4)
                for seconds in paid:
                    self.assertGreaterEqual(seconds, low - 1e-6)
                    self.assertLessEqual(seconds, high + 1e-6)

    @unittest.skipUnless(RELEASE, "release-only (slow): run with VVFP_RELEASE=1")
    def test_the_trip_samples_re_measure_exactly(self):
        for key, (n, mean, low, high) in vv5.TRIP_SAMPLES.items():
            trips = _bin_trips(JOBS[key], n, seed=11)
            paid = [frames * SECONDS for start, frames, _, _ in trips if _at_bin(start) and frames >= 0]
            with self.subTest(source=key):
                self.assertEqual(len(paid), n)
                self.assertEqual(round(statistics.mean(paid), 2), mean)
                self.assertEqual((round(min(paid), 2), round(max(paid), 2)), (low, high))

    @unittest.skipUnless(RELEASE, "release-only (slow): run with VVFP_RELEASE=1")
    def test_one_live_cycle_run_re_measures(self):
        # 8 emulated hours of the scheduler 0x46F070 for a believer dropped on the crops (LIVE_CYCLE, seed 31).
        for (key, farming), count in LIVE_COUNTS_SEED_31.items():
            v = fe.Village(seed=31)
            v.villager(skills={"farming": farming}, player_job=PLAYER[key])
            for _ in range(int(8 * 3600 / SECONDS)):
                v.w32(fe.FOOD, 1000)
                v.w32(v.mgr + fe.NONI_LEFT, 1000)
                v.w32(v.mgr + fe.CROPS_LEFT, 800)
                v.wf(fe.V0 + fe.SKILLS, float(farming))
                v.step_frame()
            got = sum(1 for _, _, c in v.food_log if fe.PAYOFF.get(c) == JOBS[key])
            self.assertEqual(got, count)

    @unittest.skipUnless(fe.IMAGE_SIZES.is_file(), "research/game-data/vv5/image_sizes.json is not present")
    def test_image_sizes_do_not_change_a_trip(self):
        for job in JOBS.values():
            got = []
            for real in (False, True):
                v = fe.Village(seed=5, image_sizes=real)
                v.villager(skills={"farming": 89})
                got.append([v.run_trip(job) for _ in range(2)])
            self.assertEqual(got[0], got[1])

    def test_walk_speeds(self):
        # |vx| + |vy| when the first walk starts, in hundredths of a pixel a frame (0x465D40 truncates each part).
        cases = (({}, 100), ({"likes": (0x26,)}, 300), ({"age": 1000}, 40), ({"age": 999}, 100),
                 ({"dislikes": (0x26,)}, 40), ({"likes": (0x26,), "sick": True}, 100),
                 ({"likes": (0x26,), "age": 1000}, 40), ({"health": 5}, 100))
        for kwargs, speed in cases:
            v = fe.Village(seed=2)
            v.villager(skills={"farming": 89}, **kwargs)
            v.start(fe.NONI)
            v.step_frame()
            step = abs(v.r32(fe.V0 + fe.VX)) + abs(v.r32(fe.V0 + fe.VY))
            with self.subTest(**{k: str(x) for k, x in kwargs.items()}):
                self.assertIn(step, (speed - 1, speed))

    def test_a_failed_farming_check_ends_the_trip_without_food(self):
        for value, paid in ((40 + 33, True), (40 + 34, False)):
            v = fe.Village(seed=6)
            v.villager(skills={"farming": 40})
            v.by_caller[FARMING_CHECK] = value
            frames, _ = v.run_trip(fe.NONI)
            self.assertEqual(frames >= 0, paid, value)

    def test_live_crops_pay_by_the_speed(self):
        for speed, food in ((3, 10), (6, 7), (10, 4)):
            v = fe.Village(seed=7, speed=speed)
            v.villager(skills={"farming": 89})
            seen = len(v.food_log)
            v.run_trip(fe.CROPS)
            self.assertEqual([a for _, a, c in v.food_log[seen:] if c in fe.PAYOFF], [food])


@unittest.skipUnless(fe.available(), NO_EXE)
class CatchUpTests(unittest.TestCase):
    def test_four_turns_a_unit_and_one_meal(self):
        # 10 uncounted units: the meal every unit, 4 job turns for all but the last 2.
        # (The extra roll comes after the 2 eaten: 8,000 or more is checked on what is left.)
        for difficulty, food, extra, eaten in ((1, 1000, 0, 20), (1, 9000, 75, 40), (1, 9000, 76, 20),
                                               (2, 1000, 75, 40), (2, 1000, 76, 20), (0, 9000, 0, 20)):
            v = fe.Village(seed=1, food=food)
            v.w32(v.mgr + fe.DIFFICULTY, difficulty)
            v.villager(age=600, skills={"farming": 60})
            v.w32(fe.V0 + fe.PROC_AGE, 590)
            v.by_caller[EXTRA_MEAL] = extra
            turns = v.life_pass()
            with self.subTest(difficulty=difficulty, food=food, extra=extra):
                self.assertEqual(turns, [fe.V0] * 32)
                self.assertEqual(food - v.r32(fe.FOOD), eaten)
                self.assertEqual(v.r32(fe.V0 + fe.PROC_AGE), 600)

    def test_a_child_eats_without_turns_and_a_heathen_neither(self):
        v = fe.Village(seed=1)
        v.villager(age=279)
        v.w32(fe.V0 + fe.PROC_AGE, 269)
        self.assertEqual(v.life_pass(), [])
        self.assertEqual(v.r32(fe.FOOD), 980)
        v.w32(fe.FOOD, 1000)
        v.villager(age=600)
        v.w32(fe.V0 + fe.PROC_AGE, 590)
        v.w8(fe.V0 + fe.HEATHEN, 1)
        self.assertEqual(v.life_pass(), [])
        self.assertEqual(v.r32(fe.FOOD), 1000)

    def _turn(self, player_job: int, farming: int = 100, rolls: dict | None = None, speed: int = 6,
              projects=(fe.GRANARY, fe.HUNGRY_TOTEM, fe.HYDRO_FARM, fe.LAKE), noni: int = 1000):
        v = fe.Village(seed=3, speed=speed, projects=projects, noni=noni)
        v.villager(skills={"farming": farming}, player_job=player_job)
        v.by_caller.update({KEPT_FIRST: 99, KEPT_SECOND: 99, FARMING_CHECK: 0, **(rolls or {})})
        seen = len(v.food_log)
        v.catch_up_turn()
        return [(fe.PAYOFF.get(c, c), a) for _, a, c in v.food_log[seen:]]

    def test_one_farming_turn_is_one_trip(self):
        self.assertEqual(self._turn(fe.PLAYER_NONI), [(fe.NONI, 10)])
        self.assertEqual(self._turn(fe.PLAYER_NONI, noni=150), [(fe.NONI, 2)], "at least 2")
        self.assertEqual(self._turn(fe.PLAYER_FISH), [(fe.FISH, 4)])
        for speed in (3, 6, 10):
            self.assertEqual(self._turn(fe.PLAYER_CROPS, speed=speed), [(fe.CROPS, 7)], speed)

    def test_the_farming_check(self):
        self.assertEqual(self._turn(fe.PLAYER_NONI, 40, {FARMING_CHECK: 73}), [(fe.NONI, 10)])
        self.assertEqual(self._turn(fe.PLAYER_NONI, 40, {FARMING_CHECK: 74}), [])

    def test_the_hungry_totem_gates_only_the_dispatcher(self):
        no_totem = (fe.GRANARY, fe.HYDRO_FARM, fe.LAKE)
        free = {CHOOSER_BLANK: 99, CHOOSER_SKILLS[0]: 99, CHOOSER_LAST: 0}
        # A free farmer: the dispatcher offers 2 sources (rand(2)): crops then the lake, never the noni.
        self.assertEqual(self._turn(0, rolls={**free, SOURCE_PICK: 0}, projects=no_totem), [(fe.CROPS, 7)])
        self.assertEqual(self._turn(0, rolls={**free, SOURCE_PICK: 1}, projects=no_totem), [(fe.FISH, 4)])
        self.assertEqual(self._turn(0, rolls={**free, SOURCE_PICK: 0}), [(fe.NONI, 10)], "with the totem")
        # Dropped on the noni bushes: picked without the totem.
        self.assertEqual(self._turn(fe.PLAYER_NONI, projects=no_totem), [(fe.NONI, 10)])
        # Nothing at all before the granary.
        self.assertEqual(self._turn(fe.PLAYER_NONI, projects=(fe.HUNGRY_TOTEM, fe.LAKE)), [])
        self.assertEqual(self._turn(0, rolls=free, projects=(fe.HUNGRY_TOTEM, fe.LAKE)), [])

    def test_the_chooser_picks_farming_0_83096_of_turns(self):
        # Every class of each roll the chooser makes, weighted by its share of 100 (Farming 100, the others 10).
        sites = (CHOOSER_BLANK, *CHOOSER_SKILLS, CHOOSER_PREF)
        classes = ((14, 15, 99, 85),) + ((0, 16, 99, 84),) * 6 + ((0, 86, 99, 14),)
        v = fe.Village(seed=3)
        share = Fraction(0)
        for pick in product((0, 1), repeat=len(sites)):
            weight = Fraction(1)
            for site, (low, low_w, high, high_w), which in zip(sites, classes, pick):
                v.by_caller[site] = (low, high)[which]
                weight *= Fraction((low_w, high_w)[which], 100)
            v.by_caller[CHOOSER_LAST] = 0
            v.villager(skills={"farming": 100})
            if v.call(fe.CHOOSER, fe.V0) == 0:
                share += weight
        self.assertEqual(share, Fraction(83096, 100000))

    def test_the_player_job_is_kept_80_in_100(self):
        for food, kept in ((1000, Fraction(80, 100)), (8000, Fraction(48, 100))):
            v = fe.Village(seed=3, food=food)
            share = Fraction(0)
            for first, second in product(((19, 20), (99, 80)), ((39, 40), (99, 60))):
                v.villager(skills={"farming": 100}, player_job=fe.PLAYER_CROPS)
                v.by_caller.update({KEPT_FIRST: first[0], KEPT_SECOND: second[0]})
                if v.call(fe.PLAYER_JOB, fe.V0) & 0xFF and v.r32(fe.V0 + fe.BEHAVIOUR) == fe.CROPS:
                    share += Fraction(first[1], 100) * Fraction(second[1], 100)
            self.assertEqual(share, kept, food)


if __name__ == "__main__":
    unittest.main()
