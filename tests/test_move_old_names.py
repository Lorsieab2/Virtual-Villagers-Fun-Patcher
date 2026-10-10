"""Repair Saves & Logs' "Move Old Files to New Names..." (src/vv_move_old_names.py; the owner,
2026-10-09: "Repair logs should have the move legacy files button!").

Only on the player's say-so, with the game closed, after a backup: everything under an older
build's name goes to its new name; under both names the logs are combined as the readers already
combine them (the Deaths logs' records counted once, the smaller like / dislike word boundary), a
whole file keeps the one written last, and whatever is superseded is set aside in "Copies Made
Before Repairs", never deleted.  Backups, Tribe History and Tribe Population are never touched.
Every folder here is built in a temporary folder."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_log_tools as tools  # noqa: E402
import vv_move_old_names as mv  # noqa: E402
import vv_save_backup as backup  # noqa: E402
import vv_save_layout as layout  # noqa: E402

DATA, LOGS, TREES = layout.DATA, layout.LOGS, layout.TREES
COPIES = f"{DATA}/{layout.COPIES}"
NOW = datetime(2026, 10, 9, 20, 0, 0)
OLD_TIME = 1_700_000_000 * 10**9
NEW_TIME = 1_800_000_000 * 10**9
HISTORY = f"{LOGS}\\Tribe History\\Village History 1.txt"


class Processes:
    def __init__(self, pids=()):
        self.pids = list(pids)

    def find(self, exe_name):
        return list(self.pids)


def write(path: Path, data: str | bytes, when: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data.encode("latin-1") if isinstance(data, str) else data)
    if when is not None:
        os.utime(path, ns=(when, when))


def tree(folder: Path, under: str = "") -> dict[str, bytes]:
    root = folder / under if under else folder
    return {p.relative_to(folder).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


class MoveTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self._tmp.name) / "Virtual Villagers - A New Home - Modded"
        f = self.folder
        write(f / "VirtualVillagers1.ldw", b"save")
        write(f / LOGS / "Tribe History" / "Village History 1.txt", "Village: Hut (Save 1)\r\nday 1\r\n")
        write(f / LOGS / "Tribe Population" / "Population 1.txt", "Village: Hut (Save 1)\r\n")
        write(f / "Backups" / "Backup 2026-01-01 00-00-00" / LOGS / "Deaths" / "Virtual Villagers 1 Deaths Log 1.txt",
              "an old backup")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def move(self, **kwargs) -> mv.MoveResult:
        return mv.move_old_files(self.folder, kwargs.pop("processes", Processes()), NOW, **kwargs)

    def kept_apart(self) -> dict[str, bytes]:
        return {k: v for k, v in tree(self.folder).items()
                if k.startswith(("Backups/Backup 2026-01-01", f"{LOGS}/Tribe History", f"{LOGS}/Tribe Population"))}

    def test_only_old_names_are_moved_into_place(self) -> None:
        f = self.folder
        write(f / LOGS / "Deaths" / "Virtual Villagers 1 Deaths Log 1.txt", "Village: Hut (Save 1)\r\nDeath 1\r\n  Name: Ana\r\n\r\n")
        write(f / LOGS / "Repairs" / "Virtual Villagers 1 Repairs Log 1.txt", "Village: Hut (Save 1)\r\nRepair 1\r\n\r\n")
        write(f / LOGS / "Genealogy" / "Virtual Villagers 1 Genealogy - Save 1.txt", "report")
        write(f / DATA / "Log Words" / "Virtual Villagers 1 Log Words.dat", f"0\t{HISTORY}\r\n")
        write(f / DATA / "Cross-Check" / "Virtual Villagers 1 Cross-Check - Save 1.dat", b"marker")
        write(f / DATA / "Parentage Records" / "Virtual Villagers 1 Parentage Records - Save 1.dat", b"parents")
        write(f / DATA / "Genealogy" / "Virtual Villagers 1 Genealogy Edits - Save 1.json", "{}")
        write(f / DATA / "Unaccounted Villagers" / "Virtual Villagers 1 Village Roster - Save 1.dat", b"roster")
        write(f / DATA / "Village Statistics" / "Village Roster - Save 1.dat", b"counted")
        apart = self.kept_apart()
        checker = tools.load_checker()
        deaths = checker.deaths_records(f, 1, 1)
        result = self.move()
        self.assertEqual(len(result.moved), 9)
        expect = {
            f"{LOGS}/Deaths and Disappearances/Virtual Villagers 1 Deaths Log 1.txt",
            f"{LOGS}/Repairs Made/Virtual Villagers 1 Repairs Log 1.txt",
            f"{TREES}/Reports/Virtual Villagers 1 Genealogy - Save 1.txt",
            f"{DATA}/Like and Dislike Words/Virtual Villagers 1 Log Words.dat",
            f"{DATA}/Log Checks/Virtual Villagers 1 Cross-Check - Save 1.dat",
            f"{DATA}/Parents (A New Home)/Virtual Villagers 1 Parentage Records - Save 1.dat",
            f"{DATA}/Family Tree Edits/Virtual Villagers 1 Family Tree Edits - Save 1.json",
            f"{DATA}/Unaccounted Villagers/Virtual Villagers 1 Villagers at Last Save - Save 1.dat",
            f"{DATA}/Village Statistics/Villagers Counted - Save 1.dat",
        }
        now = tree(f)
        self.assertLessEqual(expect, set(now))
        for old in (f"{LOGS}/Deaths", f"{LOGS}/Repairs", f"{LOGS}/Genealogy", f"{DATA}/Log Words", f"{DATA}/Cross-Check",
                    f"{DATA}/Parentage Records", f"{DATA}/Genealogy"):
            self.assertFalse((f / old).exists(), old)
        self.assertEqual(now[f"{DATA}/Parents (A New Home)/Virtual Villagers 1 Parentage Records - Save 1.dat"], b"parents")
        self.assertEqual(checker.deaths_records(f, 1, 1), deaths)
        self.assertEqual(self.kept_apart(), apart)                 # Backups, Tribe History, Tribe Population
        self.assertEqual(result.backup.backup_folder.name, "Backup 2026-10-09 20-00-00 (before repair re-arm)")
        # One record in the Repairs Made log, in the Repair tool's own shape.
        log = (f / LOGS / "Repairs Made" / "Virtual Villagers 1 Repairs Log 1.txt").read_bytes().decode("latin-1")
        self.assertIn("Village: (all villages in this save folder)\r\nRepair 2\r\n  Date: 2026-10-09 20:00:00\r\n"
                      "  Checked: the patcher's files kept under older builds' names", log)
        self.assertIn(f"  Moved: {DATA}\\Parentage Records -> {DATA}\\Parents (A New Home)\r\n", log)
        self.assertIn("  Backup: Backup 2026-10-09 20-00-00 (before repair re-arm)\r\n", log)
        # A second click finds nothing to move, and changes nothing.
        self.assertEqual(mv.plan(f), [])
        before = tree(f)
        again = self.move()
        self.assertIsNone(again.backup)
        self.assertEqual(tree(f), before)

    def test_deaths_logs_under_both_names_are_combined_each_record_once(self) -> None:
        f = self.folder
        shared = "Death 1\r\n  Name: Ana\r\n"
        write(f / LOGS / "Deaths and Disappearances" / "Virtual Villagers 1 Deaths Log 1.txt",
              f"Village: Hut (Save 1)\r\n{shared}\r\nDeath 2\r\n  Name: Bo\r\n\r\n", OLD_TIME)
        write(f / LOGS / "Deaths" / "Virtual Villagers 1 Deaths Log 1.txt",
              f"Village: Hut (Save 1)\r\n{shared}\r\nDeath 3\r\n  Name: Cy\r\n\r\n", NEW_TIME)
        write(f / LOGS / "Deaths" / "Virtual Villagers 1 Deaths Log 2.txt",
              "Village: Hut (Save 1)\r\nDeath 4\r\n  Name: Di\r\n\r\n", NEW_TIME)
        checker = tools.load_checker()
        records = sorted(checker.deaths_records(f, 1, 1))
        self.assertEqual(len(records), 4)
        new_before = (f / LOGS / "Deaths and Disappearances" / "Virtual Villagers 1 Deaths Log 1.txt").read_bytes()
        result = self.move()
        self.assertFalse((f / LOGS / "Deaths").exists())
        merged = (f / LOGS / "Deaths and Disappearances" / "Virtual Villagers 1 Deaths Log 1.txt").read_bytes()
        self.assertTrue(merged.startswith(new_before))             # the new log's bytes kept as they were
        self.assertEqual(merged.count(b"Name: Ana"), 1)
        self.assertIn(b"Death 3\r\n  Name: Cy", merged)
        self.assertEqual(sorted(checker.deaths_records(f, 1, 1)), records)
        self.assertIn(f"{LOGS}\\Deaths\\Virtual Villagers 1 Deaths Log 1.txt + {LOGS}\\Deaths and Disappearances\\"
                      "Virtual Villagers 1 Deaths Log 1.txt (1 record(s) added)", result.combined)
        # Nothing deleted: the old log and the new one as it was are in Copies Made Before Repairs.
        copies = tree(f, COPIES)
        self.assertEqual(copies[f"{COPIES}/{LOGS}/Deaths/Virtual Villagers 1 Deaths Log 1.txt"][:21], b"Village: Hut (Save 1)")
        self.assertEqual(copies[f"{COPIES}/{LOGS}/Deaths and Disappearances/Virtual Villagers 1 Deaths Log 1.txt"],
                         new_before)

    def test_logs_that_would_read_differently_are_left_under_both_names(self) -> None:
        # The old folder's records belong to a different, later village in the slot: put after the new
        # log's, they would hide the new folder's village from every reader -- so nothing is done.
        f = self.folder
        write(f / LOGS / "Deaths and Disappearances" / "Virtual Villagers 1 Deaths Log 1.txt",
              "Village: Hut (Save 1)\r\nDeath 1\r\n  Name: Ana\r\n\r\n")
        write(f / LOGS / "Deaths" / "Virtual Villagers 1 Deaths Log 1.txt",
              "Village: Cave (Save 1)\r\nDeath 1\r\n  Name: Bo\r\n\r\n")
        before = tree(f, LOGS)
        result = self.move()
        self.assertEqual({k: v for k, v in tree(f, LOGS).items() if "/Repairs Made/" not in k}, before)
        self.assertTrue(any("would change what the logs show" in line for line in result.left))

    def test_like_and_dislike_words_under_both_names_keep_the_smaller_boundary(self) -> None:
        f = self.folder
        other = f"{LOGS}\\Births and Conceptions\\Virtual Villagers 1 Births and Conceptions Log 1.txt"
        write(f / DATA / "Like and Dislike Words" / "Virtual Villagers 1 Log Words.dat",
              f"0\t{HISTORY}\r\n500\t{other}\r\n", OLD_TIME)
        write(f / DATA / "Log Words" / "Virtual Villagers 1 Log Words.dat",
              f"1763792\t{HISTORY}\r\n90\t{other}\r\n", NEW_TIME)
        checker = tools.load_checker()
        bounds = checker.word_boundaries(f, 1)
        self.assertEqual(bounds, {HISTORY.lower(): 0, other.lower(): 90})
        self.move()
        self.assertFalse((f / DATA / "Log Words").exists())
        self.assertEqual(checker.word_boundaries(f, 1), bounds)
        self.assertIn(f"{COPIES}/{DATA}/Log Words/Virtual Villagers 1 Log Words.dat", tree(f, COPIES))

    def test_a_whole_file_under_both_names_keeps_the_one_written_last(self) -> None:
        f = self.folder
        new = f / DATA / "Unaccounted Villagers" / "Virtual Villagers 1 Villagers at Last Save - Save 1.dat"
        old = f / DATA / "Unaccounted Villagers" / "Virtual Villagers 1 Village Roster - Save 1.dat"
        write(new, b"14:13", OLD_TIME)
        write(old, b"15:21", NEW_TIME)                            # the older build's, written last
        parents_new = f / DATA / "Parents (A New Home)" / "Virtual Villagers 1 Parentage Records - Save 1.dat"
        parents_old = f / DATA / "Parentage Records" / "Virtual Villagers 1 Parentage Records - Save 1.dat"
        write(parents_new, b"the real parents", NEW_TIME)
        write(parents_old, b"older parents", OLD_TIME)
        chosen = [layout.find(f, f"{DATA}\\Unaccounted Villagers\\{new.name}").read_bytes(),
                  layout.find(f, f"{DATA}\\Parents (A New Home)\\{parents_new.name}").read_bytes()]
        self.move()
        self.assertEqual([new.read_bytes(), parents_new.read_bytes()], chosen)
        self.assertEqual(chosen, [b"15:21", b"the real parents"])
        self.assertFalse(old.exists())
        self.assertFalse((f / DATA / "Parentage Records").exists())
        copies = tree(f, COPIES)
        self.assertEqual(copies[f"{COPIES}/{DATA}/Unaccounted Villagers/{new.name}"], b"14:13")
        self.assertEqual(copies[f"{COPIES}/{DATA}/Parentage Records/{parents_old.name}"], b"older parents")

    def test_an_approval_under_both_names_is_kept_under_neither(self) -> None:
        f = self.folder
        name = "Virtual Villagers 1 Repair Approved - Save 1.dat"
        write(f / DATA / "Log Checks" / name, tools.approval_bytes(1, 1))
        write(f / DATA / "Cross-Check" / name, tools.approval_bytes(1, 1))
        result = self.move()
        self.assertFalse((f / DATA / "Log Checks" / name).exists())
        self.assertFalse((f / DATA / "Cross-Check").exists())
        self.assertEqual(len([k for k in tree(f, COPIES) if k.endswith(name)]), 2)
        self.assertTrue(any("acts on neither" in line for line in result.left))

    def test_empty_old_folders_are_removed(self) -> None:
        f = self.folder
        for old, new in ((f"{DATA}/Parentage Records", f"{DATA}/Parents (A New Home)"), (f"{LOGS}/Repairs", f"{LOGS}/Repairs Made")):
            (f / old).mkdir(parents=True)
            write(f / new / "x.dat", b"x")
        (f / DATA / "Genealogy").mkdir()
        self.assertEqual({i.kind for i in mv.plan(f)}, {"remove empty"})
        result = self.move()
        self.assertEqual(sorted(result.removed), sorted([f"{DATA}\\Parentage Records", f"{LOGS}\\Repairs", f"{DATA}\\Genealogy"]))
        self.assertEqual(mv.plan(f), [])

    def test_a_running_game_is_refused_and_nothing_changes(self) -> None:
        write(self.folder / LOGS / "Deaths" / "Virtual Villagers 1 Deaths Log 1.txt", "Village: Hut (Save 1)\r\n")
        before = tree(self.folder)
        with self.assertRaises(tools.GameRunning) as caught:
            self.move(processes=Processes([7]))
        self.assertIn("Moving old files never pauses or closes", str(caught.exception))
        self.assertEqual(tree(self.folder), before)

    def test_a_failed_backup_moves_nothing(self) -> None:
        write(self.folder / LOGS / "Deaths" / "Virtual Villagers 1 Deaths Log 1.txt", "Village: Hut (Save 1)\r\n")
        before = tree(self.folder)
        with mock.patch.object(backup, "copy_save_folder", side_effect=backup.BackupError("disk full")):
            with self.assertRaises(mv.MoveError) as caught:
                self.move()
        self.assertIn("The backup failed, so nothing was moved", str(caught.exception))
        self.assertEqual(tree(self.folder), before)

    def test_an_error_midway_stops_and_says_what_moved(self) -> None:
        f = self.folder
        write(f / LOGS / "Deaths" / "Virtual Villagers 1 Deaths Log 1.txt", "Village: Hut (Save 1)\r\n")
        write(f / DATA / "Parentage Records" / "Virtual Villagers 1 Parentage Records - Save 1.dat", b"p")
        real = mv._rename
        calls = []

        def failing(source, target):
            calls.append(source)
            if len(calls) == 2:
                raise PermissionError("locked")
            return real(source, target)

        with mock.patch.object(mv, "_rename", failing):
            with self.assertRaises(mv.MoveError) as caught:
                self.move()
        text = str(caught.exception)
        self.assertIn(f"Moved: {LOGS}\\Deaths -> {LOGS}\\Deaths and Disappearances", text)
        self.assertIn("locked", text)
        self.assertTrue((f / DATA / "Parentage Records" / "Virtual Villagers 1 Parentage Records - Save 1.dat").is_file())

    def test_a_game_patched_before_v1_35_64_is_refused(self) -> None:
        f = self.folder
        write(f / LOGS / "Deaths" / "Virtual Villagers 1 Deaths Log 1.txt", "Village: Hut (Save 1)\r\n")
        games = Path(self._tmp.name) / "Games"
        game = games / f.name
        write(game / f"{f.name}.exe", b"MZ")
        report = game / "Virtual Villagers Fun Patcher Files" / "VVFP Transparency Log.txt"
        write(report, "Patcher version/commit: v1.35.63 / abc\n")
        patched = mv.patched_by(f, [games / "elsewhere", game])
        self.assertEqual(patched.version, (1, 35, 63))
        self.assertTrue(patched.refused)
        before = tree(f)
        with self.assertRaises(mv.MoveError) as caught:
            self.move(patched=patched)
        self.assertIn("v1.35.63", str(caught.exception))
        self.assertEqual(tree(f), before)
        write(report, "Patcher version/commit: v1.35.64 / abc\n")
        self.assertFalse(mv.patched_by(f, [game]).refused)
        # No report: the patch files say which names the game knows.
        report.unlink()
        write(game / "Virtual Villagers Fun Patcher Files" / "VVFP VV1 Parentage.dll", "x Parentage Records y".encode("utf-16-le"))
        self.assertTrue(mv.patched_by(f, [game]).refused)
        write(game / "Virtual Villagers Fun Patcher Files" / "VVFP Cause of Death.dll", b"Deaths and Disappearances")
        self.assertFalse(mv.patched_by(f, [game]).refused)
        # The game cannot be found: not refused, only warned about.
        unknown = mv.patched_by(f, [])
        self.assertIsNone(unknown.game_folder)
        self.assertFalse(unknown.refused)

    def test_only_the_patchers_own_folders_are_listed(self) -> None:
        f = self.folder
        write(f / LOGS / "Deaths" / "Virtual Villagers 1 Deaths Log 1.txt", "Village: Hut (Save 1)\r\n")
        for item in mv.plan(f):
            self.assertTrue(item.old.startswith((LOGS, DATA)), item.old)
            self.assertNotIn("Backups", item.old)


if __name__ == "__main__":
    unittest.main()
