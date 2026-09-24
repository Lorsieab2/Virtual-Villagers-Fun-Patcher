"""The carrying-father block is printed only while she is actually carrying.

The population roster prints a "Father:" block naming the man who fathered the
child a woman is CARRYING. The games copy his details onto her at conception
and never clear them at the birth, so testing the name alone printed the block
for every woman who had ever been pregnant, for the rest of her life.

In the owner's own logs the count of blocks should equal the count of
pregnancies, and did not: VV2 1 pregnant / 2 blocks, VV3 16 / 38, VV4 9 / 31,
VV5 5 / 18. VV3's Waikiki printed "Father: Rano" from a pregnancy long over
directly above "Parents: Father: Poro", her real father.

This guards the gate itself, and separately guards the property the gate
depends on: that every game carrying father fields also carries the pregnancy
field used to test them. A game with father fields but no pregnancy field
would silently lose the block altogether.
"""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(ROOT, "native", "population_export", "population_export.c")


def read_source():
    with open(SOURCE, encoding="utf-8", newline="") as handle:
        return handle.read()


class CarryingFatherIsGatedOnThePregnancy(unittest.TestCase):
    def setUp(self):
        self.c = read_source()

    def _gate(self):
        """The condition guarding the carrying-father block."""
        marker = "record[g->father_name] != "
        self.assertIn(marker, self.c, "the carrying-father gate moved")
        start = self.c.rindex("if (", 0, self.c.index(marker))
        end = self.c.index(") {", start)
        return self.c[start:end]

    def test_the_gate_tests_the_pregnancy(self):
        """The name alone must not be enough to print the block."""
        gate = self._gate()
        self.assertIn(
            "age_at_conception", gate,
            "the carrying-father block is gated on the father NAME alone. "
            "The games never clear that name at the birth, so the block "
            "prints for every woman who has ever been pregnant.",
        )
        self.assertIn(
            "record + g->age_at_conception", gate,
            "the gate names age_at_conception but does not READ it from the "
            "record, so it tests whether the game has the field rather than "
            "whether this villager is carrying.",
        )

    def test_the_block_is_printed_inside_that_gate(self):
        """The Father line must be under the gate, not beside it."""
        marker = "record[g->father_name] != "
        start = self.c.index(marker)
        body = self.c[start:start + 1200]
        self.assertIn('"  Father: %s', body,
                      "the Father line is no longer inside the gated block")

    def test_every_game_with_father_fields_has_a_pregnancy_field(self):
        """Otherwise the gate silently drops the block for that game.

        Read positionally from the layout table: these are brace-initialised
        rows without designators, so the fields are located by their order in
        the struct rather than by name.
        """
        start = self.c.index("static const struct game_layout GAME_LAYOUTS")
        table = self.c[start:self.c.index("\n};", start)]

        checked = 0
        for game in ("VV2", "VV3", "VV4", "VV5"):
            row = re.search(
                r'\{(?:[^{}]|\{[^{}]*\})*?"Virtual Villagers ' + game[2] + r'"',
                table[table.index("/* " + game + " --"):],
                re.S,
            )
            self.assertIsNotNone(row, game + ": layout row not found")
            text = re.sub(r"/\*.*?\*/", " ", row.group(0), flags=re.S)
            numbers = re.findall(r"\b(0x[0-9A-Fa-f]+|\d+)u\b", text)
            self.assertGreater(len(numbers), 25, game + ": row parsed short")

            # Field order in struct game_layout, counting only the `unsigned
            # int` members that carry a `u` suffix in the table.
            order = [
                "villagers_rva", "record_base", "stride", "slots", "active",
                "age", "head", "body", "name", "name_capacity",
                "father_name", "father_name_capacity", "father_head",
                "father_body", "parent_father_name", "parent_mother_name",
                "parent_name_capacity", "parent_father_head",
                "parent_father_body", "parent_mother_head",
                "parent_mother_body", "skills", "skill_count",
                "age_at_conception", "litter",
            ]
            values = {}
            for index, field in enumerate(order):
                if index < len(numbers):
                    values[field] = int(numbers[index], 0)

            father = values.get("father_name", 0)
            pregnancy = values.get("age_at_conception", 0)
            if father:
                self.assertNotEqual(
                    pregnancy, 0,
                    game + " carries father fields but no pregnancy field, so "
                    "gating the block on the pregnancy would drop it entirely.",
                )
                checked += 1

        self.assertEqual(checked, 4,
                         "expected VV2-VV5 to carry father fields; checked "
                         + str(checked))


if __name__ == "__main__":
    unittest.main()
