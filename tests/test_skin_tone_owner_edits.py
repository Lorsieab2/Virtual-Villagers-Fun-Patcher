"""The owner's hand-painted skin tones that ship with the patcher (assets/skin_tones/owner_edits).

The owner, 2026-11-26: "yes my art can ship".  What ships is the owner's painting of the SKIN ONLY: for a
sheet, mask.png (white where skin, nothing else) and tone_NN.png layers whose every painted pixel lies
inside that mask.  Nothing of a game's own art -- its sheet, hair, eyes, clothes -- may be in the folder:
the patcher puts these layers over the player's own installed sheets.

Checked here, on whatever is committed (an empty folder passes):
  * manifest.json pins every picture by SHA-256, and nothing unpinned is there;
  * every file is <game>/<sheet>/mask.png or <game>/<sheet>/tone_NN.png, NN a tone that exists;
  * a mask is only fully white or fully transparent pixels;
  * every tone layer has its mask beside it, is the mask's size, and has no pixel outside it.
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
NAME = re.compile(r"^vv[1-5]/[A-Za-z0-9_]+/(mask|tone_(\d\d))\.png$")


def pictures():
    return sorted(EDITS.rglob("*.png")) if EDITS.is_dir() else []


def outside(layer, mask):
    """How many pixels of `layer` (RGBA) with any alpha lie where `mask` (RGBA) is transparent."""
    return sum(1 for (_r, _g, _b, a), (_mr, _mg, _mb, ma) in zip(layer.getdata(), mask.getdata()) if a and not ma)


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

    def test_only_masks_and_tone_layers(self) -> None:
        for path in pictures():
            rel = path.relative_to(EDITS).as_posix()
            with self.subTest(file=rel):
                match = NAME.match(rel)
                self.assertIsNotNone(match)
                if match.group(2):
                    self.assertTrue(1 <= int(match.group(2)) <= tones.TONE_COUNT)

    def test_no_shipped_pixel_lies_outside_the_skin_mask(self) -> None:
        from PIL import Image
        for path in pictures():
            rel = path.relative_to(EDITS).as_posix()
            with self.subTest(file=rel):
                image = Image.open(path).convert("RGBA")
                if path.name == "mask.png":
                    odd = sum(1 for px in image.getdata() if px not in ((255, 255, 255, 255), (0, 0, 0, 0)))
                    self.assertEqual(odd, 0, "a mask is white where skin and transparent elsewhere")
                    continue
                beside = path.with_name("mask.png")
                self.assertTrue(beside.is_file(), "a tone layer ships with its mask")
                mask = Image.open(beside).convert("RGBA")
                self.assertEqual(image.size, mask.size)
                self.assertEqual(outside(image, mask), 0)

    def test_the_check_itself(self) -> None:
        """A layer with one pixel outside its mask is caught (so an empty folder is not a hollow pass)."""
        from PIL import Image
        mask = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
        mask.putpixel((1, 1), (255, 255, 255, 255))
        layer = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
        layer.putpixel((1, 1), (120, 80, 60, 255))
        self.assertEqual(outside(layer, mask), 0)
        layer.putpixel((2, 2), (120, 80, 60, 9))
        self.assertEqual(outside(layer, mask), 1)


if __name__ == "__main__":
    unittest.main()
