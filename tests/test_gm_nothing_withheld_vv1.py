"""Game Mechanics "nothing withheld" (the owner, 2026-11-18): A New Home's lines and the lines every game shares that
used to say a value was not read, not traced or could not be told now show the value, or say why it cannot be known
and what the player can do.  Each check fails on the old text."""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_game_mechanics as gm  # noqa: E402
import vv_game_mechanics_hidden as hidden  # noqa: E402
import vv_game_mechanics_hidden_vv1 as hidden_vv1  # noqa: E402
import vv_game_mechanics_life as life  # noqa: E402
import vv_game_mechanics_tech_time as tech_time  # noqa: E402


def _subs(name: str) -> list[tuple[str, object]]:
    return list(next(e for e in hidden_vv1.entries() if e.name == name).subs)


class SharedWording(unittest.TestCase):
    def test_could_not_be_told_says_what_to_do(self) -> None:
        self.assertIn("Browse...", gm.BROWSE_HINT)
        self.assertTrue(gm.UNTOLD.endswith(gm.BROWSE_HINT))

        class Unknown:
            def has(self, _feature):
                return None
        words = gm.patch_words(Unknown(), "vv1_learning_never_fails", "x")
        self.assertIn(gm.BROWSE_HINT, words)

    def test_difficulty_is_never_just_not_read(self) -> None:
        self.assertEqual(life.difficulty_words(2), "Hard")
        self.assertIn("never set", life.difficulty_words(7))
        self.assertIn("not in this save", life.difficulty_words(None))
        self.assertNotIn("not read", life.difficulty_words(None) + life.difficulty_words(7))


class TechDoubler(unittest.TestCase):
    def test_a_new_home_reads_the_doubler_from_the_save(self) -> None:
        # native/vv1_origins_icons VV_DOUBLER_TECH_OFFSET 0x9E90, file offset state + 4.
        self.assertEqual(tech_time.DOUBLER_TECH_AT[1][0], 0x9E94)
        data = bytearray(0xABDC + 12)
        self.assertIs(tech_time.doubler_owned(1, bytes(data)), False)
        struct.pack_into("<I", data, 0x9E94, 1)
        self.assertIs(tech_time.doubler_owned(1, bytes(data)), True)
        self.assertIsNone(tech_time.doubler_owned(1, b"\0" * 16))

    def test_every_game_reads_its_doubler_bit(self) -> None:
        # VV2 state +0x2EAE8 bit 1; VV3-VV5 the statistics block's +0x30 bit 1 (bit 2 is the Food Doubler).
        for game, at in ((2, 0x2EAEC), (3, 0x520), (4, 0x890), (5, 0x7F4)):
            with self.subTest(game=game):
                self.assertEqual(tech_time.DOUBLER_TECH_AT[game], (at, 1))
                data = bytearray(at + 8)
                struct.pack_into("<I", data, at, 2)                  # the Food Doubler only
                self.assertIs(tech_time.doubler_owned(game, bytes(data)), False)
                struct.pack_into("<I", data, at, 3)
                self.assertIs(tech_time.doubler_owned(game, bytes(data)), True)

    def test_no_line_says_not_read_here_or_not_counted(self) -> None:
        source = (ROOT / "src" / "vv_game_mechanics_tech_time.py").read_text(encoding="utf-8")
        self.assertNotIn("whether this save owns one is not read here", source)
        self.assertNotIn('add("Not counted:', source)
        self.assertIn("Outside the times above, each with its value", source)
        self.assertIn("a quarter (Science 1 or more)", source)


class ANewHomeHidden(unittest.TestCase):
    def test_the_message_line_clears_after_five_seconds(self) -> None:
        text, verified = _subs("The mask (village screen)")[0]
        self.assertIn("clears itself 5 real-life seconds after it was set", text)
        self.assertIn("\"GAME PAUSED\"", text)
        self.assertEqual(hidden.label_of(verified), "VERIFIED-C")

    def test_no_switches_the_tutorial_off(self) -> None:
        text, verified = _subs("Where the tips appear")[0]
        self.assertIn("answering \"No\"", text)
        self.assertIn("tips 261 to 311", text)
        self.assertNotIn("not observed", text)
        self.assertEqual(hidden.label_of(verified), "VERIFIED-C")


class SaveFallbacks(unittest.TestCase):
    def test_short_or_damaged_saves_say_why(self) -> None:
        for name in ("vv_game_mechanics_life.py", "vv_game_mechanics_counts.py"):
            source = (ROOT / "src" / name).read_text(encoding="utf-8")
            self.assertNotIn("where this game's save keeps its collection counts", source)
            self.assertNotIn("not read from this save by this page", source)
            self.assertNotIn("this save's Medicine level is not read here", source)
            self.assertNotIn("rows only that log keeps are not shown", source)


class RemainingList(unittest.TestCase):
    """The coordinator, 2026-11-18: A New Home's remaining lines, traced."""

    def test_the_tips_and_who_asks_for_them(self) -> None:
        tips = {t[0]: t for t in hidden_vv1.POPUP_TIPS}
        for tip, site in ((301, 0x4237AE), (313, 0x42F28B), (314, 0x42F28B), (315, 0x42F28B), (324, 0x43ABAB)):
            self.assertEqual(tips[tip][2], (site,), tip)
        self.assertEqual(hidden_vv1.NEVER_ASKED, frozenset({275, 289, 308, 309, 310}))
        for tip in hidden_vv1.NEVER_ASKED:
            self.assertIn("never shows it", hidden_vv1._popup_note(tips[tip]))
        self.assertTrue(all(hidden_vv1._popup_label(t) == hidden.C for t in hidden_vv1.POPUP_TIPS))

    def test_f3_the_mask_sparkles_and_the_graveyard(self) -> None:
        f3 = next(e for e in hidden_vv1.entries() if e.name.startswith("F3"))
        self.assertIn("pointer picture", f3.subs[0][0])
        self.assertIn("two little sparkles", _subs("The mask (village screen)")[1][0])
        grid = next(e for e in hidden_vv1.entries() if e.name.startswith("The grid at the map spot"))
        self.assertIn("the graveyard", grid.text)
        self.assertEqual(hidden.label(grid), "VERIFIED-C")

    def test_movement_step_one(self) -> None:
        import vv_game_mechanics_vv1 as vv1
        line = next((t, ok) for t, ok in vv1.HIDDEN_LINES if t.startswith("Another movement step"))
        self.assertIn("\"Not feeling well\", \"Strolling\" and the Golden Child's own wandering", line[0])
        self.assertEqual(line[1], gm.CODE)


if __name__ == "__main__":
    unittest.main()
