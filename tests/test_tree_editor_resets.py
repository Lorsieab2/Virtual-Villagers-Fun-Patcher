"""Family Tree Maker: the opacity sliders fade the parts they name; a group's size box left as it was
changes nothing; closing a never-saved tree with "No" keeps the remembered look; Reset Portrait Shapes
undoes every resize, turn and flip; Delete This Tree starts again in the remembered look; and a size
typed for one villager is not lost when another is clicked within the box's wait."""
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_family_tree as ft  # noqa: E402
import vv_genealogy_window as gw  # noqa: E402
from test_genealogy import village  # noqa: E402

TITLE = "Virtual Villagers - A New Home"


def faded(edits: ft.Edits) -> list:
    return ft.scene(ft.layout(village(), edits), TITLE, {}).items


class OpacityTests(unittest.TestCase):
    def look(self, **opacity) -> ft.Edits:
        e = ft.Edits(borders={g: "vine_both" for g in ft.GROUPS}, detail_lines=True)
        e.opacity = opacity
        return e

    def test_portraits_fade_everything_drawn_for_a_villager_and_words_none_of_it(self) -> None:
        plain = faded(self.look())
        words = faded(self.look(words=20))
        portraits = faded(self.look(portraits=20))
        self.assertEqual(len(plain), len(words))
        self.assertEqual(len(plain), len(portraits))
        kinds = set()
        for a, w, p in zip(plain, words, portraits):
            if getattr(a, "pid", None) is None:
                continue
            kinds.add(type(a).__name__)
            self.assertAlmostEqual(w.opacity, a.opacity, msg=f"Words faded a portrait's {type(a).__name__}")
            self.assertAlmostEqual(p.opacity, a.opacity * 0.2, msg=f"Portraits left a {type(a).__name__}")
        self.assertTrue({"Shape", "Line", "Poly", "Text"} <= kinds, kinds)

    def test_rainbow_borders_go_with_the_portraits(self) -> None:
        e = ft.Edits(borders={g: "thick" for g in ft.GROUPS}, schemes={"borders": "rainbow"}, opacity={"words": 20})
        lines = [i for i in faded(e) if isinstance(i, ft.Line) and i.pid is not None]
        self.assertTrue(lines)
        self.assertTrue(all(i.opacity == 1.0 for i in lines))

    def test_the_keys_swatches_go_with_the_words(self) -> None:
        e = ft.Edits(marks={"Runner": "#00ff00"}, opacity={"words": 20})
        v = village()
        e.entries[ft.entry_key(v, v.people[9])] = {"mark": "Runner"}
        swatches = [i for i in ft.scene(ft.layout(v, e), TITLE, {}).items
                    if isinstance(i, ft.Shape) and i.move == "key"]
        self.assertTrue(swatches)
        self.assertTrue(all(abs(i.opacity - 0.2) < 1e-9 for i in swatches))


def uneven() -> ft.Edits:
    """Faces and words every which size: a group's own, a villager's own, frames of every size, words
    kept inside the shape."""
    v = village()
    e = ft.Edits(shapes={"Male": "rect", "Female": "circle", "Upcoming": "diamond"}, text_inside=True,
                 sizes={"Male": [150.0, 60.0], "Female": [90.0, 90.0]})
    e.group_opts = {"Female": {"picture_size": 70.0, "text_size": 70.0}}
    first = next(p for p in v.people.values() if ft.group_of(p) == "Male")
    e.entries[ft.entry_key(v, first)] = {"text_scale": 150.0, "picture_scale": 130.0, "w": 200.0, "h": 120.0}
    return e


def measured(edits: ft.Edits, group: str | None = None) -> tuple[set, set, set]:
    """(face sizes, name font sizes, other line font sizes) of the portraits in scope, as drawn."""
    v = village()
    lay = ft.layout(v, edits)
    faces, names, lines = set(), set(), set()
    for pid in lay.x:
        p = v.people[pid]
        if group in (None, ft.group_of(p)) and not p.upcoming:
            fw, fh = ft.frame_size(edits, v, p, shrink=lay.shrink)
            faces.add(round(ft.inner_sizes(lay, p)[0] * ft.fixed_scale(lay, p, fw, fh), 6))
    for i in ft.scene(lay, TITLE, {}).items:
        if isinstance(i, ft.Text) and i.pid is not None and group in (None, ft.group_of(v.people[i.pid])):
            if i.role == "names":
                names.add(round(i.size, 6))
            elif i.role == "portraits":
                lines.add(round(i.size, 6))
    return faces, names, lines


class EqualSizeTests(unittest.TestCase):
    def test_everyone_gets_exactly_one_face_and_one_font_size(self) -> None:
        before = measured(uneven())
        self.assertGreater(len(before[1]), 1)
        e = uneven()
        e.fixed_face_size = True
        e.equal_sizes = {"all": {"face": 100.0, "text": 100.0}}
        faces, names, lines = measured(e)
        self.assertEqual((len(faces), len(names), len(lines)), (1, 1, 1), (faces, names, lines))

    def test_one_group_alone(self) -> None:
        e = uneven()
        e.equal_sizes = {"Male": {"face": 100.0, "text": 100.0}}
        faces, names, lines = measured(e, "Male")
        self.assertEqual((len(faces), len(names), len(lines)), (1, 1, 1), (faces, names, lines))

    def test_saved_and_read_back_and_bad_ones_dropped(self) -> None:
        e = ft.Edits(equal_sizes={"all": {"face": 90.0, "text": 80.0}})
        self.assertEqual(ft.Edits.from_data(e.to_data()).equal_sizes, e.equal_sizes)
        self.assertEqual(ft.Edits.from_data({"equal_sizes": {"x": {}, "Male": {"face": "a", "text": 1}}}).equal_sizes,
                         {})
        self.assertIn("equal_sizes", ft.STYLE_KEYS)


class EditorTests(unittest.TestCase):
    def setUp(self) -> None:
        try:
            import tkinter as tk
            self.root = tk.Tk()
        except Exception as exc:                            # no display
            self.skipTest(str(exc))
        self.root.withdraw()
        self.dir = tempfile.TemporaryDirectory()
        self.folder = Path(self.dir.name)
        self.saved = 0
        self.root.tree_window = {"geometry": "1200x800+-6000+-6000"}
        self.root.builds = []
        self.root.tree_style = ft.style_of(ft.Edits(shapes={"Male": "heart", "Female": "star", "Upcoming": "diamond"},
                                                    background="#123456"))

        def save():
            self.saved += 1
        self.root._save_settings = save
        for name in ("_follow_looks", "_write_outputs"):        # no save or logs to draw from here
            patch = mock.patch.object(gw.TreeEditor, name, lambda self, *a, **k: None)
            patch.start()
            self.addCleanup(patch.stop)

    def tearDown(self) -> None:
        try:
            if getattr(self, "ed", None) is not None:
                self.ed.dirty = False
                self.ed.destroy()
        except Exception:
            pass
        self.root.destroy()
        self.dir.cleanup()

    def open(self, edits: ft.Edits | None = None):
        self.ed = gw.TreeEditor(self.root, self.folder, 1, 1, TITLE, None, village(),
                                edits if edits is not None else ft.styled(self.root.tree_style))
        self.ed.withdraw()
        self.root.update()
        return self.ed

    def group(self, name):
        return [p for p in self.ed.village.people.values() if ft.group_of(p) == name and p.id in self.ed.sc.boxes]

    def test_leaving_a_group_size_box_unchanged_keeps_own_sizes(self) -> None:
        ed = self.open()
        two = [p.id for p in self.group("Female")[:2]]
        ed._select(two)
        ed.own_w.set("150")
        ed._own_size(0)
        steps = len(ed.history)
        ed._group_size("Female", axis=0)                    # <FocusOut> / <Return> on the untouched box
        ed._group_size("Female")
        for q in two:
            self.assertEqual(ed._entry(ed.village.people[q]).get("w"), 150.0)
        self.assertEqual(len(ed.history), steps)
        w_var, h_var = ed.group_sizes["Female"]             # a real change still sizes every one
        w_var.set("90")
        ed.lock_shape.set(False)
        ed._group_size("Female", axis=0)
        self.assertEqual(ed.edits.sizes["Female"][0], 90.0)
        self.assertNotIn("w", ed._entry(ed.village.people[two[0]]))

    def test_no_on_closing_a_never_saved_tree_keeps_the_remembered_look(self) -> None:
        ed = self.open()
        ed._change(title="My tribe")
        with mock.patch.object(gw.messagebox, "askyesnocancel", return_value=False):
            ed._close()
        self.ed = None
        self.assertEqual(self.root.tree_style["shapes"]["Male"], "heart")
        self.assertEqual(self.root.tree_style["background"], "#123456")

    def test_reset_portrait_shapes_undoes_group_sizes_and_flips(self) -> None:
        ed = self.open()
        ed._group_flip("Male", "flip_h")
        ed.edits.sizes["Female"] = [150.0, 150.0]
        p = self.group("Female")[0]
        ed._set_entry(p, flip_v=True, angle=30.0)
        ed._saved()
        with mock.patch.object(gw.messagebox, "askyesno", return_value=True):
            ed._reset_shapes()
        self.assertEqual(ed.edits.sizes, {})
        for q in ed.village.people.values():
            entry = ed._entry(q)
            self.assertFalse({"flip_h", "flip_v", "angle", "w", "h"} & set(entry), (q.name, entry))
        ed._undo()
        self.assertEqual(ed.edits.sizes, {"Female": [150.0, 150.0]})
        self.assertTrue(ed._entry(p).get("flip_v"))

    def test_same_face_and_text_size_button(self) -> None:
        ed = self.open(uneven())
        steps = len(ed.history)
        ed._equalize(None)
        self.assertEqual(len(ed.history), steps + 1)          # one undo step
        faces, names, lines = measured(ed.edits)
        self.assertEqual((len(faces), len(names), len(lines)), (1, 1, 1), (faces, names, lines))
        self.assertEqual(ed.edits.group_opts.get("Female", {}).get("picture_size"), None)
        self.assertTrue(all("text_scale" not in ed._entry(p) for p in ed.village.people.values()))
        # It stays equal when a portrait is resized ...
        p = self.group("Female")[0]
        ed._set_entry(p, w=40.0, h=40.0)
        ed._saved()
        faces, names, _lines = measured(ed.edits)
        self.assertEqual((len(faces), len(names)), (1, 1))
        # ... until a face or text size is changed again (a group's own: the others stay the same).
        ed._undo()
        ed._undo()
        self.assertEqual(ed.edits.equal_sizes, {})
        ed._equalize(None)
        ed.scope_var.set(ft.GROUPS["Female"])
        ed._change(text_size=60.0)
        self.assertEqual(set(ed.edits.equal_sizes), {"Male", "Upcoming"})
        self.assertEqual(len(measured(ed.edits, "Male")[1]), 1)

    def test_delete_this_tree_starts_again_in_the_remembered_look(self) -> None:
        ed = self.open()
        with mock.patch.object(gw.messagebox, "askyesno", return_value=True):
            ed._delete_tree()
        self.assertEqual(ed.edits.shapes["Male"], "heart")

    def test_a_size_typed_then_another_villager_clicked_is_kept(self) -> None:
        ed = self.open()
        a, b = (p.id for p in self.group("Female")[:2])
        ed._select([a])
        spin = next(w for w in _widgets(ed) if w.winfo_class() == "TSpinbox"
                    and str(w.cget("textvariable")) == str(ed.own_w))
        ed.own_w.set("150")
        # A key let go in it (a withdrawn window gets no key events: its binding run as Tk would): the
        # typing is applied 800 ms after it stops.
        script = spin.bind("<KeyRelease>")
        spin.tk.eval(re.sub(r"%(.)", lambda m: str(spin) if m.group(1) == "W" else "0", script))
        self.assertIsNone(ed._entry(ed.village.people[a]).get("w"))
        ed._select([b])                                      # another villager clicked at once
        self.assertEqual(ed._entry(ed.village.people[a]).get("w"), 150.0)
        self.assertNotIn("w", ed._entry(ed.village.people[b]))


def _widgets(w):
    for child in w.winfo_children():
        yield child
        yield from _widgets(child)


if __name__ == "__main__":
    unittest.main()
