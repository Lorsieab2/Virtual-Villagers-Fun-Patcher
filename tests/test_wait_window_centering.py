"""The wait window must centre on its parent, even on a second monitor.

Reported by the Virtual Families 2 patcher while porting this widget across.

The original code computed a parent-relative origin and then clamped both
coordinates with ``max(0, ...)``. On a single monitor that is invisible. On a
multi-monitor desktop it is a real failure: a window on a screen positioned
LEFT OF or ABOVE the primary display has legitimately negative root
coordinates in virtual-desktop space, so the clamp drags the child onto the
primary monitor.

For this particular widget that is the worst available outcome. The wait window
takes a modal grab, so the application stops responding to input while the only
thing explaining why has jumped to a screen the user may not even be looking
at -- which is precisely the "it looks like it crashed" impression the window
was added to prevent.

The fix is to clamp only the screen-centred fallback, where a negative value
really would be off-screen. These tests cover the pure geometry helper, so they
need no display and cannot be skipped on a headless machine.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher_gui import centered_origin  # noqa: E402

SCREEN = (1920, 1080)
SIZE = (400, 200)


class ParentRelativeTests(unittest.TestCase):
    def test_it_centres_on_a_parent_at_the_origin(self) -> None:
        x, y = centered_origin((0, 0, 1000, 800), SIZE, SCREEN)
        self.assertEqual((x, y), (300, 300))

    def test_a_monitor_to_the_LEFT_keeps_its_negative_x(self) -> None:
        """The regression. A left-hand monitor has negative virtual-desktop x."""
        x, y = centered_origin((-1920, 0, 1000, 800), SIZE, SCREEN)
        self.assertEqual(x, -1620)
        self.assertLess(x, 0, "clamping here throws the modal onto the primary monitor")
        self.assertEqual(y, 300)

    def test_a_monitor_ABOVE_keeps_its_negative_y(self) -> None:
        x, y = centered_origin((0, -1080, 1000, 800), SIZE, SCREEN)
        self.assertEqual(y, -780)
        self.assertLess(y, 0)
        self.assertEqual(x, 300)

    def test_both_negative_is_preserved(self) -> None:
        x, y = centered_origin((-1920, -1080, 1000, 800), SIZE, SCREEN)
        self.assertEqual((x, y), (-1620, -780))

    def test_a_parent_smaller_than_the_child_may_go_negative_too(self) -> None:
        """A narrow parent legitimately centres the child slightly off its left."""
        x, _y = centered_origin((10, 10, 100, 100), SIZE, SCREEN)
        self.assertEqual(x, 10 + (100 - 400) // 2)
        self.assertLess(x, 0)


class ScreenFallbackTests(unittest.TestCase):
    """With no viewable parent there is no second monitor to respect."""

    def test_it_centres_on_the_screen(self) -> None:
        x, y = centered_origin(None, SIZE, SCREEN)
        self.assertEqual((x, y), (760, 440))

    def test_the_fallback_is_still_clamped(self) -> None:
        """A window larger than the screen must not be placed off it."""
        x, y = centered_origin(None, (3000, 2000), SCREEN)
        self.assertEqual((x, y), (0, 0))


class ContractTests(unittest.TestCase):
    def test_the_caller_does_not_reintroduce_a_clamp(self) -> None:
        """The whole bug was a max(0, ...) wrapped around the geometry call."""
        source = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")
        start = source.index("def _center(")
        body = source[start : source.index("\n    def ", start + 1)]
        self.assertIn("centered_origin(", body)
        self.assertNotIn("max(0,", body,
                         "clamping the parent-relative origin is the reported bug")

    def test_the_reason_is_recorded_with_the_helper(self) -> None:
        source = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")
        start = source.index("def centered_origin(")
        doc = source[start : source.index("\n\n\nclass WaitWindow", start)]
        self.assertIn("modal", doc)
        self.assertIn("monitor", doc)


if __name__ == "__main__":
    unittest.main()
