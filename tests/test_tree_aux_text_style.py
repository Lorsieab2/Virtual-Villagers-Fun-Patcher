"""Family Tree Maker: the extra lines -- "Founder", "X's twin", "(deceased)", how they came -- bold and
italic by default, the player's own formatting kept, and the Faces & Text button that makes the player's
own extra lines bold and italic too (the owner, 2026-10-10)."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import vv_family_tree as ft  # noqa: E402
import vv_genealogy_window as gw  # noqa: E402

BI = {"bold": True, "italic": True}


def person(pid, name, number, litter=None, generation=1, alive=True, sex="Male"):
    return SimpleNamespace(id=pid, name=name, number=number, litter=litter, upcoming=False, age=1400,
                           years=70, alive=alive, gone="died", heathen=False, generation=generation, sex=sex)


def lay(people, entries=None):
    opts = {"show_units": False, "show_years": True, "show_founder": True, "show_twins": True,
            "text_wrap": ft.WRAP}
    edits = SimpleNamespace(styles={})
    entries = entries or {}
    return SimpleNamespace(edits=edits, names={}, opt=lambda _p, name: opts[name],
                           entry=lambda p: entries.get(p.id, {}),
                           village=SimpleNamespace(people={p.id: p for p in people}))


class DefaultStyleTests(unittest.TestCase):
    def test_the_trees_own_extra_lines_are_bold_and_italic(self):
        a, b = person(1, "Ghali", 1, litter=4, alive=False), person(2, "Huata", 2, litter=4)
        runs = ft.node_runs(lay([a, b]), a)
        self.assertEqual(runs, [[("1. Ghali", {})], [("70 years old", {})], [("Founder", BI)],
                                [("Huata's twin", BI)], [("(deceased)", BI)]])

    def test_the_name_and_age_alone_stay_plain(self):
        p = person(1, "Papu", 9, generation=3)
        self.assertIsNone(ft.node_runs(lay([p]), p))

    def test_bold_words_are_measured_wider_so_they_wrap_sooner(self):
        a, b = person(1, "Ghali", 1, litter=4), person(2, "Huatamakaa", 2, litter=4)
        shown = ft.shown_text(lay([a, b]), a, 20)
        # "Huatamakaa's twin" is 17 letters: plain it fits the 17 across, bold it is wrapped.
        self.assertEqual([t for t, _b, _r in shown][-2:], ["Huatamakaa's", "twin"])
        self.assertEqual(shown[-1][2], [("twin", BI)])

    def test_the_players_own_formatting_wins(self):
        p = person(1, "Ghali", 1)
        own = {1: {"lines": ["1. Ghali", "70 years old", "Founder"],
                   "runs": [[["1. Ghali", {}]], [["70 years old", {}]], [["Founder", {"underline": True}]]]}}
        self.assertEqual(ft.node_runs(lay([p], own), p)[2], [("Founder", {"underline": True})])
        retyped = {1: {"lines": ["1. Ghali", "70 years old", "Founder"]}}
        self.assertIsNone(ft.node_runs(lay([p], retyped), p))


class ButtonTests(unittest.TestCase):
    def test_the_button_keeps_other_formatting_and_the_name_and_age(self):
        lines = ["1. Ghali", "70 years old", "(deceased)", "A Mysterious Crate"]
        runs = [[["1. ", {}], ["Ghali", {"colour": "#ff0000"}]], [["70 years old", {}]], [["(deceased)", {}]],
                [["A ", {"underline": True}], ["Mysterious Crate", {"italic": False}]]]
        self.assertEqual(ft.bold_italic_aux(lines, runs), [
            [["1. ", {}], ["Ghali", {"colour": "#ff0000"}]], [["70 years old", {}]],
            [["(deceased)", BI]], [["A ", {"underline": True, **BI}], ["Mysterious Crate", BI]]])

    def test_the_button_changes_only_the_picked_groups_own_lines_in_one_step(self):
        man, woman, plain = person(1, "Ghali", 1), person(2, "Onawa", 5, sex="Female"), person(3, "Kito", 4)
        entries = {"1": {"lines": ["1. Ghali", "Founder"]}, "2": {"lines": ["5. Onawa", "Founder"]}}
        steps = []
        window = SimpleNamespace(
            village=SimpleNamespace(people={1: man, 2: woman, 3: plain}), _scope=lambda: "Female",
            _entry=lambda p: entries.get(str(p.id), {}),
            _set_entry=lambda p, **v: entries.setdefault(str(p.id), {}).update(v),
            _saved=lambda: steps.append(1), status=SimpleNamespace(set=lambda _s: None))
        self.assertEqual(gw.TreeEditor._bold_italic_extra_lines(window, ask=False), 1)
        self.assertEqual(entries["2"]["runs"], [[["5. Onawa", {}]], [["Founder", BI]]])
        self.assertNotIn("runs", entries["1"])
        self.assertEqual(steps, [1])


if __name__ == "__main__":
    unittest.main()
