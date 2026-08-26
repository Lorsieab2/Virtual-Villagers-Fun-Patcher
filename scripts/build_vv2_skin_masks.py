"""VV2 skin-tone overlay — build the per-frame skin MASK from the user's
front-frame hand-edit, via kNN extrapolation to all 7 facings.

The user erases HAIR from the FRONT frame (col 5) of male_heads.png /
female_heads.png in GIMP. That labels, per head, skin = kept(opaque),
hair = original-opaque minus theirs(erased). We learn each head's skin-vs-hair
colours from that front frame and classify the OTHER 6 facings with kNN on
[R, G, B, normalized-y * POSW] -- the vertical-position feature separates
blond/brown hair (which sits up top) from face skin even when their colours
match. Then, per the user's directive "just overlay the entire face", we
binary_fill_holes the face so eyes/lips tint WITH the skin (no feature
detection). Bald / no-hair-erased heads => whole head is skin.

Inputs (repo): research/vv2-skin-source/<stem>_frontmask.png  (full atlas dims,
  only col 5 opaque = the kept face).  <stem> in {male_heads, female_heads}.
Stock atlas from $VV2_IMAGES. Output: research/vv2-skin-source/<stem>_skinmask.png
(grayscale; opaque = tint region), consumed by build_vv2_skin_atlases.py.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

_ROOT = Path(__file__).resolve().parents[1]
SRC = _ROOT / "research" / "vv2-skin-source"
_IMAGES = os.environ.get("VV2_IMAGES", "")
CW, CH = 40, 65
FRONT = 5
POSW = 95.0   # weight of the normalized-y feature (px-scale) in the kNN metric
K = 7


def _bbox_y(al: np.ndarray):
    ys, _ = np.where(al)
    return (int(ys.min()), int(ys.max())) if len(ys) else (0, CH - 1)


def build(stem: str) -> None:
    if not _IMAGES:
        raise SystemExit("set VV2_IMAGES to the stock game's Images folder")
    orig = np.array(Image.open(Path(_IMAGES) / f"{stem}.png").convert("RGBA"))
    theirs = np.array(Image.open(SRC / f"{stem}_frontmask.png").convert("RGBA"))
    if orig.shape[:2] != theirs.shape[:2]:
        raise SystemExit(f"{stem}: atlas {orig.shape[:2]} vs frontmask {theirs.shape[:2]}")
    nrow = orig.shape[0] // CH
    skin = np.zeros(orig.shape[:2], bool)

    def cell(a, r, c):
        return a[r * CH:r * CH + CH, c * CW:c * CW + CW]

    for r in range(nrow):
        oc, tc = cell(orig, r, FRONT), cell(theirs, r, FRONT)
        oal, tal = oc[:, :, 3] > 40, tc[:, :, 3] > 40
        sp, hp = oal & tal, oal & ~tal
        y0, y1 = _bbox_y(oal)
        hh = max(y1 - y0, 1)

        def feats(m, ci):
            ys, xs = np.where(m)
            return np.hstack([ci[ys, xs, :3].astype(float), ((ys - y0) / hh * POSW)[:, None]])

        Fs, Fh = feats(sp, oc), feats(hp, oc)
        for c in range(7):
            cc = cell(orig, r, c)
            al = cc[:, :, 3] > 40
            if not al.any():
                continue
            if len(Fs) < 3:                       # bald / nothing erased -> whole head
                out = al.copy()
            else:
                train = np.vstack([Fs, Fh])
                lab = np.array([1] * len(Fs) + [0] * len(Fh))
                yy, xx = np.where(al)
                by0, by1 = _bbox_y(al)
                bh = max(by1 - by0, 1)
                q = np.hstack([cc[yy, xx, :3].astype(float), ((yy - by0) / bh * POSW)[:, None]])
                d = np.sqrt(((q[:, None, :] - train[None, :, :]) ** 2).sum(2))
                idx = np.argpartition(d, K, axis=1)[:, :K]
                vote = lab[idx].mean(1) >= 0.5
                hair = np.zeros((CH, CW), bool)
                hair[yy, xx] = ~vote
                hair = ndimage.binary_opening(hair, iterations=1)   # drop stray specks
                out = ndimage.binary_fill_holes(al & ~hair) & al    # whole-face overlay
            skin[r * CH:r * CH + CH, c * CW:c * CW + CW] = out

    SRC.mkdir(parents=True, exist_ok=True)
    Image.fromarray((skin * 255).astype("uint8")).save(SRC / f"{stem}_skinmask.png")
    print(f"{stem}: skin mask -> {SRC / (stem + '_skinmask.png')}")


if __name__ == "__main__":
    build("male_heads")
    build("female_heads")
