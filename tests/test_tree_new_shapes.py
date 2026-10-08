"""The owner's portrait shapes of 2026-10-08 -- Flower, Butterfly, Clover, Spade, Leaf -- and "Apply to
every one" for a group's shape and border."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_family_tree as ft  # noqa: E402
from test_genealogy import village  # noqa: E402

NEW = {"flower": "Flower", "butterfly": "Butterfly", "clover": "Clover", "spade": "Spade", "leaf": "Leaf"}


class NewShapeTests(unittest.TestCase):
    def test_each_is_offered_and_fills_its_box(self) -> None:
        for kind, words in NEW.items():
            self.assertEqual(ft.PORTRAIT_SHAPES[kind], words)
            points = ft.OUTLINES[kind]
            xs, ys = zip(*points)
            self.assertEqual((min(xs), max(xs), min(ys), max(ys)), (0.0, 1.0, 0.0, 1.0), kind)
            self.assertGreater(len(points), 100, kind)
            self.assertTrue(0.3 < ft.ASPECTS[kind] < 2.0, kind)
            # Its middle is inside it, so a click on the portrait finds it.
            self.assertTrue(ft.inside(ft.outline(kind, 0, 0, 100, 100), 50, 52), kind)

    def test_the_fixed_proportions_are_the_traced_ones_and_nothing_is_traced_at_start_up(self) -> None:
        for kind in NEW:
            self.assertEqual(ft.ASPECTS[kind], round(ft._raw_aspect(kind), 3), kind)
        import subprocess
        code = ("import sys, time; sys.path.insert(0, r'%s'); t = time.perf_counter(); import vv_family_tree as ft; "
                "print(time.perf_counter() - t, 'flower' in dict.keys(ft.OUTLINES))" % (ROOT / "src"))
        took, traced = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True).stdout.split()
        self.assertEqual(traced, "False")                       # traced only when first drawn (Codex, #575)

    def test_the_stored_shapes_are_the_traced_ones_and_load_at_once(self) -> None:
        import json
        import time
        stored = json.loads(ft.TREE_SHAPES_FILE.read_text(encoding="utf-8"))
        for kind, points in ft.traced_unit_outlines().items():
            self.assertEqual(len(stored[kind]), len(points), kind)
            for (sx, sy), (x, y) in zip(stored[kind], points):
                self.assertAlmostEqual(sx, x, places=4)
                self.assertAlmostEqual(sy, y, places=4)
        fresh = ft._Outlines(ft._unit_outlines())
        started = time.perf_counter()
        fresh["flower"]
        self.assertLess(time.perf_counter() - started, 0.5)     # read, not traced (Codex, #575)

    def test_the_flower_has_six_petals_one_straight_up(self) -> None:
        points = ft.outline("flower", -1, -1, 2, 2)
        top = min(points, key=lambda p: p[1])
        self.assertLess(abs(top[0]), 0.05)                      # a petal straight up, in the middle
        bottom = max(points, key=lambda p: p[1])
        self.assertLess(abs(bottom[0]), 0.05)                   # and one straight down
        # Six petal tips: the points farthest from the middle in each sixth of the turn.
        import math
        far = {}
        for x, y in points:
            sixth = int(((math.degrees(math.atan2(y, x)) + 90 + 30) % 360) // 60)
            far[sixth] = max(far.get(sixth, 0), math.hypot(x, y))
        self.assertEqual(len(far), 6)

    def test_every_group_can_take_them_and_every_export_draws_them(self) -> None:
        for kind in NEW:
            e = ft.Edits(shapes={"Male": kind, "Female": kind, "Upcoming": kind})
            data = e.to_data()
            self.assertEqual(ft.Edits.from_data(data).shapes["Male"], kind)    # kept in the tree file
            sc = ft.scene(ft.layout(village(), e), "A New Home", {})
            self.assertIn("<polygon", ft.to_svg(sc, {}))


class JoiningTests(unittest.TestCase):
    def test_lines_join_only_once_the_width_is_widened(self) -> None:
        v = village()
        p = next(q for q in v.known() if not q.upcoming)
        typed = ["1. Someone", "Leader", "Doctor"]
        for n, expected in ((17, ["1. Someone", "Leader", "Doctor"]), (30, ["1. Someone", "Leader, Doctor"])):
            e = ft.Edits(text_wrap=n)
            e.entries[ft.entry_key(v, p)] = {"lines": typed}
            ft.arrange(v, e)
            lay = ft.layout(v, e)
            self.assertEqual([t for t, _b, _r in ft.placement(lay, p)[3]], expected, n)


class SpacingAndFitTests(unittest.TestCase):
    """The owner, 2026-10-08: "allow auto resizing of portraits and text to accommodate lots of portraits
    per page" and "batch-editing of spacing between two portraits in pixels"."""

    def lay(self, **values):
        v = village()
        e = ft.Edits(**values)
        ft.arrange(v, e)
        return v, ft.layout(v, e)

    def test_the_defaults_lay_out_as_before(self) -> None:
        v, lay = self.lay()
        self.assertEqual(lay.edits._shrink, 1.0)
        row = sorted(lay.x[q] for q in lay.rows[min(lay.rows)])
        frame = max(ft.frame_size(lay.edits, v, q, own=False)[0] for q in v.people.values() if q.id in lay.x)
        self.assertAlmostEqual(row[1] - row[0], max(ft.NODE_W, frame) + ft.GAP_X)

    def test_the_gap_between_portraits_is_the_players(self) -> None:
        for gap in (4.0, 60.0):
            v, lay = self.lay(portrait_gap=gap)
            row = sorted(lay.x[q] for q in lay.rows[min(lay.rows)])
            frame = max(ft.frame_size(lay.edits, v, q, own=False)[0] for q in v.people.values() if q.id in lay.x)
            self.assertAlmostEqual(row[1] - row[0], max(ft.NODE_W, frame) + gap)
        self.assertEqual(ft.Edits.from_data(ft.Edits(portrait_gap=60.0).to_data()).portrait_gap, 60.0)

    def test_shrink_to_fit_shrinks_frames_faces_and_words_alike(self) -> None:
        v, full = self.lay()
        _v, fitted = self.lay(fit_width=420)
        s = fitted.edits._shrink
        self.assertLess(s, 1.0)
        p = next(q for q in v.known() if not q.upcoming)
        self.assertAlmostEqual(fitted.frame(p.id)[2], full.frame(p.id)[2] * s, places=6)
        sizes = {}
        for name, lay in (("full", full), ("fitted", fitted)):
            sc = ft.scene(lay, "A New Home", {})
            sizes[name] = max(i.size for i in sc.items if isinstance(i, ft.Text) and i.pid == p.id)
        self.assertAlmostEqual(sizes["fitted"], sizes["full"] * max(0.2, s), places=6)
        back = ft.Edits.from_data(ft.Edits(fit_width=420).to_data())
        self.assertEqual((back.fit_width, back._shrink), (420, 1.0))     # the shrink itself is never saved
        self.assertEqual(ft.Edits.from_data({"fit_width": 0}).fit_width, 0)

    def test_a_resize_by_hand_is_kept_before_the_shrink(self) -> None:
        source = (ROOT / "src" / "vv_tree_editor_tools.py").read_text(encoding="utf-8")
        self.assertIn("self._set_entry(p, w=round(w / s, 1), h=round(h / s, 1))", source)


class GenerationsPerPageTests(unittest.TestCase):
    """The owner, 2026-10-08: "a maximum of... 10 generations on one family tree page, if they're still
    legible" and "Default max should be 6 though"."""

    def spans(self, generations: int, **values):
        import types
        people = {g: types.SimpleNamespace(generation=g) for g in range(1, generations + 1)}
        return ft.page_spans(ft.Edits(**values), types.SimpleNamespace(people=people))

    def test_six_until_the_player_says_and_each_page_starts_with_the_last_ones_generation(self) -> None:
        self.assertEqual(ft.Edits().page_generations, 6)
        self.assertEqual(self.spans(5), [(1, 5)])
        self.assertEqual(self.spans(6), [(1, 6)])
        self.assertEqual(self.spans(14), [(1, 6), (6, 11), (11, 14)])
        self.assertEqual(self.spans(14, page_generations=10), [(1, 10), (10, 14)])
        for lo, hi in self.spans(40):
            self.assertLessEqual(hi - lo + 1, 6)

    def test_the_players_own_breaks_still_count_and_the_setting_is_kept_within_2_to_10(self) -> None:
        self.assertEqual(self.spans(14, pages=[4]), [(1, 4), (4, 9), (9, 14)])
        self.assertEqual(ft.Edits.from_data({"page_generations": 40}).page_generations, 10)
        self.assertEqual(ft.Edits.from_data({"page_generations": 1}).page_generations, 2)
        self.assertEqual(ft.Edits.from_data({}).page_generations, 6)
        self.assertEqual(ft.Edits.from_data(ft.Edits(page_generations=8).to_data()).page_generations, 8)


class ApplyToEveryOneTests(unittest.TestCase):
    def test_the_button_clears_each_villagers_own_shape_and_border_in_that_group_only(self) -> None:
        source = (ROOT / "src" / "vv_genealogy_window.py").read_text(encoding="utf-8")
        body = source[source.index("    def _group_all("):source.index("    def _live(")]
        self.assertIn("ft.group_of(p) != group", body)
        self.assertIn('self._set_entry(p, shape="", border="")', body)
        self.assertIn("self._saved()", body)
        self.assertIn('text="Apply to every one"', source)


if __name__ == "__main__":
    unittest.main()
