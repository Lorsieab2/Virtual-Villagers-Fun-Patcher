"""Time Warp must advance three villager years at EVERY speed, in all five games.

This is calibrated from play, not from a model of the engine.

On v1.34.23, VV1 at NORMAL speed subtracted 6 * 3600 = 21600 from the elapsed
clock and the village advanced exactly THREE years -- the wanted result. At
HALF speed it subtracted 3 * 3600 = 10800 and advanced only TWO. So the years
added track the amount subtracted, and 21600 is the measured three-year amount.

Scaling that amount by the running speed code is what made the result vary in
the first place. Every game now subtracts a single constant, so the advance
cannot depend on the speed setting -- which is the requirement.

VV5 keeps its own number. Its clock runs on a different scale: the shipped
129600/speed form subtracted 43200 at half speed and advanced ONE year, so
three years there is 129600.

The two families also scaled in OPPOSITE directions -- VV1-VV4 multiplied by
the speed code, VV5 divided by it -- so at most one could ever have been right.

What is pinned here is the SHAPE as much as the number: the Time Warp branch
must not read a speed field, must not multiply or divide by one, and must
subtract a single constant.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# The amounts measured in play to advance exactly three villager years.
VV1_FAMILY_ADVANCE = 21600
VV5_ADVANCE = 129600

# The three speed codes every game assigns, plus the paused sentinel. None of
# them may appear in a Time Warp branch any more.
SPEED_CODES = (3, 6, 10)
PAUSED_SENTINEL = 999

# The per-speed amounts the old scaled forms produced, which must be gone.
STALE_AMOUNTS = ("10800", "36000", "43200", "3600", "129600 ")

GAMES = {
    "vv1": ("scripts/build_vv1_origins_feature.py", "do_time_warp:", "0x4860F0", VV1_FAMILY_ADVANCE),
    "vv2": ("scripts/build_vv2_origins_feature.py", "do_time_warp:", "0x4950F0", VV1_FAMILY_ADVANCE),
    "vv3": ("scripts/build_vv3_origins_feature.py", "do_time_warp:", "0x4A4210", VV1_FAMILY_ADVANCE),
    "vv4": ("scripts/build_vv4_origins_feature.py", "do_time_warp:", "0x4B8230", VV1_FAMILY_ADVANCE),
    "vv5": ("scripts/build_vv5_origins_feature.py", "time_warp:", "0x4C6250", VV5_ADVANCE),
}


def branch_source(path: str, label: str) -> str:
    """The Time Warp branch only: from its label to the next label at the same
    indentation, so a neighbouring branch's arithmetic cannot leak in."""
    text = (ROOT / path).read_text(encoding="utf-8")
    start = text.index("        " + label)
    rest = text[start + len(label) + 8 :]
    match = re.search(r"^        [a-z_]+:", rest, re.M)
    return rest[: match.start()] if match else rest


def instructions(path: str, label: str) -> str:
    """The branch with comment lines stripped, so prose cannot satisfy a check."""
    return "\n".join(
        line for line in branch_source(path, label).splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


class TimeWarpSpeedIndependenceTests(unittest.TestCase):
    def test_every_game_subtracts_its_measured_three_year_amount(self) -> None:
        for game, (path, label, anchor, advance) in GAMES.items():
            with self.subTest(game=game):
                self.assertIn(
                    f"sub dword ptr [{anchor}], {advance}",
                    instructions(path, label),
                    f"{game} no longer subtracts its three-year amount",
                )

    def test_no_game_reads_a_speed_code_in_the_time_warp_branch(self) -> None:
        """The whole point: the advance cannot vary with the speed setting."""
        for game, (path, label, _anchor, _advance) in GAMES.items():
            with self.subTest(game=game):
                code = instructions(path, label)
                for speed in SPEED_CODES + (PAUSED_SENTINEL,):
                    for register in ("eax", "ecx", "edx", "ebx"):
                        self.assertNotIn(
                            f"cmp {register}, {speed}", code,
                            f"{game} still branches on speed code {speed}",
                        )

    def test_no_game_scales_the_advance(self) -> None:
        """Neither the multiply VV1-VV4 used nor the divide VV5 used."""
        for game, (path, label, _anchor, _advance) in GAMES.items():
            with self.subTest(game=game):
                code = instructions(path, label)
                for forbidden in ("imul", "idiv", "cdq"):
                    self.assertNotIn(
                        forbidden, code,
                        f"{game} still scales the Time Warp advance ({forbidden})",
                    )

    def test_the_old_per_speed_amounts_are_gone(self) -> None:
        """The exact values the scaled forms produced at half and double speed."""
        for game, (path, label, _anchor, advance) in GAMES.items():
            with self.subTest(game=game):
                code = instructions(path, label)
                for stale in STALE_AMOUNTS:
                    if str(advance) in stale:
                        continue
                    self.assertNotIn(
                        stale.strip(), code,
                        f"{game} still carries the speed-scaled amount {stale.strip()}",
                    )

    def test_the_vv1_family_shares_one_amount_and_vv5_does_not(self) -> None:
        """VV5's clock runs on a different scale, so it must not be unified."""
        family = {game for game, (_p, _l, _a, adv) in GAMES.items()
                  if adv == VV1_FAMILY_ADVANCE}
        self.assertEqual(family, {"vv1", "vv2", "vv3", "vv4"})
        self.assertNotEqual(VV5_ADVANCE, VV1_FAMILY_ADVANCE)


if __name__ == "__main__":
    unittest.main()
