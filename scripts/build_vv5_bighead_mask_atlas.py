"""Generate the VV5 Details-portrait bighead mask atlas (bigheads_masks.png).

Source art (owner-supplied) is a 3-column x 5-row sheet where the 3 COLUMNS are
the three head facings used by the Details idle animation (col0 = right-facing,
col1 = front, col2 = left-facing) and the 5 ROWS are the mask colours
(Blue/Orange/Red/Purple/Chief). Each column's mask is pre-aligned horizontally to
its facing's face-within-the-sprite, so the render tracks the head turn by
selecting the atlas column from the head's facing frame.

This packer:
  * keeps each column's horizontal position (the per-facing alignment), and
  * for each ROW, crops+places all three columns with the SAME vertical range so
    a colour's three facing frames share an identical Y (owner requirement), then
  * bottom-aligns the rows to a common chin line.

Output is a 3x5 even-grid RGBA PNG registered as sprite id 0x155 by
build_vv5_task9_native_actions.py and shipped to the game's Images/ folder.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "assets" / "vv5_bighead_masks" / "bigheads_masks_source.png"
OUT = ROOT / "assets" / "vv5_bighead_masks" / "bigheads_masks.png"
COLS, ROWS = 3, 5
MARGIN = 5
ALPHA = 16


def build(src_path: Path = SRC, out_path: Path = OUT) -> Image.Image:
    src = Image.open(src_path).convert("RGBA")
    W, H = src.size
    icw, ich = W // COLS, H // ROWS
    a = np.array(src)[:, :, 3]
    # per-row combined vertical bbox (across the 3 facing columns)
    rowbb = []
    maxrh = 0
    for r in range(ROWS):
        y0, y1 = 10 ** 9, -1
        for c in range(COLS):
            cell = a[r * ich:(r + 1) * ich, c * icw:(c + 1) * icw]
            ys, xs = np.where(cell > ALPHA)
            if len(ys):
                y0 = min(y0, int(ys.min()))
                y1 = max(y1, int(ys.max()) + 1)
        rowbb.append((y0, y1))
        maxrh = max(maxrh, y1 - y0)
    cell_h = maxrh + 2 * MARGIN
    out = Image.new("RGBA", (icw * COLS, cell_h * ROWS), (0, 0, 0, 0))
    for r in range(ROWS):
        y0, y1 = rowbb[r]
        rh = y1 - y0
        dy = r * cell_h + (cell_h - MARGIN - rh)  # bottom-align rows
        for c in range(COLS):
            # full column width preserves the per-facing horizontal alignment;
            # the row's shared y-range gives every colour's 3 frames the same Y.
            strip = src.crop((c * icw, r * ich + y0, (c + 1) * icw, r * ich + y1))
            out.paste(strip, (c * icw, dy), strip)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.save(out_path)
    return out


if __name__ == "__main__":
    img = build()
    dest = sys.argv[1] if len(sys.argv) > 1 else None
    print(f"wrote {OUT} {img.size} (3 facings x 5 colours, per-colour shared Y)")
    if dest:
        img.save(dest)
        print(f"also wrote {dest}")
