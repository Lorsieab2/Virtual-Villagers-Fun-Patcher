"""Story queue file: another village's array on screen (the title screen's seeded
founders after a quit to the menu, the slot unchanged) must never take over the
queue file of the village the purchase was bought in (the same rule the Barrel of
Babies file and the custom titles already follow, native/shared/foreign_sidecar.h).
"""
from __future__ import annotations

import unittest

from test_story_custom_island_event import emulated, have_stock
from test_story_queued_purchases import (
    GAMES, LATE, SQ_PICK, fresh, have, queue_file, session, state, tick,
)


@emulated
class AForeignArrayNeverTakesTheQueueFile(unittest.TestCase):
    def test_founders_on_the_title_screen_leave_the_villages_file_alone(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                story = fresh(game)
                slot = story.proc.export("VvfpStoryProbeSetPick", story.n, 0, story.proc.tick)
                self.assertGreaterEqual(slot, 0)
                tick(story)
                file = queue_file(story)
                self.assertTrue(have(file, story) & SQ_PICK)
                story.proc.export("VvfpStoryProbeQueueSaved")
                # Quit to the menu: another array in the records, the slot unchanged,
                # the purchase still in the process's memory.
                for i, name in enumerate(("Xu", "Yi", "Zo")):
                    story.village.put(i, sex="f" if i % 2 else "m", years=20 + i, name=name)
                tick(story)
                tick(story)
                self.assertEqual(queue_file(story), file,
                                 "the founders on the title screen took village A's queue file")
                # The game is quit there; relaunched, village A loads.
                again = fresh(game)
                session(again, queue_file(story), LATE)
                tick(again)
                self.assertEqual(state(again)["pick"], slot, "village A's purchase is lost")

    def test_an_array_that_queues_its_own_item_never_takes_the_inherited_one(self):
        """Review of #585: once the other array queued something of its own, the file became its own
        -- and took the purchase still in memory from village A too, so A's paid pick could be put
        back or delivered in the other village."""
        from story_custom_fixtures import Event
        from test_story_custom_island_event import EVENT_BUF
        from test_story_queued_purchases import SQ_CUSTOM
        for game in GAMES:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                story = fresh(game)
                slot = story.proc.export("VvfpStoryProbeSetPick", story.n, 0, story.proc.tick)
                self.assertGreaterEqual(slot, 0)
                tick(story)
                story.proc.export("VvfpStoryProbeQueueSaved")
                for i, name in enumerate(("Xu", "Yi", "Zo")):
                    story.village.put(i, sex="f" if i % 2 else "m", years=20 + i, name=name)
                tick(story)
                # The other array buys a Custom Island Event of its own.
                story.proc.write(EVENT_BUF, Event(game=story.n, title="Rain", text="It rained.").pack())
                self.assertTrue(story.proc.export("VvfpStoryProbeSetCustom", story.n, EVENT_BUF, story.proc.tick))
                tick(story)
                tick(story)
                file = queue_file(story)
                self.assertTrue(have(file, story) & SQ_CUSTOM, "its own purchase is in its file")
                self.assertFalse(have(file, story) & SQ_PICK, "village A's pick was written into the other's file")


if __name__ == "__main__":
    unittest.main()
