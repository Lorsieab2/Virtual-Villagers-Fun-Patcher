from __future__ import annotations

import tempfile
import unittest
import json
from unittest import mock
from pathlib import Path

from src.vv5_individual_running import PatcherError, VV5_EXE_BASENAME, DLL_NAME, _parent, _publish, _state, install_atomic, remove_atomic, recover_atomic


class VV5RunningPublicationTests(unittest.TestCase):
    def test_all_public_vv5_running_apis_reject_unsupported_mode_before_io(self) -> None:
        import src.vv_fun_patcher as patcher
        missing = Path("missing-vv5-running.exe")
        with mock.patch.object(patcher, "identify", side_effect=AssertionError("identify")), \
             mock.patch.object(patcher, "validate_all_sources", side_effect=AssertionError("validate")), \
             mock.patch.object(patcher, "load_builds", side_effect=AssertionError("catalog")), \
             mock.patch.object(patcher, "get_fun_patch", side_effect=AssertionError("lookup")):
            with self.assertRaises(patcher.PatcherError):
                patcher.dry_run(missing, "immediate_fixed", ("vv5_individual_grant_running_candidate",))
            with self.assertRaises(patcher.PatcherError):
                patcher.apply_patch(missing, "expanded_256", False, ("vv5_individual_grant_running_candidate",))
            with self.assertRaises(patcher.PatcherError):
                patcher.dry_run_all({}, "immediate_fixed", ("vv5_individual_grant_running_candidate",))
            with self.assertRaises(patcher.PatcherError):
                patcher.apply_all({}, "expanded_256", False, ("vv5_individual_grant_running_candidate",))

    def test_unresolved_report_is_bound_to_external_issuance(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            exe, dll = root / VV5_EXE_BASENAME, root / DLL_NAME
            exe.write_bytes(b"parent-exe")
            dll.write_bytes(b"parent-dll")
            pre = {exe: _state(exe), dll: _state(dll)}
            published = {exe: b"candidate-exe", dll: b"candidate-dll"}
            with mock.patch("vv3_individual_full_mastery._replace_verified", side_effect=OSError("replace")), \
                 mock.patch("vv3_individual_full_mastery._restore_member", return_value=False):
                with self.assertRaises(PatcherError):
                    _publish("install", [exe, dll], pre, published, root)
            reports = list(root.glob(".vv5run-recovery-*.json"))
            issuances = list(root.glob(".vv5run-issuance-*.json"))
            self.assertEqual(len(reports), 1)
            self.assertEqual(len(issuances), 1)
            report = json.loads(reports[0].read_text(encoding="utf-8"))
            issuance = json.loads(issuances[0].read_text(encoding="utf-8"))
            self.assertEqual(report["issuance_token"], issuance["token"])
            self.assertEqual(issuance["report_name"], reports[0].name)
            self.assertEqual(issuance["report_sha256"], __import__("hashlib").sha256(reports[0].read_bytes()).hexdigest().upper())

    def test_recovery_rejects_nested_or_alternate_destination_paths(self) -> None:
        from src.vv5_individual_running import _validate_report
        member = {
            "destination_relative": f"nested/{VV5_EXE_BASENAME}",
            "destination_type": "regular_file", "pre_exists": False,
            "pre_sha256": None, "pre_size": 0,
            "published_sha256": "A" * 64, "published_size": 1,
            "backup_relative": None, "stage_relative": None,
            "backup_inventory": None, "stage_inventory": None,
        }
        payload = {
            "schema_version": 2, "operation": "install_new", "recovery_root": ".",
            "destination_parent": ".", "initial_precondition": {"kind": "absent", "members": []},
            "replay_guard": "published_or_initial", "members": [member, {**member, "destination_relative": DLL_NAME}],
            "ownership_inventory": [], "failure_diagnostic": "test",
        }
        with self.assertRaises(PatcherError):
            _validate_report(payload, Path(tempfile.gettempdir()))

    def test_pair_publish_and_remove_style_restore_is_exact(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            exe, dll = root / VV5_EXE_BASENAME, root / DLL_NAME
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
            exe, dll = root / VV5_EXE_BASENAME, root / DLL_NAME
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

    def test_generic_render_rejects_immediate_before_variant_or_catalog_lookup(self) -> None:
        from types import SimpleNamespace
        import src.vv_fun_patcher as patcher
        with mock.patch.object(patcher, "get_patch_variant", side_effect=AssertionError("variant lookup")), \
             mock.patch.object(patcher, "_selected_fun_patches", side_effect=AssertionError("catalog lookup")):
            with self.assertRaises(patcher.PatcherError):
                patcher.render_patched_bytes(Path("missing.exe"), SimpleNamespace(id="vv5"), "immediate_fixed", ("vv5_individual_grant_running_candidate",))

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
