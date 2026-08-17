"""VV3 Heathen-mask overlay — place the VV5 masks into the head atlases at
NATIVE size (no scaling), aligned to each head's face per facing.

The VV5 mask sheet (vv5_heathenheads.png) is a uniform 8x5 grid of 65x145 cells.
The actual mask content is only ~26x45px, which fits inside a VV3 40x65 head cell
(the head occupies the lower part, leaving room above for the mask's spikes).  So
we take each mask at its NATIVE pixel size (crisp, un-resized — matching the VV5
look) and drop it onto head-atlas rows 30..34, centered on the head's detected
face for that facing (the hair pulls the bbox center off, so we align to skin).

Usage:  python build_vv3_mask_atlas.py "<game Images dir>"
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

CELL_W, CELL_H = 40, 65
SRC_CELL_W, SRC_CELL_H = 65, 145   # VV5 uniform cell (520x725 / 8 / 5)
FRAMES = 8
MASK_ROWS = 5
FACE_SAMPLE_ROWS = [3, 5, 8, 12, 20]
FACE_Y_FRAC = 0.62                 # the face sits ~62% down the mask
MASK_LIFT = 0                      # native placement, no lift (user preferred this)
HEAD_ATLASES = ("male_heads.png", "male_heads_old.png",
                "female_heads.png", "female_heads_old.png")
SRC = Path(r"C:/Users/Owner/Downloads/vv5_heathenheads.png")


def _native_mask_frames() -> list[list[Image.Image]]:
    """[row][frame] -> the mask cropped to its native content (no scaling)."""
    sheet = Image.open(SRC).convert("RGBA")
    out = []
    for r in range(MASK_ROWS):
        frames = []
        for f in range(FRAMES):
            cell = sheet.crop((f * SRC_CELL_W, r * SRC_CELL_H,
                               f * SRC_CELL_W + SRC_CELL_W, r * SRC_CELL_H + SRC_CELL_H))
            frames.append(cell.crop(cell.getbbox()))   # tight, native size
        out.append(frames)
    return out


def _is_skin(px) -> bool:
    r, g, b, a = px
    return a > 128 and r > 150 and g > 110 and b > 70 and r > b + 25 and (r - g) < 90


def _face_center_per_frame(src: Image.Image) -> list[tuple[float, float]]:
    """FACE (skin) centroid per facing, averaged over several head rows — the mask
    aligns to skin, not the hair-inflated bbox."""
    out = []
    for f in range(FRAMES):
        xs, ys = [], []
        for row in FACE_SAMPLE_ROWS:
            px = src.crop((f * CELL_W, row * CELL_H, f * CELL_W + CELL_W, row * CELL_H + CELL_H)).load()
            for y in range(CELL_H):
                for x in range(CELL_W):
                    if _is_skin(px[x, y]):
                        xs.append(x); ys.append(y)
        out.append((sum(xs) / len(xs), sum(ys) / len(ys)) if xs else (20.0, 22.0))
    return out


def _place(mask: Image.Image, face_cx: float, face_cy: float) -> Image.Image:
    """Native mask centered on the face; padded compositing crops any overhang."""
    nw, nh = mask.size
    PAD = 64
    canvas = Image.new("RGBA", (CELL_W + 2 * PAD, CELL_H + 2 * PAD), (0, 0, 0, 0))
    x = PAD + int(round(face_cx - nw / 2))
    y = PAD + int(round(face_cy + MASK_LIFT - nh * FACE_Y_FRAC))
    canvas.alpha_composite(mask, (x, y))
    return canvas.crop((PAD, PAD, PAD + CELL_W, PAD + CELL_H))


def apply_to_atlas(atlas_path: Path, native_frames: list[list[Image.Image]]) -> None:
    bak = atlas_path.with_suffix(".mask-bak.png")
    if not bak.exists():
        bak.write_bytes(atlas_path.read_bytes())
    src = Image.open(bak).convert("RGBA")   # always rebuild from clean backup
    w = src.size[0]
    base_rows = src.size[1] // CELL_H
    faces = _face_center_per_frame(src)
    new_rows = 30 + MASK_ROWS
    out = Image.new("RGBA", (w, CELL_H * new_rows), (0, 0, 0, 0))
    out.paste(src.crop((0, 0, w, CELL_H * 30)), (0, 0))
    for r in range(MASK_ROWS):
        strip = Image.new("RGBA", (CELL_W * FRAMES, CELL_H), (0, 0, 0, 0))
        for f in range(FRAMES):
            fcx, fcy = faces[f]
            strip.paste(_place(native_frames[r][f], fcx, fcy), (f * CELL_W, 0))
        out.paste(strip, (0, CELL_H * (30 + r)))
    out.save(atlas_path)
    print(f"  {atlas_path.name}: {base_rows} -> {new_rows} rows (native, face-aligned)")


def main(images_dir: Path) -> None:
    native = _native_mask_frames()
    for name in HEAD_ATLASES:
        apply_to_atlas(images_dir / name, native)
    print("done; head atlases carry native-size mask rows 30..34")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
