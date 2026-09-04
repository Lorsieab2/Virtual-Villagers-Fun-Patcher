"""A wait window that is not actually modal is worse than none at all.

The grab is the only thing stopping a second click on Apply while the first
one is still running. Tk refuses `grab_set()` with TclError until the window
manager has made the window viewable, so the natural-looking

    try:
        window.grab_set()
    except tk.TclError:
        pass

silently leaves every control underneath live. The window still looks modal --
it is drawn, it holds the foreground, it says please wait -- while a
double-click on Apply gets through twice and starts two patch workers against
the same output folder.

This came back from the Virtual Families 2 patcher, which had adopted this
window wholesale and had the identical bug found in review there. The obvious
repair, calling `wait_visibility()` first, is a trap: it blocks forever when
the window never becomes viewable, which is exactly what a withdrawn or
iconified parent produces, and it hung that project's GUI suite outright. So
the grab retries against a deadline instead and raises if it never lands.

The assertion here is on the grab actually being held, not on no exception
having been raised -- the old code raised no exception either.
"""
from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

GUI_SOURCE = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")

try:
    import tkinter as tk
except ImportError:  # pragma: no cover - platform without Tk
    tk = None

if tk is not None:
    import vv_fun_patcher_gui as gui


def _tk_available() -> bool:
    if tk is None:
        return False
    try:
        root = tk.Tk()
    except Exception:
        return False
    root.destroy()
    return True


TK = _tk_available()


class TestGrabIsNotSwallowed(unittest.TestCase):
    """Source-level, so it holds on machines with no display."""

    def _take_grab_body(self) -> str:
        """The function's CODE, with its docstring dropped.

        The docstring explains why wait_visibility() is the wrong repair, so
        scanning the whole segment for that name would match the warning
        against it as readily as a use of it.
        """
        tree = ast.parse(GUI_SOURCE)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_take_grab":
                body = node.body
                if body and isinstance(body[0], ast.Expr) and isinstance(
                    body[0].value, ast.Constant
                ) and isinstance(body[0].value.value, str):
                    body = body[1:]
                return chr(10).join(
                    ast.get_source_segment(GUI_SOURCE, statement) or ""
                    for statement in body
                )
        self.fail("WaitWindow._take_grab is gone; the grab must stay guarded")

    def test_a_failed_grab_is_never_passed_over(self):
        body = self._take_grab_body()
        self.assertIn("raise", body, "an exhausted deadline must surface, not pass")
        self.assertNotIn(
            "wait_visibility",
            body,
            "wait_visibility blocks forever on a withdrawn parent; use the deadline",
        )

    def test_the_deadline_is_bounded_and_short(self):
        self.assertGreater(gui.GRAB_TIMEOUT_SECONDS, 0)
        self.assertLessEqual(gui.GRAB_TIMEOUT_SECONDS, 10)
        self.assertGreater(gui.GRAB_POLL_SECONDS, 0)
        self.assertLess(gui.GRAB_POLL_SECONDS, gui.GRAB_TIMEOUT_SECONDS)


@unittest.skipUnless(TK, "needs a Tk display")
class TestGrabIsActuallyHeld(unittest.TestCase):
    def _root(self):
        """A Tk root, or a skip.

        The probe at import time is not a guarantee: this project's Windows
        Python can fail a later Tk() with "couldn't read file init.tcl" after
        an identical probe has just succeeded. That is an install fault, not a
        result about the grab, so it must not read as a failure here.
        """
        try:
            return tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk became unavailable mid-run: {exc}")

    def test_the_wait_window_holds_the_grab(self):
        root = self._root()
        root.geometry("300x200+100+100")
        try:
            root.update()
            wait = gui.WaitWindow(root, "Please wait", "Please wait…")
            try:
                self.assertEqual(
                    str(root.grab_current()),
                    str(wait._window),
                    "the wait window is drawn but the controls underneath are live",
                )
            finally:
                wait.close()
        finally:
            root.destroy()

    def test_a_withdrawn_parent_does_not_hang(self):
        # The wait_visibility() trap: this call used to block forever.
        root = self._root()
        root.withdraw()
        try:
            wait = gui.WaitWindow(root, "Please wait", "Please wait…")
            wait.close()
        except tk.TclError:
            pass  # a raised grab failure is the sanctioned outcome; a hang is not
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
