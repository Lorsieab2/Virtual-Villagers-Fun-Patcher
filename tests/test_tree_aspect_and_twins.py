"""Family Tree Maker: Keep aspect ratio for the size boxes, and the twins and triplets line (the owner,
2026-10-09)."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import vv_family_tree as ft  # noqa: E402


class KeepAspectTests(unittest.TestCase):
    def test_width_sets_the_height_by_the_shape(self):
        self.assertEqual(ft.keep_aspect((100.0, 150.0), 0, 200.0), (200.0, 300.0))

    def test_height_sets_the_width_by_the_shape(self):
        self.assertEqual(ft.keep_aspect((100.0, 150.0), 1, 75.0), (50.0, 75.0))

    def test_the_side_that_follows_stays_in_range(self):
        w, h = ft.keep_aspect((10.0, 1000.0), 0, 1000.0)
        self.assertEqual(w, 1000.0)
        self.assertLessEqual(h, ft.FRAME_MAX)


def person(pid, name, number, litter=None, upcoming=False):
    return SimpleNamespace(id=pid, name=name, number=number, litter=litter, upcoming=upcoming)


class TwinsTests(unittest.TestCase):
    def lay(self, people, on=True):
        return SimpleNamespace(edits=SimpleNamespace(show_twins=on), names={},
                               village=SimpleNamespace(people={p.id: p for p in people}))

    def test_twins_name_each_other(self):
        a, b = person(1, "Kalea", 3, litter=7), person(2, "Hana", 4, litter=7)
        lay = self.lay([a, b, person(3, "Papu", 5)])
        self.assertEqual(ft.born_with(lay, a), ["Hana's twin"])
        self.assertEqual(ft.born_with(lay, b), ["Kalea's twin"])

    def test_triplets_name_the_other_two(self):
        a, b, c = (person(k, n, k, litter=2) for k, n in ((1, "Ana"), (2, "Bo"), (3, "Cy")))
        self.assertEqual(ft.born_with(self.lay([a, b, c]), b), ["Ana and Cy's triplet"])

    def test_nothing_when_off_or_born_alone(self):
        a, b = person(1, "Kalea", 3, litter=7), person(2, "Hana", 4, litter=7)
        self.assertEqual(ft.born_with(self.lay([a, b], on=False), a), [])
        self.assertEqual(ft.born_with(self.lay([person(3, "Papu", 5)]), person(3, "Papu", 5)), [])

    def test_the_setting_is_saved_and_remembered_with_the_look(self):
        edits = ft.Edits()
        edits.show_twins = True
        self.assertTrue(ft.style_of(edits)["show_twins"])
        self.assertTrue(ft.styled({"show_twins": True}).show_twins)


if __name__ == "__main__":
    unittest.main()
