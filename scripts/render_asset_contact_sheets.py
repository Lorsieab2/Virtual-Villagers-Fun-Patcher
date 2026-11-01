"""Contact sheets of Picture Studio's Everything tab: one labelled picture per game per category (more pages for a
big category), drawn by the patcher's own renderer from research/game-images, into outputs/vv<n>/.

    python scripts/render_asset_contact_sheets.py [--game N ...] [--frames 8] [--workers 24]

A development aid (Pillow only labels the tiles); nothing here ships or reads a save.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_picture_image as pi  # noqa: E402
import vv_pictures_assets as pa  # noqa: E402

IMAGES = ROOT / "research" / "game-images"
OUT = ROOT / "outputs"
CACHE = OUT / ".everything-cache"
CELL, LABEL, GAP, COLUMNS, PER_PAGE = 150, 30, 6, 10, 300


def _folder(game: int) -> Path:
    return IMAGES / f"Virtual Villagers - {pi.GAME_FOLDERS[game]}"


def _load(game: int):
    return pa.load(game, [_folder(game)], root=CACHE)


def tiles(game: int, category: str, frames_per_asset: int) -> list[tuple[str, pi.Image]]:
    sheets, _module, assets, _problem = _load(game)
    out = []
    for asset in assets:
        if asset.category != category:
            continue
        frames = pa.frames_of(sheets, asset)
        if len(frames) > frames_per_asset:
            step = len(frames) / frames_per_asset
            frames = tuple(frames[int(i * step)] for i in range(frames_per_asset))
        for frame in frames:
            try:
                image = pa.render_frame(sheets, frame).cropped(0)
            except (pi.PictureError, OSError, ValueError) as exc:
                image = pi.Image(1, 1)
                frame = pa.Frame(f"cannot draw: {exc}", ())
            text = asset.shown + (f" | {frame.label}" if frame.label and frame.label != "whole" else "")
            out.append((text, image))
    return out


def render(job: tuple[int, str, int]) -> list[str]:
    game, category, frames_per_asset = job
    from PIL import Image as PImage, ImageDraw, ImageFont
    try:
        font = ImageFont.truetype("segoeui.ttf", 11)
    except OSError:
        font = ImageFont.load_default()
    items = tiles(game, category, frames_per_asset)
    written = []
    folder = OUT / f"vv{game}"
    folder.mkdir(parents=True, exist_ok=True)
    pages = max(1, -(-len(items) // PER_PAGE))
    for page in range(pages):
        chunk = items[page * PER_PAGE:(page + 1) * PER_PAGE]
        rows = max(1, -(-len(chunk) // COLUMNS))
        sheet = PImage.new("RGBA", (COLUMNS * (CELL + GAP) + GAP, rows * (CELL + LABEL + GAP) + GAP + 24),
                           (232, 232, 232, 255))
        draw = ImageDraw.Draw(sheet)
        draw.text((GAP, 4), f"{pi.GAME_FOLDERS[game]} - {category}"
                  + (f" (page {page + 1} of {pages})" if pages > 1 else "") + f": {len(items)} pictures",
                  fill=(0, 0, 0, 255), font=font)
        for i, (text, image) in enumerate(chunk):
            r, c = divmod(i, COLUMNS)
            x0, y0 = GAP + c * (CELL + GAP), 24 + GAP + r * (CELL + LABEL + GAP)
            tile = PImage.frombytes("RGBA", (image.width, image.height), bytes(image.data))
            if max(tile.size) > CELL:
                tile.thumbnail((CELL, CELL), PImage.LANCZOS)
            elif max(tile.size) * 2 <= CELL:
                f = CELL // max(tile.size)
                tile = tile.resize((tile.width * f, tile.height * f), PImage.NEAREST)
            draw.rectangle((x0, y0, x0 + CELL - 1, y0 + CELL - 1), fill=(250, 250, 250, 255))
            sheet.alpha_composite(tile, (x0 + (CELL - tile.width) // 2, y0 + (CELL - tile.height) // 2))
            words, line, lines = text.split(), "", []
            for w in words:
                if font.getlength(line + " " + w) > CELL and line:
                    lines.append(line)
                    line = w
                else:
                    line = (line + " " + w).strip()
            lines.append(line)
            for k, part in enumerate(lines[:2]):
                draw.text((x0, y0 + CELL + 1 + 13 * k), part, fill=(30, 30, 30, 255), font=font)
        name = pi.safe_file_name(category) + (f" ({page + 1})" if pages > 1 else "") + ".png"
        path = folder / name
        sheet.convert("RGB").save(path)
        written.append(str(path))
    return written


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game", type=int, nargs="*", default=[1, 2, 3, 4, 5])
    parser.add_argument("--frames", type=int, default=8)
    parser.add_argument("--workers", type=int, default=min(24, os.cpu_count() or 1))
    args = parser.parse_args()
    jobs = []
    for game in args.game:
        if not _folder(game).is_dir():
            print(f"{pi.GAME_FOLDERS[game]}: no pictures in research/game-images, skipped")
            continue
        _sheets, _module, assets, problem = _load(game)
        if problem:
            print(f"{pi.GAME_FOLDERS[game]}: {problem}")
        for category in dict.fromkeys(a.category for a in assets):
            jobs.append((game, category, args.frames))
            print(f"{pi.GAME_FOLDERS[game]} - {category}: {sum(1 for a in assets if a.category == category)} entries")
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for written in pool.map(render, jobs):
            for path in written:
                print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
