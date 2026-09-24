r"""Pregnancy state and litter size in the roster and the history (#418 phase 2A).

Both fields were already MEASURED -- the parentage exporter reads them for
every game it supports -- but the population layout never declared them, so
neither the roster nor the history showed whether a villager was carrying.

    pregnancy   VV1 0x358, VV2 0x540, VV3 0xE8C, VV4/VV5 0x1C4C
    litter      VV1 0x35C, VV2 0x544, VV3 0xE90, VV4/VV5 0x1C50

All five come from the owner's Cheat Engine tables, recorded in
docs/villager-record-reference.md, which outrank any measurement of a
running process. See that file before changing a value here.

VV2 was briefly shipped as 0x5E4 and that was WRONG. Read live, 0x5E4 holds
the values 1, 3 and 5 across a village; a litter is never 5, and the field is
two orders of magnitude too small to be an age. It must not be reinstated --
the mutation harness carries a case (M8) that fails if it is.

TWO RENDERING DECISIONS, both load-bearing:

* The pregnancy field holds the mother's age at conception, not a boolean and
  not a countdown. Read live, VV1's Akika held 787 against her age of 827 and
  Hawa 782 against 822, while every man held 0. Printing the number would put
  a figure in the history that means nothing to a reader and differs in every
  snapshot, so only its zero/non-zero state is used.

  The owner treats PREGNANT AND NURSING AS ONE STATE -- the game's own panel
  reads "Nursing for: N min" and there is no separate pregnancy display -- so
  this field marking a nursing mother is correct rather than a false positive.

* litter == 0 means ONE baby, not none. The game writes this field only on the
  twins and triplets branches (VV3 at 0x455BBF and 0x455BDD, VV4 at 0x45E8C0
  and 0x45E8D3, VV5 at 0x465F10 and 0x465F23), never for a single birth, so a
  "Babies in pregnancy: 0" line would say the opposite of the truth. It is
  printed only when > 1.
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
# VV2's pair is the owner's Cheat Engine table, whose "Change address" dialog
# resolves Villager 1's Babyplets to base 0x0D730020 + 0x544, putting the
# pregnancy field one dword below at +0x540. Read live, +0x540 is the only
# field in the whole 0xE48C record that is non-zero for exactly the carrying
# women and zero for everyone else, and every holder is female.
#
# VV3's pair was located live: +0xE8C is non-zero for exactly the 13 of 85
# villagers whose litter is also non-zero, every value sits at or just below
# that villager's own age, and Zania -- age 972, litter 3, conceived at 972 --
# was shown by the game as carrying. VV4 and VV5 are not yet verified against
# a running village and stay at 0 rather than inheriting VV3's shape.
EXPECTED = {
    1: (0x358, 0x35C),
    2: (0x540, 0x544),
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
        "parent_father_name", "parent_mother_name", "parent_name_capacity",
        "parent_father_head", "parent_father_body",
        "parent_mother_head", "parent_mother_body",
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
            r'\s*(0x[0-9A-Fa-f]+|0),.*?L"Virtual Villagers (\d) Births and Conceptions Log"',
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
        # Matched as a CONDITION rather than as one spelling of it:
        # the gate gained a with_pregnancy term and now wraps across
        # lines, which is not a change to the property here.
        self.assertIn("g->age_at_conception != 0u", self.writer)
        self.assertIn(
            "*(const int *)(record + g->age_at_conception) != 0",
                      self.writer)

    def test_a_single_baby_prints_no_litter_line(self):
        """litter == 0 means ONE baby; a "0" line would say the opposite."""
        self.assertIn("litter > 1", self.writer)
        self.assertNotIn("litter > 0", self.writer)
        self.assertNotIn("litter >= 1", self.writer)

    def test_an_unmeasured_game_prints_nothing(self):
        """Guarded on the offset, so VV3-VV5 emit no pregnancy line at all."""
        # The litter is likewise gated on with_pregnancy now, so the
        # `if (` prefix no longer immediately precedes it.
        self.assertIn("g->litter != 0u", self.writer)

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


class LayoutGuardGatesEveryReaderTests(unittest.TestCase):
    """The layout check must STOP the export, not merely report on it.

    Every field this module adds is read straight out of a villager record at
    a declared offset, and `layout_is_sane` is what proves those offsets fit
    inside the record before anything reads them. The roster and the history
    both run in `export_population` after that check.

    A mutation that leaves the call in place but deletes its early return --
    `if (!layout_is_sane(g)) { /* checked later */ }` -- passed every other
    test in this file. The guard would still be called, still compute the
    right answer, and the export would walk a record with fields reaching
    past the stride anyway, reporting one villager's pregnancy as another's.
    That is the exact failure the guard exists to prevent, so it needs a test
    that fails when the guard stops guarding.
    """

    def setUp(self) -> None:
        self.pop = POP_C.read_text(encoding="utf-8")

    def test_the_layout_check_returns_rather_than_falling_through(self):
        index = self.pop.index("if (!layout_is_sane(g)) {")
        body = self.pop[index:self.pop.index("}", index)]
        self.assertIn(
            "return 0;", body,
            "layout_is_sane is called but its failure does not stop the "
            "export: every later read, including the history's, would use "
            "offsets that were never proven to fit the record")

    def test_the_history_runs_after_the_layout_check(self):
        """Ordering is what makes the single guard cover both writers."""
        self.assertLess(
            self.pop.index("if (!layout_is_sane(g)) {"),
            self.pop.index("append_history(g, villagers"),
            "the history is appended before the layout is validated")


if __name__ == "__main__":
    unittest.main()
