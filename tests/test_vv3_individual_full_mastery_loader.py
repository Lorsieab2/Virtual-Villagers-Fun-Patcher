from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from unittest import mock
from types import SimpleNamespace
from pathlib import Path

import vv3_individual_full_mastery as loader
import vv_fun_patcher


ROOT = Path(__file__).resolve().parents[1]
PARENTS = ROOT / "outputs" / "vv3-vv4-c257-determinism-a"


class VV3IndividualFullMasteryLoaderTests(unittest.TestCase):
    def _parent(self, mode: str) -> bytes:
        name = f"vv3_fullscreen_safe_candidate_{mode}.exe"
        return (PARENTS / name).read_bytes()

    def test_hidden_registration_is_not_public_catalog(self):
        hidden = vv_fun_patcher.load_hidden_vv3_individual_full_mastery_candidate()
        self.assertFalse(hidden.raw["enabled"])
        self.assertTrue(hidden.raw["catalog_hidden"])
        self.assertNotIn(hidden.id, {p.id for p in vv_fun_patcher.load_fun_patches()})

    def test_render_and_remove_exact_both_parents(self):
        expected = {
            "collection_progression": "BFFA0B5F54CD084138EABD68D3EA67F834CEFE915F7DB0000F81639F34BF90F1",
            "immediate_fixed": "6550141AFFAEF3F7965E89F1B32A3F4CB929E8E217778C5BBCB512AAC499E59C",
        }
        for mode, digest in expected.items():
            parent = self._parent(mode)
            candidate = loader.render_parent(parent, mode)
            self.assertEqual(len(candidate), 0xCF000)
            self.assertEqual(hashlib.sha256(candidate).hexdigest().upper(), digest)
            self.assertEqual(loader.remove_candidate(candidate, mode), parent)

    def test_pe_section_and_dispatcher_guards(self):
        candidate = loader.render_parent(self._parent("collection_progression"), "collection_progression")
        self.assertEqual(candidate[0x10E:0x110], bytes.fromhex("0900"))
        self.assertEqual(candidate[0x158:0x15C], bytes.fromhex("00302E00"))
        self.assertEqual(candidate[0x340:0x348], b".vv3im\0\0")
        self.assertEqual(candidate[0xA38C3:0xA38C8], loader.HOOK_AFTER)
        self.assertEqual(candidate[0xCE000:0xCE000 + 4], bytes.fromhex("83FB010F"))

    def test_patcher_append_resolver_uses_generated_page(self):
        feature = vv_fun_patcher.load_hidden_vv3_individual_full_mastery_candidate()
        layout = feature.raw["pe_append_transaction"]["layouts"]["collection_progression"]
        page = vv_fun_patcher._resolve_append_bytes(feature, layout)
        self.assertEqual(len(page), 0x1000)
        self.assertEqual(hashlib.sha256(page).hexdigest().upper(), loader._sha(page))
        work = bytearray(self._parent("collection_progression"))
        vv_fun_patcher._apply_pe_append_transactions(work, [feature], "collection_progression")
        self.assertEqual(len(work), 0xCF000)
        self.assertEqual(bytes(work[0xCE000:]), page)

    def test_unknown_or_corrupt_parent_fails_before_output(self):
        parent = bytearray(self._parent("collection_progression"))
        parent[0x200] ^= 1
        with self.assertRaises(vv_fun_patcher.PatcherError):
            loader.render_parent(bytes(parent), "collection_progression")
        with self.assertRaises(vv_fun_patcher.PatcherError):
            loader.render_parent(self._parent("collection_progression"), "experimental_expanded_256")

    def test_atomic_new_destination_and_collision(self):
        parent = PARENTS / "vv3_fullscreen_safe_candidate_collection_progression.exe"
        with tempfile.TemporaryDirectory() as td:
            destination = Path(td) / "candidate.exe"
            companion_source = ROOT / "data" / "candidates" / "VVFP VV3 Full Heal Candidate.dll"
            companion_restore = ROOT / "data" / "candidates" / "VVFP VV3 Full Mastery Candidate.dll"
            companion_destination = Path(td) / "VVFP VV3 Full Mastery Candidate.dll"
            loader.install_atomic(parent, destination, "collection_progression", companion_source=companion_source, companion_destination=companion_destination)
            self.assertTrue(destination.is_file())
            self.assertTrue(companion_destination.is_file())
            before = destination.read_bytes()
            with self.assertRaises(vv_fun_patcher.PatcherError):
                loader.install_atomic(parent, destination, "collection_progression", companion_source=companion_source, companion_destination=companion_destination)
            self.assertEqual(destination.read_bytes(), before)
            companion_before = companion_restore.read_bytes()
            loader.remove_atomic(destination, "collection_progression", companion_destination=companion_destination, companion_restore_source=companion_restore)
            self.assertEqual(destination.read_bytes(), parent.read_bytes())
            self.assertEqual(companion_destination.read_bytes(), companion_before)

    def test_companion_is_mandatory_and_wrong_existing_preimage_is_rejected(self):
        parent = PARENTS / "vv3_fullscreen_safe_candidate_collection_progression.exe"
        companion_source = ROOT / "data" / "candidates" / "VVFP VV3 Full Heal Candidate.dll"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with self.assertRaises(vv_fun_patcher.PatcherError):
                loader.install_atomic(parent, root / "candidate.exe", "collection_progression")
            destination = root / "candidate.exe"
            companion_destination = root / "VVFP VV3 Full Mastery Candidate.dll"
            destination.write_bytes(b"foreign")
            with self.assertRaises(vv_fun_patcher.PatcherError):
                loader.install_atomic(parent, destination, "collection_progression", companion_source=companion_source, companion_destination=companion_destination)
            self.assertEqual(destination.read_bytes(), b"foreign")
            self.assertFalse(companion_destination.exists())

    def test_publication_requires_one_destination_parent(self):
        parent = PARENTS / "vv3_fullscreen_safe_candidate_collection_progression.exe"
        candidate_dll = ROOT / "data" / "candidates" / "VVFP VV3 Full Heal Candidate.dll"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with self.assertRaises(vv_fun_patcher.PatcherError):
                loader.install_atomic(parent, root / "a" / "candidate.exe", "collection_progression", companion_source=candidate_dll, companion_destination=root / "b" / "VVFP VV3 Full Mastery Candidate.dll")

    def test_second_member_replace_failure_rolls_back_both_without_mixed_pair(self):
        parent = PARENTS / "vv3_fullscreen_safe_candidate_collection_progression.exe"
        candidate_dll = ROOT / "data" / "candidates" / "VVFP VV3 Full Heal Candidate.dll"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            destination = root / "candidate.exe"
            companion_destination = root / "VVFP VV3 Full Mastery Candidate.dll"
            real_replace = loader.os.replace
            calls = {"publish": 0}
            def fail_second(src, dst):
                if str(src).endswith(".stage") and Path(dst) in {destination, companion_destination}:
                    calls["publish"] += 1
                    if calls["publish"] == 2:
                        raise OSError("injected second-member replace failure")
                return real_replace(src, dst)
            with mock.patch.object(loader, "render_parent", return_value=b"CANDIDATE-EXE"):
                with mock.patch.object(loader.os, "replace", side_effect=fail_second):
                    with self.assertRaises(vv_fun_patcher.PatcherError):
                        loader.install_atomic(parent, destination, "collection_progression", companion_source=candidate_dll, companion_destination=companion_destination)
            self.assertFalse(destination.exists())
            self.assertFalse(companion_destination.exists())
            self.assertFalse(list(root.glob("*.stage")))

    def test_reparse_ancestor_rejected_before_any_write(self):
        parent = PARENTS / "vv3_fullscreen_safe_candidate_collection_progression.exe"
        candidate_dll = ROOT / "data" / "candidates" / "VVFP VV3 Full Heal Candidate.dll"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            real_lstat = loader.os.lstat
            def fake_lstat(path):
                st = real_lstat(path)
                if Path(path) == root:
                    return SimpleNamespace(st_mode=st.st_mode, st_file_attributes=0x400, st_dev=st.st_dev, st_ino=st.st_ino, st_size=st.st_size)
                return st
            with mock.patch.object(loader.os, "lstat", side_effect=fake_lstat):
                with self.assertRaises(vv_fun_patcher.PatcherError):
                    loader.install_atomic(parent, root / "candidate.exe", "collection_progression", companion_source=candidate_dll, companion_destination=root / "VVFP VV3 Full Mastery Candidate.dll")
            self.assertEqual(list(root.iterdir()), [])

    def test_unresolved_failure_retains_replayable_report(self):
        parent = PARENTS / "vv3_fullscreen_safe_candidate_collection_progression.exe"
        candidate_dll = ROOT / "data" / "candidates" / "VVFP VV3 Full Heal Candidate.dll"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            destination = root / "candidate.exe"
            companion_destination = root / "VVFP VV3 Full Mastery Candidate.dll"
            real_replace = loader.os.replace
            calls = {"publish": 0}
            def fail_second(src, dst):
                if str(src).endswith(".stage") and Path(dst) in {destination, companion_destination}:
                    calls["publish"] += 1
                    if calls["publish"] == 2:
                        raise OSError("injected second-member replace failure")
                return real_replace(src, dst)
            with mock.patch.object(loader, "render_parent", return_value=b"CANDIDATE-EXE"):
                with mock.patch.object(loader, "_restore_member", return_value=False):
                    with mock.patch.object(loader.os, "replace", side_effect=fail_second):
                        with self.assertRaises(vv_fun_patcher.PatcherError):
                            loader.install_atomic(parent, destination, "collection_progression", companion_source=candidate_dll, companion_destination=companion_destination)
            reports = list(root.glob(".vv3im-recovery-*.json"))
            self.assertEqual(len(reports), 1)
            loader.recover_vv3_transaction(reports[0])
            self.assertFalse(destination.exists())
            self.assertFalse(companion_destination.exists())
            self.assertFalse(list(root.glob(".vv3im-*")))

    def test_recovery_schema_rejects_unknown_field_before_mutation(self):
        parent = PARENTS / "vv3_fullscreen_safe_candidate_collection_progression.exe"
        candidate_dll = ROOT / "data" / "candidates" / "VVFP VV3 Full Heal Candidate.dll"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            destination = root / "candidate.exe"
            companion_destination = root / "VVFP VV3 Full Mastery Candidate.dll"
            real_replace = loader.os.replace
            calls = {"publish": 0}
            def fail_second(src, dst):
                if str(src).endswith(".stage") and Path(dst) in {destination, companion_destination}:
                    calls["publish"] += 1
                    if calls["publish"] == 2:
                        raise OSError("injected second-member replace failure")
                return real_replace(src, dst)
            with mock.patch.object(loader, "render_parent", return_value=b"CANDIDATE-EXE"):
                with mock.patch.object(loader, "_restore_member", return_value=False):
                    with mock.patch.object(loader.os, "replace", side_effect=fail_second):
                        with self.assertRaises(vv_fun_patcher.PatcherError):
                            loader.install_atomic(parent, destination, "collection_progression", companion_source=candidate_dll, companion_destination=companion_destination)
            report = next(root.glob(".vv3im-recovery-*.json"))
            payload = json.loads(report.read_text(encoding="utf-8"))
            payload["unexpected_alias"] = True
            report.write_text(json.dumps(payload), encoding="utf-8")
            before = sorted(p.name for p in root.iterdir())
            with self.assertRaises(vv_fun_patcher.PatcherError):
                loader.recover_vv3_transaction(report)
            self.assertEqual(sorted(p.name for p in root.iterdir()), before)

    def test_recovery_schema_rejects_escape_and_duplicate_member_paths(self):
        base = {
            "schema_version": 2,
            "operation": "install_new",
            "recovery_root": ".",
            "destination_parent": ".",
            "report_relative": "recovery.json",
            "initial_precondition": {"kind": "absent", "members": []},
            "replay_guard": {"kind": "absent", "members": []},
            "members": [],
            "ownership_inventory": [],
            "failure_diagnostic": "x",
        }
        for bad in ("../escape.exe", "same.exe"):
            member = {
                "destination_relative": bad,
                "destination_type": "regular_file",
                "pre_exists": False,
                "pre_sha256": None,
                "pre_size": 0,
                "published_sha256": "A" * 64,
                "published_size": 1,
                "backup_relative": None,
                "stage_relative": None,
                "backup_inventory": None,
                "stage_inventory": None,
                "published_inventory": None,
            }
            payload = dict(base)
            payload["members"] = [member, dict(member)]
            with self.assertRaises(vv_fun_patcher.PatcherError):
                loader._validate_recovery_payload(payload, Path(tempfile.gettempdir()))

    def _make_unresolved_report(self, root: Path):
        parent = PARENTS / "vv3_fullscreen_safe_candidate_collection_progression.exe"
        candidate_dll = ROOT / "data" / "candidates" / "VVFP VV3 Full Heal Candidate.dll"
        destination = root / "candidate.exe"
        companion_destination = root / "VVFP VV3 Full Mastery Candidate.dll"
        real_replace = loader.os.replace
        calls = {"publish": 0}
        def fail_second(src, dst):
            if str(src).endswith(".stage") and Path(dst) in {destination, companion_destination}:
                calls["publish"] += 1
                if calls["publish"] == 2:
                    raise OSError("injected second-member replace failure")
            return real_replace(src, dst)
        with mock.patch.object(loader, "render_parent", return_value=b"CANDIDATE-EXE"):
            with mock.patch.object(loader, "_restore_member", return_value=False):
                with mock.patch.object(loader.os, "replace", side_effect=fail_second):
                    with self.assertRaises(vv_fun_patcher.PatcherError):
                        loader.install_atomic(parent, destination, "collection_progression", companion_source=candidate_dll, companion_destination=companion_destination)
        return next(root.glob(".vv3im-recovery-*.json")), destination, companion_destination

    def test_d274_unknown_recovery_descendant_rejected_before_mutation(self):
        with tempfile.TemporaryDirectory(prefix="vv3-d274-unknown-") as td:
            root = Path(td)
            report, destination, companion = self._make_unresolved_report(root)
            recovery_dir = next(p for p in root.glob(".vv3im-recovery-*") if p.is_dir())
            foreign = recovery_dir / ".foreign-stage"
            foreign.write_bytes(b"foreign")
            before = sorted((p.relative_to(root).as_posix(), p.read_bytes() if p.is_file() else None) for p in root.rglob("*") if p.is_file())
            with self.assertRaises(vv_fun_patcher.PatcherError):
                loader.recover_vv3_transaction(report)
            after = sorted((p.relative_to(root).as_posix(), p.read_bytes() if p.is_file() else None) for p in root.rglob("*") if p.is_file())
            self.assertEqual(after, before)

    def test_c280_complete_game_directory_siblings_are_not_recovery_owned(self):
        with tempfile.TemporaryDirectory(prefix="vv3-c280-game-dir-") as td:
            root = Path(td)
            stock = root / "stock-runtime.exe"
            runtime = root / "runtime.dat"
            stock.write_bytes(b"authenticated stock sibling")
            runtime.write_bytes(b"runtime sibling")
            report, destination, companion = self._make_unresolved_report(root)
            before = {p.name: p.read_bytes() for p in (stock, runtime)}
            loader.recover_vv3_transaction(report)
            self.assertEqual({p.name: p.read_bytes() for p in (stock, runtime)}, before)
            self.assertFalse(destination.exists())
            self.assertFalse(companion.exists())
            self.assertEqual(list(root.glob(".vv3im-*")), [])

    def test_d274_install_new_same_content_foreign_identity_rejected(self):
        with tempfile.TemporaryDirectory(prefix="vv3-d274-identity-") as td:
            root = Path(td)
            report, destination, companion = self._make_unresolved_report(root)
            original = destination.read_bytes()
            destination.unlink()
            destination.write_bytes(original)
            with self.assertRaises(vv_fun_patcher.PatcherError):
                loader.recover_vv3_transaction(report)
            self.assertEqual(destination.read_bytes(), original)
            self.assertTrue(report.exists())

    def test_d274_recovery_root_reparse_rejected_before_report_open(self):
        with tempfile.TemporaryDirectory(prefix="vv3-d274-root-") as td:
            root = Path(td)
            recovery = root / ".vv3im-recovery-root"
            recovery.mkdir()
            report = recovery / ".vv3im-recovery-test.json"
            report.write_text("{}", encoding="utf-8")
            real_lstat = loader.os.lstat
            def fake_lstat(path):
                st = real_lstat(path)
                if Path(path) == recovery:
                    return SimpleNamespace(st_mode=st.st_mode, st_file_attributes=0x400, st_dev=st.st_dev, st_ino=st.st_ino, st_size=st.st_size)
                return st
            with mock.patch.object(loader.os, "lstat", side_effect=fake_lstat):
                with self.assertRaises(vv_fun_patcher.PatcherError):
                    loader.recover_vv3_transaction(recovery)

    def test_d274_cleanup_failure_retains_report_and_recovery_material(self):
        with tempfile.TemporaryDirectory(prefix="vv3-d274-cleanup-") as td:
            root = Path(td)
            report, destination, companion = self._make_unresolved_report(root)
            real_remove = loader._remove_owned
            def fail_recovery(path, **kwargs):
                if Path(path).name.startswith(".vv3im-recovery-"):
                    raise vv_fun_patcher.PatcherError("injected cleanup failure")
                return real_remove(path, **kwargs)
            with mock.patch.object(loader, "_remove_owned", side_effect=fail_recovery):
                with self.assertRaises(vv_fun_patcher.PatcherError):
                    loader.recover_vv3_transaction(report)
            self.assertTrue(report.exists())

    def test_c282_successful_rollback_cleanup_uses_captured_inventory_and_reports_failure(self):
        with tempfile.TemporaryDirectory(prefix="vv3-c282-rollback-cleanup-") as td:
            root = Path(td)
            exe, dll = root / "candidate.exe", root / "candidate.dll"
            exe.write_bytes(b"exe-parent")
            dll.write_bytes(b"dll-parent")
            destinations = [exe, dll]
            pre = {path: loader._state(path) for path in destinations}
            published = {exe: b"exe-candidate", dll: b"dll-candidate"}
            real_replace = loader._replace_verified
            replace_calls = {"count": 0}
            def fail_second(stage, destination, expected_destination, expected_stage):
                replace_calls["count"] += 1
                if replace_calls["count"] == 2:
                    raise OSError("injected second publication failure")
                return real_replace(stage, destination, expected_destination, expected_stage)
            real_remove = loader._remove_owned
            def fail_cleanup(path, **kwargs):
                if kwargs.get("expected_tree") is not None and Path(path).name.startswith(".vv3im-recovery-"):
                    raise vv_fun_patcher.PatcherError("injected rollback cleanup failure")
                return real_remove(path, **kwargs)
            with mock.patch.object(loader, "_replace_verified", side_effect=fail_second), mock.patch.object(loader, "_remove_owned", side_effect=fail_cleanup):
                with self.assertRaises(vv_fun_patcher.PatcherError):
                    loader._transaction("install", destinations, pre, published, expected_preimage={exe: b"exe-parent", dll: b"dll-parent"}, parent=root)
            reports = list(root.glob(".vv3im-recovery-*.json"))
            self.assertEqual(len(reports), 1)
            payload = json.loads(reports[0].read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], 2)
            self.assertTrue(payload["ownership_inventory"])
            self.assertTrue(any(root.joinpath(str(item["path"])).exists() for item in payload["ownership_inventory"]))

    def test_c284_second_backup_cleanup_failure_replays_immediately(self):
        with tempfile.TemporaryDirectory(prefix="vv3-c284-replay-") as td:
            root = Path(td)
            exe, dll = root / "candidate.exe", root / "candidate.dll"
            exe.write_bytes(b"exe-parent")
            dll.write_bytes(b"dll-parent")
            destinations = [exe, dll]
            pre = {path: loader._state(path) for path in destinations}
            published = {exe: b"exe-candidate", dll: b"dll-candidate"}
            real_replace = loader._replace_verified
            calls = {"count": 0}
            def fail_second(stage, destination, expected_destination, expected_stage):
                calls["count"] += 1
                if calls["count"] == 2:
                    raise OSError("injected publication failure")
                return real_replace(stage, destination, expected_destination, expected_stage)
            with mock.patch.object(loader, "_replace_verified", side_effect=fail_second), mock.patch.object(loader, "_restore_member", return_value=False):
                with self.assertRaises(vv_fun_patcher.PatcherError):
                    loader._transaction("install", destinations, pre, published, expected_preimage={exe: b"exe-parent", dll: b"dll-parent"}, parent=root)
            report = next(root.glob(".vv3im-recovery-*.json"))
            real_remove = loader._remove_owned
            removed = {"count": 0}
            def fail_second_backup(path, **kwargs):
                if ".vv3im-" in Path(path).name and Path(path).name.endswith(".backup"):
                    removed["count"] += 1
                    if removed["count"] == 2:
                        raise vv_fun_patcher.PatcherError("injected second-backup cleanup failure")
                return real_remove(path, **kwargs)
            with mock.patch.object(loader, "_remove_owned", side_effect=fail_second_backup):
                with self.assertRaises(vv_fun_patcher.PatcherError):
                    loader.recover_atomic(report)
            retry_report = next(root.glob(".vv3im-recovery-*.json"))
            retry_payload = json.loads(retry_report.read_text(encoding="utf-8"))
            self.assertTrue(any(item.get("backup_relative", "").find("preserved") >= 0 for item in retry_payload["members"]))
            loader.recover_atomic(retry_report)
            self.assertEqual(exe.read_bytes(), b"exe-parent")
            self.assertEqual(dll.read_bytes(), b"dll-parent")
            self.assertFalse(list(root.glob(".vv3im-*")))

    def test_c280_injected_cleanup_descendant_retains_report(self):
        with tempfile.TemporaryDirectory(prefix="vv3-c280-cleanup-child-") as td:
            root = Path(td)
            report, _destination, _companion = self._make_unresolved_report(root)
            real_remove = loader._remove_owned
            def inject_child(path, **kwargs):
                if kwargs.get("expected_tree") == [] and Path(path).name.startswith(".vv3im-recovery-"):
                    (Path(path) / "injected-child").write_bytes(b"foreign")
                return real_remove(path, **kwargs)
            with mock.patch.object(loader, "_remove_owned", side_effect=inject_child):
                with self.assertRaises(vv_fun_patcher.PatcherError):
                    loader.recover_vv3_transaction(report)
            self.assertTrue(report.exists())


if __name__ == "__main__":
    unittest.main()
