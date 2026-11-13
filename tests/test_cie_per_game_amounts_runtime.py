"""Per-game award amounts in one reward step (format version 5), played by the Story / Cheat Upgrades companion.

EMULATED (unicorn, the stock executables, the TEST build; tests/test_story_cie_graph_runtime.py's harness): a
version 5 graph whose food effect gives 100 by default and exactly 700 in The Secret City (50 to 300 in New
Believers): each game makes its own amount, once, and the page says the amount made; the shipped Aspiring
Adventurer example (version 5) is played in every game by test_story_cie_graph_runtime.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_cie_graph as cg  # noqa: E402
from test_story_cie_graph_runtime import Run, emulated, have_stock, norm, stores  # noqa: E402

GRAPH = cg.load({
    "format": "vvfp-cie-graph", "version": 5, "title": "The Basket", "games": [1, 2, 3, 4, 5],
    "roles": {"subject": {"kind": "villager"}},
    "start": "s",
    "nodes": {"s": {"text": "(Name) finds a basket: (award) (award_unit).",
                    "effects": [{"do": "food", "amount": 100, "per_game": {"3": [700, 700], "5": [50, 300]},
                                 "defer": True}, {"do": "pay_award"}]}},
})
# A New Home, The Lost Children, The Secret City: a one-popup plain event's delivery in The Tree of Life and New
# Believers reaches the game's own C runtime (TlsGetValue), which this emulation does not run; the shipped example's
# per-game awards are played in all five games by test_story_cie_graph_runtime.
WANT = {"vv1": (100, 100), "vv2": (100, 100), "vv3": (700, 700)}


@emulated
class PerGameAmounts(unittest.TestCase):
    def test_each_game_its_own_amount(self):
        data = cg.compile_graph(GRAPH)
        for game, (lo, hi) in WANT.items():
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                run = Run(game)
                run.force([])
                food0, _ = stores(run)
                self.assertIsNone(run.queue(data))
                shown = run.play()
                food1, _ = stores(run)
                gained = food1 - food0
                self.assertTrue(lo <= gained <= hi, (gained, lo, hi))
                text = norm(" ".join(Run.strip(None, t, "The Basket") for _k, t, *_ in shown))
                self.assertIn(f"{gained} food", text)


if __name__ == "__main__":
    unittest.main()
