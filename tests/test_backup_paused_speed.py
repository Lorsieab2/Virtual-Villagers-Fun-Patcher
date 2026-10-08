"""Backups set to Paused game speed (the owner, 2026-10-08: a restored backup must never catch up
on the real time since it was made), and Repair Saves & Logs' "set saves to Paused".

The speed is a dword in the save buffer: 3 / 6 / 10, plus 999 while paused (1002 / 1005 / 1009),
at the in-memory field less 8.  Read on every one of the owner's saves of all five games.  These
tests build saves of each game's own layout and check that exactly those four bytes change, to
exactly what the game writes, and that nothing else is ever touched."""
from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_save_backup as backup  # noqa: E402

TITLES = {
    1: ("Virtual Villagers - A New Home", "Virtual Villagers"),
    2: ("Virtual Villagers - The Lost Children", "Virtual Villagers - The Lost Children"),
    3: ("Virtual Villagers - The Secret City", "Virtual Villagers - The Secret City"),
    4: ("Virtual Villagers - The Tree of Life", "Virtual Villagers - The Tree of Life"),
    5: ("Virtual Villagers - New Believers", "Virtual Villagers - New Believers"),
}
# The in-memory speed field of each game (docs/hidden-gates-all-five-games.md and the Origins
# companions' Time Warp), so the buffer offset is checked against an independent source.
MEMORY_FIELD = {1: 0xA318, 2: 0x2EB08, 3: 0x12F20, 4: 0x17110, 5: 0x17D7C}


def save_bytes(game: int, speed: int, header: int | None = None, buffer: int | None = None) -> bytes:
    layouts = backup._SAVE_LAYOUTS[game]
    header, length_at = next((h, at) for h, at in layouts if header in (None, h))
    buffer = buffer or backup._SAVE_BUFFERS[game][0]
    data = bytearray((i * 7 + game) & 0xFF for i in range(header + buffer))   # every byte known
    data[0:4] = b"ldwg"
    data[length_at:length_at + 4] = buffer.to_bytes(4, "little")
    at = header + MEMORY_FIELD[game] - 8
    data[at:at + 4] = speed.to_bytes(4, "little")
    return bytes(data)


class SpeedTests(unittest.TestCase):
    def test_the_field_is_the_memory_field_less_8_in_every_game(self) -> None:
        for game, field in MEMORY_FIELD.items():
            self.assertEqual(backup._SPEED_IN_BUFFER[game], field - 8, game)

    def test_pausing_adds_999_and_changes_nothing_else(self) -> None:
        for game in TITLES:
            for header, _at in backup._SAVE_LAYOUTS[game]:
                for buffer in backup._SAVE_BUFFERS[game]:
                    for speed in (3, 6, 10):
                        before = save_bytes(game, speed, header, buffer)
                        after = backup.pause_save_bytes(game, before)
                        self.assertIsNotNone(after, (game, header, buffer, speed))
                        self.assertEqual(len(after), len(before))
                        changed = [i for i in range(len(before)) if before[i] != after[i]]
                        at = header + MEMORY_FIELD[game] - 8
                        self.assertTrue(set(changed) <= set(range(at, at + 4)), (game, changed[:8]))
                        self.assertEqual(backup.save_speed(game, after), (at, speed + 999))

    def test_an_already_paused_save_is_left_alone(self) -> None:
        for game in TITLES:
            for speed in (1002, 1005, 1009):
                self.assertIsNone(backup.pause_save_bytes(game, save_bytes(game, speed)))

    def test_anything_that_is_not_the_games_save_is_never_touched(self) -> None:
        for game in TITLES:
            good = save_bytes(game, 6)
            self.assertIsNone(backup.pause_save_bytes(game, b"ldwX" + good[4:]))           # magic
            self.assertIsNone(backup.pause_save_bytes(game, good[:-1]))                     # length
            self.assertIsNone(backup.pause_save_bytes(game, save_bytes(game, 7)))           # not a speed
            self.assertIsNone(backup.pause_save_bytes(game, save_bytes(game, 0)))
            other = 1 if game != 1 else 2
            self.assertIsNone(backup.pause_save_bytes(other, good))                          # another game's


class BackupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def folder(self, game: int) -> Path:
        title, base = TITLES[game]
        folder = Path(self.tmp.name) / f"{title} - Modded"
        folder.mkdir()
        (folder / f"{base}1.ldw").write_bytes(save_bytes(game, 6))
        (folder / f"{base}2.ldw").write_bytes(save_bytes(game, 1003 - 997))     # 6
        (folder / f"{base}3.ldw").write_bytes(save_bytes(game, 1009))           # already paused
        (folder / f"{base}21.ldw").write_bytes(save_bytes(game, 6))             # an older generation
        (folder / f"{base}0.ldw").write_bytes(b"slot list")
        return folder

    def test_a_backup_holds_paused_saves_and_the_originals_are_untouched(self) -> None:
        for game in TITLES:
            with self.subTest(game=game):
                folder = self.folder(game)
                originals = {p.name: p.read_bytes() for p in folder.iterdir() if p.is_file()}
                made = backup.copy_save_folder(folder, datetime(2026, 10, 8, 12, 0, 0))
                base = TITLES[game][1]
                for name, data in originals.items():
                    self.assertEqual((folder / name).read_bytes(), data, name)      # never the originals
                copy = made.backup_folder
                for slot in (1, 2):
                    self.assertEqual(backup.save_speed(game, (copy / f"{base}{slot}.ldw").read_bytes())[1], 1005)
                self.assertEqual((copy / f"{base}3.ldw").read_bytes(), originals[f"{base}3.ldw"])
                self.assertEqual((copy / f"{base}21.ldw").read_bytes(), originals[f"{base}21.ldw"])
                self.assertEqual((copy / f"{base}0.ldw").read_bytes(), b"slot list")
                self.assertEqual(sorted(made.paused_slots), [f"{base}1.ldw", f"{base}2.ldw"])
                recorded = {f.relative.name: f.sha256 for f in made.files}
                self.assertEqual(recorded[f"{base}1.ldw"], backup._hash_file(copy / f"{base}1.ldw")[1])
                self.assertEqual(backup.unpaused_backup_saves(folder), [])

    def test_repair_pauses_older_backups_and_chosen_saves(self) -> None:
        game = 1
        folder = self.folder(game)
        made = backup.copy_save_folder(folder, datetime(2026, 10, 8, 12, 0, 0))
        base = TITLES[game][1]
        old = made.backup_folder / f"{base}1.ldw"
        old.write_bytes(save_bytes(game, 3))                    # as a backup made before v6
        self.assertEqual(backup.unpaused_backup_saves(folder), [old])
        stray = Path(self.tmp.name) / "picked.ldw"
        stray.write_bytes(save_bytes(4, 10, header=12))         # an older Tree of Life save
        junk = Path(self.tmp.name) / "junk.ldw"
        junk.write_bytes(b"not a save")

        class NoGames:
            def find(self, exe_name):
                return []

        outcome = backup.pause_saves([old, stray, junk, folder / f"{base}3.ldw"], NoGames())
        self.assertEqual(outcome.paused, [old, stray])
        self.assertEqual(outcome.already, [folder / f"{base}3.ldw"])
        self.assertEqual([p for p, _why in outcome.skipped], [junk])
        self.assertEqual(junk.read_bytes(), b"not a save")
        self.assertEqual(backup.save_speed(1, old.read_bytes())[1], 1002)
        self.assertEqual(backup.save_speed(4, stray.read_bytes())[1], 1009)
        self.assertEqual(list(Path(self.tmp.name).rglob("*.vvfp-pause-tmp")), [])

    def test_a_save_whose_game_is_running_is_left_alone(self) -> None:
        folder = self.folder(1)
        live = folder / "Virtual Villagers1.ldw"
        before = live.read_bytes()

        class Running:
            def find(self, exe_name):
                return [1234]

        outcome = backup.pause_saves([live], Running())
        self.assertEqual([p for p, _why in outcome.skipped], [live])
        self.assertEqual(live.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
