"""A generation label's box holds every line it shows (the owner, 2026-10-10, A New Home's Kalahuna Tribe 1,
page 2: "6. Generation 6 / 26 total: 10 females, 16 males / 26 living / 2 upcoming" -- the box was sized for
three lines and "2 upcoming" was drawn below it), at any font, size, bold, italic or wording, in every layout,
without running into a portrait; "1 male", not "1 males"; and each page's name names the generations it
labels."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_family_tree as ft  # noqa: E402
import vv_genealogy as gen  # noqa: E402
from test_tree_fixed_face_size import owner_village  # noqa: E402
from test_tree_packed import LAYOUTS  # noqa: E402

GAME = "Virtual Villagers - A New Home"
PICTURE = "asset:sunset-over-the-sea.png"       # the owner's: the labels drawn on plates


def labelled(lay):
    """Each generation's plate, words and line, as drawn."""
    sc = ft.scene(lay, GAME, {})
    out: dict[int, dict] = {}
    for item in sc.items:
        name = getattr(item, "move", "") or ""
        if not name.startswith("label") or not name[5:].isdigit():
            continue
        g = out.setdefault(int(name[5:]), {"plate": None, "texts": [], "line": None})
        if isinstance(item, ft.Shape):
            g["plate"] = item
        elif isinstance(item, ft.Text):
            g["texts"].append(item)
        elif isinstance(item, ft.Line):
            g["line"] = item
    return sc, out


def text_box(t) -> tuple[float, float, float, float]:
    width = ft.text_width(t.text, t.size, t.bold, t.font, t.italic)
    return t.x, t.y - t.size, t.x + width, t.y + t.size * 0.3


def meets(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


class GenerationLabelBoxTests(unittest.TestCase):
    def check(self, edits: ft.Edits, village=None):
        village = village or owner_village()
        lay = ft.layout(village, edits)
        sc, labels = labelled(lay)
        self.assertTrue(labels)
        plates = []
        for g, parts in labels.items():
            plate, texts, line = parts["plate"], parts["texts"], parts["line"]
            self.assertIsNotNone(plate, g)
            box = (plate.x, plate.y, plate.x + plate.w, plate.y + plate.h)
            for t in texts:
                left, top, right, bottom = text_box(t)
                self.assertGreaterEqual(top, box[1], (g, t.text))
                self.assertLessEqual(bottom, box[3], (g, t.text))
                self.assertGreaterEqual(left, box[0], (g, t.text))
                self.assertLessEqual(right, box[2], (g, t.text))
            ys = [py for _px, py in line.points]
            self.assertLessEqual(min(ys), box[1], g)           # the upright line beside all of it
            self.assertGreaterEqual(max(ys), box[3], g)
            self.assertGreater(line.points[0][0], box[2], g)   # past the plate, not through it
            for pid, pbox in sc.boxes.items():
                x0, y0, w, h = pbox
                self.assertFalse(meets(box, (x0, y0, x0 + w, y0 + h)), (g, pid, "a label over a portrait"))
            plates.append(box)
        for a in plates:
            for b in plates:
                if a is not b:
                    self.assertFalse(meets(a, b), "two labels overlap")
        return lay, labels

    def test_the_owners_upcoming_line_is_inside_its_box(self):
        lay, labels = self.check(ft.Edits(background_image=PICTURE, positioning="packed_generations"))
        g = lay.village.people[30].generation
        self.assertEqual([t.text for t in labels[g]["texts"]][-1], "1 upcoming")

    def test_large_bold_italic_fonts_and_custom_words(self):
        for layout in [n for n in LAYOUTS if n != "packed_families"]:    # (packed families: no labels)
            for style in ({"scale": 250}, {"scale": 300, "bold": True, "italic": True, "font": "Georgia"},
                          {"scale": 180, "script": "sub"}, {"scale": 200, "script": "super"}):
                with self.subTest(layout=layout, style=style):
                    self.check(ft.Edits(background_image=PICTURE, positioning=layout, styles={"labels": style}))
            with self.subTest(layout=layout, custom=True):
                self.check(ft.Edits(background_image=PICTURE, positioning=layout, styles={"labels": {"scale": 150}},
                                    generations={"2": ["The children of the founders, who built the village",
                                                       "line two", "line three", "line four", "line five",
                                                       "line six"]}))

    def test_equal_and_fixed_sizes_and_others_on_the_left(self):
        for extra in ({"fixed_face_size": True}, {"others_side": "left"},
                      {"sizes": {"Male": [40.0, 40.0], "Female": [40.0, 40.0], "Upcoming": [40.0, 40.0]}}):
            with self.subTest(extra=extra):
                self.check(ft.Edits(background_image=PICTURE, styles={"labels": {"scale": 220}}, **extra))

    def test_the_usual_label_is_where_it_always_was(self):
        box = ft.label_box(ft.Edits(), ["1. Generation 1", "5 total: 3 females, 2 males", "0 living"])
        self.assertEqual(box.baselines, [40, 62, 84])
        self.assertEqual(box.width, 228)
        self.assertEqual(box.line_x, 250)

    def test_one_male_one_female(self):
        v = owner_village()
        lay = ft.layout(v, ft.Edits())
        words = {g: ft.default_label_parts(lay, g)["total"] for g in lay.rows}
        for g, text in words.items():
            people = [v.people[q] for q in lay.x if v.people[q].generation == g and not v.people[q].upcoming]
            men = sum(p.sex == "Male" for p in people)
            women = sum(p.sex == "Female" for p in people)
            self.assertIn(f"{women} female{'' if women == 1 else 's'},", text)
            self.assertTrue(text.endswith(f"{men} male{'' if men == 1 else 's'}"), text)
        self.assertEqual(words[1], "2 total: 1 female, 1 male")
        self.assertNotIn("1 males", " ".join(words.values()))

    def test_each_page_names_the_generations_it_labels(self):
        v = owner_village()
        edits = ft.Edits(page_generations=2)
        spans = ft.page_spans(edits, v)
        self.assertGreater(len(spans), 1)
        for page, (lo, hi) in enumerate(spans):
            lay = ft.layout(v, edits, page)
            _sc, labels = labelled(lay)
            self.assertEqual((min(labels), max(labels)), (lo, hi), page)

    def test_a_generation_of_babies_on_the_way_only(self):
        v = owner_village()
        last = max(p.generation for p in v.people.values())
        v.people[31] = gen.Person(31, "Upcoming child", -1, -1, upcoming=True, mother=17, father=None,
                                  generation=last + 1)
        v.base_generation[31] = last + 1
        edits = ft.Edits(background_image=PICTURE)
        lay, labels = self.check(edits, v)
        self.assertEqual([t.text for t in labels[last + 1]["texts"]][1:],
                         ["0 total: 0 females, 0 males", "0 living", "1 upcoming"])
        self.assertEqual(ft.page_spans(edits, v)[-1][1], last + 1)


if __name__ == "__main__":
    unittest.main()
