"""VV4 names its skills in the order the RECORD stores them, not the order the
Details screen lists them.

The Tree of Life displays Farming, Building, Research, Healing, Parenting and
stores Farming, Parenting, Healing, Research, Building.

Every slot is named by a villager whose own Details screen showed that bar.
None is inferred by elimination:

  Tapa   [100, 19, 0, 0, 53]   Farming his full bar   -> index 0
  Pai    [0, 29, 100, 0, 0]    Healing full, Parenting mid
                               -> index 2 Healing, index 1 Parenting
  Dodi   [0, 0, 0, 100, 0]     Research his only bar  -> index 3
  Piko   [0, 7, 0, 51, 100]    Building his full bar  -> index 4
  Upaupa [0, 27, 100, 30, 10]  corroborates Healing, Research and Parenting

VV4 stores these as floats rather than ints. That changes how a value is read,
not which slot holds which skill, so the ordering evidence is unaffected.

This order matches VV3's, but it is confirmed on VV4's own evidence rather
than inherited: VV1 and VV2 put Building at index 1, so there is no single
order shared across the series.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POP_C = ROOT / "native" / "population_export" / "population_export.c"

VV4_STORAGE_ORDER = ("Farming", "Parenting", "Healing", "Research", "Building")
VV4_DISPLAY_ORDER = ("Farming", "Building", "Research", "Healing", "Parenting")

SLOT_EVIDENCE = {
    0: ("Farming", "Tapa", [100, 19, 0, 0, 53]),
    1: ("Parenting", "Pai", [0, 29, 100, 0, 0]),
    2: ("Healing", "Pai", [0, 29, 100, 0, 0]),
    3: ("Research", "Dodi", [0, 0, 0, 100, 0]),
    4: ("Building", "Piko", [0, 7, 0, 51, 100]),
}

# villager -> (values by storage index, the bars actually visible on screen)
SCREENSHOTS = {
    "Tapa": ([100, 19, 0, 0, 53], {"Farming", "Parenting", "Building"}),
    "Pai": ([0, 29, 100, 0, 0], {"Parenting", "Healing"}),
    "Dodi": ([0, 0, 0, 100, 0], {"Research"}),
    "Piko": ([0, 7, 0, 51, 100], {"Parenting", "Research", "Building"}),
    "Upaupa": ([0, 27, 100, 30, 10], {"Parenting", "Healing", "Research", "Building"}),
}

VISIBLE_AT = 5  # below this a bar does not render


def c_string_list(source: str, symbol: str) -> list[str]:
    match = re.search(
        r"static const char \*const " + re.escape(symbol) + r"\[[^\]]*\]\s*=\s*\{(.*?)\};",
        source,
        re.S,
    )
    assert match, "%s not found" % symbol
    return re.findall(r'"([^"]*)"', match.group(1))


class Vv4SkillNameOrderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pop = POP_C.read_text(encoding="utf-8")
        self.names = c_string_list(self.pop, "SKILL_NAMES_VV4")

    def test_the_storage_and_display_orders_really_do_differ(self):
        self.assertNotEqual(VV4_STORAGE_ORDER, VV4_DISPLAY_ORDER)

    def test_vv4_table_is_in_storage_order(self):
        self.assertEqual(tuple(self.names[:5]), VV4_STORAGE_ORDER)

    def test_vv4_table_is_not_the_display_order(self):
        self.assertNotEqual(tuple(self.names[:5]), VV4_DISPLAY_ORDER)

    def test_vv4_does_not_use_vv1_and_vv2_positions(self):
        """Building is at index 4 here and at index 1 in VV1 and VV2."""
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
        for who, (values, seen) in SCREENSHOTS.items():
            with self.subTest(villager=who):
                lit = {self.names[i] for i, v in enumerate(values) if v >= VISIBLE_AT}
                self.assertEqual(lit, seen)

    def test_the_display_order_would_fail_that_check(self):
        """Proves the test detects the bug it exists for."""
        wrong = 0
        for values, seen in SCREENSHOTS.values():
            lit = {VV4_DISPLAY_ORDER[i] for i, v in enumerate(values) if v >= VISIBLE_AT}
            if lit != seen:
                wrong += 1
        self.assertGreater(wrong, 0)

    def test_vv4_uses_its_own_table(self):
        self.assertIn("if (game_id == GAME_VV4) { return SKILL_NAMES_VV4; }", self.pop)

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
