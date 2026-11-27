"""The Family Tree editor's tab pages (ScrollingTab) take the mouse wheel while the pointer is over
them and must give it back -- also when their window is closed with the pointer still over a page.
The owner, 2026-11-26: after the Family Tree Maker was closed, scrolling the patcher's Game Mechanics
page stopped with 'TclError: invalid command name ".!treeeditor...!canvas"'.

Real Tk windows in a child process; skips cleanly when there is no Tk display."""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
NO_TK = 3

CHILD = r"""
import sys, tkinter
from tkinter import ttk
sys.path.insert(0, sys.argv[1])
import vv_tree_editor_tools as tools
try:
    root = tkinter.Tk()
except tkinter.TclError as exc:
    print(exc, file=sys.stderr)
    sys.exit(3)
errors = []
root.report_callback_exception = lambda kind, value, tb: errors.append(f"{kind.__name__}: {value}")
patcher_scrolled = []
root.bind_all("<MouseWheel>", lambda event: patcher_scrolled.append(event.delta))
patcher = root.tk.call("bind", "all", "<MouseWheel>")

def page():
    window = tkinter.Toplevel(root)
    book = ttk.Notebook(window)
    book.pack(fill="both", expand=True)
    tab = tools.ScrollingTab(book, "Tab")
    for n in range(100):
        ttk.Label(tab, text=f"row {n}").pack(anchor="w")
    window.update()
    return window, tab.master

def wheel():
    root.event_generate("<MouseWheel>", delta=-120, when="now")
    root.update()

# 1. Over the page the wheel is the page's; leaving gives the patcher's back.
window, canvas = page()
canvas.event_generate("<Enter>", when="now")
taken = root.tk.call("bind", "all", "<MouseWheel>") != patcher
canvas.event_generate("<Leave>", when="now")
print("taken", taken, "back_after_leave", root.tk.call("bind", "all", "<MouseWheel>") == patcher)

# 2. Entering twice before leaving still gives the patcher's back, not the page's own.
canvas.event_generate("<Enter>", when="now")
canvas.event_generate("<Enter>", when="now")
canvas.event_generate("<Leave>", when="now")
print("back_after_double_enter", root.tk.call("bind", "all", "<MouseWheel>") == patcher)

# 3. The window closed with the pointer over the page (no <Leave>): the patcher's wheel works.
canvas.event_generate("<Enter>", when="now")
window.destroy()
root.update()
print("back_after_close", root.tk.call("bind", "all", "<MouseWheel>") == patcher)
wheel()
print("patcher_scrolled", len(patcher_scrolled), "errors", len(errors))
for e in errors:
    print("ERROR", e)
root.destroy()
"""


class ScrollingTabWheelTests(unittest.TestCase):
    def test_wheel_is_given_back_on_leave_and_when_the_window_closes(self):
        done = subprocess.run([sys.executable, "-c", CHILD, str(SRC)],
                              capture_output=True, text=True, timeout=120)
        if done.returncode == NO_TK:
            self.skipTest("no Tk display: " + done.stderr.strip())
        self.assertEqual(done.returncode, 0, done.stderr)
        lines = done.stdout.split("\n")
        self.assertIn("taken True back_after_leave True", lines, done.stdout)
        self.assertIn("back_after_double_enter True", lines, done.stdout)
        self.assertIn("back_after_close True", lines, done.stdout)
        self.assertIn("patcher_scrolled 1 errors 0", lines, done.stdout)


if __name__ == "__main__":
    unittest.main()
