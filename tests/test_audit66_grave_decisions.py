"""Repair Saves & Logs' "Fix grave information" with "Retroactively edit records?" No: every field the
player answered is remembered, not only the last one (src/vv_log_decisions.py keeps one decision per
kind, village and villager, so the grave decisions' field must be part of what tells them apart).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "src"))

import vv_graves as vg  # noqa: E402
from test_fix_graves import NOW, NoGame, Village, death, grave_bytes  # noqa: E402


class EveryFieldLeftIsRemembered(unittest.TestCase):
    def village(self, game, graves, deaths):
        v = Village(game, graves, deaths)
        self.addCleanup(v.close)
        return v

    def test_two_fields_of_one_grave_left_in_one_repair(self):
        v = self.village(4, [grave_bytes(4, "Mia", 1000, head=5, body=6, male=False)],
                         death(1, "Mia", 1000, epitaph="", head=5, body=7, sex="Male"))
        self.assertEqual({d.field for d in vg.survey(v.folder, 4, 1).differences}, {"body", "sex"})
        before = v.deaths.read_bytes()
        vg.fix_graves(v.folder, 4, 1, [vg.Fix(0, "sex", "Female"), vg.Fix(0, "body", 6)], retro=False,
                      processes=NoGame(), now=NOW)
        self.assertEqual(v.deaths.read_bytes(), before)
        self.assertEqual(vg.survey(v.folder, 4, 1).differences, [], "neither field is asked about again")

    def test_a_later_repair_does_not_forget_an_earlier_answer(self):
        v = self.village(4, [grave_bytes(4, "Mia", 1000, head=5, body=6, male=False)],
                         death(1, "Mia", 1000, epitaph="", head=5, body=7, sex="Male"))
        vg.fix_graves(v.folder, 4, 1, [vg.Fix(0, "sex", "Female")], retro=False, processes=NoGame(), now=NOW)
        vg.fix_graves(v.folder, 4, 1, [vg.Fix(0, "body", 6)], retro=False, processes=NoGame(), now=NOW)
        self.assertEqual(vg.survey(v.folder, 4, 1).differences, [])


class ANewHomeGraveKeepsItsEpitaph(unittest.TestCase):
    """A New Home keeps a grave's epitaph only in the patcher's Graves file (native/vvfp_cause_of_death
    cod_vv12.inc: an entry's epitaph 0 and no text is NO epitaph -- cod_entry_epitaph returns NULL -- while
    a grave with no entry is given one by the job rule when it is first shown).  Setting only a grave's
    cause, when the Graves file has no entry for it yet, must not make an entry that wipes its epitaph."""

    def village(self, deaths):
        v = Village(1, [grave_bytes(1, "Mia", 1000)], deaths)
        self.addCleanup(v.close)
        return v

    def entry(self, v):
        data = (v.folder / "Virtual Villagers Fun Patcher Data" / "Graves"
                / "Virtual Villagers 1 Graves - Save 1.dat").read_bytes()
        return data[16:60]

    def test_a_listed_epitaph_from_the_death_record(self):
        v = self.village(death(1, "Mia", 1000, cause="Old age", epitaph="Inspired Architect"))
        vg.fix_graves(v.folder, 1, 1, [vg.Fix(0, "cause", "Disease")], retro=True, processes=NoGame(), now=NOW)
        e = self.entry(v)
        self.assertEqual(e[8], 0, "Disease")
        self.assertEqual((e[9], e[10]), (vg.EPITAPHS.index("Inspired Architect"), 0))
        self.assertEqual(vg.survey(v.folder, 1, 1).graves[0].sidecar.get("epitaph"), "Inspired Architect")

    def test_the_players_own_epitaph_from_the_death_record(self):
        v = self.village(death(1, "Mia", 1000, epitaph="Rest well"))
        vg.fix_graves(v.folder, 1, 1, [vg.Fix(0, "cause", "Disease")], retro=False, processes=NoGame(), now=NOW)
        e = self.entry(v)
        self.assertEqual((e[9], e[10], e[12:21]), (0, 1, b"Rest well"))


if __name__ == "__main__":
    unittest.main()
