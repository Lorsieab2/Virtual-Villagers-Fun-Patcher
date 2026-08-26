"""Generate the VV5 Details-portrait bighead mask atlas (bigheads_masks.png).

Source art (owner-supplied) is `vv5_heathenheads.png`, an 8-column x 5-row sheet
(one mask FRAME per head directional frame, 5 ROWS = mask colours
Blue/Orange/Red/Purple/Chief). The Details idle head only uses three facings, so
this packer extracts just those columns (owner spec):
    frame 5 = right-facing, frame 6 = front-facing, frame 7 = left-facing
and emits them, in that order, as a 3-column x 5-row atlas (col0=right, col1=front,
col2=left) -- exactly the layout the native bighead draw expects
(BIGHEAD_ATLAS_COLS=3, BH_FACE_TABLE=[0,1,2]).

This packer:
  * extracts SRC_FRAMES (the 3 Details facings) from the 8-frame source, and
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
SRC = ROOT / "assets" / "vv5_bighead_masks" / "vv5_heathenheads.png"
OUT = ROOT / "assets" / "vv5_bighead_masks" / "bigheads_masks.png"
SRC_COLS = 8            # the source is an 8-directional-frame sheet
ROWS = 5               # mask colours: Blue/Orange/Red/Purple/Chief
# Details facings, in output order (col0=right, col1=front, col2=left):
SRC_FRAMES = [5, 6, 7]
COLS = len(SRC_FRAMES)  # output columns = 3
MARGIN = 5
ALPHA = 16


def build(src_path: Path = SRC, out_path: Path = OUT) -> Image.Image:
    src = Image.open(src_path).convert("RGBA")
    W, H = src.size
    icw, ich = W // SRC_COLS, H // ROWS
    a = np.array(src)[:, :, 3]
    # per-row combined vertical bbox (across the 3 extracted facing frames)
    rowbb = []
    maxrh = 0
    for r in range(ROWS):
        y0, y1 = 10 ** 9, -1
        for sc in SRC_FRAMES:
            cell = a[r * ich:(r + 1) * ich, sc * icw:(sc + 1) * icw]
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
        for c, sc in enumerate(SRC_FRAMES):
            # full column width preserves the per-facing horizontal alignment;
            # the row's shared y-range gives every colour's 3 frames the same Y.
            strip = src.crop((sc * icw, r * ich + y0, (sc + 1) * icw, r * ich + y1))
            out.paste(strip, (c * icw, dy), strip)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.save(out_path)
    return out


if __name__ == "__main__":
    img = build()
    dest = sys.argv[1] if len(sys.argv) > 1 else None
    print(f"wrote {OUT} {img.size} (frames {SRC_FRAMES} = right/front/left x {ROWS} colours, per-colour shared Y)")
    if dest:
        img.save(dest)
        print(f"also wrote {dest}")
