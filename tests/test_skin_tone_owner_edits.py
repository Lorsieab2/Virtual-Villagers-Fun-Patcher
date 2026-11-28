"""The owner's hand-painted skin tones that ship with the patcher (assets/skin_tones/owner_edits).

The owner, 2026-11-26: "yes my art can ship"; 2026-11-27: each tone is "an editable color overlay mask
over the base art".  What ships is only WHERE the owner marked skin: for a sheet, skin_NN.png (white where
tone NN's colour layer was painted) and mask.png (the skin of every tone with none of its own).  Nothing of
a game's own art -- its sheet, shading, hair, eyes, clothes -- and no colour may be in the folder: the
patcher makes each tone's colours and shading from the player's own installed sheets.

Checked here, on whatever is committed (an empty folder passes):
  * manifest.json pins every picture by SHA-256, and nothing unpinned is there;
  * every file is <game>/<sheet>/mask.png or <game>/<sheet>/skin_NN.png, NN a tone that exists;
  * every picture is only fully white or fully transparent pixels -- a marking, never art.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_skin_tones as tones  # noqa: E402

EDITS = ROOT / "assets" / "skin_tones" / "owner_edits"
NAME = re.compile(r"^vv[1-5]/[A-Za-z0-9_]+/(mask|skin_(\d\d))\.png$")


def pictures():
    return sorted(EDITS.rglob("*.png")) if EDITS.is_dir() else []


def not_a_mark(image):
    """How many pixels of an RGBA picture are neither fully white nor fully transparent black."""
    return sum(1 for px in image.getdata() if px not in ((255, 255, 255, 255), (0, 0, 0, 0)))


class OwnerEdits(unittest.TestCase):
    def test_the_manifest_pins_every_picture(self) -> None:
        manifest = EDITS / "manifest.json"
        self.assertTrue(manifest.is_file(), "assets/skin_tones/owner_edits/manifest.json is missing")
        pins = json.loads(manifest.read_text(encoding="utf-8"))
        found = {path.relative_to(EDITS).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                 for path in pictures()}
        self.assertEqual(pins, found)
        others = [p.name for p in EDITS.rglob("*") if p.is_file() and p.suffix != ".png" and p.name != "manifest.json"]
        self.assertEqual(others, [], "only pictures and the manifest belong here")

    def test_only_masks_and_each_tones_skin(self) -> None:
        for path in pictures():
            rel = path.relative_to(EDITS).as_posix()
            with self.subTest(file=rel):
                match = NAME.match(rel)
                self.assertIsNotNone(match)
                if match.group(2):
                    self.assertTrue(1 <= int(match.group(2)) <= tones.TONE_COUNT)

    def test_the_names_allowed(self) -> None:
        self.assertTrue(NAME.match("vv1/male_heads/skin_10.png"))
        self.assertTrue(NAME.match("vv5/carrying/mask.png"))
        self.assertFalse(NAME.match("vv1/male_heads/tone_03.png"), "a painted tone layer is art: it never ships")
        self.assertFalse(NAME.match("vv1/male_heads.png"))

    def test_every_shipped_picture_is_a_mark_and_nothing_else(self) -> None:
        from PIL import Image
        for path in pictures():
            rel = path.relative_to(EDITS).as_posix()
            with self.subTest(file=rel):
                self.assertEqual(not_a_mark(Image.open(path).convert("RGBA")), 0,
                                 "white where skin and transparent elsewhere: no colour, no art")

    def test_the_check_itself(self) -> None:
        """One coloured or half-see-through pixel is caught (so an empty folder is not a hollow pass)."""
        from PIL import Image
        mark = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
        mark.putpixel((1, 1), (255, 255, 255, 255))
        self.assertEqual(not_a_mark(mark), 0)
        mark.putpixel((2, 2), (120, 80, 60, 255))
        mark.putpixel((3, 3), (255, 255, 255, 9))
        self.assertEqual(not_a_mark(mark), 2)


if __name__ == "__main__":
    unittest.main()
