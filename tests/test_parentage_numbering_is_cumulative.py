"""The conception number must keep counting across the log-file rollover.

Each log holds 256 records and then a new numbered file is opened. The record
header is printed as `existing_records + 1`, and `existing_records` came from
`count_records` on the chosen file alone -- so the 257th conception was printed
as "Conception 1" again. A village past 256 births had two records called
"Conception 1", two called "Conception 2", and nothing to order them by, which
is the one thing a numbered record exists to provide.

Demonstrated before fixing, by driving the real 32-bit DLL through 257
conceptions against a synthetic VV5 record array:

    before   log 1: 256 records, Conception 1 .. 256
             log 2:   1 record,  Conception 1 .. 1
    after    log 2:   1 record,  Conception 257 .. 257

That harness cannot run from this suite -- the companion is 32-bit and the
interpreter here is 64-bit -- so this asserts the property on the source
instead: the number handed back is the village's running number over every
one of ITS log files, not the count of one -- and never another village's
(the owner's v1.35.59 live pass: each village numbers its own from 1).
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORTER = ROOT / "native/parentage_export/parentage_export.c"


FUNCTION_OPENING = r"^(?:[A-Z_]+\s+)?(?:static\s+)?int\s+%s\("


def _function(name: str) -> str:
    """The body of one function, by name.

    The linkage keyword is matched loosely rather than as a literal
    "static int": select_log_file is declared VV_PARENTAGE_STATIC so the
    on-disk harness can link against it, and pinning the old spelling made
    these tests fail with "substring not found" while the property they
    check was untouched.
    """
    source = EXPORTER.read_text(encoding="utf-8")
    match = re.search(FUNCTION_OPENING % re.escape(name), source, re.M)
    if match is None:
        raise AssertionError("no definition of %s found" % name)
    start = match.start()
    # Walk to the closing brace at column zero, which every function here has.
    end = source.index("\n}", start) + 2
    return source[start:end]


class ParentageNumberingIsCumulativeTests(unittest.TestCase):
    def test_the_printed_number_comes_from_the_returned_count(self):
        """Guard the link between the two halves of this contract.

        If the record header stopped using `existing_records`, the accumulation
        below would still be correct and still be pointless.
        """
        source = EXPORTER.read_text(encoding="utf-8")
        # "Conception <n>" (and a death's "Death <n>"): the family's marker
        # and the running total.
        self.assertIn(
            'fprintf(file, "%s%d\\n%s", family_marker(log_family_of(kind)),\n'
            '                              existing_records + 1, text)',
            source,
        )

    def test_the_count_accumulates_over_every_log_file(self):
        # The walk serves both log families; select_log_file is its births form.
        body = _function("select_family_log_file")

        # The village's last number, kept across the walk, rather than the
        # per-file count being handed straight back.
        self.assertRegex(
            body,
            r"if \(last_here > village_last\) \{\s*village_last = last_here;",
            "select_log_file must carry the village's last number over its files; "
            "without it the number restarts at 1 in every new log",
        )
        self.assertNotRegex(
            body,
            r"\*existing_records\s*=\s*records\s*;",
            "handing back the chosen file's own count restarts the numbering "
            "at each rollover",
        )
        # Both exits must report it: the one that finds a file with room and
        # the one that finds no file at all.
        self.assertEqual(
            len(re.findall(r"\*existing_records\s*=\s*village_last\s*;", body)),
            2,
            "both returns must report the village's running number -- the gap "
            "exit as well as the not-full exit",
        )

    def test_each_village_numbers_its_own_records(self):
        """The owner's v1.35.59 live pass: a new village's records were
        numbered on from another village's ("Arrived 42-46" for Start Over's
        five founders).  Another village's file is skipped before its
        numbers are read, and the Arrived count reads only the village's
        own files."""
        body = _function("select_family_log_file")
        skip = body.index("if (!log_belongs_to_village(destination, village)) {")
        self.assertLess(skip, body.index("count_family_records(destination, family, &last_here)"))
        arrived = _function("count_arrived_records")
        self.assertIn("!log_belongs_to_village(path, village)", arrived)
        self.assertNotIn("++total", arrived, "the highest number, not a count across villages")

    def test_the_total_includes_the_file_being_appended_to(self):
        """The file's own numbers must be read before the not-full return.

        Reading them afterwards would number the first record of each file one
        too low, which is the same defect one step smaller and would still
        look plausible in a log.
        """
        # The walk serves both log families; select_log_file is its births form.
        body = _function("select_family_log_file")
        accumulate = body.index("village_last = last_here;")
        # Matched on the condition's opening rather than the whole
        # expression.
        not_full = body.index("if (records < RECORDS_PER_FILE")
        self.assertLess(
            accumulate,
            not_full,
            "the village's last number must include this file's own records "
            "before the not-full return uses it",
        )

    def test_the_rollover_threshold_is_still_what_the_docs_promise(self):
        source = EXPORTER.read_text(encoding="utf-8")
        self.assertRegex(
            source,
            r"RECORDS_PER_FILE\s*=\s*256\b",
            "the transparency log promises a new file every 256 records",
        )


if __name__ == "__main__":
    unittest.main()
