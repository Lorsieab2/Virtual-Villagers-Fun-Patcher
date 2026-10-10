"""A page of the tree ends with the generation the next page starts at (its founders there), so the parents in
that last row have their children on the next page.  They once had no lines at all and looked childless (the
owner, 2026-10-10: "these guys have children but no button will make a proper family tree for them with
lines!").  Now such a family is drawn as any family is, as far as the page allows -- each parent's line, the
couple's line, and from it (a lone parent: from them) one line down to "continued on page N" -- in the colour
it has on the page its children are on, with nothing else on the page moved, in every game and layout."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_family_tree as ft  # noqa: E402
import vv_genealogy as gen  # noqa: E402
from test_genealogy import FIRST, Y, assert_apart, assert_connected  # noqa: E402
from test_tree_packed import LAYOUTS, big_village  # noqa: E402

GAMES = {1: "Virtual Villagers - A New Home", 2: "Virtual Villagers - The Lost Children",
         5: "Virtual Villagers - New Believers"}


def deep_village(game: int) -> gen.Village:
    """Four generations: founders 1 + 2; their children 3 (with an outsider 10), 4 (with an outsider 11 and
    again with an outsider 12) and 5 (a mother, the father unknown); the grandchildren -- 3's twins among
    them -- and in the last generation 20 (child of 13 and 14, both grandchildren).  In New Believers, a
    heathen (30) with no family."""
    people: dict[int, gen.Person] = {}

    def add(pid, sex, years, father=None, mother=None, **extra):
        people[pid] = gen.Person(pid, f"P{pid}", pid % 8, pid % 8, sex=sex, age=years * Y, alive=True,
                                 father=father, mother=mother, first_seen=FIRST, **extra)
    add(1, "Male", 90, arrived=True, how="Founder")
    add(2, "Female", 89, arrived=True, how="Founder")
    add(3, "Male", 60, 1, 2)
    add(4, "Male", 58, 1, 2)
    add(5, "Female", 56, 1, 2)
    add(10, "Female", 60, arrived=True, how="Custom Island Event")
    add(11, "Female", 57, arrived=True, how="Custom Island Event")
    add(12, "Female", 55, arrived=True, how="Custom Island Event")
    add(13, "Male", 30, 3, 10, litter=7)
    add(14, "Female", 30, 3, 10, litter=7)
    add(15, "Female", 28, 4, 11)
    add(16, "Male", 26, 4, 12)
    add(17, "Male", 25, None, 5)
    add(20, "Female", 5, 13, 15)
    add(21, "Male", 3, 16, None)
    if game == 5:
        add(30, "Male", 40, arrived=True, how="Heathen", heathen=True)
    v = gen.Village(game, 1, "Paging Tribe", people)
    gen._generations(v, {FIRST: set(people)})
    gens = {1: 1, 2: 1, 3: 2, 4: 2, 5: 2, 10: 2, 11: 2, 12: 2, 13: 3, 14: 3, 15: 3, 16: 3, 17: 3, 20: 4, 21: 4, 30: 3}
    for pid, g in gens.items():
        if pid in people:
            people[pid].generation = g
            v.base_generation[pid] = g
    gen.number_people(v)
    return v


def onward_families(lay) -> list:
    return [f for f in lay.families if f.onward]


def expected(v, e, page: int) -> dict:
    """Worked out on its own: each family (father, mother) with a parent on this page and every child on a
    later page -> the page (1 up) that shows a parent and the children."""
    spans = ft.page_spans(e, v)
    lo, hi = spans[page]
    out = {}
    fams: dict[tuple, list] = {}
    for c in v.people.values():
        if c.father is not None or c.mother is not None:
            fams.setdefault((c.father, c.mother), []).append(c)
    for (f, m), kids in fams.items():
        here = [q for q in (f, m) if q is not None and lo <= v.people[q].generation <= hi]
        if here and all(c.generation > hi for c in kids):
            out[(f, m)] = next(k + 1 for k, (a, b) in enumerate(spans) if k > page
                               and any(a <= v.people[q].generation <= b for q in here)
                               and all(a <= c.generation <= b for c in kids))
    return out


class ContinuedOnNextPageTests(unittest.TestCase):
    def check_page(self, v, e, page: int, title: str) -> None:
        lay = ft.layout(v, e, page)
        drawn = ft.lines(lay)
        got = {(f.father, f.mother): f.onward_page for f in onward_families(lay)}
        self.assertEqual(got, expected(v, e, page))
        assert_connected(self, lay, drawn)          # (each onward family's lowest end at its words)
        assert_apart(self, drawn)
        sc = ft.scene(lay, title, {})
        words = [i for i in sc.items if isinstance(i, ft.Text) and i.text.startswith("continued on page")]
        self.assertEqual(len(words), len(got))
        boxes = [ft._extent(w) for w in words]
        for i, a in enumerate(boxes):       # no two run into each other
            for b in boxes[:i]:
                self.assertFalse(a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3], (a, b))
        for f in onward_families(lay):
            pieces = {piece for _c, _p, fid, piece in drawn if fid == f.id}
            parents = [q for q in (f.father, f.mother) if q is not None and q in lay.x]
            for q in parents:               # a line from every parent on the page
                self.assertTrue(any(p.startswith(f"from {ft.entry_key(v, v.people[q])}") for p in pieces), (f, pieces))
            if len(parents) == 2:
                self.assertIn("couple", pieces)
                self.assertIn("stem", pieces)
            # In the colour the family has on the page its children are on.
            there = ft.layout(v, e, f.onward_page - 1)
            same = next(g for g in there.families if (g.father, g.mother) == (f.father, f.mother))
            self.assertEqual(f.colour, same.colour)
            self.assertTrue(set(f.onward) <= set(there.x))
            # Its words beside the lowest end of its line, below every portrait.
            ends = [pt for _c, pts, fid, _k in drawn if fid == f.id for pt in pts]
            ex, ey = max(ends, key=lambda pt: (pt[1], pt[0]))
            self.assertTrue(any(abs(w.x - ex - ft.ONWARD_PAD) < 1e-6 for w in words))
            self.assertGreater(ey, max(lay.y[q] + ft.NODE_H for q in parents))
            self.assertLess(ey + 20, lay.height - ft.FOOTER_ROOM + 30)

    def test_every_game_and_layout(self):
        for game, title in GAMES.items():
            v = deep_village(game)
            for positioning in LAYOUTS:
                e = ft.Edits(page_generations=2, positioning=positioning)
                spans = ft.page_spans(e, v)
                self.assertGreater(len(spans), 1)
                for page in range(len(spans)):
                    with self.subTest(game=game, positioning=positioning, page=page):
                        self.check_page(v, e, page, title)
                first = ft.layout(v, e, 0)
                self.assertTrue(onward_families(first), (game, positioning))
                # A lone mother (the father unknown) with her children on the next page is drawn too.
                if spans[0][1] == 2:
                    self.assertTrue(any(f.father is None and f.mother == 5 for f in onward_families(first)))

    def test_the_big_village_over_pages(self):
        v = big_village()
        for positioning in LAYOUTS:
            e = ft.Edits(pages=[3], positioning=positioning)
            for page in range(len(ft.page_spans(e, v))):
                with self.subTest(positioning=positioning, page=page):
                    self.check_page(v, e, page, GAMES[1])

    def test_nothing_else_on_the_page_moves(self):
        """The portraits stand where they stood without these lines, and every other family's lines are as
        they were."""
        v = deep_village(1)
        for positioning in LAYOUTS:
            e = ft.Edits(page_generations=2, positioning=positioning)
            lay = ft.layout(v, e, 0)
            plain = ft.layout(v, e, 0)
            plain.families = [f for f in plain.families if not f.onward]
            self.assertEqual((lay.x, lay.y), (plain.x, plain.y))
            mine = {f.id for f in onward_families(lay)}
            with_them = [s for s in ft.lines(lay) if s[2] not in mine]
            self.assertEqual(with_them, ft.lines(plain), positioning)

    def test_the_last_page_and_a_one_page_tree_have_none(self):
        v = deep_village(1)
        e = ft.Edits(page_generations=2)
        self.assertEqual(onward_families(ft.layout(v, e, len(ft.page_spans(e, v)) - 1)), [])
        self.assertEqual(onward_families(ft.layout(v, ft.Edits(page_generations=10), 0)), [])

    def test_a_hidden_child_or_parent_draws_nothing(self):
        v = deep_village(1)
        e = ft.Edits(page_generations=2)
        for pid in (13, 14, 15):
            e.entries[ft.entry_key(v, v.people[pid])] = {"hidden": True}
        lay = ft.layout(v, e, 0)
        self.assertFalse(any(13 in (f.father, f.mother) or 15 in (f.father, f.mother) for f in onward_families(lay)))


if __name__ == "__main__":
    unittest.main()
