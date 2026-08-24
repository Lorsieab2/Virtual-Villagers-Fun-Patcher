"""Build the VV3 dedicated Heathen-mask atlas (Images/heathen_masks.png).

VV2 separate-atlas method: a standalone mask atlas drawn ON TOP of the head via
the game's child/scaled draw thunk (see build_vv3_mask_stage2.py). This avoids
the append-rows corruption and, with taller cells + a draw-time lift, shows the
full towering masks (red horns, chief feathers) without clipping.

Source: the user's hand-aligned port canvases (assets/vv3_heathen_masks/
mask_<color>.png, 520x1286), where the VV3 head origin is at canvas (106, 1149)
-- verified by a 100% pixel match of the ginger reference head (male_heads row
22). Each mask is placed at x=0 (native alignment) with a vertical LIFT so the
draw's matching lift (lift = (headY*34)>>7) seats the face on the head and lets
the feathers rise above it. Each cell is clipped so a profile mask never bleeds
into its neighbour frame.

Atlas: 8 cols (facings) x 5 rows (masks), cell 40x128 -> 320x640.
Rows (mask byte value -> atlas row byte-1): 0 blue,1 orange,2 red,3 purple,4 chief.

CHIEF row -- per-frame anchoring (VV2's method, added 2026-08-23):
The blue/orange/red/purple canvases lay their 8 facings out on a clean uniform
grid (each facing's face sits at the SAME baseline y ~1182), so one global origin
(CANVAS_DX,CANVAS_DY) drops all 8 into their cells correctly. The CHIEF canvas is
different: its 8 facings are STAGGERED vertically (facings 2/4/6 sit ~46px lower)
and drift horizontally, so a single origin only matches facing 0 and the rest fall
outside their cells (rendering BLANK). Fix: detect each chief face independently
(connected component), then re-anchor it so its face-band centre-x and chin-bottom
land exactly where the corresponding BLUE facing's do -- neutralising the stagger.
The chief art supplies 7 facings (0..6); facing 7 (a right profile) is missing, so
it is produced by horizontally mirroring facing 1. Feathers are ignored when
computing the horizontal anchor (they lean and would skew it); the chin-bottom is
used for the vertical anchor. Detection is numpy-only (no scipy) so the builder is
self-contained.
"""
from __future__ import annotations

from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image

CELL_W, CELL_H = 40, 128
COLS, ROWS = 8, 5
LIFT = 42
CANVAS_DX, CANVAS_DY = 106, 1149          # head-frame-0 origin in the port canvas
STRAIGHT = ["blue", "orange", "red", "purple"]   # rows 0..3: clean uniform grid
ORDER = ["blue", "orange", "red", "purple", "chief"]  # chief = row 4 (per-frame)
ALPHA_THR = 24                            # opaque cutoff for face detection
FACEBAND_FRAC = 0.40                      # lower 40% of a blob = face (ignore feathers)
CHIEF_MIRROR_SRC = 1                      # facing 7 missing -> mirror facing 1
CHIEF_DX = -1                             # live-tuned nudge (px): chief seats 1px left
CHIEF_DY = 0                              # live-tuned nudge (px): +down / -up

SRC = Path(__file__).resolve().parents[1] / "assets" / "vv3_heathen_masks"


def _label_faces(alpha: np.ndarray):
    """numpy-only 4-connected component labelling; returns face dicts sorted L->R."""
    visited = np.zeros_like(alpha, dtype=bool)
    h, w = alpha.shape
    faces = []
    for sy in range(h):
        for sx in range(w):
            if not alpha[sy, sx] or visited[sy, sx]:
                continue
            q = deque([(sy, sx)])
            visited[sy, sx] = True
            pts = []
            while q:
                y, x = q.popleft()
                pts.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and alpha[ny, nx] and not visited[ny, nx]:
                        visited[ny, nx] = True
                        q.append((ny, nx))
            if len(pts) < 30:             # ignore stray specks
                continue
            ys = np.array([p[0] for p in pts]); xs = np.array([p[1] for p in pts])
            faces.append(dict(ys=ys, xs=xs, x0=xs.min(), x1=xs.max(),
                              y0=ys.min(), y1=ys.max()))
    faces.sort(key=lambda f: (f["x0"] + f["x1"]) / 2.0)
    return faces


def _faceband_cx(face) -> float:
    """x-centroid of the lower FACEBAND_FRAC of the blob (chin/face, not feathers)."""
    ys, xs = face["ys"], face["xs"]
    cut = face["y1"] - FACEBAND_FRAC * (face["y1"] - face["y0"])
    sel = ys >= cut
    return float(xs[sel].mean()) if sel.any() else float(xs.mean())


def _blue_targets():
    """Per-facing (face-band cx, chin-bottom y) from the aligned blue canvas."""
    arr = np.array(Image.open(SRC / "mask_blue.png").convert("RGBA"))
    faces = _label_faces(arr[:, :, 3] > ALPHA_THR)
    return [dict(cx=_faceband_cx(f), bottom=f["y1"]) for f in faces]


def _chief_cell(fidx: int, face, carr: np.ndarray, targets) -> Image.Image:
    """Place one detected chief face into cell fidx, anchored to blue facing fidx."""
    cell = Image.new("RGBA", (CELL_W, CELL_H), (0, 0, 0, 0))
    sub = carr[face["y0"]:face["y1"] + 1, face["x0"]:face["x1"] + 1].copy()
    m = np.zeros(sub.shape[:2], dtype=bool)
    m[face["ys"] - face["y0"], face["xs"] - face["x0"]] = True
    sub[~m] = 0
    fimg = Image.fromarray(sub, "RGBA")
    scx = _faceband_cx(face) - face["x0"]     # source anchor within the crop
    sby = face["y1"] - face["y0"]
    t = targets[fidx]                          # target anchor within cell fidx
    ax = t["cx"] - CANVAS_DX - fidx * CELL_W + CHIEF_DX
    ay = t["bottom"] - CANVAS_DY + LIFT + CHIEF_DY
    cell.alpha_composite(fimg, (int(round(ax - scx)), int(round(ay - sby))))
    return cell


def _build_chief_row(atlas: Image.Image, ri: int):
    targets = _blue_targets()
    carr = np.array(Image.open(SRC / "mask_chief.png").convert("RGBA"))
    faces = _label_faces(carr[:, :, 3] > ALPHA_THR)
    # map each detected chief face to its nearest blue facing by face-band x
    bx = [t["cx"] for t in targets]
    by_facing, used = {}, set()
    for f in faces:
        cx = _faceband_cx(f)
        k = min((j for j in range(COLS) if j not in used),
                key=lambda j: abs(bx[j] - cx))
        by_facing[k] = f
        used.add(k)
    for f in range(COLS):
        if f in by_facing:
            cell = _chief_cell(f, by_facing[f], carr, targets)
        else:                                  # missing facing -> mirror a present one
            cell = _chief_cell(f, by_facing[CHIEF_MIRROR_SRC], carr,
                               targets).transpose(Image.FLIP_LEFT_RIGHT)
        atlas.paste(cell, (f * CELL_W, ri * CELL_H))
    return sorted(by_facing.keys())


def build() -> Path:
    atlas = Image.new("RGBA", (CELL_W * COLS, CELL_H * ROWS), (0, 0, 0, 0))
    for ri, name in enumerate(ORDER):
        if name == "chief":
            present = _build_chief_row(atlas, ri)
            print(f"  chief row: per-frame anchored, facings present {present}, "
                  f"facing {[f for f in range(COLS) if f not in present]} mirrored")
            continue
        port = Image.open(SRC / f"mask_{name}.png").convert("RGBA")
        # translate canvas(CANVAS_DX,CANVAS_DY) -> cell top (0,0), then + LIFT in y
        shifted = Image.new("RGBA", (CELL_W * COLS, CELL_H), (0, 0, 0, 0))
        shifted.alpha_composite(port, (-CANVAS_DX, -CANVAS_DY + LIFT))
        for c in range(COLS):              # per-cell clip (no bleed into neighbours)
            cell = shifted.crop((c * CELL_W, 0, c * CELL_W + CELL_W, CELL_H))
            atlas.paste(cell, (c * CELL_W, ri * CELL_H))
    out = SRC / "heathen_masks.png"
    atlas.save(out)
    print(f"heathen_masks.png: {atlas.size} (cell {CELL_W}x{CELL_H}, "
          f"{COLS} cols x {ROWS} rows; chief row per-frame anchored)")
    return out


if __name__ == "__main__":
    build()
