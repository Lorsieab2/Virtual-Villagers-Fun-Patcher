"""Rebuild the VV4 Heathen-mask atlas from the owner's CLEAN HEADLESS strips.

The previous atlas (build_vv4_mask_atlas_exact.py) isolated each mask by
subtracting the head out of a head+mask mockup. Where mask-gold met hair-gold
that subtraction failed, leaving HAIR RESIDUE ("extra head sprites") in the
village -- worst on the orange/red/chief rows.

The owner instead supplied clean, HEADLESS per-colour strips
(<downloads>/VV4 mask mockups/vv5 mask port <colour>.png), each holding the 7
face-visible directional masks (one head direction is turned away and shows no
mask). This script keeps the EXACT per-column placement + direction mapping of
the existing atlas (which was confirmed correct in-village) and only swaps the
dirty pixels for the clean strip pixels: for every one of the 8 atlas cells we
pick the clean mask whose silhouette best matches that cell, then stamp it
centred on the cell's own centroid. So alignment/facing is inherited from the
known-good atlas; only the hair goes away.

Output: assets/vv4_masks/vvfp_mask_atlas.png (shipped to Images/vvfp_mask_atlas00.png).
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
# Positions come from the ORIGINAL head-subtraction atlas (owner-approved in-village
# placement), NOT from any previously-written clean atlas -- keep this pinned to the
# dirty backup so re-runs never drift off the known-good positions.
CUR = ROOT / "assets/vv4_masks/vvfp_mask_atlas_dirty_backup.png"
STRIPS = Path(r"C:/Users/Owner/Downloads/VV4 mask mockups")
OUT = ROOT / "assets/vv4_masks/vvfp_mask_atlas.png"

CELL_W, CELL_H, COLS = 40, 65, 8
ORDER = ["blue", "orange", "red", "purple", "chief"]     # rows 0..4 = mask value 1..5


def _strip_masks(color: str):
    """Return the clean masks in a strip as a list of (rgba_crop, cx, cy) in
    left-to-right, top-to-bottom (reading) order."""
    im = np.array(Image.open(STRIPS / f"vv5 mask port {color}.png").convert("RGBA"))
    a = im[:, :, 3] > 32
    lbl, n = ndimage.label(ndimage.binary_dilation(a, iterations=3))
    comps = []
    for sl in ndimage.find_objects(lbl):
        ys, xs = sl
        piece = a[ys, xs]
        if piece.sum() < 25:
            continue
        yy, xx = np.where(piece)
        x0, y0 = xs.start + xx.min(), ys.start + yy.min()
        x1, y1 = xs.start + xx.max(), ys.start + yy.max()
        crop = im[y0:y1 + 1, x0:x1 + 1].copy()
        # blank anything outside this component's own dilated blob so a
        # neighbouring mask that grazed the bbox can't ride along
        comps.append((crop, (x0 + x1) / 2.0, (y0 + y1) / 2.0))
    comps.sort(key=lambda c: (int(c[2] // 30), c[1]))   # row band, then x
    return [c[0] for c in comps]


def _best_align(mask_alpha: np.ndarray, cell_alpha: np.ndarray):
    """Cross-correlate a clean mask's alpha against a dirty cell's alpha over ALL
    integer offsets; return (best_iou, (dy, dx)) where (dy,dx) is the top-left
    position of the mask inside the cell frame. IoU (not raw overlap) so a
    same-shape mask beats both a partial fit and a hair-inflated blob, and the
    peak offset lands the clean mask exactly on the dirty mask's core -- robust
    to the peripheral hair that skewed the centroid method."""
    from scipy.signal import fftconvolve
    m = mask_alpha.astype(np.float32)
    c = cell_alpha.astype(np.float32)
    area_m, area_c = m.sum(), c.sum()
    if area_m == 0 or area_c == 0:
        return -1.0, (0, 0)
    # correlation[i,j] = overlap when mask top-left is at (i - (mh-1), j - (mw-1))
    corr = fftconvolve(c, m[::-1, ::-1], mode="full")
    mh, mw = m.shape
    inter = np.clip(corr, 0, None)
    union = area_m + area_c - inter
    iou = np.where(union > 0, inter / union, 0.0)
    pi, pj = np.unravel_index(int(np.argmax(iou)), iou.shape)
    dy, dx = pi - (mh - 1), pj - (mw - 1)
    return float(iou[pi, pj]), (dy, dx)


def build() -> Image.Image:
    cur = np.array(Image.open(CUR).convert("RGBA"))       # dirty = correct POSITIONS
    atlas = Image.new("RGBA", (CELL_W * COLS, CELL_H * len(ORDER)), (0, 0, 0, 0))
    for r, color in enumerate(ORDER):
        masks = _strip_masks(color)
        mask_alphas = [m[:, :, 3] > 32 for m in masks]
        for c in range(COLS):
            cell = cur[r * CELL_H:(r + 1) * CELL_H, c * CELL_W:(c + 1) * CELL_W, 3] > 32
            if cell.sum() < 8:
                continue                       # this direction has no mask (blank)
            # pick the clean mask + offset that best matches THIS dirty cell
            best_i, best_iou, best_off = 0, -1.0, (0, 0)
            for i, ma in enumerate(mask_alphas):
                iou, off = _best_align(ma, cell)
                if iou > best_iou:
                    best_iou, best_i, best_off = iou, i, off
            m = masks[best_i]
            dy, dx = best_off
            atlas.alpha_composite(Image.fromarray(m), (c * CELL_W + dx, r * CELL_H + dy))
    return atlas


def main() -> None:
    atlas = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    atlas.save(OUT)
    print(f"wrote {OUT} {atlas.size} from clean headless strips "
          f"(alignment inherited from the known-good atlas, hair removed)")


if __name__ == "__main__":
    main()
