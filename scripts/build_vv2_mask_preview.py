"""Regenerate the VV2 Change-Appearance MASK preview strip (mask_preview.bmp).

The chooser dialogs (per-villager 213 and Change Appearance for All 214) show a
Mask column whose cells the DLL owner-draws as 40x65, stretched into the preview
box.  The mask picker shows the MASK ALONE (no head): compositing the mask onto a
fixed head made it look like a "random head" and, in dialog 213, a different head
than the Head selector.  Cell 0 = "None" (blank).  Cells 1-5 = Blue/Orange/Red/
Purple/Chief, using the true FRONT frame of heathen_masks.png (column 5, the most
left-right symmetric facing).

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

# Mask atlas: 8 cols x 5 rows of 65x145 (VV5-standard cell).  Column 5 = the true front facing (max
# left-right alpha symmetry across the row; verified over blue+chief).
MASK_CW, MASK_CH = 65, 145
MASK_FRONT_COL = 5
MASK_ROWS = 5                 # Blue, Orange, Red, Purple, Chief
PAD = 2                       # breathing room inside the cell


def _front_mask(masks: Image.Image, row: int) -> Image.Image:
    return masks.crop((MASK_FRONT_COL * MASK_CW, row * MASK_CH,
                       MASK_FRONT_COL * MASK_CW + MASK_CW, row * MASK_CH + MASK_CH))


def _autocrop(im: Image.Image) -> Image.Image:
    a = np.array(im)[:, :, 3]
    ys = np.where(a.max(1) > 16)[0]
    xs = np.where(a.max(0) > 16)[0]
    if not len(ys) or not len(xs):
        return im
    return im.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))


def _cell(mask: Image.Image | None) -> Image.Image:
    """The mask alone, trimmed and fit into the 40x65 cell (no head).  None = blank."""
    out = Image.new("RGBA", (CELL_W, CELL_H), BG + (255,))
    if mask is not None:
        m = _autocrop(mask)
        scale = min((CELL_W - 2 * PAD) / m.size[0], (CELL_H - 2 * PAD) / m.size[1])
        w, h = max(1, int(round(m.size[0] * scale))), max(1, int(round(m.size[1] * scale)))
        m = m.resize((w, h), Image.LANCZOS)
        out.alpha_composite(m, ((CELL_W - w) // 2, (CELL_H - h) // 2))
    return out.convert("RGB")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--images", type=Path, required=True,
                    help="path to the stock game's Images folder")
    args = ap.parse_args()

    masks = Image.open(args.images / "heathen_masks.png").convert("RGBA")

    strip = Image.new("RGB", (CELL_W * (MASK_ROWS + 1), CELL_H), BG)
    strip.paste(_cell(None), (0, 0))                             # cell 0: None (blank)
    for r in range(MASK_ROWS):                                    # cells 1..5
        strip.paste(_cell(_front_mask(masks, r)), ((r + 1) * CELL_W, 0))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    strip.save(OUT)
    print(f"wrote {OUT}  ({strip.size[0]}x{strip.size[1]}, {MASK_ROWS + 1} cells, "
          f"mask-only, front frame col {MASK_FRONT_COL})")


if __name__ == "__main__":
    main()
