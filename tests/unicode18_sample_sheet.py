"""Render sample sheets of the bundled fonts' glyphs beside the game's own text (Unicode 18.0 styling).

    python tests/unicode18_sample_sheet.py [output folder]     (default: outputs\\ of the checkout, never committed)

Each sheet is one game, run in unicorn with the companion; the player's Windows fonts are hidden from the companion
(unicode_text_emulation.ONLY_BUNDLED_FONTS), so every non-ASCII character below is drawn by a bundled font and
styled by the runtime glyph maker: scaled to the game font's cap height, on its baseline, smoothed and thickened
(Unifont), quantised to the font's own alpha levels, tinted by the game's own text colour.  Rows: the game's own
letters (ASCII), then the same line followed by CJK, cuneiform, Tangut and a character only Last Resort draws.
Needs the stock executables and game images under research\\ (they are the owner's, never committed), unicorn
and Windows.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

ROWS = (
    "Hello World 0123 Zoe",
    "Hello 世界日本語 한국어",
    "Hello \U00012000\U00012001\U0001223e\U00012362 \U00017000\U00017001\U00017002",
    "Hello \U00020000\U00020001 \U00013000 \U0001F4A9",
)
GREEN = (40, 60, 40)


def sheet(game: str, out: Path) -> list[Path]:
    import unicode18_coverage  # noqa: F401
    import unicode_text_emulation as ute
    import unicode_utf8_emulation as ue
    from vv_picture_image import Image, encode_png
    ute.ONLY_BUNDLED_FONTS = True
    tables = json.loads((ROOT / "data" / "font_glyph_tables.json").read_text(encoding="utf-8"))
    run = ue.TextRun(game, (f"{game}_unicode_text", f"{game}_details_full_names"), tables)
    paths = []
    for font in ("ldwBurweed27", "ldwarialbold"):
        blits = []
        step = 60
        for n, text in enumerate(ROWS):
            blits += run.draw_text(font, text.encode("utf-8"), 20, 15 + n * step, 0xFFFFFFFF)
        size = (900, 15 + len(ROWS) * step + 10)
        data = ue.composite(run, blits, size)
        path = out / f"Unicode 18 bundled fonts - {game} {font}.png"
        path.write_bytes(encode_png(Image(size[0], size[1], bytearray(data))))
        paths.append(path)
    return paths


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "outputs"
    out.mkdir(parents=True, exist_ok=True)
    for game in ("vv1", "vv3"):
        for path in sheet(game, out):
            print(path)


if __name__ == "__main__":
    main()
