"""Build the VV4 Heathen-mask SEPARATE atlas from the user's hand-aligned mockups.

The user's alignment mockups (assets/vv4_masks/mockups/mockup_<color>.png) are the
game's own female_heads00 ROW 26 head with the mask painted on, at a fixed offset
(HX=1, VY=-6). We recover the EXACT isolated mask by subtracting that head, denoise
the tiny gold speckle where mask-gold meets hair-gold, and lay each mask into a
320x325 grid (8 cols x 5 rows of 40x65 cells) positioned exactly where it sits on
the face. This single atlas serves BOTH the in-village render and the (scaled)
Details portrait -- the game's draw primitive scales it like the head.

Output: assets/vv4_masks/vvfp_mask_atlas.png (the separate mask atlas shipped to
Images/ and drawn ON TOP of the head; the head atlas is NOT modified).
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
MOCK = ROOT / "assets/vv4_masks/mockups"
FEMALE = ROOT / "assets/vv4_masks/base/female_heads00.png"
OUT = ROOT / "assets/vv4_masks/vvfp_mask_atlas.png"

CELL_W, CELL_H, COLS = 40, 65, 8
ORDER = ["blue", "orange", "red", "purple", "chief"]   # -> mask value 1..5, rows 0..4
HEAD_ROW = 26                 # female_heads00 row the mockups were built on
HX, VY = 1, -6               # mockup(x,y) -> female atlas (x+HX, HEAD_ROW*65+VY + y)
DIFF_THRESHOLD = 60          # per-pixel colour delta to count as "mask, not head"
MIN_BLOB = 20                # drop connected components smaller than this (denoise)


def _load(p: Path) -> np.ndarray:
    return np.array(Image.open(p).convert("RGBA"))


def _head_under(mock_shape, female: np.ndarray) -> np.ndarray:
    """The female row-26 head pixels aligned under a mockup of the given shape."""
    h, w = mock_shape
    out = np.zeros((h, w, 4), np.uint8)
    base_y = HEAD_ROW * CELL_H + VY
    for y in range(h):
        ay = base_y + y
        if 0 <= ay < female.shape[0]:
            xw = min(w, female.shape[1] - HX)
            if xw > 0:
                out[y, :xw] = female[ay, HX:HX + xw]
    return out


def _extract(color: str, female: np.ndarray) -> np.ndarray:
    mock = _load(MOCK / f"mockup_{color}.png")
    head = _head_under(mock.shape[:2], female)
    diff = np.abs(mock[:, :, :3].astype(int) - head[:, :, :3].astype(int)).sum(2)
    is_mask = (mock[:, :, 3] > 128) & ((head[:, :, 3] <= 128) | (diff > DIFF_THRESHOLD))
    lbl, n = ndimage.label(is_mask)
    if n:
        sizes = ndimage.sum(np.ones_like(lbl), lbl, range(1, n + 1))
        small = [i + 1 for i, s in enumerate(sizes) if s < MIN_BLOB]
        if small:
            is_mask &= ~np.isin(lbl, small)
    out = mock.copy()
    out[~is_mask] = [0, 0, 0, 0]
    return out


def build() -> Image.Image:
    female = _load(FEMALE)
    atlas = Image.new("RGBA", (CELL_W * COLS, CELL_H * len(ORDER)), (0, 0, 0, 0))
    for i, color in enumerate(ORDER):
        ext = _extract(color, female)
        band = Image.new("RGBA", (CELL_W * COLS, CELL_H), (0, 0, 0, 0))
        # place at the same within-cell offset the mask has on the head; a
        # negative VY clips the top few px of tall feathers (engine cell limit).
        band.alpha_composite(Image.fromarray(ext), (HX, VY))
        atlas.paste(band, (0, CELL_H * i))
    return atlas


def main() -> None:
    atlas = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    atlas.save(OUT)
    print(f"wrote {OUT} {atlas.size} (8x5 of {CELL_W}x{CELL_H}; masks blue/orange/red/purple/chief = value 1..5)")


if __name__ == "__main__":
    main()
