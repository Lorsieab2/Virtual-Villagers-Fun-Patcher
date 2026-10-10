"""Head 0, body 0 and age 0 are real values, in all five games.

The owner (2026-10-09): "for all 5 games, 0 is a valid value for head, body and age!!!!"  The first
head and the first body of every sheet are index 0, and a newborn is age 0.  So nothing may read a 0
there as unknown, missing or unset, drop it, skip it, print "(unknown)" for it or fail a match on it;
"unknown" is a separate flag, a negative number or a record's absence (None here).

These pin that rule on the Python tools that read heads, bodies and ages: the Family Tree Maker and
the Village Matchmaker (vv_genealogy, vv_family_tree), Repair Saves & Logs' reader
(vv_log_additions) and the consistency checker (scripts/vvfp_consistency_check.py).
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_family_tree as ft  # noqa: E402
import vv_genealogy as gen  # noqa: E402
import vv_log_additions as additions  # noqa: E402

spec = importlib.util.spec_from_file_location("vvfp_consistency_check_zero",
                                              ROOT / "scripts" / "vvfp_consistency_check.py")
checker = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = checker
spec.loader.exec_module(checker)

Y = gen.UNITS_PER_YEAR
FIRST = "2026-01-01 10:00:00"


def zero_village() -> gen.Village:
    """A founder couple with head 0 / body 0, and their newborn: age 0, head 0, body 0."""
    people = {
        1: gen.Person(1, "Pa", 0, 0, sex="Male", age=30 * Y, alive=True, first_seen=FIRST),
        2: gen.Person(2, "Ma", 0, 0, sex="Female", age=0, alive=True, first_seen=FIRST),
        3: gen.Person(3, "Babe", 0, 0, sex="Female", age=0, alive=True, father=1, mother=2, first_seen=FIRST),
    }
    v = gen.Village(1, 1, "Zero Tribe", people)
    gen._generations(v, {FIRST: set(people)})
    gen.number_people(v)
    return v


class GenealogyTests(unittest.TestCase):
    def test_age_zero_is_a_newborn_not_an_unknown_age(self) -> None:
        babe = zero_village().people[3]
        self.assertEqual(babe.years, 0)
        self.assertEqual(babe.age_text(), "0 game units (0 years old)")
        self.assertEqual(gen.Person(9, "Who", 1, 1).age_text(), "age unknown")     # None is unknown

    def test_head_and_body_zero_are_a_key_like_any_other(self) -> None:
        v = zero_village()
        self.assertEqual(v.people[3].key, ("Babe", 0, 0))
        self.assertEqual(gen.relationship(v, 1, 3), "parent and child")
        self.assertEqual(gen.relationship(v, 2, 3), "parent and child")
        self.assertEqual(v.people[3].generation, 2)

    def test_a_snapshots_parent_with_head_and_body_zero_is_named(self) -> None:
        lines = ["Villager 1", "  Name: Babe", "  Parents:", "    Father: Pa", "      Head: 0", "      Body: 0",
                 "    Mother: Ma", "      Head: 0", "      Body: 0"]
        self.assertEqual(gen._snapshot_parents(lines), {"Father": ("Pa", 0, 0), "Mother": ("Ma", 0, 0)})

    def test_the_matchmaker_age_window_reads_age_zero_as_an_age(self) -> None:
        v = zero_village()
        # Age 0 is too young for the 18-49 window, and any age when planning ahead.
        men, women = gen.candidates(v, gen.Rules(plan_ahead=False, allow_50_plus=True))
        self.assertNotIn("Ma", [p.name for p in women])
        men, women = gen.candidates(v, gen.Rules(plan_ahead=True, not_expecting=False))
        self.assertIn("Ma", [p.name for p in women])
        self.assertIn("Babe", [p.name for p in women])
        # Thirty years apart is too far apart: the 0 is compared, never skipped as unknown.
        rules = gen.Rules(close_in_age=True, max_age_gap_years=10)
        self.assertEqual(gen._blocked(rules, v.people[1], v.people[2], "no recorded common ancestor",
                                      gen.Fraction(0), {}), "too far apart in age")


class FamilyTreeTests(unittest.TestCase):
    def test_a_newborns_portrait_shows_age_zero(self) -> None:
        v = zero_village()
        text = ft.default_text(ft.layout(v, ft.Edits()), v.people[3])
        self.assertIn("0 game units", text)
        self.assertIn("0 years old", text)
        self.assertNotIn("age unknown", text)

    def test_a_chosen_look_of_head_and_body_zero_is_kept(self) -> None:
        v = zero_village()
        v.people[3].head, v.people[3].body = 7, 8
        key = ft.entry_key(v, v.people[3])
        e = ft.Edits(entries={key: {"look": [0, 0]}})
        self.assertEqual(ft.look_of(e, v, v.people[3]), (0, 0))


class LogReaderTests(unittest.TestCase):
    def test_a_record_with_head_and_body_zero_has_an_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Virtual Villagers 1 Deaths Log 1.txt"
            path.write_text("Village: Zero (Save 1)\n\nDeath 1\n  Name: Babe\n  Age at death: 0\n"
                            "  Head: 0\n  Body: 0\n", encoding="latin-1")
            (b,) = additions.blocks(path)
            self.assertEqual(b.identity, ("Babe", 0, 0))
            self.assertEqual(b.int_value("Age at death"), 0)

    def test_the_checker_reads_zero_heads_bodies_and_ages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = Path(tmp)
            folder = game_dir / checker.LOGS / "Births and Conceptions"
            folder.mkdir(parents=True)
            (folder / "Virtual Villagers 1 Births and Conceptions Log 1.txt").write_text(
                "Village: Zero (Save 1)\n\n"
                "Birth\n  Child: Babe\n    Head: 0\n    Body: 0\n  Mother: Ma\n    Head: 0\n    Body: 0\n"
                "  Father: Pa\n    Head: 0\n    Body: 0\n\n"
                "Arrived 1\n  Name: Newcomer\n  Age at arrival: 0\n  Sex: Male\n  Head: 0\n  Body: 0\n",
                encoding="latin-1")
            records, _files = checker.births_log(game_dir, 1, 1)
            self.assertFalse(records.damaged)
            self.assertEqual([r.kind for r in records], ["birth", "arrived"])
            birth, arrived = records
            for p in (birth.child, birth.mother, birth.father, arrived.child):
                self.assertEqual((p.head, p.body), (0, 0), p.name)
        villagers = checker.snapshot_villagers("=== x ===\nVillager 1\n  Name: Babe\n  Age: 0\n  Head: 0\n  Body: 0\n")
        self.assertEqual((villagers[0]["age"], villagers[0]["head"], villagers[0]["body"]), (0, 0, 0))


if __name__ == "__main__":
    unittest.main()
