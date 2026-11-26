"""Skin tones: the method.  The skin mask, the tone laid on the skin, and the small picture helpers.

The owner, 2026-11-26: the skin's colour is REPLACED by the tone ("instead of overlaying on the grayscale it
replaces it"), "Keep the shading from the game art though!!!", and the tones are the ten of the owner's
reference picture, Porcelain to Ebony (src/vv_skin_tones.py).  scripts/skin_tone_sheets.py uses this for
every game's sheets, the previews and the GIMP workbench.  A development tool: nothing here is shipped, and
pictures made from game art are never committed.

THE METHOD, per sheet:
  1. SKIN MASK (skin_mask).  Which pixels are skin: the colour rule, then grown into skin of its own
     colour so necks, arms, legs, hands and feet are whole (grow_alike).  Everything else -- hair, eyes, mouths, outlines,
     clothes, masks -- is never written, so it stays exactly the game's own.
  2. REPLACE, in OKLCh (shade, recolour).  A skin pixel takes the tone's hue and chroma.  Its lightness is
     the tone's own plus the pixel's offset from the middle skin of its own cell row in the game's art
     (each row is a head or a body painted in its own skin), at SHADING strength: so the tone's colour
     lands on the row's middle skin, and the art's highlights, shadows, folds and muscle lines all show.
     Chroma never drops (it rises a little into the shadows); a colour sRGB cannot hold gives up chroma,
     but never below CHROMA_FLOOR of the tone's own -- there its lightness gives way instead -- and never
     hue: nothing comes out grey (ashy).  Lightness stays between L_FLOOR and L_CEIL, and a side with no room is squeezed
     while the other is stretched a little, so dark tones keep a warm sheen and pale ones their shadows.
  3. THE PROOF (check_untouched): every pixel outside the mask is byte-identical to the game's own sheet.
"""
from __future__ import annotations

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
CHROMA_FLOOR = 0.78                     # no skin pixel has less than this share of its tone's own chroma (the
                                        # owner, 2026-11-26: "make sure not to make anything look too ashy")
SHADOW_CHROMA = 0.22                    # chroma grows by up to this share in the deepest shadow; never shrinks


# ---- colour ------------------------------------------------------------------------------------------

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


def _in_srgb(L, chroma, h):
    v = oklab_to_linear(np.stack([L, chroma * np.cos(h), chroma * np.sin(h)], -1))
    return ((v >= -1e-4) & (v <= 1 + 1e-4)).all(-1)


def oklch_to_rgb(L, chroma, hue, floor=None, toward=None):
    """sRGB 0..255 of OKLCh colours.  A colour outside sRGB keeps its hue always.  It first gives up chroma,
    but never below `floor` (when given): where even `floor` does not fit at that lightness -- the very
    lightest highlights and the very deepest shadows, where sRGB has no room for colour -- the lightness
    moves toward `toward` (the tone's own) just far enough that it does.  So nothing comes out grey."""
    L = np.asarray(L, float).copy()
    chroma = np.asarray(chroma, float) * np.ones_like(L)
    h = np.radians(hue) * np.ones_like(L)
    if floor is not None:
        floor = np.minimum(floor * np.ones_like(L), chroma)
        short = ~_in_srgb(L, floor, h)
        if short.any():
            lo, hi = L.copy(), toward * np.ones_like(L)        # lo: does not fit; hi: fits (the tone itself)
            for _ in range(14):
                mid = (lo + hi) / 2
                good = _in_srgb(mid, floor, h)
                hi = np.where(good, mid, hi)
                lo = np.where(good, lo, mid)
            L = np.where(short, hi, L)
    else:
        floor = np.zeros_like(L)
    lo, hi = floor.copy(), chroma.copy()
    ok = _in_srgb(L, hi, h)
    for _ in range(14):
        mid = (lo + hi) / 2
        good = _in_srgb(L, mid, h)
        lo = np.where(good, mid, lo)
        hi = np.where(good, hi, mid)
    c = np.where(ok, chroma, lo)
    v = np.clip(oklab_to_linear(np.stack([L, c * np.cos(h), c * np.sin(h)], -1)), 0, 1)
    return np.where(v <= 0.0031308, v * 12.92, 1.055 * v ** (1 / 2.4) - 0.055) * 255


def chroma_of(rgb):
    """The OKLCh chroma of sRGB colours 0..255."""
    lab = to_oklab(rgb)
    return np.hypot(lab[..., 1], lab[..., 2])


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
ALIKE_STEPS = 3            # how far the mask grows into skin of its own colour
ALIKE_HUE, ALIKE_SAT, ALIKE_DARKER, ALIKE_LIGHTER = 8.0, 0.14, 0.22, 0.15
BLUSH_FLOOR = 0.08
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
    # A blush is pink: a neutral white or grey (an eye's white, teeth: no saturation, so hue 0) is not one.
    blush = opaque & ((h >= 340) | (h <= 10)) & (s >= BLUSH_FLOOR) & (s <= 0.45) & (v >= 0.60)
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
    return grow_alike(a, m, never)


def alike(a, m):
    """The pixels beside the mask `m` that are skin by their neighbours: opaque, warm, and of nearly the
    hue, saturation and value of the mask pixels touching them (at least two).  The deeper shade of a neck
    under a chin, of a forearm or a shin is like that; hair and cloth beside skin are not (hair is far more
    saturated or far darker, cloth another hue)."""
    h, s, v = hsv(a)
    r, g, b = (a[..., i].astype(int) for i in range(3))
    box = np.ones((3, 3))
    n = ndimage.convolve(m.astype(float), box, mode="constant")
    with np.errstate(invalid="ignore", divide="ignore"):
        hm = ndimage.convolve(np.where(m, h, 0.0), box, mode="constant") / n
        sm = ndimage.convolve(np.where(m, s, 0.0), box, mode="constant") / n
        vm = ndimage.convolve(np.where(m, v, 0.0), box, mode="constant") / n
    return ((a[..., 3] > 0) & ~m & (n >= 2) & (r >= g) & (g >= b) & (v >= 0.40)
            & (np.abs(h - hm) <= ALIKE_HUE) & (np.abs(s - sm) <= ALIKE_SAT) & (v >= vm - ALIKE_DARKER)
            & (v <= vm + ALIKE_LIGHTER))


def grow_alike(a, m, never=None):
    """The mask grown ALIKE_STEPS pixels into skin of its own colour (the owner, 2026-11-26: "color necks
    arms and legs too")."""
    for _ in range(ALIKE_STEPS):
        more = alike(a, m)
        if never is not None:
            more &= ~never
        if not more.any():
            break
        m = m | more
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
    return oklch_to_rgb(out_L, chroma * (1 + SHADOW_CHROMA * depth), hue, CHROMA_FLOOR * chroma, L)


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


# ---- A New Home's cloth rules, and the picture helpers ---------------------------------------------

# A New Home's cloth painted in the colours of skin, by (sex, body value).  Numbers only, no art:
#   men's body 0, the off-white vest: its cream shade beside the white is cloth;
#   men's body 1, the red and cream striped top: cream beside the red is cloth.
VV1_CLOTH_RULES = {
    ("male", 0): (lambda h, s, v: (s < 0.15) & (v >= 0.85), lambda h, s, v: (s < 0.40) & (h >= 40)),
    ("male", 1): (lambda h, s, v: ((h <= 12) | (h >= 340)) & (s >= 0.55), lambda h, s, v: (h >= 44) & (s < 0.50)),
}


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
