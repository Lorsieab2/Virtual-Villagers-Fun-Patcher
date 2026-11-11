"""The main window scrolls sideways (the owner, 2026-11-11: "i wanted the sideways scrolling and vertical scrolling everywhere").

At its usual width (940 pixels) the page fills the window exactly as before and there is no
sideways bar.  Made narrower (down to the 820-pixel minimum), the page used to be squeezed to the
window, so the controls past the right edge could not be reached; now it keeps its usual width, a
horizontal bar appears, and Shift + wheel scrolls it sideways.  In a window wider than the page,
the page fills it.

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
settle()


def cut_at_usual_size():
    # Every control on the shown tab lies inside the visible canvas, at its full width, and none is
    # dropped for lack of room (a label's words may wrap; a typing box may narrow to its line).
    right_edge = canvas.winfo_rootx() + canvas.winfo_width()
    found = []
    for widget in walk(page):
        if widget.winfo_children():
            continue
        what = f"{widget.winfo_class()} {str(widget.cget('text'))[:40] if 'text' in widget.keys() else ''!r}"
        if not widget.winfo_ismapped():
            master = widget.master
            if widget.winfo_manager() and master.winfo_ismapped() and not isinstance(master, ttk.Notebook):
                found.append(f"{what}: dropped for lack of room")
            continue
        if widget.winfo_rootx() + widget.winfo_width() > right_edge + 1:
            found.append(f"{what}: past the window's right edge")
        elif (widget.winfo_width() < widget.winfo_reqwidth() - 1
              and widget.winfo_class() not in ("TEntry", "Entry", "TCombobox")):
            found.append(f"{what}: squeezed {widget.winfo_width()} < {widget.winfo_reqwidth()}")
    return found


# The usual size: every tab (each of the Patches tab's own tabs too) shows every control whole.
usual_cut, tabs_checked = {}, []
for book in [w for w in walk(page) if isinstance(w, ttk.Notebook)]:
    for tab in book.tabs():
        holder = book
        while holder is not page:                   # show the tab, and every tab it sits in
            parent = holder.master
            if isinstance(parent, ttk.Notebook):
                parent.select(holder)
            holder = parent
        book.select(tab)
        settle()
        name = book.tab(tab, "text")
        tabs_checked.append(name)
        found = cut_at_usual_size()
        if found:
            usual_cut[name] = found
sections.select(tools)
settle()
# The usual size: the page fills the window, no sideways bar.
result = {"usual_window": app.winfo_width(), "usual_canvas": canvas.winfo_width(),
          "usual_page": page.winfo_width(), "usual_bar": bool(bar.winfo_ismapped()),
          "usual_cut": usual_cut, "tabs_checked": tabs_checked}
app.geometry("820x520")
settle()
region = [float(v) for v in str(canvas.cget("scrollregion")).split()]
result.update({"window_width": app.winfo_width(), "canvas_width": canvas.winfo_width(),
          "page_req": page.winfo_reqwidth(), "page_width": page.winfo_width(),
          "region_width": int(region[2] - region[0]), "bar_shown": bool(bar.winfo_ismapped())})
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
# A window wider than the page (as far as the screen allows): the page fills it, no bar.
wide = min(page.winfo_reqwidth() + app.content_scrollbar.winfo_reqwidth() + 60, app.winfo_screenwidth() - 40)
app.geometry(f"{max(wide, gui.DEFAULT_WINDOW_WIDTH)}x700")
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

    def test_the_usual_size_has_no_sideways_bar(self) -> None:
        r = self.result
        self.assertEqual(r["usual_page"], r["usual_canvas"], r)
        self.assertFalse(r["usual_bar"], r)

    def test_every_control_on_every_tab_shows_whole_at_the_usual_size(self) -> None:
        # The owner (2026-11-11): the Patches tab's settings row (Patch Selection Settings, Unicode Font
        # and the three sliders) ran past the usual 940-pixel window; it flows onto more lines now.
        r = self.result
        for name in ("Patches", "Tools", "One Game", "All 5 Games", "A New Home", "New Believers"):
            self.assertIn(name, r["tabs_checked"])
        self.assertEqual(r["usual_cut"], {})

    def test_every_tool_control_is_reachable_at_the_minimum_width(self) -> None:
        r = self.result
        self.assertLessEqual(r["window_width"], 830, r)
        self.assertGreater(r["controls"], 40, r)
        self.assertEqual(r["cut"], [], r)
        # Narrower than usual: the page keeps the usual width (or what it needs, if less), and the bar shows.
        self.assertGreaterEqual(r["page_width"], min(r["page_req"], r["usual_canvas"]), r)
        self.assertGreaterEqual(r["region_width"], r["page_width"], r)
        if r["page_width"] > r["canvas_width"]:
            self.assertTrue(r["bar_shown"], r)

    def test_wheel_scrolls_down_and_shift_wheel_sideways(self) -> None:
        r = self.result
        self.assertEqual(r["plain_moves"][0], 0.0, "the plain wheel must not scroll sideways")
        self.assertGreater(r["plain_moves"][1], 0.0, "the plain wheel scrolls the page down")
        self.assertGreater(r["page_width"], r["canvas_width"], r)
        self.assertEqual(r["shift_returns"], "break")
        self.assertGreater(r["shift_moves"][0], 0.0, "Shift + wheel scrolls the page sideways")
        self.assertEqual(r["shift_moves"][1], r["plain_moves"][1], "Shift + wheel must not scroll down")

    def test_a_wider_window_is_filled_and_has_no_sideways_bar(self) -> None:
        r = self.result
        self.assertEqual(r["wide_page_width"], r["wide_canvas_width"], r)
        self.assertFalse(r["wide_bar_shown"], r)


if __name__ == "__main__":
    unittest.main()
