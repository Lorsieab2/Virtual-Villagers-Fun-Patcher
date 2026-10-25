"""The Family Tree's special descriptors, given by themselves where they apply (all five games).

The owner (2026-10-22): "I hope villagers get auto-denoted with special descriptors if applicable (tribal
chief, founder, runner etc)" -- the Faces & Text tab's descriptor tick boxes (Founder, Runner, twins and
triplets, how they arrived, Master of a skill, and each special villager status of the game) are ticked
unless the player unticks them; each shows only on the villagers it applies to.  A status's words and its
mark are one: untick either and both go, and stay gone (the tree's own data, never the save).
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_corrupt_skills as cs  # noqa: E402
import vv_family_tree as ft  # noqa: E402
import vv_genealogy as gen  # noqa: E402
import vv_graves  # noqa: E402
from test_genealogy import village  # noqa: E402
from test_reconcile import CASES, Base  # noqa: E402
from test_tree_auto_marks import death, hand_village, holder  # noqa: E402

GAMES = CASES[:5]


class OnByDefault(unittest.TestCase):
    FIELDS = ("show_founder", "show_runner", "show_twins", "show_arrived", "show_masters")

    def test_a_new_tree_and_an_older_one_have_them_on_and_an_untick_is_kept(self) -> None:
        for attr in self.FIELDS:
            with self.subTest(attr=attr):
                self.assertTrue(getattr(ft.Edits(), attr))
                # An earlier build wrote False whether or not the player unticked it: the new default.  (The two
                # new options no earlier build wrote: a False is the player's.)
                legacy = attr in ("show_founder", "show_runner", "show_twins")
                self.assertEqual(getattr(ft.Edits.from_data({"format": 1, attr: False}), attr), legacy)
                off = ft.Edits(**{attr: False})
                self.assertFalse(getattr(ft.Edits.from_data(off.to_data()), attr), "an untick saved now is kept")
                self.assertTrue(getattr(ft.styled({attr: False}), attr) if attr in ("show_founder", "show_runner",
                                                                                     "show_twins") else True)
        # No "Master of a skill" tick box: the tree never says "Master Farmer" (the owner, 2026-10-25).
        self.assertEqual([a for a, _w in ft.DESCRIPTOR_OPTIONS], list(self.FIELDS[:4]))


class WhereTheyApply(unittest.TestCase):
    def test_founder_runner_twins_and_arrival(self) -> None:
        v = village()
        v.people[5].runner = True
        lay = ft.layout(v, ft.Edits())
        self.assertIn("Founder", ft.default_text(lay, v.people[1]))           # A: How: Founder
        self.assertNotIn("Founder", ft.default_text(lay, v.people[5]))        # E: born to A and B
        self.assertNotIn("Founder", ft.default_text(lay, v.people[12]))       # X: an island-event arrival
        self.assertIn("Arrived: Custom Island Event", ft.default_text(lay, v.people[12]))
        self.assertNotIn("Arrived: Founder", ft.default_text(lay, v.people[1]))
        self.assertIn("Runner", ft.default_text(lay, v.people[5]))
        self.assertNotIn("Runner", ft.default_text(lay, v.people[6]))
        self.assertIn("J's twin", ft.default_text(lay, v.people[9]))
        off = ft.layout(v, ft.Edits(show_founder=False, show_runner=False, show_twins=False, show_arrived=False))
        for pid in (1, 5, 9, 12):
            self.assertEqual(ft.default_text(off, v.people[pid])[3:], [], pid)

    def test_a_backfilled_unknown_arrival_says_nothing(self) -> None:
        v = village()
        v.people[12].how = "unknown"
        self.assertEqual(ft.arrival_words(v, v.people[12]), "")

    def test_the_status_words_but_never_master_of_a_skill(self) -> None:
        """The owner, 2026-10-25: no "Master Farmer", "Master Builder"... on the tree, only the special labels."""
        v, e = hand_village(), ft.Edits()
        v.people[1].masters = ["Farmer", "Builder", "Scientist", "Parent"]
        ft.apply_auto_marks(e, v)
        lay = ft.layout(v, e)
        words = ft.default_text(lay, v.people[1])
        for w in ("Tribal Chief", "Esteemed Elder"):
            self.assertIn(w, words)
        self.assertFalse([w for w in words if w.startswith("Master ")], words)
        self.assertIn("Keeper of Shells", ft.default_text(lay, v.people[3]))   # a Custom title too


class TheMarkAndItsWordsAreOne(unittest.TestCase):
    def test_a_mark_taken_off_one_villager_takes_their_words(self) -> None:
        v, e = hand_village(), ft.Edits()
        ft.apply_auto_marks(e, v)
        e.entries["Chief|1|1"] = {"marks": ["Esteemed Elder"], "mark": "Esteemed Elder", "unmarked": ["Tribal Chief"]}
        words = ft.default_text(ft.layout(v, e), v.people[1])
        self.assertNotIn("Tribal Chief", words)
        self.assertIn("Esteemed Elder", words)

    def test_the_option_unticked_takes_the_mark_off_everyone_and_ticked_gives_it_back(self) -> None:
        v, e = hand_village(), ft.Edits()
        ft.apply_auto_marks(e, v)
        e.entries["Old|3|3"] = {"marks": ["Converted Red Mask Heathen"], "mark": "Converted Red Mask Heathen",
                                "unmarked": ["Keeper of Shells"]}     # one villager's own untick
        ft.set_status_option(e, v, "Tribal Chief", False)
        self.assertEqual(e.entries["Chief|1|1"]["marks"], ["Esteemed Elder"])
        self.assertIn(("Tribal Chief", False), ft.status_options(e, v))
        ft.apply_auto_marks(e, v)                                     # the tree opened again: still off
        self.assertNotIn("Tribal Chief", e.entries["Chief|1|1"]["marks"])
        self.assertNotIn("Tribal Chief", ft.default_text(ft.layout(v, e), v.people[1]))
        ft.set_status_option(e, v, "Tribal Chief", True)
        self.assertIn("Tribal Chief", e.entries["Chief|1|1"]["marks"])
        self.assertIn(("Tribal Chief", True), ft.status_options(e, v))
        ft.set_status_option(e, v, "Keeper of Shells", True)
        self.assertNotIn("Keeper of Shells", ft.entry_marks(e.entries["Old|3|3"]), "the villager's own untick stays")

    def test_options_only_for_the_game_they_apply_to(self) -> None:
        for game in range(1, 6):
            with self.subTest(game=game):
                v = gen.Village(game, 1, "T", {})
                labels = [label for label, _on in ft.status_options(ft.Edits(), v)]
                self.assertEqual(labels, list(gen.GAME_STATUSES[game]))
        self.assertIn("Tribal Chief", gen.GAME_STATUSES[3])
        self.assertNotIn("Tribal Chief", gen.GAME_STATUSES[5])
        self.assertIn("Heathen", gen.GAME_STATUSES[5])
        self.assertEqual(gen.GAME_STATUSES[1], ("Golden Child",))
        v = hand_village()                                            # The Secret City, with a Custom title
        self.assertIn("Keeper of Shells", [label for label, _on in ft.status_options(ft.Edits(), v)])
        renamed = ft.Edits(mark_names={"Tribal Chief": "Big Chief"})
        self.assertIn("Big Chief", [label for label, _on in ft.status_options(renamed, v)])


class MastersFromTheSaveAndTheGraves(Base):
    def test_the_living_by_their_skills_in_every_game(self) -> None:
        for tag, game in GAMES:
            with self.subTest(game=game):
                v = self.village(tag, game)
                data = bytearray(v.save_path(1).read_bytes())
                at = v.entries(bytes(data))[0]
                names = cs.SKILL_NAMES[game]
                off, is_float = cs.SKILLS[game]
                level = vv_graves.LAYOUTS[game].master
                values = [level] + [level - 1] * (len(names) - 1)
                struct.pack_into(f"<{len(names)}{'f' if is_float else 'i'}", data, at + off, *values)
                v.write_save(1, bytes(data))
                x = v.people(bytes(data))[0]
                village_ = gen.load_village(v.folder, game, 1)
                self.assertEqual(holder(village_, x.name, alive=True).masters, [gen.JOB_OF_SKILL[names[0]]])

    def test_the_dead_by_their_graves_best_skill(self) -> None:
        v = self.village("huttest", 3)
        data = bytearray(v.save_path(1).read_bytes())
        lay = vv_graves.LAYOUTS[3]
        at = lay.base
        data[at:at + lay.name_cap] = b"Oldmaster".ljust(lay.name_cap, b"\0")
        struct.pack_into("<i", data, at + lay.age, 900)
        struct.pack_into("<i", data, at + lay.job, 2)                  # Doctor
        struct.pack_into("<i", data, at + lay.value, 95)
        data[at + lay.chief] = 0
        v.write_save(1, bytes(data))
        v.deaths(death(1, "Oldmaster", 3, 4, 900))
        village_ = gen.load_village(v.folder, 3, 1)
        self.assertEqual(holder(village_, "Oldmaster").masters, ["Doctor"])


if __name__ == "__main__":
    unittest.main()
