"""Skin tones for all five games: the sheets, the previews, and the owner's GIMP workbench.

    python scripts/skin_tone_sheets.py preview   --game vv3 --images "<game>\\Images" --out previews
    python scripts/skin_tone_sheets.py sheets    --game vv3 --images "<game>\\Images" --out "<folder>"
    python scripts/skin_tone_sheets.py workbench --game vv3 --images "<game>\\Images"
    python scripts/skin_tone_sheets.py workbench-all --images-root "<the folder of the five games>"
    python scripts/skin_tone_sheets.py import    --game vv3
    python scripts/skin_tone_sheets.py publish   --game vv3 --images "<game>\\Images"

The method is scripts/skin_tone_preview.py's (the skin mask, then REPLACE in OKLCh, everything outside
the mask byte-identical).  This file knows each game's sheets, makes the same preview set per game, and
builds and reads back the owner's workbench:

THE WORKBENCH (never in the repository: it holds game art).  One .xcf per head and body sheet, written
by GIMP itself, with layers bottom to top: "Game's own art" (locked), "Skin mask" (white = skin, hidden),
"Tone 01 - S1 Porcelain" ... one per tone (skin pixels only; all hidden but one), "Hair and non-skin (vanilla)"
(locked).  `import` asks GIMP to export every layer again and keeps what the owner changed in
<workbench>\\<game>\\edits\\<sheet>\\: mask.png and tone_NN.png.  Whatever is there wins over the generated
art, here and wherever the sheets are made (Art(..., edits=...)).

THE OWNER'S ART MAY SHIP (the owner, 2026-11-26: "yes my art can ship").  `publish` copies what `import`
kept into assets/skin_tones/owner_edits/<game>/<sheet>/, as the SKIN PIXELS ONLY: mask.png (white where
skin, nothing else) and each painted tone_NN.png with every pixel outside that mask made transparent --
never the game's own layer, hair, eyes or clothes.  manifest.json there pins each file by SHA-256
(tests/test_skin_tone_owner_edits.py).  Where sheets are made, the workbench's edits come first, then
these, then the generated art.

Everything else this writes is made from the player's own game files and is never committed or shipped.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
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
    owner's folder (<workbench>/<game>/edits): a mask.png or a tone_NN.png there wins; then the owner's
    shipped edits (assets/skin_tones/owner_edits/<game>), unless `shipped` is False."""

    def __init__(self, game, images: Path, edits: Path | None = None, shipped: bool = True):
        self.game, self.images = game, Path(images)
        self.edit_folders = [f for f in (edits, SHIPPED_EDITS / game if shipped else None) if f is not None]
        self.specs = {s["name"]: s for s in sheets_of(game) if find_file(self.images, s["name"])}
        self._raw, self._mask, self._made, self.mask_source = {}, {}, {}, {}

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
            layer = np.array(Image.open(edited).convert("RGBA"))
            m, source = (layer[..., 3] > 127) & (layer[..., :3].max(-1) > 127), "the owner's edited mask"
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

    def sheet(self, name, tone=None):
        """The sheet for `tone` (a core.TONES row), or the game's own for None."""
        if tone is None:
            return self.stock(name)
        number = core.TONES.index(tone) + 1
        key = (name, number)
        if key not in self._made:
            stock = self.stock(name)
            edited = self._edit(name, f"tone_{number:02d}.png")
            if edited is not None:
                layer = np.array(Image.open(edited).convert("RGBA"))
                if layer.shape != stock.shape:
                    raise SystemExit(f"{edited}: not the sheet's size")
                made = stock.copy()
                painted = layer[..., 3] > 0
                made[painted, :3] = layer[painted, :3]
                made[..., 3] = np.maximum(stock[..., 3], np.where(painted, layer[..., 3], 0))
            else:
                mask = self.mask(name)
                made = core.recolour(stock, mask, tone, self.specs[name]["cell"][1])
                if not core.check_untouched(stock, made, mask):
                    raise SystemExit(f"{name}: a pixel outside the skin mask changed")
            self._made[key] = made
        return self._made[key]

    def tone_layer(self, name, tone):
        """A tone's sheet with only its skin pixels on it (the workbench layer)."""
        made = self.sheet(name, tone).copy()
        made[~self.mask(name)] = 0
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
SHOWN_TONE = 6          # the tone layer left visible in a new .xcf


def tone_layer_name(number):
    return f"Tone {number:02d} - S{number} {core.TONES[number - 1][4]}"


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
    for part, layer in zip(parts, item["layers"]):
        part.set_name(layer["name"])
        part.set_visible(bool(layer["visible"]))
        if layer["lock"]:
            part.set_lock_content(True)
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
        leaf = "tone_%02d.png" % int(tone.group(1)) if tone else ("mask.png" if name.startswith("Skin mask") else None)
        if leaf is not None:
            wanted.append((leaf, layer))
    if wanted:
        # Every wanted layer goes into one picture, one under the other (one file written a sheet): a copy
        # of each, cut to the sheet's own area and moved to its band.  Nothing is resampled.
        tall = Gimp.Image.new(width, height * len(wanted), Gimp.ImageBaseType.RGB)
        for k, (leaf, layer) in enumerate(wanted):
            at = layer.get_offsets()
            copy = Gimp.Layer.new_from_drawable(layer, tall)
            tall.insert_layer(copy, None, 0)
            copy.set_visible(True)
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
        done = subprocess.run(command, env=env, capture_output=True, text=True, timeout=3600)
        text = (done.stdout or "") + (done.stderr or "")
        if text.count("VVFP ") < len(job["files"]):
            raise SystemExit("GIMP did not finish every file:\n" + text[-3000:])
        return text


def _sha(array):
    return hashlib.sha1(np.ascontiguousarray(array).tobytes()).hexdigest()


def _layer_pixels(path):
    return np.array(Image.open(path).convert("RGBA"))


def _clean(layer):
    """A layer as it is compared: fully transparent pixels carry no colour."""
    layer = layer.copy()
    layer[layer[..., 3] == 0] = 0
    return layer


XCF_PINS = "_xcf"                       # in .generated.json: {sheet: the SHA-256 of the .xcf as this tool wrote it}


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest(folder: Path) -> dict:
    path = folder / ".generated.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def changed_by_the_owner(game, folder: Path, stems) -> list[str]:
    """The sheets whose .xcf is there and is NOT the file this tool wrote (its SHA-256 differs from the one
    recorded, or none was recorded): the owner's work, never to be replaced."""
    pins = _manifest(folder).get(XCF_PINS, {})
    return [stem for stem in stems
            if (folder / f"{game}_{stem}.xcf").is_file() and _file_sha(folder / f"{game}_{stem}.xcf") != pins.get(stem)]


def _prepare_workbench(game, images: Path, folder: Path, only, tmp: Path) -> dict:
    """Everything a build of one game's workbench needs before GIMP runs: the owner's changed files read
    (their edits kept), and one picture a sheet to build -- its layers one under the other."""
    folder.mkdir(parents=True, exist_ok=True)
    stems = [Path(s["name"]).stem for s in sheets_of(game) if find_file(Path(images), s["name"])]
    if only:
        stems = [stem for stem in stems if stem in only]
    theirs = changed_by_the_owner(game, folder, stems)
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
    files, made = [], []
    for name in art.specs:
        stem = Path(name).stem
        if stem not in stems or stem in theirs:
            continue
        stock, mask = art.stock(name), art.mask(name)
        white = np.zeros_like(stock)
        white[mask] = 255
        top = stock.copy()
        top[mask] = 0
        bands = [(stock, LAYER_GAME, True, True), (white, LAYER_MASK, False, False)]
        record = {"mask.png": _sha(_clean(white))}
        for number, tone in enumerate(core.TONES, 1):
            layer = art.tone_layer(name, tone)
            bands.append((layer, tone_layer_name(number), number == SHOWN_TONE, False))
            record[f"tone_{number:02d}.png"] = _sha(_clean(layer))
        bands.append((top, LAYER_TOP, True, True))
        tall = tmp / f"{game}_{stem}.png"
        Image.fromarray(np.concatenate([band[0] for band in bands], axis=0)).save(tall, compress_level=1)
        manifest[stem] = record
        made.append(stem)
        files.append({"xcf": str(folder / f"{game}_{stem}.xcf"), "png": str(tall), "width": int(stock.shape[1]),
                      "height": int(stock.shape[0]),
                      "layers": [{"name": label, "visible": visible, "lock": lock} for _, label, visible, lock in bands]})
    return {"game": game, "folder": folder, "files": files, "made": made, "manifest": manifest,
            "kept": [stem for stem in theirs if stem not in unread], "unread": unread}


def _finish_workbench(prepared: dict):
    """After GIMP: pin each .xcf written, and write the workbench's record."""
    game, folder, manifest = prepared["game"], prepared["folder"], prepared["manifest"]
    for stem in prepared["made"]:
        manifest[XCF_PINS][stem] = _file_sha(folder / f"{game}_{stem}.xcf")
    (folder / ".generated.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return [f["xcf"] for f in prepared["files"]], prepared["kept"], prepared["unread"]


def build_workbench(game, images: Path, folder: Path, only=None):
    """<folder>/<game>_<sheet>.xcf for every sheet, and .generated.json (what each generated layer was, so
    `import` can tell the owner's edits from untouched layers, and what each .xcf was when written).

    NOTHING OF THE OWNER'S IS EVER REPLACED.  An .xcf that is not the file this tool wrote is the owner's: it
    is first read as `import` reads it, so its edits are in "edits", and then it is left exactly as it is.
    If it cannot be read it is left as it is too.  Only files still as written are made again.
    Returns (written, kept, unread): the .xcf files written, the owner's sheets kept (and read), and the
    owner's sheets kept that could not be read."""
    with tempfile.TemporaryDirectory() as tmp:
        prepared = _prepare_workbench(game, Path(images), folder, only, Path(tmp))
        if prepared["files"]:
            run_gimp(_GIMP_BUILD, {"files": prepared["files"]})
    return _finish_workbench(prepared)


def build_workbenches(games_and_images, root: Path):
    """Several games' workbenches with ONE start of GIMP (a start alone takes minutes): build_workbench for
    each (game, its Images folder), into <root>/<game>.  Returns {game: (written, kept, unread)}."""
    with tempfile.TemporaryDirectory() as tmp:
        prepared = [_prepare_workbench(game, Path(images), root / game, None, Path(tmp))
                    for game, images in games_and_images]
        files = [item for one in prepared for item in one["files"]]
        if files:
            run_gimp(_GIMP_BUILD, {"files": files})
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


def import_workbench(game, folder: Path, only=None):
    """Read every <game>_<sheet>.xcf (or only the sheets in `only`) back through GIMP; keep each mask and
    tone layer the owner changed in <folder>/edits/<sheet>/ and drop the ones that are still as generated.
    Returns what was kept."""
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
            for k, leaf in enumerate(leaves):
                layer = tall[k * height:(k + 1) * height]
                target = edits / stem / leaf
                if _sha(_clean(layer)) == manifest.get(stem, {}).get(leaf):
                    if target.is_file():
                        target.unlink()         # put back as generated: the edit is withdrawn
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                Image.fromarray(layer).save(target)
                kept.append(f"{stem}/{leaf}")
    return kept


def skin_only(layer, mask):
    """A tone layer with every pixel outside the skin mask made fully transparent (what may ship)."""
    out = layer.copy()
    out[~mask] = 0
    out[out[..., 3] == 0] = 0
    return out


def publish_edits(art: Art, edits: Path, out: Path):
    """The owner's kept edits (<workbench>/<game>/edits) as shippable files under `out`/<game>/<sheet>/:
    mask.png (white where skin) for every sheet with an edit, and each painted tone layer cut to that mask.
    Then `out`/manifest.json is written again for everything under `out`.  Returns the files written."""
    written = []
    target = out / art.game
    if target.is_dir():
        for old in sorted(target.rglob("*.png")):
            old.unlink()
    for name in art.specs:
        stem = Path(name).stem
        folder = edits / stem
        tones = sorted(folder.glob("tone_*.png")) if folder.is_dir() else []
        if not tones and not (folder / "mask.png").is_file():
            continue
        mask = art.mask(name)                   # the owner's edited mask when there is one, else the generated
        (target / stem).mkdir(parents=True, exist_ok=True)
        white = np.zeros(mask.shape + (4,), np.uint8)
        white[mask] = 255
        Image.fromarray(white).save(target / stem / "mask.png")
        written.append(f"{art.game}/{stem}/mask.png")
        for path in tones:
            layer = np.array(Image.open(path).convert("RGBA"))
            if layer.shape[:2] != mask.shape:
                raise SystemExit(f"{path}: not the sheet's size")
            Image.fromarray(skin_only(layer, mask)).save(target / stem / path.name)
            written.append(f"{art.game}/{stem}/{path.name}")
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

One GIMP file per head and body sheet of each game, for editing the skin tones by hand.
These files hold the game's own art. Keep them here; they must never be shared or shipped.

THE LAYERS (bottom to top)
  Game's own art               The original sheet. Locked. For reference.
  Skin mask                    White where the patcher treats a pixel as skin. Hidden.
                               Paint white to make a pixel skin, erase to make it not skin.
  Tone 01 - S1 Porcelain ...   One layer per skin tone, light to dark, to Tone 10 - S10 Ebony.
                               Only the skin pixels are on it. All hidden but one; click the
                               eye to see another.
  Hair and non-skin (vanilla)  The original's hair, eyes, mouths and clothes. Locked, on top,
                               so painting a tone layer never covers them.

HOW TO EDIT
  - To change how one tone looks: show that Tone layer and paint on it.
  - To change WHAT counts as skin for every tone: show the Skin mask layer and paint or erase.
    Every tone you did not paint yourself is then made again from your mask.
  - If you paint a tone where the Skin mask is not white, paint the Skin mask white there too:
    only paint inside the mask goes into the patcher.
  - Do not rename, merge or delete layers, and do not resize the picture.
  - Save as .xcf under the same name (Ctrl+S).

HOW TO GET YOUR EDITS INTO THE MOD
  Run, from the patcher's folder:
      python scripts\\skin_tone_sheets.py import --game vv1      (vv1 ... vv5)
  It asks GIMP to read your .xcf files and keeps every layer you changed in
      <this folder>\\<game>\\edits\\<sheet>\\mask.png  and  tone_NN.png
  Whatever is in "edits" wins over the generated art from then on.
  A layer you did not change is not kept, so it still follows later changes to the tone list.
  To drop an edit, delete its file in "edits".

TO PUT YOUR EDITS IN THE PATCHER ITSELF (so every player gets them)
      python scripts\\skin_tone_sheets.py publish --game vv1 --images "<the game's Images folder>"
  It copies your mask and your painted tone layers into the patcher's
      assets\\skin_tones\\owner_edits\\<game>\\<sheet>\\
  as the skin pixels only: nothing of the game's own art goes with them.

TO MAKE THE FILES AGAIN (safe: nothing of yours is ever replaced)
      python scripts\\skin_tone_sheets.py workbench --game vv1 --images "<the game's Images folder>"
  A file you have changed is never overwritten. It is read first, exactly as "import" reads it, so its
  edits are kept in "edits", and then it is left as it is. Only files you have not touched are made
  again (with your "edits" applied). To have one of your own files made again, delete it yourself first.
  "import" is still how to bring "edits" up to date after you paint.
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("what", choices=["preview", "sheets", "workbench", "import", "mockup", "heathens", "publish", "audit",
                                    "workbench-all"])
    ap.add_argument("--game", choices=sorted(TITLES))
    ap.add_argument("--images-root", type=Path, help="mockup: the folder holding every game's own folder")
    ap.add_argument("--images", type=Path, help="the game's own Images folder (read only)")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--masks", action="store_true", help="preview: also a mask picture per sheet")
    ap.add_argument("--workbench", type=Path, default=WORKBENCH)
    ap.add_argument("--only", nargs="*", help="workbench: only these sheets (file names without .png)")
    args = ap.parse_args()
    if args.what == "mockup":
        mockup(args.images_root, args.out, args.workbench if args.workbench.is_dir() else None)
        return 0
    if args.what == "workbench-all":
        args.workbench.mkdir(parents=True, exist_ok=True)
        (args.workbench / "README.txt").write_text(README, encoding="utf-8")
        games = [g for g in sorted(TITLES) if not args.only or g in args.only]
        done = build_workbenches([(g, args.images_root / FOLDERS[g] / "Images") for g in games], args.workbench)
        for game, (written, kept, unread) in done.items():
            print(f"{game}: wrote {len(written)}; kept {len(kept)} changed by you (edits read); "
                  f"kept {len(unread)} changed by you that could not be read")
        return 0
    if not args.game:
        raise SystemExit("--game is needed")
    folder = args.workbench / args.game
    if args.what == "import":
        kept = import_workbench(args.game, folder)
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
        args.workbench.mkdir(parents=True, exist_ok=True)
        (args.workbench / "README.txt").write_text(README, encoding="utf-8")
        written, kept, unread = build_workbench(args.game, args.images, folder, args.only)
        for path in written:
            print("wrote", path)
        for stem in kept:
            print("kept (changed by you; its edits are in \"edits\"):", f"{args.game}_{stem}.xcf")
        for stem in unread:
            print("kept (changed by you; it could NOT be read, nothing was done to it):", f"{args.game}_{stem}.xcf")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
