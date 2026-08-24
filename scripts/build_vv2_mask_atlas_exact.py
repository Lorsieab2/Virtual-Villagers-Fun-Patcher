"""Build the VV2 mask atlas at the user's EXACT placement, measured from their files:
port mask (277x110) - bare head (277x110) = per-frame offset; apply to the game head.
No face-follow, no re-anchoring — 1:1 reproduction of the user's alignment."""
from PIL import Image
import numpy as np
from scipy import ndimage

import os
from pathlib import Path

# No author-only absolute paths.  Source mask art lives in the repo; the stock
# game's Images folder (has male_heads.png + receives heathen_masks.png) comes
# from $VV2_IMAGES.  Scratch/verify output goes to $VV2_SCRATCH (repo .scratch).
_ROOT = Path(__file__).resolve().parents[1]
FOLDER = os.environ.get("VV2_MASK_SRC", str(_ROOT / "research" / "vv2-mask-source"))
_IMAGES = os.environ.get("VV2_IMAGES", "")
if not _IMAGES:
    raise SystemExit(
        "set VV2_IMAGES to the stock game's Images folder "
        "(the one containing male_heads.png)"
    )
GAME = str(Path(_IMAGES) / "male_heads.png")
OUT_ATLAS = str(Path(_IMAGES) / "heathen_masks.png")
SCR = os.environ.get("VV2_SCRATCH", str(_ROOT / ".scratch"))
os.makedirs(SCR, exist_ok=True)

HW, HH = 40, 65
CELL_W, CELL_H = 40, 88          # atlas cell
ADULT_LIFT = 42                  # exe draws mask atlas at (x, y-42) over the head cell
FRAMES = 7
MASKS = ["blue", "orange", "red", "purple", "chief"]
# per-mask size scale (1.0 = exact user art).  Chief shrunk a few px so its tall feathers
# clip the play-area top edge less; scaled about the mask centre so the face stays aligned.
MASK_SCALE = {}  # all masks at original size
# Per-mask fine alignment (live-tuned in-game 2026-08-23). Down = +DY, right = +DX.
# Non-chief masks bake a touch high; blue is shortest (needs least drop), chief already right.
MASK_DX = {"blue": 4, "orange": 0, "red": 2, "purple": 2, "chief": -2}
MASK_DY = {"blue": 11, "orange": 20, "red": 20, "purple": 19, "chief": 0}
BAREHEAD_OTHER = "vv5 mask head alignment for other masks.png"
BAREHEAD_CHIEF = "vv5 mask head alignment for chief.png"


def _blobs(path):
    """Per-frame (x0,y0,w,h, cropped RGBA) for the 7 connected blobs, left-to-right."""
    im = np.asarray(Image.open(path).convert("RGBA"))
    lbl, n = ndimage.label(im[..., 3] > 30)
    sizes = np.bincount(lbl.ravel()); sizes[0] = 0
    ids = [i for i in range(1, n + 1) if sizes[i] > 40]
    ids.sort(key=lambda i: float(np.where(lbl == i)[1].mean()))
    out = []
    for i in ids:
        ys, xs = np.where(lbl == i)
        x0, y0, x1, y1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
        sub = im[y0:y1, x0:x1].copy()
        sub[lbl[y0:y1, x0:x1] != i] = 0
        out.append((x0, y0, x1 - x0, y1 - y0, Image.fromarray(sub, "RGBA")))
    return out


def _center(b):
    return (b[0] + b[2] / 2.0, b[1] + b[3] / 2.0)


def game_head_centers():
    g = np.asarray(Image.open(GAME).convert("RGBA"))
    out = []
    for k in range(FRAMES):
        cell = g[:HH, k * HW:(k + 1) * HW, 3] > 30
        ys, xs = np.where(cell)
        out.append(((xs.min() + xs.max() + 1) / 2.0, (ys.min() + ys.max() + 1) / 2.0))
    return out


def build():
    ghc = game_head_centers()
    bh_other = _blobs(f"{FOLDER}/{BAREHEAD_OTHER}")
    bh_chief = _blobs(f"{FOLDER}/{BAREHEAD_CHIEF}")
    atlas = Image.new("RGBA", (CELL_W * 8, CELL_H * len(MASKS)), (0, 0, 0, 0))
    verify = Image.new("RGBA", (HW * FRAMES, (HH + 30) * len(MASKS)), (95, 95, 100, 255))
    g_img = Image.open(GAME).convert("RGBA")
    for mi, nm in enumerate(MASKS):
        bh = bh_chief if nm == "chief" else bh_other
        pm = _blobs(f"{FOLDER}/vv5 mask port {nm}.png")
        # Per-frame horizontal offset (mask follows the head as it faces L/R), but
        # the VERTICAL anchor is EQUALIZED across all 7 frames so the mask never
        # bobs up/down between facing directions. Use the mean of the per-frame
        # head-center-y + offset-y so the tuned MASK_DY placement is preserved.
        offs = []
        for f in range(FRAMES):
            hc = _center(bh[f]); mc = _center(pm[f])          # canvas centers
            offs.append((mc[0] - hc[0], mc[1] - hc[1]))        # mask center vs head center
        vy_mean = sum(ghc[f][1] + offs[f][1] for f in range(FRAMES)) / float(FRAMES)
        ay_const = ADULT_LIFT + vy_mean + MASK_DY.get(nm, 0)   # constant screen-y, atlas
        vy_const = 30 + vy_mean + MASK_DY.get(nm, 0)           # constant screen-y, verify
        for f in range(FRAMES):
            off = offs[f]
            mimg = pm[f][4]
            s = MASK_SCALE.get(nm, 1.0)
            if s != 1.0:
                mimg = mimg.resize((max(1, round(mimg.width * s)), max(1, round(mimg.height * s))), Image.LANCZOS)
            mw, mh = mimg.size
            # atlas: place mask center at (ghc_x + off_x, ay_const) — Y equal for all frames
            ax = ghc[f][0] + off[0] + MASK_DX.get(nm, 0)
            ay = ay_const
            px = int(round(ax - mw / 2.0)); py = int(round(ay - mh / 2.0))
            # composite into THIS cell only, clipping any overflow so it never bleeds into the
            # neighbouring frame's cell (the "extra pixels to the side").
            sx0, sy0 = max(0, -px), max(0, -py)
            sx1, sy1 = min(mw, CELL_W - px), min(mh, CELL_H - py)
            if sx1 > sx0 and sy1 > sy0:
                sub = mimg.crop((sx0, sy0, sx1, sy1))
                atlas.alpha_composite(sub, (f * CELL_W + px + sx0, mi * CELL_H + py + sy0))
            # verify: game head + this mask at the same relative offset
            vy = mi * (HH + 30)
            cell = Image.new("RGBA", (HW, HH + 30), (0, 0, 0, 0))
            cell.alpha_composite(g_img.crop((f * HW, 0, f * HW + HW, HH)), (0, 30))
            # mask center at head-center + off (screen), head drawn at +30
            vmx = int(round(ghc[f][0] + off[0] + MASK_DX.get(nm, 0) - mw / 2.0))
            vmy = int(round(vy_const - mh / 2.0))
            cell.alpha_composite(mimg, (vmx, vmy))
            verify.alpha_composite(cell, (f * HW, vy))
    atlas.save(OUT_ATLAS)
    Image.open(GAME)  # noop
    verify.resize((verify.width * 6, verify.height * 6), Image.NEAREST).convert("RGB").save(f"{SCR}/exact_verify.png")
    print("atlas ->", OUT_ATLAS, atlas.size)
    print("verify ->", f"{SCR}/exact_verify.png")


if __name__ == "__main__":
    build()
