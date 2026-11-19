"""The owner, 2026-11-18: "In Game Mechanics, stuff that says 'wasn't counted' or similar should be checked, confirmed
and included. Nothing should be withheld!"  The Lost Children's lines that said "not traced", "not proven", "not
confirmed" or "not known", each pinned to the value read from the stock exe or the patcher's own code (the addresses
are in each module's comments)."""
from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_game_mechanics as gm  # noqa: E402
import vv_game_mechanics_events_vv2 as events  # noqa: E402
import vv_game_mechanics_hidden_vv2 as hidden2  # noqa: E402
import vv_game_mechanics_items_vv2 as items  # noqa: E402
import vv_game_mechanics_vv2 as vv2  # noqa: E402

WITHHELD = ("not traced", "was not proven", "not confirmed", "no effect of theirs is known", "father unknown",
            "not read from this save")


def lines(name: str) -> list[tuple[str, object]]:
    return list(next(e for e in items.ENTRIES if e.name == name).lines)


def line(name: str, start: str) -> tuple[str, object]:
    return next((t, v) for t, v in lines(name) if t.startswith(start))


def hidden_entry(name: str):
    return next(e for e in hidden2.entries() if e.name == name)


class NothingWithheldOnTheItemsTab(unittest.TestCase):
    def test_no_line_says_it_was_not_traced(self) -> None:
        for fact in items.item_facts():
            for words in WITHHELD:
                self.assertNotIn(words, fact.text)

    def test_the_cauldron(self) -> None:
        text, label = line("Exploration level 2", "Level 2 also lets your villagers find the cauldron")
        self.assertIn("\"Retrieving a cauldron\"", text)
        self.assertIn("only then can stews be cooked", text)
        self.assertIn("The first spot for The Cutting Tool also appears only from level 2.", text)
        self.assertEqual(label, gm.CODE)

    def test_the_culture_picks(self) -> None:
        text, label = line("Culture level 2", "A culture activity is then rolled again")
        self.assertIn("51 times in 100 nothing comes of it", text)
        self.assertIn("one of six, each 1 in 6", text)
        self.assertIn("while the village has a grave, Honoring the Dead or Reflecting, 1 in 2 each", text)
        self.assertIn("the two dances not for a villager who dislikes dancing", text)
        self.assertEqual(label, gm.CODE)

    def test_the_sewing_hut_site(self) -> None:
        text, label = line("Culture level 2", "With Science level 2 as well")
        self.assertEqual(text, "With Science level 2 as well, the sewing hut's building site appears: a villager "
                               "dropped on it starts \"Building a sewing hut\" (The Sewing Hut).")
        self.assertEqual(label, gm.CODE)

    def test_the_fire(self) -> None:
        text, label = lines("Fire")[0]
        self.assertIn("(\"Gathering dry grass\")", text)
        self.assertIn("(\"Gathering firewood\")", text)
        self.assertIn("(\"Starting a fire\")", text)
        self.assertIn("\"There is no firewood here.\"", text)
        self.assertIn("\"Some dry grass would help the fire ignite.\"", text)
        self.assertEqual(label, gm.CODE)

    def test_the_puzzles(self) -> None:
        for name, words in (
                ("The Sewing Hut", "new clothes for 5,000 tech points"),
                ("The Sewing Hut", "\"Not enough tech points to make new clothes!\""),
                ("The Cutting Tool", "\"Special wood is needed to finish the tool.\""),
                ("The Cutting Tool", "flexible pieces of wood"),
                ("The Vine Wall", "\"Reading the writings on the wall\""),
                ("The Vine Wall", "\"The Ancient Writings\""),
                ("The Boxed Gong Piece", "three villagers over 14 with Building 88 or more"),
                ("The Boxed Gong Piece", "\"It is too hard to do alone\""),
                ("The Sunken Gong Piece", "the breathing stew (stew 5, Stews)"),
                ("The Inlaid Gong Piece", "drag an Esteemed Elder's totem onto the mosaic")):
            with self.subTest(name=name, words=words):
                found = [v for t, v in lines(name) if words in t]
                self.assertEqual(found, [gm.CODE])

    def test_stew_five(self) -> None:
        self.assertTrue(items.STEW_EFFECTS[4].startswith("5: the breathing stew: the game remembers the last "
                                                         "villager to eat it"))

    def test_the_herbs_of_each_stew(self) -> None:
        stews = dict((t, v) for t, v in lines("Stews"))
        self.assertIn("Stew 5: Purple-black flower + Orange flower + Orange flower.", stews)
        self.assertIn("Stew 18: Purple-black flower + Purple-black flower + Purple-black flower.", stews)
        self.assertIn("Stew 3: Dark blue flower + Purple-black flower + Light blue flower; Dark blue flower + Brown "
                      "pitcher plant + Light blue flower.", stews)
        mixes = [t for t in stews if t.startswith("Stew ") and " + " in t]
        self.assertEqual(len(mixes), 17)                 # stews 2 to 18; every other mix makes stew 1
        self.assertTrue(all(stews[t] == gm.RUNNING for t in mixes))

    def test_the_origins_rows_are_read_from_the_patchers_code(self) -> None:
        for name in ("Origins: Full Heal / Cure All", "Origins: village-wide rows", "Origins: Villager Details rows"):
            self.assertTrue(all(v == gm.CODE for _t, v in lines(name)), name)
        self.assertIn("each villager cured counts in People Cured", lines("Origins: Full Heal / Cure All")[0][0])
        self.assertIn("every living villager with fewer than 3 likes", lines("Origins: village-wide rows")[0][0])
        self.assertIn("adds running to the villager's likes and removes a running dislike",
                      " ".join(t for t, _ in lines("Origins: Villager Details rows")))


class NothingWithheldOnTheHiddenTab(unittest.TestCase):
    def test_f3_is_the_mouse_pointer(self) -> None:
        e = hidden_entry("F3 (Collections, the help pictures, one of the intro pages, Puzzles and Milestones)")
        self.assertEqual(list(e.subs), [("The setting is the mouse pointer: F3 hides the pointer inside the game "
                                         "window and F3 again shows it (it starts shown).", hidden2.C)])

    def test_a_typed_character_ends_the_page(self) -> None:
        e = hidden_entry("Any typed character (the intro pages and the gamewin_bg.jpg screen)")
        (text, label), = e.subs
        self.assertIn("it fades out and the next screen comes", text)
        self.assertEqual(label, hidden2.C)

    def test_the_mask_sparkles(self) -> None:
        text, label = hidden_entry("The mask (village screen)").subs[0]
        self.assertIn("two little sparkles beside it (the game's sparkle picture, sparklestrip2.png)", text)
        self.assertEqual(label, hidden2.C)

    def test_the_places_and_their_figures(self) -> None:
        subs = dict(hidden_entry("Places that show their state (village)").subs)
        figure = next(t for t in subs if t.startswith("The figure after each line"))
        self.assertIn("the work done as a percentage of the whole job (rounded down)", figure)
        places = next(t for t in subs if t.startswith("The places:"))
        for words in ("area 3 the coconut trees", "59 the sewing hut", "31 the dam", "20 and 70 the vine wall"):
            self.assertIn(words, places)
        self.assertEqual({subs[figure], subs[places]}, {hidden2.C})
        self.assertFalse(any("not traced" in t for t in subs))

    def test_esc_closes_the_upgrades_menus(self) -> None:
        e = hidden_entry("Upgrades buttons (Tech and Villager Detail screens)")
        self.assertEqual(list(e.subs), [("Esc closes these menus without buying anything, as Cancel does.",
                                         hidden2.C)])


class NothingWithheldElsewhere(unittest.TestCase):
    def test_the_37_untested_likes(self) -> None:
        text, label = next((t, v) for t, v in vv2.HIDDEN_LINES if t.startswith("The other 37 likes and dislikes"))
        self.assertIn("the game's code never tests them, so they change nothing in play", text)
        self.assertIn("ants, butterflies", text)
        self.assertIn("clouds, dirt)", text)
        self.assertEqual(text.split("(", 1)[1].split(")", 1)[0].count(",") + 1, 37)
        self.assertEqual(label, gm.CODE)

    def test_the_gong_babies_father(self) -> None:
        gong = next(e for e in events.EXTRA if e.title == "Gong of Wonder")
        tier_a = next(s for s in gong.subs if isinstance(s, str) and s.startswith("Tier A"))
        self.assertIn("becomes pregnant, the father recorded as \"?\"", tier_a)
        self.assertNotIn("father unknown", tier_a)

    def test_a_short_save_says_why_the_collectibles_are_missing(self) -> None:
        source = inspect.getsource(vv2)
        self.assertIn("not in this save (the file ends before them; the game's ", source)
        self.assertIn("Collections screen shows them)", source)
        self.assertNotIn("not read from this save", source)


class Birds(unittest.TestCase):
    """The owner, 2026-11-18: the whole birds explanation, answer first, in every mode."""

    def test_the_rule_is_on_the_general_page_without_a_live_line(self) -> None:
        texts = [f.text for f in gm.general(2, 1_800_000_000.0) if f.group == "Food sources"]
        self.assertFalse(any(t.startswith("The birds: ") for t in texts))
        rule = next(t for t in texts if t.startswith("When the birds come they eat every crop on the field"))
        self.assertIn("instead of refilling to 800 at every regrowth", rule)
        self.assertIn("There is no chance roll", rule)
        self.assertTrue(any("so it runs out after 100, 143 or 250 harvests" in t for t in texts))
        self.assertTrue(any("(not only the first time)" in t for t in texts))

    def test_every_tip_pop_up_says_how_it_comes(self) -> None:
        for tip in hidden2.POPUP_TIPS:
            self.assertTrue(tip[2] or hidden2._popup_note(tip), tip[0])
        self.assertIn("flashing tutorial button", hidden2._popup_note(next(t for t in hidden2.POPUP_TIPS
                                                                             if t[0] == 393)))
        self.assertIn("when it reaches 50", hidden2._popup_note(next(t for t in hidden2.POPUP_TIPS if t[0] == 453)))
        self.assertEqual(hidden2.NEVER_ASKED, frozenset({442, 443}))

    def test_harvests_to_use_up_the_allowance(self) -> None:
        self.assertEqual([-(-vv2.BIRD_ALLOWANCE // n) for n in vv2.BIRD_HARVEST], [100, 143, 250])


if __name__ == "__main__":
    unittest.main()
