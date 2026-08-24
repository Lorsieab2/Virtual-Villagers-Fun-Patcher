"""Build the VV1 Heathen-mask sheets from the supplied, pre-aligned mask art.

The art in assets/origins/mask-art/ was authored against VV1's own head
atlas: each file is a seven-frame strip, one frame per facing column, already
positioned so that dropping it over a head row lands the mask on the face. It
is used verbatim -- no scaling, no cropping, no re-centring. This script only
moves it onto the cell grid the draw hook blits from.

Alignment was recovered from the supplied mockups rather than guessed. Each
"alignment mockup" is that colour's mask composited over a real VV1 head
(female_heads.png row 11 -- identified by its magenta hair, which is the only
part of the head the mask does not cover). Correlating the mask layer and the
head layer against the mockup independently gives each colour's offset
relative to the head cell origin, and recompositing head+mask at that offset
reproduces the mockup essentially pixel-for-pixel for blue, orange, red and
purple.

Chief is the exception: its mockup is a free-form arrangement -- individual
frames sit up to 42px off the others' baseline -- so a single offset cannot
reproduce it. Its global correlation is still the best available estimate and
is what ships; see MASK_OFFSETS.

Usage:  python scripts/build_vv1_heathen_mask_sheets.py [--check]
"""
from __future__ import annotations

import argparse
import io
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ART_DIR = ROOT / "assets" / "origins" / "mask-art"
OUT_DIR = ROOT / "assets" / "origins"
PREVIEW_BMP = ROOT / "native" / "vv1_origins_icons" / "appearance" / "mask.bmp"
# Single atlas for the in-game draw, laid out the way the stock sprite loader
# wants it: one image, COLS x ROWS of equal cells, loaded via the game's own
# 0x40A070(this, filename, cols, rows) which derives cellW = imgW/cols and
# cellH = imgH/rows. Column = facing, row = mask value - 1, so a draw is just
# (row = villager byte - 1, col = facing) with no lookup.
#
# Going through the game's loader (rather than IMG_Load + a hand-rolled blit)
# is what lets the mask ride the game's own scaled draw path, so children scale
# for free instead of needing separate art.
ATLAS_PNG = ROOT / "assets" / "origins" / "mask_atlas.png"

# VV1's head atlas is 280x1300 = 7 columns x 20 rows of 40x65 (the transparent
# separator columns fall on multiples of 40, and the 20 content bands start
# ~65 apart). The mask sheets use the same 7 columns at the same 40px pitch,
# so facing N of the sheet is facing N of the head with no lookup table.
CELL_W = 40
FACINGS = 7
HEAD_CELL_H = 65

# In mask-value order (1..5), matching vv1_mask_name() in the icons DLL.
COLOURS = ["blue", "orange", "red", "purple", "chief"]

# (x, y) of each art file's top-left relative to the head CELL origin,
# recovered from the mockups as described above. X differs per colour only
# because each file is cropped to its own content.
#
# A colour may instead give seven (x, y) pairs, one per facing. Chief needs
# that: its art has frames 2, 4 and 6 drawn about 45px below the others, and
# its mockup staggers those frames' HEADS by the same amount to compensate.
# A single offset therefore lines up four facings and leaves three with the
# villager's head exposed above the mask -- which is exactly what the first
# build of this art did. Per-frame offsets were recovered the same way as the
# rest: locate each facing's head by its magenta hair, locate the mask over
# it, subtract.
PACKED = "packed-atlas"
CHIEF_DY = -2  # px lift for the packed chief frames (playtest: up 3 from -5)
CHIEF_DX = 2   # px rightward nudge for the packed chief frames (playtest: left 3)
# The chief is a packed atlas anchored to the OTHER colours' median mask
# centre/chin. That coupling meant tuning a gridded colour (e.g. lifting
# purple) silently moved the chief and could push its tall frames off the top
# of the cell. So the anchor is FROZEN here (captured once, at a fitting
# gridded state) -- the chief now tunes independently via CHIEF_DX/CHIEF_DY,
# and gridded-colour tweaks no longer disturb it. Re-capture only if the head
# geometry itself changes.
CHIEF_REFERENCE = [
    (25.25, 77),
    (23.5, 77),
    (14.75, 77),
    (13.5, 79),
    (23.75, 77),
    (19.75, 77),
    (18.5, 77),
]

MASK_OFFSETS = {
    "blue": (24, -47),  # playtest: up 10 (too low on adults)
    "orange": (21, -44),  # playtest: up 10
    "red": (21, -60),  # playtest: up 10
    "purple": (4, -48),  # playtest: up 10
    # Chief is a PACKED ATLAS, not a strip. Its seven frames sit at irregular
    # x and in two vertical rows -- solving for a single cell origin is
    # infeasible (frame 0 requires ox <= -4 while frame 3 requires ox >= 4), so
    # no grid can cut it. The packing therefore carries no alignment
    # information, and its mockup cannot supply it either: that mockup is not a
    # straight overlay, and on the facings where this mask covers the head
    # completely there is no hair left to locate a head against.
    #
    # So chief's frames are separated individually and placed from the four
    # colours that ARE verified: each frame is centred and sat on the per-facing
    # median of their mask centre and chin. Those four reconstruct their own
    # mockups essentially pixel-for-pixel, so this is a measurement against
    # known-good art rather than a guess.
    "chief": PACKED,
}


def _frame_offsets(colour: str) -> list[tuple[int, int]]:
    value = MASK_OFFSETS[colour]
    if value is PACKED:
        raise ValueError(f"{colour} is a packed atlas; it has no grid offset")
    if isinstance(value, list):
        if len(value) != FACINGS:
            raise ValueError(f"{colour}: expected {FACINGS} per-frame offsets")
        return value
    return [value] * FACINGS


GRIDDED = [c for c in ("blue", "orange", "red", "purple") if MASK_OFFSETS[c] is not PACKED]


def _islands(image: Image.Image, min_px: int = 16) -> list[tuple[int, int, int, int]]:
    """Bounding boxes of the image's separate blobs, left to right."""
    pixels = image.load()
    w, h = image.size
    seen: set[tuple[int, int]] = set()
    out: list[tuple[int, int, int, int]] = []
    for y in range(h):
        for x in range(w):
            if pixels[x, y][3] <= 128 or (x, y) in seen:
                continue
            stack = [(x, y)]
            seen.add((x, y))
            blob = []
            while stack:
                cx, cy = stack.pop()
                blob.append((cx, cy))
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        nx, ny = cx + dx, cy + dy
                        if (
                            0 <= nx < w
                            and 0 <= ny < h
                            and (nx, ny) not in seen
                            and pixels[nx, ny][3] > 128
                        ):
                            seen.add((nx, ny))
                            stack.append((nx, ny))
            if len(blob) >= min_px:
                xs = [a for a, _ in blob]
                ys = [b for _, b in blob]
                out.append((min(xs), min(ys), max(xs) + 1, max(ys) + 1))
    out.sort()
    return out


_REFERENCE_CACHE: list[tuple[float, int]] | None = None


def _reference_placement() -> list[tuple[float, int]]:
    """Per facing, the verified colours' median mask centre-x and chin-y,
    measured in the built sheet's own coordinates."""
    import statistics

    global _REFERENCE_CACHE
    if _REFERENCE_CACHE is not None:
        return _REFERENCE_CACHE
    sheets = {c: _sheet(c) for c in GRIDDED}
    out = []
    for facing in range(FACINGS):
        centres, chins = [], []
        for c in GRIDDED:
            cell = sheets[c].crop(
                (CELL_W * facing, 0, CELL_W * (facing + 1), SHEET_CELL_H)
            )
            box = cell.getbbox()
            centres.append((box[0] + box[2]) / 2)
            chins.append(box[3])
        out.append((statistics.median(centres), int(statistics.median(chins))))
    _REFERENCE_CACHE = out
    return out

# The draw hook blits one cell per villager. The cell must span every colour's
# art, so its top sits at the highest (most negative) offset and its height
# covers the lowest extent. Both are asserted in build() rather than hardcoded
# blind, so new art that does not fit fails loudly instead of being clipped.
# Where the cell's top sits relative to the head cell's top. It is a chosen
# constant rather than a derived minimum because the packed atlas is placed by
# measurement, not by an offset, and its plumes are the tallest art here -- the
# cell has to carry them. _sheet() raises if any colour will not fit, so this
# cannot silently clip.
CELL_TOP = -85
SHEET_CELL_H = 160

# build_vv1_origins_feature.py must agree with these two, and asserts so.
DRAW_Y_OFFSET = 0x27 + CELL_TOP  # native head draws at +0x27 (39); 39-85 = -46

PREVIEW_FRAME = 5           # front-facing column, same as HEAD_FRAME in
PREVIEW_BG = (236, 236, 236)  # build_vv1_appearance_bitmaps.py
PREVIEW_CELL_H = HEAD_CELL_H
# Cross-game mask-size parity (VV2 = canonical reference): every game autocrops
# the front-frame mask blob and fits it into a (40 - 2*PAD) x (65 - 2*PAD) box
# with PAD = 2 (~90% fill of the 40x65 source cell), scaling UP small blobs as
# well as down. That keeps the on-screen mask footprint identical across all
# five games' Change Appearance pickers regardless of each atlas's native size.
PREVIEW_PAD = 2


# A facing's cell must contain that facing's mask and nothing else. Art wider
# than the 40px cell means a neighbouring facing can bleed a few pixels into
# this column, and because the two facings sit at different offsets the bleed
# lands detached from the mask -- in game that reads as specks floating above
# the villager. Anything this small next to the real mask is bleed, never art;
# a fragment above the threshold is not silently dropped, it raises.
BLEED_MAX_FRACTION = 0.10


def _strip_bleed(cell: Image.Image, colour: str, facing: int) -> Image.Image:
    """Keep the facing's own mask; drop detached crumbs from its neighbours."""
    pixels = cell.load()
    w, h = cell.size
    seen: set[tuple[int, int]] = set()
    groups: list[list[tuple[int, int]]] = []
    for y in range(h):
        for x in range(w):
            if pixels[x, y][3] <= 128 or (x, y) in seen:
                continue
            stack = [(x, y)]
            seen.add((x, y))
            group = []
            while stack:
                cx, cy = stack.pop()
                group.append((cx, cy))
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        nx, ny = cx + dx, cy + dy
                        if (
                            0 <= nx < w
                            and 0 <= ny < h
                            and (nx, ny) not in seen
                            and pixels[nx, ny][3] > 128
                        ):
                            seen.add((nx, ny))
                            stack.append((nx, ny))
            groups.append(group)
    if len(groups) <= 1:
        return cell
    groups.sort(key=len, reverse=True)
    keep = groups[0]
    for group in groups[1:]:
        if len(group) > len(keep) * BLEED_MAX_FRACTION:
            raise ValueError(
                f"{colour} facing {facing}: detached region of {len(group)}px "
                f"next to a {len(keep)}px mask is too large to be neighbour "
                "bleed -- check the offsets before dropping it"
            )
        for x, y in group:
            pixels[x, y] = (0, 0, 0, 0)
    return cell


def _keep_main_blob(cell: Image.Image) -> Image.Image:
    """Return a copy of `cell` with only its largest connected blob kept; any
    detached crumbs (neighbour-frame bleed) are cleared to transparent. Uses
    alpha > 0 so even faint bleed the >128 bleed-stripper missed is removed.
    Used for the picker preview, where a single clean mask is what matters."""
    out = cell.copy()
    px = out.load()
    w, h = out.size
    seen = [[False] * h for _ in range(w)]
    groups: list[list[tuple[int, int]]] = []
    for x in range(w):
        for y in range(h):
            if px[x, y][3] == 0 or seen[x][y]:
                continue
            stack = [(x, y)]
            seen[x][y] = True
            g = []
            while stack:
                cx, cy = stack.pop()
                g.append((cx, cy))
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        nx, ny = cx + dx, cy + dy
                        if 0 <= nx < w and 0 <= ny < h and not seen[nx][ny] and px[nx, ny][3] > 0:
                            seen[nx][ny] = True
                            stack.append((nx, ny))
            groups.append(g)
    if len(groups) <= 1:
        return out
    groups.sort(key=len, reverse=True)
    for g in groups[1:]:
        for x, y in g:
            px[x, y] = (0, 0, 0, 0)
    return out


def _sheet(colour: str) -> Image.Image:
    """The colour's art placed on the 7x40 cell grid, used verbatim.

    Each facing is taken as the 40-wide column of the art that corresponds to
    that head cell and placed at its own offset. Art wider than the cell is
    clipped at the cell edge, which is what the game does too: the draw hook
    blits exactly one 40-wide cell.
    """
    art = Image.open(ART_DIR / f"{colour}.png").convert("RGBA")
    sheet = Image.new("RGBA", (CELL_W * FACINGS, SHEET_CELL_H), (0, 0, 0, 0))
    if MASK_OFFSETS[colour] is PACKED:
        boxes = _islands(art)
        if len(boxes) != FACINGS:
            raise ValueError(
                f"{colour}: found {len(boxes)} frames in the packed atlas, "
                f"expected {FACINGS}"
            )
        for facing, box in enumerate(boxes):
            frame = art.crop(box)
            centre, chin = CHIEF_REFERENCE[facing]
            x = int(round(CELL_W * facing + centre - frame.width / 2)) + CHIEF_DX
            # CHIEF_DY lifts every packed chief frame uniformly (playtest: the
            # chief sat 25px too low in the multi-villager village view).
            y = chin - frame.height - CHIEF_DY
            # Clamp the frame fully inside its own 40px cell so NOTHING is cut
            # off at the cell edge in the village blit (the frames are <=33px
            # wide, so this only nudges a 1px overhang inward -- no real move).
            cell_lo = CELL_W * facing
            x = max(cell_lo, min(x, cell_lo + CELL_W - frame.width))
            y = max(0, min(y, SHEET_CELL_H - frame.height))
            # Clip each packed frame to its OWN 40px cell. Chief frames are
            # wider than the cell and centred, so without this they spill into
            # the neighbouring cells -- which is the in-village "horizontal
            # bleed" and the preview's intruding art (a neighbour frame's edge
            # showing up in this cell). The village blits exactly one 40px cell,
            # so clipping here loses nothing that was ever visible.
            # Clip to the cell (removes any spill into neighbours) but keep ALL
            # of THIS frame's own pixels -- the chief's feathers are several
            # disconnected blobs, so we must NOT run _keep_main_blob here or the
            # detached feather tips get dropped and the mask looks cut off.
            clipped = Image.new("RGBA", (CELL_W, SHEET_CELL_H), (0, 0, 0, 0))
            clipped.alpha_composite(frame, (x - CELL_W * facing, y))
            sheet.alpha_composite(clipped, (CELL_W * facing, 0))
        return sheet
    for facing, (ox, oy) in enumerate(_frame_offsets(colour)):
        top = oy - CELL_TOP
        if top < 0 or top + art.height > SHEET_CELL_H:
            raise ValueError(
                f"{colour} facing {facing}: art at y={oy} needs a cell taller "
                f"than {SHEET_CELL_H}; raise SHEET_CELL_H (and DRAW_Y_OFFSET) "
                "rather than cropping"
            )
        src_x = CELL_W * facing - ox
        column = art.crop((src_x, 0, src_x + CELL_W, art.height)).copy()
        cell = Image.new("RGBA", (CELL_W, SHEET_CELL_H), (0, 0, 0, 0))
        cell.alpha_composite(column, (0, top))
        # _strip_bleed drops detached neighbour crumbs at alpha>128; follow with
        # _keep_main_blob (alpha>0) to also clear faint sub-threshold bleed that
        # otherwise shows as a thin horizontal smear beside the villager. The
        # gridded-verbatim test caps how much may be removed, so this can't eat
        # a real part of the mask.
        cleaned = _keep_main_blob(_strip_bleed(cell, colour, facing))
        sheet.alpha_composite(cleaned, (CELL_W * facing, 0))
    return sheet


def build_preview_strip(sheets: dict[str, Image.Image]) -> bytes:
    """40x(65*6) BMP for the Change Appearance picker: row 0 blank, then each
    mask head-on, fitted to the cell VV5's picker uses so both games' previews
    render at the same size."""
    rows = 1 + len(COLOURS)
    strip = Image.new("RGB", (CELL_W, PREVIEW_CELL_H * rows), PREVIEW_BG)
    for index, colour in enumerate(COLOURS, start=1):
        if MASK_OFFSETS[colour] is PACKED:
            # Chief: use the FULL isolated front frame (all feathers, no cell
            # clip and no blob-culling) so the ENTIRE mask renders in the picker.
            src = Image.open(ART_DIR / f"{colour}.png").convert("RGBA")
            cell = src.crop(_islands(src)[PREVIEW_FRAME])
        else:
            # Gridded: the sheet cell is already bleed-cleaned in _sheet().
            cell = sheets[colour].crop(
                (
                    PREVIEW_FRAME * CELL_W,
                    0,
                    (PREVIEW_FRAME + 1) * CELL_W,
                    SHEET_CELL_H,
                )
            )
        bbox = cell.getbbox()
        art = cell.crop(bbox) if bbox else cell
        # Normalize to ~90% fill of the 40x65 cell (PAD inset on every side),
        # scaling UP as well as down so a small blob matches the other games'
        # footprint -- no 1.0 cap. See PREVIEW_PAD above.
        avail_w = CELL_W - 2 * PREVIEW_PAD
        avail_h = PREVIEW_CELL_H - 2 * PREVIEW_PAD
        scale = min(avail_w / art.width, avail_h / art.height)
        new_w = max(1, round(art.width * scale))
        new_h = max(1, round(art.height * scale))
        if (new_w, new_h) != (art.width, art.height):
            # NEAREST, not LANCZOS: the source is ~40px pixel art and the picker
            # upscales it into a 70/50px box, so a smooth resample here blurs the
            # mask (the owner's "looks terrible") while Body/Head -- which are NOT
            # pre-scaled and just get StretchBlt COLORONCOLOR -- stay crisp.
            # Nearest keeps hard pixel edges and matches that crispness.
            art = art.resize((new_w, new_h), Image.NEAREST)
        flat = Image.new("RGB", (CELL_W, PREVIEW_CELL_H), PREVIEW_BG)
        flat.paste(
            art,
            ((CELL_W - art.width) // 2, (PREVIEW_CELL_H - art.height) // 2),
            art,
        )
        strip.paste(flat, (0, PREVIEW_CELL_H * index))
    buf = io.BytesIO()
    strip.save(buf, "BMP")
    return buf.getvalue()


def build_atlas(sheets: dict[str, Image.Image]) -> bytes:
    """All five masks in one COLS x ROWS grid: row = mask value - 1."""
    atlas = Image.new(
        "RGBA", (CELL_W * FACINGS, SHEET_CELL_H * len(COLOURS)), (0, 0, 0, 0)
    )
    for index, colour in enumerate(COLOURS):
        atlas.paste(sheets[colour], (0, SHEET_CELL_H * index))
    buf = io.BytesIO()
    atlas.save(buf, "PNG")
    return buf.getvalue()


def build() -> list[tuple[Path, bytes]]:
    sheets = {colour: _sheet(colour) for colour in COLOURS}
    out: list[tuple[Path, bytes]] = []
    for index, colour in enumerate(COLOURS, start=1):
        buf = io.BytesIO()
        sheets[colour].save(buf, "PNG")
        out.append((OUT_DIR / f"m{index}.png", buf.getvalue()))
    out.append((ATLAS_PNG, build_atlas(sheets)))
    out.append((PREVIEW_BMP, build_preview_strip(sheets)))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="verify committed output")
    args = ap.parse_args()
    built = build()
    if args.check:
        bad = [str(p) for p, data in built if not p.exists() or p.read_bytes() != data]
        if bad:
            print("stale/missing mask output: " + ", ".join(bad))
            return 1
        print(f"{len(built)} mask outputs match the generator")
        return 0
    for path, data in built:
        path.write_bytes(data)
        print(f"wrote {path.relative_to(ROOT)} ({len(data)} bytes)")
    print(
        f"sheets: {FACINGS} facings x {CELL_W}x{SHEET_CELL_H}, supplied art used "
        f"verbatim; draw Y offset {DRAW_Y_OFFSET}"
    )
    print(
        f"atlas: {FACINGS} cols x {len(COLOURS)} rows of {CELL_W}x{SHEET_CELL_H} "
        f"= {CELL_W * FACINGS}x{SHEET_CELL_H * len(COLOURS)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
