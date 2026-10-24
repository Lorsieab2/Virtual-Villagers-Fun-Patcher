"""The border round each portrait's text box (the owner: "border options for the text boxes, like the portrait
shapes"): the portraits' border choices -- plain, dotted, dashed, the special rope and vines -- a weight (0, the
default: none, so every tree looks as it did) and a colour (Automatic: the portrait's own), round the box's
rounded corners, for everyone or one group; saved, read back, undone, drawn in the editor and every export."""
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_family_tree as ft  # noqa: E402
import vv_gdiplus  # noqa: E402
from test_genealogy import village  # noqa: E402
from test_tree_auto_line_colours import read_png  # noqa: E402

TITLE = "Virtual Villagers - A New Home"
MALE, FEMALE = 9, 10
RED = "#ff0000"
ODD = "#fe0102"                         # a colour nothing else on the tree has


def scene(edits: ft.Edits):
    return ft.scene(ft.layout(village(), edits), TITLE, {})


def borders(items: list, pid: int | None = None) -> list:
    """The plain text box borders drawn (a rounded rect of the box's radius with a stroke and no fill)."""
    return [i for i in items if isinstance(i, ft.Shape) and i.radius == ft.TEXT_BOX_RADIUS and i.fill is None
            and i.width > 0 and (pid is None or i.pid == pid)]


def words(items: list, pid: int) -> list:
    return [i for i in items if isinstance(i, ft.Text) and i.pid == pid and i.role in ("names", "portraits") and i.text]


class TextBoxBorderTests(unittest.TestCase):
    def test_default_draws_nothing_and_changes_nothing(self):
        plain = ft.Edits()
        self.assertEqual((plain.text_box_border, plain.text_box_border_colour, plain.text_box_border_width),
                         ("thin", "", 0.0))
        dressed = ft.Edits(text_box_border="rope", text_box_border_colour="#123456")    # weight 0: none
        self.assertEqual(scene(plain).items, scene(dressed).items)
        self.assertEqual(borders(scene(plain).items), [])

    def test_a_border_round_the_words_with_or_without_a_box(self):
        for opacity in (0.0, 60.0):
            with self.subTest(opacity=opacity):
                edits = ft.Edits(text_box_opacity=opacity, text_box_border="dashed", text_box_border_width=3.0,
                                 text_box_border_colour=RED)
                every = scene(edits).items
                found = borders(every, MALE)
                self.assertEqual(len(found), 1)
                line = found[0]
                self.assertEqual((line.stroke, line.width, line.dash, line.kind), (RED, 3.0, "dashed", "rect"))
                lines = words(every, MALE)
                self.assertLess(every.index(line), every.index(lines[0]))       # under its words
                for t in lines:
                    self.assertLess(line.x, t.x)
                    self.assertGreater(line.y + line.h, t.y)
                if opacity:                                                   # the box first, then its border
                    box = every[every.index(line) - 1]
                    self.assertEqual((box.fill, box.width), ("#ffffff", 0))
                    self.assertEqual((box.x, box.y, box.w, box.h, box.radius),
                                     (line.x, line.y, line.w, line.h, line.radius))

    def test_automatic_colour_is_the_portraits(self):
        every = scene(ft.Edits(text_box_border="thick", text_box_border_width=2.0)).items
        portrait = next(i for i in every if isinstance(i, ft.Shape) and i.target == ("person", MALE))
        self.assertEqual(borders(every, MALE)[0].stroke, portrait.stroke)

    def test_special_borders_follow_the_boxs_rounded_outline(self):
        edits = ft.Edits(text_box_border="vine_both", text_box_border_width=1.0)
        every = scene(edits).items
        self.assertEqual(borders(every, MALE), [])
        lines = words(every, MALE)
        first = every.index(lines[0])
        vine = [i for i in every[:first] if isinstance(i, (ft.Poly, ft.Line)) and i.pid == MALE
                and getattr(i, "block", (None, None))[1] == "rect"]
        self.assertTrue(vine)
        left = min(t.x for t in lines)
        xs = [x for i in vine for x, _y in i.points]
        self.assertLess(min(xs), left)                  # round the words, outside them
        # It is the special border round a rounded rect of the box's radius.
        self.assertTrue(all(i.block[4] == ft.TEXT_BOX_RADIUS for i in vine))
        rope = ft.Edits(text_box_border="rope", text_box_border_width=1.0)
        self.assertTrue([i for i in scene(rope).items if getattr(i, "block", (None,))[0] == "rope"])

    def test_drawn_over_the_shapes_with_its_box(self):
        edits = ft.Edits(text_box_opacity=100.0, text_box_over=True, text_box_border="thick",
                         text_box_border_width=2.0, shapes={"Male": "star", "Female": "star", "Upcoming": "diamond"})
        every = scene(edits).items
        found = borders(every)
        self.assertTrue(found)
        first = min(every.index(b) for b in found)
        later = [i for i in every[first:] if getattr(i, "pid", None) is not None]
        self.assertFalse([i for i in later if isinstance(i, ft.Shape) and i.target == ("person", i.pid)])

    def test_by_group_and_saved(self):
        edits = ft.Edits()
        edits.group_opts = {"Male": {"text_box_border": "dotted", "text_box_border_width": 2.5,
                                     "text_box_border_colour": "#00ff00"}}
        every = scene(edits).items
        self.assertEqual(len(borders(every, MALE)), 1)
        self.assertEqual(borders(every, FEMALE), [])
        self.assertEqual(borders(every, MALE)[0].dash, "dotted")
        back = ft.Edits._from_data(json.loads(json.dumps(edits.to_data())))
        self.assertEqual(back.group_opts, edits.group_opts)
        junk = ft.clean_group_opts({"Male": {"text_box_border": "zigzag", "text_box_border_width": 99,
                                             "text_box_border_colour": "red"}})
        self.assertEqual(junk, {"Male": {"text_box_border_width": 20.0}})
        tree = ft.Edits(text_box_border="vine_leaves", text_box_border_colour="#abcdef", text_box_border_width=4.0)
        back = ft.Edits._from_data(json.loads(json.dumps(tree.to_data())))
        self.assertEqual((back.text_box_border, back.text_box_border_colour, back.text_box_border_width),
                         ("vine_leaves", "#abcdef", 4.0))
        old = ft.Edits._from_data({"format": 1, "title": "Old"})
        self.assertEqual((old.text_box_border, old.text_box_border_colour, old.text_box_border_width),
                         ("thin", "", 0.0))
        bad = ft.Edits._from_data({"text_box_border": 3, "text_box_border_colour": "nope",
                                   "text_box_border_width": "x"})
        self.assertEqual((bad.text_box_border, bad.text_box_border_colour, bad.text_box_border_width),
                         ("thin", "", 0.0))
        for key in ("text_box_border", "text_box_border_colour", "text_box_border_width"):
            self.assertIn(key, ft.STYLE_KEYS)
            self.assertIn(key, ft.GROUP_FIELDS)
        # The look carried to the next new tree.
        self.assertEqual(ft.styled(ft.style_of(tree)).text_box_border_width, 4.0)

    def test_a_transparent_border_stays_transparent_when_saved_and_opened(self):
        """Codex, #606: Transparent came back as Automatic (everyone's) or was dropped (a group's)."""
        tree = ft.Edits(text_box_border="thick", text_box_border_width=3.0, text_box_border_colour=ft.TRANSPARENT)
        tree.group_opts = {"Male": {"text_box_border_colour": ft.TRANSPARENT, "text_box_border_width": 2.0}}
        back = ft.Edits._from_data(json.loads(json.dumps(tree.to_data())))
        self.assertEqual(back.text_box_border_colour, ft.TRANSPARENT)
        self.assertEqual(back.group_opts, tree.group_opts)
        self.assertEqual(ft.clean_group_opts({"Female": {"text_box_border_colour": ft.TRANSPARENT}}),
                         {"Female": {"text_box_border_colour": ft.TRANSPARENT}})
        self.assertEqual(ft.styled(ft.style_of(tree)).text_box_border_colour, ft.TRANSPARENT)
        self.assertEqual(borders(scene(back).items), [])                 # nothing drawn, for anyone

    def test_svg_export_carries_the_border(self):
        edits = ft.Edits(text_box_border="dashed", text_box_border_width=3.0, text_box_border_colour="#12ab34")
        svg = ft.to_svg(scene(edits), {})
        self.assertIn('stroke="#12ab34"', svg)
        self.assertNotIn("#12ab34", ft.to_svg(scene(ft.Edits()), {}))

    @unittest.skipUnless(vv_gdiplus.available(), "Windows' own graphics")
    def test_the_picture_has_the_border_at_the_boxs_edge(self):
        def pixel(edits: ft.Edits, scale: float, at=None):
            sc = scene(edits)
            with tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp) / "tree.png"
                self.assertTrue(vv_gdiplus.save_scene(sc, {}, out, scale=scale))
                _w, _h, rows = read_png(out)
            return sc, rows

        on = ft.Edits(text_box_border="thick", text_box_border_width=4.0, text_box_border_colour=RED)
        off = ft.Edits()
        for scale in (1.0, 2.0):                        # the picture at its own size and twice as big
            with self.subTest(scale=scale):
                sc, rows = pixel(on, scale)
                line = borders(sc.items, MALE)[0]
                x, y = round(line.x * scale), round((line.y + line.h / 2) * scale)
                r, g, b = rows[y][x][:3]
                self.assertTrue(r > 200 and g < 90 and b < 90, (r, g, b))
                _sc, plain = pixel(off, scale)
                r, g, b = plain[y][x][:3]
                self.assertFalse(r > 200 and g < 90 and b < 90, (r, g, b))
        # A rounded corner: the very corner of the box stays clear, the curve inside it is red.
        sc, rows = pixel(on, 2.0)
        line = borders(sc.items, MALE)[0]
        cx, cy = round((line.x - 1) * 2), round((line.y - 1) * 2)
        self.assertFalse(rows[cy][cx][0] > 200 and rows[cy][cx][1] < 90)


class EditorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            import tkinter as tk
            cls.root = tk.Tk()
        except Exception as exc:                            # no display
            raise unittest.SkipTest(str(exc))
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.root.destroy()

    def setUp(self) -> None:
        import vv_genealogy_window as gw
        self.gw = gw
        self.dir = tempfile.TemporaryDirectory()
        self.root.tree_window = {"geometry": "1400x860+-6000+-6000"}
        self.root.builds = []
        self.root.tree_style = ft.style_of(ft.Edits())
        self.root._save_settings = lambda: None
        for name in ("_follow_looks", "_write_outputs"):
            patch = mock.patch.object(gw.TreeEditor, name, lambda self, *a, **k: None)
            patch.start()
            self.addCleanup(patch.stop)
        self.ed = gw.TreeEditor(self.root, Path(self.dir.name), 1, 1, TITLE, None, village(),
                                ft.styled(self.root.tree_style))
        self.ed.withdraw()
        self.root.update()

    def tearDown(self) -> None:
        try:
            self.ed.dirty = False
            self.ed.destroy()
        except Exception:
            pass
        self.dir.cleanup()

    def outlined(self, colour: str) -> list:
        c = self.ed.canvas
        return [i for i in c.find_all() if c.type(i) in ("polygon", "rectangle", "line")
                and (c.itemcget(i, "outline" if c.type(i) != "line" else "fill") == colour)]

    def test_set_drawn_undone_redone_and_by_group(self) -> None:
        ed = self.ed
        self.assertEqual(self.outlined(ODD), [])
        ed.text_box_border_field._set(ODD)
        ed.text_box_border_width_var.set("3")
        ed._detail_number("text_box_border_width", ed.text_box_border_width_var, *ft.TEXT_BOX_BORDER_WIDTHS)
        self.root.update()
        self.assertEqual((ed.edits.text_box_border_colour, ed.edits.text_box_border_width), (ODD, 3.0))
        self.assertTrue(self.outlined(ODD))                          # on the canvas
        ed.text_box_border_var.set(ft.BORDERS["dashed"])
        ed.text_box_kind.event_generate("<<ComboboxSelected>>")
        self.assertEqual(ed.edits.text_box_border, "dashed")
        ed._undo()
        self.assertEqual(ed.edits.text_box_border, "thin")
        self.assertEqual(ed.text_box_border_var.get(), ft.BORDERS["thin"])
        ed._undo()
        ed._undo()
        self.root.update()
        self.assertEqual((ed.edits.text_box_border_colour, ed.edits.text_box_border_width), ("", 0.0))
        self.assertEqual(self.outlined(ODD), [])
        ed._redo()
        ed._redo()
        self.assertEqual((ed.edits.text_box_border_colour, ed.edits.text_box_border_width), (ODD, 3.0))
        # One group's own.
        ed.scope_var.set(ft.GROUPS["Female"])
        ed._refresh_panels()
        ed.text_box_border_width_var.set("5")
        ed._detail_number("text_box_border_width", ed.text_box_border_width_var, *ft.TEXT_BOX_BORDER_WIDTHS)
        self.assertEqual(ed.edits.group_opts["Female"]["text_box_border_width"], 5.0)
        self.assertEqual(ed.edits.text_box_border_width, 3.0)


if __name__ == "__main__":
    unittest.main()
