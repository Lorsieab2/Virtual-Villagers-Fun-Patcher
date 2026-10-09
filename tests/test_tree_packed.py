"""The Family Tree Maker's cluster layouts (the owner, 2026-10-09, showing two hand-made trees: "cluster
portraits like this"): Compact family clusters -- each family's children in a small cluster under their
own parents, partners side by side, families wrapped into short rows -- and Family clusters in generation
rows; and the Other Members as a grid on either side, in every layout."""
import hashlib
import json
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_family_tree as ft  # noqa: E402
import vv_genealogy as gen  # noqa: E402
from test_genealogy import FIRST, LATER, Y, assert_apart, assert_connected, village  # noqa: E402

GAME = "Virtual Villagers - A New Home"
LAYOUTS = ("dynamic", "rows", "clusters", "bands")


def big_village() -> gen.Village:
    """Founders 1 and 2 with five children.  Son 3 and a wife from outside (8) have four children, one of
    them (11) with a husband from outside (16) and a child (17); daughter 4 and a husband from outside
    (13) have one (14); son 5 marries 14, his niece -- two in-tree parents of different depths -- and they
    have 15.  Three loners of one generation (20-22) belong to nobody."""
    people: dict[int, gen.Person] = {}

    def add(pid, sex, years, father=None, mother=None, **extra):
        people[pid] = gen.Person(pid, f"P{pid}", pid, pid, sex=sex, age=years * Y, alive=True, father=father,
                                 mother=mother, first_seen=FIRST, **extra)

    add(1, "Male", 80, arrived=True, how="Founder")
    add(2, "Female", 79, arrived=True, how="Founder")
    add(3, "Male", 50, 1, 2)
    add(4, "Female", 49, 1, 2)
    add(5, "Male", 48, 1, 2)
    add(6, "Female", 47, 1, 2)
    add(7, "Male", 46, 1, 2)
    add(8, "Female", 50, arrived=True, how="Custom Island Event")
    add(13, "Male", 50, arrived=True, how="Custom Island Event")
    for pid, years in ((9, 25), (10, 24), (11, 23), (12, 22)):
        add(pid, "Female" if pid % 2 else "Male", years, 3, 8)
    add(14, "Female", 24, 13, 4)
    add(15, "Male", 2, 5, 14)
    add(16, "Male", 30, arrived=True, how="Custom Island Event")
    add(17, "Female", 1, 16, 11)
    for pid in (20, 21, 22):
        add(pid, "Male", 40, arrived=True, how="Custom Island Event")
    v = gen.Village(1, 1, "Cluster Tribe", people)
    gen._generations(v, {FIRST: set(people)})
    # Each newcomer in the generation they married into; the loners in the grandchildren's.
    for pid, g in {8: 2, 13: 2, 16: 3, 20: 3, 21: 3, 22: 3, 9: 3, 10: 3, 11: 3, 12: 3, 14: 3, 15: 4, 17: 4}.items():
        people[pid].generation = g
        v.base_generation[pid] = g
    gen.number_people(v)
    return v


def boxes(lay) -> dict:
    out = {}
    for q in lay.x:
        xs, ys = zip(*lay.frame_points(q))
        out[q] = (min(xs), min(ys), max(xs), max(ys))
    return out


def centre(lay, q) -> float:
    return lay.x[q] + ft.NODE_W / 2


class ClusterShapeTests(unittest.TestCase):
    def lay(self, **edits):
        return ft.layout(big_village(), ft.Edits(positioning="clusters", **edits))

    def test_children_hang_under_their_parents_middle(self):
        lay = self.lay()
        kids = [9, 10, 11, 12]
        self.assertEqual(len({lay.y[q] for q in kids}), 1, "one row without a limit")
        # 11 stands with her husband 16 beside her, so the row's middle takes him in too.
        row = kids + [16]
        middle = (min(centre(lay, q) for q in row) + max(centre(lay, q) for q in row)) / 2
        self.assertAlmostEqual(middle, (centre(lay, 3) + centre(lay, 8)) / 2, delta=1)
        self.assertGreater(lay.y[9], lay.y[3])

    def test_partners_stand_side_by_side(self):
        lay = self.lay()
        step = ft.Edits().portrait_gap + max(ft.NODE_W, max(ft.frame_size(lay.edits, lay.village, p, own=False)[0]
                                                             for p in lay.village.people.values()))
        for a, b in ((1, 2), (3, 8), (4, 13), (11, 16), (5, 14)):
            self.assertEqual(lay.y[a], lay.y[b], (a, b))
            self.assertAlmostEqual(abs(lay.x[a] - lay.x[b]), step, delta=0.5, msg=(a, b))
        v = village()                   # two couples whose four parents are all in the tree
        lay = ft.layout(v, ft.Edits(positioning="clusters"))
        for a, b in ((5, 8), (7, 6)):
            self.assertEqual(lay.y[a], lay.y[b])
            self.assertLess(abs(lay.x[a] - lay.x[b]), ft.NODE_W * 2.2)

    def test_a_couple_from_two_depths_hangs_under_the_lower(self):
        lay = self.lay()
        self.assertEqual(lay.y[5], lay.y[14], "5 stands with his wife, under her parents")
        self.assertGreater(lay.y[5], lay.y[3], "lower than his brothers and sisters")
        self.assertGreater(lay.y[15], lay.y[14])
        fam = next(f for f in lay.families if 5 in f.children)
        self.assertIn(5, fam.away)
        self.assertLess(abs(centre(lay, 15) - (centre(lay, 5) + centre(lay, 14)) / 2), 1)

    def test_the_couples_line_drops_from_between_them(self):
        lay = self.lay()
        fam = next(f for f in lay.families if 9 in f.children)
        stem = next(pts for _c, pts, fid, piece in ft.lines(lay) if fid == fam.id and piece == "stem")
        self.assertTrue(centre(lay, 3) < stem[0][0] < centre(lay, 8) or centre(lay, 8) < stem[0][0] < centre(lay, 3))
        couple = next(pts for _c, pts, fid, piece in ft.lines(lay) if fid == fam.id and piece == "couple")
        self.assertLessEqual(abs(couple[1][0] - couple[0][0]), abs(centre(lay, 3) - centre(lay, 8)) + 1, "short")

    def test_a_family_wraps_inside_its_own_cluster(self):
        lay = self.lay(row_limit=2)
        kids = [9, 10, 12]              # 11 stands with her husband, 9, 10 and 12 have no families
        rows = {}
        for q in kids:
            rows.setdefault(round(lay.y[q]), []).append(q)
        self.assertGreater(len(rows), 1)
        for row in rows.values():
            self.assertLessEqual(len(row), 2)
        lo, hi = min(centre(lay, q) for q in (3, 8)), max(centre(lay, q) for q in (3, 8))
        for q in kids:                  # near their parents, not out at the tree's edge
            self.assertLess(abs(centre(lay, q) - (lo + hi) / 2), 4 * ft.NODE_W)
        self.assertLess(lay.width, self.lay().width + 1)

    def test_the_generation_labels_go_down_the_page(self):
        sc = ft.scene(self.lay(), GAME, {})
        tops = {}
        for item in sc.items:
            if isinstance(item, ft.Text) and item.role == "labels" and item.part.endswith("|number"):
                tops[int(item.part.split("|")[0])] = item.y
        gens = sorted(tops)
        self.assertEqual([tops[g] for g in gens], sorted(tops[g] for g in gens))


class BandTests(unittest.TestCase):
    def test_families_wrap_and_stay_in_their_generation(self):
        v = big_village()
        lay = ft.layout(v, ft.Edits(positioning="bands", row_limit=2))
        kids = [9, 10, 11, 12, 16]      # 16 married 11 and stands beside her, in her family's block
        rows = {}
        for q in kids:
            rows.setdefault(round(lay.y[q]), []).append(q)
        self.assertGreater(len(rows), 1)
        self.assertTrue(all(len(r) <= 2 for r in rows.values()))
        self.assertEqual(lay.y[11], lay.y[16])
        self.assertLess(abs(lay.x[11] - lay.x[16]), ft.NODE_W * 2)
        g = v.people[9].generation
        for q in lay.x:                 # nobody of another generation between the band's rows
            if q not in lay.others and v.people[q].generation != g:
                self.assertFalse(min(rows) <= lay.y[q] <= max(rows), q)

    def test_a_block_sits_under_its_parents(self):
        lay = ft.layout(big_village(), ft.Edits(positioning="bands", row_limit=2))
        kids = [9, 10, 11, 12]
        middle = (min(centre(lay, q) for q in kids) + max(centre(lay, q) for q in kids)) / 2
        self.assertLess(abs(middle - (centre(lay, 3) + centre(lay, 8)) / 2), 2 * ft.NODE_W)


class EveryLayoutTests(unittest.TestCase):
    def cases(self):
        for make in (village, big_village):
            for positioning in LAYOUTS:
                for limit in (0, 2):
                    for side in ft.OTHERS_SIDES:
                        yield make, ft.Edits(positioning=positioning, row_limit=limit, others_columns=2,
                                             others_side=side)

    def test_no_two_portraits_overlap(self):
        for make, e in self.cases():
            lay = ft.layout(make(), e)
            b = boxes(lay)
            for p in b:
                for q in b:
                    if p < q:
                        x0, y0, x1, y1 = b[p]
                        a0, c0, a1, c1 = b[q]
                        self.assertFalse(x0 < a1 and a0 < x1 and y0 < c1 and c0 < y1,
                                         f"{e.positioning} {e.row_limit}: {p} and {q} overlap")

    def test_every_child_is_joined_to_its_parents(self):
        for make, e in self.cases():
            lay = ft.layout(make(), e)
            drawn = ft.lines(lay)
            assert_connected(self, lay, drawn)
            assert_apart(self, drawn)
            frames = boxes(lay)
            for fam in lay.families:
                mine = [pts for _c, pts, fid, _p in drawn if fid == fam.id]
                ends = [pt for pts in mine for pt in pts]
                for q in [c for c in fam.children if c in lay.x] + [r for r in (fam.father, fam.mother) if r in lay.x]:
                    x0, y0, x1, y1 = frames[q]
                    self.assertTrue(any(x0 - 1 <= px <= x1 + 1 and y0 - 1 <= py <= y1 + 1 for px, py in ends),
                                    f"{e.positioning}: nothing of family {fam.id}'s line reaches {q}")

    def test_lines_stay_joined_when_dragged_and_hidden(self):
        pick = random.Random(11)
        for positioning in ("clusters", "bands"):
            for diagonal in (False, True):
                v = big_village()
                lay = ft.layout(v, ft.Edits(positioning=positioning, row_limit=2, diagonal_lines=diagonal))
                keys = {f.id: ft.family_key(v, f) for f in lay.families}
                pieces = [f"{keys[fid]}|{piece}" for _c, pts, fid, piece in ft.lines(lay) if len(pts) == 2]
                for _trial in range(15):
                    lay.edits.line_moves = {p: [pick.uniform(-60, 60), pick.uniform(-60, 60)]
                                            for p in pick.sample(pieces, min(6, len(pieces)))}
                    assert_connected(self, lay, ft.lines(lay))
                lay.edits.hidden = [f"line:{pieces[0]}"]
                shown = [i for i in ft.scene(lay, GAME, {}).items if isinstance(i, ft.Line) and i.piece == pieces[0]]
                self.assertEqual(shown, [])

    def test_a_dragged_portrait_takes_its_lines_along(self):
        v = big_village()
        e = ft.Edits(positioning="clusters")
        e.entries[ft.entry_key(v, v.people[10])] = {"dx": 40.0, "dy": 60.0}
        lay = ft.layout(v, e)
        plain = ft.layout(big_village(), ft.Edits(positioning="clusters"))
        self.assertAlmostEqual(lay.x[10], plain.x[10] + 40.0)
        self.assertAlmostEqual(lay.y[10], plain.y[10] + 60.0)
        assert_connected(self, lay, ft.lines(lay))

    def test_pages_shrink_and_alignment_still_apply(self):
        v = big_village()
        for positioning in ("clusters", "bands"):
            lay = ft.layout(v, ft.Edits(positioning=positioning, pages=[2]))
            self.assertEqual(lay.pages, 2)
            assert_connected(self, lay, ft.lines(lay))
            wide = ft.layout(v, ft.Edits(positioning=positioning))
            small = ft.layout(v, ft.Edits(positioning=positioning, fit_width=int(wide.width * 0.7)))
            self.assertLess(small.shrink, 1.0)
            self.assertLess(small.width, wide.width)
            for align in ("left", "right"):
                lay = ft.layout(v, ft.Edits(positioning=positioning, row_limit=2, row_align=align))
                assert_connected(self, lay, ft.lines(lay))
            lay = ft.layout(v, ft.Edits(positioning=positioning, row_valign="top"))
            ft.scene(lay, GAME, {})


class OthersGridTests(unittest.TestCase):
    LONERS = (20, 21, 22)

    def test_columns_make_a_grid(self):
        for positioning in LAYOUTS:
            lay = ft.layout(big_village(), ft.Edits(positioning=positioning, others_columns=2))
            self.assertEqual(sorted(lay.others), list(self.LONERS))
            self.assertEqual(len({lay.x[q] for q in self.LONERS}), 2, positioning)
            self.assertEqual(len({lay.y[q] for q in self.LONERS}), 2, positioning)
            one = ft.layout(big_village(), ft.Edits(positioning=positioning))
            self.assertEqual(len({one.x[q] for q in self.LONERS}), 3, "1: one row, as always")
            self.assertEqual(len({one.y[q] for q in self.LONERS}), 1)

    def test_either_side(self):
        for positioning in LAYOUTS:
            for side in ft.OTHERS_SIDES:
                lay = ft.layout(big_village(), ft.Edits(positioning=positioning, others_columns=2, others_side=side))
                tree = [q for q in lay.x if q not in lay.others]
                if side == "left":
                    self.assertLess(max(lay.x[q] for q in lay.others) + ft.NODE_W, min(lay.x[q] for q in tree))
                    self.assertGreater(lay.label_left, 0)
                    labels = [i for i in ft.scene(lay, GAME, {}).items if isinstance(i, ft.Text) and i.role == "labels"]
                    self.assertGreater(min(i.x for i in labels), max(lay.x[q] for q in lay.others) + ft.NODE_W)
                    self.assertLess(max(i.x for i in labels), min(lay.x[q] for q in tree))
                else:
                    self.assertGreater(min(lay.x[q] for q in lay.others), max(lay.x[q] for q in tree) + ft.NODE_W)
                heading = next(i for i in ft.scene(lay, GAME, {}).items if isinstance(i, ft.Text) and i.role == "others")
                self.assertEqual(heading.x, lay.others_left)

    def test_a_band_is_as_tall_as_its_grid(self):
        lay = ft.layout(big_village(), ft.Edits(positioning="rows", others_columns=1))
        tall = ft.layout(big_village(), ft.Edits(positioning="rows", others_columns=2))
        g = big_village().people[20].generation
        self.assertGreater(tall.bands[g], lay.bands[g])
        later = [q for q in tall.x if q not in tall.others and tall.village.people[q].generation > g]
        for q in later:
            self.assertGreater(tall.y[q], max(tall.y[r] for r in tall.others) + ft.NODE_H)


class SettingsTests(unittest.TestCase):
    def test_saved_clamped_and_remembered(self):
        back = ft.Edits._from_data(ft.Edits(positioning="clusters", others_columns=3, others_side="left").to_data())
        self.assertEqual((back.positioning, back.others_columns, back.others_side), ("clusters", 3, "left"))
        self.assertEqual(ft.Edits._from_data({"positioning": "bands"}).positioning, "bands")
        self.assertEqual(ft.Edits._from_data({"others_columns": 40}).others_columns, ft.OTHERS_COLUMNS_MAX)
        self.assertEqual(ft.Edits._from_data({"others_columns": -2}).others_columns, 1)
        self.assertEqual(ft.Edits._from_data({"others_side": "up"}).others_side, "right")
        self.assertEqual((ft.Edits().others_columns, ft.Edits().others_side), (1, "right"))
        for key in ("others_columns", "others_side", "positioning"):
            self.assertIn(key, ft.STYLE_KEYS)
        self.assertEqual(ft.styled(ft.style_of(back)).others_side, "left")

    def test_the_window_offers_them(self):
        source = (ROOT / "src" / "vv_genealogy_window.py").read_text(encoding="utf-8")
        for text in ("Other Members: columns", "others_columns_var.set(", "others_side_var.set(", "ft.OTHERS_SIDES"):
            self.assertIn(text, source)
        self.assertIn("Compact family clusters", ft.POSITIONING.values())
        self.assertIn("Family clusters in generation rows", ft.POSITIONING.values())


class OtherLayoutsUnchangedTests(unittest.TestCase):
    """The two layouts there were before, exactly as they were laid out (pinned from 4db1906f)."""
    PINS = {
        "dynamic/0": ({1: (300, 150), 2: (478, 150), 3: (656, 150), 4: (834, 150), 5: (300, 434), 6: (478, 434),
                       7: (656, 434), 8: (834, 434), 9: (478, 732), 10: (656, 732), 11: (300, 732), 12: (1075, 732)},
                      (1293, 1078), "9c27f76601e203ca759f31078b9b2ed827c8b60d"),
        "dynamic/2": ({1: (300, 150), 2: (478, 150), 3: (300, 352), 4: (478, 352), 5: (300, 650), 6: (478, 650),
                       7: (300, 852), 8: (478, 852), 9: (300, 1352), 10: (478, 1352), 11: (389, 1150), 12: (719, 1150)},
                      (937, 1698), "edc46aa74779f2a1d67500be4656b83b7571c199"),
        "rows/0": ({1: (300, 150), 2: (478, 150), 3: (656, 150), 4: (834, 150), 5: (300, 434), 6: (478, 434),
                    7: (656, 434), 8: (834, 434), 9: (389, 732), 10: (567, 732), 11: (745, 732), 12: (1100, 732)},
                   (1318, 1078), "c9e6c9709051dad2279c311d89970f92b5cf467e"),
        "rows/2": ({1: (300, 150), 2: (478, 150), 3: (300, 352), 4: (478, 352), 5: (300, 650), 6: (478, 650),
                    7: (300, 852), 8: (478, 852), 9: (300, 1150), 10: (478, 1150), 11: (389, 1352), 12: (719, 1150)},
                   (937, 1698), "ba1729931614f52105a70dabf5bc82f5dba7287a"),
    }

    def test_dynamic_and_rows_are_as_they_were(self):
        for name, (pos, size, lines_hash) in self.PINS.items():
            positioning, limit = name.split("/")
            lay = ft.layout(village(), ft.Edits(positioning=positioning, row_limit=int(limit)))
            self.assertEqual({q: (round(lay.x[q], 3), round(lay.y[q], 3)) for q in lay.x}, pos, name)
            self.assertEqual((round(lay.width, 3), round(lay.height, 3)), size, name)
            drawn = [(c, [(round(a, 3), round(b, 3)) for a, b in pts], fid, piece) for c, pts, fid, piece in ft.lines(lay)]
            self.assertEqual(hashlib.sha1(json.dumps(drawn).encode()).hexdigest(), lines_hash, name)


if __name__ == "__main__":
    unittest.main()
