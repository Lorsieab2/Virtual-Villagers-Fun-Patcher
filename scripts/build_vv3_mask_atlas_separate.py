"""Build the VV3 dedicated Heathen-mask atlas (Images/heathen_masks.png).

VV2 separate-atlas method: a standalone mask atlas drawn ON TOP of the head via
the game's child/scaled draw thunk (see build_vv3_mask_stage2.py). This avoids
the append-rows corruption and, with taller cells + a draw-time lift, shows the
full towering masks (red horns, chief feathers) without clipping.

Source: the user's hand-aligned port canvases (assets/vv3_heathen_masks/
mask_<color>.png, 520x1286), where the VV3 head origin is at canvas (106, 1149)
-- verified by a 100% pixel match of the ginger reference head (male_heads row
22). Each mask is placed at x=0 (native alignment) with a vertical LIFT so the
draw's matching lift (lift = (headY*54)>>7 ~= 42*scale) seats the face on the
head and lets the feathers rise above it. Each cell is clipped so a profile mask
never bleeds into its neighbour frame.

Atlas: 8 cols (facings) x 5 rows (masks), cell 40x128 -> 320x640.
Rows (mask byte +0xED0 -> atlas row byte-1): 0 blue,1 orange,2 red,3 purple,4 chief.

The chief uses a staggered per-frame canvas and is handled by its own path
(pending un-stagger); its row is left transparent here.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

CELL_W, CELL_H = 40, 128
COLS, ROWS = 8, 5
LIFT = 42
CANVAS_DX, CANVAS_DY = 106, 1149          # head-frame-0 origin in the port canvas
STRAIGHT = ["blue", "orange", "red", "purple"]   # rows 0..3; chief (row 4) pending
ORDER = ["blue", "orange", "red", "purple", "chief"]

SRC = Path(__file__).resolve().parents[1] / "assets" / "vv3_heathen_masks"


def build() -> Path:
    atlas = Image.new("RGBA", (CELL_W * COLS, CELL_H * ROWS), (0, 0, 0, 0))
    for ri, name in enumerate(ORDER):
        if name not in STRAIGHT:
            continue                       # chief: staggered, handled separately
        port = Image.open(SRC / f"mask_{name}.png").convert("RGBA")
        # translate canvas(CANVAS_DX,CANVAS_DY) -> cell top (0,0), then + LIFT in y
        shifted = Image.new("RGBA", (CELL_W * COLS, CELL_H), (0, 0, 0, 0))
        shifted.alpha_composite(port, (-CANVAS_DX, -CANVAS_DY + LIFT))
        for c in range(COLS):              # per-cell clip (no bleed into neighbours)
            cell = shifted.crop((c * CELL_W, 0, c * CELL_W + CELL_W, CELL_H))
            atlas.paste(cell, (c * CELL_W, ri * CELL_H))
    out = SRC / "heathen_masks.png"
    atlas.save(out)
    print(f"heathen_masks.png: {atlas.size} (cell {CELL_W}x{CELL_H}, "
          f"{COLS} cols x {ROWS} rows; chief row pending un-stagger)")
    return out


if __name__ == "__main__":
    build()
