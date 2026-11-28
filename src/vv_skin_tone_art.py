"""Skin tones: making a tone's sheet from the player's own game art, with nothing but Pillow.

This is the patcher's own copy of the method (scripts/skin_tone_preview.py is the development tool's, on
numpy and scipy, which the patcher does not ship with; tests/test_skin_tone_art.py holds the two to the
same result).  The owner's method, 2026-11-26:

  1. THE SKIN MASK (skin_mask).  Which pixels of a sheet are skin: a colour rule measured row by row (each
     row of cells is a head or a body painted in its own skin), small warm sheen and blush beside it, warm
     pixels enclosed by it, then three pixels' growth into skin of its own colour so necks, arms, legs,
     hands and feet are whole.  Hair, eyes, mouths, outlines, clothes and masks are never skin.
  2. REPLACE (recolour).  A skin pixel takes the tone's hue and chroma in OKLCh; its lightness is the
     tone's plus the pixel's own offset from the middle skin of its row, at SHADING strength, so the art's
     shading shows.  Chroma never falls under CHROMA_FLOOR of the tone's own (nothing ashy): where sRGB has
     no room, lightness gives way instead.
  3. Every pixel outside the mask is left exactly as it is.

A sheet here is (width, height, pixels): pixels a list of (r, g, b, a), row by row (Pillow's getdata()).
"""
from __future__ import annotations

import math
from pathlib import Path

import vv_skin_tones

ROOT = Path(__file__).resolve().parents[1]
# The owner's marking of the skin that ships with the patcher -- where the skin is, never a pixel of art
# (tests/test_skin_tone_owner_edits.py): <game folder "vv1".."vv5">/<sheet>/skin_NN.png and mask.png.
OWNER_EDITS = ROOT / "assets" / "skin_tones" / "owner_edits"

CORE = (23.5, 42.0, 0.20, 0.82, 0.45)           # hue from, hue to, saturation from, to, value from
SHADOW = (18.0, 23.5, 0.20, 0.55, 0.45)
HIGHLIGHT = (42.0, 70.0, 0.15, 0.55, 0.85)
CAP_MARGIN, CAP_MIN, CAP_MAX = 0.15, 0.55, 0.82
MIN_BLOB, GROW, MAX_SHEEN, EDGE_REACH, CLOTH_REACH = 5, 2, 8, 2, 2
BODY_FLOOR = 0.22
BLUSH_FLOOR = 0.08
ALIKE_STEPS = 3
ALIKE_HUE, ALIKE_SAT, ALIKE_DARKER, ALIKE_LIGHTER = 8.0, 0.14, 0.22, 0.15
L_FLOOR, L_CEIL = 0.14, 0.985
GIVE, SHADING, CHROMA_FLOOR, SHADOW_CHROMA = 0.3, 0.65, 0.78, 0.22

# A New Home's cloth painted in the colours of skin, by (sex, body value): (near, also) -- a pixel within
# CLOTH_REACH of a `near` pixel that is also `also` is never skin.  Numbers only, no art.
VV1_CLOTH_RULES = {
    ("male", 0): (lambda h, s, v: s < 0.15 and v >= 0.85, lambda h, s, v: s < 0.40 and h >= 40),      # the white vest
    ("male", 1): (lambda h, s, v: (h <= 12 or h >= 340) and s >= 0.55, lambda h, s, v: h >= 44 and s < 0.50),  # stripes
}
MASK_ALPHA = 32             # a painted mask's pixel this opaque or more, and light, is skin
BABY_CELL = (3, 0)          # the held baby's column and row on carrying.png, every game


# ---- colour ------------------------------------------------------------------------------------------

def hsv(r: int, g: int, b: int):
    """(hue in degrees, saturation, value) of an 8-bit colour."""
    rf, gf, bf = r / 255, g / 255, b / 255
    mx = max(rf, gf, bf)
    d = mx - min(rf, gf, bf)
    if d > 0:
        if mx == rf:
            h = ((gf - bf) / d) % 6
        elif mx == gf:
            h = (bf - rf) / d + 2
        else:
            h = (rf - gf) / d + 4
    else:
        h = 0.0
    return h * 60, (d / mx if mx > 0 else 0.0), mx


_LINEAR = [c / 255 / 12.92 if c / 255 <= 0.04045 else ((c / 255 + 0.055) / 1.055) ** 2.4 for c in range(256)]


def lightness(r: int, g: int, b: int) -> float:
    """OKLab lightness of an 8-bit colour."""
    lr, lg, lb = _LINEAR[r], _LINEAR[g], _LINEAR[b]
    l_ = (0.4122214708 * lr + 0.5363325363 * lg + 0.0514459929 * lb) ** (1 / 3)
    m_ = (0.2119034982 * lr + 0.6806995451 * lg + 0.1073969566 * lb) ** (1 / 3)
    s_ = (0.0883024619 * lr + 0.2817188376 * lg + 0.6299787005 * lb) ** (1 / 3)
    return 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_


def chroma(r: int, g: int, b: int) -> float:
    """OKLCh chroma of an 8-bit colour."""
    lr, lg, lb = _LINEAR[r], _LINEAR[g], _LINEAR[b]
    l_ = (0.4122214708 * lr + 0.5363325363 * lg + 0.0514459929 * lb) ** (1 / 3)
    m_ = (0.2119034982 * lr + 0.6806995451 * lg + 0.1073969566 * lb) ** (1 / 3)
    s_ = (0.0883024619 * lr + 0.2817188376 * lg + 0.6299787005 * lb) ** (1 / 3)
    return math.hypot(1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
                      0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_)


def _linear_rgb(L: float, c: float, cos_h: float, sin_h: float):
    a, b = c * cos_h, c * sin_h
    l_ = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    return (4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
            -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
            -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_)


def _fits(L: float, c: float, cos_h: float, sin_h: float) -> bool:
    return all(-1e-4 <= v <= 1 + 1e-4 for v in _linear_rgb(L, c, cos_h, sin_h))


def oklch_to_rgb(L: float, c: float, hue: float, floor: float, toward: float):
    """The 8-bit sRGB colour of an OKLCh colour.  Outside sRGB it keeps its hue always; it gives up chroma
    first, never below `floor`, and where even that does not fit its lightness moves toward `toward`."""
    cos_h, sin_h = math.cos(math.radians(hue)), math.sin(math.radians(hue))
    floor = min(floor, c)
    if not _fits(L, floor, cos_h, sin_h):
        lo, hi = L, toward
        for _ in range(14):
            mid = (lo + hi) / 2
            if _fits(mid, floor, cos_h, sin_h):
                hi = mid
            else:
                lo = mid
        L = hi
    if not _fits(L, c, cos_h, sin_h):
        lo, hi = floor, c
        for _ in range(14):
            mid = (lo + hi) / 2
            if _fits(L, mid, cos_h, sin_h):
                lo = mid
            else:
                hi = mid
        c = lo
    out = []
    for v in _linear_rgb(L, c, cos_h, sin_h):
        v = min(max(v, 0.0), 1.0)
        v = v * 12.92 if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055
        out.append(int(round(v * 255)))         # round half to even, as the development tool rounds
    return tuple(out)


# ---- the skin mask -----------------------------------------------------------------------------------

def _in_box(h, s, v, box, cap=None):
    return box[0] <= h <= box[1] and box[2] <= s <= (box[3] if cap is None else cap) and v >= box[4]


def _seed(px, hsv_of, cap, floor):
    r, g, b, a = px
    if a == 0 or not (r >= g >= b):
        return False
    h, s, v = hsv_of
    return ((_in_box(h, s, v, CORE, cap) or _in_box(h, s, v, HIGHLIGHT)) and s >= floor) or _in_box(h, s, v, SHADOW)


def _median(values):
    values = sorted(values)
    n = len(values)
    return values[n // 2] if n % 2 else (values[n // 2 - 1] + values[n // 2]) / 2


def _neighbours(i, w, h):
    """The up to eight pixels round pixel number i."""
    x, y = i % w, i // w
    for dy in (-1, 0, 1):
        yy = y + dy
        if 0 <= yy < h:
            for dx in (-1, 0, 1):
                xx = x + dx
                if (dx or dy) and 0 <= xx < w:
                    yield yy * w + xx


def _dilate(pixels: set, w, h, steps=1, within=None):
    """`pixels` grown `steps` times by one pixel in the eight directions (`within`: only these rows)."""
    out = set(pixels)
    edge = pixels
    for _ in range(steps):
        new = set()
        for i in edge:
            for j in _neighbours(i, w, h):
                if j not in out and (within is None or within[0] <= j // w < within[1]):
                    new.add(j)
        out |= new
        edge = new
    return out


def _blobs(pixels: set, w, h):
    """The 8-connected groups of `pixels`."""
    left, groups = set(pixels), []
    while left:
        start = left.pop()
        group, stack = [start], [start]
        while stack:
            for j in _neighbours(stack.pop(), w, h):
                if j in left:
                    left.discard(j)
                    group.append(j)
                    stack.append(j)
        groups.append(group)
    return groups


def skin_mask(sheet, heads: bool, cell=(40, 65), front=5, cloth=None, hand=None):
    """The skin pixels of `sheet`, as a set of pixel numbers.  `heads`: a sheet of heads (else bodies).
    `cell`: the cell size.  `front`: a head sheet's front-facing column, whose cheeks give a row's reference
    skin (None: the whole row).  `cloth`: {row: (near, also)} cloth rules.  `hand`: the owner's hand-made
    mask for the sheet, a set of pixel numbers -- on heads it says where skin may be (everything but hair),
    on bodies it adds to the rule (The Lost Children)."""
    w, h, px = sheet
    cw, ch = cell
    opaque = [i for i, p in enumerate(px) if p[3] > 0]
    hsv_of = {i: hsv(*px[i][:3]) for i in opaque}
    rows = h // ch
    m: set[int] = set()
    floor = HIGHLIGHT[2] if heads else BODY_FLOOR
    by_row = [[] for _ in range(rows + 1)]
    for i in opaque:
        by_row[min(i // w // ch, rows)].append(i)
    for row in range(rows):
        if heads and front is not None:
            y0, y1 = row * ch + ch * 15 // 65, row * ch + ch * 22 // 65
            x0, x1 = front * cw + cw * 14 // 40, front * cw + cw * 27 // 40
            ref = [i for i in by_row[row] if y0 <= i // w < y1 and x0 <= i % w < x1]
        else:
            ref = by_row[row]
        sats = [hsv_of[i][1] for i in ref if _seed(px[i], hsv_of[i], CORE[3], CORE[2])]
        cap = min(max(_median(sats) + CAP_MARGIN, CAP_MIN), CAP_MAX) if sats else CORE[3]
        m.update(i for i in by_row[row] if _seed(px[i], hsv_of[i], cap, floor))
    never: set[int] = set()
    for row, (near, also) in (cloth or {}).items():
        if 0 <= row < rows:
            beside = _dilate({i for i in by_row[row] if near(*hsv_of[i])}, w, h, CLOTH_REACH,
                             (row * ch, (row + 1) * ch))
            never.update(i for i in beside if i in hsv_of and also(*hsv_of[i]))
    m -= never
    outside = None
    if not heads:
        outside = _dilate({i for i, p in enumerate(px) if p[3] < 128}, w, h, EDGE_REACH)
    kept: set[int] = set()
    for group in _blobs(m, w, h):
        if len(group) >= MIN_BLOB and (outside is None or any(i in outside for i in group)):
            kept.update(group)
    m = kept

    def warm_order(i):
        r, g, b, _ = px[i]
        return r >= g >= b

    def warm_edge(i):
        hh, s, v = hsv_of[i]
        return warm_order(i) and 18 <= hh <= 50 and s <= 0.80 and v >= 0.60 and (heads or s >= BODY_FLOOR)

    def attaches(i):
        hh, s, v = hsv_of[i]
        r, _, b, _ = px[i]
        sheen = warm_order(i) and r - b >= 12 and 0.04 <= s <= 0.45 and v >= 0.85
        # a blush is pink: a neutral white or grey (an eye's white, teeth) is not one
        blush = (hh >= 340 or hh <= 10) and BLUSH_FLOOR <= s <= 0.45 and v >= 0.60
        return sheen or blush

    m |= {i for i in _dilate(m, w, h) - m if i in hsv_of and i not in never and warm_edge(i)}
    attach = {i for i in opaque if i not in m and i not in never and attaches(i)}
    small: set[int] = set()
    for group in _blobs(attach, w, h):
        if len(group) <= MAX_SHEEN:
            small.update(group)
    for _ in range(GROW):
        m |= {i for i in _dilate(m, w, h) - m if i in small}
    for _ in range(2):
        more = set()
        for i in _dilate(m, w, h) - m:
            if i not in hsv_of or i in never:
                continue
            hh, s, v = hsv_of[i]
            r, _, b, _ = px[i]
            if (hh <= 12 or hh >= 340) and s >= 0.50:           # lips
                continue
            around = sum(1 for j in _neighbours(i, w, h) if j in m)
            warm = warm_order(i) and r - b >= 12 and v >= 0.45 and (hh <= 50 or hh >= 340)
            glint = s >= 0.15 and v >= 0.85 and 20 <= hh <= 75
            if (warm and around >= 5) or (glint and around >= 6):
                more.add(i)
        m |= more
    for _ in range(ALIKE_STEPS):
        more = alike(sheet, m, hsv_of) - never
        if not more:
            break
        m |= more
    if hand is not None:
        if heads:
            lit = {i for i in opaque if hsv_of[i][2] >= 0.45 and 12 <= hsv_of[i][0] <= 78 and hsv_of[i][1] >= 0.08}
            m = (m | lit) & hand
        else:
            m = m | hand
    return {i for i in m if px[i][3] > 0}


def alike(sheet, m: set, hsv_of=None) -> set:
    """The pixels beside the mask `m` that are skin by their neighbours: opaque, warm, and of nearly the
    hue, saturation and value of the mask pixels touching them (at least two)."""
    w, h, px = sheet
    out = set()
    for i in _dilate(m, w, h) - m:
        r, g, b, a = px[i]
        if a == 0 or not (r >= g >= b):
            continue
        hh, s, v = hsv_of[i] if hsv_of is not None else hsv(r, g, b)
        if v < 0.40:
            continue
        near = [j for j in _neighbours(i, w, h) if j in m]
        if len(near) < 2:
            continue
        hm = sm = vm = 0.0
        for j in near:
            jh, js, jv = hsv_of[j] if hsv_of is not None else hsv(*px[j][:3])
            hm += jh
            sm += js
            vm += jv
        hm, sm, vm = hm / len(near), sm / len(near), vm / len(near)
        if abs(hh - hm) <= ALIKE_HUE and abs(s - sm) <= ALIKE_SAT and vm - ALIKE_DARKER <= v <= vm + ALIKE_LIGHTER:
            out.add(i)
    return out


def baby_mask(sheet, cell) -> set:
    """The held baby's skin: the warm, lit pixels of its one cell of the carried-things sheet."""
    w, _, px = sheet
    cw, ch = cell
    out = set()
    for y in range(BABY_CELL[1] * ch, (BABY_CELL[1] + 1) * ch):
        for x in range(BABY_CELL[0] * cw, (BABY_CELL[0] + 1) * cw):
            r, g, b, a = px[y * w + x]
            if a == 255 and r >= g >= b:
                hh, s, v = hsv(r, g, b)
                if 20 <= hh <= 62 and s >= 0.18 and v >= 0.60:
                    out.add(y * w + x)
    return out


# ---- replace -----------------------------------------------------------------------------------------

def _percentile(ordered, q):
    """The q-th percentile of an ordered list, between neighbours in a straight line."""
    at = (len(ordered) - 1) * q / 100
    lo = int(math.floor(at))
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (at - lo)


def tone_scales(L, down, up):
    """How much of the art's shading below and above a row's middle skin a tone of lightness L keeps: 1, or
    less where the floor or the ceiling is in the way -- and then a little more on the other side."""
    s_down = max(min(1.0, (L - L_FLOOR) / max(down, 1e-6)), 0.0)
    s_up = max(min(1.0, (L_CEIL - L) / max(up, 1e-6)), 0.0)
    more_up = min(1 + GIVE * (1 - s_down), (L_CEIL - L) / max(up, 1e-6))
    more_down = min(1 + GIVE * (1 - s_up), (L - L_FLOOR) / max(down, 1e-6))
    return (more_down if s_up < 1 else s_down), (more_up if s_down < 1 else s_up)


def shade(offset, tone, down, up):
    """The 8-bit colour of tone `tone` (a vv_skin_tones.TONE_TABLE row) at lightness `offset` from a row's
    middle skin, the row's skin reaching `down` below and `up` above it."""
    _name, _hex, L, c, hue = tone
    offset, down, up = offset * SHADING, down * SHADING, up * SHADING
    s_down, s_up = tone_scales(L, down, up)
    out_L = min(max(L + (offset * s_down if offset < 0 else offset * s_up), L_FLOOR), L_CEIL)
    depth = min(max(-offset / max(down, 1e-6), 0.0), 1.0)
    return oklch_to_rgb(out_L, c * (1 + SHADOW_CHROMA * depth), hue, CHROMA_FLOOR * c, L)


def recolour(sheet, mask: set, tone, cell_h=65):
    """The sheet's pixels with every skin pixel's colour replaced by the tone; alpha and every other pixel
    exactly as they were.  Returns a new list of (r, g, b, a)."""
    w, h, px = sheet
    out = list(px)
    rows: dict[int, list[int]] = {}
    for i in mask:
        rows.setdefault(i // w // cell_h, []).append(i)
    for members in rows.values():
        light = {}
        for i in members:
            rgb = px[i][:3]
            if rgb not in light:
                light[rgb] = lightness(*rgb)
        ordered = sorted(light[px[i][:3]] for i in members)
        lo, mid, hi = (_percentile(ordered, q) for q in (2, 50, 98))
        made = {rgb: shade(L - mid, tone, mid - lo, hi - mid) for rgb, L in light.items()}
        for i in members:
            out[i] = made[px[i][:3]] + (px[i][3],)
    return out


# ---- a game's sheets ---------------------------------------------------------------------------------

def sheets_of(game: int):
    """Every sheet of `game` (1..5) skin shows on: dicts of name, kind ("heads", "bodies" or "baby"), cell,
    front (a head sheet's front-facing column, or None), sex and first (the body value of its first row)."""
    out = []

    def add(name, kind, cell=(40, 65), front=None, sex=None, first=0):
        out.append({"name": name, "kind": kind, "cell": cell, "front": front, "sex": sex, "first": first})

    thirds = (0, 1) if game == 1 else (0, 1, 2)
    for sex in ("male", "female"):
        if game == 1:
            add(f"{sex}_heads.png", "heads", front=5, sex=sex)
        elif game in (2, 3):
            add(f"{sex}_heads.png", "heads", front=5, sex=sex)
            add(f"{sex}_heads_old.png", "heads", front=5, sex=sex)
        else:
            add(f"{sex}_heads00.png", "heads", front=5, sex=sex)
            add(f"{sex}_heads10.png", "heads", front=5, sex=sex)
        for across in (0, 1):
            for down in thirds:
                add(f"{sex}_bodies{across}{down}.png", "bodies", sex=sex, first=10 * down)
        for down in thirds:
            add(f"{sex}_actions0{down}.png", "bodies", sex=sex, first=10 * down)
    add("carrying.png", "baby", cell=(40, 25 if game in (1, 2) else 40))
    if game in (4, 5):
        add("BigHeads00.png", "heads", cell=(80, 100))
        add("BigHeads10.png", "heads", cell=(80, 100))
        add("BigBodies.png", "bodies", cell=(80, 130))
    return out


def mask_for(game: int, spec: dict, sheet, hand=None) -> set:
    """The skin mask of one of sheets_of(game)'s sheets."""
    if spec["kind"] == "baby":
        return baby_mask(sheet, spec["cell"])
    cloth = None
    if game == 1 and spec["kind"] == "bodies" and spec["sex"]:
        rows = sheet[1] // spec["cell"][1]
        cloth = {body - spec["first"]: rule for (sex, body), rule in VV1_CLOTH_RULES.items()
                 if sex == spec["sex"] and 0 <= body - spec["first"] < rows}
    return skin_mask(sheet, spec["kind"] == "heads", spec["cell"], spec["front"], cloth, hand)


def installed_name(tone: int, name: str) -> str:
    """A tone's sheet as "VVFP Skin Tones.dll" looks for it in a game's Images folder."""
    return f"vvfp_skin_{tone:02d}_{name}"


def tone_sheet(game: int, spec: dict, sheet, tone: int, mask: set | None = None):
    """The pixels of tone `tone`'s (1..TONE_COUNT) copy of a sheet."""
    if mask is None:
        mask = mask_for(game, spec, sheet)
    return recolour(sheet, mask, vv_skin_tones.TONE_TABLE[tone - 1], spec["cell"][1])


# ---- the files -----------------------------------------------------------------------------------------

def _find(folder: Path, name: str):
    wanted = name.lower()
    for path in folder.iterdir():
        if path.name.lower() == wanted:
            return path
    return None


def _edit(edits, stem: str, leaf: str):
    for folder in edits:
        path = Path(folder) / stem / leaf
        if path.is_file():
            return path
    return None


def write_tone_sheets(game: int, images: Path, out: Path, edits=None, tones=None, report=None) -> list[str]:
    """Every tone's copy of every sheet of `game`, made from the pictures in `images` (the player's own
    game) and written to `out` under the names "VVFP Skin Tones.dll" looks for.  `edits`: folders of the
    owner's marking, the first that has a file winning (default: the shipped OWNER_EDITS of the game) -- a
    sheet's skin_NN.png there is where tone NN has skin on it (white where the owner painted that tone's
    colour layer), and its mask.png the skin of every tone that has none of its own.  Only WHERE the skin
    is comes from the owner: the colours and the shading are always made here, from the player's own
    picture.  A sheet the game does not have is skipped.  Nothing in `images` is
    changed (unless `out` is `images`, where only the new names are written).  Returns the names written."""
    from PIL import Image
    images, out = Path(images), Path(out)
    if edits is None:
        edits = [OWNER_EDITS / f"vv{game}"]
    tones = list(tones or range(1, vv_skin_tones.TONE_COUNT + 1))
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for spec in sheets_of(game):
        source = _find(images, spec["name"])
        if source is None:
            continue
        stem = Path(spec["name"]).stem
        with Image.open(source) as opened:
            image = opened.convert("RGBA")
        sheet = (image.width, image.height, list(image.getdata()))
        mask = None
        painted_mask = _edit(edits, stem, "mask.png")
        if painted_mask is not None:
            with Image.open(painted_mask) as opened:
                layer = opened.convert("RGBA")
            if layer.size == image.size:
                mask = {i for i, (r, g, b, a) in enumerate(layer.getdata())
                        if a >= MASK_ALPHA and max(r, g, b) > 127 and sheet[2][i][3] > 0}
        for tone in tones:
            painted = _edit(edits, stem, f"skin_{tone:02d}.png")
            skin = None
            if painted is not None:
                with Image.open(painted) as opened:
                    layer = opened.convert("RGBA")
                if layer.size == image.size:
                    skin = {i for i, (_r, _g, _b, a) in enumerate(layer.getdata())
                            if a > 0 and sheet[2][i][3] > 0}
            if skin is None:
                if mask is None:
                    mask = mask_for(game, spec, sheet)
                skin = mask
            pixels = recolour(sheet, skin, vv_skin_tones.TONE_TABLE[tone - 1], spec["cell"][1])
            made = Image.new("RGBA", image.size)
            made.putdata(pixels)
            name = installed_name(tone, spec["name"])
            made.save(out / name)
            written.append(name)
        if report is not None:
            report(spec["name"])
    return written


# ---- at patch time (vv_fun_patcher._write_skin_tone_sheets) --------------------------------------------------
STAMP = "vvfp-skin-tones.json"      # in Images: what the sheets there were made from, so a second patch is quick
MAKER = 2                           # raised whenever the sheets this file makes change
PREFIX = "vvfp_skin_"               # every file this makes (installed_name); no game has a file named so


def _sha256(path: Path) -> str:
    import hashlib
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _made_from(game: int, images: Path, edits) -> dict:
    """What decides a game's tone sheets: this maker, the player's own sheets, and the owner's shipped marking."""
    sources = {}
    for spec in sheets_of(game):
        source = _find(images, spec["name"])
        if source is not None:
            sources[spec["name"]] = _sha256(source)
    marks = {}
    for folder in edits:
        if Path(folder).is_dir():
            for path in sorted(Path(folder).rglob("*.png")):
                marks[path.relative_to(folder).as_posix()] = _sha256(path)
    return {"maker": MAKER, "game": game, "sheets": sources, "marking": marks}


def install(game: int, images: Path, edits=None) -> list[str]:
    """The tone sheets of `game` in its Images folder, made from the pictures there.  When the sheets already
    there were made from the same pictures by the same maker (the stamp), nothing is done.  Returns the names
    made (none when they were up to date).  The game's own pictures are only read."""
    import json
    images = Path(images)
    if edits is None:
        edits = [OWNER_EDITS / f"vv{game}"]
    made_from = _made_from(game, images, edits)
    stamp = images / STAMP
    if stamp.is_file():
        try:
            was = json.loads(stamp.read_text(encoding="utf-8"))
        except ValueError:
            was = {}
        if ({key: was.get(key) for key in made_from} == made_from
                and all((images / name).is_file() for name in was.get("files", []))):
            return []
    remove(images)
    written = write_tone_sheets(game, images, images, edits=edits)
    stamp.write_text(json.dumps(dict(made_from, files=sorted(written)), indent=1), encoding="utf-8")
    return written


def remove(images: Path) -> list[str]:
    """Take a game's tone sheets out of its Images folder: the files the stamp lists and every file with the
    sheets' own prefix -- names no game has.  Returns the names removed."""
    import json
    images = Path(images)
    stamp = images / STAMP
    names = set()
    if stamp.is_file():
        try:
            names = {str(name) for name in json.loads(stamp.read_text(encoding="utf-8")).get("files", [])}
        except ValueError:
            names = set()
    if images.is_dir():
        names |= {path.name for path in images.iterdir() if path.name.lower().startswith(PREFIX)}
    removed = []
    for name in sorted(names):
        path = images / Path(name).name
        if path.is_file() and path.name.lower().startswith(PREFIX):
            path.unlink()
            removed.append(path.name)
    if stamp.is_file():
        stamp.unlink()
    return removed
