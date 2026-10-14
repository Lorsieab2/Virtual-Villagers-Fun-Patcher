"""Family Tree Maker (v1.35.73): a villager's generation, chosen look and the family lines the player dragged are
each page's own, defaulting to the tree-wide value, so an old tree file opens exactly as before."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_family_tree as ft  # noqa: E402
import vv_genealogy_window as gw  # noqa: E402
import test_genealogy as tg  # noqa: E402

E, H = 5, 8                     # two villagers of generation 2: the founders of page 2 and the children of page 1


def two_pages() -> tuple:
    """Page 1 shows generations 1-2, page 2 generations 2-3 (page names "1" and "2")."""
    v = tg.village()
    edits = ft.Edits(pages=[2])
    ft.arrange(v, edits)
    return v, edits


def page(v, edits, k):
    return ft.layout(v, edits, k)


def drawn(lay) -> dict:
    fam = {f.id: ft.family_key(lay.village, f) for f in lay.families}
    return {f"{fam[fid]}|{piece}": pts for _c, pts, fid, piece in ft.lines(lay)}


class Editor:
    """Just enough of the window to run its per-page edits without Tk."""
    _pkey = gw.TreeEditor._pkey
    _ov = gw.TreeEditor._ov
    _entry = gw.TreeEditor._entry
    _entry_by_key = gw.TreeEditor._entry_by_key
    _set_entry = gw.TreeEditor._set_entry
    _set_entry_key = gw.TreeEditor._set_entry_key
    _line_moves_now = gw.TreeEditor._line_moves_now
    _set_line_move = gw.TreeEditor._set_line_move
    _clear_line_moves = gw.TreeEditor._clear_line_moves

    def __init__(self, v, edits, shown: int) -> None:
        self.village, self.edits, self.page = v, edits, shown


class GenerationAndLookPerPageTests(unittest.TestCase):
    def test_a_generation_set_on_one_page_moves_the_villager_on_that_page_alone(self) -> None:
        v, edits = two_pages()
        key = ft.entry_key(v, v.people[E])
        before = [page(v, edits, k) for k in (0, 1)]
        self.assertEqual(before[1].village.people[E].generation, 2)
        edits.page_edits = {"2": {"entries": {key: {"generation": 3}}}}
        after = [page(v, edits, k) for k in (0, 1)]
        self.assertEqual(after[0].village.people[E].generation, 2)              # page 1 as it was
        self.assertEqual((after[0].x, after[0].y), (before[0].x, before[0].y))
        self.assertEqual(drawn(after[0]), drawn(before[0]))
        self.assertEqual(after[1].village.people[E].generation, 3)              # page 2 has them a row lower
        self.assertGreater(after[1].y[E], before[1].y[E])
        self.assertEqual(v.people[E].generation, 2)                              # the tree itself unchanged
        self.assertEqual(ft.page_spans(edits, after[1].village), ft.page_spans(edits, v))

    def test_a_generation_outside_the_pages_own_is_ignored(self) -> None:
        v, edits = two_pages()
        key = ft.entry_key(v, v.people[E])
        plain = page(v, edits, 1)
        edits.page_edits = {"2": {"entries": {key: {"generation": 1}}}}          # page 2 shows generations 2-3
        again = page(v, edits, 1)
        self.assertEqual((again.x, again.y), (plain.x, plain.y))
        self.assertIs(ft.page_village(edits, v, 1), v)

    def test_the_tree_wide_generation_is_the_default_for_every_page(self) -> None:
        v = tg.village()
        edits = ft.Edits(pages=[2])
        key = ft.entry_key(v, v.people[E])
        edits.entries = {key: {"generation": 3}}                                 # an old file's, tree-wide
        ft.arrange(v, edits)
        self.assertEqual([page(v, edits, k).village.people[E].generation for k in (0, 1)], [3, 3])
        edits.page_edits = {"2": {"entries": {key: {"generation": None}}}}       # the records' own, on page 2
        ft.arrange(v, edits)
        self.assertEqual(page(v, edits, 0).village.people[E].generation, 3)
        self.assertEqual(page(v, edits, 1).village.people[E].generation, 2)

    def test_a_look_chosen_on_one_page_shows_on_that_page_alone(self) -> None:
        v, edits = two_pages()
        p = v.people[E]
        key = ft.entry_key(v, p)
        edits.page_edits = {"2": {"entries": {key: {"look": [9, 9]}}}}
        looks = [ft.look_of(page(v, edits, k).edits, v, p) for k in (0, 1)]
        self.assertEqual(looks, [(p.head, p.body), (9, 9)])

    def test_the_tree_wide_look_is_the_default_and_a_page_can_undo_it(self) -> None:
        v, edits = two_pages()
        p = v.people[E]
        key = ft.entry_key(v, p)
        edits.entries = {key: {"look": [7, 7]}}
        self.assertEqual([ft.look_of(page(v, edits, k).edits, v, p) for k in (0, 1)], [(7, 7), (7, 7)])
        edits.page_edits = {"2": {"entries": {key: {"look": [9, 9]}}}}
        self.assertEqual([ft.look_of(page(v, edits, k).edits, v, p) for k in (0, 1)], [(7, 7), (9, 9)])
        edits.page_edits = {"2": {"entries": {key: {"look": None}}}}
        self.assertEqual([ft.look_of(page(v, edits, k).edits, v, p) for k in (0, 1)], [(7, 7), (p.head, p.body)])

    def test_the_window_writes_a_generation_and_a_look_to_the_shown_page_only(self) -> None:
        v, edits = two_pages()
        ed = Editor(v, edits, 1)                                                 # page 2 is shown
        p = v.people[E]
        key = ft.entry_key(v, p)
        ed._set_entry(p, generation=3, look=[9, 9])
        self.assertEqual(edits.entries, {})                                      # nothing tree-wide
        self.assertEqual(edits.page_edits["2"]["entries"][key], {"generation": 3, "look": [9, 9]})
        ed._set_entry(p, generation=None, look=None)                             # back to the tree's own
        self.assertEqual(edits.page_edits["2"]["entries"].get(key, {}), {})
        edits.entries = {key: {"look": [7, 7]}}
        ed._set_entry(p, look=None)                                              # the tree's look undone here only
        self.assertEqual(ft.page_view(edits, v, 1).entries.get(key, {}).get("look"), None)
        self.assertEqual(ft.page_view(edits, v, 0).entries[key]["look"], [7, 7])

    def test_bad_generations_and_looks_are_dropped_on_load(self) -> None:
        cleaned = ft.clean_page_edits({"2": {"entries": {"k": {"generation": 0, "look": [1], "mark": "x"},
                                                         "j": {"generation": "3"}}}})
        self.assertEqual(cleaned, {"2": {"entries": {"k": {"mark": "x"}}}})


class DraggedLinesPerPageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.v, self.edits = two_pages()
        self.edits.diagonal_lines = True
        fam = lambda a: ft.family_key(self.v, next(f for f in page(self.v, self.edits, 0).families
                                                    if a in (f.father, f.mother)))
        self.first = fam(1) + "|lane"           # drawn on page 1 only
        self.second = ft.family_key(self.v, next(f for f in page(self.v, self.edits, 1).families
                                                 if E in (f.father, f.mother))) + "|lane"     # on page 2 only

    def test_a_line_dragged_on_one_page_does_not_move_on_the_other(self) -> None:
        before = [drawn(page(self.v, self.edits, k)) for k in (0, 1)]
        self.edits.page_edits = {"1": {"line_moves": {self.first: [30.0, 0.0]}}}
        after = [drawn(page(self.v, self.edits, k)) for k in (0, 1)]
        self.assertNotEqual(after[0][self.first], before[0][self.first])
        self.assertEqual(after[1], before[1])                                    # page 2 untouched
        self.assertEqual(self.edits.line_moves, {})
        self.edits.page_edits = {"2": {"line_moves": {self.second: [30.0, 0.0]}}}
        again = [drawn(page(self.v, self.edits, k)) for k in (0, 1)]
        self.assertEqual(again[0], before[0])
        self.assertNotEqual(again[1][self.second], before[1][self.second])

    def test_a_tree_wide_drag_is_the_default_and_a_page_can_undo_it(self) -> None:
        plain = [drawn(page(self.v, self.edits, k)) for k in (0, 1)]
        self.edits.line_moves = {self.second: [30.0, 0.0]}                       # as an old file saved it
        moved = drawn(page(self.v, self.edits, 1))
        self.assertNotEqual(moved[self.second], plain[1][self.second])
        self.edits.page_edits = {"2": {"line_moves": {self.second: None}}}
        self.assertEqual(drawn(page(self.v, self.edits, 1)), plain[1])
        self.assertEqual(drawn(page(self.v, self.edits, 0)), plain[0])

    def test_the_window_drags_and_clears_lines_on_the_shown_page_only(self) -> None:
        ed = Editor(self.v, self.edits, 0)
        ed._set_line_move(self.first, [30.0, 0.0], free=True)
        self.assertEqual(self.edits.line_moves, {})
        self.assertEqual(self.edits.free_lines, [])
        self.assertEqual(ft.page_view(self.edits, self.v, 0).line_moves, {self.first: [30.0, 0.0]})
        self.assertEqual(ft.page_view(self.edits, self.v, 0).free_lines, [self.first])
        self.assertEqual(ft.page_view(self.edits, self.v, 1).line_moves, {})
        ed._set_line_move(self.first, None)
        self.assertEqual(ft.clean_page_edits(self.edits.page_edits), {})
        self.edits.line_moves = {self.second: [5.0, 0.0]}
        self.edits.free_lines = [self.second]
        other = Editor(self.v, self.edits, 1)
        other._clear_line_moves()
        self.assertEqual(ft.page_view(self.edits, self.v, 1).line_moves, {})
        self.assertEqual(ft.page_view(self.edits, self.v, 1).free_lines, [])
        self.assertEqual(ft.page_view(self.edits, self.v, 0).line_moves, {self.second: [5.0, 0.0]})
        self.assertEqual(self.edits.line_moves, {self.second: [5.0, 0.0]})

    def test_page_line_moves_round_trip_and_bad_ones_are_dropped(self) -> None:
        self.edits.page_edits = {"1": {"line_moves": {"a|lane": [1.0, 2.0], "b|lane": None, "c|lane": 4.0}}}
        back = ft.Edits.from_data(json.loads(json.dumps(self.edits.to_data())))
        self.assertEqual(back.page_edits["1"]["line_moves"], {"a|lane": [1.0, 2.0], "b|lane": None, "c|lane": 4.0})
        junk = ft.clean_page_edits({"1": {"line_moves": {"a": "x", "b": [1], "c": [0, 0], "d": [3, 4]}}})
        self.assertEqual(junk, {"1": {"line_moves": {"d": [3.0, 4.0]}}})


class OldFilesTests(unittest.TestCase):
    OLD = {"format": 1, "pages": [2], "diagonal_lines": True,
           "entries": {"E|5|5": {"generation": 3, "look": [7, 7], "mark": "Star"}},
           "line_moves": {"E|5|5||H|8|8|lane": [12.0, 0.0], "A|1|1||B|2|2|lane": 6.0}, "free_lines": ["E|5|5||H|8|8|lane"]}

    def test_an_old_file_loads_unchanged_and_keeps_no_page_edits(self) -> None:
        edits = ft.Edits.from_data(json.loads(json.dumps(self.OLD)))
        self.assertEqual(edits.page_edits, {})
        self.assertEqual(edits.entries["E|5|5"], {"generation": 3, "look": [7, 7], "mark": "Star"})
        self.assertEqual(edits.line_moves, {"E|5|5||H|8|8|lane": [12.0, 0.0], "A|1|1||B|2|2|lane": 6.0})
        self.assertEqual(edits.free_lines, ["E|5|5||H|8|8|lane"])
        saved = edits.to_data()
        self.assertEqual(saved["entries"], self.OLD["entries"])
        self.assertEqual(saved["line_moves"], self.OLD["line_moves"])
        self.assertEqual(saved["page_edits"], {})

    def test_an_old_file_renders_the_same_on_every_page_with_or_without_the_new_code_paths(self) -> None:
        v = tg.village()
        edits = ft.Edits.from_data(json.loads(json.dumps(self.OLD)))
        ft.arrange(v, edits)
        for k in (0, 1):
            lay = page(v, edits, k)
            self.assertIs(ft.page_view(edits, v, k), edits)                      # nothing laid over it
            self.assertIs(ft.page_village(edits, v, k), v)
            self.assertIs(lay.village, v)
        # and the same as the file read a second time, with page_edits that keep nothing
        twin = ft.Edits.from_data(json.loads(json.dumps(self.OLD)))
        twin.page_edits = ft.clean_page_edits({"1": {"entries": {}}, "2": {"line_moves": {}}})
        w = tg.village()
        ft.arrange(w, twin)
        for k in (0, 1):
            a, b = page(v, edits, k), page(w, twin, k)
            self.assertEqual((a.x, a.y), (b.x, b.y))
            self.assertEqual(drawn(a), drawn(b))
            self.assertEqual([ft.look_of(a.edits, v, p) for p in v.people.values()],
                             [ft.look_of(b.edits, w, p) for p in w.people.values()])
        self.assertEqual(ft.look_of(page(v, edits, 1).edits, v, v.people[E]), (7, 7))
        self.assertEqual(page(v, edits, 1).village.people[E].generation, 3)


if __name__ == "__main__":
    unittest.main()
