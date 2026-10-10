"""Story / Cheat Upgrades: a queued purchase survives a quit (all five games).

A Pick Island Event, a Custom Island Event (with or without its question), The
Lost Children's Pick Gong of Wonder Outcome and the rest of a Choose Time Skip
Amount were held in the companion's memory only, while their charge and the
island event's due timer are saved with the village: a quit before the
delivery gave the next load a random event in place of the one bought, and
lost the rest of a time skip.

native/vvfp_story_upgrades/story_queue.inc keeps the queue in
"Paid Purchases\\Virtual Villagers N Story Purchases - Save S.dat" (the TEST
build keeps the file in memory, VvfpStoryProbeQueueSession / File) and puts it
back, once, for the same village when the slot's save was written after the
item -- on the companion's tick, and where the game asks for an armed event,
so the saved timer delivers the purchase, never a random event in its place.
Each "quit" here is a new emulated process: nothing of the last one's memory.
"""
from __future__ import annotations

import struct
import unittest
from pathlib import Path

from test_story_custom_island_event import (  # noqa: E402
    EVENT_BUF, SCRATCH, TEXT_BUF, Story, emulated, have_stock,
)

ROOT = Path(__file__).resolve().parents[1]
GAMES = ("vv1", "vv2", "vv3", "vv4", "vv5")
SQ_PICK, SQ_CUSTOM, SQ_GONG, SQ_SKIP = 1, 2, 4, 8
LATE = 0x7FFFFFF0                              # a save made after every item here
OC_GONG_SLOT = 1000


def village(story: Story, names=("Ama", "Bo", "Cai")) -> None:
    for i, name in enumerate(names):
        story.village.put(i, sex="f" if i % 2 else "m", years=20 + i, name=name)


def tick(story: Story) -> None:
    story.proc.tick += 300                     # the companion's 250 ms tick runs
    story.proc.export("VvfpStoryProbeSetTick", story.proc.tick)
    story.proc.export("VvfpStoryInstall", story.n)


def queue_file(story: Story) -> bytes:
    size = story.proc.export("VvfpStoryProbeQueueFile", 0, 0)
    if size <= 0:
        return b""
    buf = story.proc.alloc(size)
    story.proc.export("VvfpStoryProbeQueueFile", buf, size)
    return story.proc.read(buf, size)


def session(story: Story, file: bytes = b"", save: int = 0, unreadable: int = 0) -> None:
    buf = story.proc.alloc(max(len(file), 4)) if file else 0
    if file:
        story.proc.write(buf, file)
    story.proc.export("VvfpStoryProbeQueueSession", buf, len(file), save, unreadable)


def state(story: Story) -> dict:
    story.proc.export("VvfpStoryProbeQueueState", SCRATCH)
    v = struct.unpack("<9i", story.proc.read(SCRATCH, 36))
    return {"pick": v[0], "custom": v[1], "question": v[2], "gong": v[3], "remaining": v[4],
            "done": v[5], "active": v[6], "notice": v[7], "outcome": v[8]}


def have(file: bytes, story: Story) -> int:
    story.proc.export("VvfpStoryProbeQueueLayout", SCRATCH)
    layout = struct.unpack("<7i", story.proc.read(SCRATCH, 28))
    return struct.unpack_from("<I", file, layout[1])[0] if len(file) >= layout[0] else 0


def fresh(game: str, names=("Ama", "Bo", "Cai")) -> Story:
    story = Story(game)
    # The custom titles' tick looks for its file too: no Documents here.
    story.proc.api_handlers["SHGetSpecialFolderPathA"] = lambda p: (0, 16)
    village(story, names)
    session(story)
    return story


@emulated
class QueuedPurchasesSurviveAQuit(unittest.TestCase):
    def games(self):
        for game in GAMES:
            if have_stock(game):
                yield game

    def queued_pick(self, game: str):
        story = fresh(game)
        slot = story.proc.export("VvfpStoryProbeSetPick", story.n, 0, story.proc.tick)
        self.assertGreaterEqual(slot, 0)
        tick(story)
        file = queue_file(story)
        self.assertTrue(file and have(file, story) & SQ_PICK, f"{game}: the pick is written to the slot's file")
        story.proc.export("VvfpStoryProbeQueueSaved")   # the quit's save, after the purchase
        return slot, file

    def test_a_pick_is_put_back_once_for_its_village(self):
        for game in self.games():
            with self.subTest(game=game):
                slot, file = self.queued_pick(game)
                story = fresh(game)
                session(story, file, LATE)
                tick(story)
                self.assertEqual(state(story)["pick"], slot, "the next process gets the pick back")
                self.assertEqual(story.proc.export("VvfpStoryProbeQueueRestored"), SQ_PICK)
                tick(story)
                self.assertEqual(queue_file(story), file, "...once: nothing rewritten while it waits")
                # Its ten minutes start again; lapsed, the file goes with it.
                story.proc.tick += 11 * 60 * 1000
                story.proc.export("VvfpStoryProbeSetTick", story.proc.tick)
                self.assertEqual(story.proc.export("VvfpStoryProbeQueueLazy", story.n), 1)
                tick(story)
                self.assertEqual(queue_file(story), b"", "gone from memory in its village: gone from the file")

    def test_the_game_asking_for_the_event_puts_it_back_before_any_tick(self):
        """The save's timer can fire before the first tick: the selector's own
        question (drop_lapsed_pick, ce_drop_lapsed) restores it, so the
        purchase -- not a random event -- is what the timer delivers."""
        for game in self.games():
            with self.subTest(game=game):
                slot, file = self.queued_pick(game)
                story = fresh(game)
                session(story, file, LATE)
                self.assertEqual(story.proc.export("VvfpStoryProbeQueueLazy", story.n), 0)
                self.assertEqual(story.proc.export("VvfpStoryProbeArmedSlot"), slot)

    def test_a_save_older_than_the_purchase_never_paid_for_it(self):
        for game in self.games():
            with self.subTest(game=game):
                _slot, file = self.queued_pick(game)
                story = fresh(game)
                session(story, file, 1)                       # the save on disk predates it
                tick(story)
                self.assertEqual(state(story)["pick"], -1, "not delivered for nothing")
                self.assertEqual(queue_file(story), b"", "...and the file says what the save holds")

    def test_another_village_gets_nothing_and_the_file_waits(self):
        for game in self.games():
            with self.subTest(game=game):
                _slot, file = self.queued_pick(game)
                story = fresh(game, names=("Dov", "Eli", "Fay"))
                session(story, file, LATE)
                tick(story)
                self.assertEqual(state(story)["pick"], -1)
                self.assertEqual(queue_file(story), file, "the file is its village's, kept")

    def test_a_file_that_cannot_be_read_is_left_alone(self):
        for game in self.games():
            with self.subTest(game=game):
                _slot, file = self.queued_pick(game)
                story = fresh(game)
                session(story, file, LATE, unreadable=1)
                story.proc.export("VvfpStoryProbeSetPick", story.n, 0, story.proc.tick)
                tick(story)
                self.assertEqual(queue_file(story), file, "never written over while it cannot be read")

    def test_start_over_deletes_it_with_the_village(self):
        for game in self.games():
            with self.subTest(game=game):
                _slot, file = self.queued_pick(game)
                story = fresh(game)
                session(story, file, LATE)
                tick(story)
                story.proc.export("VvfpStoryVillageReset", story.n, 1)
                self.assertEqual(queue_file(story), b"")
                tick(story)
                story.proc.export("VvfpStoryProbeQueueLazy", story.n)
                self.assertEqual(state(story)["pick"], -1, "the queue was the erased village's")
                self.assertEqual(queue_file(story), b"")

    def test_a_custom_island_event_and_its_question_come_back(self):
        from story_custom_fixtures import Event
        for game in self.games():
            for question in (False, True):
                with self.subTest(game=game, question=question):
                    story = fresh(game)
                    event = Event(game=story.n, title="Rain", text="It rained.")
                    story.proc.write(EVENT_BUF, event.pack())
                    if question:
                        story.proc.export("VvfpStoryProbeChoiceCap", 1)
                        ok = story.proc.export("VvfpStoryProbeSetChoice", story.n, EVENT_BUF,
                                               self.choice(story), story.proc.tick)
                    else:
                        ok = story.proc.export("VvfpStoryProbeSetCustom", story.n, EVENT_BUF, story.proc.tick)
                    self.assertTrue(ok)
                    tick(story)
                    file = queue_file(story)
                    self.assertTrue(have(file, story) & SQ_CUSTOM)
                    story.proc.export("VvfpStoryProbeQueueSaved")
                    again = fresh(game)
                    if question:
                        again.proc.export("VvfpStoryProbeChoiceCap", 1)
                    session(again, file, LATE)
                    tick(again)
                    s = state(again)
                    self.assertEqual((s["custom"], s["question"]), (1, int(question)))
                    if not question:
                        self.assertEqual(again.proc.export("VvfpStoryProbeDeliver", again.n, TEXT_BUF, 4096), 1)
                        self.assertIn("It rained.", again.proc.cstring(TEXT_BUF))
                        tick(again)
                        self.assertEqual(queue_file(again), b"", "delivered: the file goes")

    def choice(self, story: Story) -> int:
        from story_custom_fixtures import Choice, Event, Outcome
        c = Choice(labels=("Yes", "No"),
                   outcomes=((Outcome(1, Event(game=story.n, title="", text="A")),),
                             (Outcome(1, Event(game=story.n, title="", text="B")),)))
        packed = c.pack()
        buf = story.proc.alloc(len(packed))
        story.proc.write(buf, packed)
        return buf

    def test_the_gong_outcome_comes_back(self):
        if not have_stock("vv2"):
            self.skipTest("no stock The Lost Children")
        story = fresh("vv2")
        story.proc.write(SCRATCH, struct.pack("<i", -1))
        state_now = story.proc.export("VvfpStoryProbeOutcomeArm", 2, OC_GONG_SLOT, SCRATCH, 1, 0, 2, 0)
        if state_now == 0:
            self.skipTest("the gong has no outcome to set in this build")
        tick(story)
        file = queue_file(story)
        self.assertTrue(have(file, story) & SQ_GONG)
        story.proc.export("VvfpStoryProbeQueueSaved")
        again = fresh("vv2")
        session(again, file, LATE)
        tick(again)
        self.assertEqual(state(again)["gong"], 1)


@emulated
@unittest.skipUnless(have_stock("vv1"), "stock A New Home is not in inputs/")
class TheRestOfATimeSkipSurvivesAQuit(unittest.TestCase):
    def test_the_years_still_to_go_carry_on(self):
        from test_story_time_skip import TimeSkipHost
        story = fresh("vv1")
        host = TimeSkipHost(story, 6)
        self.assertEqual(story.proc.export("VvfpStoryProbeTimeSkipStart", 1, 18, story.proc.tick), 6)
        tick(story)
        file = queue_file(story)
        self.assertTrue(have(file, story) & SQ_SKIP)
        story.proc.export("VvfpStoryProbeQueueSaved")
        again = fresh("vv1")
        TimeSkipHost(again, 6)
        session(again, file, LATE)
        tick(again)
        s = state(again)
        self.assertEqual((s["active"], s["remaining"], s["done"]), (1, 12, 6),
                         "12 years still to go, 6 done -- the steps made are in the save")
        del host


class StartOverListsTheFile(unittest.TestCase):
    def test_save_reset_deletes_it(self):
        reset = (ROOT / "native/shared/save_reset.c").read_text(encoding="utf-8")
        self.assertIn('Paid Purchases\\\\Virtual Villagers " n " Story Purchases - Save %d.dat"', reset)
        for game in range(1, 6):
            self.assertIn(f'STORY_QUEUE_FORMAT("{game}")', reset)

    def test_the_restore_runs_where_every_game_asks(self):
        main = (ROOT / "native/vvfp_story_upgrades/vvfp_story_upgrades.c").read_text(encoding="utf-8")
        custom = (ROOT / "native/vvfp_story_upgrades/story_custom.inc").read_text(encoding="utf-8")
        self.assertIn("static int drop_lapsed_pick(void) {\n    sq_lazy();", main)
        self.assertIn("static int ce_drop_lapsed(void) {\n    sq_lazy();", custom)


if __name__ == "__main__":
    unittest.main()
