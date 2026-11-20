"""Paths of 260 characters or more in the save folders (the owner, 2026-11-20: "no path-too-long errors").

Most players' Windows refuses a path of 260 characters or more (long paths are off).  These tests turn that
refusal on for every plain path, whatever this machine allows (`MaxPath`), and build a save folder whose
older builds' copies ("Copies Made Before Repairs") and backups run past 259 characters.  Back Up Saves
copies, lists, restores and deletes them; Repair Saves & Logs and Check Saves & Logs run beside them; and
every new copy kept before a repair has a short name that fits the budget (src/vv_repair_copies.py).
Nothing a player already has is renamed, moved or deleted."""
from __future__ import annotations

import builtins
import io
import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv1_parents_restore as parents  # noqa: E402
import vv_log_tools as tools  # noqa: E402
import vv_long_paths as lp  # noqa: E402
import vv_reconcile as rc  # noqa: E402
import vv_repair_copies as copies  # noqa: E402
import vv_save_backup as backup  # noqa: E402
import vv_save_layout as layout  # noqa: E402
import test_log_tools as tl  # noqa: E402

WINDOWS = os.name == "nt"
NOW = datetime(2026, 11, 20, 12, 0, 0)
DATA = layout.DATA
LOGS = layout.LOGS
COPIES = layout.COPIES

# The owner's own folders hold these (names from his save folders, 2026-11-20), nested deeper here.
OLD_COPIES = (
    f"{DATA}\\{COPIES}\\{LOGS}\\Save 1\\Births and Conceptions\\"
    "Virtual Villagers 1 Births and Conceptions Log 1.txt.before-rename-records-20261014-000007",
    f"{DATA}\\{COPIES}\\{DATA}\\Parents (A New Home)\\"
    "Virtual Villagers 1 Parentage Records - Save 1.dat.before-v1.35.58-repair-4 (before move to save folder)",
    f"{layout.SAVES}\\Save 1\\Data\\{COPIES}\\Data\\Parents (A New Home)\\"
    "Virtual Villagers 1 Parentage Records - Save 1.dat.before-parents-restore",
)


class MaxPath:
    """Windows with long paths turned off: every plain path of 260 characters or more is refused, as the
    file APIs refuse it (the extended-length "\\\\?\\" form is taken at any length)."""

    LIMIT = 259

    def __init__(self) -> None:
        self.refused: list[str] = []
        self._patches: list = []

    def _long(self, value) -> bool:
        if isinstance(value, int) or value is None:
            return False
        try:
            text = os.fsdecode(os.fspath(value))
        except TypeError:
            return False
        if text.startswith("\\\\?\\"):
            return False
        return len(os.path.abspath(text)) > self.LIMIT

    def _guard(self, function, answer=None):
        def guarded(*args, **kwargs):
            for value in list(args[:2]) + [kwargs.get(k) for k in ("src", "dst", "path", "file")]:
                if self._long(value):
                    self.refused.append(os.fsdecode(os.fspath(value)))
                    if answer is not None:
                        return answer
                    raise FileNotFoundError(3, "The system cannot find the path specified (MAX_PATH)",
                                            os.fsdecode(os.fspath(value)))
            return function(*args, **kwargs)
        return guarded

    def __enter__(self) -> "MaxPath":
        for name in ("stat", "lstat", "scandir", "listdir", "mkdir", "rmdir", "unlink", "remove", "rename",
                     "replace", "utime", "chmod", "open"):
            self._patches.append(mock.patch.object(os, name, self._guard(getattr(os, name))))
        for name in ("isdir", "isfile", "exists", "lexists", "islink"):
            self._patches.append(mock.patch.object(os.path, name, self._guard(getattr(os.path, name), False)))
        self._patches.append(mock.patch.object(builtins, "open", self._guard(builtins.open)))
        self._patches.append(mock.patch.object(io, "open", self._guard(io.open)))
        for p in self._patches:
            p.start()
        return self

    def __exit__(self, *exc) -> None:
        for p in reversed(self._patches):
            p.stop()
        self._patches.clear()


def put(path: Path, data: bytes) -> Path:
    lp.makedirs(path.parent)
    lp.extended(path).write_bytes(data)
    return path


def every_file(folder: Path) -> dict[str, bytes]:
    return {str(p.relative_to(folder)): lp.read_bytes(p) for p in lp.walk(folder)}


@unittest.skipUnless(WINDOWS, "Windows paths")
class LongSaveFolder(tl.FolderTest):
    """A New Home's save folder, deep enough that the older builds' copies run past 259 characters."""

    OLD = tl.LogWordsTests.OLD
    NEW = tl.LogWordsTests.NEW

    def setUp(self) -> None:
        super().setUp()
        self.folder = self.make_folder("huttest", 1, "Modded")
        self.write(self.folder, tl.HISTORY, self.OLD + self.NEW)
        self.write(self.folder, tl.WORDS_DAT.format(game=1),
                   f"{len(self.OLD)}\tVirtual Villagers Fun Patcher Logs\\Tribe History\\Village History.txt\r\n".encode())
        self.old = {rel: put(self.folder / rel, f"older copy {k}".encode()) for k, rel in enumerate(OLD_COPIES)}
        for path in self.old.values():
            self.assertTrue(lp.too_long(path), f"{len(str(path))} characters: {path}")

    def tearDown(self) -> None:
        lp.rmtree(self._tmp.name)
        super().tearDown()

    def assert_old_copies_as_they_were(self) -> None:
        for k, path in enumerate(self.old.values()):
            self.assertEqual(lp.read_bytes(path), f"older copy {k}".encode(), "never renamed, moved or changed")

    def test_the_simulation_refuses_a_long_plain_path(self) -> None:
        path = next(iter(self.old.values()))
        with MaxPath() as limit:
            with self.assertRaises(OSError):
                path.read_bytes()
            self.assertFalse(path.is_file())
            self.assertEqual(lp.read_bytes(path), b"older copy 0")
        self.assertTrue(limit.refused)

    def test_back_up_list_restore_and_delete(self) -> None:
        with MaxPath():
            before = every_file(self.folder)
            listed = backup.files_to_back_up(self.folder)
            self.assertEqual({str(p) for p in listed},
                             {k for k in before if not k.startswith("Backups\\")})
            made = backup.copy_save_folder(self.folder, NOW)
            # The backup's folder has a short name; its date and label are in the Backups index.
            self.assertEqual(made.backup_folder.name, "2026-11-20 1200")
            # Nothing in the backup runs past 259: a long file is kept under a short name in its Long Paths
            # folder, at its own place for the list and the restore.
            for p in lp.walk(made.backup_folder):
                self.assertFalse(lp.too_long(p), str(p))
            copied = {str(k): lp.read_bytes(v) for k, v in backup.backup_contents(made.backup_folder).items()}
            self.assertEqual(set(copied), {str(p) for p in listed})
            for rel in OLD_COPIES:
                self.assertEqual(copied[rel], before[rel], "the long copy is in the backup, byte for byte")
            [info] = [i for i in backup.list_backups(self.folder) if i.path == made.backup_folder]
            self.assertEqual(info.file_count, len(listed))
            self.assertEqual((info.when, info.suffix), (NOW, ""))
            # The long files change and go; the restore puts them back.
            first = self.old[OLD_COPIES[0]]
            lp.extended(first).write_bytes(b"changed")
            lp.unlink(self.old[OLD_COPIES[1]])
            result = backup.restore_backup(self.folder, made.backup_folder, processes=tl.FakeProcesses(), now=NOW)
            self.assertTrue(result.plan.changes)
            self.assert_old_copies_as_they_were()
            # ...and the backup is deleted, every long path in it with it.
            backup.delete_backup(self.folder, made.backup_folder)
            self.assertFalse(lp.exists(made.backup_folder))
            self.assertFalse(lp.exists(made.backup_folder.with_name(made.backup_folder.name + backup.DELETING)))
            self.assert_old_copies_as_they_were()

    def test_repair_check_and_restore_parents_beside_long_copies(self) -> None:
        with MaxPath() as limit:
            result = tools.approve_repair(self.folder, 1, 1, tl.FakeProcesses(), NOW)
            self.assertEqual([w.count for w in result.words], [2])
            # The copy it made: a short name in Copies Made Before Repairs, the index naming the log.
            made = copies.kept_copies(self.folder, self.folder / tl.HISTORY)[0]     # the first it made
            self.assertEqual(made, self.folder / DATA / COPIES / "Village History.txt.bak1")
            self.assertEqual(made.read_bytes(), self.OLD + self.NEW)
            self.assertFalse(lp.too_long(made))
            # The backup Repair made first holds the long copies too.
            backups = backup.list_backups(self.folder)
            self.assertTrue(backups)
            held = backup.backup_contents(backups[0].path)
            self.assertTrue(all(lp.is_file(held[Path(rel)]) for rel in OLD_COPIES))
            self.assertFalse(any(lp.too_long(p) for p in lp.walk(backups[0].path)))
            self.assertEqual(backups[0].suffix, tools.BACKUP_LABEL)
            # Check Saves & Logs' reading of the copies: the long ones and the new one, at any length.
            log = self.folder / LOGS / "Save 1" / "Births and Conceptions" / \
                "Virtual Villagers 1 Births and Conceptions Log 1.txt"
            put(log, b"Village: Hut (Save 1)\r\n\r\n")
            found = rc._copies_of(log, self.folder / DATA / COPIES, self.folder)
            self.assertIn(self.old[OLD_COPIES[0]], found)
            # Restore A New Home Parents lists the long copies of the parents file.
            listed = parents.copies(self.folder, 1)
            self.assertIn(self.old[OLD_COPIES[1]], listed)
            self.assertIn(self.old[OLD_COPIES[2]], listed)
        self.assertTrue(limit.refused is not None)
        self.assert_old_copies_as_they_were()

    def test_a_folder_that_cannot_be_listed_is_said_never_skipped(self) -> None:
        errors: list[str] = []
        real = os.scandir

        def refusing(path):
            if "Births and Conceptions" in os.fsdecode(os.fspath(path)):
                raise PermissionError(5, "Access is denied")
            return real(path)
        with mock.patch.object(os, "scandir", refusing):
            files = list(lp.walk(self.folder, errors=errors))
            self.assertTrue(files)
            self.assertTrue(any("Births and Conceptions could not be listed" in e for e in errors), errors)
            with self.assertRaises(PermissionError):
                backup.files_to_back_up(self.folder)


class Budget(unittest.TestCase):
    """Every new copy kept before a repair fits: a short name, at most COPY_RELATIVE_MAX characters inside
    the save folder -- no longer than the patcher's own longest file there."""

    def patcher_files(self) -> list[str]:
        out = []
        for game in range(1, 6):
            for slot in range(1, 6):
                own = f"{layout.SAVES}\\Save {slot}"
                for sub, stem in (("Births and Conceptions", f"Virtual Villagers {game} Births and Conceptions Log"),
                                  ("Deaths and Disappearances", f"Virtual Villagers {game} Deaths Log"),
                                  ("Unaccounted Villagers", f"Virtual Villagers {game} Unaccounted Villagers Log"),
                                  ("Island Events", f"Virtual Villagers {game} Island Events Log"),
                                  ("Repairs Made", f"Virtual Villagers {game} Repairs Log"),
                                  ("Tribe History", "Village History"), ("Tribe Population", "Village Population")):
                    for n in (1, 9):
                        out.append(f"{own}\\{layout.SAVE_LOGS}\\{sub}\\{stem} {n}.txt")
                        out.append(f"{LOGS}\\Save {slot}\\{sub}\\{stem} {n}.txt")
                for sub, name in (("Parents (A New Home)", f"Virtual Villagers 1 Parentage Records - Save {slot}.dat"),
                                  ("Unaccounted Villagers", f"Virtual Villagers {game} Villagers at Last Save - Save {slot}.dat"),
                                  ("Family Tree Edits", f"Virtual Villagers {game} Family Tree Edits - Save {slot}.json"),
                                  ("Village Statistics", f"Villagers Counted - Save {slot}.dat"),
                                  ("Custom Titles", f"Custom Titles - Save {slot}.dat"),
                                  ("Like and Dislike Words", f"Virtual Villagers {game} Log Words.dat")):
                    out.append(f"{own}\\{layout.SAVE_DATA}\\{sub}\\{name}")
                    out.append(f"{DATA}\\{sub}\\{name}")
                for title in ("Virtual Villagers", "Virtual Villagers - The Lost Children",
                              "Virtual Villagers - The Secret City", "Virtual Villagers - The Tree of Life",
                              "Virtual Villagers - New Believers"):
                    out += [f"{title}{slot}.ldw", f"{title}{slot + 20}.ldw", f"{title}{slot + 40}.ldw"]
        return out

    def test_every_copy_fits_the_budget(self) -> None:
        longest_own = len(f"{layout.SAVES}\\Save 1\\{layout.SAVE_LOGS}\\Births and Conceptions\\"
                          "Virtual Villagers 3 Births and Conceptions Log 1.txt")
        self.assertLessEqual(copies.COPY_RELATIVE_MAX, longest_own)
        for original in self.patcher_files() + ["x" * 200 + ".dat", "Some Unusually Long Custom Family Tree "
                                                "Name Of The Kalahuna Tribe - Save 3.vvtree"]:
            with self.subTest(original=original):
                place = copies.copy_relative(original)
                self.assertLessEqual(len(place), copies.COPY_RELATIVE_MAX, place)
                self.assertNotIn("Virtual Villagers 1 ", place.rpartition("\\")[2])
        # A save folder of 142 characters (a long Documents folder, the longest game title and a long
        # copy's name): every new copy is under 260.
        save_folder = "C:\\Users\\A Player With A Long Name\\OneDrive - Household\\Documents\\LDW\\" \
                      "Virtual Villagers - The Tree of Life - Modded 256 Test"
        self.assertLessEqual(len(save_folder) + 1 + copies.COPY_RELATIVE_MAX, 259)

    def test_every_backed_up_file_fits_the_budget(self) -> None:
        """Back Up Saves: a backup's folder is "Backups\\<yyyy-mm-dd hhmm>[ <n>]" (Copy Player Slot's replaced
        files "Backups\\<yyyy-mm-dd hhmm> S<slot>[ <n>]"): the patcher's deepest file (118 characters) is at
        most 148 deep there.  And a file that would still run past 259 in a backup (an older build's long
        copy) is kept under "Long Paths (Fun Patcher)\\<n> <name, at most 40>": at most 100 deep."""
        when = datetime(2026, 11, 20, 23, 59)
        deepest = len(f"{layout.SAVES}\\Save 1\\{layout.SAVE_LOGS}\\Births and Conceptions\\"
                      "Virtual Villagers 3 Births and Conceptions Log 1.txt")
        backup_dir = len(f"{backup.BACKUPS_FOLDER}\\{backup.short_backup_name(when, 999)}\\")
        aside_dir = len(f"{backup.BACKUPS_FOLDER}\\{when:%Y-%m-%d %H%M} S5 999\\")
        self.assertLessEqual(backup_dir + deepest, 148)
        self.assertLessEqual(aside_dir + deepest, 148)
        stored = backup._long_path_name(999999, "Virtual Villagers 1 " + "x" * 300 + ".dat")
        self.assertLessEqual(len(stored), 47)
        long_place = backup_dir + len(backup.LONG_PATHS) + 1 + len(stored)
        self.assertLessEqual(long_place, 100)
        # The owner's longest save folder (OneDrive Documents, "... Modded 256 LiveCheck97 IF NoBC") fits
        # every backed-up file of the patcher's own; any save folder up to 158 characters fits the Long Paths.
        owners = "C:\\Users\\Owner\\OneDrive\\Documents\\LDW\\" \
                 "Virtual Villagers - The Tree of Life - Modded 256 LiveCheck97 IF NoBC"
        self.assertLessEqual(len(owners) + 1 + backup_dir + deepest, 259)
        self.assertLessEqual(158 + 1 + long_place, 259)

    def test_short_names_stay_readable(self) -> None:
        self.assertEqual(copies.short_name("Virtual Villagers 1 Parentage Records - Save 1.dat"),
                         "Parentage Records - Save 1.dat")
        self.assertEqual(copies.short_name("Virtual Villagers - The Tree of Life21.ldw"), "The Tree of Life21.ldw")
        self.assertEqual(copies.short_name("Village History 1.txt"), "Village History 1.txt")
        long = copies.short_name("Some Unusually Long Custom Family Tree Name Of The Kalahuna Tribe - Save 3.vvtree")
        self.assertLessEqual(len(long), copies.SHORT_MAX)
        self.assertTrue(long.endswith(".vvtree"))
        self.assertEqual(copies.reason_of(".before-parents-restore-12"), "before-parents-restore")
        self.assertEqual(copies.reason_of(" (before move to save folder)-3"), "before move to save folder")
        self.assertEqual(copies.reason_of(f".before-{tools.PATCHER_VERSION}-repair"),
                         f"before-{tools.PATCHER_VERSION}-repair")
        self.assertEqual(copies.reason_of(""), "set aside")

    def test_new_copies_are_numbered_and_indexed_never_replacing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            log = put(folder / layout.SAVES / "Save 2" / "Logs" / "Tribe History" / "Village History 1.txt", b"v")
            first = tools.copy_before_repair(folder, log, ".before-history-revision")
            first.write_bytes(b"1")
            second = tools.copy_before_repair(folder, log, ".before-history-revision-2")
            self.assertEqual((first.name, second.name), ("Village History 1.txt.bak1", "Village History 1.txt.bak2"))
            # A copy not written leaves a line, never a file: the next number is still new.
            third = tools.copy_before_repair(folder, log, ".before-undelete")
            self.assertEqual(third.name, "Village History 1.txt.bak3")
            third.write_bytes(b"3")
            self.assertEqual(copies.kept_copies(folder, log), [first, third])
            self.assertEqual(copies.kept_copies(folder, log, ".before-undelete"), [third])
            index = (first.parent / copies.INDEX).read_text("utf-8")
            self.assertTrue(index.startswith("# "))
            self.assertIn("Village History 1.txt.bak1\tVirtual Villagers Fun Patcher\\Save 2\\Logs\\Tribe History\\"
                          "Village History 1.txt\tbefore-history-revision\t", index)


if __name__ == "__main__":
    unittest.main()
