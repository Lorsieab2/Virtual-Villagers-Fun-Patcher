"""Family Tree Maker preview: what is placed on a page belongs to that page alone, and the search bar's matching."""
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


def two_pages() -> tuple:
    v = tg.village()
    edits = ft.Edits(pages=[3])
    ft.arrange(v, edits)
    return v, edits


def scene_of(v, edits, page):
    return ft.scene(ft.layout(v, edits, page), "Test", {})


def moved_title_y(sc) -> float:
    return next(i.y for i in sc.items if isinstance(i, ft.Text) and i.move == "title")


class PerPageTests(unittest.TestCase):
    def test_there_are_two_pages(self) -> None:
        v, edits = two_pages()
        self.assertEqual(len(ft.page_spans(edits, v)), 2)
        self.assertEqual([ft.page_key(edits, v, k) for k in (0, 1)], [1, 3])

    def test_an_old_file_with_stickers_shows_them_on_every_page_until_localised(self) -> None:
        v, edits = two_pages()
        old = {"format": 1, "pages": [3], "stickers": [{"kind": "text", "text": "hi", "cx": 50, "cy": 50, "w": 90, "h": 40}]}
        edits = ft.Edits.from_data(old)
        ft.arrange(v, edits)
        self.assertEqual([len(scene_of(v, edits, k).stickers) for k in (0, 1)], [1, 1])      # as before
        self.assertTrue(ft.localise_stickers(edits, v))
        self.assertEqual(len(edits.stickers), 2)
        self.assertEqual([len(scene_of(v, edits, k).stickers) for k in (0, 1)], [1, 1])      # the same things
        edits.stickers[0]["cx"] = 400                                                            # moved on page 1 alone
        self.assertEqual(scene_of(v, edits, 0).stickers[0].cx, 400)
        self.assertEqual(scene_of(v, edits, 1).stickers[0].cx, 50)

    def test_a_sticker_of_one_page_is_not_drawn_on_the_other(self) -> None:
        v, edits = two_pages()
        edits.stickers.append(ft.clean_sticker({"kind": "text", "text": "x", "page": 3}))
        self.assertEqual([len(scene_of(v, edits, k).stickers) for k in (0, 1)], [0, 1])
        again = ft.Edits.from_data(json.loads(json.dumps(edits.to_data())))
        self.assertEqual(again.stickers[0]["page"], 3)

    def test_moving_the_title_on_one_page_leaves_the_other(self) -> None:
        v, edits = two_pages()
        before = [moved_title_y(scene_of(v, edits, k)) for k in (0, 1)]
        edits.page_edits = {"3": {"moved": {"title": [0.0, 100.0]}}}
        after = [moved_title_y(scene_of(v, edits, k)) for k in (0, 1)]
        self.assertEqual(after[0], before[0])
        self.assertEqual(after[1], before[1] + 100.0)
        self.assertEqual(edits.moved, {})

    def test_a_tree_wide_move_can_be_undone_on_one_page(self) -> None:
        v, edits = two_pages()
        edits.moved = {"title": [0.0, 60.0]}
        edits.page_edits = {"3": {"moved": {"title": None}}}
        flat = ft.page_view(edits, v, 1)
        self.assertNotIn("title", flat.moved)
        self.assertIn("title", ft.page_view(edits, v, 0).moved)

    def test_a_portrait_edit_and_deletion_on_one_page(self) -> None:
        v, edits = two_pages()
        key = ft.entry_key(v, v.people[5])
        edits.entries = {key: {"mark": "Star"}}
        edits.page_edits = {"3": {"entries": {key: {"mark": None, "dx": 30.0}}, "hidden": ["word:footer"]}}
        first, second = ft.page_view(edits, v, 0), ft.page_view(edits, v, 1)
        self.assertEqual(first.entries[key], {"mark": "Star"})
        self.assertEqual(second.entries[key], {"dx": 30.0})
        self.assertEqual(first.hidden, [])
        self.assertEqual(second.hidden, ["word:footer"])

    def test_the_page_edits_round_trip_and_an_old_file_has_none(self) -> None:
        edits = ft.Edits.from_data({"format": 1})
        self.assertEqual(edits.page_edits, {})
        edits.page_edits = {"3": {"moved": {"title": [1.0, 2.0]}, "family_colours": {"f": "#112233"}}, "6": {}}
        data = json.loads(json.dumps(edits.to_data()))
        self.assertEqual(list(data["page_edits"]), ["3"])
        self.assertEqual(ft.Edits.from_data(data).page_edits["3"]["moved"], {"title": [1.0, 2.0]})
        self.assertEqual(ft.Edits.from_data({"format": 1, "page_edits": "junk"}).page_edits, {})


class SearchTests(unittest.TestCase):
    def test_find_by_name_head_parent_status_and_generation(self) -> None:
        v, edits = two_pages()
        v.people[9].runner = True
        by = lambda q: gw.find_villagers(v, edits, q)      # noqa: E731
        self.assertEqual(by("j")[0], 10)
        self.assertEqual(by("head 11 body 11"), [11])
        self.assertEqual(by("e")[0], 5)                    # a name that starts with it first
        self.assertEqual(by("runner"), [9])
        self.assertTrue({2, 4} <= set(by("female generation 1")) and 5 not in by("female generation 1"))
        self.assertEqual(by("zzz"), [])
        self.assertEqual(by(""), [])

    def _with_preferences(self):
        v, edits = two_pages()
        v.people[9].likes, v.people[9].dislikes = ["running", "doing laundry"], ["snakes"]
        v.people[10].likes, v.people[10].dislikes = ["flowers"], ["the dark", "crowds"]
        v.people[11].likes, v.people[11].dislikes = [], []             # known, and has none
        for pid in set(v.people) - {9, 10, 11}:
            v.people[pid].likes = v.people[pid].dislikes = None        # not in the save or the logs
        return v, edits, (lambda q: gw.find_villagers(v, edits, q))

    def test_a_like_finds_the_villager(self) -> None:
        v, edits, by = self._with_preferences()
        self.assertEqual(by("running"), [9])
        self.assertEqual(by("LAUNDRY"), [9])                        # any case, any word of the name
        self.assertEqual(by("flowers"), [10])

    def test_a_dislike_finds_the_villager(self) -> None:
        v, edits, by = self._with_preferences()
        self.assertEqual(by("snakes"), [9])
        self.assertEqual(by("the dark"), [10])
        self.assertEqual(by("dark crowds"), [10])                   # every typed word must match
        self.assertEqual(by("snakes flowers"), [])                  # one on each villager: nobody has both

    def test_a_villager_without_data_is_not_matched_by_a_random_word(self) -> None:
        v, edits, by = self._with_preferences()
        self.assertEqual(by("snakes crowds"), [])
        self.assertEqual(by("butterflies"), [])
        unknown = gw.unknown_preferences(v)
        self.assertNotIn(9, unknown)
        self.assertNotIn(11, unknown)                               # no likes is known, not unknown
        self.assertTrue(unknown and all(v.people[q].likes is None for q in unknown))


if __name__ == "__main__":
    unittest.main()
