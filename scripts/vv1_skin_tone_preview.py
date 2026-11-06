"""A New Home (VV1) skin tones, phase 1: the skin rule, the tone model and the preview pictures.

Research only (docs/reports/skin-tone/design.md); nothing here is shipped or wired into the game.
It reads the player's own stock sheets from an Images folder given on the command line and writes the
masks and previews to an output folder given on the command line, which must be outside the repository:
game art and pictures made from it are never committed.

    python scripts/vv1_skin_tone_preview.py --images "<VV1 install>\\Images" --out "<scratch folder>"

THE SKIN RULE (measured 2026-11-06 on the stock sheets).  Each cell row of a sheet (one head value or one
body value) is painted in its own stock skin: most rows are a pale peach (saturation about 0.45-0.55),
some are tanned (female heads 0 and 2, male bodies 14-16: 0.62-0.70).  So the rule is the same everywhere
but for one number per row, CAP, measured from that row:

  CAP = clamp(median saturation of the row's reference skin + 0.15, 0.55, 0.82)
        heads: the front-facing cell (column 5), cheeks and chin (x 14..26, y 15..21);
        bodies and actions: every cell of the row.

Stage 1, SEED: not fully transparent, R >= G >= B, and in one of three HSV boxes
  core       hue 23.5..42 deg, saturation 0.20..CAP,  value >= 0.45   (lit skin)
  shadow     hue 18..23.5 deg, saturation 0.20..0.55, value >= 0.45   (shade; brown fur is 21-23 at 0.60-0.85)
  highlight  hue 42..60 deg,   saturation 0.15..0.55, value >= 0.85   (the yellow-white sheen)
kept only in 8-connected blobs of at least 5 seed pixels.
Stage 2, ATTACHED: grown from the seed by up to 2 steps (8-connected) into
  sheen      R >= G >= B, R - B >= 12, saturation 0.04..0.45, value >= 0.85
  soft shade value >= 0.45, saturation <= 0.30, hue <= 30 or >= 300, R - B >= 6
Pure whites and greys (eye whites) never qualify.

THE RECOLOUR ("centre", K = 0.30, the owner's VV2 choice in research/vv2-skin-source/README.md): each skin
pixel becomes  target + K * (pixel - mean skin of its row), so every head and body of a tone lands on the
same colour whatever stock skin its row was painted in, and K of the art's own shading is kept.
"""
from __future__ import annotations

import argparse
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

CELL_W, CELL_H = 40, 65
CORE = (23.5, 42.0, 0.20, 0.82, 0.45)
SHADOW = (18.0, 23.5, 0.20, 0.55, 0.45)
HIGHLIGHT = (42.0, 60.0, 0.15, 0.55, 0.85)
CAP_MARGIN, CAP_MIN, CAP_MAX = 0.15, 0.55, 0.82
MIN_BLOB = 5
GROW = 2
EIGHT = np.ones((3, 3), bool)

PRESETS = [
    ("Tone 1", (243, 216, 194)), ("Tone 2", (231, 193, 160)), ("Tone 3", (214, 166, 124)),
    ("Tone 4", (190, 139, 96)), ("Tone 5", (162, 112, 74)), ("Tone 6", (131, 87, 58)),
    ("Tone 7", (100, 65, 44)), ("Tone 8", (70, 46, 33)),
]
STEPS = 15                  # 1..15: preset p at step 2p - 1; even steps halfway between two presets (CIELAB)
K_DEFAULT = 0.30
STOCK_MEAN = (232, 176, 112)  # the stock sheets' typical lit skin; its nearest step stands in for "stock"

SHEETS = ["male_heads.png", "female_heads.png"] + [
    f"{sex}_{kind}{page}.png" for sex in ("male", "female")
    for kind, pages in (("bodies", ("00", "01", "10", "11")), ("actions", ("00", "01"))) for page in pages]


# ---- the rule ---------------------------------------------------------------------------------------

def hsv(a: np.ndarray):
    rgb = a[..., :3].astype(float) / 255
    mx = rgb.max(-1)
    d = mx - rgb.min(-1)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    h = np.zeros_like(mx)
    m = d > 0
    rm = m & (mx == r)
    gm = m & (mx == g) & ~rm
    bm = m & ~rm & ~gm
    h[rm] = ((g - b)[rm] / d[rm]) % 6
    h[gm] = (b - r)[gm] / d[gm] + 2
    h[bm] = (r - g)[bm] / d[bm] + 4
    return h * 60, np.where(mx > 0, d / np.maximum(mx, 1e-9), 0), mx


def _box(h, s, v, box, cap=None):
    h0, h1, s0, s1, v0 = box
    return (h >= h0) & (h <= h1) & (s >= s0) & (s <= (s1 if cap is None else cap)) & (v >= v0)


def colour_rule(a, cap=CORE[3]):
    h, s, v = hsv(a)
    r, g, b = (a[..., i].astype(int) for i in range(3))
    return (a[..., 3] > 0) & (r >= g) & (g >= b) & (
        _box(h, s, v, CORE, cap) | _box(h, s, v, SHADOW) | _box(h, s, v, HIGHLIGHT))


def row_cap(row, heads):
    ref = row[15:22, 5 * CELL_W + 14:5 * CELL_W + 27] if heads else row
    m = colour_rule(ref)
    if not m.any():
        return CORE[3]
    return float(np.clip(np.median(hsv(ref)[1][m]) + CAP_MARGIN, CAP_MIN, CAP_MAX))


def attachable(a):
    h, s, v = hsv(a)
    r, g, b = (a[..., i].astype(int) for i in range(3))
    sheen = (r >= g) & (g >= b) & (r - b >= 12) & (s >= 0.04) & (s <= 0.45) & (v >= 0.85)
    soft = (v >= 0.45) & (s <= 0.30) & ((h <= 30) | (h >= 300)) & (r - b >= 6)
    return (a[..., 3] > 0) & (sheen | soft)


def skin_mask(a, heads):
    m = np.zeros(a.shape[:2], bool)
    for r in range(a.shape[0] // CELL_H):
        sl = slice(r * CELL_H, (r + 1) * CELL_H)
        m[sl] = colour_rule(a[sl], row_cap(a[sl], heads))
    lab, n = ndimage.label(m, structure=EIGHT)
    if n:
        sizes = ndimage.sum(m, lab, index=np.arange(1, n + 1))
        keep = np.zeros(n + 1, bool)
        keep[1:] = sizes >= MIN_BLOB
        m = keep[lab]
    ok = attachable(a)
    for _ in range(GROW):
        m = m | (ndimage.binary_dilation(m, EIGHT) & ok)
    return m


# ---- the tone model ---------------------------------------------------------------------------------

_M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
_WHITE = _M @ np.ones(3)


def to_lab(rgb):
    c = np.asarray(rgb, float) / 255
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    xyz = (_M @ lin) / _WHITE
    f = np.where(xyz > 216 / 24389, np.cbrt(xyz), (24389 / 27 * xyz + 16) / 116)
    return np.array([116 * f[1] - 16, 500 * (f[0] - f[1]), 200 * (f[1] - f[2])])


def from_lab(lab):
    fy = (lab[0] + 16) / 116
    f = np.array([fy + lab[1] / 500, fy, fy - lab[2] / 200])
    xyz = np.where(f ** 3 > 216 / 24389, f ** 3, (116 * f - 16) / (24389 / 27)) * _WHITE
    lin = np.linalg.solve(_M, xyz)
    c = np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.clip(lin, 0, None) ** (1 / 2.4) - 0.055)
    return np.clip(c * 255, 0, 255)


def step_colour(step):
    i = (step - 1) / 2
    lo, hi = int(np.floor(i)), int(np.ceil(i))
    if lo == hi:
        return np.array(PRESETS[lo][1], float)
    return from_lab((to_lab(PRESETS[lo][1]) + to_lab(PRESETS[hi][1])) / 2)


def stock_step():
    target = to_lab(STOCK_MEAN)
    return min(range(1, STEPS + 1), key=lambda s: float(np.linalg.norm(to_lab(step_colour(s)) - target)))


def blend(mother, father, stock):
    """A baby's step (0 = stock): the mean of the parents' steps, a half rounded toward the mother."""
    if mother == 0 and father == 0:
        return 0
    m, f = mother or stock, father or stock
    total = m + f
    return total // 2 + (1 if total % 2 and m > f else 0)


def recolour(a, mask, target, k=K_DEFAULT, method="centre"):
    out = a.astype(float)
    t = np.asarray(target, float)
    for r in range(a.shape[0] // CELL_H):
        sl = slice(r * CELL_H, (r + 1) * CELL_H)
        sel = mask[sl]
        if not sel.any():
            continue
        block = out[sl]
        px = block[sel][:, :3]
        mean = px.mean(0)
        if method == "centre":
            new = t + k * (px - mean)
        else:  # VV2's first script: multiply to darken, screen to lighten
            new = np.where(t <= mean, px * (t / mean), 255 - (255 - px) * ((255 - t) / np.maximum(255 - mean, 1)))
        block[sel, :3] = np.clip(new, 0, 255)
        out[sl] = block
    return out.round().astype(np.uint8)


# ---- pictures ---------------------------------------------------------------------------------------

class Art:
    def __init__(self, images: Path):
        self.images = images
        self._raw, self._mask, self._tinted = {}, {}, {}

    def sheet(self, name, target=None, k=K_DEFAULT, method="centre"):
        if name not in self._raw:
            a = np.array(Image.open(self.images / name).convert("RGBA"))
            self._raw[name] = a
            self._mask[name] = skin_mask(a, "heads" in name)
        if target is None:
            return self._raw[name]
        key = (name, tuple(np.round(target, 2)), k, method)
        if key not in self._tinted:
            self._tinted[key] = recolour(self._raw[name], self._mask[name], target, k, method)
        return self._tinted[key]

    def cell(self, name, col, row, *tone):
        a = self.sheet(name, *tone)
        return Image.fromarray(a[row * CELL_H:(row + 1) * CELL_H, col * CELL_W:(col + 1) * CELL_W].copy())

    def villager(self, v, *tone):
        """Standing, placed as the village compositor 0x437790 places head and body (front-ish frames)."""
        canvas = Image.new("RGBA", (CELL_W + 4, 72), (0, 0, 0, 0))
        body = self.cell(f"{v['sex']}_bodies0{v['body'] // 10}.png", 8, v["body"] % 10, *tone)
        head = self.cell(f"{v['sex']}_heads.png", 5, v["head"], *tone)
        if v.get("age", 600) < 0x118:            # a child: body age/7+50 %, head age/14+80 %, centred
            for img, pct in ((body, v["age"] // 7 + 50), (head, v["age"] // 14 + 80)):
                w, h = int(CELL_W * pct / 100), int(CELL_H * pct / 100)
                canvas.alpha_composite(img.resize((w, h), Image.BOX), (2 + (CELL_W - w) // 2, -8 + (CELL_H - h) // 2))
        else:                                   # an adult walking: body at (0, +3), head at (0, -1)
            canvas.alpha_composite(body, (2, 6))
            canvas.alpha_composite(head, (2, 2))
        return canvas


def grid(rows, cols, draw, row_labels, col_labels, title, path, label_w=110, zoom=2):
    try:
        font = ImageFont.load_default(size=11)
    except Exception:  # an older Pillow
        font = ImageFont.load_default()
    cw, ch, top = (CELL_W + 4) * zoom + 8, 72 * zoom + 4, 40
    out = Image.new("RGB", (label_w + cw * len(cols), top + ch * len(rows) + 6), (245, 242, 235))
    d = ImageDraw.Draw(out)
    d.text((8, 6), title, fill=(20, 20, 20), font=font)
    for j, lab in enumerate(col_labels):
        d.text((label_w + j * cw + 4, 24), lab, fill=(20, 20, 20), font=font)
    for i, r in enumerate(rows):
        d.text((6, top + i * ch + ch // 2 - 6), row_labels[i], fill=(20, 20, 20), font=font)
        for j, c in enumerate(cols):
            tile = Image.new("RGBA", (CELL_W + 4, 72), (104, 142, 78, 255))
            tile.alpha_composite(draw(r, c))
            out.paste(tile.resize(((CELL_W + 4) * zoom, 72 * zoom), Image.NEAREST).convert("RGB"),
                      (label_w + j * cw + 2, top + i * ch))
    out.save(path)
    print("wrote", path)


def write_masks(art: Art, out: Path):
    union = set()
    for name in SHEETS:
        a = art.sheet(name)
        m = art._mask[name]
        union |= set(map(tuple, a[m][:, :3].tolist()))
        grey = a[..., :3].mean(-1, keepdims=True).repeat(3, -1) * 0.6 + 40
        pic = np.where(m[..., None], np.array([255, 0, 255]), grey)
        alpha = a[..., 3:4] / 255
        pic = pic * alpha + np.array([90, 110, 90]) * (1 - alpha)
        img = Image.fromarray(pic.astype(np.uint8))
        if "heads" in name:
            img = img.resize((img.width * 2, img.height * 2), Image.NEAREST)
        img.save(out / f"mask_{name}")
        opaque = int((a[..., 3] > 0).sum())
        print(f"{name}: opaque {opaque}, skin {int(m.sum())} ({100 * m.sum() / opaque:.1f}%), "
              f"distinct skin colours {len(set(map(tuple, a[m][:, :3].tolist())))}")
    print("distinct skin colours over all 14 sheets:", len(union))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--images", required=True, type=Path, help="A New Home's own Images folder (read only)")
    ap.add_argument("--out", required=True, type=Path, help="where the masks and previews go (not the repo)")
    args = ap.parse_args()
    repo = Path(__file__).resolve().parents[1]
    if args.out.resolve().is_relative_to(repo):
        raise SystemExit("--out must be outside the repository: pictures made from game art are never committed")
    args.out.mkdir(parents=True, exist_ok=True)
    art = Art(args.images)
    write_masks(art, args.out)

    child = {"sex": "male", "head": 10, "body": 2, "age": 140}
    man = {"sex": "male", "head": 11, "body": 6}
    woman = {"sex": "female", "head": 10, "body": 3}
    elder = {"sex": "male", "head": 4, "body": 5}
    girl = {"sex": "female", "head": 3, "body": 9, "age": 140}
    people = [("Child (boy, 7)", child), ("Adult man", man), ("Adult woman", woman),
              ("Elder (grey head 4)", elder), ("Child (girl, 7)", girl)]
    tones = [("Stock", None)] + [(n, np.array(c, float)) for n, c in PRESETS]
    grid(people, tones, lambda p, t: art.villager(p[1], t[1]), [p[0] for p in people], [t[0] for t in tones],
         "A New Home skin tones: stock art, then the 8 presets (2x, centre method K=0.30)",
         args.out / "preview_presets_2x.png")

    steps = [(f"{s}" + (f" P{(s + 1) // 2}" if s % 2 else ""), step_colour(s)) for s in range(1, STEPS + 1)]
    grid([("Adult man", man), ("Adult woman", woman)], steps, lambda p, t: art.villager(p[1], t[1]),
         ["Adult man", "Adult woman"], [s[0] for s in steps],
         "Fine control: the 15 steps (P = preset; even steps are halfway in CIELAB)",
         args.out / "preview_fine_steps_2x.png", label_w=80)

    ladder = [("K=0.30", 0.30, "centre"), ("K=0.60", 0.60, "centre"), ("K=1.00", 1.0, "centre"),
              ("multiply", 1.0, "multiply")]
    picks = [(n, np.array(c, float)) for n, c in (PRESETS[0], PRESETS[3], PRESETS[7])]
    rows = [(f"{m[0]} {p[0]}", (m, p)) for m in ladder for p in picks]
    grid(rows, [man, woman, elder], lambda r, c: art.villager(c, r[1][1][1], r[1][0][1], r[1][0][2]),
         [r[0] for r in rows], ["Man", "Woman", "Elder"],
         "How much of the art's shading to keep (Tones 1, 4, 8)", args.out / "preview_shading_ladder_2x.png",
         label_w=120)

    stock = stock_step()
    families = [("Tone 2 + Tone 7", 3, 13), ("Tone 1 + Tone 4", 1, 7), ("Stock + Tone 8", 0, 15),
                ("Stock + Stock", 0, 0)]

    def family_cell(r, c):
        father, mother = r[1], r[2]
        s = {"Father": father, "Mother": mother, "Child": blend(mother, father, stock)}[c]
        return art.villager({"Father": man, "Mother": woman, "Child": girl}[c], None if s == 0 else step_colour(s))

    rows = [(f"{n}  -> step {blend(m, f, stock) or 'stock'}", f, m) for n, f, m in families]
    grid(rows, ["Father", "Mother", "Child"], family_cell, [r[0] for r in rows], ["Father", "Mother", "Child"],
         f"A family: the baby's tone is the mean of its parents' steps (stock counts as step {stock})",
         args.out / "preview_family_2x.png", label_w=170)

    rng = random.Random(20261106)
    founders = []
    for _ in range(8):
        sex = rng.choice(("male", "female"))
        founders.append({"sex": sex, "head": rng.randrange(19 if sex == "male" else 20),
                         "body": rng.randrange(20), "tone": rng.randrange(1, 9)})
    grid(["Founders"], founders, lambda r, f: art.villager(f, np.array(PRESETS[f["tone"] - 1][1], float)),
         ["Random founders"], [f"{f['sex'][0].upper()}{f['head']}/{f['body']} T{f['tone']}" for f in founders],
         "Random founders and arrivals: a random preset each (head/body random as the game picks them)",
         args.out / "preview_random_founders_2x.png")
    print("stock step", stock)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
