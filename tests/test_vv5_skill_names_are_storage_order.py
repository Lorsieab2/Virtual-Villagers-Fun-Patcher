"""VV5 names its skills in the order the RECORD stores them, not the order the
Details screen lists them.

New Believers has SIX skills -- the other games' five plus Devotion. It
displays Farming, Building, Research, Healing, Parenting, Devotion and stores
Farming, Parenting, Healing, Research, Building, Devotion.

Four villagers each carry exactly one 100, at a different index, so four of
the six slots are named by an unambiguous full bar:

  Pari   [100, 40, 0, 0, 7, 0]    Farming full   -> index 0
  Apatoa [0, 40, 100, 0, 13, 0]   Healing full   -> index 2
  Turuki [0, 53, 0, 100, 25, 0]   Research full  -> index 3
  Moti   [0, 76, 0, 0, 7, 100]    Devotion full  -> index 5

All four also show a mid-length bar at index 1 that every screen names
Parenting (53, 40, 40, 76) and a short bar at index 4 that every screen names
Building (25, 7, 13, 7). Those two slots are corroborated four times each
rather than inferred by elimination.

The first five match VV3's and VV4's order with Devotion appended, but they
are confirmed on VV5's own evidence: VV1 and VV2 put Building at index 1 where
VV3, VV4 and VV5 put it at index 4, so there is no single order shared across
the series.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POP_C = ROOT / "native" / "population_export" / "population_export.c"

VV5_STORAGE_ORDER = (
    "Farming", "Parenting", "Healing", "Research", "Building", "Devotion",
)
VV5_DISPLAY_ORDER = (
    "Farming", "Building", "Research", "Healing", "Parenting", "Devotion",
)

# slot -> (skill, the villager whose full bar named it, their array)
SLOT_EVIDENCE = {
    0: ("Farming", "Pari", [100, 40, 0, 0, 7, 0]),
    2: ("Healing", "Apatoa", [0, 40, 100, 0, 13, 0]),
    3: ("Research", "Turuki", [0, 53, 0, 100, 25, 0]),
    5: ("Devotion", "Moti", [0, 76, 0, 0, 7, 100]),
}

# The two slots named by all four screens rather than by one full bar.
CORROBORATED = {
    1: ("Parenting", [53, 40, 40, 76]),
    4: ("Building", [25, 7, 13, 7]),
}

SCREENSHOTS = {
    "Turuki": ([0, 53, 0, 100, 25, 0], {"Research", "Parenting", "Building"}),
    "Pari": ([100, 40, 0, 0, 7, 0], {"Farming", "Parenting", "Building"}),
    "Apatoa": ([0, 40, 100, 0, 13, 0], {"Healing", "Parenting", "Building"}),
    "Moti": ([0, 76, 0, 0, 7, 100], {"Devotion", "Parenting", "Building"}),
}

VISIBLE_AT = 5


def c_string_list(source: str, symbol: str) -> list[str]:
    match = re.search(
        r"static const char \*const " + re.escape(symbol) + r"\[[^\]]*\]\s*=\s*\{(.*?)\};",
        source,
        re.S,
    )
    assert match, "%s not found" % symbol
    return re.findall(r'"([^"]*)"', match.group(1))


class Vv5SkillNameOrderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pop = POP_C.read_text(encoding="utf-8")
        self.names = c_string_list(self.pop, "SKILL_NAMES_VV5")

    def test_the_storage_and_display_orders_really_do_differ(self):
        self.assertNotEqual(VV5_STORAGE_ORDER, VV5_DISPLAY_ORDER)

    def test_vv5_table_is_in_storage_order(self):
        self.assertEqual(tuple(self.names[:6]), VV5_STORAGE_ORDER)

    def test_vv5_table_is_not_the_display_order(self):
        self.assertNotEqual(tuple(self.names[:6]), VV5_DISPLAY_ORDER)

    def test_vv5_has_six_skills_with_devotion_last(self):
        """The sixth slot is real and is Devotion, not a padding entry."""
        self.assertEqual(self.names[5], "Devotion")

    def test_vv5_does_not_use_vv1_and_vv2_positions(self):
        self.assertEqual(self.names[4], "Building")
        self.assertNotEqual(self.names[1], "Building")

    def test_every_full_bar_slot_matches_the_villager_that_named_it(self):
        for slot, (skill, who, values) in SLOT_EVIDENCE.items():
            with self.subTest(slot=slot, villager=who):
                self.assertEqual(
                    self.names[slot],
                    skill,
                    "slot %d was named %s by %s's full bar (array %s)"
                    % (slot, skill, who, values),
                )

    def test_the_corroborated_slots_match_all_four_screens(self):
        for slot, (skill, values) in CORROBORATED.items():
            with self.subTest(slot=slot):
                self.assertEqual(
                    self.names[slot],
                    skill,
                    "slot %d was named %s on all four screens (values %s)"
                    % (slot, skill, values),
                )

    def test_each_screenshot_is_reproduced_exactly(self):
        for who, (values, seen) in SCREENSHOTS.items():
            with self.subTest(villager=who):
                lit = {self.names[i] for i, v in enumerate(values) if v >= VISIBLE_AT}
                self.assertEqual(lit, seen)

    def test_the_display_order_would_fail_that_check(self):
        wrong = 0
        for values, seen in SCREENSHOTS.values():
            lit = {VV5_DISPLAY_ORDER[i] for i, v in enumerate(values) if v >= VISIBLE_AT}
            if lit != seen:
                wrong += 1
        self.assertGreater(wrong, 0)

    def test_vv5_uses_its_own_table(self):
        self.assertIn("if (game_id == GAME_VV5) { return SKILL_NAMES_VV5; }", self.pop)

    def test_the_log_prints_the_per_game_table(self):
        self.assertIn("skill_names_for(game_id)[skill]", self.pop)
        self.assertNotIn("SKILL_NAMES[skill]", self.pop)

    def test_unverified_games_are_left_alone(self):
        other = c_string_list(self.pop, "SKILL_NAMES_UNVERIFIED")
        self.assertEqual(
            tuple(other[:6]),
            ("Farming", "Building", "Research", "Healing", "Breeding", "Parenting"),
        )


if __name__ == "__main__":
    unittest.main()
