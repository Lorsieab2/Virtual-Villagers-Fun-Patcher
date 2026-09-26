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
    """The body of one function, located by its opening.

    Falls back to matching the name alone when the literal is not found:
    select_log_file is declared VV_PARENTAGE_STATIC so the on-disk harness
    can link against it, and matching "static int select_log_file(" broke
    this test while the property it checks was untouched.
    """
    try:
        start = source.index(opening)
    except ValueError:
        bare = opening.rsplit(" ", 1)[-1].rstrip("(")
        match = re.search(
            r"^(?:[A-Z_]+\s+)?(?:static\s+)?int\s+" + re.escape(bare) + r"\(",
            source,
            re.M,
        )
        if match is None:
            raise
        start = match.start()
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
        append = function(self.source, "static int append_record(")
        # The "Conception <n>" line is printed by append_record, because the
        # number is only known when the record is written -- which, for a
        # record held until the village's first save, is later than the
        # conception. The conception export passes is_birth = 0; the birth
        # export renders its own "Birth" block and passes is_birth = 1.
        self.assertIn("return emit_record(game_id, 0, mother, text);", conception)
        self.assertIn("return emit_record(game_id, 1, rec, text);", birth)
        self.assertIn('"Birth\\n"', birth)
        # Neither may write the other's marker: one record kind printing the
        # other's header is indistinguishable in the log from the wrong event
        # having happened. append_record prints the conception marker only on
        # its not-a-birth branch.
        self.assertNotIn('"Birth\\n"', conception)
        self.assertNotIn('"Conception %d', birth)
        self.assertRegex(
            append,
            r'if \(is_birth\) \{\s*written = fprintf\(file, "%s", text\)[^}]*\} else \{\s*'
            r'written = fprintf\(file, "Conception %d',
        )

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
        append = function(self.source, "static int append_record(")
        self.assertIn("emit_record(game_id, 1,", birth)
        self.assertIn("emit_record(game_id, 0,", conception)
        self.assertIn(
            "select_log_file(g, village, path, &existing_records, is_birth)", append)
        # And no separate birth log exists to split the two kinds apart.
        self.assertNotIn("Birth Log", self.source)

    def test_a_birth_does_not_roll_over_at_the_file_boundary(self):
        """The invariant the test above only LOOKED like it established.

        Sharing select_log_file is not enough. count_records counts only
        "Conception " lines, so a file is full -- by that count -- the instant
        its 256th conception is written. A birth asking for a file at exactly
        that moment fails `records < RECORDS_PER_FILE` and is handed the NEXT
        file, landing apart from its own conception and ahead of that file's
        first record. Every 256th birth, in every village. Found in review.

        The two calls must therefore differ: the conception may roll over, the
        birth may not.
        """
        chooser = function(self.source, "static int select_log_file(")
        # A birth must not stop at the first file with records either: after
        # the first rollover that is file 1, which would put every later birth
        # back there, apart from its conception and growing without bound. An
        # earlier attempt at this fix did exactly that. It keeps walking and
        # takes the village's NEWEST file, which is where its own conception
        # went.
        # Pinned as the real condition, not merely that the words appear:
        # replacing `if (for_birth)` with `if (0)` restores the ORIGINAL bug --
        # the birth rolling over like a conception -- and left the other
        # assertions here green.
        self.assertIn("if (for_birth) {", chooser,
                      "the birth path must branch on for_birth; disabling that "
                      "branch restores the rollover bug it exists to prevent")
        self.assertIn("last_match = number;", chooser,
                      "a birth must remember the latest matching file")
        self.assertIn("if (for_birth && last_match != 0)", chooser,
                      "and select it when the walk ends")
        self.assertNotIn("(for_birth && records > 0)", chooser,
                         "stopping at the first non-empty file sends every "
                         "post-rollover birth back to file 1")
        conception = function(
            self.source,
            "__declspec(dllexport) int __stdcall WriteParentageRecordWithFather(")
        birth = function(
            self.source, "__declspec(dllexport) int __stdcall WriteParentageBirth(")
        append = function(self.source, "static int append_record(")
        # The kind travels as is_birth -- 0 from the conception export, 1 from
        # the birth export -- into select_log_file's for_birth.
        self.assertIn("emit_record(game_id, 0,", conception,
                      "the conception path rolls over normally")
        self.assertIn("emit_record(game_id, 1,", birth,
                      "the birth path must ask not to roll over")
        self.assertIn("&existing_records, is_birth)", append,
                      "append_record must hand the kind to select_log_file")

    def test_a_birth_appends_rather_than_truncating(self):
        """A birth that opened "w" would erase the conceptions before it."""
        append = function(self.source, "static int append_record(")
        self.assertIn('_wfopen(path, L"a")', append)
        self.assertNotIn('_wfopen(path, L"w")', self.source)


if __name__ == "__main__":
    unittest.main()
