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
instead: the count handed back is the running total over every log file, not
the count of one.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORTER = ROOT / "native/parentage_export/parentage_export.c"


def _function(name: str) -> str:
    """The body of one static function, by name."""
    source = EXPORTER.read_text(encoding="utf-8")
    start = source.index("static int %s(" % name)
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
        self.assertIn('"Conception %d\\n"', source)
        self.assertIn("existing_records + 1", source)

    def test_the_count_accumulates_over_every_log_file(self):
        body = _function("select_log_file")

        # A running total that survives the loop, rather than the per-file
        # count being handed straight back.
        self.assertRegex(
            body,
            r"\btotal\s*\+=\s*records\b",
            "select_log_file must accumulate each file's records; without it "
            "the number restarts at 1 in every new log",
        )
        self.assertNotRegex(
            body,
            r"\*existing_records\s*=\s*records\s*;",
            "handing back the chosen file's own count restarts the numbering "
            "at each rollover",
        )
        # Both exits must report the total: the one that finds a file with room
        # and the one that finds no file at all.
        self.assertEqual(
            len(re.findall(r"\*existing_records\s*=\s*total\s*;", body)),
            2,
            "both returns must report the running total -- the gap exit as "
            "well as the not-full exit",
        )

    def test_the_total_includes_the_file_being_appended_to(self):
        """`total += records` must precede the not-full return.

        Adding it afterwards would number the first record of each file one too
        low, which is the same defect one step smaller and would still look
        plausible in a log.
        """
        body = _function("select_log_file")
        accumulate = body.index("total += records")
        not_full = body.index("if (records < RECORDS_PER_FILE)")
        self.assertLess(
            accumulate,
            not_full,
            "the running total must include this file's own records before "
            "the not-full return uses it",
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
