"""Patch descriptions render **bold** as bold in the patcher.

The owner: "make sure your text formatting is fixed. (there's a lot of patch
descriptions with bold asterisks that DON'T bold the text in there.)"  The
descriptions state their dependencies in **bold** (an owner rule); the GUI
showed the asterisks literally because it used a plain label.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher as vfp  # noqa: E402
import vv_fun_patcher_gui as gui  # noqa: E402


class SplitBoldTests(unittest.TestCase):
    def test_segments(self):
        self.assertEqual(gui.split_bold("plain"), [("plain", False)])
        self.assertEqual(gui.split_bold("a **b** c"), [("a ", False), ("b", True), (" c", False)])
        self.assertEqual(gui.split_bold("**b**"), [("b", True)])
        self.assertEqual(gui.split_bold("a **b** c **d**"),
                         [("a ", False), ("b", True), (" c ", False), ("d", True)])

    def test_an_unmatched_marker_stays_literal(self):
        self.assertEqual(gui.split_bold("a **b"), [("a **b", False)])
        self.assertEqual(gui.split_bold("x **y** z **w"), [("x ", False), ("y", True), (" z **w", False)])

    def test_every_catalog_description_has_balanced_markers(self):
        for patch in vfp.load_public_fun_patches():
            with self.subTest(patch=patch.id):
                self.assertEqual(patch.description.count("**") % 2, 0)


class WindowTests(unittest.TestCase):
    def test_no_description_in_the_window_shows_literal_asterisks(self):
        gui.SETTINGS = Path(tempfile.mkdtemp()) / "settings.json"
        try:
            app = gui.App()
        except Exception as exc:  # no display
            self.skipTest(f"no Tk display: {exc}")
        try:
            app.update()

            def walk(w):
                yield w
                for c in w.winfo_children():
                    yield from walk(c)

            widgets = list(walk(app))
            rich = [w for w in widgets if isinstance(w, gui.RichDescription)]
            self.assertEqual(len(rich), len(vfp.load_public_fun_patches()), "one per patch")
            for w in rich:
                self.assertNotIn("**", w.get("1.0", "end"))
            with_markers = [p for p in vfp.load_public_fun_patches() if "**" in p.description]
            self.assertEqual(sum(1 for w in rich if w.tag_ranges("bold")), len(with_markers))
            for w in widgets:
                if w.winfo_class() in ("TLabel", "Label", "TCheckbutton"):
                    self.assertNotIn("**", str(w.cget("text")), w.winfo_class())
        finally:
            app.destroy()


if __name__ == "__main__":
    unittest.main()
