"""Villager ages in the last-names windows (the owner, v1.35.85: "please add Villager Ages to all places that
list villagers in the last names windows"), all five games: Repair Saves & Logs' last-names window, "Each
villager's own rule...", the "Villagers with no last name" prompt, Random last names' earlier-records question,
the shared-family note and the name-problem message.

An age reads "34 years old": whole villager years from the save's own age (20 game units a year, as the family
tree and the logs word it).  A villager no longer in the village shows none (the logs' age is when they died or
were last seen), nor does an age the save does not give.  Pure functions and the source: no Tk, no game."""
from __future__ import annotations

import sys
import unittest
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_fun_patcher_gui as gui  # noqa: E402
import vv_last_names as ln  # noqa: E402
from test_missing_last_names import Village  # noqa: E402


@dataclass
class V:
    name: str
    age: int | None = None
    alive: bool = True


class TheAge(unittest.TestCase):
    def test_years_from_game_units(self):
        self.assertEqual(gui.last_name_age(V("Ago", 0)), "0 years old", "a newborn's 0 is a real age")
        self.assertEqual(gui.last_name_age(V("Ago", 19)), "0 years old")
        self.assertEqual(gui.last_name_age(V("Ago", 20)), "1 years old")
        self.assertEqual(gui.last_name_age(V("Ago", 1379)), "68 years old")
        self.assertEqual(gui.last_name_age(V("Golden Child", 100)), "5 years old")

    def test_nothing_for_the_dead_or_an_unknown_age(self):
        self.assertEqual(gui.last_name_age(V("Moa", 900, alive=False)), "")
        self.assertEqual(gui.last_name_age(V("Moa", None)), "")
        self.assertEqual(gui.last_name_age(V("Moa", -1)), "")

    def test_a_name_with_its_age(self):
        self.assertEqual(gui.last_name_who(V("Goro Wanjiko", 680)), "Goro Wanjiko (34 years old)")
        self.assertEqual(gui.last_name_who(V("Moa", 680, alive=False)), "Moa")
        self.assertEqual(gui.last_name_who(V("Moa")), "Moa")

    def test_every_game_reads_the_age_from_the_save(self):
        checker = ln.tools.load_checker()
        for game in (2, 3, 4, 5):
            self.assertIsInstance(checker.LAYOUTS[game].age, int, f"game {game}")
        source = (ROOT / "src" / "vv_last_names.py").read_text(encoding="utf-8")
        self.assertIn("age_at = -0x28 if game == 1 else checker.LAYOUTS[game].age", source,
                      "A New Home: record +0x348, the name at +0x370")


class TheLists(Village):
    """A small The Secret City save (every villager 600 game units: 30 years old) and its logs (a dead Moa)."""

    def test_the_last_names_window_and_own_rules_rows(self):
        people, parents = ln.everyone(self.folder, 3, 1)
        rows = dict(zip((v.name for v in people), gui.last_name_rows(people, parents)))
        self.assertEqual(rows["Ago Akikai"], "Ago Akikai (Male, 30 years old)")
        self.assertEqual(rows["Kid"], "Kid (Male, 30 years old) -- father Ago Akikai, mother Aipi")
        self.assertEqual(rows["Kalea"], "Kalea (Female, 30 years old) -- arrived")
        self.assertEqual(rows["Moa Akikai"], "Moa Akikai (sex unknown, no longer in the village)",
                         "the dead: no age (the Deaths log's is their age at death)")
        for v in people:
            if v.alive:
                self.assertIn("30 years old", rows[v.name])

    def test_the_no_last_name_prompt(self):
        self.record("rule\tfather")
        lines = gui.missing_last_names_lines(ln.missing_last_names(self.folder, 3, 1))
        self.assertTrue(any(line.startswith("• Kalea (30 years old) arrived (Custom Island Event) with no last name")
                            for line in lines), lines)
        self.assertTrue(any(line.startswith("• Aipi (30 years old) has no last name") for line in lines))
        self.assertTrue(all("(30 years old)" in line for line in lines))

    def test_the_prompt_lists_twenty_then_how_many_more(self):
        missing = [ln.Missing(ln.Living(0, f"V{k}", "Male", 0, k, 1, "", age=40)) for k in range(23)]
        lines = gui.missing_last_names_lines(missing)
        self.assertEqual(len(lines), 21)
        self.assertEqual(lines[0], "• V0 (2 years old) has no last name")
        self.assertEqual(lines[-1], "... and 3 more")

    def test_the_check_note_is_unchanged(self):
        self.assertEqual(ln.Missing(ln.Living(0, "Aipi", "Female", 0, 0, 1, "", age=40)).describe(),
                         "Aipi has no last name")


class TheWindowsUseThem(unittest.TestCase):
    SOURCE = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")

    def body(self, name: str, end: str) -> str:
        return self.SOURCE[self.SOURCE.index(f"    def {name}("):self.SOURCE.index(f"    def {end}(")]

    def test_every_list_in_the_last_names_windows(self):
        main = self.body("_last_names_dialog", "_own_rules_dialog")
        own = self.body("_own_rules_dialog", "_repair_questions")
        prompt = self.body("_missing_last_names_prompt", "_missing_last_names_at_repair")
        self.assertIn("last_name_rows(people, parents)", main)
        self.assertIn("last_name_rows(shown, parents)", own)
        self.assertIn("lines = missing_last_names_lines(missing)", prompt)
        # Random last names' "Earlier records give these villagers a last name" and the name-problem message.
        self.assertIn('f"{last_name_who(v)}: an earlier record calls them "', main)
        self.assertIn('f"{last_name_who(v)}: {problem}"', main)
        # "N villager(s) share a last name with a family they are not related to: ..."
        self.assertIn("(v.name, last_name_age(v), shared[v.identity])", main)
        for text in (main, own, prompt):
            self.assertNotIn('f"{v.name}: ', text, "a villager named without their age")


if __name__ == "__main__":
    unittest.main()
