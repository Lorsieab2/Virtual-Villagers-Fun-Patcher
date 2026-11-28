"""Skin tones for all five games: the sheets, the previews, and the owner's GIMP workbench.

    python scripts/skin_tone_sheets.py preview   --game vv3 --images "<game>\\Images" --out previews
    python scripts/skin_tone_sheets.py sheets    --game vv3 --images "<game>\\Images" --out "<folder>"
    python scripts/skin_tone_sheets.py workbench --game vv3 --images "<game>\\Images"
    python scripts/skin_tone_sheets.py workbench-all --images-root "<the folder of the five games>"
    python scripts/skin_tone_sheets.py import    --game vv3 [--same-for-all-tones]
    python scripts/skin_tone_sheets.py spread    --game vv3 --sheet vv3_carrying [--from 10]   (or --all-sheets)
    python scripts/skin_tone_sheets.py learn     --game vv3 --images-root "<the folder of the five games>" [--write]
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
        edited = self._edit(name, "mask.png") or self._edit(name, LEARNED_MASK)
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
LAYER_SHADING, PAINT_WORDS = "Shading (locked)", "colour (paint here)"   # LAYER_SHADING: the files before 2026-11-28
SHADING_WORDS = "shading (locked)"
SHOWN_TONE = 10         # the tone shown, and its folder open, in a new .xcf: Ebony, the tone the owner edits
QUICK_LAYOUT_BACKUP = "_before quick-edit layout 2026-11-28"


def tone_layer_name(number):
    """A tone's GROUP in an .xcf."""
    return f"Tone {number:02d} - S{number} {core.TONES[number - 1][4]}"


def paint_layer_name(number):
    """The layer of a tone's group the owner paints: flat colour where that tone has skin."""
    return f"{core.TONES[number - 1][4]} {PAINT_WORDS}"


def shading_layer_name(number):
    """The locked shading layer of a tone's group: "Ebony shading (locked)".  (Files before 2026-11-28 have
    "Shading (locked)", "Shading (locked) #1" ... "#9"; nothing reads either name: the readers find a tone's
    group by "Tone NN" and its colour layer by "paint here".)"""
    return f"{core.TONES[number - 1][4]} {SHADING_WORDS}"


def is_paint_layer(name: str) -> bool:
    """Whether a layer of a tone's group is its colour layer (the one the owner paints), by old or new names."""
    return "paint here" in name


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
    groups, order, active = {}, [], None
    for part, layer in zip(parts, item["layers"]):
        part.set_name(layer["name"])
        part.set_visible(bool(layer["visible"]))
        if layer.get("clip"):
            # Shown only where the layer under it in its group has paint.
            part.set_composite_mode(Gimp.LayerCompositeMode.CLIP_TO_BACKDROP)
        if layer["lock"]:
            part.set_lock_content(True)
            part.set_lock_position(True)
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
                group.set_expanded(bool(layer["group_visible"]))    # the tone shown is the folder open
                groups[name] = group
                order.append(name)
            image.reorder_item(part, groups[name], 0)
        if layer.get("active"):
            active = part
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
    if active is not None:
        image.set_selected_layers([active])     # opens ready to paint
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


def run_gimp(script: str, job: dict, idle=True):
    """One GIMP batch process (never two at once) running `script` with `job`; `idle`: at idle priority."""
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
        quiet = {"creationflags": 0x00000040} if os.name == "nt" and idle else {}
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
            bands.append((shaded, shading_layer_name(number), True, True, group, number == SHOWN_TONE, True))
            record[f"skin_{number:02d}.png"] = _sha(painted_from_layer(flat))      # as `import` will read it
        bands.append((top, LAYER_TOP, False, True, None, False, False))    # hidden: it would cover new skin
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
                            "clip": clip, "active": label == paint_layer_name(SHOWN_TONE)}
                           for _, label, shown, lock, group, group_shown, clip in bands]}
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
    sheet, the paint of ONE tone -- `source` (1..10), or tone 10 (Ebony) when the owner changed it, or the one
    tone they changed -- is taken as the skin
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
            learned = (json.loads((folder / LEARNED).read_text(encoding="utf-8")).get("sheets", [])
                       if (folder / LEARNED).is_file() else [])
            if stem in learned and "mask.png" in leaves and not (edits / stem / LEARNED_MASK).is_file():
                # A sheet rebuilt with a learned skin whose learned mask is gone: its "Skin mask" layer, when it is
                # still as built, IS that skin.
                layer = tall[leaves.index("mask.png") * height:(leaves.index("mask.png") + 1) * height]
                marked = mask_from_layer(layer)
                mark = np.zeros_like(layer)
                mark[marked] = 255
                if _sha(_clean(mark)) == record.get("mask.png"):
                    (edits / stem).mkdir(parents=True, exist_ok=True)
                    Image.fromarray(mark).save(edits / stem / LEARNED_MASK)
                    say(f"{game}_{stem}: its learned skin was put back in edits ({LEARNED_MASK})")
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
                elif f"skin_{len(core.TONES):02d}.png" in changed:
                    for_all = f"skin_{len(core.TONES):02d}.png"    # Ebony is the tone the owner edits
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
        elif item["tones"] in changed:
            source = item["tones"]      # Tone 10 (Ebony) is the tone the owner edits: the others follow it
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
    or tone 10 (Ebony, the tone the owner edits) when it was changed since the file was built, or else the
    one tone that was -- each in its own tone's flat colour.  (The owner,
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


# ---- learning from the owner's edits (the owner, 2026-11-28: "the other unedited gimp files should attempt to
# recolor the skin and nonskin parts based on the edited ones (to make my job easier)")
LEARNED = "learned.json"            # <workbench>/<game>/learned.json: the rule last applied, and the sheets it was put on
# A sheet's learned skin is kept as edits/<sheet>/learned_mask.png -- NOT as mask.png: `import` withdraws a mask.png
# that equals the file's own "Skin mask" layer (it is then no edit of the owner's), and a file rebuilt with the
# learned skin has exactly that layer.  (Found 2026-11-28: an import after `learn --write` deleted all 18 learned
# masks.)  The owner's own mask.png, when there is one, wins over it.
LEARNED_MASK = "learned_mask.png"
LEARN_LEAST, LEARN_TIMES = 3, 4     # a colour counts when changed on this many pixels, this many times oftener one way


def _packed(rgb, width=1):
    """Each pixel's colour as one number (0xRRGGBB).  `width` > 1: its colour BUCKET instead -- red, green and
    blue each in steps of `width` levels, so that near-identical colours count together."""
    rgb = (rgb // max(1, width)).astype(np.uint32)
    return (rgb[..., 0] << 16) | (rgb[..., 1] << 8) | rgb[..., 2]


def read_colour_layers(paths, tmp: Path) -> dict:
    """{path: {leaf: pixels}} -- every tone's colour layer (skin_NN.png) and the "Skin mask" (mask.png) of each
    .xcf, read through GIMP from a COPY of the file (the owner's file is only ever copied).  One start of GIMP."""
    files = []
    for k, path in enumerate(paths):
        copy = tmp / f"copy{k}" / Path(path).name
        copy.parent.mkdir(parents=True)
        shutil.copy2(path, copy)
        files.append({"xcf": str(copy), "out": str(tmp / f"out{k}")})
    if files:
        run_gimp(_GIMP_EXPORT, {"files": files})
    read = {}
    for path, item in zip(paths, files):
        leaves = json.loads((Path(item["out"]) / "layers.json").read_text(encoding="utf-8"))
        read[path] = {}
        if leaves:
            tall = _layer_pixels(Path(item["out"]) / "layers.png")
            height = tall.shape[0] // len(leaves)
            read[path] = {leaf: tall[k * height:(k + 1) * height] for k, leaf in enumerate(leaves)}
    return read


def owners_skin(layers: dict, record: dict, built):
    """What the owner made skin on an edited sheet, and from which layers: tone 10 (Ebony) when it was changed
    since the build, else the tones that were (a pixel is skin when most of them have paint there), else None.
    -> (skin, the tones)."""
    votes = [(leaf, painted_from_layer(layer)) for leaf, layer in sorted(layers.items())
             if leaf.startswith("skin_") and layer.shape[:2] == built.shape
             and _sha(painted_from_layer(layer)) != record.get(leaf)]
    if not votes:
        return None, []
    ebony = f"skin_{len(core.TONES):02d}.png"
    for leaf, vote in votes:            # the owner, 2026-11-28: "i'll edit the ebony skin tone and the others can
        if leaf == ebony:               # hopefully follow suit" -- Ebony alone speaks when it was changed
            return vote, [leaf[5:7]]
    count = np.sum([vote for _leaf, vote in votes], axis=0)
    return count * 2 > len(votes), [leaf[5:7] for leaf, _vote in votes]


def learn_counts(stock, built, skin, cell_h, width=1) -> dict:
    """{colour: [added, removed, kept skin, kept not skin]} over a sheet's opaque pixels: the game's own colour
    under each pixel the owner ADDED to the skin, REMOVED from it, or left as it was built.  Only the rows of
    the sheet the owner worked on count (a row with no change at all may simply not be done yet)."""
    done = np.zeros(built.shape, bool)
    for top in range(0, built.shape[0], cell_h):
        if (skin[top:top + cell_h] != built[top:top + cell_h]).any():
            done[top:top + cell_h] = True
    opaque = (stock[..., 3] > 0) & done
    colours = _packed(stock[..., :3], width)
    counts = {}
    for column, where in enumerate((skin & ~built & opaque, built & ~skin & opaque, built & skin & opaque,
                                    opaque & ~built & ~skin)):
        values, numbers = np.unique(colours[where], return_counts=True)
        for value, number in zip(values.tolist(), numbers.tolist()):
            counts.setdefault(value, [0, 0, 0, 0])[column] += number
    return counts


def add_counts(total: dict, more: dict) -> dict:
    for colour, row in more.items():
        mine = total.setdefault(colour, [0, 0, 0, 0])
        for k in range(4):
            mine[k] += row[k]
    return total


def learned_rule(counts: dict, least=LEARN_LEAST, times=LEARN_TIMES):
    """-> (skin, not skin, mixed, rare).  A colour is SKIN everywhere when the owner added it to the skin on at
    least `least` pixels, `times` times as often as they removed it, AND on the rows they worked on it ends up
    skin `times` times as often as not (a colour they added in one place but left as clothes in many others
    says nothing).  NOT SKIN the other way round.  A colour changed without such a lead is mixed, one changed
    on fewer than `least` pixels rare: both are left as built.  A colour never changed is in none of them."""
    skin, non, mixed, rare = set(), set(), set(), set()
    for colour, (added, removed, kept, kept_not) in counts.items():
        if not added and not removed:
            continue
        if added >= least and added >= times * removed and added + kept >= times * kept_not:
            skin.add(colour)
        elif removed >= least and removed >= times * added and removed + kept_not >= times * kept:
            non.add(colour)
        elif added + removed < least:
            rare.add(colour)
        else:
            mixed.add(colour)
    return skin, non, mixed, rare


def apply_rule(stock, built, skin_colours: set, not_colours: set, width=1):
    """A sheet's skin by the learned rule: as built, plus every opaque pixel of a skin colour, less every pixel
    of a not-skin colour (colours, or colour buckets `width` levels wide, as they were counted)."""
    colours = _packed(stock[..., :3], width)
    is_skin = np.isin(colours, np.array(sorted(skin_colours), np.uint32))
    is_not = np.isin(colours, np.array(sorted(not_colours), np.uint32))
    return ((built | is_skin) & ~is_not) & (stock[..., 3] > 0)


def learn(games_and_images, root: Path, across=False, write=False, yes=False, least=LEARN_LEAST, times=LEARN_TIMES,
          tolerance=0, say=print, backup=None):
    """Learn, from the sheets the owner edited, which of the game's own colours are skin and which are not, and
    put that on the sheets still exactly as built.

    Reads every .xcf the owner changed (a copy of it, through GIMP).  `across`: one rule from all the games'
    edits together, else one a game.  Without `write` (the dry run) nothing at all is written: it says the
    rule and, sheet by sheet, the pixels that would be added and removed.  `tolerance`: colours are counted
    and matched in buckets that many levels wide (0 or 1: exact colours).  With `write`, for each sheet that
    is still as built, not open in GIMP, and would change: its new skin is kept as
    <game>/edits/<sheet>/mask.png, the .xcf is copied into <game>/<backup> and made again (every tone's colour
    layer on the new skin; colours and shading as ever).  A file the owner changed is never written.  With
    GIMP running it cannot be seen which files it has open: then nothing is rebuilt without `yes`.
    Returns {game: {sheet: (added, removed)}} for the sheets that change."""
    import datetime
    backup = backup or f"_before learned recolor {datetime.date.today().isoformat()}"
    games = []
    for game, images in games_and_images:
        folder = root / game
        base = Art(game, images, shipped=False)                 # the masks as first built: no edits, no rule
        stems = {Path(name).stem: name for name in base.specs if (folder / f"{game}_{Path(name).stem}.xcf").is_file()}
        theirs = changed_by_the_owner(game, folder, list(stems))
        games.append({"game": game, "images": images, "folder": folder, "base": base, "stems": stems, "theirs": theirs,
                      "counts": {}, "manifest": _manifest(folder)})
    with tempfile.TemporaryDirectory() as tmp:
        paths = [one["folder"] / f"{one['game']}_{stem}.xcf" for one in games for stem in one["theirs"]]
        read = read_colour_layers(paths, Path(tmp)) if paths else {}
    for one in games:
        game, base, folder = one["game"], one["base"], one["folder"]
        for stem in one["theirs"]:
            name = one["stems"][stem]
            built, stock = base.mask(name), base.stock(name)
            record = one["manifest"].get(stem, {})
            if _sha(built) != record.get("skin_01.png"):            # built on a skin already learned or edited
                with_edits = Art(game, one["images"], folder / "edits", shipped=False).mask(name)
                if _sha(with_edits) == record.get("skin_01.png"):
                    built = with_edits
            skin, tones = owners_skin(read[one["folder"] / f"{game}_{stem}.xcf"], one["manifest"].get(stem, {}), built)
            if skin is None:
                say(f"{game}_{stem}: yours, but no tone's skin differs from the build: nothing to learn from it")
                continue
            counts = learn_counts(stock, built, skin, base.specs[name]["cell"][1], max(1, tolerance))
            add_counts(one["counts"], counts)
            added, removed = sum(row[0] for row in counts.values()), sum(row[1] for row in counts.values())
            rule = learned_rule(counts, least, times)
            again = apply_rule(stock, built, rule[0], rule[1], max(1, tolerance))
            put, cut = again & ~built, built & ~again
            say(f"{game}_{stem}: learned from tone{'s' if len(tones) > 1 else ''} {', '.join(tones)}: "
                f"you added {added:,} pixels to the skin and removed {removed:,}. Its own rule, tried on this same "
                f"sheet, would add {int(put.sum()):,} pixels ({int((put & skin).sum()):,} of them skin in your edit) "
                f"and remove {int(cut.sum()):,} ({int((cut & ~skin).sum()):,} of them not skin in your edit)")
    pooled = {}
    if across:
        for one in games:
            add_counts(pooled, one["counts"])
    done = {}
    for one in games:
        game, folder, base = one["game"], one["folder"], one["base"]
        counts = pooled if across else one["counts"]
        skin, non, mixed, rare = learned_rule(counts, least, times)
        say(f"{game}: the rule{' (from all the games together)' if across else ''}"
            f"{f' (colours within {tolerance} levels counted together)' if tolerance > 1 else ' (exact colours)'}: {len(skin):,} colours are skin "
            f"(you added them on {sum(counts[c][0] for c in skin):,} pixels, removed on {sum(counts[c][1] for c in skin):,}); "
            f"{len(non):,} colours are not skin (removed on {sum(counts[c][1] for c in non):,}, added on "
            f"{sum(counts[c][0] for c in non):,}); left as built: {len(mixed):,} mixed colours, {len(rare):,} rare ones")
        if not skin and not non:
            done[game] = {}
            continue
        changes, masks = {}, {}
        for stem, name in one["stems"].items():
            if stem in one["theirs"]:
                continue
            built = base.mask(name)
            new = apply_rule(base.stock(name), built, skin, non, max(1, tolerance))
            added, removed = int((new & ~built).sum()), int((built & ~new).sum())
            if added or removed:
                changes[stem], masks[stem] = (added, removed), new
                say(f"  {game}_{stem}: {added:,} pixels added to the skin, {removed:,} removed (of {int(built.sum()):,})")
        say(f"{game}: {len(changes)} of the {len(one['stems']) - len(one['theirs'])} sheets still as built would change; "
            f"{len(one['theirs'])} are yours and are never touched" + (": " + ", ".join(sorted(one["theirs"])) if one["theirs"] else ""))
        done[game] = changes
        if not write or not changes:
            continue
        free, unknown = [], []
        for stem in sorted(changes):
            state, why = held_open(folder / f"{game}_{stem}.xcf")
            if state == "open":
                say(f"  {game}_{stem}: left alone: {why}")
            elif state == "unknown" and not yes:
                unknown.append(why)
            else:
                free.append(stem)
        if unknown:
            say(f"{game}: nothing was rebuilt. {unknown[0]}. Close GIMP and run this again, or, when none of these "
                "files is open in GIMP, run it again with --yes added.")
            continue
        was = json.loads((folder / LEARNED).read_text(encoding="utf-8")).get("sheets", []) if (folder / LEARNED).is_file() else []
        for stem in free:
            mark = np.zeros(masks[stem].shape + (4,), np.uint8)
            mark[masks[stem]] = 255
            (folder / "edits" / stem).mkdir(parents=True, exist_ok=True)
            Image.fromarray(mark).save(folder / "edits" / stem / LEARNED_MASK)
        (folder / LEARNED).write_text(json.dumps({
            "sheets": sorted(set(was) | set(free)), "least": least, "times": times, "tolerance": tolerance,
            "skin": [f"{c:06x}" for c in sorted(skin)], "not skin": [f"{c:06x}" for c in sorted(non)]}, indent=1), encoding="utf-8")
        written, _kept, _unread = build_workbench(game, one["images"], folder, only=free, fresh_backup=backup)
        say(f"{game}: made {len(written)} files again with the learned skin; each as it was is in {backup}")
    return done


# ---- learning by outfit (the owner, 2026-11-28, chose it over one colour rule for a whole game): what the owner
# made skin or cloth on a body is carried to the SAME body's rows of the other sheets.  The big body pictures and
# the small walking frames are different drawings of the same outfit (another pose, half the size), so no pixel of
# one lies on a pixel of the other: what is carried is the outfit's own colours.  A pixel of a frame changes only
# when its colour is, within a tight tolerance, a colour of that outfit which the owner made all skin or all cloth.
OUTFIT_RADIUS, OUTFIT_PURE = 6, 0.95


def _body_cells(spec, shape):
    """The cells of a body sheet as (sex, body number, y, x, height, width).  A sheet for one sex: every frame
    of row r is body first + r.  The big bodies (no sex of its own, two columns): column 0 male, 1 female."""
    w, h = spec["cell"]
    rows, cols = shape[0] // h, shape[1] // w
    if spec["kind"] != "bodies":
        return []
    if spec["sex"] is None and cols != 2:
        return []
    return [(spec["sex"] or ("male", "female")[c], spec["first"] + r, r * h, c * w, h, w)
            for r in range(rows) for c in range(cols)]


def outfit_tables(spec, stock, built, skin, columns=None) -> dict:
    """{(sex, body): (colours, skin counts, not-skin counts)} from an edited body sheet: for each outfit the
    owner worked on (a cell with any change; on a one-sex sheet, any frame of the row), every colour of its
    opaque pixels with how often the owner has it as skin and as not skin.  `columns` (a slice) limits the
    pixels of each cell that are read (the self check reads one half and predicts the other)."""
    cells = _body_cells(spec, stock.shape)
    worked = {(sex, body) for sex, body, y, x, h, w in cells if (skin[y:y + h, x:x + w] != built[y:y + h, x:x + w]).any()}
    pooled = {}
    for sex, body, y, x, h, w in cells:
        if (sex, body) not in worked:
            continue
        part = (slice(y, y + h), slice(x, x + w) if columns is None else slice(x + columns.start, x + columns.stop))
        opaque = stock[part][..., 3] > 0
        colours = _packed(stock[part][..., :3])[opaque]
        verdict = skin[part][opaque]
        counts = pooled.setdefault((sex, body), {})
        for is_skin in (True, False):
            values, numbers = np.unique(colours[verdict == is_skin], return_counts=True)
            for value, number in zip(values.tolist(), numbers.tolist()):
                counts.setdefault(value, [0, 0])[0 if is_skin else 1] += number
    tables = {}
    for key, counts in pooled.items():
        values = np.array(sorted(counts), np.uint32)
        rgb = np.stack([values >> 16, (values >> 8) & 255, values & 255], axis=1).astype(np.int16)
        both = np.array([counts[v] for v in values.tolist()], np.int64).reshape(-1, 2)
        tables[key] = (rgb, both[:, 0], both[:, 1])
    return tables


def outfit_decide(table, rgb, radius=OUTFIT_RADIUS, least=LEARN_LEAST, pure=OUTFIT_PURE):
    """For each colour of `rgb` (N x 3): 1 skin, 0 not skin, -1 no decision.  A colour is decided only when the
    outfit's colours within `radius` levels of it (on each of red, green and blue) were seen on at least `least`
    pixels and `pure` of those the owner has the same way."""
    from scipy.spatial import cKDTree
    colours, as_skin, as_not = table
    out = np.full(len(rgb), -1, np.int8)
    if not len(colours) or not len(rgb):
        return out
    unique, back = np.unique(rgb.astype(np.int16), axis=0, return_inverse=True)
    near = cKDTree(colours).query_ball_point(unique, radius + 0.5, p=np.inf)
    verdict = np.full(len(unique), -1, np.int8)
    for k, found in enumerate(near):
        if not found:
            continue
        yes, no = int(as_skin[found].sum()), int(as_not[found].sum())
        if yes + no >= least:
            if yes >= pure * (yes + no):
                verdict[k] = 1
            elif no >= pure * (yes + no):
                verdict[k] = 0
    return verdict[back.reshape(-1)]


def orange_or_yellow(cell, skin):
    """The pixels of a frame that are orange or yellow in the game's art (OKLCh hue 50 to 110 degrees) and clearly
    more saturated than the frame's own skin `skin` -- cloth, hair, fruit, beads, flowers, masks.  The owner,
    2026-11-28: "be careful painting orange and yellow things."  With no skin to compare with, every orange or
    yellow pixel of any strength counts."""
    lab = core.to_oklab(cell[..., :3])
    chroma = np.hypot(lab[..., 1], lab[..., 2])
    hue = np.degrees(np.arctan2(lab[..., 2], lab[..., 1])) % 360
    limit = (max(float(np.percentile(chroma[skin], 90)) * 1.15, float(np.median(chroma[skin])) + 0.02)
             if skin.any() else 0.02)
    return (cell[..., 3] > 0) & (hue >= 50) & (hue <= 110) & (chroma > limit)


def _carry_to_cell(table, cell, was, radius):
    """One frame's skin with an outfit's rule on it -> (skin, how many pixels followed their neighbours).
    First the pixels whose own colour decides.  Then the specks left among them: an undecided pixel inside the
    sprite follows its neighbours when at least 6 of the 8 around it are now the other way and at least 3 of
    those were themselves changed by a decision (twice over, so a speck two pixels wide goes too)."""
    from scipy import ndimage
    opaque = cell[..., 3] > 0
    verdict = np.full(opaque.shape, -1, np.int8)
    verdict[opaque] = outfit_decide(table, cell[..., :3][opaque], radius)
    # Orange and yellow things are never ADDED to the skin by a near colour or by their neighbours: only when
    # the owner painted that very colour as skin on this outfit (and nowhere on it as cloth).  Removing is free.
    colours, as_skin, as_not = table
    theirs = {(int(r) << 16) | (int(g) << 8) | int(b)
              for (r, g, b), yes, no in zip(colours.tolist(), as_skin.tolist(), as_not.tolist()) if yes and not no}
    never = orange_or_yellow(cell, was) & ~np.isin(_packed(cell[..., :3]), np.array(sorted(theirs), np.uint32))
    now = was.copy()
    now[(verdict == 1) & ~never] = True
    now[verdict == 0] = False
    around = np.ones((3, 3), int)
    around[1, 1] = 0
    count = lambda what: ndimage.convolve(what.astype(int), around, mode="constant")
    followed = 0
    for _ in range(2):
        free = opaque & (verdict == -1)
        off = free & now & (count(opaque & ~now) >= 6) & (count(was & ~now) >= 3)
        on = free & ~now & ~never & (count(now) >= 6) & (count(now & ~was) >= 3)
        now[off], now[on] = False, True
        followed += int(off.sum()) + int(on.sum())
    return now, followed


def apply_outfits(spec, stock, built, tables, radius=OUTFIT_RADIUS):
    """A body sheet's skin with the owner's outfits carried to it -> (skin, frames matched, frames skipped).  A
    frame is matched when the owner worked on its outfit (same sex, same body number); every other frame is
    left exactly as built."""
    new, matched, skipped = built.copy(), 0, 0
    for sex, body, y, x, h, w in _body_cells(spec, stock.shape):
        cell = stock[y:y + h, x:x + w]
        opaque = cell[..., 3] > 0
        if not opaque.any():
            continue
        table = tables.get((sex, body))
        if table is None:
            skipped += 1
            continue
        matched += 1
        new[y:y + h, x:x + w] = _carry_to_cell(table, cell, built[y:y + h, x:x + w], radius)[0]
    return new, matched, skipped


def outfit_self_check(spec, stock, built, skin, radius=OUTFIT_RADIUS):
    """The method tried on the owner's own sheet: each worked outfit's rule is learned from the LEFT half of its
    cell only and carried to the RIGHT half, which it has not seen, and compared with what the owner did there.
    -> {"added": (pixels, right), "removed": (pixels, right), "owner": (added, removed) on those right halves}."""
    w = spec["cell"][0]
    tables = outfit_tables(spec, stock, built, skin, slice(0, w // 2))
    put = cut = put_right = cut_right = theirs_put = theirs_cut = 0
    for sex, body, y, x, h, cw in _body_cells(spec, stock.shape):
        table = tables.get((sex, body))
        if table is None:
            continue
        part = (slice(y, y + h), slice(x + cw // 2, x + cw))
        cell, was, now = stock[part], built[part], skin[part]
        opaque = cell[..., 3] > 0
        carried = _carry_to_cell(table, cell, was, radius)[0]
        add, remove = carried & ~was, was & ~carried
        put, put_right = put + int(add.sum()), put_right + int((add & now).sum())
        cut, cut_right = cut + int(remove.sum()), cut_right + int((remove & ~now).sum())
        theirs_put, theirs_cut = theirs_put + int((now & ~was & opaque).sum()), theirs_cut + int((was & ~now).sum())
    return {"added": (put, put_right), "removed": (cut, cut_right), "owner": (theirs_put, theirs_cut)}


def learn_outfits(games_and_images, root: Path, write=False, yes=False, radius=OUTFIT_RADIUS, say=print, backup=None,
                  preview: Path | None = None):
    """Carry the owner's edits of each body (outfit) to the same body's rows on the sheets still as built.

    Reads every body sheet the owner changed (a copy, through GIMP): tone 10 (Ebony) when it was changed -- the
    owner edits Ebony and "the others can hopefully follow suit" -- so the result is every tone's skin.  Without
    `write` nothing is written (the dry run): per sheet the pixels added and removed and the frames matched and
    skipped, and the self check on the owner's own sheet.  `preview`: a folder for a before-and-after picture
    of each game (tone 10).  With `write`: as `learn` -- only sheets still as built and not open in GIMP, their
    new skin kept as edits/<sheet>/mask.png, each file backed up, then made again.
    Returns {game: {sheet: (added, removed, frames matched, frames skipped)}}."""
    import datetime
    backup = backup or f"_before learned recolor {datetime.date.today().isoformat()}"
    games = []
    for game, images in games_and_images:
        folder = root / game
        base = Art(game, images, shipped=False)
        stems = {Path(name).stem: name for name in base.specs if (folder / f"{game}_{Path(name).stem}.xcf").is_file()}
        theirs = changed_by_the_owner(game, folder, list(stems))
        games.append({"game": game, "images": images, "folder": folder, "base": base, "stems": stems, "theirs": theirs,
                      "manifest": _manifest(folder)})
    with tempfile.TemporaryDirectory() as tmp:
        paths = [one["folder"] / f"{one['game']}_{stem}.xcf" for one in games for stem in one["theirs"]
                 if one["base"].specs[one["stems"][stem]]["kind"] == "bodies"]
        read = read_colour_layers(paths, Path(tmp)) if paths else {}
    done = {}
    for one in games:
        game, base, folder = one["game"], one["base"], one["folder"]
        tables = {}
        for stem in one["theirs"]:
            name = one["stems"][stem]
            spec = base.specs[name]
            path = folder / f"{game}_{stem}.xcf"
            if path not in read:
                say(f"{game}_{stem}: yours; not a body sheet, so nothing is carried from it yet")
                continue
            built, stock = base.mask(name), base.stock(name)
            skin, tones = owners_skin(read[path], one["manifest"].get(stem, {}), built)
            if skin is None:
                say(f"{game}_{stem}: yours, but no tone's skin differs from the build: nothing to carry")
                continue
            mine = outfit_tables(spec, stock, built, skin)
            for key, (rgb, as_skin, as_not) in mine.items():
                if key in tables:                               # the same outfit worked on in two sheets
                    old = tables[key]
                    rgb, as_skin, as_not = (np.concatenate([old[0], rgb]), np.concatenate([old[1], as_skin]),
                                            np.concatenate([old[2], as_not]))
                tables[key] = (rgb, as_skin, as_not)
            check = outfit_self_check(spec, stock, built, skin, radius)
            say(f"{game}_{stem}: read tone {', '.join(tones)}: {len(mine)} outfits worked on "
                f"({', '.join(f'{sex} body {body}' for sex, body in sorted(mine))}); you added "
                f"{int((skin & ~built).sum()):,} pixels to the skin and removed {int((built & ~skin).sum()):,}")
            say(f"  tried on this sheet itself (each outfit learned from the left half of its picture, carried to the "
                f"right half): it would add {check['added'][0]:,} pixels, {check['added'][1]:,} of them skin in your "
                f"edit, and remove {check['removed'][0]:,}, {check['removed'][1]:,} of them removed in your edit; on "
                f"those right halves you yourself added {check['owner'][0]:,} and removed {check['owner'][1]:,}")
        changes, masks = {}, {}
        for stem, name in one["stems"].items():
            spec = base.specs[name]
            if stem in one["theirs"] or spec["kind"] != "bodies" or not tables:
                continue
            built, stock = base.mask(name), base.stock(name)
            new, matched, skipped = apply_outfits(spec, stock, built, tables, radius)
            added, removed = int((new & ~built).sum()), int((built & ~new).sum())
            say(f"  {game}_{stem}: {added:,} pixels added to the skin, {removed:,} removed (of {int(built.sum()):,}); "
                f"{matched} frames matched to an outfit you worked on, {skipped} left as built")
            if added or removed:
                changes[stem], masks[stem] = (added, removed, matched, skipped), new
        if not tables:
            say(f"{game}: no body sheet of yours to carry from")
        done[game] = changes
        if preview is not None and changes:
            _outfit_preview(base, one["stems"], masks, Path(preview) / f"{game}_outfit_learning_before_after.png")
            say(f"{game}: before and after, tone 10: {Path(preview) / (game + '_outfit_learning_before_after.png')}")
        if not write or not changes:
            continue
        free, unknown = [], []
        for stem in sorted(changes):
            state, why = held_open(folder / f"{game}_{stem}.xcf")
            if state == "open":
                say(f"  {game}_{stem}: left alone: {why}")
            elif state == "unknown" and not yes:
                unknown.append(why)
            else:
                free.append(stem)
        if unknown:
            say(f"{game}: nothing was rebuilt. {unknown[0]}. Close GIMP and run this again, or, when none of these "
                "files is open in GIMP, run it again with --yes added.")
            continue
        was = json.loads((folder / LEARNED).read_text(encoding="utf-8")).get("sheets", []) if (folder / LEARNED).is_file() else []
        for stem in free:
            mark = np.zeros(masks[stem].shape + (4,), np.uint8)
            mark[masks[stem]] = 255
            (folder / "edits" / stem).mkdir(parents=True, exist_ok=True)
            Image.fromarray(mark).save(folder / "edits" / stem / LEARNED_MASK)
        (folder / LEARNED).write_text(json.dumps({
            "sheets": sorted(set(was) | set(free)), "by": "outfit", "radius": radius,
            "outfits": [f"{sex} body {body}" for sex, body in sorted(tables)]}, indent=1), encoding="utf-8")
        written, _kept, _unread = build_workbench(game, one["images"], folder, only=free, fresh_backup=backup)
        say(f"{game}: made {len(written)} files again with the learned skin; each as it was is in {backup}")
    return done


def _outfit_preview(base: Art, stems: dict, masks: dict, out: Path, most=6):
    """A picture of the rows that change most, as built (above) and with the learned skin (below), in tone 10,
    three times the size, the changed pixels marked beneath in red (added) and blue (removed)."""
    tone = core.TONES[-1]
    strips = []
    for stem in sorted(masks, key=lambda s: -int((masks[s] != base.mask(stems[s])).sum()))[:most]:
        name = stems[stem]
        stock, built, new = base.stock(name), base.mask(name), masks[stem]
        h = base.specs[name]["cell"][1]
        row = int(np.argmax([(new != built)[top:top + h].sum() for top in range(0, built.shape[0], h)]))
        part = slice(row * h, (row + 1) * h)
        before = core.recolour(stock, built, tone, h)[part]
        after = core.recolour(stock, new, tone, h)[part]
        marks = np.zeros_like(before)
        marks[(new & ~built)[part]] = (220, 30, 30, 255)
        marks[(built & ~new)[part]] = (30, 60, 220, 255)
        strips.append(np.concatenate([before, after, marks], axis=0))
    width = max(strip.shape[1] for strip in strips)
    canvas = np.concatenate([np.pad(strip, ((0, 4), (0, width - strip.shape[1]), (0, 0))) for strip in strips], axis=0)
    flat = np.full(canvas.shape[:2] + (3,), 236, np.uint8)
    alpha = canvas[..., 3:4].astype(np.float32) / 255
    picture = (canvas[..., :3] * alpha + flat * (1 - alpha)).astype(np.uint8)
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(picture).resize((picture.shape[1] * 3, picture.shape[0] * 3), Image.NEAREST).save(out)


# ---- orange and yellow things are not skin (the owner, 2026-11-28: "can you re-edit my gimp files to account for
# orange/yellow details???? please theres a ton of orange clothes")
ORANGE_HUES = (50.0, 110.0)         # OKLCh hue, degrees: orange through yellow


def orange_not_skin(stock, skin, cell_h):
    """The skin pixels of a body sheet that are orange or yellow cloth or detail in the game's own art: hue 50 to
    110 degrees and clearly more saturated than the sheet's own middle skin (the median chroma of all its skin
    plus the larger of 0.03 and half of it), so lit skin, which is only a little stronger, stays.  The whole
    sheet's middle, not a row's: every body of a sheet has the same skin, and a row can be mostly cloth (a tan
    robe built as skin once made the row's own middle the robe, and the arms and feet came out as "orange").
    Only ever a part of `skin`: nothing is added."""
    if not skin.any():
        return np.zeros(skin.shape, bool)
    lab = core.to_oklab(stock[..., :3])
    chroma = np.hypot(lab[..., 1], lab[..., 2])
    hue = np.degrees(np.arctan2(lab[..., 2], lab[..., 1])) % 360
    middle = float(np.median(chroma[skin]))
    limit = middle + max(0.03, 0.5 * middle)
    return skin & (hue >= ORANGE_HUES[0]) & (hue <= ORANGE_HUES[1]) & (chroma > limit)


def orange_dry_run(games_and_images, root: Path, preview: Path | None = None, say=print):
    """What taking orange and yellow things out of the skin would do, sheet by sheet: nothing is written but the
    preview pictures.  A sheet still as built: its skin as built (learned skin included).  A sheet the owner
    edited (read from a copy, through GIMP): tone 10's paint, and only pixels that came from the build or the
    learning -- never one the owner painted themselves.  Returns {game: {sheet: pixels removed}}."""
    done = {}
    games = []
    for game, images in games_and_images:
        folder = root / game
        edits = folder / "edits"
        art = Art(game, images, edits if edits.is_dir() else None, shipped=False)
        # Body sheets only: on the head sheets this rule took whole faces (the first dry run's pictures): a head's
        # complexion is its own, and nothing here tells a warm face from blond hair.
        stems = {Path(name).stem: name for name in art.specs
                 if art.specs[name]["kind"] == "bodies" and (folder / f"{game}_{Path(name).stem}.xcf").is_file()}
        games.append((game, folder, art, stems, changed_by_the_owner(game, folder, list(stems))))
    with tempfile.TemporaryDirectory() as tmp:
        paths = [folder / f"{game}_{stem}.xcf" for game, folder, _art, _stems, theirs in games for stem in theirs]
        read = read_colour_layers(paths, Path(tmp)) if paths else {}
    tone = core.TONES[-1]
    for game, folder, art, stems, theirs in games:
        done[game], strips, total, skin_total = {}, [], 0, 0
        for stem, name in stems.items():
            stock, built = art.stock(name), art.mask(name)
            h = art.specs[name]["cell"][1]
            now, own = built, np.zeros(built.shape, bool)
            if stem in theirs:
                layers = read.get(folder / f"{game}_{stem}.xcf", {})
                ebony = layers.get(f"skin_{len(core.TONES):02d}.png")
                if ebony is not None and ebony.shape[:2] == built.shape:
                    now = painted_from_layer(ebony) & (stock[..., 3] > 0)
                    own = now & ~built                          # painted by the owner: never undone
            out = orange_not_skin(stock, now, h) & ~own
            count = int(out.sum())
            total, skin_total = total + count, skin_total + int(now.sum())
            done[game][stem] = count
            if count:
                say(f"  {game}_{stem}{' (yours)' if stem in theirs else ''}: {count:,} orange or yellow pixels out of "
                    f"the skin (of {int(now.sum()):,})" + (f"; {int((orange_not_skin(stock, now, h) & own).sum()):,} "
                    "more are your own paint and stay" if stem in theirs else ""))
                rows = np.array([out[top:top + h].sum() for top in range(0, out.shape[0], h)])
                for row in np.argsort(-rows)[:2]:
                    if rows[row]:
                        part = slice(int(row) * h, (int(row) + 1) * h)
                        marks = core.recolour(stock, now, tone, h)[part].copy()
                        marks[out[part]] = (255, 0, 200, 255)
                        strips.append((int(rows[row]), np.concatenate(
                            [stock[part], core.recolour(stock, now, tone, h)[part], marks,
                             core.recolour(stock, now & ~out, tone, h)[part]], axis=0)))
        say(f"{game}: {total:,} pixels out of the skin on {sum(1 for c in done[game].values() if c)} of "
            f"{len(stems)} sheets (of {skin_total:,} skin pixels)")
        if preview is not None and strips:
            strips = [strip for _count, strip in sorted(strips, key=lambda item: -item[0])[:10]]
            width = min(max(strip.shape[1] for strip in strips), 960)
            canvas = np.concatenate([np.pad(strip[:, :width], ((0, 6), (0, width - min(width, strip.shape[1])), (0, 0)))
                                     for strip in strips], axis=0)
            flat = np.full(canvas.shape[:2] + (3,), 236, np.uint8)
            alpha = canvas[..., 3:4].astype(np.float32) / 255
            picture = (canvas[..., :3] * alpha + flat * (1 - alpha)).astype(np.uint8)
            out_path = Path(preview) / f"{game}_orange_yellow_out_of_skin.png"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            Image.fromarray(picture).resize((picture.shape[1] * 2, picture.shape[0] * 2), Image.NEAREST).save(out_path)
            say(f"{game}: picture (each block: the game's art; Ebony now; the pixels to take out in pink; Ebony "
                f"after): {out_path}")
    return done


_GIMP_CUT = r'''
import json, os, re, shutil
import gi
gi.require_version("Gimp", "3.0")
gi.require_version("Gegl", "0.4")
from gi.repository import Gimp, Gio, Gegl
FORMAT = "R'G'B'A u8"
job = json.load(open(os.environ["VVFP_SKIN_JOB"], encoding="utf-8"))


def wanted_layers(image):
    found = []
    for layer in image.get_layers():
        name = layer.get_name()
        if name.startswith("Skin mask"):
            found.append(layer)
        if re.match(r"Tone (\d+)", name) and layer.is_group():
            found += [child for child in layer.get_children() if "paint here" in child.get_name()]
    return found


def pixels(layer, width, height):
    at = layer.get_offsets()
    return layer.get_buffer().get(Gegl.Rectangle.new(-at[-2], -at[-1], width, height), 1.0, FORMAT, Gegl.AbyssPolicy.NONE)


def cut(item, result):
    # The pixels to take out: a picture the sheet's size, opaque where a pixel goes.
    mark = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(item["cut"]))
    width, height = mark.get_width(), mark.get_height()
    out = bytes(pixels(mark.get_layers()[0], width, height)[3::4])
    mark.delete()
    keep = int.from_bytes(bytes(0 if b else 255 for b in out), "little")
    gone = int.from_bytes(bytes(255 if b else 0 for b in out), "little")
    image = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(item["xcf"]))
    if (image.get_width(), image.get_height()) != (width, height):
        result["did"] = "another size"
        image.delete()
        return
    layers = wanted_layers(image)
    if len(layers) != item["layers"]:
        result["did"] = "not ours"
        image.delete()
        return
    os.makedirs(item["backup"], exist_ok=True)
    stem, k = os.path.splitext(os.path.basename(item["xcf"]))[0], 1
    kept = os.path.join(item["backup"], stem + ".xcf")
    while os.path.exists(kept):
        k += 1
        kept = os.path.join(item["backup"], "%s (%d).xcf" % (stem, k))
    shutil.copy2(item["xcf"], kept)
    result["backup"] = kept
    for layer in layers:
        at = layer.get_offsets()
        if at[-2] or at[-1] or layer.get_width() != width or layer.get_height() != height:
            layer.resize_to_image_size()
        data = bytearray(pixels(layer, width, height))
        alpha = int.from_bytes(bytes(data[3::4]), "little") & keep
        data[3::4] = alpha.to_bytes(width * height, "little")
        buffer = layer.get_buffer()
        buffer.set(Gegl.Rectangle.new(0, 0, width, height), FORMAT, bytes(data))
        buffer.flush()
        layer.update(0, 0, width, height)
    Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, image, Gio.File.new_for_path(item["xcf"]), None)
    image.delete()
    # Read the saved file again: no layer has paint left on a pixel that was to go.
    image = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(item["xcf"]))
    left = 0
    for layer in wanted_layers(image):
        if int.from_bytes(bytes(pixels(layer, width, height)[3::4]), "little") & gone:
            left += 1
    image.delete()
    result["left"] = left
    result["did"] = "cut"


for item in job["files"]:
    result = {"xcf": item["xcf"], "did": "nothing"}
    try:
        cut(item, result)
    except Exception as problem:
        result["did"], result["why"] = "failed", repr(problem)
    json.dump(result, open(item["result"], "w", encoding="utf-8"))
    print("VVFP cut", item["xcf"], result["did"])
'''


def orange_write(games_and_images, root: Path, yes=False, say=print, backup=None):
    """Take the orange and yellow things out of the skin IN the workbench files (body sheets): every tone's colour
    layer and the "Skin mask" lose those pixels; nothing is added and nothing else in a file changes.  Each file
    is first copied into <game>/<backup>.  A sheet still as built stays "as built" (its record and pin follow,
    and its new skin is kept as edits/<sheet>/learned_mask.png so the mod and a rebuild have it); a sheet of
    the owner's stays theirs, and a pixel they painted in Ebony themselves is never taken.  A file open in
    GIMP is left; when that cannot be told nothing is written without `yes`.  One start of GIMP a game."""
    import datetime
    backup = backup or f"_before orange fix {datetime.date.today().isoformat()}"
    for game, images in games_and_images:
        folder = root / game
        edits = folder / "edits"
        art = Art(game, images, edits if edits.is_dir() else None, shipped=False)
        stems = {Path(name).stem: name for name in art.specs
                 if art.specs[name]["kind"] == "bodies" and (folder / f"{game}_{Path(name).stem}.xcf").is_file()}
        theirs = changed_by_the_owner(game, folder, list(stems))
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            read = read_colour_layers([folder / f"{game}_{stem}.xcf" for stem in theirs], tmp / "read") if theirs else {}
            files, plans = [], {}
            for stem, name in stems.items():
                stock, built = art.stock(name), art.mask(name)
                h = art.specs[name]["cell"][1]
                now, own = built, np.zeros(built.shape, bool)
                if stem in theirs:
                    ebony = read.get(folder / f"{game}_{stem}.xcf", {}).get(f"skin_{len(core.TONES):02d}.png")
                    if ebony is None or ebony.shape[:2] != built.shape:
                        say(f"  {game}_{stem} (yours): left alone: its Ebony layer could not be read")
                        continue
                    now = painted_from_layer(ebony) & (stock[..., 3] > 0)
                    own = now & ~built
                out = orange_not_skin(stock, now, h) & ~own
                if not out.any():
                    continue
                path = folder / f"{game}_{stem}.xcf"
                state, why = held_open(path)
                if state == "open" or (state == "unknown" and not yes):
                    say(f"  {game}_{stem}: left alone: {why}")
                    continue
                mark = np.zeros(out.shape + (4,), np.uint8)
                mark[out] = 255
                Image.fromarray(mark).save(tmp / f"{stem}_cut.png")
                files.append({"xcf": str(path), "cut": str(tmp / f"{stem}_cut.png"), "backup": str(folder / backup),
                              "layers": len(core.TONES) + 1, "result": str(tmp / f"{stem}.json")})
                plans[stem] = (out, built & ~out)
            if not files:
                say(f"{game}: nothing to take out")
                continue
            run_gimp(_GIMP_CUT, {"files": files})
            manifest = _manifest(folder)
            learned = json.loads((folder / LEARNED).read_text(encoding="utf-8")) if (folder / LEARNED).is_file() else {}
            good = 0
            for item in files:
                stem = Path(item["xcf"]).stem[len(game) + 1:]
                result = json.loads(Path(item["result"]).read_text(encoding="utf-8"))
                out, new = plans[stem]
                if result["did"] != "cut" or result.get("left"):
                    say(f"  {game}_{stem}: NOT DONE ({result.get('why', result['did'])}"
                        f"{', paint left on ' + str(result['left']) + ' layers' if result.get('left') else ''})"
                        + (f"; the file as it was is in {result['backup']}" if result.get("backup") else ""))
                    continue
                good += 1
                say(f"  {game}_{stem}{' (yours)' if stem in theirs else ''}: {int(out.sum()):,} orange or yellow pixels "
                    "taken out of the skin in all ten tones (checked in the saved file)")
                if stem in theirs:
                    continue
                white = np.zeros(new.shape + (4,), np.uint8)
                white[new] = 255
                (edits / stem).mkdir(parents=True, exist_ok=True)
                Image.fromarray(white).save(edits / stem / LEARNED_MASK)
                record = manifest.setdefault(stem, {})
                record["mask.png"] = _sha(_clean(white))
                for number in range(1, len(core.TONES) + 1):
                    record[f"skin_{number:02d}.png"] = _sha(new)
                manifest.setdefault(XCF_PINS, {})[stem] = _file_sha(Path(item["xcf"]))
                learned["sheets"] = sorted(set(learned.get("sheets", [])) | {stem})
            (folder / ".generated.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
            (folder / LEARNED).write_text(json.dumps(learned, indent=1), encoding="utf-8")
            say(f"{game}: {good} of {len(files)} files written; each as it was is in {backup}")


def publish_edits(art: Art, edits: Path, out: Path):
    """The owner's kept edits (<workbench>/<game>/edits) as shippable files under `out`/<game>/<sheet>/:
    skin_NN.png for each tone whose colour layer the owner painted, and mask.png when they changed the
    "Skin mask" or the sheet has a learned skin (learned_mask.png) -- each white where skin and nothing else,
    on pixels of the sprite only.  WHERE the skin is
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
        if (folder / "mask.png").is_file() or (folder / LEARNED_MASK).is_file():
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


# ---- quick-edit layout (the owner, 2026-11-28, through the coordinator) -------------------------------
#
# Every .xcf opens ready to paint Ebony: Tone 10's group shown and open, every other tone's group hidden and
# closed, "Ebony colour (paint here)" the active layer, "Hair and non-skin (vanilla)" and "Skin mask"
# hidden, the game's art locked; each tone's shading layer named after its tone ("Ebony shading (locked)",
# not GIMP's "Shading (locked) #9") with its pixels and position locked.  Nothing else in a file changes:
# each is backed up first, and after it is saved GIMP reads it again and compares every layer with the
# backup -- pixels, masks, sizes, places, modes, opacities -- allowing only visibility, locks, names of the
# shading layers, folders open or closed, and the active layer to differ.  A file that fails is put back.

QUICK_CHANGEABLE = ("visible", "lock_content", "lock_position", "expanded", "name")

_GIMP_QUICK_LAYOUT = r'''
import hashlib, json, os, re
import gi
gi.require_version("Gimp", "3.0")
gi.require_version("Gegl", "0.4")
from gi.repository import Gimp, Gio, Gegl
job = json.load(open(os.environ["VVFP_SKIN_JOB"], encoding="utf-8"))
SHOWN = job["shown"]
NAMES = {int(k): v for k, v in job["tones"].items()}


def pixels(drawable):
    buffer = drawable.get_buffer()
    rect = buffer.get_extent()
    # Float RGBA holds every 8-bit value exactly, whatever the layer's own format.
    data = buffer.get(rect, 1.0, "RGBA float", Gegl.AbyssPolicy.NONE)
    return "%d,%d,%d,%d:%s" % (rect.x, rect.y, rect.width, rect.height, hashlib.sha1(bytes(data)).hexdigest())


def describe(image):
    out = []
    def walk(layer, path):
        mask = layer.get_mask()
        entry = {
            "path": path, "name": layer.get_name(), "group": bool(layer.is_group()),
            "visible": bool(layer.get_visible()), "lock_content": bool(layer.get_lock_content()),
            "lock_position": bool(layer.get_lock_position()), "lock_alpha": bool(layer.get_lock_alpha()),
            "lock_visibility": bool(layer.get_lock_visibility()), "expanded": bool(layer.get_expanded()),
            "opacity": round(float(layer.get_opacity()), 4), "mode": int(layer.get_mode()),
            "composite_mode": int(layer.get_composite_mode()), "composite_space": int(layer.get_composite_space()),
            "blend_space": int(layer.get_blend_space()), "offsets": list(layer.get_offsets()[-2:]),
            "size": [layer.get_width(), layer.get_height()], "color_tag": int(layer.get_color_tag()),
            "mask": pixels(mask) if mask is not None else None,
            "pixels": None if layer.is_group() else pixels(layer),
        }
        out.append(entry)
        if layer.is_group():
            for k, child in enumerate(layer.get_children()):
                walk(child, path + [k])
    for k, layer in enumerate(image.get_layers()):
        walk(layer, [k])
    return {"width": image.get_width(), "height": image.get_height(), "precision": int(image.get_precision()),
            "base": int(image.get_base_type()), "layers": out,
            "selected": [layer.get_name() for layer in image.get_selected_layers()]}


def lay_out(image, result):
    paint, did = None, []
    groups = [layer for layer in image.get_layers() if layer.is_group() and re.match(r"Tone (\d+)", layer.get_name())]
    if len(groups) != len(NAMES):
        result["did"] = "not ours (%d tone folders)" % len(groups)
        return False
    for layer in image.get_layers():
        name = layer.get_name()
        tone = re.match(r"Tone (\d+)", name)
        if tone and layer.is_group():
            n = int(tone.group(1))
            if n not in NAMES:
                result["did"] = "not ours (%s)" % name
                return False
            if layer.get_visible() != (n == SHOWN):
                layer.set_visible(n == SHOWN)
                did.append("%s %s" % (name, "shown" if n == SHOWN else "hidden"))
            layer.set_expanded(n == SHOWN)
            for child in layer.get_children():
                cname = child.get_name()
                if "paint here" in cname:
                    if n == SHOWN:
                        paint = child
                        if not child.get_visible():
                            child.set_visible(True)
                            did.append("%s shown" % cname)
                    continue
                if cname.startswith("Shading (locked)") or cname.endswith("shading (locked)"):
                    want = "%s shading (locked)" % NAMES[n]
                    if cname != want:
                        child.set_name(want)
                        did.append("%s -> %s" % (cname, want))
                    child.set_lock_content(True)
                    child.set_lock_position(True)
                    if n == SHOWN and not child.get_visible():
                        child.set_visible(True)
                        did.append("%s shown" % want)
        elif name == "Hair and non-skin (vanilla)" or name.startswith("Skin mask"):
            if layer.get_visible():
                layer.set_visible(False)
                did.append("%s hidden" % name)
        elif name.startswith("Game's own art"):
            layer.set_lock_content(True)
            layer.set_lock_position(True)
    if paint is None:
        result["did"] = "not ours (no colour layer in Tone %d)" % SHOWN
        return False
    image.set_selected_layers([paint])
    result["changes"] = did
    result["active"] = paint.get_name()
    return True


for item in job["files"]:
    result = {"xcf": item["xcf"], "did": "nothing"}
    try:
        image = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(item["xcf"]))
        result["before"] = describe(image)
        if lay_out(image, result):
            Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, image, Gio.File.new_for_path(item["xcf"]), None)
            result["did"] = "saved"
        image.delete()
        if result["did"] == "saved":
            # The file as saved, and the backup, each read again from disk.
            for key, path in (("after", item["xcf"]), ("backup", item["backup"])):
                image = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(path))
                result[key] = describe(image)
                image.delete()
    except Exception as problem:
        result["did"], result["why"] = "failed", repr(problem)
    json.dump(result, open(item["result"], "w", encoding="utf-8"))
    print("VVFP quick", item["xcf"], result["did"])
'''


def quick_layout_check(backup: dict, after: dict, shown=SHOWN_TONE) -> list[str]:
    """What is wrong with a file laid out for quick editing, compared with its backup (both as GIMP described
    them): [] when every layer's pixels, mask, size, place, mode and opacity are the backup's, only the
    allowed things differ, and the file opens ready to paint `shown`."""
    wrong = []
    for key in ("width", "height", "precision", "base"):
        if backup[key] != after[key]:
            wrong.append(f"the picture's {key} changed")
    was, now = backup["layers"], after["layers"]
    if [layer["path"] for layer in was] != [layer["path"] for layer in now]:
        return wrong + ["the layers are not the same layers in the same order"]
    for old, new in zip(was, now):
        for key in old:
            if key in QUICK_CHANGEABLE or old[key] == new[key]:
                continue
            wrong.append(f"{old['name']}: its {key} changed")
        if old["name"] != new["name"] and not (
                (old["name"].startswith(LAYER_SHADING) or old["name"].endswith(SHADING_WORDS))
                and new["name"].endswith(SHADING_WORDS)):
            wrong.append(f"{old['name']}: renamed to {new['name']}")
    tops = [layer for layer in now if len(layer["path"]) == 1]
    for layer in tops:
        name = layer["name"]
        tone = name.startswith("Tone ") and layer["group"] and int(name[5:7])
        if tone:
            if layer["visible"] != (tone == shown) or layer["expanded"] != (tone == shown):
                wrong.append(f"{name}: shown/open should be {tone == shown}")
        elif name in (LAYER_TOP,) or name.startswith(LAYER_MASK):
            if layer["visible"]:
                wrong.append(f"{name}: should be hidden")
        elif name.startswith(LAYER_GAME) and not (layer["lock_content"] and layer["lock_position"]):
            wrong.append(f"{name}: should be locked")
    for layer in now:
        if len(layer["path"]) == 2 and layer["name"].endswith(SHADING_WORDS):
            if not (layer["lock_content"] and layer["lock_position"]):
                wrong.append(f"{layer['name']}: should be locked")
    names = [layer["name"] for layer in now]
    if len(set(names)) != len(names):
        wrong.append("two layers share a name")
    if after["selected"] != [paint_layer_name(shown)]:
        wrong.append(f"the active layer is {after['selected']}")
    return wrong


def quick_layout(root: Path, games, yes=False, backup=QUICK_LAYOUT_BACKUP, normal_priority=True, say=print) -> dict:
    """Lay out every .xcf of `games` under `root` for quick editing (above).  Each file is first copied into
    <root>/<game>/<backup> (a copy already there is never overwritten); a file that fails the check is put
    back from it.  A file still exactly as this tool wrote it (pinned) is pinned again as laid out, so a
    rebuild still knows it is not the owner's.  Returns {file name: [what is wrong] or []}."""
    files, pins_before, done = [], {}, {}
    for game in games:
        folder = root / game
        for path in sorted(folder.glob(f"{game}_*.xcf")):
            state, why = held_open(path)
            if state == "open" or (state == "unknown" and not yes):
                raise SystemExit(f"Nothing was changed: {path.name}: {why}. Save and close it in GIMP; run again "
                                 "with --yes when no file is open there.")
            kept = folder / backup / path.name
            kept.parent.mkdir(parents=True, exist_ok=True)
            if kept.exists() and _file_sha(kept) != _file_sha(path):
                k = 2
                while kept.with_name(f"{path.stem} ({k}).xcf").exists():
                    k += 1
                kept = kept.with_name(f"{path.stem} ({k}).xcf")
            if not kept.exists():
                shutil.copy2(path, kept)
            if _file_sha(kept) != _file_sha(path):
                raise SystemExit(f"the backup of {path.name} is not the file: nothing was changed")
            pins_before[str(path)] = _file_sha(path)
            files.append({"xcf": str(path), "backup": str(kept), "game": game})
    tones = {str(n): core.TONES[n - 1][4] for n in range(1, len(core.TONES) + 1)}
    with tempfile.TemporaryDirectory() as tmp:
        for k, item in enumerate(files):
            item["result"] = str(Path(tmp) / f"{k}.json")
        if files:
            run_gimp(_GIMP_QUICK_LAYOUT, {"files": files, "shown": SHOWN_TONE, "tones": tones}, idle=not normal_priority)
        results = [json.loads(Path(item["result"]).read_text(encoding="utf-8")) for item in files]
    for item, result in zip(files, results):
        path = Path(item["xcf"])
        if result["did"] != "saved":
            wrong = [f"not changed: {result['did']} {result.get('why', '')}".strip()]
        else:
            wrong = quick_layout_check(result["backup"], result["after"])
            if result["before"] != result["backup"]:
                wrong.append("the file as opened is not its backup")
        if wrong and result["did"] == "saved":
            shutil.copy2(item["backup"], path)          # put back exactly as it was
            wrong.append("PUT BACK from the backup")
        done[path.name] = (wrong, result)
    for game in games:
        folder = root / game
        manifest = _manifest(folder)
        pins = manifest.get(XCF_PINS, {})
        changed = False
        for stem, pin in list(pins.items()):
            path = folder / f"{game}_{stem}.xcf"
            if pins_before.get(str(path)) == pin and not done[path.name][0]:
                pins[stem] = _file_sha(path)
                changed = True
        if changed:
            (folder / ".generated.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return done


README = """VVFP Skin Tones Workbench
=========================

One GIMP file per head and body sheet of each game, for marking by hand where each skin tone goes.
These files hold the game's own art. Keep them here; they must never be shared or shipped.

EVERY FILE OPENS READY TO PAINT EBONY: Tone 10 (Ebony) is the one tone shown, its folder is
open, its "Ebony colour (paint here)" layer is the highlighted one, and "Hair and non-skin
(vanilla)" is hidden.

THE LAYERS (top to bottom)
  Hair and non-skin (vanilla)  The original's hair, eyes, mouths and clothes. Locked. Hidden
                               (click its eye to see the hair and clothes again).
  Tone 10 - S10 Ebony ...      One folder (layer group) per skin tone, dark to light, down to
  Tone 01 - S1 Porcelain       Tone 01 - S1 Porcelain. Ebony is shown; click a folder's eye to
                               see another. Inside each folder:
      <tone> shading (locked)      The game art's own light and dark, in the tone's colours. It
                                   shows only where the colour layer under it has paint.
                                   Never paint it. (Older files: "Shading (locked) #1" etc.)
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
  - "Hair and non-skin (vanilla)" is hidden while you work: it lies on top and would cover skin
    you add over hair or clothes.
  - If your painting does nothing, check you didn't add a layer mask: right-click the layer >
    Delete Layer Mask.
  - Do not paint the shading layer. Do not rename, merge or delete layers or folders, and do not
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
                                    "workbench-all", "spread", "learn", "orange", "quick-layout"])
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
    ap.add_argument("--all-games", action="store_true", help="learn: every game (needs --images-root)")
    ap.add_argument("--across-games", action="store_true", help="learn: one rule from all the games' edits together")
    ap.add_argument("--by-outfit", action="store_true",
                    help="learn: carry what you did on each body (outfit) to the same body's rows on the other "
                         "sheets, instead of one colour rule for the whole game")
    ap.add_argument("--preview", type=Path, help="learn --by-outfit: a folder for a before-and-after picture")
    ap.add_argument("--write", action="store_true", help="learn: really rebuild the unedited sheets (left out: a dry "
                                                         "run that only lists what would change)")
    ap.add_argument("--tolerance", type=int, default=0, help="learn: count colours in buckets this many levels wide "
                                                             "(each of red, green, blue); 0 = exact colours only. "
                                                             "With --by-outfit: how close a colour must be to one "
                                                             "of the outfit's (default 6)")
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
    if args.what == "quick-layout":
        games = sorted(TITLES) if args.all_games else [args.game]
        if games == [None]:
            raise SystemExit("say which game with --game, or --all-games")
        games = [g for g in games if (args.workbench / g).is_dir()]
        done = quick_layout(args.workbench, games, args.yes)
        for name, (wrong, result) in sorted(done.items()):
            print(f"{name}: " + ("; ".join(wrong) if wrong else
                                 f"laid out and checked ({len(result.get('changes', []))} changes)"))
        bad = sum(1 for wrong, _ in done.values() if wrong)
        print(f"{len(done) - bad} of {len(done)} files laid out; every layer's pixels checked against the backup")
        return 1 if bad else 0
    if args.what == "orange":
        games = sorted(TITLES) if args.all_games else [args.game]
        if games == [None] or args.images_root is None:
            raise SystemExit("say which game with --game or --all-games, and give --images-root")
        pairs = [(g, args.images_root / FOLDERS[g] / "Images") for g in games if (args.workbench / g).is_dir()]
        if args.write:
            orange_write(pairs, args.workbench, args.yes)
            return 0
        print("DRY RUN: nothing is written but the pictures.")
        orange_dry_run(pairs, args.workbench, args.preview)
        return 0
    if args.what == "learn":
        games = sorted(TITLES) if args.all_games or args.across_games else [args.game]
        if games == [None]:
            raise SystemExit("say which game with --game, or --all-games")
        if args.images_root is None and (len(games) > 1 or args.images is None):
            raise SystemExit("--images-root (the folder holding every game's own folder) is needed")
        pairs = [(g, args.images if args.images and len(games) == 1 else args.images_root / FOLDERS[g] / "Images") for g in games]
        pairs = [(g, images) for g, images in pairs if (args.workbench / g).is_dir()]
        if not args.write:
            print("DRY RUN: nothing is written. This is what the unedited sheets would get.")
        if args.by_outfit:
            done = learn_outfits(pairs, args.workbench, args.write, args.yes, args.tolerance or OUTFIT_RADIUS,
                                 preview=args.preview)
        else:
            done = learn(pairs, args.workbench, args.across_games, args.write, args.yes, tolerance=args.tolerance)
        if args.across_games and args.game:
            done = {args.game: done.get(args.game, {})}
        if not args.write and any(done.values()):
            print("To do it, run the same command again with --write added.")
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
