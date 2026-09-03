"""VV3 must force the island-event table to exist BEFORE it snapshots it.

VV3 presents the purchased "Another One of Those Barrels" event by pointing
every slot of the island-event object array at the barrel singleton, running
the game's own presenter, then restoring the array it saved.

The event objects are allocated lazily: the manager constructor at 0x418630
fills 0x4B3C7C onwards, and nothing exists until the lazy getter 0x419AC0 has
run once. The routine originally called that getter AFTER taking its snapshot,
so on the first barrel purchase of a session it captured 57 nulls, let the
constructor build the real table, presented, and then wrote the nulls back over
it. Because the singleton at 0x4B3C38 was left non-null the getter never
rebuilt the table, which killed the purchased barrel AND every natural island
event for the rest of the session.

Live tracing is what found it -- the pending flag at 0x4B3C75 went 1 -> 0 on
schedule, 75,000 tech points were charged, "Barrel of Babies completed." was
shown, and all 58 slots read zero with no popup. None of that is visible in the
cave's bytes, so this pins the ordering instead.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "scripts" / "build_vv3_origins_feature.py"


def present_routine() -> str:
    """The assembly text of barrel_present_code."""
    text = GENERATOR.read_text(encoding="utf-8")
    start = text.index("barrel_present_code = assemble(")
    end = text.index("BARREL_PRESENT_VA,", start)
    return text[start:end]


class BarrelPresentOrderingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.routine = present_routine()

    def test_the_manager_getter_runs_before_the_snapshot(self) -> None:
        """The whole bug in one assertion."""
        getter = self.routine.find("call 0x{BARREL_SELECT_MANAGER_VA:X}")
        self.assertNotEqual(getter, -1, "the lazy manager getter is no longer called")
        snapshot = self.routine.find("bp_save:")
        self.assertNotEqual(snapshot, -1, "the snapshot loop is gone")
        self.assertLess(
            getter, snapshot,
            "the island-event table is built lazily by the manager constructor, so "
            "snapshotting before the getter runs captures nulls -- and the restore "
            "loop then writes those nulls back over the table, permanently killing "
            "the barrel and every natural island event for the session",
        )

    def test_the_barrel_object_is_read_after_the_getter(self) -> None:
        """Reading slot 0x39 before construction yields null, so the splat is null."""
        getter = self.routine.find("call 0x{BARREL_SELECT_MANAGER_VA:X}")
        read = self.routine.find("mov eax, dword ptr [0x{BARREL_EVENT_OBJECT_VA:X}]")
        self.assertNotEqual(read, -1, "the barrel object read is gone")
        self.assertLess(getter, read)

    def test_the_getter_is_called_exactly_once(self) -> None:
        """Calling it again after the snapshot would reintroduce the old order."""
        self.assertEqual(
            self.routine.count("call 0x{BARREL_SELECT_MANAGER_VA:X}"), 1
        )

    def test_the_manager_is_carried_to_the_presenter_in_a_saved_register(self) -> None:
        """eax does not survive the snapshot loop, so the manager must be held.

        ebx is callee-saved, and the whole routine runs inside pushad/popad, so
        parking the manager there costs nothing and keeps the presenter's `this`
        correct.
        """
        self.assertRegex(self.routine, r"mov ebx, eax")
        presenter = self.routine.find("call 0x{BARREL_PRESENT_EVENT_VA:X}")
        self.assertNotEqual(presenter, -1, "the presenter call is gone")
        window = self.routine[:presenter]
        self.assertIn(
            "mov ecx, ebx", window,
            "the presenter must receive the manager that was constructed earlier",
        )

    def test_the_array_is_still_restored(self) -> None:
        """The fix is about ordering, not about dropping the restore."""
        self.assertIn("bp_restore:", self.routine)
        self.assertIn("popad", self.routine)

    def test_the_reasoning_is_recorded_next_to_the_code(self) -> None:
        """A future edit that reorders these two calls must see why it matters."""
        text = GENERATOR.read_text(encoding="utf-8")
        anchor = text.index("barrel_present_code = assemble(")
        comment = text[max(0, anchor - 2600):anchor]
        self.assertIn("lazily", comment)
        self.assertIn("0x418630", comment)


if __name__ == "__main__":
    unittest.main()
