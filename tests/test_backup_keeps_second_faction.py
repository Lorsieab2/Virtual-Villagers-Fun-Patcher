"""The Secret City's second faction survives Back Up Saves, Repair's pause and Restore Saves.

VV3 Both Factions binds each entry of its per-save file to an FNV-1a fingerprint of the save (docs/
vv3-both-factions.md).  Pausing a backup's copy changes the save's game clock inside that fingerprint, so
before this fix a restored backup loaded with one faction (the owner, 2026-10-27: "I restored my tribe from a
backup and now I've lost the second faction").  These tests use a real 256-villager Secret City save."""
from __future__ import annotations

import gzip
import struct
import sys
import tempfile
import unittest
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


if __name__ == "__main__":
    unittest.main()
