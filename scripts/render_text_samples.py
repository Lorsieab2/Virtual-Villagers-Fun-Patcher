"""Render Picture Studio Text samples for every game and font (docs/picture-studio-text.md "Samples").

    python scripts/render_text_samples.py [output folder] [game folder root]

The game folder root holds "Virtual Villagers - <title>\\Images" for each game (default: research\\game-images,
a copy of the games' Images folders; never shipped).  Each sample is written twice: as the PNG Picture Studio
saves (transparent, 2x) and as a preview on a dark background with the made glyphs outlined.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_picture_image as pi  # noqa: E402
import vv_pictures_text as text  # noqa: E402

SAMPLES = {
    "1 Plain": "Welcome to the island!\nThe quick brown fox jumps over the lazy dog 0123456789",
    "2 Accents": "Café crème brûlée, naïve Zoë, Ångström\n"
                 "Łódź, Škoda, İstanbul, ǘ, ệ, ąę, #1 & 50% (ok)",
    "3 Other scripts": "Ωμέγα  Привет  中文  "
                       "한국어\nनमस्ते  مرحبا  "
                       "สวัสดี  こんにちは",
    "4 Emoji": "Hi \U0001F44B\U0001F3FD \U0001F468‍\U0001F469‍\U0001F467 ❤️ 1️⃣ "
               "\U0001F334\U0001F965\U0001F30B ✓",
}
PREVIEW_BG = (45, 59, 76, 255)
MARKS = {text.SOURCE_PATCHER: (42, 111, 219, 255), text.SOURCE_MADE: (224, 120, 0, 255),
         text.SOURCE_EMOJI: (160, 64, 208, 255), "missing": (208, 32, 32, 255)}


def preview(rendered: text.Rendered, scale: int = 2) -> pi.Image:
    image = rendered.image
    canvas = pi.Image(image.width + 16, image.height + 16)
    canvas.data[:] = bytes(PREVIEW_BG) * (canvas.width * canvas.height)
    canvas.draw(image, 8, 8)
    canvas = canvas.scaled(scale)
    for x, y, w, h, source, _cluster in rendered.boxes:
        colour = bytes(MARKS.get(source, (255, 0, 0, 255)))
        x0, y0, x1, y1 = (x + 8) * scale, (y + 8) * scale, (x + 8 + w) * scale - 1, (y + 8 + h) * scale - 1
        for xx in range(x0, x1 + 1, 2):
            for yy in (y0, y1):
                if 0 <= xx < canvas.width and 0 <= yy < canvas.height:
                    canvas.data[(yy * canvas.width + xx) * 4:(yy * canvas.width + xx) * 4 + 4] = colour
        for yy in range(y0, y1 + 1, 2):
            for xx in (x0, x1):
                if 0 <= xx < canvas.width and 0 <= yy < canvas.height:
                    canvas.data[(yy * canvas.width + xx) * 4:(yy * canvas.width + xx) * 4 + 4] = colour
    return canvas


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else ROOT / "outputs" / "text-samples"
    art = Path(argv[1]) if len(argv) > 1 else ROOT / "research" / "game-images"
    out.mkdir(parents=True, exist_ok=True)
    written = 0
    for game, title in text.TITLES.items():
        folder = art / f"Virtual Villagers - {title}" / "Images"
        colours = text.game_colours(game)
        for info in text.font_infos(game):
            sheet_path = folder / info["sheet"]
            if not sheet_path.is_file():
                print(f"skipped {title} {info['name']}: no {sheet_path}")
                continue
            renderer = text.TextRenderer(game, info["key"], pi.decode_png(sheet_path.read_bytes()),
                                         images_dir=folder)
            for n, (label, sample) in enumerate(SAMPLES.items()):
                colour = colours[3].value if n == 0 else text.DEFAULT_COLOUR     # dark brown, then white
                rendered = renderer.render(sample, colour)
                stem = f"VV{game} {info['name'].split(' (')[0]} - {label}"
                pi.save_png(rendered.image, out / f"{stem}.png", scale=2)
                pi.save_png(preview(rendered), out / f"{stem} (preview, made glyphs outlined).png", margin=0)
                written += 2
            stock = text.game_render(renderer.font, renderer.sheet, text.game_bytes(SAMPLES["2 Accents"]))
            pi.save_png(stock, out / f"VV{game} {info['name'].split(' (')[0]} - 2 Accents (unpatched game).png",
                        scale=2)
            written += 1
    if text.ttf_installed():
        for size in (18, 48):
            renderer = text.TextRenderer(5, text.TTF_KEY, ttf_size=size)
            rendered = renderer.render(SAMPLES["2 Accents"] + "\n" + SAMPLES["4 Emoji"])
            pi.save_png(rendered.image, out / f"Burweed ICG (installed) {size}px.png")
            written += 1
    print(f"{written} pictures in {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
