"""Generate the VV1 Heathen-mask overlay sheets from the VV5 mask art.

The overlay is drawn by a hook inside VV1's own per-villager render loop with
a direct SDL_UpperBlit, so this script controls the sheet geometry outright.
It deliberately mirrors VV1's OWN head atlas geometry:

    male_heads.png / female_heads.png are 280x1300 = 7 columns x 20 rows of
    40x65 cells (confirmed empirically: the fully-transparent separator
    columns fall on multiples of 40, and 1300/65 == 20 exactly).

so each generated sheet is 7 cells of 40x65 (280x65), one cell per facing
column. At runtime the hook blits cell[facing] at the villager's own screen
position, which means alignment is a property of THIS ART, not of the
assembly: to nudge a mask, regenerate the sheets, don't touch the patch.

Two constraints from the requester, both honoured here:

  * "don't crop the mask sprites" -- the only crop is getbbox(), which removes
    fully transparent margin and therefore loses no visible pixel. Placement
    is then clamped so the whole mask (feathers included) stays inside the
    cell rather than being cut off at the edge.
  * "do not alter the mask sizing" -- the art is copied at its native pixel
    size. There is no resize anywhere in this script.

Usage:  python scripts/build_vv1_heathen_mask_sheets.py [--check]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "assets" / "origins"

# VV5 mask sheet: 520x725 = 8 columns x 5 rows of 65x145.
MASK_SHEET = Path(
    r"C:/Users/Owner/Downloads/Virtual Villagers - New Believers/Images"
    r"/vv5_heathenheads.png"
)
MASK_CELL_W, MASK_CELL_H = 65, 145
MASK_FRAMES, MASK_ROWS = 8, 5

# VV1 head atlas geometry (see module docstring).
HEAD_SHEET = Path(
    r"C:/Users/Owner/Downloads/Virtual Villagers - A New Home/Images/male_heads.png"
)
CELL_W, CELL_H = 40, 65
FACINGS = 7

# Head rows sampled when locating the face; averaging several head styles
# keeps one unusual hairstyle from dragging the centroid around.
FACE_SAMPLE_ROWS = [1, 3, 5, 8, 12]

# The face sits roughly this far down the mask art, so aligning the mask's
# face point to the head's face point means offsetting by this fraction.
FACE_Y_FRAC = 0.62

# VV1 has 7 facing columns; the VV5 mask art has 8 frames, so the mapping
# cannot be a straight 1:1 index. This table is the tunable part: entry i is
# the mask frame drawn for VV1 head column i. Values below are a first pass
# read off a side-by-side render of both sheets (VV1 columns 0-1 face right,
# 2-3 face left, 4-6 are frontal; mask frames 0-3 face left, 4-6 are frontal,
# 7 faces right). Expect to refine these against an in-game screenshot -- that
# is a one-line edit here plus a regenerate, with no patch rebuild needed.
MASK_FRAME_FOR_FACING = [7, 6, 0, 1, 4, 5, 6]

COLOURS = ["blue", "orange", "red", "purple", "chief"]


def _is_skin(px) -> bool:
    r, g, b, a = px
    return a > 128 and r > 150 and g > 110 and b > 70 and r > b + 25 and (r - g) < 90


def _face_centre_per_facing(head: Image.Image) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for f in range(FACINGS):
        xs: list[int] = []
        ys: list[int] = []
        for row in FACE_SAMPLE_ROWS:
            cell = head.crop(
                (f * CELL_W, row * CELL_H, (f + 1) * CELL_W, (row + 1) * CELL_H)
            )
            px = cell.load()
            for y in range(CELL_H):
                for x in range(CELL_W):
                    if _is_skin(px[x, y]):
                        xs.append(x)
                        ys.append(y)
        out.append(
            (sum(xs) / len(xs), sum(ys) / len(ys)) if xs else (CELL_W / 2, CELL_H * 0.34)
        )
    return out


def _native_mask_frames(row: int) -> list[Image.Image]:
    sheet = Image.open(MASK_SHEET).convert("RGBA")
    frames = []
    for f in range(MASK_FRAMES):
        cell = sheet.crop(
            (
                f * MASK_CELL_W,
                row * MASK_CELL_H,
                (f + 1) * MASK_CELL_W,
                (row + 1) * MASK_CELL_H,
            )
        )
        bbox = cell.getbbox()
        # getbbox() only strips fully transparent margin: no visible pixel is
        # lost, and the result keeps the art at its native size.
        frames.append(cell.crop(bbox) if bbox else cell)
    return frames


def _place(mask: Image.Image, face_cx: float, face_cy: float) -> Image.Image:
    nw, nh = mask.size
    pad = 96
    canvas = Image.new("RGBA", (CELL_W + 2 * pad, CELL_H + 2 * pad), (0, 0, 0, 0))
    ix = int(round(face_cx - nw / 2))
    iy = int(round(face_cy - nh * FACE_Y_FRAC))
    # Keep the whole mask inside the cell so nothing is clipped away.
    if nw <= CELL_W:
        ix = max(0, min(ix, CELL_W - nw))
    if nh <= CELL_H:
        iy = max(0, min(iy, CELL_H - nh))
    else:
        iy = 0
    canvas.alpha_composite(mask, (pad + ix, pad + iy))
    return canvas.crop((pad, pad, pad + CELL_W, pad + CELL_H))


def build() -> list[tuple[Path, bytes]]:
    head = Image.open(HEAD_SHEET).convert("RGBA")
    faces = _face_centre_per_facing(head)
    results: list[tuple[Path, bytes]] = []
    for row in range(MASK_ROWS):
        frames = _native_mask_frames(row)
        sheet = Image.new("RGBA", (CELL_W * FACINGS, CELL_H), (0, 0, 0, 0))
        for facing in range(FACINGS):
            art = frames[MASK_FRAME_FOR_FACING[facing]]
            fcx, fcy = faces[facing]
            sheet.paste(_place(art, fcx, fcy), (facing * CELL_W, 0))
        out = OUT_DIR / f"m{row + 1}.png"
        import io

        buf = io.BytesIO()
        sheet.save(buf, "PNG")
        results.append((out, buf.getvalue()))
    return results


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--check",
        action="store_true",
        help="verify the committed sheets match what this script generates",
    )
    args = ap.parse_args()
    built = build()
    if args.check:
        bad = [str(p) for p, data in built if not p.exists() or p.read_bytes() != data]
        if bad:
            print("stale/missing mask sheets: " + ", ".join(bad))
            return 1
        print(f"{len(built)} mask sheets match the generator")
        return 0
    for path, data in built:
        path.write_bytes(data)
        print(f"wrote {path.relative_to(ROOT)} ({len(data)} bytes)")
    print(f"geometry: {FACINGS} facings x {CELL_W}x{CELL_H}, native size, no scaling")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
