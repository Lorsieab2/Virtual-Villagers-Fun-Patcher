"""A delivered mother is not expecting (src/vv_genealogy.py _save_people, src/vv_last_names.py carrying).

Live, v1.35.66 release candidate: The Secret City's Lolla Salongo and The Tree of Life's Tautai Sakura
had each delivered (a Birth record, no "Nursing" in the Population log, the pregnancy field 0 in
memory), yet the Family Tree Maker drew an "Upcoming child" for each and the Matchmaker's "Not already
expecting" left them out.  The games copy the expected father's name onto the mother at conception and
never clear it at the birth; the tree read that name as the pregnancy.  The pregnancy field decides,
as the Population exporter's "Nursing" line does (native/population_export GAME_LAYOUTS
age_at_conception); the name is only who the father is.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_genealogy as gen  # noqa: E402
import vv_last_names as ln  # noqa: E402
from test_last_names_rename import TABLE, entry  # noqa: E402


class PregnancyField(unittest.TestCase):
    def test_one_dword_before_the_litter_in_every_game(self):
        # Memory: +0x358/+0x35C, +0x540/+0x544, +0xE8C/+0xE90, +0x1C4C/+0x1C50 (twice); the saves
        # keep the pair together in one window.
        for game in range(1, 6):
            with self.subTest(game=game):
                self.assertEqual(ln.PREGNANCY[game], gen.LITTER_FROM_NAME[game] - 4)

    def test_the_memory_offsets_the_population_log_uses(self):
        self.assertEqual(ln.PREGNANCY[1], 0x358 - 0x370)
        self.assertEqual(ln.PREGNANCY[2], 0x540 - 0x564)
        # The Secret City: window (0xE6C, 0x40) at entry +0xAC, the name at entry +0x14.
        self.assertEqual(ln.PREGNANCY[3], 0xE8C - 0xE6C + 0xAC - 0x14)
        # The Tree of Life: window (0x1C34, 0x28) at entry +0xAC, the name at entry +0x14.
        self.assertEqual(ln.PREGNANCY[4], 0x1C4C - 0x1C34 + 0xAC - 0x14)


class DeliveredMother(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        people = [
            entry("Spok", 0, 1, 5, 6),
            entry("Lolla", 1, 50, 7, 8, expecting=("Spok", 5, 6), pregnant=0),     # delivered: stale name
            entry("Ofu", 0, 50, 9, 9, father=("Spok", 5, 6), mother=("Lolla", 7, 8)),
            entry("Kolea", 1, 51, 3, 3, expecting=("Spok", 5, 6), pregnant=590),   # carrying now
        ]
        (self.folder / "Virtual Villagers - The Secret City1.ldw").write_bytes(
            b"ldwg" + bytes(TABLE - 4) + b"".join(people) + bytes(64))
        self.village = gen.load_village(self.folder, 3, 1)
        self.who = {p.name: p for p in self.village.known()}

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_stale_expected_father_is_no_pregnancy(self):
        self.assertFalse(self.who["Lolla"].expecting)
        self.assertTrue(self.who["Kolea"].expecting)

    def test_only_the_real_pregnancy_has_an_upcoming_child(self):
        upcoming = [p for p in self.village.people.values() if p.upcoming]
        self.assertEqual([self.village.people[p.mother].name for p in upcoming], ["Kolea"])
        self.assertEqual(self.village.people[upcoming[0].father].name, "Spok", "the name is still the father")

    def test_the_matchmaker_offers_the_delivered_mother(self):
        _men, women = gen.candidates(self.village, gen.Rules())
        names = {w.name for w in women}
        self.assertIn("Lolla", names)
        self.assertNotIn("Kolea", names, "Not already expecting still leaves out the one carrying")
        self.assertIn("Lolla", gen.pair_report(self.village, gen.Rules(), "The Secret City"))


if __name__ == "__main__":
    unittest.main()
