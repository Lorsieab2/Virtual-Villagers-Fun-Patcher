"""Build the Change Appearance mask PREVIEW atlas from VV2's shared strip.

For pixel-identical pickers across all 5 games the owner wants VV4 to use VV2's
mask sprites. Source: assets/vv4_masks/vv2_mask_preview.bmp (pulled from VV2's
branch codex/vv2-heathen-mask:native/vv2_origins_icons/appearance/mask_preview.bmp)
-- a 240x65 strip of SIX 40x65 cells: cell 0 blank, cells 1..5 =
Blue/Orange/Red/Purple/Chief, front frame, mask alone, ~90% fill, on a
(236,236,236) button-face background. We color-key that gray to transparent and
save a PNG (our GDI+ picker composites it over the dialog). Cell index == mask
value (0 = none). Output: assets/vv4_masks/vvfp_mask_preview.png (240x65).
"""
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "assets/vv4_masks/vv2_mask_preview.bmp"
OUT = ROOT / "assets/vv4_masks/vvfp_mask_preview.png"
KEY = (236, 236, 236)          # VV2's button-face background
TOL = 6


def main() -> None:
    im = Image.open(SRC).convert("RGBA")
    px = im.load()
    w, h = im.size
    for y in range(h):
        for x in range(w):
            r, g, b, _ = px[x, y]
            if abs(r - KEY[0]) <= TOL and abs(g - KEY[1]) <= TOL and abs(b - KEY[2]) <= TOL:
                px[x, y] = (0, 0, 0, 0)
    im.save(OUT)
    print("wrote", OUT, im.size)


if __name__ == "__main__":
    main()
