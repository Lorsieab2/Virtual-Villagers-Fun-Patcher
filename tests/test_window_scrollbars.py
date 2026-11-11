"""Every window the patcher opens scrolls when its content is taller than the screen, and
sideways when it is wider than the window (the owner, 2026-11-11: "i wanted the
sideways scrolling and vertical scrolling everywhere in the patcher").

A window's controls go in vv_tree_editor_tools.scrollable_frame: a Canvas with a vertical
Scrollbar, a horizontal one (vv_scrollbars.horizontal_bar, shown only while needed) and an
inner frame, the wheel scrolling it while the pointer is over the window, Shift + wheel
sideways. The static check below walks the GUI modules that create windows and requires every
Toplevel creation either to use that helper, or to be listed in EXEMPT with the reason it
already scrolls (or cannot grow). A second static check requires every scrolling area with a
vertical bar (Text, Listbox, Treeview, Canvas) in every module to have a horizontal one too,
or to be listed in NO_SIDEWAYS with the reason (a Text that wraps its words). The Tk checks
build real windows and skip cleanly when there is no Tk display.
"""
from __future__ import annotations

import ast
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
HELPER = "scrollable_frame"
HELPER_MODULE = "vv_tree_editor_tools.py"
WINDOW_MODULES = ["vv_fun_patcher_gui.py", "vv_genealogy_window.py", "vv_game_mechanics_window.py",
                  "vv_stew_recipes_window.py", HELPER_MODULE]
NO_TK = 3

# file::enclosing function (Class.method, nested as outer.inner), or file::ClassName for a
# Toplevel subclass. Each one is a window that already scrolls, or cannot grow, so it does not
# go through the helper.
EXEMPT = {
    "vv_genealogy_window.py::show_tip":
        "a borderless hover tip of one wrapped label, gone when the mouse moves",
    "vv_fun_patcher_gui.py::WaitWindow.__init__":
        "a small fixed-size progress window (not resizable, close disabled while the work runs)",
    "vv_fun_patcher_gui.py::App._show_folder_confirmation":
        "its rows already scroll in their own canvas, sized to the screen",
    "vv_fun_patcher_gui.py::App._show_log_report":
        "its report is a Text box with its own scroll bar",
    "vv_fun_patcher_gui.py::App._history_list_dialog":
        "its plan is a Text box with its own scroll bar; the window is sized above the buttons",
    "vv_fun_patcher_gui.py::App._undo_history_dialog":
        "its plan is a Text box with its own scroll bar; the window is sized above the buttons",
    "vv_fun_patcher_gui.py::App._move_to_save_folders_dialog":
        "its list is a Text box with its own scroll bar; the window is sized above the buttons",
    "vv_fun_patcher_gui.py::App._own_rules_dialog":
        "the villagers' rows already scroll in their own canvas; the buttons stay under it",
    "vv_fun_patcher_gui.py::App._repair_questions":
        "every question already scrolls in its own fixed canvas",
    "vv_fun_patcher_gui.py::App._graves_dialog":
        "every row already scrolls in its own fixed canvas",
    "vv_genealogy_window.py::TreeEditor":
        "the tree editor: a drawing canvas and tab pages that already scroll (ScrollingTab); "
        "wrapping it would fight both",
    "vv_genealogy_window.py::TreeEditor._ask_looks":
        "the villagers' list already scrolls in its own canvas",
    "vv_genealogy_window.py::_show_text":
        "a Text box with its own scroll bar, in a fixed-size window",
    "vv_game_mechanics_window.py::open_game_mechanics":
        "resizable: the pickers keep their height, the page is a Text box with its own scroll bar that "
        "takes the rest, and a minimum size keeps the pickers and buttons on screen "
        "(tests/test_game_mechanics.py builds it)",
    "vv_stew_recipes_window.py::open_stew_recipes":
        "resizable: the intro and Close keep their height, each tab's page is a Text box with its own scroll bar that "
        "takes the rest, and a minimum size keeps them on screen (tests/test_stew_recipes.py builds it)",
    "vv_tree_editor_tools.py::choose_font":
        "a font list (Text) with its own scroll bar; the search box and buttons sit around it",
}

# file::enclosing function::the scrolled widget: a scrolling area with a vertical bar and no
# horizontal one, and why it needs none.
NO_SIDEWAYS = {
    "vv_fun_patcher_gui.py::VirtualList.__init__::self":
        "the patch list: each row is laid out at the list's own width (the page around it scrolls sideways)",
}

# An EXEMPT window scrolls sideways itself (its function has a horizontal bar: horizontal_bar,
# scrolled_listbox or an xscrollcommand), or is listed here with why nothing in it can be cut off
# at the side.
EXEMPT_NOT_SIDEWAYS = {
    "vv_genealogy_window.py::show_tip": "one label that wraps at a fixed width",
    "vv_fun_patcher_gui.py::WaitWindow.__init__": "fixed size, not resizable; its message wraps",
    "vv_fun_patcher_gui.py::App._show_log_report":
        "the report is a Text box that wraps its words; the Close button sits alone under it",
    "vv_fun_patcher_gui.py::App._history_list_dialog":
        "the plan is a Text box that wraps its words; a short row of buttons under it",
    "vv_fun_patcher_gui.py::App._undo_history_dialog":
        "the plan is a Text box that wraps its words; a short row of buttons under it",
    "vv_fun_patcher_gui.py::App._move_to_save_folders_dialog":
        "the list is a Text box that wraps its words; a short row of buttons under it",
    "vv_genealogy_window.py::_show_text": "a Text box that wraps its words, in a fixed-size window",
    "vv_game_mechanics_window.py::open_game_mechanics":
        "each page is a Text box that wraps its words (the owner: no sideways scrolling to read a sentence); "
        "the minimum size keeps the pickers and buttons on screen, and the tribe list scrolls sideways "
        "(scrolled_listbox in _game_tab)",
    "vv_stew_recipes_window.py::open_stew_recipes":
        "each page is a Text box that wraps its words; the minimum size keeps the tabs and Close on screen",
}

TK_CHILD = r"""
import sys, tkinter
from tkinter import ttk
sys.path.insert(0, sys.argv[1])
import vv_tree_editor_tools as tools
try:
    root = tkinter.Tk()
except tkinter.TclError as exc:
    print(exc, file=sys.stderr)
    sys.exit(3)
root.withdraw()
window = tkinter.Toplevel(root)
frame = tools.scrollable_frame(window, padding=8)
for n in range(300):
    ttk.Label(frame, text=f"row {n}").pack(anchor="w")
window.update()
canvas = [w for w in window.winfo_children() if isinstance(w, tkinter.Canvas)]
bars = [w for w in window.winfo_children() if isinstance(w, ttk.Scrollbar)]
bars.sort(key=lambda bar: str(bar.cget("orient")) != "vertical")
print(len(canvas), len(bars), bars[0].cget("orient"), window.winfo_height(),
      window.winfo_screenheight(), bars[1].cget("orient"), int(bars[1].winfo_ismapped()))
canvas[0].yview_moveto(1.0)
print(canvas[0].yview()[0] > 0.0)
root.destroy()
"""


TK_WIDE_CHILD = r"""
import json, sys, tkinter
from tkinter import ttk
sys.path.insert(0, sys.argv[1])
import vv_scrollbars
import vv_tree_editor_tools as tools
try:
    root = tkinter.Tk()
except tkinter.TclError as exc:
    print(exc, file=sys.stderr)
    sys.exit(3)
root.withdraw()
window = tkinter.Toplevel(root)
frame = tools.scrollable_frame(window, padding=8)
wide = ttk.Label(frame, text="W" * 60)            # wider than the narrow window, narrower than the screen
wide.pack(anchor="w")
for n in range(5):
    ttk.Label(frame, text=f"row {n}").pack(anchor="w")
window.update()


def settle():
    for _ in range(6):
        window.update()


canvas = next(w for w in window.winfo_children() if isinstance(w, tkinter.Canvas))
bar = next(w for w in window.winfo_children() if isinstance(w, vv_scrollbars.AutoScrollbar))
content = frame.winfo_reqwidth()
window.geometry(f"{max(240, content // 3)}x300")
settle()
region = [float(v) for v in str(canvas.cget("scrollregion")).split()]
result = {"content_width": content, "narrow_bar_shown": bool(bar.winfo_ismapped()),
          "narrow_frame_width": frame.winfo_width(), "narrow_region_width": int(region[2] - region[0])}
wide.focus_force()
settle()
wide.event_generate("<MouseWheel>", delta=-120)
settle()
result["plain_wheel_x"] = canvas.xview()[0]
wide.event_generate("<Shift-MouseWheel>", delta=-120)
settle()
result["shift_wheel_x"] = canvas.xview()[0]
window.geometry(f"{content + 200}x300")
settle()
result.update(wide_bar_shown=bool(bar.winfo_ismapped()), wide_frame_width=frame.winfo_width(),
              wide_canvas_width=canvas.winfo_width())
other = tkinter.Toplevel(root)
holder = ttk.Frame(other)
holder.pack(fill="both", expand=True)
text = tkinter.Text(holder, width=20, height=4, wrap="none")
ybar = ttk.Scrollbar(holder, orient="vertical", command=text.yview)
text.configure(yscrollcommand=ybar.set)
ybar.pack(side="right", fill="y")
text.pack(side="left", fill="both", expand=True)
xbar = vv_scrollbars.horizontal_bar(text)
text.insert("1.0", "short")
for _ in range(6):
    other.update()
result["text_bar_short"] = bool(xbar.winfo_ismapped())
text.insert("end", "\n" + "long " * 60)
for _ in range(6):
    other.update()
result["text_bar_long"] = bool(xbar.winfo_ismapped())
holder, listbox = vv_scrollbars.scrolled_listbox(other, height=3, width=20)
holder.pack(fill="both", expand=True)
listbox.insert("end", "short")
for _ in range(6):
    other.update()
bars = [w for w in holder.winfo_children() if isinstance(w, vv_scrollbars.AutoScrollbar)]
result["list_bars_short"] = sorted(str(b.cget("orient")) for b in bars if b.winfo_ismapped())
for n in range(10):
    listbox.insert("end", f"tribe {n} " + "long " * 20)
for _ in range(6):
    other.update()
result["list_bars_long"] = sorted(str(b.cget("orient")) for b in bars if b.winfo_ismapped())
listbox.event_generate("<Shift-MouseWheel>", delta=-120, when="now")
for _ in range(6):
    other.update()
result["list_shift_x"] = listbox.xview()[0]
root.destroy()
print(json.dumps(result))
"""


def _qualname(stack: list[str]) -> str:
    return ".".join(stack)


def _scan(module: str) -> tuple[list[tuple[str, int]], dict[str, int], set[str]]:
    """(creations, helper calls per function, names imported from the helper module) for one file."""
    tree = ast.parse((SRC / module).read_text(encoding="utf-8"), filename=module)
    creations: list[tuple[str, int]] = []
    helper_calls: dict[str, int] = {}
    imported: set[str] = set()

    def visit(node: ast.AST, stack: list[str]) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ImportFrom) and child.module == "vv_tree_editor_tools":
                imported.update(alias.name for alias in child.names)
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                visit(child, stack + [child.name])
                continue
            if isinstance(child, ast.ClassDef):
                if any(isinstance(base, ast.Attribute) and base.attr == "Toplevel" for base in child.bases):
                    creations.append((child.name, child.lineno))
                visit(child, stack + [child.name])
                continue
            if isinstance(child, ast.Call):
                func = child.func
                if isinstance(func, ast.Attribute) and func.attr == "Toplevel":
                    creations.append((_qualname(stack), child.lineno))
                if isinstance(func, ast.Name) and func.id == HELPER:
                    key = _qualname(stack)
                    helper_calls[key] = helper_calls.get(key, 0) + 1
            visit(child, stack)

    visit(tree, [])
    return creations, helper_calls, imported


def _definition(module: str, qualname: str) -> str:
    """The source of a function or class in a file, found by its dotted name."""
    text = (SRC / module).read_text(encoding="utf-8")
    nodes: list = ast.parse(text, filename=module).body
    found = None
    for part in qualname.split("."):
        found = next(n for n in nodes if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                     and n.name == part)
        nodes = found.body
    return ast.get_source_segment(text, found)


def _scroll_areas(module: str) -> tuple[list[tuple[str, str, int]], set[tuple[str, str]], set[tuple[str, str]]]:
    """(vertically scrolled widgets as (function, widget, line), (function, widget) given a horizontal bar,
    (function, widget) that are Text boxes wrapping their words) for one file."""
    tree = ast.parse((SRC / module).read_text(encoding="utf-8"), filename=module)
    vertical: list[tuple[str, str, int]] = []
    sideways: set[tuple[str, str]] = set()
    wrapped: set[tuple[str, str]] = set()

    def keyword(call: ast.Call, name: str):
        return next((k.value for k in call.keywords if k.arg == name), None)

    def visit(node: ast.AST, stack: list[str]) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                visit(child, stack + [child.name])
                continue
            key = _qualname(stack)
            if isinstance(child, ast.Assign) and isinstance(child.value, ast.Call):
                wrap = keyword(child.value, "wrap")
                if isinstance(wrap, ast.Constant) and wrap.value == "word":
                    wrapped.update((key, ast.unparse(target)) for target in child.targets)
            if isinstance(child, ast.Call):
                func = child.func
                if isinstance(func, ast.Attribute) and func.attr == "Scrollbar":
                    command, orient = keyword(child, "command"), keyword(child, "orient")
                    horizontal = isinstance(orient, ast.Constant) and orient.value == "horizontal"
                    if isinstance(command, ast.Attribute) and command.attr in ("xview", "yview"):
                        widget = ast.unparse(command.value)
                        if horizontal and command.attr == "xview":
                            sideways.add((key, widget))
                        elif not horizontal and command.attr == "yview":
                            vertical.append((key, widget, child.lineno))
                if isinstance(func, ast.Name) and func.id == "horizontal_bar" and child.args:
                    sideways.add((key, ast.unparse(child.args[0])))
            visit(child, stack)

    visit(tree, [])
    return vertical, sideways, wrapped


class WindowScrollbars(unittest.TestCase):
    def test_every_scrolling_area_scrolls_sideways_too(self):
        problems, seen = [], set()
        for path in sorted(SRC.glob("*.py")):
            if "Scrollbar(" not in path.read_text(encoding="utf-8"):
                continue
            vertical, sideways, wrapped = _scroll_areas(path.name)
            for function, widget, line in vertical:
                key = f"{path.name}::{function}::{widget}"
                if key in NO_SIDEWAYS:
                    seen.add(key)
                elif (function, widget) not in sideways and (function, widget) not in wrapped:
                    problems.append(f"{key} (line {line}): a vertical bar but no horizontal_bar")
        self.assertEqual(problems, [])
        self.assertEqual(sorted(set(NO_SIDEWAYS) - seen), [], "NO_SIDEWAYS lists areas that no longer exist")

    def test_helper_has_a_horizontal_bar_and_shift_wheel(self):
        source = _definition(HELPER_MODULE, HELPER)
        self.assertIn("horizontal_bar(canvas)", source)
        self.assertIn("fill_or_keep_width(canvas, item, frame)", source)
        self.assertIn("scroll_sideways(canvas, event)", source)
        # The notebook pages that scroll (the tree editor's tabs) do the same.
        source = _definition(HELPER_MODULE, "ScrollingTab")
        self.assertIn("horizontal_bar(canvas)", source)
        self.assertIn("fill_or_keep_width(canvas, window, self)", source)
        self.assertIn("scroll_sideways(canvas, event)", source)

    def test_every_exempt_window_scrolls_sideways_or_says_why_not(self):
        problems = []
        for key in EXEMPT:
            module, name = key.split("::")
            source = _definition(module, name)
            sideways = any(word in source for word in ("horizontal_bar(", "scrolled_listbox(", "xscrollcommand"))
            if sideways and key in EXEMPT_NOT_SIDEWAYS:
                problems.append(f"{key} scrolls sideways now: take it out of EXEMPT_NOT_SIDEWAYS")
            elif not sideways and key not in EXEMPT_NOT_SIDEWAYS:
                problems.append(f"{key}: no horizontal bar and no reason in EXEMPT_NOT_SIDEWAYS")
        self.assertEqual(problems, [])
        self.assertEqual(sorted(set(EXEMPT_NOT_SIDEWAYS) - set(EXEMPT)), [])

    def test_real_window_scrolls_sideways_when_narrower_than_its_content(self):
        done = subprocess.run([sys.executable, "-c", TK_WIDE_CHILD, str(SRC)],
                              capture_output=True, text=True, timeout=120)
        if done.returncode == NO_TK:
            self.skipTest("no Tk display: " + done.stderr.strip())
        self.assertEqual(done.returncode, 0, done.stderr)
        result = json.loads(done.stdout.strip().splitlines()[-1])
        # Narrow: the content keeps its width, the bar shows, and Shift + wheel moves it sideways.
        self.assertTrue(result["narrow_bar_shown"], result)
        self.assertGreaterEqual(result["narrow_frame_width"], result["content_width"], result)
        self.assertGreaterEqual(result["narrow_region_width"], result["content_width"], result)
        self.assertGreater(result["shift_wheel_x"], 0.0, result)
        self.assertEqual(result["plain_wheel_x"], 0.0, "the plain wheel must not scroll sideways")
        # Wide: the content fills the window, as before, and the bar is gone.
        self.assertFalse(result["wide_bar_shown"], result)
        self.assertEqual(result["wide_frame_width"], result["wide_canvas_width"], result)
        # A Text box that does not wrap gets its bar only when a line is wider than the box.
        self.assertFalse(result["text_bar_short"], result)
        self.assertTrue(result["text_bar_long"], result)
        # A tribe list (scrolled_listbox): no bars while it fits, both once it is longer and wider.
        self.assertEqual(result["list_bars_short"], [], result)
        self.assertEqual(result["list_bars_long"], ["horizontal", "vertical"], result)
        self.assertGreater(result["list_shift_x"], 0.0, result)

    def test_helper_is_a_canvas_with_a_vertical_scrollbar(self):
        tree = ast.parse((SRC / HELPER_MODULE).read_text(encoding="utf-8"))
        helpers = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == HELPER]
        self.assertEqual(len(helpers), 1, f"{HELPER} must be defined once in {HELPER_MODULE}")
        source = ast.get_source_segment((SRC / HELPER_MODULE).read_text(encoding="utf-8"), helpers[0])
        self.assertIn("tk.Canvas(", source)
        self.assertIn("ttk.Scrollbar(", source)
        self.assertIn('orient="vertical"', source)
        self.assertIn("create_window", source)
        self.assertIn('bind("<MouseWheel>"', source)

    def test_every_window_goes_through_the_helper_or_is_exempt(self):
        problems = []
        seen_exempt = set()
        for module in WINDOW_MODULES:
            creations, helper_calls, imported = _scan(module)
            if module != HELPER_MODULE and any(f"{module}::{name}" not in EXEMPT for name, _line in creations):
                self.assertIn(HELPER, imported, f"{module} must import {HELPER} from {HELPER_MODULE}")
            per_function: dict[str, int] = {}
            for name, line in creations:
                key = f"{module}::{name}"
                if key in EXEMPT:
                    seen_exempt.add(key)
                    continue
                per_function[name] = per_function.get(name, 0) + 1
            for name, count in per_function.items():
                if helper_calls.get(name, 0) < count:
                    problems.append(f"{module}::{name}: {count} window(s) but "
                                    f"{helper_calls.get(name, 0)} {HELPER} call(s)")
        self.assertEqual(problems, [])
        stale = sorted(set(EXEMPT) - seen_exempt)
        self.assertEqual(stale, [], "EXEMPT lists windows that no longer exist")

    def test_real_window_gets_a_scroll_bar_when_content_is_taller_than_the_screen(self):
        done = subprocess.run([sys.executable, "-c", TK_CHILD, str(SRC)],
                              capture_output=True, text=True, timeout=120)
        if done.returncode == NO_TK:
            self.skipTest("no Tk display: " + done.stderr.strip())
        self.assertEqual(done.returncode, 0, done.stderr)
        lines = done.stdout.strip().splitlines()
        canvases, bars, orient, height, screen, sideways, shown = lines[0].split()
        # A vertical bar, and a horizontal one that stays hidden while the content fits the width.
        self.assertEqual((canvases, bars, orient, sideways, shown), ("1", "2", "vertical", "horizontal", "0"))
        self.assertLessEqual(int(height), int(screen), "the window must stay on the screen")
        self.assertEqual(lines[1], "True", "the wheel-scrolled canvas must move to the bottom")


if __name__ == "__main__":
    unittest.main()
