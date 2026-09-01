"""VV3's Details-portrait mask registration is one reviewable number per axis.

VV3 previously buried its horizontal correction in a bare `args[1] - 8` and had
no vertical nudge at all -- the lift was only the scale-aware multiplier.  That
made a retune a code edit rather than a value change, and left nothing for a
test to pin.

Both axes are now explicit macros, matching how VV1 and VV2 express the same
thing, so all three games can be retuned and reviewed the same way.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT / "native" / "vv3_full_mastery_candidate" / "vv3_full_mastery_candidate.c"
)

# Screen X grows rightward and screen Y grows downward, so both being negative
# seats the mask further left and higher on the portrait.
# Y moved from -5 to -1 -- a reviewed 4 px downward move on the portrait only.
DETAILS_MASK_X_NUDGE_PX = -11
DETAILS_MASK_Y_NUDGE_PX = -1


class VV3DetailsMaskNudgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SOURCE.read_text(encoding="utf-8")

    def _macro(self, name: str) -> int:
        match = re.search(
            r"^#define\s+" + re.escape(name) + r"\s+\((-?\d+)\)",
            self.source,
            re.M,
        )
        self.assertIsNotNone(match, f"{name} is not defined as a plain integer")
        return int(match.group(1))

    def test_both_axes_are_declared_macros(self) -> None:
        self.assertEqual(
            self._macro("VV3_DETAILS_MASK_X_NUDGE_PX"), DETAILS_MASK_X_NUDGE_PX
        )
        self.assertEqual(
            self._macro("VV3_DETAILS_MASK_Y_NUDGE_PX"), DETAILS_MASK_Y_NUDGE_PX
        )

    def test_the_draw_uses_the_macros_rather_than_literals(self) -> None:
        self.assertIn("x       = args[1] + VV3_DETAILS_MASK_X_NUDGE_PX;", self.source)
        self.assertIn("+ VV3_DETAILS_MASK_Y_NUDGE_PX;", self.source)
        # The old hardcoded correction must be gone, or a retune would silently
        # apply on top of it.
        self.assertNotIn("x       = args[1] - 8;", self.source)

    def test_the_scale_aware_lift_is_preserved(self) -> None:
        """The vertical nudge is added ON TOP of the lift, not instead of it.

        Replacing the lift with a flat offset would break the child/adult
        registration, which tracks the live portrait scale.
        """
        self.assertIn(
            "args[2] - ((scaledY * VV3_MASK_LIFT_MUL) >> 7)", self.source
        )
        self.assertIn("#define VV3_MASK_LIFT_MUL 18", self.source)

    def test_the_mask_draw_still_writes_no_villager_state(self) -> None:
        """The overlay stays cosmetic: it may read a record but never write one."""
        start = self.source.index("void __stdcall VV3DrawMaskOnHead")
        body = self.source[
            start : self.source.index(chr(10) + "}" + chr(10), start)
        ]
        self.assertNotIn("VV3_SetMaskForRecord", body)
        for forbidden in ("*(int *)(record", "*(char *)(record", "*(unsigned"):
            with self.subTest(pattern=forbidden):
                self.assertNotIn(forbidden + " ", body)

    def test_the_details_nudges_are_independent_of_the_village_view(self) -> None:
        """The two screens draw through different engine functions.

        Details goes through 0x004093A0 with an integer scaled-Y; the village
        goes through 0x0042E5E0 with a float scale.  Sharing one macro between
        them would make every retune of one screen silently move the other, so
        the village pair must exist separately and the Details draw must not
        reference it.
        """
        self.assertIn("#define VV3_WORLD_MASK_X_NUDGE_PX", self.source)
        self.assertIn("#define VV3_WORLD_MASK_Y_NUDGE_PX", self.source)
        start = self.source.index("void __stdcall VV3DrawMaskOnHead")
        body = self.source[
            start : self.source.index(chr(10) + "}" + chr(10), start)
        ]
        self.assertNotIn("VV3_WORLD_MASK_", body)



if __name__ == "__main__":
    unittest.main()
