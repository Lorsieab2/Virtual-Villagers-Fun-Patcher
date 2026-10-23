"""The box behind each portrait's name and age words (the owner, 2026-10-23: "Text box background" on the
Faces & Text tab): a colour, an opacity (0 %: none, as every tree has it), drawn under the words by default
and over the shapes when asked, for everyone or one group (Edits.group_opts)."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_family_tree as ft  # noqa: E402
from test_genealogy import village  # noqa: E402

TITLE = "Virtual Villagers - A New Home"
MALE, FEMALE = 9, 10


def items(edits: ft.Edits) -> list:
    return ft.scene(ft.layout(village(), edits), TITLE, {}).items


def boxes(edits: ft.Edits, pid: int | None = None) -> list:
    return [i for i in items(edits) if isinstance(i, ft.Shape) and i.radius == 5 and i.width == 0
            and i.target is None and (pid is None or i.pid == pid)]


def words(edits: ft.Edits, pid: int) -> list:
    return [i for i in items(edits) if isinstance(i, ft.Text) and i.pid == pid and i.role in ("names", "portraits")]


class TextBoxTests(unittest.TestCase):
    def test_default_draws_nothing_and_changes_nothing(self):
        plain, zero = ft.Edits(), ft.Edits(text_box_colour="#123456", text_box_over=True)
        self.assertEqual(plain.text_box_opacity, 0.0)
        self.assertEqual(boxes(plain), [])
        self.assertEqual(boxes(zero), [])
        self.assertEqual(items(plain), items(zero))              # at 0 % neither colour nor order changes anything

    def test_colour_and_opacity_applied_under_the_words(self):
        edits = ft.Edits(text_box_colour="#ff8800", text_box_opacity=40.0)
        found = boxes(edits, MALE)
        self.assertEqual(len(found), 1)
        box = found[0]
        self.assertEqual((box.fill, box.stroke), ("#ff8800", "#ff8800"))
        self.assertAlmostEqual(box.opacity, 0.4 * ft.see_through(edits, "portraits"))
        every = items(edits)
        lines = words(edits, MALE)
        self.assertEqual(every.index(box) + 1, every.index(lines[0]))      # just under its words ...
        shape = next(i for i in every if isinstance(i, ft.Shape) and i.target == ("person", MALE))
        self.assertLess(every.index(shape), every.index(box))              # ... over its own shape
        for t in lines:                                                   # it holds every line
            self.assertLess(box.x, t.x)
            self.assertLess(box.y, t.y - t.size * 0.5)
            self.assertGreater(box.y + box.h, t.y)

    def test_overlay_puts_boxes_and_words_after_every_shape(self):
        edits = ft.Edits(text_box_opacity=100.0, text_box_over=True, shapes={"Male": "star", "Female": "star", "Upcoming": "diamond"})
        every = items(edits)
        found = boxes(edits)
        self.assertTrue(found)
        first = min(every.index(b) for b in found)
        later = [i for i in every[first:] if getattr(i, "pid", None) is not None]
        self.assertTrue(all(isinstance(i, (ft.Text, ft.Shape)) and (isinstance(i, ft.Text) or i in found)
                            for i in later))
        under = ft.Edits(text_box_opacity=100.0, shapes={"Male": "star", "Female": "star", "Upcoming": "diamond"})
        every = items(under)
        first = min(every.index(b) for b in boxes(under))
        self.assertTrue(any(isinstance(i, ft.Shape) and i.target == ("person", i.pid) for i in every[first:]))

    def test_by_group(self):
        edits = ft.Edits()
        edits.group_opts = {"Male": {"text_box_opacity": 80.0, "text_box_colour": "#00ff00", "text_box_over": True}}
        self.assertEqual(len(boxes(edits, MALE)), 1)
        self.assertEqual(boxes(edits, FEMALE), [])
        self.assertEqual(boxes(edits, MALE)[0].fill, "#00ff00")
        back = ft.Edits._from_data(json.loads(json.dumps(edits.to_data())))
        self.assertEqual(back.group_opts, edits.group_opts)
        junk = ft.clean_group_opts({"Male": {"text_box_colour": "red", "text_box_opacity": 400, "text_box_over": 1}})
        self.assertEqual(junk, {"Male": {"text_box_opacity": 100.0}})

    def test_saved_and_old_trees_load_with_defaults(self):
        edits = ft.Edits(text_box_colour="#abcdef", text_box_opacity=35.0, text_box_over=True)
        back = ft.Edits._from_data(json.loads(json.dumps(edits.to_data())))
        self.assertEqual((back.text_box_colour, back.text_box_opacity, back.text_box_over),
                         ("#abcdef", 35.0, True))
        old = ft.Edits._from_data({"format": 1, "title": "Old"})
        self.assertEqual((old.text_box_colour, old.text_box_opacity, old.text_box_over), ("#ffffff", 0.0, False))
        bad = ft.Edits._from_data({"text_box_colour": "nope", "text_box_opacity": "x", "text_box_over": "yes"})
        self.assertEqual((bad.text_box_colour, bad.text_box_opacity, bad.text_box_over), ("#ffffff", 0.0, False))
        for key in ("text_box_colour", "text_box_opacity", "text_box_over"):
            self.assertIn(key, ft.STYLE_KEYS)
            self.assertIn(key, ft.GROUP_FIELDS)

    def test_exports_carry_the_box(self):
        edits = ft.Edits(text_box_colour="#12ab34", text_box_opacity=50.0)
        scene = ft.scene(ft.layout(village(), edits), TITLE, {})
        svg = ft.to_svg(scene, {})
        self.assertIn('fill="#12ab34"', svg)
        self.assertIn('opacity="0.5"', svg)
        self.assertNotIn('#12ab34', ft.to_svg(ft.scene(ft.layout(village(), ft.Edits()), TITLE, {}), {}))


if __name__ == "__main__":
    unittest.main()
