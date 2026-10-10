"""The Family Tree Maker's Villager Info tab (the owner, 2026-10-10): the selected villager's icon, name,
age, partners with their children and babies on the way, and notes; males' names and ages bold blue,
females' bold pink."""
import sys
import tkinter as tk
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_family_tree as ft  # noqa: E402
import vv_genealogy as gen  # noqa: E402
import vv_villager_info as vi  # noqa: E402

P = gen.Person


def town(game: int = 2) -> gen.Village:
    people = [
        P(1, "Ago", 0, 0, "Male", 900, True, generation=1, number=1),
        P(2, "Bela", 3, 1, "Female", 880, True, generation=1, number=2),
        P(3, "Cora", 4, 2, "Female", 870, True, generation=1, number=3, expecting=True),
        P(4, "Dan", 5, 3, "Male", 0, True, father=1, mother=2, litter=7, birth_record=1, generation=2, number=4),
        P(5, "Eli", 6, 4, "Female", 0, True, father=1, mother=2, litter=7, birth_record=2, generation=2, number=5),
        P(6, "Fen", 7, 5, "Male", 120, False, gone="died", father=1, mother=3, birth_record=3, generation=2,
          number=6),
        P(7, "Gil", 8, 6, "Male", 300, True, mother=2, generation=2, number=7),
        P(8, "Upcoming child", -1, -1, upcoming=True, mother=3, father=1, litter=-1, generation=2),
        P(9, "Upcoming child", -1, -2, upcoming=True, mother=3, father=1, litter=-1, generation=2),
    ]
    return gen.Village(game, 1, "Test", {p.id: p for p in people})


def text(v, pid, edits=None):
    return vi.plain_text(vi.info_lines(v, edits or ft.Edits(), pid))


def styles(v, pid, words):
    return {r[1] for line in vi.info_lines(v, ft.Edits(), pid) for r in line if r[0] == words}


class InfoTests(unittest.TestCase):
    def test_partners_children_in_birth_order_and_babies_on_the_way(self):
        v = town()
        out = text(v, 1)
        self.assertLess(out.index("Bela"), out.index("Cora"))          # first child's birth decides
        self.assertLess(out.index("Dan"), out.index("Eli"))
        self.assertIn("On the way: twins (expected mother: Cora)", out)
        self.assertIn("Fen", out)
        self.assertRegex(out, r"Fen, died at .*6 years old\n")
        self.assertNotIn("Gil", out)                                    # Bela's, father unknown

    def test_unknown_other_parent(self):
        out = text(town(), 2)
        self.assertIn("Other parent unknown", out)
        self.assertGreater(out.index("Gil"), out.index("Other parent unknown"))

    def test_names_and_ages_bold_by_sex_and_babies_grey(self):
        v = town()
        self.assertEqual(styles(v, 1, "Ago"), {"Male"})
        # Only partner names (and the children heading) are bold (the owner, 2026-10-10).
        self.assertEqual(styles(v, 1, "Bela"), {"Female+strong"})
        self.assertEqual(styles(v, 1, "Dan"), {"Male"})
        self.assertIn("note+strong", {r[1] for line in vi.info_lines(v, ft.Edits(), 1) for r in line
                                      if "Children (in order of birth)" in r[0]})
        self.assertIn("unknown", {r[1] for line in vi.info_lines(v, ft.Edits(), 1) for r in line
                                  if r[0].startswith("On the way")})

    def test_zero_age_and_head_are_real(self):
        v = town()
        self.assertIn("0 years old", text(v, 4))
        edits = ft.Edits()
        self.assertEqual(ft.look_of(edits, v, v.people[1])[0], 0)

    def test_notes(self):
        v = town()
        out = text(v, 4)
        self.assertIn("Eli's twin", out)
        self.assertIn("Father: Ago", out)
        self.assertIn("Mother: Bela", out)
        self.assertIn("Generation II, number 4", out)
        self.assertIn("Founder", text(v, 1))
        self.assertIn("Deceased", text(v, 6))

    def test_golden_child_and_heathen(self):
        v = town(1)
        v.people[7].family = 199
        self.assertIn("Golden Child", text(v, 7))
        self.assertNotIn("Golden Child", text(town(2), 7))
        v5 = town(5)
        v5.people[1].heathen = True
        self.assertIn("Heathen", text(v5, 1))

    def test_mark_shown_and_edits_untouched(self):
        v = town()
        edits = ft.Edits()
        edits.entries[ft.entry_key(v, v.people[1])] = {"mark": "Tribal Chief"}
        before = repr(edits.entries)
        self.assertIn("Special mark: Tribal Chief", text(v, 1, edits))
        self.assertEqual(repr(edits.entries), before)

    def test_custom_and_special_titles_in_the_notes(self):
        # The owner, 2026-10-10: Hoani Chuchip is "Helpful Spirit" -- the Notes say so.
        for game in (1, 2, 3, 4, 5):
            v = town(game)
            titles = {("Ago", 0, 0): {"custom": "Helpful Spirit", "special": "Esteemed Elder"}}
            out = vi.plain_text(vi.info_lines(v, ft.Edits(), 1, titles=titles))
            self.assertIn("Custom title: Helpful Spirit", out)
            self.assertIn("Special title: Esteemed Elder", out)
            self.assertNotIn("Custom title", vi.plain_text(vi.info_lines(v, ft.Edits(), 2, titles=titles)))
        v5 = town(5)
        out = vi.plain_text(vi.info_lines(v5, ft.Edits(), 2, titles={("Bela", 3, 1): {"special": "Former Heathen"}}))
        self.assertIn("Special title: Former Heathen", out)
        # The Golden Child is said once.
        v1 = town(1)
        v1.people[7].family = 199
        out = vi.plain_text(vi.info_lines(v1, ft.Edits(), 7, titles={("Gil", 8, 6): {"special": "Golden Child"}}))
        self.assertEqual(out.count("Golden Child"), 1)

    def test_titles_follow_earlier_looks(self):
        v = town()
        v.relooked[("Ago", 9, 9)] = ("Ago", 0, 0)
        self.assertEqual(vi.titles_of(v, {("Ago", 9, 9): {"custom": "Chief Cook"}}, v.people[1]),
                         {"custom": "Chief Cook"})

    def test_the_titles_file_is_read_and_wins_over_the_logs(self):
        import struct
        import tempfile
        from unittest import mock
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "t.dat"
            path.write_bytes(b"VCT1" + struct.pack("<III", 2, 1, 1) + struct.pack("<II", 4, 77)
                             + b"Helpful Spirit".ljust(32, b"\0"))
            self.assertEqual(vi.read_titles_file(path, 1), [(4, 77, "Helpful Spirit")])
            self.assertEqual(vi.read_titles_file(path, 2), [])          # another game's file
        with mock.patch.object(vi, "log_titles", return_value={("A", 0, 0): {"custom": "Old", "special": "Scholar"},
                                                                 ("B", 1, 1): {"custom": "Gone"}}), \
                mock.patch.object(vi, "file_titles", return_value={("A", 0, 0): "New"}):
            got = vi.village_titles(Path("."), 1, 1)
        self.assertEqual(got[("A", 0, 0)], {"custom": "New", "special": "Scholar"})
        self.assertEqual(got[("B", 1, 1)], {"custom": "Gone"})            # not in the save: the logs say

    def test_tab_shows_hint_unless_one_selected(self):
        try:
            root = tk.Tk()
        except tk.TclError:
            self.skipTest("no display")
        root.withdraw()
        try:
            from types import SimpleNamespace
            from tkinter import ttk
            ed = SimpleNamespace(notebook=ttk.Notebook(root), village=town(), edits=ft.Edits(), game=2,
                                 present={}, selected=[], lay=None)
            tab = vi.VillagerInfoTab(ed)
            self.assertIn(vi.HINT, tab.text.get("1.0", "end"))
            ed.selected = [1]
            tab.refresh()
            shown = tab.text.get("1.0", "end")
            self.assertIn("Ago", shown)
            self.assertTrue(tab.links)
            ed.selected = [1, 2]
            tab.refresh()
            self.assertIn(vi.HINT, tab.text.get("1.0", "end"))
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
