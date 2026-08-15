"""Regenerate the VV2 Change Appearance head/body preview strips.

The chooser (native/vv2_origins_icons) shows a static head and body preview
cropped from the stock game's villager art.  Each source atlas lays 30 heads /
bodies out in rows of 40x65 cells with several animation frames per row across
the columns; we pick one clean, front-facing frame per part and composite it
onto the dialog background into a single 30-wide strip BMP that the DLL's
owner-draw handler blits from.

Frames (chosen for a clean, front-facing pose):
    HEAD_FRAME = 5
    BODY_FRAME = 8

Requires Pillow and the stock game's Images folder.  Example:
    python scripts/build_vv2_appearance_sheets.py \
        --images "C:/Games/Virtual Villagers - The Lost Children/Images"
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "native" / "vv2_origins_icons" / "appearance"

BG = (236, 236, 236)   # dialog face background
CW, CH = 40, 65        # source cell size
N = 30                 # heads / bodies per part
HEAD_FRAME = 5         # column within a head row used as the static pose
BODY_FRAME = 8         # column within a body row used as the static pose


def composite(cell: Image.Image) -> Image.Image:
    base = Image.new("RGBA", cell.size, BG + (255,))
    base.alpha_composite(cell)
    return base.convert("RGB")


def head_sheet(images: Path, src_name: str, out_name: str) -> None:
    im = Image.open(images / src_name).convert("RGBA")
    sheet = Image.new("RGB", (CW * N, CH), BG)
    for i in range(N):
        cell = im.crop(
            (HEAD_FRAME * CW, i * CH, HEAD_FRAME * CW + CW, i * CH + CH)
        )
        sheet.paste(composite(cell), (i * CW, 0))
    sheet.save(OUT / out_name)


def body_sheet(images: Path, sex: str, out_name: str) -> None:
    sheet = Image.new("RGB", (CW * N, CH), BG)
    for i in range(N):
        atlas = Image.open(images / f"{sex}_bodies0{i // 10}.png").convert("RGBA")
        row = i % 10
        cell = atlas.crop(
            (BODY_FRAME * CW, row * CH, BODY_FRAME * CW + CW, row * CH + CH)
        )
        sheet.paste(composite(cell), (i * CW, 0))
    sheet.save(OUT / out_name)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--images",
        type=Path,
        required=True,
        help="path to the stock game's Images folder",
    )
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    head_sheet(args.images, "male_heads.png", "head_m_young.bmp")
    head_sheet(args.images, "male_heads_old.png", "head_m_old.bmp")
    head_sheet(args.images, "female_heads.png", "head_f_young.bmp")
    head_sheet(args.images, "female_heads_old.png", "head_f_old.bmp")
    body_sheet(args.images, "male", "body_m.bmp")
    body_sheet(args.images, "female", "body_f.bmp")
    print(f"done; HEAD_FRAME={HEAD_FRAME} BODY_FRAME={BODY_FRAME}")


if __name__ == "__main__":
    main()
