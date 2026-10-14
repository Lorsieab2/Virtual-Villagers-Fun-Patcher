"""The Faces & Text "Add status labels" button: every portrait that has a status and does not already
show it gets the status as a bold italic last line; nothing else is touched (v1.35.73)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_family_tree as ft  # noqa: E402
from test_genealogy import village  # noqa: E402


def lay_with(entries: dict | None = None, **changes):
    v = village()
    for pid, fields in changes.items():
        for k, val in fields.items():
            setattr(v.people[int(pid[1:])], k, val)
    e = ft.Edits(entries={ft.entry_key(v, v.people[int(pid[1:])]): ent for pid, ent in (entries or {}).items()})
    return v, ft.layout(v, e)


class StatusLabelsTests(unittest.TestCase):
    def test_dead_villager_with_no_typed_text_ends_up_with_the_status_once(self) -> None:
        v, lay = lay_with(p3={"alive": False, "gone": "died"})
        p = v.people[3]
        # The patcher's own words already end with it: nothing to add, and it is there exactly once.
        self.assertIsNone(ft.status_for_portrait(lay, p))
        self.assertEqual(ft.node_text(lay, p).count("(deceased)"), 1)

    def test_default_words_missing_the_status_get_it_as_a_bold_italic_line(self) -> None:
        v, lay = lay_with(p3={"alive": False, "gone": "died"})
        p = v.people[3]
        real = ft.default_text
        try:
            ft.default_text = lambda lay_, q: [x for x in real(lay_, q) if x != "(deceased)"]
            lines, runs = ft.status_for_portrait(lay, p)
        finally:
            ft.default_text = real
        self.assertEqual(lines[-1], "(deceased)")
        self.assertEqual(runs[-1], [["(deceased)", {"bold": True, "italic": True}]])

    def test_typed_text_without_the_status_gets_it(self) -> None:
        v, lay = lay_with({"p3": {"lines": ["3. Mine", "my words"]}}, p3={"alive": False, "gone": "died"})
        lines, runs = ft.status_for_portrait(lay, v.people[3])
        self.assertEqual(lines, ["3. Mine", "my words", "(deceased)"])
        self.assertEqual(runs[-1], [["(deceased)", {"bold": True, "italic": True}]])
        for gone, word in (("disappeared", "(disappeared)"), ("left", "(left the village)")):
            v.people[3].gone = gone
            self.assertEqual(ft.status_for_portrait(lay, v.people[3])[0][-1], word)

    def test_a_villager_already_showing_the_status_gets_nothing_new(self) -> None:
        for typed in (["3. Mine", "(deceased)"], ["3. Mine", "Son of Ago (deceased)"], ["3. Mine", "(disappeared)"]):
            v, lay = lay_with({"p3": {"lines": typed}}, p3={"alive": False, "gone": "died"})
            self.assertIsNone(ft.status_for_portrait(lay, v.people[3]), typed)
        v, lay = lay_with({"p3": {"lines": ["3. Mine", "Heathen"]}}, p3={"heathen": True})
        self.assertIsNone(ft.status_for_portrait(lay, v.people[3]))

    def test_a_living_villager_and_a_baby_on_the_way_get_nothing(self) -> None:
        v, lay = lay_with({"p3": {"lines": ["3. Mine", "words"]}})
        self.assertIsNone(ft.status_for_portrait(lay, v.people[3]))
        self.assertIsNone(ft.status_for_portrait(lay, v.people[4]))
        v.people[13] = ft.gen.Person(13, "Upcoming child", -1, -1, upcoming=True, mother=8, father=5, generation=3)
        self.assertIsNone(ft.status_for_portrait(ft.layout(v, ft.Edits()), v.people[13]))

    def test_a_living_heathen_with_typed_text_gets_heathen(self) -> None:
        v, lay = lay_with({"p3": {"lines": ["3. Mine"]}}, p3={"heathen": True})
        self.assertEqual(ft.status_for_portrait(lay, v.people[3])[0], ["3. Mine", "Heathen"])


if __name__ == "__main__":
    unittest.main()
