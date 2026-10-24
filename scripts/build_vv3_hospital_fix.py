"""Build The Secret City's fixed hospital sheet for Fix Vanilla Bugs.

The owner redrew the table legs of the hospital's lower supply table
(assets/vv3_hospital/hospital_owner_source.png, by Lorsieab2): "It's the exact
same as the normal one except I fixed the table leg graphics."  The stock sheet
is the game's Images/map_hospitalStates.png (1071x280 RGBA, three 357x280
frames side by side: straw beds, mats, sleeping bags under the roof), vendored
here byte for byte as assets/vv3_hospital/map_hospitalStates_stock.png.

The shipped sheet, assets/vv3_hospital/vvfp_hospitalFixed.png, is the stock
sheet with only the owner's VISIBLE changes taken over: a pixel is the owner's
when its alpha differs, or its colour differs where either image shows it
(alpha > 0).  Everything else is the stock pixel, so the colour the owner's
editor wrote under fully transparent pixels (invisible; about 210,000 of them)
is dropped and the stock bytes kept.  Every pixel taken must lie inside the
two table-leg boxes below, or the build fails.  The file carries the stock
sheet's own gAMA (0.45) and no other ancillary chunk.

Run:  python scripts/build_vv3_hospital_fix.py
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

from PIL import Image
from PIL.PngImagePlugin import PngInfo

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "assets" / "vv3_hospital"
STOCK = FOLDER / "map_hospitalStates_stock.png"
OWNER = FOLDER / "hospital_owner_source.png"
OUT = FOLDER / "vvfp_hospitalFixed.png"

FRAME_W, FRAME_H, FRAMES = 357, 280, 3
# The lower supply table's legs, sheet coordinates (x0, y0, x1, y1), end
# exclusive.  Frame 1 (straw beds) has no change.
LEG_BOXES = {
    "frame 2 (mats)": (498, 241, 525, 274),
    "frame 3 (sleeping bags)": (840, 246, 881, 269),
}


def visible_changes(stock: Image.Image, owner: Image.Image) -> list[tuple[int, int]]:
    """Every (x, y) where the two sheets look different."""
    out = []
    s = stock.load()
    o = owner.load()
    for y in range(stock.height):
        for x in range(stock.width):
            a, b = s[x, y], o[x, y]
            if a == b:
                continue
            if a[3] != b[3] or (a[:3] != b[:3] and (a[3] or b[3])):
                out.append((x, y))
    return out


def in_leg_box(x: int, y: int) -> bool:
    return any(x0 <= x < x1 and y0 <= y < y1 for x0, y0, x1, y1 in LEG_BOXES.values())


def build() -> Image.Image:
    stock = Image.open(STOCK).convert("RGBA")
    owner = Image.open(OWNER).convert("RGBA")
    if stock.size != (FRAME_W * FRAMES, FRAME_H) or owner.size != stock.size:
        raise SystemExit(f"unexpected sizes: stock {stock.size}, owner {owner.size}")
    changes = visible_changes(stock, owner)
    outside = [p for p in changes if not in_leg_box(*p)]
    if outside:
        raise SystemExit(f"{len(outside)} changed pixels outside the table legs, e.g. {outside[:5]}")
    fixed = stock.copy()
    f = fixed.load()
    o = owner.load()
    for x, y in changes:
        f[x, y] = o[x, y]
    return fixed


def main() -> None:
    fixed = build()
    info = PngInfo()
    info.add(b"gAMA", struct.pack(">I", 45000))   # the stock sheet's own gamma
    fixed.save(OUT, format="PNG", pnginfo=info, optimize=True)
    print(OUT, OUT.stat().st_size)


if __name__ == "__main__":
    main()
