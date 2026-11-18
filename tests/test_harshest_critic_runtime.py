"""(Name1)'s Harshest Critic in the engine: each of its six .cieg files runs in every game's emulated Story Upgrades
(the test DLL in the game's own stock executable), with Scrolling Popups as the collection's rows require.

Many runs per file and game, each with its own random stream, so the walk meets the six skill groups, the four
choices and the routes: every run is queued, walked to its end, and each text the game would show is plain words
(no "{pool}" or "(role.pronoun)" left), at most the popup's 2,000 bytes.  Skipped without the emulator or the stock
executables (GitHub CI has neither)."""
from __future__ import annotations

import functools
import random
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from test_story_custom_island_event import HAVE_EMULATOR, emulated, have_stock  # noqa: E402

if HAVE_EMULATOR:
    from test_story_cie_graph_runtime import DONE, IDLE  # noqa: E402
    from test_story_cie_graph_runtime_v6 import V6  # noqa: E402

FILES = ("hc1_routes", "hc2_pleas", "hc3_disasters", "hc4_noises", "hc5_victories", "hc6_sabotage")
RUNS = 12
LEFTOVER = re.compile(r"\{[A-Za-z@_]|\((?:subject|mentor|rival|prankster|master|official|examiner|elder|chief|patient)"
                      r"\b", re.I)


@emulated
class HarshestCriticRuns(unittest.TestCase):
    def test_every_file_runs_in_every_game(self):
        games = [f"vv{n}" for n in range(1, 6) if have_stock(f"vv{n}")]
        if not games:
            self.skipTest("needs the stock executables")
        people = [(0, "f", 30, "Ana", 20, False), (1, "m", 41, "Bo", 20, False), (2, "f", 35, "Cia", 20, False),
                  (3, "m", 28, "Dov", 20, False), (4, "f", 16, "Eli", 5, False), (5, "m", 52, "Fin", 20, False)]
        for fid in FILES:
            data = (ROOT / "assets" / "event_collection" / f"{fid}.cieg").read_bytes()
            for game in games:
                for k in range(RUNS):
                    with self.subTest(file=fid, game=game, run=k):
                        rnd = random.Random(f"{fid}:{game}:{k}")
                        r = V6(game, people)
                        # the emulator's 2,000,000-instruction budget per call is too few for loading a
                        # 100-KB .cieg (its CRC and checks): a bigger budget, still bounded
                        r.p.call = functools.partial(type(r.p).call, r.p, limit=100_000_000)
                        r.rolls([rnd.randrange(1 << 15) for _ in range(256)])
                        r.p.export("VvfpStoryProbeGraphScroll", 1)
                        why = r.queue6(data)
                        self.assertIsNone(why, why)
                        shown = r.walk_through([k % 4] * 4)
                        self.assertIn(r.state()["phase"], (IDLE, DONE))
                        self.assertTrue(shown)
                        for _kind, text, labels in shown:
                            self.assertLessEqual(len(text.encode("cp1252", "replace")), 2000)
                            for t in [text] + list(labels or []):
                                self.assertIsNone(LEFTOVER.search(t), t)


if __name__ == "__main__":
    unittest.main()
