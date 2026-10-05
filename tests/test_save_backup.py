"""Back Up Saves: find the save folders, pause the game, copy, verify.

The owner's request: "an easy tool to pause the player's saves and make a copy
of them in the save folder too", as a button in the patcher window that pauses
the game and then copies, for all five games and every Modded variant.

Everything here runs against a throwaway Documents folder made by the test and
a fake process controller, except WindowsProcessesTests, which pauses and
resumes a child process the test itself starts -- never a game, and never by
name (pausing "every python.exe" would pause whatever else is running).
"""
from __future__ import annotations

import ast
import hashlib
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_save_backup as backup  # noqa: E402
from vv_fun_patcher import load_builds  # noqa: E402

TITLES = [build.title for build in load_builds()]
NOW = datetime(2026, 10, 4, 13, 5, 22)


def write(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


class FakeProcesses:
    """Records every find/suspend/resume, and what the copy saw."""

    def __init__(self, pids=(), fail_on=None, find_error=None):
        self.pids = list(pids)
        self.fail_on = fail_on
        self.find_error = find_error
        self.events: list[tuple[str, object]] = []
        self.suspended: set[int] = set()

    def find(self, exe_name):
        self.events.append(("find", exe_name))
        if self.find_error is not None:
            raise self.find_error
        return list(self.pids)

    def suspend(self, pid, exe_name):
        if pid == self.fail_on:
            self.events.append(("refused", pid))
            raise backup.PauseRefused(f"{exe_name} ({pid}): access was denied.")
        self.events.append(("suspend", pid))
        self.suspended.add(pid)
        return pid

    def resume(self, handle):
        self.events.append(("resume", handle))
        self.suspended.discard(handle)


class TempDocuments(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.documents = Path(self._tmp.name) / "Documents"
        self.ldw = self.documents / "LDW"
        self.ldw.mkdir(parents=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def save_folder(self, name="Virtual Villagers - The Secret City - Modded") -> Path:
        folder = self.ldw / name
        title = name.split(" - Modded")[0]
        write(folder / f"{title}0.ldw", b"slot zero")
        write(folder / f"{title}1.ldw", os.urandom(94500))
        write(
            folder / "Virtual Villagers Fun Patcher Logs" / "Births and Conceptions"
            / "Virtual Villagers 3 Births and Conceptions Log 1.txt",
            b"Village: Kalahuna (Save 1)\r\n",
        )
        write(
            folder / "Virtual Villagers Fun Patcher Data" / "Masks" / "masks_1.dat",
            os.urandom(300),
        )
        write(folder / "Village Statistics - Save 1.txt", b"legacy top-level file")
        return folder


class DiscoveryTests(TempDocuments):
    def test_every_modded_variant_of_every_game_is_found(self) -> None:
        for title in TITLES:
            for suffix in backup.PATCHER_SUFFIXES:
                (self.ldw / f"{title} - {suffix}").mkdir()
        for title in TITLES:
            names = [p.name for p in backup.find_save_folders(title, self.documents)]
            self.assertEqual(
                names, [f"{title} - {suffix}" for suffix in backup.PATCHER_SUFFIXES]
            )
            for name in names:
                self.assertTrue(backup.is_patcher_save_folder(title, name))

    def test_only_this_games_modded_folders_and_patcher_ones_first(self) -> None:
        title = "Virtual Villagers - The Tree of Life"
        for name in (
            title,                                  # the stock game's own saves
            f"{title} - Modded HutTest",            # a renamed build
            f"{title} - Modded 256",
            f"{title} - Modded",
            f"{title} - Modded - Copy",             # a copy the player made
            "Virtual Villagers - New Believers - Modded",   # another game
        ):
            (self.ldw / name).mkdir()
        write(self.ldw / f"{title} - Modded.txt", b"a file, not a folder")
        names = [p.name for p in backup.find_save_folders(title, self.documents)]
        self.assertEqual(
            names,
            [
                f"{title} - Modded",
                f"{title} - Modded 256",
                f"{title} - Modded - Copy",
                f"{title} - Modded HutTest",
            ],
        )
        self.assertFalse(backup.is_patcher_save_folder(title, f"{title} - Modded HutTest"))
        self.assertFalse(backup.is_patcher_save_folder(title, f"{title} - Modded - Copy"))
        self.assertFalse(backup.is_patcher_save_folder(title, title))

    def test_no_documents_or_no_ldw_finds_nothing(self) -> None:
        self.assertEqual(backup.find_save_folders(TITLES[0], None), [])
        self.assertEqual(
            backup.find_save_folders(TITLES[0], Path(self._tmp.name) / "nowhere"), []
        )

    def test_the_exe_is_named_after_the_folder(self) -> None:
        folder = self.ldw / "Virtual Villagers - New Believers - Modded 256"
        self.assertEqual(
            backup.game_exe_name(folder), "Virtual Villagers - New Believers - Modded 256.exe"
        )

    @unittest.skipUnless(sys.platform == "win32", "Windows Known Folder API")
    def test_documents_comes_from_the_known_folder_api(self) -> None:
        documents = backup.documents_folder()
        self.assertIsNotNone(documents)
        self.assertTrue(documents.is_absolute())
        # The same answer the shell gives through the older CSIDL call, which
        # also follows redirection; never a Path.home() guess.
        import ctypes
        buffer = ctypes.create_unicode_buffer(260)
        ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buffer)
        self.assertEqual(os.path.normcase(str(documents)), os.path.normcase(buffer.value))

    def test_the_module_never_guesses_documents_from_home(self) -> None:
        source = (ROOT / "src" / "vv_save_backup.py").read_text(encoding="utf-8")
        self.assertNotIn("Path.home()", source)
        self.assertNotIn("USERPROFILE", source)
        self.assertIn("SHGetKnownFolderPath", source)


class CopyTests(TempDocuments):
    def test_everything_is_copied_and_verified_except_backups(self) -> None:
        folder = self.save_folder()
        old = write(folder / "Backups" / "Backup 2020-01-01 00-00-00" / "old.ldw", b"old")
        result = backup.copy_save_folder(folder, NOW)
        self.assertEqual(
            result.backup_folder, folder / "Backups" / "Backup 2026-10-04 13-05-22"
        )
        expected = sorted(
            p.relative_to(folder)
            for p in folder.rglob("*")
            if p.is_file() and p.relative_to(folder).parts[0] != "Backups"
        )
        self.assertEqual(len(expected), 5, "nonzero denominator")
        self.assertEqual(sorted(item.relative for item in result.files), expected)
        for relative in expected:
            original = (folder / relative).read_bytes()
            copy = (result.backup_folder / relative).read_bytes()
            self.assertEqual(copy, original, relative)
            item = next(i for i in result.files if i.relative == relative)
            self.assertEqual(item.size, len(original))
            self.assertEqual(item.sha256, hashlib.sha256(original).hexdigest())
        self.assertEqual(result.file_count, 5)
        self.assertEqual(
            result.total_bytes, sum((folder / r).stat().st_size for r in expected)
        )
        # The earlier backup was neither copied nor touched.
        self.assertFalse(any("Backups" in item.relative.parts for item in result.files))
        self.assertFalse((result.backup_folder / "Backups").exists())
        self.assertEqual(old.read_bytes(), b"old")

    def test_backups_is_excluded_whatever_its_case(self) -> None:
        folder = self.save_folder()
        write(folder / "BACKUPS" / "x.ldw", b"x")
        relatives = backup.files_to_back_up(folder)
        self.assertFalse(any(r.parts[0].casefold() == "backups" for r in relatives))
        # ...but only at the top: a "Backups" deeper down is ordinary content.
        write(folder / "Virtual Villagers Fun Patcher Data" / "Backups" / "y.dat", b"y")
        self.assertIn(
            Path("Virtual Villagers Fun Patcher Data") / "Backups" / "y.dat",
            backup.files_to_back_up(folder),
        )

    def test_an_existing_backup_is_never_overwritten(self) -> None:
        folder = self.save_folder()
        taken = folder / "Backups" / "Backup 2026-10-04 13-05-22"
        sentinel = write(taken / "Virtual Villagers - The Secret City1.ldw", b"keep me")
        first = backup.copy_save_folder(folder, NOW)
        self.assertEqual(first.backup_folder.name, "Backup 2026-10-04 13-05-22 (2)")
        second = backup.copy_save_folder(folder, NOW)
        self.assertEqual(second.backup_folder.name, "Backup 2026-10-04 13-05-22 (3)")
        self.assertEqual(sentinel.read_bytes(), b"keep me")
        self.assertEqual(len(list(taken.iterdir())), 1)

    def test_a_file_is_never_written_over(self) -> None:
        folder = self.save_folder()
        target = folder / "Backups" / "dest.ldw"
        write(target, b"keep me")
        with self.assertRaises(FileExistsError):
            backup._copy_one(folder / "Virtual Villagers - The Secret City0.ldw", target)
        self.assertEqual(target.read_bytes(), b"keep me")

    def test_a_copy_that_does_not_verify_is_refused_and_kept_aside(self) -> None:
        folder = self.save_folder()
        real = backup._hash_file
        calls = {"n": 0}

        def corrupt(path):
            size, digest = real(path)
            calls["n"] += 1
            if "Backups" in path.parts and calls["n"] >= 3:
                return size, "0" * 64
            return size, digest

        with mock.patch.object(backup, "_hash_file", side_effect=corrupt):
            with self.assertRaises(backup.BackupError) as caught:
                backup.copy_save_folder(folder, NOW)
        self.assertIn("NOT a usable backup", str(caught.exception))
        backups = sorted(p.name for p in (folder / "Backups").iterdir())
        self.assertEqual(backups, ["Backup 2026-10-04 13-05-22 INCOMPLETE"])
        # Nothing in the save folder itself was harmed.
        self.assertEqual(len(backup.files_to_back_up(folder)), 5)

    def test_a_short_copy_is_refused(self) -> None:
        folder = self.save_folder()
        real = backup._hash_file

        def short(path):
            size, digest = real(path)
            return (size - 1, digest) if "Backups" in path.parts else (size, digest)

        with mock.patch.object(backup, "_hash_file", side_effect=short):
            with self.assertRaises(backup.BackupError):
                backup.copy_save_folder(folder, NOW)

    def test_a_file_that_changes_during_the_copy_is_refused(self) -> None:
        folder = self.save_folder()
        real = backup._hash_file

        def changed(path):
            size, digest = real(path)
            if "Backups" not in path.parts:
                return size, "f" * 64
            return size, digest

        with mock.patch.object(backup, "_hash_file", side_effect=changed):
            with self.assertRaises(backup.BackupError) as caught:
                backup.copy_save_folder(folder, NOW)
        self.assertIn("changed while it was being copied", str(caught.exception))

    def test_an_empty_or_missing_folder_is_refused(self) -> None:
        empty = self.ldw / "Virtual Villagers - A New Home - Modded"
        empty.mkdir()
        with self.assertRaises(backup.BackupError):
            backup.copy_save_folder(empty, NOW)
        with self.assertRaises(backup.BackupError):
            backup.copy_save_folder(self.ldw / "missing", NOW)
        self.assertFalse((empty / "Backups").exists())

    @unittest.skipUnless(sys.platform == "win32", "junctions are a Windows feature")
    def test_a_linked_folder_is_not_entered(self) -> None:
        import _winapi
        folder = self.save_folder()
        elsewhere = write(Path(self._tmp.name) / "elsewhere" / "big.bin", b"not a save")
        _winapi.CreateJunction(str(elsewhere.parent), str(folder / "link"))
        # A link back to the save folder itself would otherwise recurse.
        _winapi.CreateJunction(str(folder), str(folder / "Virtual Villagers Fun Patcher Data" / "loop"))
        relatives = backup.files_to_back_up(folder)
        self.assertFalse(any(r.parts[0] == "link" for r in relatives))
        self.assertFalse(any("loop" in r.parts for r in relatives))
        self.assertEqual(len(relatives), 5)


class PauseTests(TempDocuments):
    def test_the_copy_happens_while_every_game_process_is_paused(self) -> None:
        folder = self.save_folder()
        processes = FakeProcesses(pids=[111, 222])
        seen = {}
        real_copy = backup.copy_save_folder

        def copy_while_watching(path, now=None):
            seen["paused_during_copy"] = set(processes.suspended)
            return real_copy(path, now)

        with mock.patch.object(backup, "copy_save_folder", side_effect=copy_while_watching):
            result = backup.back_up_save_folder(folder, processes, NOW)
        self.assertEqual(seen["paused_during_copy"], {111, 222})
        self.assertEqual(processes.suspended, set(), "every process was resumed")
        self.assertEqual(result.paused, 2)
        self.assertEqual(
            processes.events,
            [
                ("find", "Virtual Villagers - The Secret City - Modded.exe"),
                ("suspend", 111),
                ("suspend", 222),
                ("resume", 222),
                ("resume", 111),
            ],
        )

    def test_a_game_that_is_not_running_is_simply_copied(self) -> None:
        folder = self.save_folder()
        processes = FakeProcesses()
        result = backup.back_up_save_folder(folder, processes, NOW)
        self.assertEqual(result.paused, 0)
        self.assertEqual(result.file_count, 5)

    def test_the_game_is_resumed_even_when_the_copy_fails(self) -> None:
        folder = self.save_folder()
        processes = FakeProcesses(pids=[111])
        with mock.patch.object(
            backup, "copy_save_folder", side_effect=OSError("disk full")
        ):
            with self.assertRaises(OSError):
                backup.back_up_save_folder(folder, processes, NOW)
        self.assertEqual(processes.events[-1], ("resume", 111))
        self.assertEqual(processes.suspended, set())

    def test_the_game_is_resumed_even_on_an_unexpected_error(self) -> None:
        folder = self.save_folder()
        processes = FakeProcesses(pids=[111])
        with mock.patch.object(
            backup, "copy_save_folder", side_effect=KeyboardInterrupt
        ):
            with self.assertRaises(KeyboardInterrupt):
                backup.back_up_save_folder(folder, processes, NOW)
        self.assertEqual(processes.suspended, set())

    def test_a_game_that_cannot_be_paused_is_not_copied(self) -> None:
        folder = self.save_folder()
        processes = FakeProcesses(pids=[111, 222], fail_on=222)
        with self.assertRaises(backup.PauseRefused) as caught:
            backup.back_up_save_folder(folder, processes, NOW)
        self.assertIn("access was denied", str(caught.exception))
        self.assertFalse((folder / "Backups").exists(), "nothing was copied")
        # The one that was paused is resumed again.
        self.assertEqual(
            processes.events[1:], [("suspend", 111), ("refused", 222), ("resume", 111)]
        )
        self.assertEqual(processes.suspended, set())

    def test_when_the_process_list_fails_nothing_is_copied(self) -> None:
        folder = self.save_folder()
        processes = FakeProcesses(find_error=backup.BackupError("no list"))
        with self.assertRaises(backup.BackupError):
            backup.back_up_save_folder(folder, processes, NOW)
        self.assertFalse((folder / "Backups").exists())

    def test_every_process_is_resumed_even_if_one_resume_fails(self) -> None:
        folder = self.save_folder()

        class OneResumeFails(FakeProcesses):
            def resume(self, handle):
                super().resume(handle)
                if handle == 222:
                    raise backup.BackupError("could not resume 222")

        processes = OneResumeFails(pids=[111, 222])
        result = backup.back_up_save_folder(folder, processes, NOW)
        self.assertIn(("resume", 111), processes.events)
        # Codex on #521: the backup was made and verified, so it is reported
        # as made -- with the resume problem beside it, not instead of it.
        self.assertEqual(result.file_count, 5)
        self.assertEqual(result.resume_problems, ["could not resume 222"])
        self.assertTrue(result.backup_folder.is_dir())

    def test_a_resume_problem_on_a_failed_copy_is_noted_on_the_error(self) -> None:
        folder = self.save_folder()

        class ResumeFails(FakeProcesses):
            def resume(self, handle):
                super().resume(handle)
                raise backup.BackupError("could not resume")

        with mock.patch.object(backup, "copy_save_folder", side_effect=OSError("disk full")):
            with self.assertRaises(OSError) as caught:
                backup.back_up_save_folder(folder, ResumeFails(pids=[1]), NOW)
        self.assertIn("could not resume", " ".join(getattr(caught.exception, "__notes__", [])))


@unittest.skipUnless(sys.platform == "win32", "Windows process API")
class WindowsProcessesTests(unittest.TestCase):
    """Pause and resume a real process: a child this test starts itself."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ticks = Path(self._tmp.name) / "ticks.txt"
        code = (
            "import time, sys\n"
            "n = 0\n"
            "while True:\n"
            "    n += 1\n"
            "    open(sys.argv[1], 'w').write(str(n))\n"
            "    time.sleep(0.02)\n"
        )
        self.child = subprocess.Popen([sys.executable, "-c", code, str(self.ticks)])
        self.exe_name = Path(sys.executable).name
        deadline = time.time() + 10
        while not self.ticks.exists() and time.time() < deadline:
            time.sleep(0.05)

    def tearDown(self) -> None:
        self.child.kill()
        self.child.wait()
        self._tmp.cleanup()

    def _ticks(self) -> int:
        for _ in range(20):
            try:
                return int(self.ticks.read_text() or 0)
            except (ValueError, OSError):
                time.sleep(0.01)
        return -1

    def test_a_process_is_really_paused_and_resumed(self) -> None:
        processes = backup.WindowsProcesses()
        self.assertIn(self.child.pid, processes.find(self.exe_name))
        handle = processes.suspend(self.child.pid, self.exe_name)
        try:
            time.sleep(0.2)
            frozen = self._ticks()
            time.sleep(0.5)
            self.assertEqual(self._ticks(), frozen, "the process kept running")
        finally:
            processes.resume(handle)
        time.sleep(0.5)
        self.assertGreater(self._ticks(), frozen, "the process did not resume")
        self.assertIsNone(self.child.poll(), "the process was not closed")

    def test_a_process_with_another_name_is_refused(self) -> None:
        processes = backup.WindowsProcesses()
        with self.assertRaises(backup.PauseRefused):
            processes.suspend(self.child.pid, "Virtual Villagers - A New Home - Modded.exe")
        before = self._ticks()
        time.sleep(0.3)
        self.assertGreater(self._ticks(), before, "a refused process must not be paused")

    def test_a_process_that_cannot_be_opened_is_refused(self) -> None:
        processes = backup.WindowsProcesses()
        with self.assertRaises(backup.PauseRefused):
            processes.suspend(4, "System")  # the System process: access denied


class SaveFolderScannersIgnoreBackupsTests(unittest.TestCase):
    """Nothing else in the patcher may read, migrate or delete a backup.

    The shipped companions and the patcher only ever look at named files in a
    save folder or at the folder's top level with a name filter, and skip
    directories, so a Backups subfolder is invisible to them. These checks pin
    that: a new recursive walk, or a directory delete, fails here and must be
    taught to skip Backups. The Start Over (Save Reset) harness also runs the
    reset against a real Backups folder (native/shared/save_reset_harness.c).
    """

    def shipped_native_sources(self):
        for path in sorted((ROOT / "native").rglob("*.c")):
            if "harness" in path.name:
                continue
            yield path

    def test_no_shipped_companion_deletes_a_folder_or_walks_one_recursively(self) -> None:
        for path in self.shipped_native_sources():
            text = path.read_text(encoding="utf-8", errors="replace")
            for call in ("RemoveDirectory", "SHFileOperation", "IFileOperation"):
                self.assertNotIn(call, text, f"{path.relative_to(ROOT)} calls {call}")

    def test_every_shipped_directory_listing_skips_folders_and_is_filtered(self) -> None:
        listings = 0
        for path in self.shipped_native_sources():
            text = path.read_text(encoding="utf-8", errors="replace")
            for match in re.finditer(r"FindFirstFile\w*\s*\(", text):
                listings += 1
                body = text[match.start(): match.start() + 2500]
                self.assertIn(
                    "FILE_ATTRIBUTE_DIRECTORY",
                    body,
                    f"{path.relative_to(ROOT)}: a listing that does not skip folders",
                )
        self.assertGreater(listings, 0, "nonzero denominator")

    def test_the_patchers_save_folder_globs_are_not_recursive(self) -> None:
        source = (ROOT / "src" / "vv_fun_patcher.py").read_text(encoding="utf-8")
        for match in re.finditer(r"(source|destination)\.(r?glob)\(", source):
            self.assertEqual(match.group(2), "glob", match.group(0))

    def test_copying_saves_into_a_256_folder_ignores_its_backups(self) -> None:
        from vv_fun_patcher import EXPANDED_PATCH_MODES, copy_vanilla_saves

        build = next(b for b in load_builds() if b.id == "vv3")
        mode = sorted(EXPANDED_PATCH_MODES)[0]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vanilla = root / build.title
            write(vanilla / f"{build.title}0.ldw", b"zero")
            write(vanilla / f"{build.title}1.ldw", b"one")
            write(vanilla / "Backups" / "Backup x" / f"{build.title}2.ldw", b"backup")
            modded = root / f"{build.title} - Modded 256"
            kept = write(modded / "Backups" / "Backup y" / f"{build.title}1.ldw", b"keep")
            result = copy_vanilla_saves(build, mode, save_root=root)
            self.assertNotIn("error", result)
            copied = sorted(p.name for p in modded.glob("*.ldw"))
            self.assertEqual(copied, [f"{build.title}0.ldw", f"{build.title}1.ldw"])
            self.assertEqual(kept.read_bytes(), b"keep")

    def test_the_start_over_harness_covers_backups(self) -> None:
        harness = (ROOT / "native" / "shared" / "save_reset_harness.c").read_text(
            encoding="utf-8"
        )
        self.assertIn("Backups\\\\Backup", harness)
        self.assertIn("A BACKUP SURVIVES START OVER", harness)


class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def method(self, name):
        return next(
            node
            for node in ast.walk(self.tree)
            if isinstance(node, ast.FunctionDef) and node.name == name
        )

    def test_one_game_tab_has_the_link_beside_the_folder_links(self) -> None:
        single = ast.get_source_segment(self.source, self.method("_build_single_tab"))
        self.assertIn('"Open Modified EXE Folder"', single)
        self.assertIn('links, "Back Up Saves", self._back_up_single_saves', single)

    def test_every_all_five_row_has_the_link_and_there_is_an_all_five_button(self) -> None:
        bulk = ast.get_source_segment(self.source, self.method("_build_all_tab"))
        self.assertIn('"Back up saves"', bulk)
        self.assertIn("self._back_up_saves([game])", bulk)
        self.assertIn("for index, build in enumerate(self.builds)", bulk)
        self.assertIn('text="Back Up Saves (All 5)..."', bulk)
        self.assertIn("self._back_up_saves(list(self.builds))", bulk)

    def test_the_backup_runs_off_the_main_thread_through_the_module(self) -> None:
        run = ast.get_source_segment(self.source, self.method("_run_backups"))
        self.assertIn("vv_save_backup.back_up_save_folder(folder)", run)
        self.assertIn("self._run_with_wait(", run)

    def test_folders_come_from_the_known_documents_folder(self) -> None:
        chooser = ast.get_source_segment(self.source, self.method("_back_up_saves"))
        self.assertIn("vv_save_backup.documents_folder()", chooser)
        self.assertIn("vv_save_backup.find_save_folders(build.title, documents)", chooser)

    def test_the_player_is_told_about_the_pause_and_the_last_save(self) -> None:
        chooser = ast.get_source_segment(self.source, self.method("_show_backup_chooser"))
        results = ast.get_source_segment(self.source, self.method("_show_backup_results"))
        self.assertIn("paused for the copy", chooser)
        self.assertIn("as of its last save", chooser)
        self.assertIn("paused for the copy and has", results)
        self.assertIn("as of its last save", results)
        self.assertIn('"Open Backup Folder"', results)
        self.assertIn("NOT backed up", results)

    def test_the_module_ships_in_the_release(self) -> None:
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        self.assertIn('"src/vv_save_backup.py"', release)


# ---------------------------------------------------------------------------
# Restore
# ---------------------------------------------------------------------------

def save_bytes(game: int, village: str, filler: int = 0, expanded: bool = False) -> bytes:
    """A save file the games (and the reader) accept, naming ``village``."""
    header = backup._SAVE_HEADER[game]
    length = backup._SAVE_BUFFERS[game][1 if expanded else 0]
    data = bytearray(header + length)
    data[0:4] = b"ldwg"
    at = backup._SAVE_LENGTH_AT[game]
    data[at:at + 4] = length.to_bytes(4, "little")
    name_at = header + backup._NAME_OFFSET[game]
    encoded = village.encode("ascii")
    data[name_at:name_at + len(encoded)] = encoded
    data[-1] = filler          # lets two saves of one village differ
    return bytes(data)


GAME_TITLES = {
    1: "Virtual Villagers - A New Home",
    2: "Virtual Villagers - The Lost Children",
    3: "Virtual Villagers - The Secret City",
    4: "Virtual Villagers - The Tree of Life",
    5: "Virtual Villagers - New Believers",
}
# Each game's own save base name (A New Home's saves are "Virtual Villagers<N>.ldw").
SAVE_BASE = {1: "Virtual Villagers", 2: GAME_TITLES[2], 3: GAME_TITLES[3],
             4: GAME_TITLES[4], 5: GAME_TITLES[5]}
LOGS = "Virtual Villagers Fun Patcher Logs"
DATA = "Virtual Villagers Fun Patcher Data"


class RestoreBase(TempDocuments):
    game = 3
    suffix = "Modded"

    def make_village(self, filler=0):
        g = self.game
        folder = self.ldw / f"{GAME_TITLES[g]} - {self.suffix}"
        base = SAVE_BASE[g]
        expanded = "256" in self.suffix
        write(folder / f"{base}0.ldw", b"meta" + bytes([filler]))
        for slot, village in ((1, "Kalahuna"), (2, "Elsewhere")):
            write(folder / f"{base}{slot}.ldw", save_bytes(g, village, filler, expanded))
            write(folder / f"{base}{slot + 20}.ldw", save_bytes(g, village, filler + 1, expanded))
            write(folder / DATA / "Village Statistics" / f"Village Statistics - Save {slot}.dat",
                  f"stats {slot} {filler}".encode())
            write(folder / LOGS / "Village Statistics" / f"Village Statistics v2 - Save {slot}.txt",
                  f"Village: {village} (Save {slot})\r\n{filler}\r\n".encode())
            write(folder / LOGS / "Births and Conceptions" /
                  f"Virtual Villagers {g} Births and Conceptions Log {slot}.txt",
                  f"Village: {village} (Save {slot})\r\nrecord {filler}\r\n".encode())
        return folder

    def snapshot(self, folder):
        return {
            str(r): (folder / r).read_bytes() for r in backup.files_to_back_up(folder)
        }

    def backups_snapshot(self, folder):
        root = folder / "Backups"
        return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


class ListingTests(RestoreBase):
    def test_names_and_slots_are_read_for_every_game_and_256(self) -> None:
        for game in range(1, 6):
            for suffix in (["Modded", "Modded 256"] if game >= 3 else ["Modded"]):
                with self.subTest(game=game, suffix=suffix):
                    self.game, self.suffix = game, suffix
                    folder = self.make_village()
                    self.assertEqual(backup.game_number(folder), game)
                    self.assertEqual(
                        backup.slot_villages(game, folder), {1: "Kalahuna", 2: "Elsewhere"}
                    )
                    first = backup.copy_save_folder(folder, datetime(2026, 1, 1, 9, 0, 0))
                    second = backup.copy_save_folder(folder, datetime(2026, 1, 2, 9, 0, 0))
                    listed = backup.list_backups(folder)
                    self.assertEqual([i.path for i in listed],
                                     [second.backup_folder, first.backup_folder])
                    self.assertEqual(listed[0].villages, {1: "Kalahuna", 2: "Elsewhere"})
                    self.assertEqual(listed[0].file_count, second.file_count)
                    self.assertEqual(listed[0].size, second.total_bytes)

    def test_an_invalid_save_has_no_name(self) -> None:
        folder = self.make_village()
        bad = write(folder / "x1.ldw", b"ldwg" + bytes(40))
        self.assertIsNone(backup.read_village_name(3, bad))
        wrong_length = bytearray(save_bytes(3, "Kalahuna"))
        wrong_length[8] ^= 1
        self.assertIsNone(backup.read_village_name(3, write(folder / "y1.ldw", bytes(wrong_length))))

    def test_incomplete_and_foreign_folders_are_not_listed_and_order_is_newest_first(self) -> None:
        folder = self.make_village()
        root = folder / "Backups"
        for name in ("Backup 2026-01-01 09-00-00", "Backup 2026-01-01 09-00-00 (2)",
                     "Backup 2026-01-03 09-00-00 (before restore)",
                     "Backup 2026-01-02 09-00-00 INCOMPLETE", "My stuff",
                     "Backup 2026-13-40 99-00-00"):
            write(root / name / "Virtual Villagers - The Secret City1.ldw", b"x")
        names = [i.path.name for i in backup.list_backups(folder)]
        self.assertEqual(names, ["Backup 2026-01-03 09-00-00 (before restore)",
                                 "Backup 2026-01-01 09-00-00 (2)",
                                 "Backup 2026-01-01 09-00-00"])
        self.assertTrue(backup.list_backups(folder)[0].before_restore)


class AttributionTests(RestoreBase):
    def test_every_patcher_file_kind_is_attributed_to_its_slot(self) -> None:
        folder = self.ldw / "Virtual Villagers - A New Home - Modded"
        cases = {
            "Virtual Villagers0.ldw": "meta",
            "Virtual Villagers1.ldw": 1, "Virtual Villagers22.ldw": 2,
            "Virtual Villagers43.ldw": 3, "Virtual Villagers5.ldw": 5,
            "Virtual Villagers7.ldw": "unknown",
            "Virtual Villagers1 - Copy.ldw": "unknown",
            "ldwLog.txt": "engine log",
            "vv1_masks_2.dat": 2, "vv1_doublers_3.dat": 3, "vv1_parents_4.dat": 4,
            "vvfp_masks_5.dat": 5, "vv2_masks_1.dat": 1,
            "Village Statistics - Save 4.txt": 4,
            f"{DATA}/Virtual Villagers 1 Village Masks - Save 1.dat": 1,
            f"{DATA}/Virtual Villagers 1 Origins Doublers - Save 2.dat": 2,
            f"{DATA}/Virtual Villagers 1 Parentage Records - Save 3.dat": 3,
            f"{DATA}/Village Masks - Save 4.dat": 4,
            f"{DATA}/Custom Titles/Custom Titles - Save 5.dat": 5,
            f"{DATA}/Virtual Villagers 1 Graves - Save 1.dat": 1,
            f"{DATA}/Virtual Villagers 1 Village Roster - Save 2.dat": 2,
            f"{DATA}/Village Statistics/Village Statistics - Save 3.dat": 3,
            f"{DATA}/Village Statistics/Village Statistics - Save 3.dat.tmp": 3,
            f"{DATA}/Stew Discoveries/Stew Discoveries - Save 4.dat": 4,
            f"{DATA}/Village Elders/Village Elders - Save 5.dat": 5,
            f"{DATA}/Village Elders/Village Elders - Save 5.dat.unreadable-1.dat": 5,
            f"{LOGS}/Village Statistics/Village Statistics - Save 1.txt": 1,
            f"{LOGS}/Village Statistics/Village Statistics v2 - Save 2.txt": 2,
        }
        for name, expected in cases.items():
            write(folder / name, b"data")
        headed = {
            f"{LOGS}/Births and Conceptions/Virtual Villagers 1 Births and Conceptions Log 7.txt":
                ("Village: Kalahuna (Save 3)\r\n", 3),
            f"{LOGS}/Deaths/Virtual Villagers 1 Deaths Log 1.txt":
                ("Village: Kalahuna (Save 2)\r\n", 2),
            f"{LOGS}/Unaccounted Villagers/Virtual Villagers 1 Unaccounted Villagers Log 1.txt":
                ("Village: X (Save 4)\r\n", 4),
            f"{LOGS}/Tribe Population/Village Population 9.txt":
                ("Virtual Villagers: A New Home Village Population\r\nVillage: K (Save 5)\r\n", 5),
            f"{LOGS}/Tribe History/Village History 1.txt":
                ("Virtual Villagers: A New Home Village History\r\nVillage: K (Save 1)\r\n", 1),
            f"{LOGS}/Births and Conceptions/Virtual Villagers 1 Births and Conceptions Log 8.txt":
                ("no header, written before the village had a name\r\n", "unknown"),
        }
        for name, (text, expected) in headed.items():
            write(folder / name, text.encode())
            cases[name] = expected
        for name, expected in cases.items():
            with self.subTest(name=name):
                self.assertEqual(backup.file_slot(Path(name), folder), expected)


class RestoreTests(RestoreBase):
    def restore(self, folder, chosen, slot=None, processes=None, now=None):
        return backup.restore_backup(
            folder, chosen, slot, processes or FakeProcesses(), now or datetime(2026, 2, 1, 8, 0, 0)
        )

    def test_whole_restore_puts_the_backup_back_and_saves_the_present_first(self) -> None:
        folder = self.make_village(filler=1)
        made = backup.copy_save_folder(folder, datetime(2026, 1, 1, 9, 0, 0))
        wanted = self.snapshot(folder)
        # Play on: every file changes, a new log page appears, one file vanishes.
        self.make_village(filler=7)
        write(folder / LOGS / "Births and Conceptions" /
              "Virtual Villagers 3 Births and Conceptions Log 3.txt", b"Village: Kalahuna (Save 1)\r\n")
        (folder / DATA / "Village Statistics" / "Village Statistics - Save 2.dat").unlink()
        present = self.snapshot(folder)
        backups_before = self.backups_snapshot(folder)

        result = self.restore(folder, made.backup_folder)
        self.assertEqual(self.snapshot(folder), wanted)
        self.assertIn(Path(LOGS, "Births and Conceptions",
                           "Virtual Villagers 3 Births and Conceptions Log 3.txt"), result.plan.remove)
        self.assertEqual(result.before_restore.backup_folder.name,
                         "Backup 2026-02-01 08-00-00 (before restore)")
        safety = result.before_restore.backup_folder
        self.assertEqual(
            {str(r): (safety / r).read_bytes() for r in backup.files_to_back_up(safety)}, present
        )
        # No earlier backup was touched.
        after = self.backups_snapshot(folder)
        for key, value in backups_before.items():
            self.assertEqual(after[key], value)
        # ...and the restore can itself be undone.
        backup.restore_backup(folder, safety, None, FakeProcesses(), datetime(2026, 2, 1, 8, 0, 1))
        self.assertEqual(self.snapshot(folder), present)

    def test_one_slot_is_restored_and_the_other_left_alone(self) -> None:
        folder = self.make_village(filler=1)
        made = backup.copy_save_folder(folder, datetime(2026, 1, 1, 9, 0, 0))
        wanted = self.snapshot(folder)
        self.make_village(filler=7)
        # The meta save is unchanged, so the slot can be restored alone.
        write(folder / "Virtual Villagers - The Secret City0.ldw", b"meta\x01")
        present = self.snapshot(folder)
        result = self.restore(folder, made.backup_folder, slot=1)
        now = self.snapshot(folder)
        for key in now:
            owner = backup.file_slot(Path(key), folder)
            expected = wanted[key] if owner == 1 else present[key]
            self.assertEqual(now[key], expected, key)
        self.assertTrue(result.plan.replace)
        self.assertTrue(all(backup.file_slot(p, folder) == 1 for p in result.plan.replace))

    def test_a_slot_restore_is_refused_when_the_meta_save_differs(self) -> None:
        folder = self.make_village(filler=1)
        made = backup.copy_save_folder(folder, datetime(2026, 1, 1, 9, 0, 0))
        self.make_village(filler=7)
        present = self.snapshot(folder)
        with self.assertRaises(backup.RestoreRefused) as caught:
            self.restore(folder, made.backup_folder, slot=1)
        self.assertIn("slot 0", str(caught.exception))
        self.assertEqual(self.snapshot(folder), present)
        self.assertEqual(len(backup.list_backups(folder)), 1, "no safety backup was made")

    def test_a_slot_restore_is_refused_for_an_unattributable_file(self) -> None:
        folder = self.make_village(filler=1)
        write(folder / DATA / "mystery.dat", b"one")
        made = backup.copy_save_folder(folder, datetime(2026, 1, 1, 9, 0, 0))
        write(folder / DATA / "mystery.dat", b"two")
        with self.assertRaises(backup.RestoreRefused) as caught:
            self.restore(folder, made.backup_folder, slot=1)
        self.assertIn("mystery.dat", str(caught.exception))
        # The same file, unchanged, does not stand in the way.
        write(folder / DATA / "mystery.dat", b"one")
        self.restore(folder, made.backup_folder, slot=1)

    def test_a_log_page_now_owned_by_another_village_is_never_overwritten(self) -> None:
        folder = self.make_village(filler=1)
        made = backup.copy_save_folder(folder, datetime(2026, 1, 1, 9, 0, 0))
        page = folder / LOGS / "Births and Conceptions" / "Virtual Villagers 3 Births and Conceptions Log 1.txt"
        write(page, b"Village: Elsewhere (Save 2)\r\n")      # page 1 reused by Save 2
        with self.assertRaises(backup.RestoreRefused):
            self.restore(folder, made.backup_folder, slot=1)
        self.assertEqual(page.read_bytes(), b"Village: Elsewhere (Save 2)\r\n")

    def test_a_running_game_is_never_restored_into(self) -> None:
        folder = self.make_village(filler=1)
        made = backup.copy_save_folder(folder, datetime(2026, 1, 1, 9, 0, 0))
        self.make_village(filler=7)
        present = self.snapshot(folder)
        processes = FakeProcesses(pids=[42])
        with self.assertRaises(backup.RestoreRefused) as caught:
            self.restore(folder, made.backup_folder, processes=processes)
        self.assertIn("Quit the game from its own menu", str(caught.exception))
        self.assertEqual(self.snapshot(folder), present)
        self.assertNotIn("suspend", [e[0] for e in processes.events], "never paused or killed")
        self.assertEqual(len(backup.list_backups(folder)), 1)

    def test_a_game_started_during_the_safety_backup_stops_the_restore(self) -> None:
        folder = self.make_village(filler=1)
        made = backup.copy_save_folder(folder, datetime(2026, 1, 1, 9, 0, 0))
        self.make_village(filler=7)
        present = self.snapshot(folder)

        class StartsLater(FakeProcesses):
            def find(self, exe_name):
                super().find(exe_name)
                return [42] if len(self.events) > 1 else []

        with self.assertRaises(backup.RestoreRefused):
            self.restore(folder, made.backup_folder, processes=StartsLater())
        self.assertEqual(self.snapshot(folder), present)

    def test_a_failure_part_way_puts_every_file_back(self) -> None:
        folder = self.make_village(filler=1)
        made = backup.copy_save_folder(folder, datetime(2026, 1, 1, 9, 0, 0))
        self.make_village(filler=7)
        write(folder / "extra.txt", b"only now")
        present = self.snapshot(folder)
        real = backup._place
        calls = {"n": 0}

        def fail_third(source, target):
            calls["n"] += 1
            if calls["n"] == 3:
                raise OSError("disk full")
            return real(source, target)

        with mock.patch.object(backup, "_place", side_effect=fail_third):
            with self.assertRaises(backup.BackupError) as caught:
                self.restore(folder, made.backup_folder)
        self.assertIn("Every file was put back", str(caught.exception))
        self.assertEqual(self.snapshot(folder), present)
        self.assertFalse(list(folder.rglob(backup._TEMP_GLOB)))

    def test_a_failed_removal_also_rolls_back(self) -> None:
        folder = self.make_village(filler=1)
        made = backup.copy_save_folder(folder, datetime(2026, 1, 1, 9, 0, 0))
        self.make_village(filler=7)
        write(folder / "a.txt", b"a")
        write(folder / "b.txt", b"b")
        present = self.snapshot(folder)
        real_unlink = Path.unlink

        def unlink(self_path, *args, **kwargs):
            if self_path.name == "b.txt":
                raise PermissionError("in use")
            return real_unlink(self_path, *args, **kwargs)

        with mock.patch.object(Path, "unlink", unlink):
            with self.assertRaises(backup.BackupError):
                self.restore(folder, made.backup_folder)
        self.assertEqual(self.snapshot(folder), present)

    def test_a_copy_that_does_not_verify_is_never_put_in_place(self) -> None:
        folder = self.make_village(filler=1)
        target = folder / "Virtual Villagers - The Secret City1.ldw"
        original = target.read_bytes()
        source = write(Path(self._tmp.name) / "src.ldw", b"new")
        real = backup._hash_file

        def lie(path):
            size, digest = real(path)
            return (size, "0" * 64) if ".vvfp-restore-" in path.name else (size, digest)

        with mock.patch.object(backup, "_hash_file", side_effect=lie):
            with self.assertRaises(backup.BackupError):
                backup._place(source, target)
        self.assertEqual(target.read_bytes(), original)

    def test_only_its_own_backups_can_be_restored_or_deleted(self) -> None:
        folder = self.make_village()
        made = backup.copy_save_folder(folder, datetime(2026, 1, 1, 9, 0, 0))
        other = self.ldw / "elsewhere" / "Backup 2026-01-01 09-00-00"
        write(other / "x.ldw", b"x")
        incomplete = write(folder / "Backups" / "Backup 2026-01-01 09-00-01 INCOMPLETE" / "x", b"x").parent
        for bad in (other, incomplete, folder, folder / "Backups", folder / DATA):
            with self.subTest(bad=bad):
                with self.assertRaises(backup.RestoreRefused):
                    backup.delete_backup(folder, bad)
                with self.assertRaises(backup.RestoreRefused):
                    backup.plan_restore(folder, bad)
        self.assertTrue(other.is_dir() and incomplete.is_dir() and (folder / DATA).is_dir())
        backup.delete_backup(folder, made.backup_folder)
        self.assertFalse(made.backup_folder.exists())
        self.assertTrue((folder / "Virtual Villagers - The Secret City1.ldw").is_file())

    def test_deleting_one_backup_leaves_the_others(self) -> None:
        folder = self.make_village()
        first = backup.copy_save_folder(folder, datetime(2026, 1, 1, 9, 0, 0))
        second = backup.copy_save_folder(folder, datetime(2026, 1, 2, 9, 0, 0))
        keep = self.backups_snapshot(folder)
        backup.delete_backup(folder, first.backup_folder)
        after = self.backups_snapshot(folder)
        self.assertEqual(after, {k: v for k, v in keep.items() if k.startswith(second.backup_folder.name)})

    def test_a_restore_never_writes_into_any_backup(self) -> None:
        folder = self.make_village(filler=1)
        made = backup.copy_save_folder(folder, datetime(2026, 1, 1, 9, 0, 0))
        other = backup.copy_save_folder(folder, datetime(2026, 1, 1, 9, 0, 5))
        self.make_village(filler=7)
        keep = self.backups_snapshot(folder)
        self.restore(folder, made.backup_folder)
        self.restore(folder, other.backup_folder, slot=None, now=datetime(2026, 2, 1, 8, 0, 9))
        after = self.backups_snapshot(folder)
        for key, value in keep.items():
            self.assertEqual(after[key], value, key)



class DeleteBackupTests(RestoreBase):
    """Found live: OneDrive marks folders read-only, and a plain rmtree then
    stopped part-way, leaving a half-emptied backup that was still listed."""

    @unittest.skipUnless(sys.platform == "win32", "Windows file attributes")
    def test_read_only_files_and_folders_are_deleted(self) -> None:
        import ctypes
        folder = self.make_village()
        made = backup.copy_save_folder(folder, datetime(2026, 1, 1, 9, 0, 0))
        inner = made.backup_folder / DATA / "Village Statistics"
        for path in (inner, inner / "Village Statistics - Save 1.dat", made.backup_folder / DATA):
            self.assertTrue(ctypes.windll.kernel32.SetFileAttributesW(str(path), 1))  # READONLY
        backup.delete_backup(folder, made.backup_folder)
        self.assertEqual(list((folder / "Backups").iterdir()), [])

    def test_a_refused_rename_deletes_nothing(self) -> None:
        folder = self.make_village()
        made = backup.copy_save_folder(folder, datetime(2026, 1, 1, 9, 0, 0))
        keep = self.backups_snapshot(folder)
        with mock.patch.object(Path, "rename", side_effect=PermissionError("in use")):
            with self.assertRaises(backup.BackupError) as caught:
                backup.delete_backup(folder, made.backup_folder)
        self.assertIn("nothing was deleted", str(caught.exception))
        self.assertEqual(self.backups_snapshot(folder), keep)
        self.assertEqual(len(backup.list_backups(folder)), 1)

    def test_a_delete_that_cannot_finish_never_leaves_a_listed_backup(self) -> None:
        folder = self.make_village()
        made = backup.copy_save_folder(folder, datetime(2026, 1, 1, 9, 0, 0))
        with mock.patch.object(backup, "DELETE_RETRY_SECONDS", 0), \
             mock.patch.object(backup.shutil, "rmtree", side_effect=PermissionError("locked")):
            with self.assertRaises(backup.BackupError) as caught:
                backup.delete_backup(folder, made.backup_folder)
        self.assertIn("(deleting)", str(caught.exception))
        self.assertEqual(backup.list_backups(folder), [])
        self.assertTrue((folder / "Virtual Villagers - The Secret City1.ldw").is_file())

    def test_a_briefly_locked_file_is_retried(self) -> None:
        folder = self.make_village()
        made = backup.copy_save_folder(folder, datetime(2026, 1, 1, 9, 0, 0))
        real = backup.shutil.rmtree
        calls = {"n": 0}

        def flaky(path, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise PermissionError("held by the indexer")
            return real(path, **kwargs)

        with mock.patch.object(backup, "DELETE_RETRY_SECONDS", 0), \
             mock.patch.object(backup.shutil, "rmtree", side_effect=flaky):
            backup.delete_backup(folder, made.backup_folder)
        self.assertEqual(list((folder / "Backups").iterdir()), [])


class CodexFollowUpTests(RestoreBase):
    """The review findings on #521, each pinned."""

    def test_a_backup_is_made_under_a_name_that_is_never_listed(self) -> None:
        folder = self.make_village()
        seen = []
        real = backup._copy_one

        def watch(source, destination):
            seen.append(destination.relative_to(folder / "Backups").parts[0])
            self.assertEqual(backup.list_backups(folder), [], "listed while being made")
            return real(source, destination)

        with mock.patch.object(backup, "_copy_one", side_effect=watch):
            made = backup.copy_save_folder(folder, NOW)
        self.assertTrue(all(name.endswith(" (in progress)") for name in seen))
        self.assertEqual(made.backup_folder.name, "Backup 2026-10-04 13-05-22")
        self.assertEqual([i.path for i in backup.list_backups(folder)], [made.backup_folder])

    def test_a_briefly_held_folder_is_still_given_its_name(self) -> None:
        folder = self.make_village()
        real = Path.rename
        calls = {"n": 0}

        def held_once(self_path, target):
            calls["n"] += 1
            if calls["n"] == 1:
                raise PermissionError("OneDrive has it")
            return real(self_path, target)

        with mock.patch.object(backup, "DELETE_RETRY_SECONDS", 0),              mock.patch.object(Path, "rename", held_once):
            made = backup.copy_save_folder(folder, NOW)
        self.assertEqual(made.backup_folder.name, "Backup 2026-10-04 13-05-22")
        self.assertTrue(made.backup_folder.is_dir())

    def test_a_second_failed_backup_in_one_second_is_still_set_aside(self) -> None:
        folder = self.make_village()
        with mock.patch.object(backup, "_copy_one", side_effect=OSError("disk full")):
            for _ in range(2):
                with self.assertRaises(backup.BackupError):
                    backup.copy_save_folder(folder, NOW)
        names = sorted(p.name for p in (folder / "Backups").iterdir())
        self.assertEqual(names, ["Backup 2026-10-04 13-05-22 INCOMPLETE",
                                 "Backup 2026-10-04 13-05-22 INCOMPLETE (2)"])
        self.assertEqual(backup.list_backups(folder), [])

    @unittest.skipUnless(sys.platform == "win32", "junctions are a Windows feature")
    def test_a_junction_is_recognised_without_path_is_junction(self) -> None:
        import _winapi
        folder = self.make_village()
        _winapi.CreateJunction(str(self.documents), str(folder / "link"))
        with mock.patch.object(Path, "is_junction", create=True, new=None):
            self.assertTrue(backup._is_link(folder / "link"))
            self.assertFalse(backup._is_link(folder / DATA))
            self.assertFalse(any(r.parts[0] == "link" for r in backup.files_to_back_up(folder)))

    def test_a_linked_file_is_not_copied(self) -> None:
        folder = self.make_village()
        outside = write(Path(self._tmp.name) / "outside.txt", b"not a save")
        try:
            os.symlink(outside, folder / "linked.txt")
        except (OSError, NotImplementedError):
            self.skipTest("this account cannot create symbolic links")
        self.assertNotIn(Path("linked.txt"), backup.files_to_back_up(folder))

    def test_files_are_checked_for_links_too(self) -> None:
        # Creating a real symbolic link needs a privilege most accounts lack,
        # so the test above often skips; this pins that files are asked too.
        folder = self.make_village()
        real = backup._is_link
        with mock.patch.object(
            backup, "_is_link", side_effect=lambda path: path.name.endswith("0.ldw") or real(path)
        ):
            names = [r.name for r in backup.files_to_back_up(folder)]
        self.assertNotIn("Virtual Villagers - The Secret City0.ldw", names)
        self.assertIn("Virtual Villagers - The Secret City1.ldw", names)

    @unittest.skipUnless(sys.platform == "win32", "Windows process API")
    def test_an_unfinished_process_list_fails_closed(self) -> None:
        processes = backup.WindowsProcesses()
        with mock.patch.object(backup.ctypes, "get_last_error", return_value=5):
            with self.assertRaises(backup.BackupError):
                processes.find("Virtual Villagers - A New Home - Modded.exe")

    def test_only_patcher_files_are_given_a_slot(self) -> None:
        folder = self.ldw / "Virtual Villagers - A New Home - Modded"
        for name, expected in {
            "My Save 1 notes.txt": "unknown",
            "Notes - Save 1.txt": "unknown",
            "Other Mod/Thing - Save 1.dat": "unknown",
            "Other Mod/Village: x (Save 1).txt": "unknown",
            "Village Statistics - Save 1.txt": 1,
            f"{DATA}/Village Masks - Save 2.dat": 2,
            f"{DATA}/Village Masks - Save 2.dat.bak": "unknown",
        }.items():
            with self.subTest(name=name):
                write(folder / name, b"Village: K (Save 1)\r\n")
                self.assertEqual(backup.file_slot(Path(name), folder), expected)

    def test_a_file_that_looks_like_a_temporary_is_never_touched(self) -> None:
        folder = self.make_village()
        target = folder / "Virtual Villagers - The Secret City1.ldw"
        lookalike = write(folder / "Virtual Villagers - The Secret City1.ldw.vvfp-restore-aaaaaaaaaaaa.tmp", b"mine")
        source = write(Path(self._tmp.name) / "src.ldw", b"restored")
        ids = iter(["a" * 32, "b" * 32])

        class FakeUuid:
            def __init__(self, value):
                self.hex = value

        with mock.patch.object(backup.uuid, "uuid4", side_effect=lambda: FakeUuid(next(ids))):
            backup._place(source, target)
        self.assertEqual(target.read_bytes(), b"restored")
        self.assertEqual(lookalike.read_bytes(), b"mine")

    def test_a_game_started_while_files_are_changed_stops_and_rolls_back(self) -> None:
        folder = self.make_village(filler=1)
        made = backup.copy_save_folder(folder, datetime(2026, 1, 1, 9, 0, 0))
        self.make_village(filler=7)
        write(folder / "extra.txt", b"only now")
        present = self.snapshot(folder)

        class StartsMidway(FakeProcesses):
            def find(self, exe_name):
                super().find(exe_name)
                return [42] if len(self.events) > 4 else []

        with self.assertRaises(backup.BackupError) as caught:
            backup.restore_backup(folder, made.backup_folder, None, StartsMidway(),
                                  datetime(2026, 2, 1, 8, 0, 0))
        self.assertIn("started during the restore", str(caught.exception))
        self.assertEqual(self.snapshot(folder), present)

class RestoreGuiTests(unittest.TestCase):
    setUpClass = classmethod(GuiTests.setUpClass.__func__)
    method = GuiTests.method

    def test_restore_sits_beside_back_up_on_both_tabs(self) -> None:
        single = ast.get_source_segment(self.source, self.method("_build_single_tab"))
        self.assertIn('links, "Restore Saves...", self._restore_single_saves', single)
        bulk = ast.get_source_segment(self.source, self.method("_build_all_tab"))
        self.assertIn('"Restore saves..."', bulk)
        self.assertIn("self._restore_saves(game)", bulk)

    def test_restore_planning_runs_off_the_main_thread(self) -> None:
        run = ast.get_source_segment(self.source, self.method("_run_restore"))
        self.assertIn("lambda: vv_save_backup.plan_restore(folder, info.path, slot)", run)
        self.assertEqual(run.count("vv_save_backup.plan_restore("), 1)

    def test_long_dialogs_scroll(self) -> None:
        for name in ("_show_backup_chooser", "_show_backup_results"):
            body = ast.get_source_segment(self.source, self.method(name))
            self.assertIn("self._scrolling_dialog(", body, name)
        helper = ast.get_source_segment(self.source, self.method("_scrolling_dialog"))
        self.assertIn("ttk.Scrollbar", helper)

    def test_a_resume_problem_is_shown(self) -> None:
        results = ast.get_source_segment(self.source, self.method("_show_backup_results"))
        self.assertIn("result.resume_problems", results)

    def test_the_restore_window_lists_restores_and_deletes_through_the_module(self) -> None:
        window = ast.get_source_segment(self.source, self.method("_show_restore_window"))
        self.assertIn("vv_save_backup.list_backups(", window)
        self.assertIn("vv_save_backup.delete_backup(", window)
        run = ast.get_source_segment(self.source, self.method("_run_restore"))
        self.assertIn("vv_save_backup.plan_restore(", run)
        self.assertIn("vv_save_backup.restore_backup(", run)
        self.assertIn("self._run_with_wait(", run)
        self.assertIn("askyesno", run)


if __name__ == "__main__":
    unittest.main()
