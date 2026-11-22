"""Paths of 260 characters or more in the save folders (the owner, 2026-11-20: "no path-too-long errors").

Most players' Windows refuses a path of 260 characters or more (long paths are off).  These tests turn that
refusal on for every plain path, whatever this machine allows (`MaxPath`), and build a save folder whose
older builds' copies ("Copies Made Before Repairs") and backups run past 259 characters.  Back Up Saves
copies, lists, restores and deletes them; Repair Saves & Logs and Check Saves & Logs run beside them; and
every new copy kept before a repair has a short name that fits the budget (src/vv_repair_copies.py).
Nothing a player already has is renamed, moved or deleted."""
from __future__ import annotations

import builtins
import errno
import gzip
import io
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv1_parents_restore as parents  # noqa: E402
import vv3_second_faction as faction  # noqa: E402
import vv_backup_details  # noqa: E402
import vv_log_tools as tools  # noqa: E402
import vv_tribe_rename as rename  # noqa: E402
import test_backup_keeps_second_faction as sf  # noqa: E402
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
                    # As Windows raises it: ERROR_PATH_NOT_FOUND (3), errno ENOENT -- the error every
                    # Python's pathlib treats as "not there" (GitHub CI's Python re-raised errno 3).
                    raise FileNotFoundError(errno.ENOENT, "The system cannot find the path specified (MAX_PATH)",
                                            os.fsdecode(os.fspath(value)), 3)
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

    def test_a_long_junction_is_never_entered(self) -> None:
        """GitHub CI on #769: the link check read a long path plainly, so a junction past 259 characters went
        unseen (and an older Python raised).  It is seen at any length, and the backup never enters it."""
        import _winapi
        place = next(iter(self.old.values())).parent / ("junction " + "j" * 100)
        self.assertTrue(lp.too_long(place))
        _winapi.CreateJunction(str(Path(self._tmp.name)), os.fspath(lp.extended(place)))
        self.addCleanup(lambda: os.rmdir(lp.extended(place)) if lp.exists(place) else None)
        with MaxPath():
            self.assertTrue(backup._is_link(place))
            self.assertFalse(backup._is_link(next(iter(self.old.values()))))
            self.assertFalse([r for r in backup.files_to_back_up(self.folder) if place.name in str(r)])

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
        # ("Homes" stands in for the 5-letter home folder, so no account path ships in the archive.)
        save_folder = "C:\\Homes\\A Player With A Long Name\\OneDrive - Household\\Documents\\LDW\\" \
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
        owners = "C:\\Homes\\Owner\\OneDrive\\Documents\\LDW\\" \
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


def deep_save_folder(tmp: str, title: str, save_name: str, live_length: int = 250) -> Path:
    """A recognised Modded save folder so deep that its slot save is `live_length` characters long: fine for
    the game, but past 259 at its place in a backup ("Backups\\<yyyy-mm-dd hhmm>\\" adds 25 or more)."""
    base = Path(tmp) / "Homes" / "Documents" / "LDW"
    name = f"{title} - Modded"
    pad = live_length - len(str(base)) - len(name) - len(save_name) - 3      # three more backslashes
    if not 1 <= pad <= 200:
        raise unittest.SkipTest(f"the temporary folder is {len(str(base))} characters deep")
    folder = base / ("p" * pad) / name
    lp.makedirs(folder)
    return folder


@unittest.skipUnless(WINDOWS, "Windows paths")
class DeepSlotSaves(unittest.TestCase):
    """Codex review on #769: a recognised Modded save folder whose live slot save is 250 characters long.  Its
    slot saves (and logs) are kept in the backup's Long Paths folder, and everything that reads a backup reads
    them there: the pause, its hash and file times, the list, Restore Saves' slot of a legacy log, the details,
    Repair's unpaused backups and the backup's game speed."""

    LOG = f"{LOGS}\\Births and Conceptions\\Virtual Villagers 1 Births and Conceptions Log 1.txt"
    LIVE = 250                          # the live slot save's length

    def setUp(self) -> None:
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(lambda: lp.rmtree(holder.name))
        self.game = rename.GAMES[0]
        self.folder = deep_save_folder(holder.name, self.game.title, self.game.save_path(Path(), 1).name,
                                       self.LIVE)
        self.save = self.game.save_path(self.folder, 1)
        self.assertEqual(len(str(self.save)), self.LIVE)
        put(self.save, tl.fixture("vv1-huttest-1"))
        put(self.game.index_path(self.folder), tl.fixture("vv1-huttest-0"))
        self.assertIsNotNone(backup.pause_save_bytes(1, lp.read_bytes(self.save)), "the fixture is not paused")
        # A legacy log known by its header alone: no "Save N" in its name or its folders.
        self.log = put(self.folder / self.LOG, b"Village: Hut (Save 1)\r\n\r\nfirst\r\n")
        self.assertEqual(backup.file_slot(Path(self.LOG), self.folder), 1)
        self.village = backup.read_village_name(1, self.save)
        self.assertTrue(self.village)

    def test_the_backup_pauses_the_long_slot_save(self) -> None:
        live = lp.read_bytes(self.save)
        with MaxPath():
            made = backup.copy_save_folder(self.folder, NOW)
            self.assertFalse(made.backup_folder.name.endswith(backup.INCOMPLETE))
            contents = backup.backup_contents(made.backup_folder)
            relative = Path(self.save.name)
            stored = contents[relative]
            self.assertEqual(stored.parent.name, backup.LONG_PATHS, "kept in the Long Paths folder")
            self.assertTrue(lp.too_long(made.backup_folder / relative))
            # Paused where it is, its hash and its file times those of the paused copy.
            copy = lp.read_bytes(stored)
            self.assertIsNone(backup.pause_save_bytes(1, copy), "the backup's copy is Paused")
            self.assertEqual(made.paused_slots, [self.save.name])
            self.assertEqual(made.unpaused_bytes[relative], live)
            record = next(c for c in made.files if c.relative == relative)
            self.assertEqual(record.size, len(copy))
            self.assertEqual((record.size, record.sha256), backup._hash_file(stored))
            self.assertEqual(lp.stat(stored).st_mtime_ns, lp.stat(self.save).st_mtime_ns)
            self.assertEqual(lp.read_bytes(self.save), live, "the live save is untouched")
            # The list names the village; Repair finds nothing left to pause; the details read the slot.
            [info] = backup.list_backups(self.folder)
            self.assertEqual(info.villages, {1: self.village})
            self.assertEqual(backup.unpaused_backup_saves(self.folder), [])
            details = vv_backup_details.read_backup(1, info, now=NOW.timestamp())
            self.assertEqual([(s.slot, s.tribe, s.speed) for s in details.slots], [(1, self.village, "Paused")])
            # The backup's game speed is set where the save is, and Repair then finds it unpaused.
            outcome = backup.set_backup_speed(self.folder, made.backup_folder, "normal")
            self.assertEqual([name for name, _old, _new in outcome.changed], [self.save.name], outcome.skipped)
            self.assertIsNotNone(backup.pause_save_bytes(1, lp.read_bytes(stored)))
            self.assertEqual(backup.unpaused_backup_saves(self.folder), [stored])
            paused = backup.pause_saves([stored], tl.FakeProcesses())
            self.assertEqual(paused.paused, [stored], paused.skipped)

    def test_a_one_slot_restore_reads_the_long_logs_header_in_the_backup(self) -> None:
        with MaxPath():
            made = backup.copy_save_folder(self.folder, NOW)
            contents = backup.backup_contents(made.backup_folder)
            self.assertEqual(contents[Path(self.LOG)].parent.name, backup.LONG_PATHS)
            self.assertEqual(backup.file_slot(Path(self.LOG), made.backup_folder, contents[Path(self.LOG)]), 1)
            lp.extended(self.log).write_bytes(b"Village: Hut (Save 1)\r\n\r\nfirst\r\nsecond\r\n")
            plan = backup.plan_restore(self.folder, made.backup_folder, 1)
            self.assertEqual(set(plan.replace), {Path(self.LOG), Path(self.save.name)})   # the save: paused
            result = backup.restore_backup(self.folder, made.backup_folder, 1, tl.FakeProcesses(),
                                           NOW + timedelta(minutes=1))
            self.assertEqual(set(result.plan.replace), {Path(self.LOG), Path(self.save.name)})
            self.assertEqual(lp.read_bytes(self.log), b"Village: Hut (Save 1)\r\n\r\nfirst\r\n")


class DeepLogsOnly(DeepSlotSaves):
    """Codex review on #769, the log alone: a shallower folder (a 200-character live save), whose slot saves fit
    at their own places in the backup but whose legacy log is kept in its Long Paths folder.  The backup's
    copy of the log is read there for its "Village: ... (Save 1)" header, so a one-slot restore is not refused."""

    LIVE = 200

    def test_the_backup_pauses_the_long_slot_save(self) -> None:
        with MaxPath():
            made = backup.copy_save_folder(self.folder, NOW)
            contents = backup.backup_contents(made.backup_folder)
            self.assertEqual(contents[Path(self.save.name)], made.backup_folder / self.save.name, "at its place")
            self.assertIsNone(backup.pause_save_bytes(1, lp.read_bytes(contents[Path(self.save.name)])))
            self.assertEqual(made.paused_slots, [self.save.name])


@unittest.skipUnless(WINDOWS, "Windows paths")
class DeepSecondFaction(unittest.TestCase):
    """The Secret City in a save folder that deep: the faction file is in the backup's Long Paths folder too,
    and the paused copy keeps its second faction there; an old backup's is linked again there."""

    def setUp(self) -> None:
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(lambda: lp.rmtree(holder.name))
        self.base = sf.BASE
        self.folder = deep_save_folder(holder.name, sf.BASE, f"{sf.BASE}1.ldw")
        self.save = gzip.open(sf.SAVE).read()
        put(self.folder / f"{self.base}1.ldw", self.save)
        self.dat = put(faction.faction_file(self.folder, 1), sf.faction_bytes(1, [faction.fingerprint(self.save)]))

    def test_the_backup_keeps_the_second_faction_in_the_long_paths_folder(self) -> None:
        with MaxPath():
            made = backup.copy_save_folder(self.folder, NOW)
            contents = backup.backup_contents(made.backup_folder)
            save = contents[Path(f"{self.base}1.ldw")]
            dat = contents[self.dat.relative_to(self.folder)]
            self.assertEqual({save.parent.name, dat.parent.name}, {backup.LONG_PATHS})
            copy = lp.read_bytes(save)
            self.assertNotEqual(copy, self.save, "the backup's copy is paused")
            self.assertIsNotNone(faction.entry_for(lp.extended(dat), faction.fingerprint(copy)), "and keeps its faction")
            record = next(c for c in made.files if c.relative == self.dat.relative_to(self.folder))
            self.assertEqual((record.size, record.sha256), backup._hash_file(dat))

    def test_an_old_backup_is_linked_again_in_the_long_paths_folder(self) -> None:
        with MaxPath():
            made = backup.copy_save_folder(self.folder, NOW)
            contents = backup.backup_contents(made.backup_folder)
            dat = contents[self.dat.relative_to(self.folder)]
            lp.extended(dat).write_bytes(lp.read_bytes(self.dat))          # as a backup made before the fix
            put(self.folder / f"{self.base}21.ldw", self.save)               # the game's own copy
            relinked = backup.relink_backups(self.folder)
            self.assertEqual(relinked, {made.backup_folder.name: {1: True}})
            copy = lp.read_bytes(contents[Path(f"{self.base}1.ldw")])
            self.assertIsNotNone(faction.entry_for(lp.extended(dat), faction.fingerprint(copy)))


if __name__ == "__main__":
    unittest.main()
