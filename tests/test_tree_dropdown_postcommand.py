"""A drop-down's own postcommand still runs when the Family Tree Maker widens its list.

The owner, 2026-11-25 (Python 3.14): every drop-down printed "TypeError: '_tkinter.Tcl_Obj' object is
not callable" from _widen_popdown -- cget("postcommand") gave the box's command back as a Tcl object,
neither a str nor a Python callable -- and the list was never widened.
"""
from __future__ import annotations

import sys
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import ttk

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import vv_genealogy_window as gw  # noqa: E402


class WidenPopdown(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            cls.root = tk.Tk()
        except tk.TclError as e:
            raise unittest.SkipTest(f"no display for Tk: {e}")
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.root.destroy()

    def test_the_boxs_own_command_runs_whatever_type_cget_returns(self) -> None:
        ran = []
        combo = ttk.Combobox(self.root, values=["a short one", "a much, much longer choice than the box"],
                             postcommand=lambda: ran.append(1))
        name = str(combo.cget("postcommand"))

        class TclObjLike:                           # what cget gave on the owner's Python 3.14: not a str,
            def __str__(self) -> str:               # not callable, its string the Tcl command's name
                return name

        for before in (combo.cget("postcommand"), TclObjLike()):
            gw.TreeEditor._widen_popdown(combo, before)()
        self.assertEqual(ran, [1, 1])
        self.assertTrue(combo.cget("style").startswith("List"))

    def test_no_command_of_its_own(self) -> None:
        combo = ttk.Combobox(self.root, values=["x"])
        gw.TreeEditor._widen_popdown(combo, combo.cget("postcommand"))()

    def test_a_python_callable(self) -> None:
        ran = []
        combo = ttk.Combobox(self.root, values=["x"])
        gw.TreeEditor._widen_popdown(combo, lambda: ran.append(1))()
        self.assertEqual(ran, [1])


if __name__ == "__main__":
    unittest.main()
