"""Print the stock The Secret City pictures' sizes as a Python dict (for src/vv_assets_vv3.py SIZES).

Reads only the headers of research/game-images/<title>/Images (PNG IHDR, JPEG SOF via src/vv_jpeg.py)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_pictures_assets as pa  # noqa: E402

IMAGES = ROOT / "research" / "game-images" / "Virtual Villagers - The Secret City" / "Images"


def sizes() -> dict:
    out = {}
    for p in sorted(IMAGES.iterdir(), key=lambda p: p.name.casefold()):
        if p.suffix.casefold() in pa.PICTURE_EXTENSIONS:
            out[p.name] = pa.picture_size(p.read_bytes())
    return out


if __name__ == "__main__":
    items = list(sizes().items())
    line = "    "
    print("SIZES = {")
    for name, (w, h) in items:
        piece = f"{name!r}: ({w}, {h}), "
        if len(line) + len(piece) > 116:
            print(line.rstrip())
            line = "    "
        line += piece
    print(line.rstrip())
    print("}")
