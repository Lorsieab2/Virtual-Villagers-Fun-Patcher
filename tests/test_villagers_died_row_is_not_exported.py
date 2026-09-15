"""No exporter may print a Villagers Died row.

The owner removed it: "remove 'Villagers Died' because 'Villagers Buried' is
better, even when the graveyards are full."

The counters themselves were deliberately left in place -- `death_hooks` in
`scripts/build_statistics_features.py` still installs them and they still
increment -- so that the fields can come back without new reverse engineering
if the owner ever asks for them.

That split is exactly what makes a guard necessary. Review raised it on #349:
`test_death_summaries_match_the_build.py` derives "which games ship Villagers
Died" from `death_hooks`, so with the row gone and the hooks kept, every
targeted test still passed while nothing emitted the row and the documents
still described one. Instrumentation shipping and a row being printed had
silently become different facts with only the first of them checked.

So this module checks the second fact directly, against the exporter source
rather than against any prose.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORTER = ROOT / "native" / "statistics_export" / "statistics_export.c"
REQUIREMENTS = ROOT / "docs" / "village-statistics-requirements.md"


class VillagersDiedRowIsNotExportedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = EXPORTER.read_text(encoding="utf-8")

    def test_no_format_string_prints_the_row(self) -> None:
        """A row reaches the file only through a format-string literal."""
        self.assertNotIn(
            '"Villagers Died',
            self.source,
            "an exporter format string still prints Villagers Died",
        )

    def test_no_extra_row_is_labelled_with_it(self) -> None:
        """The shared later-game writer prints extras by label.

        VV3 and VV4 each spent an extras slot on this row. A label passed
        there prints just as surely as a format-string literal, so the string
        must not appear as an argument either.
        """
        labels = re.findall(r'0x[0-9A-Fa-f]+u,\s*"([^"]+)"', self.source)
        self.assertNotIn("Villagers Died", labels)

    def test_the_counter_instrumentation_is_still_present(self) -> None:
        """The owner asked to remove the ROW, not the counter.

        Without this, deleting the hooks as well would pass every other test
        here while quietly discarding measured reverse engineering and making
        the row impossible to restore without redoing it.
        """
        builder = (ROOT / "scripts" / "build_statistics_features.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("death_hooks", builder)
        self.assertGreaterEqual(
            builder.count('"death_hooks"'),
            3,
            "the three games that instrument the death counter must keep it",
        )

    def test_the_requirements_document_does_not_still_request_the_row(self) -> None:
        text = REQUIREMENTS.read_text(encoding="utf-8")
        if "Villagers Died" not in text:
            return
        self.assertIn(
            "NO LONGER EXPORTED",
            text,
            "the requirements still ask for a Villagers Died row",
        )


if __name__ == "__main__":
    unittest.main()
