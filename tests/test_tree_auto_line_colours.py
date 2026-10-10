"""Auto-colour family lines (the owner, 2026-10-09: "add a button for auto-coloring family lines in the family
tree maker. (should be distinct from other line colors and not blend into the background)"): lines only,
each family's a colour clearly different from every other's (most where lines cross or run close), at least
3:1 (WCAG non-text contrast) against the background actually under it -- plain, gradient, picture or
transparent -- at the lines' opacity, or else a thin casing under it; the same tree always the same colours; undo, Reset and saving; and the
editor, the PNG and the SVG all drawing the same colours."""
import json
import math
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_family_tree as ft  # noqa: E402
import vv_gdiplus  # noqa: E402
import vv_genealogy_window as gw  # noqa: E402
import vv_line_colours as lc  # noqa: E402
import vv_tree_editor_tools as tools  # noqa: E402
from test_genealogy import village  # noqa: E402

GAME = "Virtual Villagers - A New Home"
# The closest two families' OKLab distance (x100; about 2 is just noticeable) the button must reach on a white
# page, by how many families there are.  Measured 2026-10-10 (any colour, a casing where one blends): 21.8, 10.6
# and 7.6 (the closest crossing or nearby pair 38.6, 17.0 and 12.5).
NEAREST = {10: 19.0, 50: 9.5, 112: 6.5}


# ---- independent checks (not the module's own arithmetic) ------------------------------------------

def _lum(rgb) -> float:
    def lin(v):
        v /= 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _ratio(a, b) -> float:
    la, lb = _lum(a), _lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def _rgb(colour: str) -> tuple:
    return tuple(int(colour[k:k + 2], 16) for k in (1, 3, 5))


def png_rgb(path: Path, width: int, height: int, colours) -> None:
    """An 8-bit RGB PNG whose pixel (x, y) is colours(x, y)."""
    rows = b"".join(b"\0" + b"".join(bytes(colours(x, y)) for x in range(width)) for y in range(height))

    def chunk(kind: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))

    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


def read_png(path: Path) -> tuple[int, int, list]:
    """An 8-bit RGB or RGBA PNG's pixels (rows of (r, g, b, a)), every filter undone."""
    data = path.read_bytes()
    pos, idat = 8, b""
    while pos < len(data):
        n = struct.unpack(">I", data[pos:pos + 4])[0]
        kind, body = data[pos + 4:pos + 8], data[pos + 8:pos + 8 + n]
        if kind == b"IHDR":
            w, h, _depth, colour_type = struct.unpack(">IIBB", body[:10])
        elif kind == b"IDAT":
            idat += body
        pos += 12 + n
    bpp = 4 if colour_type == 6 else 3
    raw = zlib.decompress(idat)
    stride = w * bpp
    prev = bytearray(stride)
    rows = []
    for y in range(h):
        f = raw[y * (stride + 1)]
        line = bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for i in range(stride):
            a = line[i - bpp] if i >= bpp else 0
            b = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            if f == 1:
                line[i] = (line[i] + a) & 255
            elif f == 2:
                line[i] = (line[i] + b) & 255
            elif f == 3:
                line[i] = (line[i] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append([tuple(line[x * bpp:x * bpp + 3]) + ((line[x * bpp + 3],) if bpp == 4 else (255,))
                     for x in range(w)])
        prev = line
    return w, h, rows


def page_colours(backdrop: ft.Backdrop, width: float, height: float):
    """The background as the PNG export draws it, at full size: (x, y) -> the colours seen there (over white
    and black where it is see-through)."""
    if backdrop.colour2 or backdrop.picture is not None:
        w, h, data = vv_gdiplus.backdrop_pixels(backdrop, width, height, 1.0)

        def at(x, y):
            x, y = min(w - 1, max(0, int(x))), min(h - 1, max(0, int(y)))
            k = (y * w + x) * 4
            r, g, b, a = data[k + 2], data[k + 1], data[k], data[k + 3]
            f = a / 255
            return [(r, g, b)] if a == 255 else [tuple(c * f + u * (1 - f) for c in (r, g, b)) for u in (255, 0)]
        return at
    plain = [(255, 255, 255), (0, 0, 0)] if backdrop.colour == ft.TRANSPARENT else [_rgb(backdrop.colour)]
    return lambda x, y: plain


def worst_on_page(sc: ft.Scene, frames=(), casing: bool = False) -> dict[str, float]:
    """Each family's lowest contrast against the background, every 2 pixels along its lines and up to 4
    pixels either side, at the lines' opacity (blended over the background as GDI+ blends it)."""
    backdrop = next(i for i in sc.items if isinstance(i, ft.Backdrop))
    under = page_colours(backdrop, sc.width, sc.height)
    out: dict[str, float] = {}
    for item in sc.items:
        if not (isinstance(item, ft.Line) and item.target and item.target[0] == "family"
                and item.casing == casing):
            continue
        c = _rgb(item.colour)
        a = item.opacity
        for (x0, y0), (x1, y1) in zip(item.points, item.points[1:]):
            n = max(1, int(math.hypot(x1 - x0, y1 - y0) // 2))
            for k in range(n + 1):
                x, y = x0 + (x1 - x0) * k / n, y0 + (y1 - y0) * k / n
                if any(ft.inside(f, x, y) for f in frames):
                    continue
                for dx in (-4, 0, 4):
                    for dy in (-4, 0, 4):
                        for bg in under(x + dx, y + dy):
                            shown = tuple(a * u + (1 - a) * v for u, v in zip(c, bg))
                            r = _ratio(shown, bg)
                            if r < out.get(item.target[1], math.inf):
                                out[item.target[1]] = r
    return out


def oklab_distance(c1: str, c2: str) -> float:
    def lab(rgb):
        def lin(v):
            v /= 255
            return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
        r, g, b = (lin(v) for v in rgb)
        l_, m_, s_ = ((0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3),
                      (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3),
                      (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3))
        return (0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
                1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
                0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_)
    return 100 * math.dist(lab(_rgb(c1)), lab(_rgb(c2)))


# ---- trees -----------------------------------------------------------------------------------------

def many_families(n: int, backdrop: ft.Backdrop | None = None, opacity: float = 1.0, width: float = 3.0):
    """A page of n families' lines, ten across, each crossing its neighbours' (a couple's line, a stem
    down and a children's line, as the tree draws them); [(layout, scene)]."""
    rows = (n + 9) // 10
    w, h = 1700.0, 140.0 * rows + 160
    sc = ft.Scene(w, h, (backdrop or ft.Backdrop("#ffffff")).colour, [backdrop or ft.Backdrop("#ffffff")])
    for k in range(n):
        x0, y0 = 60 + (k % 10) * 155, 80 + (k // 10) * 140
        key = f"family {k:03d}"
        sc.items.append(ft.Line([(x0, y0), (x0 + 210, y0)], "#000000", width, target=("family", key),
                                piece=f"{key}|couple", opacity=opacity))
        sc.items.append(ft.Line([(x0 + 105, y0), (x0 + 105, y0 + 60), (x0 + 300, y0 + 60), (x0 + 300, y0 + 100)],
                                "#000000", width, target=("family", key), piece=f"{key}|kids", opacity=opacity))
    return [(SimpleNamespace(edits=ft.Edits(), x={}), sc)]


def recoloured(pages, colours: dict[str, str]):
    for _lay, sc in pages:
        for item in sc.items:
            if isinstance(item, ft.Line) and item.target and item.target[1] in colours:
                item.colour = colours[item.target[1]]
    return pages


def coloured(pages, colours: dict[str, str]):
    """The pages with the families' lines in these colours (saved as their own) and the casings the scene
    puts under them."""
    for lay, sc in pages:
        lc.apply(lay.edits, colours)
        for item in sc.items:
            if isinstance(item, ft.Line) and item.target and item.target[1] in colours:
                item.colour = colours[item.target[1]]
        cased = lc.casings(lay, sc)
        sc.items[1:1] = cased
    return pages


@unittest.skipUnless(vv_gdiplus.available(), "the background is drawn with GDI+ (Windows)")
class ContrastTests(unittest.TestCase):
    """Never blending into the background: a family's colour that would fall below 3:1 against the worst
    point under its lines gets a thin casing, dark or white, whichever stands out more there."""

    def backgrounds(self, folder: Path) -> dict[str, ft.Backdrop]:
        stripes = folder / "stripes.png"
        png_rgb(stripes, 64, 48, lambda x, y: (255, 224, 138) if (x // 8) % 2 else (168, 216, 255))
        dusk = folder / "dusk.png"
        png_rgb(dusk, 64, 48, lambda x, y: (20 + x, 24, 60 + y))
        return {
            "white": ft.Backdrop("#ffffff"),
            "dark": ft.Backdrop("#1b1b3a"),
            "mid grey": ft.Backdrop("#7f7f7f"),
            "light gradient": ft.Backdrop("#ffffff", "#a0c4ff"),
            "dark gradient": ft.Backdrop("#000000", "#303060"),
            "rainbow": ft.Backdrop("#ffffff", "rainbow-across"),
            "striped picture, stretched": ft.Backdrop("#ffffff", "", stripes, "stretch", 0),
            "striped picture, tiled, 45% opacity": ft.Backdrop("#203040", "", stripes, "tile", 55),
            "dark picture, fitted": ft.Backdrop("#ffffff", "", dusk, "fit", 0),
            "transparent": ft.Backdrop(ft.TRANSPARENT),
            "picture on transparent, 50%": ft.Backdrop(ft.TRANSPARENT, "", stripes, "cover", 50),
        }

    # Backgrounds where a line may lie over both a dark and a light part (the vivid rainbow's blue and cyan, a
    # dark picture fitted between white bars, a half see-through picture over white or black): there neither
    # a dark nor a white casing stands out 3:1 everywhere, only the better of the two.
    MIXED = {"rainbow", "dark picture, fitted", "picture on transparent, 50%", "transparent"}

    def test_every_family_stands_out_or_is_cased_on_every_background(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name, backdrop in self.backgrounds(Path(tmp)).items():
                with self.subTest(background=name):
                    pages = many_families(30, backdrop)
                    res = lc.auto_colours(pages)
                    self.assertEqual(len(res.colours), 30)
                    sc = coloured(pages, res.colours)[0][1]
                    lines = worst_on_page(sc)
                    cases = worst_on_page(sc, casing=True)
                    fams = lc.gather(pages)
                    cased = {i.target[1]: i.colour for i in sc.items if isinstance(i, ft.Line) and i.casing}
                    self.assertEqual(sorted(cased), res.cased)
                    for key, ratio in lines.items():
                        if key not in cased:
                            self.assertGreaterEqual(ratio, lc.FLOOR - 0.05, (name, key))
                            continue
                        self.assertIn(cased[key], lc.CASINGS)
                        other = next(c for c in lc.CASINGS if c != cased[key])
                        self.assertGreaterEqual(lc.worst_contrast(fams[key], cased[key]),
                                                lc.worst_contrast(fams[key], other))    # the better of the two
                        if name not in self.MIXED:
                            self.assertGreaterEqual(cases[key], lc.FLOOR - 0.05, (name, key))

    def test_the_lines_opacity_is_counted(self):
        pages = many_families(20, ft.Backdrop("#ffffff"), opacity=0.6)
        res = lc.auto_colours(pages)
        sc = coloured(pages, res.colours)[0][1]
        lines = worst_on_page(sc)
        cased = {i.target[1] for i in sc.items if isinstance(i, ft.Line) and i.casing}
        self.assertEqual({k for k, r in lines.items() if r < lc.FLOOR - 0.05} - cased, set())
        self.assertTrue(all(i.opacity == 0.6 for i in sc.items if isinstance(i, ft.Line) and i.casing))
        # Too see-through to stand out anywhere: every family cased.
        faint = lc.auto_colours(many_families(5, ft.Backdrop("#ffffff"), opacity=0.25))
        self.assertEqual(len(faint.cased), 5)

    def test_a_transparent_page_is_checked_on_white_and_black(self):
        pages = many_families(12, ft.Backdrop(ft.TRANSPARENT))
        res = lc.auto_colours(pages)
        for key, colour in res.colours.items():
            blends = min(_ratio(_rgb(colour), (255, 255, 255)), _ratio(_rgb(colour), (0, 0, 0))) < lc.FLOOR
            self.assertEqual(key in res.cased, blends, colour)

    def test_behind_a_portrait_does_not_count(self):
        # A line wholly behind a portrait: nothing read; the page's own colour counts.
        pages = many_families(1, ft.Backdrop("#ffffff"))
        lay = pages[0][0]
        lay.x = {1: 0}
        lay.frame_points = lambda q: [(0, 0), (2000, 0), (2000, 2000), (0, 2000)]
        fams = lc.gather(pages)
        self.assertEqual(fams["family 000"].colours, [(255, 255, 255)])


class CasingTests(unittest.TestCase):
    def test_only_where_needed_under_every_line_wider_and_the_same_everywhere(self):
        v = village()
        e = ft.Edits()
        lay = ft.layout(v, e)
        keys = sorted({ft.family_key(v, f) for f in lay.families})
        self.assertGreaterEqual(len(keys), 2)
        e.family_lines[keys[0]] = {"colour": "#fafafa"}         # by hand: white lines on a white page
        e.family_lines[keys[1]] = {"colour": "#202020"}         # and dark ones, which stand out
        # Off unless the player ticks "Outline lines that blend into the background" (the owner, 2026-10-10):
        # nothing drawn, anywhere.
        self.assertFalse(e.outline_lines)
        off = ft.scene(ft.layout(v, e), GAME, {})
        self.assertFalse(any(isinstance(i, ft.Line) and i.casing for i in off.items))
        self.assertNotIn('stroke="#1a1a1a"', ft.to_svg(off, {}))
        e.outline_lines = True
        self.assertTrue(ft.Edits._from_data(json.loads(json.dumps(e.to_data()))).outline_lines)
        self.assertFalse(ft.Edits._from_data({}).outline_lines)
        sc = ft.scene(ft.layout(v, e), GAME, {})
        cases = [i for i in sc.items if isinstance(i, ft.Line) and i.casing]
        lines = [i for i in sc.items if isinstance(i, ft.Line) and i.piece]
        self.assertTrue(cases)
        self.assertEqual({i.target[1] for i in cases}, {keys[0]})
        self.assertEqual({i.colour for i in cases}, {"#1a1a1a"})
        first_line = sc.items.index(lines[0])
        self.assertTrue(all(sc.items.index(c) < first_line for c in cases))   # under every family line
        mine = [i for i in lines if i.target[1] == keys[0]]
        self.assertEqual(sorted((tuple(map(tuple, i.points)), i.width + 2 * lc.CASING) for i in mine),
                         sorted((tuple(map(tuple, c.points)), c.width) for c in cases))
        svg = ft.to_svg(sc, {})
        self.assertIn('stroke="#1a1a1a"', svg)
        # The casings fade with the Family lines opacity, as their lines do.
        e.opacity["lines"] = 40
        faded = [i for i in ft.scene(ft.layout(v, e), GAME, {}).items if isinstance(i, ft.Line) and i.casing]
        self.assertTrue(faded and all(abs(i.opacity - 0.4) < 1e-9 for i in faded))
        # Reset to family colours: no outlines either.
        self.assertTrue(lc.reset(e))
        self.assertFalse(e.outline_lines)
        # Family colours (no colour of their own) are never cased: older trees look as they did.
        plain = ft.scene(ft.layout(v, ft.Edits(outline_lines=True)), GAME, {})
        self.assertFalse(any(isinstance(i, ft.Line) and i.casing for i in plain.items))


class DistinctTests(unittest.TestCase):
    def test_distinct_from_each_other(self):
        for n, least in NEAREST.items():
            with self.subTest(families=n):
                res = lc.auto_colours(many_families(n), render=False)
                self.assertEqual(len(set(res.colours.values())), n)
                found = min(oklab_distance(a, b) for i, a in enumerate(res.colours.values())
                            for b in list(res.colours.values())[i + 1:])
                self.assertAlmostEqual(found, res.nearest, places=3)
                self.assertGreaterEqual(found, least)
                # Lines that cross or run close are further apart than the closest pair overall.
                self.assertGreaterEqual(res.nearest_close, res.nearest)

    def test_crossing_families_are_the_most_different(self):
        pages = many_families(40)
        res = lc.auto_colours(pages, render=False)
        fams = lc.gather(pages, render=False)
        keys = sorted(fams)
        near = lc.closeness([fams[k] for k in keys])
        crossing = [oklab_distance(res.colours[keys[i]], res.colours[keys[j]]) for (i, j), c in near.items() if c > 0.9]
        self.assertTrue(crossing)
        self.assertGreaterEqual(min(crossing), 1.3 * res.nearest)

    def test_the_same_tree_always_gives_the_same_colours(self):
        first = lc.auto_colours(many_families(50), render=False).colours
        lc._CANDIDATES.clear()
        self.assertEqual(lc.auto_colours(many_families(50), render=False).colours, first)


class EditsTests(unittest.TestCase):
    def test_lines_only_portraits_keep_their_family_colours(self):
        v = village()
        e = ft.Edits()
        lay = ft.layout(v, e)
        before = ft.scene(lay, GAME, {})
        res = lc.auto_colours([(lay, before)])
        self.assertTrue(res.colours)
        lc.apply(e, res.colours)
        lay2 = ft.layout(v, e)
        after = ft.scene(lay2, GAME, {})
        self.assertEqual(lay.birth_colour, lay2.birth_colour)
        self.assertEqual([f.colour for f in lay.families], [f.colour for f in lay2.families])
        self.assertEqual(e.family_colours, {})
        shapes = [(i.pid, i.stroke, i.fill) for i in before.items if isinstance(i, ft.Shape) and i.pid is not None]
        self.assertEqual(shapes, [(i.pid, i.stroke, i.fill) for i in after.items
                                  if isinstance(i, ft.Shape) and i.pid is not None])
        for item in after.items:
            if isinstance(item, ft.Line) and item.piece:
                self.assertEqual(item.colour, res.colours[item.target[1]])

    def test_an_own_line_colour_wins_over_the_lines_scheme(self):
        v = village()
        e = ft.Edits(schemes={"lines": "rainbow"})
        lay = ft.layout(v, e)
        key = ft.family_key(v, lay.families[0])
        e.family_lines[key] = {"colour": "#123456"}
        items = ft.scene(ft.layout(v, e), GAME, {}).items
        mine = [i.colour for i in items if isinstance(i, ft.Line) and i.target == ("family", key)]
        self.assertTrue(mine)
        self.assertEqual(set(mine), {"#123456"})

    def test_saved_with_weight_and_type_and_reset_keeps_them(self):
        e = ft.Edits(family_lines={"a": {"width": 5.0, "colour": "#ABCDEF"}, "b": {"colour": "#010203"},
                                   "c": {"colour": "plaid", "dash": "dotted"}})
        back = ft.Edits._from_data(json.loads(json.dumps(e.to_data())))
        self.assertEqual(back.family_lines, {"a": {"width": 5.0, "colour": "#abcdef"}, "b": {"colour": "#010203"},
                                             "c": {"dash": "dotted"}})
        self.assertTrue(lc.reset(back))
        self.assertEqual(back.family_lines, {"a": {"width": 5.0}, "c": {"dash": "dotted"}})
        self.assertFalse(lc.reset(back))
        lc.apply(back, {"a": "#111111", "d": "#222222"})
        self.assertEqual(back.family_lines["a"], {"width": 5.0, "colour": "#111111"})


class _Var:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class _Editor:
    """The window's Auto-colour, Reset and undo, without its widgets."""
    _auto_line_colours = gw.TreeEditor._auto_line_colours
    _reset_line_colours = gw.TreeEditor._reset_line_colours
    _line_colour = gw.TreeEditor._line_colour
    _state = tools.CanvasTools._state
    _record = tools.CanvasTools._record
    _undo = tools.CanvasTools._undo
    _restore = tools.CanvasTools._restore
    obj = None

    def __init__(self):
        self.village = village()
        self.edits = ft.Edits()
        self.lay = ft.layout(self.village, self.edits)
        self.history, self.future = [], []
        self.status = _Var()
        self.last_state = self._state()

    def _page_scene(self, page):
        lay = ft.layout(self.village, self.edits, page)
        return lay, ft.scene(lay, GAME, {})

    def _saved(self):
        self._record()

    def _refresh_panels(self):
        pass

    def redraw(self):
        pass

    def _typing(self):
        return False

    def configure(self, **_kw):
        pass

    def update_idletasks(self):
        pass


class WindowTests(unittest.TestCase):
    def test_undo_reset_and_by_hand(self):
        ed = _Editor()
        key = ft.family_key(ed.village, ed.lay.families[0])
        ed.edits.family_lines[key] = {"width": 6.0}
        ed._saved()
        ed._auto_line_colours()
        coloured = json.loads(json.dumps(ed.edits.family_lines))
        self.assertTrue(all("colour" in s for s in coloured.values()))
        self.assertEqual(coloured[key]["width"], 6.0)
        self.assertIn("Ctrl+Z", ed.status.get())
        ed._undo()                                          # Ctrl+Z: the colours as they were
        self.assertEqual(ed.edits.family_lines, {key: {"width": 6.0}})
        ed._auto_line_colours()
        self.assertEqual(ed.edits.family_lines, coloured)   # the same tree, the same colours
        ed._line_colour(key, "#ff00ff")                     # one family by hand, as before
        self.assertEqual(ed.edits.family_lines[key], {"width": 6.0, "colour": "#ff00ff"})
        ed._reset_line_colours()                            # Reset: the family colours again
        self.assertEqual(ed.edits.family_lines, {key: {"width": 6.0}})
        ed._undo()
        self.assertEqual(ed.edits.family_lines[key]["colour"], "#ff00ff")


@unittest.skipUnless(vv_gdiplus.available(), "the PNG is drawn with GDI+ (Windows)")
class ExportTests(unittest.TestCase):
    def test_png_and_svg_draw_the_editors_colours(self):
        v = village()
        e = ft.Edits(background="#f4efe0")
        lay = ft.layout(v, e)
        lc.apply(e, lc.auto_colours([(lay, ft.scene(lay, GAME, {}))]).colours)
        sc = ft.scene(ft.layout(v, e), GAME, {})
        lines = [i for i in sc.items if isinstance(i, ft.Line) and i.piece]
        svg = ft.to_svg(sc, {})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tree.png"
            self.assertTrue(vv_gdiplus.save_scene(sc, {}, path))
            w, h, rows = read_png(path)
            checked, wrong = 0, []
            for item in lines:
                self.assertIn(f'stroke="{item.colour}"', svg)
                # The editor's canvas draws item.colour (faded by the opacity, here none).
                self.assertEqual(gw.faded(item.colour, item.opacity, sc.background).lower(), item.colour.lower())
                for (x0, y0), (x1, y1) in zip(item.points, item.points[1:]):
                    if abs(x1 - x0) > 12 and y0 == y1:      # the middle of a long flat piece
                        x, y = int((x0 + x1) / 2), int(y0)
                        if not any(ft.inside(lay.frame_points(q), x, y) for q in lay.x):
                            got = rows[y][x][:3]
                            if max(abs(a - b) for a, b in zip(got, _rgb(item.colour))) > 3:
                                wrong.append((item.target[1], (x, y), got, item.colour))
                            checked += 1
            # (Where another family's line crosses on top, that one shows: a few at most.)
            self.assertGreater(checked, 5)
            self.assertLessEqual(len(wrong), checked // 10, wrong)


if __name__ == "__main__":
    unittest.main()
