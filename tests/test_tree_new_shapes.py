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
