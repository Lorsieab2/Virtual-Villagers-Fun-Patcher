"""Extract the VV3 Change Appearance preview strips from the stock atlases.

Regenerates the six BMP resources embedded in the VV3 Origins Icons DLL for
the custom head+body chooser.  Each strip is a horizontal 24-bpp row of
40x65 cells (one per selectable index) composited on the dialog background,
matching the VV2 chooser format so ShowVV3AppearanceChooser can blit cell
`index` via StretchBlt.

The stock atlases are the game's own Images (male_heads.png etc.); pass the
game's Images directory as the only argument.  The six committed BMPs under
native/vv3_full_mastery_candidate/appearance/ are the source of truth for the
DLL build, so this script only needs to be re-run if the atlases change.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "native" / "vv3_full_mastery_candidate" / "appearance"
BACKGROUND = (236, 236, 236)
CELL_W, CELL_H = 40, 65


def _strip(cells: list[tuple[Image.Image, int]], name: str) -> None:
    image = Image.new("RGB", (CELL_W * len(cells), CELL_H), BACKGROUND)
    for index, (atlas, row) in enumerate(cells):
        cell = atlas.crop((0, row * CELL_H, CELL_W, row * CELL_H + CELL_H)).convert("RGBA")
        base = Image.new("RGBA", (CELL_W, CELL_H), BACKGROUND + (255,))
        base.alpha_composite(cell)
        image.paste(base.convert("RGB"), (index * CELL_W, 0))
    OUT.mkdir(parents=True, exist_ok=True)
    image.save(OUT / f"{name}.bmp", "BMP")
    print(f"{name}.bmp: {image.width}x{image.height}")


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: build_vv3_appearance_bmps.py <VV3 Images directory>")
        return 2
    src = Path(sys.argv[1])
    # Heads: 320x1950 atlases, 30 rows of 65 px; take frame 0 (first 40 px).
    for name, atlas in (
        ("head_m_young", "male_heads.png"),
        ("head_m_old", "male_heads_old.png"),
        ("head_f_young", "female_heads.png"),
        ("head_f_old", "female_heads_old.png"),
    ):
        image = Image.open(src / atlas)
        _strip([(image, row) for row in range(30)], name)
    # Bodies: outfits 0..29 span three 640x650 sheets (10 outfits each);
    # cell V is sheet V // 10, row V % 10, frame 0.
    for name, prefix in (("body_m", "male_bodies"), ("body_f", "female_bodies")):
        sheets = [Image.open(src / f"{prefix}0{i}.png") for i in (0, 1, 2)]
        _strip([(sheets[v // 10], v % 10) for v in range(30)], name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
