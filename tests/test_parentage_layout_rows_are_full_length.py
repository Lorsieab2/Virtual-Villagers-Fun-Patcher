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
    return re.findall(
        r"^\s+(?:unsigned int|int|const wchar_t \*)\s+(\w+);", body, re.M
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

        # VV2 is the only game that copies the father's traits onto the mother.
        self.assertEqual(decoded[1]["father_head_copy"], "0x5E0")
        self.assertEqual(decoded[1]["father_body_copy"], "0x5DC")
        for index in (0, 2, 3, 4):
            with self.subTest(game=index + 1):
                self.assertEqual(decoded[index]["father_head_copy"], "0")
                self.assertEqual(decoded[index]["father_body_copy"], "0")

        # The copies must not collide with the mother's own trait offsets, which
        # is what reading a shifted slot would look like.
        for index, entry in enumerate(decoded):
            with self.subTest(game=index + 1):
                copies = {entry["father_head_copy"], entry["father_body_copy"]}
                copies.discard("0")
                self.assertNotIn(entry["head"], copies)
                self.assertNotIn(entry["body"], copies)

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
