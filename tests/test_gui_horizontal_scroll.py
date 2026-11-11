"""The main window scrolls sideways (the owner, 2026-11-11: "i wanted the sideways scrolling and vertical scrolling everywhere").

At the 820-pixel minimum width the Tools tab's rows of buttons are wider than the window.  The
page used to be squeezed to the window's width, so the controls past the right edge could not be
reached.  Now the page keeps its own width in a narrower window, a horizontal bar appears, and
Shift + wheel scrolls it sideways; in a window wider than the page the page still fills it.

The app is built in its own interpreter (Tk cannot build a second App in one process); the test
skips cleanly when there is no Tk display.
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

CHILD = r"""
import json, sys, tkinter
from pathlib import Path
from tkinter import ttk
sys.path.insert(0, sys.argv[1])
import vv_fun_patcher_gui as gui
gui.SETTINGS = Path(sys.argv[2])
try:
    app = gui.App()
except tkinter.TclError as exc:
    print(exc, file=sys.stderr)
    sys.exit(3)


def walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from walk(child)


def settle():
    for _ in range(6):
        app.update()


canvas, page, bar = app.content_canvas, app.content_frame, app.content_xbar
sections = next(w for w in walk(app) if isinstance(w, ttk.Notebook)
                and any(w.tab(t, "text") == "Tools" for t in w.tabs()))
tools = next(sections.nametowidget(t) for t in sections.tabs() if sections.tab(t, "text") == "Tools")
sections.select(tools)
app.geometry("820x520")
settle()
region = [float(v) for v in str(canvas.cget("scrollregion")).split()]
result = {"window_width": app.winfo_width(), "canvas_width": canvas.winfo_width(),
          "page_req": page.winfo_reqwidth(), "page_width": page.winfo_width(),
          "region_width": int(region[2] - region[0]), "bar_shown": bool(bar.winfo_ismapped())}
# Every control on the Tools tab: at its full width and inside each frame around it, up to the page.
controls, cut = 0, []
for widget in walk(tools):
    if widget.winfo_children() or not widget.winfo_ismapped():
        continue
    controls += 1
    right = widget.winfo_rootx() + widget.winfo_width()
    if widget.winfo_width() < widget.winfo_reqwidth():
        cut.append(f"{widget} squeezed: {widget.winfo_width()} < {widget.winfo_reqwidth()}")
    holder = widget.master
    while holder is not None and holder is not canvas:
        if right > holder.winfo_rootx() + holder.winfo_width():
            cut.append(f"{widget} past the right edge of {holder}")
            break
        holder = holder.master
    if right - page.winfo_rootx() > result["region_width"]:
        cut.append(f"{widget} past the scroll region")
result["controls"], result["cut"] = controls, cut


class Wheel:
    def __init__(self, x, y, delta, state):
        self.x_root, self.y_root, self.delta, self.state = x, y, delta, state


app.winfo_containing = lambda _x, _y: page
canvas.xview_moveto(0.0)
canvas.yview_moveto(0.0)
settle()
result["plain_returns"] = app._scroll_content(Wheel(10, 10, -120, 0))
settle()
result["plain_moves"] = [canvas.xview()[0], canvas.yview()[0]]
result["shift_returns"] = app._scroll_content(Wheel(10, 10, -120, 1))
settle()
result["shift_moves"] = [canvas.xview()[0], canvas.yview()[0]]
# A window wider than the page: the page fills it and the bar is gone, as before.
app.geometry(f"{page.winfo_reqwidth() + 300}x700")
settle()
result.update(wide_canvas_width=canvas.winfo_width(), wide_page_width=page.winfo_width(),
              wide_bar_shown=bool(bar.winfo_ismapped()))
app.destroy()
print(json.dumps(result))
"""


class MainWindowScrollsSideways(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with tempfile.TemporaryDirectory() as folder:
            done = subprocess.run(
                [sys.executable, "-c", CHILD, str(ROOT / "src"), str(Path(folder) / "settings.json")],
                capture_output=True, text=True, timeout=300,
            )
        if done.returncode == NO_TK:
            raise unittest.SkipTest(f"no Tk display: {done.stderr.strip()[-200:]}")
        if done.returncode != 0:
            raise AssertionError(done.stderr[-2000:])
        cls.result = json.loads(done.stdout.strip().splitlines()[-1])

    def test_every_tool_control_is_reachable_at_the_minimum_width(self) -> None:
        r = self.result
        self.assertLessEqual(r["window_width"], 830, r)
        self.assertGreater(r["controls"], 40, r)
        self.assertEqual(r["cut"], [], r)
        # The controls fit, or the scroll region is wider than the window and its bar is shown.
        if r["page_req"] > r["canvas_width"]:
            self.assertGreaterEqual(r["page_width"], r["page_req"], r)
            self.assertGreaterEqual(r["region_width"], r["page_req"], r)
            self.assertTrue(r["bar_shown"], r)

    def test_wheel_scrolls_down_and_shift_wheel_sideways(self) -> None:
        r = self.result
        self.assertEqual(r["plain_moves"][0], 0.0, "the plain wheel must not scroll sideways")
        self.assertGreater(r["plain_moves"][1], 0.0, "the plain wheel scrolls the page down")
        if r["page_req"] > r["canvas_width"]:
            self.assertEqual(r["shift_returns"], "break")
            self.assertGreater(r["shift_moves"][0], 0.0, "Shift + wheel scrolls the page sideways")
            self.assertEqual(r["shift_moves"][1], r["plain_moves"][1], "Shift + wheel must not scroll down")

    def test_a_wider_window_is_filled_and_has_no_sideways_bar(self) -> None:
        r = self.result
        self.assertEqual(r["wide_page_width"], r["wide_canvas_width"], r)
        self.assertFalse(r["wide_bar_shown"], r)


if __name__ == "__main__":
    unittest.main()
