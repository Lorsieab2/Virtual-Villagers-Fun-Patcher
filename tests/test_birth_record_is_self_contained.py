"""A Birth record can be written from the child's record alone.

The owner's requirement is that all five games ship the same log format, Birth
records included. VV1 supplies its parents as arguments because it stores none
on a villager record; VV2-VV5 store everything on the child's own record.

For the other four games a birth hook is a trampoline in a code cave with a
strict byte budget. If it had to extract the child's name and two integers,
and both parents' names and four integers, it would be forty-odd instructions
of hand-written assembly per game. Reading them in the companion instead --
compiled, testable, one implementation -- leaves the hook passing two things:
the game id and the child's record pointer.

These pin that property. An argument the caller does supply must still win, so
VV1's existing behaviour cannot be disturbed by the record path.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORTER = ROOT / "native/parentage_export/parentage_export.c"


def _birth_body() -> str:
    source = EXPORTER.read_text(encoding="utf-8")
    at = source.index("__declspec(dllexport) int __stdcall WriteParentageBirth(")
    return source[at : source.index("\n}", at)]


def _without_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/", " ", text, flags=re.S)


class BirthRecordIsSelfContained(unittest.TestCase):
    def setUp(self) -> None:
        self.body = _birth_body()
        self.code = _without_comments(self.body)

    def test_every_game_is_accepted(self) -> None:
        """The VV1-only gate is gone; the format is uniform across five games."""
        self.assertNotIn(
            "game_id != GAME_VV1",
            self.code,
            "the birth export refuses every game but VV1, so four of the five "
            "logs cannot carry a Birth record at all",
        )
        self.assertIn("game_id < GAME_VV1 || game_id > GAME_VV5", self.code)

    def test_the_child_can_come_from_the_record(self) -> None:
        for field in ("name", "head", "body"):
            with self.subTest(field=field):
                self.assertIn(
                    "rec + g->%s)" % field,
                    self.code,
                    "the child's %s cannot be read from its own record, so a "
                    "hook must extract it in assembly" % field,
                )

    def test_both_parents_can_come_from_the_record(self) -> None:
        for field in ("parent_father_name", "parent_mother_name",
                      "parent_father_head", "parent_father_body",
                      "parent_mother_head", "parent_mother_body"):
            with self.subTest(field=field):
                self.assertIn("rec + g->%s)" % field, self.code)

    def test_an_explicit_argument_still_wins(self) -> None:
        """VV1 passes real values; the record must never override them.

        Each record read is guarded by the caller having supplied nothing --
        an empty name, or a negative head/body. Zero is a real head and a real
        body in these games, so negative is the only safe "absent" marker and
        a `== 0` test here would discard a villager genuinely at row 0.
        """
        self.assertIn("child_name == NULL || child_name[0] == ", self.code)
        for who in ("mother", "father"):
            with self.subTest(parent=who):
                self.assertIn(
                    "%s_name == NULL || %s_name[0] == " % (who, who),
                    self.code,
                )
        for value in ("child_head", "child_body", "mother_head", "mother_body",
                      "father_head", "father_body"):
            with self.subTest(value=value):
                self.assertIn("if (%s < 0)" % value, self.code)
                self.assertNotIn("if (%s == 0)" % value, self.code)

    def test_a_nameless_record_is_still_refused(self) -> None:
        """Dropping the mandatory-name guard must not log an empty slot."""
        self.assertIn(
            "if (child_name == NULL || child_name[0] == '\\0') {",
            self.body,
            "a record with no name in it would be logged as a birth",
        )


if __name__ == "__main__":
    unittest.main()
