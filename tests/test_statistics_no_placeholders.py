"""No statistics row may ship as a placeholder.

While the owner's five-game Village Statistics directive
(docs/village-statistics-directive.md) is being implemented, unfinished rows
are marked PENDING-IMPLEMENTATION in the exporter source.  This fails until
every such marker is gone, so a fake counter can never be released.
"""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class NoPlaceholderTests(unittest.TestCase):
    def test_no_pending_statistics_rows(self):
        for path in sorted((ROOT / "native").rglob("*.c")):
            with self.subTest(path=path.name):
                self.assertNotIn("PENDING-IMPLEMENTATION", path.read_text(encoding="utf-8", errors="replace"))


if __name__ == "__main__":
    unittest.main()
