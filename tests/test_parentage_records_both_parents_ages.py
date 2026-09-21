"""The parentage log records BOTH parents' ages at conception.

The owner first asked to record only the mother's age, then reversed it:
"since you know the fathers now, I think it's wise to capture the father's ages
too upon conception." So the conception record now prints an age for the mother
AND an age for the father.

What makes the father's age reliable -- and what these guards protect -- is
WHERE it is read. No game copies the father's age onto the mother, so it cannot
come from her record and must not come from a by-name scan of the villager
array (which fails when he has died or a second villager shares his name -- the
"(record not found)" defect that had the field removed the first time). It is
read from HIS OWN captured record at the conception hook, the one moment it is
reliably his: `*(const int *)(father_from_caller + g->age)`, exactly where his head and
body already come from. When no father record was captured the age says so,
using the same wording head and body use, never a scan.

These guards read the SHIPPED DLL as well as the source: a correct source
change whose DLL was not rebuilt would leave the old single-age format in the
artifact the player actually runs.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "native/parentage_export/parentage_export.c"
COMPANION = ROOT / "assets/parentage/VVFP Parentage Export.dll"


class BothParentsAgesAreRecordedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = SOURCE.read_text(encoding="utf-8")

    def test_the_source_prints_two_ages(self) -> None:
        """One for the mother, one for the father."""
        self.assertEqual(
            self.source.count("Age at conception"),
            2,
            "the record should print an age for the mother AND the father",
        )

    def test_the_mothers_age_is_read_straight_from_her_record(self) -> None:
        """Hers is printed as %d directly from her record, between Mother and
        Father in the format string."""
        match = re.search(
            r'"  Mother: %s\\n"\s*"    Age at conception: %d\\n"',
            self.source,
        )
        self.assertIsNotNone(
            match, "the mother's age must be printed from her own record"
        )
        mother_age = self.source.index('"    Age at conception: %d')
        father = self.source.index('"  Father: %s')
        self.assertLess(
            mother_age, father, "the mother's age must precede the father block"
        )
        self.assertIn("*(const int *)(mother + g->age)", self.source)

    def test_the_fathers_age_comes_from_his_own_captured_record(self) -> None:
        """His is rendered to text (like his head and body) so it can say when
        it is unavailable, and it is read from HIS record, never a name scan."""
        # printed under the Father block, as a string
        father_age_line = re.search(
            r'"  Father: %s\\n"\s*"    Age at conception: %s\\n"',
            self.source,
        )
        self.assertIsNotNone(
            father_age_line,
            "the father's age must print under the Father block, as a string",
        )
        # rendered from his own record at conception
        self.assertIn("*(const int *)(father_from_caller + g->age)", self.source)
        self.assertIn("father_age", self.source)

    def test_the_father_age_never_falls_back_to_a_name_scan(self) -> None:
        """The unavailable wording must match head and body -- a real capture
        or an honest "not captured", never find_record_by_name for the age."""
        self.assertIn(
            'memcpy(father_age, "(not captured for this birth)", 30)',
            self.source,
        )
        # the age is only ever set from the captured record or a placeholder;
        # it is never assigned from a scanned record
        self.assertNotIn("father_age =", self.source.replace("char father_age", ""))

    def test_both_age_offsets_are_bounds_checked(self) -> None:
        """Both parents read g->age, so the stride guard must survive."""
        self.assertIn(
            "if (g->age + WORD > stride) return 0;",
            self.source,
            "the age offset must be bounds-checked against the stride",
        )

    def test_the_shipped_dll_prints_two_ages(self) -> None:
        """Source is not the artifact. A stale DLL keeps the old one-age row."""
        if not COMPANION.is_file():
            self.skipTest("the parentage companion DLL is not present")
        blob = COMPANION.read_bytes()
        self.assertEqual(
            blob.count(b"Age at conception"),
            2,
            "the shipped DLL should carry both ages -- rebuild it if not",
        )

    def test_the_shipped_dll_puts_the_father_age_before_his_head(self) -> None:
        """Proves the father's age row is present in the artifact, between the
        Father line and his Head."""
        if not COMPANION.is_file():
            self.skipTest("the parentage companion DLL is not present")
        blob = COMPANION.read_bytes()
        self.assertIn(
            b"  Father: %s\n    Age at conception: %s\n    Head: %s\n",
            blob,
            "the shipped DLL must print the father's age between him and his head",
        )


if __name__ == "__main__":
    unittest.main()
