"""Family Tree Maker colour schemes and tabs (the owner, 2026-10-09): "increase the number of color options:
rainbow, alternating colors (2-7)" -- "for special marks, Plain portrait borders, Portrait insides, Family
lines, Detail lines"; and "organize the tree options better. Portrait editing in one place, text in another.
Why not have tabs?", with "Marks & Key" named "Special Marks"."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_family_tree as ft  # noqa: E402
from test_genealogy import village  # noqa: E402

GAME = "Virtual Villagers - A New Home"


def drawn(edits: ft.Edits):
    return ft.scene(ft.layout(village(), edits), GAME, {}).items


def portraits(items) -> dict:
    """Each villager's portrait: the first shape drawn for them (no marks here)."""
    out = {}
    for i in items:
        if isinstance(i, ft.Shape) and i.target and i.target[0] == "person":
            out.setdefault(i.pid, i)
    return out


def palette(e: ft.Edits) -> set:
    return set(e.special_palette[:e.special_count])


class SchemeColourTests(unittest.TestCase):
    def test_as_set_unless_chosen(self):
        for part in ft.SCHEME_PARTS:
            self.assertIsNone(ft.scheme_colour(ft.Edits(), part, 0.3, 2))

    def test_alternating_takes_the_chosen_count_by_turns(self):
        e = ft.Edits(schemes={"lines": "alternate"}, special_count=2)
        self.assertEqual([ft.scheme_colour(e, "lines", 0, j) for j in range(4)],
                         [e.special_palette[0], e.special_palette[1]] * 2)

    def test_rainbow_follows_the_rainbow_strength(self):
        bright = ft.Edits(schemes={"insides": "rainbow"}, rainbow_strength="bright")
        deep = ft.Edits(schemes={"insides": "rainbow"}, rainbow_strength="deep")
        self.assertEqual(ft.scheme_colour(bright, "insides", 0, 0), ft.RAINBOW[0])
        self.assertNotEqual(ft.scheme_colour(deep, "insides", 0, 0), ft.RAINBOW[0])

    def test_saved_and_remembered_with_the_look_and_nonsense_dropped(self):
        e = ft.Edits(schemes={"borders": "rainbow", "marks": "alternate"})
        self.assertEqual(ft.Edits._from_data(e.to_data()).schemes, {"borders": "rainbow", "marks": "alternate"})
        self.assertIn("schemes", ft.STYLE_KEYS)
        odd = ft.Edits._from_data({"schemes": {"borders": "plaid", "roof": "rainbow", "lines": "own"}})
        self.assertEqual(odd.schemes, {})
        self.assertEqual(ft.Edits._from_data({"schemes": "rainbow"}).schemes, {})


class SchemeSceneTests(unittest.TestCase):
    def test_borders_run_round_each_portrait_in_the_colours(self):
        e = ft.Edits(schemes={"borders": "alternate"}, special_count=3)
        items = drawn(e)
        people = list(portraits(items).values())
        self.assertTrue(people)
        self.assertTrue(all(s.width == 0 for s in people), "the outline is drawn in pieces instead")
        pieces = [i for i in items if isinstance(i, ft.Line) and i.target and i.target[0] == "person"]
        self.assertEqual({p.colour for p in pieces}, palette(e))
        self.assertEqual(len(pieces), 48 * len(people))

    def test_a_special_border_keeps_its_own_colours(self):
        e = ft.Edits(schemes={"borders": "rainbow"})
        for group in ft.GROUPS:
            e.borders[group] = "rope"
        items = drawn(e)
        self.assertTrue([i for i in items if isinstance(i, ft.Poly)], "the rope is drawn")
        self.assertFalse([i for i in items if isinstance(i, ft.Line) and i.target and i.target[0] == "person"])

    def test_insides_villager_by_villager_and_their_own_colour_wins(self):
        e = ft.Edits(schemes={"insides": "alternate"}, special_count=2)
        self.assertEqual({s.fill for s in portraits(drawn(e)).values()}, palette(e))
        v = village()
        lay = ft.layout(v, e)
        someone = next(iter(lay.x))
        e.entries[ft.entry_key(v, v.people[someone])] = {"fill": "#123456"}
        self.assertEqual(portraits(ft.scene(ft.layout(v, e), GAME, {}).items)[someone].fill, "#123456")

    def test_family_lines_family_by_family(self):
        e = ft.Edits(schemes={"lines": "alternate"}, special_count=2)
        lines = [i for i in drawn(e) if isinstance(i, ft.Line) and i.target and i.target[0] == "family"]
        self.assertTrue(lines)
        self.assertLessEqual({i.colour for i in lines}, palette(e))
        self.assertEqual({i.colour for i in drawn(ft.Edits(schemes={"lines": "alternate"}, special_count=1))
                          if isinstance(i, ft.Line) and i.target and i.target[0] == "family"} - palette(e), set())

    def test_detail_lines_line_by_line(self):
        e = ft.Edits(schemes={"details": "rainbow"}, detail_lines=True)
        for group in ft.GROUPS:
            e.shapes[group] = "scallop"
        details = [i for i in drawn(e) if isinstance(i, ft.Line) and i.target is None and i.opacity < 1]
        self.assertGreater(len({i.colour for i in details}), 2)


class PictureAndTextSizeTests(unittest.TestCase):
    """The owner, 2026-10-09: "i want to be able to resize the villager's picture and text within the shape"."""

    def faces_and_words(self, e, pid=None):
        items = drawn(e) if pid is None else ft.scene(ft.layout(village(), e), GAME, {}).items
        heads = {i.pid: i for i in items if isinstance(i, (ft.Head, ft.Shape)) and getattr(i, "fill", None) is not None
                 and i.pid is not None and isinstance(i, ft.Shape) and i.kind == "ellipse" and i.w < 200}
        words = {}
        for i in items:
            if isinstance(i, ft.Text) and i.role == "names":
                words.setdefault(i.pid, i)
        return heads, words

    def test_every_portraits_picture_and_text_grow(self):
        _h, small = self.faces_and_words(ft.Edits())
        big_e = ft.Edits(text_size=150.0)
        _h, big = self.faces_and_words(big_e)
        pid = next(iter(small))
        self.assertAlmostEqual(big[pid].size / small[pid].size, 1.5, delta=0.4)
        lay = ft.layout(village(), ft.Edits(picture_size=200.0))
        p = lay.village.people[pid]
        self.assertEqual(ft.inner_sizes(lay, p), (2.0, 1.0))

    def test_one_villagers_own_sizes_multiply_the_trees(self):
        v = village()
        e = ft.Edits(picture_size=50.0, text_size=200.0)
        p = next(iter(v.people.values()))
        e.entries[ft.entry_key(v, p)] = {"picture_scale": 300.0, "text_scale": 50.0}
        self.assertEqual(ft.inner_sizes(ft.layout(v, e), p), (1.5, 1.0))

    def test_saved_remembered_and_kept_in_range(self):
        e = ft.Edits(picture_size=140.0, text_size=80.0)
        back = ft.Edits._from_data(e.to_data())
        self.assertEqual((back.picture_size, back.text_size), (140.0, 80.0))
        self.assertIn("picture_size", ft.STYLE_KEYS)
        self.assertIn("text_size", ft.STYLE_KEYS)
        odd = ft.Edits._from_data({"picture_size": 9999, "text_size": -5,
                                   "entries": {"A|1|1": {"picture_scale": 250, "mark": "x"}}})
        self.assertEqual((odd.picture_size, odd.text_size), (ft.PICTURE_SCALE_MAX, ft.TEXT_SCALE_MIN))
        self.assertEqual(odd.entries["A|1|1"]["picture_scale"], 250.0)

    def test_the_lines_space_out_with_bigger_words(self):
        def gaps(e):
            items = drawn(e)
            pid = next(i.pid for i in items if isinstance(i, ft.Text) and i.role == "names")
            ys = sorted(i.y for i in items if isinstance(i, ft.Text) and i.pid == pid and i.role in ("names", "portraits"))
            return ys[1] - ys[0]
        self.assertAlmostEqual(gaps(ft.Edits(text_size=200.0)) / gaps(ft.Edits()), 2.0, delta=0.05)


class RowLineUpTests(unittest.TestCase):
    """The owner, 2026-10-09: "justify portraits ... top middle bottom ... left right center" (each row)."""

    def sized(self, **settings):
        v = village()
        e = ft.Edits(**settings)
        lay = ft.layout(v, e)
        gen1 = [q for q in lay.x if v.people[q].generation == min(p.generation for p in v.people.values())
                and q not in lay.others]
        big = gen1[0]
        e.entries[ft.entry_key(v, v.people[big])] = {"w": 200.0, "h": 300.0}
        return v, e, gen1

    def frames(self, v, e, gen1):
        lay = ft.layout(v, e)
        return {q: lay.frame(q) for q in gen1}

    def test_tops_and_bottoms_line_up_with_the_tallest(self):
        v, e, gen1 = self.sized(row_valign="top")
        tops = {round(f[1], 3) for f in self.frames(v, e, gen1).values()}
        self.assertEqual(len(tops), 1, "every top level")
        e.row_valign = "bottom"
        bottoms = {round(f[1] + f[3], 3) for f in self.frames(v, e, gen1).values()}
        self.assertEqual(len(bottoms), 1, "every bottom level")
        e.row_valign = "middle"
        middles = {round(f[1] + f[3] / 2, 3) for f in self.frames(v, e, gen1).values()}
        self.assertEqual(len(middles), 1, "every middle level, as before")

    def test_rows_go_left_centre_or_right_across_the_tree(self):
        v = village()

        def edges(align):
            lay = ft.layout(v, ft.Edits(row_align=align, positioning="rows"))
            out = {}
            for q in lay.x:
                if q not in lay.others:
                    g = v.people[q].generation
                    lo, hi = out.get(g, (1e9, -1e9))
                    out[g] = (min(lo, lay.x[q]), max(hi, lay.x[q]))
            return out
        lefts = {lo for lo, _hi in edges("left").values()}
        rights = {hi for _lo, hi in edges("right").values()}
        self.assertEqual(len(lefts), 1)
        self.assertEqual(len(rights), 1)
        self.assertEqual(edges("centre"), edges("arranged"), "straight rows are centred already")

    def test_saved_and_remembered(self):
        back = ft.Edits._from_data(ft.Edits(row_align="right", row_valign="bottom").to_data())
        self.assertEqual((back.row_align, back.row_valign), ("right", "bottom"))
        self.assertIn("row_align", ft.STYLE_KEYS)
        odd = ft.Edits._from_data({"row_align": "diagonal", "row_valign": 3})
        self.assertEqual((odd.row_align, odd.row_valign), ("arranged", "middle"))


class KeyPluralTests(unittest.TestCase):
    """The owner, 2026-10-09: "monstera leafs; Babies on the way: butterflys.  ahem. grammar." """

    def test_every_shape_in_the_key_is_good_english(self):
        cases = {"monstera": "Monstera leaves", "butterfly": "butterflies", "leaf": "leaves", "starfish": "starfish",
                 "fish_left": "fish (facing left)", "bananas": "bunches of bananas", "oval_wide": "ovals (horizontal)",
                 "wave_circle": "ocean waves in a circle", "turtle_h": "turtle shells (on their sides)",
                 "ship_wheel": "ship's wheels", "cross": "crosses", "x": "Xs", "arch": "arches",
                 "hibiscus": "hibiscus flowers", "circle": "circles"}
        for shape, words in cases.items():
            self.assertEqual(ft.plural(shape), words)
        for shape in ft.PORTRAIT_SHAPES:
            self.assertNotRegex(ft.plural(shape), r"(leafs|ys|fishs|\)s)\b", shape)


class TabTests(unittest.TestCase):
    SOURCE = (ROOT / "src" / "vv_genealogy_window.py").read_text(encoding="utf-8")

    def test_the_options_sit_on_their_own_tabs_in_order(self):
        for name in ("Portraits", "Text", "Tree Layout", "Special Marks"):
            self.assertIn(f'"{name}"', self.SOURCE)
        self.assertNotIn('"Whole Tree"', self.SOURCE)
        self.assertNotIn('"Marks & Key"', self.SOURCE)
        order = ("Selected Villagers", "Portraits", "Text", "Fonts", "Tree Layout", "Special Marks",
                 "Page Background", "Add Pictures & Text Boxes")
        start = self.SOURCE.index("    TAB_ORDER = (")
        listed = self.SOURCE[start:self.SOURCE.index(")", start)]
        self.assertEqual([n for n in order if f'"{n}"' in listed], list(order))
        self.assertLess(listed.index('"Portraits"'), listed.index('"Text"'))
        self.assertIn("self._order_tabs()", self.SOURCE)

    def test_every_part_has_a_scheme_box(self):
        self.assertIn("Rainbow and alternating colours", self.SOURCE)
        self.assertIn("for k, (part, words) in enumerate(ft.SCHEME_PARTS.items()):", self.SOURCE)


if __name__ == "__main__":
    unittest.main()
