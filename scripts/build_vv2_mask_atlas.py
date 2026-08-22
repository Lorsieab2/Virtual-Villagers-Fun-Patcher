"""VV2 Heathen-mask overlay atlas builder.

Uses VV3's technique (scripts/build_vv3_mask_atlas.py) — native-size masks, face
extracted per facing, drawn by the render hook via FUN_004095b0 — but with the
one deviation VV2 needs: the masks (Chief ~72px, Red ~63px) are TALLER than the
65px head-atlas cell, so cramming them into head rows would clip the feathers.
Instead we pack them into a DEDICATED mask atlas with taller cells (40x88), each
mask face-anchored at a fixed cell-y, so the render hook draws the whole mask at
the head with the face-plate on the villager and the feathers/spikes above.

The VV5 sheet's 8 masks/row are separate blobs whose centers are offset from any
uniform grid, so we extract each mask by its own connected component (no double,
no bleed, no cropping).

Usage:
  python build_vv2_mask_atlas.py --atlas <out.png>          # write dedicated mask atlas
  python build_vv2_mask_atlas.py --preview                  # write on-head preview PNG
"""
from __future__ import annotations

import sys
from pathlib import Path
from PIL import Image
import numpy as np
from scipy import ndimage

SRC_CELL_W, SRC_CELL_H = 65, 145   # VV5 uniform cell (520x725 / 8 / 5)
FRAMES = 8
MASK_ROWS = 5
FACE_Y_FRAC = 0.62                 # the mask's own face sits ~62% down the mask

# head atlas (for face detection + preview)
HEAD_W, HEAD_H = 35, 65
FACE_SAMPLE_ROWS = [3, 5, 8, 12, 20]

# dedicated mask atlas: taller cell so the tallest mask fits fully, face-anchored
MASK_CELL_W, MASK_CELL_H = 40, 88
MASK_ANCHOR_Y = 54                 # the mask's face-line sits at this cell-y (fixed)

SRC = Path(r"C:/Users/Owner/Downloads/vv5_heathenheads.png")
HEADS_DIR = Path(r"C:/Users/Owner/Downloads/Vanilla Games - Copy/Virtual Villagers - The Lost Children/Images")
SCRATCH = Path(r"C:/Users/Owner/AppData/Local/Temp/claude/C--Users-Owner--claude/0273893a-8270-4370-a19f-cd0f96b9c774/scratchpad")


def _native_mask_frames() -> list[list[Image.Image]]:
    """8 full, isolated, native-size masks per row (by connected blob), facing 0..7."""
    m = np.asarray(Image.open(SRC).convert("RGBA"))
    out = []
    for r in range(MASK_ROWS):
        band = m[r * SRC_CELL_H:(r + 1) * SRC_CELL_H]
        lbl, n = ndimage.label(band[..., 3] > 20)
        sizes = np.bincount(lbl.ravel()); sizes[0] = 0
        ids = sorted((i for i in range(1, n + 1) if sizes[i] > 150), key=lambda i: -sizes[i])[:FRAMES]
        frames = []
        for i in ids:
            ys, xs = np.where(lbl == i)
            y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
            sub = band[y0:y1, x0:x1].copy()
            sub[lbl[y0:y1, x0:x1] != i] = 0
            frames.append((float(xs.mean()), Image.fromarray(sub, "RGBA")))
        frames.sort(key=lambda t: t[0])
        assert len(frames) == FRAMES, f"row {r}: {len(frames)} masks (expected {FRAMES})"
        out.append([im for _, im in frames])
    return out


def _is_skin(px) -> bool:
    r, g, b, a = px
    return a > 128 and r > 150 and g > 110 and b > 70 and r > b + 25 and (r - g) < 90


def _face_center_per_frame(src: Image.Image) -> list[tuple[float, float]]:
    out = []
    for f in range(FRAMES):
        xs, ys = [], []
        for row in FACE_SAMPLE_ROWS:
            px = src.crop((f * HEAD_W, row * HEAD_H, f * HEAD_W + HEAD_W, row * HEAD_H + HEAD_H)).load()
            for y in range(HEAD_H):
                for x in range(HEAD_W):
                    if _is_skin(px[x, y]):
                        xs.append(x); ys.append(y)
        out.append((sum(xs) / len(xs), sum(ys) / len(ys)) if xs else (HEAD_W / 2, 24.0))
    return out


def _paste_faceanchored(dst: Image.Image, mask: Image.Image, cx: int, face_y: int) -> None:
    """Paste the WHOLE mask so it's h-centered on cx and its face-line lands on face_y."""
    nw, nh = mask.size
    x = cx - nw // 2
    y = face_y - int(round(nh * FACE_Y_FRAC))
    dst.alpha_composite(mask, (x, y))


def build_mask_atlas(out_path: Path) -> None:
    frames = _native_mask_frames()
    atlas = Image.new("RGBA", (MASK_CELL_W * FRAMES, MASK_CELL_H * MASK_ROWS), (0, 0, 0, 0))
    for r in range(MASK_ROWS):
        for f in range(FRAMES):
            cell = Image.new("RGBA", (MASK_CELL_W, MASK_CELL_H), (0, 0, 0, 0))
            _paste_faceanchored(cell, frames[r][f], MASK_CELL_W // 2, MASK_ANCHOR_Y)
            atlas.paste(cell, (f * MASK_CELL_W, r * MASK_CELL_H))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    atlas.save(out_path)
    print(f"mask atlas -> {out_path}  ({atlas.size[0]}x{atlas.size[1]} = {FRAMES} frames x {MASK_ROWS} masks, cell {MASK_CELL_W}x{MASK_CELL_H}, face-line y={MASK_ANCHOR_Y})")


def preview() -> None:
    frames = _native_mask_frames()
    heads = Image.open(HEADS_DIR / "male_heads.png").convert("RGBA")
    faces = _face_center_per_frame(heads)
    PADTOP = 30
    ch = HEAD_H + PADTOP
    grid = Image.new("RGBA", (HEAD_W * FRAMES, ch * MASK_ROWS), (110, 110, 110, 255))
    for r in range(MASK_ROWS):
        for f in range(FRAMES):
            cell = Image.new("RGBA", (HEAD_W, ch), (0, 0, 0, 0))
            cell.alpha_composite(heads.crop((f * HEAD_W, 0, f * HEAD_W + HEAD_W, HEAD_H)), (0, PADTOP))
            fcx, fcy = faces[f]
            _paste_faceanchored(cell, frames[r][f], int(round(fcx)), PADTOP + int(round(fcy)))
            grid.alpha_composite(cell, (f * HEAD_W, r * ch))
    out = SCRATCH / "vv2_mask_preview.png"
    grid.resize((HEAD_W * FRAMES * 7, ch * MASK_ROWS * 7), Image.NEAREST).convert("RGB").save(out)
    print("preview ->", out)


def main(argv) -> None:
    if "--preview" in argv:
        preview()
    elif "--atlas" in argv:
        i = argv.index("--atlas")
        build_mask_atlas(Path(argv[i + 1]))
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
