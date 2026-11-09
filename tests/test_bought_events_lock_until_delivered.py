"""Bought island events and barrels: never sold twice for one delivery, never locked for good,
kept across a quit, and gone with a village that is started over (the owner, 2026-11-09:
"Yes fix the issues!!!", after the #736 audit).

1. A bought island event is ON ITS WAY UNTIL THE GAME'S TRIGGER DELIVERS IT.  A New Home, The
   Lost Children and The Tree of Life without its token read their lock as "the island timer due
   within the five seconds the purchase gave it"; The Secret City released its flag (0x6E0050) at
   its due second.  The Tech screen pauses the game, so an event bought there stays due,
   undelivered, while the screen is open: five seconds later the lock read as delivered and a
   second Origins Island Event, Pick or Custom Island Event could be sold -- two charges, one
   event.  The keeper every Origins companion already runs (native/shared/island_timer_keep.h)
   knows a bought event from its purchase (its write of the timer) until the trigger's own write
   for it; the Tech menu's Island Event row (each companion's row_block_reason) and the Story /
   Cheat Upgrades' lock (through the host table: story_bought_on_its_way) now ask it.
2. AN EMPTY VILLAGE IS NEVER LOCKED FOR GOOD.  The trigger does nothing while nobody lives in the
   village, so an island event bought there never comes.  There, and only for a plain Custom
   Island Event (the one event that reaches an empty village), the custom event takes the waiting
   event's place, and it is not charged when that one was bought (story_custom_ui.inc
   ce_purchase_locked).  A barrel waiting in The Tree of Life or New Believers is never replaced.
3. THE TREE OF LIFE: AN ISLAND EVENT BOUGHT BEFORE A BARREL SURVIVES A QUIT WITH IT.  The Barrel's
   cue puts the Island Event back on the shared timer only while its process-only token
   (0x728B08) is set; the token is now kept in the Barrel's own file and set again with it.
4. START OVER (OR THE TRIBE DELETED) TAKES ITS PURCHASES WITH IT.  A barrel or bought island event
   held in the executable's memory came to the new village started in the same slot; "VVFP Save
   Reset.dll" now tells the Origins companion (VvfpOriginsVillageReset), which clears them for the
   village in memory -- no refund: the village that paid is gone, the new one never paid.

Everything here runs the shipped bytes: each game's executable as the patcher renders it, with the
test builds of the keeper and the Story / Cheat Upgrades companion, or the shipped Origins
companions, mapped beside it in the emulator.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from test_story_cheat_upgrades import (  # noqa: E402
    CLOCK,
    HAVE_EMULATOR,
    TEST_DLL,
    LockTests,
    have_stock,
    process,
    render,
)

if HAVE_EMULATOR:
    from story_emulator import HEAP, Process  # noqa: E402
    from test_bought_events_keep_natural_timer import (  # noqa: E402
        DLL as KEEPER_DLL,
        HOUR,
        OTHER_ROSTER,
        ROSTER,
        Village as KeeperVillage,
    )
else:  # pragma: no cover - environment dependent
    KEEPER_DLL = ROOT / "tests" / "test_dlls" / "VVFP Island Event Timer.test.dll"

LOCKED = ("vv1", "vv2", "vv3", "vv4")       # the games whose lock went by the clock
GAMES = ("vv1", "vv2", "vv3", "vv4", "vv5")
TIMER = {"vv1": 0xA300, "vv2": 0x2EAE0, "vv3": 0x12EF4, "vv4": 0x170E0, "vv5": 0x17D3C}
CLOCKS = {"vv1": 0x402F70, "vv2": 0x403200, "vv3": 0x403330, "vv4": 0x403750}
ORIGINS_COMPANION = {
    "vv1": ROOT / "assets/origins/VVFP VV1 Origins Icons.dll",
    "vv2": ROOT / "assets/origins/VVFP VV2 Origins Icons.dll",
    "vv3": ROOT / "data/candidates/VVFP VV3 Full Mastery Candidate.dll",
    "vv4": ROOT / "assets/origins/VVFP VV4 Origins Icons.dll",
    "vv5": ROOT / "data/candidates/VVFP VV5 Task9 Origins Icons.dll",
}


def _skip_without(path: Path):
    def wrap(cls):
        return unittest.skipUnless(HAVE_EMULATOR, "capstone/unicorn/pefile not installed")(
            unittest.skipUnless(path.is_file(), "test builds are not in the release source archive")(cls))
    return wrap


def _source(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. The keeper: on its way from the purchase until the trigger delivers it
# ---------------------------------------------------------------------------

@_skip_without(KEEPER_DLL)
class TheKeeperKnowsUntilTheTriggerDelivers(unittest.TestCase):
    """native/shared/island_timer_keep.h itk_on_its_way, the answer every island-event lock asks."""

    @staticmethod
    def on(v) -> int:
        return v.proc.export("ItkProbeOnItsWay")

    def test_the_origins_purchase_is_on_its_way_while_the_tech_screen_stays_open(self):
        for game in LOCKED:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                v = KeeperVillage(game)
                v.set_timer(CLOCK + 3 * HOUR)
                self.assertEqual(self.on(v), 0, "nothing bought")
                v.buy()                                  # the Origins Island Event's own code
                self.assertEqual(self.on(v), 1)
                v.now += 60                              # the paused Tech screen stays open a minute
                self.assertEqual(self.on(v), 1, "still undelivered")
                # What the old locks read then: due more than five seconds ago is not "within the window".
                self.assertGreater((v.timer() - v.now) & 0xFFFFFFFF, 5)
                self.assertTrue(v.tick(), "the screen closed: the game's trigger runs it")
                self.assertEqual(self.on(v), 0, "delivered: the lock lifts")
                self.assertEqual(v.timer(), CLOCK + 3 * HOUR, "and the natural event keeps its time")

    def test_a_story_arm_is_on_its_way_the_same(self):
        for game in LOCKED:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                v = KeeperVillage(game)
                v.set_timer(CLOCK + 3 * HOUR)
                v.story_arm(v.now + 5)                   # Pick / Custom Island Event / the notice
                v.now += 600
                self.assertEqual(self.on(v), 1)
                self.assertTrue(v.tick())
                self.assertEqual(self.on(v), 0)

    def test_an_empty_village_keeps_it_on_its_way_until_someone_lives(self):
        """The trigger does nothing while the game's own count is 0 -- not even reschedule -- so the
        event stays on its way (a second one is never sold for it); the Story / Cheat Upgrades let a
        Custom Island Event take its place there (EmptyVillageCustomTakesThePlace)."""
        for game in LOCKED:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                v = KeeperVillage(game)
                v.set_timer(CLOCK + 3 * HOUR)
                v.buy()
                v.now += 60
                p = v.proc
                owner = v._helpers()
                count = {"vv1": 0x41CF90, "vv2": 0x425860, "vv3": 0x45E8F0, "vv4": 0x467610}[game]
                p.stub(count, lambda q: (0, 0))           # everyone has died
                bought = v.timer()
                for _ in range(3):
                    p.set_reg("esp", HEAP + 0x3000000)
                    p.set_reg("esi", owner)
                    p.set_reg("ebx", 0)
                    p.set_reg("eax", v.now)
                    p.set_reg(v.spec["obj_reg"], v.obj)
                    p.run(v.spec["trigger"], v.spec["skip"])
                    self.assertEqual(v.timer(), bought, "the trigger waited, as stock")
                    self.assertEqual(self.on(v), 1)
                self.assertTrue(v.tick(), "someone lives again: the trigger runs it")
                self.assertEqual(self.on(v), 0)

    def test_everyone_dying_after_the_purchase_keeps_it_on_its_way(self):
        """Codex on #745: the purchase is tied to its village by the save slot and the keeper's record, not
        by who survives.  Bought while villagers live, then everyone dies (the roster callbacks skip the
        dead): still on its way, in memory and after a relaunch into the empty village."""
        nobody = [0] * 256
        for game in GAMES:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                v = KeeperVillage(game)
                v.set_timer(CLOCK + 3 * HOUR)
                v.buy()
                v.village(1, ROSTER[:2] + [0] * 254)      # most have died: two survivors
                self.assertEqual(self.on(v), 1)
                v.village(1, nobody)                       # everyone has died
                self.assertEqual(self.on(v), 1)
                v.proc.export("ItkProbeSaved", 1)          # saved, then the game closed
                v.proc.export("ItkProbeSession", 1)
                self.assertEqual(self.on(v), 0, "a new process: nothing in memory yet")
                v.now += 60
                _run_trigger(v, 0)                         # the empty village's trigger, due, runs nothing
                self.assertEqual(self.on(v), 1, "its file is this slot's: on its way again")

    def test_never_another_villages_and_start_over_forgets_it(self):
        for game in LOCKED:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                v = KeeperVillage(game)
                v.set_timer(CLOCK + 3 * HOUR)
                v.buy()
                v.village(1, OTHER_ROSTER)
                self.assertEqual(self.on(v), 0, "another village in the slot")
                v.village(2, ROSTER)
                self.assertEqual(self.on(v), 0, "another slot")
                v.village(1, ROSTER)
                self.assertEqual(self.on(v), 1)
                v.proc.export("ItkProbeVillageReset", 3)
                self.assertEqual(self.on(v), 1, "another slot's tribe deleted: kept")
                v.proc.export("ItkProbeVillageReset", 1)
                self.assertEqual(self.on(v), 0, "Start Over in its slot: gone with the village")


# ---------------------------------------------------------------------------
# 1, 2. The Story / Cheat Upgrades' lock, through the host table
# ---------------------------------------------------------------------------

class _Host:
    """An Origins companion's host table (native/shared/story_bridge.h) of this release: the slot,
    the mask store, the island timer's arming and its "on its way" (`on[0]`)."""

    def __init__(self, proc, n: int, *, size: int = 40):
        self.on = [0]
        code = proc.alloc(0x100)
        proc.write(code, b"\xC3" * 0x60)
        proc.stub(code, lambda p: (1, 0))
        proc.stub(code + 0x10, lambda p: (0, 4))
        proc.stub(code + 0x20, lambda p: (1, 8))
        proc.stub(code + 0x30, lambda p: (0, 8))
        proc.stub(code + 0x40, lambda p: (self.on[0], 0))
        table = proc.alloc(0x40)
        proc.write(table, struct.pack("<10I", size, code, code + 0x10, code + 0x20, 0, 0, 0, 0,
                                      code + 0x30, code + 0x40))
        assert proc.export("VvfpStoryAttachHost", n, table) == 1


@_skip_without(TEST_DLL)
class TheStoryLockAsksTheKeeper(unittest.TestCase):
    def _bought_and_left_open(self, game):
        """A pick armed exactly as the Island Event purchase arms it, then the Tech screen left open a
        minute -- with what each game's old lock then read."""
        n = int(game[2:])
        proc = process(game)
        world = LockTests._world(LockTests(), proc, game)
        proc.export("VvfpStoryInstall", n)
        host = _Host(proc, n)
        proc.export("VvfpStoryProbeArm", n, 0, 0)
        host.on[0] = 1                                            # the keeper saw the arm's write
        proc.stub(CLOCKS[game], lambda p: (CLOCK + 60, 0))         # a minute later, still paused
        if game == "vv3":
            proc.write(0x6E0050, b"\0")      # released by its due second (the menu draw, the frame hook)
        if game == "vv4":
            proc.write(0x728B08, b"\0")      # no token (a relaunch, or the Tech menu's retire)
        return proc, world, host, n

    def test_bought_and_still_undelivered_is_still_on_its_way(self):
        for game in LOCKED:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                proc, world, host, n = self._bought_and_left_open(game)
                self.assertEqual(proc.export("VvfpStoryProbePending", n), 1,
                                 "a second Island Event, Pick or Custom Island Event would be sold")
                host.on[0] = 0                                    # the trigger delivered it
                self.assertEqual(proc.export("VvfpStoryProbePending", n), 0, "delivered: the lock lifts")

    def test_a_host_without_the_answer_goes_by_the_timer_as_before(self):
        for game in LOCKED:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                n = int(game[2:])
                proc = process(game)
                LockTests._world(LockTests(), proc, game)
                proc.export("VvfpStoryInstall", n)
                host = _Host(proc, n, size=36)                    # a host built before the entry
                host.on[0] = 1
                proc.export("VvfpStoryProbeArm", n, 0, 0)
                self.assertEqual(proc.export("VvfpStoryProbePending", n), 1, "due within five seconds")
                proc.stub(CLOCKS[game], lambda p: (CLOCK + 3600 * 24, 0))
                if game == "vv3":
                    proc.write(0x6E0050, b"\0")
                if game == "vv4":
                    proc.write(0x728B08, b"\0")
                self.assertEqual(proc.export("VvfpStoryProbePending", n), 0, "its entry is never read")

    def test_new_believers_bits_stay_its_lock(self):
        """New Believers' bits (0x51D388) already last until the delivery (vv5_retire_delivered_island);
        its lock does not ask the keeper, which also holds its Barrel's write."""
        if not have_stock("vv5"):
            self.skipTest("stock executable not present")
        proc = process("vv5")
        world = LockTests._world(LockTests(), proc, "vv5")
        proc.export("VvfpStoryInstall", 5)
        host = _Host(proc, 5)
        host.on[0] = 1
        proc.put32(world + 0x17D3C, CLOCK + 36000)
        proc.put32(world + 0x17D50, CLOCK)
        self.assertEqual(proc.export("VvfpStoryProbePending", 5), 0)


@_skip_without(TEST_DLL)
class ACustomIslandEventIsAvailableAtAllTimes(unittest.TestCase):
    """The owner (2026-11-09): "I want the following available at all times always: Custom Island Events (with
    full functionality) ESPECIALLY THE PARTS THAT BRING NEW VILLAGERS.  These should be a special exception where
    no adult is needed to spawn villagers."  Each game's own trigger, popup and count, as the patcher renders the
    executable; the game's leaf routines (clock, random, sound, builder, picker) are stand-ins."""

    def _empty(self, game, *, living=0, counter=5):
        from test_story_empty_village import _Empty
        e = _Empty(self, game, counter=counter)
        e.population[0] = living
        return e

    def _newcomers(self):
        from story_custom_fixtures import Event, Spawn
        return Event(title="The Long Night", text="Strangers came ashore.", spawns=[Spawn(count=2)])

    def test_an_empty_village_gets_its_newcomers(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                e = self._empty(game)
                e.queue(self._newcomers())
                self.assertEqual(e.trigger.fire(), "custom")
                self.assertEqual(len(e.story.creations), 2, "both newcomers made by the game's own creator")
                self.assertEqual(e.story.proc.export("VvfpStoryProbeCustomPending", e.n), 0)

    def test_nobody_the_trigger_accepts_and_it_still_comes(self):
        """Villagers live, but none the trigger's own draw accepts (A New Home and The Lost Children draw adults
        only; a villager whose age has not caught up never passes): before, the trigger waited for ever."""
        none = {"vv1": -1, "vv2": -1, "vv3": 1, "vv4": 0, "vv5": 0}
        # Codex on #745: with exactly two opening events done (2) the bypass once took the next event for an
        # opening one and returned before asking -- a village of children waited.
        for game, counter in [(g, c) for g in GAMES for c in (2, 5)]:
            if not have_stock(game):
                continue
            with self.subTest(game=game, island_events_seen=counter):
                e = self._empty(game, living=3, counter=counter)
                e.story.village.put(1, sex="m", years=5, name="Keoni")     # a child
                picker, pop = e.trigger.SPEC[game]["picker"]
                e.story.proc.stub(picker, lambda q, v=none[game], pop=pop: (v & 0xFFFFFFFF, pop))
                if game == "vv3":
                    e.story.proc.stub(0x45EE60, lambda q: (0, 4))      # the drawn one is not a live villager
                e.queue(self._newcomers())
                self.assertEqual(e.trigger.fire(), "custom")
                self.assertEqual(len(e.story.creations), 2)

    def test_with_someone_the_trigger_accepts_it_is_the_games_own_draw(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                e = self._empty(game, living=4)
                e.story.village.put(1, sex="m", years=30, name="Adam")
                e.queue(self._newcomers())
                self.assertEqual(e.trigger.fire(), "custom")
                self.assertGreaterEqual(len(e.draws), 1, "the trigger's own draw, as before")

    def test_a_question_still_needs_someone_to_ask(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                e = self._empty(game)
                from story_custom_fixtures import Choice, Event, Outcome
                p = e.story.proc
                from test_story_empty_village import CHOICE_BUF
                from test_story_custom_island_event import EVENT_BUF
                event = Event(title="A Fork", text="Which way?")
                event.game = e.n
                p.write(EVENT_BUF, event.pack())
                choice = Choice(labels=("Left", "Right"),
                                outcomes=([Outcome(1, Event(title="", text="Left."))],
                                          [Outcome(1, Event(title="", text="Right."))]))
                p.write(CHOICE_BUF, choice.pack())
                p.export("VvfpStoryProbeSetChoice", e.n, EVENT_BUF, CHOICE_BUF, 0)
                self.assertEqual(e.run_waiting(), [])

    def test_changes_with_nobody_to_apply_them_to_are_skipped_and_named(self):
        from test_story_custom_island_event import _stories
        from story_custom_fixtures import Event
        for game, story in _stories():
            v = story.village
            v.put(2, sex="m", years=30, name="Gone")
            change = story.change(2, sick=1)
            v.put(2, sex="m", years=30, name="Gone", health=0)       # died before it came
            ok, r, text = story.apply(Event(title="Rain", text="It rained.", food_op=1, food_amount=10,
                                            changes=[change]))
            with self.subTest(game=game):
                self.assertEqual((r["skipped"], r["changed"]), (1, 0))
                flat = text.replace("\n", " ")
                self.assertIn("1 of the chosen villagers were no longer here.", flat)
                self.assertIn("Their changes were skipped: there was nobody to apply them to.", flat)
                self.assertNotEqual(r["food_after"], r["food_before"], "the rest of the event still happens")


@_skip_without(TEST_DLL)
class ACustomIslandEventGoesFirst(unittest.TestCase):
    """story_custom_ui.inc ce_purchase_locked / ce_requeue_tick: a bought or picked island event already on its way
    never stops a Custom Island Event: the custom event comes first, the waiting one right after it, each with its
    own charge."""

    def gate(self, proc, n) -> tuple:
        out = proc.alloc(12)
        proc.export("VvfpStoryProbeCustomGate", n, out)
        return struct.unpack("<3i", proc.read(out, 12))

    def _bought(self, game, *, picked=False):
        n = int(game[2:])
        proc = process(game)
        world = LockTests._world(LockTests(), proc, game)
        proc.export("VvfpStoryInstall", n)
        from test_story_custom_island_event import events_seen_address
        proc.put32(events_seen_address(game, world), 5)          # past its two opening island events
        host = _Host(proc, n)
        if picked:
            proc.export("VvfpStoryProbeArm", n, 0, 0)            # Pick Island Event, armed as bought
        else:
            LockTests._purchase(LockTests(), proc, game, world)  # the Origins Island Event's own code
        host.on[0] = 1                                            # the keeper saw its write
        if game == "vv5":
            proc.put32(world + 0x17D50, CLOCK)
        return proc, world, host, n

    def _deliver_custom(self, proc, n):
        from story_custom_fixtures import Event
        from test_story_custom_island_event import EVENT_BUF, TEXT_BUF
        event = Event(game=n, title="The Long Night", text="The stars went out.")
        proc.write(EVENT_BUF, event.pack())
        self.assertEqual(proc.export("VvfpStoryProbeQueueCustom", n, EVENT_BUF, 0), 1, "never refused")
        self.assertEqual(proc.export("VvfpStoryProbeDeliver", n, TEXT_BUF, 4096), 1, "it comes first")

    def _the_trigger_rescheduled(self, proc, world, host, game):
        """What the game's trigger leaves after running the custom event: the timer hours away, the keeper's
        record delivered, The Secret City's flag released by its frame hook."""
        proc.put32(world + TIMER[game], CLOCK + 36000)
        host.on[0] = 0
        if game == "vv3":
            proc.write(0x6E0050, b"\0")

    def _due_again(self, proc, world, game) -> bool:
        if game == "vv5":
            return proc.u32(world + TIMER[game]) == 0 and bool(proc.u32(0x51D388) & 0x10)
        return proc.u32(world + TIMER[game]) == CLOCK + 5

    def test_a_bought_event_waiting_comes_right_after_it(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                proc, world, host, n = self._bought(game)
                refused, displaces, _ = self.gate(proc, n)
                self.assertEqual((refused, displaces), (0, 1))
                self._deliver_custom(proc, n)
                self._the_trigger_rescheduled(proc, world, host, game)
                proc.export("VvfpStoryInstall", n)                # the next frame
                self.assertTrue(self._due_again(proc, world, game), "the bought event is made due again")
                self.assertEqual(proc.export("VvfpStoryProbePending", n), 1)
                proc.export("VvfpStoryInstall", n)
                self.assertEqual(self.gate(proc, n)[2], 0, "once")

    def test_a_picked_event_waiting_comes_right_after_it(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                proc, world, host, n = self._bought(game, picked=True)
                slot = proc.export("VvfpStoryProbeArmedSlot")
                self._deliver_custom(proc, n)
                self.assertEqual(proc.export("VvfpStoryProbeArmedSlot"), slot, "the pick was not taken")
                self._the_trigger_rescheduled(proc, world, host, game)
                proc.export("VvfpStoryInstall", n)
                self.assertTrue(self._due_again(proc, world, game))
                self.assertEqual(proc.export("VvfpStoryProbeArmedSlot"), slot)

    def test_the_custom_event_is_routed_before_a_pick(self):
        """A New Home, The Lost Children: the family rolls go to the custom event's family while both are armed,
        so the pick's own rolls are not taken by the custom event's run."""
        # A pick of the other family (A New Home's villager encounters, position 15; The Lost Children's family A,
        # position 30), whose roll would answer 0.
        for game, site, position in (("vv1", 0x423818, 15), ("vv2", 0x42EF28, 30)):
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                from story_custom_fixtures import Event
                from test_story_custom_island_event import EVENT_BUF
                n = int(game[2:])
                proc = process(game)
                world = LockTests._world(LockTests(), proc, game)
                from test_story_custom_island_event import events_seen_address
                proc.put32(events_seen_address(game, world), 5)          # past its two opening island events
                proc.export("VvfpStoryInstall", n)
                proc.export("VvfpStoryProbeSetPick", n, position, 0)
                event = Event(game=n, title="The Long Night", text="The stars went out.")
                proc.write(EVENT_BUF, event.pack())
                proc.export("VvfpStoryProbeQueueCustom", n, EVENT_BUF, 0)
                esp = HEAP + 0x3000000
                proc.set_reg("esp", esp)
                proc.put32(esp, 100)
                proc.stub(0x402F10 if game == "vv1" else 0x4031A0, lambda q: (0, 0))
                proc.run(site, site + 5)
                self.assertEqual(proc.reg("eax"), 99, "the island family: the custom event's own")

    def test_one_charge_each(self):
        body = _source("native/vvfp_story_upgrades/vvfp_story_upgrades.c")
        charged = body[body.index("static int story_charged("):]
        charged = charged[:charged.index("\n}\n")]
        self.assertNotIn("waived", charged)
        self.assertIn("if (done) {\n        a->change_tech(CE_AMOUNT_SUBTRACT, price);", charged)
        custom = _source("native/vvfp_story_upgrades/story_custom_ui.inc")
        self.assertNotIn("story_charge_waived", custom)


@_skip_without(TEST_DLL)
class TheEventACustomOneWentAheadOfSurvivesAQuit(unittest.TestCase):
    """Codex on #745: buy an island event, queue a Custom Island Event ahead of it, quit before either came --
    the bought one used to be lost on reload (the waiting purchase lived only in memory).  The queue file now
    keeps it with the custom event (SQ_REQUEUE, story_queue.inc): after the reload the custom event comes, and
    the bought one follows it, charged once (only the custom event's own charge is new)."""

    SQ_CUSTOM, SQ_REQUEUE = 2, 32

    def _story(self, game):
        from test_story_queued_purchases import fresh
        story = fresh(game)
        p = story.proc
        if game == "vv3" and p.u32(0x4B309C) == 0:
            p.put32(0x4B309C, p.alloc(0x13000))
        world = story.village.world or p.u32(0x4B309C)
        if game in CLOCKS:
            p.stub(CLOCKS[game], lambda q: (CLOCK, 0))
        host = _Host(p, story.n)
        return story, world, host

    def _bought(self, story, world, host, game):
        p = story.proc
        host.on[0] = 1                                         # the keeper saw the purchase's write
        p.put32(world + TIMER[game], CLOCK + 5 if game != "vv5" else 0)
        if game == "vv3":
            p.write(0x6E0050, b"\1")
        if game == "vv4":
            p.write(0x728B08, b"\1")
            p.put32(0x728B0C, CLOCK + 5)
        if game == "vv5":
            p.put32(0x51D388, 0x10)
            p.put32(world + 0x17D50, CLOCK)

    def _queue_custom(self, story):
        from story_custom_fixtures import Event
        from test_story_custom_island_event import EVENT_BUF
        event = Event(game=story.n, title="The Long Night", text="The stars went out.")
        story.proc.write(EVENT_BUF, event.pack())
        self.assertEqual(story.proc.export("VvfpStoryProbeQueueCustom", story.n, EVENT_BUF, 0), 1)

    def test_bought_then_a_custom_event_then_a_quit(self):
        from test_story_custom_island_event import TEXT_BUF
        from test_story_queued_purchases import LATE, have, queue_file, session, tick
        for game in GAMES:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                story, world, host = self._story(game)
                self._bought(story, world, host, game)
                self._queue_custom(story)
                tick(story)
                file = queue_file(story)
                self.assertEqual(have(file, story) & (self.SQ_CUSTOM | self.SQ_REQUEUE),
                                 self.SQ_CUSTOM | self.SQ_REQUEUE, "the waiting purchase is in the file")
                story.proc.export("VvfpStoryProbeQueueSaved")   # the quit's save

                again, world2, host2 = self._story(game)       # the next process, the save loaded
                self._bought(again, world2, host2, game)
                session(again, file, LATE)
                tick(again)
                out = again.proc.alloc(12)
                again.proc.export("VvfpStoryProbeCustomGate", again.n, out)
                self.assertEqual(struct.unpack("<3i", again.proc.read(out, 12))[2], again.n,
                                 "the custom event is back, and the bought one waits behind it")
                self.assertEqual(again.proc.export("VvfpStoryProbeDeliver", again.n, TEXT_BUF, 4096), 1,
                                 "the custom event comes first")
                again.proc.put32(world2 + TIMER[game], CLOCK + 36000)  # the trigger's reschedule
                host2.on[0] = 0
                if game == "vv3":
                    again.proc.write(0x6E0050, b"\0")
                tick(again)
                self.assertEqual(again.proc.export("VvfpStoryProbePending", again.n), 1,
                                 "the bought event is made due again: it follows")
                expected = 0 if game == "vv5" else CLOCK + 5
                self.assertEqual(again.proc.u32(world2 + TIMER[game]), expected)

    def test_a_quit_right_after_the_custom_event_came(self):
        """Delivered, the bought one not yet made due again: the file says so, and the next process makes it due."""
        from test_story_custom_island_event import TEXT_BUF
        from test_story_queued_purchases import LATE, have, queue_file, session, tick
        for game in GAMES:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                story, world, host = self._story(game)
                self._bought(story, world, host, game)
                self._queue_custom(story)
                tick(story)
                self.assertEqual(story.proc.export("VvfpStoryProbeDeliver", story.n, TEXT_BUF, 4096), 1)
                tick(story)                                    # the trigger has not rescheduled yet
                file = queue_file(story)
                self.assertEqual(have(file, story) & (self.SQ_CUSTOM | self.SQ_REQUEUE), self.SQ_REQUEUE)
                story.proc.export("VvfpStoryProbeQueueSaved")

                again, world2, host2 = self._story(game)
                again.proc.put32(world2 + TIMER[game], CLOCK + 36000)
                session(again, file, LATE)
                tick(again)
                tick(again)
                self.assertEqual(again.proc.export("VvfpStoryProbePending", again.n), 1, "it follows")


@_skip_without(TEST_DLL)
class ACustomEventBehindABarrelSurvivesAQuit(unittest.TestCase):
    """Codex on #745: The Tree of Life / New Believers -- a Barrel bought, then a Custom Island Event queued, then
    a quit.  The barrel goes first; the custom event is made due right after it (ce_behind_barrel), and the queue
    file now keeps that (SQ_BARREL_FIRST): after the reload the barrel comes, then the custom event at once --
    not at the next natural island event."""

    SQ_CUSTOM, SQ_BARREL_FIRST = 2, 64

    def _story(self, game):
        return TheEventACustomOneWentAheadOfSurvivesAQuit._story(self, game)

    def _barrel(self, story, world, game):
        p = story.proc
        p.put32(world + TIMER[game], 0)                       # the barrel's own write: due now
        if game == "vv4":
            p.write(0x728B04, b"\1")
        else:
            p.put32(0x51D388, 0x04)
            p.put32(world + 0x17D50, CLOCK)

    def test_barrel_then_a_custom_event_then_a_quit(self):
        from story_custom_fixtures import Event
        from test_story_custom_island_event import EVENT_BUF
        from test_story_queued_purchases import LATE, have, queue_file, session, tick
        for game in ("vv4", "vv5"):
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                story, world, host = self._story(game)
                self._barrel(story, world, game)
                event = Event(game=story.n, title="The Long Night", text="The stars went out.")
                story.proc.write(EVENT_BUF, event.pack())
                self.assertEqual(story.proc.export("VvfpStoryProbeQueueCustom", story.n, EVENT_BUF, 0), 1)
                tick(story)
                file = queue_file(story)
                self.assertEqual(have(file, story) & (self.SQ_CUSTOM | self.SQ_BARREL_FIRST),
                                 self.SQ_CUSTOM | self.SQ_BARREL_FIRST)
                story.proc.export("VvfpStoryProbeQueueSaved")

                again, world2, host2 = self._story(game)       # the save loaded: the barrel still on its way
                self._barrel(again, world2, game)
                session(again, file, LATE)
                tick(again)
                self.assertEqual(again.proc.export("VvfpStoryProbeCustomPending", again.n), 1)
                # The barrel comes: the game's trigger presents it and reschedules its next natural event.
                if game == "vv4":
                    again.proc.write(0x728B04, b"\0")
                    again.proc.write(0x728B08, b"\0")             # (its own requeue not counted on here)
                else:
                    again.proc.put32(0x51D388, 0)
                again.proc.put32(world2 + TIMER[game], CLOCK + 36000)
                tick(again)
                self.assertEqual(again.proc.export("VvfpStoryProbePending", again.n), 1,
                                 "the custom event is made due right after the barrel")
                expected = 0 if game == "vv5" else CLOCK + 5
                self.assertEqual(again.proc.u32(world2 + TIMER[game]), expected)


@_skip_without(TEST_DLL)
class ABarrelIsNeverAnIslandEventToPutBack(unittest.TestCase):
    """Codex on #745: The Tree of Life -- a Barrel bought on its own writes the island timer, and the keeper holds
    that write too, so the host's "a bought island event is on its way" said yes: a Custom Island Event bought
    then recorded an island event to put back after itself, and a random one was armed for free.  A Barrel with no
    Island Event token is never an island event (ce_purchase_locked, and the VV4 host entry itself); New
    Believers goes by its island bits (0x30), never the Barrel's (0x04)."""

    def _village(self, game, *, island: bool):
        n = int(game[2:])
        proc = process(game)
        world = LockTests._world(LockTests(), proc, game)
        proc.export("VvfpStoryInstall", n)
        from test_story_custom_island_event import events_seen_address
        proc.put32(events_seen_address(game, world), 5)          # past its two opening island events
        host = _Host(proc, n)
        proc.put32(world + TIMER[game], 0)                        # the Barrel's own write: due now
        host.on[0] = 1                                            # the keeper holds that write
        if game == "vv4":
            proc.write(0x728B04, b"\1")
            if island:
                proc.write(0x728B08, b"\1")                       # an Island Event bought too: its token
                proc.put32(0x728B0C, 0)
        else:
            proc.put32(0x51D388, 0x04 | (0x10 if island else 0))
            proc.put32(world + 0x17D50, CLOCK)
        return proc, world, host, n

    def gate(self, proc, n) -> tuple:
        out = proc.alloc(12)
        proc.export("VvfpStoryProbeCustomGate", n, out)
        return struct.unpack("<3i", proc.read(out, 12))

    def _custom_after_the_barrel(self, proc, world, host, n, game):
        """A custom event queued, the Barrel presented (the trigger reschedules the timer), the custom event made
        due and delivered, the trigger rescheduling again; then two frames."""
        from story_custom_fixtures import Event
        from test_story_custom_island_event import EVENT_BUF, TEXT_BUF
        event = Event(game=n, title="The Long Night", text="The stars went out.")
        proc.write(EVENT_BUF, event.pack())
        self.assertEqual(proc.export("VvfpStoryProbeQueueCustom", n, EVENT_BUF, 0), 1, "never refused")
        if game == "vv4":
            proc.write(0x728B04, b"\0")
            proc.write(0x728B08, b"\0")
        else:
            proc.put32(0x51D388, proc.u32(0x51D388) & ~0x04)
        proc.put32(world + TIMER[game], CLOCK + 36000)
        host.on[0] = 0
        proc.export("VvfpStoryInstall", n)                        # the custom event is made due after it
        self.assertEqual(proc.export("VvfpStoryProbeDeliver", n, TEXT_BUF, 4096), 1, "the custom event came")
        proc.put32(world + TIMER[game], CLOCK + 36000)
        if game == "vv5":
            proc.put32(0x51D388, 0)
        proc.export("VvfpStoryInstall", n)
        proc.export("VvfpStoryInstall", n)

    def test_barrel_only_then_a_custom_event_arms_nothing_more(self):
        for game in ("vv4", "vv5"):
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                proc, world, host, n = self._village(game, island=False)
                self.assertEqual(self.gate(proc, n)[:2], (0, 0), "no island event is waiting")
                self._custom_after_the_barrel(proc, world, host, n, game)
                self.assertEqual(self.gate(proc, n)[2], 0, "nothing recorded to put back")
                self.assertEqual(proc.u32(world + TIMER[game]), CLOCK + 36000, "the game's own next event")
                self.assertEqual(proc.export("VvfpStoryProbePending", n), 0, "no free island event armed")

    def test_barrel_and_a_bought_island_event_then_a_custom_event_the_island_event_follows(self):
        if not have_stock("vv4"):
            self.skipTest("stock executable not present")
        proc, world, host, n = self._village("vv4", island=True)
        self.assertEqual(self.gate(proc, n)[:2], (0, 1), "the bought island event is waiting")
        self._custom_after_the_barrel(proc, world, host, n, "vv4")
        self.assertEqual(proc.u32(world + TIMER["vv4"]), CLOCK + 5, "the bought island event is made due again")
        self.assertEqual(proc.export("VvfpStoryProbePending", n), 1)


# ---------------------------------------------------------------------------
# 1, 2. The Origins companions' own rows ask the keeper too
# ---------------------------------------------------------------------------

class TheTechMenuRowsAskTheKeeper(unittest.TestCase):
    def test_each_island_event_row(self):
        vv1 = _source("native/vv1_origins_icons/vv1_origins_icons.c")   # The Lost Children's too
        self.assertIn("if (row == PENDING_ROW_ISLAND && ((state & STATE_ISLAND_PENDING) != 0 || itk_on_its_way())) {",
                      vv1)
        vv3 = _source("native/vv3_full_mastery_candidate/vv3_full_mastery_candidate.c")
        reason = vv3[vv3.index("static int vv3_row_block_reason("):]
        self.assertLess(reason.index("if (itk_on_its_way()) {\n        return VV3_BLOCK_ALREADY_PENDING;"),
                        reason.index("*(volatile unsigned char *)(UINT_PTR)VV3_ISLAND_PENDING_FLAG = 0;"),
                        "the keeper is asked before the flag is released by its due second")
        vv4 = _source("native/vv4_origins_icons/vv4_origins_icons.c")
        self.assertIn("((state & STATE_ISLAND_PENDING) != 0 || vv4_island_on_its_way())", vv4)
        helper = vv4[vv4.index("static int vv4_island_on_its_way(void) {"):]
        helper = helper[:helper.index("\n}\n")]
        self.assertIn("0x00728B04u != 0", helper)
        self.assertIn("0x00728B08u == 0", helper)

    def test_every_host_hands_the_answer_over(self):
        for rel in ("native/vv1_origins_icons/vv1_origins_icons.c", "native/vv2_origins_icons/vv2_origins_icons.c",
                    "native/vv3_full_mastery_candidate/vv3_full_mastery_candidate.c",
                    "native/vv5_task9_origins/vv5_task9_origins.c"):
            with self.subTest(source=rel):
                self.assertIn("itk_story_arming, itk_story_on_its_way\n    };", _source(rel))
        # The Tree of Life's Barrel writes the same timer: its host entry is the Tech row's own answer, which
        # leaves out a Barrel bought on its own (Codex, #745).
        vv4 = _source("native/vv4_origins_icons/vv4_origins_icons.c")
        self.assertIn("itk_story_arming, vv4_story_island_on_its_way\n    };", vv4)
        entry = vv4[vv4.index("static int __stdcall vv4_story_island_on_its_way(void) {"):]
        self.assertEqual(entry[:entry.index("\n}\n")].split("{", 1)[1].strip(), "return vv4_island_on_its_way();")

    def test_the_custom_button_is_the_story_companions_to_judge(self):
        bridge = _source("native/shared/story_bridge.h")
        clicked = bridge[bridge.index("static int vvfp_story_pick_clicked("):]
        self.assertLess(clicked.index("if (command == VVFP_STORY_CUSTOM_ID) {"),
                        clicked.index("if (blocked_reason != NULL) {"))


# ---------------------------------------------------------------------------
# 3. The Tree of Life: the Island Event behind a Barrel survives a quit
# ---------------------------------------------------------------------------

@_skip_without(TEST_DLL)
class TheTreeOfLifeIslandEventBehindABarrel(unittest.TestCase):
    def _relaunched(self, token: int):
        """After a relaunch: the Barrel re-armed from its file (vv4_paid_rearm: armed, three
        children, the saved zero timer) and -- with the fix -- the Island Event token from the same
        file (vv4_paid_restore_held: the token, its stamp the timer the re-arm left)."""
        proc = process("vv4")
        world = LockTests._world(LockTests(), proc, "vv4")
        proc.write(0x728B00, b"\1")
        proc.write(0x728B04, b"\1")
        proc.put32(world + 0x170E0, 0)
        proc.write(0x728B08, bytes((token,)))
        proc.put32(0x728B0C, 0)
        proc.export("VvfpStoryInstall", 4)
        return proc, world

    def test_the_barrel_comes_first_then_the_island_event_again(self):
        if not have_stock("vv4"):
            self.skipTest("stock executable not present")
        for token, island_back in ((1, True), (0, False)):
            with self.subTest(token_restored=bool(token)):
                proc, world = self._relaunched(token)
                self.assertEqual(proc.export("VvfpStoryProbePending", 4), 1)
                LockTests()._vv4_trigger(proc, world, (5, 3), seen=1)
                self.assertEqual(proc.read(0x728B04, 1), b"\0", "the Barrel was presented")
                if island_back:
                    self.assertEqual(proc.u32(world + 0x170E0), CLOCK + 5, "the bought event put back")
                    self.assertEqual(proc.u32(0x728B0C), CLOCK + 5)
                    self.assertEqual(proc.export("VvfpStoryProbePending", 4), 1, "and on its way")
                else:
                    self.assertGreater(proc.u32(world + 0x170E0), CLOCK + 5,
                                       "without the token: left for the next natural event (the bug)")

    def test_the_companion_keeps_the_token_with_the_barrel(self):
        vv4 = _source("native/vv4_origins_icons/vv4_origins_icons.c")
        self.assertIn('"Virtual Villagers - The Tree of Life", vv4_paid_rearm,\n    vv4_paid_held, vv4_paid_restore_held\n};',
                      vv4)
        held = vv4[vv4.index("static unsigned int vv4_paid_held(void) {"):]
        held = held[:held.index("static const vv_paid_game VV4_PAID")]
        self.assertIn("0x00728B08u != 0 ? 1u : 0u;", held)
        self.assertIn("*(volatile unsigned char *)(UINT_PTR)0x00728B08u = 1;", held)
        self.assertIn("*(volatile unsigned int *)(UINT_PTR)0x00728B0Cu = 0u;", held)
        paid = _source("native/shared/paid_purchases.h")
        self.assertEqual(paid.count("vv_paid_write(game, slot, vv_paid_word(g), roster)"), 4,
                         "every write keeps what waits behind the token")
        self.assertIn("g->restore_held(f.token >> 8);", paid)


# ---------------------------------------------------------------------------
# 4. Start Over: the Origins companions drop what the erased village bought
# ---------------------------------------------------------------------------

# Each game's save manager (native/shared/game_save_slot.h) and its current-slot field.
SAVE_MANAGER = {"vv1": (0x48AEDC, 0xABE4, 0xB000), "vv2": (0x4997BC, 0x30378, 0x31000),
                "vv3": (0x4B309C, 0x12F24, 0x13000), "vv4": (0x4CB51C, 0x17114, 0x18000),
                "vv5": (0x4DACE0, 0x17D80, 0x18000)}
# What each game holds for a purchase not yet delivered: (address, bytes while bought, bytes after).
HELD = {
    "vv1": ((0x48D700, b"\2", b"\0"), (0x48D704, struct.pack("<I", 17), bytes(4))),
    "vv2": ((0x49C700, b"\3", b"\0"), (0x49C708, struct.pack("<I", 9), bytes(4))),
    "vv3": ((0x6E0058, b"\1", b"\0"), (0x6E004C, struct.pack("<I", CLOCK), bytes(4)),
            (0x6E0050, b"\1", b"\0"), (0x6E0054, struct.pack("<I", CLOCK + 5), bytes(4))),
    "vv4": ((0x728B00, b"\1", b"\0"), (0x728B04, b"\1", b"\0"), (0x728B08, b"\1", b"\0"),
            (0x728B0C, struct.pack("<I", CLOCK + 5), bytes(4))),
    # New Believers: the Barrel's and the Island Event's bits go; the doublers' (1, 2) are the save's.
    "vv5": ((0x51D388, struct.pack("<I", 0x3F), struct.pack("<I", 0x03)),),
}


class StartOverTakesThePurchasesWithTheVillage(unittest.TestCase):
    def test_each_origins_companion_clears_them_for_the_village_in_memory_only(self):
        if not HAVE_EMULATOR:
            self.skipTest("capstone/unicorn/pefile not installed")
        for game in GAMES:
            if not have_stock(game) or not ORIGINS_COMPANION[game].is_file():
                continue
            with self.subTest(game=game):
                n = int(game[2:])
                proc = Process(render(game, "collection_progression"), ORIGINS_COMPANION[game])
                self.assertIn("VvfpOriginsVillageReset", proc.exports)
                pointer, field, size = SAVE_MANAGER[game]
                manager = proc.alloc(size)
                proc.put32(pointer, manager)
                proc.put32(manager + field, 2)           # the village in memory is Save 2's
                for va, bought, _ in HELD[game]:
                    proc.write(va, bought)

                def held():
                    return [proc.read(va, len(bought)) for va, bought, _ in HELD[game]]
                before = held()
                proc.export("VvfpOriginsVillageReset", n, 3)
                self.assertEqual(held(), before, "another slot's tribe deleted: the village in memory keeps them")
                proc.export("VvfpOriginsVillageReset", n % 5 + 1, 2)
                self.assertEqual(held(), before, "another game's call changes nothing")
                proc.export("VvfpOriginsVillageReset", n, 2)
                self.assertEqual(held(), [after for _, _, after in HELD[game]],
                                 "Start Over in its own slot: gone with the village")

    def test_the_reset_companion_tells_each_origins_companion(self):
        reset = _source("native/save_reset_export/save_reset_export.c")
        body = reset[reset.index("__declspec(dllexport) int __stdcall ResetDeletedTribe("):]
        self.assertLess(body.index("notify_origins(game, slot);"), body.index("vv_reset_slot_state("))
        for name in ("VVFP VV1 Origins Icons.dll", "VVFP VV2 Origins Icons.dll", "VVFP Origins Icons.dll",
                     "VVFP VV4 Origins Icons.dll"):
            self.assertIn(f'"{name}",', reset)
        self.assertIn('GetProcAddress(origins, "VvfpOriginsVillageReset")', reset)
        self.assertNotIn("LoadLibrary", reset)
        for rel in ("native/vv1_origins_icons/vv1_origins_icons.def", "native/vv2_origins_icons/vv2_origins_icons.def",
                    "native/vv3_full_mastery_candidate/vv3_full_mastery_candidate.def",
                    "native/vv4_origins_icons/vv4_origins_icons.def", "native/vv5_task9_origins/vv5_task9_origins.def"):
            with self.subTest(def_file=rel):
                self.assertIn("VvfpOriginsVillageReset=_VvfpOriginsVillageReset@8", _source(rel))


# ---------------------------------------------------------------------------
# 5. A Barrel of Babies that can never arrive is refunded (the owner, on #745)
# ---------------------------------------------------------------------------

# The Tree of Life and New Believers: the Barrel rides the island-event trigger, which does nothing
# while the game's own count (VV4 0x467610, VV5 0x4713F0: believers) is 0.  Each game's tech points.
REFUND = {"vv4": dict(count=0x467610, tech=0x4D6F88), "vv5": dict(count=0x4713F0, tech=0x51D5F8)}
# Each game's own count, the trigger's first test.
COUNT = {"vv1": 0x41CF90, "vv2": 0x425860, "vv3": 0x45E8F0, "vv4": 0x467610, "vv5": 0x4713F0}
BARREL_PRICE = 75000


def _barrel_pending(v) -> bool:
    if v.game == "vv4":
        return v.proc.read(0x728B04, 1) != b"\0"
    return bool(v.proc.u32(0x51D388) & 0x0C)


def _run_trigger(v, living: int) -> None:
    """The game's own trigger once, the timer due, the game's count answering `living` -- with nobody,
    up to where it leaves (as stock, it does nothing)."""
    p = v.proc
    owner = v._helpers()
    p.stub(COUNT[v.game], lambda q: (living, 0))
    p.set_reg("esp", HEAP + 0x3000000)
    p.set_reg("esi", owner)
    p.set_reg("ebx", 0)
    p.set_reg("eax", v.now)
    p.set_reg(v.spec["obj_reg"], v.obj)
    p.run(v.spec["trigger"], v.spec["skip"])


@_skip_without(KEEPER_DLL)
class ABarrelThatCanNeverArriveIsRefunded(unittest.TestCase):
    """native/shared/barrel_refund.h, through the keeper's test build (the same header and the same
    wiring the two Origins companions compile), on each game's own purchase and trigger."""

    def _bought(self, game, price, *, island=False):
        v = KeeperVillage(game)
        natural = CLOCK + 3 * HOUR
        v.set_timer(natural)
        if island:
            v.buy("island")
        v.buy("barrel")      # the Origins purchase's own code (New Believers: its Tech screen's close too)
        if game == "vv5":
            v.proc.put32(0x51D5A4, 0xFFFFFFFF)            # no God Power armed
        v.proc.export("ItkProbeBarrelRefund", v.n, price)
        v.proc.put32(REFUND[game]["tech"], 1000)
        self.assertTrue(_barrel_pending(v))
        return v, natural

    def state(self, v):
        out = v.proc.alloc(16)
        v.proc.export("ItkProbeBarrelState", out)
        return dict(zip(("refunds", "told", "amount", "files"), struct.unpack("<4i", v.proc.read(out, 16))))

    def test_nobody_left_refunds_it_once_with_its_price(self):
        for game in REFUND:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                v, natural = self._bought(game, BARREL_PRICE)
                v.now += 10
                _run_trigger(v, 0)
                self.assertEqual(v.proc.u32(REFUND[game]["tech"]), 1000 + BARREL_PRICE, "exactly what it cost")
                self.assertFalse(_barrel_pending(v), "cleared: nothing stays blocked")
                st = self.state(v)
                self.assertEqual((st["refunds"], st["told"], st["amount"]), (1, 1, BARREL_PRICE),
                                 "the player is told, with the amount")
                self.assertEqual(st["files"], 1 if game == "vv4" else 0, "The Tree of Life's file goes at once")
                self.assertEqual(v.timer(), natural, "the game's own next event keeps its time")
                self.assertEqual(v.proc.export("ItkProbeOnItsWay"), 0)
                for _ in range(3):                         # the trigger keeps asking: never again
                    v.now += 2
                    _run_trigger(v, 0)
                self.assertEqual(v.proc.u32(REFUND[game]["tech"]), 1000 + BARREL_PRICE)
                self.assertEqual(self.state(v)["refunds"], 1)

    def test_a_free_barrel_gives_back_nothing_and_is_still_cleared(self):
        for game in REFUND:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                v, _ = self._bought(game, 0)              # the Origins upgrades were free
                _run_trigger(v, 0)
                self.assertEqual(v.proc.u32(REFUND[game]["tech"]), 1000)
                self.assertFalse(_barrel_pending(v))
                st = self.state(v)
                self.assertEqual((st["refunds"], st["told"], st["amount"]), (1, 1, 0))

    def test_anyone_the_trigger_can_run_for_and_it_waits_as_before(self):
        """A village with someone in it (children included: the trigger's draw has no age bounds) still
        gets its barrel, however long it waits for room or its cue: never refunded."""
        for game in REFUND:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                v, _ = self._bought(game, BARREL_PRICE)
                v.proc.export("ItkProbeBarrelRefund", v.n, BARREL_PRICE)
                self.assertTrue(v.tick())                  # the game's own count answers 1
                self.assertEqual(v.proc.u32(REFUND[game]["tech"]), 1000)
                self.assertEqual(self.state(v)["refunds"], 0)

    def test_a_reload_never_refunds_it_twice(self):
        """What a save holds after the refund: New Believers' bits are the save's own word (cleared with
        the refund, in the same save as the refunded points); The Tree of Life's token comes back only
        from its file, which the refund deleted (tests/test_paid_purchases.py, check 12).  Loaded again,
        nothing is pending, so nothing is paid."""
        for game in REFUND:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                v, _ = self._bought(game, BARREL_PRICE)
                _run_trigger(v, 0)
                saved_tech = v.proc.u32(REFUND[game]["tech"])
                saved_word = v.proc.u32(0x51D388) if game == "vv5" else None
                again = KeeperVillage(game)                # a new process, the save loaded
                again.proc.export("ItkProbeBarrelRefund", again.n, BARREL_PRICE)
                again.proc.put32(REFUND[game]["tech"], saved_tech)
                if saved_word is not None:
                    again.proc.put32(0x51D388, saved_word)
                    again.proc.put32(0x51D5A4, 0xFFFFFFFF)
                again.set_timer(0)
                _run_trigger(again, 0)
                self.assertEqual(again.proc.u32(REFUND[game]["tech"]), saved_tech)
                self.assertEqual(self.state(again)["refunds"], 0)

    def test_an_island_event_waiting_too_keeps_the_timer(self):
        """The Tree of Life: an Island Event bought before the Barrel waits on the same timer; the barrel
        is refunded, the island event stays on its way (a Custom Island Event may take its place)."""
        if not have_stock("vv4"):
            self.skipTest("stock executable not present")
        v, _ = self._bought("vv4", BARREL_PRICE, island=True)
        _run_trigger(v, 0)
        self.assertFalse(_barrel_pending(v))
        self.assertEqual(v.timer(), 0, "still due")
        self.assertEqual(v.proc.read(0x728B08, 1), b"\1")
        self.assertEqual(v.proc.export("ItkProbeOnItsWay"), 1)


class TheShippedCompanionsRefundIt(unittest.TestCase):
    """The shipped Tree of Life and New Believers Origins companions, started as "VVFP Startup.dll"
    starts them, on the rendered executable: nobody left, the trigger due -> the price back, the
    barrel cleared, the player told in a message box."""

    SPEC = {
        "vv4": dict(world_ptr=0x4CB51C, timer=0x170E0, clock=0x403750, trigger=0x43FA32, skip=0x43FC0E),
        "vv5": dict(world_ptr=0x4DACE0, timer=0x17D3C, clock=0x4036E0, trigger=0x4426DF, skip=0x44285F),
    }

    def test_each(self):
        if not HAVE_EMULATOR:
            self.skipTest("capstone/unicorn/pefile not installed")
        for game, s in self.SPEC.items():
            if not have_stock(game) or not ORIGINS_COMPANION[game].is_file():
                continue
            with self.subTest(game=game):
                n = int(game[2:])
                p = Process(render(game, "collection_progression"), ORIGINS_COMPANION[game])
                boxes = []
                p.api_handlers["VirtualAlloc"] = lambda q: (q.alloc(q.arg(1)), 16)
                p.api_handlers["GetActiveWindow"] = lambda q: (0, 0)
                p.api_handlers["MessageBoxW"] = lambda q: (
                    boxes.append(q.read(q.arg(1), 400).decode("utf-16le").split("\0")[0]) or 1, 16)
                p.export("VvfpStartup", n, 0)               # nothing else shipped: the price is the Origins one
                world = p.alloc(0x18000)
                p.put32(s["world_ptr"], world)
                p.put32(world + s["timer"], 0)
                p.stub(s["clock"], lambda q: (CLOCK, 0))
                p.stub(REFUND[game]["count"], lambda q: (0, 0))
                if game == "vv4":
                    p.write(0x728B04, b"\1")
                else:
                    p.put32(0x51D388, 0x04 | 0x01)          # the barrel handed over; a doubler owned
                    p.put32(0x51D5A4, 0xFFFFFFFF)
                p.put32(REFUND[game]["tech"], 1000)
                scene = p.alloc(0x100)
                p.put32(scene + 0x10, world)
                for _ in range(2):
                    p.set_reg("esi", scene)
                    p.set_reg("ebx", 0)
                    p.set_reg("esp", HEAP + 0x3000000)
                    p.run(s["trigger"], s["skip"])
                self.assertEqual(p.u32(REFUND[game]["tech"]), 1000 + BARREL_PRICE)
                if game == "vv4":
                    self.assertEqual(p.read(0x728B04, 1), b"\0")
                else:
                    self.assertEqual(p.u32(0x51D388), 0x01, "the doubler's bit stays")
                self.assertEqual(len(boxes), 1, "told once")
                self.assertIn("Barrel of Babies", boxes[0])
                self.assertIn("75,000 tech points have been given back", boxes[0])

    def test_the_companions_charge_what_the_upgrades_cost(self):
        for rel, game in (("native/vv4_origins_icons/vv4_origins_icons.c", 4),
                          ("native/vv5_task9_origins/vv5_task9_origins.c", 5)):
            with self.subTest(source=rel):
                text = _source(rel)
                self.assertIn(f"return vvfp_story_price({game}, VV{game}_BARREL_PRICE);", text)
                self.assertIn(f"#define VV{game}_BARREL_PRICE 75000", text)
        header = _source("native/shared/barrel_refund.h")
        self.assertIn('vvfp_tr("vvfp.shared/barrel_refund.vv_br_tell.s0"', header)
        self.assertIn('vvfp_tr("vvfp.shared/barrel_refund.vv_br_tell.s1"', header)
        due = header[header.index("static int __cdecl vv_br_due("):]
        self.assertLess(due.index("g->cancel();"), due.index("*g->tech += price;"),
                        "cleared before it is paid: no second check can find it pending")


if __name__ == "__main__":
    unittest.main()
