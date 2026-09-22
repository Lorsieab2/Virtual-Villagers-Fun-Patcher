r"""Pregnancy state and litter size in the roster and the history (#418 phase 2A).

Both fields were already MEASURED -- the parentage exporter reads them for
every game it supports -- but the population layout never declared them, so
neither the roster nor the history showed whether a villager was carrying.

    litter      VV1 0x35C, VV2 0x544, VV3 0xE90, VV4/VV5 0x1C50
    pregnancy   VV1 0x358 (the due field), VV2 0x5E4 (a flag written at
                0x44BA10). VV3/VV4/VV5 have no measured field and declare 0,
                so nothing is printed for them rather than a guess -- the same
                rule the skill table already follows.

TWO RENDERING DECISIONS, both load-bearing:

* The due field is a COUNTDOWN, not a boolean. Read live from the owner's
  village, Akika held 787 and Hawa 782 while pregnant and both men held 0.
  Printing the number would put a figure in the history that means nothing to
  a reader and changes every tick, so every snapshot would differ even when
  nothing happened. Only its zero/non-zero state is used.

* litter == 0 means ONE baby, not none. It carries 2 or 3 for twins and
  triplets and is cleared at delivery, so a "Babies in pregnancy: 0" line
  would say the opposite of the truth. It is printed only when > 1.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POP_C = ROOT / "native" / "population_export" / "population_export.c"
PAR_C = ROOT / "native" / "parentage_export" / "parentage_export.c"

# game -> (due, litter) as this change declares them. 0 means "not measured".
# game -> (age_at_conception, litter). 0 means "not established for this game".
#
# VV3's pair was located live: +0xE8C is non-zero for exactly the 13 of 85
# villagers whose litter is also non-zero, every value sits at or just below
# that villager's own age, and Zania -- age 972, litter 3, conceived at 972 --
# was shown by the game as carrying. VV4 and VV5 are not yet verified against
# a running village and stay at 0 rather than inheriting VV3's shape.
EXPECTED = {
    1: (0x358, 0x35C),
    2: (0x5E4, 0x544),
    3: (0xE8C, 0xE90),
    4: (0x1C4C, 0x1C50),
    5: (0x1C4C, 0x1C50),
}


def function(source: str, opening: str) -> str:
    start = source.index(opening)
    return source[start:source.index("\n}", start)]


def population_rows() -> dict[int, dict[str, int]]:
    source = POP_C.read_text(encoding="utf-8")
    table = source[source.index("GAME_LAYOUTS[6] = {"):]
    table = re.sub(r"/\*.*?\*/", "", table, flags=re.DOTALL)
    names = [
        "villagers_rva", "villagers_rva_is_pointer",
        "record_base", "stride", "slots",
        "active", "age", "head", "body",
        "name", "name_capacity",
        "father_name", "father_name_capacity", "father_head", "father_body",
        "skills", "skill_count", "skills_are_float",
        "age_at_conception", "litter",
        "likes", "dislikes", "preference_slots",
    ]
    rows = {}
    for m in re.finditer(
        r'\{\s*1,\s*((?:0x[0-9A-Fa-f]+u?|\w+|,|\s)+?)"Virtual Villagers (\d)"',
        table, re.DOTALL,
    ):
        values = [int(v.rstrip("u"), 0)
                  for v in re.findall(r"0x[0-9A-Fa-f]+u?|\b\d+u?\b", m.group(1))]
        rows[int(m.group(2))] = dict(zip(names, values))
    return rows


class PregnancyLayoutTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rows = population_rows()
        self.pop = POP_C.read_text(encoding="utf-8")

    def test_every_game_declares_the_expected_fields(self):
        self.assertEqual(set(self.rows), set(EXPECTED), "a game row went missing")
        for game, (due, litter) in EXPECTED.items():
            with self.subTest(game=game):
                self.assertEqual(self.rows[game]["age_at_conception"], due)
                self.assertEqual(self.rows[game]["litter"], litter)

    def test_the_litter_offsets_are_the_parentage_exporters_own(self):
        """Not retyped: the same field the conception log already reads.

        A litter offset that drifted from the parentage exporter's would make
        the two logs disagree about the same pregnancy. Matched per game
        against that exporter's own row, not merely "appears somewhere in the
        file" -- which would pass even if VV3's offset were used for VV4.
        """
        par = PAR_C.read_text(encoding="utf-8")
        table = par[par.index("GAME_LAYOUTS[6] = {"):]
        table = re.sub(r"/\*.*?\*/", "", table, flags=re.DOTALL)
        found = {}
        for m in re.finditer(
            r'FATHER_BY_\w+,\s*(0x[0-9A-Fa-f]+|0),\s*(0x[0-9A-Fa-f]+|0),'
            r'\s*(0x[0-9A-Fa-f]+|0),.*?L"Virtual Villagers (\d) Parentage Log"',
            table, re.DOTALL,
        ):
            found[int(m.group(4))] = int(m.group(3), 0)
        self.assertEqual(set(found), set(EXPECTED), "could not read every parentage row")
        for game, (_, litter) in EXPECTED.items():
            with self.subTest(game=game):
                if litter == 0:
                    # Not declared yet (VV4, VV5): nothing is printed for them,
                    # which is correct until a running village confirms the
                    # offset. Silence is allowed; a WRONG value is not.
                    continue
                self.assertEqual(
                    litter, found[game],
                    "VV%d litter: population says 0x%X, parentage says 0x%X"
                    % (game, litter, found[game]),
                )

    def test_every_declared_field_fits_inside_the_record(self):
        for game, row in self.rows.items():
            with self.subTest(game=game):
                for field in ("age_at_conception", "litter"):
                    off = row[field]
                    if off:
                        self.assertLess(off + 4, row["stride"],
                                        "%s reaches past the stride" % field)

    def test_every_game_is_now_established(self):
        """All five are declared, each confirmed against ground truth.

        VV1 live (Akika age 827 holding 787, cleared on delivery); VV2 from the
        repo's own measurement; VV3 live (13 of 85 carrying) and the owner's
        Cheat Engine table; VV4 and VV5 from that table, corroborated in the
        executable -- each writes its age clock into this field in the
        conception routine, immediately before the litter, and VV4's is the
        only write to the field in the whole image.
        """
        for game, (aac, litter) in EXPECTED.items():
            with self.subTest(game=game):
                self.assertNotEqual(aac, 0, "VV%d has no pregnancy field" % game)
                self.assertNotEqual(litter, 0, "VV%d has no litter field" % game)

    def test_the_layout_guard_checks_them(self):
        guard = function(self.pop, "static int layout_is_sane(")
        self.assertIn("g->age_at_conception != 0u && g->age_at_conception + WORD > g->stride", guard)
        self.assertIn("g->litter != 0u && g->litter + WORD > g->stride", guard)


class PregnancyOutputTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pop = POP_C.read_text(encoding="utf-8")
        self.writer = function(self.pop, "static int write_villager(")

    def test_pregnancy_prints_state_not_the_countdown(self):
        """The raw value would change every tick and mean nothing to a reader."""
        self.assertIn('fprintf(file, "  Pregnant: yes\\n")', self.writer)
        self.assertNotIn('"  Pregnant: %d', self.writer)
        self.assertNotIn('"  Due: %d', self.writer)

    def test_pregnancy_is_only_printed_when_true(self):
        self.assertIn("if (g->age_at_conception != 0u && *(const int *)(record + g->age_at_conception) != 0) {",
                      self.writer)

    def test_a_single_baby_prints_no_litter_line(self):
        """litter == 0 means ONE baby; a "0" line would say the opposite."""
        self.assertIn("litter > 1", self.writer)
        self.assertNotIn("litter > 0", self.writer)
        self.assertNotIn("litter >= 1", self.writer)

    def test_an_unmeasured_game_prints_nothing(self):
        """Guarded on the offset, so VV3-VV5 emit no pregnancy line at all."""
        self.assertIn("if (g->litter != 0u) {", self.writer)

    def test_the_lines_are_written_before_the_preferences(self):
        """A villager's own facts stay together, ahead of likes and dislikes."""
        preg = self.writer.index('"  Pregnant: yes')
        likes = self.writer.index('"  Likes: %s')
        self.assertLess(preg, likes)

    def test_both_lines_check_their_write(self):
        """Every other field in this writer fails the export on a short write."""
        block = self.writer[self.writer.index('"  Pregnant: yes'):]
        block = block[:block.index("Likes and dislikes")]
        self.assertEqual(block.count("return 0;"), 2,
                         "a pregnancy write is not checked")


if __name__ == "__main__":
    unittest.main()
