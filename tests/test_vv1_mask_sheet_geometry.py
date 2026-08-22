"""Keep the mask sheets and the patch that blits them describing one geometry.

The sheet generator and the patch builder each carry the cell size and the
draw offset. They are two files, so they can drift -- and a drift here is
silent: the patch would keep blitting happily, just from the wrong rows, and
the mask would sit off the villager's head with nothing failing.

These also pin the alignment provenance: the offsets in the generator were
recovered by correlating the supplied mockups against the stock head atlas,
not chosen by eye, so the sheets must actually match what the generator
produces from the committed art.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

try:
    from PIL import Image

    HAVE_PIL = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_PIL = False


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@unittest.skipUnless(HAVE_PIL, "requires Pillow")
class VV1MaskSheetGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sheets = _load(
            "vv1_mask_sheets", ROOT / "scripts" / "build_vv1_heathen_mask_sheets.py"
        )
        cls.patch = _load(
            "vv1_origins_feature", ROOT / "scripts" / "build_vv1_origins_feature.py"
        )

    def test_generator_and_patch_agree_on_cell_geometry(self) -> None:
        self.assertEqual(self.sheets.CELL_W, self.patch.MASK_CELL_W)
        self.assertEqual(self.sheets.SHEET_CELL_H, self.patch.MASK_CELL_H)

    def test_generator_and_patch_agree_on_the_draw_offset(self) -> None:
        self.assertEqual(self.sheets.DRAW_Y_OFFSET, self.patch.MASK_DRAW_Y_OFFSET)

    def test_committed_sheets_match_the_generator(self) -> None:
        stale = [
            str(path.relative_to(ROOT))
            for path, data in self.sheets.build()
            if not path.exists() or path.read_bytes() != data
        ]
        self.assertEqual(
            stale,
            [],
            "mask sheets/preview are stale; re-run "
            "scripts/build_vv1_heathen_mask_sheets.py",
        )

    def test_every_sheet_is_seven_facings_on_the_head_atlas_pitch(self) -> None:
        for index in range(1, 6):
            path = ROOT / "assets" / "origins" / f"m{index}.png"
            with self.subTest(sheet=path.name):
                w, h = Image.open(path).size
                self.assertEqual(w, self.sheets.CELL_W * self.sheets.FACINGS)
                self.assertEqual(h, self.sheets.SHEET_CELL_H)

    def test_gridded_art_is_used_verbatim(self) -> None:
        """For the strip colours: every pixel the sheet keeps is the supplied
        art's own pixel, at the offset recovered from that colour's mockup.

        Pixels may be REMOVED -- art wider than the 40px cell bleeds crumbs into
        the neighbouring column, and those are stripped so they do not render as
        specks floating above the villager. Nothing may be recoloured or moved.
        """
        for colour in self.sheets.GRIDDED:
            art = Image.open(
                ROOT / "assets" / "origins" / "mask-art" / f"{colour}.png"
            ).convert("RGBA")
            sheet = self.sheets._sheet(colour)
            cw = self.sheets.CELL_W
            for facing, (ox, oy) in enumerate(self.sheets._frame_offsets(colour)):
                with self.subTest(colour=colour, facing=facing):
                    src_x = cw * facing - ox
                    src = art.crop((src_x, 0, src_x + cw, art.height)).load()
                    top = oy - self.sheets.CELL_TOP
                    got = sheet.crop(
                        (cw * facing, top, cw * (facing + 1), top + art.height)
                    ).load()
                    removed = 0
                    for y in range(art.height):
                        for x in range(cw):
                            if got[x, y][3] > 0:
                                self.assertEqual(
                                    got[x, y],
                                    src[x, y],
                                    f"{colour} facing {facing} pixel ({x},{y}) "
                                    "was altered, not merely moved",
                                )
                            elif src[x, y][3] > 128:
                                removed += 1
                    self.assertLess(removed, 60, f"{colour} facing {facing}")

    def test_packed_atlas_frames_are_moved_not_redrawn(self) -> None:
        """Chief's atlas is separated into frames and repositioned; each frame's
        own pixels must survive that intact."""
        for colour, value in self.sheets.MASK_OFFSETS.items():
            if value is not self.sheets.PACKED:
                continue
            art = Image.open(
                ROOT / "assets" / "origins" / "mask-art" / f"{colour}.png"
            ).convert("RGBA")
            boxes = self.sheets._islands(art)
            sheet = self.sheets._sheet(colour)
            self.assertEqual(len(boxes), self.sheets.FACINGS)
            for facing, box in enumerate(boxes):
                with self.subTest(colour=colour, facing=facing):
                    frame = art.crop(box)
                    cell = sheet.crop(
                        (
                            self.sheets.CELL_W * facing,
                            0,
                            self.sheets.CELL_W * (facing + 1),
                            self.sheets.SHEET_CELL_H,
                        )
                    )
                    kept = sum(1 for px in cell.getdata() if px[3] > 128)
                    orig = sum(1 for px in frame.getdata() if px[3] > 128)
                    self.assertGreater(
                        kept,
                        orig * 0.9,
                        f"{colour} facing {facing}: only {kept} of {orig} px "
                        "survived placement",
                    )

    def test_packed_atlas_matches_the_verified_colours(self) -> None:
        """A packed atlas carries no alignment of its own, so it is placed from
        the colours whose mockups verify. It must actually land in their band."""
        ref = self.sheets._reference_placement()
        for colour, value in self.sheets.MASK_OFFSETS.items():
            if value is not self.sheets.PACKED:
                continue
            sheet = self.sheets._sheet(colour)
            for facing, (centre, chin) in enumerate(ref):
                with self.subTest(colour=colour, facing=facing):
                    box = sheet.crop(
                        (
                            self.sheets.CELL_W * facing,
                            0,
                            self.sheets.CELL_W * (facing + 1),
                            self.sheets.SHEET_CELL_H,
                        )
                    ).getbbox()
                    self.assertLessEqual(abs(box[3] - chin), 2)
                    self.assertLessEqual(abs((box[0] + box[2]) / 2 - centre), 2)


if __name__ == "__main__":
    unittest.main()
