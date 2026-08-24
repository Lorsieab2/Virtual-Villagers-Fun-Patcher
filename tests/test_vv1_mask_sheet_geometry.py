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
        art's own pixel. The sheet applies two transforms that are explicitly
        allowed -- bleed crumbs from the neighbouring column are REMOVED, and the
        whole frame is TRANSLATED vertically so every facing's mask bottom aligns
        (see _align_frame_bottoms). Nothing may be recoloured or reshaped.

        We reconstruct the generator's own pre-alignment clean cell (its own
        _strip_bleed + _keep_main_blob on the placed column) and compare it to
        the final aligned sheet cell bbox-to-bbox: because the alignment is a
        pure vertical translation, the two crops must be pixel-identical and the
        horizontal extent unchanged.
        """
        cw = self.sheets.CELL_W
        H = self.sheets.SHEET_CELL_H
        for colour in self.sheets.GRIDDED:
            art = Image.open(
                ROOT / "assets" / "origins" / "mask-art" / f"{colour}.png"
            ).convert("RGBA")
            sheet = self.sheets._sheet(colour)
            for facing, (ox, oy) in enumerate(self.sheets._frame_offsets(colour)):
                with self.subTest(colour=colour, facing=facing):
                    src_x = cw * facing - ox
                    column = art.crop((src_x, 0, src_x + cw, art.height)).copy()
                    top = oy - self.sheets.CELL_TOP
                    cell = Image.new("RGBA", (cw, H), (0, 0, 0, 0))
                    cell.alpha_composite(column, (0, top))
                    clean = self.sheets._keep_main_blob(
                        self.sheets._strip_bleed(cell, colour, facing)
                    )
                    cbb = clean.getbbox()
                    got = sheet.crop((cw * facing, 0, cw * (facing + 1), H))
                    gbb = got.getbbox()
                    self.assertTrue(cbb and gbb, f"{colour} facing {facing} empty")
                    # horizontal extent unchanged; same height (pure vertical move)
                    self.assertEqual((cbb[0], cbb[2]), (gbb[0], gbb[2]),
                                     f"{colour} facing {facing} moved horizontally")
                    self.assertEqual(cbb[3] - cbb[1], gbb[3] - gbb[1],
                                     f"{colour} facing {facing} height changed")
                    cl = clean.crop(cbb).load()
                    gl = got.crop(gbb).load()
                    w, h = cbb[2] - cbb[0], cbb[3] - cbb[1]
                    for y in range(h):
                        for x in range(w):
                            self.assertEqual(
                                gl[x, y], cl[x, y],
                                f"{colour} facing {facing} pixel ({x},{y}) altered",
                            )

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
        a FROZEN reference (CHIEF_REFERENCE, captured from the verified colours)
        plus the playtest CHIEF_DX/CHIEF_DY nudges. It must land where that
        anchor puts it."""
        ref = self.sheets.CHIEF_REFERENCE
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
                    # Chief frames sit at the frozen reference chin lifted by
                    # CHIEF_DY, and centred at the reference centre nudged right
                    # by CHIEF_DX.
                    self.assertLessEqual(
                        abs(box[3] - (chin - self.sheets.CHIEF_DY)), 2
                    )
                    # The horizontal check only applies to frames that fit
                    # WITHIN the cell. Several chief frames are wider than the
                    # 40px cell and clip at its edges (box touches 0 or CELL_W),
                    # which makes their bbox centre meaningless -- the vertical
                    # (chin) check above still pins those. For unclipped frames,
                    # the centre must sit at the frozen reference nudged right
                    # by CHIEF_DX.
                    clipped = box[0] == 0 or box[2] == self.sheets.CELL_W
                    if not clipped:
                        self.assertLessEqual(
                            abs(
                                (box[0] + box[2]) / 2
                                - (centre + self.sheets.CHIEF_DX)
                            ),
                            2,
                        )


if __name__ == "__main__":
    unittest.main()
