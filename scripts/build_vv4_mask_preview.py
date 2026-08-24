"""Build the Change Appearance mask PREVIEW atlas from the render atlas.

The render atlas (assets/vv4_masks/vvfp_mask_atlas.png, 8 dir cols x 5 mask rows
of 40x65) positions each mask to OVERLAY a head, so its content sits high/left
in the cell -- fine in-world, but as an isolated dialog preview it looks tiny
and off-centre. For the picker preview we want each mask autocropped and
centred at ~90% fill in a clean 40x65 cell (VV2 parity: source cell 40x65 for
all 5 games). Output: assets/vv4_masks/vvfp_mask_preview.png = 40 x (65*5),
one column, row = mask 1..5 (Blue/Orange/Red/Purple/Chief) at index 0..4.
"""
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "assets/vv4_masks/vvfp_mask_atlas.png"
OUT = ROOT / "assets/vv4_masks/vvfp_mask_preview.png"
CW, CH = 40, 65
FRONT_COL = 5          # 6th frame from the left = the front-facing mask
ROWS = 5
PAD = 2                # ~90% fill (fit into (40-4) x (65-4))


def main() -> None:
    atlas = Image.open(SRC).convert("RGBA")
    out = Image.new("RGBA", (CW, CH * ROWS), (0, 0, 0, 0))
    for r in range(ROWS):
        cell = atlas.crop((FRONT_COL * CW, r * CH, FRONT_COL * CW + CW, r * CH + CH))
        bbox = cell.getbbox()
        if bbox is None:
            continue                      # empty (shouldn't happen)
        mask = cell.crop(bbox)
        maxw, maxh = CW - 2 * PAD, CH - 2 * PAD
        scale = min(maxw / mask.width, maxh / mask.height)
        w, h = max(1, round(mask.width * scale)), max(1, round(mask.height * scale))
        mask = mask.resize((w, h), Image.LANCZOS)
        dst = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
        dst.alpha_composite(mask, ((CW - w) // 2, (CH - h) // 2))
        out.paste(dst, (0, r * CH))
    OUT.write_bytes(b"")                   # ensure parent exists / truncate
    out.save(OUT)
    print("wrote", OUT, out.size)


if __name__ == "__main__":
    main()
