"""Repair Saves & Logs: last names -- "Sort by:" (the owner, v1.35.80), in the last-names window and in
"Each villager's own rule...": Alphabetical (first name, then last name; numbered names in numeral order),
Arrived at top (each group in the order shown), Age (oldest to youngest; ties by name), and As in the
save (the order both windows always used, the default).  Re-sorting only moves the rows: every box keeps
its chosen last name and edits, and nothing is written until OK."""
from __future__ import annotations

import sys
import unittest
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher_gui as gui  # noqa: E402


@dataclass
class V:
    name: str
    age: int | None = None
    arrived: bool = False
    alive: bool = True


PEOPLE = [V("kalama ii", 300), V("Zola Jumapili", 900, True), V("Azizi Kalama X", 100), V("Azizi Kalama II", 500),
          V("Azizi Kalama I", 500), V("Mosi", None, True), V("azizi Bahati", 700, alive=False)]


def names(order):
    return [PEOPLE[k].name for k in order]


class TheOrders(unittest.TestCase):
    def test_the_choices_and_the_default(self):
        self.assertEqual(gui.LAST_NAMES_SORTS, ("As in the save", "Alphabetical (first name, then last name)",
                                                "Arrived at top", "Age (oldest to youngest)"))
        self.assertEqual(gui.last_names_order(PEOPLE, gui.SORT_AS_SAVED), list(range(len(PEOPLE))))

    def test_alphabetical_is_case_insensitive_with_numerals_in_order(self):
        self.assertEqual(names(gui.last_names_order(PEOPLE, gui.SORT_ALPHABETICAL)),
                         ["azizi Bahati", "Azizi Kalama I", "Azizi Kalama II", "Azizi Kalama X", "kalama ii",
                          "Mosi", "Zola Jumapili"])

    def test_arrived_at_top_keeps_each_group_in_the_order_shown(self):
        self.assertEqual(names(gui.last_names_order(PEOPLE, gui.SORT_ARRIVED)),
                         ["Zola Jumapili", "Mosi", "kalama ii", "Azizi Kalama X", "Azizi Kalama II", "Azizi Kalama I",
                          "azizi Bahati"])
        alphabetical = gui.last_names_order(PEOPLE, gui.SORT_ALPHABETICAL)
        self.assertEqual(names(gui.last_names_order(PEOPLE, gui.SORT_ARRIVED, alphabetical)),
                         ["Mosi", "Zola Jumapili", "azizi Bahati", "Azizi Kalama I", "Azizi Kalama II",
                          "Azizi Kalama X", "kalama ii"])

    def test_age_oldest_first_ties_by_name_unknown_last(self):
        self.assertEqual(names(gui.last_names_order(PEOPLE, gui.SORT_AGE)),
                         ["Zola Jumapili", "azizi Bahati", "Azizi Kalama I", "Azizi Kalama II", "kalama ii",
                          "Azizi Kalama X", "Mosi"])


class TheWindows(unittest.TestCase):
    def setUp(self):
        self.source = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")

    def _method(self, name: str, end: str) -> str:
        return self.source[self.source.index(f"    def {name}("):self.source.index(f"    def {end}(")]

    def test_both_windows_have_sort_by_remembered_for_the_session(self):
        for method in (self._method("_last_names_dialog", "_own_rules_dialog"),
                       self._method("_own_rules_dialog", "_repair_questions")):
            self.assertIn('text="Sort by:"', method)
            self.assertIn('getattr(self, "_last_names_sort", SORT_AS_SAVED)', method)
            self.assertIn("self._last_names_sort = sort_var.get()", method)
            # Re-sorting only moves the rows' widgets: their boxes keep what is in them.
            self.assertIn("widget.grid_configure(row=place)", method)

    def test_edits_survive_a_re_sort(self):
        try:
            import tkinter as tk
            from tkinter import ttk
            root = tk.Tk()
        except Exception as exc:                 # no display
            self.skipTest(f"Tk is not available: {exc}")
        self.addCleanup(root.destroy)
        root.withdraw()
        frame = ttk.Frame(root)
        rows, values = [], []
        for k, v in enumerate(PEOPLE):
            var = tk.StringVar(value=f"last{k}")
            ttk.Label(frame, text=v.name).grid(row=k, column=0)
            ttk.Combobox(frame, textvariable=var).grid(row=k, column=1)
            rows.append(frame.grid_slaves(row=k))
            values.append(var)
        values[3].set("typed by the player")
        shown = list(range(len(PEOPLE)))
        for sort in (gui.SORT_ALPHABETICAL, gui.SORT_AGE, gui.SORT_ARRIVED, gui.SORT_AS_SAVED):
            shown[:] = gui.last_names_order(PEOPLE, sort, shown)
            for place, k in enumerate(shown):
                for widget in rows[k]:
                    widget.grid_configure(row=place)
            for place, k in enumerate(shown):
                label = next(w for w in frame.grid_slaves(row=place) if isinstance(w, ttk.Label))
                self.assertEqual(label.cget("text"), PEOPLE[k].name)
        self.assertEqual([v.get() for v in values][3], "typed by the player")
        self.assertEqual([v.get() for k, v in enumerate(values) if k != 3], [f"last{k}" for k in range(7) if k != 3])


if __name__ == "__main__":
    unittest.main()
