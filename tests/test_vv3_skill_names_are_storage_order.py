"""VV3 names its skills in the order the RECORD stores them, not the order the
Details screen lists them.

The Secret City displays Farming, Building, Research, Healing, Parenting and
stores Farming, Parenting, Healing, Research, Building.

Every slot is named by a villager whose own Details screen showed that bar --
none is inferred by elimination, which matters because VV3's order is NOT the
same as VV1's or VV2's and there is no sibling game to sanity-check it
against.

  Vinapu [100, 0, 0, 5, 0]    Farming his only visible bar  -> index 0
  Yasawa [0, 31, 0, 5, 97]    Building long, Parenting short
                              -> index 4 Building, index 1 Parenting
  Dino   [0, 0, 100, 0, 0]    Healing his only bar          -> index 2
  Totolo [0, 0, 0, 100, 4]    Research his only full bar    -> index 3
  Pangai [0, 10, 89, 100, 0]  Research, Healing and Parenting, corroborating

Values of about 5 or less do not render as a visible bar, which is why the
trace 4s and 5s are absent from those screens; the tests below treat anything
under 10 as invisible for that reason.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POP_C = ROOT / "native" / "population_export" / "population_export.c"

VV3_STORAGE_ORDER = ("Farming", "Parenting", "Healing", "Research", "Building")
VV3_DISPLAY_ORDER = ("Farming", "Building", "Research", "Healing", "Parenting")

# The slot, the skill, and the villager whose single visible bar named it, so
# a regression reports which observation it contradicts.
SLOT_EVIDENCE = {
    0: ("Farming", "Vinapu", [100, 0, 0, 5, 0]),
    1: ("Parenting", "Yasawa", [0, 31, 0, 5, 97]),
    2: ("Healing", "Dino", [0, 0, 100, 0, 0]),
    3: ("Research", "Totolo", [0, 0, 0, 100, 4]),
    4: ("Building", "Yasawa", [0, 31, 0, 5, 97]),
}

# villager -> (values by storage index, the set of bars actually visible on
# that villager's Details screen).
SCREENSHOTS = {
    "Vinapu": ([100, 0, 0, 5, 0], {"Farming"}),
    "Yasawa": ([0, 31, 0, 5, 97], {"Building", "Parenting"}),
    "Dino": ([0, 0, 100, 0, 0], {"Healing"}),
    "Totolo": ([0, 0, 0, 100, 4], {"Research"}),
    "Pangai": ([0, 10, 89, 100, 0], {"Research", "Healing", "Parenting"}),
}

VISIBLE_AT = 10  # a bar below this does not render


def c_string_list(source: str, symbol: str) -> list[str]:
    match = re.search(
        r"static const char \*const " + re.escape(symbol) + r"\[[^\]]*\]\s*=\s*\{(.*?)\};",
        source,
        re.S,
    )
    assert match, "%s not found" % symbol
    return re.findall(r'"([^"]*)"', match.group(1))


class Vv3SkillNameOrderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pop = POP_C.read_text(encoding="utf-8")
        self.names = c_string_list(self.pop, "SKILL_NAMES_VV3")

    def test_the_storage_and_display_orders_really_do_differ(self):
        self.assertNotEqual(VV3_STORAGE_ORDER, VV3_DISPLAY_ORDER)

    def test_vv3_table_is_in_storage_order(self):
        self.assertEqual(tuple(self.names[:5]), VV3_STORAGE_ORDER)

    def test_vv3_table_is_not_the_display_order(self):
        self.assertNotEqual(tuple(self.names[:5]), VV3_DISPLAY_ORDER)

    def test_vv3_order_is_not_borrowed_from_vv1_or_vv2(self):
        """Building is at index 4 here and index 1 in the other two games.

        A copied answer would put it back at index 1, so this fails loudly if
        anyone ever assumes the orders are shared.
        """
        self.assertEqual(self.names[4], "Building")
        self.assertNotEqual(self.names[1], "Building")

    def test_every_slot_matches_the_villager_that_named_it(self):
        for slot, (skill, who, values) in SLOT_EVIDENCE.items():
            with self.subTest(slot=slot, villager=who):
                self.assertEqual(
                    self.names[slot],
                    skill,
                    "slot %d was named %s by %s (array %s)" % (slot, skill, who, values),
                )

    def test_each_screenshot_is_reproduced_exactly(self):
        """The order must light exactly the bars the owner saw, no more, no less."""
        for who, (values, seen) in SCREENSHOTS.items():
            with self.subTest(villager=who):
                lit = {
                    self.names[i] for i, v in enumerate(values) if v >= VISIBLE_AT
                }
                self.assertEqual(lit, seen)

    def test_the_display_order_would_fail_that_check(self):
        """Proves the test detects the bug it exists for."""
        wrong = 0
        for values, seen in SCREENSHOTS.values():
            lit = {
                VV3_DISPLAY_ORDER[i] for i, v in enumerate(values) if v >= VISIBLE_AT
            }
            if lit != seen:
                wrong += 1
        self.assertGreater(wrong, 0)

    def test_vv3_uses_its_own_table(self):
        self.assertIn("if (game_id == GAME_VV3) { return SKILL_NAMES_VV3; }", self.pop)

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
