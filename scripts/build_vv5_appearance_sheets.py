"""Build VV5's Change Appearance body preview strips from its Images atlases.

Each body value is one row across three 10-row pages; columns are pose frames.
The selector has 30 valid values, so the embedded preview sheets must contain
30 cells as well.  The source Images folder is supplied by the caller.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "native" / "vv5_task9_origins" / "appearance"
CELL_W, CELL_H = 40, 65
ROWS_PER_PAGE = 10
PAGE_COUNT = 3
BODY_FRAME = 8  # 0-based: the ninth column from the left.
BACKGROUND = (236, 236, 236)


def build_body_strip(images: Path, sex: str) -> Image.Image:
    strip = Image.new("RGB", (CELL_W * (ROWS_PER_PAGE * PAGE_COUNT), CELL_H), BACKGROUND)
    output_index = 0
    for page in range(PAGE_COUNT):
        atlas_path = images / f"{sex}_bodies0{page}.png"
        with Image.open(atlas_path) as opened:
            atlas = opened.convert("RGBA")
        expected_size = (CELL_W * 16, CELL_H * ROWS_PER_PAGE)
        if atlas.size != expected_size:
            raise ValueError(f"unexpected {atlas_path.name} size {atlas.size}; expected {expected_size}")
        for row in range(ROWS_PER_PAGE):
            box = (
                BODY_FRAME * CELL_W,
                row * CELL_H,
                (BODY_FRAME + 1) * CELL_W,
                (row + 1) * CELL_H,
            )
            cell = atlas.crop(box)
            if cell.getchannel("A").getbbox() is None:
                raise ValueError(f"empty sprite at {atlas_path.name}, row {row}, frame {BODY_FRAME}")
            background = Image.new("RGBA", (CELL_W, CELL_H), BACKGROUND + (255,))
            background.alpha_composite(cell)
            strip.paste(background.convert("RGB"), (output_index * CELL_W, 0))
            output_index += 1
    if output_index != ROWS_PER_PAGE * PAGE_COUNT:
        raise AssertionError(f"built {output_index} cells, expected 30")
    return strip


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images", type=Path, required=True, help="VV5 game's Images folder")
    args = parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for sex in ("male", "female"):
        output = OUTPUT / f"body_{sex[0]}.bmp"
        build_body_strip(args.images, sex).save(output, "BMP")
        print(f"{output.name}: {CELL_W * ROWS_PER_PAGE * PAGE_COUNT}x{CELL_H}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
