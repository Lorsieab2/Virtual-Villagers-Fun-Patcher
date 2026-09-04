"""VV3's village-view mask sits on the face, and its offset tracks body size.

Two things are pinned here.

First, the offset itself.  The masks used to draw low and to the right of the
villagers' faces, so the village draw now applies a reviewed registration of
10 px left and 33 px up, with a further 4 px left on the two right-facing
frames, whose art sits deeper into its cell.

Second -- and this is the part a plain constant would get wrong -- that offset
is multiplied by the villager's live draw scale.  Children are drawn smaller
than adults, so a flat 33 px lift would overshoot a toddler's head while
sitting correctly on an adult -- at the newborn scale of 0.80 the lift is
26 px and the sideways move 8 px.

The scale comes from the sixth village head-draw argument, and it is an
IEEE-754 *float*, not an integer: 0x0042E5E0 loads the two coordinates with
`fild` (integer to float) but consumes the sixth argument with a bare
`fmul [esp+arg5]`.  The stock caller fixes its range exactly -- at 0x00460913
the renderer compares the villager's age at +0xDC4 against 0x118 and either
stores 0x3F800000 (1.0f) for an adult or computes (age/14 + 80) * 0.01 for a
child, which spans 0.80 at birth to 1.00 at adulthood.

Reading that float as an integer is the failure this file exists to catch:
0x3F800000 read as an int is 1,065,353,216, and multiplying a nudge by it
would throw the mask out of the universe.
"""
from __future__ import annotations

import re
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT / "native" / "vv3_full_mastery_candidate" / "vv3_full_mastery_candidate.c"
)

WORLD_MASK_X_NUDGE_PX = -10
WORLD_MASK_Y_NUDGE_PX = -33

# The stock child-scale curve at 0x0046091E..0x00460934.
CHILD_SLOPE = struct.unpack("<f", struct.pack("<I", 0x3D924925))[0]   # 1/14
CHILD_BASE = 80.0
CHILD_UNIT = struct.unpack("<f", struct.pack("<I", 0x3C23D70A))[0]    # 0.01
ADULT_AGE = 0x118


def stock_scale(age: int) -> float:
    """Reproduce the engine's own villager draw scale for a given age."""
    if age >= ADULT_AGE:
        return 1.0
    return (age * CHILD_SLOPE + CHILD_BASE) * CHILD_UNIT


def scaled_nudge(px: int, scale: float) -> int:
    """Round half away from zero, matching vv3_scaled_nudge."""
    value = px * scale
    return int(value + 0.5) if value >= 0 else int(value - 0.5)


class VV3WorldMaskNudgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SOURCE.read_text(encoding="utf-8")
        # The same signature also appears as a forward declaration near
        # the top of the file; skip past it to the definition.  Built
        # without escapes so no rewrite of this file can corrupt them.
        marker = "void __stdcall VV3WorldMaskDrawAt(void *record, int *args)"
        declaration = cls.source.index(marker + ";")
        start = cls.source.index(marker, declaration + 1)
        end = cls.source.index(chr(10) + "}" + chr(10), start)
        cls.body = cls.source[start:end]

    def _macro(self, name: str) -> int:
        match = re.search(
            r"^#define\s+" + re.escape(name) + r"\s+\((-?\d+)\)", self.source, re.M
        )
        self.assertIsNotNone(match, f"{name} is not defined as a plain integer")
        return int(match.group(1))

    def test_both_axes_are_declared_macros(self) -> None:
        self.assertEqual(self._macro("VV3_WORLD_MASK_X_NUDGE_PX"), WORLD_MASK_X_NUDGE_PX)
        self.assertEqual(self._macro("VV3_WORLD_MASK_Y_NUDGE_PX"), WORLD_MASK_Y_NUDGE_PX)

    def test_the_draw_applies_both_axes_through_the_scale(self) -> None:
        # X carries a per-facing term on top of the shared nudge: the
        # right-facing mask art sits further into its cell than the
        # left-facing art, so one shared X value cannot centre both.
        self.assertIn("mask_args[1] += vv3_scaled_nudge(", self.body)
        self.assertIn(
            "VV3_WORLD_MASK_X_NUDGE_PX + VV3_WORLD_MASK_X_NUDGE_BY_FACING[facing & 7]",
            self.body,
        )
        self.assertIn(
            "mask_args[2] += vv3_scaled_nudge(VV3_WORLD_MASK_Y_NUDGE_PX, scale);",
            self.body,
        )
        self.assertIn("scale = vv3_world_scale(mask_args[5]);", self.body)

    def test_the_per_facing_x_table_covers_all_eight_facings(self) -> None:
        """One entry per facing, and the facing is masked before indexing.

        Indexing this table with the head's raw fifth argument would read past
        its end -- that argument is a composite whose facing is only the low
        three bits, the same trap that once made the mask sample the wrong
        atlas column.
        """
        table = re.search(
            r"VV3_WORLD_MASK_X_NUDGE_BY_FACING\[8\]\s*=\s*\{([^}]*)\}",
            self.source,
        )
        self.assertIsNotNone(table, "the per-facing X table is gone")
        entries = [e.strip() for e in table.group(1).split(",") if e.strip()]
        self.assertEqual(len(entries), 8)
        self.assertIn("[facing & 7]", self.body)

    def test_the_scale_argument_is_reinterpreted_as_a_float(self) -> None:
        """It must be bit-copied, never converted.

        `(float)mask_args[5]` would turn the adult 0x3F800000 into 1.065e9.
        """
        helper = self.source[
            self.source.index("static float vv3_world_scale(") : self.source.index(
                "static int vv3_scaled_nudge("
            )
        ]
        self.assertIn("memcpy(&scale, &raw, sizeof(scale));", helper)
        self.assertNotIn("(float)raw", helper)
        self.assertNotIn("(float)mask_args[5]", self.body)

    def test_a_garbage_scale_degrades_to_the_stock_adult_value(self) -> None:
        """Including NaN, which fails every ordered comparison."""
        helper = self.source[
            self.source.index("static float vv3_world_scale(") : self.source.index(
                "static int vv3_scaled_nudge("
            )
        ]
        self.assertIn("if (!(scale > 0.05f) || !(scale < 8.0f)) {", helper)
        self.assertIn("return 1.0f;", helper)

    def test_an_adult_gets_the_full_reviewed_offset(self) -> None:
        scale = stock_scale(ADULT_AGE)
        self.assertEqual(scale, 1.0)
        self.assertEqual(scaled_nudge(WORLD_MASK_X_NUDGE_PX, scale), -10)
        self.assertEqual(scaled_nudge(WORLD_MASK_Y_NUDGE_PX, scale), -33)

    def test_a_child_gets_a_proportionally_smaller_offset(self) -> None:
        """A newborn is drawn at 0.80, so it moves 80% of the adult offset.

        Derived from the constants rather than written out, so retuning the
        registration does not require hand-editing an expected pixel count
        here -- the property under test is the proportionality, not the
        particular numbers.
        """
        newborn = stock_scale(0)
        self.assertAlmostEqual(newborn, 0.80, places=4)
        self.assertEqual(
            scaled_nudge(WORLD_MASK_X_NUDGE_PX, newborn),
            int(WORLD_MASK_X_NUDGE_PX * 0.80),
        )
        self.assertEqual(
            scaled_nudge(WORLD_MASK_Y_NUDGE_PX, newborn),
            int(WORLD_MASK_Y_NUDGE_PX * 0.80),
        )

    def test_the_offset_grows_monotonically_with_age_up_to_the_adult_value(self) -> None:
        previous = 0
        for age in range(0, ADULT_AGE + 1):
            lift = -scaled_nudge(WORLD_MASK_Y_NUDGE_PX, stock_scale(age))
            self.assertGreaterEqual(lift, previous)
            self.assertLessEqual(lift, -WORLD_MASK_Y_NUDGE_PX)
            previous = lift
        self.assertEqual(previous, -WORLD_MASK_Y_NUDGE_PX)

    def test_the_nudge_never_rounds_a_real_offset_away(self) -> None:
        """Truncation must not swallow a whole pixel of a child's offset.

        The smallest villager is drawn at 0.80, so every offset lands between
        80% of the adult value and the adult value itself. Bounds are derived
        from the constant so this keeps holding after a retune.
        """
        full = abs(WORLD_MASK_X_NUDGE_PX)
        smallest = int(full * 0.80)
        for age in (0, 40, 100, 200, 279, ADULT_AGE):
            with self.subTest(age=age):
                offset = abs(scaled_nudge(WORLD_MASK_X_NUDGE_PX, stock_scale(age)))
                self.assertLessEqual(offset, full)
                self.assertGreaterEqual(offset, smallest)

    def test_the_world_draw_still_writes_no_villager_state(self) -> None:
        """The overlay stays cosmetic: the registration must not change that."""
        self.assertNotIn("VV3_SetMaskForRecord", self.body)
        for forbidden in ("*(int *)((unsigned char *)record + 0xF20) =",):
            self.assertNotIn(forbidden, self.body)

    def test_the_explicit_facing_column_survives_the_retune(self) -> None:
        """Registration must not disturb the column selection it sits beside."""
        self.assertIn("facing = mask_args[4] & 7;", self.body)
        self.assertIn("mask_args[4] = facing;", self.body)


if __name__ == "__main__":
    unittest.main()
