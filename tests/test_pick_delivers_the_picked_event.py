"""Pick Island Event delivers exactly the event picked -- all five games, with the island-event trigger's real code.

Found live (crash-hunt smoke, v1.35.97, The Lost Children, collection_progression and immediate_fixed): picking "The
Great Coconut Debate" and then "The Masks of the Harvest Dance" in a new village both delivered -- and logged -- "A
Mysterious Sack".  Both events open with a question.  A New Home's and The Lost Children's trigger makes a village's
first island event its two-choice family (Island Events Seen 0); a player's own event comes before it, and the count
stub (story_empty_village.inc ce_trigger_bypass) sent the trigger on PAST that check -- which also skipped the
two-choice family roll, so a question could only reach the "island event or crate / sack" roll, which sends anything
but a plain event to the crate (A New Home) or the sack (The Lost Children).  A question now goes on just after the
villager draw, where the family roll sends it to the two-choice family that asks it.

EMULATED (the Story TEST build, each game's executable as the patcher renders it): each game's trigger (the Trigger
harness of tests/test_story_opening_events.py) with an event bought through Pick Island Event's own queue
(VvfpStoryProbeGraphQueue, strict cast, origin Pick Island Event) -- a plain event and a question made here, and in The
Lost Children the two events of the live report from the shipped collection -- in a new village (Island Events Seen
0) and an established one.  The trigger must reach the family that shows THAT event, and its delivery point must show
its title: A New Home / The Lost Children's island-event chooser (plain) or two-choice setup (question), the later
games' selector.
"""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "src"))

import vv_cie_graph as cie  # noqa: E402
from test_story_custom_island_event import (  # noqa: E402
    CHOOSER,
    HAVE_EMULATOR,
    SELECT,
    TEST_DLL,
    Story,
    emulated,
    have_stock,
)
from test_story_opening_events import CLOCK, Trigger  # noqa: E402
from test_story_two_choice_hooks import DIALOG  # noqa: E402

if HAVE_EMULATOR:
    from story_emulator import HEAP

GAMES = ("vv1", "vv2", "vv3", "vv4", "vv5")
CG_ORIGIN_PICK = 1
DUE_STRICT_PICK = 1 | 0x100 | (CG_ORIGIN_PICK << 9)   # made due, strict cast, origin Pick Island Event
COLLECTION = ROOT / "assets" / "event_collection"

PLAIN = {
    "format": "vvfp-cie-graph", "version": 6, "title": "The Quiet Tide", "games": [1, 2, 3, 4, 5],
    "roles": {"subject": {"kind": "villager", "min_age": 14}},
    "start": "p",
    "nodes": {"p": {"text": "(Name) watches the tide go out."}},
}
QUESTION = {
    "format": "vvfp-cie-graph", "version": 6, "title": "The Two Shells", "games": [1, 2, 3, 4, 5],
    "roles": {"subject": {"kind": "villager", "min_age": 14}},
    "start": "q",
    "nodes": {
        "q": {"type": "question", "text": "(Name) finds two shells. Which one should (he/she) keep?",
              "choices": [{"label": "The white one", "next": "a"}, {"label": "The pink one", "next": "b"}]},
        "a": {"text": "(Name) keeps the white shell."},
        "b": {"text": "(Name) keeps the pink shell."},
    },
}
# The live report's two picks (The Lost Children): both open with a question.
LIVE = (("lch47_coconut_debate", "The Great Coconut Debate"), ("b285_masks_harvest", "The Masks of the Harvest Dance"))


def made(data: dict) -> bytes:
    g, problems = cie.validate(copy.deepcopy(data))
    assert problems == [], problems
    return cie.compile_graph(g)


class PickTrigger(Trigger):
    """The trigger with a village of six adults; `fire()` says which family the trigger built and `shown()` runs
    that family's delivery point and returns what it shows (None: the game's own event)."""

    def __init__(self, story: Story):
        super().__init__(story)
        for i in range(3, 7):
            story.village.put(i, sex="m" if i % 2 else "f", years=30, name=f"Villager{i}")
        self.buf = story.proc.alloc(0x40000)
        if self.game == "vv3" and story.proc.u32(0x4B309C) == 0:
            story.proc.put32(0x4B309C, self.world)     # the manager the purchase's helper writes

    def queue(self, data: bytes) -> str | None:
        p = self.story.proc
        p.write(self.buf, data)
        at = p.export("VvfpStoryProbeGraphQueue", self.story.n, self.buf, len(data), DUE_STRICT_PICK)
        return None if at == 0 else p.cstring(at)

    def fire(self) -> str:
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
        return self.built[0]

    def shown_island(self) -> str | None:
        """The island-event family's delivery point: the text it shows, None when the game chose its own."""
        p = self.story.proc
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
            if len(self.story.calls.get(chooser, [])) != calls:
                return None
            return p.cstring(event_object + 0x277F, 0x2710)
        _, site, resume, register, *_ = SELECT[self.game]
        p.set_reg("esi", 5)
        p.set_reg("esp", HEAP + 0x3000000)
        p.run(site, resume)
        obj = p.reg(register)
        return None if obj == self.stock_objects[5] else f"object {obj:#x}"

    def shown_question(self) -> str | None:
        """A New Home / The Lost Children: the two-choice family's setup call -- the question it shows, None when the
        game's own encounter is set up."""
        d = DIALOG[self.game]
        p = self.story.proc
        story = self.story
        dlg = p.alloc(0x5200)
        p.put32(dlg + 0x54, 2)
        p.put32(dlg + 0x58, 3)
        p.put32(dlg + 0x5C, 4)
        p.put32(dlg + d["subject"], 0xFFFFFFFF)
        p.put32(dlg + d["choice"], 0xFFFFFFFF)
        p.put32(dlg + d["villagers"], story.village.array)
        story.record_call(d["select"], 4)
        for va in d["stubs"]:
            story.record_call(va, 4)
        story.record_call(d["setup"], 0, value=1)
        story.record_call(d["resolve"], 0)
        calls = len(story.calls.get(d["setup"], []))
        p.set_reg("esp", HEAP + 0x3000000)
        p.set_reg("ecx", dlg)
        p.set_reg("esi", dlg)
        p.run(d["site"], d["site"] + 5)
        if len(story.calls.get(d["setup"], [])) != calls:
            return None
        return p.cstring(dlg + d["q"], 0x2710)


@emulated
class PickDeliversThePickedEvent(unittest.TestCase):
    def _picks(self, game):
        picks = [("plain", PLAIN["title"], made(PLAIN)), ("question", QUESTION["title"], made(QUESTION))]
        if game == "vv2":
            for leaf, title in LIVE:
                path = COLLECTION / f"{leaf}.cieg"
                self.assertTrue(path.is_file(), path)
                picks.append(("question", title, path.read_bytes()))
        return picks

    def test_every_game_delivers_the_picked_event_in_a_new_and_an_established_village(self):
        if not TEST_DLL.is_file():
            self.skipTest("the Story test build is not in tests/test_dlls")
        for game in GAMES:
            if not have_stock(game):
                continue
            for kind, title, data in self._picks(game):
                for seen in (0, 5):
                    with self.subTest(game=game, event=title, island_events_seen=seen):
                        trigger = PickTrigger(Story(game))
                        trigger.counter = seen
                        self.assertIsNone(trigger.queue(data), "the pick is queued")
                        p = trigger.story.proc
                        asked = False
                        shown_first = None
                        # Each display of the event, as the trigger brings it (a long question's text comes as
                        # pages first, then the question itself), until nothing of it is armed.
                        for display in range(8):
                            if p.export("VvfpStoryProbeCustomPending", trigger.story.n) == 0:
                                break
                            built = trigger.fire()
                            self.assertNotEqual(built, "other", f"display {display}: never the crate / sack")
                            if built == "visitor":
                                self.assertIn(game, ("vv1", "vv2"))
                                shown = trigger.shown_question()
                                self.assertIsNotNone(shown, f"display {display}: the picked event's question, "
                                                     "not the game's own encounter")
                                asked = True
                            else:
                                self.assertEqual(built, "island")
                                shown = trigger.shown_island()
                                self.assertIsNotNone(shown, f"display {display}: the picked event, not the "
                                                     "game's own")
                            shown_first = shown if shown_first is None else shown_first
                            if asked:
                                break
                            p.export("VvfpStoryInstall", trigger.story.n)      # the companion's frame
                        else:
                            self.fail("the event never finished arriving")
                        self.assertIsNotNone(shown_first)
                        if game in CHOOSER:
                            self.assertTrue(shown_first.startswith(title), shown_first)
                            self.assertEqual(asked, kind == "question", "a question is asked by the two-choice "
                                             "family; a plain event never")
                        if seen == 0:
                            self.assertEqual(trigger.counter, 0, "a player's event before the village's first "
                                             "island event is not counted: the opening events still come")

    def test_a_picked_question_waits_while_the_village_is_empty(self):
        """Found live too (A New Home, immediate_fixed): "The Stone That Chose" (a question) was bought, a Time Warp
        then starved the whole tribe, and no Island Events record was written.  As designed: a question needs a
        living villager to ask, so the trigger makes no event while the game's own population count is 0 (stock: it
        does nothing then, not even reschedule) -- nothing is shown, nothing logged, and the event stays on its way,
        never lost."""
        if not TEST_DLL.is_file():
            self.skipTest("the Story test build is not in tests/test_dlls")
        # A New Home and The Lost Children (the live report's games, and the two whose first-event route this file
        # fixes): their trigger code past an empty count runs here with no other routine; the later three's empty
        # village is covered by tests/test_story_empty_village.py.
        for game in ("vv1", "vv2", "vv3"):
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                trigger = PickTrigger(Story(game))
                trigger.counter = 0
                self.assertIsNone(trigger.queue(made(QUESTION)))
                p = trigger.story.proc
                count_va = [va for va, value in trigger.g["stubs"].items() if value == 5][0]
                p.stub(count_va, lambda proc: (0, 0))          # everyone has died
                p.api_handlers.setdefault("GetSystemTimeAsFileTime",
                                          lambda q: (q.write(q.arg(0), bytes(8)), (0, 4))[1])
                p.put32(trigger.world + trigger.g["countdown"], CLOCK)
                p.set_reg("esi", trigger.this)
                p.set_reg("ebx", 0)
                p.set_reg("esp", HEAP + 0x3000000)
                p.run(trigger.g["start"], trigger.g["end"])
                self.assertEqual(trigger.built, [], "no event is made")
                self.assertEqual(p.export("VvfpStoryProbeCustomPending", trigger.story.n), 1, "still on its way")


if __name__ == "__main__":
    unittest.main()
