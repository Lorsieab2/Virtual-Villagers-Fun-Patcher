"""No shipped text file holds mojibake: UTF-8 text that was read as Windows-1252 and saved again, so that an
em dash shows as "â€”", an ellipsis as "â€¦" and a times sign as "Ã—" (README.md had three, v1.35.85).

Every text file the release ZIP carries (scripts/build_release.py FILES) -- README.md, How to Use.txt, the
data/*.json manifests and guides, the patcher's own sources -- is read as UTF-8, every string a JSON file holds
is checked too (an escaped "\\u00e2\\u20ac\\u201d" is the same damage), and any run of characters that turns
back into real UTF-8 text when written out as Windows-1252 fails the test, with where it is and what it was meant
to be.
"""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_release  # noqa: E402

TEXT = {".md", ".txt", ".json", ".py", ".ps1", ".csv", ".ini", ".cfg"}
# A UTF-8 lead byte read as Windows-1252 (Â..ô), then one or more continuation bytes read the same way
# (0x80..0xBF: Latin-1 for most, Windows-1252's own letters and punctuation for 0x80..0x9F).
SUSPECT = re.compile("[Â-ô][\u0080-¿ŒœŠšŸŽžƒˆ˜"
                     "–—‘-‚“-„†-•…‰‹›€™]+")


def mojibake(text: str) -> list[tuple[str, str]]:
    """Each run that is UTF-8 read as Windows-1252, with the text it was."""
    found = []
    for match in SUSPECT.finditer(text):
        try:
            meant = match.group().encode("cp1252").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue                                      # real accented text, not damage
        if meant and not meant.isascii():
            found.append((match.group(), meant))
    return found


def strings(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for k, v in value.items() for s in strings(k) + strings(v)]
    if isinstance(value, list):
        return [s for v in value for s in strings(v)]
    return []


class ShippedTextHasNoMojibake(unittest.TestCase):
    def test_the_detector_finds_the_damage_and_passes_real_text(self) -> None:
        self.assertEqual(mojibake("free â€” so"), [("â€”", "—")])
        self.assertEqual(mojibake("waitâ€¦"), [("â€¦", "…")])
        self.assertEqual(mojibake("3Ã— great"), [("Ã—", "×")])
        self.assertEqual(mojibake("café — naïve … 3× “quoted” é’"), [])

    def test_no_shipped_text_file_holds_mojibake(self) -> None:
        checked = 0
        for relative in build_release.FILES:
            path = ROOT / relative
            if path.suffix.lower() not in TEXT:
                continue
            checked += 1
            text = path.read_text(encoding="utf-8-sig")
            texts = [text]
            if path.suffix.lower() == ".json":
                texts += strings(json.loads(text))
            with self.subTest(file=relative):
                bad = sorted({hit for t in texts for hit in mojibake(t)})
                self.assertEqual(bad, [], f"{relative}: mis-encoded text (found, meant): {bad}")
        self.assertIn("README.md", build_release.FILES)
        self.assertIn("How to Use.txt", build_release.FILES)
        self.assertGreater(checked, 100)


if __name__ == "__main__":
    unittest.main()
