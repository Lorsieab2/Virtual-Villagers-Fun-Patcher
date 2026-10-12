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


if __name__ == "__main__":
    unittest.main()
