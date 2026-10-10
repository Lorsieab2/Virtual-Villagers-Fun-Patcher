"""Line colours: Default / Auto / Rainbow / Gradient / Range (the owner, 2026-10-10), the order the colours run
across the tree, the vivid Auto palette, saving, undo and Reset."""
import colorsys
import json
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_family_tree as ft  # noqa: E402
import vv_line_colours as lc  # noqa: E402
from test_genealogy import village  # noqa: E402
from test_tree_auto_line_colours import GAME, _Editor, _ratio, _rgb, many_families  # noqa: E402


def lch(colour):
    L, a, b = lc.oklab(_rgb(colour))
    return L, math.hypot(a, b), math.degrees(math.atan2(b, a)) % 360


def hsv_hue(colour):
    r, g, b = (v / 255 for v in _rgb(colour))
    return colorsys.rgb_to_hsv(r, g, b)[0] * 360


def rising(h, tol=1.5):
    return all(b >= a - tol for a, b in zip(h, h[1:]))


def keys_in_order(n):
    return [f"family {k:03d}" for k in range(n)]


class AutoIsVividTests(unittest.TestCase):
    MIN_BINS = {6: 6, 12: 7, 30: 10, 60: 10}

    def test_hue_spread_and_mean_chroma(self):
        for n, bins in self.MIN_BINS.items():
            with self.subTest(families=n):
                cols = list(lc.auto_colours(many_families(n), render=False).colours.values())
                chroma = sum(lch(c)[1] for c in cols) / n
                self.assertGreaterEqual(chroma, 0.17, (n, chroma))
                found = {int(lch(c)[2] // 30) for c in cols if lch(c)[1] > 0.06}
                self.assertGreaterEqual(len(found), bins, (n, sorted(found)))

    def test_lightness_varies_and_neutrals_are_only_accents(self):
        cols = list(lc.auto_colours(many_families(60), render=False).colours.values())
        lums = [lch(c)[0] for c in cols]
        self.assertGreater(max(lums) - min(lums), 0.25)
        dull = [c for c in cols if lch(c)[1] < 0.06]
        self.assertLessEqual(len(dull), 60 // lc.ACCENT + 1)

    def test_contrast_and_determinism(self):
        for bg in ("#ffffff", "#101018", "#7f7f7f"):
            a = lc.auto_colours(many_families(30, ft.Backdrop(bg)), render=False)
            self.assertEqual(a.colours, lc.auto_colours(many_families(30, ft.Backdrop(bg)), render=False).colours)
            for k, c in a.colours.items():
                if k not in a.cased:
                    self.assertGreaterEqual(_ratio(_rgb(c), _rgb(bg)), lc.FLOOR - 0.01, (bg, c))


def run(mode, n=10, bg="#000000", **kw):
    pages = many_families(n, ft.Backdrop(bg))
    res = lc.mode_colours(pages, mode, render=False, **kw)
    return res, keys_in_order(n)


class RainbowTests(unittest.TestCase):
    def hues(self, order, reverse=False, n=10):
        res, keys = run("rainbow", n, order=order, reverse=reverse)
        return [hsv_hue(res.colours[k]) for k in keys]

    def test_left_to_right_goes_red_to_violet(self):
        h = self.hues("x")
        self.assertTrue(rising(h), h)
        self.assertLess(h[0], 10)
        self.assertGreater(h[-1], 250)

    def test_right_to_left_and_reverse_run_backwards(self):
        h = self.hues("x_rev")
        self.assertTrue(rising(h[::-1]), h)
        self.assertEqual(self.hues("x", reverse=True), h)
        self.assertEqual(self.hues("x_rev", reverse=True), self.hues("x"))

    def test_top_to_bottom_and_bottom_to_top_by_rows(self):
        res, keys = run("rainbow", 30, order="y")
        by_row = [hsv_hue(res.colours[k]) for k in keys]
        ranked = sorted(keys, key=lambda k: (int(k.split()[1]) // 10, k))   # rows from the top, then by name
        h = [hsv_hue(res.colours[k]) for k in ranked]
        self.assertTrue(rising(h), h)
        res2, _ = run("rainbow", 30, order="y_rev")
        h2 = [hsv_hue(res2.colours[k]) for k in ranked]
        self.assertTrue(rising(h2[::-1]), h2)
        self.assertTrue(by_row)

    def test_per_row_every_row_runs_the_rainbow_again(self):
        res, keys = run("rainbow", 30, order="row")
        for k in range(10):
            self.assertEqual({res.colours[keys[k + 10 * r]] for r in range(3)}, {res.colours[keys[k]]})
        h = [hsv_hue(res.colours[k]) for k in keys[:10]]
        self.assertTrue(rising(h), h)

    def test_per_generation_is_constant_within_a_generation(self):
        v = village()
        e = ft.Edits()
        lay = ft.layout(v, e)
        sc = ft.scene(lay, GAME, {})
        res = lc.mode_colours([(lay, sc)], "rainbow", "generation", render=False)
        gens = {}
        for f in lay.families:
            pid = f.father if f.father is not None else f.mother
            key = ft.family_key(v, f)
            if key in res.colours:
                gens.setdefault(v.people[pid].generation, set()).add(res.colours[key])
        self.assertGreaterEqual(len(gens), 2)
        self.assertTrue(all(len(c) == 1 for c in gens.values()), gens)
        self.assertEqual(len({next(iter(c)) for c in gens.values()}), len(gens))    # other generations differ

    def test_deterministic(self):
        self.assertEqual(run("rainbow", 20)[0].colours, run("rainbow", 20)[0].colours)


class GradientTests(unittest.TestCase):
    def test_endpoints_and_in_between(self):
        res, keys = run("gradient", 10, bg="#ffffff", start="#0033cc", end="#cc0000")
        self.assertEqual(res.colours[keys[0]], "#0033cc")
        self.assertEqual(res.colours[keys[-1]], "#cc0000")
        mid = lch(res.colours[keys[4]])
        self.assertTrue(len({res.colours[k] for k in keys}) == 10)
        self.assertNotEqual(res.colours[keys[4]], res.colours[keys[5]])
        self.assertTrue(mid)

    def test_order_and_reverse(self):
        a, keys = run("gradient", 10, bg="#ffffff", start="#0033cc", end="#cc0000", order="x_rev")
        self.assertEqual(a.colours[keys[-1]], "#0033cc")
        b, _ = run("gradient", 10, bg="#ffffff", start="#0033cc", end="#cc0000", reverse=True)
        self.assertEqual(a.colours, b.colours)

    def test_a_blending_end_is_adjusted_not_dropped(self):
        res, keys = run("gradient", 10, bg="#ffffff", start="#ffff00", end="#00ffff")
        self.assertEqual(len(res.colours), 10)
        for c in res.colours.values():
            self.assertGreaterEqual(_ratio(_rgb(c), (255, 255, 255)), lc.FLOOR - 0.01)


class RangeTests(unittest.TestCase):
    BASES = ["#e63946", "#3a86ff"]

    @staticmethod
    def gap(a, b):
        return min(abs(a - b), 360 - abs(a - b))

    def test_only_the_base_colours_hues(self):
        res, keys = run("range", 24, bg="#ffffff", bases=self.BASES)
        hues = [lch(b)[2] for b in self.BASES]
        for c in res.colours.values():
            self.assertLessEqual(min(self.gap(lch(c)[2], h) for h in hues), 16, c)
        self.assertEqual(len(set(res.colours.values())), 24)       # all different
        used = {min(range(2), key=lambda i: self.gap(lch(c)[2], hues[i])) for c in res.colours.values()}
        self.assertEqual(used, {0, 1})                             # both bases used
        self.assertGreater(len({round(lch(c)[0], 1) for c in res.colours.values()}), 3)    # varied lightness

    def test_a_gray_base_gives_grays(self):
        res, _ = run("range", 6, bg="#ffffff", bases=["#808080"])
        self.assertTrue(all(lch(c)[1] < 0.03 for c in res.colours.values()))

    def test_few_families_get_the_base_colours(self):
        res, keys = run("range", 2, bg="#ffffff", bases=self.BASES)
        self.assertEqual(set(res.colours.values()), set(self.BASES))

    def test_deterministic(self):
        self.assertEqual(run("range", 15, bases=self.BASES)[0].colours, run("range", 15, bases=self.BASES)[0].colours)


class ContrastTests(unittest.TestCase):
    def test_every_mode_stands_out_on_any_plain_background(self):
        for mode in ("rainbow", "gradient", "range"):
            for bg in ("#ffffff", "#000000", "#7f7f7f", "#1b1b3a", "#d9c7a0"):
                with self.subTest(mode=mode, bg=bg):
                    res, _ = run(mode, 30, bg=bg, bases=["#e63946", "#f2c200", "#3a86ff"])
                    for k, c in res.colours.items():
                        if k not in res.cased:
                            self.assertGreaterEqual(_ratio(_rgb(c), _rgb(bg)), lc.FLOOR - 0.01, (c, bg))
                    if bg != "#7f7f7f":
                        self.assertEqual(res.cased, [])


class SavedTests(unittest.TestCase):
    def test_round_trip(self):
        e = ft.Edits(line_mode="range", line_order="generation", line_reverse=True, gradient_start="#112233",
                     gradient_end="#abcdef", range_colours=["#e63946", "#3a86ff"])
        back = ft.Edits._from_data(json.loads(json.dumps(e.to_data())))
        self.assertEqual((back.line_mode, back.line_order, back.line_reverse, back.gradient_start,
                          back.gradient_end, back.range_colours),
                         ("range", "generation", True, "#112233", "#abcdef", ["#e63946", "#3a86ff"]))

    def test_old_edits_load_unchanged(self):
        e = ft.Edits._from_data({"outline_lines": True, "family_lines": {"a||b": {"colour": "#123456"}}})
        self.assertEqual((e.line_mode, e.line_order, e.line_reverse), ("default", "x", False))
        self.assertEqual(e.range_colours, list(ft.RANGE_DEFAULT))
        self.assertEqual(e.family_lines, {"a||b": {"colour": "#123456"}})

    def test_bad_values_fall_back(self):
        e = ft.Edits._from_data({"line_mode": "zigzag", "line_order": 7, "gradient_start": "red",
                                 "range_colours": ["nope", 3]})
        self.assertEqual((e.line_mode, e.line_order, e.gradient_start), ("default", "x", "#ff7a18"))
        self.assertEqual(e.range_colours, list(ft.RANGE_DEFAULT))

    def test_new_trees_keep_default_colouring(self):
        v = village()
        sc = ft.scene(ft.layout(v, ft.Edits()), GAME, {})
        fam = [i for i in sc.items if isinstance(i, ft.Line) and i.piece]
        self.assertTrue(fam)
        self.assertFalse(ft.Edits().family_lines)
        self.assertFalse(ft.Edits().outline_lines)


class WindowTests(unittest.TestCase):
    def test_modes_undo_and_reset(self):
        ed = _Editor()
        ed._colour_lines("rainbow")
        self.assertEqual(ed.edits.line_mode, "rainbow")
        rainbow = json.loads(json.dumps(ed.edits.family_lines))
        self.assertTrue(rainbow and all("colour" in s for s in rainbow.values()))
        ed._colour_lines("gradient", gradient_start="#0033cc", gradient_end="#cc0000", line_order="y")
        self.assertEqual((ed.edits.line_mode, ed.edits.line_order), ("gradient", "y"))
        self.assertNotEqual(ed.edits.family_lines, rainbow)
        ed._undo()                                              # one step: back to the rainbow, order and all
        self.assertEqual((ed.edits.line_mode, ed.edits.line_order), ("rainbow", "x"))
        self.assertEqual(ed.edits.family_lines, rainbow)
        ed._colour_lines("range", range_colours=["#e63946", "#3a86ff"])
        self.assertEqual(ed.edits.range_colours, ["#e63946", "#3a86ff"])
        ed._reset_line_colours()
        self.assertEqual((ed.edits.line_mode, ed.edits.family_lines), ("default", {}))
        ed._undo()
        self.assertEqual(ed.edits.line_mode, "range")

    def test_outline_off_by_default_and_portraits_unchanged(self):
        ed = _Editor()
        before = {k: v.colour for k, v in ((f.id, f) for f in ed.lay.families)}
        ed._colour_lines("rainbow")
        self.assertFalse(ed.edits.outline_lines)
        lay = ft.layout(ed.village, ed.edits)
        self.assertEqual({f.id: f.colour for f in lay.families}, before)


if __name__ == "__main__":
    unittest.main()
