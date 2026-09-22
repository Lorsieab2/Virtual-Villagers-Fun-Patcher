r"""The parentage log records BOTH conceptions and births, in one file.

The owner wants both tracked. Both already exist -- `WriteParentageRecordWithFather`
writes a "Conception <n>" record and `WriteParentageBirth` writes a "Birth"
record -- and the owner's live VV1 log holds two Birth records (Yepa from Akika
and Bobo, Unagi from Hawa and Rongo) with no Conception records, because no
conception happened while the companion was installed.

That asymmetry is exactly the state in which the two kinds could quietly stop
coexisting, and nothing asserted the property that lets them share a file:

  * `count_records` counts ONLY lines beginning "Conception ", so births do not
    advance the conception number. A birth that counted would make the next
    conception skip a number, and the numbering exists to order the records.
  * Births do not count toward the roll-over either, so a log holds its full
    quota of conceptions PLUS their births rather than being cut short by them.

Both properties live in one counting function and one comment, so a plausible
"tidy up" -- counting every record header, or giving births their own number --
would break the owner's numbering without failing any other test in the suite.

Asserted on the source: the companion is 32-bit and this interpreter is 64-bit,
the same constraint `test_parentage_numbering_is_cumulative` documents.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORTER = ROOT / "native/parentage_export/parentage_export.c"


def function(source: str, opening: str) -> str:
    start = source.index(opening)
    return source[start:source.index("\n}", start)]


class BothRecordKindsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = EXPORTER.read_text(encoding="utf-8")

    def test_both_record_kinds_are_exported(self):
        """Either export going missing silently halves what is tracked."""
        self.assertIn(
            "__declspec(dllexport) int __stdcall WriteParentageRecordWithFather(",
            self.source, "the conception record's export is gone")
        self.assertIn(
            "__declspec(dllexport) int __stdcall WriteParentageBirth(",
            self.source, "the birth record's export is gone")

    def test_each_export_writes_its_own_marker(self):
        conception = function(
            self.source,
            "__declspec(dllexport) int __stdcall WriteParentageRecordWithFather(")
        birth = function(
            self.source, "__declspec(dllexport) int __stdcall WriteParentageBirth(")
        self.assertIn('"Conception %d\\n"', conception)
        self.assertIn('"Birth\\n"', birth)
        # Neither may write the other's marker: one record kind printing the
        # other's header is indistinguishable in the log from the wrong event
        # having happened.
        self.assertNotIn('"Birth\\n"', conception)
        self.assertNotIn('"Conception %d\\n"', birth)

    def test_only_conceptions_are_counted(self):
        """Births must not advance the conception number or the rollover.

        `count_records` is the single place that decides both, so this pins the
        marker it matches rather than merely that some counting happens.
        """
        counter = function(self.source, "static int count_records(")
        self.assertIn('strncmp(line, "Conception ", 11) == 0', counter)
        self.assertNotIn("Birth", counter)

    def test_the_two_kinds_share_one_log_file(self):
        """A birth in its own file could not be read beside its conception.

        Both paths go through `select_log_file`, which is also what applies the
        roll-over, so they cannot drift onto different files or disagree about
        which numbered log is current.
        """
        birth = function(
            self.source, "__declspec(dllexport) int __stdcall WriteParentageBirth(")
        conception = function(
            self.source,
            "__declspec(dllexport) int __stdcall WriteParentageRecordWithFather(")
        self.assertIn("select_log_file(g, village, path, &existing_records)", birth)
        self.assertIn("select_log_file(g, village, path, &existing_records)", conception)
        # And no separate birth log exists to split the two kinds apart.
        self.assertNotIn("Birth Log", self.source)

    def test_a_birth_appends_rather_than_truncating(self):
        """A birth that opened "w" would erase the conceptions before it."""
        birth = function(
            self.source, "__declspec(dllexport) int __stdcall WriteParentageBirth(")
        self.assertIn('_wfopen(path, L"a")', birth)
        self.assertNotIn('_wfopen(path, L"w")', birth)


if __name__ == "__main__":
    unittest.main()
