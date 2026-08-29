"""Pack the owner's dedicated bighead mask source ("bigheads vv4 vv5 mask.png",
the same source VV5 uses) into a clean 3-col x 5-row grid for the VV4 Details
portrait: autocrop each frame, center-x, CHIN(bottom)-align rows to a common
baseline (chief's tall feathers rise above; chins stay put). Cell 40x90. The DLL
builds a game sprite from it (FUN_0040ABA0 subcols=3, subrows=5); the portrait
draws its FRONT column (1) at the head's own scale x1.5. Bighead-resolution art,
so NO village-atlas upscale. Row order = Blue/Orange/Red/Purple/Chief (mask-1).
"""
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
SRC = Path("C:/Users/Owner/Downloads/bigheads vv4 vv5 mask.png")
OUT = ROOT / "assets/vv4_masks/vvfp_bighead_mask_atlas.png"
CW, CH, MARGIN = 40, 90, 3


def main():
    src = np.array(Image.open(SRC).convert("RGBA"))
    a = src[:, :, 3] > 16
    lbl, n = ndimage.label(ndimage.binary_dilation(a, iterations=2))
    comps = []
    for i, sl in enumerate(ndimage.find_objects(lbl)):
        if sl is None:
            continue
        ys, xs = sl
        own = (lbl[ys, xs] == i + 1) & a[ys, xs]
        if own.sum() < 50:
            continue
        yy, xx = np.where(own)
        comps.append((xs.start + xx.min(), ys.start + yy.min(),
                      xs.start + xx.max(), ys.start + yy.max()))
    comps.sort(key=lambda b: (b[1] + b[3]))
    rows, cur, last = [], [], None
    for b in comps:
        cy = (b[1] + b[3]) / 2
        if last is None or cy - last < 80:
            cur.append(b)
        else:
            rows.append(cur)
            cur = [b]
        last = cy
    rows.append(cur)
    rows = [sorted(r, key=lambda b: b[0]) for r in rows]
    assert len(rows) == 5 and all(len(r) == 3 for r in rows), [len(r) for r in rows]
    atlas = Image.new("RGBA", (3 * CW, 5 * CH), (0, 0, 0, 0))
    for ri, r in enumerate(rows):
        for ci, (x0, y0, x1, y1) in enumerate(r):
            crop = Image.fromarray(src[y0:y1 + 1, x0:x1 + 1])
            w, h = crop.size
            dx = max(0, (CW - w) // 2)
            dy = max(0, CH - MARGIN - h)          # chin (bottom) aligned
            atlas.alpha_composite(crop, (ci * CW + dx, ri * CH + dy))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    atlas.save(OUT)
    print(f"wrote {OUT} ({atlas.size}) 3x5 chin-aligned bighead mask atlas")


if __name__ == "__main__":
    main()
