from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "docs" / "doubler-composition-audit.md"
GENERATOR = ROOT / "scripts" / "generate_transparency_docs.py"
RELEASE = ROOT / "scripts" / "build_release.py"


class DoublerAuditDocumentationTests(unittest.TestCase):
    def test_matrix_covers_all_games_and_unresolved_statuses_are_explicit(self) -> None:
        text = AUDIT.read_text(encoding="utf-8")
        for title in (
            "VV1 A New Home",
            "VV2 The Lost Children",
            "VV3 The Secret City",
            "VV4 The Tree of Life",
            "VV5 New Believers",
        ):
            self.assertIn(title, text)
        self.assertIn("**Pending**", text)
        self.assertIn("**STOP**", text)
        self.assertIn("tail-jump", text)
        self.assertIn("collection-adjusted positive delta", text)

    def test_audit_states_both_composition_rules(self) -> None:
        text = AUDIT.read_text(encoding="utf-8")
        self.assertIn("Island Event results are never doubled", text)
        self.assertIn("twice the exact native", text)
        self.assertIn("positive, zero", text)
        self.assertIn("or negative", text)
        self.assertIn("collection plus doubler", text)

    def test_project_transparency_and_release_include_audit_boundary(self) -> None:
        self.assertIn("docs/doubler-composition-audit.md", RELEASE.read_text(encoding="utf-8"))
        self.assertIn("docs/doubler-composition-audit.md", GENERATOR.read_text(encoding="utf-8"))
        self.assertIn("return-address checks alone", GENERATOR.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
