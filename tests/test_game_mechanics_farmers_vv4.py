"""The Tree of Life (VV4): the farmers' trips and catch-up job turns, re-measured from the stock exe.

Pins src/vv_game_mechanics_farmers_vv4.py.  Everything that needs the stock executable runs its own code in
unicorn through tests/farmers_emulation_vv4.py (what is stubbed there: rand, the clock, the two singleton getters
and the scene's mouse hotspot list) over the game's own map, research/game-data/vv4/cmap.dat (copied from the
game's Assets folder; never committed).  Without the executable or the map the emulation tests skip (CI).

The full re-measurement of TRIP_SAMPLES (1,200 trips, a few minutes) and six of LIVE_CYCLE's 36 runs of 24
emulated hours (about 7 minutes each) run only with VVFP_RELEASE=1 (every run: also VVFP_FARMERS_CYCLE=all).
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

import vv_game_mechanics_farmers as farmers  # noqa: E402
import vv_game_mechanics_farmers_vv4 as vv4  # noqa: E402

try:
    import farmers_emulation_vv4 as fe  # noqa: E402
    HAVE = fe.STOCK.is_file() and fe.CMAP.is_file()
except ImportError:                  # unicorn or pefile missing
    fe, HAVE = None, False

NO_EXE = "the stock Tree of Life executable or research/game-data/vv4/cmap.dat is not present"
RELEASE = os.environ.get("VVFP_RELEASE") == "1"
SECONDS = 0.033
KEY_ACTION = {"blackberry picks": 99, "fish in the net": 129, "fruit stomps": 100}
KEY_REWARD = {"blackberry picks": 13, "fish in the net": 16, "fruit stomps": 15}

# rand(N) call sites, by the address the call returns to.
CHECK = 0x462B1A                     # the skill check 0x462A80, Farming: passes on rand(100) <= Farming + 33
CHOOSER_BLANK = 0x461CD1             # rand(100) < 15: no job (a villager who does not like work)
CHOOSER_SKILLS = (0x461D25, 0x461D4A, 0x461D7F, 0x461DAA, 0x461E06)  # Farming, Parenting, Building, Healing, Research
CHOOSER_PREF, CHOOSER_LAST = 0x461E47, 0x461E75   # preference wins on <= 85; the job on rand(100) < skill + 40
GATE_1, GATE_2 = 0x4634F4, 0x463503  # the player-task gate 0x4634D0
PICK = 0x463A68                      # the dispatcher's rand(n) over the sources it offers
FISH_SIDE = 0x43320B                 # rand(100) < 50: the 2-point walk to the nets, else the 3-point one
GOLDEN = 0x43336B                    # rand(100) < 2 x scales + 1 (and a scale found): the Golden Fish
FRUITWELLS = 0x468AA1                # the catch-up bonus: on rand(100) < Farming - 25
MEAL_LOW, EXTRA_MEAL = 0x4684A3, 0x468503   # at <= 500 food a meal on rand(100) < 50; 2 more on rand(100) <= 75
SCHEDULER = 0x465886                 # the scheduler 0x465840: rand(100) <= 65 does nothing

FARMER = {"farming": 100}


def _farmer(**kw):
    return {**FARMER, **kw}


class ModuleTests(unittest.TestCase):
    """The module's own consistency; no executable needed."""

    def test_the_trips_pair_with_the_page(self):
        turns, trips = farmers.game_trips(4)
        self.assertEqual(turns, 4)
        self.assertEqual([t.key for t in trips], ["blackberry picks", "fish in the net", "fruit stomps"])
        page = (ROOT / "src" / "vv_game_mechanics_vv4.py").read_text(encoding="utf-8")
        for trip in trips:
            self.assertIn(f'("{trip.key}", ', page)
            self.assertEqual(trip.success_offset, 34)
            self.assertIsNone(trip.live_food, "the page's own food a trip applies")
            self.assertIsNone(trip.catch_up_food)
            self.assertEqual(set(trip.live_seconds), {3, 6, 10})
            self.assertEqual(len(set(trip.live_seconds.values())), 1, "the speed does not change a trip")
            _, mean, lo, hi = vv4.TRIP_SAMPLES[trip.key]
            self.assertEqual((mean, (lo, hi)), (trip.live_seconds[6], trip.live_span[6]))
            self.assertLess(lo, mean)
            self.assertLess(mean, hi)
            self.assertEqual(set(vv4.LIVE_CYCLE[trip.key]), {100, 50, 20})
        by_key = {t.key: t for t in trips}
        self.assertAlmostEqual(by_key["blackberry picks"].catch_up_trips_per_turn, vv4.task_trips_per_turn(100))
        self.assertAlmostEqual(by_key["fish in the net"].catch_up_trips_per_turn, vv4.task_trips_per_turn(100))
        self.assertEqual(by_key["fruit stomps"].catch_up_trips_per_turn, 0.0)

    def test_the_shares(self):
        self.assertAlmostEqual(vv4.FARMING_CHOSEN, 0.85 * (0.84 + 0.16 * 0.86), places=12)
        self.assertAlmostEqual(vv4.farming_chosen(100), 0.83096)
        self.assertAlmostEqual(vv4.farming_chosen(40), 0.83096 * 0.8)
        self.assertEqual(vv4.farming_chosen(5), 0.0)
        self.assertAlmostEqual(vv4.task_trips_per_turn(100), 0.8 + 0.2 * 0.83096 / 2)
        self.assertAlmostEqual(vv4.task_trips_per_turn(100, nets=False), 0.8 + 0.2 * 0.83096)
        self.assertAlmostEqual(vv4.task_trips_per_turn(100, food=8000), 0.48 + 0.52 * 0.83096 / 2)
        self.assertEqual(vv4.FRUITWELLS["food"], {1: 5, 2: 7, 3: 10})
        self.assertAlmostEqual(vv4.fruitwells_food_unit(100), 3.75)
        self.assertEqual(vv4.fruitwells_food_unit(25), 0.0)

    def test_live_cycle_is_the_pooled_runs(self):
        self.assertEqual(vv4.LIVE_CYCLE, {"blackberry picks": {100: 112.4, 50: 116.6, 20: 126.6},
                                          "fish in the net": {100: 86.0, 50: 94.7, 20: 113.6},
                                          "fruit stomps": {100: 168.2, 50: 175.8, 20: 192.6}})
        for key, by_skill in vv4.LIVE_CYCLE_COUNTS.items():
            for farming, counts in by_skill.items():
                halves = [2 * vv4._RUN_SECONDS / sum(counts[:2]), 2 * vv4._RUN_SECONDS / sum(counts[2:])]
                with self.subTest(source=key, farming=farming):
                    self.assertLess(abs(halves[0] - halves[1]) / vv4.LIVE_CYCLE[key][farming], 0.017)


@unittest.skipUnless(HAVE, NO_EXE)
class LiveTripTests(unittest.TestCase):
    def test_a_trip_is_the_same_at_every_speed(self):
        # Nothing in the update 0x465BD0, the walk or the step timers reads the speed (the scene stops calling the
        # villagers while it is 999, paused, 0x43FF8A): frame for frame equal.
        for action in KEY_ACTION.values():
            got = []
            for speed in (3, 6, 10):
                v = fe.Village(seed=4, speed=speed)
                v.villager(skills=_farmer(farming=89))
                got.append([v.run_trip(action)[:2] for _ in range(2)])
            with self.subTest(action=action):
                self.assertEqual(got[0], got[1])
                self.assertEqual(got[1], got[2])

    def test_trips_from_the_bin_fall_in_the_measured_span(self):
        for trip in vv4.TRIPS:
            low, high = trip.live_span[6]
            trips = fe.bin_trips(KEY_ACTION[trip.key], 4, seed=14)
            with self.subTest(source=trip.key):
                for start, frames, _, rewards in trips:
                    self.assertEqual(rewards, [KEY_REWARD[trip.key]])
                    self.assertGreaterEqual(frames * SECONDS, low - 1e-6)
                    self.assertLessEqual(frames * SECONDS, high + 1e-6)

    @unittest.skipUnless(RELEASE, "release-only (slow): run with VVFP_RELEASE=1")
    def test_the_trip_samples_re_measure_exactly(self):
        for key, (n, mean, low, high) in vv4.TRIP_SAMPLES.items():
            trips = fe.bin_trips(KEY_ACTION[key], 400, seed=11, farming=89)
            paid = [frames * SECONDS for _, frames, _, rewards in trips if rewards == [KEY_REWARD[key]]]
            with self.subTest(source=key):
                self.assertEqual(len(paid), n)
                self.assertEqual(round(statistics.mean(paid), 2), mean)
                self.assertEqual((round(min(paid), 2), round(max(paid), 2)), (low, high))

    def test_walk_speeds(self):
        # |vx| + |vy| a frame, in hundredths of a pixel (0x45E6F0 truncates each part): 100, 300 for an adult who
        # likes running (0x45E2EE) and for a child who does not dislike it, 40 for one who dislikes it or an elder
        # (age units >= 840 + 160 x Medicine, 0x465EB0).
        cases = (({}, 100), ({"likes": (0x26,)}, 300), ({"dislikes": (0x26,)}, 40), ({"age": 1000}, 40),
                 ({"age": 999}, 100), ({"age": 200}, 300))
        for kwargs, speed in cases:
            v = fe.Village(seed=2)
            r = v.villager(skills=_farmer(farming=89), **kwargs)
            v.start(99)
            v.step_frame()
            with self.subTest(**kwargs):
                self.assertIn(abs(v.r32(r + fe.VX)) + abs(v.r32(r + fe.VY)), (speed - 1, speed))

    def test_a_failed_farming_check_ends_the_trip_without_food(self):
        for action in KEY_ACTION.values():
            for value, paid in ((73, True), (74, False)):
                v = fe.Village(seed=6)
                v.villager(skills=_farmer(farming=40))
                v.by_caller[CHECK] = value
                frames, _, _ = v.run_trip(action)
                with self.subTest(action=action, roll=value):
                    self.assertEqual(frames >= 0, paid)

    def test_the_tutorial_passes_a_failed_check(self):
        # Before its "Great job!" tip 0x2B2 has been seen, a failed Farming check passes once "Darn!" (0x2D2) has
        # (the tips' seen flags: the setter 0x44B970; the display marks a shown tip at 0x44C0CE).
        for darn, great, paid in ((False, False, False), (True, False, True), (True, True, False)):
            v = fe.Village(seed=6, tutorial_done=great)
            if darn:
                v.call(fe.TIP_SEEN, fe.TIPS, fe.TUTORIAL_FAIL_TIP)
            v.villager(skills=_farmer(farming=0))
            v.by_caller[CHECK] = 99
            with self.subTest(darn=darn, great=great):
                self.assertEqual(v.run_trip(99)[0] >= 0, paid)

    def test_the_fishing_walk_needs_the_piers(self):
        # Without Fishing Nets the piers (areas 0x60 / 0x61) stay blocked and the 3-point walk gives up there.
        v = fe.Village(seed=8, solved=(6,))
        v.villager(skills=_farmer(farming=89))
        v.by_caller[FISH_SIDE] = 50
        paid, _, _ = v.run_trip(129)
        self.assertEqual(paid, -1)
        for side in (49, 50):
            v = fe.Village(seed=8)
            v.villager(skills=_farmer(farming=89))
            v.by_caller[FISH_SIDE] = side
            self.assertGreater(v.run_trip(129)[0], 0)

    def test_a_golden_fish(self):
        # The scale count 0x413B90 (the collection 0x4CC838) is answered with 3 here: rand(100) < 7.
        for roll, event in ((6, 17), (7, 16)):
            v = fe.Village(seed=8)
            v.villager(skills=_farmer(farming=89))
            v.uc.hook_add(fe.UC_HOOK_CODE, lambda *_, v=v: v._ret(3, 0x10), begin=0x413B90, end=0x413B90)
            v.by_caller[GOLDEN] = roll
            food = v.food()
            _, _, rewards = v.run_trip(129)
            with self.subTest(roll=roll):
                self.assertEqual(rewards, [event])
                self.assertEqual(v.food() - food, 8 if event == 17 else 4)

    def test_the_scheduler_waits_two_in_three(self):
        # An idle villager asks the scheduler once each whole real-life second (0x465C53..0x465CC8); 66 in 100
        # it does nothing (0x465889).
        for roll, works in ((65, False), (66, True)):
            v = fe.Village(seed=3)
            v.villager(skills=_farmer(), task=fe.TASK_BERRIES, preference=0)
            v.by_caller.update({SCHEDULER: roll, GATE_1: 99, GATE_2: 99})
            for _ in range(70):
                v.step_frame()
            with self.subTest(roll=roll):
                self.assertEqual(v.r32(v.rec(0) + fe.ACTION) == 99, works)


@unittest.skipUnless(HAVE, NO_EXE)
class CatchUpTests(unittest.TestCase):
    def _turn(self, task=0, farming=100, rolls=None, berries=1000, solved=(6, 0xB), levels=(1,) * 8):
        v = fe.Village(seed=3, berries=berries, solved=solved, levels=levels)
        v.villager(skills=_farmer(farming=farming), task=task, preference=0)
        v.by_caller.update({CHECK: 0, GATE_1: 99, GATE_2: 99, **(rolls or {})})
        food = v.food()
        v.catch_up_turn()
        return [e for _, e in v.events if e in (13, 15, 16, 17)], v.food() - food

    def test_one_turn_is_one_trip_paying_as_live(self):
        self.assertEqual(self._turn(fe.TASK_BERRIES), ([13], 10))
        self.assertEqual(self._turn(fe.TASK_BERRIES, berries=150), ([13], 2), "at least 2")
        self.assertEqual(self._turn(fe.TASK_BERRIES, berries=3), ([], 0), "the task ends at 3 berries or less")
        self.assertEqual(self._turn(fe.TASK_FISH), ([16], 4))
        self.assertEqual(self._turn(fe.TASK_FISH, levels=(1, 1, 1, 1, 3, 1, 1, 1)), ([16], 8), "Food Mastery 3")
        # The task 2 (only in an edited save) reaches the fruit even while catching up: 3 food.
        self.assertEqual(self._turn(2), ([15], 3))

    def test_the_farming_check(self):
        self.assertEqual(self._turn(fe.TASK_BERRIES, 40, {CHECK: 73}), ([13], 10))
        self.assertEqual(self._turn(fe.TASK_BERRIES, 40, {CHECK: 74}), ([], 0))

    def test_the_task_gate(self):
        # A player-given task is done unless rand(100) < 20, or rand(100) < 40 with 8,000 food or more (or a
        # dislike of work); otherwise the job turn falls back to the chooser.
        no_job = {CHOOSER_BLANK: 0}
        self.assertEqual(self._turn(fe.TASK_BERRIES, rolls={GATE_1: 19, **no_job}), ([], 0))
        self.assertEqual(self._turn(fe.TASK_BERRIES, rolls={GATE_1: 20, GATE_2: 0, **no_job}), ([13], 10))
        v = fe.Village(seed=3, food=8000)
        v.villager(skills=_farmer(), task=fe.TASK_BERRIES, preference=0)
        v.by_caller.update({CHECK: 0, GATE_1: 20, GATE_2: 39, **no_job})
        v.catch_up_turn()
        self.assertEqual([e for _, e in v.events if e == 13], [])

    def test_no_fruit_while_catching_up(self):
        # The dispatcher offers the fruit only when not catching up (0x463A30): two sources, not three.
        from unicorn.x86_const import UC_X86_REG_EDI
        for catch_up, offered in ((True, 2), (False, 3)):
            seen = []
            v = fe.Village(seed=3)
            r = v.villager(skills=_farmer(), preference=0)
            v.uc.hook_add(fe.UC_HOOK_CODE, lambda uc, *_, seen=seen: seen.append(uc.reg_read(UC_X86_REG_EDI)),
                          begin=0x463A62, end=0x463A62)
            v.w8(fe.GAME + fe.G_CATCHUP, 1 if catch_up else 0)
            v.call(0x4639B0, r, 0)
            with self.subTest(catch_up=catch_up):
                self.assertEqual(seen, [offered])

    def test_the_chooser_picks_farming_0_83096_of_turns(self):
        share = Fraction(0)
        sites = (CHOOSER_BLANK, *CHOOSER_SKILLS, CHOOSER_PREF)
        classes = ((0, 15, 99, 85),) + ((0, 16, 99, 84),) * 5 + ((0, 86, 99, 14),)
        v = fe.Village(seed=3, solved=(6,))
        for pick in product((0, 1), repeat=len(sites)):
            weight = Fraction(1)
            for site, (low, low_w, high, high_w), which in zip(sites, classes, pick):
                v.by_caller[site] = (low, high)[which]
                weight *= Fraction((low_w, high_w)[which], 100)
            v.by_caller.update({CHOOSER_LAST: 0, CHECK: 0})
            v.w32(fe.GAME + fe.G_BERRIES, 1000)
            v.villager(skills=_farmer(), preference=0)
            seen = len(v.events)
            v.catch_up_turn()
            if [e for _, e in v.events[seen:]] == [13]:
                share += weight
        self.assertEqual(share, Fraction(83096, 100000))

    def test_the_life_tick(self):
        # 10 uncounted units: 4 job turns for each but the last 2, a meal of 2 each unit, the Fruitwells bonus
        # (5 food) on rand(100) < Farming - 25 after each unit's turns.
        for kw, rolls, turns, eaten, bonus in (
                ({}, {FRUITWELLS: 99}, 32, 20, 0),
                ({}, {FRUITWELLS: 34}, 32, 20 - 40, 8),
                ({"health": 10}, {FRUITWELLS: 34}, 32, 20 - 40, 8),
                ({"task": 2}, {FRUITWELLS: 99}, 32, 20 - 40, 8)):
            v = fe.Village(seed=1)
            r = v.villager(skills=_farmer(farming=60), preference=0, **kw)
            v.w32(r + fe.PROC_AGE, 490)
            v.by_caller.update(rolls)
            calls = v.life_tick()
            with self.subTest(**kw, **{hex(k): x for k, x in rolls.items()}):
                self.assertEqual(len(calls), turns)
                self.assertEqual(1000 - v.food(), eaten)
                self.assertEqual(sum(1 for _, a in v.food_log if a == 5), bonus)
                self.assertEqual(v.r32(r + fe.PROC_AGE), 500)

    def test_the_fruitwells_bonus_and_food_mastery(self):
        for level, food in ((1, 5), (2, 7), (3, 10)):
            v = fe.Village(seed=1, levels=(1, 1, 1, 1, level, 1, 1, 1))
            r = v.villager(skills=_farmer(farming=60), preference=0)
            v.w32(r + fe.PROC_AGE, 497)
            v.by_caller.update({FRUITWELLS: 0, EXTRA_MEAL: 99})
            v.life_tick()
            with self.subTest(level=level):
                self.assertEqual(v.food() - 1000, food - 3 * 2)

    def test_no_bonus_without_the_fruitwells_or_for_a_child(self):
        v = fe.Village(seed=1, solved=(0xB,))
        r = v.villager(skills=_farmer(farming=60), preference=0)
        v.w32(r + fe.PROC_AGE, 490)
        v.by_caller[FRUITWELLS] = 0
        v.life_tick()
        self.assertNotIn(5, [a for _, a in v.food_log])
        v = fe.Village(seed=1)
        r = v.villager(skills=_farmer(farming=60), preference=0, age=279)
        v.w32(r + fe.PROC_AGE, 269)
        v.by_caller[FRUITWELLS] = 0
        self.assertEqual(v.life_tick(), [])
        self.assertNotIn(5, [a for _, a in v.food_log])

    def test_meals(self):
        for food, difficulty, rolls, eaten in ((1000, 1, {}, 20), (9000, 1, {EXTRA_MEAL: 75}, 40),
                                               (9000, 1, {EXTRA_MEAL: 76}, 20), (1000, 2, {EXTRA_MEAL: 75}, 40),
                                               (9000, 0, {EXTRA_MEAL: 0}, 20), (500, 1, {MEAL_LOW: 49}, 20),
                                               (500, 1, {MEAL_LOW: 50}, 0)):
            v = fe.Village(seed=1, food=food, difficulty=difficulty, solved=(0xB,))
            r = v.villager(skills=_farmer(farming=60), preference=0)
            v.w32(r + fe.PROC_AGE, 490)
            v.by_caller.update(rolls)
            v.life_tick()
            with self.subTest(food=food, difficulty=difficulty, rolls=rolls):
                self.assertEqual(food - v.food(), eaten)


@unittest.skipUnless(HAVE and RELEASE, "release-only (slow): run with VVFP_RELEASE=1")
class LiveCycleTests(unittest.TestCase):
    """LIVE_CYCLE pools 36 runs of 24 emulated hours (about 7 minutes each on one core); this re-runs the seed-1 run
    of each source at Farming 100 and 20 and checks its count exactly (set VVFP_FARMERS_CYCLE=all for every run)."""

    def test_live_cycle_counts_re_measure(self):
        every = os.environ.get("VVFP_FARMERS_CYCLE") == "all"
        for key, (task, berries, solved) in vv4.CYCLE_SETUP.items():
            for farming, counts in vv4.LIVE_CYCLE_COUNTS[key].items():
                if not every and farming == 50:
                    continue
                for seed, count in zip(vv4.CYCLE_SEEDS, counts, strict=True):
                    if not every and seed != 1:
                        continue
                    seconds, got = fe.scheduler(task, farming, vv4.CYCLE_HOURS, seed=seed, berries=berries,
                                                solved=solved)
                    with self.subTest(source=key, farming=farming, seed=seed):
                        self.assertAlmostEqual(seconds, vv4._RUN_SECONDS, places=3)
                        self.assertEqual(got.get(KEY_REWARD[key], 0), count)


if __name__ == "__main__":
    unittest.main()
