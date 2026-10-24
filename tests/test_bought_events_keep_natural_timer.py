"""Bought island events do not change when the game's own island events come.

The owner (2026-10-23): "Do buying custom island events affect the timing of
naturally spawned ones?  I would prefer they don't affect timing."

Each game keeps one island-event timer.  Every purchase that delivers an
island event writes it (the Origins Island Event, The Tree of Life's and New
Believers' Barrel of Babies, and the Story / Cheat Upgrades' arms), and the
game's own trigger then wrote it again -- 8 to 23 hours from the bought
event, or 30 minutes after a village's first -- so every natural event came
later than it would have.  native/shared/island_timer_keep.h keeps the time
the purchase overwrote and puts it back right after the trigger's own write.

Everything here runs the shipped executable bytes (each game as the patcher
renders it, in all three population modes) with the test build of the
keeper (tests/test_dlls/VVFP Island Event Timer.test.dll, the same header and
sites the Origins companions compile) in the emulator: the purchases' own
code writes the timer, the game's own trigger runs from its due check to the
moment it has counted the event, and only the game's helpers it calls on the
way (its clock, random numbers, population count, villager draw, sound) are
stand-ins that pop exactly what the real routines pop.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from test_story_cheat_upgrades import (  # noqa: E402
    GAMES,
    HAVE_EMULATOR,
    MODES,
    have_stock,
    render,
)

if HAVE_EMULATOR:
    from story_emulator import STACK_TOP, Process  # noqa: E402

DLL = ROOT / "tests" / "test_dlls" / "VVFP Island Event Timer.test.dll"
CLOCK = 1_700_000_000
HOUR = 3600


def emulated(cls):
    return unittest.skipUnless(HAVE_EMULATOR, "capstone/unicorn/pefile not installed")(
        unittest.skipUnless(DLL.is_file(), "test builds are not in the release source archive (tests/test_dlls)")(cls))


# Per game: the timer's offset in its object, the counter (Island Events
# Seen: an offset in the same object, or a global), the clock and random
# routines, the trigger's due check and its not-due target, and the
# routines the trigger calls with what they pop.
SPEC = {
    "vv1": dict(size=0xB000, timer=0xA300, counter=("obj", 0x9E40), clock=0x402F70, rand=0x402F10,
                trigger=0x4237BD, skip=0x423ABE, obj_reg="edi", hours=(12, 23)),
    "vv2": dict(size=0x31000, timer=0x2EAE0, counter=("obj", 0x2E51C), clock=0x403200, rand=0x4031A0,
                trigger=0x42EECD, skip=0x42F1D4, obj_reg="edi", hours=(10, 19)),
    "vv3": dict(size=0x13000, timer=0x12EF4, counter=("abs", 0x5824C4), clock=0x403330, rand=0x4032D0,
                trigger=0x468732, skip=0x4688DF, obj_reg="ecx", hours=(8, 15)),
    "vv4": dict(size=0x18000, timer=0x170E0, counter=("abs", 0x4D6E04), clock=0x403750, rand=0x4036D0,
                trigger=0x43FA3D, skip=0x43FC0E, obj_reg="ecx", hours=(8, 15)),
    "vv5": dict(size=0x18000, timer=0x17D3C, counter=("abs", 0x51D37C), clock=0x4036E0, rand=0x403660,
                trigger=0x4426EA, skip=0x44285F, obj_reg="ecx", hours=(8, 15)),
}

# Each trigger path: the random answers that take it, whether it needs the
# counter at 0, and where the trigger has just counted the event (the stop).
PATHS = {
    "vv1": {"crate": ([99, 99, 99], False, 0x4238B5), "island": ([99, 0], False, 0x42393D),
            "visitor": ([0], False, 0x423A93), "first": ([0], True, 0x423A93)},
    "vv2": {"sack": ([99, 99, 99], False, 0x42EFC5), "single": ([99, 0], False, 0x42F04D),
            "two_choice": ([0], False, 0x42F1A3), "first": ([0], True, 0x42F1A3)},
    "vv3": {"hours_a": ([99, 99, 99], False, 0x468870), "hours_b": ([99, 0], False, 0x468870),
            "hours_c": ([0], False, 0x468870), "first": ([0], True, 0x468870)},
    "vv4": {"hours_a": ([99, 99, 99], False, 0x43FBDD), "hours_b": ([99, 0], False, 0x43FBDD),
            "hours_c": ([0], False, 0x43FBDD), "first": ([0], True, 0x43FBDD)},
    "vv5": {"hours_a": ([99, 99, 99], False, 0x442850), "hours_b": ([99, 0], False, 0x442850),
            "hours_c": ([0], False, 0x442850), "first": ([0], True, 0x442850)},
}

# Every site the keeper writes (native/shared/island_timer_vvN.inc), in order:
# the trigger's due check, the trigger's own writes, the purchases' writes.
KEEPER_SITES = {
    "vv1": (0x4237BD, 0x423891, 0x42391A, 0x423A37, 0x423A6F, 0x456B47),
    "vv2": (0x42EECD, 0x42EFA1, 0x42F02A, 0x42F147, 0x42F17F, 0x494824),
    "vv3": (0x468732, 0x468809, 0x468842, 0x468899, 0x4688D4, 0x6DF34A),
    "vv4": (0x43FA3D, 0x43FB00, 0x43FB3E, 0x43FB9D, 0x43FBD0, 0x4897B8, 0x4897E6, 0x728A6B),
    "vv5": (0x4426EA, 0x4427CA, 0x442801, 0x442834, 0x7CCCFC, 0x7CEE63),
}

ROSTER = [0x1111 * (i + 1) for i in range(12)] + [0] * 244
OTHER_ROSTER = [0x7777 * (i + 1) for i in range(12)] + [0] * 244


class Village:
    """One game's process: the executable, the keeper installed, a village."""

    def __init__(self, game: str, mode: str = "collection_progression", install: bool = True):
        self.game = game
        self.n = int(game[2:])
        self.spec = SPEC[game]
        self.proc = Process(render(game, mode), DLL)
        p = self.proc
        self.obj = p.alloc(self.spec["size"])
        self.now = CLOCK
        p.stub(self.spec["clock"], lambda q: (self.now, 0))
        self.rands: list[int] = []
        self.rand_calls: list[int] = []

        def rand(q):
            self.rand_calls.append(q.arg(0))
            value = self.rands.pop(0) if self.rands else 0
            return min(value, q.arg(0) - 1), 0
        p.stub(self.spec["rand"], rand)
        self.roster_buf = p.alloc(4 * 256)
        self.village(1, ROSTER)
        if install:
            self.installed = p.export("ItkProbeInstall", self.n)

    # ---- the village ---------------------------------------------------
    def village(self, slot: int, roster: list[int]) -> None:
        self.proc.write(self.roster_buf, struct.pack("<256I", *roster))
        self.proc.export("ItkProbeVillage", slot, self.roster_buf)

    @property
    def field(self) -> int:
        return self.obj + self.spec["timer"]

    def timer(self) -> int:
        return self.proc.u32(self.field)

    def set_timer(self, value: int) -> None:
        self.proc.put32(self.field, value)

    def counter_va(self) -> int:
        kind, at = self.spec["counter"]
        return self.obj + at if kind == "obj" else at

    def counter(self) -> int:
        return self.proc.u32(self.counter_va())

    def set_counter(self, value: int) -> None:
        self.proc.put32(self.counter_va(), value)

    def state(self) -> list[int]:
        out = self.proc.alloc(32)
        self.proc.export("ItkProbeState", out)
        return list(struct.unpack("<6I", self.proc.read(out, 24)))

    # ---- the purchases: each game's own code ----------------------------
    def buy(self, what: str = "island") -> None:
        p, g = self.proc, self.game
        p.set_reg("esp", STACK_TOP - 0x2000)
        if g == "vv1":
            p.set_reg("edi", self.obj)
            p.run(0x456B3B, 0x456B4D)
        elif g == "vv2":
            p.set_reg("edi", self.obj)
            p.run(0x494818, 0x49482A)
        elif g == "vv3":
            p.call(0x6DF340, [], ecx=self.obj)
        elif g == "vv4":
            p.stub(0x41FE70, lambda q: (self.obj, 0))
            if what == "island":
                p.run(0x4897A7, 0x4897CA)
            elif what == "barrel":
                p.run(0x4897CC, 0x4897F0)
            else:                               # the re-arm after a barrel went ahead
                p.write(0x728B08, b"\x01")
                p.call(0x728A50, [])
        else:
            if what == "island":
                p.set_reg("edi", self.obj)
                p.run(0x7CCCFC, 0x7CCD16)
            else:
                p.stub(0x425950, lambda q: (self.obj, 0))
                p.put32(0x51D388, 8)
                p.run(0x7CEE00, 0x7CEE6E)

    def story_arm(self, value: int) -> None:
        """A Story / Cheat Upgrades arm: its host call, then its own write."""
        self.proc.export("ItkProbeStoryArming", self.field, value)
        self.set_timer(value)

    # ---- the trigger: the game's own code --------------------------------
    def _helpers(self) -> int:
        """Stand-ins for the routines the trigger calls before its rolls;
        returns the owner object (esi)."""
        p, g = self.proc, self.game
        owner = p.alloc(0x100)
        p.put32(owner + 0x10, self.obj)
        record = p.alloc(0x4000)
        if g == "vv1":
            p.put32(owner + 0x20, record)
            p.put32(owner + 0x18, p.alloc(0x100))
            p.stub(0x41CF90, lambda q: (1, 0))          # living count
            p.stub(0x43BCD0, lambda q: (0, 4))          # an adult's index (push 1)
            p.stub(0x41D110, lambda q: (1, 0))
            p.stub(0x431470, lambda q: (0, 4))          # the sound (push 0xD)
        elif g == "vv2":
            p.put32(owner + 0x20, record)
            p.put32(owner + 0x18, p.alloc(0x100))
            p.stub(0x425860, lambda q: (1, 0))
            p.stub(0x44BAE0, lambda q: (0, 4))
            p.stub(0x426110, lambda q: (1, 0))
            p.stub(0x43F010, lambda q: (0, 4))
        elif g == "vv3":
            p.stub(0x45E8F0, lambda q: (1, 0))
            p.stub(0x45C9D0, lambda q: (0, 4))
            p.stub(0x402200, lambda q: (1, 0))
            p.stub(0x45EE60, lambda q: (1, 4))
            p.stub(0x45C840, lambda q: (record, 4))
            p.stub(0x424110, lambda q: (0, 4))
        elif g == "vv4":
            p.stub(0x467610, lambda q: (1, 0))
            p.stub(0x4679B0, lambda q: (record, 0x28))  # ten arguments
            p.stub(0x416EB0, lambda q: (1, 0))
            p.stub(0x448E10, lambda q: (0, 4))
        else:
            p.stub(0x4713F0, lambda q: (1, 0))
            p.put32(0x51D5A4, 0xFFFFFFFF)               # no barrel under way
            p.stub(0x471870, lambda q: (record, 0x38))  # fourteen arguments
            p.stub(0x417650, lambda q: (1, 0))
            p.stub(0x44C440, lambda q: (0, 4))
        return owner

    def tick(self, path: str | None = None) -> bool:
        """One frame of the trigger at the current clock.  Returns whether
        an event was made (the run reached the counted event)."""
        p = self.proc
        owner = self._helpers()
        p.set_reg("esp", STACK_TOP - 0x8000)
        p.set_reg("esi", owner)
        p.set_reg("ebx", 0)
        p.set_reg("eax", self.now)
        p.set_reg(self.spec["obj_reg"], self.obj)
        if self.timer() > self.now:
            p.run(self.spec["trigger"], self.spec["skip"])
            return False
        rolls, needs_first, stop = PATHS[self.game][path or self.default_path()]
        if needs_first:
            self.set_counter(0)
        elif self.counter() == 0:
            self.set_counter(5)
        self.rands = list(rolls)
        p.run(self.spec["trigger"], stop)
        return True

    def default_path(self) -> str:
        return [k for k, v in PATHS[self.game].items() if not v[1]][1]

    def hours(self) -> range:
        low, high = self.spec["hours"]
        return range(self.now + low * HOUR, self.now + high * HOUR + 1, HOUR)


@emulated
class TheSitesAreTheGamesOwn(unittest.TestCase):
    def test_the_sites_are_the_listed_ones(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                v = Village(game, install=False)
                buf = v.proc.alloc(8)
                got = []
                while v.proc.export("ItkProbeSite", v.n, len(got), buf):
                    got.append(v.proc.u32(buf))
                self.assertEqual(tuple(got), KEEPER_SITES[game])

    def test_every_site_holds_the_listed_bytes_in_every_mode_and_installs(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            for mode in MODES:
                with self.subTest(game=game, mode=mode):
                    v = Village(game, mode)
                    self.assertEqual(v.installed, 1)

    def test_a_changed_site_installs_nothing(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                v = Village(game, install=False)
                p = v.proc
                buf = p.alloc(8)
                index, first = 0, None
                while True:
                    length = p.export("ItkProbeSite", v.n, index, buf)
                    if length == 0:
                        break
                    if first is None:
                        first = p.u32(buf)
                    index += 1
                last_va = p.u32(buf)
                p.write(last_va, b"\xCC")
                before = p.read(first, 12)
                self.assertEqual(p.export("ItkProbeInstall", v.n), 0)
                self.assertEqual(p.read(first, 12), before, "a site was written although one differed")


@emulated
class BoughtEventsKeepTheNaturalTime(unittest.TestCase):
    def _each(self):
        for game in GAMES:
            if have_stock(game):
                yield game

    def test_before_the_fix_the_trigger_gave_the_bought_event_fresh_hours(self):
        """What the games do without the keeper: the natural time is gone."""
        for game in self._each():
            with self.subTest(game=game):
                v = Village(game, install=False)
                natural = CLOCK + 3 * HOUR
                v.set_timer(natural)
                v.buy()
                v.now += 10
                self.assertTrue(v.tick())
                self.assertIn(v.timer(), v.hours())
                self.assertNotEqual(v.timer(), natural)

    def test_the_origins_island_event_keeps_the_natural_time_on_every_path(self):
        for game in self._each():
            for path, (_, first, _) in PATHS[game].items():
                with self.subTest(game=game, path=path):
                    v = Village(game)
                    natural = CLOCK + 7 * HOUR + 123
                    v.set_timer(natural)
                    v.buy()
                    self.assertNotEqual(v.timer(), natural)   # the purchase's own write
                    v.now += 10
                    self.assertTrue(v.tick(path))
                    self.assertEqual(v.timer(), natural)
                    self.assertEqual(v.state()[0], 0)

    def test_each_barrel_and_re_arm_keeps_it(self):
        cases = [("vv4", "barrel"), ("vv4", "again"), ("vv5", "barrel")]
        for game, what in cases:
            if not have_stock(game):
                continue
            with self.subTest(game=game, what=what):
                v = Village(game)
                natural = CLOCK + 9 * HOUR
                v.set_timer(natural)
                v.buy(what)
                self.assertNotEqual(v.timer(), natural)
                v.now += 10
                self.assertTrue(v.tick())
                self.assertEqual(v.timer(), natural)

    def test_a_story_arm_keeps_it(self):
        for game in self._each():
            with self.subTest(game=game):
                v = Village(game)
                natural = CLOCK + 2 * HOUR
                v.set_timer(natural)
                v.story_arm(0 if game == "vv5" else CLOCK + 5)
                v.now += 10
                self.assertTrue(v.tick())
                self.assertEqual(v.timer(), natural)

    def test_due_soon_and_overdue(self):
        """A natural time a few seconds away, or already passed, comes back
        as it was: the game's own event then comes next."""
        for game in self._each():
            for natural in (CLOCK + 2, CLOCK - 600):
                with self.subTest(game=game, natural=natural - CLOCK):
                    v = Village(game)
                    v.set_timer(natural)
                    v.buy()
                    v.now += 10
                    self.assertTrue(v.tick())
                    self.assertEqual(v.timer(), natural)
                    # the next frame: the natural event, rescheduled as stock
                    v.now += 1
                    self.assertTrue(v.tick())
                    self.assertIn(v.timer(), v.hours())

    def test_a_natural_event_is_untouched(self):
        for game in self._each():
            with self.subTest(game=game):
                v = Village(game)
                v.set_timer(CLOCK - 1)
                self.assertTrue(v.tick())
                self.assertIn(v.timer(), v.hours())

    def test_a_trigger_that_waits_keeps_the_purchase(self):
        """Not due yet: nothing happens; due, the bought event takes the time back."""
        for game in self._each():
            with self.subTest(game=game):
                v = Village(game)
                natural = CLOCK + 4 * HOUR
                v.set_timer(natural)
                v.buy()
                armed = v.timer()
                if armed > v.now:                      # now + 5 (New Believers: due at once)
                    self.assertFalse(v.tick())
                    self.assertEqual(v.timer(), armed)
                    self.assertEqual(v.state()[0], 1)
                v.now = CLOCK + 10
                self.assertTrue(v.tick())
                self.assertEqual(v.timer(), natural)

    def test_a_pause_or_a_time_warp_moves_the_natural_time_with_the_timer(self):
        """Whatever the game adds to its timer while the purchase waits (a
        pause moves it later; a load of a paused save too) it adds to the
        natural time as well."""
        for game in self._each():
            with self.subTest(game=game):
                v = Village(game)
                natural = CLOCK + 5 * HOUR
                v.set_timer(natural)
                v.buy()
                v.set_timer(v.timer() + 900)            # paused for 15 minutes
                v.now += 900 + 10
                self.assertTrue(v.tick())
                self.assertEqual(v.timer(), natural + 900)

    def test_two_writes_before_delivery_keep_the_first_natural_time(self):
        for game in self._each():
            with self.subTest(game=game):
                v = Village(game)
                natural = CLOCK + 6 * HOUR
                v.set_timer(natural)
                v.buy()
                v.story_arm(0 if game == "vv5" else CLOCK + 5)   # e.g. a queued purchase put back
                v.now += 10
                self.assertTrue(v.tick())
                self.assertEqual(v.timer(), natural)


@emulated
class IslandEventsSeenIsCountedAsBefore(unittest.TestCase):
    """The owner: island event counting stays exactly as it is.  Every event
    the trigger makes is counted once, bought or not, with or without the
    keeper."""

    def test_the_count_is_the_same_with_and_without_the_keeper(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            for path in PATHS[game]:
                with self.subTest(game=game, path=path):
                    counts = []
                    for install in (False, True):
                        v = Village(game, install=install)
                        v.set_timer(CLOCK + 3 * HOUR)
                        v.buy()
                        v.now += 10
                        v.tick(path)
                        counts.append(v.counter())
                    self.assertEqual(counts[0], counts[1])
                    first = PATHS[game][path][1]
                    self.assertEqual(counts[1], 1 if first else 6)


@emulated
class KeptAcrossAQuit(unittest.TestCase):
    def _each(self):
        for game in GAMES:
            if have_stock(game):
                yield game

    def test_bought_then_saved_and_reloaded(self):
        for game in self._each():
            with self.subTest(game=game):
                v = Village(game)
                natural = CLOCK + 8 * HOUR
                v.set_timer(natural)
                v.buy()
                self.assertEqual(v.state()[4], 1, "the file is written at the purchase")
                v.proc.export("ItkProbeSaved", 1)          # the quit's save
                v.proc.export("ItkProbeSession", 1)        # a new process, the file on disk
                self.assertEqual(v.state()[0], 0)
                v.now += 3600                              # the load's catch-up
                self.assertTrue(v.tick())
                self.assertEqual(v.timer(), natural)
                self.assertEqual(v.state()[4], 0, "the file goes with the delivery")

    def test_a_paused_save_reloaded(self):
        for game in self._each():
            with self.subTest(game=game):
                v = Village(game)
                natural = CLOCK + 8 * HOUR
                v.set_timer(natural)
                v.buy()
                v.proc.export("ItkProbeSaved", 1)
                v.proc.export("ItkProbeSession", 1)
                v.set_timer(v.timer() + 5000)              # the load moves it by the paused time
                v.now += 5000 + 10
                self.assertTrue(v.tick())
                self.assertEqual(v.timer(), natural + 5000)

    def test_a_crash_before_the_save_is_never_used(self):
        """The save on disk was written before the purchase: it holds the
        natural time itself, and the file is deleted, never applied."""
        for game in self._each():
            with self.subTest(game=game):
                v = Village(game)
                natural = CLOCK + 8 * HOUR
                v.set_timer(natural)
                v.proc.export("ItkProbeSaved", 1)          # the save before the purchase
                v.buy()
                v.proc.export("ItkProbeSession", 1)        # crashed: no save after it
                v.set_timer(CLOCK - 1)                     # the old save's natural event, due
                self.assertTrue(v.tick())
                self.assertIn(v.timer(), v.hours())
                self.assertEqual(v.state()[4], 0)

    def test_another_village_never_takes_it(self):
        for game in self._each():
            with self.subTest(game=game):
                v = Village(game)
                natural = CLOCK + 8 * HOUR
                v.set_timer(natural)
                v.buy()
                v.proc.export("ItkProbeSaved", 1)
                v.proc.export("ItkProbeSession", 1)
                v.village(1, OTHER_ROSTER)                 # Start Over / a new tribe in the slot
                v.set_timer(CLOCK - 1)
                self.assertTrue(v.tick())
                self.assertIn(v.timer(), v.hours())
                self.assertEqual(v.state()[4], 1, "the other village's file is left for it")

    def test_another_slot_in_the_same_session_never_takes_it(self):
        for game in self._each():
            with self.subTest(game=game):
                v = Village(game)
                v.set_timer(CLOCK + 8 * HOUR)
                v.buy()
                v.village(2, OTHER_ROSTER)                 # another slot loaded
                v.set_timer(CLOCK - 1)
                self.assertTrue(v.tick())
                self.assertIn(v.timer(), v.hours())

    def test_a_barrel_saved_and_reloaded_then_re_armed_keeps_the_natural_time(self):
        """Review of #604: a Barrel of Babies bought, saved and reloaded before
        its delivery is armed again after the reload -- The Tree of Life's
        companion re-arms it (vv4_paid_rearm: itk_note, then the timer to 0),
        New Believers' own per-frame payload zeroes the timer again for the
        saved purchase bit.  That second write must keep the natural time the
        file holds, not take the saved purchase's own timer for it."""
        for game in ("vv4", "vv5"):
            if not have_stock(game):
                continue
            for paused in (0, 5000):
                with self.subTest(game=game, paused=paused):
                    v = Village(game)
                    natural = CLOCK + 8 * HOUR
                    v.set_timer(natural)
                    v.buy("barrel")
                    v.proc.export("ItkProbeSaved", 1)
                    v.proc.export("ItkProbeSession", 1)      # relaunch: memory empty, file on disk
                    v.set_timer(v.timer() + paused)          # the load moves the saved timer by a pause
                    if game == "vv4":
                        v.story_arm(0)                       # vv4_paid_rearm: itk_note(timer, 0), then 0
                    else:
                        v.buy("barrel")                      # the saved bit: the payload zeroes it again
                    self.assertEqual(v.state()[0], 1)
                    self.assertEqual(v.state()[5], natural + paused, "the file kept the natural time")
                    v.now += 10
                    self.assertTrue(v.tick())
                    self.assertEqual(v.timer(), natural + paused)

    def test_buying_in_a_second_village_starts_fresh(self):
        """Review of #604: a purchase still on its way in another slot's
        village never lends its distance to a purchase made in this one, and
        the new purchase is bound to this village."""
        for game in self._each():
            with self.subTest(game=game):
                v = Village(game)
                v.set_timer(CLOCK + 8 * HOUR)
                v.buy()                                      # village A, slot 1: on its way
                v.village(2, OTHER_ROSTER)                   # village B loaded, A's purchase pending
                natural_b = CLOCK + 3 * HOUR
                v.set_timer(natural_b)
                v.buy()
                state = v.state()
                self.assertEqual(state[2], 2, "bound to the second village's slot")
                v.now += 10
                self.assertTrue(v.tick())
                self.assertEqual(v.timer(), natural_b)

    def test_buying_in_another_village_of_the_same_slot_starts_fresh(self):
        for game in self._each():
            with self.subTest(game=game):
                v = Village(game)
                v.set_timer(CLOCK + 8 * HOUR)
                v.buy()
                v.village(1, OTHER_ROSTER)                   # Start Over in the slot
                natural_b = CLOCK + 2 * HOUR
                v.set_timer(natural_b)
                v.buy()
                v.now += 10
                self.assertTrue(v.tick())
                self.assertEqual(v.timer(), natural_b)


@emulated
class TheStoryArmsTellTheKeeperFirst(unittest.TestCase):
    """The Story / Cheat Upgrades' arms (Pick Island Event, Custom Island
    Event, the time skip's notice, a queued purchase put back) hand the
    keeper the timer and the value they are about to write, BEFORE writing
    it -- through the host table every Origins companion gives them.  (The
    Secret City's arm calls the Origins purchase's own helper, whose write
    the keeper's site sees, so it needs no call.)"""

    def test_each_arm_calls_island_arming_with_the_old_value_still_there(self):
        from test_story_cheat_upgrades import LockTests, process
        for game in ("vv1", "vv2", "vv4", "vv5"):
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                n = int(game[2:])
                proc = process(game)
                world = LockTests._world(LockTests(), proc, game)
                offset = SPEC[game]["timer"]
                natural = proc.u32(world + offset)
                seen = []

                def arming(q):
                    seen.append((q.arg(0), q.arg(1), q.u32(q.arg(0))))
                    return 0, 8
                code = proc.alloc(0x100)
                for i, fn in enumerate((lambda q: (1, 0), lambda q: (0, 4), lambda q: (0, 8), arming)):
                    proc.stub(code + 0x10 * i, fn)
                host = proc.alloc(0x40)
                fields = [code, code + 0x10, code + 0x20, 0, 0, 0, 0, code + 0x30]
                proc.write(host, struct.pack("<i8I", 36, *fields))
                self.assertEqual(proc.export("VvfpStoryAttachHost", n, host), 1)
                proc.export("VvfpStoryProbeArm", n, 0, 0)
                written = proc.u32(world + offset)
                self.assertEqual(seen, [(world + offset, written, natural)])


@emulated
class EveryPatchTogether(unittest.TestCase):
    def test_no_patch_of_any_game_changes_a_site(self):
        """Every public patch of a game rendered together, in every mode:
        each site still holds the bytes listed, so the keeper installs."""
        import vv_fun_patcher as patcher
        from test_story_cheat_upgrades import _builds, stock_path
        catalog = patcher.load_public_fun_patches()
        for game in GAMES:
            if not have_stock(game):
                continue
            rows = [p for p in catalog if p.id.startswith(game + "_")]
            # An alternative row (Fruit Trees Take Turns Refilling) is never built
            # with the row it conflicts with: once without it, once in that row's place.
            replaced = {c for p in rows if p.id in patcher.ALTERNATIVE_FUN_PATCH_IDS
                        for c in patcher.conflict_ids(p)}
            selections = [("all", [p.id for p in rows if p.id not in patcher.ALTERNATIVE_FUN_PATCH_IDS])]
            if replaced:
                selections.append(("alternatives instead", [p.id for p in rows if p.id not in replaced]))
            for label, chosen in selections:
                ids = patcher.resolve_fun_patch_ids(chosen, game_id=game)
                for mode in MODES:
                    with self.subTest(game=game, mode=mode, selection=label):
                        data, _ = patcher.render_patched_bytes(stock_path(game), _builds()[game], mode, ids)
                        proc = Process(bytes(data), DLL)
                        self.assertEqual(proc.export("ItkProbeInstall", int(game[2:])), 1)


if __name__ == "__main__":
    unittest.main()
