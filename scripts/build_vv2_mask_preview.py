"""Regenerate the VV2 Change-Appearance MASK preview strip (mask_preview.bmp).

The chooser dialog (native/vv2_origins_icons) shows a Body / Head / Mask column;
the DLL owner-draws each as a 40x65 cell stretched into the preview box.  The
Head column uses the stock FRONT-facing head frame (male_heads.png column 5); the
Mask column must match that pose, so this builder composites the FRONT mask frame
(heathen_masks.png column 6) onto the SAME front head — otherwise the mask preview
shows a side-facing "random" head that doesn't match the Head selector.

6 cells: none, Blue, Orange, Red, Purple, Chief.

Requires Pillow + the stock game's Images folder.  Example:
    python scripts/build_vv2_mask_preview.py \
        --images "C:/Games/Virtual Villagers - The Lost Children/Images"
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "native" / "vv2_origins_icons" / "appearance" / "mask_preview.bmp"

BG = (236, 236, 236)          # dialog face background (matches head/body strips)
CELL_W, CELL_H = 40, 65       # DLL preview cell (VV2_APPEARANCE_CELL_W/H)

# Head atlas: 7 cols x 30 rows of 40x65.  Column 5 = the front pose the Head
# selector uses (build_vv2_appearance_sheets.HEAD_FRAME).  Row 3 = a plain,
# neutral short-hair head so the mask reads clearly.
HEAD_CW, HEAD_CH = 40, 65
HEAD_FRAME = 5
HEAD_ROW = 3
HEAD_FACE_CY = 24             # head face line within its 65-tall cell

# Mask atlas: 8 cols x 5 rows of 40x88, face line baked at cell-y 56.  Column 6 =
# the symmetric FRONT facing (see build_vv2_mask_atlas / heathen_masks.png).
MASK_CW, MASK_CH = 40, 88
MASK_FRONT_COL = 6
MASK_ROWS = 5                 # Blue, Orange, Red, Purple, Chief

HEAD_TOP = 22                 # y where the head cell is placed in the 40x65 preview cell


def _front_head(images: Path) -> Image.Image:
    atlas = Image.open(images / "male_heads.png").convert("RGBA")
    return atlas.crop((HEAD_FRAME * HEAD_CW, HEAD_ROW * HEAD_CH,
                       HEAD_FRAME * HEAD_CW + HEAD_CW, HEAD_ROW * HEAD_CH + HEAD_CH))


def _front_mask(masks: Image.Image, row: int) -> Image.Image:
    return masks.crop((MASK_FRONT_COL * MASK_CW, row * MASK_CH,
                       MASK_FRONT_COL * MASK_CW + MASK_CW, row * MASK_CH + MASK_CH))


def _alpha_ymid(im: Image.Image) -> float:
    """Vertical midpoint of an image's opaque region."""
    a = np.array(im)[:, :, 3]
    ys = np.where(a.max(1) > 16)[0]
    return (ys.min() + ys.max()) / 2.0 if len(ys) else im.size[1] / 2.0


def _cell(head: Image.Image, head_ymid: float, mask: Image.Image | None) -> Image.Image:
    """Head placed at a FIXED y (uniform head size across cells); the mask is then
    slid vertically so its opaque midpoint lands on the head's, i.e. the mask face
    sits over the head face with the feathers rising above."""
    out = Image.new("RGBA", (CELL_W, CELL_H), BG + (255,))
    out.alpha_composite(head, (0, HEAD_TOP))
    if mask is not None:
        m = int(round(HEAD_TOP + head_ymid - _alpha_ymid(mask)))
        out.alpha_composite(mask, (0, m))
    return out.convert("RGB")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--images", type=Path, required=True,
                    help="path to the stock game's Images folder")
    args = ap.parse_args()

    head = _front_head(args.images)
    head_ymid = _alpha_ymid(head)
    masks = Image.open(args.images / "heathen_masks.png").convert("RGBA")

    strip = Image.new("RGB", (CELL_W * (MASK_ROWS + 1), CELL_H), BG)
    strip.paste(_cell(head, head_ymid, None), (0, 0))            # cell 0: no mask
    for r in range(MASK_ROWS):                                    # cells 1..5
        strip.paste(_cell(head, head_ymid, _front_mask(masks, r)), ((r + 1) * CELL_W, 0))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    strip.save(OUT)
    print(f"wrote {OUT}  ({strip.size[0]}x{strip.size[1]}, {MASK_ROWS + 1} cells, "
          f"front head col {HEAD_FRAME} row {HEAD_ROW} + front mask col {MASK_FRONT_COL})")


if __name__ == "__main__":
    main()
