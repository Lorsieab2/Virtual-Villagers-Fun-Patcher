"""Every "Please wait" can be closed, and a read-only check is not made twice (the owner, v1.35.97).

The owner pressed Repair Saves & Logs on a 378-villager village on a busy computer: "Checking the logs...
Nothing is changed." ran on and on, and its window could not be closed.  Two things are pinned here:

  * the wait window has a Cancel button and a working close button.  Work that only reads stops at once
    (WaitCancelled, which App.report_callback_exception ends quietly); work that writes files carries on
    and says why, so nothing is ever left half-written.  A failure in the work is raised on the main
    thread and, when no handler takes it, shown in a message instead of vanishing;
  * Check Saves & Logs makes the read-only reconciliation (the slowest read of a large village) once, not
    twice, and hands Repair Saves & Logs the plan it made, so Repair does not plan again.
"""
from __future__ import annotations

import sys
import threading
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

GUI_SOURCE = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")

try:
    import tkinter as tk
except ImportError:  # pragma: no cover - platform without Tk
    tk = None

if tk is not None:
    import vv_fun_patcher_gui as gui

import vv_log_additions  # noqa: E402
import vv_log_tools  # noqa: E402
import vv_reconcile  # noqa: E402
from test_log_tools import FolderTest  # noqa: E402


def _tk_available() -> bool:
    if tk is None:
        return False
    try:
        probe = tk.Tk()
    except tk.TclError:
        return False
    probe.destroy()
    return True


@unittest.skipUnless(tk is not None and _tk_available(), "Tk display is not available")
class WaitCanBeClosedTests(unittest.TestCase):
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

    def _wait_window(self):
        tops = self._toplevels()
        self.assertEqual(len(tops), 1, tops)
        return tops[0]

    @staticmethod
    def _buttons(widget) -> list:
        found = []
        for child in widget.winfo_children():
            if child.winfo_class() == "TButton":
                found.append(child)
            found += WaitCanBeClosedTests._buttons(child)
        return found

    def _press_later(self, how: str, seen: dict) -> None:
        def press() -> None:
            top = self._wait_window()
            seen["buttons"] = [str(b.cget("text")) for b in self._buttons(top)]
            if how == "cancel":
                self._buttons(top)[0].invoke()
            else:                                   # the title bar's close button
                self.app.tk.call(top.protocol("WM_DELETE_WINDOW"))
            seen["pressed"] = True
        self.app.after(150, press)

    def _blocking_work(self, release: threading.Event, done: threading.Event):
        def work():
            release.wait(30)
            done.set()
            return "finished"
        return work

    def test_cancel_stops_a_read_only_wait_and_closes_it(self) -> None:
        for how in ("cancel", "close"):
            with self.subTest(how=how):
                release, done, seen = threading.Event(), threading.Event(), {}
                self._press_later(how, seen)
                try:
                    with self.assertRaises(gui.WaitCancelled):
                        self.app._run_with_wait("Checking the logs…\n\nNothing is changed.",
                                                self._blocking_work(release, done))
                    self.assertTrue(seen.get("pressed"))
                    self.assertEqual(seen["buttons"], ["Cancel"])
                    self.assertFalse(done.is_set(), "the wait closed before the work finished")
                    self.assertEqual(self._toplevels(), [])
                finally:
                    release.set()

    def test_cancellable_can_be_given_by_the_caller(self) -> None:
        release, done, seen = threading.Event(), threading.Event(), {}
        self._press_later("cancel", seen)
        try:
            with self.assertRaises(gui.WaitCancelled):
                self.app._run_with_wait("Checking all five original games.", self._blocking_work(release, done),
                                        cancellable=True)
        finally:
            release.set()
        self.assertEqual(self._toplevels(), [])

    def test_work_that_writes_carries_on_and_says_why(self) -> None:
        release, done, seen = threading.Event(), threading.Event(), {}
        self._press_later("cancel", seen)
        self.app.after(600, release.set)
        result = self.app._run_with_wait("Repairing the logs…\n\nThe save folder is backed up first.",
                                         self._blocking_work(release, done))
        self.assertTrue(seen.get("pressed"))
        self.assertEqual(result, "finished")
        self.assertTrue(done.is_set())
        self.assertEqual(self._toplevels(), [])

    def test_a_failure_closes_the_wait_and_reaches_the_caller(self) -> None:
        def boom():
            raise RuntimeError("unexpected")

        with self.assertRaises(RuntimeError):
            self.app._run_with_wait("Checking the logs…\n\nNothing is changed.", boom)
        self.assertEqual(self._toplevels(), [])

    def test_a_cancel_ends_quietly_and_an_uncaught_error_is_shown(self) -> None:
        with mock.patch.object(gui.messagebox, "showerror") as shown, \
                mock.patch("sys.stderr"):
            self.app.report_callback_exception(gui.WaitCancelled, gui.WaitCancelled(), None)
            shown.assert_not_called()
            self.assertEqual(self.app.status_var.get(), "Cancelled. Nothing was changed.")
            try:
                raise ValueError("a bad value")
            except ValueError as exc:
                self.app.report_callback_exception(ValueError, exc, exc.__traceback__)
            shown.assert_called_once()
            self.assertIn("a bad value", shown.call_args.args[1])

    def test_the_startup_splash_still_has_no_cancel(self) -> None:
        splash = gui.WaitWindow(self.app, "Please wait", "Loading.", modal=False)
        try:
            self.assertEqual(self._buttons(splash._window), [])
        finally:
            splash.close()


class ReconcileOnceTests(FolderTest):
    def test_check_logs_reconciles_once_and_keeps_its_plan(self) -> None:
        folder = self.make_folder("huttest", 3, "Modded")
        real = vv_reconcile.reconcile
        calls = []

        def counted(*args, **kwargs):
            calls.append(args)
            return real(*args, **kwargs)

        with mock.patch.object(vv_reconcile, "reconcile", counted):
            result = vv_log_tools.check_logs(folder, 1, 3)
        self.assertEqual(len(calls), 1, "the reconciliation was made more than once")
        self.assertIsNotNone(result.kinds)
        fresh = vv_log_additions.plan(folder, 3, 1)
        self.assertEqual([k.id for k in result.kinds], [k.id for k in fresh])
        self.assertEqual([sorted(k.questions) for k in result.kinds], [sorted(k.questions) for k in fresh])

    def test_repair_uses_the_checks_plan(self) -> None:
        body = GUI_SOURCE[GUI_SOURCE.index("    def _repair_logs("):]
        survey = body[:body.index("        try:\n            (checked, old_words, kinds")]
        self.assertIn("kinds = checked.kinds", survey)
        self.assertIn("if kinds is None:", survey)


if __name__ == "__main__":
    unittest.main()
