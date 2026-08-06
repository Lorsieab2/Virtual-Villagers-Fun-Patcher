from __future__ import annotations

import tempfile
import unittest
import json
import shutil
from unittest import mock
from pathlib import Path

from src.vv5_individual_running import PatcherError, VV5_EXE_BASENAME, DLL_NAME, VV5_MODE, ISSUANCE_REGISTRY_NAME, _parent, _publish, _state, install_atomic, remove_atomic, recover_atomic


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
            issuances = [p for p in (root / ISSUANCE_REGISTRY_NAME).glob("*.json") if ".v" not in p.name]
            successors = [p for p in (root / ISSUANCE_REGISTRY_NAME).glob("*.v*.json")]
            self.assertEqual(len(reports), 1)
            self.assertEqual(len(issuances), 1)
            self.assertEqual(len(successors), 1)
            self.assertTrue((root / ISSUANCE_REGISTRY_NAME / f".{issuances[0].name}.pointer").exists())
            report = json.loads(reports[0].read_text(encoding="utf-8"))
            issuance = json.loads(issuances[0].read_text(encoding="utf-8"))
            bound = json.loads(successors[0].read_text(encoding="utf-8"))
            self.assertEqual(report["issuance_token"], issuance["token"])
            self.assertNotIn("report_name", issuance)
            self.assertEqual(bound["report_name"], reports[0].name)
            self.assertEqual(bound["report_sha256"], __import__("hashlib").sha256(reports[0].read_bytes()).hexdigest().upper())
            self.assertEqual(issuance["destination_parent_absolute"], str(root).lower())
            self.assertEqual(issuance["registry_relative"], ISSUANCE_REGISTRY_NAME)

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

    def test_c287_production_failure_strict_replay_cleans_pair_report_and_registry(self) -> None:
        """A real VV5 publication report must replay through the strict path once."""
        import hashlib
        import src.vv5_individual_running as running
        parent_exe = b"P" * 0xF4000
        parent_dll = b"parent-dll"
        candidate_exe = b"C" * 0xF6000
        candidate_dll = parent_dll
        values = {
            "VV5_PARENT_EXE_SHA256": hashlib.sha256(parent_exe).hexdigest().upper(),
            "VV5_CANDIDATE_EXE_SHA256": hashlib.sha256(candidate_exe).hexdigest().upper(),
            "VV5_PARENT_DLL_SHA256": hashlib.sha256(parent_dll).hexdigest().upper(),
            "VV5_CANDIDATE_DLL_SHA256": hashlib.sha256(candidate_dll).hexdigest().upper(),
            "DLL_SHA256": hashlib.sha256(parent_dll).hexdigest().upper(),
            "DLL_SIZE": len(parent_dll),
        }
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            exe, dll = root / VV5_EXE_BASENAME, root / DLL_NAME
            exe.write_bytes(parent_exe); dll.write_bytes(parent_dll)
            pre = {exe: _state(exe), dll: _state(dll)}
            with mock.patch.multiple(running, **values), \
                 mock.patch("vv3_individual_full_mastery._replace_verified", side_effect=OSError("replace")), \
                 mock.patch("vv3_individual_full_mastery._restore_member", return_value=False):
                with self.assertRaises(PatcherError):
                    _publish("install", [exe, dll], pre, {exe: candidate_exe, dll: candidate_dll}, root)
            report = next(root.glob(".vv5run-recovery-*.json"))
            issuance = next((root / ISSUANCE_REGISTRY_NAME).glob("*.json"))
            relocated = root.parent / "relocated-vv5-evidence"
            shutil.copytree(root, relocated)
            try:
                with mock.patch.multiple(running, **values):
                    with self.assertRaises(PatcherError):
                        recover_atomic(relocated / report.name)
                self.assertTrue(report.exists())
                self.assertTrue(issuance.exists())
            finally:
                shutil.rmtree(relocated)
            with mock.patch.multiple(running, **values):
                recover_atomic(report)
            self.assertEqual(exe.read_bytes(), parent_exe)
            self.assertEqual(dll.read_bytes(), parent_dll)
            self.assertFalse(report.exists())
            self.assertFalse(issuance.exists())
            self.assertFalse((root / ISSUANCE_REGISTRY_NAME).exists())
            self.assertEqual(list(root.glob(".vv5run-*")), [])

    def test_c287_issuance_substitution_before_cleanup_is_rejected(self) -> None:
        import src.vv5_individual_running as running
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            exe, dll = root / VV5_EXE_BASENAME, root / DLL_NAME
            exe.write_bytes(b"parent-exe"); dll.write_bytes(b"parent-dll")
            pre = {exe: _state(exe), dll: _state(dll)}
            published = {exe: b"candidate-exe", dll: b"candidate-dll"}
            real_rename = running.os.rename
            def substitute(src, dst):
                if Path(src).parent.name == ISSUANCE_REGISTRY_NAME and Path(src).suffix == ".json":
                    Path(src).write_bytes(b"foreign")
                return real_rename(src, dst)
            with mock.patch.object(running.os, "rename", side_effect=substitute):
                with self.assertRaises(PatcherError):
                    _publish("install", [exe, dll], pre, published, root)
            self.assertEqual(exe.read_bytes(), b"candidate-exe")
            self.assertEqual(dll.read_bytes(), b"candidate-dll")
            self.assertTrue(any((root / ISSUANCE_REGISTRY_NAME).iterdir()))

    def test_c287_issuance_creation_race_is_exclusive_and_does_not_publish(self) -> None:
        import src.vv5_individual_running as running
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            exe, dll = root / VV5_EXE_BASENAME, root / DLL_NAME
            exe.write_bytes(b"parent-exe"); dll.write_bytes(b"parent-dll")
            pre = {exe: _state(exe), dll: _state(dll)}
            original_link = running.os.link
            def race_link(src, dst):
                Path(dst).write_bytes(b"foreign-issuance")
                return original_link(src, dst)
            with mock.patch.object(running.os, "link", side_effect=race_link):
                with self.assertRaises(PatcherError):
                    _publish("install", [exe, dll], pre, {exe: b"candidate-exe", dll: b"candidate-dll"}, root)
            self.assertEqual(exe.read_bytes(), b"parent-exe")
            self.assertEqual(dll.read_bytes(), b"parent-dll")
            self.assertTrue((root / ISSUANCE_REGISTRY_NAME).is_dir())
            self.assertEqual((root / ISSUANCE_REGISTRY_NAME / next((root / ISSUANCE_REGISTRY_NAME).iterdir()).name).read_bytes(), b"foreign-issuance")

    def test_c287_issuance_binding_replacement_race_is_rejected(self) -> None:
        import src.vv5_individual_running as running
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            registry, registry_identity, _ = running._registry(root)
            issuance = registry / "token.json"
            running._write_issuance(issuance, {"schema_version": 1, "token": "token"})
            before = running._inventory(root, issuance)
            self.assertIsNotNone(before)
            original_inventory = running._inventory
            calls = {"n": 0}
            def race_inventory(base, path):
                if path == issuance:
                    calls["n"] += 1
                    if calls["n"] == 2:
                        issuance.write_bytes(b"substituted")
                return original_inventory(base, path)
            with mock.patch.object(running, "_inventory", side_effect=race_inventory):
                with self.assertRaises(PatcherError):
                    running._replace_issuance(issuance, before, {"schema_version": 1, "token": "token", "bound": True})
            self.assertEqual(issuance.read_bytes(), b"substituted")

    def test_c287_relocated_complete_tree_is_rejected_before_replay(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); relocated = root / "relocated"
            report = root / ".vv5run-recovery-fabricated.json"
            report.write_text(json.dumps({"feature_owner": "vv5_individual_grant_running_candidate", "mode": VV5_MODE}), encoding="utf-8")
            shutil.copytree(root, relocated)
            with self.assertRaises(PatcherError):
                recover_atomic(relocated / report.name)

    def test_c289_foreign_registry_child_surfaces_and_preserves_authority(self) -> None:
        import src.vv5_individual_running as running
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            exe, dll = root / VV5_EXE_BASENAME, root / DLL_NAME
            exe.write_bytes(b"parent-exe"); dll.write_bytes(b"parent-dll")
            pre = {exe: _state(exe), dll: _state(dll)}
            published = {exe: b"candidate-exe", dll: b"candidate-dll"}
            real_cleanup = running._cleanup_registry
            raced = {"done": False}
            def inject(registry, expected):
                if not raced["done"]:
                    (registry / "foreign-child").write_bytes(b"foreign")
                    raced["done"] = True
                return real_cleanup(registry, expected)
            with mock.patch.object(running, "_cleanup_registry", side_effect=inject):
                with self.assertRaises(PatcherError):
                    _publish("install", [exe, dll], pre, published, root)
            self.assertEqual((root / ISSUANCE_REGISTRY_NAME / "foreign-child").read_bytes(), b"foreign")
            self.assertTrue(list(root.glob(f".{ISSUANCE_REGISTRY_NAME}-*.vv5run-tombstone-*")))

    def test_c289_issuance_pointer_race_is_no_overwrite(self) -> None:
        import src.vv5_individual_running as running
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); registry, _identity, _created = running._registry(root)
            issuance = registry / "0123456789abcdef0123456789abcdef.json"
            running._write_issuance(issuance, {"schema_version": 2, "token": "t"})
            before = running._inventory(root, issuance)
            self.assertIsNotNone(before)
            real_link = running.os.link
            def race(src, dst):
                if Path(dst).name == f".{issuance.name}.pointer":
                    Path(dst).write_bytes(b"foreign-pointer")
                return real_link(src, dst)
            with mock.patch.object(running.os, "link", side_effect=race):
                with self.assertRaises(PatcherError):
                    running._replace_issuance(issuance, before, {"schema_version": 2, "token": "t", "bound": True})
            self.assertEqual((registry / f".{issuance.name}.pointer").read_bytes(), b"foreign-pointer")
            self.assertEqual(json.loads(issuance.read_text(encoding="utf-8"))["token"], "t")

    def test_c289_issuance_delete_substitution_is_quarantined_and_survives(self) -> None:
        import src.vv5_individual_running as running
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); registry, _identity, _created = running._registry(root)
            issuance = registry / "0123456789abcdef0123456789abcdef.json"
            running._write_issuance(issuance, {"schema_version": 2, "token": "t"})
            expected = running._inventory(root, issuance)
            real_rename = running.os.rename
            def race(src, dst):
                if Path(src) == issuance:
                    issuance.write_bytes(b"foreign")
                return real_rename(src, dst)
            with mock.patch.object(running.os, "rename", side_effect=race):
                with self.assertRaises(PatcherError):
                    running._quarantine_owned(issuance, expected, owner_parent=root)
            tombstones = list(root.glob(f".{ISSUANCE_REGISTRY_NAME}-*.vv5run-tombstone-*"))
            self.assertEqual(len(tombstones), 1)
            self.assertEqual(tombstones[0].read_bytes(), b"foreign")

    def test_c289_existing_registry_without_issued_authority_rejects_before_publish(self) -> None:
        import src.vv5_individual_running as running
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ISSUANCE_REGISTRY_NAME).mkdir()
            exe, dll = root / VV5_EXE_BASENAME, root / DLL_NAME
            exe.write_bytes(b"parent-exe"); dll.write_bytes(b"parent-dll")
            pre = {exe: _state(exe), dll: _state(dll)}
            with self.assertRaises(PatcherError):
                _publish("install", [exe, dll], pre, {exe: b"candidate-exe", dll: b"candidate-dll"}, root)
            self.assertEqual(exe.read_bytes(), b"parent-exe")
            self.assertEqual(dll.read_bytes(), b"parent-dll")

    def test_c289_emergency_marker_replays_and_cleans_issuance(self) -> None:
        import src.vv5_individual_running as running
        import hashlib
        parent_exe = b"P" * 0xF4000
        parent_dll = b"D" * 64
        candidate_exe = b"C" * 0xF6000
        values = {
            "VV5_PARENT_EXE_SHA256": hashlib.sha256(parent_exe).hexdigest().upper(),
            "VV5_CANDIDATE_EXE_SHA256": hashlib.sha256(candidate_exe).hexdigest().upper(),
            "VV5_PARENT_DLL_SHA256": hashlib.sha256(parent_dll).hexdigest().upper(),
            "VV5_CANDIDATE_DLL_SHA256": hashlib.sha256(parent_dll).hexdigest().upper(),
            "DLL_SHA256": hashlib.sha256(parent_dll).hexdigest().upper(),
            "DLL_SIZE": len(parent_dll),
        }
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            exe, dll = root / VV5_EXE_BASENAME, root / DLL_NAME
            exe.write_bytes(parent_exe); dll.write_bytes(parent_dll)
            pre = {exe: _state(exe), dll: _state(dll)}
            with mock.patch.multiple(running, **values), \
                 mock.patch("vv3_individual_full_mastery._replace_verified", side_effect=OSError("replace")), \
                 mock.patch("vv3_individual_full_mastery._restore_member", return_value=False), \
                 mock.patch("vv3_individual_full_mastery._write_recovery_impl", side_effect=PatcherError("report publication")):
                with self.assertRaises(PatcherError):
                    _publish("install", [exe, dll], pre, {exe: candidate_exe, dll: parent_dll}, root)
            marker = next(root.glob(".vv5run-emergency-*.json"))
            with mock.patch.multiple(running, **values):
                recover_atomic(marker)
            self.assertEqual(exe.read_bytes(), parent_exe)
            self.assertEqual(dll.read_bytes(), parent_dll)
            self.assertFalse(marker.exists())
            self.assertFalse((root / ISSUANCE_REGISTRY_NAME).exists())
            self.assertEqual(list(root.glob(".vv5run-*")), [])


if __name__ == "__main__":
    unittest.main()
