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
        with self.assertRaises(backup.BackupError):
            backup.back_up_save_folder(folder, processes, NOW)
        self.assertIn(("resume", 111), processes.events)


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
        self.assertIn("for row, build in enumerate(self.builds)", bulk)
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


if __name__ == "__main__":
    unittest.main()
