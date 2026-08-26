"""VV2 skin-tone overlay — bake the pre-tinted head (later body) atlas variants.

Detection was abandoned (blond hair + tan clothing are pixel-identical to skin);
instead the user HAND-MASKED the skin on the FRONT frame of each head atlas in
GIMP, and we extrapolate that to all 7 facings via kNN, then bake 10 tinted
tone variants per atlas. This script is the offline asset step: apply the saved
skin MASK + the piecewise recolor to produce <stem>_skinNN.png for NN=01..10.

Recolor (per skin pixel, per channel; base = measured skin mean 199,153,106):
  target_c <= base_c : px * (target_c/base_c)                    (multiply = darken)
  target_c >  base_c : 255-(255-px)*((255-target_c)/(255-base_c))(screen  = lighten)
=> full near-white .. near-black range with the game's own skin as the MIDDLE (T5).

Inputs (repo, reproducible):
  research/vv2-skin-source/male_heads_skinmask.png    (grayscale, opaque = tint)
  research/vv2-skin-source/female_heads_skinmask.png
The mask itself is regenerated from the user's front-frame hand-edits
(*_frontmask.png) by scripts/build_vv2_skin_masks.py (kNN extrapolation).

Stock head atlases (male_heads.png/female_heads.png) come from $VV2_IMAGES.
Outputs go to $VV2_SKIN_OUT (default: repo .scratch/skin_atlases).
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
from PIL import Image

_ROOT = Path(__file__).resolve().parents[1]
SRC = _ROOT / "research" / "vv2-skin-source"
_IMAGES = os.environ.get("VV2_IMAGES", "")
OUT = Path(os.environ.get("VV2_SKIN_OUT", str(_ROOT / ".scratch" / "skin_atlases")))

BASE = np.array([199.0, 153.0, 106.0])  # measured VV2 skin mean
# 10 tone TARGETS (resulting skin RGB); T5 == BASE (middle). Named "Skin Tone 1..10".
TARGETS = [
    (252, 240, 230), (238, 216, 196), (224, 192, 162), (210, 170, 132), (199, 153, 106),
    (172, 130, 94),  (146, 106, 74),  (118, 84, 58),   (90, 62, 42),    (58, 38, 26),
]


def recolor(atlas: np.ndarray, mask: np.ndarray, target) -> Image.Image:
    a = atlas.astype(float)
    t = np.array(target, float)
    for c in range(3):
        px = a[:, :, c][mask]
        px = np.where(
            t[c] <= BASE[c],
            px * (t[c] / BASE[c]),
            255 - (255 - px) * ((255 - t[c]) / max(255 - BASE[c], 1)),
        )
        a[:, :, c][mask] = np.clip(px, 0, 255)
    return Image.fromarray(a.astype("uint8"), "RGBA")


def bake(stem: str) -> None:
    if not _IMAGES:
        raise SystemExit("set VV2_IMAGES to the stock game's Images folder")
    atlas = np.array(Image.open(Path(_IMAGES) / f"{stem}.png").convert("RGBA"))
    mask = np.array(Image.open(SRC / f"{stem}_skinmask.png").convert("L")) > 128
    if atlas.shape[:2] != mask.shape:
        raise SystemExit(f"{stem}: atlas {atlas.shape[:2]} vs mask {mask.shape} mismatch")
    OUT.mkdir(parents=True, exist_ok=True)
    for i, target in enumerate(TARGETS, 1):
        recolor(atlas, mask, target).save(OUT / f"{stem}_skin{i:02d}.png")
    print(f"{stem}: 10 tone variants -> {OUT}")


if __name__ == "__main__":
    bake("male_heads")
    bake("female_heads")
