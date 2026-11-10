"""A game-speed change or pause always works on a save the game wrote (the owner, v1.35.92: "the game
speed should always be able to be altered in the save using repair saves!!!!!!!! for all 5 games" and
"backup saves should always set the save to paused").

The owner's Tree of Life save was refused: "its game clock was last changed after its last tick" -- the
player pressed pause (or a speed button) after the game's last world tick and saved before another, so
the clock's wall base is later than the save's last tick.  The change is now replayed at that press, the
latest moment the save knows of (src/vv_save_clock.py, NORMALISING).  These tests check, on real saves
of every clock state and against the stock routine run in the emulator (tests/test_save_speed_edit.py):

  * every change from such a save is the game's own bytes, in The Secret City and The Tree of Life,
    stock and 256 Villagers;
  * the game time, the village's age and every timer carry over: the game base is kept, nothing is
    moved back to the old tick, no running timer is brought forward, the save's last tick is unchanged,
    and the game played on from the result reads the same game clock as the game played on from the
    original;
  * Back Up Saves pauses every such slot save, and lists none as not paused;
  * the speed games A New Home, The Lost Children and New Believers change from every speed;
  * only a file that is not the game's save is refused, and then nothing is written.
"""
from __future__ import annotations

import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_save_backup as backup  # noqa: E402
import vv_save_clock as clock  # noqa: E402
import test_save_speed_edit as se  # noqa: E402

CLOCK_GAMES = (3, 4)
GAPS = (1, 2, 60, 5_000)


def clock_of(save: se.Save, game: int) -> list[int]:
    rules = clock.GAMES[game]
    return [save.get(rules.clock + 4 * k) for k in range(4)]


def game_time(game: int, fields: list[int], at: int) -> int:
    """The game clock the game reads at wall moment `at` (VV3 0x426590, VV4 0x41DB20)."""
    return clock._game_clock(clock.GAMES[game], list(fields), at)


class ChangedAfterTheLastTick(unittest.TestCase):
    def setUp(self) -> None:
        if not all(se.have(game) for game in CLOCK_GAMES):
            self.skipTest("the stock Secret City and Tree of Life are not in inputs\\")

    def starts(self, game: int):
        for name in (se.FIXTURE[game], se.FIXTURE_256[game]):
            for gap in GAPS:
                for start in se.SPEEDS:
                    yield name, gap, f"paused {start}", se.pressed_after_tick(game, name, start, 999, gap)
                    for press in se.SPEEDS:
                        if press != start:
                            yield (name, gap, f"{start} -> {press}",
                                   se.pressed_after_tick(game, name, start, press, gap))

    def test_every_change_succeeds_and_keeps_game_time_and_timers(self) -> None:
        for game in CLOCK_GAMES:
            rules = clock.GAMES[game]
            for name, gap, label, data in self.starts(game):
                before = se.Save(game, data)
                now = before.get(rules.now)
                old = clock_of(before, game)
                press = old[2]
                self.assertGreater(press, now)
                for speed in se.SPEEDS:
                    for paused in (False, True):
                        with self.subTest(game=game, fixture=name, gap=gap, start=label, speed=speed,
                                          paused=paused):
                            out = clock.edit_speed(game, data, before.header, speed, paused) or data
                            after = se.Save(game, out)
                            new = clock_of(after, game)
                            # The last tick is the game's; the clock is changed at the press.
                            self.assertEqual(after.get(rules.now), now)
                            self.assertEqual(new[2], press)
                            # The game time at the press is exactly what it was: no fast-forward,
                            # no rewind, so the village's age is unchanged.
                            self.assertEqual(game_time(game, new, press), game_time(game, old, press))
                            self.assertEqual(new[3], old[3])
                            # Speed and pause as asked.
                            self.assertEqual(after.get(rules.speed), speed + 999 if paused else speed)
                            self.assertEqual(new[0], 0 if paused else speed)
                            # No timer still ahead of the press is brought before it.
                            for field in rules.timers:
                                t0, t1 = before.get(field), after.get(field)
                                if t0 > press and t0 != clock.MASK and old[0] != 0:
                                    self.assertGreaterEqual(t1, press, (hex(field), t0, t1))

    def test_played_on_the_game_clock_runs_on_from_where_it_was(self) -> None:
        """The game played on from the edited save, for an hour of wall time at its new speed, reads
        the game base plus that hour at that speed: the same clock the original would have read had
        the player changed the speed in the game at that moment."""
        for game in CLOCK_GAMES:
            for gap in GAPS:
                data = se.pressed_after_tick(game, se.FIXTURE[game], 6, 999, gap)
                before = se.Save(game, data)
                press = clock_of(before, game)[2]
                base = clock_of(before, game)[3]
                for speed in se.SPEEDS:
                    out = clock.edit_speed(game, data, before.header, speed, False)
                    fields = clock_of(se.Save(game, out), game)
                    hour = 3_600
                    expected = base + clock._trunc(clock.Fraction(hour) /
                                                   clock._wall_per_game_second(clock.GAMES[game], speed))
                    self.assertEqual(game_time(game, fields, press + hour), expected, (game, gap, speed))

    def test_back_up_saves_pauses_every_one(self) -> None:
        for game in CLOCK_GAMES:
            for name, gap, label, data in self.starts(game):
                with self.subTest(game=game, fixture=name, gap=gap, start=label):
                    paused = backup.pause_save_bytes(game, data)
                    value = se.Save(game, data).get(clock.GAMES[game].speed)
                    if value >= 999:
                        self.assertIsNone(paused)          # already paused as the game pauses
                        continue
                    self.assertIsNotNone(paused)
                    self.assertEqual(paused, se.stock_edit(game, data, value, True))
                    self.assertEqual(clock_of(se.Save(game, paused), game)[0], 0)

    def test_repair_sets_every_choice(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for game in CLOCK_GAMES:
                data = se.pressed_after_tick(game, se.FIXTURE[game], 6, 999, 3)
                folder = Path(tmp) / se.EXE[game][:-4]
                folder.mkdir(exist_ok=True)
                path = folder / f"{se.EXE[game][:-4]}1.ldw"
                for choice in ("slow", "normal", "fast", "paused"):
                    path.write_bytes(data)
                    backup.set_speed_choice(game, path, choice, NoGames())
                    want = {"slow": 10, "normal": 6, "fast": 3, "paused": 1005}[choice]
                    self.assertEqual(backup.save_speed(game, path.read_bytes())[1], want, (game, choice))


class OddClockStates(unittest.TestCase):
    """Clock states the patcher refused before v1.35.93: a paused clock whose speed before the pause is
    not a speed, and a running rate the game never stores."""

    def setUp(self) -> None:
        if not all(se.have(game) for game in CLOCK_GAMES):
            self.skipTest("the stock Secret City and Tree of Life are not in inputs\\")

    def test_a_pause_with_no_speed_before_it_unpauses_to_the_saves_speed(self) -> None:
        for game in CLOCK_GAMES:
            rules = clock.GAMES[game]
            for odd in (0, 7, 999):
                save = se.Save(game, se.pressed_after_tick(game, se.FIXTURE[game], 6, 999, 2))
                save.put(rules.clock + 4, odd)
                data = save.bytes()
                for speed in se.SPEEDS:
                    with self.subTest(game=game, before=odd, speed=speed):
                        out = clock.edit_speed(game, data, save.header, speed, False)
                        self.assertEqual(out, se.stock_edit(game, data, speed, False))
                        self.assertEqual(clock_of(se.Save(game, out), game)[0], speed)
                        self.assertEqual(clock_of(se.Save(game, out), game)[3], clock_of(save, game)[3])

    def test_a_rate_the_game_never_stores_is_changed_by_the_games_arithmetic(self) -> None:
        for game in CLOCK_GAMES:
            rules = clock.GAMES[game]
            save = se.Save(game, se.running(game, se.FIXTURE[game], 6))
            save.put(rules.clock, 5)
            data = save.bytes()
            for speed in se.SPEEDS:
                for paused in (False, True):
                    with self.subTest(game=game, speed=speed, paused=paused):
                        out = clock.edit_speed(game, data, save.header, speed, paused)
                        self.assertEqual(out, se.stock_edit(game, data, speed, paused))


class NoGames:
    def find(self, exe_name):
        return []


class BackUpSavesPausesEverySlot(unittest.TestCase):
    def test_a_backup_never_lists_a_slot_as_not_paused(self) -> None:
        if not all(se.have(game) for game in CLOCK_GAMES):
            self.skipTest("the stock Secret City and Tree of Life are not in inputs\\")
        with tempfile.TemporaryDirectory() as tmp:
            for game in CLOCK_GAMES:
                title = se.EXE[game][:-4]
                folder = Path(tmp) / f"{title} - Modded 256"
                folder.mkdir()
                saves = {1: se.pressed_after_tick(game, se.FIXTURE_256[game], 6, 3, 2),
                         2: se.pressed_after_tick(game, se.FIXTURE[game], 10, 6, 1),
                         3: se.running(game, se.FIXTURE[game], 3)}
                for slot, data in saves.items():
                    (folder / f"{title}{slot}.ldw").write_bytes(data)
                result = backup.copy_save_folder(folder)
                self.assertEqual(result.not_paused, [])
                self.assertEqual(sorted(result.paused_slots), [f"{title}{slot}.ldw" for slot in (1, 2, 3)])
                for slot, data in saves.items():
                    self.assertEqual((folder / f"{title}{slot}.ldw").read_bytes(), data)   # live untouched
                    copy = (result.backup_folder / f"{title}{slot}.ldw").read_bytes()
                    self.assertGreaterEqual(backup.save_speed(game, copy)[1], 999)


class GameSpeedInABackup(unittest.TestCase):
    """Repair Saves & Logs sets the game speed of a backup's saves (the owner, v1.35.92: "ALLOW THE ABILITY
    IN REPAIR SAVES TO SET THE GAME SPEED IN BACKUPS TOO"): only that backup's copies change."""

    def setUp(self) -> None:
        if not all(se.have(game) for game in (1, 2, 3, 4, 5)):
            self.skipTest("the stock games are not in inputs\\")

    def test_every_game_every_choice_only_the_backup_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for game in (1, 2, 3, 4, 5):
                title = se.EXE[game][:-4]
                folder = Path(tmp) / f"{title} - Modded"
                folder.mkdir()
                if isinstance(clock.GAMES[game], clock.ClockGame):
                    live = se.pressed_after_tick(game, se.FIXTURE[game], 6, 999, 2)   # once refused
                else:
                    live = se.running(game, se.FIXTURE[game], 6)
                (folder / f"{title}1.ldw").write_bytes(live)
                os.utime(folder / f"{title}1.ldw", ns=(1_700_000_000 * 10**9, 1_700_000_000 * 10**9))
                made = backup.copy_save_folder(folder)
                other = backup.copy_save_folder(folder, suffix=" (before something)")
                copy = made.backup_folder / f"{title}1.ldw"
                untouched = (other.backup_folder / f"{title}1.ldw").read_bytes()
                for choice, want in (("fast", 3), ("slow", 10), ("normal", 6), ("paused", 1005)):
                    with self.subTest(game=game, choice=choice):
                        before = copy.read_bytes()
                        mtime = copy.stat().st_mtime_ns
                        done = backup.set_backup_speed(folder, made.backup_folder, choice)
                        after = copy.read_bytes()
                        self.assertEqual(backup.save_speed(game, after)[1], want)
                        self.assertEqual(done.changed, [(copy.name, backup.save_speed(game, before)[1], want)])
                        header = backup._save_header(game, before)
                        value = backup.save_speed(game, before)[1]
                        self.assertEqual(after, clock.edit_speed(game, before, header, want % 999, want >= 999))
                        self.assertEqual(after, se.stock_edit(game, before, want % 999, want >= 999))
                        self.assertNotEqual(value, want)
                        self.assertLessEqual(abs(copy.stat().st_mtime_ns - mtime), 2_000_000_000)
                        # The live save and the other backup are exactly as they were.
                        self.assertEqual((folder / f"{title}1.ldw").read_bytes(), live)
                        self.assertEqual((other.backup_folder / f"{title}1.ldw").read_bytes(), untouched)
                again = backup.set_backup_speed(folder, made.backup_folder, "paused")
                self.assertEqual((again.changed, again.already), ([], [copy.name]))

    def test_a_folder_that_is_not_one_of_its_backups_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            title = se.EXE[4][:-4]
            folder = Path(tmp) / f"{title} - Modded 256"
            folder.mkdir()
            data = se.running(4, se.FIXTURE[4], 6)
            (folder / f"{title}1.ldw").write_bytes(data)
            for not_a_backup in (folder, Path(tmp)):
                with self.assertRaises(backup.BackupError):
                    backup.set_backup_speed(folder, not_a_backup, "fast")
            self.assertEqual((folder / f"{title}1.ldw").read_bytes(), data)


class OnlyANonSaveIsRefused(unittest.TestCase):
    def test_a_file_that_is_not_the_games_save_is_refused_and_left(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for game in (1, 2, 3, 4, 5):
                title = se.EXE[game][:-4]
                path = Path(tmp) / f"{title}1.ldw"
                path.write_bytes(b"not a save at all")
                with self.assertRaises(backup.BackupError):
                    backup.set_speed_choice(game, path, "normal", NoGames())
                self.assertEqual(path.read_bytes(), b"not a save at all")


if __name__ == "__main__":
    unittest.main()
