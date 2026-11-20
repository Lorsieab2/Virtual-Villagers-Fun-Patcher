"""Game Mechanics: the professions count in Vital statistics (the owner, 2026-11-19: "there should be a check to see
how many villagers are of each profession in game mechanics. (highest skill + checked preference)"):
src/vv_game_mechanics_life.py profession_line, on the committed save fixtures of all five games."""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_game_mechanics as gm  # noqa: E402
import vv_game_mechanics_life as life  # noqa: E402
from test_game_mechanics_time_units import pages  # noqa: E402

VITAL = gm.GROUPS[0]


def person(game: int, skills: dict[str, float], ticked: str | None = None, years: int = 30) -> life.Person:
    import vv_corrupt_skills as cs
    p = life.Person("X", "Male", years * life.YEAR, years * life.YEAR, 100, False, 0, 1)
    p.skills = tuple(float(skills.get(name, 0)) for name in cs.SKILL_NAMES[game])
    p.ticked = ticked
    return p


class Professions(unittest.TestCase):
    def test_every_save_page_has_the_line_in_vital_statistics(self) -> None:
        for name, facts in pages():
            if name.startswith("general"):
                continue
            with self.subTest(name):
                for page in (facts, gm.minimum(facts)):
                    hits = [f.text for f in page if f.group == VITAL and f.text.startswith("Professions of the ")]
                    self.assertEqual(len(hits), 1, name)
                    m = re.match(r"^Professions of the (\d+) adults? \(14 or more; the job ticked, else the highest "
                                 r"skill\): (.+)\.$", hits[0])
                    self.assertIsNotNone(m, hits[0])
                    counts = [int(n) for n in re.findall(r"(\d+) [a-z]+ \(\d+ ticked\)", m.group(2))]
                    self.assertEqual(sum(counts), int(m.group(1)), hits[0])
                    self.assertNotIn("not read", hits[0])

    def test_ticked_job_wins_over_the_highest_skill(self) -> None:
        p = person(4, {"Building": 90, "Farming": 10}, ticked="Farming")
        line = life.profession_line(4, [p])
        self.assertIn("1 farmer (1 ticked)", line)
        self.assertIn("0 builders (0 ticked)", line)

    def test_children_are_left_out(self) -> None:
        line = life.profession_line(4, [person(4, {"Farming": 50}, years=10), person(4, {"Farming": 50})])
        self.assertTrue(line.startswith("Professions of the 1 adult ("))

    def test_ties_follow_the_action_bar(self) -> None:
        # The Tree of Life / New Believers: a later skill takes over when above the best with its fraction dropped.
        self.assertEqual(life.highest_skill(person(4, {"Farming": 40.7, "Parenting": 40.2}), 4), "Parenting")
        self.assertEqual(life.highest_skill(person(4, {"Farming": 40.7, "Parenting": 40.0}), 4), "Farming")
        # A New Home / The Lost Children: the first of Parenting, Building, Healing, Farming, Research.
        self.assertEqual(life.highest_skill(person(1, {"Farming": 30, "Healing": 30}), 1), "Healing")
        # The Secret City: the first of Farming, Parenting, Healing, Research, Building.
        self.assertEqual(life.highest_skill(person(3, {"Building": 30, "Farming": 30}), 3), "Farming")

    def test_new_believers_counts_devotees_and_no_heathens(self) -> None:
        heathen = person(5, {"Devotion": 50})
        heathen.heathen = True
        line = life.profession_line(5, [person(5, {"Devotion": 50}), heathen])
        self.assertIn("1 devotee (0 ticked)", line)
        self.assertTrue(line.startswith("Professions of the 1 adult ("))
        self.assertNotIn("devotees", life.profession_line(4, [person(4, {"Farming": 1})]))


if __name__ == "__main__":
    unittest.main()
