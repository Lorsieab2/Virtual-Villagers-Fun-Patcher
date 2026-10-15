"""The last-names window's "the rule gives" marks and Check Saves & Logs' wrong last names read the same rules
(v1.35.73, critical; the owner's screenshots of A New Home, Kalahuna Tribe 1).

Under "Last names come from: From the father" the window said "23 last name(s) are not what the rule gives"
and marked, among others, Akika Akikai (father Hoto Okelani, mother Aika Akikai) "the rule gives Temitope"
-- neither the father's last name nor the rule shown.  Fix wrong last names and reopening gave the same.

The cause (reproduced on a copy of the owner's folder): the window computed its marks from the LIVING
villagers' own rules only (saved_own, filtered to living keys), while the record also keeps the own rules of
dead fathers (Hiji Temitope, Pili Sirikit, Turi Uzumati: 50:50).  Without Hiji's 50:50 the window re-derived
Aika Akikai (father Hiji Temitope) as "Temitope" by the village's From the father, and then Akika (whose
father Hoto Okelani's own rule is 50:50) as one of Okelani/Temitope, never Akikai.  Check Saves & Logs read
every line and found only Tiki Alosaka II.  Both now use expected_last_names with the same rules
(check_rules), a 50:50 child carrying either parent's last name is right in both, and a mark given by a
parent's own rule says so instead of "the rule gives".
"""
from __future__ import annotations

import sys
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_last_names as ln  # noqa: E402

GUI_SOURCE = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")


def village():
    """The owner's shape, A New Home: Hiji Temitope (dead, own rule 50:50) and Ashby Akikai (dead) are Aika
    Akikai's parents; Hoto Okelani (own rule 50:50, his last name set by the player) and Aika are Akika
    Akikai's; Bo Powaka (no own rule) and Aika are Nalu Powaka's (right) and Mele Akikai's (wrong)."""
    L = ln.Living
    people = [
        L(0, "Hoto Okelani", "Male", 18, 5, 1, "Okelani"),
        L(1, "Aika Akikai", "Female", 3, 3, 1, "Akikai"),
        L(2, "Akika Akikai", "Female", 4, 4, 1, "Akikai"),
        L(3, "Bo Powaka", "Male", 6, 6, 1, "Powaka"),
        L(4, "Nalu Powaka", "Male", 7, 7, 1, "Powaka"),
        L(5, "Mele Akikai", "Female", 8, 8, 1, "Akikai"),
        L(-1, "Hiji Temitope", "Male", 17, 11, 0, "", alive=False),
        L(-1, "Ashby Akikai", "Female", 9, 9, 0, "", alive=False),
    ]
    by = {v.name: v for v in people}
    key = lambda name: by[name].identity  # noqa: E731
    parents = {key("Aika Akikai"): (key("Hiji Temitope"), key("Ashby Akikai")),
               key("Akika Akikai"): (key("Hoto Okelani"), key("Aika Akikai")),
               key("Nalu Powaka"): (key("Bo Powaka"), key("Aika Akikai")),
               key("Mele Akikai"): (key("Bo Powaka"), key("Aika Akikai"))}
    own = {ln.own_key(by["Hiji Temitope"]): "random", ln.own_key(by["Hoto Okelani"]): "random"}
    return people, parents, own, by


def carried(name: str) -> str:
    return ln.split_name(1, name, {"Okelani"})[1]


class OneReading(unittest.TestCase):
    """expected_last_names is the one reading both the window and the check use."""

    def expected(self, pending=None):
        people, parents, own, by = village()
        living_keys = {ln.own_key(v) for v in people if v.alive}
        pending = {k: r for k, r in own.items() if k in living_keys} if pending is None else pending
        fixed = {by["Hoto Okelani"].identity: "Okelani"}
        return ln.expected_last_names(people, parents, "father", None, ln.with_siblings(fixed, parents), carried,
                                      ln.check_rules(own, pending, living_keys)), by

    def test_from_the_father_gives_the_fathers_last_name(self):
        want, by = self.expected()
        self.assertEqual(want[by["Nalu Powaka"].identity], ("Powaka", "father", ()))
        self.assertEqual(want[by["Mele Akikai"].identity][0], "Powaka")
        self.assertTrue(ln.wrong_last_name("Akikai", *want[by["Mele Akikai"].identity][::2]))
        self.assertFalse(ln.wrong_last_name("Powaka", *want[by["Nalu Powaka"].identity][::2]))

    def test_a_dead_fathers_own_rule_still_decides_his_childs_name(self):
        want, by = self.expected()
        should, used, either = want[by["Aika Akikai"].identity]
        self.assertEqual(used, "random", "Hiji Temitope is dead, and his 50:50 was the rule at her birth")
        self.assertFalse(ln.wrong_last_name("Akikai", should, either), (should, either))

    def test_the_akika_case_is_right_under_her_fathers_own_rule(self):
        want, by = self.expected()
        should, used, either = want[by["Akika Akikai"].identity]
        self.assertEqual(used, "random")
        self.assertEqual(set(either), {"Okelani", "Akikai"}, "the father's or the mother's, never Temitope")
        self.assertFalse(ln.wrong_last_name("Akikai", should, either))
        self.assertNotIn("Temitope", (should, *either))

    def test_a_pending_use_the_village_rule_takes_a_living_parents_own_rule_away(self):
        people, _parents, own, by = village()
        hoto = ln.own_key(by["Hoto Okelani"])
        living_keys = {ln.own_key(v) for v in people if v.alive}
        rules = ln.check_rules(own, {hoto: ""}, living_keys)
        self.assertNotIn(hoto, rules)
        self.assertEqual(rules[ln.own_key(by["Hiji Temitope"])], "random", "the dead father's line stays")

    def test_the_mark_names_the_rule_that_gave_it(self):
        self.assertEqual(ln.wrong_last_name_mark("Powaka", "father", "father"), "the rule gives Powaka")
        self.assertEqual(ln.wrong_last_name_mark("Powaka", "random", "father", ("Okelani", "Powaka")),
                         "should be Okelani or Powaka: a parent's own rule, 50:50, applies")
        self.assertEqual(ln.wrong_last_name_mark("", "father", "father"), "the rule gives none")


def widgets(root):
    out, stack = [], [root]
    while stack:
        w = stack.pop()
        out.append(w)
        stack.extend(w.winfo_children())
    return out


class TheWindow(unittest.TestCase):
    """The real last-names window, on the synthetic village: its marks are the check's."""

    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"no display: {exc}")
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def open(self):
        import vv_fun_patcher_gui as gui
        people, parents, own, by = village()
        living_keys = {ln.own_key(v) for v in people if v.alive}
        seen = {}

        def look():
            win = [w for w in widgets(self.root) if isinstance(w, tk.Toplevel)][-1]
            rows, marks = {}, {}
            for w in widgets(win):
                if w.winfo_class() in ("Label", "TLabel") and w.winfo_manager() == "grid":
                    info = w.grid_info()
                    text = str(w.cget("text"))
                    if int(info["column"]) == 0:
                        rows[int(info["row"])] = text.split(" (")[0]
                    elif int(info["column"]) == 2:
                        marks[int(info["row"])] = text
            seen["marks"] = {rows[r]: marks.get(r, "") for r in rows}
            seen["rule"] = next(str(w.get()) for w in widgets(win) if w.winfo_class() == "TCombobox"
                                and str(w.cget("state")) == "readonly")
            seen["alert"] = next((str(w.cget("text")) for w in widgets(win)
                                  if w.winfo_class() == "TLabel" and "are not what the rule gives" in str(w.cget("text"))), "")
            next(w for w in widgets(win) if w.winfo_class() == "TButton" and str(w.cget("text")) == "Cancel").invoke()

        self.root.after(300, look)
        fake = SimpleNamespace(_repair_questions=lambda *a, **k: None, _own_rules_dialog=lambda *a, **k: None)
        info = SimpleNamespace(slot=1, name="Kalahuna Tribe 1")
        names = {"chosen": {}, "answers": {}}
        patches = [
            mock.patch.object(ln, "everyone", return_value=(people, parents)),
            mock.patch.object(ln, "read_record", return_value=("father", {("Hoto", 18, 5): "Okelani"})),
            mock.patch.object(ln, "known_names", return_value={"Okelani"}),
            mock.patch.object(ln, "own_rules_now", return_value=dict(own)),
            mock.patch.object(ln, "read_own", return_value={k: r for k, r in own.items() if k in living_keys}),
            mock.patch.object(ln, "read_arrivals", return_value=True),
            mock.patch.object(gui.messagebox, "showerror", side_effect=AssertionError),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        gui.App._last_names_dialog(fake, self.root, Path(self.tmp.name), 1, info, names,
                                   tk.BooleanVar(master=self.root))
        return seen, by

    def test_the_window_marks_only_what_the_check_finds(self):
        seen, _by = self.open()
        marks = seen["marks"]
        self.assertEqual(marks["Akika Akikai"], "", "never 'the rule gives Temitope' (the owner's screenshot)")
        self.assertEqual(marks["Aika Akikai"], "", "her dead father's own 50:50 still counts")
        self.assertEqual(marks["Nalu Powaka"], "", "the father's last name is right")
        self.assertEqual(marks["Mele Akikai"], "the rule gives Powaka")
        self.assertEqual(seen["alert"], "1 last name(s) are not what the rule gives.")

    def test_the_rule_shown_is_the_rule_every_the_rule_gives_mark_uses(self):
        seen, by = self.open()
        self.assertEqual(seen["rule"], ln.INHERIT["father"])
        fathers = {"Akika Akikai": "Okelani", "Nalu Powaka": "Powaka", "Mele Akikai": "Powaka"}
        for name, mark in seen["marks"].items():
            if mark.startswith("the rule gives "):
                self.assertEqual(mark, f"the rule gives {fathers[name]}", name)


class TheWindowsSource(unittest.TestCase):
    def test_the_window_uses_the_shared_reading(self):
        body = GUI_SOURCE[GUI_SOURCE.index("    def _last_names_dialog("):GUI_SOURCE.index("    def _own_rules_dialog(")]
        self.assertIn("vv_last_names.check_rules(recorded_own, own_state, living_keys)", body)
        self.assertIn("vv_last_names.expected_last_names(", body)
        self.assertIn("vv_last_names.wrong_last_name_mark(right, used, rule_key(), either)", body)


if __name__ == "__main__":
    unittest.main()
