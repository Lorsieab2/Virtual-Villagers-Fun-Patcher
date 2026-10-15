"""Every window the patcher opens scrolls when its content is taller than the screen.

A window's controls go in vv_tree_editor_tools.scrollable_frame: a Canvas with a vertical
Scrollbar and an inner frame, the wheel scrolling it while the pointer is over the window.
The static check below walks the three GUI modules that create windows and requires every
Toplevel creation either to use that helper, or to be listed in EXEMPT with the reason it
already scrolls (or cannot grow). The Tk check builds one real window and skips cleanly
when there is no Tk display.
"""
from __future__ import annotations

import ast
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
HELPER = "scrollable_frame"
HELPER_MODULE = "vv_tree_editor_tools.py"
WINDOW_MODULES = ["vv_fun_patcher_gui.py", "vv_genealogy_window.py", HELPER_MODULE]
NO_TK = 3

# file::enclosing function (Class.method, nested as outer.inner), or file::ClassName for a
# Toplevel subclass. Each one is a window that already scrolls, or cannot grow, so it does not
# go through the helper.
EXEMPT = {
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
    "vv_tree_editor_tools.py::choose_font":
        "a font list (Text) with its own scroll bar; the search box and buttons sit around it",
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
print(len(canvas), len(bars), bars[0].cget("orient"), window.winfo_height(),
      window.winfo_screenheight())
canvas[0].yview_moveto(1.0)
print(canvas[0].yview()[0] > 0.0)
root.destroy()
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


class WindowScrollbars(unittest.TestCase):
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
            if module != HELPER_MODULE:
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
        canvases, bars, orient, height, screen = lines[0].split()
        self.assertEqual((canvases, bars, orient), ("1", "1", "vertical"))
        self.assertLessEqual(int(height), int(screen), "the window must stay on the screen")
        self.assertEqual(lines[1], "True", "the wheel-scrolled canvas must move to the bottom")


if __name__ == "__main__":
    unittest.main()
