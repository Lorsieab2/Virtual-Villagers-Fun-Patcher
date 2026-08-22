"""VV4 Heathen-mask overlay — place the VV5 masks into the head atlases at NATIVE
size (no scaling), aligned to each head's face per facing.

Mirrors the proven VV3 method (scripts/build_vv3_mask_atlas.py): the VV5 mask
sheet (vv5_heathenheads.png) is a uniform 8x5 grid of 65x145 cells; the mask
content is only ~26x45px, which fits a VV4 40x65 head cell. Each mask is taken at
NATIVE pixel size (tight-cropped, un-resized) and dropped onto head-atlas rows
30..34, centred on the head's detected SKIN (face) centroid for that facing — the
hair pulls the bbox off, so we align to skin, with the mask's face (~62% down)
sitting on the head's face. NO scaling, NO lift.

VV4 head atlases use the 00/10 (young/old) suffix. Usage:
    python build_vv4_mask_atlas.py --images "<install>/Images" --masks vv5_heathenheads.png --out <dir>
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

CELL_W, CELL_H = 40, 65
SRC_CELL_W, SRC_CELL_H = 65, 145
FRAMES = 8
MASK_ROWS = 5
HEAD_ROWS = 30
FACE_SAMPLE_ROWS = [3, 5, 8, 12, 20]
FACE_Y_FRAC = 0.62          # the face sits ~62% down the mask
MASK_LIFT = 0               # native placement, no lift (matches VV3 / user preference)
HEAD_ATLASES = ("male_heads00.png", "male_heads10.png",
                "female_heads00.png", "female_heads10.png")


def _native_mask_frames(src: Path) -> list[list[Image.Image]]:
    sheet = Image.open(src).convert("RGBA")
    out = []
    for r in range(MASK_ROWS):
        frames = []
        for f in range(FRAMES):
            cell = sheet.crop((f * SRC_CELL_W, r * SRC_CELL_H,
                               f * SRC_CELL_W + SRC_CELL_W, r * SRC_CELL_H + SRC_CELL_H))
            frames.append(cell)                          # FULL cell, uncropped (user: don't crop)
        out.append(frames)
    return out


def _is_skin(px) -> bool:
    r, g, b, a = px
    return a > 128 and r > 150 and g > 110 and b > 70 and r > b + 25 and (r - g) < 90


def _face_center_per_frame(src: Image.Image, cell_w: int = CELL_W,
                           cell_h: int = CELL_H) -> list[tuple[float, float]]:
    out = []
    for f in range(FRAMES):
        xs, ys = [], []
        for row in FACE_SAMPLE_ROWS:
            px = src.crop((f * cell_w, row * cell_h, f * cell_w + cell_w, row * cell_h + cell_h)).load()
            for y in range(cell_h):
                for x in range(cell_w):
                    if _is_skin(px[x, y]):
                        xs.append(x); ys.append(y)
        out.append((sum(xs) / len(xs), sum(ys) / len(ys)) if xs else (cell_w / 2.0, cell_h / 3.0))
    return out


def _place(mask: Image.Image, face_cx: float, face_cy: float,
           cell_w: int = CELL_W, cell_h: int = CELL_H, scale: float = 1.0) -> Image.Image:
    """Composite the FULL (uncropped) mask cell, aligned so the mask's own face
    (content-bbox centre-x, ~62% down its content) sits on the head's face.
    Only the placement offset uses the content bbox; no mask pixels are cropped.
    ``scale`` grows the mask uniformly for the larger detail-portrait heads (the
    small heads use scale 1.0, which skips the resize so their output is
    byte-identical). The output is one head cell, so anything beyond it clips."""
    if scale != 1.0:
        mask = mask.resize((max(1, round(mask.width * scale)),
                            max(1, round(mask.height * scale))), Image.LANCZOS)
    bb = mask.getbbox()                       # content extent (for the anchor only)
    mask_face_x = (bb[0] + bb[2]) / 2.0
    mask_face_y = bb[1] + (bb[3] - bb[1]) * FACE_Y_FRAC
    PAD = 256
    canvas = Image.new("RGBA", (cell_w + 2 * PAD, cell_h + 2 * PAD), (0, 0, 0, 0))
    x = PAD + int(round(face_cx - mask_face_x))
    y = PAD + int(round(face_cy + MASK_LIFT - mask_face_y))
    canvas.alpha_composite(mask, (x, y))       # full cell, nothing cropped off the sprite
    return canvas.crop((PAD, PAD, PAD + cell_w, PAD + cell_h))


def build_atlas(src: Image.Image, native: list[list[Image.Image]],
                cell_w: int = CELL_W, cell_h: int = CELL_H,
                head_rows: int = HEAD_ROWS, scale: float = 1.0) -> Image.Image:
    w = src.size[0]
    faces = _face_center_per_frame(src, cell_w, cell_h)
    out = Image.new("RGBA", (w, cell_h * (head_rows + MASK_ROWS)), (0, 0, 0, 0))
    out.paste(src.crop((0, 0, w, cell_h * head_rows)), (0, 0))
    for r in range(MASK_ROWS):
        for f in range(FRAMES):
            fcx, fcy = faces[f]
            out.paste(_place(native[r][f], fcx, fcy, cell_w, cell_h, scale),
                      (f * cell_w, cell_h * (head_rows + r)))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", required=True)
    ap.add_argument("--masks", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    native = _native_mask_frames(Path(a.masks))
    outdir = Path(a.out); outdir.mkdir(parents=True, exist_ok=True)
    for name in HEAD_ATLASES:
        src = Image.open(Path(a.images) / name).convert("RGBA")
        assert src.size == (CELL_W * FRAMES, CELL_H * HEAD_ROWS), f"{name} unexpected size {src.size}"
        build_atlas(src, native).save(outdir / name)
        print(f"  {name}: {HEAD_ROWS} -> {HEAD_ROWS + MASK_ROWS} rows (native, face-aligned)")


if __name__ == "__main__":
    main()
