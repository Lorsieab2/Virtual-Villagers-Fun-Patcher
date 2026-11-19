"""The owner, 2026-11-18: "In Game Mechanics, stuff that says 'wasn't counted' or similar should be checked, confirmed
and included. Nothing should be withheld!"  New Believers' lines that said "not traced", "an estimate" or "could not
be told" without the way out, each pinned to the value read from the stock exe or the patcher's own code (the
addresses are in each module's comments)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_game_mechanics as gm  # noqa: E402
import vv_game_mechanics_faith_vv5 as faith  # noqa: E402
import vv_game_mechanics_hidden as hidden  # noqa: E402
import vv_game_mechanics_hidden_vv5 as hidden5  # noqa: E402
import vv_game_mechanics_items_vv5 as items  # noqa: E402
import vv_game_mechanics_vv5 as vv5  # noqa: E402

NOW = 1.8e9
C = "VERIFIED-C"


def village(installed, certain: bool = True, general: bool = False) -> gm.Village:
    return gm.Village(Path("."), 5, 1, Path("5.ldw"), gm.blank_save(5, NOW), installed, NOW, certain=certain,
                      general=general)


def entry(name: str):
    return next(e for e in items.entries() if e.name == name)


def hidden_entry(name: str):
    return next(e for e in hidden5.entries() if e.name == name)


class TheSpawnRate(unittest.TestCase):
    def test_once_a_frame_at_30_frames_a_second(self) -> None:
        facts = [f for f in vv5.facts(village(frozenset())) if f.group == "Mushrooms"]
        line = next(f for f in facts if f.text.startswith("That is about one thing a real-life minute"))
        self.assertIn("(0.99 on average)", line.text)
        self.assertIn("once a frame and draws 30 frames a real-life second", line.text)
        self.assertEqual(line.verified, gm.CODE)
        page = " ".join(f.text for f in facts)
        self.assertNotIn("estimate", page)
        self.assertNotIn("was not read from the code", page)
        self.assertAlmostEqual(30 * 60 * 18 / 32768, 0.99, places=2)


class PatchNotTold(unittest.TestCase):
    def test_the_player_is_told_to_browse(self) -> None:
        lines = [f.text for f in faith.lines(village(None))]
        for feature in (faith.FAITH_LOSS, faith.NEW_HEATHENS, faith.HEATHEN_NOTICE):
            line = next(t for t in lines if f"\"{gm.feature_name(feature)}\" (" in t)
            self.assertIn("pick the game with Browse... on the Game Mechanics window", line, feature)


class Puzzles(unittest.TestCase):
    def test_divine_energy_at_the_start(self) -> None:
        text, verified = entry("Divine Energy").subs[0]
        self.assertEqual(text, "A new village starts with a Divine Energy cap of 50 and 50 Divine Energy: the game's "
                               "new-village set-up sets both as its last step.")
        self.assertEqual(verified, gm.CODE)

    def test_dismantling_counts(self) -> None:
        self.assertTrue(entry("The Hungry Totem").subs[0][0].startswith("It takes 12 dismantling actions"))
        self.assertTrue(entry("The Knowing Totem").subs[0][0].startswith("It takes 12 dismantling actions"))
        self.assertEqual(entry("The Blocking Totem").cost, "40 dismantling actions (\"Dismantling the Blocking "
                                                           "Totem\")")
        self.assertIn("the totem falls at 40", entry("The Blocking Totem").text)
        self.assertIn("restore the mausoleum while the game catches up", entry("The Blocking Totem").text)
        self.assertIn("the totem falls at 30", entry("The Rainbow Totem").text)
        self.assertIn("six children are squeezing into it at the same moment, it breaks 5 real-life seconds later",
                      entry("The Hollow Totem").text)
        for name in ("The Hungry Totem", "The Knowing Totem", "The Blocking Totem", "The Rainbow Totem",
                     "The Hollow Totem"):
            e = entry(name)
            self.assertNotIn("dismantling actions it takes was not traced", " ".join([e.text] + [t for t, _ in e.subs]))

    def test_barrel_and_everyone_collects(self) -> None:
        barrel = next(e for e in items.entries() if e.kind == items.PATCHER and e.name == "Barrel of Babies")
        self.assertEqual(barrel.subs, (("The purchase brings the believers' Barrel O' Babies! (the game's event 26), "
                                        "not the Heathens' one.", gm.CODE),))
        red = entry("Red (rare) mushroom")
        line = next(s for s in red.subs if "counted and paid once for each" in s[0])
        self.assertEqual(line[1], gm.CODE)


class Tips(unittest.TestCase):
    def test_pop_ups_once_a_village(self) -> None:
        subs = hidden_entry("Where the tips appear").subs
        once = next(t for t, v in subs if t.startswith("Each pop-up shows once a village"))
        self.assertIn("keeps the marks in the save", once)
        self.assertIn("\"No\" to \"Do you need help?\"", once)
        self.assertNotIn("Whether each pop-up shows once a village is not traced.", [t for t, _ in subs])
        randoms = next((t, v) for t, v in subs if t.startswith("Random tips 31 to 50"))
        self.assertEqual(randoms[1], gm.CODE)
        self.assertIn("never shows them", randoms[0])

    def test_worked_out_numbers(self) -> None:
        name = f"The {len(hidden5.POPUP_TIPS)} tip pop-ups (eTTip tutorial, eTip milestones)"
        lines = {int(t.split(":")[0]): (t, v) for t, v in hidden_entry(name).subs}
        for tip, words in ((739, "reaches 25 people"), (740, "reaches 50 people"),
                           (741, "90 people or more when there is no room to grow"),
                           (761, "Hut 1, 2 or 3 is restored"), (762, "the Clothing Hut is built"),
                           (767, "last relic"), (768, "last lab gear piece"), (700, "the Love Shack is built"),
                           (671, "the tutorial's next instruction"), (701, "the tutorial's next instruction")):
            self.assertIn(words, lines[tip][0], tip)
            self.assertEqual(hidden.label_of(lines[tip][1]), C, tip)
        for tip in (721, 724, 725, 727, 742, 764):
            self.assertIn("no code of the normal game asks for it", lines[tip][0], tip)
            self.assertEqual(hidden.label_of(lines[tip][1]), C, tip)
        self.assertNotIn("which is not traced", hidden_entry(name).text)

    def test_the_ground_click(self) -> None:
        e = hidden_entry("Places that show their state (village)")
        self.assertEqual(hidden.label(e), C)
        self.assertIn("\"<n> of 12 pieces of lab equipment collected\"", e.text)
        self.assertIn("\"13 of 12\"", e.text)
        self.assertNotIn("was not traced", e.text)


class RemainingList(unittest.TestCase):
    """The coordinator, 2026-11-18: New Believers' remaining lines and the owner's two questions."""

    def test_the_five_tutorial_tips_are_unused(self) -> None:
        tips = {t[0]: t for t in hidden5.POPUP_TIPS}
        for tip in (704, 705, 707, 710, 715):
            self.assertEqual(hidden5._popup_label(tips[tip]), hidden5.C)
            self.assertIn("unused", hidden5._popup_note(tips[tip]))

    def test_lab_equipment_of_12_and_of_24(self) -> None:
        text = hidden_entry("Places that show their state (village)").text
        self.assertIn("\"13 of 12\"", text)
        self.assertIn("\"<n> of 24\"", text)

    def test_f3_and_the_water(self) -> None:
        self.assertIn("pointer picture", hidden_entry("F3 (Puzzles and Milestones)").subs[0][0])
        water = hidden_entry("Places that show their state (village)").subs[0]
        self.assertIn("splash sound and makes a ripple", water[0])
        self.assertEqual(hidden.label_of(water[1]), C)

    def test_items_traced(self) -> None:
        self.assertIn("its map area 16", entry("Medicine level 2").subs[0][0])
        farm = entry("The Hydroponic Farm").subs[0]
        self.assertIn("so it takes 30", farm[0])
        for name in ("The Hollow Totem", "The Rainbow Totem"):
            self.assertIn("closed to the villagers' walking until the totem falls", entry(name).subs[0][0])

    def test_the_last_six(self) -> None:
        self.assertIn("Faith is set to 25 to 59", entry("The Heathen Builder").text)
        self.assertIn("With Research 88 or more", entry("The Heathen Scientist").text)
        self.assertIn("gains 30 Faith", entry("The Heathen Scientist").text)
        self.assertTrue(entry("The Tribute Statue").subs[0][0].startswith("DEAD (never runs)"))
        self.assertIn("the builder's after The Heathen Builder", entry("The Heathen Chief").subs[0][0])
        self.assertIn("\"Starting a fire\" with both in gives the third", entry("The fire pit").subs[0][0])
        self.assertFalse([e.name for e in items.entries() if e.verified is False])
        self.assertFalse([e.name for e in items.entries() for _t, v in e.subs if v is False])
        import vv_game_mechanics_nursery as nursery
        source = Path(nursery.__file__).read_text(encoding="utf-8")
        self.assertIn("a teacher who turns Heathen keeps the Nursery", source)
        self.assertNotIn("stays was not traced", source)


if __name__ == "__main__":
    unittest.main()
