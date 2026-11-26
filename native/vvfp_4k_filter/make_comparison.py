"""Before/after pictures for the 4K filter (research prototype, not shipped).

usage: python -I make_comparison.py <folder with vv4k_upscale.exe> <output folder> [<display w> <display h>
                                    [<Windows display scaling, e.g. 1.5>]]
       python -I make_comparison.py png <picture.argb> <w> <h> <out.png>

Builds three test frames from the games' own art in this repository, runs every candidate filter (the CPU reference,
vv4k_filters.c) to the display size (default 3840x2160), and writes for each frame:
  <frame>.native.png                 the frame as the game draws it (800x600 or 1024x768)
  <frame>.<filter>.png               the whole display picture
  <frame>.compare.png                the same detail of every candidate side by side, at 1:1 display pixels
The frames:
  vv1_scene      A New Home's map (two of its own map pictures, MapX2Y1.jpg and MapX1Y2.jpg, JPEG as the game ships
                 them), its restored garden, and villager heads from its head sheet: 800x600 like the game
  vv4_options    The Tree of Life's Options window (docs/vv4-difficulty-options-preview.png, the game's own art and
                 font): 800x600 like the game
  vv5_upgrades   New Believers' upgrades screen mock-up (assets/candidates/vv5_full_mastery/provenance/VV5Mockup.jpg,
                 a JPEG -- it carries JPEG noise the live game does not have): 1024x768 like the game
"""
from __future__ import annotations

import struct
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
FILTERS = ["stock-nearest", "bilinear", "sharp-pixels", "edge-directed", "edge-directed-2x"]
LABELS = {
    "stock-nearest": "A. today (SDL nearest, uneven pixels)",
    "bilinear": "B. plain smooth (bilinear)",
    "sharp-pixels": "C. sharp pixels (integer + fit)",
    "edge-directed": "D. edge-directed 4x + fit (proposed)",
    "edge-directed-2x": "E. edge-directed 2x + fit (faster)",
}


def to_argb(image: Image.Image) -> bytes:
    # 0xAARRGGBB little-endian is B, G, R, A in memory; alpha 0xFF.
    r, g, b = image.convert("RGB").split()
    return Image.merge("RGBA", (b, g, r, Image.new("L", image.size, 255))).tobytes()


def from_argb(data: bytes, w: int, h: int) -> Image.Image:
    # 0xAARRGGBB little-endian is B, G, R, A in memory.
    return Image.frombuffer("RGBA", (w, h), data, "raw", "BGRA", 0, 1).convert("RGB")


def vv1_scene() -> Image.Image:
    images = ROOT / "data" / "vv1_visual_mods" / "base" / "Images"
    frame = Image.new("RGB", (800, 600))
    frame.paste(Image.open(images / "MapX2Y1.jpg").convert("RGB"), (0, 0))
    frame.paste(Image.open(images / "MapX1Y2.jpg").convert("RGB").crop((0, 0, 288, 512)), (512, 0))
    bottom = Image.open(images / "MapX1Y2.jpg").convert("RGB").crop((0, 424, 512, 512))
    frame.paste(bottom, (0, 512))
    frame.paste(bottom.crop((0, 0, 288, 88)), (512, 512))
    garden = Image.open(images / "garden_restored.png").convert("RGBA")
    frame.paste(garden, (430, 250), garden)
    # Villager heads from A New Home's head sheet (7 columns x 20 rows of 40 x 65 cells), standing in a row.
    sheet = Image.open(ROOT / "assets" / "vv1_grey_hair" / "young_female_reference.png").convert("RGBA")
    males = Image.open(ROOT / "assets" / "vv1_grey_hair" / "young_male_reference.png").convert("RGBA")
    x = 250
    for n, (src, row, col) in enumerate([(sheet, 0, 5), (males, 2, 5), (sheet, 4, 6), (males, 7, 4), (sheet, 12, 5),
                                         (males, 15, 6)]):
        cell = src.crop((col * 40, row * 65, col * 40 + 40, row * 65 + 65))
        frame.paste(cell, (x + n * 48, 470 + (n % 2) * 14), cell)
    return frame


def frames() -> dict[str, Image.Image]:
    return {
        "vv1_scene": vv1_scene(),
        "vv4_options": Image.open(ROOT / "docs" / "vv4-difficulty-options-preview.png").convert("RGB"),
        "vv5_upgrades": Image.open(ROOT / "assets" / "candidates" / "vv5_full_mastery" / "provenance" /
                                   "VV5Mockup.jpg").convert("RGB"),
    }


# The detail shown side by side for each frame: (x, y) in the native frame, size in native pixels.
DETAILS = {"vv1_scene": (250, 400, 200), "vv4_options": (120, 270, 200), "vv5_upgrades": (0, 0, 200)}


def compare_sheet(name: str, outputs: dict[str, Image.Image], frame: Image.Image, dw: int, dh: int) -> Image.Image:
    fw, fh = frame.size
    scale = min(dw / fw, dh / fh)
    ox, oy = (dw - fw * scale) / 2, (dh - fh * scale) / 2
    x, y, size = DETAILS[name]
    box = (int(ox + x * scale), int(oy + y * scale), int(ox + (x + size) * scale), int(oy + (y + size * 0.75) * scale))
    tile_w, tile_h = box[2] - box[0], box[3] - box[1]
    rows = (len(FILTERS) + 1) // 2
    sheet = Image.new("RGB", (tile_w * 2 + 30, (tile_h + 40) * rows + 10), (24, 24, 24))
    draw = ImageDraw.Draw(sheet)
    for n, f in enumerate(FILTERS):
        cx, cy = 10 + (n % 2) * (tile_w + 10), 10 + (n // 2) * (tile_h + 40)
        sheet.paste(outputs[f].crop(box), (cx, cy + 26))
        draw.text((cx, cy + 6), LABELS[f], fill=(240, 240, 240))
    return sheet


def main() -> int:
    if sys.argv[1] == "png":   # png <picture.argb> <w> <h> <out.png>: e.g. the GPU probe's picture
        w, h = int(sys.argv[3]), int(sys.argv[4])
        from_argb(Path(sys.argv[2]).read_bytes(), w, h).save(sys.argv[5])
        return 0
    tools, out = Path(sys.argv[1]), Path(sys.argv[2])
    dw, dh = (int(sys.argv[3]), int(sys.argv[4])) if len(sys.argv) > 4 else (3840, 2160)
    out.mkdir(parents=True, exist_ok=True)
    for name, frame in frames().items():
        frame.save(out / f"{name}.native.png")
        raw = out / f"{name}.argb"
        raw.write_bytes(to_argb(frame))
        prefix = out / f"{name}.{dw}x{dh}"
        result = subprocess.run([str(tools / "vv4k_upscale.exe"), str(raw), str(frame.size[0]), str(frame.size[1]),
                                 str(dw), str(dh), str(prefix)], capture_output=True, text=True, check=True)
        print(name, frame.size)
        print(result.stdout.rstrip())
        outputs = {}
        for f in FILTERS:
            path = Path(f"{prefix}.{f}.argb")
            outputs[f] = from_argb(path.read_bytes(), dw, dh)
            outputs[f].save(out / f"{name}.{dw}x{dh}.{f}.png", optimize=False)
            path.unlink()
        compare_sheet(name, outputs, frame, dw, dh).save(out / f"{name}.{dw}x{dh}.compare.png")
        if len(sys.argv) > 5:
            # Today on a display with Windows scaling (e.g. 1.5 = 150%): the games are not DPI aware, so SDL draws
            # nearest-neighbour into a window of the scaled-down size and Windows stretches that (bilinear) to the
            # real pixels.
            s = float(sys.argv[5])
            vw, vh = round(dw / s), round(dh / s)
            k = min(vw / frame.size[0], vh / frame.size[1])
            small = frame.resize((round(frame.size[0] * k), round(frame.size[1] * k)), Image.NEAREST)
            big = small.resize((round(small.size[0] * s), round(small.size[1] * s)), Image.BILINEAR)
            today = Image.new("RGB", (dw, dh))
            today.paste(big, ((dw - big.size[0]) // 2, (dh - big.size[1]) // 2))
            today.save(out / f"{name}.{dw}x{dh}.today-at-{round(s * 100)}pct-scaling.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
