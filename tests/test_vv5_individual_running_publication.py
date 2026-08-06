from __future__ import annotations

import tempfile
import unittest
from unittest import mock
from pathlib import Path

from src.vv5_individual_running import PatcherError, _parent, _publish, _state, install_atomic, remove_atomic, recover_atomic


class VV5RunningPublicationTests(unittest.TestCase):
    def test_pair_publish_and_remove_style_restore_is_exact(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            exe, dll = root / "game.exe", root / "VVFP VV5 Full Mastery Candidate.dll"
            exe.write_bytes(b"parent-exe")
            dll.write_bytes(b"parent-dll")
            destinations = [exe, dll]
            pre = {p: _state(p) for p in destinations}
            published = {exe: b"candidate-exe", dll: b"candidate-dll"}
            _publish("install", destinations, pre, published, root)
            self.assertEqual(exe.read_bytes(), b"candidate-exe")
            self.assertEqual(dll.read_bytes(), b"candidate-dll")
            restore = {exe: b"parent-exe", dll: b"parent-dll"}
            pre2 = {p: _state(p) for p in destinations}
            _publish("remove", destinations, pre2, restore, root)
            self.assertEqual(exe.read_bytes(), b"parent-exe")
            self.assertEqual(dll.read_bytes(), b"parent-dll")
            self.assertEqual(list(root.glob(".vv5run-*")), [])

    def test_second_replace_failure_never_accepts_mixed_pair(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            exe, dll = root / "game.exe", root / "companion.dll"
            exe.write_bytes(b"exe0")
            dll.write_bytes(b"dll0")
            pre = {exe: _state(exe), dll: _state(dll)}
            published = {exe: b"exe1", dll: b"dll1"}
            original = __import__("os").replace
            calls = {"n": 0}

            def fail_second(src, dst):
                calls["n"] += 1
                if calls["n"] == 2:
                    raise OSError("injected second replace failure")
                return original(src, dst)

            with mock.patch("src.vv5_individual_running.os.replace", side_effect=fail_second):
                with self.assertRaises(PatcherError):
                    _publish("install", [exe, dll], pre, published, root)
            self.assertEqual(exe.read_bytes(), b"exe0")
            self.assertEqual(dll.read_bytes(), b"dll0")
            self.assertEqual(list(root.glob(".vv5run-*")), [])

    def test_reparse_ancestor_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            target = root / "real"
            target.mkdir()
            link = root / "link"
            try:
                link.symlink_to(target, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation unavailable")
            with self.assertRaises(PatcherError):
                _parent([link / "a.exe", link / "b.dll"])

    def test_immediate_mode_rejected_before_any_filesystem_access(self) -> None:
        """The unsupported mode gate is the first operation of each API."""
        with mock.patch("src.vv5_individual_running.Path.read_bytes", side_effect=AssertionError("read")), \
             mock.patch("src.vv5_individual_running.Path.read_text", side_effect=AssertionError("text")), \
             mock.patch("src.vv5_individual_running.os.lstat", side_effect=AssertionError("lstat")), \
             mock.patch("src.vv5_individual_running.os.scandir", side_effect=AssertionError("scandir")):
            with self.assertRaises(PatcherError):
                install_atomic(Path("missing.exe"), Path("missing.exe"), "immediate_fixed")
            with self.assertRaises(PatcherError):
                remove_atomic(Path("missing.exe"), "immediate_fixed")
            with self.assertRaises(PatcherError):
                recover_atomic(Path("missing-report.json"), "immediate_fixed")

    def test_cross_game_recovery_report_rejected_by_owner_before_replay(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            report = root / ".vv5run-recovery-cross-game.json"
            report.write_text('{"feature_owner":"vv3_individual_full_mastery","mode":"collection_progression","parent_sha256":"x","candidate_sha256":"y"}', encoding="utf-8")
            with self.assertRaises(PatcherError):
                recover_atomic(report)
            self.assertTrue(report.is_file())


if __name__ == "__main__":
    unittest.main()
