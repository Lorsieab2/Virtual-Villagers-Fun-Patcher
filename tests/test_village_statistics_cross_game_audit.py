from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = "7fe0a047706693d69c9b504f7a7b0b014280dee3"


class VillageStatisticsCrossGameAuditTests(unittest.TestCase):
    def test_exact_cross_game_contract_is_documented(self) -> None:
        paths = (
            ROOT / "docs" / "village-statistics-export-research.md",
            ROOT / "docs" / "village-statistics-requirements.md",
            ROOT / "docs" / "origins-playtest-readiness.md",
            ROOT / "docs" / "village-statistics-transparency.md",
        )
        for path in paths:
            with self.subTest(path=path.name):
                text = " ".join(path.read_text(encoding="utf-8").split())
                self.assertIn(AUDIT, text)
                self.assertIn("persisted lifetime maximum", text)
                self.assertIn("successful skeleton pickup", text)
                self.assertIn("ON HOLD", text)

    def test_migration_and_vv2_field_guards_are_exact(self) -> None:
        text = " ".join(
            (ROOT / "docs" / "village-statistics-export-research.md")
            .read_text(encoding="utf-8")
            .split()
        )
        self.assertIn("one-time lower-bound baseline", text)
        self.assertIn("atomic, save-scoped initialized marker", text)
        self.assertIn("never repeatedly add current memorial counts", text)
        self.assertIn("state+0x2E514", text)
        self.assertIn("Village Elders", text)
        self.assertIn("forbidden for buried migration", text)
        self.assertIn("insufficient downstream site", text)


if __name__ == "__main__":
    unittest.main()
