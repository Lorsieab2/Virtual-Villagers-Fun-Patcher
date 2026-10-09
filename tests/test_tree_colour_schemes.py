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
        self.assertIn("Every part's colour scheme", self.SOURCE)
        self.assertIn("for k, (part, words) in enumerate(ft.SCHEME_PARTS.items()):", self.SOURCE)


if __name__ == "__main__":
    unittest.main()
