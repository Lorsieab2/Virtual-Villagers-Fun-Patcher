"""The art of "Grey Hair at 55" (A New Home): check the two grey head sheets and write the Change
Appearance picker's preview strips from them.

THE SHEETS (assets/vv1_grey_hair/, shipped to the game's Images folder under the same names):

    vvfp_grey_male_heads.png      the men's grey heads
    vvfp_grey_female_heads.png    the women's grey heads

Each must be exactly the stock layout of A New Home's own male_heads.png / female_heads.png
(young_male_reference.png / young_female_reference.png beside them are those stock sheets): a PNG of
280 x 1300 pixels with an alpha channel, 7 columns x 20 rows of 40 x 65 cells; the row is the head
value 0..19 and the columns are the same facings and frames as the stock sheet's.  A sheet of any
other size is refused here, and by the DLL in the game (which then keeps that sex's young heads).

THE PREVIEWS: column 5 of each sheet (the column the stock Change Appearance strips are cut from,
scripts/build_vv1_appearance_bitmaps.py), flattened onto the picker's grey (236, 236, 236), as
native/vv1_grey_hair/preview/head_m_grey.bmp and head_f_grey.bmp, compiled into the DLL.

THE PLACEHOLDER.  PLACEHOLDER_grey_male.png / PLACEHOLDER_grey_female.png are a machine-made mockup,
for building and testing only.  While a shipped sheet is byte-for-byte one of them,
placeholder_sheets() names it and scripts/build_release.py refuses to build a release.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "assets" / "vv1_grey_hair"
PREVIEW = ROOT / "native" / "vv1_grey_hair" / "preview"
SHEETS = {"male": ART / "vvfp_grey_male_heads.png", "female": ART / "vvfp_grey_female_heads.png"}
PLACEHOLDERS = (ART / "PLACEHOLDER_grey_male.png", ART / "PLACEHOLDER_grey_female.png")
PREVIEWS = {"male": PREVIEW / "head_m_grey.bmp", "female": PREVIEW / "head_f_grey.bmp"}
SIZE = (280, 1300)
CELL_W, CELL_H = 40, 65
HEAD_FRAME = 5
BACKGROUND = (236, 236, 236)


def load_sheet(path: Path) -> Image.Image:
    """The sheet at `path` as RGBA; ValueError unless it is a 280 x 1300 PNG."""
    with Image.open(path) as image:
        if image.format != "PNG":
            raise ValueError(f"{path.name}: not a PNG ({image.format})")
        if image.size != SIZE:
            raise ValueError(f"{path.name}: {image.size[0]} x {image.size[1]} pixels; a grey head sheet must be "
                             f"exactly {SIZE[0]} x {SIZE[1]} (7 x 20 cells of {CELL_W} x {CELL_H})")
        return image.convert("RGBA")


def preview_strip(sheet: Image.Image) -> Image.Image:
    """Column 5, flattened onto the picker's grey: 40 x 1300, one 65-pixel row per head."""
    column = sheet.crop((CELL_W * HEAD_FRAME, 0, CELL_W * (HEAD_FRAME + 1), SIZE[1]))
    canvas = Image.new("RGB", column.size, BACKGROUND)
    canvas.paste(column, (0, 0), column)
    return canvas


def placeholder_sheets() -> list[str]:
    """The shipped sheets that are still a PLACEHOLDER file, byte for byte."""
    placeholders = {p.read_bytes() for p in PLACEHOLDERS if p.is_file()}
    return [str(p.relative_to(ROOT)).replace("\\", "/") for p in SHEETS.values()
            if p.is_file() and p.read_bytes() in placeholders]


def main() -> int:
    PREVIEW.mkdir(parents=True, exist_ok=True)
    for sex, path in SHEETS.items():
        preview_strip(load_sheet(path)).save(PREVIEWS[sex])
    for name in placeholder_sheets():
        print(f"NOTE: {name} is still the PLACEHOLDER art; scripts/build_release.py will refuse a release.")
    print("wrote", ", ".join(str(p.relative_to(ROOT)) for p in PREVIEWS.values()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
