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
    for i, sl in enumerate(ndimage.find_objects(lbl)):
        if sl is None:
            continue
        label = i + 1
        # THIS component's real pixels only: dilation unified a mask's feather bits
        # into one label, but a neighbour mask can still fall inside this bbox --
        # so keep only (this label AND opaque), which drops the grazing neighbour
        # AND the dilation halo. Without this the crop carried stray specks that
        # showed as loose pixels beside masks in-village.
        own = (lbl == label) & a
        if own.sum() < 25:
            continue
        ys, xs = np.where(own)
        x0, y0, x1, y1 = xs.min(), ys.min(), xs.max(), ys.max()
        crop = im[y0:y1 + 1, x0:x1 + 1].copy()
        keep = own[y0:y1 + 1, x0:x1 + 1]
        crop[~keep] = (0, 0, 0, 0)
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
        cols = [c for c in range(COLS)
                if (cur[r * CELL_H:(r + 1) * CELL_H, c * CELL_W:(c + 1) * CELL_W, 3] > 32).sum() >= 8]
        cells = {c: cur[r * CELL_H:(r + 1) * CELL_H, c * CELL_W:(c + 1) * CELL_W, 3] > 32
                 for c in cols}
        cs = sorted(cols)
        n = len(masks)
        assign: dict[int, tuple[np.ndarray, tuple[int, int]]] = {}
        # Chief's source frames sweep left->front but its front starts at p3 (vs the
        # head's front at col 5) and it has NO right-facing source, so an explicit
        # per-column (source_index, mirror) map -- owner-referenced -- centres the
        # front on col 5 and builds the right directions (6,7) from mirrored lefts.
        CHIEF_MAP = [(0, 0), (1, 0), (2, 0), (2, 0), (3, 0), (4, 0), (2, 1), (1, 1)]
        if color == "chief" and set(cs) <= set(range(8)):
            for c in cs:
                si, mir = CHIEF_MAP[c]
                si = min(si, n - 1)
                src = masks[si][:, ::-1] if mir else masks[si]
                assign[c] = (src, _best_align(src[:, :, 3] > 32, cells[c])[1])
        elif color == "chief":
            # Chief ONLY: its port frames aren't distributed 1:1 with the 8 head
            # columns (fronts land at p3/p4, not p4-6 like the others), so
            # index-for-index mapping mis-faces it. A DP that assigns each column
            # its best-IoU port under a NON-DECREASING port-index constraint keeps
            # the facing sweep ordered and self-corrects the distribution. (The
            # other colours ARE 1:1 and use the proven direct mapping below --
            # matching the sparse dirty columns with the DP regressed them.)
            iou = {c: [_best_align(mask_alphas[i], cells[c])[0] for i in range(n)] for c in cs}
            off = {c: [_best_align(mask_alphas[i], cells[c])[1] for i in range(n)] for c in cs}
            NEG = -1e9
            dp = [[NEG] * n for _ in cs]
            par = [[-1] * n for _ in cs]
            for i in range(n):
                dp[0][i] = iou[cs[0]][i]
            for k in range(1, len(cs)):
                run, run_j = NEG, -1
                for i in range(n):             # running max of dp[k-1][j], j<=i
                    if dp[k - 1][i] > run:
                        run, run_j = dp[k - 1][i], i
                    dp[k][i] = iou[cs[k]][i] + run
                    par[k][i] = run_j
            i = int(np.argmax(dp[-1]))
            for k in range(len(cs) - 1, -1, -1):
                assign[cs[k]] = (masks[i], off[cs[k]][i])
                if k > 0:
                    i = par[k][i]
        else:
            # DIRECT ordered mapping: port frame p[c] IS the mask for column c
            # (strips sweep the head's facings, verified p0..p6 == dirty d0..d6).
            for c in cs:
                if c < n:
                    assign[c] = (masks[c], _best_align(mask_alphas[c], cells[c])[1])
        # Last column = the head's turned-AWAY 8th direction; with left/front-only
        # ports its best match is a horizontal MIRROR (a reused front points the
        # wrong way -- the "wrong frame for the face frame" report). Chief already
        # sets col 7 via CHIEF_MAP, so don't re-pick it here.
        last = cs[-1]
        if color != "chief":
            best = None
            for src in masks:
                for cand in (src, src[:, ::-1]):
                    v, o = _best_align(cand[:, :, 3] > 32, cells[last])
                    if best is None or v > best[0]:
                        best = (v, cand, o)
            assign[last] = (best[1], best[2])
        for c, (m, off_) in assign.items():
            dy, dx = off_
            # Chief's right-facing frames (cols 6-7) read 3px too far left on the
            # head -- nudge them right (owner-tuned). Clamp below keeps it in-cell.
            if color == "chief" and c in (6, 7):
                dx += 3
            mh, mw = m.shape[:2]
            # CLAMP each mask fully inside its own 40x65 cell, then composite through
            # a cell-sized tile so it can NEVER bleed into a neighbour. A mask pushed
            # past the cell edge shows twice: cut off in its own cell AND bleeding
            # into the next (the "pixel bleed + chief cutoff" report). Masks fit the
            # cell; if one is larger, centre it for a minimal symmetric clip.
            dx = max(0, min(dx, CELL_W - mw)) if mw <= CELL_W else (CELL_W - mw) // 2
            dy = max(0, min(dy, CELL_H - mh)) if mh <= CELL_H else (CELL_H - mh) // 2
            tile = Image.new("RGBA", (CELL_W, CELL_H), (0, 0, 0, 0))
            tile.alpha_composite(Image.fromarray(m), (dx, dy))
            atlas.alpha_composite(tile, (c * CELL_W, r * CELL_H))
    return atlas


def main() -> None:
    atlas = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    atlas.save(OUT)
    print(f"wrote {OUT} {atlas.size} from clean headless strips "
          f"(alignment inherited from the known-good atlas, hair removed)")


if __name__ == "__main__":
    main()
