"""Rebuild the VV2 mask atlas from the owner's 8-direction frame sheet.

The source sheet (``native/vv2_origins_icons/heathen_mask_frames_8dir_source.png``)
is hand-laid-out mask-only art: five rows (blue, orange, red, purple, chief) of
eight directional frames each, at irregular spacing rather than a uniform grid.
Frames are located as connected alpha blobs, grouped into rows by centroid Y and
ordered left-to-right by centroid X.

VV2's head atlas has SEVEN columns, so the eighth frame of each row is dropped.

PLACEMENT: each frame is centred on a BAKED anchor rather than re-derived from
scratch. Those anchors are the per-cell centroids of the atlas that was tuned and
play-verified in-game, so an art swap changes only the art. They are constants
here on purpose: anchoring to "the current atlas" is self-defeating, because the
first swap overwrites the very reference the next rebuild would need.

Usage:
    python -m scripts.build_vv2_mask_atlas_from_frames [--out PATH]

The rebuilt atlas must be re-embedded by rebuilding the DLL
(scripts/build_vv2_origins_icons.ps1), after which BOTH pins on the DLL digest
need re-certifying: data/vv2_origins_feature.json and the doubler-audit
assertion in tests/test_doubler_audit.py.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

_ROOT = Path(__file__).resolve().parents[1]
_NATIVE = _ROOT / "native" / "vv2_origins_icons"
SOURCE = _NATIVE / "heathen_mask_frames_8dir_source.png"
ATLAS = _NATIVE / "heathen_masks.png"

CELL_W, CELL_H = 40, 88     # atlas cell
FRAMES = 7                  # VV2 head atlas columns; the 8th source frame is dropped
MASKS = ["blue", "orange", "red", "purple", "chief"]
_MIN_BLOB = 60              # ignore stray specks
_ROW_GAP = 60               # vertical gap that separates one mask row from the next


def extract_frames(source: Path) -> dict[str, list[np.ndarray]]:
    """Per-mask, left-to-right list of tightly-cropped RGBA frames."""
    src = np.array(Image.open(source).convert("RGBA"))
    lbl, count = ndimage.label(src[:, :, 3] > 30)
    sizes = np.bincount(lbl.ravel())
    sizes[0] = 0
    ids = [i for i in range(1, count + 1) if sizes[i] > _MIN_BLOB]
    if not ids:
        raise SystemExit(f"{source}: no mask blobs found")

    centroids = {
        i: (float(np.where(lbl == i)[0].mean()), float(np.where(lbl == i)[1].mean()))
        for i in ids
    }
    ordered = sorted(c[0] for c in centroids.values())
    rows: list[list[float]] = [[ordered[0]]]
    for y in ordered[1:]:
        if y - rows[-1][-1] > _ROW_GAP:
            rows.append([y])
        else:
            rows[-1].append(y)
    if len(rows) != len(MASKS):
        raise SystemExit(f"{source}: expected {len(MASKS)} mask rows, found {len(rows)}")

    out: dict[str, list[np.ndarray]] = {}
    for name, row in zip(MASKS, rows):
        lo, hi = min(row) - 30, max(row) + 30
        members = [i for i in ids if lo <= centroids[i][0] <= hi]
        members.sort(key=lambda i: centroids[i][1])
        frames = []
        for i in members:
            ys, xs = np.where(lbl == i)
            crop = src[ys.min():ys.max() + 1, xs.min():xs.max() + 1].copy()
            sub = lbl[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
            crop[sub != i] = 0          # drop any neighbour bleeding into the bbox
            frames.append(crop)
        out[name] = frames
    return out


# Per-cell (x, y) centroids of the play-verified atlas, in cell-local pixels.
# Recovered from the pre-swap atlas; see the PLACEMENT note above before editing.
ANCHORS: dict[str, list[tuple[float, float]]] = {
    "blue": [(25.0676, 62.6235), (26.5346, 63.3918), (14.9471, 63.1862), (13.7787, 62.4507),
             (25.3579, 63.9178), (21.5034, 63.904), (16.3002, 62.9485)],
    "orange": [(22.0771, 59.8314), (21.3472, 60.9793), (14.9322, 59.9024), (15.0628, 60.0109),
               (21.5495, 60.768), (20.2237, 60.8553), (17.7926, 60.6659)],
    "red": [(24.9966, 55.1837), (25.434, 55.7779), (16.7596, 55.6313), (14.504, 55.3403),
            (24.3163, 56.2863), (22.0649, 56.0024), (17.7808, 56.0897)],
    "purple": [(24.0526, 57.0226), (25.985, 55.8828), (16.8717, 57.6126), (14.9845, 58.1118),
               (23.0944, 57.3815), (21.4154, 57.329), (18.6926, 57.5446)],
    "chief": [(26.9353, 52.2666), (25.8468, 51.7996), (13.9846, 50.7947), (12.3549, 52.2024),
              (25.5981, 50.7587), (20.7673, 50.6944), (17.4393, 51.7745)],
}


def _centroid(mask: np.ndarray) -> tuple[float, float]:
    ys, xs = np.where(mask)
    return float(xs.mean()), float(ys.mean())


def build(source: Path, out: Path) -> None:
    frames = extract_frames(source)
    atlas = Image.new("RGBA", (CELL_W * 8, CELL_H * len(MASKS)), (0, 0, 0, 0))

    for row, name in enumerate(MASKS):
        available = frames[name]
        if len(available) < FRAMES:
            raise SystemExit(f"{name}: need {FRAMES} frames, found {len(available)}")
        for col in range(FRAMES):
            ref_cx, ref_cy = ANCHORS[name][col]

            art = available[col]
            art_cx, art_cy = _centroid(art[:, :, 3] > 30)
            px = int(round(ref_cx - art_cx))
            py = int(round(ref_cy - art_cy))

            h, w = art.shape[:2]
            sx0, sy0 = max(0, -px), max(0, -py)
            sx1, sy1 = min(w, CELL_W - px), min(h, CELL_H - py)
            if sx1 > sx0 and sy1 > sy0:         # clip so art never bleeds into a neighbour
                piece = Image.fromarray(art[sy0:sy1, sx0:sx1], "RGBA")
                atlas.alpha_composite(piece, (col * CELL_W + px + sx0, row * CELL_H + py + sy0))

    atlas.save(out)
    print(f"atlas -> {out} {atlas.size}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", type=Path, default=SOURCE)
    ap.add_argument("--out", type=Path, default=ATLAS)
    args = ap.parse_args()
    if not args.source.is_file():
        raise SystemExit(f"missing input: {args.source}")
    build(args.source, args.out)


if __name__ == "__main__":
    main()
