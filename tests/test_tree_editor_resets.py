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
            patch = mock.patch.object(gw.TreeEditor, name, lambda self: None)
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
