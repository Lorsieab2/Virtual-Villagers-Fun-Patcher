"""Fix Vanilla Bugs (A New Home): the Golden Child is never the villager of a NATURAL island event
that could kill him or make him disappear ("VVFP VV1 Golden Child Safe.dll",
native/vv1_golden_child_safe).  Owner-approved 2026-10-24, decision "B"; the owner's definitions:
lethal = sets health to 0 or below, judged against his health when the event picks its villager;
natural events only -- Custom Island Event and Pick Island Event may pick anyone the player wishes.

Everything here runs the game's own code in an emulator: the villager picker 0x43BCD0 and the
rotting crate's bite 0x42AAA0, stock and with the DLL installed, with the game's rand(bound)
answered by the test so every value it can return is tried.

* For each of the seven events (the Strange Berries, the Mysterious Face, the Book: always; the
  Suspicious Monkey, the Wild Mushroom, the rotting and the old fruit crates: when the most they
  could take is at least his health) the picker never returns him, and for every value of rand it
  returns exactly the villager the stock picker returns from the same village without him -- so
  each of the others is as likely as before.  At one more point of health than the threshold, and
  for every other event, the picker is the stock one byte for byte (he can be picked).
* He alone: -1 (the game's own "nobody", which ends the setup with no event), with no rand call.
* Many random villages (seeds): the same, every rand value.
* A picked event (Story / Cheat Upgrades' VvfpStoryEventChosen) is the stock picker; a setup call
  that a Story scope call stands in for is recognised through VvfpStoryCallerReturn.
* The bite: passes over him only when it would bring him to 0 or below; everyone else as stock.
* Story / Cheat Upgrades' own flag (its test build): set when a pick is delivered, cleared by the
  game's own roll.
* All or nothing: one changed byte anywhere it checks and nothing is written; it installs on every
  rendered build, beside the whole catalog.

The live effect in a running game is NOT verified here.
"""
from __future__ import annotations

import functools
import random
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_fun_patcher as patcher  # noqa: E402

try:
    import pefile  # noqa: F401
    from story_emulator import HEAP, STACK_TOP, Process

    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False
    HEAP = STACK_TOP = 0

DLL = ROOT / "assets" / "golden_child_safe" / "VVFP VV1 Golden Child Safe.dll"
STORY_TEST_DLL = ROOT / "tests" / "test_dlls" / "VVFP Story Upgrades.test.dll"

PICKER = 0x43BCD0
BITE = 0x42AAA0
RAND = 0x402F10
STRIDE = 0x3D8
GOLDEN = 0xC7
# The setups' `call 0x43BCD0`, by event (variant, family): what each could do to its villager.
ALWAYS = {"The Strange Berries": 0x418AA3, "The Mysterious Face": 0x418BB1, "The Book": 0x4191C8}
THRESHOLD = {"The Suspicious Monkey": (0x418F25, 50), "The Wild Mushroom": (0x418FAC, 49),
             "A Mysterious Crate (rotting)": (0x42B22B, 35), "A Mysterious Crate (old fruit)": (0x42B391, 110)}
# Every other setup that picks a villager with 0x43BCD0 (encounter cases 0, 2, 4, 5, 6, 8, 11, 12,
# 13, 15; crate cases 0, 1, 2, 4, 6, 7, 8) and the delivery parent pick (0x4237DD, adults only).
OTHERS = (0x418A1C, 0x418B2A, 0x418C38, 0x418CBF, 0x418D46, 0x418E9E, 0x419033, 0x4190BA, 0x419141,
          0x41924F, 0x42B06B, 0x42B11E, 0x42B1D1, 0x42B2DE, 0x42B444, 0x42B51C, 0x42B5C7)
# The setup jump tables: (table, cases) -> the case each affected call belongs to.
ENCOUNTER_TABLE, CRATE_TABLE = 0x419338, 0x42B71C
CASE_OF = {0x418AA3: ("encounter", 1), 0x418BB1: ("encounter", 3), 0x4191C8: ("encounter", 14),
           0x418F25: ("encounter", 9), 0x418FAC: ("encounter", 10), 0x42B22B: ("crate", 3),
           0x42B391: ("crate", 5)}


@functools.lru_cache(maxsize=None)
def _build():
    return {b.id: b for b in patcher.load_builds()}["vv1"]


def stock_path() -> Path:
    return ROOT / "inputs" / "vv1-stock-copy" / _build().input_name


@functools.lru_cache(maxsize=None)
def stock_exe() -> bytes:
    return stock_path().read_bytes()


def have() -> bool:
    return HAVE_EMULATOR and stock_path().is_file() and DLL.is_file()


def signed(value: int) -> int:
    return value - (1 << 32) if value & 0x80000000 else value


class Village:
    """256 villager records in the emulator, and the picker / bite run on them."""

    def __init__(self, dll: bool, exe: bytes | None = None, install: bool = True):
        self.p = Process(exe if exe is not None else stock_exe(), DLL if dll else None)
        if dll and install:
            self.p.export("VvfpStartup", 1, 0)
        self.records = self.p.alloc(256 * STRIDE)
        self.dialog = self.p.alloc(0x6000)
        self.p.put32(self.dialog + 0x50AC, self.records)
        self.rand_bounds: list[int] = []
        self.answer = 0
        self.p.stub(RAND, self._rand)

    def _rand(self, p):
        bound = p.arg(0)
        self.rand_bounds.append(bound)
        value = self.answer
        assert 0 <= value < max(bound, 1), (value, bound)
        return value, 0

    def put(self, i: int, *, health: int = 100, age: int = 400, present: int = 1, golden: bool = False):
        at = self.records + i * STRIDE
        self.p.write(at + 0x28, bytes([present]))
        self.p.put32(at + 0x344, health)
        self.p.put32(at + 0x348, age)
        self.p.put32(at + 0x36C, GOLDEN if golden else 0)

    def health(self, i: int) -> int:
        return signed(self.p.u32(self.records + i * STRIDE + 0x344))

    def sick(self, i: int) -> int:
        return self.p.u32(self.records + i * STRIDE + 0x354)

    def pick(self, call: int, adults_only: int = 0, *, back: int | None = None) -> int:
        """The picker as the setup at `call` calls it (or, `back`, as a Story scope call does: its own
        return address in the slot)."""
        esp = STACK_TOP - 0x4000
        ret = back if back is not None else call + 5
        self.p.put32(esp, ret)
        self.p.put32(esp + 4, adults_only)
        self.p.set_reg("esp", esp)
        self.p.set_reg("ecx", self.records)
        self.p.run(PICKER, ret)
        self.slot = esp
        return signed(self.p.reg("eax"))

    def bite(self, chance: int, bites: int, damage: int) -> None:
        self.p.call(BITE, [chance, bites, damage], ecx=self.dialog)


def every_answer(make, call: int, adults_only: int = 0, **kw):
    """(the rand bound, [the picker's answer for each value rand can return]) for a village `make`
    builds; bound 0 when rand was never asked."""
    v = make()
    v.answer = 0
    first = v.pick(call, adults_only, **kw)
    if not v.rand_bounds:
        return 0, [first]
    bound = v.rand_bounds[0]
    out = []
    for r in range(bound):
        v = make()
        v.answer = r
        out.append(v.pick(call, adults_only, **kw))
    return bound, out


def _skip():
    return unittest.skipUnless(have(), "unicorn/pefile, the stock A New Home or the DLL is missing")


@_skip()
class TheSetups(unittest.TestCase):
    """The seven calls are the events named: each lies in its own case of the setup's jump table."""

    def test_each_call_is_its_event(self):
        p = Process(stock_exe())
        for call, (family, case) in CASE_OF.items():
            table, cases = (ENCOUNTER_TABLE, 16) if family == "encounter" else (CRATE_TABLE, 9)
            starts = sorted(p.u32(table + 4 * k) for k in range(cases))
            start = p.u32(table + 4 * case)
            after = min([s for s in starts if s > start] + [start + 0x200])
            with self.subTest(call=hex(call)):
                self.assertTrue(start <= call < after, "the call is in its own case")
                self.assertEqual(p.read(call, 1), b"\xE8")
                self.assertEqual(p.u32(call + 1) + call + 5 & 0xFFFFFFFF, PICKER)


def village_with(dll: bool, gc_at: int | None, gc_health: int = 100, gc_age: int = 100, n: int = 8):
    def make():
        v = Village(dll)
        for i in range(n):
            v.put(i, health=60 + i, age=300 + 40 * i)
        if gc_at is not None:
            v.put(gc_at, health=gc_health, age=gc_age, golden=True)
        return v
    return make


@_skip()
class NeverTheGoldenChild(unittest.TestCase):
    def check_spared(self, call: int, health: int) -> None:
        for gc_at in (0, 3, 7):
            with self.subTest(call=hex(call), health=health, at=gc_at):
                bound, answers = every_answer(village_with(True, gc_at, health), call)

                def without():                  # the stock picker, the same village without him
                    v = village_with(False, gc_at, health)()
                    v.put(gc_at, present=0)
                    return v
                others = [i for i in range(8) if i != gc_at]
                self.assertNotIn(gc_at, answers)
                self.assertEqual(bound, len(others), "rand is asked for the others only")
                self.assertEqual(answers, others, "each value of rand gives the villager the game would")
                self.assertEqual((bound, answers), every_answer(without, call))

    def check_stock(self, call: int, health: int) -> None:
        with self.subTest(call=hex(call), health=health, stock=True):
            got = every_answer(village_with(True, 3, health), call)
            want = every_answer(village_with(False, 3, health), call)
            self.assertEqual(got, want, "the game's own picker, the Golden Child included")
            self.assertIn(3, got[1])

    def test_always_events(self):
        for name, call in ALWAYS.items():
            for health in (1, 50, 100):
                self.check_spared(call, health)

    def test_health_thresholds(self):
        for name, (call, most) in THRESHOLD.items():
            for health in sorted({1, most - 1, most} - {0}):
                if health <= 100:
                    self.check_spared(call, health)
            if most + 1 <= 100:
                self.check_stock(call, most + 1)
                self.check_stock(call, 100)

    def test_old_fruit_crate_at_full_health(self):
        self.check_spared(THRESHOLD["A Mysterious Crate (old fruit)"][0], 100)

    def test_every_other_event_is_stock(self):
        for call in OTHERS + (0x4237DD,):
            for adults in (0, 1):
                with self.subTest(call=hex(call), adults=adults):
                    got = every_answer(village_with(True, 3, 1), call, adults)
                    want = every_answer(village_with(False, 3, 1), call, adults)
                    self.assertEqual(got, want)
        # Not the Golden Child: everyone as stock, even for the seven.
        for call in list(ALWAYS.values()) + [c for c, _ in THRESHOLD.values()]:
            with self.subTest(call=hex(call), golden=False):
                self.assertEqual(every_answer(village_with(True, None), call),
                                 every_answer(village_with(False, None), call))

    def test_he_alone_is_nobody(self):
        for call in list(ALWAYS.values()) + [c for c, _ in THRESHOLD.values()]:
            with self.subTest(call=hex(call)):
                v = village_with(True, 0, 10, n=0)()
                self.assertEqual(v.pick(call), -1)
                self.assertEqual(v.rand_bounds, [], "no rand call, as the stock picker with nobody")
                s = village_with(False, None, n=0)()
                self.assertEqual(s.pick(call), -1, "the game's own answer when nobody is there")

    def test_the_dead_absent_and_children_as_stock(self):
        """The others are chosen by the game's own rule: health above 0, present, adults when asked."""
        def make(dll):
            def build():
                v = Village(dll)
                v.put(0, health=0)
                v.put(1, present=0)
                v.put(2, age=100)
                v.put(3, health=-5)
                v.put(4)
                v.put(5, age=279)
                v.put(6, age=280)
                if dll:
                    v.put(7, health=40, golden=True)
                return v
            return build
        for call in (ALWAYS["The Book"], THRESHOLD["The Suspicious Monkey"][0]):
            for adults in (0, 1):
                with self.subTest(call=hex(call), adults=adults):
                    self.assertEqual(every_answer(make(True), call, adults),
                                     every_answer(make(False), call, adults))

    def test_many_seeds(self):
        calls = list(ALWAYS.values()) + [c for c, _ in THRESHOLD.values()]
        for seed in range(60):
            rng = random.Random(seed)
            n = rng.randint(1, 40)
            people = [dict(health=rng.choice([0, -3, 1, 20, 49, 50, 51, 100]), age=rng.choice([100, 279, 280, 900]),
                           present=rng.choice([0, 1, 1, 1])) for _ in range(n)]
            gc = rng.randrange(n)
            gc_health = rng.choice([1, 35, 36, 49, 50, 51, 100])
            people[gc] = dict(health=gc_health, age=100, present=1)
            call = calls[seed % len(calls)]

            def make(dll, without=False):
                def build():
                    v = Village(dll)
                    for i, person in enumerate(people):
                        if without and i == gc:
                            v.put(i, present=0)
                        else:
                            v.put(i, golden=(i == gc), **person)
                    return v
                return build
            most = dict(THRESHOLD.values()).get(call)
            spared = most is None or gc_health <= most
            with self.subTest(seed=seed, call=hex(call), gc_health=gc_health):
                got = every_answer(make(True), call)
                if spared:
                    self.assertEqual(got, every_answer(make(False, without=True), call))
                    self.assertNotIn(gc, got[1])
                else:
                    self.assertEqual(got, every_answer(make(False), call))


class FakeStory:
    """Story / Cheat Upgrades' two exports, answered by the test."""

    MODULE = 0x0B000000

    def __init__(self, v: Village, chosen: int = 0, back: int | None = None, call: int | None = None):
        self.v, self.chosen, self.back, self.call = v, chosen, back, call
        p = v.p
        self.chosen_at = p.alloc(16)
        self.caller_at = p.alloc(16)
        p.stub(self.chosen_at, lambda q: (self.chosen if q.arg(0) == 1 else 0, 4))
        p.stub(self.caller_at, self._caller)
        p.api_handlers["GetModuleHandleA"] = lambda q: (
            self.MODULE if q.cstring(q.arg(0)) == "VVFP Story Upgrades.dll" else 0, 4)
        names = {"VvfpStoryEventChosen": self.chosen_at, "VvfpStoryCallerReturn": self.caller_at}
        p.api_handlers["GetProcAddress"] = lambda q: (
            names.get(q.cstring(q.arg(1)), 0) if q.arg(0) == self.MODULE else 0, 8)

    def _caller(self, q):
        slot = q.arg(0)
        if self.back is not None and q.u32(slot) == self.back:
            return self.call + 5, 4
        return 0, 4


@_skip()
class PickedEventsAreThePlayers(unittest.TestCase):
    def test_a_picked_event_is_stock(self):
        call = ALWAYS["The Strange Berries"]
        for chosen in (1, 0):
            with self.subTest(chosen=chosen):
                v = village_with(True, 3, 100)()
                FakeStory(v, chosen=chosen)
                answers = []
                for r in range(8 if chosen else 7):
                    v.rand_bounds.clear()
                    v.answer = r
                    answers.append(v.pick(call))
                if chosen:
                    self.assertEqual(answers, list(range(8)), "the stock picker: the Golden Child included")
                    self.assertIn(3, answers)
                else:
                    self.assertEqual(answers, [0, 1, 2, 4, 5, 6, 7])

    def test_through_a_story_scope_call(self):
        """The setup's call is Story's scope call: the slot holds its oc_scope_back."""
        call = THRESHOLD["The Suspicious Monkey"][0]
        v = village_with(True, 3, 20)()
        back = v.p.alloc(16)
        v.p.write(back, b"\xC3")
        FakeStory(v, chosen=0, back=back, call=call)
        seen = []
        for r in range(7):
            v.answer = r
            seen.append(v.pick(call, back=back))
        self.assertEqual(seen, [0, 1, 2, 4, 5, 6, 7])
        # A slot no scope call took (another caller of the picker): stock.
        v2 = village_with(True, 3, 20)()
        other = v2.p.alloc(16)
        v2.p.write(other, b"\xC3")
        FakeStory(v2, chosen=0, back=None, call=call)
        v2.answer = 3
        self.assertEqual(v2.pick(call, back=other), 3)

    def test_a_picked_rotting_crate_bites_him(self):
        v = village_with(True, 2, 15)()
        FakeStory(v, chosen=1)
        v.answer = 0
        v.bite(45, 1, 20)
        self.assertEqual(v.health(2), 0)
        self.assertEqual(v.sick(2), 1)


@_skip()
class TheBite(unittest.TestCase):
    def run_bite(self, dll: bool, gc_health: int, damage: int, bites: int = 1):
        v = village_with(dll, 2, gc_health)()
        v.answer = 0                      # every roll hits
        v.bite(45, bites, damage)
        return v

    def test_spared_only_when_it_would_kill(self):
        for damage in (10, 15, 20):
            for gc_health in (1, damage - 1, damage, damage + 1, 100):
                with self.subTest(damage=damage, gc_health=gc_health):
                    fixed, stock = self.run_bite(True, gc_health, damage), self.run_bite(False, gc_health, damage)
                    for i in (0, 1, 3, 4, 5, 6, 7):
                        self.assertEqual(fixed.health(i), stock.health(i))
                        self.assertEqual(fixed.sick(i), stock.sick(i))
                    self.assertEqual(fixed.rand_bounds, stock.rand_bounds, "everyone's roll as before")
                    if gc_health <= damage:
                        self.assertEqual(fixed.health(2), gc_health, "not bitten")
                        self.assertEqual(fixed.sick(2), 0, "not made sick")
                        self.assertEqual(stock.health(2), 0, "the stock bite kills him")
                    else:
                        self.assertEqual((fixed.health(2), fixed.sick(2)), (stock.health(2), stock.sick(2)))

    def test_a_sickness_only_loop_is_stock(self):
        """The badly weathered crate's loop (no bites): he falls ill as everyone may."""
        fixed, stock = self.run_bite(True, 5, 0, bites=0), self.run_bite(False, 5, 0, bites=0)
        self.assertEqual([fixed.sick(i) for i in range(8)], [stock.sick(i) for i in range(8)])
        self.assertEqual(fixed.sick(2), 1)


@_skip()
class AllOrNothing(unittest.TestCase):
    SITES = ((PICKER, b"\x81\xEC\x00\x04\x00\x00"), (0x42AAFC, b"\x84\xDB\x8B\x8F\xAC\x50\x00\x00"))

    def installed(self, p: Process) -> bool:
        return p.export("VvfpGoldenChildSafeInstalled") == 1

    def test_installs_on_the_stock_game_only(self):
        p = Process(stock_exe(), DLL)
        p.export("VvfpStartup", 3, 0)
        self.assertFalse(self.installed(p))
        for site, stock in self.SITES:
            self.assertEqual(p.read(site, len(stock)), stock)
        p.export("VvfpStartup", 1, 0)
        self.assertTrue(self.installed(p))
        for site, _stock in self.SITES:
            self.assertEqual(p.read(site, 1), b"\xE9")

    def test_one_changed_byte_installs_nothing(self):
        checks = [PICKER + 0x10, PICKER + 0x180, PICKER + 0x197, BITE, BITE + 0x60, BITE + 0xB2, RAND + 3]
        checks += [c for c in CASE_OF] + [c + 5 for c in CASE_OF]
        for at in checks:
            with self.subTest(at=hex(at)):
                p = Process(stock_exe(), DLL)
                p.write(at, bytes([p.read(at, 1)[0] ^ 0xFF]))
                before = [p.read(s, len(b)) for s, b in self.SITES]
                p.export("VvfpStartup", 1, 0)
                self.assertFalse(self.installed(p))
                self.assertEqual([p.read(s, len(b)) for s, b in self.SITES], before)

    def test_installs_beside_story_upgrades_rand_calls(self):
        """Story / Cheat Upgrades points the two rand calls at its own answer (0x43BE53, 0x42AAEC)."""
        p = Process(stock_exe(), DLL)
        for call in (0x43BE53, 0x42AAEC):
            p.write(call + 1, struct.pack("<i", 0x0E000000 - (call + 5)))
        p.export("VvfpStartup", 1, 0)
        self.assertTrue(self.installed(p))

    def test_installs_on_the_rendered_builds(self):
        ids = [x.id for x in patcher.load_public_fun_patches()
               if x.game_id == "vv1" and x.id not in patcher.ALTERNATIVE_FUN_PATCH_IDS
               and x.id not in patcher.EXPERIMENTAL_FUN_PATCH_IDS]
        for mode in ("stock", "collection_progression", "immediate_fixed"):
            with self.subTest(mode=mode):
                data, _ = patcher.render_patched_bytes(stock_path(), _build(), mode, ids)
                p = Process(bytes(data), DLL)
                p.export("VvfpStartup", 1, 0)
                self.assertTrue(self.installed(p))


@unittest.skipUnless(HAVE_EMULATOR and STORY_TEST_DLL.is_file() and stock_path().is_file() if HAVE_EMULATOR else False,
                     "the Story / Cheat Upgrades test build or the stock A New Home is missing")
class StoryUpgradesSaysWhichEventsArePicked(unittest.TestCase):
    """VvfpStoryEventChosen: 1 from a delivered pick's roll until the game rolls on its own."""

    def test_the_flag(self):
        import test_story_outcomes as so
        for site, slot, bound in ((0x418932, (1 << 6) | 1, 16), (0x42B03E, (2 << 6) | 5, 9)):
            with self.subTest(site=hex(site)):
                g = so.Game("vv1")
                self.assertEqual(g.proc.export("VvfpStoryEventChosen", 1), 0)
                g.proc.export("VvfpStoryProbeSetTick", 0)
                g.proc.export("VvfpStoryProbeSetPick", 1, so._position("vv1", slot), 0)
                self.assertEqual(g.roll(site, bound), slot & 0x3F)
                self.assertEqual(g.proc.export("VvfpStoryEventChosen", 1), 1, "the picked event")
                self.assertEqual(g.proc.export("VvfpStoryEventChosen", 2), 0, "only A New Home")
                g.roll(site, bound)
                self.assertEqual(g.proc.export("VvfpStoryEventChosen", 1), 0, "the game's own roll")


if __name__ == "__main__":
    unittest.main()
