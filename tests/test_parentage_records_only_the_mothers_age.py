"""The parentage log records the mother's age at conception and not the father's.

The owner's instruction is to "only record the age of the mother since that's
what determines child age". The child's age derives from hers, so hers is the
value with explanatory power; his was decorative.

It was also the last field that depended on the by-name scan. No game copies
the father's age onto the mother -- only his name, head and body -- so an age
for him could only come from finding his live record in the villager array.
That lookup fails whenever he has died between conception and delivery, or
whenever a second living villager shares his name and the scan rightly refuses
to guess, which is how the log came to print "(record not found)" beside a
perfectly good head and body. Removing the field removes the lookup's only
remaining consumer.

These guards read the SHIPPED DLL, not just the source. A correct source change
whose DLL was not rebuilt would leave the old format string in the artifact the
player actually runs, and the log would keep asking for a field the exporter no
longer computes.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "native/parentage_export/parentage_export.c"
COMPANION = ROOT / "assets/parentage/VVFP Parentage Export.dll"


class OnlyTheMothersAgeIsRecordedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = SOURCE.read_text(encoding="utf-8")

    def test_the_source_prints_exactly_one_age(self) -> None:
        """Two would mean the father's row came back."""
        self.assertEqual(
            self.source.count("Age at conception"),
            1,
            "the record should print an age for the mother only",
        )

    def test_the_one_age_belongs_to_the_mother(self) -> None:
        """Counting is not enough -- the survivor could be the wrong one.

        The mother's age is the only one read as %d straight from her record;
        the father's was rendered to text first so it could say it was
        unavailable. So the surviving row must be the %d one, and it must sit
        between "Mother:" and "Father:" in the format string.
        """
        match = re.search(
            r'"  Mother: %s\\n"\s*"    Age at conception: %d\\n"',
            self.source,
        )
        self.assertIsNotNone(
            match, "the mother's age must still be printed from her own record"
        )
        father = self.source.index('"  Father: %s')
        mother_age = self.source.index('"    Age at conception: %d')
        self.assertLess(
            mother_age, father, "the surviving age is on the wrong parent"
        )

    def test_no_father_age_is_computed(self) -> None:
        """The buffer and every branch that filled it must be gone.

        Leaving the computation while dropping the printed row would keep the
        by-name scan load-bearing for a value nobody reads.
        """
        self.assertNotIn(
            "father_age",
            self.source,
            "a father age is still being computed for a field that is not printed",
        )

    def test_the_mothers_age_offset_is_still_validated(self) -> None:
        """She still reads it, so the bounds check must survive the removal.

        An age offset at or beyond the record stride would read into the NEXT
        villager's record. The father's removal must not take the guard with it.
        """
        self.assertIn(
            "if (g->age + WORD > stride) return 0;",
            self.source,
            "the age offset must still be bounds-checked against the stride",
        )

    def test_the_shipped_dll_prints_one_age(self) -> None:
        """Source is not the artifact. A stale DLL keeps the old two-age row."""
        if not COMPANION.is_file():
            self.skipTest("the parentage companion DLL is not present")
        blob = COMPANION.read_bytes()
        self.assertEqual(
            blob.count(b"Age at conception"),
            1,
            "the shipped DLL still carries a second age -- rebuild it",
        )

    def test_the_shipped_dll_puts_head_straight_after_father(self) -> None:
        """Proves the removal, not merely that one string was deduplicated.

        A count of one would also pass if the compiler had pooled two identical
        literals into a single copy. The adjacency cannot be reached that way.
        """
        if not COMPANION.is_file():
            self.skipTest("the parentage companion DLL is not present")
        blob = COMPANION.read_bytes()
        self.assertIn(
            b"  Father: %s\n    Head: %s\n",
            blob,
            "the shipped DLL still has a row between the father and his head",
        )


if __name__ == "__main__":
    unittest.main()
