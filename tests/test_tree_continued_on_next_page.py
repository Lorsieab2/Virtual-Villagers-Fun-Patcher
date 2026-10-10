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
        for box in boxes:                   # nor into a portrait, nor any line
            for q in lay.x:
                xs, ys = zip(*lay.frame_points(q))
                self.assertFalse(box[0] < max(xs) and min(xs) < box[2] and box[1] < max(ys) and min(ys) < box[3], q)
            for _c, pts, _fid, _k in drawn:
                for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
                    lo_x, hi_x, lo_y, hi_y = min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1)
                    self.assertFalse(lo_x < box[2] and box[0] < hi_x and lo_y < box[3] - 2 and box[1] + 2 < hi_y
                                     if lo_x != hi_x or lo_y != hi_y else False, (box, pts))
        for f in onward_families(lay):
            pieces = {piece for _c, _p, fid, piece in drawn if fid == f.id}
            self.assertTrue(all(p.startswith(ft.ONWARD_PIECE) for p in pieces))    # named apart (per page)
            pieces = {p[len(ft.ONWARD_PIECE):] for p in pieces}
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
            # Its words centred under the lowest end of its own line, below every portrait.
            ends = [pt for _c, pts, fid, _k in drawn if fid == f.id for pt in pts]
            ex, ey = max(ends, key=lambda pt: (pt[1], pt[0]))
            mine = [w for w in words if w.move == ft.onward_key(v, f)]
            self.assertEqual(len(mine), 1)
            self.assertTrue(mine[0].centre and abs(mine[0].x - ex) < 1e-6 and ft._extent(mine[0])[1] > ey - 1)
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


def first_onward(v, e):
    lay = ft.layout(v, e, 0)
    fam = next(f for f in onward_families(lay) if f.father is not None and f.mother is not None)
    return lay, fam


def onward_texts(sc) -> list:
    return [i for i in sc.items if isinstance(i, ft.Text) and i.role == "onward"]


class OnwardWordsAreEditableTests(unittest.TestCase):
    """The owner, 2026-10-10: the "continued on page N" words editable in every way the tree's other words are."""

    def setUp(self):
        self.v = deep_village(1)
        self.e = ft.Edits(page_generations=2)

    def scene(self):
        return ft.scene(ft.layout(self.v, self.e, 0), GAMES[1], {})

    def test_their_role_style_and_opacity(self):
        self.assertIn("onward", ft.ROLES)
        self.assertIn("onward", ft.OPACITY)
        self.e.styles["onward"] = ft.clean_style({"font": "Georgia", "scale": 150, "bold": True, "italic": True,
                                                  "underline": True, "colour": "#123456"})
        self.e.opacity["onward"] = 40
        for t in onward_texts(self.scene()):
            self.assertEqual((t.font, t.bold, t.italic, t.underline, t.colour), ("Georgia", True, True, True, "#123456"))
            self.assertAlmostEqual(t.size, ft.ONWARD_SIZE * 1.5)
            self.assertAlmostEqual(t.opacity, 0.4)

    def test_their_words_one_family_or_every_family_with_the_page_filled_in(self):
        lay, fam = first_onward(self.v, self.e)
        key = ft.onward_key(self.v, fam)
        self.e.words["onward"] = "to page {page}"
        texts = {t.move: t.text for t in onward_texts(self.scene())}
        self.assertTrue(texts and all(t == f"to page {f.onward_page}" for f in onward_families(lay)
                                      for k, t in texts.items() if k == ft.onward_key(self.v, f)))
        self.e.words[key] = "kids: page {page}"
        texts = {t.move: t.text for t in onward_texts(self.scene())}
        self.assertEqual(texts[key], f"kids: page {fam.onward_page}")
        self.assertTrue(all(t.startswith("to page") for k, t in texts.items() if k != key))

    def test_retyping_keeps_the_page_number_the_pages(self):
        import types
        import vv_genealogy_window as win
        lay, fam = first_onward(self.v, self.e)
        key = ft.onward_key(self.v, fam)
        saved = []
        me = types.SimpleNamespace(edits=self.e, lay=lay, village=self.v, _saved=lambda: saved.append(1))
        me._onward_family = lambda name: win.TreeEditor._onward_family(me, name)
        now, own, commit = win.TreeEditor._onward_words_of(me, key)
        self.assertEqual((now, own), (f"continued on page {fam.onward_page}",) * 2)
        commit(f"to page {fam.onward_page}")
        self.assertEqual(self.e.words[key], "to page {page}")
        commit(own)                                  # the default again: nothing kept
        self.assertNotIn(key, self.e.words)
        _now, _own, every = win.TreeEditor._onward_words_of(me, key, every=True)
        every(f"see page {fam.onward_page}")
        self.assertEqual(self.e.words["onward"], "see page {page}")

    def test_hidden_moved_saved_and_old_edits_unchanged(self):
        lay, fam = first_onward(self.v, self.e)
        key = ft.onward_key(self.v, fam)
        before = {t.move: (t.x, t.y) for t in onward_texts(self.scene())}
        self.e.moved[key] = [30.0, 12.0]
        after = {t.move: (t.x, t.y) for t in onward_texts(self.scene())}
        self.assertEqual(after[key], (before[key][0] + 30.0, before[key][1] + 12.0))
        self.assertEqual({k: p for k, p in after.items() if k != key}, {k: p for k, p in before.items() if k != key})
        self.e.hidden.append(f"word:{key}")
        self.assertNotIn(key, {t.move for t in onward_texts(self.scene())})
        self.e.words[key] = "x {page}"
        self.e.styles["onward"] = {"bold": True}
        back = ft.Edits.from_data(self.e.to_data())
        self.assertEqual((back.words, back.moved, back.hidden, back.styles),
                         (self.e.words, self.e.moved, self.e.hidden, self.e.styles))
        self.e.hidden.append("word:onward")
        self.assertEqual(onward_texts(self.scene()), [])
        old = ft.Edits(page_generations=2).to_data()      # saved before these words were editable
        for name in ("words", "styles", "opacity", "moved", "hidden"):
            self.assertFalse(old[name])
        self.assertEqual(ft.Edits.from_data(old).to_data(), old)

    def test_their_line_recoloured_like_any_family_line(self):
        lay, fam = first_onward(self.v, self.e)
        fkey = ft.family_key(self.v, fam)
        self.e.family_lines[fkey] = {"colour": "#ff00aa"}
        sc = self.scene()
        mine = [i for i in sc.items if isinstance(i, ft.Line) and i.piece.startswith(fkey + "|" + ft.ONWARD_PIECE)]
        self.assertTrue(mine and all(i.colour == "#ff00aa" and i.target == ("family", fkey) for i in mine))


class LineMovesPerPageTests(unittest.TestCase):
    def test_a_piece_dragged_on_one_page_stays_put_on_the_other(self):
        v = deep_village(1)
        e = ft.Edits(page_generations=2)
        lay1, fam = first_onward(v, e)
        fkey = ft.family_key(v, fam)
        page2 = ft.layout(v, e, fam.onward_page - 1)
        here = {k: p for _c, p, fid, k in ft.lines(lay1) if fid == fam.id}
        there_fam = next(f for f in page2.families if (f.father, f.mother) == (fam.father, fam.mother))
        there = {k: p for _c, p, fid, k in ft.lines(page2) if fid == there_fam.id}
        self.assertIn("couple", there)
        e.line_moves[f"{fkey}|couple"] = 9.0                         # dragged on the children's page (as saved before)
        self.assertEqual({k: p for _c, p, fid, k in ft.lines(ft.layout(v, e, 0)) if fid == fam.id}, here)
        moved = {k: p for _c, p, fid, k in ft.lines(ft.layout(v, e, fam.onward_page - 1)) if fid == there_fam.id}
        self.assertNotEqual(moved["couple"], there["couple"])
        e.line_moves = {f"{fkey}|{ft.ONWARD_PIECE}couple": 9.0}      # dragged above the page break
        self.assertNotEqual({k: p for _c, p, fid, k in ft.lines(ft.layout(v, e, 0)) if fid == fam.id}[
            f"{ft.ONWARD_PIECE}couple"], here[f"{ft.ONWARD_PIECE}couple"])
        self.assertEqual({k: p for _c, p, fid, k in ft.lines(ft.layout(v, e, fam.onward_page - 1))
                          if fid == there_fam.id}, there)


class NoClusterTests(unittest.TestCase):
    def test_partners_far_apart_get_their_words_side_by_side_under_their_own_lines(self):
        """Many couples whose partners stand far apart, all with children on the next page: one row of
        words, each under its own line (never stacked at the middle)."""
        people: dict[int, gen.Person] = {}

        def add(pid, sex, years, father=None, mother=None, **extra):
            people[pid] = gen.Person(pid, f"P{pid}", pid % 8, pid % 8, sex=sex, age=years * Y, alive=True,
                                     father=father, mother=mother, first_seen=FIRST, **extra)
        add(1, "Male", 90, arrived=True, how="Founder")
        add(2, "Female", 89, arrived=True, how="Founder")
        for k in range(8):
            add(10 + k, "Male" if k < 4 else "Female", 60 - k, 1, 2)
        for k in range(4):                       # each man with a woman at the far end of the row
            add(30 + k, "Female", 10, 10 + k, 17 - k)
        v = gen.Village(1, 1, "Far Tribe", people)
        gen._generations(v, {FIRST: set(people)})
        for pid, g in {1: 1, 2: 1, **{10 + k: 2 for k in range(8)}, **{30 + k: 3 for k in range(4)}}.items():
            people[pid].generation = g
            v.base_generation[pid] = g
        gen.number_people(v)
        e = ft.Edits(page_generations=2, positioning="rows")
        lay = ft.layout(v, e, 0)
        fams = onward_families(lay)
        self.assertEqual(len(fams), 4)
        self.assertEqual(len({f.lane_y for f in fams}), 1)         # one row
        self.assertEqual(len({round(f.stem_x) for f in fams}), 4)
        ContinuedOnNextPageTests.check_page(self, v, e, 0, GAMES[1])


if __name__ == "__main__":
    unittest.main()
