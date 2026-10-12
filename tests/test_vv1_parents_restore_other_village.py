"""Restore A New Home Parents never gives one village's parents to another.

A "<name>.another-village-<ticks>-<n>" copy (native/vv1_parentage/vv1_parentage.c) is, by definition, a
file whose roster shared nobody with the village on screen when it was set aside -- very often a
DIFFERENT village (a save copied into the slot).  Villagers are identified by gender, family number and
name, which repeat across villages (names come from a fixed pool), so a copy that is not this village's
must not be a source: its "Mira Tala" is not this village's "Mira Tala".  All synthetic files."""
from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import vv1_parents_restore as restore  # noqa: E402
from test_vv1_parents_restore import Idle, SLOT, parents, table  # noqa: E402


class OtherVillageCopyTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.folder = self.root / "Virtual Villagers - Test"
        records = self.folder / "Virtual Villagers Fun Patcher Data" / "Parentage Records"
        records.mkdir(parents=True)
        self.path = records / restore.file_name(SLOT)
        # Village B is on screen: five villagers, none with parents (founders and the like).
        self.path.write_bytes(table([
            (0, "Mira Tala", 2, 7, 1, 1, 0, None, None, None),
            (1, "Oren Tala", 1, 7, 2, 2, 0, None, None, None),
            (2, "Pia Tala", 2, 8, 3, 3, 0, None, None, None),
            (3, "Quin Tala", 1, 8, 4, 4, 0, None, None, None),
            (4, "Rho Tala", 2, 9, 5, 5, 0, None, None, None),
        ]))
        # Village A, set aside when B was copied into the slot: a different village that happens to
        # have a "Mira Tala" (same gender and family number) whose parents are A's own.
        aside = self.path.with_name(self.path.name + ".another-village-12345-0")
        aside.write_bytes(table([
            (0, "Mira Tala", 2, 7, 6, 6, 0, "Ayo Zuri", "Bela Zuri", None),
            (1, "Ayo Zuri", 1, 31, 7, 7, 0, None, None, None),
            (2, "Bela Zuri", 2, 32, 8, 8, 0, None, None, None),
            (3, "Cai Zuri", 1, 33, 9, 9, 0, None, None, None),
            (4, "Dee Zuri", 2, 34, 10, 10, 0, None, None, None),
        ]))
        (self.folder / "Virtual Villagers Fun Patcher Logs").mkdir()

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_a_copy_of_another_village_is_not_a_source(self):
        plan = restore.plan(self.folder, SLOT)
        self.assertEqual(plan.restored, [], [r for r in plan.restored])
        self.assertEqual(parents(bytes(plan.table.data), "Mira Tala")[:2], ("", ""))

    def test_a_copy_of_this_village_still_is(self):
        same = self.path.with_name(self.path.name + ".another-village-12345-1")
        same.write_bytes(table([
            (0, "Mira Tala", 2, 7, 1, 1, 0, "Oren Tala", "Pia Tala", None),
            (1, "Oren Tala", 1, 7, 2, 2, 0, None, None, None),
            (2, "Pia Tala", 2, 8, 3, 3, 0, None, None, None),
            (3, "Quin Tala", 1, 8, 4, 4, 0, None, None, None),
        ]))
        import os, time
        os.utime(same, (time.time() + 10, time.time() + 10))
        plan = restore.plan(self.folder, SLOT)
        self.assertEqual(parents(bytes(plan.table.data), "Mira Tala")[:2], ("Oren Tala", "Pia Tala"))


if __name__ == "__main__":
    unittest.main()
