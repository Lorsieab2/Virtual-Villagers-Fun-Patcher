"""A New Home's Golden Child subsection of the Game Mechanics window (src/vv_game_mechanics_vv1.py
golden_child_facts, GOLDEN_CHILD_LINES): the rules traced on the stock executable, this save's Golden Child, his
puzzle and the cave's 36-hour timer with its live countdown.  The committed real save (tests/fixtures/rename_tribe)
is copied and changed byte by byte at the offsets the module documents."""
from __future__ import annotations

import math
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_game_mechanics as gm  # noqa: E402
import vv_game_mechanics_life as life  # noqa: E402
import vv_game_mechanics_vv1 as vv1  # noqa: E402
from test_game_mechanics_life import NOW, entries, fixture, group, page, put  # noqa: E402


def created(data: bytes) -> int:
    return struct.unpack_from("<I", data, 4)[0] + struct.unpack_from("<i", data, vv1.CREATED)[0]


def with_golden_child(data: bytearray, born_hour: int, cave_open: bool = False, alive: bool = True) -> str:
    data[vv1.GC_FLAG] = 1
    put(data, vv1.GC_HOUR, born_hour)
    data[vv1.CAVE_FLAG] = 1 if cave_open else 0
    put(data, vv1.CAVE_HOUR, born_hour + 1 if cave_open else 0)
    at = entries(1, data)[0]
    if alive:
        put(data, at + life.VV1_FAMILY, life.GOLDEN_FAMILY)
    from vv_last_names import _cstr
    return _cstr(data, at, 0x18)


class GoldenChild(unittest.TestCase):
    def lines(self, data: bytes) -> list[gm.Fact]:
        return group(page(self, 1, data), gm.GOLDEN_CHILD)

    def test_the_vague_special_action_is_gone(self) -> None:
        facts = page(self, 1, fixture(1))
        text = gm.render(facts)
        self.assertNotIn("special action", text)
        # Real-life wording (the 2026-10-25 audit: every time says real-life or in-game).
        self.assertIn("The Golden Child's cave timer: 36 real-life hours after his birth, at any speed; see Golden "
                      "Child.", text)
        self.assertIn("The 36-hour action is the Cave Opening.", text)

    def test_the_chances_follow_the_rolls(self) -> None:
        # 0x448266 (34 of 100), 0x4479BD (84), 0x4479F3 (21 / 79), 0x44692E (26 / 74), 0x446C48 (7 cases).
        self.assertAlmostEqual(vv1.P_TIMER, 0.225624)
        self.assertAlmostEqual(vv1.P_SHOW, 0.34 * 0.84 * 0.21 * 0.26)
        self.assertAlmostEqual(vv1.P_ACT, 0.34 * 0.84 * 0.21 * 0.74 / 7)
        rules = "\n".join(line for line, _ok in vv1.GOLDEN_CHILD_LINES)
        for words in ("22.6% chance (34% x 84% x 79%)", "1.6% a short show", "0.63% each of"):
            self.assertIn(words, rules)

    def test_every_time_says_real_or_game_time(self) -> None:
        rules = "\n".join(line for line, _ok in vv1.GOLDEN_CHILD_LINES)
        self.assertIn("36 real hours after his birth", rules)
        self.assertIn("36 hours on Slow, Normal and Fast alike (10.8, 18 or 36 game years", rules)
        self.assertIn("12 hours on Fast or Normal and 10 hours on Slow", rules)

    def test_only_the_unproven_lines_are_unconfirmed(self) -> None:
        # The Start Over line was the last unproven one; the 2026-10-25 audit read it in the exe (the new-village
        # set-up 0x41C38A..0x41C39E clears every puzzle flag, his 0xA008 included), so none is left.
        unconfirmed = [line for line, ok in vv1.GOLDEN_CHILD_LINES if ok not in gm.TRUSTED]
        self.assertEqual(unconfirmed, [])
        new_village = next(ok for line, ok in vv1.GOLDEN_CHILD_LINES if line.startswith("A new village (Start Over)"))
        self.assertEqual(new_village, gm.CODE)
        leave = next(line for line, ok in vv1.GOLDEN_CHILD_LINES if line.startswith("How he can leave:"))
        self.assertIn("In the original game island events can pick him", leave)
        self.assertNotIn("being added", leave)

    def test_no_golden_child_yet(self) -> None:
        data = fixture(1)
        self.assertEqual(data[vv1.GC_FLAG], 0)
        first = self.lines(data)[0]
        self.assertTrue(first.text.startswith("This village has no Golden Child yet. First it needs The Idol done"))
        self.assertEqual(first.verified, gm.SAVE)

    def test_the_timer_counts_down_in_real_time(self) -> None:
        data = fixture(1)
        hour = math.ceil((NOW - created(data)) / 3600) - 30          # 30 hours ago: 6 to go
        name = with_golden_child(data, hour)
        facts = self.lines(data)
        self.assertTrue(facts[0].text.startswith(f"{name} is this village's Golden Child, born in hour {hour:,}"))
        timer = next(f for f in facts if f.due is not None)
        self.assertEqual(timer.due, created(data) + (hour + 36) * 3600)
        self.assertEqual(timer.due_kind, "due")
        self.assertIn("The cave is still shut. His 36 hours are up at", timer.text)
        self.assertIn(f"{gm.when(timer.due)} (in 6 h", gm.render(facts, NOW))

    def test_the_timer_runs_while_the_save_is_paused(self) -> None:
        data = fixture(1)
        speed = struct.unpack_from("<i", data, vv1.SPEED)[0]
        put(data, vv1.SPEED, gm.speed_base(speed) + gm.PAUSED)
        hour = math.ceil((NOW - created(data)) / 3600) - 1
        with_golden_child(data, hour)
        timer = next(f for f in self.lines(data) if f.due is not None)
        self.assertEqual(timer.due, created(data) + (hour + 36) * 3600)

    def test_past_the_36_hours(self) -> None:
        data = fixture(1)
        hour = math.ceil((NOW - created(data)) / 3600) - 40
        with_golden_child(data, hour)
        facts = self.lines(data)
        self.assertFalse(any(f.due is not None for f in facts))
        self.assertTrue(any("his 36 hours were up at" in f.text and "22.6% chance he opens it" in f.text
                            for f in facts))

    def test_the_cave_already_open(self) -> None:
        data = fixture(1)
        with_golden_child(data, 274, cave_open=True)
        self.assertIn("The cave was opened in hour 275 of the village: his 36-hour timer is spent.",
                      [f.text for f in self.lines(data)])

    def test_born_but_gone(self) -> None:
        data = fixture(1)
        with_golden_child(data, 10, alive=False)
        texts = [f.text for f in self.lines(data)]
        self.assertTrue(any("no Golden Child lives in it now; the game never makes another" in t for t in texts))
        self.assertIn("The cave is still shut, and with no Golden Child it can never open.", texts)

    def test_the_general_page_keeps_the_rules_only(self) -> None:
        facts = [f for f in gm.general(1) if f.group == gm.GOLDEN_CHILD]
        self.assertEqual([f.text for f in facts], [line for line, _ok in vv1.GOLDEN_CHILD_LINES])

    def test_only_a_new_home_has_the_subsection(self) -> None:
        for game in range(2, 6):
            with self.subTest(game=game):
                self.assertEqual(group(page(self, game, fixture(game)), gm.GOLDEN_CHILD), [])


if __name__ == "__main__":
    unittest.main()
