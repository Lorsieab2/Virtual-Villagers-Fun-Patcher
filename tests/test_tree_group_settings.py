"""Family Tree Maker settings by group (the owner, 2026-10-09: "make all these options by group", "as many
options as realistically and logically possible should be by group with options to equalize"): a group's
portraits (Males, Females, Babies on the way) may have their own faces-and-words, detail-line and inside
settings (Edits.group_opts), picked with "Settings for:" in the window."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_family_tree as ft  # noqa: E402
import vv_genealogy_window as gw  # noqa: E402
import vv_tree_editor_tools as tools  # noqa: E402
from test_genealogy import village  # noqa: E402

TITLE = "Virtual Villagers - A New Home"
MALE, FEMALE = 9, 10            # I and J, twins, generation III


def texts(edits: ft.Edits, pid: int) -> list:
    return [i for i in ft.scene(ft.layout(village(), edits), TITLE, {}).items
            if isinstance(i, ft.Text) and i.pid == pid and i.role in ("names", "portraits")]


def shapes(edits: ft.Edits, pid: int) -> list:
    return [i for i in ft.scene(ft.layout(village(), edits), TITLE, {}).items
            if isinstance(i, ft.Shape) and i.pid == pid and i.target == ("person", pid)]


def detail_lines(edits: ft.Edits, pid: int) -> list:
    return [i for i in ft.scene(ft.layout(village(), edits), TITLE, {}).items
            if isinstance(i, ft.Line) and i.pid == pid and i.opacity < 1]


def males(base: dict | None = None, **values) -> ft.Edits:
    edits = ft.Edits(shapes={"Male": "star", "Female": "star", "Upcoming": "diamond"}, **(base or {}))
    edits.group_opts = {"Male": values}
    return edits


class ModelTests(unittest.TestCase):
    def test_the_fields(self):
        for name in ("text_align", "text_valign", "text_room", "flip_words", "turn_words", "text_inside",
                     "picture_size", "text_size", "text_wrap", "show_units", "show_years", "show_twins",
                     "show_founder", "detail_lines", "detail_colour", "detail_opacity", "detail_width",
                     "portrait_fill"):
            self.assertIn(name, ft.GROUP_FIELDS)
            self.assertTrue(hasattr(ft.Edits(), name))
        self.assertNotIn("mark_style", ft.GROUP_FIELDS)
        self.assertIn("group_opts", ft.STYLE_KEYS)

    def test_opt_is_the_groups_else_the_trees(self):
        v = village()
        edits = males(text_align="left")
        self.assertEqual(ft.opt(edits, v.people[MALE], "text_align"), "left")
        self.assertEqual(ft.opt(edits, v.people[FEMALE], "text_align"), "centre")
        lay = ft.layout(v, edits)
        self.assertEqual(lay.opt(v.people[MALE], "text_size"), 100.0)
        self.assertEqual(ft.group_view(edits, "Male").text_align, "left")
        self.assertIs(ft.group_view(edits, None), edits)

    def assertOnlyMalesChange(self, name, value, measure, base=None):
        plain = males(base)
        plain.group_opts = {}
        own = males(base, **{name: value})
        self.assertNotEqual(measure(own, MALE), measure(plain, MALE), name)
        self.assertEqual(measure(own, FEMALE), measure(plain, FEMALE), name)

    def test_each_field_takes_effect_for_its_group_only(self):
        words = lambda e, q: [(round(t.x, 2), round(t.y, 2), t.text, round(t.size, 2), t.centre, t.end, t.mirror_h,
                               t.angle) for t in texts(e, q)]
        cases = {
            "text_align": "left", "text_valign": "top", "text_room": "shape",
            "picture_size": 50.0, "text_size": 150.0, "text_wrap": 8, "show_units": False, "show_years": False,
            "show_twins": True,
        }
        for name, value in cases.items():
            with self.subTest(name=name):
                self.assertOnlyMalesChange(name, value, words)
        # Kept inside the shape: only where the words would leave it (left-aligned words in a star's outline).
        self.assertOnlyMalesChange("text_inside", True, words, {"text_align": "left", "text_room": "shape"})
        detail = lambda e, q: [(l.colour, l.width, round(l.opacity, 3)) for l in detail_lines(e, q)]
        for name, value in {"detail_lines": False, "detail_colour": "#123456", "detail_opacity": 90.0,
                            "detail_width": 4.0}.items():
            with self.subTest(name=name):
                self.assertOnlyMalesChange(name, value, detail)
        fill = lambda e, q: [s.fill for s in shapes(e, q)]
        self.assertOnlyMalesChange("portrait_fill", "#ffeeaa", fill)

    def test_founder_flip_and_turn_words_for_one_group(self):
        v = village()
        lay = ft.layout(v, males(show_founder=True))
        self.assertIn("Founder", ft.default_text(lay, v.people[1]))          # A, a male founder
        self.assertNotIn("Founder", ft.default_text(lay, v.people[2]))       # B, a female one
        key_m, key_f = ft.entry_key(v, v.people[MALE]), ft.entry_key(v, v.people[FEMALE])
        for name, entry, check in (("flip_words", {"flip_h": True}, lambda t: t.mirror_h),
                                   ("turn_words", {"angle": 30.0}, lambda t: t.angle == 30.0)):
            with self.subTest(name=name):
                edits = males(**{name: True})
                edits.entries = {key_m: dict(entry), key_f: dict(entry)}
                self.assertTrue(all(check(t) for t in texts(edits, MALE)))
                self.assertFalse(any(check(t) for t in texts(edits, FEMALE)))

    def test_a_villagers_own_sizes_still_win(self):
        v = village()
        edits = males(picture_size=50.0, text_size=200.0)
        edits.entries[ft.entry_key(v, v.people[MALE])] = {"picture_scale": 100.0 * 2, "text_scale": 50.0}
        lay = ft.layout(v, edits)
        self.assertEqual(ft.inner_sizes(lay, v.people[MALE]), (0.5 * 2.0, 2.0 * 0.5))
        self.assertEqual(ft.inner_sizes(lay, v.people[11]), (0.5, 2.0))       # K: the group's alone

    def test_saved_and_read_back_bad_values_dropped(self):
        edits = males(text_align="right", text_valign="bottom", text_size=150.0, portrait_fill="#102030",
                      detail_colour="", show_years=False, text_wrap=30)
        back = ft.Edits.from_data(json.loads(json.dumps(edits.to_data())))
        self.assertEqual(back.group_opts["Male"]["text_align"], "right")
        self.assertIs(back.group_opts["Male"]["centre_heads"], False)
        self.assertEqual(back.group_opts["Male"]["text_size"], 150.0)
        self.assertEqual(back.group_opts["Male"]["detail_colour"], "")
        self.assertEqual(back.to_data()["group_opts"], back.group_opts)
        data = ft.Edits().to_data()
        data["group_opts"] = {
            "Male": {"text_align": "sideways", "text_size": "big", "show_units": 1, "portrait_fill": "red",
                     "mark_style": "glow", "text_wrap": 999, "detail_width": True, "detail_opacity": 50,
                     "centre_heads": False},
            "Female": {"text_room": "nowhere"},
            "Martians": {"text_align": "left"},
            "Upcoming": "not a dict",
        }
        back = ft.Edits.from_data(data)
        self.assertEqual(back.group_opts, {"Male": {"text_wrap": ft.WRAP_MAX, "detail_opacity": 50.0}})
        self.assertEqual(ft.Edits.from_data({**ft.Edits().to_data(), "group_opts": [1, 2]}).group_opts, {})
        self.assertEqual(ft.styled(ft.style_of(males(text_size=150.0))).group_opts, {"Male": {"text_size": 150.0}})


class _Var:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class _Editor:
    """The window's settings logic, without its widgets."""
    _change = gw.TreeEditor._change
    _scope = gw.TreeEditor._scope
    _view = gw.TreeEditor._view
    _show_scope_note = gw.TreeEditor._show_scope_note
    _clear_group = gw.TreeEditor._clear_group
    _all_groups_same = gw.TreeEditor._all_groups_same
    _detail_number = gw.TreeEditor._detail_number
    _reset_button = gw.TreeEditor._reset_button
    _number = staticmethod(gw.TreeEditor._number)
    _state = tools.CanvasTools._state
    _record = tools.CanvasTools._record
    _undo = tools.CanvasTools._undo
    _redo = tools.CanvasTools._redo
    _restore = tools.CanvasTools._restore
    obj = None
    dirty = False

    def __init__(self):
        self.edits = ft.Edits()
        self.scope_var = _Var(gw.EVERYONE)
        self.scope_note = _Var()
        self.refreshed = 0
        self.history, self.future = [], []
        self.status = _Var()
        self.last_state = self._state()

    def _saved(self):
        self._record()

    def _refresh_panels(self):
        self.refreshed += 1

    def redraw(self):
        pass

    def _typing(self):
        return False


class WindowTests(unittest.TestCase):
    def setUp(self):
        self.ed = _Editor()

    def pick(self, group):
        self.ed.scope_var.set(ft.GROUPS[group] if group else gw.EVERYONE)

    def test_the_picker_writes_the_groups_own(self):
        self.pick("Male")
        self.ed._change(text_size=150.0)
        self.ed._change(text_valign="top", centre_heads=False)
        self.assertEqual(self.ed.edits.text_size, 100.0)
        self.assertEqual(self.ed.edits.group_opts, {"Male": {"text_size": 150.0, "text_valign": "top",
                                                             "centre_heads": False}})
        self.assertEqual(self.ed._view().text_size, 150.0)
        self.assertIn("differ", self.ed.scope_note.get())
        self.ed._change(text_size=100.0)                    # the same as everyone's: none of its own
        self.assertNotIn("text_size", self.ed.edits.group_opts["Male"])
        self.ed._change(portrait_gap=60.0)                  # not a group's setting: the tree's
        self.assertEqual(self.ed.edits.portrait_gap, 60.0)
        self.pick(None)
        self.ed._change(text_size=120.0)
        self.assertEqual(self.ed.edits.text_size, 120.0)
        self.ed._change(everyone=True, text_align="left")
        self.assertEqual(self.ed.edits.text_align, "left")

    def test_number_boxes_compare_with_the_picked_group(self):
        self.pick("Female")
        self.ed._change(text_size=150.0)
        self.ed._detail_number("text_size", _Var("150"), ft.TEXT_SCALE_MIN, ft.TEXT_SCALE_MAX)
        self.assertEqual(len(self.ed.history), 1)          # no second step: nothing changed
        self.ed._detail_number("text_size", _Var("100"), ft.TEXT_SCALE_MIN, ft.TEXT_SCALE_MAX)
        self.assertEqual(self.ed.edits.group_opts, {})

    def test_reset_with_a_group_picked_clears_only_its_own(self):
        try:
            import tkinter as tk
            root = tk.Tk()
        except Exception as exc:                            # no display
            self.skipTest(str(exc))
        try:
            self.ed.edits.text_size = 130.0
            self.ed.edits.group_opts = {"Male": {"text_size": 150.0, "text_align": "left"},
                                        "Female": {"text_size": 80.0}}
            self.pick("Male")
            self.ed._reset_button(root, "text_size").invoke()
            self.assertEqual(self.ed.edits.group_opts, {"Male": {"text_align": "left"}, "Female": {"text_size": 80.0}})
            self.assertEqual(self.ed.edits.text_size, 130.0)
            self.pick(None)
            self.ed._reset_button(root, "text_size").invoke()
            self.assertEqual(self.ed.edits.text_size, 100.0)
            self.assertEqual(self.ed.edits.group_opts["Female"], {"text_size": 80.0})
        finally:
            root.destroy()

    def test_same_as_everyone_and_make_every_group_the_same(self):
        self.ed.edits.group_opts = {"Male": {"text_size": 150.0}, "Female": {"show_years": False}}
        self.pick("Male")
        self.ed._clear_group(self.ed._scope())
        self.assertEqual(self.ed.edits.group_opts, {"Female": {"show_years": False}})
        self.ed.edits.group_opts["Upcoming"] = {"text_size": 50.0}
        self.ed._all_groups_same()
        self.assertEqual(self.ed.edits.group_opts, {})

    def test_undo_is_one_step_per_change(self):
        self.pick("Male")
        self.ed._change(text_align="right")
        self.ed._change(text_size=200.0)
        self.ed._clear_group("Male")
        self.assertEqual(self.ed.edits.group_opts, {})
        self.ed._undo()
        self.assertEqual(self.ed.edits.group_opts, {"Male": {"text_align": "right", "text_size": 200.0}})
        self.ed._undo()
        self.assertEqual(self.ed.edits.group_opts, {"Male": {"text_align": "right"}})
        self.ed._redo()
        self.assertEqual(self.ed.edits.group_opts["Male"]["text_size"], 200.0)

    def test_the_pickers_sit_in_the_window(self):
        source = (ROOT / "src" / "vv_genealogy_window.py").read_text(encoding="utf-8")
        self.assertEqual(source.count("self._scope_picker("), 3)   # Faces & Text, inside colour, detail lines
        for words in ('text="Settings for:"', 'text="Same as everyone"', 'text="Make every group the same"'):
            self.assertIn(words, source)
        self.assertIn("e = self._view()", source[source.index("    def _refresh_panels("):])


if __name__ == "__main__":
    unittest.main()
