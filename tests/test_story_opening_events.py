"""A new village's two opening island events stay the game's own (v1.35.73).

The owner: "ALL VV GAMES WILL ALWAYS SHOW TWO ISLAND EVENTS WHEN STARTING A
NEW TRIBE GAME!!! THIS IS BASE-GAME".  A Custom Island Event bought before or
at the start of a new tribe used to be delivered in place of one of those two
(native/vvfp_story_upgrades/story_custom.inc, "A new village's two opening
island events").

* StockOpeningTests read the five stock executables: each village start sets
  the trigger's island-event counter to 0 and makes the first event due
  900 s later, and each trigger makes the second one due 30 minutes after the
  first only while that counter is 0.
* OpeningSequenceTests run each game's real island-event trigger (the stock
  code as the patcher renders it, with the companion's detours installed)
  three times in a new village with a custom event queued at its start; only
  the game's leaf routines (clock, random, sound, the event builder, the
  popup) are stubs.  The first two events are the game's own; the custom
  event is the third.
* HeldPurchaseTests: bought then, the purchase does not bring the first
  opening event forward; it keeps the lock, and once the game has made both
  opening events the companion's tick makes the island event due exactly as
  the Island Event purchase does.
"""
from __future__ import annotations

import unittest

from test_story_custom_island_event import (  # noqa: E402
    CHOOSER,
    EVENT_BUF,
    HAVE_EMULATOR,
    MODES,
    SELECT,
    TEXT_BUF,
    Event,
    Process,
    Story,
    emulated,
    events_seen_address,
    have_stock,
    render,
    stock_path,
    TEST_DLL,
)

if HAVE_EMULATOR:
    from story_emulator import HEAP

try:
    import pefile
    from capstone import CS_ARCH_X86, CS_MODE_32, Cs

    HAVE_CAPSTONE = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_CAPSTONE = False

GAMES = ("vv1", "vv2", "vv3", "vv4", "vv5")
CLOCK = 1_700_000_000
# Each game's own population count, the one its island-event trigger asks
# (thiscall, no arguments).
POPULATION_COUNT = {"vv1": 0x41CF90, "vv2": 0x425860, "vv3": 0x45E8F0, "vv4": 0x467610,
                    "vv5": 0x4713F0}


# ---------------------------------------------------------------------------
# The stock executables: where the opening events come from
# ---------------------------------------------------------------------------

# (village start, its counter write, its first-event countdown write,
#  the trigger's 30-minute reschedule while the counter is 0)
STOCK = {
    "vv1": dict(start=0x41C000, zero=(0x41C3EB, "mov dword ptr [ebp + 0x9e40], ebx"),
                ebx=0x41C009, first=(0x41C4A9, "add eax, 0x384", 0x41C4AE, "mov dword ptr [ebp + 0xa300], eax"),
                gap=(0x423A1E, "cmp dword ptr [ecx + 0x9e40], ebx", 0x423A37,
                     "add dword ptr [eax + 0xa300], 0x708")),
    "vv2": dict(start=0x424C80, zero=(0x4251D5, "mov dword ptr [ebp + 0x2e51c], ebx"),
                ebx=0x424CA1, first=(0x42529B, "add eax, 0x384", 0x4252A2, "mov dword ptr [ebp + 0x2eae0], eax"),
                gap=(0x42F12E, "cmp dword ptr [ecx + 0x2e51c], ebx", 0x42F147,
                     "add dword ptr [eax + 0x2eae0], 0x708")),
    "vv3": dict(start=0x427F70, reset=(0x427FD3, 0x5824A0, 0x426450),
                first=(0x4280B2, "add eax, 0x384", 0x4280B9, "mov dword ptr [esi + 0x12ef4], eax"),
                gap=(0x4687A5, "mov eax, dword ptr [0x5824c4]", 0x468899,
                     "add dword ptr [eax + 0x12ef4], 0x708")),
    "vv4": dict(start=0x41F1E0, reset=(0x41F243, 0x4D6DE0, 0x41D9D0),
                first=(0x41F31B, "add eax, 0x384", 0x41F322, "mov dword ptr [esi + 0x170e0], eax"),
                gap=(0x43FB81, "cmp dword ptr [0x4d6e04], ebx", 0x43FB9D,
                     "add dword ptr [eax + 0x170e0], 0x708")),
    "vv5": dict(start=0x4246A0, reset=(0x424738, 0x51D358, 0x41EBF0),
                first=(0x424854, "add eax, 0x384", 0x42485B, "mov dword ptr [esi + 0x17d3c], eax"),
                gap=(0x4427E5, "cmp dword ptr [0x51d37c], ebx", 0x442801,
                     "add dword ptr [eax + 0x17d3c], 0x708")),
}


def _stock(game):
    if not HAVE_CAPSTONE:
        raise unittest.SkipTest("capstone/pefile not installed")
    if not have_stock(game):
        raise unittest.SkipTest(f"stock {game} is not in inputs/")
    pe = pefile.PE(str(stock_path(game)))
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    base = pe.OPTIONAL_HEADER.ImageBase

    def ins(va):
        code = pe.get_data(va - base, 16)
        i = next(md.disasm(code, va))
        return f"{i.mnemonic} {i.op_str}".strip(), i.size

    def from_to(a, b):
        out = []
        while a < b:
            text, size = ins(a)
            out.append((a, text))
            a += size
        return out
    return ins, from_to


class StockOpeningTests(unittest.TestCase):
    def test_each_village_start_zeroes_the_counter_and_makes_the_first_event_due_in_15_minutes(self):
        for game, s in STOCK.items():
            with self.subTest(game=game):
                ins, from_to = _stock(game)
                if "zero" in s:
                    # A New Home / The Lost Children: the world's own field, ebx = 0.
                    self.assertEqual(ins(s["ebx"])[0], "xor ebx, ebx")
                    walk = [t for a, t in from_to(s["ebx"], s["zero"][0] + 1)]
                    self.assertFalse([t for t in walk[1:] if t.startswith(("mov ebx", "xor ebx", "pop ebx",
                                                                            "inc ebx", "add ebx"))],
                                     "ebx stays 0 up to the write")
                    self.assertEqual(ins(s["zero"][0])[0], s["zero"][1])
                else:
                    # The later three: the statistics block (0x98 bytes, the counter at
                    # +0x24) is reset by a routine that zeroes all of it.
                    at, block, reset = s["reset"]
                    self.assertEqual(ins(at)[0], f"mov ecx, 0x{block:x}")
                    self.assertEqual(ins(at + 5)[0], f"call 0x{reset:x}")
                    body = [t for a, t in from_to(reset, reset + 0x30)]
                    joined = " | ".join(body)
                    self.assertTrue("rep stosd" in joined or "push 0x98" in joined, joined)
                    self.assertIn("mov dword ptr [e", joined)       # +4 = 0x63, nothing at +0x24
                    self.assertNotIn("+ 0x24]", joined)
                    self.assertEqual(block + 0x24, events_seen_address(game, 0))
                self.assertEqual(ins(s["first"][0])[0], s["first"][1])
                self.assertEqual(ins(s["first"][2])[0], s["first"][3])

    def test_the_second_event_is_due_30_minutes_after_the_first_only_while_the_counter_is_0(self):
        for game, s in STOCK.items():
            with self.subTest(game=game):
                ins, _ = _stock(game)
                self.assertEqual(ins(s["gap"][0])[0], s["gap"][1])
                self.assertEqual(ins(s["gap"][2])[0], s["gap"][3])


# ---------------------------------------------------------------------------
# Each game's real trigger, three times, in a new village
# ---------------------------------------------------------------------------

def _p(value, pop):
    return lambda proc: (value & 0xFFFFFFFF, pop)


class Trigger:
    """One game's island-event trigger in the emulator: its stock code from
    the clock check to the end of the event, with its leaf routines
    stubbed.  `fire()` runs it once and then, if it built an island event,
    runs the companion's delivery point inside that event's builder (the
    chooser call of A New Home / The Lost Children, the selector of the
    later three) exactly as the delivery tests do."""

    SPEC = {
        "vv1": dict(start=0x4237B3, end=0x423ABE, countdown=0xA300, clock=0x402F70, rand=0x402F10,
                    stubs={0x41CF90: 5, 0x41D110: 0, 0x431470: (0, 4), 0x401AB0: (0, 8),
                           0x427620: 0, 0x418400: 0, 0x42A6A0: 0},
                    picker=(0x43BCD0, 4), builder=(0x4286B0, 8), encounter=0x41A460, other=0x42D0E0),
        "vv2": dict(start=0x42EEC3, end=0x42F1F9, countdown=0x2EAE0, clock=0x403200, rand=0x4031A0,
                    stubs={0x425860: 5, 0x426110: 0, 0x43F010: (0, 4), 0x401AD0: (0, 8),
                           0x433190: 0, 0x41F040: 0, 0x437180: 0},
                    picker=(0x44BAE0, 4), builder=(0x4348E0, 8), encounter=0x422380, other=0x439DD0),
        "vv3": dict(start=0x468727, end=0x468901, countdown=0x12EF4, clock=0x403330, rand=0x4032D0,
                    stubs={0x45E8F0: 5, 0x402200: 0, 0x45EE60: (1, 4), 0x424110: (0, 4)},
                    picker=(0x45C9D0, 4), builder=(0x419B30, 0), getter=0x419AC0),
        "vv4": dict(start=0x43FA32, end=0x43FBEA, countdown=0x170E0, clock=0x403750, rand=0x4036D0,
                    stubs={0x467610: 5, 0x416EB0: 0, 0x448E10: (0, 4)},
                    picker=(0x4679B0, 0x28), builder=(0x418000, 0), getter=0x417F70),
        "vv5": dict(start=0x4426DF, end=0x442881, countdown=0x17D3C, clock=0x4036E0, rand=0x403660,
                    stubs={0x4713F0: 5, 0x417650: 0, 0x44C440: (0, 4)},
                    picker=(0x471870, 0x38), builder=(0x418870, 0), getter=0x4187F0),
    }

    def __init__(self, story: Story):
        self.story = story
        self.game = story.game
        g = self.SPEC[self.game]
        self.g = g
        p = story.proc
        v = story.village
        v.put(1, sex="m", years=30, name="Adam")
        v.put(2, sex="f", years=30, name="Bea")
        if v.world is None:
            v.world = p.alloc(0x18000)
        self.world = v.world
        self.this = p.alloc(0x100)
        p.put32(self.this + 0x10, self.world)
        p.put32(self.this + 0x18, p.alloc(0x100))
        p.put32(self.this + 0x20, getattr(v, "array", 0) or p.alloc(0x100))
        p.stub(g["clock"], _p(CLOCK, 0))
        for va, value in g["stubs"].items():
            value, pop = value if isinstance(value, tuple) else (value, 0)
            p.stub(va, _p(value, pop))
        # The game's own random routine: rand(100) answers 50 first in each
        # trigger run (no visitor roll), then 10 (A New Home / The Lost
        # Children: their island family); every other bound answers 0.
        self.rolls = []

        def rand(proc):
            bound = proc.arg(0)
            if bound == 100:
                self.rolls.append(bound)
                return (50 if len(self.rolls) == 1 else 10), 0
            return 0, 0
        p.stub(g["rand"], rand)
        picker, pop = g["picker"]
        drawn = 1 if self.game in ("vv1", "vv2", "vv3") else v.record(1)
        p.stub(picker, _p(drawn, pop))
        if self.game == "vv3":
            p.stub(0x45C840, _p(v.record(1), 4))
        if self.game == "vv5":
            p.put32(0x51D5A4, 0xFFFFFFFF)            # no barrel under way
        self.built = []
        builder, pop = g["builder"]
        p.stub(builder, lambda proc: (self.built.append("island") or 0, pop))
        if "encounter" in g:
            p.stub(g["encounter"], lambda proc: (self.built.append("visitor") or 0, 0))
            p.stub(g["other"], lambda proc: (self.built.append("other") or 0, 0))
        else:
            event_object = p.alloc(0x40)
            p.stub(g["getter"], _p(event_object, 4))
        # The delivery point's own setup, once.
        if self.game in CHOOSER:
            story.record_call(CHOOSER[self.game][2], 8)
        else:
            table = SELECT[self.game][0]
            self.stock_objects = {}
            for slot in range(1, 58):
                obj = p.alloc(0x20)
                p.put32(table + 4 * slot, obj)
                self.stock_objects[slot] = obj

    @property
    def counter(self) -> int:
        return self.story.proc.u32(events_seen_address(self.game, self.world))

    @counter.setter
    def counter(self, value: int) -> None:
        self.story.proc.put32(events_seen_address(self.game, self.world), value)

    def fire(self) -> str:
        """The trigger once, with the island event due now.  Returns what the
        player saw: "custom", "stock island event", "visitor" or "other"."""
        p = self.story.proc
        g = self.g
        self.rolls.clear()
        self.built.clear()
        p.put32(self.world + g["countdown"], CLOCK)
        p.set_reg("esi", self.this)
        p.set_reg("ebx", 0)
        p.set_reg("esp", HEAP + 0x3000000)
        p.run(g["start"], g["end"])
        assert len(self.built) == 1, self.built
        if self.built[0] != "island":
            return self.built[0]
        return "custom" if self._deliver() else "stock island event"

    def _deliver(self) -> bool:
        p = self.story.proc
        before = p.export("VvfpStoryProbeCustomPending", self.story.n)
        if self.game in CHOOSER:
            site, resume, chooser = CHOOSER[self.game]
            calls = len(self.story.calls.get(chooser, []))
            event_object = p.alloc(0x5100)
            esp = HEAP + 0x3000000
            p.put32(esp, 2)
            p.put32(esp + 4, 6)
            p.set_reg("esp", esp)
            p.set_reg("ecx", event_object)
            p.set_reg("esi", event_object)
            p.set_reg("ebp", event_object + 0x277F)
            p.run(site, resume)
            delivered = len(self.story.calls.get(chooser, [])) == calls
            if delivered:
                assert p.cstring(event_object + 0x277F).startswith("The Long Night"), \
                    p.cstring(event_object + 0x277F)
        else:
            _, site, resume, register, *_ = SELECT[self.game]
            p.set_reg("esi", 5)
            p.set_reg("esp", HEAP + 0x3000000)
            p.run(site, resume)
            obj = p.reg(register)
            delivered = obj != self.stock_objects[5]
            if delivered:
                assert obj == p.export("VvfpStoryProbeObject")
        if delivered:
            assert before == 1
            assert p.export("VvfpStoryProbeCustomPending", self.story.n) == 0
        return delivered


def _custom_event(story) -> None:
    event = Event(title="The Long Night", text="The stars went out.")
    event.game = story.n
    story.proc.write(EVENT_BUF, event.pack())


@emulated
class OpeningSequenceTests(unittest.TestCase):
    def _new_village(self, game):
        if not have_stock(game):
            self.skipTest(f"stock {game} is not in inputs/")
        story = Story(game)
        trigger = Trigger(story)
        trigger.counter = 0                       # a new tribe: no island event yet
        return story, trigger

    def test_a_custom_event_bought_at_the_start_comes_third(self):
        """Queued at village start (the purchase's own path), the first two
        island events are the game's own and the custom event is the third."""
        for game in GAMES:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                story, trigger = self._new_village(game)
                _custom_event(story)
                self.assertEqual(story.proc.export("VvfpStoryProbeQueueCustom", story.n, EVENT_BUF, 0), 1)
                seen = []
                for _ in range(3):
                    seen.append(trigger.fire())
                    story.proc.export("VvfpStoryInstall", story.n)       # the companion's frame
                first = "visitor" if game in ("vv1", "vv2") else "stock island event"
                self.assertEqual(seen, [first, "stock island event", "custom"])
                self.assertEqual(trigger.counter, 3, "the game counted each of the three")
                self.assertEqual(story.proc.export("VvfpStoryProbeCustomPending", story.n), 0, "taken once")

    def test_queued_after_the_first_event_it_still_waits_for_the_second(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                story, trigger = self._new_village(game)
                seen = [trigger.fire()]
                _custom_event(story)
                story.proc.export("VvfpStoryProbeSetCustom", story.n, EVENT_BUF, 0)
                seen += [trigger.fire(), trigger.fire()]
                first = "visitor" if game in ("vv1", "vv2") else "stock island event"
                self.assertEqual(seen, [first, "stock island event", "custom"])

    def test_an_established_village_gets_it_at_the_next_event(self):
        """Unchanged once the two opening events are over."""
        for game in GAMES:
            if not have_stock(game):
                continue
            for seen_before in (2, 7):
                with self.subTest(game=game, seen=seen_before):
                    story, trigger = self._new_village(game)
                    trigger.counter = seen_before
                    _custom_event(story)
                    story.proc.export("VvfpStoryProbeSetCustom", story.n, EVENT_BUF, 0)
                    self.assertEqual(trigger.fire(), "custom")
                    self.assertEqual(trigger.counter, seen_before + 1)

    def test_the_opening_rolls_and_draws_stay_the_games_own(self):
        """A New Home / The Lost Children: while the custom event waits, the
        family rolls are the game's own random draws (the first event is the
        game's visitor, the second the game's own roll)."""
        for game in ("vv1", "vv2"):
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                story, trigger = self._new_village(game)
                _custom_event(story)
                story.proc.export("VvfpStoryProbeSetCustom", story.n, EVENT_BUF, 0)
                trigger.fire()
                self.assertEqual(trigger.rolls, [100], "the visitor roll was the game's own")
                trigger.fire()
                self.assertEqual(trigger.rolls, [100, 100], "both family rolls were the game's own")
                trigger.fire()
                self.assertEqual(trigger.rolls, [], "the custom event's own route: no random roll")


@emulated
class EveryModeTests(unittest.TestCase):
    def test_held_in_every_mode_with_the_whole_catalog(self):
        """The hold reads the counter through the trigger's own count sites
        (story_custom.inc, ce_event_counter): with every public patch rendered,
        in all three population modes, those sites are still the stock ones,
        so the event being built as the first or second is never the custom
        one."""
        for game in GAMES:
            if not have_stock(game):
                continue
            for mode in MODES:
                with self.subTest(game=game, mode=mode):
                    story = Story(game, mode, full=True)
                    story.village.put(1, sex="m", years=30, name="Adam")
                    p = story.proc
                    delivered = []
                    for counted in (1, 2, 3):        # the trigger has just counted the event it builds
                        p.put32(events_seen_address(game, story.village.world or 0), counted)
                        _custom_event(story)
                        p.export("VvfpStoryProbeSetCustom", story.n, EVENT_BUF, 0)
                        delivered.append(p.export("VvfpStoryProbeDeliver", story.n, TEXT_BUF, 4096))
                    self.assertEqual(delivered, [0, 0, 1])


# ---------------------------------------------------------------------------
# The purchase at a new village: the lock, and the event made due later
# ---------------------------------------------------------------------------

@emulated
class HeldPurchaseTests(unittest.TestCase):
    def _world(self, proc, game, seen):
        import test_story_cheat_upgrades as part1

        world = part1.LockTests._world(None, proc, game)
        proc.put32(events_seen_address(game, world), seen)
        # A new village: its founders are alive (the game's own population
        # count says so).  An empty village never waits for its opening
        # events (EmptyVillageTests, test_story_empty_village.py).
        proc.stub(POPULATION_COUNT[game], lambda p: (3, 0))
        return world

    def _state(self, proc, game, world):
        import test_story_cheat_upgrades as part1

        return [proc.read(base + off, size) for base, off, size in part1.LockTests.STATE[game](world)]

    def test_bought_at_the_start_it_keeps_the_lock_without_bringing_the_first_event_forward(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            n = int(game[2:])
            with self.subTest(game=game):
                proc = Process(render(game, "collection_progression"), TEST_DLL)
                world = self._world(proc, game, 0)
                untouched = self._state(proc, game, world)
                _write_event(proc, n)
                self.assertEqual(proc.export("VvfpStoryProbeQueueCustom", n, EVENT_BUF, 0), 1)
                self.assertEqual(self._state(proc, game, world), untouched,
                                 "the island event's own schedule is left as the game set it")
                self.assertEqual(proc.export("VvfpStoryProbePending", n), 0)
                self.assertEqual(proc.export("VvfpStoryProbeCustomHeld"), 1)
                # The lock: one island event at a time, as with any queued event.
                self.assertEqual(proc.export("VvfpStoryPickPending", n), 1)
                self.assertEqual(proc.export("VvfpStoryPickIslandEvent", n, 0), 0)
                self.assertIn("already queued", proc.messages[-1])
                self.assertEqual(proc.export("VvfpStoryCustomIslandEvent", n, 0), 0)
                self.assertIn("already queued", proc.messages[-1])

    def test_after_the_second_opening_event_it_is_made_due_as_the_purchase_does(self):
        import test_story_cheat_upgrades as part1

        for game in GAMES:
            if not have_stock(game):
                continue
            n = int(game[2:])
            with self.subTest(game=game):
                proc = Process(render(game, "collection_progression"), TEST_DLL)
                world = self._world(proc, game, 0)
                _write_event(proc, n)
                proc.export("VvfpStoryProbeQueueCustom", n, EVENT_BUF, 0)
                untouched = self._state(proc, game, world)
                proc.put32(events_seen_address(game, world), 1)           # the first opening event
                proc.export("VvfpStoryInstall", n)
                self.assertEqual(self._state(proc, game, world), untouched, "still waiting")
                self.assertEqual(proc.export("VvfpStoryProbeCustomHeld"), 1)
                proc.put32(events_seen_address(game, world), 2)           # the second
                proc.export("VvfpStoryInstall", n)
                self.assertEqual(proc.export("VvfpStoryProbeCustomHeld"), 0)
                self.assertEqual(proc.export("VvfpStoryProbePending", n), 1, "made due")
                bought = Process(render(game, "collection_progression"), TEST_DLL)
                bought_world = self._world(bought, game, 2)
                part1.LockTests._purchase(None, bought, game, bought_world)
                self.assertEqual(self._state(proc, game, world), self._state(bought, game, bought_world),
                                 "exactly the Island Event purchase's own writes")
                # Made due once: later frames write nothing more.
                proc.put32(world + {"vv1": 0xA300, "vv2": 0x2EAE0, "vv3": 0x12EF4, "vv4": 0x170E0,
                                    "vv5": 0x17D3C}[game], CLOCK + 36000)
                after = self._state(proc, game, world)
                proc.export("VvfpStoryInstall", n)
                self.assertEqual(self._state(proc, game, world), after)
                self.assertEqual(proc.export("VvfpStoryProbeCustomPending", n), 1, "still queued")

    def test_the_time_skip_notice_is_not_held(self):
        """Not an island event (its count is taken back): armed as before."""
        for game in ("vv3", "vv4", "vv5"):
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                from test_story_time_skip import TimeSkipHost, island_ready, notice, run_skip, tick

                story = Story(game)
                island_ready(story)
                story.proc.put32(events_seen_address(game, story.village.world or 0), 0)
                host = TimeSkipHost(story, 6)
                at = run_skip(story, host, 6)
                tick(story, at + 100)
                self.assertEqual(notice(story)["armed"], 1)
                self.assertEqual(story.proc.export("VvfpStoryProbePending", story.n), 1)
                self.assertEqual(story.proc.export("VvfpStoryProbeCustomHeld"), 0)


def _write_event(proc, n):
    event = Event(title="The Long Night", text="The stars went out.")
    event.game = n
    proc.write(EVENT_BUF, event.pack())


if __name__ == "__main__":
    unittest.main()
