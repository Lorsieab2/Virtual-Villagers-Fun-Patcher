"""Skin tones, preliminary art: grayscale the skin, overlay the tone, put the game's own hair back.

The owner's method (2026-11-26): "grayscale heads, overlay the skintone. then overlay the vanilla hair
colors on it."  This script is the reference for that pipeline and writes the preview pictures.  It is a
development tool: it reads a game's own Images folder (read only) and writes pictures made from game art
to an output folder, which must never be committed (previews/ is in .git/info/exclude).

    python scripts/skin_tone_preview.py --game vv1 --images "<A New Home>\\Images" --out previews

THE PIPELINE, per sheet:
  1. SKIN MASK.  Which pixels are skin (see skin_mask).  Everything else -- hair, eyes, mouths, outlines,
     clothes, masks -- is never read or written, so it stays exactly the game's own.
  2. GRAYSCALE.  A skin pixel keeps only its lightness (CIE L*), placed within its own cell row's skin range:
     the row's 2nd percentile is 0, its median 0.5, its 98th percentile 1.  (Each row is a head or a body
     painted in its own stock skin, some tanned, so the range is measured per row.)
  3. OVERLAY THE TONE.  The tone's colour lands exactly on the grey's middle.  Darker greys go down a
     shadow span and lighter greys up a highlight span, and the two spans are set PER TONE so that the
     art's contrast survives where a flat multiply would crush it: a dark tone that has no room below
     keeps a floor under its shadows and gets a taller highlight span instead; a light tone the other
     way round.  Shadows lean a little redder and richer, highlights a little yellower and paler, the way
     skin is painted by hand, so dark tones stay warm instead of going grey.
  4. HAIR BACK ON TOP.  Because of 1, hair was never touched; step 4 is the proof: every pixel outside the
     mask is compared with the stock sheet and must be byte-identical (check_untouched).

THE TONES are one table, TONE_TABLE: tone 0 is the game's own art, tones 1..N are colours, light to dark.
Swap the table for the owner's exact colours and nothing else changes.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

CELL_W, CELL_H = 40, 65
EIGHT = np.ones((3, 3), bool)

# ---- the tones: ONE table, src/vv_skin_tones.py ----------------------------------------------------
# Each row is (name, hex, OKLab lightness, chroma, hue in degrees) of the LIT MID-SKIN: the owner's ten,
# Porcelain to Ebony.  Tone 0 (the game's own art, "Default") is not in the table.
import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import vv_skin_tones as _model  # noqa: E402

TONE_TABLE = list(_model.TONE_TABLE)


def _hex(text):
    return tuple(int(text[i:i + 2], 16) for i in (1, 3, 5))

# REPLACE (the owner, 2026-11-26: "instead of overlaying on the grayscale it replaces it").  All in OKLCh.
L_FLOOR, L_CEIL = 0.14, 0.985           # no skin pixel darker or lighter than this (OKLab lightness)
GIVE = 0.3                              # of a side the floor or ceiling squeezes, this much goes to the other
SHADING = 0.65                          # how much of the art's own light and dark a tone keeps (the owner's
                                        # reference is flatter than the art; 1 is the art's full shading)
SHADOW_CHROMA = 0.22                    # chroma grows by up to this share in the deepest shadow; never shrinks


# ---- colour ------------------------------------------------------------------------------------------

_M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
_WHITE = _M @ np.ones(3)


def to_lab(rgb):
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


def _lin(rgb):
    c = np.asarray(rgb, float) / 255
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


_OK1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929], [0.2119034982, 0.6806995451, 0.1073969566],
                 [0.0883024619, 0.2817188376, 0.6299787005]])
_OK2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468], [1.9779984951, -2.4285922050, 0.4505937099],
                 [0.0259040371, 0.7827717662, -0.8086757660]])


def to_oklab(rgb):
    return np.cbrt(_lin(rgb) @ _OK1.T) @ _OK2.T


def oklab_to_linear(lab):
    return ((np.asarray(lab, float) @ np.linalg.inv(_OK2).T) ** 3) @ np.linalg.inv(_OK1).T


def oklch_to_rgb(L, chroma, hue):
    """sRGB 0..255 of OKLCh colours.  A colour outside sRGB keeps its lightness and hue and gives up only
    as much chroma as it must (never a per-channel clip, which would shift the hue)."""
    L, chroma = np.asarray(L, float), np.asarray(chroma, float) * np.ones_like(L)
    h = np.radians(hue) * np.ones_like(L)

    def lin(c):
        return oklab_to_linear(np.stack([L, c * np.cos(h), c * np.sin(h)], -1))

    def inside(c):
        v = lin(c)
        return ((v >= -1e-4) & (v <= 1 + 1e-4)).all(-1)

    lo, hi = np.zeros_like(chroma), chroma.copy()
    ok = inside(hi)
    for _ in range(14):
        mid = (lo + hi) / 2
        good = inside(mid)
        lo = np.where(good, mid, lo)
        hi = np.where(good, hi, mid)
    v = np.clip(lin(np.where(ok, chroma, lo)), 0, 1)
    return np.where(v <= 0.0031308, v * 12.92, 1.055 * v ** (1 / 2.4) - 0.055) * 255


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


def _tones():
    """TONE_TABLE as (name, L, chroma, hue, what, note) in OKLCh: name "S5", what "Copper"."""
    return [(f"S{i}", L, chroma, hue, what, f"{text}, exact")
            for i, (what, text, L, chroma, hue) in enumerate(TONE_TABLE, 1)]


TONES = _tones()


def tone_lab(tone):
    h = np.radians(tone[3])
    return np.array([tone[1], tone[2] * np.cos(h), tone[2] * np.sin(h)])


def tone_steps():
    """OKLab delta E from each tone's mid-skin to the next one's."""
    return [float(np.linalg.norm(tone_lab(a) - tone_lab(b))) for a, b in zip(TONES, TONES[1:])]


# ---- the skin mask (A New Home; measured 2026-11-06, docs of draft PR #707) ---------------------------

CORE = (23.5, 42.0, 0.20, 0.82, 0.45)
SHADOW = (18.0, 23.5, 0.20, 0.55, 0.45)
HIGHLIGHT = (42.0, 70.0, 0.15, 0.55, 0.85)
CAP_MARGIN, CAP_MIN, CAP_MAX = 0.15, 0.55, 0.82
MIN_BLOB = 5
GROW = 2
MAX_SHEEN = 8
EDGE_REACH = 2
CLOTH_REACH = 2
BODY_FLOOR = 0.22          # off-white and cream cloth is under this; a body's palest skin is over it


def _box(h, s, v, box, cap=None):
    h0, h1, s0, s1, v0 = box
    return (h >= h0) & (h <= h1) & (s >= s0) & (s <= (s1 if cap is None else cap)) & (v >= v0)


def colour_rule(a, cap=CORE[3], floor=CORE[2], highlight=True):
    h, s, v = hsv(a)
    r, g, b = (a[..., i].astype(int) for i in range(3))
    boxes = ((_box(h, s, v, CORE, cap) | _box(h, s, v, HIGHLIGHT)) & (s >= floor)) | _box(h, s, v, SHADOW)
    return (a[..., 3] > 0) & (r >= g) & (g >= b) & boxes


def row_cap(row, heads, cell=(CELL_W, CELL_H), front=5):
    """(cap, floor): the row's own saturation limits, from its reference skin.  The floor keeps cream and
    off-white cloth (the white vest, the striped top) out of a BODY row's seeds; a face's pale highlight
    is real skin, so heads keep the plain floor and the highlight box."""
    cw, ch = cell
    # A head's reference skin: the cheeks and chin of its front-facing cell (40 x 65 cells: x 14..26,
    # y 15..21; scaled for the big portrait heads).  None: the whole row.
    ref = row
    if heads and front is not None:
        ref = row[ch * 15 // 65:ch * 22 // 65, front * cw + cw * 14 // 40:front * cw + cw * 27 // 40]
    m = colour_rule(ref)
    if not m.any():
        return CORE[3], HIGHLIGHT[2] if heads else BODY_FLOOR
    med = float(np.median(hsv(ref)[1][m]))
    floor = HIGHLIGHT[2] if heads else BODY_FLOOR
    return float(np.clip(med + CAP_MARGIN, CAP_MIN, CAP_MAX)), floor


def skin_mask(a, heads, exclude=(), cloth=None, cell=(CELL_W, CELL_H), front=5):
    """The skin pixels of sheet `a`.  `exclude` is a list of (row, x0, y0, x1, y1) cell rectangles
    (x, y within a cell; applied to every cell of that row) that are never skin: the numbers-only
    exception table for hair or cloth painted in exactly the colours of skin.  `cloth` is
    {row: (near, also)}: in that row a pixel within CLOTH_REACH of a `near` pixel that is also `also`
    is never skin.  `cell` is the sheet's cell size and `front` a head sheet's front-facing column."""
    CELL_W, CELL_H = cell
    m = np.zeros(a.shape[:2], bool)
    for r in range(a.shape[0] // CELL_H):
        sl = slice(r * CELL_H, (r + 1) * CELL_H)
        cap, floor = row_cap(a[sl], heads, cell, front)
        m[sl] = colour_rule(a[sl], cap, floor, heads)
    never = np.zeros_like(m)
    for row, x0, y0, x1, y1 in exclude:
        for c in range(a.shape[1] // CELL_W):
            never[row * CELL_H + y0:row * CELL_H + y1, c * CELL_W + x0:c * CELL_W + x1] = True
    if cloth:
        hh, ss, vv = hsv(a)
        for row, (near, also) in cloth.items():
            sl = slice(row * CELL_H, (row + 1) * CELL_H)
            beside = ndimage.binary_dilation(near(hh[sl], ss[sl], vv[sl]) & (a[sl][..., 3] > 0), EIGHT,
                                             iterations=CLOTH_REACH)
            never[sl] |= beside & also(hh[sl], ss[sl], vv[sl])
    m &= ~never
    lab, n = ndimage.label(m, structure=EIGHT)
    if n:
        sizes = ndimage.sum(m, lab, index=np.arange(1, n + 1))
        keep = np.zeros(n + 1, bool)
        keep[1:] = sizes >= MIN_BLOB
        if not heads:
            # A body's skin always reaches the figure's outline somewhere (an arm, a leg, the neck).  A
            # skin-coloured patch wholly inside cloth is the cloth's own pattern (the cream stripes of
            # the men's striped top), so it is never skin.
            outside = ndimage.binary_dilation(a[..., 3] < 128, EIGHT, iterations=EDGE_REACH)
            keep[1:] &= ndimage.maximum(outside, lab, index=np.arange(1, n + 1)) > 0
        m = keep[lab]
    h, s, v = hsv(a)
    r, g, b = (a[..., i].astype(int) for i in range(3))
    opaque = a[..., 3] > 0
    warm_edge = opaque & (r >= g) & (g >= b) & (h >= 18) & (h <= 50) & (s <= 0.80) & (v >= 0.60)
    blush = opaque & ((h >= 340) | (h <= 10)) & (s <= 0.45) & (v >= 0.60)
    sheen = opaque & (r >= g) & (g >= b) & (r - b >= 12) & (s >= 0.04) & (s <= 0.45) & (v >= 0.85)
    if not heads:
        warm_edge &= s >= BODY_FLOOR
    m = m | (ndimage.binary_dilation(m, EIGHT) & warm_edge & ~never)
    # Sheen and blush are skin only as SMALL patches: a big warm-white area is cloth.
    attach = (sheen | blush) & ~m & ~never
    lab, n = ndimage.label(attach, structure=EIGHT)
    if n:
        sizes = ndimage.sum(attach, lab, index=np.arange(1, n + 1))
        keep = np.zeros(n + 1, bool)
        keep[1:] = sizes <= MAX_SHEEN
        attach = keep[lab]
    for _ in range(GROW):
        m = m | (ndimage.binary_dilation(m, EIGHT) & attach)
    # Enclosed: a warm pixel with skin nearly all round it is skin too (the deep orange shade beside an
    # eye or under a brow, a bright glint).  Neutral pixels (eye whites, teeth) and dark ones never are.
    warm = opaque & ~never & (r >= g) & (g >= b) & (r - b >= 12) & (v >= 0.45) & ((h <= 50) | (h >= 340))
    glint = opaque & ~never & (s >= 0.15) & (v >= 0.85) & (h >= 20) & (h <= 75)
    lips = opaque & ((h <= 12) | (h >= 340)) & (s >= 0.50)
    for _ in range(2):
        around = ndimage.convolve(m.astype(np.uint8), np.ones((3, 3), np.uint8), mode="constant") - m
        m = m | (~m & ~lips & ((warm & (around >= 5)) | (glint & (around >= 6))))
    return m


# ---- replace the skin's colour with the tone; the art's shading moves only its lightness -------------

def tone_scales(L, down, up):
    """(scale_down, scale_up) for a tone of lightness L over a row whose skin goes `down` below and `up`
    above its own middle.  1 keeps the art's own shading; a side with no room (a dark tone's shadows over
    the floor, a pale tone's highlights under the ceiling) is squeezed to fit, and the other side is
    stretched by GIVE of that, so the shading stays readable at both ends of the scale."""
    s_down = min(1.0, (L - L_FLOOR) / max(down, 1e-6))
    s_up = min(1.0, (L_CEIL - L) / max(up, 1e-6))
    s_down, s_up = max(s_down, 0.0), max(s_up, 0.0)
    more_up = min(1 + GIVE * (1 - s_down), (L_CEIL - L) / max(up, 1e-6))
    more_down = min(1 + GIVE * (1 - s_up), (L - L_FLOOR) / max(down, 1e-6))
    return (more_down if s_up < 1 else s_down), (more_up if s_down < 1 else s_up)


def shade(offset, tone, down, up):
    """The tone at lightness offsets `offset` from the row's middle skin (OKLab L).  Hue is the tone's own,
    always.  Chroma is the tone's own and grows a little into the shadows; it never shrinks, except where
    sRGB itself cannot hold it (oklch_to_rgb)."""
    _, L, chroma, hue = tone[:4]
    offset, down, up = offset * SHADING, down * SHADING, up * SHADING
    s_down, s_up = tone_scales(L, down, up)
    out_L = np.clip(L + np.where(offset < 0, offset * s_down, offset * s_up), L_FLOOR, L_CEIL)
    depth = np.clip(-offset / max(down, 1e-6), 0, 1)
    return oklch_to_rgb(out_L, chroma * (1 + SHADOW_CHROMA * depth), hue)


def recolour(a, mask, tone, cell_h=CELL_H):
    """Sheet `a` with every skin (mask) pixel's colour replaced by the tone; nothing else is written."""
    L = to_oklab(a[..., :3])[..., 0]
    out = a.copy()
    for r in range(a.shape[0] // cell_h):
        sl = slice(r * cell_h, (r + 1) * cell_h)
        sel = mask[sl]
        if not sel.any():
            continue
        lo, mid, hi = np.percentile(L[sl][sel], (2, 50, 98))
        block = out[sl]
        block[sel, :3] = shade(L[sl][sel] - mid, tone, mid - lo, hi - mid).round().astype(np.uint8)
        out[sl] = block
    return out


def check_untouched(stock, made, mask):
    """Step 4's proof: every pixel outside the mask (hair, eyes, clothes, alpha) is the game's own."""
    same = (stock == made).all(-1)
    return bool(same[~mask].all()) and bool((stock[..., 3] == made[..., 3]).all())


# ---- pictures ---------------------------------------------------------------------------------------

# A New Home's cloth painted in the colours of skin, by (sex, body value).  Numbers only, no art:
#   men's body 0, the off-white vest: its cream shade beside the white is cloth;
#   men's body 1, the red and cream striped top: cream beside the red is cloth.
VV1_EXCLUDE: dict[str, tuple] = {}
VV1_CLOTH_RULES = {
    ("male", 0): (lambda h, s, v: (s < 0.15) & (v >= 0.85), lambda h, s, v: (s < 0.40) & (h >= 40)),
    ("male", 1): (lambda h, s, v: ((h <= 12) | (h >= 340)) & (s >= 0.55), lambda h, s, v: (h >= 44) & (s < 0.50)),
}


def cloth_rules_for(name):
    """VV1_CLOTH_RULES as {row within this sheet: rule}; a body or action file's second digit is its
    half of the body values (0: bodies 0-9, 1: bodies 10-19)."""
    stem = name.split(".")[0]
    if "heads" in stem:
        return None
    sex, first = stem.split("_")[0], 10 * int(stem[-1])
    return {body - first: rule for (s, body), rule in VV1_CLOTH_RULES.items() if s == sex and 0 <= body - first < 10}

VV1_SHEETS = ["male_heads.png", "female_heads.png"] + [
    f"{sex}_{kind}{page}.png" for sex in ("male", "female")
    for kind, pages in (("bodies", ("00", "01", "10", "11")), ("actions", ("00", "01"))) for page in pages]


class Art:
    def __init__(self, images: Path):
        self.images = images
        self._raw, self._mask, self._made = {}, {}, {}

    def sheet(self, name, tone=None):
        if name not in self._raw:
            a = np.array(Image.open(self.images / name).convert("RGBA"))
            self._raw[name] = a
            self._mask[name] = skin_mask(a, "heads" in name, VV1_EXCLUDE.get(name, ()), cloth_rules_for(name))
        if tone is None:
            return self._raw[name]
        key = (name, tone[0])
        if key not in self._made:
            made = recolour(self._raw[name], self._mask[name], tone)
            if not check_untouched(self._raw[name], made, self._mask[name]):
                raise SystemExit(f"{name}: a pixel outside the skin mask changed")
            self._made[key] = made
        return self._made[key]

    def cell(self, name, col, row, tone=None):
        a = self.sheet(name, tone)
        return Image.fromarray(a[row * CELL_H:(row + 1) * CELL_H, col * CELL_W:(col + 1) * CELL_W].copy())

    def head(self, sex, row, tone=None, col=5):
        return self.cell(f"{sex}_heads.png", col, row, tone)

    def body(self, sex, row, tone=None, col=8):
        return self.cell(f"{sex}_bodies0{row // 10}.png", col, row % 10, tone)

    def villager(self, v, tone=None):
        """Standing, placed as the village draw 0x437790 places head and body."""
        canvas = Image.new("RGBA", (CELL_W + 4, 72), (0, 0, 0, 0))
        body, head = self.body(v["sex"], v["body"], tone), self.head(v["sex"], v["head"], tone)
        if v.get("age", 600) < 0x118:            # a child: body age/7+50 %, head age/14+80 %
            for img, pct in ((body, v["age"] // 7 + 50), (head, v["age"] // 14 + 80)):
                w, h = int(CELL_W * pct / 100), int(CELL_H * pct / 100)
                canvas.alpha_composite(img.resize((w, h), Image.BOX), (2 + (CELL_W - w) // 2, -8 + (CELL_H - h) // 2))
        else:
            canvas.alpha_composite(body, (2, 6))
            canvas.alpha_composite(head, (2, 2))
        return canvas


def _font(size=12):
    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return ImageFont.load_default()


GRASS = (104, 142, 78, 255)


def grid(rows, cols, draw, row_labels, col_labels, title, path, zoom, size, label_w=120):
    font = _font(12 if zoom > 1 else 10)
    cw, ch, top = max(size[0] * zoom + 4, 74), size[1] * zoom + 4, 40
    out = Image.new("RGB", (label_w + cw * len(cols) + 4, top + ch * len(rows) + 6), (245, 242, 235))
    d = ImageDraw.Draw(out)
    d.text((8, 5), title, fill=(20, 20, 20), font=font)
    for j, lab in enumerate(col_labels):
        d.text((label_w + j * cw + 2, 24), lab, fill=(20, 20, 20), font=font)
    for i, r in enumerate(rows):
        d.text((6, top + i * ch + ch // 2 - 6), row_labels[i], fill=(20, 20, 20), font=font)
        for j, c in enumerate(cols):
            tile = Image.new("RGBA", size, GRASS)
            tile.alpha_composite(draw(r, c))
            out.paste(tile.resize((size[0] * zoom, size[1] * zoom), Image.NEAREST).convert("RGB"),
                      (label_w + j * cw + 2, top + i * ch))
    out.save(path)
    print("wrote", path)


def swatches(path):
    """The tone table: the ramp of mid-skin swatches with the delta E to the next, then each tone's
    shadow / own colour / highlight, then where each row stands against its published hex."""
    font = _font()
    sw = 62
    steps = tone_steps()
    out = Image.new("RGB", (16 + sw * len(TONES), 190 + 15 * len(TONES)), (245, 242, 235))
    d = ImageDraw.Draw(out)
    d.text((8, 4), "Tone ramp: each tone's mid-skin, and the OKLab delta E to the next tone", fill=(20, 20, 20), font=font)
    for j, tone in enumerate(TONES):
        mid = tuple(int(x) for x in shade(np.array([0.0]), tone, 0.14, 0.07)[0].round())
        d.rectangle((8 + j * sw, 22, 8 + (j + 1) * sw - 1, 62), fill=mid)
        d.text((8 + j * sw + 2, 64), f"S{j + 1} {tone[4]}"[:13], fill=(20, 20, 20), font=_font(9))
        if j < len(steps):
            d.text((8 + (j + 1) * sw - 14, 78), f"{steps[j]:.3f}", fill=(120, 30, 30), font=_font(9))
    d.text((8, 96), "Shadow, the tone itself, highlight", fill=(20, 20, 20), font=font)
    for j, tone in enumerate(TONES):
        for i, g in enumerate((-0.14, 0.0, 0.07)):
            c = tuple(int(x) for x in shade(np.array([g]), tone, 0.14, 0.07)[0].round())
            d.rectangle((8 + j * sw, 112 + i * 20, 8 + (j + 1) * sw - 3, 112 + (i + 1) * 20 - 2), fill=c)
    for j, tone in enumerate(TONES):
        mid = tuple(int(x) for x in shade(np.array([0.0]), tone, 0.14, 0.07)[0].round())
        line = (f"{tone[0]} ({tone[4]}): L {tone[1]:.2f} C {tone[2]:.3f} h {tone[3]:.0f}  "
                f"#{mid[0]:02x}{mid[1]:02x}{mid[2]:02x}  {tone[5]}")
        d.text((8, 180 + 15 * j), line, fill=(20, 20, 20), font=_font(10))
        print(line + (f"  next dE {steps[j]:.3f}" if j < len(steps) else ""))
    out.save(path)
    print("wrote", path)


def write_masks(art: Art, out: Path):
    for name in VV1_SHEETS:
        a = art.sheet(name)
        m = art._mask[name]
        grey = a[..., :3].mean(-1, keepdims=True).repeat(3, -1) * 0.6 + 40
        pic = np.where(m[..., None], np.array([255, 0, 255]), grey)
        alpha = a[..., 3:4] / 255
        pic = pic * alpha + np.array([90, 110, 90]) * (1 - alpha)
        img = Image.fromarray(pic.astype(np.uint8))
        img.resize((img.width * 2, img.height * 2), Image.NEAREST).save(out / f"mask_{name}")
        opaque = int((a[..., 3] > 0).sum())
        print(f"{name}: opaque {opaque}, skin {int(m.sum())} ({100 * m.sum() / opaque:.1f}%)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--game", default="vv1", choices=["vv1"])
    ap.add_argument("--images", required=True, type=Path, help="the game's own Images folder (read only)")
    ap.add_argument("--out", required=True, type=Path, help="where the previews go (never committed)")
    ap.add_argument("--masks", action="store_true", help="also write one mask picture per sheet")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    art = Art(args.images)
    tones = [("Game's own", None)] + [(f"{i} {t[4]}", t) for i, t in enumerate(TONES, 1)]
    labels = [t[0] for t in tones]
    g = args.game
    swatches(args.out / f"{g}_tone_table.png")
    if args.masks:
        (args.out / "masks").mkdir(exist_ok=True)
        write_masks(art, args.out / "masks")

    people = [("Man", {"sex": "male", "head": 11, "body": 6}),
              ("Woman", {"sex": "female", "head": 10, "body": 3}),
              ("Man, gold hair", {"sex": "male", "head": 0, "body": 1}),
              ("Woman, blond", {"sex": "female", "head": 3, "body": 12}),
              ("Elder man", {"sex": "male", "head": 4, "body": 15}),
              ("Woman, tanned head", {"sex": "female", "head": 0, "body": 7}),
              ("Boy, 7", {"sex": "male", "head": 10, "body": 2, "age": 140}),
              ("Girl, 7", {"sex": "female", "head": 6, "body": 9, "age": 140})]
    heads = [(f"{s[0].upper()} head {r}", (s, r)) for s, r in
             (("male", 0), ("male", 2), ("male", 4), ("male", 8), ("male", 13), ("male", 17),
              ("female", 0), ("female", 3), ("female", 5), ("female", 9), ("female", 14), ("female", 18))]
    bodies = [(f"{s[0].upper()} body {r}", (s, r)) for s, r in
              (("male", 0), ("male", 1), ("male", 3), ("male", 9), ("male", 14), ("male", 18),
               ("female", 0), ("female", 4), ("female", 8), ("female", 11), ("female", 16), ("female", 19))]
    for zoom in (1, 4):
        z = f"{zoom}x"
        grid(people, tones, lambda p, t: art.villager(p[1], t[1]), [p[0] for p in people], labels,
             f"A New Home: villagers, the game's own art then the {len(TONES)} tones ({z})",
             args.out / f"{g}_villagers_{z}.png", zoom, (CELL_W + 4, 72), label_w=130)
        grid(heads, tones, lambda h, t: art.head(h[1][0], h[1][1], t[1]).crop((4, 0, 36, 34)),
             [h[0] for h in heads], labels, f"A New Home: heads ({z})",
             args.out / f"{g}_heads_{z}.png", zoom, (32, 34), label_w=90)
        grid(bodies, tones, lambda b, t: art.body(b[1][0], b[1][1], t[1]).crop((4, 14, 36, 62)),
             [b[0] for b in bodies], labels, f"A New Home: bodies ({z})",
             args.out / f"{g}_bodies_{z}.png", zoom, (32, 48), label_w=90)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
