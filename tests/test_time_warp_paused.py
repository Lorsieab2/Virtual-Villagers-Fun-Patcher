"""Time Warp must advance three villager years at EVERY speed, paused included.

All five games used to refuse Time Warp outright while the game was paused,
showing "Time Warp is unavailable while the game is paused."  None of them
refuses now.

No game scales its advance any more, so no game can be thrown off by the
paused sentinel either.

The two families used to scale in OPPOSITE directions -- VV1-VV4 multiplied by
the speed code, VV5 divided by it -- so at most one could ever have been right,
and neither delivered a constant result. Play settled it: on v1.34.23 VV1 at
NORMAL speed subtracted 21600 and advanced exactly three villager years, while
HALF speed subtracted 10800 and advanced two. The years track the amount alone.

Each game now subtracts one constant -- 21600 in VV1-VV4, 129600 in VV5, whose
clock runs on a different scale -- so the advance is identical at half, normal,
double and paused. Removing VV5's divide also removes the case where the paused
sentinel 999 gave 129600/999 = 129 seconds, a no-op the player still paid for.

The speed field each game used to read is still named below, because these
tests assert it is NOT read.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PAUSE_SENTINEL = "999"

# The amounts measured in play to advance exactly three villager years.
VV1_FAMILY_ADVANCE = 21600
VV5_ADVANCE = 129600

# Every game, with the speed field exactly as it appears in its generator.
ALL_GAMES = {
    "vv1": ("build_vv1_origins_feature.py", "[edi + 0xA318]"),
    "vv2": ("build_vv2_origins_feature.py", "[edi + 0x2EB08]"),
    "vv3": ("build_vv3_origins_feature.py", "[edi + ebp + 0x12F20]"),
    "vv4": ("build_vv4_origins_feature.py", "[eax + 0x17110]"),
    # VV5's SHIPPING Time Warp is the Task9 page, not the Origins base: the
    # loader replaces the VV5 base record with data/vv5_task9_native_actions.json.
    # Testing only the base generator passed while public VV5 modes still showed
    # the paused refusal, so the production path is the one covered here.
    "vv5": ("build_vv5_task9_native_actions.py", "[edi+0x17D7C]"),
    # The inactive base generator must not regress either.
    "vv5_base": ("build_vv5_origins_feature.py", "[edi + 0x17D7C]"),
}

# The games whose engine divides the injected shift by speed.
MULTIPLY_GAMES = ("vv1", "vv2", "vv3", "vv4")
DIVIDE_GAMES = ("vv5", "vv5_base")


def _source(name: str) -> str:
    return (ROOT / "scripts" / name).read_text(encoding="utf-8")


def _time_warp_branch(text: str) -> str:
    """The Time Warp routine only.

    A generator mentions its speed field in unrelated places -- the pause
    guard, the menu row state -- so checking the whole file would fail for
    reasons that have nothing to do with Time Warp.
    """
    for label in ("do_time_warp:", "time_warp:", "def build_time_warp("):
        index = text.find(label)
        if index < 0:
            continue
        window = text[index : index + 4000]
        for terminator in ("jmp success", "jmp show_status", "jmp status",
                           "show_message"):
            cut = window.find(terminator)
            if cut > 0:
                return _strip_comments(window[: cut + len(terminator)])
        return _strip_comments(window)
    return ""


def _strip_comments(block: str) -> str:
    """Drop comment lines, so prose explaining a removed value cannot fail a
    check that the value is gone from the instructions."""
    return chr(10).join(
        line for line in block.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


class TimeWarpPausedTests(unittest.TestCase):
    def test_no_game_refuses_while_paused(self) -> None:
        for game, (generator, field) in ALL_GAMES.items():
            with self.subTest(game=game):
                refusal = re.compile(
                    r"cmp\s+dword ptr\s+" + re.escape(field) + r",\s*" + PAUSE_SENTINEL
                )
                self.assertIsNone(
                    refusal.search(_source(generator)),
                    f"{game} still refuses Time Warp while paused; every speed "
                    f"option must advance three villager years",
                )

    def test_no_game_reads_its_speed_field_for_time_warp(self) -> None:
        """Nothing to normalise once nothing is read.

        Every game used to normalise anything that was not 3 or 10 to 6 so the
        paused sentinel 999 landed on the normal-speed delta. With a single
        constant there is no speed-dependent path left to get wrong.
        """
        for game, (generator, field) in ALL_GAMES.items():
            with self.subTest(game=game):
                text = _source(generator)
                warp = _time_warp_branch(text)
                # The field may still be READ as a liveness guard -- VV5's
                # Task9 page uses it to reject a bad manager pointer before
                # charging. What must be gone is any BRANCH on a speed value.
                for speed in ("3", "6", "10", PAUSE_SENTINEL):
                    for register in ("eax", "ecx", "edx", "ebx"):
                        self.assertNotIn(
                            "cmp " + register + ", " + speed + chr(10),
                            warp,
                            f"{game} still branches on speed code {speed}",
                        )

    def test_no_game_scales_its_advance(self) -> None:
        """The multiply VV1-VV4 used and the divide VV5 used are both gone."""
        for game, (generator, _field) in ALL_GAMES.items():
            with self.subTest(game=game):
                warp = _time_warp_branch(_source(generator))
                self.assertTrue(warp, f"{game} Time Warp branch not found")
                for forbidden in ("imul eax, eax, 3600", "idiv ecx", "div ecx"):
                    self.assertNotIn(
                        forbidden, warp,
                        f"{game} still scales the Time Warp advance ({forbidden})",
                    )

    def test_every_game_subtracts_its_measured_three_year_amount(self) -> None:
        for game, (generator, _field) in ALL_GAMES.items():
            with self.subTest(game=game):
                warp = _time_warp_branch(_source(generator))
                amount = VV5_ADVANCE if game.startswith("vv5") else VV1_FAMILY_ADVANCE
                self.assertIn(
                    str(amount), warp,
                    f"{game} no longer carries its three-year amount {amount}",
                )

    def test_vv5_keeps_its_own_amount(self) -> None:
        """VV5's clock runs on a different scale; unifying the two is a bug."""
        self.assertNotEqual(VV5_ADVANCE, VV1_FAMILY_ADVANCE)
        for game in ("vv5", "vv5_base"):
            with self.subTest(game=game):
                self.assertIn(
                    str(VV5_ADVANCE), _time_warp_branch(_source(ALL_GAMES[game][0])),
                    f"{game} must keep VV5's own measured amount",
                )

    def test_no_game_still_emits_the_paused_refusal(self) -> None:
        needle = "mov eax, 0x{s['paused']"
        for game, (generator, _field) in ALL_GAMES.items():
            with self.subTest(game=game):
                self.assertNotIn(
                    needle, _source(generator),
                    f"{game} still shows the paused refusal message",
                )


if __name__ == "__main__":
    unittest.main()
