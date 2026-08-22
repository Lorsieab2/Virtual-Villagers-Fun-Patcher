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

    def test_art_is_used_verbatim(self) -> None:
        """No scaling and no repainting: every pixel the sheet keeps is the
        supplied art's own pixel, at the offset recovered from the mockups.

        Pixels may be REMOVED -- a facing whose art is wider than the 40px cell
        bleeds a few crumbs into its neighbour's column, and those are stripped
        so they do not render as specks floating above the villager. Nothing
        may be recoloured or moved.
        """
        for colour in self.sheets.COLOURS:
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
                    self.assertLess(
                        removed,
                        60,
                        f"{colour} facing {facing}: {removed}px dropped -- far "
                        "more than neighbour bleed, check the offsets",
                    )

    def test_chief_uses_per_frame_offsets(self) -> None:
        """Chief's art staggers three facings ~45px below the rest; a single
        offset leaves those villagers' heads exposed above the mask."""
        offsets = self.sheets._frame_offsets("chief")
        ys = {y for _, y in offsets}
        self.assertGreater(
            len(ys), 1, "chief must keep per-facing offsets, not one shared offset"
        )
        self.assertEqual(len(offsets), self.sheets.FACINGS)


if __name__ == "__main__":
    unittest.main()
