"""Time Warp advances an EXACT number of years, and paused costs nothing.

Five theories of the engine have now been tried and each was wrong: "scale by
the speed", "one flat amount everywhere", "VV1-VV4 divide while VV5
multiplies", a per-speed table calibrated from play, and finally the flat 43200
justified by "a villager year is 4 real hours at slow, 2 at normal, 1 at fast".
That last one shipped in v1.34.30 and measured 2 / 4 / 9 years instead of
3 / 6 / 12.

The mechanism is now read directly out of the stock executables rather than
modelled, and it is IDENTICAL in all five games:

  * The game speed is a DIVISOR, not a multiplier: 10 slow, 6 normal, 3 fast,
    999 while paused (VV1 writes them at 0x004294C4 / 0x0042950A / 0x0042954D).
  * A villager accumulates unconverted real seconds, then converts them with
    ``units += (pending / 60) / speed_code``, at 20 age units per villager
    year (VV1 divides by 20 at 0x0042EB12).
  * So one villager year costs ``20 * 60 * code`` real seconds: 12000 slow,
    7200 normal, 3600 fast -- 2 hours at normal and 1 at fast exactly, but
    3h20m at slow, NOT the 4 hours the flat-43200 model assumed.

  * And, crucially, the pending seconds are CLAMPED before that conversion
    (VV1 0x42EA7C, VV2 0x43B86A, VV3 0x45F51D, VV4 0x466594, VV5 0x46FFCB):
    over 86400 becomes 86400, and otherwise anything over 23800 slow /
    31000 normal / 38200 fast is forced down to 31000.

The clamp is what defeats every flat delta. Hitting 3 / 6 / 12 needs
``years * 20 * 60 * code`` seconds -- 36000 slow, 43200 normal, 43200 fast --
and every one of those is above its own threshold, so all three collapse to
31000 and land 2.55 / 4.3 / 8.6 years. Pushing a LARGER number in makes the
warp SMALLER. No single amount, and no per-speed table, can reach the targets
through the world clock alone.

The fix therefore applies the advance in two halves, in the companion DLL:
the world clock moves by the true delta so every other time-based system sees
a real jump, and each living villager is credited the exact age units directly
while its "last seen" marker moves by the same delta, so its own tick cannot
process -- and clamp -- the same jump a second time.

MIGRATED below names the games converted so far. The rest still ship the flat
delta and are asserted to still have it, so this file always states exactly
which games are fixed rather than quietly passing over the ones that are not.
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

# Games whose Time Warp has moved into the companion DLL. Grows one game per
# pull request; the flat-delta assertions below cover the remainder.
MIGRATED = {"vv1", "vv2"}

# Each game's Time Warp constants are scoped with its own prefix:
# vv2_origins_icons.c #includes vv1_origins_icons.c after pre-defining the
# shared VV_* offsets to VV2's values, so an unprefixed constant in one
# game's Time Warp code would be silently retargeted in the other's build.
COMPANIONS = {
    "vv1": "native/vv1_origins_icons/vv1_origins_icons.c",
    "vv2": "native/vv2_origins_icons/vv2_origins_icons.c",
}

# The engine's own speed divisors, and the years each must buy.
SPEED_CODES = {"slow": 10, "normal": 6, "fast": 3}
TARGET_YEARS = {"slow": 3, "normal": 6, "fast": 12}
UNITS_PER_YEAR = 20
SECONDS_PER_UNIT = 60

# The per-speed clamp thresholds, and the value everything above one is forced
# down to.
CLAMP_THRESHOLDS = {"slow": 23800, "normal": 31000, "fast": 38200}
CLAMPED_TO = 31000

# What v1.34.30 shipped, and what the unmigrated games still carry.
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


def required_delta(speed: str) -> int:
    """The real seconds the target years cost at this speed."""
    return TARGET_YEARS[speed] * UNITS_PER_YEAR * SECONDS_PER_UNIT * SPEED_CODES[speed]


class EngineArithmeticTests(unittest.TestCase):
    """The model, stated independently of any generator."""

    def test_a_year_costs_twenty_units_at_sixty_seconds_per_speed_step(self) -> None:
        expected_seconds_per_year = {"slow": 12000, "normal": 7200, "fast": 3600}
        for speed, code in SPEED_CODES.items():
            with self.subTest(speed=speed):
                self.assertEqual(
                    UNITS_PER_YEAR * SECONDS_PER_UNIT * code,
                    expected_seconds_per_year[speed],
                )

    def test_the_required_delta_round_trips_exactly(self) -> None:
        """No truncation anywhere in the engine's integer conversion."""
        for speed, code in SPEED_CODES.items():
            with self.subTest(speed=speed):
                delta = required_delta(speed)
                units = (delta // SECONDS_PER_UNIT) // code
                self.assertEqual(units // UNITS_PER_YEAR, TARGET_YEARS[speed])
                self.assertEqual(units % UNITS_PER_YEAR, 0)

    def test_no_flat_delta_can_reach_the_targets(self) -> None:
        """Why the world clock alone is not enough -- at any single value.

        Every required delta is above its own clamp threshold, so a world-clock
        advance is cut to 31000 whatever number is pushed in.
        """
        for speed in SPEED_CODES:
            with self.subTest(speed=speed):
                self.assertGreater(required_delta(speed), CLAMP_THRESHOLDS[speed])

    def test_the_flat_delta_that_shipped_lands_short_everywhere(self) -> None:
        """Reproduces the reported 2 / 4 / 9 from the clamp alone."""
        landed = {}
        for speed, code in SPEED_CODES.items():
            self.assertGreater(FLAT_DELTA, CLAMP_THRESHOLDS[speed])
            units = (CLAMPED_TO // SECONDS_PER_UNIT) // code
            landed[speed] = units / UNITS_PER_YEAR
        # 2.55 / 4.3 / 8.6 -- the owner read 2 / 4 / 9 off the screen, the
        # fast case reading 8 or 9 depending on a villager's fractional age.
        self.assertEqual(int(landed["slow"]), 2)
        self.assertEqual(int(landed["normal"]), 4)
        self.assertEqual(int(landed["fast"]), 8)
        for speed in SPEED_CODES:
            self.assertLess(landed[speed], TARGET_YEARS[speed])


class MigratedGamesTests(unittest.TestCase):
    """Games whose Time Warp is owned by the companion DLL."""

    def test_the_flat_advance_is_gone_from_the_executable(self) -> None:
        for gid in sorted(MIGRATED):
            with self.subTest(game=gid):
                text = source(GENERATORS[gid])
                self.assertNotIn(f"mov eax, {FLAT_DELTA}", text)
                self.assertEqual(time_warp_branch(text), "")
                self.assertNotIn("tw_slow:", text)
                self.assertNotIn("tw_fast:", text)

    def test_the_row_is_dispatched_to_the_companion(self) -> None:
        for gid in sorted(MIGRATED):
            with self.subTest(game=gid):
                self.assertIn("TIME_WARP_HELPER_VA", source(GENERATORS[gid]))

    def test_the_companion_knows_the_speed_codes_and_targets(self) -> None:
        for gid in sorted(MIGRATED):
            with self.subTest(game=gid):
                dll = source(COMPANIONS[gid])
                codes = {
                    name.lower(): int(value)
                    for name, value in re.findall(
                        r"#define VV\d_TW_SPEED_(SLOW|NORMAL|FAST)\s+(\d+)", dll
                    )
                }
                self.assertEqual(codes, SPEED_CODES)
                years = {
                    name.lower(): int(value)
                    for name, value in re.findall(
                        r"case VV\d_TW_SPEED_(SLOW|NORMAL|FAST):\s+return (\d+);", dll
                    )
                }
                self.assertEqual(years, TARGET_YEARS)
                self.assertRegex(dll, rf"#define VV\d_TW_UNITS_PER_YEAR\s+{UNITS_PER_YEAR}\b")

    def test_the_companion_applies_both_halves(self) -> None:
        """Ages credited directly, and the tick prevented from double-counting."""
        for gid in sorted(MIGRATED):
            with self.subTest(game=gid):
                dll = source(COMPANIONS[gid])
                self.assertRegex(dll, r"VV\d_TW_TIME_EPOCH_VA")
                self.assertRegex(dll, r"VV\d_TW_LAST_SEEN_OFFSET")
                self.assertIn("+= delta;", dll)
                self.assertIn("+= units;", dll)

    def test_the_companion_refuses_while_paused_without_charging(self) -> None:
        """The refusal must precede the deduction, not follow it."""
        for gid in sorted(MIGRATED):
            with self.subTest(game=gid):
                dll = source(COMPANIONS[gid])
                self.assertRegex(dll, r"#define VV\d_TW_SPEED_PAUSED\s+999")
                self.assertIn("unavailable while the game is paused", dll)
                refusal = dll.find("unavailable while the game is paused")
                charge = dll.find("*tech -= cost;")
                self.assertNotEqual(charge, -1, f"{gid} companion never charges")
                self.assertLess(
                    refusal, charge,
                    f"{gid} refuses only after charging, which is the reported bug",
                )

    def test_cancel_is_distinguishable_from_a_refusal(self) -> None:
        """Cancel reopens the Tech menu; a refusal closes it after its message.

        Before the row moved into the DLL it went through the shared
        confirmation, whose zero result jumps back to menu_loop. A single
        return value for both cancel and refusal would close the whole menu on
        Cancel, which no other row does.
        """
        for gid in sorted(MIGRATED):
            with self.subTest(game=gid):
                dll = source(COMPANIONS[gid])
                self.assertRegex(dll, r"#define VV\d_TW_CANCELLED 0")
                self.assertRegex(dll, r"#define VV\d_TW_APPLIED   1")
                self.assertRegex(dll, r"#define VV\d_TW_REFUSED   2")
                self.assertRegex(dll, r"return VV\d_TW_CANCELLED;")
                exe = source(GENERATORS[gid])
                after = exe[exe.index("call 0x{TIME_WARP_HELPER_VA:X}"):]
                after = after[:400]
                self.assertIn("test eax, eax", after)
                self.assertIn("jz menu_loop", after)

    def test_the_nonempty_preflight_counts_any_occupied_record(self) -> None:
        """A village of records the age credit skips is still a village.

        Its clock, and those records' markers, must still move -- otherwise the
        row reports it could not reach the village and nothing advances.
        """
        for gid in sorted(MIGRATED):
            with self.subTest(game=gid):
                dll = source(COMPANIONS[gid])
                fn = dll[dll.index("_time_warp_apply("):]
                pre = fn[fn.index("Count BEFORE"): fn.index("if (credited == 0) {")]
                self.assertNotIn("eligible", pre)
                self.assertNotIn("golden", pre)

    def test_the_confirmation_names_the_speed_and_the_years(self) -> None:
        for gid in sorted(MIGRATED):
            with self.subTest(game=gid):
                dll = source(COMPANIONS[gid])
                self.assertIn("On %s game speed, this will advance %d villager years.", dll)
                self.assertIn('"Advanced %d years."', dll)


class PendingGamesTests(unittest.TestCase):
    """Games still on the flat delta, named rather than skipped silently."""

    def pending(self) -> list[str]:
        return sorted(set(GENERATORS) - MIGRATED)

    def test_every_pending_game_still_carries_the_flat_delta(self) -> None:
        for gid in self.pending():
            with self.subTest(game=gid):
                warp = time_warp_branch(source(GENERATORS[gid]))
                self.assertTrue(warp, f"{gid} Time Warp branch not found")
                self.assertIn(f"mov eax, {FLAT_DELTA}", warp)

    def test_every_pending_game_still_tests_the_paused_sentinel(self) -> None:
        for gid in self.pending():
            with self.subTest(game=gid):
                self.assertIn(
                    PAUSE_SENTINEL, source(GENERATORS[gid]),
                    f"{gid} no longer tests for the paused sentinel 999",
                )

    def test_the_pending_refusal_comes_before_the_deduction(self) -> None:
        for gid in self.pending():
            with self.subTest(game=gid):
                text = source(GENERATORS[gid])
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
