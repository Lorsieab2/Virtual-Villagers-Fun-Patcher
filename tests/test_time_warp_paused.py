"""Time Warp must advance three villager years at EVERY speed, paused included.

All five games used to refuse Time Warp outright while the game was paused,
showing "Time Warp is unavailable while the game is paused."  None of them
refuses now.

Each game reads a speed field holding 3 (half), 6 (normal), 10 (double), or the
sentinel 999 while paused.  Every game normalises anything that is not 3 or 10
to 6 before scaling, so the paused sentinel lands on the normal-speed delta.

The two families scale in OPPOSITE directions, and that distinction is the
point of this file:

  * VV1-VV4 multiply -- `speed * 3600`.
  * VV5 divides -- `129600 / speed`.

Copying VV1-VV4's multiply into VV5 is not "making it work like VV1-VV4"; it is
the regression shipped in v1.34.18.  Matching the BEHAVIOUR means normalising
the same way and then scaling in each engine's own direction.

VV5 previously had no normalisation at all and divided by the raw field, so the
paused sentinel gave 129600/999 = 129 seconds -- a no-op the player still paid
for, which is why it used to refuse.  Adding the normalisation needed the
payload to grow, which the removed expanded-256 IDA relocation ledger forbade.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PAUSE_SENTINEL = "999"

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

    def test_every_game_normalises_unexpected_speeds_to_normal(self) -> None:
        """The paused sentinel must land on the normal-speed delta.

        VV1 defaults EAX to the normal delta and overrides only for 3 and 10;
        the rest force the speed code to 6.  Either shape maps 999 onto normal.
        """
        for game, (generator, _field) in ALL_GAMES.items():
            with self.subTest(game=game):
                text = _source(generator)
                self.assertTrue(
                    "mov eax, 21600" in text or "mov ecx, 6" in text
                    or "mov eax, 6" in text,
                    f"{game} has no normalisation, so the paused sentinel 999 "
                    f"would scale into a nonsense delta",
                )

    def test_the_multiply_games_still_multiply(self) -> None:
        for game in MULTIPLY_GAMES:
            with self.subTest(game=game):
                text = _source(ALL_GAMES[game][0])
                self.assertTrue(
                    "imul eax, eax, 3600" in text or "mov eax, 21600" in text,
                    f"{game} no longer scales the clock shift by game speed",
                )

    def test_the_divide_games_still_divide(self) -> None:
        """VV5 matches VV1-VV4's behaviour without copying their formula.

        Its engine scales the opposite way.  Writing `speed * 3600` here would
        reintroduce the v1.34.18 regression.
        """
        for game in DIVIDE_GAMES:
            with self.subTest(game=game):
                text = _source(ALL_GAMES[game][0])
                self.assertRegex(
                    text, "div ecx",
                    f"{game} must divide (the Task9 page uses unsigned `div`, "
                    f"the base generator `idiv`)",
                )
                self.assertNotIn(
                    "imul eax, eax, 3600", text,
                    f"{game} must not copy the multiply-family formula; its "
                    f"engine scales the other way and that swap shipped as a "
                    f"regression once already",
                )

    def test_the_two_families_are_disjoint(self) -> None:
        """Guards the split above against quietly collapsing into one rule."""
        self.assertEqual(
            set(MULTIPLY_GAMES) & set(DIVIDE_GAMES), set()
        )
        self.assertEqual(
            set(MULTIPLY_GAMES) | set(DIVIDE_GAMES), set(ALL_GAMES)
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
