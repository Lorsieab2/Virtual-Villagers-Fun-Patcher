"""The Family Tree Maker and Village Matchmaker audit (v1.35.85), each fix from a small hand-made village.

* The Matchmaker, when the rules leave no woman (or no man) to pair at all -- the owner's Secret City Save 2:
  every woman aged 18-49 already expecting -- said "The least related pairs available:" over an empty list and
  left "Every allowed partner, per woman" blank.  It now says why, and "(none)".
* New Believers' Heathen Mommy's father "Unknown" (head 2, body 2) is the game's own word, a name only (docs/
  vv5-heathen-mommy-research.md): he was drawn as a founder "(left the village)".
* A Heathen's portrait said "Heathen" twice (the automatic mark and the living Heathen's word).
* The Appearance changed question named the head only, so a body-only change (the Secret City chief's robe)
  read "New look (head 22)" / "Old look (head 22)".
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_family_tree as ft  # noqa: E402
import vv_genealogy as gen  # noqa: E402
from test_genealogy import village  # noqa: E402

Y = gen.UNITS_PER_YEAR


class NobodyToPair(unittest.TestCase):
    def test_every_woman_expecting_is_said_and_no_empty_list_is_offered(self) -> None:
        v = village()
        for p in v.living():
            if p.sex == "Female" and gen._age_ok(p, gen.Rules()):
                p.expecting = True          # J (20), H (42), F (44), X (30): all four in the window
        text = gen.pair_report(v, gen.Rules(), "Test")
        self.assertNotIn("least related pairs available", text)
        self.assertIn("No pair meets every rule: no woman can be paired (of the 6 living women, "
                      "2 not aged 18-49 and 4 already expecting).", text)
        self.assertIn("== Every allowed partner, per woman ==\n  (none)", text)

    def test_no_man_at_all(self) -> None:
        v = village()
        for p in v.living():
            if p.sex == "Male":
                p.age = 10 * Y
        text = gen.pair_report(v, gen.Rules(), "Test")
        self.assertIn("no man can be paired (of the 6 living men, 6 not aged 18-49)", text)

    def test_pairs_still_listed_as_before(self) -> None:
        text = gen.pair_report(village(), gen.Rules(allow_50_plus=True, close_in_age=False), "Test")
        self.assertIn("== Suggested pairs (each villager once) ==\n  1. #", text)
        self.assertNotIn("(none)", text)


def heathen_mommy_village() -> gen.Village:
    v = village()
    v.game = 5
    v.people[20] = gen.Person(20, "Unknown", 2, 2, sex="Male", first_seen=v.people[1].first_seen)
    v.people[21] = gen.Person(21, "Upcoming child", -1, -1, upcoming=True, mother=12, father=20)
    for p in v.people.values():
        p.placeholder = gen.is_placeholder_father(5, p)
    gen._generations(v, {v.people[1].first_seen: set(v.people)})
    gen.number_people(v)
    return v


class HeathenMommyFather(unittest.TestCase):
    def test_unknown_2_2_is_new_believers_default_father_only(self) -> None:
        unknown = gen.Person(1, "Unknown", 2, 2)
        self.assertTrue(gen.is_placeholder_father(5, unknown))
        self.assertFalse(gen.is_placeholder_father(4, unknown), "The Tree of Life has no Heathen Mommy")
        unknown.alive = True                # a living villager of that name and look is a villager
        self.assertFalse(gen.is_placeholder_father(5, unknown))

    def test_never_drawn_as_a_founder_who_left(self) -> None:
        v = heathen_mommy_village()
        lay = ft.layout(v, ft.Edits())
        words = ft.default_text(lay, v.people[20])
        self.assertNotIn("Founder", words)
        self.assertNotIn("(left the village)", words)
        self.assertFalse(ft.is_founder(v, v.people[20]))
        report = gen.report(v, "Test")
        self.assertIn("Unknown (a default father: a name only, not a villager)", report)
        self.assertNotIn("no longer in the village -- generation I, founder", report)


class HeathenSaidOnce(unittest.TestCase):
    def test_a_living_heathen_with_the_heathen_mark(self) -> None:
        v = village()
        v.game = 5
        p = v.people[12]
        p.heathen, p.statuses = True, ["Heathen"]
        e = ft.Edits()
        ft.apply_auto_marks(e, v)
        words = ft.default_text(ft.layout(v, e), p)
        self.assertEqual(words.count("Heathen"), 1, words)
        plain = ft.default_text(ft.layout(v, ft.Edits()), p)       # no mark: the word is still said once
        self.assertEqual(plain.count("Heathen"), 1, plain)


class LookQuestion(unittest.TestCase):
    def test_head_and_body_both_named(self) -> None:
        import vv_genealogy_window as gw
        self.assertEqual(gw.look_choice("New", (22, 29)), "New look (head 22, body 29)")
        self.assertNotEqual(gw.look_choice("Old", (22, 13)), gw.look_choice("New", (22, 29)))


if __name__ == "__main__":
    unittest.main()
