"""Build the Change Appearance mask PREVIEW atlas from the bighead mask art.

Source: assets/vv4_masks/vvfp_bighead_mask_src.png -- the owner's bighead masks,
5 rows (Blue/Orange/Red/Purple/Chief) x 3 frames, on transparent bg with
spacing. The owner wants the picker preview to use FRAME 2 (0-based column 2 =
the rightmost frame). We detect the row bands by alpha projection, crop frame 2
of each row, autocrop, and centre it at ~90% fill in a clean 40x65 cell (the
VV2-parity source size). Output: assets/vv4_masks/vvfp_mask_preview.png =
40 x (65*5), one column, row = mask 1..5 at index 0..4.
"""
from pathlib import Path
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "assets/vv4_masks/vvfp_bighead_mask_src.png"
OUT = ROOT / "assets/vv4_masks/vvfp_mask_preview.png"
CW, CH = 40, 65
PAD = 2
FRAME2_X = (120, 163)          # frame-2 (rightmost) column band, with a little margin


def row_bands(mask):
    v = mask.sum(1)
    bands, s = [], None
    for i, x in enumerate(v):
        if x > 0 and s is None:
            s = i
        elif x <= 0 and s is not None:
            bands.append((s, i)); s = None
    if s is not None:
        bands.append((s, len(v)))
    return bands


def main() -> None:
    im = Image.open(SRC).convert("RGBA")
    a = np.array(im)
    content = a[:, :, 3] > 16
    # restrict to the frame-2 column, find the 5 row bands there
    col = np.zeros_like(content)
    col[:, FRAME2_X[0]:FRAME2_X[1]] = content[:, FRAME2_X[0]:FRAME2_X[1]]
    bands = row_bands(col)
    if len(bands) != 5:
        raise RuntimeError(f"expected 5 mask rows in frame 2, got {len(bands)}: {bands}")
    out = Image.new("RGBA", (CW, CH * 5), (0, 0, 0, 0))
    for r, (y0, y1) in enumerate(bands):
        cell = im.crop((FRAME2_X[0], y0, FRAME2_X[1], y1))
        bbox = cell.getbbox()
        if bbox is None:
            continue
        m = cell.crop(bbox)
        maxw, maxh = CW - 2 * PAD, CH - 2 * PAD
        scale = min(maxw / m.width, maxh / m.height)
        w, h = max(1, round(m.width * scale)), max(1, round(m.height * scale))
        m = m.resize((w, h), Image.LANCZOS)
        dst = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
        dst.alpha_composite(m, ((CW - w) // 2, (CH - h) // 2))
        out.paste(dst, (0, r * CH))
    out.save(OUT)
    print("wrote", OUT, out.size, "from frame-2 rows", bands)


if __name__ == "__main__":
    main()
