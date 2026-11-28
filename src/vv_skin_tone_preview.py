"""The Skin Tones preview: a woman and a man, both adults, in each of the ten tones (the owner, 2026-11-28: the row's
"?" and How to Use show "female+male adult in all 10 tones, Change Appearance orientation", built from the player's
own files).

Made when it is asked for, from the player's own installed game sheets: the game's art is never shipped.  Each
figure is drawn as Change Appearance shows a villager: the head's front-facing column (5) of the head sheet over
the body's front-facing standing frame (column 8 of the body sheet; the owner: one frame RIGHT of the back-facing
one), the head lifted 4 pixels above the body, as the village stands an adult.  The tones are made exactly as the
patch makes them (src/vv_skin_tone_art.py, with the owner's shipped marking), so the preview is what the game will
show.

Only Pillow is needed.  Nothing is written into the game's folder.
"""
from __future__ import annotations

from pathlib import Path

import vv_skin_tone_art
import vv_skin_tones

HEAD_COL = 5            # the head sheet's front-facing column (native/vv4_origins_icons VV_HEAD_FRAME_COL)
BODY_COL = 8            # the body sheet's front-facing standing frame (VV_BODY_FRAME_COL)
CELL = (40, 65)
# The two adults shown (head row, body row): the same pair as scripts/skin_tone_sheets.py's previews.
PEOPLE = (("Woman", "female", 10, 3), ("Man", "male", 11, 6))
FIGURE = (44, 72)       # one figure's box: body at (2, 6), head at (2, 2), as the village stands an adult


def head_sheet(game: int, sex: str) -> str:
    return f"{sex}_heads00.png" if game in (4, 5) else f"{sex}_heads.png"


def body_sheet(sex: str, body: int) -> str:
    return f"{sex}_bodies0{body // 10}.png"


def _spec(game: int, name: str) -> dict:
    return next(s for s in vv_skin_tone_art.sheets_of(game) if s["name"] == name)


def _cells(game: int, images: Path, name: str, col: int, row: int, edits) -> list:
    """[the game's own cell, then each tone's] of one cell of one sheet, as Pillow pictures: the skin exactly as
    the patch finds it on the whole sheet (the owner's marking, else the colour rule), then the cell's own row
    recoloured (a tone's shading reads only its row, so this is the patch's own result for that row)."""
    from PIL import Image
    source = vv_skin_tone_art._find(Path(images), name)
    if source is None:
        raise FileNotFoundError(f"{name} is not in {images}")
    with Image.open(source) as opened:
        image = opened.convert("RGBA")
    w, h = CELL
    if (col + 1) * w > image.width or (row + 1) * h > image.height:
        raise ValueError(f"{name} has no cell at column {col}, row {row}")
    whole = (image.width, image.height, list(image.getdata()))
    stem = Path(name).stem
    mask = _layer_skin(vv_skin_tone_art._edit(edits, stem, "mask.png"), image, whole, True)
    if mask is None:
        mask = vv_skin_tone_art.mask_for(game, _spec(game, name), whole)
    first, last = row * h * image.width, (row + 1) * h * image.width
    band = image.crop((0, row * h, image.width, (row + 1) * h))
    sheet = (band.width, band.height, whole[2][first:last])
    out = [band.crop((col * w, 0, (col + 1) * w, h))]
    for tone in range(1, vv_skin_tones.TONE_COUNT + 1):
        skin = _layer_skin(vv_skin_tone_art._edit(edits, stem, f"skin_{tone:02d}.png"), image, whole, False)
        skin = mask if skin is None else skin
        here = {i - first for i in skin if first <= i < last}
        made = Image.new("RGBA", band.size)
        made.putdata(vv_skin_tone_art.recolour(sheet, here, vv_skin_tones.TONE_TABLE[tone - 1], h))
        out.append(made.crop((col * w, 0, (col + 1) * w, h)))
    return out


def _layer_skin(path, image, whole, is_mask: bool) -> set | None:
    """The skin an edit layer marks, read as vv_skin_tone_art.write_tone_sheets reads it; None when there is none."""
    from PIL import Image
    if path is None:
        return None
    with Image.open(path) as opened:
        layer = opened.convert("RGBA")
    if layer.size != image.size:
        return None
    if is_mask:
        return {i for i, (r, g, b, a) in enumerate(layer.getdata())
                if a >= vv_skin_tone_art.MASK_ALPHA and max(r, g, b) > 127 and whole[2][i][3] > 0}
    return {i for i, (_r, _g, _b, a) in enumerate(layer.getdata()) if a > 0 and whole[2][i][3] > 0}


def figures(game: int, images: Path, edits=None) -> dict:
    """{"Woman": [the game's own figure, tone 1 ... tone 10], "Man": [...]} as Pillow pictures of FIGURE size."""
    from PIL import Image
    if edits is None:
        edits = [vv_skin_tone_art.OWNER_EDITS / f"vv{game}"]
    out = {}
    for label, sex, head, body in PEOPLE:
        heads = _cells(game, images, head_sheet(game, sex), HEAD_COL, head, edits)
        bodies = _cells(game, images, body_sheet(sex, body), BODY_COL, body % 10, edits)
        row = []
        for head_cell, body_cell in zip(heads, bodies):
            canvas = Image.new("RGBA", FIGURE, (0, 0, 0, 0))
            canvas.alpha_composite(body_cell, (2, 6))
            canvas.alpha_composite(head_cell, (2, 2))
            row.append(canvas)
        out[label] = row
    return out


def preview(game: int, images: Path, zoom: int = 2, edits=None, games_own: bool = False):
    """The preview picture: the woman's row over the man's, one column a tone (light to dark), each tone's name
    under its column.  `games_own`: the game's own skin first, as "Game's own".  A Pillow RGBA picture."""
    from PIL import Image, ImageDraw
    rows = figures(game, images, edits)
    names = [vv_skin_tones.tone_name(n) for n in range(1, vv_skin_tones.TONE_COUNT + 1)]
    if games_own:
        names = ["Game's own"] + names
    else:
        rows = {label: figs[1:] for label, figs in rows.items()}
    fw, fh = FIGURE[0] * zoom, FIGURE[1] * zoom
    col_w, label_h, left = max(fw, 84), 30, 56
    picture = Image.new("RGBA", (left + col_w * len(names), fh * len(rows) + label_h), (104, 142, 78, 255))
    draw = ImageDraw.Draw(picture)
    for k, (label, figs) in enumerate(rows.items()):
        draw.text((6, k * fh + fh // 2 - 6), label, fill=(255, 255, 255, 255))
        for c, fig in enumerate(figs):
            big = fig.resize((fw, fh), Image.NEAREST)
            picture.alpha_composite(big, (left + c * col_w + (col_w - fw) // 2, k * fh))
    for c, name in enumerate(names):
        words = name.split(" ")
        for line, text in enumerate(words if len(words) > 1 else [name]):
            width = draw.textlength(text)
            draw.text((left + c * col_w + (col_w - width) / 2, fh * len(rows) + 2 + 12 * line), text,
                      fill=(255, 255, 255, 255))
    return picture


def images_folder(game: int, folders) -> Path | None:
    """The first of `folders` (game folders or their Images folders) holding this game's head and body sheets."""
    for folder in folders:
        for candidate in (Path(folder), Path(folder) / "Images"):
            try:
                if candidate.is_dir() and all(vv_skin_tone_art._find(candidate, name) is not None
                                              for name in (head_sheet(game, "male"), body_sheet("male", 6))):
                    return candidate
            except OSError:
                continue
    return None
