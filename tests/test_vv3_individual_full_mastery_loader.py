from __future__ import annotations

import hashlib
import json
import ctypes
import tempfile
import unittest
import uuid
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
            self.assertTrue(report.exists() or list(root.glob(".vv3im-emergency-*.json")))

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
            self.assertTrue(report.exists() or list(root.glob(".vv3im-emergency-*.json")))

    def test_c310_forged_self_issued_cleanup_binding_fails_closed(self):
        with tempfile.TemporaryDirectory(prefix="vv3-c310-forged-issuance-") as td:
            root = Path(td)
            report, destination, companion = self._make_unresolved_report(root)
            payload = json.loads(report.read_text(encoding="utf-8"))
            payload["issuance_identity"]["record"]["sha256"] = "0" * 64
            report.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8", newline="\r\n")
            before = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            with self.assertRaises(vv_fun_patcher.PatcherError):
                loader.recover_vv3_transaction(report)
            after = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            self.assertEqual(after, before)

    def test_c310_same_content_authority_substitution_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="vv3-c310-authority-race-") as td:
            root = Path(td)
            report, _destination, _companion = self._make_unresolved_report(root)
            manifest = loader._chain_manifest_path(report)
            data = manifest.read_bytes()
            manifest.unlink()
            manifest.write_bytes(data)
            with self.assertRaises(vv_fun_patcher.PatcherError):
                loader._read_chain_manifest(report)

    def test_c310_three_generation_successor_chain_is_transitively_bound(self):
        with tempfile.TemporaryDirectory(prefix="vv3-c310-chain-") as td:
            root = Path(td)
            manifest = root / "manifest.json"
            canonical = loader._transaction_authority_path(manifest)
            prior = {"path": "external", "type": "regular_file", "size": 1, "sha256": "a" * 64, "st_dev": 1, "st_ino": 1}
            previous = prior
            names = []
            for _ in range(3):
                successor = canonical.with_name(f"{canonical.stem}.v{uuid.uuid4().hex}.json")
                successor.write_text(json.dumps({"previous_authority_record": previous}, sort_keys=True), encoding="utf-8")
                previous = loader._inventory_entry(root, successor)
                names.append(successor)
            self.assertEqual(loader._discover_transaction_authority(manifest), names[-1])

    def test_c310_canonical_metadata_has_explicit_raw_git_attributes(self):
        attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
        self.assertIn("vv3_individual_full_mastery_candidate.json -text", attributes)
        self.assertIn("vv3_individual_full_mastery_candidate_map.json -text", attributes)
        for name in ("vv3_individual_full_mastery_candidate.json", "vv3_individual_full_mastery_candidate_map.json"):
            data = (ROOT / "data" / "candidates" / name).read_bytes()
            self.assertFalse(data.startswith(b"\xef\xbb\xbf"))
            self.assertNotIn(b"\n", data.replace(b"\r\n", b""))

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
            self.assertTrue(all(item.get("backup_relative", "").endswith(".backup") and item.get("backup_inventory", {}).get("sha256") == item.get("pre_sha256") for item in retry_payload["members"]))
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
            self.assertTrue(report.exists() or list(root.glob(".vv3im-emergency-*.json")))

    def test_c286_deletion_identity_rejects_substituted_report_stage_backup_and_root(self):
        with tempfile.TemporaryDirectory(prefix="vv3-c286-delete-") as td:
            root = Path(td)
            recovery = root / ".vv3im-recovery-test"
            recovery.mkdir()
            for name in ("report.json", "stage.bin", "backup.bin"):
                path = recovery / name
                path.write_bytes(name.encode("ascii"))
                expected = loader._inventory_entry(recovery, path)
                path.write_bytes(b"substituted")
                with self.assertRaises(vv_fun_patcher.PatcherError):
                    loader._remove_owned(path, expected=expected)
                path.write_bytes(name.encode("ascii"))
            expected_root = loader._inventory_entry(root, recovery)
            expected_tree = loader._inventory_tree(recovery)
            replacement = root / ".replacement"
            recovery.rename(replacement)
            recovery.mkdir()
            with self.assertRaises(vv_fun_patcher.PatcherError):
                loader._remove_owned(recovery, expected=expected_root, expected_tree=expected_tree)

    def test_c286_report_publication_race_is_no_overwrite(self):
        with tempfile.TemporaryDirectory(prefix="vv3-c286-report-") as td:
            root = Path(td)
            report, _destination, _companion = self._make_unresolved_report(root)
            payload = json.loads(report.read_text(encoding="utf-8"))
            report.unlink()
            real_link = loader.os.link
            def race(src, dst):
                if Path(dst) == report:
                    report.write_bytes(b"foreign-report")
                return real_link(src, dst)
            with mock.patch.object(loader.os, "link", side_effect=race):
                with self.assertRaises(vv_fun_patcher.PatcherError):
                    loader._write_recovery_at(report, payload, root)
            self.assertEqual(report.read_bytes(), b"foreign-report")
            self.assertFalse(report.with_suffix(".tmp").exists())

    def test_c288_refresh_pointer_race_preserves_old_report_and_foreign_pointer(self):
        with tempfile.TemporaryDirectory(prefix="vv3-c288-refresh-race-") as td:
            root = Path(td)
            report, _destination, _companion = self._make_unresolved_report(root)
            payload = json.loads(report.read_text(encoding="utf-8"))
            root_name = next(item["path"] for item in payload["ownership_inventory"] if item["type"] == "directory")
            recovery_root = root / root_name
            pointer = loader._report_pointer_path(report)
            real_link = loader.os.link
            def race(src, dst):
                if Path(dst) == pointer:
                    pointer.write_bytes(b"foreign-pointer")
                return real_link(src, dst)
            with mock.patch.object(loader.os, "link", side_effect=race):
                with self.assertRaises(vv_fun_patcher.PatcherError):
                    loader._refresh_recovery_report(report, payload, root, recovery_root)
            self.assertTrue(report.exists())
            self.assertEqual(pointer.read_bytes(), b"foreign-pointer")
            self.assertEqual(list(root.glob(f"{report.stem}.v*.json")), [])

    def test_c288_emergency_marker_reconstructs_replays_and_cleans(self):
        with tempfile.TemporaryDirectory(prefix="vv3-c288-emergency-replay-") as td:
            root = Path(td)
            report, destination, companion = self._make_unresolved_report(root)
            payload = json.loads(report.read_text(encoding="utf-8"))
            root_name = next(
                item["path"]
                for item in payload["ownership_inventory"]
                if item["type"] == "directory"
            )
            recovery_root = root / root_name
            details = dict(payload)
            details.update({
                "_report_prefix": ".vv3im",
                "_recovery_root_name": recovery_root.name,
                "_recovery_root_identity": loader._inventory_entry(root, recovery_root),
                "_expected_ownership_inventory": payload["ownership_inventory"],
            })
            details.pop("report_relative", None)
            original_report = loader._inventory_entry(root, report)
            loader._remove_owned(report, expected=original_report)
            marker = loader._write_emergency_marker(root, details, vv_fun_patcher.PatcherError("injected report failure"))
            loader.recover_vv3_transaction(marker)
            self.assertFalse(destination.exists())
            self.assertFalse(companion.exists())
            self.assertEqual(list(root.glob(".vv3im-*")), [])

    def test_c288_emergency_root_escape_and_unknown_child_are_rejected(self):
        with tempfile.TemporaryDirectory(prefix="vv3-c288-emergency-guards-") as td:
            root = Path(td)
            report, _destination, _companion = self._make_unresolved_report(root)
            payload = json.loads(report.read_text(encoding="utf-8"))
            root_name = next(item["path"] for item in payload["ownership_inventory"] if item["type"] == "directory")
            recovery_root = root / root_name
            details = dict(payload)
            details.update({
                "_report_prefix": ".vv3im",
                "_recovery_root_name": recovery_root.name,
                "_recovery_root_identity": loader._inventory_entry(root, recovery_root),
                "_expected_ownership_inventory": payload["ownership_inventory"],
            })
            (recovery_root / "foreign-child").write_bytes(b"foreign")
            with self.assertRaises(vv_fun_patcher.PatcherError):
                loader._write_emergency_marker(root, details, vv_fun_patcher.PatcherError("injected"))
            self.assertTrue((recovery_root / "foreign-child").exists())
            details["_recovery_root_name"] = "..\\escape"
            with self.assertRaises(vv_fun_patcher.PatcherError):
                loader._write_emergency_marker(root, details, vv_fun_patcher.PatcherError("injected"))

    def test_c288_final_delete_race_quarantines_foreign_material(self):
        with tempfile.TemporaryDirectory(prefix="vv3-c288-tombstone-") as td:
            root = Path(td)
            target = root / "owned.bin"
            target.write_bytes(b"owned")
            expected = loader._inventory_entry(root, target)
            original_link = loader.os.link
            def race(src, dst):
                if Path(src) == target:
                    target.write_bytes(b"foreign")
                return original_link(src, dst)
            with mock.patch.object(loader.os, "link", side_effect=race):
                with self.assertRaises(vv_fun_patcher.PatcherError):
                    loader._remove_owned(target, expected=expected)
            tombstones = list(root.glob(".owned.bin.vv3im-tombstone-*"))
            self.assertEqual(len(tombstones), 1)
            self.assertEqual(tombstones[0].read_bytes(), b"foreign")

    def test_c290_directory_form_canonical_and_pointer_chain(self):
        with tempfile.TemporaryDirectory(prefix="vv3-c290-directory-chain-") as td:
            root = Path(td)
            report, _destination, _companion = self._make_unresolved_report(root)
            payload = json.loads(report.read_text(encoding="utf-8"))
            root_name = next(item["path"] for item in payload["ownership_inventory"] if item["type"] == "directory")
            recovery_root = root / root_name
            loader._refresh_recovery_report(report, payload, root, recovery_root)
            loader.recover_atomic(root)
            self.assertFalse(report.exists())
            self.assertEqual(list(root.glob(".vv3im-*")), [])

    def test_c290_directory_form_emergency_marker_chain(self):
        with tempfile.TemporaryDirectory(prefix="vv3-c290-directory-emergency-") as td:
            root = Path(td)
            report, destination, companion = self._make_unresolved_report(root)
            payload = json.loads(report.read_text(encoding="utf-8"))
            root_name = next(item["path"] for item in payload["ownership_inventory"] if item["type"] == "directory")
            recovery_root = root / root_name
            details = dict(payload)
            details.update({
                "_report_prefix": ".vv3im",
                "_recovery_root_name": recovery_root.name,
                "_recovery_root_identity": loader._inventory_entry(root, recovery_root),
                "_expected_ownership_inventory": payload["ownership_inventory"],
            })
            loader._remove_owned(report, expected=loader._inventory_entry(root, report))
            loader._write_emergency_marker(root, details, vv_fun_patcher.PatcherError("injected"))
            loader.recover_atomic(root)
            self.assertFalse(destination.exists())
            self.assertFalse(companion.exists())
            self.assertEqual(list(root.glob(".vv3im-*")), [])

    def test_c290_orphan_successor_and_missing_backup_fail_before_mutation(self):
        with tempfile.TemporaryDirectory(prefix="vv3-c290-orphan-") as td:
            root = Path(td)
            report, destination, companion = self._make_unresolved_report(root)
            successor = report.with_name(f"{report.stem}.v{'a' * 32}{report.suffix}")
            successor.write_bytes(b"orphan")
            before = destination.read_bytes() if destination.exists() else None
            with self.assertRaises(vv_fun_patcher.PatcherError):
                loader.recover_atomic(root)
            self.assertEqual(destination.read_bytes() if destination.exists() else None, before)
            successor.unlink()
            payload = json.loads(report.read_text(encoding="utf-8"))
            payload["ownership_inventory"] = payload["ownership_inventory"][1:]
            report.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(vv_fun_patcher.PatcherError):
                loader.recover_atomic(report)
            self.assertTrue(report.exists())

    def test_c290_directory_prefix_with_dot_v_keeps_canonical_discoverable(self):
        with tempfile.TemporaryDirectory(prefix="vv3-c290-prefix-") as td:
            root = Path(td)
            canonical = root / ".vtest-recovery-0123456789abcdef0123456789abcdef.json"
            successor = root / ".vtest-recovery-0123456789abcdef0123456789abcdef.vffffffffffffffffffffffffffffffff.json"
            canonical.write_bytes(b"canonical")
            successor.write_bytes(b"successor")
            reports, successors, markers = loader._report_chain_siblings(root, canonical, recovery_prefix=".vtest")
            self.assertEqual(reports, [canonical])
            self.assertEqual(successors, [successor])
            self.assertEqual(markers, [])

    def test_c292_publish_postlink_replacement_is_rejected_and_preserved(self):
        with tempfile.TemporaryDirectory(prefix="vv3-c292-publish-race-") as td:
            root = Path(td)
            tmp = root / "report.tmp"
            final = root / "report.json"
            tmp.write_bytes(b"owned")
            real_link = loader.os.link
            def race(src, dst):
                real_link(src, dst)
                Path(dst).unlink()
                Path(dst).write_bytes(b"foreign")
            with mock.patch.object(loader.os, "link", side_effect=race):
                with self.assertRaises(vv_fun_patcher.PatcherError):
                    loader._publish_exclusive(tmp, final, root)
            self.assertEqual(final.read_bytes(), b"foreign")
            self.assertEqual(tmp.read_bytes(), b"owned")

    def test_c292_file_substitution_after_tombstone_link_survives(self):
        with tempfile.TemporaryDirectory(prefix="vv3-c292-file-tombstone-") as td:
            root = Path(td)
            target = root / "owned.bin"
            target.write_bytes(b"owned")
            expected = loader._inventory_entry(root, target)
            real_link = loader.os.link
            def race(src, dst):
                real_link(src, dst)
                target.unlink()
                target.write_bytes(b"foreign")
            with mock.patch.object(loader.os, "link", side_effect=race):
                with self.assertRaises(vv_fun_patcher.PatcherError):
                    loader._quarantine_delete(target, expected, directory=False)
            self.assertEqual(target.read_bytes(), b"foreign")
            tombstones = list(root.glob(".owned.bin.vv3im-tombstone-*"))
            self.assertEqual(len(tombstones), 1)
            self.assertEqual(tombstones[0].read_bytes(), b"owned")

    def test_c292_directory_quarantine_without_noreplace_is_fail_closed(self):
        with tempfile.TemporaryDirectory(prefix="vv3-c292-dir-tombstone-") as td:
            root = Path(td)
            target = root / "owned-dir"
            target.mkdir()
            (target / "member").write_bytes(b"owned")
            expected = loader._inventory_entry(root, target)
            with mock.patch.object(loader, "_move_noreplace", side_effect=vv_fun_patcher.PatcherError("race")):
                with self.assertRaises(vv_fun_patcher.PatcherError):
                    loader._quarantine_delete(target, expected, directory=True)
            self.assertTrue(target.exists())
            self.assertEqual((target / "member").read_bytes(), b"owned")

    def test_c292_final_tombstone_substitution_is_not_deleted(self):
        with tempfile.TemporaryDirectory(prefix="vv3-c292-final-tombstone-") as td:
            root = Path(td)
            target = root / "owned.bin"
            target.write_bytes(b"owned")
            expected = loader._inventory_entry(root, target)
            real_delete = loader._delete_file_by_handle
            def substitute(path, record):
                if "tombstone" in path.name:
                    path.unlink()
                    path.write_bytes(b"foreign")
                    raise vv_fun_patcher.PatcherError("tombstone substitution")
                return real_delete(path, record)
            with mock.patch.object(loader, "_delete_file_by_handle", side_effect=substitute):
                with self.assertRaises(vv_fun_patcher.PatcherError):
                    loader._quarantine_delete(target, expected, directory=False)
            self.assertFalse(target.exists())
            tombstones = list(root.glob(".owned.bin.vv3im-tombstone-*"))
            self.assertEqual(len(tombstones), 1)
            self.assertEqual(tombstones[0].read_bytes(), b"foreign")

    def test_c294_windows_delete_api_signatures_are_declared(self):
        class FakeFunction:
            pass
        class FakeKernel:
            CreateFileW = FakeFunction()
            SetFileInformationByHandle = FakeFunction()
            GetFileInformationByHandleEx = FakeFunction()
            CloseHandle = FakeFunction()
        from ctypes import wintypes
        fake = FakeKernel()
        loader._configure_windows_delete_api(fake, ctypes, wintypes)
        self.assertIs(fake.CreateFileW.restype, wintypes.HANDLE)
        self.assertIs(fake.SetFileInformationByHandle.restype, wintypes.BOOL)
        self.assertIs(fake.GetFileInformationByHandleEx.restype, wintypes.BOOL)
        self.assertIs(fake.CloseHandle.restype, wintypes.BOOL)
        self.assertEqual(len(fake.CreateFileW.argtypes), 7)
        self.assertEqual(len(fake.SetFileInformationByHandle.argtypes), 4)
        self.assertEqual(len(fake.GetFileInformationByHandleEx.argtypes), 4)
        self.assertEqual(len(fake.CloseHandle.argtypes), 1)

    def test_c294_non_windows_delete_path_fails_closed(self):
        with tempfile.TemporaryDirectory(prefix="vv3-c294-posix-delete-") as td:
            root = Path(td)
            target = root / "owned.bin"
            target.write_bytes(b"owned")
            expected = loader._inventory_entry(root, target)
            with mock.patch.object(loader.os, "name", "posix"):
                with self.assertRaises(vv_fun_patcher.PatcherError):
                    loader._delete_file_by_handle(target, expected)
            self.assertEqual(target.read_bytes(), b"owned")

    def test_c296_chain_member_same_content_inode_replacement_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="vv3-c296-chain-race-") as td:
            root = Path(td)
            canonical = root / (".vv3im-recovery-" + "a" * 32 + ".json")
            canonical.write_bytes(b"canonical")
            original = loader._inventory_entry
            calls = {"canonical": 0}

            def recapture(base, path):
                record = original(base, path)
                if path == canonical:
                    calls["canonical"] += 1
                    if calls["canonical"] == 1:
                        replacement = root / "replacement.tmp"
                        replacement.write_bytes(b"canonical")
                        replacement.replace(canonical)
                return record

            with mock.patch.object(loader, "_inventory_entry", side_effect=recapture):
                with self.assertRaises(vv_fun_patcher.PatcherError):
                    loader._report_chain_siblings(root, canonical, recovery_prefix=".vv3im")

    def test_c296_directory_quarantine_source_substitution_fails_before_move(self):
        with tempfile.TemporaryDirectory(prefix="vv3-c296-dir-race-") as td:
            root = Path(td)
            source = root / "owned-dir"
            destination = root / "tombstone"
            source.mkdir()
            (source / "member").write_bytes(b"owned")
            original = loader._inventory_entry
            calls = {"source": 0}

            def substitute(base, path):
                record = original(base, path)
                if path == source:
                    calls["source"] += 1
                    if calls["source"] == 1:
                        source.rename(root / "foreign-dir")
                        source.mkdir()
                return record

            with mock.patch.object(loader, "_inventory_entry", side_effect=substitute):
                with self.assertRaises(vv_fun_patcher.PatcherError):
                    loader._move_noreplace(source, destination)
            self.assertTrue((root / "foreign-dir" / "member").exists())
            self.assertTrue(source.exists())

    def test_c296_foreign_emergency_chain_report_name_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="vv3-c296-foreign-chain-") as td:
            root = Path(td)
            report, _destination, _companion = self._make_unresolved_report(root)
            payload = json.loads(report.read_text(encoding="utf-8"))
            root_name = next(item["path"] for item in payload["ownership_inventory"] if item["type"] == "directory")
            recovery_root = root / root_name
            details = dict(payload)
            details.update({
                "_report_prefix": ".vv3im",
                "_recovery_root_name": recovery_root.name,
                "_recovery_root_identity": loader._inventory_entry(root, recovery_root),
                "_expected_ownership_inventory": payload["ownership_inventory"],
            })
            loader._remove_owned(report, expected=loader._inventory_entry(root, report))
            marker = loader._write_emergency_marker(root, details, vv_fun_patcher.PatcherError("injected"))
            manifest = loader._chain_manifest_path(marker)
            raw = json.loads(manifest.read_text(encoding="utf-8"))
            raw["report_name"] = ".vv3im-emergency-" + "f" * 32 + ".json"
            manifest.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaises(vv_fun_patcher.PatcherError):
                loader.recover_atomic(marker)
            self.assertTrue(marker.exists())

    def test_c298_chain_manifest_roles_are_strictly_bound_before_mutation(self):
        with tempfile.TemporaryDirectory(prefix="vv3-c298-chain-roles-") as td:
            root = Path(td)
            report, destination, _companion = self._make_unresolved_report(root)
            manifest = loader._chain_manifest_path(report)
            raw = json.loads(manifest.read_text(encoding="utf-8"))
            raw["member_roles"] = {"foreign": "recovery_member"}
            manifest.write_text(json.dumps(raw), encoding="utf-8")
            before = destination.read_bytes() if destination.exists() else None
            with self.assertRaises(vv_fun_patcher.PatcherError):
                loader.recover_atomic(report)
            self.assertEqual(destination.read_bytes() if destination.exists() else None, before)
            self.assertTrue(manifest.exists())

    def test_c298_orphan_chain_manifest_wrong_prefix_fails_closed(self):
        with tempfile.TemporaryDirectory(prefix="vv3-c298-chain-prefix-") as td:
            root = Path(td)
            report, destination, _companion = self._make_unresolved_report(root)
            orphan = root / (".chain-.other-recovery-" + "a" * 32 + ".json")
            orphan.write_text("{}", encoding="utf-8")
            before = destination.read_bytes() if destination.exists() else None
            with self.assertRaises(vv_fun_patcher.PatcherError):
                loader.recover_atomic(report)
            self.assertEqual(destination.read_bytes() if destination.exists() else None, before)
            self.assertTrue(orphan.exists())

    def test_c298_missing_directory_quarantine_source_fails_closed(self):
        with tempfile.TemporaryDirectory(prefix="vv3-c298-missing-source-") as td:
            root = Path(td)
            with self.assertRaises(vv_fun_patcher.PatcherError):
                loader._move_noreplace(root / "missing", root / "tombstone")
            self.assertFalse((root / "tombstone").exists())

    def test_c300_chain_commit_states_are_explicit_and_replayable(self):
        with tempfile.TemporaryDirectory(prefix="vv3-c300-states-") as td:
            root = Path(td)
            report, _destination, _companion = self._make_unresolved_report(root)
            manifest = loader._chain_manifest_path(report)
            self.assertEqual(json.loads(manifest.read_text(encoding="utf-8"))["transaction_journal"]["state"], "canonical_published")
            payload = json.loads(report.read_text(encoding="utf-8"))
            recovery_root = root / next(item["path"] for item in payload["ownership_inventory"] if item["type"] == "directory")
            loader._refresh_recovery_report(report, payload, root, recovery_root)
            successor = next(root.glob(f"{report.stem}.v*.json"))
            successor_manifest = loader._chain_manifest_path(successor)
            self.assertEqual(json.loads(successor_manifest.read_text(encoding="utf-8"))["transaction_journal"]["state"], "successor_pointer_manifest")

    def test_c300_vv3_mutation_fails_before_io_on_32bit_windows(self):
        with mock.patch.object(loader.os, "name", "nt"), \
             mock.patch.object(loader.struct, "calcsize", return_value=4), \
             mock.patch.object(loader.os, "lstat", side_effect=AssertionError("filesystem touched")):
            with self.assertRaises(vv_fun_patcher.PatcherError):
                loader.install_atomic(Path("missing.exe"), Path("candidate.exe"), "collection_progression", companion_source=Path("missing.dll"), companion_destination=Path("companion.dll"))

    def test_c300_tombstone_deletion_substitution_retains_verified_vv3_backup(self):
        with tempfile.TemporaryDirectory(prefix="vv3-c300-preserved-") as td:
            root = Path(td)
            target = root / "owned.bin"
            target.write_bytes(b"owned")
            expected = loader._inventory_entry(root, target)
            original_delete = loader._delete_file_by_handle

            def substitute(path, identity):
                if path == target:
                    target.unlink()
                    target.write_bytes(b"foreign")
                return original_delete(path, identity)

            with mock.patch.object(loader, "_delete_file_by_handle", side_effect=substitute):
                with self.assertRaises(vv_fun_patcher.PatcherError):
                    loader._quarantine_delete(target, expected, directory=False)
            preserved = list(root.glob(".owned.bin.vv3im-preserved-*.backup"))
            self.assertGreaterEqual(len(preserved), 2)
            self.assertIn(b"owned", [item.read_bytes() for item in preserved])
            self.assertEqual(target.read_bytes(), b"foreign")

    def test_c302_manifest_uses_one_bound_transaction_journal(self):
        with tempfile.TemporaryDirectory(prefix="vv3-c302-journal-") as td:
            root = Path(td)
            report, _destination, _companion = self._make_unresolved_report(root)
            manifest = loader._chain_manifest_path(report)
            raw = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertNotIn("commit_state", raw)
            self.assertEqual(raw["schema_version"], 3)
            self.assertEqual(raw["transaction_journal"]["state"], "canonical_published")
            self.assertEqual(raw["transaction_journal"]["authority"]["report"]["name"], report.name)

            raw["transaction_journal"]["state"] = "emergency_marker"
            manifest.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaises(vv_fun_patcher.PatcherError):
                loader._read_chain_manifest(report)

    def test_c302_journal_rejects_role_swap_and_duplicate_destination(self):
        with tempfile.TemporaryDirectory(prefix="vv3-c302-roles-") as td:
            root = Path(td)
            report, _destination, _companion = self._make_unresolved_report(root)
            manifest = loader._chain_manifest_path(report)
            raw = json.loads(manifest.read_text(encoding="utf-8"))
            roles = dict(raw["member_roles"])
            keys = list(roles)
            self.assertGreaterEqual(len(keys), 2)
            roles[keys[0]] = "bogus_role"
            raw["member_roles"] = roles
            manifest.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaises(vv_fun_patcher.PatcherError):
                loader._read_chain_manifest(report)

    def test_c304_independent_authority_journal_binds_manifest_identity(self):
        with tempfile.TemporaryDirectory(prefix="vv3-c304-independent-journal-") as td:
            root = Path(td)
            report, _destination, _companion = self._make_unresolved_report(root)
            manifest = loader._chain_manifest_path(report)
            journal = loader._transaction_authority_path(manifest)
            self.assertTrue(journal.exists())
            raw = json.loads(journal.read_text(encoding="utf-8"))
            self.assertEqual(raw["kind"], "vv3_recovery_transaction_authority")
            self.assertEqual(raw["manifest_name"], manifest.name)
            raw["manifest_record"]["sha256"] = "0" * 64
            journal.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaises(vv_fun_patcher.PatcherError):
                loader._read_chain_manifest(report)

    def test_c304_guard_failure_retains_owned_copy_and_replays(self):
        with tempfile.TemporaryDirectory(prefix="vv3-c304-guard-replay-") as td:
            root = Path(td)
            target = root / "owned.bin"
            target.write_bytes(b"owned")
            expected = loader._inventory_entry(root, target)
            real_delete = loader._delete_file_by_handle
            failed = {"done": False}

            def fail_guard(path, identity):
                if "preserved-guard-" in path.name and not failed["done"]:
                    failed["done"] = True
                    raise vv_fun_patcher.PatcherError("injected final guard failure")
                return real_delete(path, identity)

            with mock.patch.object(loader, "_delete_file_by_handle", side_effect=fail_guard):
                with self.assertRaises(vv_fun_patcher.PatcherError):
                    loader._quarantine_delete(target, expected, directory=False)
            authorities = list(root.glob(".vv3im-cleanup-*.json"))
            self.assertEqual(len(authorities), 1)
            self.assertTrue(any(item.read_bytes() == b"owned" for item in root.glob("*.backup")))
            loader.recover_cleanup_authority(authorities[0])
            self.assertEqual(list(root.glob(".vv3im-cleanup-*.json")), [])
            self.assertEqual(list(root.glob("*.backup")), [])

    def test_c302_canonical_and_emergency_authorities_conflict_before_replay(self):
        with tempfile.TemporaryDirectory(prefix="vv3-c302-conflict-") as td:
            root = Path(td)
            report, _destination, _companion = self._make_unresolved_report(root)
            payload = json.loads(report.read_text(encoding="utf-8"))
            root_name = next(item["path"] for item in payload["ownership_inventory"] if item["type"] == "directory")
            recovery_root = root / root_name
            details = dict(payload)
            details.update({
                "_report_prefix": ".vv3im",
                "_recovery_root_name": recovery_root.name,
                "_recovery_root_identity": loader._inventory_entry(root, recovery_root),
                "_expected_ownership_inventory": payload["ownership_inventory"],
            })
            details.pop("report_relative", None)
            marker = loader._write_emergency_marker(root, details, vv_fun_patcher.PatcherError("injected"))
            with self.assertRaises(vv_fun_patcher.PatcherError):
                loader.recover_vv3_transaction(marker)
            self.assertTrue(report.exists())
            self.assertTrue(marker.exists())

    def test_c302_directory_cleanup_uses_identity_delete_not_path_rmdir(self):
        with tempfile.TemporaryDirectory(prefix="vv3-c302-dir-delete-") as td:
            root = Path(td)
            target = root / "owned-dir"
            target.mkdir()
            expected = loader._inventory_entry(root, target)
            calls = []

            def move(source, destination):
                source.rename(destination)

            def delete_directory(path, identity):
                calls.append((path, identity))
                path.rmdir()

            with mock.patch.object(loader, "_move_noreplace", side_effect=move), \
                 mock.patch.object(loader, "_delete_directory_by_handle", side_effect=delete_directory):
                loader._quarantine_delete(target, expected, directory=True)
            self.assertEqual(len(calls), 1)
            self.assertFalse(target.exists())

    def test_c302_backup_replacement_after_tombstone_delete_retains_owned_guard(self):
        with tempfile.TemporaryDirectory(prefix="vv3-c302-backup-race-") as td:
            root = Path(td)
            target = root / "owned.bin"
            target.write_bytes(b"owned")
            expected = loader._inventory_entry(root, target)
            real_delete = loader._delete_file_by_handle
            injected = {"done": False}

            def delete(path, identity):
                result = real_delete(path, identity)
                if "vv3im-tombstone-" in path.name and not injected["done"]:
                    preserved = next(item for item in root.glob(".owned.bin.vv3im-preserved-*.backup") if "preserved-guard-" not in item.name)
                    preserved.unlink()
                    preserved.write_bytes(b"foreign")
                    injected["done"] = True
                return result

            with mock.patch.object(loader, "_delete_file_by_handle", side_effect=delete):
                with self.assertRaises(vv_fun_patcher.PatcherError):
                    loader._quarantine_delete(target, expected, directory=False)
            backups = list(root.glob("*.backup"))
            self.assertIn(b"foreign", [item.read_bytes() for item in backups])
            self.assertIn(b"owned", [item.read_bytes() for item in backups])

    def test_c306_hidden_namespace_rejects_foreign_insertion(self):
        with tempfile.TemporaryDirectory(prefix="vv3-c306-hidden-") as td:
            root = Path(td)
            # The production name is intentionally nested behind a member
            # basename; it must remain accepted while an arbitrary prefix is
            # rejected.
            owned = root / (".candidate.exe.vv3im-preserved-" + "a" * 32 + ".backup")
            owned.write_bytes(b"owned")
            loader._validate_vv3_hidden_namespace(root)
            foreign = root / ".vv3im-foreign"
            foreign.write_bytes(b"foreign")
            with self.assertRaises(vv_fun_patcher.PatcherError):
                loader._validate_vv3_hidden_namespace(root)
            self.assertEqual(foreign.read_bytes(), b"foreign")

    def test_c306_transaction_authority_rejects_malformed_existing_content(self):
        with tempfile.TemporaryDirectory(prefix="vv3-c306-authority-") as td:
            root = Path(td)
            manifest = root / ".chain-manifest.json"
            manifest.write_bytes(b"manifest")
            payload = {
                "report_name": "report.json", "report_record": None,
                "canonical_name": None, "canonical_record": None,
                "pointer_name": None, "pointer_record": None,
                "successor_name": None, "successor_record": None,
                "marker_name": None, "marker_record": None,
                "recovery_root_name": "recovery", "recovery_root_record": None,
                "ownership_inventory": [], "members": [], "member_roles": {},
                "destination_paths_absolute": [],
                "transaction_journal": {"state": "prepared"},
            }
            manifest_record = loader._inventory_entry(root, manifest)
            journal, original_record = loader._write_transaction_authority(manifest, payload, manifest_record)
            raw = json.loads(journal.read_text(encoding="utf-8"))
            raw["member_roles"] = "foreign"
            journal.write_text(json.dumps(raw, sort_keys=True), encoding="utf-8")
            tampered = journal.read_bytes()
            with self.assertRaises(vv_fun_patcher.PatcherError):
                loader._write_transaction_authority(manifest, payload, manifest_record)
            self.assertEqual(journal.read_bytes(), tampered)
            self.assertNotEqual(loader._inventory_entry(root, journal), original_record)

    def test_c306_late_complete_authority_temp_write_is_accepted(self):
        with tempfile.TemporaryDirectory(prefix="vv3-c306-late-temp-") as td:
            root = Path(td)
            manifest = root / ".chain-manifest.json"
            manifest.write_bytes(b"manifest")
            payload = {
                "report_name": "report.json", "report_record": None,
                "canonical_name": None, "canonical_record": None,
                "pointer_name": None, "pointer_record": None,
                "successor_name": None, "successor_record": None,
                "marker_name": None, "marker_record": None,
                "recovery_root_name": "recovery", "recovery_root_record": None,
                "ownership_inventory": [], "members": [], "member_roles": {},
                "destination_paths_absolute": [],
                "transaction_journal": {"state": "prepared"},
            }
            real_write = loader._write_file
            def late_write(path, data):
                real_write(path, data)
                if Path(path).suffix == ".tmp":
                    raise OSError("late write after complete bytes")
            with mock.patch.object(loader, "_write_file", side_effect=late_write):
                journal, record = loader._write_transaction_authority(manifest, payload, loader._inventory_entry(root, manifest))
            self.assertEqual(record, loader._inventory_entry(root, journal))
            self.assertTrue(journal.is_file())

    def test_c306_cleanup_authority_rejects_same_inode_content_mutation(self):
        with tempfile.TemporaryDirectory(prefix="vv3-c306-cleanup-") as td:
            root = Path(td)
            owned = root / "owned.bin"
            owned.write_bytes(b"owned")
            record = loader._inventory_entry(root, owned)
            authority, _ = loader._write_cleanup_authority(root, [{"name": owned.name, "role": "source", "record": record}])
            owned.write_bytes(b"foreign")
            with self.assertRaises(vv_fun_patcher.PatcherError):
                loader.recover_cleanup_authority(authority)
            self.assertEqual(owned.read_bytes(), b"foreign")
            self.assertTrue(authority.exists())

    def test_c308_cleanup_authority_is_schema2_bound_and_exact_namespace(self):
        with tempfile.TemporaryDirectory(prefix="vv3-c308-authority-") as td:
            root = Path(td)
            owned = root / "owned.bin"
            owned.write_bytes(b"owned")
            record = loader._inventory_entry(root, owned)
            with mock.patch.object(loader, "_require_windows_identity_atomic", return_value=None), \
                 mock.patch.object(loader, "_delete_file_by_handle", side_effect=lambda path, expected: Path(path).unlink()):
                authority, _ = loader._write_cleanup_authority(root, [{"name": owned.name, "role": "source", "record": record}])
            raw = json.loads(authority.read_text(encoding="utf-8"))
            self.assertEqual(raw["schema_version"], 2)
            self.assertEqual(raw["authority_binding"]["owner"], "vv3_individual_full_mastery")
            self.assertEqual(raw["transaction_binding"]["member_names"], [owned.name])
            self.assertIn("namespace_inventory", raw)

    def test_c308_forged_cleanup_target_is_rejected_before_delete(self):
        with tempfile.TemporaryDirectory(prefix="vv3-c308-forged-") as td:
            root = Path(td)
            owned = root / "owned.bin"
            foreign = root / "foreign.bin"
            owned.write_bytes(b"owned")
            foreign.write_bytes(b"foreign")
            record = loader._inventory_entry(root, owned)
            with mock.patch.object(loader, "_require_windows_identity_atomic", return_value=None), \
                 mock.patch.object(loader, "_delete_file_by_handle", side_effect=lambda path, expected: Path(path).unlink()):
                authority, _ = loader._write_cleanup_authority(root, [{"name": owned.name, "role": "source", "record": record}])
            raw = json.loads(authority.read_text(encoding="utf-8"))
            raw["members"][0]["name"] = foreign.name
            authority.write_text(json.dumps(raw, sort_keys=True), encoding="utf-8", newline="\r\n")
            with self.assertRaises(vv_fun_patcher.PatcherError):
                loader.recover_cleanup_authority(authority)
            self.assertEqual(owned.read_bytes(), b"owned")
            self.assertEqual(foreign.read_bytes(), b"foreign")

    def test_c308_hidden_namespace_rejects_arbitrary_valid_looking_member(self):
        with tempfile.TemporaryDirectory(prefix="vv3-c308-hidden-") as td:
            root = Path(td)
            foreign = root / (".vv3im-preserved-" + "a" * 32 + ".backup")
            foreign.write_bytes(b"foreign")
            with self.assertRaises(vv_fun_patcher.PatcherError):
                loader._validate_vv3_hidden_namespace(root, expected=set())

    def test_c308_manifest_map_pins_are_canonical_and_current(self):
        manifest = ROOT / "data" / "candidates" / "vv3_individual_full_mastery_candidate.json"
        mapping = ROOT / "data" / "candidates" / "vv3_individual_full_mastery_candidate_map.json"
        for path, expected in ((manifest, "943A8B1F04C34CB094ABF7CCC8863B2F17F4BAC179E5DA6A68E6FADD833E1884"), (mapping, "610D27014C8131C935BA4326D64FDB1D25285104567F060BD534653040562187")):
            data = path.read_bytes()
            self.assertFalse(data.startswith(b"\xef\xbb\xbf"))
            self.assertFalse(any(data[i] == 0x0A and (i == 0 or data[i - 1] != 0x0D) for i in range(len(data))))
            self.assertEqual(hashlib.sha256(data).hexdigest().upper(), expected)

    def test_c308_authority_publish_failure_keeps_prior_valid_journal(self):
        with tempfile.TemporaryDirectory(prefix="vv3-c308-journal-") as td:
            root = Path(td)
            manifest = root / ".chain-manifest.json"
            manifest.write_bytes(b"manifest")
            payload = {
                "report_name": "report.json", "report_record": None,
                "canonical_name": None, "canonical_record": None,
                "pointer_name": None, "pointer_record": None,
                "successor_name": None, "successor_record": None,
                "marker_name": None, "marker_record": None,
                "recovery_root_name": "recovery", "recovery_root_record": None,
                "ownership_inventory": [], "members": [], "member_roles": {},
                "destination_paths_absolute": [],
                "transaction_journal": {"state": "prepared"},
            }
            with mock.patch.object(loader, "_require_windows_identity_atomic", return_value=None), \
                 mock.patch.object(loader, "_delete_file_by_handle", side_effect=lambda path, expected: Path(path).unlink()):
                journal, old_record = loader._write_transaction_authority(manifest, payload, loader._inventory_entry(root, manifest))
                with mock.patch.object(loader, "_publish_exclusive", side_effect=vv_fun_patcher.PatcherError("publish race")):
                    with self.assertRaises(vv_fun_patcher.PatcherError):
                        loader._write_transaction_authority(manifest, payload, loader._inventory_entry(root, manifest))
            self.assertTrue(journal.exists())
            self.assertEqual(loader._inventory_entry(root, journal), old_record)

    def test_c318_emergency_marker_requires_embedded_security_bindings(self):
        with tempfile.TemporaryDirectory(prefix="vv3-c318-emergency-bindings-") as td:
            root = Path(td)
            report, _destination, _companion = self._make_unresolved_report(root)
            payload = json.loads(report.read_text(encoding="utf-8"))
            recovery_root = root / next(item["path"] for item in payload["ownership_inventory"] if item["type"] == "directory")
            details = dict(payload)
            details.update({
                "_report_prefix": ".vv3im",
                "_recovery_root_name": recovery_root.name,
                "_recovery_root_identity": loader._inventory_entry(root, recovery_root),
                "_expected_ownership_inventory": payload["ownership_inventory"],
            })
            details.pop("report_parent_identity", None)
            with self.assertRaises(vv_fun_patcher.PatcherError):
                loader._write_emergency_marker(root, details, vv_fun_patcher.PatcherError("injected"))
            self.assertFalse(list(root.glob(".vv3im-emergency-*.json")))

    def test_c318_emergency_reader_rejects_synthesized_location_bindings(self):
        with tempfile.TemporaryDirectory(prefix="vv3-c318-synthesized-location-") as td:
            root = Path(td)
            report, _destination, _companion = self._make_unresolved_report(root)
            payload = json.loads(report.read_text(encoding="utf-8"))
            recovery_root = root / next(item["path"] for item in payload["ownership_inventory"] if item["type"] == "directory")
            details = dict(payload)
            details.update({
                "_report_prefix": ".vv3im",
                "_recovery_root_name": recovery_root.name,
                "_recovery_root_identity": loader._inventory_entry(root, recovery_root),
                "_expected_ownership_inventory": payload["ownership_inventory"],
            })
            marker = loader._write_emergency_marker(root, details, vv_fun_patcher.PatcherError("injected"))
            raw = json.loads(marker.read_text(encoding="utf-8"))
            raw["recovery_payload"].pop("destination_parent_absolute", None)
            marker.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaises(vv_fun_patcher.PatcherError):
                loader._read_issuance_binding(loader._chain_manifest_path(marker))

    def test_c318_vv3_report_rejects_vv5_registry_fields(self):
        with tempfile.TemporaryDirectory(prefix="vv3-c318-cross-caller-") as td:
            root = Path(td)
            report, _destination, _companion = self._make_unresolved_report(root)
            payload = json.loads(report.read_text(encoding="utf-8"))
            payload["issuance_registry_relative"] = ".vv5run-issuance"
            payload["issuance_registry_identity"] = {"st_dev": 1, "st_ino": 2}
            allowed = {key for key in payload if key not in {"schema_version", "operation", "recovery_root", "destination_parent", "report_relative", "initial_precondition", "replay_guard", "members", "ownership_inventory", "failure_diagnostic"}}
            with self.assertRaises(vv_fun_patcher.PatcherError):
                loader._validate_recovery_payload(payload, root, allowed_metadata=allowed)

    def test_c318_mutation_after_second_namespace_capture_fails_closed(self):
        with tempfile.TemporaryDirectory(prefix="vv3-c318-second-capture-") as td:
            root = Path(td)
            report, _destination, _companion = self._make_unresolved_report(root)
            original = loader._validate_vv3_hidden_namespace
            injected = {"done": False}
            def inject(parent, *, expected=None):
                result = original(parent, expected=expected)
                if expected and len(expected) == 1 and next(iter(expected)).startswith(".vv3im-journal-") and not injected["done"]:
                    (root / ".vv3im-foreign-after-capture").write_bytes(b"foreign")
                    injected["done"] = True
                return result
            with mock.patch.object(loader, "_validate_vv3_hidden_namespace", side_effect=inject):
                with self.assertRaises(vv_fun_patcher.PatcherError):
                    loader.recover_vv3_transaction(report)
            self.assertTrue((root / ".vv3im-foreign-after-capture").exists())

    def test_c318_final_authority_deletion_failure_retains_journal(self):
        with tempfile.TemporaryDirectory(prefix="vv3-c318-finalization-replay-") as td:
            root = Path(td)
            report, _destination, _companion = self._make_unresolved_report(root)
            original_delete = loader._delete_file_by_handle
            def fail_authority(path, expected):
                if Path(path).name.startswith(".vv3im-journal-"):
                    raise vv_fun_patcher.PatcherError("injected final authority deletion failure")
                return original_delete(path, expected)
            with mock.patch.object(loader, "_delete_file_by_handle", side_effect=fail_authority):
                with self.assertRaises(vv_fun_patcher.PatcherError):
                    loader.recover_vv3_transaction(report)
            self.assertTrue(list(root.glob(".vv3im-journal-*.json")))


if __name__ == "__main__":
    unittest.main()
