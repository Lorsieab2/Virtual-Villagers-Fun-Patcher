"""Family Tree Maker options of 2026-10-09 (the owner): spacing between generations, "Founder", text
alignment, keeping words inside the shape, and the new portrait shapes; and where the tree keeps its
files after the save folders' new names (src/vv_save_layout.py)."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import vv_family_tree as ft  # noqa: E402
import vv_save_layout as layout  # noqa: E402


class SettingsTests(unittest.TestCase):
    def test_new_settings_are_saved_and_read_back(self):
        e = ft.Edits()
        e.row_gap, e.show_founder, e.text_align, e.text_valign, e.text_inside = 75.0, True, "right", "bottom", True
        back = ft.Edits._from_data(e.to_data())
        self.assertEqual((back.row_gap, back.show_founder, back.text_align, back.text_valign, back.text_inside),
                         (75.0, True, "right", "bottom", True))
        self.assertFalse(back.centre_heads)               # an older build reads "bottom" as not centred

    def test_an_older_file_keeps_its_centring(self):
        self.assertEqual(ft.Edits._from_data({"centre_heads": False}).text_valign, "top")
        self.assertEqual(ft.Edits._from_data({}).text_valign, "middle")
        self.assertEqual(ft.Edits._from_data({}).text_align, "centre")

    def test_the_settings_are_part_of_the_remembered_look(self):
        for key in ("row_gap", "show_founder", "text_align", "text_valign", "text_inside"):
            self.assertIn(key, ft.STYLE_KEYS)


class ShapeTests(unittest.TestCase):
    NEW = ("trapezoid", "pentagon", "star4", "plump_star", "star6", "slim_star6", "arrow_h", "arrow_v", "arch",
           "scallop", "snail", "oval_wide", "hibiscus", "sand_dollar", "turtle_v", "turtle_h", "mermaid_tail",
           "fish_right", "fish_left", "wave_circle", "conch", "starfish", "ship_wheel", "coconut", "bananas", "monstera", "anchor", "mermaid_tail_h")

    def test_the_owners_pictures_have_their_detail_lines(self):
        for kind in ("scallop", "snail", "sand_dollar", "turtle_v", "mermaid_tail", "fish_left", "conch",
                     "starfish", "star", "flower"):
            with self.subTest(kind=kind):
                self.assertTrue(ft.details(kind))
        self.assertEqual(len(ft.decor("hibiscus")), 5)            # its stamen and pollen, drawn like the border
        self.assertEqual(len(ft.decor("wave_circle")), 1)
        self.assertEqual(ft.details("rect"), ())

    def test_the_detail_settings_are_saved_and_read_back(self):
        e = ft.Edits()
        e.detail_lines, e.detail_colour, e.detail_opacity, e.detail_width = False, "#123456", 70.0, 2.0
        back = ft.Edits._from_data(e.to_data())
        self.assertEqual((back.detail_lines, back.detail_colour, back.detail_opacity, back.detail_width),
                         (False, "#123456", 70.0, 2.0))
        self.assertEqual(ft.Edits._from_data({"detail_colour": "not a colour"}).detail_colour, "")

    def test_each_new_shape_is_offered_and_drawn_at_its_own_proportions(self):
        for kind in self.NEW:
            with self.subTest(kind=kind):
                self.assertIn(kind, ft.PORTRAIT_SHAPES)
                pts = ft.outline(kind, 0, 0, 100, 100)
                xs, ys = zip(*pts)
                self.assertAlmostEqual(min(xs), 0, delta=0.5)
                self.assertAlmostEqual(max(xs), 100, delta=0.5)
                self.assertAlmostEqual(min(ys), 0, delta=0.5)
                self.assertAlmostEqual(max(ys), 100, delta=0.5)
                self.assertGreater(ft.ASPECTS[kind], 0)


class RightAlignedTextTests(unittest.TestCase):
    def test_right_aligned_words_end_at_x(self):
        t = ft.Text(200, 50, "Founder", 10, "#000000", end=True)
        left, _top, right, _bottom = ft._extent(t)
        self.assertAlmostEqual(right, 200)
        self.assertLess(left, 200)


class SaveLayoutTests(unittest.TestCase):
    def test_a_new_name_maps_back_to_the_old_one(self):
        d, g = layout.DATA, layout.LOGS
        self.assertEqual(layout.old_name(f"{g}\\Deaths and Disappearances\\x.txt"), f"{g}\\Deaths\\x.txt")
        self.assertEqual(layout.old_name(f"{d}\\Family Tree Edits\\Virtual Villagers 1 Family Tree Edits - Save 2.json"),
                         f"{d}\\Genealogy\\Virtual Villagers 1 Genealogy Edits - Save 2.json")
        self.assertEqual(layout.old_name(f"{d}\\Village Statistics\\Villagers Counted - Save 1.dat"),
                         f"{d}\\Village Statistics\\Village Roster - Save 1.dat")
        self.assertIsNone(layout.old_name(f"{d}\\Village Elders\\Village Elders - Save 1.dat"))

    def test_the_tree_finds_its_edits_under_either_name_and_the_move_keeps_every_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            old = folder / layout.DATA / "Genealogy" / "Virtual Villagers 1 Genealogy Edits - Save 1.json"
            old.parent.mkdir(parents=True)
            old.write_text("{}")
            deaths = folder / layout.LOGS / "Deaths" / "Virtual Villagers 1 Deaths Log 1.txt"
            deaths.parent.mkdir(parents=True)
            deaths.write_text("Death 1")
            (deaths.parent / (deaths.name + ".before-v1.35.61-repair")).write_text("copy")
            self.assertEqual(ft.Edits.path(folder, 1, 1), old)
            layout.migrate(folder)
            new = folder / layout.DATA / "Family Tree Edits" / "Virtual Villagers 1 Family Tree Edits - Save 1.json"
            self.assertEqual(ft.Edits.path(folder, 1, 1), new)
            self.assertTrue(new.is_file() and not old.exists())
            self.assertTrue((folder / layout.LOGS / "Deaths and Disappearances" / deaths.name).is_file())
            self.assertTrue((folder / layout.DATA / layout.COPIES / layout.LOGS / "Deaths and Disappearances"
                             / (deaths.name + ".before-v1.35.61-repair")).is_file())
            self.assertEqual(layout.migrate(folder), [])          # once only


class SpecialBorderAndTextRoomTests(unittest.TestCase):
    def test_every_special_border_goes_round_every_shape(self):
        self.assertEqual(list(ft.SPECIAL_BORDERS), ["rope", "vine_leaves", "vine_flowers", "vine_both"])
        for border in ft.SPECIAL_BORDERS:
            self.assertIn(border, ft.BORDERS)
            for kind in ft.PORTRAIT_SHAPES:
                with self.subTest(border=border, kind=kind):
                    lines = ft.special_border(border, kind, (0, 0, 100, 140, 0.0), ft.corner_radius(kind))
                    self.assertGreater(len(lines), 2)        # the rope's or the vine's line and what is on it
        kept = ft.Edits._from_data({"borders": {"Male": "stone_palm"}}).borders.get("Male")
        self.assertIn(kept, ft.BORDERS)                      # a stone tablet saved before: the plain border

    def test_text_room_auto_boxes_every_shape(self):
        frame = (0, 0, 100, 100, 0.0)
        outline = ft.shape_points("monstera", 0, 0, 100, 100)
        self.assertEqual(len(ft.text_room_points("auto", "circle", outline, frame)), 48)     # the oval filling it
        self.assertIs(ft.text_room_points("shape", "circle", outline, frame), outline)
        boxed = ft.text_room_points("auto", "monstera", outline, frame)
        self.assertEqual(len(boxed), 4)
        self.assertEqual(len(ft.text_room_points("oval", "circle", outline, frame)), 48)
        self.assertEqual(ft.Edits._from_data(ft.Edits(text_room="oval").to_data()).text_room, "oval")
        self.assertEqual(ft.Edits._from_data({"text_room": "nonsense"}).text_room, "auto")

class SpecialBorderColourTests(unittest.TestCase):
    def test_the_colour_settings_are_saved_and_read_back(self):
        e = ft.Edits()
        e.special_mode, e.special_count = "gradient", 5
        e.special_pick = {"rope": "#123456", "flower": "#abcdef"}
        back = ft.Edits._from_data(e.to_data())
        self.assertEqual((back.special_mode, back.special_count, back.special_pick), ("gradient", 5, e.special_pick))
        self.assertEqual(ft.Edits._from_data({"special_mode": "nope", "special_count": 40}).special_mode, "natural")
        self.assertEqual(ft.Edits._from_data({"special_count": 40}).special_count, 7)

    def test_natural_colours_and_the_modes_colour_the_parts(self):
        def fills(border, mode):
            e = ft.Edits()
            e.special_mode = mode
            items = ft.special_border(border, "circle", (0, 0, 200, 200, 0.0), 0.0, e)
            return {i.fill for i in items if isinstance(i, ft.Poly) and i.fill}
        self.assertIn(ft.NATURAL["rope"], fills("rope", "natural"))
        self.assertIn(ft.NATURAL["flower"], fills("vine_flowers", "natural"))
        self.assertGreater(len(fills("vine_flowers", "rainbow")), 6)          # a rainbow of flowers

    def test_every_export_draws_a_special_border(self):
        import types
        sys.path.insert(0, str(Path(__file__).resolve().parents[0]))
        from test_genealogy import village
        e = ft.Edits(borders={g: "vine_both" for g in ft.GROUPS})
        sc = ft.scene(ft.layout(village(), e), "A New Home", {})
        self.assertTrue(any(isinstance(i, ft.Poly) for i in sc.items))
        self.assertIn('fill-rule="evenodd"', ft.to_svg(sc, {}))


if __name__ == "__main__":
    unittest.main()
