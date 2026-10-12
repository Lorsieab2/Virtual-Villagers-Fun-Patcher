"""A backup and a restore keep every file's own modification time.

Two companions believe a queued purchase only when "the slot's save was written after it": the
Barrel of Babies file (native/shared/paid_purchases.h vv_paid_arrive) and the Story Purchases file
(native/vvfp_story_upgrades/story_queue.inc sq_restore) compare the save's last-write time with the
moment the purchase became pending, because a save older than the purchase does not hold its charge.

A backup made while the game runs (the game is paused for the copy) holds the save as it is on disk
-- written BEFORE the pending purchase -- and the purchase file.  Restoring it used to give every
file the time of the restore, so the restored old save looked newer than the purchase and the
purchase was delivered with no charge in the save: a free Barrel of Babies, or a free picked island
event.  The copy and the restore now carry each file's time with it, so the old save stays older
than the purchase and the companion drops the file.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_save_backup as backup  # noqa: E402
from test_backup_paused_speed import save_bytes  # noqa: E402

NOW = datetime(2026, 10, 11, 9, 30, 0)
SAVE_TIME = 1_600_000_000_000_000_000      # ns: 2020-09-13
PURCHASE_TIME = 1_700_000_000_000_000_000  # ns: 2023-11-14
FOLDER = "Virtual Villagers - The Secret City - Modded"
SAVE = "Virtual Villagers - The Secret City1.ldw"
PURCHASE = ("Virtual Villagers Fun Patcher Data/Paid Purchases/"
            "Virtual Villagers 3 Paid Purchases - Save 1.dat")


class NoGames:
    def find(self, exe_name):
        return []


def stamp(path: Path, ns: int) -> None:
    os.utime(path, ns=(ns, ns))


class FileTimes(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self._tmp.name) / "LDW" / FOLDER
        self.folder.mkdir(parents=True)
        # A real, running-speed save of The Secret City (the backup sets its copy to Paused).
        (self.folder / SAVE).write_bytes(save_bytes(3, 6))
        (self.folder / PURCHASE).parent.mkdir(parents=True)
        (self.folder / PURCHASE).write_bytes(b"pending purchase")
        stamp(self.folder / SAVE, SAVE_TIME)
        stamp(self.folder / PURCHASE, PURCHASE_TIME)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def mtime(self, path: Path) -> int:
        return path.stat().st_mtime_ns

    def test_the_backup_copy_keeps_each_files_time_even_a_save_set_to_paused(self) -> None:
        made = backup.copy_save_folder(self.folder, NOW)
        self.assertEqual(made.paused_slots, [SAVE], "the save's copy is the one set to Paused")
        self.assertEqual(self.mtime(made.backup_folder / SAVE), SAVE_TIME)
        self.assertEqual(self.mtime(made.backup_folder / PURCHASE), PURCHASE_TIME)
        self.assertEqual(self.mtime(self.folder / SAVE), SAVE_TIME, "the original is never touched")

    def test_a_restore_puts_the_saves_old_time_back_so_the_purchase_stays_newer(self) -> None:
        made = backup.copy_save_folder(self.folder, NOW)
        # Later play: the purchase is delivered, the game quits and saves.
        (self.folder / SAVE).write_bytes(save_bytes(3, 3))
        (self.folder / PURCHASE).unlink()
        restored = backup.restore_backup(self.folder, made.backup_folder, None, NoGames(),
                                         datetime(2026, 10, 11, 10, 0, 0))
        self.assertTrue(restored.plan.changes)
        self.assertEqual(self.mtime(self.folder / SAVE), SAVE_TIME)
        self.assertEqual(self.mtime(self.folder / PURCHASE), PURCHASE_TIME)
        self.assertLess(self.mtime(self.folder / SAVE), self.mtime(self.folder / PURCHASE),
                        "the restored save is older than the purchase: the companion drops the file")

    def test_the_safety_backup_a_restore_makes_keeps_the_times_it_rolls_back_to(self) -> None:
        later = SAVE_TIME + 10_000_000_000            # 10 s on (Windows keeps 100 ns)
        (self.folder / SAVE).write_bytes(save_bytes(3, 3))
        stamp(self.folder / SAVE, later)
        safety = backup.copy_save_folder(self.folder, datetime(2026, 10, 11, 9, 45, 0), suffix=" (before restore)")
        self.assertEqual(self.mtime(safety.backup_folder / SAVE), later)


if __name__ == "__main__":
    unittest.main()
