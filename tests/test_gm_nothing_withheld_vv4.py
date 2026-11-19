"""The owner, 2026-11-18: "In Game Mechanics, stuff that says 'wasn't counted' or similar should be checked, confirmed
and included. Nothing should be withheld!"  The Tree of Life's lines that said "not traced", "an estimate", "not
read here" or carried an UNCONFIRMED label, each pinned to the value read from the stock exe or the patcher's own
code (the addresses are in each module's comments)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_game_mechanics as gm  # noqa: E402
import vv_game_mechanics_hidden_vv4 as hidden4  # noqa: E402
import vv_game_mechanics_items_vv4 as items  # noqa: E402
import vv_game_mechanics_vv4 as vv4  # noqa: E402

NOW = 1.8e9
C = hidden4.C


def village(installed=frozenset()) -> gm.Village:
    return gm.Village(Path("."), 4, 1, Path("4.ldw"), gm.blank_save(4, NOW), installed, NOW)


def entry(name: str):
    return next(e for e in items.entries() if e.name == name)


def sub(name: str, start: str):
    return next((t, ok) for t, ok in entry(name).subs if t.startswith(start))


def hidden_entry(name: str):
    return next(e for e in hidden4.entries() if e.name == name)


class TheSpawnRate(unittest.TestCase):
    def test_once_a_frame_at_30_frames_a_second(self) -> None:
        facts = [f for f in vv4.facts(village()) if f.group == "Mushrooms"]
        line = next(f for f in facts if f.text.startswith("While playing (not paused) a mushroom or a collectible"))
        self.assertIn("about every 45 real-life seconds on average", line.text)
        self.assertIn("once a frame, 30 frames a second (a frame every 33 thousandths of a second)", line.text)
        self.assertIn("about once in 1,365 frames, 45 seconds", line.text)
        self.assertNotIn("estimate", line.text)
        self.assertNotIn("not read here", line.text)
        self.assertEqual(line.verified, gm.CODE)
        # 24 in 32,768 a 33 ms frame.
        self.assertAlmostEqual(32768 / 24 * 0.033, 45.06, places=2)


class Chances(unittest.TestCase):
    def test_new_villagers_likes(self) -> None:
        line, verified = next((t, ok) for t, ok in vv4.CHANCE_V4 if t.startswith("A new villager, the first five"))
        self.assertIn("so 1 villager in 162 likes running; that one of a new village's first five does is 3.05%", line)
        self.assertNotIn("30%", line)
        self.assertEqual(verified, gm.CODE)
        self.assertAlmostEqual(1 - (161 / 162) ** 5, 0.0305, places=4)

    def test_the_weather(self) -> None:
        line, verified = next((t, ok) for t, ok in vv4.CHANCE_V4 if t.startswith("Clear weather lasts"))
        self.assertIn("(480 to 1,799 seconds on the game's clock)", line)
        self.assertIn("for 1.5 to 3, 3 to 6 or 5 to 10 real-life minutes (180 to 359 seconds on the game's clock)",
                      line)
        self.assertNotIn("not traced", line)
        self.assertEqual(verified, gm.CODE)


class Stews(unittest.TestCase):
    def test_the_salt_water_pair(self) -> None:
        self.assertEqual(entry("Soap").text, "soapy x3, in salt water, with no heat: makes soap (clicked, the pot "
                                             "then says \"Soap is ready to stack.\").")
        self.assertEqual(entry("Cloth pulp").text, "pulpy vines x3, in salt water, with no heat: makes the pulp for "
                                                   "cloth (clicked, the pot then says \"Pulp for cloth is ready.\").")
        self.assertIn("soap made in the pot (soapy herbs x3 in salt water)", entry("Soap Invented").text)
        self.assertIn("In salt water, soapy x3 makes soap and pulpy vines x3 the pulp for cloth", vv4.STEW_LINES[1][0])
        self.assertFalse(any(e.name == "Soapy herbs in salt water" for e in items.entries()))


class Technologies(unittest.TestCase):
    def test_the_sites_and_the_rubble(self) -> None:
        self.assertEqual(entry("Medicine level 3").subs, (("Level 3 makes the Hospital appear as a building site.",
                                                           gm.CODE),))
        self.assertEqual(entry("Learning level 3").subs, (("Level 3 makes the Nursery School appear as a building "
                                                           "site.", gm.CODE),))
        self.assertEqual(entry("Construction level 1").subs[0], (
            "Dropped on the rubble over the Cooking Pit the villager does not clear it: the game says \"Removing "
            "these rocks seems technically challenging.\"", gm.CODE))
        self.assertEqual(entry("Construction level 2").subs, (
            ("Level 2 makes Hut 2 appear as a building site.", gm.CODE),
            ("Villagers dropped on the rubble over the Cooking Pit clear it (\"Clearing rubble\").", gm.CODE)))
        self.assertEqual(entry("Construction level 3").subs[0], ("Level 3 makes Hut 3 appear as a building site.",
                                                                 gm.CODE))


class Puzzles(unittest.TestCase):
    def test_the_step_counts_are_code(self) -> None:
        for name in ("The Cutting Tool", "Boiling Water", "Soap Invented", "The Butterflies", "The Frog Rescue",
                     "Cloth Invented", "The Nursery School"):
            self.assertEqual(entry(name).verified, gm.CODE, name)

    def test_the_butterflies(self) -> None:
        text = entry("The Butterflies").text
        self.assertIn("the stalks turn green 4 real-life hours later", text)
        self.assertIn("\"The stalks are still recovering.\"", text)

    def test_the_dendrology_needs(self) -> None:
        self.assertEqual(entry("Pruning the Tree").subs, (("Binding the branch needs Dendrology level 2.", gm.CODE),))
        self.assertEqual(entry("Purify Tree").subs, (("Purifying the tree needs Dendrology level 3.", gm.CODE),))


class Buildings(unittest.TestCase):
    def test_the_sites(self) -> None:
        self.assertEqual(sub("Building in general", "A builder takes on a building by itself")[1], gm.CODE)
        for name, line in (("Hut 2", "It is built only at Construction level 2."),
                           ("Hut 3", "It is built only at Construction level 3."),
                           ("The Nursery School (the building)", "It appears as a site at Learning level 3."),
                           ("The Hospital", "It appears as a site at Medicine level 3.")):
            self.assertEqual(entry(name).subs, ((line, gm.CODE),), name)

    def test_fixing_huts_patch(self) -> None:
        text, verified = sub("Fixing huts", "With the patcher")
        self.assertIn("It steps in on 75 of every 100 of the game's choices for a builder", text)
        self.assertIn("on 14 in 100 of those", text)
        self.assertEqual(verified, gm.CODE)


class Items(unittest.TestCase):
    def test_new_clothes(self) -> None:
        text, verified = entry("New clothes").subs[0]
        self.assertIn("the 5,000 tech points are taken when the villager's change comes", text)
        self.assertIn("\"Not enough tech points to make new clothes!\"", text)
        self.assertNotIn("not traced", text)
        self.assertEqual(verified, gm.CODE)

    def test_the_golden_fish_patch(self) -> None:
        self.assertEqual(sub("Fishing Nets", "With the patcher (\"Complete Fish Scales")[1], gm.CODE)

    def test_the_duplication_patch_says_what_to_watch(self) -> None:
        text, verified = sub("Mushrooms", "With the patcher (\"VV1 Mushroom")
        self.assertIn("drop two children on one mushroom and watch the food count", text)
        self.assertFalse(verified)


class Patcher(unittest.TestCase):
    def test_the_doublers_say_what_they_skip(self) -> None:
        tech = entry("Tech Point Doubler")
        self.assertIn("research is on that list -- the researcher's points, the Lab Equipment bonus and the Fire "
                      "Pit's +1", tech.text)
        self.assertNotIn("every positive tech-point gain the villagers earn is doubled", tech.text)
        food = entry("Food Point Doubler")
        self.assertIn("every farming trip is on that list -- blackberry picks and harvests, the Cooking Pit fruit, "
                      "fish and the Golden Fish", food.text)
        self.assertIn("it doubles mushrooms, crabs", food.text)
        self.assertEqual((tech.verified, food.verified), (gm.CODE, gm.CODE))

    def test_running_for_all_needs_a_free_like(self) -> None:
        text = entry("All Villagers Like Running").text
        self.assertIn("every living villager with a free Like slot comes to like running", text)
        self.assertIn("a villager whose 3 Like slots are full gets no like", text)

    def test_the_rows_are_code_but_one(self) -> None:
        unconfirmed = [e.name for e in items.entries() if e.kind == items.PATCHER and e.verified is False]
        self.assertEqual(unconfirmed, ["Change Appearance for All"])
        self.assertIn("5 real-life seconds after it is bought", entry("Island Event").text)
        self.assertIn("brings 3 children", entry("Barrel of Babies").text)


class Hidden(unittest.TestCase):
    def test_b_key_has_no_effect(self) -> None:
        e = hidden_entry("B (village screen)")
        self.assertIn("the key has no effect", e.text)
        self.assertEqual(e.verified, C)

    def test_f3_is_the_mouse_pointer(self) -> None:
        text, verified = hidden_entry("F3 (Puzzles and Milestones)").subs[0]
        self.assertTrue(text.startswith("The setting is whether the mouse pointer is drawn"))
        self.assertEqual(verified, C)

    def test_the_ground_clicks(self) -> None:
        text, verified = hidden_entry("The collection displays (village)").subs[0]
        self.assertIn("a click on the water while the game runs makes a splash and a ripple instead", text)
        self.assertEqual(verified, C)
        other = hidden_entry("Other places (village)")
        for line in ("\"Time remaining for fire:\"", "\"Berries remaining:\"", "\"Cutting tools left:\"",
                     "\"Still need <n> additional herbs!\"", "One spot opens the Mausoleum screen."):
            self.assertIn(line, other.text)
        self.assertNotIn("not traced", other.text)
        self.assertEqual(other.verified, C)


if __name__ == "__main__":
    unittest.main()
