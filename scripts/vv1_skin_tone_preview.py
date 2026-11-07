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
Stage 2, EDGES: one step (8-connected) into warm skin-edge pixels just past the boxes (R >= G >= B, hue
  18..50, saturation <= 0.80, value >= 0.60).
Stage 3, SHEEN AND BLUSH: up to 2 steps into warm near-white shine (R >= G >= B, R - B >= 12, saturation
  0.04..0.45, value >= 0.85) and pale pink blush (hue >= 340 or <= 10, saturation <= 0.45, value >= 0.60).
  Both are skin: shine goes to the ramp's top, blush to the skin of its lightness.
Never skin (the FEATURES): eye whites and teeth (neutral, R - B < 12), lips (strong red, saturation above
0.45), outlines, pupils, brows and mouth lines (value under 0.45, or CIE L* below the row's skin range).

THE RECOLOUR, v2: a GRADIENT MAP.  Each tone is a hand-picked ramp of six natural skin colours, deepest
shadow to highlight (hue-shifted the way pixel-art skin ramps are: redder shadows, warmer highlights).
A skin pixel keeps only its lightness: its CIE L* is placed within its row's own skin range (2nd
percentile -> ramp 0, median -> the mid stop, 98th percentile -> ramp 1) and the ramp's colour at that
place replaces it.  So the art's shading and contrast survive at every tone, and the hue noise of the
dithering does not come through.  Then:
  * EDGES: a feature pixel touching skin that is a dark warm mix of skin and outline (hue 15..45, value
    0.20..0.45) is moved halfway to the ramp colour of its own lightness, so the anti-aliasing stays soft;
  * READABILITY: a feature pixel (one darker than its row's skin range: outlines, pupils, brows, mouth
    lines; never hair or cloth of skin lightness) within 3 pixels of skin whose L* is less than 14 below
    the new skin around it is darkened to 14 below it (hue and chroma kept), so eyes, brows and mouths stay readable
    on dark tones.  Eye whites are never touched.
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

# Six stops each: deepest shadow, shadow, low mid, mid, light, highlight.
STOP_AT = np.array([0.0, 0.18, 0.38, 0.60, 0.80, 1.0])
MID_AT = 0.60
RAMPS = [
    ("Tone 1", [(128, 78, 72), (176, 118, 102), (214, 158, 136), (240, 198, 174), (251, 222, 201), (255, 240, 226)]),
    ("Tone 2", [(118, 70, 58), (166, 108, 86), (204, 148, 118), (231, 186, 152), (245, 210, 180), (253, 231, 207)]),
    ("Tone 3", [(106, 62, 46), (150, 96, 70), (190, 134, 98), (218, 170, 128), (236, 196, 155), (249, 220, 186)]),
    ("Tone 4", [(88, 50, 36), (128, 80, 56), (168, 114, 80), (196, 147, 104), (218, 175, 132), (236, 203, 166)]),
    ("Tone 5", [(70, 40, 30), (104, 64, 46), (140, 92, 64), (170, 120, 84), (196, 150, 110), (220, 182, 146)]),
    ("Tone 6", [(54, 31, 26), (80, 48, 36), (110, 70, 50), (138, 94, 66), (166, 122, 90), (196, 158, 126)]),
    ("Tone 7", [(40, 23, 20), (60, 36, 29), (84, 53, 40), (110, 72, 52), (138, 98, 72), (172, 136, 110)]),
    ("Tone 8", [(28, 16, 15), (43, 26, 22), (62, 39, 31), (84, 55, 41), (110, 78, 60), (146, 114, 94)]),
]
STEPS = 15                  # 1..15: preset p at step 2p - 1; even steps halfway between two ramps (CIELAB)
FEATURE_GAP = 14.0          # L* a feature keeps below the new skin around it
FEATURE_REACH = 3
STOCK_MID = (232, 176, 112)  # the stock sheets' typical lit skin; its nearest step stands in for "stock"

SHEETS = ["male_heads.png", "female_heads.png"] + [
    f"{sex}_{kind}{page}.png" for sex in ("male", "female")
    for kind, pages in (("bodies", ("00", "01", "10", "11")), ("actions", ("00", "01"))) for page in pages]


# ---- colour ------------------------------------------------------------------------------------------

_M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
_WHITE = _M @ np.ones(3)


def to_lab(rgb):
    """CIELAB of sRGB colours (..., 3) in 0..255."""
    c = np.asarray(rgb, float) / 255
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    xyz = lin @ _M.T / _WHITE
    f = np.where(xyz > 216 / 24389, np.cbrt(xyz), (24389 / 27 * xyz + 16) / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def from_lab(lab):
    lab = np.asarray(lab, float)
    fy = (lab[..., 0] + 16) / 116
    f = np.stack([fy + lab[..., 1] / 500, fy, fy - lab[..., 2] / 200], -1)
    xyz = np.where(f ** 3 > 216 / 24389, f ** 3, (116 * f - 16) / (24389 / 27)) * _WHITE
    lin = xyz @ np.linalg.inv(_M).T
    c = np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.clip(lin, 0, None) ** (1 / 2.4) - 0.055)
    return np.clip(c * 255, 0, 255)


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


# ---- the rule ---------------------------------------------------------------------------------------

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


def sheen(a):
    _, s, v = hsv(a)
    r, g, b = (a[..., i].astype(int) for i in range(3))
    return (a[..., 3] > 0) & (r >= g) & (g >= b) & (r - b >= 12) & (s >= 0.04) & (s <= 0.45) & (v >= 0.85)


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
    h, s, v = hsv(a)
    r, g, b = (a[..., i].astype(int) for i in range(3))
    opaque = a[..., 3] > 0
    warm_edge = opaque & (r >= g) & (g >= b) & (h >= 18) & (h <= 50) & (s <= 0.80) & (v >= 0.60)
    blush = opaque & ((h >= 340) | (h <= 10)) & (s <= 0.45) & (v >= 0.60)
    m = m | (ndimage.binary_dilation(m, EIGHT) & warm_edge)
    ok = sheen(a) | blush
    for _ in range(GROW):
        m = m | (ndimage.binary_dilation(m, EIGHT) & ok)
    return m


# ---- the tone model ---------------------------------------------------------------------------------

def step_ramp(step):
    """The six stops (sRGB) of fine step 1..15: a preset on odd steps, the CIELAB midpoint on even."""
    i = (step - 1) / 2
    lo, hi = int(np.floor(i)), int(np.ceil(i))
    if lo == hi:
        return np.array(RAMPS[lo][1], float)
    return from_lab((to_lab(RAMPS[lo][1]) + to_lab(RAMPS[hi][1])) / 2)


def preset_ramp(p):
    return np.array(RAMPS[p - 1][1], float)


def stock_step():
    target = to_lab(np.array(STOCK_MID, float))
    return min(range(1, STEPS + 1), key=lambda s: float(np.linalg.norm(to_lab(step_ramp(s)[3]) - target)))


def blend(mother, father, stock):
    """A baby's step (0 = stock): the mean of the parents' steps, a half rounded toward the mother."""
    if mother == 0 and father == 0:
        return 0
    m, f = mother or stock, father or stock
    total = m + f
    return total // 2 + (1 if total % 2 and m > f else 0)


def _ramp_at(ramp_lab, t):
    """Lab colour at ramp positions t (0..1), linear between stops."""
    t = np.clip(t, 0, 1)
    out = np.empty(t.shape + (3,))
    for c in range(3):
        out[..., c] = np.interp(t, STOP_AT, ramp_lab[:, c])
    return out


def _place(L, lo, mid, hi):
    """A skin lightness's place on the ramp: lo -> 0, mid -> MID_AT, hi -> 1."""
    below = MID_AT * (L - lo) / max(mid - lo, 1e-6)
    above = MID_AT + (1 - MID_AT) * (L - mid) / max(hi - mid, 1e-6)
    return np.where(L < mid, below, above)


def recolour(a, mask, ramp):
    """Sheet `a` with its skin gradient-mapped onto `ramp` (six sRGB stops)."""
    ramp_lab = to_lab(ramp)
    lab = to_lab(a[..., :3])
    L = lab[..., 0]
    h, _, v = hsv(a)
    out_lab = lab.copy()
    new_skin_L = np.full(L.shape, np.nan)
    row_lo = np.full(L.shape, -1.0)
    edge_ok = (a[..., 3] > 0) & ~mask & (h >= 15) & (h <= 45) & (v >= 0.20) & (v < 0.45)
    near_skin = ndimage.binary_dilation(mask, EIGHT)
    for r in range(a.shape[0] // CELL_H):
        sl = slice(r * CELL_H, (r + 1) * CELL_H)
        sel = mask[sl]
        if not sel.any():
            continue
        lo, mid, hi = np.percentile(L[sl][sel], (2, 50, 98))
        row_lo[sl] = lo
        block = out_lab[sl]
        block[sel] = _ramp_at(ramp_lab, _place(L[sl][sel], lo, mid, hi))
        edge = edge_ok[sl] & near_skin[sl]
        if edge.any():
            block[edge] = 0.5 * block[edge] + 0.5 * _ramp_at(ramp_lab, _place(L[sl][edge], lo, mid, hi))
        out_lab[sl] = block
        ns = new_skin_L[sl]
        ns[sel] = block[sel][:, 0]
        new_skin_L[sl] = ns
    # Readability: features near skin stay FEATURE_GAP below the new skin around them.
    filled = np.where(mask, new_skin_L, 0.0)
    weight = mask.astype(float)
    size = 2 * FEATURE_REACH + 1
    local = ndimage.uniform_filter(filled, size) / np.maximum(ndimage.uniform_filter(weight, size), 1e-6)
    near = ndimage.binary_dilation(mask, EIGHT, iterations=FEATURE_REACH)
    r_, g_, b_ = (a[..., i].astype(int) for i in range(3))
    neutral_white = (np.abs(r_ - b_) < 12) & (v > 0.75)
    feature = (a[..., 3] > 0) & ~mask & near & ~neutral_white & (L < row_lo - 4) & (v < 0.35)
    too_close = feature & (out_lab[..., 0] > local - FEATURE_GAP)
    out_lab[..., 0] = np.where(too_close, np.maximum(local - FEATURE_GAP, 0), out_lab[..., 0])
    changed = mask | (edge_ok & near_skin) | too_close
    out = a.copy()
    rgb = from_lab(out_lab).round().astype(np.uint8)
    out[..., :3] = np.where(changed[..., None], rgb, a[..., :3])
    return out


# ---- pictures ---------------------------------------------------------------------------------------

class Art:
    def __init__(self, images: Path):
        self.images = images
        self._raw, self._mask, self._tinted = {}, {}, {}

    def sheet(self, name, ramp=None):
        if name not in self._raw:
            a = np.array(Image.open(self.images / name).convert("RGBA"))
            self._raw[name] = a
            self._mask[name] = skin_mask(a, "heads" in name)
        if ramp is None:
            return self._raw[name]
        key = (name, tuple(np.round(np.asarray(ramp).ravel(), 2)))
        if key not in self._tinted:
            self._tinted[key] = recolour(self._raw[name], self._mask[name], np.asarray(ramp, float))
        return self._tinted[key]

    def cell(self, name, col, row, ramp=None):
        a = self.sheet(name, ramp)
        return Image.fromarray(a[row * CELL_H:(row + 1) * CELL_H, col * CELL_W:(col + 1) * CELL_W].copy())

    def villager(self, v, ramp=None):
        """Standing, placed as the village compositor 0x437790 places head and body (front-ish frames)."""
        canvas = Image.new("RGBA", (CELL_W + 4, 72), (0, 0, 0, 0))
        body = self.cell(f"{v['sex']}_bodies0{v['body'] // 10}.png", 8, v["body"] % 10, ramp)
        head = self.cell(f"{v['sex']}_heads.png", 5, v["head"], ramp)
        if v.get("age", 600) < 0x118:            # a child: body age/7+50 %, head age/14+80 %, centred
            for img, pct in ((body, v["age"] // 7 + 50), (head, v["age"] // 14 + 80)):
                w, h = int(CELL_W * pct / 100), int(CELL_H * pct / 100)
                canvas.alpha_composite(img.resize((w, h), Image.BOX), (2 + (CELL_W - w) // 2, -8 + (CELL_H - h) // 2))
        else:                                   # an adult walking: body at (0, +3), head at (0, -1)
            canvas.alpha_composite(body, (2, 6))
            canvas.alpha_composite(head, (2, 2))
        return canvas

    def face(self, v, ramp=None):
        """The head's front cell alone, cropped to the face."""
        return self.cell(f"{v['sex']}_heads.png", 5, v["head"], ramp).crop((6, 0, 34, 30))


def _font():
    try:
        return ImageFont.load_default(size=12)
    except Exception:  # an older Pillow
        return ImageFont.load_default()


def grid(rows, cols, draw, row_labels, col_labels, title, path, label_w=110, zoom=3, size=(CELL_W + 4, 72)):
    font = _font()
    cw, ch, top = size[0] * zoom + 8, size[1] * zoom + 4, 44
    out = Image.new("RGB", (label_w + cw * len(cols), top + ch * len(rows) + 6), (245, 242, 235))
    d = ImageDraw.Draw(out)
    d.text((8, 6), title, fill=(20, 20, 20), font=font)
    for j, lab in enumerate(col_labels):
        d.text((label_w + j * cw + 4, 26), lab, fill=(20, 20, 20), font=font)
    for i, r in enumerate(rows):
        d.text((6, top + i * ch + ch // 2 - 6), row_labels[i], fill=(20, 20, 20), font=font)
        for j, c in enumerate(cols):
            tile = Image.new("RGBA", size, (104, 142, 78, 255))
            tile.alpha_composite(draw(r, c))
            out.paste(tile.resize((size[0] * zoom, size[1] * zoom), Image.NEAREST).convert("RGB"),
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


def ramp_strip(path):
    """The eight ramps as swatches."""
    font = _font()
    sw = 28
    out = Image.new("RGB", (90 + 6 * sw, 20 + 8 * sw), (245, 242, 235))
    d = ImageDraw.Draw(out)
    for i, (name, stops) in enumerate(RAMPS):
        d.text((6, 20 + i * sw + 8), name, fill=(20, 20, 20), font=font)
        for j, c in enumerate(stops):
            d.rectangle((90 + j * sw, 20 + i * sw, 90 + (j + 1) * sw - 2, 20 + (i + 1) * sw - 2), fill=c)
    d.text((90, 4), "deep shadow .. highlight", fill=(20, 20, 20), font=font)
    out.save(path)
    print("wrote", path)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--images", required=True, type=Path, help="A New Home's own Images folder (read only)")
    ap.add_argument("--out", required=True, type=Path, help="where the masks and previews go (not the repo)")
    ap.add_argument("--no-masks", action="store_true", help="skip the 14 mask pictures")
    args = ap.parse_args()
    repo = Path(__file__).resolve().parents[1]
    if args.out.resolve().is_relative_to(repo):
        raise SystemExit("--out must be outside the repository: pictures made from game art are never committed")
    args.out.mkdir(parents=True, exist_ok=True)
    art = Art(args.images)
    if not args.no_masks:
        write_masks(art, args.out)
    ramp_strip(args.out / "ramps.png")

    child = {"sex": "male", "head": 10, "body": 2, "age": 140}
    man = {"sex": "male", "head": 11, "body": 6}
    woman = {"sex": "female", "head": 10, "body": 3}
    elder = {"sex": "male", "head": 4, "body": 5}
    girl = {"sex": "female", "head": 3, "body": 9, "age": 140}
    people = [("Child (boy, 7)", child), ("Adult man", man), ("Adult woman", woman),
              ("Elder (grey head 4)", elder), ("Child (girl, 7)", girl)]
    tones = [("Stock", None)] + [(n, preset_ramp(p)) for p, (n, _) in enumerate(RAMPS, 1)]
    grid(people, tones, lambda p, t: art.villager(p[1], t[1]), [p[0] for p in people], [t[0] for t in tones],
         "A New Home skin tones v2: stock art, then the 8 preset ramps (3x, gradient map)",
         args.out / "preview_presets_3x.png", label_w=130)

    picks = [1, 4, 6, 8]
    faces = [("Man", man), ("Woman", woman)]
    grid(faces, [("Stock", None)] + [(f"Tone {p}", preset_ramp(p)) for p in picks],
         lambda f, t: art.face(f[1], t[1]), ["Man", "Woman"], ["Stock"] + [f"Tone {p}" for p in picks],
         "Faces close up (4x): stock, Tones 1, 4, 6, 8", args.out / "preview_faces_4x.png",
         label_w=70, zoom=4, size=(28, 30))

    steps = [(f"{s}" + (f" P{(s + 1) // 2}" if s % 2 else ""), step_ramp(s)) for s in range(1, STEPS + 1)]
    grid([("Adult man", man), ("Adult woman", woman)], steps, lambda p, t: art.villager(p[1], t[1]),
         ["Adult man", "Adult woman"], [s[0] for s in steps],
         "Fine control: the 15 steps (P = preset; even steps are halfway in CIELAB)",
         args.out / "preview_fine_steps_3x.png", label_w=90)

    stock = stock_step()
    families = [("Tone 2 + Tone 7", 3, 13), ("Tone 1 + Tone 4", 1, 7), ("Tone 5 + Tone 8", 9, 15),
                ("Tone 3 + Tone 6", 5, 11)]

    def family_cell(r, c):
        father, mother = r[1], r[2]
        s = {"Father": father, "Mother": mother, "Child": blend(mother, father, stock)}[c]
        return art.villager({"Father": man, "Mother": woman, "Child": girl}[c], None if s == 0 else step_ramp(s))

    rows = [(f"{n}  -> step {blend(m, f, stock)}", f, m) for n, f, m in families]
    grid(rows, ["Father", "Mother", "Child"], family_cell, [r[0] for r in rows], ["Father", "Mother", "Child"],
         "A family: the baby's tone is the mean of its parents' steps", args.out / "preview_family_3x.png",
         label_w=170)

    rng = random.Random(20261106)
    founders = []
    for _ in range(8):
        sex = rng.choice(("male", "female"))
        founders.append({"sex": sex, "head": rng.randrange(19 if sex == "male" else 20),
                         "body": rng.randrange(20), "tone": rng.randrange(1, 9)})
    grid(["Founders"], founders, lambda r, f: art.villager(f, preset_ramp(f["tone"])),
         ["Random founders"], [f"{f['sex'][0].upper()}{f['head']}/{f['body']} T{f['tone']}" for f in founders],
         "Random founders and arrivals: a random preset each", args.out / "preview_random_founders_3x.png")
    print("stock step", stock)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
