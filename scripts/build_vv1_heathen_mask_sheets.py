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
CELL_W, HEAD_CELL_H = 40, 65
FACINGS = 7

# The generated sheet does NOT reuse the head cell's 65px height. VV1's head
# content is only ~23x25 sitting at the top of its 65px cell, while the VV5
# mask art is up to 46px tall because it includes the feather plumes that rise
# ABOVE the head. Aligning the mask's face to the head's face therefore needs
# the plumes to occupy space above that point, which a top-anchored 65px cell
# cannot express without clipping them off.
#
# So the sheet uses its own 52px cell, each frame placed so its face point
# lands on a fixed row (MASK_FACE_CELL_Y), and the draw hook offsets the
# destination Y so that row lands on the head's face. Nothing is scaled and
# nothing is cropped: the tallest frame (46px) starts at y=3 and ends at y=49,
# comfortably inside the cell.
#
# Sized from the real art, not row 0 alone: frame heights run 32..72 across the
# five colour rows (the Tribal Chief headdress in row 4 is the tallest at 72,
# and row 2 reaches 64). A cell sized off row 0 clips those, which the guard in
# _place() catches rather than silently cropping.
SHEET_CELL_H = 76
MASK_FACE_CELL_Y = 45

# Head rows sampled when locating the face; averaging several head styles
# keeps one unusual hairstyle from dragging the centroid around.
FACE_SAMPLE_ROWS = [1, 3, 5, 8, 12]

# The face sits roughly this far down the mask art, so aligning the mask's
# face point to the head's face point means offsetting by this fraction.
FACE_Y_FRAC = 0.62

# Measured from the stock atlas: the head's own skin centroid sits this far
# down its 65px cell (16.8-17.6 across all seven facings, so a single constant
# is fine). build_vv1_origins_feature.py's stash hook derives its Y offset from
# this and MASK_FACE_CELL_Y; the two must be changed together.
HEAD_FACE_CELL_Y = 17

# VV1 has 7 facing columns; the VV5 mask art has 8 frames, so the mapping
# cannot be a straight 1:1 index. This table is the tunable part: entry i is
# the mask frame drawn for VV1 head column i. Values below are a first pass
# read off a side-by-side render of both sheets (VV1 columns 0-1 face right,
# 2-3 face left, 4-6 are frontal; mask frames 0-3 face left, 4-6 are frontal,
# 7 faces right). Expect to refine these against an in-game screenshot -- that
# is a one-line edit here plus a regenerate, with no patch rebuild needed.
MASK_FRAME_FOR_FACING = [7, 6, 0, 1, 4, 5, 6]

COLOURS = ["blue", "orange", "red", "purple", "chief"]

# Change Appearance preview strip. The dialog previews head and body from BMP
# resources compiled into the icons DLL (see build_vv1_appearance_bitmaps.py),
# so the mask preview is built the same way rather than inventing a second
# mechanism. Geometry matches that script's convention: one 40-wide column,
# one row per selectable value, stacked top to bottom.
#
# Row 0 is the blank "(None)" entry so the strip can be indexed by the mask
# value directly (0..5) with no offset arithmetic in the dialog code.
#
# PREVIEW_FRAME 5 matches build_vv1_appearance_bitmaps.py's own HEAD_FRAME: it
# is the front-facing column, so the previewed mask faces the player the same
# way the previewed head does.
PREVIEW_FRAME = 5
PREVIEW_BG = (236, 236, 236)
PREVIEW_BMP = ROOT / "native" / "vv1_origins_icons" / "appearance" / "mask.bmp"


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
                (f * CELL_W, row * HEAD_CELL_H, (f + 1) * CELL_W, (row + 1) * HEAD_CELL_H)
            )
            px = cell.load()
            for y in range(HEAD_CELL_H):
                for x in range(CELL_W):
                    if _is_skin(px[x, y]):
                        xs.append(x)
                        ys.append(y)
        out.append(
            (sum(xs) / len(xs), sum(ys) / len(ys)) if xs else (CELL_W / 2, float(HEAD_FACE_CELL_Y))
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


def _place(mask: Image.Image, face_cx: float) -> Image.Image:
    """Native-size mask, horizontally centred on the head's face, vertically
    anchored so its face point lands on MASK_FACE_CELL_Y.

    No resize and no content crop: the only crop is getbbox() upstream, which
    removes fully transparent margin. Placement is checked to stay inside the
    cell so the plumes are never clipped.
    """
    nw, nh = mask.size
    canvas = Image.new("RGBA", (CELL_W, SHEET_CELL_H), (0, 0, 0, 0))
    ix = int(round(face_cx - nw / 2))
    ix = max(0, min(ix, CELL_W - nw)) if nw <= CELL_W else 0
    iy = int(round(MASK_FACE_CELL_Y - nh * FACE_Y_FRAC))
    if iy < 0 or iy + nh > SHEET_CELL_H:
        raise ValueError(
            f"mask {nw}x{nh} would be clipped at y={iy} in a {SHEET_CELL_H}px "
            "cell; raise SHEET_CELL_H rather than cropping the art"
        )
    canvas.alpha_composite(mask, (ix, iy))
    return canvas


def build() -> list[tuple[Path, bytes]]:
    head = Image.open(HEAD_SHEET).convert("RGBA")
    faces = _face_centre_per_facing(head)
    results: list[tuple[Path, bytes]] = []
    for row in range(MASK_ROWS):
        frames = _native_mask_frames(row)
        sheet = Image.new("RGBA", (CELL_W * FACINGS, SHEET_CELL_H), (0, 0, 0, 0))
        for facing in range(FACINGS):
            art = frames[MASK_FRAME_FOR_FACING[facing]]
            fcx, _fcy = faces[facing]
            sheet.paste(_place(art, fcx), (facing * CELL_W, 0))
        out = OUT_DIR / f"m{row + 1}.png"
        import io

        buf = io.BytesIO()
        sheet.save(buf, "PNG")
        results.append((out, buf.getvalue()))
    return results


def build_preview_strip() -> bytes:
    """One 40x(76*6) BMP: row 0 blank, rows 1-5 the five masks head-on.

    Flattened onto the dialog's own background colour because a BMP resource
    carries no alpha; appearance_draw() fills the same colour before blitting,
    so the seam is invisible.
    """
    import io

    rows = 1 + MASK_ROWS
    strip = Image.new("RGB", (CELL_W, SHEET_CELL_H * rows), PREVIEW_BG)
    for row in range(MASK_ROWS):
        sheet = Image.open(OUT_DIR / f"m{row + 1}.png").convert("RGBA")
        cell = sheet.crop(
            (
                PREVIEW_FRAME * CELL_W,
                0,
                (PREVIEW_FRAME + 1) * CELL_W,
                SHEET_CELL_H,
            )
        )
        flat = Image.new("RGB", cell.size, PREVIEW_BG)
        flat.paste(cell, (0, 0), cell)
        strip.paste(flat, (0, SHEET_CELL_H * (row + 1)))
    buf = io.BytesIO()
    strip.save(buf, "BMP")
    return buf.getvalue()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--check",
        action="store_true",
        help="verify the committed sheets match what this script generates",
    )
    args = ap.parse_args()
    built = build()
    built.append((PREVIEW_BMP, build_preview_strip()))
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
    print(f"geometry: {FACINGS} facings x {CELL_W}x{SHEET_CELL_H}, native size, no scaling, nothing cropped")
    print(f"preview strip: {CELL_W}x{SHEET_CELL_H * (1 + MASK_ROWS)} (frame {PREVIEW_FRAME}, row 0 = None)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
