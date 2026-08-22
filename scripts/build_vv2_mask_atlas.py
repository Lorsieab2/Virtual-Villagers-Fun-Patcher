"""VV2 Heathen-mask overlay atlas builder.

Uses VV3's technique (scripts/build_vv3_mask_atlas.py) — native-size masks, face
extracted per facing, drawn by the render hook via FUN_004095b0 — but with the
one deviation VV2 needs: the masks (Chief ~72px, Red ~63px) are TALLER than the
65px head-atlas cell, so cramming them into head rows would clip the feathers.
Instead we pack them into a DEDICATED mask atlas with taller cells (40x88), each
mask face-anchored at a fixed cell-y, so the render hook draws the whole mask at
the head with the face-plate on the villager and the feathers/spikes above.

The VV5 sheet's 8 masks/row are separate blobs whose centers are offset from any
uniform grid, so we extract each mask by its own connected component (no double,
no bleed, no cropping).

Usage:
  python build_vv2_mask_atlas.py --atlas <out.png>          # write dedicated mask atlas
  python build_vv2_mask_atlas.py --preview                  # write on-head preview PNG
"""
from __future__ import annotations

import sys
from pathlib import Path
from PIL import Image
import numpy as np
from scipy import ndimage

SRC_CELL_W, SRC_CELL_H = 65, 145   # VV5 uniform cell (520x725 / 8 / 5)
FRAMES = 8
MASK_ROWS = 5
# where each mask's own face-line sits as a fraction of its height (feathers push the
# Chief's face lower down its sprite, so it needs a larger fraction).  Order = atlas row:
# 0 Blue, 1 Orange, 2 Red, 3 Purple, 4 Tribal Chief.
FACE_Y_FRAC_PER_MASK = [0.60, 0.60, 0.64, 0.60, 0.74]
# per-MASK fine nudge (independent of facing) — some masks (esp. Chief, with tall asymmetric
# feathers that skew the eye-band centroid) need their own offset.  +x = right, +y = down.
# Per-mask CENTERING correction (small): only to center a mask at the FRONT if its own face
# detection is slightly off — NOT a general shift.  The profile shift comes entirely from
# FACE_FOLLOW (zero at front, growing toward profiles in the face-turn direction) per the rule
# "no shift at front; increase shift the more the face turns".
MASK_DX = [0, 0, 0, 0, 0]        # Blue, Orange, Red, Purple, Chief
MASK_DY = [0, 0, -2, -6, -3]     # raise Red/Purple/Chief (their faces sit lower in the sprite)
# Port mask art is already at the user's chosen size, so no rescale (all 1.0).  (Kept for the
# fallback VV5-extraction path; when port files are present these are effectively unused.)
MASK_SCALE = [1.0, 1.0, 1.0, 1.0, 1.0]

# head atlas geometry: the engine loads male_heads.png (280x1950) as 7 cols x 30 rows
# of 40x65 cells (verified via the loader 0x40a270 args).  The mask atlas MUST match
# this cell so the render hook can draw it with the head's own position+scale args and
# get correct scaling (children included) for free.
HEAD_W, HEAD_H = 40, 65
FACE_SAMPLE_ROWS = [3, 5, 8, 12, 20]

# mask atlas: a CUSTOM cell TALLER than the head cell (40x88) so even the Chief renders
# fully (feathers + chin), never shrunk or clipped.  Every mask's face-line is anchored at
# a fixed cell-y (MASK_ANCHOR_CY); the render hook then lifts the whole cell by
# (MASK_ANCHOR_CY - HEAD_FACE_CY) so the face lands on the villager's face — scaled by the
# child draw for small villagers.  Horizontal still follows the head's per-facing face-x.
MASK_CELL_W, MASK_CELL_H = 40, 88
MASK_ANCHOR_CY = 56                # mask face-line sits here in the cell (feathers above)
# How strongly the mask follows the head's per-facing face-x offset from centre.  1.0 = follow
# the skin centroid fully (over-shoots profiles — the mask's face-edge lands on the head's
# face-edge, flinging it toward the turn); 0.0 = always centred (doesn't follow at all).  ~0.5
# tracks the face without the profile overshoot.  Front facings are ~centred either way.
FACE_FOLLOW = 0.35
# fine per-facing horizontal nudge (px, +right) applied after damping — for hand-tuning any
# residual on specific facings without disturbing the others.  Index = frame 0..7.
NUDGE_X = [0, 0, 0, 0, 0, 0, 0, 0]
HEAD_FACE_CY = 24                  # the head's face sits here in its 40x65 cell
ADULT_MASK_DY = MASK_ANCHOR_CY - HEAD_FACE_CY   # 32px lift (preview + exe reference)

SRC = Path(r"C:/Users/Owner/Downloads/Virtual Villagers - New Believers/Images/vv5_heathenheads.png")
HEADS_DIR = Path(r"C:/Users/Owner/Downloads/Virtual Villagers - The Lost Children/Images")
SCRATCH = Path(r"C:/Users/Owner/AppData/Local/Temp/claude/C--Users-Owner--claude/0273893a-8270-4370-a19f-cd0f96b9c774/scratchpad")

# User-authored resized mask art ("port" files) — correct sizes + full Chief feathers that my
# VV5 extraction had cropped.  If present, these are the mask source (7 frames each, already at
# the user's chosen size, so MASK_SCALE is forced to 1.0).  One connected component per frame.
PORT_DIR = Path(r"C:/Users/Owner/Downloads/VV2 mask mockups")
PORT_FILES = ["blue", "orange", "red", "purple", "chief"]


def _port_mask_frames() -> list[list[Image.Image]]:
    """[row][frame] the user's resized mask art, extracted as one connected blob per frame."""
    out = []
    for nm in PORT_FILES:
        m = np.asarray(Image.open(PORT_DIR / f"vv5 mask port {nm}.png").convert("RGBA"))
        lbl, n = ndimage.label(m[..., 3] > 30)
        sizes = np.bincount(lbl.ravel()); sizes[0] = 0
        ids = [i for i in range(1, n + 1) if sizes[i] > 40]
        ids.sort(key=lambda i: float(np.where(lbl == i)[1].mean()))
        assert len(ids) == FRAMES - 1, f"{nm}: {len(ids)} frames (expected {FRAMES - 1})"
        frames = []
        for i in ids:
            ys, xs = np.where(lbl == i)
            y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
            sub = m[y0:y1, x0:x1].copy()
            sub[lbl[y0:y1, x0:x1] != i] = 0
            frames.append(Image.fromarray(sub, "RGBA"))
        out.append(frames)
    return out


def _mask_frames() -> list[list[Image.Image]]:
    """Prefer the user's port art (7 frames) if present; else the VV5 extraction (8 frames)."""
    if PORT_DIR.exists() and all((PORT_DIR / f"vv5 mask port {nm}.png").exists() for nm in PORT_FILES):
        return _port_mask_frames()
    return _native_mask_frames()


def _native_mask_frames() -> list[list[Image.Image]]:
    """8 full, isolated, native-size masks per row (by connected blob), facing 0..7."""
    m = np.asarray(Image.open(SRC).convert("RGBA"))
    out = []
    for r in range(MASK_ROWS):
        band = m[r * SRC_CELL_H:(r + 1) * SRC_CELL_H]
        lbl, n = ndimage.label(band[..., 3] > 20)
        sizes = np.bincount(lbl.ravel()); sizes[0] = 0
        ids = sorted((i for i in range(1, n + 1) if sizes[i] > 150), key=lambda i: -sizes[i])[:FRAMES]
        frames = []
        for i in ids:
            ys, xs = np.where(lbl == i)
            y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
            sub = band[y0:y1, x0:x1].copy()
            sub[lbl[y0:y1, x0:x1] != i] = 0
            frames.append((float(xs.mean()), Image.fromarray(sub, "RGBA")))
        frames.sort(key=lambda t: t[0])
        assert len(frames) == FRAMES, f"row {r}: {len(frames)} masks (expected {FRAMES})"
        out.append([im for _, im in frames])
    return out


def _is_skin(px) -> bool:
    r, g, b, a = px
    return a > 128 and r > 150 and g > 110 and b > 70 and r > b + 25 and (r - g) < 90


def _face_center_per_frame(src: Image.Image) -> list[tuple[float, float]]:
    out = []
    for f in range(FRAMES):
        xs, ys = [], []
        for row in FACE_SAMPLE_ROWS:
            px = src.crop((f * HEAD_W, row * HEAD_H, f * HEAD_W + HEAD_W, row * HEAD_H + HEAD_H)).load()
            for y in range(HEAD_H):
                for x in range(HEAD_W):
                    if _is_skin(px[x, y]):
                        xs.append(x); ys.append(y)
        out.append((sum(xs) / len(xs), sum(ys) / len(ys)) if xs else (HEAD_W / 2, 24.0))
    return out


def _mask_face_cx(m: Image.Image, frac: float) -> float:
    """The mask's OWN face x within its bitmap: opacity centroid in a horizontal band around
    the face-line (frac down the mask).  For a profile the whole-bbox center leans toward the
    wrapped-back side, but the eye/face band centroid tracks the actual face — so aligning THIS
    to the head's face-x makes the mask follow the face across all facings, not overshoot."""
    a = np.asarray(m)[..., 3] > 20
    nh = a.shape[0]
    c = int(round(nh * frac))
    lo, hi = max(0, c - 8), min(nh, c + 8)
    ys, xs = np.where(a[lo:hi])
    return float(xs.mean()) if len(xs) else m.size[0] / 2.0


def _scaled(mask: Image.Image, s: float) -> Image.Image:
    """Scale a native mask by per-mask factor s (masks render a bit big at native size)."""
    if s == 1.0:
        return mask
    w, h = mask.size
    return mask.resize((max(1, round(w * s)), max(1, round(h * s))), Image.LANCZOS)


def _place_in_cell(mask: Image.Image, face_x: float, face_y: float, frac: float) -> Image.Image:
    """Return a CELL-sized image with the mask fit fully inside (no clip), positioned so the
    mask's OWN face (eye-band centroid horizontally, face-line vertically) lands on the head's
    face (face_x, face_y).  Taller masks are scaled DOWN to fit (never clipped) so the whole
    thing stays inside the cell and the engine's per-villager scale applies verbatim."""
    m = mask
    nw, nh = m.size
    s = min(1.0, MASK_CELL_W / nw, MASK_CELL_H / nh)
    if s < 1.0:
        m = m.resize((max(1, round(nw * s)), max(1, round(nh * s))), Image.LANCZOS)
        nw, nh = m.size
    mfx = _mask_face_cx(m, frac)                   # mask's own face x within its bitmap
    cell = Image.new("RGBA", (MASK_CELL_W, MASK_CELL_H), (0, 0, 0, 0))
    x = round(face_x - mfx)                         # land the mask's face on the head's face-x
    y = round(face_y - nh * frac)
    x = max(0, min(x, MASK_CELL_W - nw))            # keep fully inside (fits after scale)
    y = max(0, min(y, MASK_CELL_H - nh))
    cell.alpha_composite(m, (x, y))
    return cell


def _avg_faces() -> list[tuple[float, float]]:
    """Per-facing head face centroid AVERAGED over all head atlases that exist (male/female,
    young/old) — the in-world crowd is a mix, and there is only ONE shared mask atlas, so
    aligning to the average face-x per facing minimises drift for the whole population."""
    names = ["male_heads.png", "male_heads_old.png", "female_heads.png", "female_heads_old.png"]
    per = []
    for nm in names:
        p = HEADS_DIR / nm
        if p.exists():
            per.append(_face_center_per_frame(Image.open(p).convert("RGBA")))
    if not per:
        per = [_face_center_per_frame(Image.open(HEADS_DIR / "male_heads.png").convert("RGBA"))]
    return [(sum(pf[f][0] for pf in per) / len(per), sum(pf[f][1] for pf in per) / len(per))
            for f in range(FRAMES)]


def _target_x(fcx: float, f: int) -> float:
    """Where the mask's face should land horizontally for facing f: the head's face-x pulled
    partway back toward centre (FACE_FOLLOW) so profiles don't overshoot, plus a per-facing
    hand nudge.  Front facings (fcx ~ centre) are essentially unchanged; left/right facings
    get shifted toward the head's turned face by the damped amount."""
    center = MASK_CELL_W / 2.0
    return center + FACE_FOLLOW * (fcx - center) + NUDGE_X[f]


def build_mask_atlas(out_path: Path) -> None:
    frames = _mask_frames()
    faces = _avg_faces()
    atlas = Image.new("RGBA", (MASK_CELL_W * FRAMES, MASK_CELL_H * MASK_ROWS), (0, 0, 0, 0))
    for r in range(MASK_ROWS):
        for f in range(FRAMES):
            if f >= len(frames[r]):            # port art has 7 frames; col 7 stays empty
                continue
            tx = _target_x(faces[f][0], f) + MASK_DX[r]
            cell = _place_in_cell(_scaled(frames[r][f], MASK_SCALE[r]), tx,
                                  MASK_ANCHOR_CY + MASK_DY[r], FACE_Y_FRAC_PER_MASK[r])
            atlas.paste(cell, (f * MASK_CELL_W, r * MASK_CELL_H))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    atlas.save(out_path)
    print(f"mask atlas -> {out_path}  ({atlas.size[0]}x{atlas.size[1]} = {FRAMES} frames x {MASK_ROWS} masks, "
          f"cell {MASK_CELL_W}x{MASK_CELL_H}, fit-to-cell + per-mask face-anchor)")


def preview() -> None:
    frames = _mask_frames()
    heads = Image.open(HEADS_DIR / "male_heads.png").convert("RGBA")
    faces = _avg_faces()
    PADTOP = 40
    ch = HEAD_H + PADTOP
    grid = Image.new("RGBA", (HEAD_W * FRAMES, ch * MASK_ROWS), (110, 110, 110, 255))
    for r in range(MASK_ROWS):
        for f in range(FRAMES):
            if f >= len(frames[r]):
                continue
            cell = Image.new("RGBA", (HEAD_W, ch), (0, 0, 0, 0))
            cell.alpha_composite(heads.crop((f * HEAD_W, 0, f * HEAD_W + HEAD_W, HEAD_H)), (0, PADTOP))
            fcx, fcy = faces[f]
            # overlay the EXACT in-game mask cell (fixed vertical anchor), then lift it by the
            # adult DY the render hook applies -> face lands on the head's face in this preview.
            mcell = _place_in_cell(_scaled(frames[r][f], MASK_SCALE[r]), _target_x(fcx, f) + MASK_DX[r],
                                   MASK_ANCHOR_CY + MASK_DY[r], FACE_Y_FRAC_PER_MASK[r])
            cell.alpha_composite(mcell, (0, PADTOP - ADULT_MASK_DY))
            grid.alpha_composite(cell, (f * HEAD_W, r * ch))
    out = SCRATCH / "vv2_mask_preview.png"
    grid.resize((HEAD_W * FRAMES * 7, ch * MASK_ROWS * 7), Image.NEAREST).convert("RGB").save(out)
    print("preview ->", out)


def main(argv) -> None:
    if "--preview" in argv:
        preview()
    elif "--atlas" in argv:
        i = argv.index("--atlas")
        build_mask_atlas(Path(argv[i + 1]))
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
