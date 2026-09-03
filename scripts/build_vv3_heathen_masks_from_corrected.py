"""Reformat the user's corrected mask atlas (assets/vv3_heathen_masks/
heathen_masks_corrected_src.png, an 8x5 grid at 65x145/cell) into the DLL's
render grid heathen_masks.png (8x5 at 40x128/cell).

The DLL loader slices heathen_masks.png into 8 cols x 5 rows and the render is
calibrated for 40x128 cells with each mask BOTTOM-anchored at the face line
(y~=75) and horizontally placed per-frame to encode facing direction.  We map
the corrected art onto that same anchor grid: scale by a single factor S (so the
corrected masks match the current on-screen face size), then per cell place the
scaled content so its horizontal centre and its bottom match the CURRENT atlas's
per-cell centre/bottom.  This swaps in the correct art (incl. the proper chief
frames) while preserving the render calibration.
"""
from pathlib import Path
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "assets" / "vv3_heathen_masks" / "heathen_masks_corrected_src.png"
CUR = ROOT / "assets" / "vv3_heathen_masks" / "heathen_masks.png"
OUT = ROOT / "assets" / "vv3_heathen_masks" / "heathen_masks.png"

# CUR and OUT are deliberately the SAME file: the alignment this script preserves
# is read out of the atlas it then overwrites.  That makes the reference
# self-destroying -- run it a second time and it measures its own output, so the
# scale factor S collapses towards 1.0 and the art drifts.  Run it exactly ONCE
# against a pristine atlas; to re-run, first restore heathen_masks.png from
# heathen_masks.prev-backup.png (committed alongside this script for that reason).

COLS, ROWS = 8, 5
OCW, OCH = 40, 128           # output (render) cell


def content_bbox(cell_rgba: np.ndarray):
    al = cell_rgba[:, :, 3]
    ys = np.where(al.any(axis=1))[0]
    xs = np.where(al.any(axis=0))[0]
    if not len(ys):
        return None
    return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1   # x0,y0,x1,y1


def cells(img: Image.Image):
    a = np.array(img.convert("RGBA"))
    w, h = img.size
    cw, ch = w // COLS, h // ROWS
    for r in range(ROWS):
        for c in range(COLS):
            yield r, c, a[r * ch:(r + 1) * ch, c * cw:(c + 1) * cw]


def main():
    src = Image.open(SRC).convert("RGBA")
    cur = Image.open(CUR).convert("RGBA")
    # current per-cell centre-x + bottom-y (the anchor grid we map onto)
    cur_anchor = {}
    for r, c, cell in cells(cur):
        bb = content_bbox(cell)
        if bb:
            cur_anchor[(r, c)] = ((bb[0] + bb[2]) / 2.0, bb[3])   # cx, bottom
    # single scale S = median(current face width / user face width)
    ratios = []
    src_bb = {}
    for r, c, cell in cells(src):
        bb = content_bbox(cell)
        src_bb[(r, c)] = bb
        if bb and (r, c) in cur_anchor:
            cur_cell = np.array(cur)[r * OCH:(r + 1) * OCH, c * OCW:(c + 1) * OCW]
            cbb = content_bbox(cur_cell)
            if cbb:
                ratios.append((cbb[2] - cbb[0]) / (bb[2] - bb[0]))
    S = float(np.median(ratios))
    print(f"scale S = {S:.4f}  (from {len(ratios)} cells)")

    out = Image.new("RGBA", (OCW * COLS, OCH * ROWS), (0, 0, 0, 0))
    scw, sch = src.size[0] // COLS, src.size[1] // ROWS
    for r, c, _ in cells(src):
        bb = src_bb[(r, c)]
        if not bb or (r, c) not in cur_anchor:
            continue
        # crop the source content, scale by S
        cell_img = src.crop((c * scw + bb[0], r * sch + bb[1],
                             c * scw + bb[2], r * sch + bb[3]))
        nw = max(1, round(cell_img.width * S))
        nh = max(1, round(cell_img.height * S))
        cell_img = cell_img.resize((nw, nh), Image.LANCZOS)
        cx, by = cur_anchor[(r, c)]
        # paste so scaled-content centre-x = cx, bottom = by, within this out cell
        px = int(round(c * OCW + cx - nw / 2.0))
        py = int(round(r * OCH + by - nh))
        out.alpha_composite(cell_img, (px, py))
    out.save(OUT)
    print(f"wrote {OUT}  {out.size}")


if __name__ == "__main__":
    main()
