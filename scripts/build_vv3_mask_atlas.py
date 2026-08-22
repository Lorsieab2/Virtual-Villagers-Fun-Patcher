"""Append the user's pre-aligned Heathen-mask art to the VV3 head atlases.

The mask art (assets/vv3_heathen_masks/mask_<color>.png) is an 8-frame
directional strip at head-atlas x-scale (40 px/frame), pre-aligned by the user
to the exact head sprites.  Each strip is composited into the head atlas as new
rows 30..34 at x=0, with only a per-mask vertical seat (SEAT_DY) so the face
sits on the head.  No scaling, no per-frame nudging -- the art carries its own
alignment.

Rows (mask byte +0xED0 -> atlas row 29+byte):
    30 blue (1), 31 orange (2), 32 red (3), 33 purple (4), 34 chief (5).

NOTE ON HEIGHT: the head atlas cell is 40x65, so any mask taller than the room
above the head (notably the Tribal Chief's feathers and the red horns) is
clipped at the cell top.  Showing the full towering masks needs the two-cell
render (tracked separately); this builder produces the single-cell version.

Usage:  python build_vv3_mask_atlas.py "<game Images dir>"
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

CELL_W, CELL_H = 40, 65
FRAMES = 8
# rows 30..34, in mask-byte order (1..5)
MASK_ORDER = ["blue", "orange", "red", "purple", "chief"]
# per-mask vertical seat (atlas-y offset; negative = up), derived from the
# user's alignment mockups against female_heads row 26 (head position is
# consistent across every head row and atlas).
SEAT_DY = {"blue": -4, "orange": -2, "red": -20, "purple": -4, "chief": -54}

SRC = Path(__file__).resolve().parents[1] / "assets" / "vv3_heathen_masks"
HEAD_ATLASES = [
    "male_heads.png", "male_heads_old.png",
    "female_heads.png", "female_heads_old.png",
]


def _mask_row(color: str) -> Image.Image:
    port = Image.open(SRC / f"mask_{color}.png").convert("RGBA")
    row = Image.new("RGBA", (CELL_W * FRAMES, CELL_H), (0, 0, 0, 0))
    row.alpha_composite(port, (0, SEAT_DY[color]))   # clips to the 65px cell
    return row


def apply_to_atlas(atlas_path: Path) -> None:
    bak = atlas_path.with_suffix(".mask-bak.png")
    if bak.exists():
        src = Image.open(bak).convert("RGBA")          # clean 30-row original
    else:
        src = Image.open(atlas_path).convert("RGBA")
        bak.write_bytes(atlas_path.read_bytes())       # back up the original
    w = src.width
    new_rows = 30 + len(MASK_ORDER)
    out = Image.new("RGBA", (w, CELL_H * new_rows), (0, 0, 0, 0))
    out.paste(src.crop((0, 0, w, CELL_H * 30)), (0, 0))
    for i, color in enumerate(MASK_ORDER):
        out.alpha_composite(_mask_row(color), (0, (30 + i) * CELL_H))
    out.save(atlas_path)
    print(f"  {atlas_path.name}: 30 -> {new_rows} rows (user art, x=0 seated)")


def main(images_dir: Path) -> None:
    for name in HEAD_ATLASES:
        apply_to_atlas(images_dir / name)
    print("done; head atlases carry the user's mask rows 30..34 (single-cell)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print('usage: build_vv3_mask_atlas.py "<game Images dir>"')
        raise SystemExit(2)
    main(Path(sys.argv[1]))
