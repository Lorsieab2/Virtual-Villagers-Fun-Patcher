"""Time Warp must advance three villager years at EVERY speed, paused included.

All five games used to refuse Time Warp outright while the game was paused,
showing "Time Warp is unavailable while the game is paused."  The requirement is
that every speed option advances exactly three villager years, so the refusal is
gone in VV1-VV4 and the paused sentinel is normalised like any other unexpected
speed code.

Each game reads a speed field that holds 3 (half), 6 (normal), 10 (double), or
the sentinel 999 while paused.  VV1-VV4 all scale as `speed * 3600` after
normalising anything that is not 3 or 10 to 6, so 999 lands on the normal-speed
delta and a paused Time Warp advances the normal-speed three years.

VV5 is deliberately excluded and still refuses.  It scales the other way
(`129600 / speed`) and has no normalisation, so 999 would divide down to a
129-second no-op rather than a three-year advance.  Adding normalisation there
needs extra instructions, and the VV5 payload is size-frozen by an IDA
relocation ledger asserted complete at 66 rows -- a size change invalidates it
and it cannot be regenerated here.  A test below pins that VV5 keeps its refusal
so paused never silently becomes a no-op.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PAUSE_SENTINEL = "999"

# game -> (generator, speed field expression as it appears in the source)
GAMES = {
    "vv1": ("build_vv1_origins_feature.py", "[edi + 0xA318]"),
    "vv2": ("build_vv2_origins_feature.py", "[edi + 0x2EB08]"),
    "vv3": ("build_vv3_origins_feature.py", "[edi + ebp + 0x12F20]"),
    "vv4": ("build_vv4_origins_feature.py", "[eax + 0x17110]"),
}
VV5 = ("build_vv5_origins_feature.py", "[edi + 0x17D7C]")


def _source(name: str) -> str:
    return (ROOT / "scripts" / name).read_text(encoding="utf-8")


class TimeWarpPausedTests(unittest.TestCase):
    def test_vv1_to_vv4_no_longer_refuse_while_paused(self) -> None:
        for game, (generator, field) in GAMES.items():
            with self.subTest(game=game):
                text = _source(generator)
                refusal = re.compile(
                    r"cmp\s+dword ptr\s+" + re.escape(field) + r",\s*" + PAUSE_SENTINEL
                )
                self.assertIsNone(
                    refusal.search(text),
                    f"{game} still refuses Time Warp while paused; every speed "
                    f"option must advance three villager years",
                )

    def test_vv1_to_vv4_normalise_unexpected_speeds_to_normal(self) -> None:
        """The paused sentinel must land on the normal-speed delta.

        VV1 does it by defaulting EAX to the normal delta and only overriding
        for 3 and 10; VV2-VV4 do it by forcing the speed code to 6.  Either
        shape means 999 produces the normal-speed advance.
        """
        for game, (generator, _field) in GAMES.items():
            with self.subTest(game=game):
                text = _source(generator)
                normalises = (
                    "mov eax, 21600" in text          # VV1: normal is the default
                    or "mov eax, 6" in text           # VV2-VV4: force normal
                )
                self.assertTrue(
                    normalises,
                    f"{game} has no normalisation, so the paused sentinel 999 "
                    f"would scale into a nonsense delta",
                )

    def test_vv1_to_vv4_still_scale_by_speed(self) -> None:
        """Three villager years is speed-proportional in VV1-VV4."""
        for game, (generator, _field) in GAMES.items():
            with self.subTest(game=game):
                text = _source(generator)
                self.assertTrue(
                    "imul eax, eax, 3600" in text or "mov eax, 21600" in text,
                    f"{game} no longer scales the clock shift by game speed",
                )

    def test_vv5_still_refuses_while_paused(self) -> None:
        """Deliberate: VV5 divides by the raw speed and has no normalisation.

        Removing its refusal without adding normalisation would turn a paused
        Time Warp into 129600/999 = 129 seconds -- a no-op dressed up as a
        purchase. It keeps refusing until its payload can take the extra
        instructions.
        """
        generator, field = VV5
        text = _source(generator)
        refusal = re.compile(
            r"cmp\s+dword ptr\s+" + re.escape(field) + r",\s*" + PAUSE_SENTINEL
        )
        self.assertIsNotNone(
            refusal.search(text),
            "VV5 dropped its paused refusal without gaining speed "
            "normalisation; paused would become a 129-second no-op",
        )

    def test_the_paused_message_is_still_available_for_vv5(self) -> None:
        self.assertIn(
            "Time Warp is unavailable while the game is paused.",
            _source(VV5[0]),
        )


if __name__ == "__main__":
    unittest.main()
