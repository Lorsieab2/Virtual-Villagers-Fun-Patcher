"""Change Appearance in the Family Tree Maker (src/vv_genealogy.py, vv_family_tree.py, vv_genealogy_window.py).

The owner (2026-10-07): "regarding appearance changes, sure. Log those. And ask the player if they wish
to update the villager's appearance in the family tree or not."  The "Appearance changed" records the
games now write (native/shared/appearance_log.h) say the villager with the old look and the one with
the new look are one villager.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_family_tree as ft  # noqa: E402
import vv_genealogy as gen  # noqa: E402
from test_last_names_rename import LOGS, TABLE, entry  # noqa: E402

BIRTHS = "Births and Conceptions/Virtual Villagers 3 Births and Conceptions Log 1.txt"


class ChangedLooks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        people = [entry("Ago", 0, 1, 7, 8), entry("Aipi", 1, 50, 2, 2),
                  entry("Kid", 0, 50, 9, 9, father=("Ago", 3, 4), mother=("Aipi", 2, 2))]
        (self.folder / "Virtual Villagers - The Secret City1.ldw").write_bytes(
            b"ldwg" + bytes(TABLE - 4) + b"".join(people) + bytes(64))

    def tearDown(self):
        self.tmp.cleanup()

    def births(self, text: str) -> None:
        path = self.folder / LOGS / BIRTHS
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(("Village: Tribe (Save 1)\n" + text).replace("\n", "\r\n").encode())

    def changed(self, old: tuple, new: tuple, name: str = "Ago") -> str:
        return (f"Appearance changed\n  Name: {name}\n  Old head: {old[0]}\n  Old body: {old[1]}\n"
                f"  New head: {new[0]}\n  New body: {new[1]}\n\n")

    def test_the_old_look_is_the_same_villager(self):
        self.births(self.changed((3, 4), (7, 8)))
        v = gen.load_village(self.folder, 3, 1)
        ago = [p for p in v.known() if p.name == "Ago"]
        self.assertEqual(len(ago), 1, "one Ago, not one for each look")
        kid = next(p for p in v.known() if p.name == "Kid")
        self.assertEqual(kid.father, ago[0].id, "the child's father, saved with the old look, is him")
        self.assertEqual(ago[0].old_looks, [(3, 4)])
        self.assertEqual(v.relooked, {("Ago", 3, 4): ("Ago", 7, 8)})

    def test_without_the_record_the_old_look_is_someone_else(self):
        v = gen.load_village(self.folder, 3, 1)
        self.assertEqual(len([p for p in v.known() if p.name == "Ago"]), 2)
        self.assertEqual(v.relooked, {})

    def test_changes_chain_and_a_change_back_is_his_own_look_again(self):
        self.births(self.changed((1, 1), (3, 4)) + self.changed((3, 4), (7, 8)))
        v = gen.load_village(self.folder, 3, 1)
        self.assertEqual(v.relooked, {("Ago", 1, 1): ("Ago", 7, 8), ("Ago", 3, 4): ("Ago", 7, 8)})
        self.births(self.changed((7, 8), (3, 4)) + self.changed((3, 4), (7, 8)))
        v = gen.load_village(self.folder, 3, 1)
        self.assertEqual(v.relooked, {("Ago", 3, 4): ("Ago", 7, 8)})

    def test_edits_follow_the_villager_and_the_chosen_look_is_drawn(self):
        self.births(self.changed((3, 4), (7, 8)))
        v = gen.load_village(self.folder, 3, 1)
        ago = next(p for p in v.known() if p.name == "Ago")
        saved = {"entries": {"Ago|3|4": {"mark": "Chief"}}, "line_moves": {"Ago|3|4 bar": [1.0, 0.0]}}
        moved = json.loads(ft.relooked_keys(json.dumps(saved), v.relooked))
        self.assertEqual(moved, {"entries": {"Ago|7|8": {"mark": "Chief"}}, "line_moves": {"Ago|7|8 bar": [1.0, 0.0]}})
        edits = ft.Edits.from_data({"entries": {"Ago|7|8": {"look": [3, 4]}}})
        self.assertEqual(ft.look_of(edits, v, ago), (3, 4))
        self.assertEqual(ft.look_of(ft.Edits(), v, ago), (7, 8))
        self.assertEqual(ft.Edits.from_data(edits.to_data()).entries["Ago|7|8"]["look"], [3, 4])
        self.assertNotIn("look", ft.Edits.from_data({"entries": {"Ago|7|8": {"look": "old", "mark": "x"}}})
                         .entries["Ago|7|8"])


class TheEditorAsks(unittest.TestCase):
    SOURCE = (ROOT / "src" / "vv_genealogy_window.py").read_text(encoding="utf-8")

    def test_it_asks_once_each_change_and_the_edits_follow(self):
        follow = self.SOURCE[self.SOURCE.index("    def _follow_looks(self)"):self.SOURCE.index("    def _ask_looks(")]
        self.assertIn('if p.old_looks and "look" not in self._entry(p)', follow, "asked only until answered")
        self.assertLess(follow.index('.pop("look", None)'), follow.index("ft.relooked_keys("),
                        "a newer change asks again")
        for caller in ("        self._build()\n        self._follow_looks()",
                       "        self.selected = []\n        self._follow_looks()\n        self.redraw()",
                       "        self.page = 0\n        self._follow_looks()"):
            self.assertIn(caller, self.SOURCE)


if __name__ == "__main__":
    unittest.main()
