"""Game Mechanics: where the code and what was seen live disagree, the page keeps both.

The owner, 2026-10-27: "for cases where the code contradicts live observation write both cases down."  Each pair
below is one such case: the code's line (with its addresses, VERIFIED-C or VERIFIED-E) and what was seen (the
owner's word, gm.OWNER, or a live run, UNCONFIRMED while it is not explained).  Neither side may be dropped or
merged into the other, so each is pinned as its own line with its own label, on the general page of its game.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_game_mechanics as gm  # noqa: E402
import vv_game_mechanics_vv3 as vv3  # noqa: E402

NOW = 1_790_000_000 + 3_000_000

# (game, group, the code's line starts, its label, the observed line starts, its label)
PAIRS = (
    # The VV3 brewed potion: 300 real seconds after brewing (0x430E60) vs the owner's "it follows the speed".
    (3, "Technologies, items and buildings",
     "The game spoils a brewed potion 5 real-life minutes after it is brewed, the same at every speed", gm.CODE,
     "The owner sees a brewed potion's time follow the game speed", gm.OWNER),
    # The Lovers: the picker's adult class 360..999 (0x45D460) vs the owner's teenager.
    (3, "Island events",
     "In the game's code both picks use the picker's adult class, 360 to 999 age units", gm.RUNNING,
     "The owner has seen The Lovers choose a teenager (14 to 17 villager years) while playing.", gm.OWNER),
    (3, "Island events",
     "A teenager, in the game's code: as for her gift, the game's own draw never chooses one", gm.RUNNING,
     "A teenager, seen by the owner: as for her gift.", gm.OWNER),
    (3, "Hidden villager stats",
     "The Lovers in the game's code: both lovers are picked only from villagers of 18 to 49.95", gm.RUNNING,
     "Breeding age: no villager under 18 has children, but the owner has seen The Lovers", gm.OWNER),
    # New Believers: The Missing Kids marks a Heathen child sick (0x4161D1) vs the owner's "never fall sick".
    (5, "Island events",
     "In the game's code \"Yell for help\" marks the Heathen child sick too (0x4161D1)", gm.RUNNING,
     "The owner: Heathens never fall sick in play.", gm.OWNER),
    (5, "Faith and Heathens",
     "Heathens: the life tick skips them (0x472CB7)", gm.RUNNING,
     "The owner: Heathens never fall sick in play.", gm.OWNER),
    (5, "Death and graves",
     "In the game's code a Heathen can be marked sick: The Missing Kids", gm.CODE,
     "Heathens never age, eat or fall sick (the game runs none of that for them)", gm.OWNER),
    # A New Home: the dislike of running is read only under 14 (0x43CCF0) vs the owner's "works for adults too".
    (1, "Hidden villager stats",
     "In the game's code the dislike of running is read in one place only", gm.CODE,
     "Running, liked: a villager of 14 or more runs", gm.OWNER),
)


def _page(game: int) -> list[gm.Fact]:
    return gm.general(game, now=NOW)


class BothSidesAreWritten(unittest.TestCase):
    pages: dict[int, list[gm.Fact]] = {}

    @classmethod
    def setUpClass(cls) -> None:
        cls.pages = {game: _page(game) for game in sorted({pair[0] for pair in PAIRS})}

    def _one(self, game: int, group: str, start: str, label: object) -> gm.Fact:
        found = [f for f in self.pages[game] if f.group == group and f.text.startswith(start)]
        self.assertTrue(found, f"VV{game} {group}: no line starts {start!r}")
        self.assertTrue(all(f.verified == label for f in found), f"VV{game} {group}: {start!r} is not {label!r}")
        return found[0]

    def test_each_pair_keeps_the_code_and_the_observation_as_separate_lines(self) -> None:
        for game, group, code, code_label, seen, seen_label in PAIRS:
            with self.subTest(game=game, code=code):
                a = self._one(game, group, code, code_label)
                b = self._one(game, group, seen, seen_label)
                self.assertIsNot(a, b)
                self.assertFalse(b.text.startswith(code))
                self.assertFalse(a.text.startswith(seen))

    def test_the_code_side_gives_its_addresses(self) -> None:
        for game, group, code, code_label, _seen, _label in PAIRS:
            with self.subTest(game=game, code=code):
                text = self._one(game, group, code, code_label).text
                if "0x" not in text:     # the Hidden villager stats Lovers line cites its addresses in the comment
                    self.assertIn("The Lovers in the game's code", text)

    def test_vv1_running_keeps_the_untraced_step_unconfirmed(self) -> None:
        # Step 1 of the step dispatcher (0x43CBD0) sets the running speed under 14 with no dislike read; what
        # queues it is not traced, so the line stays UNCONFIRMED.
        self._one(1, "Hidden villager stats", "Another movement step (0x43CBD0) gives every villager under 14", False)

    def test_vv3_autosave_and_the_live_run_are_both_written(self) -> None:
        # The code: the per-frame update 0x427720 runs the save check 0x427DD0 at 0x427B40, every 600 seconds of
        # the computer's clock.  Seen: a 30-minute live run left no new save, not explained.
        lines = dict(vv3.CHANCE_LINES)
        seen = [line for line in lines if line.startswith("Seen in a live run of the game made for the Game Mechanics "
                                                         "audit: a village played for 30 minutes of real time left no "
                                                         "new save")]
        self.assertEqual(len(seen), 1)
        self.assertIs(lines[seen[0]], False)                       # UNCONFIRMED: the run is not explained
        self.assertIn("0x427DD0", seen[0])
        self.assertIn("Autosave: while the game is open it checks the computer's clock on every frame",
                      gm.autosave_line(3))


if __name__ == "__main__":
    unittest.main()
