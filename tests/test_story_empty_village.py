"""A Custom Island Event for a village where everyone has died (all five games).

The owner (2026-10-21): "allow Custom Island Events to be bought and
triggered when everyone is dead (so the player can add new villagers)".

native/vvfp_story_upgrades/story_empty_village.inc.  Each game's island-event
trigger does nothing while the game's own population count is 0, and the
purchase refused a village with no living adult; New Believers' selector also
returns before its delivery site when no stock event is possible.

* StockTests read the five stock executables: the count call each trigger
  makes and the skip after it, the routine between the villager draw and the
  age check whose value the stub hands on, the point the stub resumes at, and
  New Believers' selector exit.
* EmptyTriggerTests run each game's real trigger (the stock code as the
  patcher renders it, all three population modes, and 256 Villagers in the
  three games that have it) with the game's count answering 0: a queued plain
  custom event is delivered without any villager drawn, the game reschedules
  and counts it; with nothing queued, a question, or (A New Home / The Lost
  Children) before the first island event, the empty village waits exactly as
  stock; a living village is unchanged.
* SelectorTests run New Believers' selector exit for real.
* PurchaseTests: a plain event may be bought for an empty village and is
  made due at once (an empty village never has its opening events); a
  question is refused with its reason; someone alive but no adult is still
  refused.
* ArrivalTests: the new villagers, the food and tech, and the skeletons of an
  all-dead village, through the engine and through the trigger end to end.
"""
from __future__ import annotations

import struct
import unittest

import test_story_custom_island_event as tsc
from story_custom_fixtures import Choice, Outcome
from test_story_custom_island_event import (  # noqa: E402
    EVENT_BUF,
    HAVE_EMULATOR,
    MODES,
    TEXT_BUF,
    Event,
    Spawn,
    Story,
    emulated,
    events_seen_address,
    have_stock,
    stock_path,
)
from test_story_opening_events import CLOCK, POPULATION_COUNT, Trigger  # noqa: E402

try:
    import pefile
    from capstone import CS_ARCH_X86, CS_MODE_32, Cs

    HAVE_CAPSTONE = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_CAPSTONE = False

GAMES = ("vv1", "vv2", "vv3", "vv4", "vv5")
CHOICE_BUF = EVENT_BUF + 0x2C000 if HAVE_EMULATOR else 0

# (the count call, the count routine, where it skips to, the routine between
#  the draw and the age check, the register it is kept in, the resume point)
SITES = {
    "vv1": (0x4237CB, 0x41CF90, 0x423ABE, 0x4237E7, 0x41D110, "edi", 0x423816),
    "vv2": (0x42EEDB, 0x425860, 0x42F1D4, 0x42EEF7, 0x426110, "edi", 0x42EF26),
    "vv3": (0x468743, 0x45E8F0, 0x4688DF, 0x468761, 0x402200, "ebp", 0x468798),
    "vv4": (0x43FA4E, 0x467610, 0x43FC0E, 0x43FA7A, 0x416EB0, "ebp", 0x43FA9B),
    "vv5": (0x4426FB, 0x4713F0, 0x44285F, 0x442739, 0x417650, "ebp", 0x44275A),
}


def _disassembler(game):
    if not HAVE_CAPSTONE:
        raise unittest.SkipTest("capstone/pefile not installed")
    if not have_stock(game):
        raise unittest.SkipTest(f"stock {game} is not in inputs/")
    pe = pefile.PE(str(stock_path(game)))
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    base = pe.OPTIONAL_HEADER.ImageBase

    def ins(va):
        i = next(md.disasm(pe.get_data(va - base, 16), va))
        return f"{i.mnemonic} {i.op_str}".strip(), i.size
    return ins


class StockTests(unittest.TestCase):
    def test_each_trigger_skips_while_the_games_own_count_is_0(self):
        for game, (site, count, skip, between_at, between, keep, resume) in SITES.items():
            with self.subTest(game=game):
                ins = _disassembler(game)
                text, size = ins(site)
                self.assertEqual(text, f"call 0x{count:x}")
                text2, size2 = ins(site + size)
                self.assertEqual(text2, "test eax, eax")
                self.assertEqual(ins(site + size + size2)[0], f"je 0x{skip:x}")
                self.assertTrue(ins(site - 2)[0] == "mov ecx, edi" or ins(site - 5)[0].startswith("mov ecx, 0x"),
                                "the counted object is loaded just before the call")

    def test_the_routine_between_the_draw_and_the_check_and_the_resume_point(self):
        for game, (site, count, skip, between_at, between, keep, resume) in SITES.items():
            with self.subTest(game=game):
                ins = _disassembler(game)
                self.assertEqual(ins(between_at)[0], f"call 0x{between:x}")
                after = between_at + 5
                # the draw's own checks may sit between the call and the move
                moves = []
                for _ in range(3):
                    text, size = ins(after)
                    moves.append(text)
                    after += size
                self.assertIn(f"mov {keep}, eax", moves)
                self.assertEqual(ins(resume)[0], "push 0x64", "the trigger's first family / event roll")

    def test_new_believers_selector_exit(self):
        ins = _disassembler("vv5")
        self.assertEqual(ins(0x4188E5)[0], "test edi, edi")
        self.assertEqual(ins(0x4188E7)[0], "je 0x4189c5")
        self.assertEqual([ins(a)[0] for a in (0x4188ED, 0x4188EF, 0x4188F1, 0x4188F6)],
                         ["push 1", "push 0x2f", "mov ecx, 0x4db358", "call 0x413450"])
        self.assertEqual([ins(a)[0] for a in (0x4188FB, 0x4188FD, 0x4188FF, 0x418904)],
                         ["push 1", "push 0x30", "mov ecx, 0x4db358", "call 0x413450"])
        self.assertEqual(ins(0x41895B)[0], "mov eax, dword ptr [esi*4 + 0x4dc850]")


# ---------------------------------------------------------------------------
# The trigger, with everyone dead
# ---------------------------------------------------------------------------

def _render_256(game, mode):
    ids = [f"{game}_origins_village_wide_upgrades", f"{game}_story_cheat_upgrades", f"{game}_population_256"]
    data, _ = tsc.patcher.render_patched_bytes(stock_path(game), tsc._builds()[game], mode, ids)
    return bytes(data)


class _Empty:
    """One game's trigger (test_story_opening_events.Trigger) in a village
    whose two villagers are skeletons, the game's count answering 0."""

    def __init__(self, testcase, game, mode="collection_progression", counter=5, *, pop256=False):
        if not have_stock(game):
            testcase.skipTest(f"stock {game} is not in inputs/")
        if pop256:
            original = tsc.render
            tsc.render = _render_256
            try:
                self.story = Story(game, mode)
            finally:
                tsc.render = original
        else:
            self.story = Story(game, mode)
        self.trigger = Trigger(self.story)
        p = self.story.proc
        v = self.story.village
        v.put(1, sex="m", years=30, name="Adam", health=0)
        v.put(2, sex="f", years=30, name="Bea", health=0)
        self.population = [0]
        p.stub(POPULATION_COUNT[game], lambda q: (self.population[0], 0))
        self.draws = []
        picker, pop = Trigger.SPEC[game]["picker"]
        drawn = 1 if game in ("vv1", "vv2", "vv3") else v.record(1)

        def draw(q):
            self.draws.append(1)
            return drawn, pop
        p.stub(picker, draw)
        self.trigger.counter = counter
        self.game = game
        self.n = self.story.n

    def queue(self, event=None):
        event = event or Event(title="The Long Night", text="The stars went out.")
        event.game = self.n
        self.story.proc.write(EVENT_BUF, event.pack())
        self.story.proc.export("VvfpStoryProbeSetCustom", self.n, EVENT_BUF, 0)

    @property
    def countdown(self):
        return self.story.proc.u32(self.trigger.world + Trigger.SPEC[self.game]["countdown"])

    def run_waiting(self):
        """The trigger once with the event due, up to the skip its count leads
        to (where it leaves, as stock, with nothing built); returns what it
        built."""
        p = self.story.proc
        g = Trigger.SPEC[self.game]
        self.trigger.built.clear()
        p.put32(self.trigger.world + g["countdown"], CLOCK)
        p.set_reg("esi", self.trigger.this)
        p.set_reg("ebx", 0)
        p.set_reg("esp", tsc.HEAP + 0x3000000)
        p.run(g["start"], SITES[self.game][2])
        return list(self.trigger.built)


@emulated
class EmptyTriggerTests(unittest.TestCase):
    def test_a_queued_custom_event_reaches_an_empty_village_in_every_mode(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            for mode in MODES:
                with self.subTest(game=game, mode=mode):
                    e = _Empty(self, game, mode)
                    e.queue()
                    self.assertEqual(e.trigger.fire(), "custom")
                    self.assertEqual(e.draws, [], "no villager is drawn: there is none")
                    self.assertEqual(e.trigger.counter, 6, "the game counted its island event")
                    self.assertGreater(e.countdown, CLOCK, "the game rescheduled the next one")
                    self.assertEqual(e.story.proc.export("VvfpStoryProbeCustomPending", e.n), 0)

    def test_with_256_villagers(self):
        for game in ("vv3", "vv4", "vv5"):
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                e = _Empty(self, game, pop256=True)
                e.queue()
                self.assertEqual(e.trigger.fire(), "custom")
                self.assertEqual(e.draws, [])

    def test_nothing_queued_the_empty_village_waits_as_stock(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                e = _Empty(self, game)
                self.assertEqual(e.run_waiting(), [])
                self.assertEqual(e.countdown, CLOCK, "not rescheduled, as stock")
                self.assertEqual((e.draws, e.trigger.counter), ([], 5))

    def test_a_question_waits_it_needs_a_living_villager(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                e = _Empty(self, game)
                p = e.story.proc
                event = Event(title="A Fork", text="Which way?")
                event.game = e.n
                p.write(EVENT_BUF, event.pack())
                choice = Choice(labels=("Left", "Right"),
                                outcomes=([Outcome(1, Event(title="", text="Left."))],
                                          [Outcome(1, Event(title="", text="Right."))]))
                p.write(CHOICE_BUF, choice.pack())
                p.export("VvfpStoryProbeSetChoice", e.n, EVENT_BUF, CHOICE_BUF, 0)
                self.assertEqual(e.run_waiting(), [])
                self.assertEqual(p.export("VvfpStoryProbeCustomPending", e.n), 1, "still queued")

    def test_a_new_home_and_the_lost_children_keep_their_first_visitor(self):
        for game in ("vv1", "vv2"):
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                e = _Empty(self, game, counter=0)
                e.queue()
                self.assertEqual(e.run_waiting(), [])
                self.assertEqual(e.story.proc.export("VvfpStoryProbeCustomPending", e.n), 1)

    def test_an_empty_village_does_not_wait_for_its_opening_events(self):
        """It can never have them: the trigger does nothing while it is empty."""
        for game in GAMES:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                e = _Empty(self, game, counter=1)
                e.queue()
                self.assertEqual(e.trigger.fire(), "custom")
                self.assertEqual(e.trigger.counter, 2)

    def test_a_living_village_is_unchanged(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                e = _Empty(self, game)
                e.population[0] = 4
                e.story.village.put(1, sex="m", years=30, name="Adam")
                e.queue()
                self.assertEqual(e.trigger.fire(), "custom")
                self.assertEqual(len(e.draws), 1, "the game's own draw, as before")
                e.trigger.counter = 1                  # opening events still hold it
                e.queue()
                self.assertEqual(e.trigger.fire(), "stock island event")

    def test_new_villagers_arrive_through_the_trigger(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                e = _Empty(self, game)
                e.queue(Event(title="The Long Night", text="The stars went out.",
                              spawns=[Spawn(count=2, sex=1), Spawn(count=1, sex=2)]))
                self.assertEqual(e.trigger.fire(), "custom")
                made = [i for i, _, _ in e.story.creations]
                self.assertEqual(len(made), 3)
                self.assertFalse({1, 2} & set(made), "the skeletons keep their records")
                L = e.story.village.L
                for i in made:
                    self.assertEqual(e.story.village.byte(i, L["active"]), 1)
                    self.assertGreater(e.story.village.i32(i, L["health"]), 0)


@emulated
class SelectorTests(unittest.TestCase):
    """New Believers' selector 0x418870 from its exit test 0x4188E5."""

    def _run(self, queued, until):
        e = _Empty(self, "vv5")
        p = e.story.proc
        trophies = []
        p.stub(0x413450, lambda q: (trophies.append((q.reg("ecx"), q.arg(0), q.arg(1))) or 0, 8))
        if queued:
            e.queue()
        p.set_reg("edi", 0)
        p.set_reg("esi", 0x77)
        p.set_reg("esp", tsc.HEAP + 0x3000000)
        p.run(0x4188E5, until)
        return e, p, trophies

    def test_no_stock_event_possible_presents_the_custom_event(self):
        e, p, trophies = self._run(True, 0x418962)
        self.assertEqual(p.reg("eax"), p.export("VvfpStoryProbeObject"))
        self.assertEqual(p.reg("esi"), 1)
        self.assertEqual(trophies, [(0x4DB358, 0x2F, 1), (0x4DB358, 0x30, 1)], "as the stock path")
        self.assertEqual(p.export("VvfpStoryProbeCustomPending", 5), 0)

    def test_nothing_queued_leaves_as_stock(self):
        e, p, trophies = self._run(False, 0x4189C5)
        self.assertEqual(trophies, [])


# ---------------------------------------------------------------------------
# Buying it
# ---------------------------------------------------------------------------

def _island_state(proc, game, world):
    """What the Island Event purchase needs (test_story_cheat_upgrades
    LockTests._world), on the village's own world."""
    if game == "vv1":
        proc.put32(world + 0xA300, CLOCK + 36000)
        proc.stub(0x402F70, lambda p: (CLOCK, 0))
    elif game == "vv2":
        proc.put32(world + 0x2EAE0, CLOCK + 36000)
        proc.stub(0x403200, lambda p: (CLOCK, 0))
    elif game == "vv3":
        manager = proc.alloc(0x13000)
        proc.put32(0x4B309C, manager)
        proc.write(0x6E0050, b"\0")
        proc.stub(0x403330, lambda p: (CLOCK, 0))
    elif game == "vv4":
        proc.put32(world + 0x170E0, CLOCK + 36000)
        proc.write(0x728B04, bytes(12))
        proc.stub(0x403750, lambda p: (CLOCK, 0))
    else:
        proc.put32(world + 0x17D3C, CLOCK + 36000)
        proc.put32(0x51D388, 0)


@emulated
class PurchaseTests(unittest.TestCase):
    def _story(self, game):
        if not have_stock(game):
            self.skipTest(f"stock {game} is not in inputs/")
        return Story(game)

    def test_a_plain_event_may_be_bought_for_an_empty_village(self):
        """The game's own count runs for real over a village with nobody in it."""
        for game in GAMES:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                story = self._story(game)
                self.assertIsNone(story.refusal(Event(spawns=[Spawn(count=3)], food_op=1, food_amount=100)))
                story.village.put(3, sex="m", years=40, name="Bones", health=0)
                self.assertIsNone(story.refusal(Event(spawns=[Spawn()])), "skeletons are not alive")

    def test_someone_alive_but_no_adult_is_still_refused(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                story = self._story(game)
                story.village.put(1, sex="m", years=5, name="Kid")
                self.assertIn("living adult", story.refusal(Event()) or "")

    def test_a_question_is_refused_with_its_reason(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                story = self._story(game)
                p = story.proc
                p.export("VvfpStoryProbeChoiceCap", 1)
                event = Event(title="A Fork", text="Which way?")
                event.game = story.n
                p.write(EVENT_BUF, event.pack())
                choice = Choice(labels=("Left", "Right"),
                                outcomes=([Outcome(1, Event(title="", text="Left."))],
                                          [Outcome(1, Event(title="", text="Right."))]))
                p.write(CHOICE_BUF, choice.pack())
                at = p.export("VvfpStoryProbeChoiceRefusal", story.n, EVENT_BUF, CHOICE_BUF)
                self.assertNotEqual(at, 0)
                self.assertIn("nobody to ask a question", p.cstring(at))

    def test_the_first_island_event_rule_stays(self):
        for game in ("vv1", "vv2"):
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                story = self._story(game)
                story.proc.put32(events_seen_address(game, story.village.world), 0)
                self.assertIn("first island event", story.refusal(Event()) or "")

    def test_bought_for_an_empty_new_village_it_is_made_due_at_once(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                story = self._story(game)
                p = story.proc
                world = story.village.world
                _island_state(p, game, world)
                p.put32(events_seen_address(game, world or 0), 1)
                event = Event(spawns=[Spawn(count=2)])
                event.game = story.n
                p.write(EVENT_BUF, event.pack())
                self.assertEqual(p.export("VvfpStoryProbeQueueCustom", story.n, EVENT_BUF, 0), 1)
                self.assertEqual(p.export("VvfpStoryProbeCustomHeld"), 0)
                self.assertEqual(p.export("VvfpStoryProbePending", story.n), 1, "made due")

    def test_held_by_the_opening_events_then_everyone_dies(self):
        """Bought in a new village (held), then the last villager dies: the
        companion's frame makes it due, since the opening events can no
        longer come."""
        for game in GAMES:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                story = self._story(game)
                p = story.proc
                world = story.village.world
                _island_state(p, game, world)
                alive = [2]
                p.stub(POPULATION_COUNT[game], lambda q: (alive[0], 0))
                p.put32(events_seen_address(game, world or 0), 1)
                event = Event(spawns=[Spawn(count=2)])
                event.game = story.n
                p.write(EVENT_BUF, event.pack())
                self.assertEqual(p.export("VvfpStoryProbeQueueCustom", story.n, EVENT_BUF, 0), 1)
                self.assertEqual(p.export("VvfpStoryProbeCustomHeld"), 1)
                p.export("VvfpStoryInstall", story.n)
                self.assertEqual(p.export("VvfpStoryProbePending", story.n), 0, "still waiting")
                alive[0] = 0
                p.export("VvfpStoryInstall", story.n)
                self.assertEqual(p.export("VvfpStoryProbeCustomHeld"), 0)
                self.assertEqual(p.export("VvfpStoryProbePending", story.n), 1, "made due")


# ---------------------------------------------------------------------------
# What arrives
# ---------------------------------------------------------------------------

@emulated
class ArrivalTests(unittest.TestCase):
    def test_new_villagers_food_and_tech_in_an_empty_village_every_mode(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            for mode in MODES:
                with self.subTest(game=game, mode=mode):
                    story = Story(game, mode)
                    ok, r, text = story.apply(Event(spawns=[Spawn(count=3, sex=2, age=500)],
                                                    food_op=1, food_amount=250, tech_op=1, tech_amount=40))
                    self.assertEqual((r["born"], r["no_room_spawns"], r["refused"]), (3, 0, 0))
                    self.assertEqual(r["food_after"] - r["food_before"], 250)
                    self.assertEqual(r["tech_after"] - r["tech_before"], 40)
                    self.assertEqual(len(story.creations), 3)

    def test_an_all_dead_village_with_skeletons(self):
        from test_story_maker_additions import REVIVE, STOP, record, stub_clock

        for game in GAMES:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                story = Story(game)
                story.order = []
                stub_clock(story)
                record(story, *STOP[game])
                v = story.village
                bodies = []
                for i, name in ((0, "Ana"), (3, "Bo"), (5, "Cy")):
                    v.put(i, sex="f", years=30, name=name, health=0)
                    v.proc.write(v.record(i) + REVIVE[game]["sick"], b"\1")
                    bodies.append(i)
                revive = (3, v.identity(3), 70, 1)
                ok, r, _ = story.apply(Event(revives=[revive], spawns=[Spawn(count=2)]))
                self.assertEqual((r["revived"], r["born"]), (1, 2))
                self.assertEqual(v.i32(3, REVIVE[game]["health"]), 70)
                made = [i for i, _, _ in story.creations]
                self.assertFalse(set(bodies) & set(made), "no body's record is taken")
                self.assertEqual(v.i32(0, REVIVE[game]["health"]), 0, "the others stay skeletons")


if __name__ == "__main__":
    unittest.main()
