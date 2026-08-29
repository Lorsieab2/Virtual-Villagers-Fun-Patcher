"""Generate the VV5 Details-portrait bighead mask atlas (bigheads_masks.png).

The bighead mask uses the NORMAL heathen mask atlas (vv5_heathenheads.png, an
8-column x 5-row sheet), taking ONLY the three Details facings the owner specified.
The owner counts frames 1-based (leftmost column = frame 1), so owner frames
5/6/7 are 0-based columns 4/5/6:
    frame 5 (col 4) = right-facing, frame 6 (col 5) = front-facing,
    frame 7 (col 6) = left-facing
and emitting them (in that order) as a 3-column x 5-row atlas (col0=right,
col1=front, col2=left) -- the layout the native bighead draw expects
(BIGHEAD_ATLAS_COLS=3, BH_FACE_TABLE=[0,1,2]).

Positioning: the native bighead draw's tuning (BH_COLDX_TABLE, BH_LIFT, BH_ROWDY,
child offset) was dialed in against the ORIGINAL atlas's 54x81 cell placement, and
the owner confirmed that positioning is correct. So each extracted frame is ALIGNED
to the original atlas's per-cell placement -- same chin line, same horizontal
centre, same content height per colour/facing -- so the proven tuning still lands.
The original placement is reconstructed from bigheads_masks_source.png (the same
packer that produced the shipped-correct atlas). Only the ART changes (to the
owner's frames 5/6/7); the geometry is preserved.

Output is a 3x5 even-grid RGBA PNG registered as sprite id 0x155 by
build_vv5_task9_native_actions.py and shipped to the game's Images/ folder.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
# Placement reference: the original 3-col source, packed exactly as the
# shipped-correct atlas was, gives the per-cell target chin/centre/height.
REF_SRC = ROOT / "assets" / "vv5_bighead_masks" / "bigheads_masks_source.png"
# Art source: the normal heathen mask atlas; we take frames 5/6/7.
ART_SRC = ROOT / "assets" / "vv5_bighead_masks" / "vv5_heathenheads.png"
OUT = ROOT / "assets" / "vv5_bighead_masks" / "bigheads_masks.png"
COLS, ROWS = 3, 5            # output: 3 Details facings x 5 mask colours
ART_COLS = 8                 # vv5_heathenheads.png is 8 directional frames
SRC_FRAMES = [4, 5, 6]       # owner frames 5/6/7 (1-based) = cols 4/5/6: right / front / left
TARGET_CELL_W, TARGET_CELL_H = 54, 81
MARGIN = 5
ALPHA = 16


def _reference_atlas() -> Image.Image:
    """Rebuild the original-placement 3x5 atlas from the 3-col source (the packer
    that produced the shipped-correct geometry), at 54x81 cells."""
    src = Image.open(REF_SRC).convert("RGBA")
    W, H = src.size
    icw, ich = W // COLS, H // ROWS
    a = np.array(src)[:, :, 3]
    rowbb = []
    maxrh = 0
    for r in range(ROWS):
        y0, y1 = 10 ** 9, -1
        for c in range(COLS):
            cell = a[r * ich:(r + 1) * ich, c * icw:(c + 1) * icw]
            ys, xs = np.where(cell > ALPHA)
            if len(ys):
                y0 = min(y0, int(ys.min()))
                y1 = max(y1, int(ys.max()) + 1)
        rowbb.append((y0, y1))
        maxrh = max(maxrh, y1 - y0)
    cell_h = maxrh + 2 * MARGIN
    out = Image.new("RGBA", (icw * COLS, cell_h * ROWS), (0, 0, 0, 0))
    for r in range(ROWS):
        y0, y1 = rowbb[r]
        rh = y1 - y0
        dy = r * cell_h + (cell_h - MARGIN - rh)
        for c in range(COLS):
            strip = src.crop((c * icw, r * ich + y0, (c + 1) * icw, r * ich + y1))
            out.paste(strip, (c * icw, dy), strip)
    return out.resize((TARGET_CELL_W * COLS, TARGET_CELL_H * ROWS), Image.LANCZOS)


def _autocrop(im: Image.Image) -> Image.Image:
    b = np.array(im)[:, :, 3]
    ys, xs = np.nonzero(b > ALPHA)
    return im.crop((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1))


def build(out_path: Path = OUT) -> Image.Image:
    ref = _reference_atlas()          # correct-placement reference
    ra = np.array(ref)[:, :, 3]
    art = Image.open(ART_SRC).convert("RGBA")
    acw, ach = art.size[0] // ART_COLS, art.size[1] // ROWS
    ocw, och = TARGET_CELL_W, TARGET_CELL_H
    out = Image.new("RGBA", (ocw * COLS, och * ROWS), (0, 0, 0, 0))
    for r in range(ROWS):
        for i, sf in enumerate(SRC_FRAMES):
            # target placement from the reference cell (chin, h-centre, height)
            cell = ra[r * och:(r + 1) * och, i * ocw:(i + 1) * ocw]
            ys, xs = np.nonzero(cell > ALPHA)
            hcenter = (int(xs.min()) + int(xs.max())) / 2.0
            chin = int(ys.max())
            height = int(ys.max()) - int(ys.min()) + 1
            # extract + uniformly scale the owner's frame to the target height
            frame = _autocrop(art.crop((sf * acw, r * ach, (sf + 1) * acw, (r + 1) * ach)))
            s = height / frame.height
            nw, nh = max(1, round(frame.width * s)), max(1, round(height))
            scaled = frame.resize((nw, nh), Image.LANCZOS)
            x0 = int(round(hcenter - nw / 2.0))
            y0 = int(round(chin - nh))
            out.alpha_composite(scaled, (i * ocw + x0, r * och + y0))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.save(out_path)
    return out


if __name__ == "__main__":
    img = build()
    print(f"wrote {OUT} {img.size} (frames {SRC_FRAMES}=R/F/L from vv5_heathenheads.png, aligned to original placement)")
    if len(sys.argv) > 1:
        img.save(sys.argv[1])
        print(f"also wrote {sys.argv[1]}")
