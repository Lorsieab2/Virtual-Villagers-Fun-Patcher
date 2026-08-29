"""Re-seat VV5's native 65x145 mask atlas onto VV4's head registration (VV5's
own instruction: convert the cell registration per facing so the mask's in-cell
FACE point matches VV4's head face point). Keeps the native 65x145 size (owner:
scaling made them too small). Bakes the per-facing HORIZONTAL alignment here (it
scales correctly from the cell corner at draw time); the VERTICAL lift is done
in the exe cave (MASK_DY_VALUES, scaled) so feather headroom is preserved.
"""
from pathlib import Path
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "assets/vv4_masks/vv5_heathenheads_source.png"   # 520x725, 65x145 cells
OUT = ROOT / "assets/vv4_masks/vvfp_mask_atlas_reseat.png"
COLS, ROWS, CW, CH = 8, 5, 65, 145
# VV4 head face x per facing col (measured from male_heads00 eye centroids).
HEAD_FACE_X = [25, 23, 19, 19, 23, 22, 19, 21]


def main():
    src = np.array(Image.open(SRC).convert("RGBA"))
    out = np.zeros_like(src)
    for r in range(ROWS):
        for c in range(COLS):
            cell = src[r * CH:(r + 1) * CH, c * CW:(c + 1) * CW]
            a = cell[:, :, 3] > 32
            ys, xs = np.where(a)
            if len(xs) == 0:
                continue
            lo = int(ys.max() * 0.6)                 # face = lower ~40% of content
            fx = xs[ys >= lo]
            mask_face_x = fx.mean() if len(fx) else xs.mean()
            shift = int(round(HEAD_FACE_X[c] - mask_face_x))   # align face x to head
            shifted = np.roll(cell, shift, axis=1)
            if shift > 0:
                shifted[:, :shift] = 0
            elif shift < 0:
                shifted[:, shift:] = 0
            out[r * CH:(r + 1) * CH, c * CW:(c + 1) * CW] = shifted
    Image.fromarray(out).save(OUT)
    print(f"wrote {OUT} ({Image.fromarray(out).size}) -- per-facing X re-seat to VV4 head face")


if __name__ == "__main__":
    main()
