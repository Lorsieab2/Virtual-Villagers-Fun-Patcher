"""Build the VV1 Change Appearance preview strips from the stock game art.

The source sheets come from the user-supplied VV1 install under the ignored
research/ tree (research/vv1-appearance-source/); only the small derived BMP
strips below are committed as runtime assets, the same convention already
used by extract_vv1_origins_icons.py for the Tech-screen icon set.

Cell geometry (40x65 per cell, one frame column, twenty variant rows) is not
guessed: it is exactly what the stock executable's own sprite-sheet loader
computes for these files. Decompiling the loader (sub_40A070 for the single-
file head sheets, sub_40A0F0 for the four-file body sheets) at
inputs/vv1-stock-copy/Virtual Villagers - A New Home.exe shows:

  male_heads.png / female_heads.png (280x1300, one file):
    registered with explicit column/row counts 7 and 20 -- cell width
    280/7 = 40, cell height 1300/20 = 65. Column = animation frame,
    row = the villager record's head index (0..19; male villagers are only
    ever randomized into 0..18, per the RNG(19) vs RNG(20) split already
    confirmed for VV_HEAD_OFFSET/VV_CLOTHING_OFFSET in vv1_origins_icons.c).

  male_bodiesCR.png / female_bodiesCR.png (640x650, four files per gender,
  C,R in {0,1}): registered as a 2x2 grid of files, each internally
  16 columns x 10 rows of 40x65 cells (640/16 = 40, 650/10 = 65) -- so the
  full logical sheet is 32 frame-columns x 20 variant-rows, split into
  filename "<prefix><col-block><row-block><suffix>" quadrants. Column 0
  (the preview frame this dialog wants) always lives in col-block 0, so
  only the two row-block files (*bodies00, *bodies01) are ever needed: rows
  0-9 come from *bodies00's own rows 0-9, rows 10-19 from *bodies01's own
  rows 0-9 (its local row = global row - 10).

Cropping one column out of each source therefore needs no per-cell loop --
it is one rect crop per source file, described below.

Frame choice: column 0 is not a resting pose for either sheet -- each row
is a walk-cycle animation (confirmed by inspecting every column of a row
side by side), and column 0 happens to be a mid-stride frame for the body
sheet (torso leaning, one leg forward) that reads as visibly wrong when
frozen as a single still preview image, rather than a clean standing
portrait. HEAD_FRAME=5 and BODY_FRAME=8 were picked by inspecting every
column of row 0 side by side and choosing the ones that read as a
neutral/standing pose instead of a mid-motion one.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "research" / "vv1-appearance-source"
OUTPUT = ROOT / "native" / "vv1_origins_icons" / "appearance"

CELL_W = 40
CELL_H = 65
ROWS_PER_BODY_FILE = 10
TOTAL_ROWS = 20
BACKGROUND = (236, 236, 236)
HEAD_FRAME = 5
BODY_FRAME = 8


def _flatten(image: Image.Image) -> Image.Image:
    """Composite RGBA onto the same neutral background the picker's
    WM_DRAWITEM fill uses, since a classic 24bpp resource BMP has no alpha
    channel."""
    canvas = Image.new("RGB", image.size, BACKGROUND)
    canvas.paste(image.convert("RGBA"), (0, 0), image.convert("RGBA"))
    return canvas


def _head_strip(gender: str) -> Image.Image:
    source = Image.open(SOURCE / f"{gender}_heads.png")
    if source.size != (CELL_W * 7, CELL_H * TOTAL_ROWS):
        raise ValueError(f"unexpected {gender}_heads.png size: {source.size}")
    left = CELL_W * HEAD_FRAME
    return _flatten(source.crop((left, 0, left + CELL_W, CELL_H * TOTAL_ROWS)))


def _body_strip(gender: str) -> Image.Image:
    strip = Image.new("RGB", (CELL_W, CELL_H * TOTAL_ROWS), BACKGROUND)
    left = CELL_W * BODY_FRAME
    for row_block, y_offset in ((0, 0), (1, CELL_H * ROWS_PER_BODY_FILE)):
        source = Image.open(SOURCE / f"{gender}_bodies0{row_block}.png")
        if source.size != (CELL_W * 16, CELL_H * ROWS_PER_BODY_FILE):
            raise ValueError(
                f"unexpected {gender}_bodies0{row_block}.png size: {source.size}"
            )
        block = _flatten(
            source.crop((left, 0, left + CELL_W, CELL_H * ROWS_PER_BODY_FILE))
        )
        strip.paste(block, (0, y_offset))
    return strip


def main() -> int:
    if not SOURCE.is_dir():
        raise SystemExit(
            f"missing source tree: {SOURCE}\n"
            "Copy male_heads.png, female_heads.png, male_bodies00.png, "
            "male_bodies01.png, female_bodies00.png, female_bodies01.png "
            "from a real VV1 install's Images/ folder there first."
        )
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for gender in ("male", "female"):
        head = _head_strip(gender)
        head.save(OUTPUT / f"head_{gender[0]}.bmp")
        body = _body_strip(gender)
        body.save(OUTPUT / f"body_{gender[0]}.bmp")
    print(f"Wrote 4 appearance strips ({CELL_W}x{CELL_H * TOTAL_ROWS} each) to {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
