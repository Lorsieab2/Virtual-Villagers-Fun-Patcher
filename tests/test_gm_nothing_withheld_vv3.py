"""The owner, 2026-11-18: "In Game Mechanics, stuff that says 'wasn't counted' or similar should be checked,
confirmed and included. Nothing should be withheld!"  The Secret City's lines that once said "left out", "not
traced", "not read" or "not seen", each now showing the value traced in the stock exe (addresses in the modules'
comments), pinned here with their labels.  Every assertion fails on the old text."""
from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_game_mechanics as gm  # noqa: E402
import vv_game_mechanics_chances as ch  # noqa: E402
import vv_game_mechanics_chances_vv3 as chances_vv3  # noqa: E402
import vv_game_mechanics_hidden_vv3 as hidden_vv3  # noqa: E402
import vv_game_mechanics_items_vv3 as items  # noqa: E402


def _roll(start: str) -> ch.Roll:
    found = [r for r in chances_vv3.ROLLS if r.text.startswith(start)]
    assert len(found) == 1, start
    return found[0]


def _entry(name: str) -> items.Entry:
    return next(e for e in items.entries() if e.name == name)


class CosmeticRollsAreShown(unittest.TestCase):
    """Chances: the creation looks, pose and place, the dead look lists, research's sparkle and the lesson."""

    def test_the_comment_no_longer_leaves_them_out(self) -> None:
        source = inspect.getsource(chances_vv3)
        self.assertNotIn("Cosmetic rolls left out", source)
        self.assertNotIn("reported, not shown", source)

    def test_looks_at_creation(self) -> None:
        roll = _roll("A new villager's looks")
        self.assertEqual(roll.verified, gm.CODE)
        words = roll.words(roll.text)
        self.assertIn("one of the 29 everyday bodies, each 3.45%", words)
        self.assertIn("the robe, comes only with becoming the Tribal Chief", words)
        self.assertIn("one of the 30 heads, each 3.33% or 3.34%", words)
        subs = [roll.words(s) for s in roll.subs]
        self.assertIn("A baby's head: 95% of the time the average of its two parents' heads (rounded down) moved by "
                      "-1, 0 or +1, a third each, and kept within the 30; otherwise (5%) one of the 30 at random, "
                      "as for a founder.", subs)
        self.assertIn("A new villager first appears standing 51.05% of the time and sitting 48.95%; a Crystal of "
                      "Reflections copy rolls the same.", subs)
        self.assertTrue(any(s.startswith("A baby or an island-event arrival first appears at a random spot")
                            for s in subs))
        self.assertTrue(any(s.startswith("DEAD code (never runs)") for s in subs))
        sites = {c.site for c in roll.checks}
        self.assertTrue({0x456522, 0x456500, 0x4564A9, 0x4564DC, 0x4565C4, 0x456365, 0x4563C7} <= sites)

    def test_research_sparkle(self) -> None:
        roll = _roll("Research's sparkle")
        self.assertEqual(roll.verified, gm.CODE)
        self.assertIn("one of three small effects 10.01% of the time", roll.words(roll.text))
        self.assertIn("it changes nothing", roll.text)

    def test_the_step_42_reward_is_educate_the_childrens_lesson(self) -> None:
        roll = _roll("Educate the Children's lesson")
        self.assertEqual(roll.verified, gm.CODE)
        self.assertIn("gains 7, 8 or 9 points (a third each) in one of the five skills", roll.text)
        self.assertIn("each 20% (a roll of 0 to 4)", roll.text)
        self.assertEqual({c.site for c in roll.checks}, {0x458F13, 0x458F2D})

    def test_the_weather_strength_pictures_are_named(self) -> None:
        roll = _roll("The weather:")
        last = roll.subs[-1]
        self.assertNotIn("was not seen", last)
        self.assertIn("the overview map also shows a puddle", last)
        self.assertIn("the ground map's patch at the Lift", last)
        self.assertEqual(roll.sub_verified[-1], gm.CODE)

    def test_the_new_lines_reach_the_page(self) -> None:
        village = gm.Village(Path("."), 3, 1, Path("x"), b"", frozenset(), 0.0)
        text = "\n".join(f.text for f in ch.facts(village))
        self.assertIn("A new villager first appears standing 51.05%", text)
        self.assertIn("Research's sparkle", text)
        self.assertIn("Educate the Children's lesson", text)


class ItemsShowTheTracedRules(unittest.TestCase):
    def test_the_robe_chooser(self) -> None:
        text, ok = _entry("The First Chief").subs[0]
        self.assertEqual(ok, gm.CODE)
        self.assertIn("it draws one at random when the village is made", text)
        self.assertIn("draws again every 2 real-life seconds", text)
        self.assertNotIn("chosen when the village is made and not shown to the player", text)

    def test_the_roster_of_the_dead(self) -> None:
        entry = _entry("The Roster of the Dead")
        self.assertEqual(entry.verified, gm.CODE)
        self.assertIn("each \"Clearing leaves\" trip adds 1 when the villager reaches the roster, 2 when the Tribal "
                      "Chief directing that work passes the supervision roll", entry.text)
        self.assertNotIn("not traced", entry.text)

    def test_weather_dancing(self) -> None:
        entry = _entry("Weather Dancing")
        self.assertEqual(entry.verified, gm.CODE)
        self.assertIn("3 or more villagers with Farming 50 or more are \"Doing a weather dance\"", entry.text)
        self.assertIn("15 seconds later on the game's clock (7.5, 15 or 25 real-life seconds", entry.text)
        self.assertIn("fog comes instead", entry.text)

    def test_the_lift_tip_is_the_games_string(self) -> None:
        self.assertEqual(_entry("The Lift").subs[0][1], gm.CODE)

    def test_the_cliff_and_clam_keys(self) -> None:
        for name in ("The Cliff Key", "The Clam Key"):
            entry = _entry(name)
            self.assertEqual(entry.verified, gm.CODE, name)
            self.assertNotEqual(entry.text, "solved in 1 step.", name)
        self.assertIn("Someone left some burned-out torches here", _entry("The Cliff Key").text)

    def test_educate_needs_leadership_two(self) -> None:
        text, ok = _entry("Educate the Children (the chief's power)").subs[0]
        self.assertEqual(ok, gm.CODE)
        self.assertNotIn("the game's Leadership text says so", text)
        self.assertIn("It needs Leadership level 2", text)

    def test_the_clothes_deduction(self) -> None:
        text, ok = _entry("New clothes").subs[0]
        self.assertEqual(ok, gm.CODE)
        self.assertNotIn("not traced", text)
        self.assertIn("the 5,000 tech points are taken as the clothes screen opens", text)

    def test_patches_traced_in_their_bytes(self) -> None:
        nature = _entry("Nature level 3").subs[0]
        self.assertEqual(nature[1], gm.CODE)
        self.assertIn("62, 70 or 78 years", nature[0])
        self.assertEqual(_entry("Learning Skills Never Fails").verified, gm.CODE)


class HiddenShowsTheSharedSlot(unittest.TestCase):
    def test_the_three_screens(self) -> None:
        entry = next(e for e in hidden_vv3._keys() if e.name.startswith("Esc (the shared slot"))
        text, ok = entry.subs[0][0], entry.subs[0][1]
        self.assertNotIn("not read here", text)
        self.assertIn("Collections, Puzzles and Milestones, and Tech", text)
        self.assertEqual(ok, hidden_vv3.C)


class KeptListDone(unittest.TestCase):
    """The coordinator, 2026-11-18: the patcher's own rows, the sharks and The Chief and the Princess, traced."""

    def test_no_catalog_line_is_unconfirmed(self) -> None:
        self.assertEqual([e.name for e in items.entries() if e.verified is False], [])
        self.assertEqual([e.name for e in items.entries() for _t, v in e.subs if v is False], [])

    def test_the_chief_and_the_princess(self) -> None:
        entry = _entry("The Chief and the Princess")
        self.assertIn("once all three keys are in place", entry.text)
        self.assertIn("every 3 minutes of the game's clock", entry.text)
        self.assertEqual(entry.verified, gm.CODE)

    def test_the_patchers_rows(self) -> None:
        self.assertIn("5 real-life seconds (real time, the same at every speed) after it is bought",
                      _entry("Island Event").text)
        self.assertIn("below 80 health is brought to 100", _entry("Full Heal").text)
        self.assertIn("450,000", _entry("Change Appearance for All").text)
        # PR #805 (4648d5680, 3b5990488): The Secret City's doublers cover research, fish and crabs.
        self.assertIn("the tech points research earns are doubled (with the chief's, Magic's, the potion's and the "
                      "fire's extra points)", _entry("Tech Point Doubler").text)
        self.assertIn("the food gathered from food sources is doubled (fruit, honey, fish, crabs and mushrooms, with "
                      "the chief's bonuses), and so is the chief's grant of food", _entry("Food Point Doubler").text)
        self.assertIn("a running dislike is taken away for free", _entry("Grant Running").text)

    def test_every_tip_pop_up_says_how_it_comes(self) -> None:
        for tip in hidden_vv3.POPUP_TIPS:
            self.assertTrue(tip[2] or hidden_vv3._how(tip), tip[0])
        self.assertIn("Coral collection is completed", hidden_vv3._how(next(t for t in hidden_vv3.POPUP_TIPS
                                                                            if t[0] == 721)))
        self.assertIn("each time a hut is finished", hidden_vv3._how(next(t for t in hidden_vv3.POPUP_TIPS
                                                                          if t[0] == 717)))

    def test_places_and_the_plaque(self) -> None:
        subs = [t for t, _v in next(e for e in hidden_vv3.entries()
                                    if e.name == "Places that show their state (village)").subs]
        self.assertTrue(any(t.startswith("Which place gives which line: the fire pit") for t in subs))
        self.assertTrue(any("opens the Roster of the Dead" in t for t in subs))

    def test_the_tutorial_coral(self) -> None:
        import vv_game_mechanics_vv3 as vv3
        line = next(t for t, _ok in vv3.CHANCE_LINES if "(tip 658)" in t)
        self.assertIn("gone after 90 real-life seconds", line)

    def test_the_sharks_have_no_timer(self) -> None:
        import vv_game_mechanics_vv3 as vv3
        texts = [t for t, _ok in vv3.CHANCE_LINES]
        self.assertTrue(any(t.startswith("The sharks have no timer") for t in texts))
        self.assertFalse(any("the sharks' timer" in t for t in texts))


if __name__ == "__main__":
    unittest.main()
