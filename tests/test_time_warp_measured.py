"""Time Warp advances an EXACT number of years, and paused costs nothing.

This file replaces tests/test_time_warp_paused.py and
tests/test_time_warp_speed_independent.py, and then replaced its own earlier
contents twice more. Four theories of the engine were tried and each was wrong
for at least one game: "scale by the speed", "one flat amount everywhere",
"VV1-VV4 divide while VV5 multiplies", and finally a per-speed table calibrated
by scaling play measurements. The last of those was not wrong so much as
INEXACT -- it scaled by whole years read off a screen, so VV3's "4 to 5 years"
could only ever produce an estimate.

The owner then supplied the game's own time base, which settles it exactly:

    one villager year = 4 real hours at slow
                        2 real hours at normal
                        1 real hour  at fast

The delta is subtracted from a real-time clock, so the years a delta buys are
`delta / (hours * 3600)`:

    slow    43200 / 14400 =  3 years
    normal  43200 /  7200 =  6 years
    fast    43200 /  3600 = 12 years

The requested targets, 3 / 6 / 12, are exactly inverse to the hours-per-year
4 / 2 / 1. So ONE flat amount hits all three precisely, and no per-speed table
is needed at all. That also removes the feature's dependence on reading the
speed field correctly, which every previous table was guessing around.

Paused still reads the speed field, because whether to refuse a paused
purchase is a separate question from how far the clock moves.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

GENERATORS = {
    "vv1": "scripts/build_vv1_origins_feature.py",
    "vv2": "scripts/build_vv2_origins_feature.py",
    "vv3": "scripts/build_vv3_origins_feature.py",
    "vv4": "scripts/build_vv4_origins_feature.py",
    "vv5": "scripts/build_vv5_origins_feature.py",
}

# Real hours per villager year, as stated by the owner.
HOURS_PER_YEAR = {"slow": 4, "normal": 2, "fast": 1}
TARGET_YEARS = {"slow": 3, "normal": 6, "fast": 12}
FLAT_DELTA = 43200

PAUSE_SENTINEL = "0x3E7"


def source(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def time_warp_branch(text: str) -> str:
    """The assembly from the Time Warp label to the next unrelated label."""
    match = re.search(r"^\s*(do_)?time_warp:\s*$", text, re.M)
    if not match:
        return ""
    rest = text[match.end():]
    for candidate in re.finditer(r"^\s{8}([a-z_0-9]+):\s*$", rest, re.M):
        if not candidate.group(1).startswith("tw_"):
            return rest[: candidate.start()]
    return rest


class ExactYearsTests(unittest.TestCase):
    def test_the_flat_delta_is_exact_at_every_speed(self) -> None:
        """The arithmetic, stated independently of any generator."""
        for speed, hours in HOURS_PER_YEAR.items():
            with self.subTest(speed=speed):
                seconds_per_year = hours * 3600
                self.assertEqual(
                    FLAT_DELTA % seconds_per_year, 0,
                    "the delta must divide evenly, or the advance is an estimate",
                )
                self.assertEqual(FLAT_DELTA // seconds_per_year, TARGET_YEARS[speed])

    def test_the_targets_are_inverse_to_the_year_length(self) -> None:
        """Why one flat amount can be exact at three different speeds."""
        for speed, hours in HOURS_PER_YEAR.items():
            with self.subTest(speed=speed):
                self.assertEqual(hours * TARGET_YEARS[speed], 12)

    def test_every_game_subtracts_that_exact_amount(self) -> None:
        for gid, generator in GENERATORS.items():
            with self.subTest(game=gid):
                warp = time_warp_branch(source(generator))
                self.assertTrue(warp, f"{gid} Time Warp branch not found")
                self.assertIn(f"mov eax, {FLAT_DELTA}", warp)

    def test_no_game_still_selects_a_delta_by_speed(self) -> None:
        """A per-speed table is now wrong, not merely redundant.

        Each entry would have to buy a different number of years, which is the
        opposite of what one flat amount achieves.
        """
        for gid, generator in GENERATORS.items():
            with self.subTest(game=gid):
                warp = time_warp_branch(source(generator))
                self.assertNotIn("tw_slow:", warp, f"{gid} still branches per speed")
                self.assertNotIn("tw_fast:", warp, f"{gid} still branches per speed")

    def test_vv5_no_longer_divides_by_its_speed_field(self) -> None:
        """Its three speeds all read the same value, so the division did nothing.

        VV5 measured 1 / 5 / 8 years while every speed ran the same 32400 --
        the engine's own spread showing through a divisor that never varied.
        """
        warp = time_warp_branch(source(GENERATORS["vv5"]))
        self.assertNotIn("div ecx", warp)
        self.assertNotIn("mov eax, 194400", warp)


class PausedRefusesTests(unittest.TestCase):
    """Paused advances 0 years everywhere, so it must not cost anything."""

    def test_every_game_checks_the_paused_sentinel(self) -> None:
        for gid, generator in GENERATORS.items():
            with self.subTest(game=gid):
                self.assertIn(
                    PAUSE_SENTINEL, source(generator),
                    f"{gid} no longer tests for the paused sentinel 999",
                )

    def test_the_refusal_comes_before_the_deduction(self) -> None:
        """Checking after the charge still costs the player.

        VV1 charged 50,000 tech points for an advance of zero years, which is
        the reported bug. The guard is worthless unless it precedes the
        instruction that deducts.
        """
        for gid, generator in GENERATORS.items():
            with self.subTest(game=gid):
                text = source(generator)
                refusal = text.find("tw_charge_ok")
                self.assertNotEqual(
                    refusal, -1, f"{gid} has no pre-charge Time Warp guard"
                )
                deduction = re.search(
                    r"^\s*(sub dword ptr \[[^\]]+\], eax|neg eax)\s*$",
                    text[refusal:], re.M,
                )
                self.assertIsNotNone(
                    deduction, f"{gid} guard is not followed by the deduction"
                )

    def test_no_game_advances_the_clock_while_paused(self) -> None:
        for gid, generator in GENERATORS.items():
            with self.subTest(game=gid):
                text = source(generator)
                guard = text.find("tw_charge_ok:")
                self.assertNotEqual(guard, -1, f"{gid} has no tw_charge_ok label")
                window = text[max(0, guard - 700): guard]
                self.assertIn(
                    PAUSE_SENTINEL, window,
                    f"{gid} guard does not test the speed against 999",
                )
                self.assertRegex(
                    window, r"mov eax, 0x\{s\['(paused|tw_paused)'\]:X\}",
                    f"{gid} guard does not show the paused message",
                )


class LabelHonestyTests(unittest.TestCase):
    def test_no_dialog_promises_a_fixed_number_of_years(self) -> None:
        """The advance depends on the speed, so a fixed caption cannot be true.

        The caption used to read "Advances 3 Villager Years" while the action
        moved six years at normal and twelve at fast -- understating a
        permanent 50,000-point purchase by up to four times.
        """
        for rc in ROOT.glob("native/**/*.rc"):
            with self.subTest(resource=rc.name):
                text = rc.read_text(encoding="utf-8", errors="surrogateescape")
                self.assertNotRegex(
                    text, r"Time Warp[^\"]*Advances \d+ Villager Years",
                    f"{rc.name} still promises a fixed number of years",
                )


if __name__ == "__main__":
    unittest.main()
