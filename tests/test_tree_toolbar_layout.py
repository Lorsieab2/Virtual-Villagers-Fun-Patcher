"""Family Tree Maker toolbar (the owner: the Hide panel button at the far right of the toolbar was squeezed to a
sliver; "please put it somewhere else or under the taskbar at the top", and "you may put shortcut keys in the
taskbar too").  Help, Full screen and Hide panel sit at the right end of the Find a villager row, each at its
full width; both rows wrap onto more lines instead of squeezing or cutting off a control, at any window width
and with fonts at 150% and 200%; the button and F4 hide and show the panel; and every shortcut the toolbar
rows and menus show works."""
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
import vv_genealogy_window as gw  # noqa: E402
from test_genealogy import village  # noqa: E402

TITLE = "Virtual Villagers - A New Home"


def walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from walk(child)


class ToolbarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # One Tk for the class: starting a fresh Tk() for every test now and then fails on this Python.
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
        self.dir = tempfile.TemporaryDirectory()
        self.root.builds = []
        self.root.tree_style = ft.style_of(ft.Edits())
        self.root._save_settings = lambda: None
        for name in ("_follow_looks", "_write_outputs"):        # no save or logs to draw from here
            patch = mock.patch.object(gw.TreeEditor, name, lambda self, *a, **k: None)
            patch.start()
            self.addCleanup(patch.stop)
        self.ed = None

    def tearDown(self) -> None:
        try:
            if self.ed is not None:
                self.ed.dirty = False
                self.ed.destroy()
        except Exception:
            pass
        import tkinter.font as tkfont
        for name, size in getattr(self, "sizes", {}).items():      # the fonts back as they were
            tkfont.nametofont(name, root=self.root).configure(size=size)
        self.dir.cleanup()

    def open(self, width: int = 1400, fonts: float = 1.0):
        import tkinter.font as tkfont
        if self.ed is not None:                         # one Tk per test (a second Tk() can fail to start)
            self.ed.dirty = False
            self.ed.destroy()
            self.ed = None
        if not hasattr(self, "sizes"):
            self.sizes = {name: int(tkfont.nametofont(name, root=self.root).cget("size"))
                          for name in tkfont.names(self.root)}
        for name, size in self.sizes.items():           # 150% / 200%: every named font that much bigger
            tkfont.nametofont(name, root=self.root).configure(size=round(size * fonts))
        self.root.tree_window = {"geometry": f"{width}x800+-6000+-6000"}
        self.ed = gw.TreeEditor(self.root, Path(self.dir.name), 1, 1, TITLE, None, village(),
                                ft.styled(self.root.tree_style))
        self.settle()
        return self.ed

    def settle(self) -> None:
        end = time.time() + 0.6
        while time.time() < end:
            self.ed.update()
            time.sleep(0.02)

    def test_the_window_buttons_are_on_the_find_row_not_the_toolbar(self) -> None:
        ed = self.open()
        for text in ("Hide panel (F4)", "Full screen (F11)", "Help (F1)"):
            on_find = [w for w in walk(ed.find_row) if "text" in w.keys() and str(w.cget("text")) == text]
            on_bar = [w for w in walk(ed.toolbar) if "text" in w.keys() and str(w.cget("text")) == text]
            self.assertEqual(len(on_find), 1, text)
            self.assertEqual(on_bar, [], text)
        self.assertIn(ed.panel_button, list(walk(ed.find_row)))
        # Right-aligned: the Hide panel button ends at the row's right end.
        right = ed.find_row.winfo_rootx() + ed.find_row.winfo_width()
        self.assertLessEqual(abs(ed.panel_button.winfo_rootx() + ed.panel_button.winfo_width() - right), 2)

    def test_nothing_is_squeezed_at_any_width_or_scaling(self) -> None:
        import tkinter.font as tkfont
        for width, fonts in ((1400, 1.0), (1280, 1.0), (960, 1.0), (640, 1.0), (1400, 1.5), (1400, 2.0),
                             (960, 1.5), (960, 2.0)):
            with self.subTest(width=width, fonts=fonts):
                ed = self.open(width, fonts)
                for row in (ed.toolbar, ed.find_row):
                    right = row.winfo_rootx() + row.winfo_width()
                    for w in walk(row):
                        if w.winfo_class() in ("TFrame", "Frame", "Menu", "TSeparator"):
                            continue
                        what = f"{w.winfo_class()} {w.cget('text') if 'text' in w.keys() else ''}"
                        self.assertTrue(w.winfo_ismapped(), what)
                        need = w.winfo_reqwidth()
                        if w.winfo_class() in ("TCombobox", "TEntry"):      # a typing box narrows to its line
                            need = min(need, w.master.winfo_width())
                        self.assertGreaterEqual(w.winfo_width(), need - 1, what)
                        self.assertLessEqual(w.winfo_rootx() + w.winfo_width(), right + 1, what)
                b = ed.panel_button
                words = tkfont.nametofont("TkDefaultFont", root=self.root).measure(str(b.cget("text")))
                self.assertGreaterEqual(b.winfo_width(), max(b.winfo_reqwidth(), words))
                self.assertLessEqual(b.winfo_rootx() + b.winfo_width(), ed.winfo_rootx() + ed.winfo_width())

    def test_a_flow_row_asks_for_its_widest_child_or_all_on_one_line(self) -> None:
        """Codex, #605: the frame's own helper once shadowed `natural`, so both asked for the sum."""
        import tkinter as tk
        holder = tk.Toplevel(self.root)
        holder.withdraw()
        try:
            for natural, wanted in ((False, 200), (True, 300)):
                with self.subTest(natural=natural):
                    row = tk.Frame(holder)
                    for wide in (100, 200):
                        tk.Frame(row, width=wide, height=10).pack(side="left")
                    gw.flow_row(row, natural=natural)
                    holder.update_idletasks()
                    self.assertEqual(row.winfo_reqwidth(), wanted)
        finally:
            holder.destroy()

    def test_nothing_on_the_side_panel_is_cut_off_at_its_default_width(self) -> None:
        """The owner's screenshot: "Make every..." and "Automa..." cut off in Text box background."""
        ed = self.open(1400)
        names = []
        for tab in ed.notebook.tabs():
            ed.notebook.select(tab)
            self.settle()
            names.append(ed.notebook.tab(tab, "text"))
            for w in walk(ed.nametowidget(tab)):
                if w.winfo_class() in gw.TIP_CLASSES and w.winfo_ismapped():
                    self.assertFalse(gw.is_cut_off(w), f"{names[-1]}: {w.winfo_class()} {gw._words(w)!r}")
        self.assertIn("Faces & Text", names)
        # The Text box background's buttons, each whole.
        for text in ("Make every group the same", "Automatic", "Choose...", "Transparent", "Same as everyone"):
            found = [w for w in walk(ed.text_box_field.master.master) if "text" in w.keys()
                     and str(w.cget("text")) == text]
            self.assertTrue(found, text)

    def test_the_button_and_f4_hide_and_show_the_panel(self) -> None:
        ed = self.open()
        shown = lambda: str(ed.panel) in ed.body.panes()        # noqa: E731
        self.assertTrue(shown())
        ed.panel_button.invoke()
        self.assertFalse(shown())
        self.assertEqual(str(ed.panel_button.cget("text")), "Show panel (F4)")
        self.settle()
        self.assertGreaterEqual(ed.panel_button.winfo_width(), ed.panel_button.winfo_reqwidth())
        ed.panel_button.invoke()
        self.assertTrue(shown())
        self.assertEqual(str(ed.panel_button.cget("text")), "Hide panel (F4)")
        ed.focus_force()
        ed.update()
        ed.event_generate("<F4>")
        self.assertFalse(shown())
        ed.event_generate("<F4>")
        self.assertTrue(shown())

    def test_every_shortcut_shown_works(self) -> None:
        ed = self.open()
        tips = {w.tip_text for w in walk(ed.toolbar) if hasattr(w, "tip_text")}
        tips |= {w.tip_text for w in walk(ed.find_row) if hasattr(w, "tip_text")}
        self.assertEqual(tips, {"Zoom out (-)", "Zoom (Ctrl+0: 100%)", "Zoom in (+)", "The next match (Enter)"})
        ed.focus_force()
        ed.update()
        for key, name, args in (("<minus>", "_zoom_step", (-1,)), ("<plus>", "_zoom_step", (1,)),
                                ("<Control-Key-0>", "_zoom_to", (1.0,)), ("<F1>", "_help", ()),
                                ("<F11>", "_toggle_full", ()), ("<F4>", "_toggle_panel", ())):
            with self.subTest(key=key), mock.patch.object(ed, name) as called:
                ed.event_generate(key)
                called.assert_called_once_with(*args)
        with mock.patch.object(ed.find_entry, "focus_set") as focus:
            ed.event_generate("<Control-f>")
            focus.assert_called_once_with()
        self.ed.find_var.set("x")
        with mock.patch.object(ed, "_find_next") as find:
            ed.find_entry.focus_force()
            ed.update()
            ed.find_entry.event_generate("<Return>")
            find.assert_called_once_with()
        menus = {}
        bar = ed.nametowidget(ed.cget("menu"))
        for i in range(bar.index("end") + 1):
            menu = ed.nametowidget(bar.entrycget(i, "menu"))
            for j in range(menu.index("end") + 1):
                if menu.type(j) == "command":
                    menus[menu.entrycget(j, "label")] = menu.entrycget(j, "accelerator")
        self.assertEqual(menus["Hide or Show the Panel"], "F4")
        self.assertEqual(menus["Full Screen"], "F11")
        self.assertEqual(menus["Find a Villager"], "Ctrl+F")
        self.assertEqual(menus["Controls"], "F1")
        self.assertIn("Ctrl+F", gw.CONTROLS)

    def hover(self, widget) -> str | None:
        """What the hover tip on `widget` says after the mouse rests on it (None: no tip)."""
        gw._tip_hide()
        widget.event_generate("<Enter>", x=2, y=2)
        end = time.time() + (gw.TIP_DELAY + 300) / 1000
        while time.time() < end:
            self.root.update()
            time.sleep(0.02)
        win = gw._TIP["win"]
        words = None if win is None else str(win.winfo_children()[0].cget("text"))
        gw._tip_hide()
        return words

    def test_cut_off_words_show_in_a_hover_tip_on_widgets_made_later(self) -> None:
        import tkinter as tk
        from tkinter import ttk
        ed = self.open()
        dialog = tk.Toplevel(ed)                # a window the editor opens, after it was built
        dialog.geometry("800x200+-6000+-6000")
        words = "Make every group the same as Everyone, with Automatic colours"
        cut = ttk.Label(dialog, text=words)
        cut.place(x=0, y=0, width=60)
        whole = ttk.Label(dialog, text="Short")
        whole.place(x=0, y=40)
        button = ttk.Button(dialog, text=words)
        button.place(x=0, y=80, width=70)
        box = ttk.Combobox(dialog, values=[words])
        box.set(words)
        box.place(x=0, y=120, width=90)
        later = tk.Label(dialog, textvariable=tk.StringVar(dialog, value=words))
        later.place(x=0, y=160, width=50)
        dialog.update()
        self.assertEqual(self.hover(cut), words)
        self.assertIsNone(self.hover(whole))
        self.assertEqual(self.hover(button), words)
        self.assertEqual(self.hover(box), words)
        self.assertEqual(self.hover(later), words)
        cut.place_configure(width=600)              # wide enough now: no tip
        dialog.update()
        self.assertIsNone(self.hover(cut))
        # A shortcut tip always shows; with the words too when they are cut off.
        minus = next(w for w in walk(ed.toolbar) if getattr(w, "tip_text", "") == "Zoom out (-)")
        self.assertEqual(self.hover(minus), "Zoom out (-)")
        # Not in the patcher's own windows.
        other = tk.Toplevel(self.root)
        other.geometry("200x50+-6000+-6000")
        theirs = ttk.Label(other, text=words)
        theirs.place(x=0, y=0, width=40)
        other.update()
        self.assertIsNone(self.hover(theirs))
        other.destroy()
        dialog.destroy()


if __name__ == "__main__":
    unittest.main()
