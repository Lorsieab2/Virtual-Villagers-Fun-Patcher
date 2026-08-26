"""Build the 40x65-cell game mask atlas from the owner's corrected reference
atlas (assets/vv4_masks/vv5_heathenheads_source.png, 8 cols x 5 rows of 65x145).

The owner's atlas has the CORRECT facings (esp. chief, incl. mirrored right
frames) but uses taller cells. The game draw pipeline + per-mask DY table are
tuned for 40x65 cells whose content sits at the known-good vertical anchor
inherited from the prior atlas. So we TRANSPLANT: for each cell, take the
owner's mask content and place it into a 40x65 cell, matching the CURRENT
atlas's per-cell content position (horizontal centre + content BOTTOM = the
mask's face baseline), scaling down any content taller/wider than the cell so
nothing clips. That keeps the working render/DY tuning while adopting the
owner's correct art + facings.
"""
from pathlib import Path
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OWNER = ROOT / "assets/vv4_masks/vv5_heathenheads_source.png"
CUR = ROOT / "assets/vv4_masks/vvfp_mask_atlas.png"          # current 40x65, working positions
OUT = ROOT / "assets/vv4_masks/vvfp_mask_atlas.png"
CW, CH, COLS, ROWS = 40, 65, 8, 5


def content_bbox(alpha):
    ys, xs = np.where(alpha > 32)
    if len(ys) == 0:
        return None
    return xs.min(), ys.min(), xs.max(), ys.max()


def main():
    own = np.array(Image.open(OWNER).convert("RGBA"))
    OW, OH = own.shape[1] // COLS, own.shape[0] // ROWS
    cur = np.array(Image.open(CUR).convert("RGBA"))
    atlas = Image.new("RGBA", (CW * COLS, CH * ROWS), (0, 0, 0, 0))
    for r in range(ROWS):
        for c in range(COLS):
            oc = own[r * OH:(r + 1) * OH, c * OW:(c + 1) * OW]
            bb = content_bbox(oc[:, :, 3])
            if bb is None:
                continue
            x0, y0, x1, y1 = bb
            crop = Image.fromarray(oc[y0:y1 + 1, x0:x1 + 1])
            w, h = crop.size
            # scale down to fit the 40x65 cell (uniform, preserve aspect)
            s = min(1.0, (CW - 2) / w, (CH - 2) / h)
            if s < 1.0:
                crop = crop.resize((max(1, round(w * s)), max(1, round(h * s))), Image.LANCZOS)
                w, h = crop.size
            # PRESERVE the owner's authored per-facing alignment (VV5: the art is
            # pre-aligned per facing -- do NOT re-center or the mask fights the head).
            # The owner positioned each mask relative to the head-reference = the
            # source cell centre; carry that exact px offset into our cell UNSCALED
            # (our masks are ~head-sized already). Uniform for ALL colors incl chief.
            own_cx = (x0 + x1 + 1) / 2.0
            cx = CW / 2.0 + (own_cx - OW / 2.0)      # unscaled offset from cell centre
            dx = int(round(cx - w / 2.0))
            # vertical: proven content-BOTTOM anchor (the DY table is tuned for it).
            cbb = content_bbox(cur[r * CH:(r + 1) * CH, c * CW:(c + 1) * CW, 3])
            bottom = cbb[3] if cbb else CH - 3
            dy = int(round(bottom - h + 1))
            # allow horizontal overhang (wide feathers clip at the edge rather than
            # dragging the face off-center); clamp vertically to the cell.
            dy = max(0, min(dy, CH - h))
            tile = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
            tile.alpha_composite(crop, (dx, dy))
            atlas.alpha_composite(tile, (c * CW, r * CH))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    atlas.save(OUT)
    print(f"wrote {OUT} ({atlas.size}) transplanted from owner atlas {OWNER.name}")


if __name__ == "__main__":
    main()
