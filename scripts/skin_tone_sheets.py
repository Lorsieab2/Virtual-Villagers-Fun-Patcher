"""Skin tones for all five games: the sheets, the previews, and the owner's GIMP workbench.

    python scripts/skin_tone_sheets.py preview   --game vv3 --images "<game>\\Images" --out previews
    python scripts/skin_tone_sheets.py sheets    --game vv3 --images "<game>\\Images" --out "<folder>"
    python scripts/skin_tone_sheets.py workbench --game vv3 --images "<game>\\Images"
    python scripts/skin_tone_sheets.py workbench-all --images-root "<the folder of the five games>"
    python scripts/skin_tone_sheets.py import    --game vv3 [--same-for-all-tones]
    python scripts/skin_tone_sheets.py spread    --game vv3 --sheet vv3_carrying [--from 10]   (or --all-sheets)
    python scripts/skin_tone_sheets.py publish   --game vv3 --images "<game>\\Images"

The method is scripts/skin_tone_preview.py's (the skin mask, then REPLACE in OKLCh, everything outside
the mask byte-identical).  This file knows each game's sheets, makes the same preview set per game, and
builds and reads back the owner's workbench:

THE WORKBENCH (never in the repository: it holds game art).  One .xcf per head and body sheet, written
by GIMP itself, with layers bottom to top: "Game's own art" (locked), "Skin mask" (white = skin, hidden),
one layer GROUP per tone "Tone 01 - S1 Porcelain" ... (all hidden but one), "Hair and non-skin (vanilla)"
(locked).  The owner, 2026-11-27: each tone is "an editable color overlay mask over the base art so it
keeps its shading and i can add more colored skin and delete them in each tone".  So a tone's group holds
"<tone> colour (paint here)" -- flat tone colour on that tone's skin pixels, the layer the owner paints and
erases -- and over it "Shading (locked)": the tone's shaded colour for every pixel of the sprite, shown
only where the colour layer has paint (Normal mode, composite mode "Clip to backdrop").  The group alone
is, pixel for pixel, the tone's own sheet on its skin; a pixel the owner adds is shaded at once.
`import` asks GIMP for every colour layer again and keeps where the owner painted, for each tone they
changed, in <workbench>\\<game>\\edits\\<sheet>\\skin_NN.png (white where painted), and mask.png when the
"Skin mask" was changed.  Whatever is there wins over the generated mask, here and wherever the sheets are
made (Art(..., edits=...)).  The colours and the shading are never read back: always made from the art.

THE OWNER'S MARKING MAY SHIP (the owner, 2026-11-26: "yes my art can ship").  `publish` copies what
`import` kept into assets/skin_tones/owner_edits/<game>/<sheet>/ as WHERE THE SKIN IS ONLY: skin_NN.png
and mask.png, white where skin and nothing else -- no colour, and never the game's own layer, hair, eyes
or clothes.  manifest.json there pins each file by SHA-256 (tests/test_skin_tone_owner_edits.py).  Where
sheets are made, the workbench's edits come first, then these, then the generated mask.

Everything else this writes is made from the player's own game files and is never committed or shipped.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skin_tone_preview as core  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
WORKBENCH = Path(os.environ.get("VVFP_SKIN_WORKBENCH",
                                str(Path.home() / "OneDrive" / "Documents" / "VVFP Skin Tones Workbench")))
GIMP = Path(os.environ.get("VVFP_GIMP", str(Path.home() / "AppData/Local/Programs/GIMP 3/bin/gimp-console-3.exe")))
SEXES = ("male", "female")
GAMES_OWN = "Game's own"                 # the game's own skin, as every picture and window calls it

TITLES = {"vv1": "A New Home", "vv2": "The Lost Children", "vv3": "The Secret City",
          "vv4": "The Tree of Life", "vv5": "New Believers"}


def sheets_of(game):
    """Every sheet skin shows on, as dicts: name, kind ("heads" or "bodies": which mask rule), cell,
    front (a head sheet's front-facing column for its reference skin, or None), sex, first (the body value
    of the sheet's first row), old (a head sheet of the old)."""
    out = []

    def add(name, kind, cell=(40, 65), front=None, sex=None, first=0, old=False):
        out.append({"name": name, "kind": kind, "cell": cell, "front": front, "sex": sex, "first": first, "old": old})

    thirds = (0, 1) if game == "vv1" else (0, 1, 2)
    for sex in SEXES:
        if game == "vv1":
            add(f"{sex}_heads.png", "heads", front=5, sex=sex)
        elif game in ("vv2", "vv3"):
            add(f"{sex}_heads.png", "heads", front=5, sex=sex)
            add(f"{sex}_heads_old.png", "heads", front=5, sex=sex, old=True)
        else:
            add(f"{sex}_heads00.png", "heads", front=5, sex=sex)
            add(f"{sex}_heads10.png", "heads", front=5, sex=sex, old=True)
        for across in (0, 1):
            for down in thirds:
                add(f"{sex}_bodies{across}{down}.png", "bodies", sex=sex, first=10 * down)
        for down in thirds:
            add(f"{sex}_actions0{down}.png", "bodies", sex=sex, first=10 * down)
    # The held baby (the owner, 2026-11-26: "Just the held baby sprite no other"): one cell of the
    # carried-things sheet, the same swaddled baby in all five games.  Nothing else on that sheet is skin.
    add("carrying.png", "baby", cell=(40, 25 if game in ("vv1", "vv2") else 40))
    if game in ("vv4", "vv5"):
        add("BigHeads00.png", "heads", cell=(80, 100))
        add("BigHeads10.png", "heads", cell=(80, 100), old=True)
        add("BigBodies.png", "bodies", cell=(80, 130))
    return out


# Cloth painted in the colours of skin, by game and (sex, body value); numbers only (see the core file).
CLOTH_RULES = {"vv1": core.VV1_CLOTH_RULES}
# The owner's hand-made masks (The Lost Children): research/vv2-skin-source/<sheet>_skinmask.png.
OWNER_MASKS = {"vv2": ROOT / "research" / "vv2-skin-source"}
SHIPPED_EDITS = ROOT / "assets" / "skin_tones" / "owner_edits"
BABY_CELL = (3, 0)          # the held baby's column and row on carrying.png, every game


def baby_mask(a, cell):
    """The held baby's skin: the warm, lit pixels of its one cell (its little face).  The swaddling is a
    blue-white and the eyes are purple, so neither is taken."""
    w, h = cell
    x0, y0 = BABY_CELL[0] * w, BABY_CELL[1] * h
    part = a[y0:y0 + h, x0:x0 + w]
    hue, sat, val = core.hsv(part)
    r, g, b = (part[..., i].astype(int) for i in range(3))
    m = np.zeros(a.shape[:2], bool)
    m[y0:y0 + h, x0:x0 + w] = ((part[..., 3] == 255) & (r >= g) & (g >= b) & (hue >= 20) & (hue <= 62)
                               & (sat >= 0.18) & (val >= 0.60))
    return m


def find_file(folder: Path, name: str):
    """The file called `name` in `folder`, whatever its letter case; None when it is not there."""
    wanted = name.lower()
    for path in folder.iterdir():
        if path.name.lower() == wanted:
            return path
    return None


class Art:
    """A game's sheets: its own art, each sheet's skin mask, and each tone's sheet.  `edits` is the
    owner's folder (<workbench>/<game>/edits): a skin_NN.png (a tone's own skin) or a mask.png there wins; then the owner's
    shipped edits (assets/skin_tones/owner_edits/<game>), unless `shipped` is False."""

    def __init__(self, game, images: Path, edits: Path | None = None, shipped: bool = True):
        self.game, self.images = game, Path(images)
        self.edit_folders = [f for f in (edits, SHIPPED_EDITS / game if shipped else None) if f is not None]
        self.specs = {s["name"]: s for s in sheets_of(game) if find_file(self.images, s["name"])}
        self._raw, self._mask, self._made, self.mask_source, self._tone_mask = {}, {}, {}, {}, {}

    def stock(self, name):
        if name not in self._raw:
            self._raw[name] = np.array(Image.open(find_file(self.images, name)).convert("RGBA"))
        return self._raw[name]

    def _edit(self, name, leaf):
        for folder in self.edit_folders:
            path = folder / Path(name).stem / leaf
            if path.is_file():
                return path
        return None

    def mask(self, name):
        if name in self._mask:
            return self._mask[name]
        spec, a = self.specs[name], self.stock(name)
        edited = self._edit(name, "mask.png")
        owner = OWNER_MASKS.get(self.game)
        owner = owner / f"{Path(name).stem}_skinmask.png" if owner else None
        if edited is not None:
            m, source = mask_from_layer(np.array(Image.open(edited).convert("RGBA"))), "the owner's edited mask"
        elif spec["kind"] == "baby":
            m, source = baby_mask(a, spec["cell"]), "the held baby's cell only"
        else:
            rules = CLOTH_RULES.get(self.game, {})
            cloth = None
            if spec["kind"] == "bodies" and spec["sex"]:
                rows = a.shape[0] // spec["cell"][1]
                cloth = {body - spec["first"]: rule for (sex, body), rule in rules.items()
                         if sex == spec["sex"] and 0 <= body - spec["first"] < rows}
            m = core.skin_mask(a, spec["kind"] == "heads", (), cloth, spec["cell"], spec["front"])
            source = "the colour rule"
            if owner is not None and owner.is_file():
                hand = np.array(Image.open(owner).convert("L")) > 128
                if spec["kind"] == "heads":
                    # The owner marked the HAIR; their mask is everything else on the head, eyes and
                    # mouths included.  So it says where skin may be, and the colour rule says which of
                    # those pixels are skin: hair the rule would have taken is out, eyes and lips stay.
                    # Inside it the rule can be generous: any warm, lit pixel (the pale yellow sheen of
                    # these faces too) is skin; dark lines, neutral whites, coloured eyes and red lips
                    # are not.
                    h, s, v = core.hsv(a)
                    lit = (v >= 0.45) & (h >= 12) & (h <= 78) & (s >= 0.08)
                    m, source = (m | lit) & hand, "the owner's hand-made mask (no hair), less eyes, mouths and lines"
                else:
                    # The owner's body masks mark skin, but cover about half of it (many frames are
                    # only partly marked), so they add to the colour rule.
                    m, source = m | hand, "the colour rule plus the owner's hand-made mask"
        if m.shape != a.shape[:2]:
            raise SystemExit(f"{name}: its mask is {m.shape[1]} x {m.shape[0]}, the sheet {a.shape[1]} x {a.shape[0]}")
        m = m & (a[..., 3] > 0)
        self._mask[name], self.mask_source[name] = m, source
        return m

    def tone_mask(self, name, number):
        """The skin of one tone (1..10) on a sheet: what the owner painted on that tone's colour layer
        (edits: skin_NN.png, white where painted) when they did, else the sheet's own mask."""
        painted = self._edit(name, f"skin_{number:02d}.png")
        if painted is None:
            return self.mask(name)
        key = (name, number)
        if key not in self._tone_mask:
            layer = np.array(Image.open(painted).convert("RGBA"))
            stock = self.stock(name)
            if layer.shape != stock.shape:
                raise SystemExit(f"{painted}: not the sheet's size")
            self._tone_mask[key] = painted_from_layer(layer) & (stock[..., 3] > 0)
        return self._tone_mask[key]

    def sheet(self, name, tone=None):
        """The sheet for `tone` (a core.TONES row), or the game's own for None."""
        if tone is None:
            return self.stock(name)
        number = core.TONES.index(tone) + 1
        key = (name, number)
        if key not in self._made:
            stock = self.stock(name)
            mask = self.tone_mask(name, number)
            made = core.recolour(stock, mask, tone, self.specs[name]["cell"][1])
            if not core.check_untouched(stock, made, mask):
                raise SystemExit(f"{name}: a pixel outside the skin mask changed")
            self._made[key] = made
        return self._made[key]

    def tone_layer(self, name, tone):
        """A tone's sheet with only its skin pixels on it (the workbench layer)."""
        made = self.sheet(name, tone).copy()
        made[~self.tone_mask(name, core.TONES.index(tone) + 1)] = 0
        return made

    def cell(self, name, col, row, tone=None):
        w, h = self.specs[name]["cell"]
        return Image.fromarray(self.sheet(name, tone)[row * h:(row + 1) * h, col * w:(col + 1) * w].copy())

    def head(self, sex, row, tone=None, old=False, col=5):
        if self.game == "vv1":
            name = f"{sex}_heads.png"
        elif self.game in ("vv2", "vv3"):
            name = f"{sex}_heads_old.png" if old else f"{sex}_heads.png"
        else:
            name = f"{sex}_heads10.png" if old else f"{sex}_heads00.png"
        return self.cell(name, col, row, tone)

    def body(self, sex, row, tone=None, col=8):
        return self.cell(f"{sex}_bodies0{row // 10}.png", col, row % 10, tone)

    def baby(self, tone=None):
        """The held baby's cell."""
        return self.cell("carrying.png", BABY_CELL[0], BABY_CELL[1], tone)

    def villager(self, v, tone=None):
        """Standing: the body's and the head's cells one over the other, as the village draws them
        (a child: body age/7 + 50 percent, head age/14 + 80 percent)."""
        canvas = Image.new("RGBA", (44, 72), (0, 0, 0, 0))
        body = self.body(v["sex"], v["body"], tone)
        head = self.head(v["sex"], v["head"], tone, v.get("old", False))
        if v.get("age", 600) < 0x118:
            for img, pct in ((body, v["age"] // 7 + 50), (head, v["age"] // 14 + 80)):
                w, h = int(40 * pct / 100), int(65 * pct / 100)
                canvas.alpha_composite(img.resize((w, h), Image.BOX), (2 + (40 - w) // 2, -8 + (65 - h) // 2))
        else:
            canvas.alpha_composite(body, (2, 6))
            canvas.alpha_composite(head, (2, 2))
        return canvas


# ---- the per-game report and previews ---------------------------------------------------------------

def mask_report(art: Art, out: Path | None = None):
    """One line per sheet: where its mask came from and how much of the sheet is skin; with `out`, a
    picture per sheet too (skin in magenta), 2x."""
    lines = []
    for name in art.specs:
        a, m = art.stock(name), art.mask(name)
        opaque = int((a[..., 3] > 0).sum())
        lines.append(f"{name}: {art.mask_source[name]}; skin {int(m.sum())} of {opaque} opaque pixels "
                     f"({100 * m.sum() / max(opaque, 1):.1f}%)")
        if out is not None:
            grey = a[..., :3].mean(-1, keepdims=True).repeat(3, -1) * 0.6 + 40
            pic = np.where(m[..., None], np.array([255, 0, 255]), grey)
            alpha = a[..., 3:4] / 255
            pic = pic * alpha + np.array([90, 110, 90]) * (1 - alpha)
            img = Image.fromarray(pic.astype(np.uint8))
            img.resize((img.width * 2, img.height * 2), Image.NEAREST).save(out / f"mask_{Path(name).stem}.png")
    return lines


def _rows(count, wanted):
    return [r for r in wanted if r < count]


def previews(art: Art, out: Path, masks=False):
    g, title = art.game, TITLES[art.game]
    out.mkdir(parents=True, exist_ok=True)
    tones = [(GAMES_OWN, None)] + [(f"S{i} {t[4]}", t) for i, t in enumerate(core.TONES, 1)]
    labels = [t[0] for t in tones]
    core.swatches(out / f"{g}_tone_table.png")
    if masks:
        (out / "masks" / g).mkdir(parents=True, exist_ok=True)
    for line in mask_report(art, out / "masks" / g if masks else None):
        print(line)
    heads_n = art.stock(f"male_heads{'00' if g in ('vv4', 'vv5') else ''}.png").shape[0] // 65
    bodies_n = 20 if g == "vv1" else 30
    hr, br = _rows(heads_n, (0, 2, 4, 8, 11, 13, 17, 21, 26)), _rows(bodies_n, (0, 1, 3, 6, 9, 14, 15, 18, 22, 27))
    people = [("Man", {"sex": "male", "head": 11, "body": 6}), ("Woman", {"sex": "female", "head": 10, "body": 3}),
              ("Man 2", {"sex": "male", "head": 0, "body": 1}), ("Woman 2", {"sex": "female", "head": 3, "body": 12}),
              ("Man 3", {"sex": "male", "head": 4, "body": 15}), ("Woman 3", {"sex": "female", "head": 0, "body": 7})]
    if bodies_n == 30:
        people += [("Man 4", {"sex": "male", "head": 22, "body": 24}), ("Woman 4", {"sex": "female", "head": 25, "body": 21})]
    children = [("Boy, 3", {"sex": "male", "head": 10, "body": 2, "age": 60}),
                ("Girl, 5", {"sex": "female", "head": 6, "body": 9, "age": 100}),
                ("Boy, 9", {"sex": "male", "head": 3, "body": 5, "age": 180}),
                ("Girl, 12", {"sex": "female", "head": 12, "body": 14, "age": 240})]
    elders = [(f"Old {'man' if s == 'male' else 'woman'} {h}", {"sex": s, "head": h, "body": b, "old": True})
              for s, h, b in (("male", 1, 4), ("male", 7, 10), ("male", 15, 17), ("female", 2, 5), ("female", 9, 13),
                              ("female", 16, 19))]
    heads = [(f"{s[0].upper()} head {r}", (s, r)) for s in SEXES for r in hr]
    bodies = [(f"{s[0].upper()} body {r}", (s, r)) for s in SEXES for r in br]
    for zoom in (1, 4):
        z = f"{zoom}x"

        def people_grid(rows, what, leaf):
            core.grid(rows, tones, lambda p, t: art.villager(p[1], t[1]), [p[0] for p in rows], labels,
                      f"{title}: {what}, the game's own art then the {len(core.TONES)} tones ({z})",
                      out / f"{g}_{leaf}_{z}.png", zoom, (44, 72), label_w=130)

        people_grid(people, "villagers", "villagers")
        people_grid(children, "children", "children")
        if g != "vv1":
            people_grid(elders, "elders (the old heads)", "elders")
        core.grid(heads, tones, lambda h, t: art.head(h[1][0], h[1][1], t[1]).crop((4, 0, 36, 34)),
                  [h[0] for h in heads], labels, f"{title}: heads ({z})", out / f"{g}_heads_{z}.png", zoom, (32, 34), label_w=90)
        core.grid(bodies, tones, lambda b, t: art.body(b[1][0], b[1][1], t[1]).crop((4, 14, 36, 62)),
                  [b[0] for b in bodies], labels, f"{title}: bodies ({z})", out / f"{g}_bodies_{z}.png", zoom, (32, 48), label_w=90)
        if g in ("vv4", "vv5") and "BigHeads00.png" in art.specs:
            big = [(f"Big head row {r}", r) for r in _rows(30, (0, 5, 11, 17, 23, 29))]
            core.grid(big, tones, lambda b, t: art.cell("BigHeads00.png", 1, b[1], t[1]), [b[0] for b in big], labels,
                      f"{title}: the Details big heads ({z})", out / f"{g}_bigheads_{z}.png", zoom, (80, 100), label_w=110)
        if "carrying.png" in art.specs:
            size = art.specs["carrying.png"]["cell"]
            core.grid([("Held baby", None)], tones, lambda b, t: art.baby(t[1]), ["Held baby"], labels,
                      f"{title}: the held baby ({z})", out / f"{g}_held_baby_{z}.png", zoom, size, label_w=90)
    check_rows(art, out)


def check_rows(art: Art, out: Path, zoom=3):
    """Every body value, the game's own beside a dark tone, four frames: for checking clothes."""
    from PIL import ImageDraw
    tone = core.TONES[9]
    count = 20 if art.game == "vv1" else 30
    per = 10
    for sex in SEXES:
        cols = (0, 4, 8, 12)
        w = len(cols) * 2 * 40 * zoom + 60
        pic = Image.new("RGB", (w * (count // per), per * 65 * zoom), (104, 142, 78))
        d = ImageDraw.Draw(pic)
        for row in range(count):
            ox, oy = (row // per) * w, (row % per) * 65 * zoom
            d.text((ox + 2, oy + 2), f"{sex[0].upper()}{row}", fill=(255, 255, 255))
            for i, col in enumerate(cols):
                for j, t in enumerate((None, tone)):
                    tile = Image.new("RGBA", (40, 65), core.GRASS)
                    tile.alpha_composite(art.body(sex, row, t, col))
                    pic.paste(tile.resize((40 * zoom, 65 * zoom), Image.NEAREST).convert("RGB"),
                              (ox + 40 + (i * 2 + j) * 40 * zoom, oy))
        pic.save(out / f"{art.game}_check_all_{sex}_bodies.png")
        print("wrote", out / f"{art.game}_check_all_{sex}_bodies.png")


FOLDERS = {g: f"Virtual Villagers - {t}" for g, t in TITLES.items()}
MOCKUP_HEADS = {"male": 11, "female": 10}
# Typical adults with bare arms and legs and clothes that are plainly not skin-coloured.
MOCKUP_BODIES = {"male": 6, "female": 3}
MOCKUP_BODIES_VV1 = {"male": 6, "female": 11}


def mockup(root: Path, out: Path, edits_root: Path | None = None):
    """ONE picture of all five games: a man, a woman and the held baby of each, as the game's own and in every
    tone.  all_games_male_female_10tones.png has each villager at 2x; the _2x file at 4x."""
    from PIL import ImageDraw
    rows = []
    for game in sorted(TITLES):
        images = root / FOLDERS[game] / "Images"
        edits = edits_root / game / "edits" if edits_root else None
        art = Art(game, images, edits if edits and edits.is_dir() else None)
        for sex, word in (("male", "man"), ("female", "woman")):
            v = {"sex": sex, "head": MOCKUP_HEADS[sex], "body": (MOCKUP_BODIES_VV1 if game == "vv1" else MOCKUP_BODIES)[sex]}
            rows.append((f"{TITLES[game]}: {word}", (44, 72), [art.villager(v, t) for t in [None] + list(core.TONES)]))
            print(f"{game} {word}: head {v['head']}, body {v['body']}")
        cell = art.specs["carrying.png"]["cell"]
        rows.append((f"{TITLES[game]}: held baby", cell, [art.baby(t) for t in [None] + list(core.TONES)]))
    labels = [GAMES_OWN] + [f"S{i} {t[4]}" for i, t in enumerate(core.TONES, 1)]
    out.mkdir(parents=True, exist_ok=True)
    for zoom, leaf in ((2, "all_games_male_female_10tones.png"), (4, "all_games_male_female_10tones_2x.png")):
        label_w, top = 100 * zoom, 34 + 22
        cw = 44 * zoom + 6
        height = top + sum(size[1] * zoom + 6 for _, size, _ in rows) + 6
        pic = Image.new("RGB", (label_w + cw * len(labels) + 6, height), (245, 242, 235))
        d = ImageDraw.Draw(pic)
        font = core._font(6 + 3 * zoom)
        d.text((8, 6), "Skin tones in all five games: the game's own art, then the ten tones.  "
               "Made from each game's own sheets; every pixel that is not skin is the game's own.",
               fill=(20, 20, 20), font=font)
        for j, text in enumerate(labels):
            d.rectangle((label_w + cw * j, 26, label_w + cw * (j + 1) - 6, 34),
                        fill=(245, 242, 235) if j == 0 else tuple(
                            int(x) for x in core.shade(np.array([0.0]), core.TONES[j - 1], 0.14, 0.07)[0].round()))
            d.text((label_w + cw * j, 38), text if zoom > 2 else text[:13], fill=(20, 20, 20), font=core._font(4 + 3 * zoom))
        y = top
        for label, size, tiles in rows:
            d.text((6, y + size[1] * zoom // 2 - 6), label, fill=(20, 20, 20), font=font)
            for j, tile in enumerate(tiles):
                cell = Image.new("RGBA", size, core.GRASS)
                cell.alpha_composite(tile, ((size[0] - tile.width) // 2, 0))
                pic.paste(cell.resize((size[0] * zoom, size[1] * zoom), Image.NEAREST).convert("RGB"),
                          (label_w + cw * j, y))
            y += size[1] * zoom + 6
        pic.save(out / leaf)
        print("wrote", out / leaf)


def heathens(images: Path, out: Path):
    """New Believers' Heathens in each mask colour, as the game's own and in every tone.  Drawn by the patcher's
    own copy of the game's villager draw (src/vv_pictures_vv5.py: the same sheets, anchors and mask
    placement as the game), from a scratch copy of the game's pictures with the toned sheets in it.  The
    mask sheet is never toned, so every mask is the game's own."""
    import io
    import shutil
    import vv_picture_image as pi
    import vv_pictures_vv5 as v5
    art = Art("vv5", images)
    masks = [("Blue mask", {}), ("Orange mask", {"orange": 1}), ("Red mask", {"red": 1}),
             ("Purple mask", {"rank": 12}), ("Chief's mask", {"rank": 13})]
    looks = [(f"{'Man' if male else 'Woman'}, {label.lower()}",
              v5.Look(male=male, head=MOCKUP_HEADS["male" if male else "female"],
                      body=MOCKUP_BODIES["male" if male else "female"], faction=1, **fields))
             for label, fields in masks for male in (True, False)]
    pose = v5.Pose(pose=8, turn=5, shadow=False, x=30, y=20)
    rows = [[] for _ in looks]
    with tempfile.TemporaryDirectory() as tmp:
        for number, tone in enumerate([None] + list(core.TONES)):
            folder = Path(tmp) / str(number)
            (folder / "Images").mkdir(parents=True)
            shutil.copytree(images.parent / "Assets", folder / "Assets")
            for path in images.iterdir():
                if path.is_file() and path.suffix.lower() == ".png":
                    if tone is not None and path.name in art.specs:
                        Image.fromarray(art.sheet(path.name, tone)).save(folder / "Images" / path.name)
                    else:
                        shutil.copyfile(path, folder / "Images" / path.name)
            renderer = v5.load(pi.FolderSource(folder))
            for i, (_label, look) in enumerate(looks):
                drawn = pi.render_plan(renderer.sheets, renderer.planner.plan(look, pose))
                rows[i].append(Image.open(io.BytesIO(drawn.to_png())).convert("RGBA"))
    labels = [GAMES_OWN] + [f"S{i} {t[4]}" for i, t in enumerate(core.TONES, 1)]
    size = (max(t.width for row in rows for t in row), max(t.height for row in rows for t in row))
    for zoom in (1, 4):
        core.grid(list(range(len(looks))), list(range(len(labels))), lambda r, c: rows[r][c],
                  [label for label, _ in looks], labels,
                  f"New Believers: Heathens in each mask colour ({zoom}x); the masks are the game's own",
                  out / f"vv5_heathens_{zoom}x.png", zoom, size, label_w=150)


ASH_UNDER, ASH_SHARE = 0.70, 0.01       # a row fails when over 1% of its toned skin has under 70% of the tone's chroma
MISS_SHARE = 0.01                       # ... or when pixels still like the skin beside them are over 1% of its skin


def audit(art: Art, out: Path):
    """The two checks the owner asked for (2026-11-26), on every sheet and row of the game, and a proof
    picture.  ASH: in every tone, the share of toned skin pixels whose chroma (measured on the finished
    8-bit colours) is under ASH_UNDER of the tone's own.  MISSES: pixels left untoned that are like the
    toned skin touching them (core.alike: necks, forearms, shins, hands, feet the mask stopped short of).
    Returns the lines of the report; <game>_audit.txt and <game>_necks_arms_legs_4x.png are written."""
    g, title = art.game, TITLES[art.game]
    out.mkdir(parents=True, exist_ok=True)
    lines, bad = [f"{title}: skin tone audit"], 0
    for name, spec in art.specs.items():
        stock, mask = art.stock(name), art.mask(name)
        ch = spec["cell"][1]
        rows = stock.shape[0] // ch
        left = core.alike(stock, mask) if spec["kind"] != "baby" else np.zeros_like(mask)
        ash = np.zeros(rows)
        for tone in core.TONES:
            made = art.sheet(name, tone)
            low = np.zeros_like(mask)
            low[mask] = core.chroma_of(made[mask][:, :3].astype(float)) < ASH_UNDER * tone[2]
            for row in range(rows):
                skin = int(mask[row * ch:(row + 1) * ch].sum())
                if skin:
                    ash[row] = max(ash[row], low[row * ch:(row + 1) * ch].sum() / skin)
        failed = []
        for row in range(rows):
            skin = int(mask[row * ch:(row + 1) * ch].sum())
            miss = int(left[row * ch:(row + 1) * ch].sum())
            if skin and (ash[row] > ASH_SHARE or miss / skin > MISS_SHARE):
                failed.append(f"row {row}: ash {100 * ash[row]:.1f}%, like-skin left {miss} of {skin} ({100 * miss / skin:.1f}%)")
        bad += len(failed)
        lines.append(f"  {name} ({art.mask_source[name]}): skin {int(mask.sum())}; worst ash share {100 * ash.max():.2f}%; "
                     f"like-skin pixels left {int(left.sum())} ({100 * left.sum() / max(int(mask.sum()), 1):.2f}%)"
                     + ("" if not failed else "; " + str(len(failed)) + " rows over the limits"))
        lines += ["      " + f for f in failed]
    lines.append(f"  rows over the limits: {bad}")
    (out / f"{g}_audit.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    # The proof: whole villagers (neck, arms, legs, hands, feet all in view), the game's own, S5 and S10, 4x.
    shown = [(GAMES_OWN, None), (f"S5 {core.TONES[4][4]}", core.TONES[4]), (f"S10 {core.TONES[9][4]}", core.TONES[9])]
    bodies_n = 20 if g == "vv1" else 30
    people = [(f"{'Man' if sex == 'male' else 'Woman'}, head {head}, body {body}", {"sex": sex, "head": head, "body": body})
              for sex, head, body in (("male", 11, 6), ("female", 10, 3), ("male", 2, 14), ("female", 5, 11),
                                      ("male", 7, 9), ("female", 14, 7), ("male", 17, bodies_n - 2),
                                      ("female", 1, bodies_n - 1))]
    cols = [(f"{label}, frame {frame}", tone, frame) for frame in (8, 0) for label, tone in shown]

    def draw(person, col):
        _label, tone, frame = col
        v = person[1]
        canvas = Image.new("RGBA", (44, 72), (0, 0, 0, 0))
        canvas.alpha_composite(art.body(v["sex"], v["body"], tone, frame), (2, 6))
        canvas.alpha_composite(art.head(v["sex"], v["head"], tone), (2, 2))
        return canvas

    core.grid(people, cols, draw, [p[0] for p in people], [c[0] for c in cols],
              f"{title}: necks, arms, legs, hands and feet -- the game's own art, S5 and S10, two frames (4x)",
              out / f"{g}_necks_arms_legs_4x.png", 4, (44, 72), label_w=170)
    return lines


def installed_name(tone_number: int, name: str) -> str:
    """A tone's sheet as "VVFP Skin Tones.dll" looks for it in a game's Images folder
    (native/vvfp_skin_tones/vvfp_skin_tones.c st_toned_sheet): vvfp_skin_<NN>_<the game's own file name>."""
    return f"vvfp_skin_{tone_number:02d}_{name}"


def write_sheets(art: Art, out: Path):
    """Every tone's sheets into `out`, named as the game's companion looks for them (installed_name)."""
    out.mkdir(parents=True, exist_ok=True)
    for number, tone in enumerate(core.TONES, 1):
        for name in art.specs:
            Image.fromarray(art.sheet(name, tone)).save(out / installed_name(number, name))
    print("wrote", len(core.TONES) * len(art.specs), "sheets in", out)


# ---- the GIMP workbench ------------------------------------------------------------------------------

LAYER_GAME, LAYER_MASK, LAYER_TOP = "Game's own art", "Skin mask", "Hair and non-skin (vanilla)"
LAYER_SHADING, PAINT_WORDS = "Shading (locked)", "colour (paint here)"
SHOWN_TONE = 6          # the tone left visible in a new .xcf


def tone_layer_name(number):
    """A tone's GROUP in an .xcf."""
    return f"Tone {number:02d} - S{number} {core.TONES[number - 1][4]}"


def paint_layer_name(number):
    """The layer of a tone's group the owner paints: flat colour where that tone has skin."""
    return f"{core.TONES[number - 1][4]} {PAINT_WORDS}"


def tone_colour(number):
    return core._hex(core.TONE_TABLE[number - 1][1])


def shaded_everywhere(stock, mask, tone, cell_h):
    """The tone's shaded colour for EVERY opaque pixel of a sheet (opaque where the sheet is, nothing
    elsewhere): each pixel's own lightness offset from its row's middle skin, as core.recolour shades skin.
    On the mask it is exactly core.recolour's colours; off it, it is what a pixel would be if it were made
    skin -- so a tone's group shows the right shading wherever the owner paints.  A row with no skin takes
    the sheet's own middle."""
    L = core.to_oklab(stock[..., :3])[..., 0]
    opaque = stock[..., 3] > 0
    out = np.zeros_like(stock)
    if not opaque.any():
        return out
    whole = np.percentile(L[mask] if mask.any() else L[opaque], (2, 50, 98))
    for r in range(stock.shape[0] // cell_h):
        sl = slice(r * cell_h, (r + 1) * cell_h)
        here, skin = opaque[sl], mask[sl]
        if not here.any():
            continue
        lo, mid, hi = np.percentile(L[sl][skin], (2, 50, 98)) if skin.any() else whole
        values, back = np.unique(L[sl][here], return_inverse=True)
        colours = core.shade(values - mid, tone, mid - lo, hi - mid).round().astype(np.uint8)
        block = out[sl]
        block[here, :3] = colours[back]
        block[here, 3] = 255
        out[sl] = block
    return out


_GIMP_BUILD = r'''
import json, os
import gi
gi.require_version("Gimp", "3.0")
from gi.repository import Gimp, Gio
job = json.load(open(os.environ["VVFP_SKIN_JOB"], encoding="utf-8"))
for item in job["files"]:
    # One picture holds every layer of the sheet, one under the other (one file read a sheet, not one a
    # layer).  Each layer is a copy of it cut down to its own band and moved to the top: nothing is resampled.
    image = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(item["png"]))
    width, height = item["width"], item["height"]
    whole = image.get_layers()[0]
    parts = [whole]
    for k in range(1, len(item["layers"])):
        part = whole.copy()
        image.insert_layer(part, None, 0)
        part.resize(width, height, 0, -k * height)
        part.set_offsets(0, 0)
        parts.append(part)
    whole.resize(width, height, 0, 0)
    whole.set_offsets(0, 0)
    image.resize(width, height, 0, 0)
    groups, order = {}, []
    for part, layer in zip(parts, item["layers"]):
        part.set_name(layer["name"])
        part.set_visible(bool(layer["visible"]))
        if layer.get("clip"):
            # Shown only where the layer under it in its group has paint.
            part.set_composite_mode(Gimp.LayerCompositeMode.CLIP_TO_BACKDROP)
        if layer["lock"]:
            part.set_lock_content(True)
        name = layer.get("group")
        if name:
            if name not in groups:
                try:
                    group = Gimp.GroupLayer.new(image, name)
                except TypeError:
                    group = Gimp.GroupLayer.new(image)
                    group.set_name(name)
                image.insert_layer(group, None, image.get_item_position(part))
                group.set_mode(Gimp.LayerMode.NORMAL)   # its own little picture: the clip sees the group only
                group.set_visible(bool(layer["group_visible"]))
                groups[name] = group
                order.append(name)
            image.reorder_item(part, groups[name], 0)
    if item.get("check"):
        # Each group as it shows on its own, one under the other, for the builder to compare.
        tops = image.get_layers()
        shown = [layer.get_visible() for layer in tops]
        tall = Gimp.Image.new(width, height * len(order), Gimp.ImageBaseType.RGB)
        for k, name in enumerate(order):
            for layer in tops:
                layer.set_visible(layer.get_id() == groups[name].get_id())
            shot = Gimp.Layer.new_from_visible(image, tall, name)
            tall.insert_layer(shot, None, 0)
            shot.set_offsets(0, k * height)
        tall.merge_visible_layers(Gimp.MergeType.CLIP_TO_IMAGE)
        Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, tall, Gio.File.new_for_path(item["check"]), None)
        tall.delete()
        for layer, was in zip(tops, shown):
            layer.set_visible(was)
    Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, image, Gio.File.new_for_path(item["xcf"]), None)
    image.delete()
    print("VVFP wrote", item["xcf"])
'''

_GIMP_EXPORT = r'''
import json, os, re
import gi
gi.require_version("Gimp", "3.0")
from gi.repository import Gimp, Gio
job = json.load(open(os.environ["VVFP_SKIN_JOB"], encoding="utf-8"))
for item in job["files"]:
    image = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(item["xcf"]))
    width, height = image.get_width(), image.get_height()
    os.makedirs(item["out"], exist_ok=True)
    wanted = []
    for layer in image.get_layers():
        name = layer.get_name()
        tone = re.match(r"Tone (\d+)", name)
        if tone and layer.is_group():
            # A tone's group: the layer the owner paints says where that tone has skin.
            for child in layer.get_children():
                if "paint here" in child.get_name():
                    wanted.append(("skin_%02d.png" % int(tone.group(1)), child))
            continue
        # (A plain "Tone NN" layer of the first workbench is a painted picture: never read.)
        if name.startswith("Skin mask"):
            wanted.append(("mask.png", layer))
    if wanted:
        # Every wanted layer goes into one picture, one under the other (one file written a sheet): a copy
        # of each, cut to the sheet's own area and moved to its band.  Nothing is resampled.
        tall = Gimp.Image.new(width, height * len(wanted), Gimp.ImageBaseType.RGB)
        for k, (leaf, layer) in enumerate(wanted):
            at = layer.get_offsets()
            copy = Gimp.Layer.new_from_drawable(layer, tall)
            tall.insert_layer(copy, None, 0)
            copy.set_visible(True)                  # read the same whether or not its eye is on,
            try:
                copy.set_opacity(100.0)             # at any opacity (the tutorial marks at 50%),
                copy.set_mode(Gimp.LayerMode.NORMAL)    # and in any mode
            except Exception:
                pass                                # the mask is still read right (mask_from_layer)
            copy.resize(width, height, at[-2], at[-1])
            copy.set_offsets(0, k * height)
        tall.merge_visible_layers(Gimp.MergeType.CLIP_TO_IMAGE)
        Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, tall, Gio.File.new_for_path(os.path.join(item["out"], "layers.png")), None)
        tall.delete()
    json.dump([leaf for leaf, _ in wanted], open(os.path.join(item["out"], "layers.json"), "w", encoding="utf-8"))
    image.delete()
    print("VVFP read", item["xcf"])
'''


def run_gimp(script: str, job: dict):
    """One GIMP batch process (never two at once) running `script` with `job`."""
    if not GIMP.is_file():
        raise SystemExit(f"GIMP 3 was not found at {GIMP} (set VVFP_GIMP to gimp-console-3.exe)")
    with tempfile.TemporaryDirectory() as tmp:
        job_path, script_path = Path(tmp) / "job.json", Path(tmp) / "batch.py"
        job_path.write_text(json.dumps(job), encoding="utf-8")
        script_path.write_text(script, encoding="utf-8")
        env = dict(os.environ, VVFP_SKIN_JOB=str(job_path))
        command = [str(GIMP), "-n", "-i", "-d", "-f", "--batch-interpreter", "python-fu-eval",
                   "-b", f"exec(open(r'{script_path}', encoding='utf-8').read())", "--quit"]
        # At idle priority: the owner may be painting in GIMP on the same machine.
        quiet = {"creationflags": 0x00000040} if os.name == "nt" else {}
        done = subprocess.run(command, env=env, capture_output=True, text=True, timeout=3600, **quiet)
        text = (done.stdout or "") + (done.stderr or "")
        if text.count("VVFP ") < len(job["files"]):
            raise SystemExit("GIMP did not finish every file:\n" + text[-3000:])
        return text


def _sha(array):
    return hashlib.sha1(np.ascontiguousarray(array).tobytes()).hexdigest()


def _layer_pixels(path):
    return np.array(Image.open(path).convert("RGBA"))


MASK_ALPHA = 32             # a mask pixel this opaque or more, and light, is skin (vv_skin_tone_art.MASK_ALPHA)


def mask_from_layer(layer):
    """The skin a "Skin mask" layer marks: every light pixel that is not (nearly) see-through.  A mask left
    at 50% opacity while marking still reads whole; the eraser's see-through pixels are not skin."""
    return (layer[..., 3] >= MASK_ALPHA) & (layer[..., :3].max(-1) > 127)


def _clean(layer):
    """A layer as it is compared: fully transparent pixels carry no colour."""
    layer = layer.copy()
    layer[layer[..., 3] == 0] = 0
    return layer


XCF_PINS = "_xcf"                       # in .generated.json: {sheet: the SHA-256 of the .xcf as this tool wrote it}


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


TUTORIAL_NAME = "How to mark skin in GIMP.txt"
TUTORIAL = ROOT / "docs" / "skin-tones-gimp-tutorial.txt"
# The two guides as they were first put in the workbench by hand, before they were pinned (SHA-256): still
# "as written", so the first build after this may bring them up to date.
FIRST_GUIDES = {
    "README.txt": {"6886980ddb01c9d2fe79206167580f37baab4858f81f751c93f7a77e1885597b"},
    TUTORIAL_NAME: {"76586ed5e6dc419ef6ff4974e405d215e222d5b43a6bd5f127b09efc0f52443f"},
}


def write_guides(workbench: Path) -> dict[str, str]:
    """README.txt and the GIMP tutorial in the workbench folder, by the rule of the .xcf files: a guide that
    is not there is written; one still exactly as this tool wrote it is brought up to date; one the owner
    has changed is left as it is.  .guides.json there pins what was written.  Returns {name: what was done}."""
    workbench.mkdir(parents=True, exist_ok=True)
    pins_path = workbench / ".guides.json"
    pins = json.loads(pins_path.read_text(encoding="utf-8")) if pins_path.is_file() else {}
    done = {}
    for name, text in (("README.txt", README), (TUTORIAL_NAME, TUTORIAL.read_text(encoding="utf-8"))):
        path, data = workbench / name, text.encode("utf-8")
        if path.is_file():
            now = _file_sha(path)
            if now == hashlib.sha256(data).hexdigest():
                done[name] = "up to date"
            elif now != pins.get(name) and now not in FIRST_GUIDES.get(name, ()):
                done[name] = "kept (changed by you)"
                continue
            else:
                done[name] = "brought up to date"
        else:
            done[name] = "written"
        path.write_bytes(data)
        pins[name] = hashlib.sha256(data).hexdigest()
    pins_path.write_text(json.dumps(pins, indent=1), encoding="utf-8")
    return done


def _manifest(folder: Path) -> dict:
    path = folder / ".generated.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def changed_by_the_owner(game, folder: Path, stems) -> list[str]:
    """The sheets whose .xcf is there and is NOT the file this tool wrote (its SHA-256 differs from the one
    recorded, or none was recorded): the owner's work, never to be replaced."""
    pins = _manifest(folder).get(XCF_PINS, {})
    return [stem for stem in stems
            if (folder / f"{game}_{stem}.xcf").is_file() and _file_sha(folder / f"{game}_{stem}.xcf") != pins.get(stem)]


def painted_from_layer(layer):
    """Where a tone's colour layer has paint: any colour, however faint.  (The layer is built with the
    sprite's own alpha, so the faint pixels of a sprite's edge are skin as built; the hard-edged eraser leaves
    nothing at all.)"""
    return layer[..., 3] > 0


def _prepare_workbench(game, images: Path, folder: Path, only, tmp: Path, fresh_backup=None, check=None) -> dict:
    """Everything a build of one game's workbench needs before GIMP runs: the owner's changed files read
    (their edits kept), and one picture a sheet to build -- its layers one under the other.

    `fresh_backup` (the owner, 2026-11-27: "i want to start fresh"): a folder name.  Every sheet is then made
    again whether or not its file was changed, nothing is read back first, and each file about to be replaced
    is first copied into <folder>/<fresh_backup>/ (a copy already there is never overwritten).
    `check`: a folder; each sheet's groups are also written there as GIMP shows them (<game>_<sheet>.png)."""
    folder.mkdir(parents=True, exist_ok=True)
    stems = [Path(s["name"]).stem for s in sheets_of(game) if find_file(Path(images), s["name"])]
    if only:
        stems = [stem for stem in stems if stem in only]
    theirs = [] if fresh_backup else changed_by_the_owner(game, folder, stems)
    unread = []
    if theirs:
        try:
            import_workbench(game, folder, theirs)
        except (SystemExit, Exception) as problem:      # GIMP missing, a file it cannot open: keep, never replace
            print(f"could not read the changed files ({problem}); they are left as they are")
            unread = list(theirs)
    edits = folder / "edits"
    art = Art(game, images, edits if edits.is_dir() else None)     # after the import: the edits just kept apply
    manifest = _manifest(folder)
    manifest.setdefault(XCF_PINS, {})
    files, made, backed_up = [], [], []
    for name in art.specs:
        stem = Path(name).stem
        if stem not in stems or stem in theirs:
            continue
        stock, mask = art.stock(name), art.mask(name)
        cell_h = art.specs[name]["cell"][1]
        white = np.zeros_like(stock)
        white[mask] = 255
        top = stock.copy()
        top[mask] = 0
        # (pixels, name, shown, locked, group, group shown, clipped to the layer under it)
        bands = [(stock, LAYER_GAME, True, True, None, False, False), (white, LAYER_MASK, False, False, None, False, False)]
        record = {"mask.png": _sha(_clean(white))}
        for number, tone in enumerate(core.TONES, 1):
            skin = art.tone_mask(name, number)
            flat = np.zeros_like(stock)
            flat[skin, :3] = tone_colour(number)
            flat[skin, 3] = stock[skin, 3]
            shaded = shaded_everywhere(stock, skin, tone, cell_h)
            if not (shaded[skin][:, :3] == art.tone_layer(name, tone)[skin][:, :3]).all():
                raise SystemExit(f"{name}, tone {number}: the shading layer is not the tone's own shading")
            group = tone_layer_name(number)
            bands.append((flat, paint_layer_name(number), True, False, group, number == SHOWN_TONE, False))
            bands.append((shaded, LAYER_SHADING, True, True, group, number == SHOWN_TONE, True))
            record[f"skin_{number:02d}.png"] = _sha(painted_from_layer(flat))      # as `import` will read it
        bands.append((top, LAYER_TOP, True, True, None, False, False))
        tall = tmp / f"{game}_{stem}.png"
        Image.fromarray(np.concatenate([band[0] for band in bands], axis=0)).save(tall, compress_level=1)
        manifest[stem] = record
        made.append(stem)
        xcf = folder / f"{game}_{stem}.xcf"
        if fresh_backup and xcf.is_file():
            kept = folder / fresh_backup / xcf.name
            kept.parent.mkdir(parents=True, exist_ok=True)
            if not kept.exists():
                shutil.copy2(xcf, kept)
            if _file_sha(kept) != _file_sha(xcf) and not kept.with_name(xcf.stem + " (2).xcf").exists():
                shutil.copy2(xcf, kept.with_name(xcf.stem + " (2).xcf"))
            backed_up.append(xcf.name)
        item = {"xcf": str(xcf), "png": str(tall), "width": int(stock.shape[1]), "height": int(stock.shape[0]),
                "layers": [{"name": label, "visible": shown, "lock": lock, "group": group, "group_visible": group_shown,
                            "clip": clip} for _, label, shown, lock, group, group_shown, clip in bands]}
        if check is not None:
            Path(check).mkdir(parents=True, exist_ok=True)
            item["check"] = str(Path(check) / f"{game}_{stem}.png")
        files.append(item)
    return {"game": game, "folder": folder, "files": files, "made": made, "manifest": manifest, "art": art,
            "kept": [stem for stem in theirs if stem not in unread], "unread": unread, "backed_up": backed_up}


def check_groups(prepared: dict) -> list[str]:
    """After a build with `check`: each tone group as GIMP shows it against the tone's own sheet (its skin
    pixels), pixel for pixel.  Returns one line per sheet."""
    art, game, lines = prepared["art"], prepared["game"], []
    for item in prepared["files"]:
        if "check" not in item:
            continue
        stem = Path(item["xcf"]).stem[len(game) + 1:]
        name = next(n for n in art.specs if Path(n).stem == stem)
        tall = _layer_pixels(Path(item["check"]))
        height, wrong = item["height"], 0
        for k, tone in enumerate(core.TONES):
            shown = _clean(tall[k * height:(k + 1) * height])
            wrong += int((shown != _clean(art.tone_layer(name, tone))).any(-1).sum())
        lines.append(f"{game} {stem}: {len(core.TONES)} tone groups, {int(art.mask(name).sum())} skin pixels each, "
                     f"{wrong} pixels differ from the tone's own sheet")
    return lines


def _finish_workbench(prepared: dict):
    """After GIMP: pin each .xcf written, and write the workbench's record."""
    game, folder, manifest = prepared["game"], prepared["folder"], prepared["manifest"]
    for stem in prepared["made"]:
        manifest[XCF_PINS][stem] = _file_sha(folder / f"{game}_{stem}.xcf")
    (folder / ".generated.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return [f["xcf"] for f in prepared["files"]], prepared["kept"], prepared["unread"]


def build_workbench(game, images: Path, folder: Path, only=None, fresh_backup=None, check=None):
    """<folder>/<game>_<sheet>.xcf for every sheet, and .generated.json (what each generated layer was, so
    `import` can tell the owner's edits from untouched layers, and what each .xcf was when written).

    NOTHING OF THE OWNER'S IS EVER REPLACED.  An .xcf that is not the file this tool wrote is the owner's: it
    is first read as `import` reads it, so its edits are in "edits", and then it is left exactly as it is.
    If it cannot be read it is left as it is too.  Only files still as written are made again.
    Returns (written, kept, unread): the .xcf files written, the owner's sheets kept (and read), and the
    owner's sheets kept that could not be read."""
    with tempfile.TemporaryDirectory() as tmp:
        prepared = _prepare_workbench(game, Path(images), folder, only, Path(tmp), fresh_backup, check)
        if prepared["files"]:
            run_gimp(_GIMP_BUILD, {"files": prepared["files"]})
    for line in check_groups(prepared):
        print(line)
    return _finish_workbench(prepared)


def build_workbenches(games_and_images, root: Path, fresh_backup=None, check=None):
    """Several games' workbenches with ONE start of GIMP (a start alone takes minutes): build_workbench for
    each (game, its Images folder), into <root>/<game>.  Returns {game: (written, kept, unread)}."""
    with tempfile.TemporaryDirectory() as tmp:
        prepared = [_prepare_workbench(game, Path(images), root / game, None, Path(tmp), fresh_backup, check)
                    for game, images in games_and_images]
        files = [item for one in prepared for item in one["files"]]
        if files:
            run_gimp(_GIMP_BUILD, {"files": files})
    for one in prepared:
        for line in check_groups(one):
            print(line)
    return {one["game"]: _finish_workbench(one) for one in prepared}


def pin_as_written(game, folder: Path, not_after: float):
    """For a workbench built before the .xcf files were pinned: pin every .xcf not modified after
    `not_after` (the time its build ended) as the file this tool wrote.  One changed since is the owner's
    and is left unpinned.  Returns the sheets pinned."""
    manifest = _manifest(folder)
    pins = manifest.setdefault(XCF_PINS, {})
    done = []
    for path in sorted(folder.glob(f"{game}_*.xcf")):
        stem = path.stem[len(game) + 1:]
        if stem not in pins and path.stat().st_mtime <= not_after:
            pins[stem] = _file_sha(path)
            done.append(stem)
    (folder / ".generated.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return done


def _keep_skin(target: Path, painted, as_built, kept, label):
    """Keep where a tone has skin as a white mark in "edits" -- or, when it is as built, withdraw the edit."""
    if _sha(painted) == as_built:
        if target.is_file():
            target.unlink()
        return
    mark = np.zeros(painted.shape + (4,), np.uint8)
    mark[painted] = 255
    target.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(mark).save(target)
    kept.append(label)


def import_workbench(game, folder: Path, only=None, same_for_all=False, source=None, say=print):
    """Read every <game>_<sheet>.xcf (or only the sheets in `only`) back through GIMP; keep where the owner
    painted each tone's colour layer (skin_NN.png) and their mask, when changed, in <folder>/edits/<sheet>/
    and drop the ones that are still as generated.  Returns what was kept.

    `same_for_all` (the owner, 2026-11-28: "copy the edited pixels of one tone to the other tones"): for each
    sheet, the paint of ONE tone -- `source` (1..10), or the one tone the owner changed -- is taken as the skin
    of all ten tones, whatever the other tones' layers hold.  The .xcf is not touched.  A sheet where several
    tones were changed differently and no `source` is given is read the ordinary way, and said so."""
    manifest = _manifest(folder)
    edits = folder / "edits"
    kept = []
    with tempfile.TemporaryDirectory() as tmp:
        files = [{"xcf": str(path), "out": str(Path(tmp) / path.stem[len(game) + 1:])}
                 for path in sorted(folder.glob(f"{game}_*.xcf"))
                 if not only or path.stem[len(game) + 1:] in only]
        if not files:
            raise SystemExit(f"no {game}_*.xcf in {folder}")
        run_gimp(_GIMP_EXPORT, {"files": files})
        for item in files:
            stem = Path(item["out"]).name
            leaves = json.loads((Path(item["out"]) / "layers.json").read_text(encoding="utf-8"))
            if not leaves:
                continue
            tall = _layer_pixels(Path(item["out"]) / "layers.png")
            height = tall.shape[0] // len(leaves)
            record = manifest.get(stem, {})
            for_all = None
            if same_for_all:
                tones = {leaf: painted_from_layer(tall[k * height:(k + 1) * height])
                         for k, leaf in enumerate(leaves) if leaf.startswith("skin_")}
                changed = [leaf for leaf in sorted(tones) if _sha(tones[leaf]) != record.get(leaf)]
                if source is not None:
                    if f"skin_{source:02d}.png" not in tones:
                        say(f"{game}_{stem}: it has no colour layer for tone {source}; read the ordinary way")
                    else:
                        for_all = f"skin_{source:02d}.png"
                elif len({_sha(tones[leaf]) for leaf in changed}) == 1:
                    for_all = changed[0]
                elif changed:
                    say(f"{game}_{stem}: tones " + ", ".join(leaf[5:7] for leaf in changed) + " were changed, and "
                        "differently, so each was read as it is. To use one of them for all ten, add --from and its number.")
                if for_all is not None:
                    say(f"{game}_{stem}: tone {for_all[5:7]}'s paint is the skin of all {len(core.TONES)} tones")
            for k, leaf in enumerate(leaves):
                layer = tall[k * height:(k + 1) * height]
                target = edits / stem / leaf
                if leaf.startswith("skin_"):
                    # A tone's colour layer: painted is skin for that tone, erased is not.  Kept as white
                    # where painted -- nothing of the game's art, and not the colour either.
                    painted = tones[for_all] if for_all is not None else painted_from_layer(layer)
                    _keep_skin(target, painted, record.get(leaf), kept, f"{stem}/{leaf}")
                    continue
                if _sha(_clean(layer)) == manifest.get(stem, {}).get(leaf):
                    if target.is_file():
                        target.unlink()         # put back as generated: the edit is withdrawn
                    continue
                if leaf == "mask.png":              # kept clean: white where skin, nothing else
                    marked = mask_from_layer(layer)
                    layer = np.zeros_like(layer)
                    layer[marked] = 255
                    if _sha(_clean(layer)) == manifest.get(stem, {}).get(leaf):
                        if target.is_file():
                            target.unlink()
                        continue                    # only its opacity differed: not an edit
                target.parent.mkdir(parents=True, exist_ok=True)
                Image.fromarray(layer).save(target)
                kept.append(f"{stem}/{leaf}")
    return kept


_GIMP_SPREAD = r'''
import hashlib, json, os, re, shutil
import gi
gi.require_version("Gimp", "3.0")
gi.require_version("Gegl", "0.4")
from gi.repository import Gimp, Gio, Gegl
FORMAT = "R'G'B'A u8"
PAINTED = bytes([0] + [1] * 255)
job = json.load(open(os.environ["VVFP_SKIN_JOB"], encoding="utf-8"))


def colour_layers(image):
    found = {}
    for group in image.get_layers():
        tone = re.match(r"Tone (\d+)", group.get_name())
        if tone and group.is_group():
            for child in group.get_children():
                if "paint here" in child.get_name():
                    found[int(tone.group(1))] = child
    return found


def alpha_of(layer, width, height):
    # The layer's alpha over the picture's own area, whatever the layer's size and place.
    at = layer.get_offsets()
    rect = Gegl.Rectangle.new(-at[-2], -at[-1], width, height)
    return bytes(layer.get_buffer().get(rect, 1.0, FORMAT, Gegl.AbyssPolicy.NONE)[3::4])


def cover(alpha):
    return hashlib.sha1(alpha.translate(PAINTED)).hexdigest()


def spread(item, result):
    image = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(item["xcf"]))
    width, height = image.get_width(), image.get_height()
    layers = colour_layers(image)
    if sorted(layers) != list(range(1, item["tones"] + 1)):
        result["did"] = "not ours"
        image.delete()
        return
    alphas = {n: alpha_of(layer, width, height) for n, layer in layers.items()}
    covers = {n: cover(alpha) for n, alpha in alphas.items()}
    changed = sorted(n for n in covers if covers[n] != item["records"].get(str(n)))
    result["changed"] = changed
    source = item.get("source")
    if source is None:
        if not changed:
            result["did"] = "unchanged"
        elif len({covers[n] for n in changed}) > 1:
            result["did"] = "several"
        else:
            source = changed[0]
    if source is None:
        image.delete()
        return
    result["source"] = source
    result["pixels"] = alphas[source].translate(PAINTED).count(1)
    targets = sorted(n for n in layers if covers[n] != covers[source])
    if not targets:
        result["did"] = "same already"
        image.delete()
        return
    # The file as it is, kept first (a copy already there is never overwritten).
    os.makedirs(item["backup"], exist_ok=True)
    stem, k = os.path.splitext(os.path.basename(item["xcf"]))[0], 1
    kept = os.path.join(item["backup"], stem + ".xcf")
    while os.path.exists(kept):
        k += 1
        kept = os.path.join(item["backup"], "%s (%d).xcf" % (stem, k))
    shutil.copy2(item["xcf"], kept)
    result["backup"] = kept
    alpha = alphas[source]
    for n in targets:
        layer = layers[n]
        at = layer.get_offsets()
        if at[-2] or at[-1] or layer.get_width() != width or layer.get_height() != height:
            layer.resize_to_image_size()
        red, green, blue = item["colours"][str(n)]
        data = bytearray(4 * width * height)
        data[0::4] = alpha.translate(bytes([0] + [red] * 255))
        data[1::4] = alpha.translate(bytes([0] + [green] * 255))
        data[2::4] = alpha.translate(bytes([0] + [blue] * 255))
        data[3::4] = alpha
        buffer = layer.get_buffer()
        buffer.set(Gegl.Rectangle.new(0, 0, width, height), FORMAT, bytes(data))
        buffer.flush()
        layer.update(0, 0, width, height)
    Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, image, Gio.File.new_for_path(item["xcf"]), None)
    image.delete()
    # Read the saved file again: every tone must now cover exactly the source's pixels.
    image = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(item["xcf"]))
    again = {n: cover(alpha_of(layer, width, height)) for n, layer in colour_layers(image).items()}
    image.delete()
    result["same"] = len(again) == item["tones"] and set(again.values()) == {covers[source]}
    result["targets"] = targets
    result["did"] = "spread"


for item in job["files"]:
    result = {"xcf": item["xcf"], "did": "nothing"}
    try:
        spread(item, result)
    except Exception as problem:
        result["did"], result["why"] = "failed", repr(problem)
    json.dump(result, open(item["result"], "w", encoding="utf-8"))
    print("VVFP spread", item["xcf"], result["did"])
'''


def held_open(path: Path):
    """Whether another program has an .xcf open: ("open" | "unknown" | "free", why).  GIMP reads a file
    and lets go of it, so no lock says a file is open in it; its windows' titles name the picture in front
    only.  So with GIMP running and the file not named, the honest answer is "unknown"."""
    try:
        with open(path, "r+b"):
            pass
    except PermissionError:
        return "open", "another program has it locked"
    except OSError as problem:
        return "unknown", str(problem)
    if os.name != "nt":
        return "unknown", "whether GIMP has it open can only be seen on Windows"
    try:
        titles = _gimp_window_titles()
    except Exception as problem:          # the list of programs or of windows could not be had
        return "unknown", f"the running programs could not be listed ({problem})"
    if titles is None:
        return "free", ""
    if any(Path(path).stem.lower() in title.lower() for title in titles):
        return "open", "GIMP has it open"
    return "unknown", "GIMP is running, and which files it has open cannot be seen"


def _gimp_window_titles():
    """The titles of every window of every running gimp*.exe (Windows), or None when none is running."""
    import csv
    import ctypes
    from ctypes import wintypes
    done = subprocess.run(["tasklist", "/fo", "csv", "/nh", "/fi", "imagename eq gimp*"],
                          capture_output=True, text=True, timeout=60)
    ids = {int(row[1]) for row in csv.reader(done.stdout.splitlines())
           if len(row) > 1 and row[0].lower().startswith("gimp") and row[1].isdigit()}
    if not ids:
        return None
    user, titles = ctypes.windll.user32, []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def each(window, _):
        owner = wintypes.DWORD()
        user.GetWindowThreadProcessId(window, ctypes.byref(owner))
        if owner.value in ids:
            text = ctypes.create_unicode_buffer(1024)
            user.GetWindowTextW(window, text, 1024)
            if text.value:
                titles.append(text.value)
        return True

    user.EnumWindows(each, 0)
    return titles


def sheet_stem(game, sheet):
    """A sheet as the owner may name it ("vv1_carrying", "vv1_carrying.xcf", "carrying") -> "carrying"."""
    stem = Path(sheet).stem if sheet.lower().endswith(".xcf") else sheet
    return stem[len(game) + 1:] if stem.lower().startswith(game + "_") else stem


def spread_tone(game, folder: Path, sheets=None, source=None, yes=False, backup=None):
    """Make every tone's colour layer of an .xcf the same painted pixels as one tone's -- `source` (1..10),
    or the one tone changed since the file was built -- each in its own tone's flat colour.  (The owner,
    2026-11-28: "to save time, i'd like to copy the edited pixels of one tone to the other tones in a
    file.")  `sheets`: the sheets ("carrying"), or None for every .xcf of the game.

    A file another program has open is left alone; when that cannot be told (GIMP is running) nothing is
    done without `yes`.  Each file changed is first copied into <folder>/<backup>.  One start of GIMP.
    Returns [(sheet, plain words)], and prints nothing."""
    import datetime
    backup = backup or f"_before spread {datetime.date.today().isoformat()}"
    manifest = _manifest(folder)
    paths = sorted(folder.glob(f"{game}_*.xcf"))
    if sheets:
        wanted = {sheet_stem(game, sheet) for sheet in sheets}
        missing = wanted - {path.stem[len(game) + 1:] for path in paths}
        if missing:
            raise SystemExit(f"no such file in {folder}: " + ", ".join(f"{game}_{stem}.xcf" for stem in sorted(missing)))
        paths = [path for path in paths if path.stem[len(game) + 1:] in wanted]
    if not paths:
        raise SystemExit(f"no {game}_*.xcf in {folder}")
    said, unknown, files = [], [], []
    with tempfile.TemporaryDirectory() as tmp:
        for path in paths:
            stem = path.stem[len(game) + 1:]
            record = manifest.get(stem, {})
            records = {str(n): record.get(f"skin_{n:02d}.png") for n in range(1, len(core.TONES) + 1)}
            if not all(records.values()):
                said.append((stem, "left alone: it is one of the older files, without a colour layer for each tone."))
                continue
            state, why = held_open(path)
            if state == "open":
                said.append((stem, f"left alone: {why}. Save it and close it in GIMP, then run this again."))
                continue
            if state == "unknown":
                unknown.append((stem, why))
            files.append({"xcf": str(path), "source": source, "tones": len(core.TONES), "records": records,
                          "colours": {str(n): [int(v) for v in tone_colour(n)] for n in range(1, len(core.TONES) + 1)},
                          "backup": str(folder / backup), "result": str(Path(tmp) / f"{stem}.json"), "stem": stem})
        if unknown and not yes:
            raise SystemExit(
                f"Nothing was changed. {unknown[0][1]}.\n"
                "If one of these files is open in GIMP, save it and close it there first: this tool rewrites the\n"
                "file on disk, and GIMP would not show the change (and saving from GIMP afterwards would undo it).\n"
                "When none of them is open in GIMP, run the same command again with --yes added.")
        if files:
            run_gimp(_GIMP_SPREAD, {"files": files})
        for item in files:
            said.append((item["stem"], _spread_words(json.loads(Path(item["result"]).read_text(encoding="utf-8")), folder)))
    return sorted(said)


def _tone_words(number):
    return f"Tone {number:02d} ({core.TONES[number - 1][4]})"


def _spread_words(result, folder: Path) -> str:
    did, changed = result["did"], result.get("changed", [])
    if did == "spread":
        kept = Path(result["backup"])
        where = kept.relative_to(folder) if kept.is_relative_to(folder) else kept
        if not result.get("same"):
            return (f"SOMETHING WENT WRONG: after copying {_tone_words(result['source'])}'s skin, the tones do not all "
                    f"cover the same pixels. The file as it was is safe in {where}")
        return (f"copied {_tone_words(result['source'])}'s skin to the other {len(result['targets'])} tones that differed. "
                f"All {len(core.TONES)} tones now cover the same "
                f"{result['pixels']:,} pixels (checked in the saved file). The file as it was is in {where}")
    if did == "same already":
        return f"nothing to do: every tone already covers the same pixels as {_tone_words(result['source'])}."
    if did == "unchanged":
        return "nothing to do: no tone has been changed since the file was built. (To copy a tone anyway, add --from and its number.)"
    if did == "several":
        return ("left alone: " + ", ".join(_tone_words(n) for n in changed) + " were changed, and differently. "
                "Say which one to copy: add --from and its number.")
    if did == "not ours":
        return "left alone: it does not have the ten tone folders with their colour layers."
    if result.get("backup"):
        return f"FAILED ({result.get('why', did)}). The file as it was is in {result['backup']}"
    return f"FAILED ({result.get('why', did)}). The file was not changed."


def publish_edits(art: Art, edits: Path, out: Path):
    """The owner's kept edits (<workbench>/<game>/edits) as shippable files under `out`/<game>/<sheet>/:
    skin_NN.png for each tone whose colour layer the owner painted, and mask.png when they changed the
    "Skin mask" -- each white where skin and nothing else, on pixels of the sprite only.  WHERE the skin is
    ships; no colour and nothing of a game's art does.  Then `out`/manifest.json is written again for
    everything under `out`.  Returns the files written."""
    written = []
    target = out / art.game
    if target.is_dir():
        for old in sorted(target.rglob("*.png")):
            old.unlink()
    for name in art.specs:
        stem = Path(name).stem
        folder = edits / stem
        if not folder.is_dir():
            continue
        marks = {}
        if (folder / "mask.png").is_file():
            marks["mask.png"] = art.mask(name)
        for number in range(1, len(core.TONES) + 1):
            if (folder / f"skin_{number:02d}.png").is_file():
                marks[f"skin_{number:02d}.png"] = art.tone_mask(name, number)
        for leaf, mask in marks.items():
            (target / stem).mkdir(parents=True, exist_ok=True)
            white = np.zeros(mask.shape + (4,), np.uint8)
            white[mask] = 255
            Image.fromarray(white).save(target / stem / leaf)
            written.append(f"{art.game}/{stem}/{leaf}")
    write_manifest(out)
    return written


def write_manifest(out: Path):
    """`out`/manifest.json: {"<game>/<sheet>/<file>.png": its SHA-256} for every picture under `out`."""
    out.mkdir(parents=True, exist_ok=True)
    pins = {path.relative_to(out).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(out.rglob("*.png"))}
    (out / "manifest.json").write_text(json.dumps(pins, indent=1, sort_keys=True) + "\n", encoding="utf-8")


README = """VVFP Skin Tones Workbench
=========================

One GIMP file per head and body sheet of each game, for marking by hand where each skin tone goes.
These files hold the game's own art. Keep them here; they must never be shared or shipped.

THE LAYERS (top to bottom)
  Hair and non-skin (vanilla)  The original's hair, eyes, mouths and clothes. Locked.
  Tone 10 - S10 Ebony ...      One folder (layer group) per skin tone, dark to light, down to
  Tone 01 - S1 Porcelain       Tone 01 - S1 Porcelain. One is shown; click a folder's eye to see
                               another. Inside each folder:
      Shading (locked)             The game art's own light and dark, in the tone's colours. It
                                   shows only where the colour layer under it has paint.
                                   Never paint it.
      <tone> colour (paint here)   Flat paint in the tone's colour on every pixel that is skin
                                   in that tone. THE LAYER YOU EDIT: paint = skin, erased = not.
  Skin mask                    From the first version of these files. Hidden. White = skin for
                               every tone whose colour layer you have not changed yourself.
  Game's own art               The original sheet. Locked. Shows wherever a tone has no paint.

HOW TO EDIT
  Step by step, with GIMP's tools and keys: see "How to mark skin in GIMP.txt" in this folder.
  - Open a tone's folder and click its "colour (paint here)" layer.
  - Pencil to add skin, Eraser to remove it. Any paint colour works: the Shading layer gives it
    the tone's shaded colour as you paint.
  - Each tone is separate. A change in one tone is in that tone only. To copy one tone's skin
    to the other nine in a file (save and close it in GIMP first):
        python scripts\\skin_tone_sheets.py spread --game vv1 --sheet vv1_carrying
    or leave the file alone and run "import" with  --same-for-all-tones  added.
  - Hide "Hair and non-skin (vanilla)" while you work: it lies on top and would cover skin you
    add over hair or clothes.
  - Do not paint the Shading layer. Do not rename, merge or delete layers or folders, and do not
    resize the picture.
  - Save as .xcf under the same name (Ctrl+S).

HOW TO GET YOUR EDITS INTO THE MOD
  Run, from the patcher's folder:
      python scripts\\skin_tone_sheets.py import --game vv1      (vv1 ... vv5)
  It asks GIMP to read your .xcf files and keeps, for every tone whose colour layer you changed,
  where you painted, in
      <this folder>\\<game>\\edits\\<sheet>\\skin_NN.png        (NN = the tone's number)
  (and mask.png if you changed the Skin mask). Whatever is in "edits" wins from then on.
  Only WHERE the skin is gets kept. The colours and the shading are always made again from the
  game's own art.
  A tone you did not change is not kept, so it still follows later changes to the automatic mask.
  To drop an edit, delete its file in "edits".

TO PUT YOUR EDITS IN THE PATCHER ITSELF (so every player gets them)
      python scripts\\skin_tone_sheets.py publish --game vv1 --images "<the game's Images folder>"
  It copies where you marked skin into the patcher's
      assets\\skin_tones\\owner_edits\\<game>\\<sheet>\\
  as plain white marks: no colour and nothing of the game's own art goes with them. The patcher
  makes each tone from every player's own game files, on the pixels you marked.

TO MAKE THE FILES AGAIN (safe: nothing of yours is ever replaced)
      python scripts\\skin_tone_sheets.py workbench --game vv1 --images "<the game's Images folder>"
  A file you have changed is never overwritten. It is read first, exactly as "import" reads it, so its
  edits are kept in "edits", and then it is left as it is. Only files you have not touched are made
  again (with your "edits" applied). To have one of your own files made again, delete it yourself first.
  "import" is still how to bring "edits" up to date after you paint.

THE OLDER FILES
  The files as they were before 2026-11-27 (one flat layer a tone) are in each game's
  "_before overlay 2026-11-27" folder.
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("what", choices=["preview", "sheets", "workbench", "import", "mockup", "heathens", "publish", "audit",
                                    "workbench-all", "spread"])
    ap.add_argument("--game", choices=sorted(TITLES))
    ap.add_argument("--images-root", type=Path, help="mockup: the folder holding every game's own folder")
    ap.add_argument("--images", type=Path, help="the game's own Images folder (read only)")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--masks", action="store_true", help="preview: also a mask picture per sheet")
    ap.add_argument("--workbench", type=Path, default=WORKBENCH)
    ap.add_argument("--only", nargs="*", help="workbench: only these sheets (file names without .png)")
    ap.add_argument("--fresh-backup", help="workbench: make EVERY sheet again, first copying each file replaced "
                                           "into this folder beside it; nothing is read back first")
    ap.add_argument("--check", type=Path, help="workbench: also write each sheet's tone groups as GIMP shows them "
                                               "into this folder, and compare them with the tones' own sheets")
    ap.add_argument("--sheet", nargs="*", help="spread, import: only these files (vv1_carrying or carrying)")
    ap.add_argument("--all-sheets", action="store_true", help="spread: every .xcf of the game")
    ap.add_argument("--from", dest="source", type=int, choices=range(1, len(core.TONES) + 1), metavar="TONE",
                    help="spread, import --same-for-all-tones: the tone (1-10) whose painted pixels are copied; "
                         "left out, the one tone you changed")
    ap.add_argument("--yes", action="store_true", help="spread: go ahead although it cannot be seen whether GIMP "
                                                       "has the file open (you have checked that it has not)")
    ap.add_argument("--same-for-all-tones", action="store_true",
                    help="import: take the one changed tone's paint as the skin of all ten tones (the .xcf is not touched)")
    args = ap.parse_args()
    if args.what == "mockup":
        mockup(args.images_root, args.out, args.workbench if args.workbench.is_dir() else None)
        return 0
    if args.what == "workbench-all":
        for name, what in write_guides(args.workbench).items():
            print(f"{name}: {what}")
        games = [g for g in sorted(TITLES) if not args.only or g in args.only]
        done = build_workbenches([(g, args.images_root / FOLDERS[g] / "Images") for g in games], args.workbench,
                                 args.fresh_backup, args.check)
        for game, (written, kept, unread) in done.items():
            print(f"{game}: wrote {len(written)}; kept {len(kept)} changed by you (edits read); "
                  f"kept {len(unread)} changed by you that could not be read")
        return 0
    if not args.game:
        raise SystemExit("--game is needed")
    folder = args.workbench / args.game
    if args.what == "spread":
        if bool(args.sheet) == bool(args.all_sheets):
            raise SystemExit("say which file with --sheet (for example --sheet vv1_carrying), or --all-sheets for every file of the game")
        for stem, words in spread_tone(args.game, folder, args.sheet or None, args.source, args.yes):
            print(f"{args.game}_{stem}: {words}")
        print('To bring the result into the mod, run "import" for this game. If a file was open in GIMP, open it again there.')
        return 0
    if args.what == "import":
        kept = import_workbench(args.game, folder, [sheet_stem(args.game, s) for s in args.sheet] if args.sheet else None,
                                args.same_for_all_tones, args.source)
        print("kept", len(kept), "edited layers in", folder / "edits")
        for line in kept:
            print(" ", line)
        return 0
    if args.images is None:
        raise SystemExit("--images is needed")
    edits = folder / "edits"
    art = Art(args.game, args.images, edits if edits.is_dir() else None)
    if args.what == "publish":
        if not edits.is_dir():
            raise SystemExit(f"no edits in {edits}: run `import` first")
        for line in publish_edits(Art(args.game, args.images, edits, shipped=False), edits, SHIPPED_EDITS):
            print("wrote", line)
        return 0
    if args.what == "heathens":
        heathens(args.images, args.out)
        return 0
    if args.what == "audit":
        for line in audit(art, args.out):
            print(line)
        return 0
    if args.what == "preview":
        previews(art, args.out, args.masks)
    elif args.what == "sheets":
        if args.out.resolve().is_relative_to(ROOT) and "previews" not in args.out.parts:
            raise SystemExit("--out must be outside the repository: sheets made from game art are never committed")
        write_sheets(art, args.out)
    else:
        for name, what in write_guides(args.workbench).items():
            print(f"{name}: {what}")
        written, kept, unread = build_workbench(args.game, args.images, folder, args.only, args.fresh_backup,
                                                args.check)
        for path in written:
            print("wrote", path)
        for stem in kept:
            print("kept (changed by you; its edits are in \"edits\"):", f"{args.game}_{stem}.xcf")
        for stem in unread:
            print("kept (changed by you; it could NOT be read, nothing was done to it):", f"{args.game}_{stem}.xcf")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
