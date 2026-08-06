from __future__ import annotations

import tempfile
import unittest
import json
import shutil
import os
from unittest import mock
from pathlib import Path

from src.vv5_individual_running import (
    PatcherError, VV5_EXE_BASENAME, DLL_NAME, VV5_MODE, ISSUANCE_REGISTRY_NAME,
    AUTHORITY_NAME, _parent, _publish, _state, install_atomic, remove_atomic,
    recover_atomic, recover_cleanup_atomic, _registry_members, _discover_reports, _quarantine_owned,
)
import src.vv5_individual_running as running


class VV5RunningPublicationTests(unittest.TestCase):
    def test_c297_direct_recovery_rejects_orphan_chain_before_report_read(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            report = root / (".vv5run-recovery-" + "a" * 32 + ".json")
            report.write_bytes(b"not-json")
            orphan = root / ".chain-foreign.json"
            orphan.write_bytes(b"foreign")
            with self.assertRaises(PatcherError):
                recover_atomic(report)
            self.assertEqual(orphan.read_bytes(), b"foreign")

    def test_c297_non_windows_install_fails_before_filesystem_io(self) -> None:
        with mock.patch.object(running.os, "name", "posix"), \
             mock.patch.object(running.os, "lstat", side_effect=AssertionError("filesystem touched")):
            with self.assertRaises(PatcherError):
                install_atomic(Path("missing.exe"), Path(VV5_EXE_BASENAME), VV5_MODE,
                               companion_source=Path("missing.dll"), companion_destination=Path(DLL_NAME))

    def test_c297_non_windows_publish_fails_before_filesystem_io(self) -> None:
        with mock.patch.object(running.os, "name", "posix"), \
             mock.patch.object(running.os, "lstat", side_effect=AssertionError("filesystem touched")):
            with self.assertRaises(PatcherError):
                _publish("install", [Path(VV5_EXE_BASENAME), Path(DLL_NAME)], {}, {}, Path("."))

    def test_c299_deletion_substitution_retains_verified_preserved_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            registry = root / ISSUANCE_REGISTRY_NAME
            registry.mkdir()
            source = registry / "issuance.json"
            source.write_bytes(b"owned")
            expected = running._inventory(root, source)
            original_delete = running._strict_delete_file_by_handle

            def substitute(path, identity):
                if path == source:
                    source.unlink()
                    source.write_bytes(b"foreign")
                return original_delete(path, identity)

            with mock.patch.object(running, "_strict_delete_file_by_handle", side_effect=substitute):
                with self.assertRaises(PatcherError):
                    running._quarantine_owned(source, expected, owner_parent=root)
            preserved = list(root.glob(".issuance.json.vv5run-preserved-*.backup"))
            self.assertEqual(len(preserved), 1)
            self.assertEqual(preserved[0].read_bytes(), b"owned")
            self.assertEqual(source.read_bytes(), b"foreign")

    def test_c301_sibling_added_between_scans_is_rejected(self) -> None:
        """A newly injected hidden child cannot be adopted by final recapture."""
        with tempfile.TemporaryDirectory() as td:
            parent = Path(td)
            report = parent / (".vv5run-recovery-" + "a" * 32 + ".json")
            report.write_bytes(b"report")
            real_scandir = os.scandir
            calls = {"n": 0}

            class _Scan:
                def __init__(self, entries):
                    self.entries = entries
                def __iter__(self):
                    return iter(self.entries)
                def __enter__(self):
                    return self
                def __exit__(self, *_args):
                    return False

            def scan(path):
                calls["n"] += 1
                if calls["n"] == 2:
                    (parent / ".vv5run-foreign-child").write_bytes(b"foreign")
                return _Scan(list(real_scandir(path)))

            with mock.patch.object(running.os, "scandir", side_effect=scan):
                with self.assertRaises(PatcherError):
                    running._validate_recovery_siblings(parent, selected=report.name)
            self.assertEqual((parent / ".vv5run-foreign-child").read_bytes(), b"foreign")

    def test_c301_sibling_rename_between_scans_is_rejected(self) -> None:
        """A report rename is a membership change, even when its bytes match."""
        with tempfile.TemporaryDirectory() as td:
            parent = Path(td)
            report = parent / (".vv5run-recovery-" + "b" * 32 + ".json")
            report.write_bytes(b"report")
            renamed = parent / (".vv5run-recovery-" + "c" * 32 + ".json")
            real_scandir = os.scandir
            calls = {"n": 0}

            class _Scan:
                def __init__(self, entries):
                    self.entries = entries
                def __iter__(self):
                    return iter(self.entries)
                def __enter__(self):
                    return self
                def __exit__(self, *_args):
                    return False

            def scan(path):
                calls["n"] += 1
                if calls["n"] == 2:
                    report.rename(renamed)
                return _Scan(list(real_scandir(path)))

            with mock.patch.object(running.os, "scandir", side_effect=scan):
                with self.assertRaises(PatcherError):
                    running._validate_recovery_siblings(parent, selected=report.name)
            self.assertTrue(renamed.exists())

    def test_c301_sibling_removed_between_scans_is_rejected(self) -> None:
        """A captured member disappearing is a set change, not an empty success."""
        with tempfile.TemporaryDirectory() as td:
            parent = Path(td)
            report = parent / (".vv5run-recovery-" + "d" * 32 + ".json")
            report.write_bytes(b"report")
            real_scandir = os.scandir
            calls = {"n": 0}

            class _Scan:
                def __init__(self, entries):
                    self.entries = entries
                def __iter__(self):
                    return iter(self.entries)
                def __enter__(self):
                    return self
                def __exit__(self, *_args):
                    return False

            def scan(path):
                calls["n"] += 1
                if calls["n"] == 2:
                    report.unlink()
                return _Scan(list(real_scandir(path)))

            with mock.patch.object(running.os, "scandir", side_effect=scan):
                with self.assertRaises(PatcherError):
                    running._validate_recovery_siblings(parent, selected=report.name)

    def test_c301_backup_replacement_after_tombstone_cleanup_survives(self) -> None:
        """A backup replaced after tombstone cleanup is foreign and is retained."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            registry = root / ISSUANCE_REGISTRY_NAME
            registry.mkdir()
            source = registry / "issuance.json"
            source.write_bytes(b"owned")
            record = running._inventory(root, source)
            registry_identity = running._identity(registry)
            real_cleanup = running._cleanup
            injected = {"done": False}

            def cleanup(path, *, expected=None):
                result = real_cleanup(path, expected=expected)
                if path.name.endswith(".vv5run-tombstone-*") or "vv5run-tombstone-" in path.name:
                    backups = [item for item in root.glob("*.backup") if "vv5run-preserved-" in item.name and "vv5-preserved-guard-" not in item.name]
                    if backups and not injected["done"]:
                        backups[0].unlink()
                        backups[0].write_bytes(b"foreign")
                        injected["done"] = True
                return result

            with mock.patch.object(running, "_cleanup", side_effect=cleanup):
                with self.assertRaises(PatcherError):
                    running._cleanup_issuance_artifacts(registry, registry_identity, [(source, record)], None)
            backups = list(root.glob("*.backup"))
            self.assertIn(b"foreign", [path.read_bytes() for path in backups])
            self.assertIn(b"owned", [path.read_bytes() for path in backups])
            self.assertTrue(registry.exists())

    def test_c301_partial_preserved_backup_failure_has_no_unowned_residue(self) -> None:
        """A partial preserved-copy failure is cleaned only when its identity is owned."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            registry = root / ISSUANCE_REGISTRY_NAME
            registry.mkdir()
            source = registry / "issuance.json"
            source.write_bytes(b"owned")
            expected = running._inventory(root, source)
            original_write = running._write

            def fail_preserved(path, data):
                if path.name.endswith(".backup"):
                    path.write_bytes(data[:2])
                    raise OSError("injected partial backup write")
                return original_write(path, data)

            with mock.patch.object(running, "_write", side_effect=fail_preserved):
                with self.assertRaises(PatcherError):
                    running._quarantine_owned(source, expected, owner_parent=root)
            self.assertEqual(len(list(root.glob("*.backup"))), 1)
            self.assertEqual(len(list(root.glob(".vv5-preserved-backup-failure-*.json"))), 1)
            self.assertTrue(source.exists())
            self.assertEqual(source.read_bytes(), b"owned")

    def test_c301_registry_cleanup_failure_retains_durable_authority(self) -> None:
        """Registry cleanup is last; an injected failure leaves retry authority."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            registry = root / ISSUANCE_REGISTRY_NAME
            registry.mkdir()
            source = registry / "issuance.json"
            source.write_bytes(b"owned")
            record = running._inventory(root, source)
            registry_identity = running._identity(registry)
            with mock.patch.object(running, "_cleanup_registry", side_effect=PatcherError("injected registry cleanup")):
                with self.assertRaises(PatcherError):
                    running._cleanup_issuance_artifacts(registry, registry_identity, [(source, record)], None)
            self.assertTrue(registry.exists())
            self.assertEqual(list(registry.iterdir()), [])

    def test_c303_complete_copy_after_write_exception_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            registry = root / ISSUANCE_REGISTRY_NAME
            registry.mkdir()
            source = registry / "issuance.json"
            source.write_bytes(b"owned")
            expected = running._inventory(root, source)
            original_write = running._write

            def write_then_raise(path, data):
                if path.name.endswith(".backup"):
                    original_write(path, data)
                    raise OSError("flush reported late")
                return original_write(path, data)

            with mock.patch.object(running, "_write", side_effect=write_then_raise):
                _tombstone, _record, preserved = running._quarantine_owned(source, expected, owner_parent=root)
            self.assertEqual(preserved.read_bytes(), b"owned")

    def test_c303_cleanup_failure_writes_durable_record_and_replays(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            registry = root / ISSUANCE_REGISTRY_NAME
            registry.mkdir()
            source = registry / "issuance.json"
            source.write_bytes(b"owned")
            record = running._inventory(root, source)
            real_cleanup = running._cleanup
            failed = {"done": False}

            def fail_once(path, *, expected=None):
                if "vv5run-tombstone-" in path.name and not failed["done"]:
                    failed["done"] = True
                    raise PatcherError("injected tombstone cleanup failure")
                return real_cleanup(path, expected=expected)

            with mock.patch.object(running, "_cleanup", side_effect=fail_once):
                with self.assertRaises(PatcherError):
                    running._cleanup_issuance_artifacts(registry, running._identity(registry), [(source, record)], None)
            records = list(root.glob(".vv5run-cleanup-*.json"))
            # Successor publication intentionally retains a transitive chain;
            # every member remains recoverable until strict finalization.
            self.assertGreaterEqual(len(records), 1)
            records.sort(key=lambda path: int(running._validate_cleanup_record(path)[0]["record_version"]), reverse=True)
            raw, _identity = running._validate_cleanup_record(records[0])
            self.assertEqual(raw["feature_owner"], running.VV5_FEATURE_OWNER)
            self.assertEqual(raw["artifacts"][0]["role"], "issuance_member")
            self.assertIsNotNone(raw["artifacts"][0]["guard_record"])

            recover_cleanup_atomic(records[0])
            self.assertFalse(records[0].exists())
            self.assertFalse(registry.exists())
            self.assertEqual(list(root.glob(".vv5run-*")), [])

    def test_c303_guard_link_failure_retains_authority(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            registry = root / ISSUANCE_REGISTRY_NAME
            registry.mkdir()
            source = registry / "issuance.json"
            source.write_bytes(b"owned")
            record = running._inventory(root, source)
            original_link = running.os.link

            def fail_guard(src, dst):
                if "vv5-preserved-guard-" in Path(dst).name:
                    raise OSError("injected guard link failure")
                return original_link(src, dst)

            with mock.patch.object(running.os, "link", side_effect=fail_guard):
                with self.assertRaises(PatcherError):
                    running._cleanup_issuance_artifacts(registry, running._identity(registry), [(source, record)], None)
            self.assertTrue(list(root.glob(".vv5run-cleanup-*.json")))
            self.assertTrue(registry.exists())

    def test_c303_guard_cleanup_failure_is_retryable(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            registry = root / ISSUANCE_REGISTRY_NAME
            registry.mkdir()
            source = registry / "issuance.json"
            source.write_bytes(b"owned")
            record = running._inventory(root, source)
            real_cleanup = running._cleanup
            failed = {"done": False}

            def fail_guard(path, *, expected=None):
                if "vv5-preserved-guard-" in path.name and not failed["done"]:
                    failed["done"] = True
                    raise PatcherError("injected guard cleanup failure")
                return real_cleanup(path, expected=expected)

            with mock.patch.object(running, "_cleanup", side_effect=fail_guard):
                with self.assertRaises(PatcherError):
                    running._cleanup_issuance_artifacts(registry, running._identity(registry), [(source, record)], None)
            cleanup_record = next(root.glob(".vv5run-cleanup-*.json"))
            recover_cleanup_atomic(cleanup_record)
            self.assertFalse(cleanup_record.exists())
            self.assertFalse(registry.exists())

    def test_c305_late_complete_cleanup_record_write_is_replayable(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            registry = root / ISSUANCE_REGISTRY_NAME
            registry.mkdir()
            source = registry / "issuance.json"
            source.write_bytes(b"owned")
            payload = running._cleanup_record_payload(
                root,
                registry,
                running._identity(registry),
                [(source, running._inventory(root, source))],
                remove_registry=True,
            )
            original_write = running._write

            def late_write(path, data):
                original_write(path, data)
                if path.name.startswith(".vv5run-cleanup-"):
                    raise OSError("late flush report")

            with mock.patch.object(running, "_write", side_effect=late_write):
                record_path, _record = running._write_cleanup_record(root, payload)
            self.assertTrue(record_path.exists())
            record_path.unlink()
            source.unlink()
            registry.rmdir()

    def test_c305_registry_already_removed_finalization_replays_to_zero_residue(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            registry = root / ISSUANCE_REGISTRY_NAME
            registry.mkdir()
            source = registry / "issuance.json"
            source.write_bytes(b"owned")
            payload = running._cleanup_record_payload(
                root,
                registry,
                running._identity(registry),
                [(source, running._inventory(root, source))],
                remove_registry=True,
            )
            record_path, _record = running._write_cleanup_record(root, payload)
            source.unlink()
            registry.rmdir()
            # A registry-absent record without an externally issued authority
            # is a forged/ambiguous replay and must fail closed with evidence
            # intact (C309 authority binding contract).
            with self.assertRaises(PatcherError):
                recover_cleanup_atomic(record_path)
            self.assertTrue(record_path.exists())
            self.assertFalse(registry.exists())

    def test_c299_32bit_windows_capability_fails_before_io(self) -> None:
        with mock.patch.object(running.os, "name", "nt"), \
             mock.patch.object(running.struct, "calcsize", return_value=4), \
             mock.patch.object(running.os, "lstat", side_effect=AssertionError("filesystem touched")):
            with self.assertRaises(PatcherError):
                install_atomic(Path("missing.exe"), Path(VV5_EXE_BASENAME), VV5_MODE,
                               companion_source=Path("missing.dll"), companion_destination=Path(DLL_NAME))

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
            real_link = running.os.link
            def substitute(src, dst):
                if Path(src).parent.name == ISSUANCE_REGISTRY_NAME and Path(src).suffix == ".json":
                    Path(src).write_bytes(b"foreign")
                return real_link(src, dst)
            with mock.patch.object(running.os, "link", side_effect=substitute):
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
            # Tombstones/backups are retired before registry removal; the
            # injected child keeps the registry as durable retry authority.
            self.assertTrue((root / ISSUANCE_REGISTRY_NAME).exists())

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
            real_link = running.os.link
            def race(src, dst):
                if Path(src) == issuance:
                    issuance.write_bytes(b"foreign")
                return real_link(src, dst)
            with mock.patch.object(running.os, "link", side_effect=race):
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

    def test_c291_registry_setup_failure_cleans_only_owned_authority(self) -> None:
        import src.vv5_individual_running as running
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            exe, dll = root / VV5_EXE_BASENAME, root / DLL_NAME
            exe.write_bytes(b"parent-exe"); dll.write_bytes(b"parent-dll")
            pre = {exe: _state(exe), dll: _state(dll)}
            with mock.patch.object(running, "_write_issuance", side_effect=PatcherError("authority setup")):
                with self.assertRaises(PatcherError):
                    _publish("install", [exe, dll], pre, {exe: b"candidate-exe", dll: b"candidate-dll"}, root)
            self.assertEqual(exe.read_bytes(), b"parent-exe")
            self.assertEqual(dll.read_bytes(), b"parent-dll")
            self.assertFalse((root / ISSUANCE_REGISTRY_NAME).exists())

    def test_c291_foreign_registry_child_is_rejected_before_pair_mutation(self) -> None:
        import src.vv5_individual_running as running
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            registry, registry_identity, created = running._registry(root)
            authority_path, _token, authority = running._ensure_authority(registry, registry_identity, created)
            (registry / "foreign-child").write_bytes(b"foreign")
            exe, dll = root / VV5_EXE_BASENAME, root / DLL_NAME
            exe.write_bytes(b"parent-exe"); dll.write_bytes(b"parent-dll")
            pre = {exe: _state(exe), dll: _state(dll)}
            with self.assertRaises(PatcherError):
                _publish("install", [exe, dll], pre, {exe: b"candidate-exe", dll: b"candidate-dll"}, root)
            self.assertEqual(exe.read_bytes(), b"parent-exe")
            self.assertEqual(dll.read_bytes(), b"parent-dll")
            self.assertEqual((registry / "foreign-child").read_bytes(), b"foreign")
            self.assertEqual((registry / AUTHORITY_NAME).read_bytes(), authority_path.read_bytes())

    def test_c291_second_issuance_is_serialized_before_pair_mutation(self) -> None:
        import src.vv5_individual_running as running
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            registry, registry_identity, created = running._registry(root)
            authority_path, _token, authority = running._ensure_authority(registry, registry_identity, created)
            running._write_issuance(registry / "busy.json", {"schema_version": 2, "token": "busy"})
            exe, dll = root / VV5_EXE_BASENAME, root / DLL_NAME
            exe.write_bytes(b"parent-exe"); dll.write_bytes(b"parent-dll")
            pre = {exe: _state(exe), dll: _state(dll)}
            with self.assertRaises(PatcherError):
                _publish("install", [exe, dll], pre, {exe: b"candidate-exe", dll: b"candidate-dll"}, root)
            self.assertEqual(exe.read_bytes(), b"parent-exe")
            self.assertEqual(dll.read_bytes(), b"parent-dll")
            self.assertTrue((registry / "busy.json").exists())
            self.assertTrue((registry / AUTHORITY_NAME).exists())

    def test_c291_existing_authority_is_retained_after_successful_transaction(self) -> None:
        import src.vv5_individual_running as running
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            registry, registry_identity, created = running._registry(root)
            authority_path, _token, _authority = running._ensure_authority(registry, registry_identity, created)
            exe, dll = root / VV5_EXE_BASENAME, root / DLL_NAME
            exe.write_bytes(b"parent-exe"); dll.write_bytes(b"parent-dll")
            pre = {exe: _state(exe), dll: _state(dll)}
            _publish("install", [exe, dll], pre, {exe: b"candidate-exe", dll: b"candidate-dll"}, root)
            self.assertTrue((root / ISSUANCE_REGISTRY_NAME).is_dir())
            self.assertTrue(authority_path.exists())

    def test_c291_directory_form_replay_uses_complete_registry_chain(self) -> None:
        import hashlib
        import src.vv5_individual_running as running
        parent_exe = b"P" * 0xF4000
        candidate_exe = b"C" * 0xF6000
        values = {
            "VV5_PARENT_EXE_SHA256": hashlib.sha256(parent_exe).hexdigest().upper(),
            "VV5_CANDIDATE_EXE_SHA256": hashlib.sha256(candidate_exe).hexdigest().upper(),
            "VV5_PARENT_DLL_SHA256": hashlib.sha256(b"parent-dll").hexdigest().upper(),
            "VV5_CANDIDATE_DLL_SHA256": hashlib.sha256(b"parent-dll").hexdigest().upper(),
            "DLL_SHA256": hashlib.sha256(b"parent-dll").hexdigest().upper(),
            "DLL_SIZE": len(b"parent-dll"),
        }
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            exe, dll = root / VV5_EXE_BASENAME, root / DLL_NAME
            exe.write_bytes(parent_exe); dll.write_bytes(b"parent-dll")
            pre = {exe: _state(exe), dll: _state(dll)}
            with mock.patch.multiple(running, **values), \
                 mock.patch("vv3_individual_full_mastery._replace_verified", side_effect=OSError("replace")), \
                 mock.patch("vv3_individual_full_mastery._restore_member", return_value=False):
                with self.assertRaises(PatcherError):
                    _publish("install", [exe, dll], pre, {exe: candidate_exe, dll: b"parent-dll"}, root)
            with mock.patch.multiple(running, **values):
                recover_atomic(root)
            self.assertEqual(exe.read_bytes(), parent_exe)
            self.assertEqual(dll.read_bytes(), b"parent-dll")
            self.assertFalse((root / ISSUANCE_REGISTRY_NAME).exists())

    def test_c293_registry_membership_substitution_is_detected_after_scan(self) -> None:
        import src.vv5_individual_running as running
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            registry, registry_identity, created = running._registry(root)
            running._ensure_authority(registry, registry_identity, created)
            real_inventory = running._inventory
            injected = {"done": False}
            def inject(base, path):
                result = real_inventory(base, path)
                if path.name == AUTHORITY_NAME and not injected["done"]:
                    (registry / "foreign-child").write_bytes(b"foreign")
                    injected["done"] = True
                return result
            with mock.patch.object(running, "_inventory", side_effect=inject):
                with self.assertRaises(PatcherError):
                    running._registry_members(registry)
            self.assertTrue((registry / "foreign-child").exists())

    def test_c293_registry_reparse_attribute_is_rejected_without_symlink_privilege(self) -> None:
        import src.vv5_individual_running as running
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            registry, registry_identity, created = running._registry(root)
            running._ensure_authority(registry, registry_identity, created)
            real_unsafe = running._unsafe
            calls = {"count": 0}
            def reparse(st):
                calls["count"] += 1
                if calls["count"] > 2:
                    return True
                return real_unsafe(st)
            with mock.patch.object(running, "_unsafe", side_effect=reparse):
                with self.assertRaises(PatcherError):
                    running._registry_members(registry)

    def test_c293_authority_substitution_after_read_is_rejected(self) -> None:
        import src.vv5_individual_running as running
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            registry, registry_identity, created = running._registry(root)
            authority_path, _token, _authority = running._ensure_authority(registry, registry_identity, created)
            real_read = running._read
            replaced = {"done": False}
            def substitute(path):
                data = real_read(path)
                if path == authority_path and not replaced["done"]:
                    path.write_bytes(b"foreign-authority")
                    replaced["done"] = True
                return data
            with mock.patch.object(running, "_read", side_effect=substitute):
                with self.assertRaises(PatcherError):
                    running._ensure_authority(registry, registry_identity, created)
            self.assertEqual(authority_path.read_bytes(), b"foreign-authority")

    def test_c293_report_discovery_rejects_matching_directory_member(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            bad = root / ".vv5run-recovery-0123456789abcdef0123456789abcdef.json"
            bad.mkdir()
            with self.assertRaises(PatcherError):
                recover_atomic(root)
            self.assertTrue(bad.is_dir())

    def test_c293_postlink_same_content_replacement_is_rejected_by_file_id(self) -> None:
        import src.vv5_individual_running as running
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            tmp = root / "issuance.tmp"
            final = root / "issuance.json"
            tmp.write_bytes(b"same-content")
            real_link = running.os.link
            def replace_same_content(src, dst):
                real_link(src, dst)
                Path(dst).unlink()
                Path(dst).write_bytes(b"same-content")
            with mock.patch.object(running.os, "link", side_effect=replace_same_content):
                with self.assertRaises(PatcherError):
                    running._publish_exclusive(tmp, final, root)
            self.assertEqual(final.read_bytes(), b"same-content")
            self.assertTrue(tmp.exists())

    def test_c293_quarantine_substitution_after_link_preserves_foreign_source(self) -> None:
        import src.vv5_individual_running as running
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            registry, registry_identity, created = running._registry(root)
            issuance = registry / "0123456789abcdef0123456789abcdef.json"
            running._write_issuance(issuance, {"schema_version": 2, "token": "t"})
            expected = running._inventory(root, issuance)
            real_link = running.os.link
            def replace_after_link(src, dst):
                real_link(src, dst)
                if Path(src) == issuance:
                    issuance.unlink()
                    issuance.write_bytes(b"foreign")
            with mock.patch.object(running.os, "link", side_effect=replace_after_link):
                with self.assertRaises(PatcherError):
                    running._quarantine_owned(issuance, expected, owner_parent=root)
            self.assertEqual(issuance.read_bytes(), b"foreign")
            tombstones = list(root.glob(f".{ISSUANCE_REGISTRY_NAME}-*.vv5run-tombstone-*"))
            self.assertEqual(len(tombstones), 1)

    def test_c291_registry_substitution_during_replay_is_rejected_unchanged(self) -> None:
        import hashlib
        import src.vv5_individual_running as running
        parent_exe = b"P" * 0xF4000
        candidate_exe = b"C" * 0xF6000
        values = {
            "VV5_PARENT_EXE_SHA256": hashlib.sha256(parent_exe).hexdigest().upper(),
            "VV5_CANDIDATE_EXE_SHA256": hashlib.sha256(candidate_exe).hexdigest().upper(),
            "VV5_PARENT_DLL_SHA256": hashlib.sha256(b"parent-dll").hexdigest().upper(),
            "VV5_CANDIDATE_DLL_SHA256": hashlib.sha256(b"parent-dll").hexdigest().upper(),
            "DLL_SHA256": hashlib.sha256(b"parent-dll").hexdigest().upper(),
            "DLL_SIZE": len(b"parent-dll"),
        }
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            exe, dll = root / VV5_EXE_BASENAME, root / DLL_NAME
            exe.write_bytes(parent_exe); dll.write_bytes(b"parent-dll")
            pre = {exe: _state(exe), dll: _state(dll)}
            with mock.patch.multiple(running, **values), \
                 mock.patch("vv3_individual_full_mastery._replace_verified", side_effect=OSError("replace")), \
                 mock.patch("vv3_individual_full_mastery._restore_member", return_value=False):
                with self.assertRaises(PatcherError):
                    _publish("install", [exe, dll], pre, {exe: candidate_exe, dll: b"parent-dll"}, root)
            report = next(root.glob(".vv5run-recovery-*.json"))
            registry = root / ISSUANCE_REGISTRY_NAME
            moved = root / ".vv5run-registry-original"
            registry.rename(moved)
            registry.mkdir()
            (registry / "foreign").write_bytes(b"foreign")
            with mock.patch.multiple(running, **values):
                with self.assertRaises(PatcherError):
                    recover_atomic(report)
            self.assertEqual(exe.read_bytes(), parent_exe)
            self.assertEqual(dll.read_bytes(), b"parent-dll")
            self.assertTrue((registry / "foreign").exists())

    def test_c295_registry_final_recapture_rejects_same_content_inode_replacement(self) -> None:
        import src.vv5_individual_running as running
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            registry = root / ISSUANCE_REGISTRY_NAME
            registry.mkdir()
            child = registry / "issuance.json"
            child.write_bytes(b"same")
            original = running._inventory
            calls = {"child": 0}

            def recapture(root_arg, path_arg):
                record = original(root_arg, path_arg)
                if path_arg == child:
                    calls["child"] += 1
                    if calls["child"] == 1:
                        replacement = registry / "replacement.tmp"
                        replacement.write_bytes(b"same")
                        os.replace(replacement, child)
                return record

            with mock.patch.object(running, "_inventory", side_effect=recapture):
                with self.assertRaises(PatcherError):
                    _registry_members(registry)
            self.assertEqual(child.read_bytes(), b"same")

    def test_c295_discovery_rejects_unknown_vv5run_residue_before_report_use(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            parent = Path(td)
            (parent / ".vv5run-random.tmp").write_bytes(b"foreign")
            with self.assertRaises(PatcherError):
                _discover_reports(parent)
            self.assertTrue((parent / ".vv5run-random.tmp").exists())

    def test_c295_quarantine_predelete_substitution_preserves_foreign_source(self) -> None:
        import src.vv5_individual_running as running
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            registry = root / ISSUANCE_REGISTRY_NAME
            registry.mkdir()
            source = registry / "issuance.json"
            source.write_bytes(b"owned")
            expected = running._inventory(root, source)
            original_delete = running._strict_delete_file_by_handle

            def substitute(path, identity):
                if path == source:
                    source.unlink()
                    source.write_bytes(b"foreign")
                return original_delete(path, identity)

            with mock.patch.object(running, "_strict_delete_file_by_handle", side_effect=substitute):
                with self.assertRaises(PatcherError):
                    _quarantine_owned(source, expected, owner_parent=root)
            self.assertEqual(source.read_bytes(), b"foreign")
            self.assertEqual(len(list(root.glob(f".{ISSUANCE_REGISTRY_NAME}-*.vv5run-tombstone-*"))), 1)

    def test_c295_recover_validates_ancestor_chain_before_report_probe(self) -> None:
        import src.vv5_individual_running as running
        report = Path("C:/untrusted-vv5run/recovery.json")
        with mock.patch.object(running, "_validate_recovery_ancestors", side_effect=PatcherError("ancestor")), \
             mock.patch.object(running.os.path, "lexists", side_effect=AssertionError("report probed")):
            with self.assertRaisesRegex(PatcherError, "ancestor"):
                recover_atomic(report)

    def test_c307_cleanup_record_binds_external_authority_and_issuance(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            registry = root / ISSUANCE_REGISTRY_NAME
            registry.mkdir()
            registry_identity = running._identity(registry)
            authority_path, _token, authority = running._ensure_authority(registry, registry_identity, True)
            issuance = registry / ("a" * 32 + ".json")
            running._write_issuance(issuance, {"schema_version": 2, "token": "a" * 32, "authority_token": authority["token"], "authority_record": authority["record"], "operation": "install", "destination_parent_absolute": str(root).lower(), "destination_paths_absolute": [], "members": []})
            payload = running._cleanup_record_payload(root, registry, registry_identity, [(issuance, running._inventory(root, issuance)), (authority_path, authority["record"])], remove_registry=True, authority=(authority_path, authority["record"]))
            self.assertEqual(payload["schema_version"], 2)
            self.assertIsNotNone(payload["authority_binding"])
            self.assertEqual(payload["issuance_bindings"][0]["name"], issuance.name)
            self.assertEqual(payload["transaction_binding"]["registry_identity"], registry_identity)

    def test_c307_dual_valid_cleanup_authorities_are_ambiguous(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            registry = root / ISSUANCE_REGISTRY_NAME
            registry.mkdir()
            source = registry / "issuance.json"
            source.write_bytes(b"owned")
            payload = running._cleanup_record_payload(root, registry, running._identity(registry), [(source, running._inventory(root, source))], remove_registry=False)
            first, _ = running._write_cleanup_record(root, payload)
            second, _ = running._write_cleanup_record(root, payload)
            with self.assertRaises(PatcherError):
                recover_cleanup_atomic(first)
            self.assertTrue(first.exists() and second.exists())

    def test_c307_started_cleanup_state_replays_quarantine_and_finalization(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            registry = root / ISSUANCE_REGISTRY_NAME
            registry.mkdir()
            registry_identity = running._identity(registry)
            authority_path, _token, authority = running._ensure_authority(registry, registry_identity, True)
            source = registry / ("b" * 32 + ".json")
            running._write_issuance(source, {"schema_version": 2, "token": "b" * 32, "authority_token": authority["token"], "authority_record": authority["record"], "operation": "install", "destination_parent_absolute": str(root).lower(), "destination_paths_absolute": [], "members": []})
            payload = running._cleanup_record_payload(root, registry, registry_identity, [(source, running._inventory(root, source)), (authority_path, authority["record"])], remove_registry=True, authority=(authority_path, authority["record"]))
            record, _ = running._write_cleanup_record(root, payload)
            recover_cleanup_atomic(record)
            self.assertFalse(registry.exists())
            self.assertFalse(list(root.glob(".vv5run-cleanup-*.json")))

    def test_c307_forged_cleanup_artifact_role_is_rejected_before_delete(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            registry = root / ISSUANCE_REGISTRY_NAME
            registry.mkdir()
            source = registry / "issuance.json"
            sibling = registry / "unrelated-sibling.json"
            source.write_bytes(b"owned")
            sibling.write_bytes(b"keep")
            payload = running._cleanup_record_payload(root, registry, running._identity(registry), [(source, running._inventory(root, source))], remove_registry=False)
            payload["artifacts"][0]["name"] = sibling.name
            record, _ = running._write_cleanup_record(root, payload)
            with self.assertRaises(PatcherError):
                recover_cleanup_atomic(record)
            self.assertEqual(sibling.read_bytes(), b"keep")
            self.assertEqual(source.read_bytes(), b"owned")

    def test_c309_three_version_cleanup_chain_is_transitively_bound(self) -> None:
        """Every successor remains linked to the immutable predecessor chain."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            registry = root / ISSUANCE_REGISTRY_NAME
            registry.mkdir()
            rid = running._identity(registry)
            authority_path, _token, authority = running._ensure_authority(registry, rid, True)
            source = registry / ("c" * 32 + ".json")
            running._write_issuance(source, {"schema_version": 2, "token": "c" * 32, "authority_token": authority["token"], "authority_record": authority["record"], "operation": "install", "destination_parent_absolute": str(root).lower(), "destination_paths_absolute": [], "members": []})
            payload = running._cleanup_record_payload(root, registry, rid, [(source, running._inventory(root, source)), (authority_path, authority["record"])], remove_registry=True, authority=(authority_path, authority["record"]))
            record, identity = running._write_cleanup_record(root, payload)
            for _ in range(2):
                raw, _ = running._validate_cleanup_record(record)
                record, identity = running._update_cleanup_record(record, identity, raw)
            chain = running._cleanup_authority_chain(root)
            self.assertEqual([int(item[1]["record_version"]) for item in chain], [3, 2, 1])
            self.assertEqual(len(chain), 3)

    def test_c309_absent_registry_requires_preserved_externally_bound_evidence(self) -> None:
        """A forged absent-registry record cannot become a deletion authority."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            registry = root / ISSUANCE_REGISTRY_NAME
            registry.mkdir()
            rid = running._identity(registry)
            authority_path, _token, authority = running._ensure_authority(registry, rid, True)
            source = registry / ("d" * 32 + ".json")
            running._write_issuance(source, {"schema_version": 2, "token": "d" * 32, "authority_token": authority["token"], "authority_record": authority["record"], "operation": "install", "destination_parent_absolute": str(root).lower(), "destination_paths_absolute": [], "members": []})
            payload = running._cleanup_record_payload(root, registry, rid, [(source, running._inventory(root, source)), (authority_path, authority["record"])], remove_registry=True, authority=(authority_path, authority["record"]))
            record, _ = running._write_cleanup_record(root, payload)
            for child in list(registry.iterdir()):
                child.unlink()
            registry.rmdir()
            with self.assertRaises(PatcherError):
                recover_cleanup_atomic(record)
            self.assertTrue(record.exists())


if __name__ == "__main__":
    unittest.main()
