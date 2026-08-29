"""Append the user's pre-aligned Heathen-mask art to the VV3 head atlases.

The mask art (assets/vv3_heathen_masks/mask_<color>.png) is the user's aligned
"port" canvas: a 520x1286 image where the 8 directional masks are placed to sit
exactly on the VV3 head sprites.  The head origin in that canvas is (106, 1149)
-- i.e. atlas head-frame-0 top-left maps to canvas (106, 1149) -- verified by a
100% pixel match of the ginger reference head (male_heads row 22).  So each mask
row is just the port translated by (-106, -1149) into the 320x65 head cell.

Rows (mask byte +0xED0 -> atlas row 29+byte):
    30 blue (1), 31 orange (2), 32 red (3), 33 purple (4), 34 chief (5).

The chief uses a staggered per-frame canvas and is handled by its own path
(build_vv3_chief_mask_row); the straight-row masks use the shared offset.

NOTE ON HEIGHT: masks whose tall parts (red horns, purple ears, chief feathers)
rise above the 65px head cell are clipped here (single-cell).  Showing them in
full needs the two-cell "towering" render, tracked separately.

Usage:  python build_vv3_mask_atlas.py "<game Images dir>"
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

CELL_W, CELL_H = 40, 65
FRAMES = 8
# atlas head-frame-0 origin within the user's 520x1286 port canvas
CANVAS_DX, CANVAS_DY = 106, 1149
# rows 30..34 in mask-byte order (1..5); chief handled per-frame
STRAIGHT_MASKS = ["blue", "orange", "red", "purple"]
MASK_ORDER = ["blue", "orange", "red", "purple", "chief"]

SRC = Path(__file__).resolve().parents[1] / "assets" / "vv3_heathen_masks"
HEAD_ATLASES = [
    "male_heads.png", "male_heads_old.png",
    "female_heads.png", "female_heads_old.png",
]


def _straight_mask_row(color: str) -> Image.Image:
    port = Image.open(SRC / f"mask_{color}.png").convert("RGBA")
    row = Image.new("RGBA", (CELL_W * FRAMES, CELL_H), (0, 0, 0, 0))
    row.alpha_composite(port, (-CANVAS_DX, -CANVAS_DY))   # clips to the 65px cell
    return row


def _mask_row(color: str) -> Image.Image:
    if color in STRAIGHT_MASKS:
        return _straight_mask_row(color)
    # chief: staggered layout, per-frame (deferred). Placeholder = empty row so
    # the atlas keeps 35 rows and selecting the chief shows the head cleanly.
    return Image.new("RGBA", (CELL_W * FRAMES, CELL_H), (0, 0, 0, 0))


def apply_to_atlas(atlas_path: Path) -> None:
    bak = atlas_path.with_suffix(".mask-bak.png")
    if bak.exists():
        src = Image.open(bak).convert("RGBA")          # clean 30-row original
    else:
        src = Image.open(atlas_path).convert("RGBA")
        bak.write_bytes(atlas_path.read_bytes())
    w = src.width
    new_rows = 30 + len(MASK_ORDER)
    out = Image.new("RGBA", (w, CELL_H * new_rows), (0, 0, 0, 0))
    out.paste(src.crop((0, 0, w, CELL_H * 30)), (0, 0))
    for i, color in enumerate(MASK_ORDER):
        out.alpha_composite(_mask_row(color), (0, (30 + i) * CELL_H))
    out.save(atlas_path)
    print(f"  {atlas_path.name}: 30 -> {new_rows} rows (blue/orange/red/purple aligned; chief pending)")


def main(images_dir: Path) -> None:
    for name in HEAD_ATLASES:
        apply_to_atlas(images_dir / name)
    print("done")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print('usage: build_vv3_mask_atlas.py "<game Images dir>"')
        raise SystemExit(2)
    main(Path(sys.argv[1]))
