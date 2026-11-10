"""Mockups of Yellow Fruit Trees are No Longer Unlimited's six stages (The Tree of Life), on the game's own map.

The companion ("VVFP VV4 Fruit Supply.dll") draws one 256 x 256 picture over the two yellow fruit trees, chosen by the
fruit left (FS_STAGES in native/vvfp_vv4_fruit_supply/vvfp_vv4_fruit_supply.c):

    assets/fruit_supply/vvfp_fruit_tree_5.png .. _0.png   5, 4, 3, 2, 1 or no fruits on each tree

each the owner's art, 8-bit RGBA, drawn with its top-left on world (0, 1664): the section (0, 128)-(256, 384) of the
map tile MapX0Y3.jpg (assets/fruit_supply/yellow_fruit_trees_map_section.png is that section as the map has it).

    python scripts/vv4_fruit_tree_mockups.py DIR

writes "Fruit trees mockup - 5 fruits.png" .. "- 1 fruit.png" and "- empty.png" into DIR: the pictures now
in assets/fruit_supply laid over the game's own map tile (research/game-images, not committed; without it, over the
section only).  Nothing else is written.

After new art: python scripts/build_vv4_yellow_fruit_trees_limited_feature.py --no-build (pins the pictures).
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "assets" / "fruit_supply"
BASE = ART / "yellow_fruit_trees_map_section.png"
PICTURE = "vvfp_fruit_tree_{}.png"
NAMES = {5: "5 fruits", 4: "4 fruits", 3: "3 fruits", 2: "2 fruits", 1: "1 fruit", 0: "empty"}
TILE = ROOT / "research" / "game-images" / "Virtual Villagers - The Tree of Life" / "Images" / "MapX0Y3.jpg"
SECTION_IN_TILE = (0, 128)


def mockups(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    if TILE.is_file():
        scene, at = Image.open(TILE).convert("RGBA"), SECTION_IN_TILE
    else:
        scene, at = Image.open(BASE).convert("RGBA"), (0, 0)
    for stage, label in NAMES.items():                 # the picture's number is its fruits on each tree
        view = scene.copy()
        view.alpha_composite(Image.open(ART / PICTURE.format(stage)).convert("RGBA"), at)
        path = out / f"Fruit trees mockup - {label}.png"
        view.convert("RGB").save(path)
        print("wrote", path)


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    mockups(Path(sys.argv[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
