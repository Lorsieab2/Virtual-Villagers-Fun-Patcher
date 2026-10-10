"""A settable canvas size (the owner, 2026-10-09): Automatic (the page fits the tree) by default; else a
width x height typed or a ready-made size, on every page.  A tree larger than the canvas shrinks evenly to
fit, centred; a smaller one is centred at its own size; the background fills the canvas; the pictures and
text boxes the player placed keep their places and sizes; PNG and SVG are the canvas's size."""
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_family_tree as ft  # noqa: E402
from test_tree_packed import big_village  # noqa: E402

GAME = "Virtual Villagers - A New Home"


def page(edits: ft.Edits, n: int = 0) -> ft.Scene:
    v = big_village()
    ft.arrange(v, edits)
    return ft.scene(ft.layout(v, edits, n), GAME, {})


def outside(sc: ft.Scene) -> list:
    """Everything drawn (not the player's stickers) any part of which lies off the canvas."""
    out = []
    for item in sc.items:
        box = ft._extent(item)
        if box and not isinstance(item, ft.Sticker) and (box[0] < -0.01 or box[1] < -0.01
                                                         or box[2] > sc.width + 0.01 or box[3] > sc.height + 0.01):
            out.append((type(item).__name__, box))
    return out


def drawn(sc: ft.Scene, page_box: tuple) -> tuple:
    """The box round the tree's own page (where it lies on the canvas) and everything drawn."""
    boxes = [ft._extent(i) for i in sc.items if not isinstance(i, ft.Sticker) and ft._extent(i)] + [page_box]
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


class CanvasSizeTests(unittest.TestCase):
    def test_automatic_is_unchanged(self):
        auto = page(ft.Edits())
        self.assertEqual(auto.fit, (1.0, 0.0, 0.0))
        lay = ft.layout(big_village(), ft.Edits())
        self.assertGreaterEqual(auto.width, lay.width)
        self.assertEqual((ft.Edits().canvas_w, ft.Edits().canvas_h), (0, 0))

    def test_a_larger_canvas_centres_the_tree_at_its_own_size(self):
        auto = page(ft.Edits())
        sc = page(ft.Edits(canvas_w=int(auto.width) + 1000, canvas_h=int(auto.height) + 600))
        self.assertEqual((sc.width, sc.height), (int(auto.width) + 1000, int(auto.height) + 600))
        s, ox, oy = sc.fit
        self.assertEqual(s, 1.0)
        left, top, right, bottom = drawn(sc, (ox, oy, ox + auto.width, oy + auto.height))
        self.assertAlmostEqual(left, sc.width - right)          # centred both ways
        self.assertAlmostEqual(top, sc.height - bottom)
        for q, (x, y, w, h) in auto.boxes.items():      # every portrait moved, not resized
            self.assertEqual(sc.boxes[q], (x + ox, y + oy, w, h))
        self.assertEqual(outside(sc), [])

    def test_a_smaller_canvas_shrinks_everything_evenly_and_nothing_goes_off_it(self):
        auto = page(ft.Edits())
        for w, h in [(800, 600), (600, 1400), *ft.CANVAS_SIZES.values()]:
            sc = page(ft.Edits(canvas_w=w, canvas_h=h))
            self.assertEqual((sc.width, sc.height), (w, h))
            s, ox, oy = sc.fit
            self.assertLessEqual(s, min(1.0, w / auto.width, h / auto.height) + 1e-9)
            left, top, right, bottom = drawn(sc, (ox, oy, ox + auto.width * s, oy + auto.height * s))
            self.assertAlmostEqual(left, w - right, places=6)          # centred both ways ...
            self.assertAlmostEqual(top, h - bottom, places=6)
            if s < 1.0:                                                 # ... as large as fits
                self.assertTrue(min(left, top) < 1e-6, (w, h, left, top))
            self.assertEqual(outside(sc), [], (w, h))
            title = next(i for i in sc.items if isinstance(i, ft.Text) and i.role == "title")
            self.assertAlmostEqual(title.size, 30 * s)
            q, (bx, by, bw, bh) = next(iter(auto.boxes.items()))
            self.assertEqual(tuple(round(v, 6) for v in sc.boxes[q]),
                             tuple(round(v, 6) for v in (bx * s + ox, by * s + oy, bw * s, bh * s)))
            back = ft.to_tree(sc, *ft.to_page(sc, 123.0, 45.0))
            self.assertAlmostEqual(back[0], 123.0)
            self.assertAlmostEqual(back[1], 45.0)

    def test_the_background_fills_the_canvas_and_stickers_keep_their_place(self):
        sticker = ft.new_text_box(300, 200, "Hello")
        sc = page(ft.Edits(canvas_w=900, canvas_h=700, background2="#000000", stickers=[sticker]))
        self.assertIsInstance(sc.items[0], ft.Backdrop)
        st = sc.stickers[0]
        self.assertEqual((st.cx, st.cy, st.w, st.h), (300, 200, sticker["w"], sticker["h"]))
        svg = ft.to_svg(sc, {})
        self.assertIn('<rect width="100%" height="100%"', svg)
        self.assertRegex(svg, r'^<svg [^>]*width="900" height="700"')

    def test_every_page_has_the_canvas_size(self):
        e = ft.Edits(canvas_w=1920, canvas_h=1080, pages=[3])
        spans = ft.page_spans(e, big_village())
        self.assertGreater(len(spans), 1)
        for n in range(len(spans)):
            sc = page(e, n)
            self.assertEqual((sc.width, sc.height), (1920, 1080))
            self.assertEqual(outside(sc), [])

    def test_saved_and_read_back_with_the_style(self):
        e = ft.Edits(canvas_w=2480, canvas_h=3508)
        data = e.to_data()
        self.assertEqual((data["canvas_w"], data["canvas_h"]), (2480, 3508))
        back = ft.Edits.from_data(data)
        self.assertEqual((back.canvas_w, back.canvas_h), (2480, 3508))
        self.assertIn("canvas_w", ft.STYLE_KEYS)
        self.assertIn("canvas_h", ft.STYLE_KEYS)
        for bad in ({"canvas_w": "x", "canvas_h": 5}, {"canvas_w": 100}, {"canvas_w": True, "canvas_h": 500},
                    {"canvas_w": -4, "canvas_h": 500}):
            got = ft.Edits.from_data({**ft.Edits().to_data(), **{"canvas_w": 0, "canvas_h": 0}, **bad})
            self.assertEqual((got.canvas_w, got.canvas_h), (0, 0), bad)
        huge = ft.Edits.from_data({**data, "canvas_w": 10 ** 9, "canvas_h": 1})
        self.assertEqual((huge.canvas_w, huge.canvas_h), (ft.CANVAS_MAX, ft.CANVAS_MIN))

    def test_the_ready_made_sizes(self):
        self.assertEqual(sorted(ft.CANVAS_SIZES.values()), sorted([
            (1920, 1080), (3840, 2160), (2048, 2048), (2480, 3508), (3508, 2480), (2550, 3300), (3300, 2550),
            (1080, 1920)]))

    def test_the_png_is_the_canvas_size(self):
        try:
            import vv_gdiplus
        except Exception:                       # noqa: BLE001 -- not Windows
            self.skipTest("no GDI+")
        sc = page(ft.Edits(canvas_w=640, canvas_h=480))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.png"
            if not vv_gdiplus.save_scene(sc, {}, path):
                self.skipTest("no GDI+")
            head = path.read_bytes()[:24]
            self.assertEqual((int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")), (640, 480))
        self.assertTrue(re.search(r'width="640" height="480"', ft.to_svg(sc, {})))


class _Var:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class CanvasControlTests(unittest.TestCase):
    """The Background tab's Canvas size box and its width and height boxes."""

    def editor(self):
        import vv_genealogy_window as gw

        class Fake:
            CANVAS_AUTO, CANVAS_CUSTOM = gw.TreeEditor.CANVAS_AUTO, gw.TreeEditor.CANVAS_CUSTOM
            _show_canvas = gw.TreeEditor._show_canvas
            _canvas_mode = gw.TreeEditor._canvas_mode
            _canvas_numbers = gw.TreeEditor._canvas_numbers
            _canvas_typed = gw.TreeEditor._canvas_typed
            _set_canvas = gw.TreeEditor._set_canvas

            def __init__(self):
                self.edits = ft.Edits()
                self.sc = ft.Scene(1234.4, 567.6, "#ffffff")
                self.canvas_mode_var, self.canvas_w_var, self.canvas_h_var = _Var(), _Var(), _Var()
                self.changes = []

            def _change(self, everyone=False, **values):
                self.changes.append((everyone, values))
                for name, value in values.items():
                    setattr(self.edits, name, value)
        return Fake()

    def test_the_controls(self):
        ed = self.editor()
        ed._show_canvas()
        self.assertEqual(ed.canvas_mode_var.get(), ed.CANVAS_AUTO)
        ed.canvas_mode_var.set("HD (1920 x 1080)")
        ed._canvas_mode()
        self.assertEqual((ed.edits.canvas_w, ed.edits.canvas_h), (1920, 1080))
        self.assertEqual(ed.changes[-1], (True, {"canvas_w": 1920, "canvas_h": 1080}), "one step to undo, for everyone")
        self.assertEqual((ed.canvas_w_var.get(), ed.canvas_h_var.get()), ("1920", "1080"))
        ed.canvas_w_var.set("10")                  # still being typed: nothing yet
        ed._canvas_typed()
        self.assertEqual(ed.edits.canvas_w, 1920)
        ed.canvas_w_var.set("2550"); ed.canvas_h_var.set("3300")
        ed._canvas_typed()
        self.assertEqual(ed.canvas_mode_var.get(), "US Letter portrait (2550 x 3300, 300 dpi)")
        ed.canvas_w_var.set("1000"); ed._canvas_typed()
        self.assertEqual(ed.canvas_mode_var.get(), ed.CANVAS_CUSTOM)
        ed.canvas_mode_var.set(ed.CANVAS_AUTO); ed._canvas_mode()
        self.assertEqual((ed.edits.canvas_w, ed.edits.canvas_h), (0, 0))
        self.assertEqual(ed.canvas_w_var.get(), "")
        ed.canvas_mode_var.set(ed.CANVAS_CUSTOM); ed._canvas_mode()   # nothing typed: the page as it is
        self.assertEqual((ed.edits.canvas_w, ed.edits.canvas_h), (1234, 568))
        n = len(ed.changes)
        ed._set_canvas(1234, 568)
        self.assertEqual(len(ed.changes), n, "no step for no change")


if __name__ == "__main__":
    unittest.main()
