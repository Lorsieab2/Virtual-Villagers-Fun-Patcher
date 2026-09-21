"""VV1 names its skills in the order the RECORD stores them, not the order the
Details screen lists them.

The two differ, and assuming they matched mislabelled three slots out of five
in every population log. The offset (0x3BC) and the count (5) were always
right; only the names were wrong.

Measured against the owner's running game on 2026-09-21:

  Yepa, a child with exactly one non-zero skill, holds it at index 4, and her
  Details screen shows Research. One villager, one skill, no ambiguity.

  Rongo's five values are all distinct -- 29, 39, 50, 59, 78 -- and his bars
  rank, shortest to longest: Breeding, Building, Farming, Healing, Research.
  That fixes every slot at once.

Building and Healing land on the same name in both orders, which is why the
bug survived: two of every five numbers were correctly labelled.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POP_C = ROOT / "native" / "population_export" / "population_export.c"
SORT_C = ROOT / "native" / "vv1_sort_by" / "vv1_sort_by.c"

# The measured storage order. Index is the slot at 0x3BC + 4*index.
VV1_STORAGE_ORDER = ("Breeding", "Building", "Farming", "Healing", "Research")

# What the Details screen lists, top to bottom. Kept here to assert the two
# are NOT the same, so a future edit cannot quietly collapse them again.
VV1_DISPLAY_ORDER = ("Farming", "Building", "Research", "Healing", "Breeding")

# Villagers read live from the running game: name -> (values by index, the
# skill the game's own Details screen names as highest).
LIVE_VILLAGERS = {
    "Rongo": ([29, 39, 50, 59, 78], "Research"),
    "Bobo": ([33, 0, 49, 49, 87], "Research"),
    "Akika": ([43, 25, 80, 24, 69], "Farming"),
    "Hawa": ([40, 61, 67, 0, 51], "Farming"),
    "Kifa": ([0, 0, 36, 0, 0], "Farming"),
    "Maiya": ([0, 0, 0, 5, 0], "Healing"),
    "Yepa": ([0, 0, 0, 0, 7], "Research"),
}


def c_string_list(source: str, symbol: str) -> list[str]:
    """The string literals of a `static const char *const SYMBOL[...] = {...};`."""
    match = re.search(
        r"static const char \*const " + re.escape(symbol) + r"\[[^\]]*\]\s*=\s*\{(.*?)\};",
        source,
        re.S,
    )
    assert match, "%s not found" % symbol
    return re.findall(r'"([^"]*)"', match.group(1))


class Vv1SkillNameOrderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pop = POP_C.read_text(encoding="utf-8")

    def test_the_storage_and_display_orders_really_do_differ(self):
        """Guard the premise: if these ever match, this whole file is moot."""
        self.assertNotEqual(
            VV1_STORAGE_ORDER,
            VV1_DISPLAY_ORDER,
            "VV1 stores its skills in a different order than it displays them",
        )

    def test_vv1_table_is_in_storage_order(self):
        names = c_string_list(self.pop, "SKILL_NAMES_VV1")
        self.assertEqual(tuple(names[:5]), VV1_STORAGE_ORDER)

    def test_vv1_table_is_not_the_display_order(self):
        """The exact bug: the screen's order used as though it were the record's."""
        names = c_string_list(self.pop, "SKILL_NAMES_VV1")
        self.assertNotEqual(
            tuple(names[:5]),
            VV1_DISPLAY_ORDER,
            "VV1 is labelled in Details-screen order again",
        )

    def test_every_live_villager_is_labelled_as_the_game_labels_them(self):
        """The real check: our names must agree with the game's own screen."""
        names = c_string_list(self.pop, "SKILL_NAMES_VV1")
        for who, (values, expected) in LIVE_VILLAGERS.items():
            with self.subTest(villager=who):
                best = max(range(len(values)), key=lambda i: values[i])
                self.assertEqual(
                    names[best],
                    expected,
                    "%s's highest skill is slot %d; the game calls it %s"
                    % (who, best, expected),
                )

    def test_the_display_order_would_fail_that_check(self):
        """Proves the test can actually detect the bug it exists for."""
        wrong = 0
        for values, expected in LIVE_VILLAGERS.values():
            best = max(range(len(values)), key=lambda i: values[i])
            if VV1_DISPLAY_ORDER[best] != expected:
                wrong += 1
        self.assertGreater(
            wrong, 0, "the old order must mislabel someone, or this proves nothing"
        )

    def test_the_unverified_table_is_left_alone(self):
        """VV2-VV5 keep their names until each is checked against its own game.

        Correcting them from VV1's evidence would repeat the assumption that
        caused this bug in the first place.
        """
        names = c_string_list(self.pop, "SKILL_NAMES_UNVERIFIED")
        self.assertEqual(tuple(names[:5]), VV1_DISPLAY_ORDER)

    def test_only_vv1_uses_the_corrected_table(self):
        self.assertIn("if (game_id == GAME_VV1) { return SKILL_NAMES_VV1; }", self.pop)

    def test_the_log_prints_the_per_game_table(self):
        self.assertIn("skill_names_for(game_id)[skill]", self.pop)
        self.assertNotIn("SKILL_NAMES[skill]", self.pop)

    def test_sort_by_records_the_storage_order(self):
        """Sorting uses values, not names, but the comment must not mislead."""
        sort = SORT_C.read_text(encoding="utf-8")
        match = re.search(r"#define VV1_SKILLS_OFFSET\s+0x3BCu(.*?)\*/", sort, re.S)
        self.assertIsNotNone(match, "the skills offset comment is gone")
        comment = match.group(1).lower()
        for name in VV1_STORAGE_ORDER:
            self.assertIn(name.lower(), comment)
        self.assertIn("storage order", comment)


if __name__ == "__main__":
    unittest.main()
