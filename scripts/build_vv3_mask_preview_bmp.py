"""Build the VV3 Change Appearance *mask* preview strip (mask_strip.bmp).

Parity with the VV5 New Believers mask chooser: the Mask slot shows a real
preview image of the selected mask, not just its name.  This strip is the mask
analogue of the head/body strips built by build_vv3_appearance_bmps.py.

Layout: a horizontal 24-bpp row of six MASK_CELL_W x MASK_CELL_H cells composited
on the dialog background.  Cell 0 is blank ((None)); cells 1..5 are the five
masks (Blue/Orange/Red/Purple/Tribal Chief) taken from the front-facing frame
(frame 5, matching the head preview) of the VV5 heathen-mask sheet.  Each mask is
tight-cropped to its own content and centred at native 1:1 scale, so the taller
masks (e.g. the Tribal Chief's feathers) read as taller -- exactly as they draw
in game.  ShowVV3AppearanceChooser blits cell `mask_index` via StretchBlt.

The VV5 sheet is a uniform 8x5 grid of 65x145 cells (520x725).  Pass its path,
or rely on the default VV5 New Believers install location.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "native" / "vv3_full_mastery_candidate" / "appearance"
BACKGROUND = (236, 236, 236)
SRC_CELL_W, SRC_CELL_H = 65, 145      # VV5 uniform cell (520x725 / 8 / 5)
FRONT_FRAME = 5                        # front-facing frame (matches head preview)
MASK_ROWS = 5
# Preview cell: wide enough for the widest mask, tall enough for the Tribal
# Chief's feathers (frame-5 content maxes ~37x72), with a little margin.
MASK_CELL_W, MASK_CELL_H = 65, 80
DEFAULT_SRC = Path(
    r"C:/Users/Owner/Downloads/Virtual Villagers - New Believers/Images/vv5_heathenheads.png"
)


def build(src_path: Path) -> Path:
    sheet = Image.open(src_path).convert("RGBA")
    strip = Image.new("RGB", (MASK_CELL_W * (MASK_ROWS + 1), MASK_CELL_H), BACKGROUND)
    for r in range(MASK_ROWS):
        x = FRONT_FRAME * SRC_CELL_W
        cell = sheet.crop((x, r * SRC_CELL_H, x + SRC_CELL_W, r * SRC_CELL_H + SRC_CELL_H))
        content = cell.crop(cell.getbbox())          # tight, native size (no scaling)
        base = Image.new("RGBA", (MASK_CELL_W, MASK_CELL_H), BACKGROUND + (255,))
        px = (MASK_CELL_W - content.width) // 2
        py = (MASK_CELL_H - content.height) // 2
        base.alpha_composite(content, (max(0, px), max(0, py)))
        # cell 0 stays blank ((None)); masks fill cells 1..5
        strip.paste(base.convert("RGB"), ((r + 1) * MASK_CELL_W, 0))
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / "mask_strip.bmp"
    strip.save(out, "BMP")
    print(f"mask_strip.bmp: {strip.width}x{strip.height} "
          f"({MASK_ROWS + 1} cells of {MASK_CELL_W}x{MASK_CELL_H})")
    return out


def main() -> int:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SRC
    if not src.exists():
        print(f"mask sheet not found: {src}")
        return 2
    build(src)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
