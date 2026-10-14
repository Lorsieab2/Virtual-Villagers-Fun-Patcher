"""Family Tree Maker (v1.35.73): a generation label's words are each page's own, defaulting to the tree-wide
label, so an old tree file opens exactly as before (the owner: "generation labels and text should be per-page")."""
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
    """Page 1 shows generations 1-2, page 2 generations 2-3: generation 2 is on both."""
    v = tg.village()
    edits = ft.Edits(pages=[2])
    ft.arrange(v, edits)
    return v, edits


def label(v, edits, k: int, g: int) -> list[str]:
    return ft.generation_label(ft.layout(v, edits, k), g)


class Editor:
    """Just enough of the window to run its generation-label edits without Tk."""
    _pkey = gw.TreeEditor._pkey
    _ov = gw.TreeEditor._ov
    _generations_now = gw.TreeEditor._generations_now
    _set_generation_label = gw.TreeEditor._set_generation_label

    def __init__(self, v, edits, shown: int) -> None:
        self.village, self.edits, self.page = v, edits, shown


class GenerationLabelsPerPageTests(unittest.TestCase):
    def test_a_label_changed_on_one_page_does_not_change_on_another(self) -> None:
        v, edits = two_pages()
        was = [label(v, edits, k, 2) for k in (0, 1)]
        Editor(v, edits, 1)._set_generation_label(2, ["Elders", "of page two"])
        self.assertEqual(label(v, edits, 1, 2), ["Elders", "of page two"])
        self.assertEqual(label(v, edits, 0, 2), was[0])                 # page 1 as it was
        self.assertEqual(edits.generations, {})                         # the tree-wide label untouched
        # and the other way round, from a tree-wide label: one page can put the patcher's own back
        edits.generations, edits.page_edits = {"2": ["Everywhere"]}, {}
        self.assertEqual(label(v, edits, 0, 2), ["Everywhere"])
        Editor(v, edits, 0)._set_generation_label(2, None)
        self.assertEqual(label(v, edits, 0, 2), was[0])
        self.assertEqual(label(v, edits, 1, 2), ["Everywhere"])
        self.assertEqual(edits.generations, {"2": ["Everywhere"]})

    def test_an_old_file_without_the_new_keys_renders_the_same(self) -> None:
        v, _e = two_pages()
        old = {"pages": [2], "generations": {"2": ["Old words"]}}
        edits = ft.Edits.from_data(json.loads(json.dumps(old)))
        self.assertEqual(edits.page_edits, {})
        for k in (0, 1):
            self.assertEqual(label(v, edits, k, 2), ["Old words"])
            self.assertIs(ft.page_view(edits, v, k), edits)

    def test_page_labels_round_trip_and_junk_is_cleaned(self) -> None:
        v, edits = two_pages()
        edits.generations = {"2": ["Tree"]}
        edits.page_edits = {"2": {"generations": {"2": ["Own", "words"], "3": None}}}
        back = ft.Edits.from_data(json.loads(json.dumps(edits.to_data())))
        self.assertEqual(back.page_edits["2"]["generations"], {"2": ["Own", "words"], "3": None})
        self.assertEqual(label(v, back, 1, 2), ["Own", "words"])
        self.assertEqual(label(v, back, 0, 2), ["Tree"])
        junk = ft.clean_page_edits({"2": {"generations": {"x": ["a"], "2": 5, "3": ["ok", 7]}},
                                    "1": {"generations": "nope"}, "3": {"generations": {}}})
        self.assertEqual(junk, {"2": {"generations": {"3": ["ok", "7"]}}})


if __name__ == "__main__":
    unittest.main()
