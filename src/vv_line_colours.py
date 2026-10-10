"""Auto-colour family lines (the owner, 2026-10-09: "add a button for auto-coloring family lines in the
family tree maker. (should be distinct from other line colors and not blend into the background)").

Lines only: each family's lines get a colour of their own (Edits.family_lines[key]["colour"]); the family's
own colour, which its children's portraits share, is left as it was.

How the colours are chosen, the same tree always giving the same colours (nothing here is random):

* The candidates are a fixed grid of colours spread evenly in OKLab, the perceptual colour space (equal
  steps look equally different), every one inside sRGB.
* Never blending into the background: the background is drawn exactly as the PNG export draws it
  (vv_gdiplus.backdrop_pixels: the colour, the gradient, the picture with its fit and opacity) and read
  under and beside every few pixels of each family's lines.  A family may only have a colour whose WCAG
  non-text contrast (at least 3:1, WCAG 2.1 SC 1.4.11) holds against the worst of those points, the line
  drawn at its opacity (Opacity > Family lines) over each.  A transparent background is checked against
  both white (as the editor and the PNG show it) and black (an SVG on a dark page).  A point hidden behind a
  portrait (Lines behind portraits, or a line that meets a frame) does not count.
* Distinct from each other: the colours are chosen to make the closest pair of families as different
  (OKLab distance) as can be, families whose lines cross or run close together counting as closer than
  they are (their distance divided by 1 + how near their lines come, 0-1), so they end up the most
  different.  A greedy start and then rounds in which each family in turn takes the colour furthest from
  every other's; a round never makes the closest pair closer, and it stops when nothing changes.
* Among colours nearly as distinct as the best, the one with the stronger contrast.

Nothing but the standard library (the patcher's promise); GDI+ through vv_gdiplus on Windows.
"""
from __future__ import annotations

import bisect
import math
from dataclasses import dataclass, field
from itertools import repeat
from operator import mul

import vv_family_tree as ft
import vv_gdiplus

FLOOR = 3.0             # WCAG 2.1 non-text contrast: every line at least this against the background
SPACING = 6.0           # pixels between the points read along a line
NEAR = 160.0            # lines nearer than this (pixels) count as running close together
NEAR_SPACING = 12.0     # pixels between the points compared for nearness
TIE = 1.0               # OKLab distance (x100) within which two colours are as distinct: the stronger contrast wins
MAX_PIXELS = 4_000_000  # the background is read at a scale that keeps it to about this many pixels
ROUNDS = 40
WHITE, BLACK = (255, 255, 255), (0, 0, 0)


# ---- colour arithmetic ---------------------------------------------------------------------------

def _rgb(colour: str) -> tuple[int, int, int]:
    h = colour.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _hex(rgb) -> str:
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(round(v)))) for v in rgb)


def _linear(v: float) -> float:
    v /= 255.0
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


_LIN = [_linear(v) for v in range(256)]


def luminance(rgb) -> float:
    """WCAG relative luminance of an sRGB colour (0-255 channels, whole or not)."""
    r, g, b = (_LIN[int(v)] if float(v).is_integer() else _linear(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(l1: float, l2: float) -> float:
    """WCAG contrast ratio of two relative luminances."""
    hi, lo = (l1, l2) if l1 >= l2 else (l2, l1)
    return (hi + 0.05) / (lo + 0.05)


def oklab(rgb) -> tuple[float, float, float]:
    r, g, b = (_linear(v) for v in rgb)
    l_ = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m_ = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s_ = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    return (0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
            1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
            0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_)


def distance(c1: str, c2: str) -> float:
    """How different two colours look: OKLab distance, times 100 (about 2 is just noticeable)."""
    a, b = oklab(_rgb(c1)), oklab(_rgb(c2))
    return 100 * math.dist(a, b)


def _from_oklch(L: float, C: float, h: float):
    """An OKLCh colour as sRGB 0-255, or None outside sRGB."""
    a, b = C * math.cos(math.radians(h)), C * math.sin(math.radians(h))
    l_ = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    lin = (4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
           -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
           -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_)
    if any(v < -1e-4 or v > 1 + 1e-4 for v in lin):
        return None
    out = []
    for v in lin:
        v = min(1.0, max(0.0, v))
        out.append(255 * (12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055))
    return out


_CANDIDATES: list[str] = []


def candidates() -> list[str]:
    """Every colour the button may give a family's lines, in a fixed order: an even grid in OKLCh
    (lightness 0.14-0.98 in steps of 0.04, colour strength 0.03-0.30 in steps of 0.03, every 10 degrees of
    hue) inside sRGB, and the greys."""
    if not _CANDIDATES:
        seen = set()
        for k in range(22):
            L = 0.14 + k * 0.04
            grid = [(L, 0.0, 0.0)] + [(L, 0.03 * c, h) for c in range(1, 11) for h in range(0, 360, 10)]
            for L_, C, h in grid:
                rgb = _from_oklch(L_, C, h)
                if rgb is not None:
                    colour = _hex(rgb)
                    if colour not in seen:
                        seen.add(colour)
                        _CANDIDATES.append(colour)
        for grey in ("#000000", "#ffffff"):
            if grey not in seen:
                _CANDIDATES.append(grey)
    return _CANDIDATES


# ---- the background ------------------------------------------------------------------------------

class Background:
    """The page's background as drawn (ft.Backdrop): the colours a line at (x, y) is seen against."""

    def __init__(self, backdrop: "ft.Backdrop", width: float, height: float, render: bool = True) -> None:
        self.b = backdrop
        self.width, self.height = max(1.0, float(width)), max(1.0, float(height))
        self.transparent = backdrop.colour == ft.TRANSPARENT
        self.pixels = None
        self.scale = 1.0
        self.plain = not backdrop.colour2 and backdrop.picture is None
        if not self.plain and render:
            self.scale = min(1.0, math.sqrt(MAX_PIXELS / (self.width * self.height)))
            try:
                self.pixels = vv_gdiplus.backdrop_pixels(backdrop, self.width, self.height, self.scale)
            except OSError:
                self.pixels = None

    def _opaque(self, rgba) -> list[tuple]:
        """A pixel as seen: itself, or (partly see-through) over white and over black."""
        r, g, b, a = rgba
        if a >= 255:
            return [(r, g, b)]
        f = a / 255.0
        return [tuple(c * f + w * (1 - f) for c in (r, g, b)) for w in (255, 0)]

    def _gradient(self, x: float, y: float) -> tuple:
        stops = ft.gradient_stops(self.b)
        t = x / self.width if ft.RAINBOWS.get(self.b.colour2) == "across" else y / self.height
        t = min(1.0, max(0.0, t))
        for (c0, a0), (c1, a1) in zip(stops, stops[1:]):
            if t <= a1 or (c1, a1) == stops[-1]:
                f = 0.0 if a1 <= a0 else (t - a0) / (a1 - a0)
                p, q = (WHITE if c == ft.TRANSPARENT else _rgb(c) for c in (c0, c1))
                return tuple(u + (v - u) * min(1.0, max(0.0, f)) for u, v in zip(p, q))
        return WHITE

    def under(self, x: float, y: float, reach: float) -> list[tuple]:
        """The colours at (x, y) and up to `reach` pixels round it."""
        if self.pixels is not None:
            w, h, data = self.pixels
            s = self.scale
            r = max(1, int(round(reach * s)))
            step = max(1, r // 2)
            cx, cy = int(x * s), int(y * s)
            out = []
            for py in range(max(0, cy - r), min(h - 1, cy + r) + 1, step):
                row = py * w * 4
                for px in range(max(0, cx - r), min(w - 1, cx + r) + 1, step):
                    k = row + px * 4
                    out.extend(self._opaque((data[k + 2], data[k + 1], data[k], data[k + 3])))
            if out:
                return out
        if self.plain or self.b.picture is not None and not self.b.colour2:
            return [WHITE, BLACK] if self.transparent else [_rgb(self.b.colour)]
        return [self._gradient(px, py) for px, py in ((x, y), (x - reach, y - reach), (x + reach, y + reach))]


# ---- the lines -----------------------------------------------------------------------------------

def _walk(points: list, spacing: float) -> list[tuple[float, float]]:
    """Points every `spacing` pixels along a polyline, its corners among them."""
    out = [tuple(points[0])]
    for (ax, ay), (bx, by) in zip(points, points[1:]):
        n = max(1, int(math.hypot(bx - ax, by - ay) // spacing))
        out.extend((ax + (bx - ax) * k / n, ay + (by - ay) * k / n) for k in range(1, n + 1))
    return out


@dataclass
class _Family:
    key: str
    width: float = 0.0
    opacity: float = 1.0
    lums: list = field(default_factory=list)        # the background's luminances under it, sorted
    colours: list = field(default_factory=list)     # and its colours (for a see-through line)
    near: list = field(default_factory=list)        # (page, x, y): the points compared for nearness


def _portraits(lay) -> list:
    """The portraits that hide a line behind them: (left, top, right, bottom, corners)."""
    if ft.see_through(lay.edits, "portraits") < 1 or lay.edits.portrait_fill == ft.TRANSPARENT:
        return []
    out = []
    for q in lay.x:
        corners = lay.frame_points(q)
        xs, ys = zip(*corners)
        out.append((min(xs), min(ys), max(xs), max(ys), corners))
    return out


def _hidden(frames: list, x: float, y: float) -> bool:
    return any(x0 <= x <= x1 and y0 <= y <= y1 and ft.inside(c, x, y) for x0, y0, x1, y1, c in frames)


def gather(pages: list, render: bool = True) -> dict[str, _Family]:
    """Every family with lines on the tree's pages ([(Layout, Scene)]), with the background under them."""
    fams: dict[str, _Family] = {}
    for page, (lay, sc) in enumerate(pages):
        backdrop = next((i for i in sc.items if isinstance(i, ft.Backdrop)), None) or ft.Backdrop(sc.background)
        bg = Background(backdrop, sc.width, sc.height, render)
        frames = _portraits(lay)
        for item in sc.items:
            if not isinstance(item, ft.Line) or not item.target or item.target[0] != "family" or len(item.points) < 2:
                continue
            fam = fams.setdefault(item.target[1], _Family(item.target[1], item.width, item.opacity))
            fam.width = max(fam.width, item.width)
            fam.opacity = min(fam.opacity, item.opacity)
            reach = item.width / 2 + 2
            for x, y in _walk(item.points, SPACING):
                if not _hidden(frames, x, y):
                    fam.colours.extend(bg.under(x, y, reach))
            fam.near.extend((page, x, y) for x, y in _walk(item.points, NEAR_SPACING))
    page_colour = pages[0][1].background if pages else ft.TRANSPARENT
    for fam in fams.values():
        if not fam.colours:             # every bit of it behind portraits: against the page's own colour
            fam.colours = [_rgb(page_colour)] if ft._colour_ok(page_colour) else [WHITE, BLACK]
        fam.colours = sorted({tuple(int(round(v)) for v in c) for c in fam.colours})
        fam.lums = sorted({luminance(c) for c in fam.colours})
    return fams


def worst_contrast(fam: _Family, colour: str, colours: list | None = None) -> float:
    """The family's lines in `colour` against the background under them: the lowest contrast anywhere."""
    rgb = _rgb(colour)
    if fam.opacity >= 1:
        lc = luminance(rgb)
        i = bisect.bisect_left(fam.lums, lc)
        near = fam.lums[max(0, i - 1):i + 1] or fam.lums[-1:]
        return min(contrast(lc, lb) for lb in near)
    a = max(0.0, fam.opacity)
    worst = math.inf
    for bg in fam.colours if colours is None else colours:
        shown = tuple(a * c + (1 - a) * b for c, b in zip(rgb, bg))
        worst = min(worst, contrast(luminance(shown), luminance(bg)))
    return worst


def _some(colours: list, n: int = 40) -> list:
    """Up to n of the colours, from darkest to lightest (a see-through line is first tried on these)."""
    if len(colours) <= n:
        return colours
    order = sorted(colours, key=luminance)
    return [order[round(k * (len(order) - 1) / (n - 1))] for k in range(n)]


def closeness(fams: list[_Family]) -> dict[tuple[int, int], float]:
    """How near each two families' lines come, 0 (NEAR pixels apart or more, or on other pages) to 1
    (they cross or touch)."""
    cells: dict[tuple, list] = {}
    for i, fam in enumerate(fams):
        for page, x, y in fam.near:
            cells.setdefault((page, int(x // NEAR), int(y // NEAR)), []).append((x, y, i))
    best: dict[tuple[int, int], float] = {}
    for (page, cx, cy), here in cells.items():
        around = [p for dx in (-1, 0, 1) for dy in (-1, 0, 1) for p in cells.get((page, cx + dx, cy + dy), ())]
        for x, y, i in here:
            for u, v, j in around:
                if j > i:
                    d = math.hypot(x - u, y - v)
                    if d < NEAR:
                        near = 1 - d / NEAR
                        if near > best.get((i, j), 0.0):
                            best[(i, j)] = near
    return best


# ---- choosing ------------------------------------------------------------------------------------

@dataclass
class Result:
    colours: dict[str, str]                 # family key -> its lines' colour
    contrast: dict[str, float]              # family key -> its worst contrast against the background
    nearest: float                          # the two most alike families' OKLab distance (x100)
    nearest_close: float                    # the same for families whose lines come within NEAR / 2
    short: list[str]                        # families that could not reach FLOOR (a see-through line)


def choose(fams: dict[str, _Family]) -> Result:
    keys = sorted(fams)
    if not keys:
        return Result({}, {}, math.inf, math.inf, [])
    group = [fams[k] for k in keys]
    n = len(group)
    pool = candidates()
    labs = [oklab(_rgb(c)) for c in pool]
    # Each family's allowed colours (their index in pool) and how strongly they stand out.
    allowed: list[list[int]] = []
    strength: list[dict[int, float]] = []
    short = []
    for fam in group:
        few = _some(fam.colours) if fam.opacity < 1 else None
        scores = {i: worst_contrast(fam, c, few) for i, c in enumerate(pool)}
        if few is not None:              # the ones that pass on the few, checked on every colour
            scores = {i: (worst_contrast(fam, pool[i]) if s >= FLOOR else s) for i, s in scores.items()}
        ok = [i for i, s in scores.items() if s >= FLOOR]
        if not ok:                       # nothing can (a line almost see-through): the strongest there are
            top = max(scores.values())
            ok = [i for i, s in scores.items() if s >= top * 0.95]
            short.append(fam.key)
        allowed.append(ok)
        strength.append(scores)
    used = sorted({i for ok in allowed for i in ok})
    where = {c: k for k, c in enumerate(used)}
    used_labs = [labs[i] for i in used]

    class _Columns(dict):
        """The candidates' distances (x100) to one of them, worked out when first asked for."""
        def __missing__(self, p: int) -> list:
            here = used_labs[p]
            column = self[p] = [100 * math.dist(here, lab) for lab in used_labs]
            return column

    dist = _Columns()
    near = closeness(group)
    factor = [[1.0] * n for _ in range(n)]
    for (i, j), c in near.items():
        factor[i][j] = factor[j][i] = 1 / (1 + c)
    # Each family's choices as rows of `dist` (indexes into `used`).
    choices = [[where[i] for i in ok] for ok in allowed]

    def spread(f: int, others: list[int]) -> list[float]:
        """For each of f's choices: its weighted distance to the nearest of `others`' colours."""
        best = [math.inf] * len(choices[f])
        for g in others:
            here = dist[pick[g]]
            column = [here[c] for c in choices[f]]
            best = list(map(min, best, map(mul, column, repeat(factor[f][g]))))
        return best

    def take(f: int, others: list[int]) -> int:
        values = spread(f, others)
        top = max(values)
        # As distinct as the best (within TIE), then the strongest contrast, then the first in the grid.
        return max((k for k, v in enumerate(values) if v >= top - TIE),
                   key=lambda k: (strength[f][used[choices[f][k]]], -k))

    # The most constrained families (fewest colours, then most neighbours) first.
    crowd = [sum(1 - factor[f][g] for g in range(n) if g != f) for f in range(n)]
    order = sorted(range(n), key=lambda f: (len(choices[f]), -crowd[f], keys[f]))
    pick: dict[int, int] = {}
    done: list[int] = []
    for f in order:
        pick[f] = choices[f][take(f, done)] if done else choices[f][max(
            range(len(choices[f])), key=lambda k: (strength[f][used[choices[f][k]]], -k))]
        done.append(f)

    def own(f: int) -> float:
        return min((dist[pick[f]][pick[g]] * factor[f][g] for g in range(n) if g != f), default=math.inf)

    for _round in range(ROUNDS):
        changed = False
        for f in order:
            others = [g for g in range(n) if g != f]
            if not others:
                break
            values = spread(f, others)
            k = max(range(len(values)), key=lambda k: (values[k], -k))
            if values[k] > own(f) + 1e-6:
                pick[f] = choices[f][k]
                changed = True
        if not changed:
            break
    colours = {keys[f]: pool[used[pick[f]]] for f in range(n)}
    pairs = [(dist[pick[f]][pick[g]], f, g) for f in range(n) for g in range(f + 1, n)]
    return Result(colours, {keys[f]: strength[f][used[pick[f]]] for f in range(n)},
                  min((d for d, _f, _g in pairs), default=math.inf),
                  min((d for d, f, g in pairs if near.get((f, g), 0.0) >= 0.5), default=math.inf), short)


def auto_colours(pages: list, render: bool = True) -> Result:
    """The colours for every family's lines on the tree's pages ([(Layout, Scene)], as drawn)."""
    return choose(gather(pages, render))


def apply(edits: "ft.Edits", colours: dict[str, str]) -> None:
    """The families' lines in these colours (Edits.family_lines), their weight and type kept."""
    for key, colour in colours.items():
        edits.family_lines[key] = {**edits.family_lines.get(key, {}), "colour": colour}


def reset(edits: "ft.Edits") -> bool:
    """Every family's lines back in the family's own colour; whether any changed."""
    changed = False
    for key in list(edits.family_lines):
        style = edits.family_lines[key]
        if "colour" in style:
            changed = True
            rest = {k: v for k, v in style.items() if k != "colour"}
            if rest:
                edits.family_lines[key] = rest
            else:
                del edits.family_lines[key]
    return changed
