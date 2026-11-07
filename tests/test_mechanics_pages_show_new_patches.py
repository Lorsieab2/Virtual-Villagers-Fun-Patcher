"""The Game Mechanics pages show this round's patches stock first, then patched, also when whether the game has
the patch cannot be told (no exe or patch log found): Faith Loss is Doubled/Gains Halved and Puddle Play Moves to
the Lake Shore (New Believers), and Food Gains are Flat's pick on the Food Mastery line (The Tree of Life, New
Believers)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_game_mechanics as gm  # noqa: E402
import vv_game_mechanics_faith_vv5 as faith  # noqa: E402
import vv_game_mechanics_vv4 as vv4  # noqa: E402
import vv_game_mechanics_vv5 as vv5  # noqa: E402

NOW = 1.8e9


def village(game: int, installed, certain: bool = True, general: bool = False) -> gm.Village:
    return gm.Village(Path("."), game, 1, Path(f"{game}.ldw"), gm.blank_save(game, NOW), installed, NOW,
                      certain=certain, general=general)


def texts(facts) -> list[str]:
    return [f.text for f in facts]


class FaithLoss(unittest.TestCase):
    HEADER = "every loss roll's chance is doubled"

    def lines(self, installed, certain=True):
        return texts(faith.lines(village(5, installed, certain, general=True)))

    def test_shown_in_the_game_after_the_stock_rolls(self) -> None:
        lines = self.lines(frozenset({faith.FAITH_LOSS}))
        at = next(n for n, t in enumerate(lines) if self.HEADER in t)
        self.assertIn("(in this game)", lines[at])
        self.assertTrue(any("A sick believer loses 1 more" in t for t in lines[:at]), "the stock rolls come first")

    def test_shown_when_it_cannot_be_told(self) -> None:
        for installed, certain in ((None, True), (frozenset(), False)):
            lines = self.lines(installed, certain)
            header = [t for t in lines if self.HEADER in t]
            self.assertEqual(len(header), 1, (installed, certain))
            self.assertIn("whether the game has it could not be told", header[0])

    def test_absent_when_it_is_known_out(self) -> None:
        self.assertFalse(any(self.HEADER in t for t in self.lines(frozenset())))


class Puddles(unittest.TestCase):
    WORDS = "Normally \"Playing in puddles\" stops once The Lake holds water."

    def other(self, installed, certain=True):
        return [t for t in texts(vv5.facts(village(5, installed, certain))) if self.WORDS in t]

    def test_in_out_and_unknown(self) -> None:
        self.assertEqual(self.other(frozenset()), [])
        inside = self.other(frozenset({vv5.PUDDLES}))
        self.assertEqual(len(inside), 1)
        self.assertIn("is in the game", inside[0])
        unknown = self.other(None)
        self.assertEqual(len(unknown), 1)
        self.assertIn("could not be told", unknown[0])


class FlatFoodMastery(unittest.TestCase):
    PATCHED = "a pick 7 -> 10 -> 14 on Fast, 3 -> 4 -> 6 on Normal, 2 -> 3 -> 4 on Slow and 4 -> 6 -> 8 while catching up."

    def mastery_line(self, module, game, installed, certain=True) -> str:
        lines = [t for t in texts(module.facts(village(game, installed, certain)))
                 if t.startswith("Food Mastery (a technology) boosts")]
        self.assertEqual(len(lines), 1)
        return lines[0]

    def test_stock_first_then_the_flat_pick(self) -> None:
        for module, game in ((vv4, 4), (vv5, 5)):
            with self.subTest(game=game):
                out = self.mastery_line(module, game, frozenset())
                self.assertNotIn(gm.feature_name(module.FLAT), out)
                inside = self.mastery_line(module, game, frozenset({module.FLAT}))
                self.assertTrue(inside.startswith(out[:-1]), "the stock gains come first, unchanged")
                self.assertIn(f"With \"{gm.feature_name(module.FLAT)}\": {self.PATCHED}", inside)
                unknown = self.mastery_line(module, game, None)
                self.assertIn("(whether the game has it could not be told): " + self.PATCHED, unknown)


if __name__ == "__main__":
    unittest.main()
