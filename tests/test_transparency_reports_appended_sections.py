"""The transparency document must describe every appended executable section.

The generator counted `patches` and later `composition_patches`, but never
`pe_append_transaction`. So a feature that adds a whole executable section and
rewrites the PE headers that map it reported only its hook: one parentage
feature said "Guarded executable edits: 1" while also appending a 4096-byte
code page and changing three header fields.

That is worse than saying nothing. The document exists so a player can see
exactly what a patch does to their game, and a count that omits the largest
change still reads as complete.

Eight shipping features were affected -- three parentage features and five
Origins bases.

The assertion is deliberately derived from the manifests rather than from a
list of feature ids: a new appending feature must appear in the document
without anyone remembering to extend this test.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher as patcher  # noqa: E402


TRANSPARENCY = ROOT / "docs" / "transparency-log.md"


def _sections() -> dict[str, str]:
    """The document body for each feature, keyed by feature id."""
    text = TRANSPARENCY.read_text(encoding="utf-8")
    sections: dict[str, str] = {}
    for chunk in text.split("\n#### ")[1:]:
        match = re.match(r"[^\n]*?\(`([^`]+)`\)", chunk)
        if match:
            sections[match.group(1)] = chunk
    return sections


class TransparencyReportsAppendedSectionsTests(unittest.TestCase):
    def test_every_appending_feature_reports_its_section(self) -> None:
        sections = _sections()
        checked = 0

        for feature in patcher.load_fun_patches():
            transaction = feature.raw.get("pe_append_transaction")
            if not isinstance(transaction, dict):
                continue
            layouts = transaction.get("layouts")
            if not isinstance(layouts, dict) or not layouts:
                continue
            layout = next(iter(layouts.values()))
            if not isinstance(layout, dict):
                continue

            with self.subTest(feature=feature.id):
                body = sections.get(feature.id)
                self.assertIsNotNone(
                    body,
                    f"{feature.id} appends a section but has no transparency "
                    "section at all",
                )
                self.assertIn(
                    "new executable section",
                    body,
                    f"{feature.id} appends {layout.get('append_length')} bytes "
                    "and the document does not say so",
                )
                # The reported size must be the size actually declared, not a
                # placeholder -- a wrong number is worse than an absent one.
                self.assertIn(
                    f"Appends {int(layout['append_length'])} bytes",
                    body,
                    f"{feature.id} reports a different size than it declares",
                )
                headers = layout.get("header_patches") or []
                self.assertIn(
                    f"rewrites {len(headers)} PE header field(s)",
                    body,
                    f"{feature.id} reports a different header count than it "
                    "declares",
                )
                checked += 1

        # Guard against the document and the manifests both going quiet: this
        # test must actually examine the features it exists for.
        self.assertGreaterEqual(
            checked,
            8,
            "fewer appending features were checked than ship today; either a "
            "feature stopped appending or this test stopped finding them",
        )

    def test_an_overlay_alternative_is_disclosed(self) -> None:
        """A feature that can skip its append must say so, and name the base.

        Otherwise the document describes a section the player may never get,
        with nothing to explain why their patched game differs.
        """
        sections = _sections()
        checked = 0
        for feature in patcher.load_fun_patches():
            transaction = feature.raw.get("pe_append_transaction")
            if not isinstance(transaction, dict):
                continue
            overlays = transaction.get("composition_overlays")
            if not isinstance(overlays, dict) or not overlays:
                continue
            with self.subTest(feature=feature.id):
                body = sections.get(feature.id, "")
                self.assertIn("appends nothing", body)
                for base_id in overlays:
                    self.assertIn(
                        base_id,
                        body,
                        f"{feature.id} does not name {base_id} as the feature "
                        "whose selection changes its behaviour",
                    )
                checked += 1
        self.assertGreater(checked, 0, "no overlay-declaring feature was found")


if __name__ == "__main__":
    unittest.main()
