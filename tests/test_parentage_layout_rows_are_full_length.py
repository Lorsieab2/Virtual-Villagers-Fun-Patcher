"""Every parentage layout row must initialise every field, positionally.

`GAME_LAYOUTS` is a positional initialiser and MSVC does not warn about a short
row: the missing trailing fields are zero-filled and, worse, every value after
the omission keeps its written position, so adding a field in the middle of the
struct silently shifts one game's data by a slot. Nothing downstream would look
wrong -- the offsets are all plausible small integers -- and the log would carry
confident garbage for that game.

That is not hypothetical here. Two fields (`father_head_copy`, `father_body_copy`)
were inserted before `no_villager` after the rows were written, so a row that
was not updated would now be reading its `no_villager` sentinel as a trait
offset.

This checks the arity of every row and pins the values that prove the alignment
is right rather than merely consistent.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORTER = ROOT / "native/parentage_export/parentage_export.c"


def _fields() -> list[str]:
    source = EXPORTER.read_text(encoding="utf-8")
    body = source[source.index("struct game_layout {") :]
    body = body[: body.index("\n};")]
    # Every declared type must appear here. A field whose type is missing from
    # this list is invisible to the parser, which UNDERCOUNTS the struct and
    # makes a correctly-aligned row look one value too long -- misleading in
    # the opposite direction to the misalignment this file exists to catch.
    # `const char *const *` (the per-game skill-name table) is one such form.
    return re.findall(
        r"^\s+(?:(?:unsigned int|int|const wchar_t \*)\s+"
        r"|const char \*const \*\s*|const char \*\s*)(\w+);",
        body,
        re.M,
    )


def _rows() -> list[list[str]]:
    """The five real rows, comments stripped, as lists of initialiser values."""
    source = EXPORTER.read_text(encoding="utf-8")
    table = source[source.index("GAME_LAYOUTS[6] = {") :]
    table = table[: table.index("\n};")]
    table = re.sub(r"/\*.*?\*/", "", table, flags=re.S)
    # Index 0 is the deliberately-empty unsupported row; the rest are VV1..VV5.
    raw = re.findall(r"\{(.*?)\}", table, re.S)[1:]
    rows = []
    for entry in raw:
        # Split on commas that are not inside the trailing wide-string literal.
        parts = [p.strip() for p in re.split(r',(?![^"]*"\s*$)', entry) if p.strip()]
        rows.append(parts)
    return rows


class ParentageLayoutRowsAreFullLengthTests(unittest.TestCase):
    def setUp(self):
        self.fields = _fields()
        self.rows = _rows()

    def test_every_game_has_a_row(self):
        self.assertEqual(len(self.rows), 5, "expected one row per game, VV1..VV5")

    def test_every_row_initialises_every_field(self):
        # log_name is the trailing member and is not matched by the field regex
        # above, so a full row carries one more value than that list.
        expected = len(self.fields) + 1
        for index, row in enumerate(self.rows, start=1):
            with self.subTest(game=index):
                self.assertEqual(
                    len(row),
                    expected,
                    "VV%d initialises %d of %d fields; a short positional row "
                    "shifts every later value by a slot without any warning"
                    % (index, len(row), expected),
                )

    def test_the_alignment_is_right_not_merely_consistent(self):
        """Pin values that can only be correct if no slot has shifted.

        Arity alone would still pass if two adjacent fields were transposed, or
        if every row were short by the same amount. These are read by name from
        the decoded row, so they fail loudly if the columns move.
        """
        names = self.fields + ["log_name"]
        decoded = [dict(zip(names, row)) for row in self.rows]

        # VV1 is the only game with a "no such villager" sentinel, and it is
        # 0xC7. If a slot had shifted this would be a trait offset or zero.
        self.assertEqual(decoded[0]["no_villager"], "0xC7")

        # Every game but VV1 copies the father's traits onto the mother. These
        # were all zero except VV2 until VV3/VV4/VV5's conception routines were
        # disassembled; the offsets are pinned against each stock executable in
        # tests/test_parentage_father_copies.py.
        #
        # They still serve this test's purpose, which is detecting a shifted
        # column: each value is distinct from its neighbours in the same row,
        # so a slot shift moves a recognisable number into the wrong name.
        expected_copies = {
            0: ("0", "0"),            # VV1 records nothing about the father
            1: ("0x5E0", "0x5DC"),
            2: ("0xE68", "0xE64"),
            3: ("0x1C30", "0x1C2C"),
            4: ("0x1C30", "0x1C2C"),
        }
        for index, (head, body) in expected_copies.items():
            with self.subTest(game=index + 1):
                self.assertEqual(decoded[index]["father_head_copy"], head)
                self.assertEqual(decoded[index]["father_body_copy"], body)
                if head != "0":
                    # Body sits four bytes BEFORE head in every game that
                    # copies. A transposed pair is exactly what a shifted slot
                    # or a by-eye pairing produces, and it would otherwise look
                    # entirely plausible.
                    self.assertEqual(int(body, 16) + 4, int(head, 16))

        # The copies must not collide with the mother's own trait offsets, which
        # is what reading a shifted slot would look like.
        for index, entry in enumerate(decoded):
            with self.subTest(game=index + 1):
                copies = {entry["father_head_copy"], entry["father_body_copy"]}
                copies.discard("0")
                self.assertNotIn(entry["head"], copies)
                self.assertNotIn(entry["body"], copies)

        # Fields in the MIDDLE of the row, which a shift confined to the
        # middle would move while arity and the trailing fields stay right.
        # That gap is not hypothetical: inserting father_key_capacity after
        # `father` while writing its value after `litter` shifted every row,
        # putting the litter offset into father_key_capacity -- and this test
        # passed, because the count was still correct and the pinned fields
        # were all near the end.
        for index, entry in enumerate(decoded, start=1):
            with self.subTest(game=index):
                # The litter count is a real record offset in every game, so a
                # value that is zero or implausibly small means a slot moved.
                litter = int(entry["litter"], 0)
                self.assertGreater(
                    litter,
                    0x100,
                    "VV%d litter offset %s is too small to be a record field; "
                    "a middle-of-row shift has moved it" % (index, entry["litter"]),
                )
                # The key width is a small count, never an offset. If an offset
                # lands here the row has shifted the other way.
                key = int(entry["father_key_capacity"], 0)
                self.assertLessEqual(
                    key,
                    0x40,
                    "VV%d father_key_capacity %s looks like an offset rather "
                    "than a width; a slot has shifted"
                    % (index, entry["father_key_capacity"]),
                )

        # Every row names its own game's log file, so a wholesale row shift
        # cannot hide behind matching arity.
        for index, entry in enumerate(decoded, start=1):
            with self.subTest(game=index):
                self.assertIn("Virtual Villagers %d" % index, entry["log_name"])

    def test_the_two_copy_fields_precede_no_villager(self):
        """The insertion point that made this test necessary, pinned.

        They were added before `no_villager`, so anything that moves them
        changes what an un-updated row would silently read.
        """
        self.assertLess(
            self.fields.index("father_head_copy"), self.fields.index("no_villager")
        )
        self.assertLess(
            self.fields.index("father_body_copy"), self.fields.index("no_villager")
        )


if __name__ == "__main__":
    unittest.main()
