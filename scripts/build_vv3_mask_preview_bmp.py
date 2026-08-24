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
SRC_CELL_W, SRC_CELL_H = 40, 128       # VV3 atlas cell (heathen_masks.png = 320x640)
FRONT_FRAME = 5                        # 6th frame from the left (front-facing)
MASK_ROWS = 5
# The mask preview uses a 40x65 cell, each mask scaled to fit (preserving aspect)
# and centred.  Source is VV3's OWN mask atlas so the picker art matches exactly
# what renders in game.
MASK_CELL_W, MASK_CELL_H = 40, 65
# Cross-game parity (VV2 canonical): autocrop the mask blob and fit it into a
# (40-2*PAD) x (65-2*PAD) window centred in the 40x65 cell -- the mask fills ~90%
# of the cell in every game, so it reads the same size once each game's identical
# 40x65 source cell is scaled into the shared preview boxes.
MASK_PAD = 2
DEFAULT_SRC = Path(__file__).resolve().parents[1] / "assets" / "vv3_heathen_masks" / "heathen_masks.png"


def build(src_path: Path) -> Path:
    sheet = Image.open(src_path).convert("RGBA")
    strip = Image.new("RGB", (MASK_CELL_W * (MASK_ROWS + 1), MASK_CELL_H), BACKGROUND)
    fit_w, fit_h = MASK_CELL_W - 2 * MASK_PAD, MASK_CELL_H - 2 * MASK_PAD
    for r in range(MASK_ROWS):
        x = FRONT_FRAME * SRC_CELL_W
        cell = sheet.crop((x, r * SRC_CELL_H, x + SRC_CELL_W, r * SRC_CELL_H + SRC_CELL_H))
        content = cell.crop(cell.getbbox())          # tight native content
        scale = min(fit_w / content.width, fit_h / content.height)
        nw, nh = max(1, int(round(content.width * scale))), max(1, int(round(content.height * scale)))
        content = content.resize((nw, nh), Image.LANCZOS)
        base = Image.new("RGBA", (MASK_CELL_W, MASK_CELL_H), BACKGROUND + (255,))
        base.alpha_composite(content, ((MASK_CELL_W - nw) // 2, (MASK_CELL_H - nh) // 2))
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
