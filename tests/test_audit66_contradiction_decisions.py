"""A backfilled Arrived record the player already answered ("Remove", then "Retroactively edit
records?" No) is never asked about again -- by Duplicate backfilled Arrived records (plan_born_arrived)
nor by Records that contradict each other (src/vv_log_contradictions.py), and Check Logs does not call
it WRONG (the checker's own check_backfilled_arrivals already follows the remembered answer).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "src"))

import vv_log_additions as additions  # noqa: E402
import vv_log_contradictions as contra  # noqa: E402
import vv_log_decisions  # noqa: E402
from test_log_contradictions import Folder, arrived  # noqa: E402


class AnsweredOnceIsNotAskedAgain(unittest.TestCase):
    def test_no_to_retroactive_removal_is_followed_by_the_contradictions(self):
        f = Folder(1)
        self.addCleanup(f.tmp.cleanup)
        path = f.births(arrived(8, "Hoani Chuchip", 11, 2, how="Barrel of Babies", backfill=False)
                        + arrived(12, "Hoani Chuchip", 11, 2))
        before = path.read_bytes()
        kind = additions.plan_backfilled_arrivals(f.path, 1, 1, {}, None)
        self.assertEqual(len(kind.removes), 1)
        answers = {k: (additions.RETRO_NO if k.endswith("|retro") else q.default) for k, q in kind.questions.items()}
        additions.apply(f.path, [kind], {"born_arrived"}, answers)
        vv_log_decisions.record(f.path, 1, 1, additions.resolve_decisions([kind], {"born_arrived"}, answers))
        self.assertEqual(path.read_bytes(), before, "No leaves the log as it is")
        self.assertEqual(additions.plan_backfilled_arrivals(f.path, 1, 1, {}, None).removes, [])
        found = contra.find(f.path, 1, 1)
        self.assertEqual([x for x in found if x.wrong], [], "not WRONG: the player's answer is remembered")
        self.assertTrue(any("as you chose" in x.text for x in found))
        self.assertEqual(contra.plan(f.path, 1, 1).questions, {}, "...and not asked again")


if __name__ == "__main__":
    unittest.main()
