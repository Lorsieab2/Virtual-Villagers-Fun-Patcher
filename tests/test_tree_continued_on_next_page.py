"""A parent in a page's last generation has their children on the next page (which starts with that generation
as its founders).  Without a mark the parent looked childless (the owner, 2026-10-10: "these guys have children
but no button will make a proper family tree for them with lines!"): now a short dotted line down from the
portrait and "to page N" say where the family's lines are, and they really are drawn there."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_family_tree as ft  # noqa: E402
from test_tree_packed import big_village  # noqa: E402

GAME = "Virtual Villagers - A New Home"


class ContinuedOnNextPageTests(unittest.TestCase):
    def setUp(self):
        self.v = big_village()
        self.e = ft.Edits(pages=[3])
        self.spans = ft.page_spans(self.e, self.v)
        self.assertGreater(len(self.spans), 1)

    def test_every_parent_with_children_elsewhere_is_marked_and_the_lines_are_on_that_page(self):
        marked_any = False
        for n, (lo, hi) in enumerate(self.spans[:-1]):
            lay = ft.layout(self.v, self.e, n)
            marks = ft.continued_on(lay)
            for q, pages in marks.items():
                marked_any = True
                self.assertEqual(self.v.people[q].generation, hi)
                for page in pages:
                    other = ft.layout(self.v, self.e, page - 1)
                    self.assertIn(q, other.x)
                    drawn = {f for _c, _p, f, _k in ft.lines(other)}
                    self.assertTrue(any(f.id in drawn and q in (f.father, f.mother) for f in other.families), (q, page))
            for pid, p in self.v.people.items():
                if pid in lay.x and p.generation == hi:
                    kids = [c for c in self.v.people.values() if pid in (c.father, c.mother)]
                    on_here = any(c.id in lay.x for c in kids)
                    self.assertEqual(bool(kids) and not on_here, pid in marks, pid)
        self.assertTrue(marked_any)

    def test_the_mark_is_drawn_and_the_last_page_has_none(self):
        lay = ft.layout(self.v, self.e, 0)
        sc = ft.scene(lay, GAME, {})
        texts = [i.text for i in sc.items if isinstance(i, ft.Text) and i.text.startswith("to page")]
        self.assertEqual(len(texts), len(ft.continued_on(lay)))
        self.assertTrue(texts)
        last = ft.layout(self.v, self.e, len(self.spans) - 1)
        self.assertEqual(ft.continued_on(last), {})

    def test_a_single_page_tree_has_no_marks(self):
        self.assertEqual(ft.continued_on(ft.layout(self.v, ft.Edits(page_generations=10), 0)), {})


if __name__ == "__main__":
    unittest.main()
