"""The main window's page must stay far below the Windows child-window limit.

Windows cannot paint any part of a child window past y = 32,767 (a signed 16-bit
coordinate). When every patch description sat on one page it grew to 33,237 px and the
folder choosers and buttons at its bottom were blank. The patch list is now one tab per
game, so only the tallest tab counts.

The app is built in its own interpreter (Tk cannot build a second App in one process);
the test skips cleanly when there is no Tk display.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

NO_TK = 3
WINDOWS_LIMIT = 32767
MAIN_PAGE_BUDGET = 24000
# Widgets under one game's patch tab: a header, the list, its scrollbar and the rows on
# screen (about four at a time, six widgets each). Before the list was virtual a tab held
# 101 to 176 of them.
WIDGETS_PER_TAB_BOUND = 60

CHILD = r"""
import json, os, sys, tkinter
from pathlib import Path
from tkinter import ttk
sys.path.insert(0, sys.argv[1])
os.environ["USERPROFILE"] = sys.argv[2]
import vv_fun_patcher_gui as gui
gui.SETTINGS = Path(sys.argv[2]) / "settings.json"
try:
    app = gui.App()
except tkinter.TclError as exc:
    print(exc, file=sys.stderr)
    sys.exit(3)
app.withdraw()
app.update_idletasks()
canvas = app.content_canvas
page = canvas.nametowidget(canvas.itemcget(app.content_window, "window"))
heights = {"main page": page.winfo_reqheight()}


def walk(widget):
    for child in widget.winfo_children():
        yield child
        yield from walk(child)


for widget in walk(app):
    if isinstance(widget, tkinter.Canvas):
        for item in widget.find_all():
            if widget.type(item) == "window":
                inner = widget.nametowidget(widget.itemcget(item, "window"))
                heights[str(widget)] = inner.winfo_reqheight()
for notebook in (w for w in walk(app) if isinstance(w, ttk.Notebook)):
    for tab in notebook.tabs():
        heights[str(notebook) + ":" + notebook.tab(tab, "text")] = notebook.nametowidget(tab).winfo_reqheight()
widgets = {}
for tab in app.patch_pages.tabs():
    page = app.patch_pages.nametowidget(tab)
    widgets[app.patch_pages.tab(tab, "text")] = sum(1 for _ in walk(page))
app.destroy()
print(json.dumps({"heights": heights, "widgets": widgets}))
"""


class PageHeight(unittest.TestCase):
    def test_every_scrolled_page_is_far_below_the_windows_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            done = subprocess.run(
                [sys.executable, "-c", CHILD, str(ROOT / "src"), folder],
                capture_output=True, text=True, timeout=300,
            )
        if done.returncode == NO_TK:
            self.skipTest("no Tk display: " + done.stderr.strip())
        self.assertEqual(done.returncode, 0, done.stderr)
        data = json.loads(done.stdout.strip().splitlines()[-1])
        heights = data["heights"]
        self.assertLess(heights["main page"], MAIN_PAGE_BUDGET, heights)
        for name, height in heights.items():
            self.assertLess(height, WINDOWS_LIMIT, f"{name}: {height}")

    def test_each_game_tab_creates_only_its_visible_rows(self):
        # The patch list is virtual: a game's tab holds the widgets of the rows on screen
        # (plus a margin), not one set per patch. Every game tab stays under the bound.
        with tempfile.TemporaryDirectory() as folder:
            done = subprocess.run(
                [sys.executable, "-c", CHILD, str(ROOT / "src"), folder],
                capture_output=True, text=True, timeout=300,
            )
        if done.returncode == NO_TK:
            self.skipTest("no Tk display: " + done.stderr.strip())
        self.assertEqual(done.returncode, 0, done.stderr)
        widgets = json.loads(done.stdout.strip().splitlines()[-1])["widgets"]
        self.assertEqual(len(widgets), 5, widgets)
        for name, count in widgets.items():
            self.assertLess(count, WIDGETS_PER_TAB_BOUND, f"{name}: {count} widgets")


if __name__ == "__main__":
    unittest.main()
