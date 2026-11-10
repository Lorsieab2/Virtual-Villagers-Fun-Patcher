"""The Secret City's second faction survives Back Up Saves, Repair's pause and Restore Saves.

VV3 Both Factions binds each entry of its per-save file to an FNV-1a fingerprint of the save (docs/
vv3-both-factions.md).  Pausing a backup's copy changes the save's game clock inside that fingerprint, so
before this fix a restored backup loaded with one faction (the owner, 2026-10-27: "I restored my tribe from a
backup and now I've lost the second faction").  These tests use a real 256-villager Secret City save."""
from __future__ import annotations

import gzip
import os
import struct
import sys
import tempfile
import unittest
from unittest import mock
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv3_second_faction as faction  # noqa: E402
import vv_save_backup as backup  # noqa: E402

GAME_FOLDER = "Virtual Villagers - The Secret City - Modded"
BASE = "Virtual Villagers - The Secret City"
SAVE = (ROOT / "tests" / "fixtures" / "rename_tribe" / "vv3-256-1.ldw.gz")
NOW = datetime(2026, 10, 27, 12, 0, 0)


class NoGame:
    def find(self, name):
        return []

    def suspend(self, pid, exe):
        return None

    def resume(self, handle):
        pass


def faction_bytes(slot: int, fingerprints: list[int], secondary: int = 6, level: int = 2) -> bytes:
    """A version-2 file as the DLL writes it: entries newest last, the rest zero."""
    entries = b"".join(struct.pack("<IIBBBBIIB3x", fp & 0xFFFFFFFF, fp >> 32, secondary, level, 5, 1,
                                   1_700_000_000, 0, 0b101) for fp in fingerprints)
    body = struct.pack("<5I", faction.MAGIC, 2, 3, slot, len(fingerprints)) + entries
    return body + b"\0" * (20 + 16 * 24 - len(body))


class SecondFaction(unittest.TestCase):

    def setUp(self):
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.folder = Path(holder.name) / GAME_FOLDER
        self.folder.mkdir()
        self.save = gzip.open(SAVE).read()
        self.assertIsNotNone(backup.pause_save_bytes(3, self.save), "the fixture must be a running (unpaused) save")
        (self.folder / f"{BASE}1.ldw").write_bytes(self.save)
        self.dat = faction.faction_file(self.folder, 1)
        self.dat.parent.mkdir(parents=True)
        self.dat.write_bytes(faction_bytes(1, [faction.fingerprint(self.save)]))

    def linked(self, folder: Path, name: str = f"{BASE}1.ldw") -> bool:
        return faction.entry_for(faction.faction_file(folder, 1),
                                 faction.fingerprint((folder / name).read_bytes())) is not None

    def test_a_backup_keeps_the_second_faction(self):
        before = self.dat.read_bytes()
        made = backup.copy_save_folder(self.folder, NOW)
        copy = (made.backup_folder / f"{BASE}1.ldw").read_bytes()
        self.assertNotEqual(copy, self.save, "the backup's copy is paused")
        self.assertTrue(self.linked(made.backup_folder), "the paused copy keeps its second faction")
        new = faction.entry_for(faction.faction_file(made.backup_folder, 1), faction.fingerprint(copy))
        old = faction.entry_for(self.dat, faction.fingerprint(self.save))
        self.assertEqual(new[8:12], old[8:12], "same factions and levels")
        self.assertEqual(new[16], old[16], "same recipes")
        self.assertEqual((self.folder / f"{BASE}1.ldw").read_bytes(), self.save, "the live save is untouched")
        self.assertEqual(self.dat.read_bytes(), before, "the live faction file is untouched")
        record = next(c for c in made.files if c.relative == self.dat.relative_to(self.folder))
        self.assertEqual(record.size, faction.faction_file(made.backup_folder, 1).stat().st_size)

    def test_a_failed_restore_puts_the_faction_file_back_as_it_was(self):
        """Codex, #651: the before-restore backup's faction file gains an entry (dropping its oldest when full);
        the bytes it had are kept, as the unpaused saves are, so a rollback writes exactly those."""
        self.dat.write_bytes(faction_bytes(1, list(range(1, 16)) + [faction.fingerprint(self.save)]))
        live = self.dat.read_bytes()
        made = backup.copy_save_folder(self.folder, NOW)
        relative = self.dat.relative_to(self.folder)
        self.assertNotEqual(faction.faction_file(made.backup_folder, 1).read_bytes(), live, "the copy gained an entry")
        self.assertEqual(made.unpaused_bytes[relative], live, "and its bytes as copied are kept")
        self.dat.write_bytes(b"changed by a restore")
        self.assertEqual(backup._roll_back(self.folder, made, [relative]), [])
        self.assertEqual(self.dat.read_bytes(), live, "a rollback puts the file back exactly")

    def test_a_save_without_a_second_faction_gets_no_entry(self):
        self.dat.write_bytes(faction_bytes(1, [12345]))
        made = backup.copy_save_folder(self.folder, NOW)
        self.assertEqual(faction.faction_file(made.backup_folder, 1).read_bytes(), faction_bytes(1, [12345]))

    def test_an_invalid_file_is_never_written(self):
        self.dat.write_bytes(b"not a faction file")
        made = backup.copy_save_folder(self.folder, NOW)
        self.assertEqual(faction.faction_file(made.backup_folder, 1).read_bytes(), b"not a faction file")

    def test_an_old_backup_is_linked_again_from_the_games_own_copy(self):
        """A backup made before the fix (its copy paused, its file without the paused fingerprint) is linked
        again on Restore Saves, from the game's copy of the save it was made from (here the slot's N+20)."""
        old = self.folder / "Backups" / "Backup 2026-10-25 21-58-47"
        old.mkdir(parents=True)
        (old / f"{BASE}1.ldw").write_bytes(backup.pause_save_bytes(3, self.save))
        faction.faction_file(old, 1).parent.mkdir(parents=True)
        faction.faction_file(old, 1).write_bytes(self.dat.read_bytes())
        self.assertFalse(self.linked(old))
        (self.folder / f"{BASE}21.ldw").write_bytes(self.save)          # the game's own copy
        (self.folder / f"{BASE}1.ldw").write_bytes(self.save[:-1] + b"\x01")   # played on since
        result = backup.restore_backup(self.folder, old, None, NoGame(), NOW + timedelta(minutes=1))
        self.assertEqual(result.backups_relinked.get(old.name), {1: True})
        self.assertTrue(self.linked(old), "the old backup has its second faction again")
        self.assertTrue(self.linked(self.folder), "and so does the restored save")

    def test_saves_that_already_match_the_backup_still_get_it_back(self):
        """Codex, PR #650 (the owner's own case): the live saves are already the restored backup's, faction
        file and all, so the plan alone has nothing to do; with the backups linked first (as the Restore
        window now does), the repaired faction file is what the restore brings back."""
        old = self.folder / "Backups" / "Backup 2026-10-25 21-58-47"
        old.mkdir(parents=True)
        paused = backup.pause_save_bytes(3, self.save)
        (old / f"{BASE}1.ldw").write_bytes(paused)
        faction.faction_file(old, 1).parent.mkdir(parents=True)
        faction.faction_file(old, 1).write_bytes(self.dat.read_bytes())
        (self.folder / f"{BASE}1.ldw").write_bytes(paused)              # the earlier restore
        (self.folder / f"{BASE}21.ldw").write_bytes(self.save)          # the game's own copy
        (old / f"{BASE}21.ldw").write_bytes(self.save)
        self.assertEqual(backup.plan_restore(self.folder, old).changes, 0)
        backup.relink_backups(self.folder)
        self.assertGreater(backup.plan_restore(self.folder, old).changes, 0)
        backup.restore_backup(self.folder, old, None, NoGame(), NOW + timedelta(minutes=1))
        self.assertTrue(self.linked(self.folder), "the live save has its second faction again")

    def test_no_copy_means_no_guess(self):
        old = self.folder / "Backups" / "Backup 2026-10-25 21-58-47"
        old.mkdir(parents=True)
        other = bytearray(self.save)
        other[0x1000] ^= 0xFF                                            # a save no copy reproduces
        (old / f"{BASE}1.ldw").write_bytes(backup.pause_save_bytes(3, bytes(other)))
        faction.faction_file(old, 1).parent.mkdir(parents=True)
        faction.faction_file(old, 1).write_bytes(self.dat.read_bytes())
        self.assertEqual(backup.relink_backups(self.folder), {old.name: {1: False}})
        self.assertEqual(faction.faction_file(old, 1).read_bytes(), self.dat.read_bytes(), "nothing written")

    def test_repairs_pause_keeps_the_second_faction(self):
        old = self.folder / "Backups" / "Backup 2026-10-25 21-58-47"
        old.mkdir(parents=True)
        (old / f"{BASE}1.ldw").write_bytes(self.save)                   # an old backup, never paused
        faction.faction_file(old, 1).parent.mkdir(parents=True)
        faction.faction_file(old, 1).write_bytes(self.dat.read_bytes())
        outcome = backup.pause_saves([old / f"{BASE}1.ldw"], NoGame())
        self.assertEqual(outcome.paused, [old / f"{BASE}1.ldw"])
        self.assertTrue(self.linked(old))

    def test_the_file_keeps_sixteen_newest_last(self):
        self.dat.write_bytes(faction_bytes(1, list(range(1, 17))))
        source = faction.entry_for(self.dat, 16)
        self.assertTrue(faction.add_entry(self.dat, 99, source))
        data = self.dat.read_bytes()
        self.assertEqual(len(data), 20 + 16 * 24)
        fps = [struct.unpack_from("<I", data, 20 + i * 24)[0] for i in range(16)]
        self.assertEqual(fps, list(range(2, 17)) + [99])

    # ---- Repair's game speed in a backup (Codex, #750) ----------------------------------------------

    def old_backup(self) -> Path:
        """A backup made before the patcher kept the faction link: its copy paused, its faction file without
        the paused fingerprint; the game's own copy of the save it was made from is the slot's N+20."""
        old = self.folder / "Backups" / "Backup 2026-10-25 21-58-47"
        old.mkdir(parents=True)
        (old / f"{BASE}1.ldw").write_bytes(backup.pause_save_bytes(3, self.save))
        faction.faction_file(old, 1).parent.mkdir(parents=True)
        faction.faction_file(old, 1).write_bytes(self.dat.read_bytes())
        (self.folder / f"{BASE}21.ldw").write_bytes(self.save)
        self.assertFalse(self.linked(old))
        return old

    def test_a_backups_speed_change_recovers_its_second_faction_first(self):
        old = self.old_backup()
        for choice in ("fast", "slow", "normal", "paused"):
            with self.subTest(choice=choice):
                done = backup.set_backup_speed(self.folder, old, choice)
                self.assertEqual([name for name, *_ in done.changed], [f"{BASE}1.ldw"])
                self.assertTrue(self.linked(old), "the changed save keeps its second faction")
                new = faction.entry_for(faction.faction_file(old, 1),
                                        faction.fingerprint((old / f"{BASE}1.ldw").read_bytes()))
                source = faction.entry_for(self.dat, faction.fingerprint(self.save))
                self.assertEqual(new[8:], source[8:], "the same factions, levels and recipes")
        self.assertEqual((self.folder / f"{BASE}1.ldw").read_bytes(), self.save, "the live save is untouched")

    def state(self, folder: Path) -> tuple:
        path = folder / f"{BASE}1.ldw"
        return path.read_bytes(), path.stat().st_mtime_ns, faction.faction_file(folder, 1).read_bytes()

    def failing_steps(self):
        """Each step after the save is written, failing: the relink (after writing its entry), the time."""
        real_relink = faction.relink

        def relink_then_fail(*args):
            real_relink(*args)
            raise OSError("the faction file could not be written")

        def times_fail(path, times):
            raise backup.BackupError(f"The time of {path.name} could not be kept (test).")

        yield "relink", lambda: mock.patch.object(backup.vv3_second_faction, "relink", relink_then_fail)
        yield "times", lambda: mock.patch.object(backup, "_keep_times", times_fail)

    def set_old_time(self, path: Path) -> None:
        os.utime(path, ns=(1_600_000_000 * 10**9, 1_600_000_000 * 10**9))

    def test_a_failure_after_the_write_puts_everything_back(self):
        old = self.old_backup()
        copy = old / f"{BASE}1.ldw"
        live = self.folder / f"{BASE}1.ldw"
        self.set_old_time(copy)
        self.set_old_time(live)
        for step, patch in self.failing_steps():
            with self.subTest(tool="backup speed", step=step):
                before = self.state(old)
                with patch():
                    done = backup.set_backup_speed(self.folder, old, "fast")
                self.assertEqual(done.changed, [])
                self.assertEqual([name for name, _ in done.skipped], [copy.name])
                self.assertIn("put back exactly as it was", done.skipped[0][1])
                self.assertEqual(self.state(old), before, "bytes, time and faction file as they were")
                self.assertFalse(self.linked(old), "the recovered link is taken back too")
            with self.subTest(tool="Repair game speed", step=step):
                before = self.state(self.folder)
                with patch(), self.assertRaises(backup.BackupError) as raised:
                    backup.set_speed_choice(3, live, "fast", NoGame())
                self.assertIn("put back exactly as it was", str(raised.exception))
                self.assertEqual(self.state(self.folder), before)
            with self.subTest(tool="Repair set to Paused", step=step):
                kept = copy.read_bytes()
                copy.write_bytes(self.save)                              # an old backup, never paused
                self.set_old_time(copy)
                before = self.state(old)
                with patch():
                    outcome = backup.pause_saves([copy], NoGame())
                self.assertEqual(outcome.paused, [])
                self.assertIn("put back exactly as it was", outcome.skipped[0][1])
                self.assertEqual(self.state(old), before)
                copy.write_bytes(kept)
                self.set_old_time(copy)
        # Nothing failing, a retry does it all: changed, linked, its time kept.
        done = backup.set_backup_speed(self.folder, old, "fast")
        self.assertEqual(len(done.changed), 1)
        self.assertTrue(self.linked(old))
        self.assertEqual(copy.stat().st_mtime_ns, 1_600_000_000 * 10**9)

    def test_the_live_speed_change_keeps_the_second_faction_and_the_time(self):
        live = self.folder / f"{BASE}1.ldw"
        self.set_old_time(live)
        backup.set_speed_choice(3, live, "slow", NoGame())
        self.assertNotEqual(live.read_bytes(), self.save)
        self.assertTrue(self.linked(self.folder))
        self.assertEqual(live.stat().st_mtime_ns, 1_600_000_000 * 10**9)


if __name__ == "__main__":
    unittest.main()
