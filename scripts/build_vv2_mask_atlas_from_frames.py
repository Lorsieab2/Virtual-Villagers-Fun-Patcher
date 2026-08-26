"""Rebuild the VV2 mask atlas from the owner's 8-direction frame sheet.

The source sheet (``native/vv2_origins_icons/heathen_mask_frames_8dir_source.png``)
is hand-laid-out mask-only art: five rows (blue, orange, red, purple, chief) of
eight directional frames each, at irregular spacing rather than a uniform grid.
Frames are located as connected alpha blobs, grouped into rows by centroid Y and
ordered left-to-right by centroid X.

VV2's head atlas has SEVEN columns, so the eighth frame of each row is dropped.

PLACEMENT: a mask must COVER THE FACE in every facing, so each frame is aligned
by its own face-covering region onto the head's actual face for that frame.

Both halves of that are measured, not guessed:
  * FACE_ANCHOR below is the median skin centroid per head frame over all 60 head
    variants (30 male + 30 female). Spread is only 0.6-2.4px, so one anchor per
    frame serves every head.
  * The mask's face region is the bottom FACE_FRAC of its sprite -- the part that
    sits on the face. Anchoring by the FULL sprite instead lets a tall headdress
    drag the mask off the face, which is exactly how the chief frames went wrong.

An earlier version anchored to the centroids of the previous atlas. That looked
fine but was wrong: it inherited a horizontal error of up to 7px on the turned
frames, so masks did not track the face across facings.

Chief frames 0/1/4/5 lose a few feather-tip pixels to the cell edge at this
alignment. That is deliberate: covering the face outranks a feather tip, and
clamping them inside the cell would push the mask 2-4px off the face.

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

# The mask cell is deliberately LARGER than the 40x65 head cell: headdresses and
# feathers extend past the head, and a head-sized cell clips them (chief lost 64px
# of feather tip at 40 wide). PAD_X is the horizontal margin on EACH side, so the
# exe draws the mask at (headX - PAD_X, headY - LIFT).
CELL_W, CELL_H = 52, 90     # mask atlas cell (head cell is 40x65)
PAD_X = 6                   # (CELL_W - 40) / 2
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


# Head-cell (x, y) of the face per frame: median skin centroid across all 60 head
# variants. Regenerate with scripts/measure_vv2_face_anchors.py if the head art
# ever changes; do not hand-edit.
FACE_ANCHOR: dict[int, tuple[float, float]] = {
    0: (22.780, 23.230), 1: (21.980, 22.750), 2: (20.920, 22.990), 3: (20.010, 23.400),
    4: (22.160, 22.580), 5: (21.830, 22.660), 6: (21.060, 22.970),
}
LIFT = 42          # exe draws the atlas cell at (x, y - LIFT) over the head cell
FACE_FRAC = 0.55   # bottom fraction of a mask sprite treated as its face region


def face_anchor(art: np.ndarray) -> tuple[float, float]:
    """Centroid of the mask's face-covering region (bottom FACE_FRAC of the sprite)."""
    opaque = art[:, :, 3] > 30
    rows = np.where(opaque.any(1))[0]
    if len(rows) == 0:
        return 0.0, 0.0
    top, bottom = rows.min(), rows.max()
    cut = int(bottom - (bottom - top) * FACE_FRAC)
    region = opaque.copy()
    region[:cut, :] = False
    if region.sum() < 10:       # very short sprite: fall back to the whole thing
        region = opaque
    ys, xs = np.where(region)
    return float(xs.mean()), float(ys.mean())


def build(source: Path, out: Path) -> None:
    frames = extract_frames(source)
    atlas = Image.new("RGBA", (CELL_W * 8, CELL_H * len(MASKS)), (0, 0, 0, 0))

    for row, name in enumerate(MASKS):
        available = frames[name]
        if len(available) < FRAMES:
            raise SystemExit(f"{name}: need {FRAMES} frames, found {len(available)}")
        for col in range(FRAMES):
            face_x, face_y = FACE_ANCHOR[col]
            art = available[col]
            art_x, art_y = face_anchor(art)
            # Put the mask's face region on the head's face. +LIFT converts the
            # head-cell y into this taller atlas cell's coordinates.
            px = int(round(PAD_X + face_x - art_x))
            py = int(round(face_y + LIFT - art_y))

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
