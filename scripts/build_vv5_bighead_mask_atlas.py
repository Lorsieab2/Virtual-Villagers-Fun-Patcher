"""Ship the VV5 Details-portrait bighead mask atlas (bigheads_masks.png).

The mask atlas IS the game's own native heathen-mask sheet, vv5_heathenheads.png
(the filename appears verbatim in the stock exe's strings). It is a uniform
8-column x 5-row grid of 65x145 cells:
    columns 0..7 = the 8 head FACINGS (one mask frame per head direction)
    rows 0..4    = the 5 mask COLOURS (blue/orange/red/purple/chief)

Every cell is artist-aligned to VV5's head geometry: each facing's mask is already
placed within its 65x145 cell so that, drawn at the head's own position and scale,
it lands exactly on the face -- including VV5's ~12px per-facing head-turn shift.
So we must ship the sheet UNMODIFIED (no re-crop, no re-pack, no resize); any
repacking destroys the built-in per-facing alignment and the mask drifts off the
face when the head turns. The native draw needs no per-facing offset table for the
same reason -- the art carries the offsets.

Output = an exact copy registered as sprite id 0x155 (8 cols x 5 rows) by
build_vv5_task9_native_actions.py and shipped to the game's Images/ folder.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "assets" / "vv5_bighead_masks" / "vv5_heathenheads.png"
OUT = ROOT / "assets" / "vv5_bighead_masks" / "bigheads_masks.png"
COLS, ROWS = 8, 5          # native layout: 8 facings x 5 colours
CELL_W, CELL_H = 65, 145   # native cell (VV5 head geometry)


def build(src_path: Path = SRC, out_path: Path = OUT) -> Image.Image:
    src = Image.open(src_path).convert("RGBA")
    if src.size != (CELL_W * COLS, CELL_H * ROWS):
        raise RuntimeError(
            f"vv5_heathenheads.png is {src.size}, expected "
            f"{(CELL_W * COLS, CELL_H * ROWS)} (8x5 of {CELL_W}x{CELL_H})"
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    src.save(out_path)
    return src


if __name__ == "__main__":
    img = build()
    print(f"wrote {OUT} {img.size} (native 8 facings x 5 colours, {CELL_W}x{CELL_H} cell, unmodified)")
    if len(sys.argv) > 1:
        img.save(sys.argv[1])
