"""The patcher must never sit on the main thread with no sign of life.

Copying a whole game folder and rendering patched bytes takes long enough that
Windows relabels the window "(Not Responding)".  Nothing is wrong when that
happens, but it reads as a crash, and players close the patcher mid-copy.

Two things have to hold for the wait window to actually help:

  * the work runs OFF the main thread, so the event loop can keep painting --
    a wait window drawn and then blocked behind a synchronous call is exactly
    as frozen as no wait window at all; and
  * the work never touches Tk, because every caller reads its Tk variables on
    the main thread first.  Reading a Tk variable from another thread is not
    safe, and the failure is intermittent, so it is guarded here rather than
    left to be noticed in the field.
"""
from __future__ import annotations

import ast
import re
import sys
import threading
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
        probe = tk.Tk()
    except tk.TclError:
        return False
    probe.destroy()
    return True


# The calls that block long enough to look like a hang.
BLOCKING_CALLS = frozenset(
    {"apply_patch", "apply_all", "dry_run", "dry_run_all", "validate_all_sources"}
)

# App methods that read a Tk variable, so they are main-thread only.
TK_ACCESSORS = frozenset({"_mode", "_output_root", "_selected_fun_patch_ids"})

# Matched on the tree, not on the text.  A first attempt at these guards
# compared strings and both were vacuous: the "is it inside _run_with_wait"
# check looked at everything preceding the call, which already contained an
# earlier _run_with_wait, and the lambda-body regex silently matched none of
# the single-line lambdas.  Each passed on the exact regression it named.
TREE = ast.parse(GUI_SOURCE)
APP = next(
    node for node in ast.walk(TREE) if isinstance(node, ast.ClassDef) and node.name == "App"
)


def _method(name: str) -> ast.FunctionDef:
    for node in APP.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"App.{name} not found")


def _called_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _wait_lambdas(scope: ast.AST) -> list[ast.Lambda]:
    """Every lambda handed to _run_with_wait -- i.e. every off-thread body."""
    found = []
    for node in ast.walk(scope):
        if isinstance(node, ast.Call) and _called_name(node) == "_run_with_wait":
            found.extend(arg for arg in node.args if isinstance(arg, ast.Lambda))
    return found


def _handler_body(name: str) -> str:
    """Return the source of one App method, up to the next method."""
    match = re.search(rf"\n    def {name}\(self\)[^\n]*:\n(.*?)(?=\n    def )", GUI_SOURCE, re.S)
    assert match, f"{name} not found in the GUI source"
    return match.group(1)


class PleaseWaitSourceTests(unittest.TestCase):
    """These read source because the guarantee is structural, not runtime."""

    def test_the_blocking_calls_go_through_the_wait_window(self) -> None:
        for handler in ("_apply", "_apply_all"):
            method = _method(handler)
            off_thread = {
                id(node)
                for lam in _wait_lambdas(method)
                for node in ast.walk(lam)
            }
            blocking = [
                node
                for node in ast.walk(method)
                if isinstance(node, ast.Call) and _called_name(node) in BLOCKING_CALLS
            ]
            # If this handler stopped making blocking calls entirely the loop
            # below would pass without checking anything.
            self.assertTrue(blocking, f"{handler} makes no blocking call at all")
            for node in blocking:
                with self.subTest(handler=handler, call=_called_name(node), line=node.lineno):
                    self.assertIn(
                        id(node),
                        off_thread,
                        f"{handler} calls {_called_name(node)} on line {node.lineno} "
                        f"directly instead of through _run_with_wait; that blocks "
                        f"the Tk main thread and the patcher looks frozen for the "
                        f"whole duration",
                    )

    def test_tk_variables_are_not_read_from_the_worker_thread(self) -> None:
        """The lambdas handed to _run_with_wait run off the main thread."""
        checked = 0
        for handler in ("_apply", "_apply_all"):
            lambdas = _wait_lambdas(_method(handler))
            self.assertTrue(lambdas, f"{handler} runs nothing off the main thread")
            for lam in lambdas:
                checked += 1
                for node in ast.walk(lam):
                    if not isinstance(node, ast.Call):
                        continue
                    func = node.func
                    if not isinstance(func, ast.Attribute):
                        continue
                    if not (isinstance(func.value, ast.Name) and func.value.id == "self"):
                        continue
                    with self.subTest(handler=handler, accessor=func.attr):
                        self.assertNotIn(
                            func.attr,
                            TK_ACCESSORS,
                            f"{handler} reads a Tk variable via self.{func.attr}() "
                            f"on line {node.lineno}, inside work that runs on a "
                            f"worker thread; Tk variables are main-thread only, and "
                            f"the resulting corruption is intermittent",
                        )
        self.assertGreaterEqual(checked, 4, "expected both handlers to defer several calls")

    def test_the_startup_load_is_covered_too(self) -> None:
        """The window is invisible until _build_ui finishes, so cover that too."""
        init = _handler_body("__init__")
        self.assertIn("WaitWindow(", init)
        self.assertIn("self.withdraw()", init)
        for loader in ("load_builds()", "load_public_fun_patches()", "self._build_ui()"):
            with self.subTest(loader=loader):
                self.assertLess(
                    init.index("WaitWindow("),
                    init.index(loader),
                    f"{loader} runs before the splash is up, so it happens with "
                    f"nothing on screen",
                )
        self.assertLess(init.index("self._build_ui()"), init.index("splash.close()"))


@unittest.skipUnless(tk is not None and _tk_available(), "Tk display is not available")
class RunWithWaitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            cls.app = gui.App()
        except tk.TclError as exc:  # pragma: no cover - Tk is flaky under pytest
            raise unittest.SkipTest(f"Tk could not start: {exc}") from exc
        cls.app.withdraw()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.app.destroy()

    def _toplevels(self) -> list:
        return [child for child in self.app.winfo_children() if isinstance(child, tk.Toplevel)]

    def test_the_startup_splash_does_not_outlive_the_load(self) -> None:
        """A splash left on screen is worse than no splash."""
        self.assertEqual(self._toplevels(), [])

    def test_it_returns_the_workers_value(self) -> None:
        self.assertEqual(self.app._run_with_wait("working", lambda: 21 * 2), 42)

    def test_the_work_runs_off_the_main_thread(self) -> None:
        """The point of the thread: the main thread stays free to repaint."""
        main = threading.get_ident()
        worker = self.app._run_with_wait("working", threading.get_ident)
        self.assertNotEqual(worker, main)

    def test_a_failure_is_re_raised_on_the_main_thread(self) -> None:
        """Otherwise the exception dies in the thread and the caller's
        `except PatcherError` never runs -- the patcher would report success
        for a patch that never happened."""
        def boom():
            raise OSError("disk full")

        with self.assertRaises(OSError):
            self.app._run_with_wait("working", boom)

    def test_the_wait_window_is_closed_even_when_the_work_fails(self) -> None:
        def boom():
            raise OSError("disk full")

        with self.assertRaises(OSError):
            self.app._run_with_wait("working", boom)
        self.assertEqual(self._toplevels(), [])

    def test_the_wait_window_is_closed_when_the_work_succeeds(self) -> None:
        self.app._run_with_wait("working", lambda: None)
        self.assertEqual(self._toplevels(), [])


if __name__ == "__main__":
    unittest.main()
