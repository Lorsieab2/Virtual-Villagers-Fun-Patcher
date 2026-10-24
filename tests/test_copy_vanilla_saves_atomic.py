"""copy_vanilla_saves is all-or-none.

Copying the vanilla saves into the "Modded 256" save folder stages and
verifies every copy beside the destination first, then swaps the whole set in
with a backup of the saves it replaces.  A failure at any step (a copy, a
move out, a move in, the final check, a locked save, a crash) leaves every
file under the save root byte-identical to before, with its time kept, and
never touches the patcher's logs, .dat files or Backups folder.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher as vvp  # noqa: E402
from vv_fun_patcher import PatcherError, copy_vanilla_saves, load_builds  # noqa: E402

MODE = "experimental_expanded_256"


def snapshot(root: Path) -> dict[str, tuple[str, bytes | None, int]]:
    """Every file and folder under ``root``: kind, bytes, modification time."""
    found: dict[str, tuple[str, bytes | None, int]] = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_dir():
            found[rel] = ("dir", None, 0)
        else:
            found[rel] = ("file", path.read_bytes(), path.stat().st_mtime_ns)
    return found


class AtomicSaveCopyTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.root = Path(self._temp.name) / "LDW"
        self.build = load_builds()[2]
        title = self.build.title
        self.vanilla = self.root / title
        self.modded = self.root / f"{title} - Modded 256"
        self.vanilla.mkdir(parents=True)
        self.sources = {
            f"{title}0.ldw": b"vanilla-zero" * 50,
            f"{title}1.ldw": b"vanilla-one" * 70,
            f"{title}21.ldw": b"vanilla-twenty-one" * 30,
        }
        for index, (name, data) in enumerate(self.sources.items()):
            path = self.vanilla / name
            path.write_bytes(data)
            os.utime(path, ns=(1_600_000_000_000_000_000 + index, 1_600_000_000_000_000_000 + index))
        patch = mock.patch.object(vvp, "SAVE_COPY_LOCK_DELAY_SECONDS", 0)
        patch.start()
        self.addCleanup(patch.stop)

    def tearDown(self) -> None:
        self._temp.cleanup()

    def make_existing_modded(self) -> None:
        title = self.build.title
        self.modded.mkdir(parents=True)
        files = {
            f"{title}0.ldw": b"modded-zero",
            f"{title}1.ldw": b"modded-one" * 9,
            f"{title}5.ldw": b"modded-five",
            "Virtual Villagers Fun Patcher/Save 1/Village History.txt": b"per-save history",
            "Virtual Villagers Fun Patcher/Save 1/ElderTotems.dat": b"\x07totems",
            "Virtual Villagers Fun Patcher Logs/Village History 1.txt": b"history",
            "Virtual Villagers Fun Patcher Data/titles 1.dat": b"\x01\x02dat",
            f"{title}1 parents.dat": b"sidecar",
            f"Backups/Backup 2026-10-01/{title}1.ldw": b"backed-up",
        }
        for index, (rel, data) in enumerate(files.items()):
            path = self.modded / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            os.utime(path, ns=(1_500_000_000_000_000_000 + index, 1_500_000_000_000_000_000 + index))

    def run_copy(self) -> dict:
        return copy_vanilla_saves(self.build, MODE, replace_existing=True, save_root=self.root)

    def assert_untouched(self, before: dict) -> None:
        self.assertEqual(snapshot(self.root), before)

    # -- a normal run ------------------------------------------------------

    def test_normal_replace_gives_exactly_the_vanilla_set_and_keeps_patcher_files(self) -> None:
        self.make_existing_modded()
        before = snapshot(self.root)
        result = self.run_copy()
        self.assertEqual(result["status"], "vanilla_saves_copied")
        self.assertEqual(result["copied_files"], 3)
        title = self.build.title
        self.assertEqual(
            sorted(p.name for p in self.modded.glob(f"{title}*.ldw")), sorted(self.sources)
        )
        for name, data in self.sources.items():
            placed = self.modded / name
            self.assertEqual(placed.read_bytes(), data)
            self.assertEqual(placed.stat().st_mtime_ns, (self.vanilla / name).stat().st_mtime_ns)
        after = snapshot(self.root)
        kept = 0
        for rel, entry in before.items():
            inside = rel[len(self.modded.name) + 1:] if rel.startswith(self.modded.name + "/") else None
            if inside is not None and ("/" in inside or not inside.endswith(".ldw")):
                self.assertEqual(after.get(rel), entry, rel)
                kept += 1
        self.assertGreaterEqual(kept, 6, "the patcher's logs, .dat files and Backups were checked")
        # Nothing left beside the save folder: no staging, no backup.
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), sorted([self.vanilla.name, self.modded.name]))
        # The vanilla folder is only read.
        for rel, entry in before.items():
            if rel.startswith(self.vanilla.name + "/"):
                self.assertEqual(after[rel], entry)

    def test_normal_first_copy_creates_the_folder(self) -> None:
        result = copy_vanilla_saves(self.build, MODE, save_root=self.root)
        self.assertEqual(result["status"], "vanilla_saves_copied")
        self.assertEqual(
            {p.name: p.read_bytes() for p in self.modded.iterdir()}, self.sources
        )
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), sorted([self.vanilla.name, self.modded.name]))

    def test_existing_saves_without_replace_are_preserved(self) -> None:
        self.make_existing_modded()
        before = snapshot(self.root)
        result = copy_vanilla_saves(self.build, MODE, save_root=self.root)
        self.assertEqual(result["status"], "existing_modded_saves_preserved")
        self.assert_untouched(before)

    # -- fault injection -----------------------------------------------------

    def test_failure_on_every_staging_copy_changes_nothing(self) -> None:
        for fresh in (False, True):
            for fail_at in range(1, len(self.sources) + 1):
                with self.subTest(fresh=fresh, fail_at=fail_at):
                    if self.modded.exists():
                        shutil.rmtree(self.modded)
                    if not fresh:
                        self.make_existing_modded()
                    before = snapshot(self.root)
                    real = shutil.copy2
                    calls = {"n": 0}

                    def flaky(src, dst, *a, **k):
                        calls["n"] += 1
                        if calls["n"] == fail_at:
                            Path(dst).write_bytes(b"half")
                            raise OSError(28, "No space left on device")
                        return real(src, dst, *a, **k)

                    with mock.patch.object(vvp.shutil, "copy2", flaky):
                        with self.assertRaises(OSError):
                            self.run_copy()
                    self.assert_untouched(before)

    def test_failure_on_every_swap_move_changes_nothing(self) -> None:
        # 3 existing saves moved out, then 3 staged saves moved in.
        for fresh in (False, True):
            moves = 3 if fresh else 6
            for fail_at in range(1, moves + 1):
                with self.subTest(fresh=fresh, fail_at=fail_at):
                    if self.modded.exists():
                        shutil.rmtree(self.modded)
                    if not fresh:
                        self.make_existing_modded()
                    before = snapshot(self.root)
                    real = os.replace
                    calls = {"n": 0}

                    def flaky(src, dst):
                        calls["n"] += 1
                        if calls["n"] == fail_at:
                            raise OSError(5, "Simulated failure during the swap")
                        return real(src, dst)

                    with mock.patch.object(vvp.os, "replace", flaky):
                        with self.assertRaises(OSError):
                            self.run_copy()
                    self.assert_untouched(before)

    def test_crash_during_the_swap_changes_nothing(self) -> None:
        self.make_existing_modded()
        before = snapshot(self.root)
        real = os.replace
        calls = {"n": 0}

        def crash(src, dst):
            calls["n"] += 1
            if calls["n"] == 5:
                raise KeyboardInterrupt
            return real(src, dst)

        with mock.patch.object(vvp.os, "replace", crash):
            with self.assertRaises(KeyboardInterrupt):
                self.run_copy()
        self.assert_untouched(before)

    def test_a_placed_save_that_fails_its_final_check_changes_nothing(self) -> None:
        self.make_existing_modded()
        before = snapshot(self.root)
        real = os.replace
        calls = {"n": 0}

        def corrupting(src, dst):
            result = real(src, dst)
            calls["n"] += 1
            if calls["n"] == 6:            # the last staged save moved in
                Path(dst).write_bytes(b"corrupted")
            return result

        with mock.patch.object(vvp.os, "replace", corrupting):
            with self.assertRaisesRegex(PatcherError, "verification failed"):
                self.run_copy()
        self.assert_untouched(before)

    def test_a_staged_copy_that_does_not_match_changes_nothing(self) -> None:
        self.make_existing_modded()
        before = snapshot(self.root)
        real = shutil.copy2

        def wrong(src, dst, *a, **k):
            real(src, dst, *a, **k)
            Path(dst).write_bytes(Path(dst).read_bytes()[:-1] + b"?")

        with mock.patch.object(vvp.shutil, "copy2", wrong):
            with self.assertRaisesRegex(PatcherError, "verification failed"):
                self.run_copy()
        self.assert_untouched(before)

    def test_a_briefly_locked_save_is_retried(self) -> None:
        self.make_existing_modded()
        real = os.replace
        calls = {"n": 0}

        def busy_once(src, dst):
            calls["n"] += 1
            if calls["n"] == 2:
                raise PermissionError(13, "The process cannot access the file")
            return real(src, dst)

        with mock.patch.object(vvp.os, "replace", busy_once):
            result = self.run_copy()
        self.assertEqual(result["status"], "vanilla_saves_copied")
        for name, data in self.sources.items():
            self.assertEqual((self.modded / name).read_bytes(), data)

    def test_a_save_that_stays_locked_fails_cleanly(self) -> None:
        self.make_existing_modded()
        before = snapshot(self.root)
        locked = self.modded / f"{self.build.title}1.ldw"
        real = os.replace

        def locked_replace(src, dst):
            if Path(src) == locked:
                raise PermissionError(13, "The process cannot access the file")
            return real(src, dst)

        with mock.patch.object(vvp.os, "replace", locked_replace):
            with self.assertRaisesRegex(PatcherError, "locked by another program"):
                self.run_copy()
        self.assert_untouched(before)

    @unittest.skipUnless(os.name == "nt", "Windows file locks")
    def test_a_save_held_open_by_another_program_fails_cleanly(self) -> None:
        self.make_existing_modded()
        before = snapshot(self.root)
        # An open handle without delete sharing blocks renaming it on Windows.
        with open(self.modded / f"{self.build.title}1.ldw", "rb"):
            with self.assertRaisesRegex(PatcherError, "locked by another program"):
                self.run_copy()
        self.assert_untouched(before)

    def test_an_undo_that_fails_keeps_every_original_in_the_backup(self) -> None:
        self.make_existing_modded()
        title = self.build.title
        originals = {
            p.name: p.read_bytes() for p in self.modded.glob(f"{title}*.ldw")
        }
        real = os.replace
        calls = {"n": 0}

        def failing(src, dst):
            calls["n"] += 1
            if calls["n"] == 4:                      # the first save moved in
                raise OSError(5, "swap failed")
            if calls["n"] >= 5 and ".copy-backup-" in str(src):
                raise OSError(5, "undo failed")      # every undo move fails
            return real(src, dst)

        with mock.patch.object(vvp.os, "replace", failing):
            with self.assertRaisesRegex(PatcherError, "kept in"):
                self.run_copy()
        backups = [p for p in self.root.iterdir() if ".copy-backup-" in p.name]
        self.assertEqual(len(backups), 1)
        # Not one original save was deleted: each is in the folder or the backup.
        for name, data in originals.items():
            held = [p for p in (self.modded / name, backups[0] / name) if p.is_file()]
            self.assertIn(data, [p.read_bytes() for p in held], name)
        self.assertEqual(
            (self.modded / "Virtual Villagers Fun Patcher Logs/Village History 1.txt").read_bytes(),
            b"history",
        )


if __name__ == "__main__":
    unittest.main()
