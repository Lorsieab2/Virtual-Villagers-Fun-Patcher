"""Time Warp is calibrated from PLAY, and paused refuses without charging.

This file replaces tests/test_time_warp_paused.py and
tests/test_time_warp_speed_independent.py, both of which asserted models of the
engine that playtesting disproved. Three different theories have now been tried
-- "scale by the speed", "one flat amount everywhere", and "VV1-VV4 divide
while VV5 multiplies" -- and each was wrong for at least one game. What follows
is the owner's measurements and the arithmetic that turns them into deltas,
with no engine model in between.

Measured on v1.34.29, which was already running a per-speed table:

    game   slow      normal     fast        paused
    VV1    1 @32400  3 @21600   11 @21600   0
    VV2    1 @32400  3 @21600    9 @10800   0
    VV3    3 @16200  3 @21600  4-5 @36000   0
    VV4    -- its Tech screen crashed before it could be measured --
    VV5    1 @32400  5 @32400    8 @32400   0  (all three ran the same amount)

The goal is no longer three years at every speed. That target needed the delta
to cancel the engine's own scaling, and three separate theories of how to do
that were each wrong for at least one game. The target is now 3 at slow, 6 at
normal and 12 at fast -- a doubling per step, which is roughly what the engine
already does -- so each delta only has to be scaled by target / observed.

Assuming only that the advance is LINEAR in the delta at a fixed speed. That
one assumption is the thing to re-check if a re-measure disagrees.

VV5's three speeds all ran the same 32400 and still produced 1 / 5 / 8, so its
spread comes from the engine rather than from the delta. It still divides
(194400 / speed) rather than branching, which is why it ran one amount at every
setting; retuning it to the new targets needs its speed field confirmed first,
since the division cannot distinguish speeds the field does not distinguish.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# game -> (generator, slow, normal, fast) for the four table-driven games
TABLE_GAMES = {
    "vv1": ("scripts/build_vv1_origins_feature.py", 97200, 43200, 23564),
    "vv2": ("scripts/build_vv2_origins_feature.py", 97200, 43200, 14400),
    "vv3": ("scripts/build_vv3_origins_feature.py", 16200, 43200, 96000),
    # VV4 still carries its v1.34.29 table: its Tech screen crashed before it
    # could be measured, so there is nothing yet to scale from.
    "vv4": ("scripts/build_vv4_origins_feature.py", 32400, 21600, 10800),
}

# What v1.34.29 actually ran, and the years each speed produced in play.
V1_34_29 = {
    "vv1": ((32400, 21600, 21600), (1, 3, 11)),
    "vv2": ((32400, 21600, 10800), (1, 3, 9)),
    "vv3": ((16200, 21600, 36000), (3, 3, 4.5)),   # fast reported as 4-5
}
# The target is no longer three years everywhere. The owner asked for 3 at
# slow, 6 at normal and 12 at fast, which goes WITH the engine's own scaling
# rather than trying to cancel it.
TARGET_YEARS = (3, 6, 12)
# VV5 divides instead of branching; 32400 * 6 = 194400.
VV5_GENERATOR = "scripts/build_vv5_origins_feature.py"
VV5_CONSTANT = 194400

ALL_GENERATORS = {gid: gen for gid, (gen, *_rest) in TABLE_GAMES.items()}
ALL_GENERATORS["vv5"] = VV5_GENERATOR

PAUSE_SENTINEL = "0x3E7"


def source(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def time_warp_branch(text: str) -> str:
    """The assembly from the Time Warp label to the next label."""
    match = re.search(r"^\s*(do_)?time_warp:\s*$", text, re.M)
    if not match:
        return ""
    rest = text[match.end():]
    # The branch continues through its own tw_* helper labels (tw_slow,
    # tw_fast, tw_apply, tw_divide) and ends at the next unrelated label.
    for candidate in re.finditer(r"^\s{8}([a-z_0-9]+):\s*$", rest, re.M):
        if not candidate.group(1).startswith("tw_"):
            return rest[: candidate.start()]
    return rest


class PausedRefusesTests(unittest.TestCase):
    """Paused advances 0 years everywhere, so it must not cost anything."""

    def test_every_game_checks_the_paused_sentinel(self) -> None:
        for gid, generator in ALL_GENERATORS.items():
            with self.subTest(game=gid):
                self.assertIn(
                    PAUSE_SENTINEL, source(generator),
                    f"{gid} no longer tests for the paused sentinel 999",
                )

    def test_the_refusal_comes_before_the_deduction(self) -> None:
        """The whole point: checking after the charge still costs the player.

        VV1 charged 50,000 tech points for an advance of zero years, which is
        the reported bug. The guard is worthless unless it precedes the
        instruction that deducts.
        """
        for gid, generator in ALL_GENERATORS.items():
            with self.subTest(game=gid):
                text = source(generator)
                refusal = text.find("tw_charge_ok")
                self.assertNotEqual(
                    refusal, -1, f"{gid} has no pre-charge Time Warp guard"
                )
                # The deduction that the guard jumps over.
                deduction = re.search(
                    r"^\s*(sub dword ptr \[[^\]]+\], eax|neg eax)\s*$",
                    text[refusal:], re.M,
                )
                self.assertIsNotNone(
                    deduction, f"{gid} guard is not followed by the deduction"
                )

    def test_no_game_advances_the_clock_while_paused(self) -> None:
        """A paused purchase must reach a message, not the clock write."""
        for gid, generator in ALL_GENERATORS.items():
            with self.subTest(game=gid):
                text = source(generator)
                # Anchor on the LABEL, not the first mention: the jump to it
                # comes before the sentinel test, so searching back from the
                # jump would look at the wrong side of the guard.
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


class MeasuredDeltaTests(unittest.TestCase):
    def test_each_table_game_uses_its_measured_deltas(self) -> None:
        for gid, (generator, slow, normal, fast) in TABLE_GAMES.items():
            with self.subTest(game=gid):
                warp = time_warp_branch(source(generator))
                self.assertTrue(warp, f"{gid} Time Warp branch not found")
                for label, value in (("slow", slow), ("normal", normal), ("fast", fast)):
                    self.assertIn(
                        f"mov eax, {value}", warp,
                        f"{gid} is missing its measured {label} delta {value}",
                    )

    def test_each_table_game_branches_on_the_speed_codes(self) -> None:
        """3 / 6 / 10, read from what VV1 and VV3 actually store."""
        for gid, (generator, *_rest) in TABLE_GAMES.items():
            with self.subTest(game=gid):
                warp = time_warp_branch(source(generator))
                self.assertIn("cmp eax, 3", warp)
                self.assertIn("cmp eax, 10", warp)

    def test_no_table_game_kept_the_old_flat_amount_alone(self) -> None:
        """A single unconditional 21600 is the shape that measured wrong."""
        for gid, (generator, *_rest) in TABLE_GAMES.items():
            with self.subTest(game=gid):
                warp = time_warp_branch(source(generator))
                self.assertNotRegex(
                    warp, r"sub dword ptr \[0x[0-9A-Fa-f]+\], 21600",
                    f"{gid} still subtracts a flat 21600",
                )

    def test_vv5_divides_so_it_needs_no_speed_codes(self) -> None:
        warp = time_warp_branch(source(VV5_GENERATOR))
        self.assertTrue(warp, "VV5 Time Warp branch not found")
        self.assertIn(f"mov eax, {VV5_CONSTANT}", warp)
        self.assertIn("div ecx", warp)
        self.assertNotIn("mov eax, 129600", warp)

    def test_vv5_guards_its_divisor(self) -> None:
        """A zero speed would fault; the branch must fall back to normal."""
        warp = time_warp_branch(source(VV5_GENERATOR))
        self.assertIn("test ecx, ecx", warp)
        self.assertIn("mov ecx, 6", warp)

    def test_the_vv5_constant_is_the_normal_speed_measurement(self) -> None:
        """129600 gave 12 years, so 3 years is 32400, and 32400 * 6 = 194400."""
        self.assertEqual(VV5_CONSTANT, 32400 * 6)


class MeasurementProvenanceTests(unittest.TestCase):
    """The numbers must stay traceable to the measurements that produced them."""

    def test_each_generator_records_that_it_was_measured(self) -> None:
        for gid, generator in ALL_GENERATORS.items():
            with self.subTest(game=gid):
                warp = time_warp_branch(source(generator))
                self.assertRegex(
                    warp.lower(), r"measured",
                    f"{gid} Time Warp no longer says where its numbers came from",
                )

    def test_the_deltas_are_the_measurements_scaled_to_the_targets(self) -> None:
        """Re-derives every table number from what v1.34.29 actually did.

        Each game's own delta is scaled per speed, not one shared constant:
        the three games were running different amounts, so scaling from a
        single number would only be right for whichever game happened to
        match it.
        """
        for gid, (ran, observed) in V1_34_29.items():
            _generator, *current = TABLE_GAMES[gid]
            with self.subTest(game=gid):
                expected = [
                    round(delta * target / years)
                    for delta, years, target in zip(ran, observed, TARGET_YEARS)
                ]
                self.assertEqual(current, expected)

    def test_every_target_is_a_doubling_of_the_one_below(self) -> None:
        """3 / 6 / 12 -- the shape the engine already produces.

        Earlier attempts tried to make one number of years hold across every
        speed and had to fight the clock to do it. Each of the three theories
        that produced was wrong for at least one game.
        """
        slow, normal, fast = TARGET_YEARS
        self.assertEqual(normal, slow * 2)
        self.assertEqual(fast, normal * 2)

    def test_vv4_is_still_awaiting_its_measurement(self) -> None:
        """Recorded rather than silently left behind.

        VV4's Tech screen crashed in v1.34.29 (a cave declared at
        IMAGE_BASE + file offset in a section that is not identity-mapped), so
        it could not be measured. Its table is unchanged until it is.
        """
        self.assertNotIn("vv4", V1_34_29)
        self.assertEqual(TABLE_GAMES["vv4"][1:], (32400, 21600, 10800))


if __name__ == "__main__":
    unittest.main()
