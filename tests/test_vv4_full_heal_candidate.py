import json
import struct
import sys
import unittest
from unittest.mock import patch as mock_patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv4_full_heal import (  # noqa: E402
    NO_DEDUCTION,
    apply_transaction,
    dry_run,
    plan_transaction,
    success_message,
    failure_message,
    TECH_DEDUCTION_RECEIVER,
    TECH_DEDUCTION_CALL,
)


MANIFEST = ROOT / "data/candidates/vv4_full_heal_cure_all_candidate.json"
MAP = ROOT / "data/candidates/vv4_full_heal_cure_all_candidate_map.json"


class VV4FullHealCandidateTests(unittest.TestCase):
    def test_final_companion_verification_uses_full_relative_path_and_last_writer(self):
        import tempfile
        import hashlib
        import vv_fun_patcher as patcher
        with tempfile.TemporaryDirectory(prefix="vv4hc-companion-final-") as temp:
            root = Path(temp)
            (root / "a").mkdir()
            (root / "b").mkdir()
            (root / "a" / "same.dll").write_bytes(b"final-a")
            (root / "b" / "same.dll").write_bytes(b"final-b")
            records = [
                {"path": str(root / "a" / "same.dll"), "sha256": hashlib.sha256(b"old-a").hexdigest()},
                {"path": str(root / "a" / "same.dll"), "sha256": hashlib.sha256(b"final-a").hexdigest()},
                {"path": str(root / "b" / "same.dll"), "sha256": hashlib.sha256(b"final-b").hexdigest()},
            ]
            patcher._verify_final_companion_records(root, records)

    def test_final_companion_verification_rejects_stale_last_writer(self):
        import tempfile
        import hashlib
        import vv_fun_patcher as patcher
        with tempfile.TemporaryDirectory(prefix="vv4hc-companion-stale-") as temp:
            root = Path(temp)
            (root / "same.dll").write_bytes(b"candidate")
            records = [
                {"path": str(root / "same.dll"), "sha256": hashlib.sha256(b"candidate").hexdigest()},
                {"path": str(root / "same.dll"), "sha256": hashlib.sha256(b"parent").hexdigest()},
            ]
            with self.assertRaises(Exception):
                patcher._verify_final_companion_records(root, records)

    def test_recovery_report_replays_verified_backup_and_cleans_material(self):
        import tempfile
        import hashlib
        import vv_fun_patcher as patcher
        with tempfile.TemporaryDirectory(prefix="vv4hc-recovery-") as temp:
            root = Path(temp)
            destination = root / "dest" / "game.exe"
            destination.parent.mkdir()
            destination.write_bytes(b"original")
            recovery = root / ".recovery"
            backup_dir = recovery / "backups"
            backup_dir.mkdir(parents=True)
            backup = backup_dir / "game.exe"
            backup.write_bytes(b"original")
            destination.unlink()
            records = [{
                "relative_path": "game.exe",
                "original_path": str(destination),
                "sha256": hashlib.sha256(b"original").hexdigest().upper(),
                "size": len(b"original"),
            }]
            destination.parent.rmdir()
            report = patcher._write_recovery_report(
                recovery, "install", records, backup_dir,
                destination_root=destination.parent,
                destination_snapshot={"exists": False, "entries": []},
                destination_precondition={"exists": False, "entries": []},
                restored_snapshot={"exists": True, "entries": [{
                    "relative_path": "game.exe", "type": "file", "size": 8,
                    "sha256": hashlib.sha256(b"original").hexdigest().upper(),
                }]},
            )
            patcher.recover_vv4_transaction(recovery)
            self.assertEqual(destination.read_bytes(), b"original")
            self.assertFalse(recovery.exists())

    def test_production_removal_recovery_retains_candidate_backup_and_replays(self):
        import importlib.util
        import tempfile
        import vv_fun_patcher as patcher
        spec = importlib.util.spec_from_file_location(
            "vv4hc_builder_production_recovery", ROOT / "scripts" / "build_vv4_full_heal_candidate.py"
        )
        builder = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(builder)
        feature = patcher.FunPatch(json.loads(MANIFEST.read_text(encoding="utf-8")))
        page, _ = builder.build_page()
        companion, _ = builder.build_resource_only_companion(builder.PARENT_DLL.read_bytes())
        for mode in ("collection_progression", "immediate_fixed"):
            with tempfile.TemporaryDirectory(prefix="vv4hc-production-recovery-") as temp:
                root = Path(temp)
                exe_name = "Virtual Villagers - The Tree of Life - Modded.exe"
                parent = builder._render_parents()[mode]
                (root / exe_name).write_bytes(builder._patch_parent(parent, page))
                (root / "VVFP Origins Icons.dll").write_bytes(companion)
                real_replace = patcher.os.replace
                calls = {"count": 0}
                def fail_publish_and_first_restore(source, destination):
                    calls["count"] += 1
                    if calls["count"] in (2, 3):
                        raise OSError("injected production restore failure")
                    return real_replace(source, destination)
                with mock_patch.object(patcher.os, "replace", side_effect=fail_publish_and_first_restore):
                    with self.assertRaises(Exception):
                        patcher.publish_vv4_full_heal_removal(root, exe_name, feature, mode)
                recovery_dirs = list(root.parent.glob(f".{root.name}.remove-recovery-*"))
                self.assertEqual(len(recovery_dirs), 1)
                report = recovery_dirs[0] / "recovery-report.json"
                payload = json.loads(report.read_text(encoding="utf-8"))
                self.assertTrue(payload["members"])
                member = payload["members"][0]
                self.assertEqual(member["original_size"], 942080)
                self.assertEqual(member["backup_size"], 942080)
                self.assertTrue(member["backup_relative_path"])
                patcher.recover_vv4_transaction(recovery_dirs[0])
                self.assertEqual(patcher.sha256(root / exe_name), patcher.VV4_FULL_HEAL_CANDIDATE_EXE_HASHES[mode])
                self.assertEqual(patcher.sha256(root / "VVFP Origins Icons.dll"), feature.raw["companion_files"][0]["sha256"])

    def test_replay_second_member_failure_retains_backups_for_successful_retry(self):
        import tempfile
        import hashlib
        import vv_fun_patcher as patcher
        with tempfile.TemporaryDirectory(prefix="vv4hc-replay-retry-") as temp:
            root = Path(temp)
            destination = root / "dest"
            destination.mkdir()
            (destination / "a.bin").write_bytes(b"old-a")
            (destination / "b.bin").write_bytes(b"old-b")
            recovery = root / ".recovery"
            backup_dir = recovery / "backups"
            backup_dir.mkdir(parents=True)
            (backup_dir / "a.bin").write_bytes(b"new-a")
            (backup_dir / "b.bin").write_bytes(b"new-b")
            records = []
            for name in ("a.bin", "b.bin"):
                data = (backup_dir / name).read_bytes()
                records.append({
                    "relative_path": name,
                    "original_path": str(destination / name),
                    "sha256": hashlib.sha256(data).hexdigest().upper(),
                    "size": len(data),
                })
            report = patcher._write_recovery_report(
                recovery, "remove", records, backup_dir,
                destination_root=destination,
                destination_snapshot=patcher._capture_tree_snapshot(destination),
                destination_precondition=patcher._capture_tree_snapshot(destination),
                restored_snapshot={"exists": True, "entries": [
                    {"relative_path": "a.bin", "type": "file", "size": 5, "sha256": hashlib.sha256(b"new-a").hexdigest().upper()},
                    {"relative_path": "b.bin", "type": "file", "size": 5, "sha256": hashlib.sha256(b"new-b").hexdigest().upper()},
                ]},
            )
            payload = json.loads(report.read_text(encoding="utf-8"))
            real_replace = patcher.os.replace
            calls = {"count": 0}
            def fail_second(source, destination_path):
                calls["count"] += 1
                if calls["count"] == 2:
                    raise OSError("injected replay failure")
                return real_replace(source, destination_path)
            with mock_patch.object(patcher.os, "replace", side_effect=fail_second):
                with self.assertRaises(Exception):
                    patcher.recover_vv4_transaction(recovery)
            payload_after = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(len(payload_after["members"]), 2)
            self.assertTrue(all((recovery / item["backup_relative_path"]).is_file() for item in payload_after["members"]))
            patcher.recover_vv4_transaction(recovery)
            self.assertEqual((destination / "a.bin").read_bytes(), b"new-a")
            self.assertEqual((destination / "b.bin").read_bytes(), b"new-b")

    def test_snapshot_rejects_simulated_windows_reparse_attribute_before_walk(self):
        import stat
        import tempfile
        from types import SimpleNamespace
        import vv_fun_patcher as patcher
        with tempfile.TemporaryDirectory(prefix="vv4hc-reparse-") as temp:
            root = Path(temp)
            fake = SimpleNamespace(st_mode=stat.S_IFDIR | 0o755, st_file_attributes=0x400)
            with mock_patch.object(patcher.os, "lstat", return_value=fake):
                with self.assertRaises(Exception):
                    patcher._capture_tree_snapshot(root)

    def test_install_new_recovery_rejects_foreign_destination_before_any_write(self):
        import hashlib
        import tempfile
        import vv_fun_patcher as patcher
        with tempfile.TemporaryDirectory(prefix="vv4hc-install-new-race-") as temp:
            root = Path(temp)
            destination = root / "new-game"
            recovery = root / ".recovery"
            backup_dir = recovery / "backups"
            backup_dir.mkdir(parents=True)
            backup = backup_dir / "game.exe"
            backup.write_bytes(b"original")
            digest = hashlib.sha256(b"original").hexdigest().upper()
            record = [{
                "relative_path": "game.exe",
                "original_path": str(destination / "game.exe"),
                "sha256": digest,
                "size": 8,
            }]
            absent = {"exists": False, "entries": []}
            restored = {"exists": True, "entries": [{
                "relative_path": "game.exe", "type": "file", "size": 8, "sha256": digest,
            }]}
            report = patcher._write_recovery_report(
                recovery, "install", record, backup_dir,
                destination_root=destination,
                destination_snapshot=absent,
                restored_snapshot=restored,
                destination_precondition=absent,
            )
            destination.mkdir()
            (destination / "foreign.bin").write_bytes(b"foreign")
            report_before = report.read_bytes()
            backup_before = backup.read_bytes()
            with self.assertRaises(Exception):
                patcher.recover_vv4_transaction(recovery)
            self.assertEqual(report.read_bytes(), report_before)
            self.assertEqual(backup.read_bytes(), backup_before)
            self.assertEqual((destination / "foreign.bin").read_bytes(), b"foreign")
            for item in destination.iterdir():
                item.unlink()
            destination.rmdir()
            patcher.recover_vv4_transaction(recovery)
            self.assertEqual((destination / "game.exe").read_bytes(), b"original")

    def test_snapshot_rejects_reparse_descendant_before_hash(self):
        import stat
        import tempfile
        from types import SimpleNamespace
        import vv_fun_patcher as patcher
        with tempfile.TemporaryDirectory(prefix="vv4hc-reparse-descendant-") as temp:
            root = Path(temp)
            child = root / "child"
            child.mkdir()
            (child / "data.bin").write_bytes(b"x")
            real_lstat = patcher.os.lstat
            def fake_lstat(path):
                info = real_lstat(path)
                if Path(path) == child:
                    return SimpleNamespace(
                        st_mode=stat.S_IFDIR | 0o755,
                        st_file_attributes=0x400,
                        st_dev=info.st_dev,
                        st_ino=info.st_ino,
                        st_size=info.st_size,
                    )
                return info
            with mock_patch.object(patcher.os, "lstat", side_effect=fake_lstat):
                with self.assertRaises(Exception):
                    patcher._capture_tree_snapshot(root)

    def test_complete_parent_chain_and_overlay_owner_preimage_gate(self):
        import importlib.util
        import vv_fun_patcher as patcher
        spec = importlib.util.spec_from_file_location("vv4hc_builder_overlay", ROOT / "scripts" / "build_vv4_full_heal_candidate.py")
        builder = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(builder)
        feature = patcher.FunPatch(json.loads(MANIFEST.read_text(encoding="utf-8")))
        parent = builder._render_parents()["collection_progression"]
        self.assertTrue(patcher._vv4_full_heal_overlay_allowed(
            feature=feature,
            current_owner="feature:vv4_full_heal_cure_all_candidate",
            prior_owner="feature:vv4_enable_origins_exclusive_features",
            prior_start=0x8960F,
            prior_end=0x89614,
            patch_mode="collection_progression",
            offset=0x8960F,
            before=bytes.fromhex("E941FEFFFF"),
            composed_sha256=__import__("hashlib").sha256(parent).hexdigest().upper(),
        ))
        for kwargs in (
            {"current_owner": "feature:wrong"},
            {"prior_owner": "feature:wrong"},
            {"patch_mode": "experimental_expanded_256"},
            {"before": b"\x00" * 5},
        ):
            args = {
                "feature": feature,
                "current_owner": "feature:vv4_full_heal_cure_all_candidate",
                "prior_owner": "feature:vv4_enable_origins_exclusive_features",
                "prior_start": 0x8960F,
                "prior_end": 0x89614,
                "patch_mode": "collection_progression",
                "offset": 0x8960F,
                "before": bytes.fromhex("E941FEFFFF"),
                "composed_sha256": __import__("hashlib").sha256(parent).hexdigest().upper(),
            }
            args.update(kwargs)
            self.assertFalse(patcher._vv4_full_heal_overlay_allowed(**args))

    def test_atomic_combined_removal_restores_exact_parent_exe_and_dll(self):
        import importlib.util
        import tempfile
        import vv_fun_patcher as patcher
        spec = importlib.util.spec_from_file_location("vv4hc_builder_remove", ROOT / "scripts" / "build_vv4_full_heal_candidate.py")
        builder = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(builder)
        feature = patcher.FunPatch(json.loads(MANIFEST.read_text(encoding="utf-8")))
        page, _ = builder.build_page()
        companion, _ = builder.build_resource_only_companion(builder.PARENT_DLL.read_bytes())
        for mode in ("collection_progression", "immediate_fixed"):
            with tempfile.TemporaryDirectory(prefix="vv4hc-publish-remove-") as temp:
                root = Path(temp)
                exe_name = "Virtual Villagers - The Tree of Life - Modded.exe"
                parent = builder._render_parents()[mode]
                candidate = builder._patch_parent(parent, page)
                (root / exe_name).write_bytes(candidate)
                (root / "VVFP Origins Icons.dll").write_bytes(companion)
                patcher.publish_vv4_full_heal_removal(root, exe_name, feature, mode)
                self.assertEqual(patcher.sha256(root / exe_name), builder.PARENT_HASHES[mode])
                self.assertEqual(patcher.sha256(root / "VVFP Origins Icons.dll"), builder.PARENT_DLL_SHA256)
                self.assertEqual(list(root.glob(".*stage-*")), [])

    def test_atomic_combined_removal_second_replace_failure_restores_both(self):
        import importlib.util
        import tempfile
        import vv_fun_patcher as patcher
        spec = importlib.util.spec_from_file_location("vv4hc_builder_remove_fail", ROOT / "scripts" / "build_vv4_full_heal_candidate.py")
        builder = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(builder)
        feature = patcher.FunPatch(json.loads(MANIFEST.read_text(encoding="utf-8")))
        page, _ = builder.build_page()
        companion, _ = builder.build_resource_only_companion(builder.PARENT_DLL.read_bytes())
        with tempfile.TemporaryDirectory(prefix="vv4hc-publish-remove-fail-") as temp:
            root = Path(temp)
            exe_name = "Virtual Villagers - The Tree of Life - Modded.exe"
            parent = builder._render_parents()["immediate_fixed"]
            (root / exe_name).write_bytes(builder._patch_parent(parent, page))
            (root / "VVFP Origins Icons.dll").write_bytes(companion)
            before_exe = (root / exe_name).read_bytes()
            before_dll = (root / "VVFP Origins Icons.dll").read_bytes()
            real_replace = patcher.os.replace
            state = {"replaces": 0, "failed": False}
            def fail_second(source, destination):
                state["replaces"] += 1
                if state["replaces"] == 2 and not state["failed"]:
                    state["failed"] = True
                    raise OSError("injected second replace failure")
                return real_replace(source, destination)
            with mock_patch.object(patcher.os, "replace", side_effect=fail_second):
                with self.assertRaises(Exception):
                    patcher.publish_vv4_full_heal_removal(root, exe_name, feature, "immediate_fixed")
            self.assertEqual((root / exe_name).read_bytes(), before_exe)
            self.assertEqual((root / "VVFP Origins Icons.dll").read_bytes(), before_dll)
            self.assertEqual(list(root.parent.glob(f".{root.name}.remove-stage-*")), [])
    def test_candidate_is_disabled_and_stock_only(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        artifact_map = json.loads(MAP.read_text(encoding="utf-8"))
        self.assertFalse(manifest["enabled"])
        self.assertTrue(manifest["catalog_hidden"])
        self.assertFalse(manifest["catalog_enabled"])
        self.assertEqual(manifest["supported_modes"], ["collection_progression", "immediate_fixed"])
        self.assertEqual(set(manifest["rejected_modes"]), {"experimental_expanded_256", "experimental_expanded_256_progression"})
        self.assertEqual(manifest["source"]["stock_sha256"], "6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220")
        self.assertEqual(artifact_map["parents"]["vv4fm_page_sha256"], "FD72C661B533117BF38D69E7EB855250A93927C831C265226930794C1EFDDB62")
        self.assertEqual(manifest["hook"]["hook_before_parent"], "E941FEFFFF")
        self.assertEqual(manifest["hook"]["hook_preserved_suffix"], "724C")
        self.assertEqual(manifest["hook"]["hook_after"], "E9EC792B00")
        self.assertEqual(manifest["hook"]["hook_length"], 5)
        self.assertEqual(manifest["transaction"]["deduction"]["receiver"], "0x4D6F88")
        self.assertEqual(manifest["transaction"]["deduction"]["call"], "0x41E300")
        self.assertEqual(manifest["native_operations"]["sickness_clear"]["people_cured_dword"], "[0x4D6DF0]")
        self.assertEqual(manifest["companion_files"][0]["sha256"], "165F327783DFECAB4C42DB28D6F926BCA46397F725F036BFC367BB659384C0AC")
        self.assertEqual(manifest["companion_files"][0]["source"], "generated:vv4_full_heal_companion")
        self.assertEqual(manifest["companion_files"][0]["preimage_sha256"], manifest["companion_files"][0]["restore_sha256"])
        self.assertEqual(manifest["companion_files"][0]["size"], 298496)
        self.assertEqual(manifest["companion_files"][0]["resource_directory_size"], "0x33800")
        self.assertEqual(manifest["companion_files"][0]["destination"], "VVFP Origins Icons.dll")
        self.assertEqual(manifest["companion_files"][0]["artwork_resource_id"], 110)
        self.assertEqual(manifest["companion_files"][0]["artwork_sha256"], "83552374DFD7AC1AACC57D371C01C26BA1A438ADF34B904609A72165EB73C5A0")
        self.assertEqual(manifest["hook"]["helper_length"], 2053)
        self.assertEqual(manifest["hook"]["helper_sha256"], "F4271D44AB481D1441EA7D8D297AC346FCF0F2840EE9869B90EE1E875A4B403F")
        self.assertEqual(manifest["hook"]["page_sha256"], "EC7E987845C3081C435CED913CCEE951CC67B0E766FAAB363D313D0B5874A739")
        self.assertEqual(artifact_map["companion"]["sha256"], manifest["companion_files"][0]["sha256"])
        self.assertIn("RT_DIALOG 201/203", artifact_map["companion"]["resource_contract"])
        self.assertEqual(artifact_map["ownership"]["exe_hook"]["command5_continuation"], "0x4895D9")
        self.assertEqual(artifact_map["ownership"]["exe_hook"]["non_command5_continuation"], "0x489455")
        self.assertEqual(artifact_map["ownership"]["companion"]["destination"], "VVFP Origins Icons.dll")
        self.assertEqual(manifest["hook"]["shim_bytes"], "83F8050F84F7000000E94784D4FF")
        self.assertTrue(manifest["hook"]["unknown_until_recertified"])

    def test_dry_run_counts_overlap_and_uses_exact_150_resolutions(self):
        records = [{"active": 0, "status": 0, "health": 0, "sick": 0} for _ in range(150)]
        records[3] = {"active": 1, "status": 0, "health": 50, "sick": 1}
        records[8] = {"active": 1, "status": 0, "health": 100, "sick": 1}
        records[11] = {"active": 1, "status": 0, "health": 70, "sick": 0}
        records[12] = {"active": 1, "status": 1, "health": 20, "sick": 1}
        calls = []
        result = dry_run(lambda i: calls.append(i) or records[i])
        self.assertEqual(calls, list(range(150)))
        self.assertEqual((result.sick_count, result.partial_count), (2, 2))
        self.assertEqual(len(result.states), 150)
        self.assertTrue(any(s.index == 8 and s.health == 100 and s.sick for s in result.states))

    def test_noop_cancel_insufficient_and_success_messages_are_no_charge(self):
        records = [{"active": 1, "status": 0, "health": 100, "sick": 0} for _ in range(150)]
        noop = plan_transaction(lambda i: records[i], 1, True, lambda: (lambda i: records[i], 1))
        self.assertEqual(noop.status, "no_change")
        self.assertIn(NO_DEDUCTION, noop.message)
        records[0]["health"] = 80
        cancel = plan_transaction(lambda i: records[i], 1_000_000, False, lambda: (lambda i: records[i], 1_000_000))
        self.assertEqual(cancel.status, "cancel")
        self.assertIn(NO_DEDUCTION, cancel.message)
        insufficient = plan_transaction(lambda i: records[i], 0, True, lambda: (lambda i: records[i], 0))
        self.assertEqual(insufficient.status, "insufficient")
        self.assertIn(NO_DEDUCTION, insufficient.message)
        self.assertIn("Full Heal / Cure All cured 2", success_message(2, 3))
        self.assertIn(NO_DEDUCTION, failure_message(1, 2, "postverify"))

    def test_reacquisition_and_funds_follow_confirmation(self):
        records = [{"active": 1, "status": 0, "health": 100, "sick": 0} for _ in range(150)]
        records[1]["health"] = 50
        phases = []
        def reacquire():
            phases.append("reacquire")
            return (lambda i: records[i], 30_000)
        result = plan_transaction(lambda i: records[i], 30_000, True, reacquire)
        self.assertEqual(result.status, "commit")
        self.assertEqual(phases, ["reacquire"])
        self.assertEqual(result.deduction, 0)

    def test_apply_uses_native_callbacks_once_and_never_touches_health_100(self):
        records = [{"active": 1, "status": 0, "health": 100, "sick": 0} for _ in range(150)]
        records[2].update(health=40, sick=1)
        records[4].update(health=100, sick=1)
        plan = plan_transaction(lambda i: records[i], 30_000, True, lambda: (lambda i: records[i], 30_000))
        writes, clears, cured, deductions = [], [], [], []
        def set_health(index, reason, value):
            writes.append((index, reason, value))
            records[index]["health"] = value
            return True
        def clear(index):
            clears.append(index)
            records[index]["sick"] = 0
            return True
        result = apply_transaction(lambda i: records[i], plan, set_health, clear, lambda: cured.append(1), lambda receiver, amount, call: deductions.append((receiver, amount, call)))
        self.assertEqual(result.status, "success")
        self.assertEqual(writes, [(2, -1, 100)])
        self.assertEqual(clears, [2, 4])
        self.assertEqual(len(cured), 2)
        self.assertEqual(deductions, [(TECH_DEDUCTION_RECEIVER, -30_000, TECH_DEDUCTION_CALL)])

    def test_partial_failure_is_no_charge_and_reports_actual_counts(self):
        records = [{"active": 1, "status": 0, "health": 100, "sick": 0} for _ in range(150)]
        records[0].update(health=20, sick=1)
        plan = plan_transaction(lambda i: records[i], 30_000, True, lambda: (lambda i: records[i], 30_000))
        result = apply_transaction(lambda i: records[i], plan, lambda *_: False, lambda *_: False, lambda: None, lambda *_: (_ for _ in ()).throw(AssertionError("deduction")))
        self.assertEqual(result.status, "partial")
        self.assertIn(NO_DEDUCTION, result.message)

    def test_postverify_requires_predicted_counts_before_deduction(self):
        records = [{"active": 1, "status": 0, "health": 100, "sick": 0} for _ in range(150)]
        records[0].update(health=40)
        records[1].update(health=50)
        plan = plan_transaction(lambda i: records[i], 30_000, True, lambda: (lambda i: records[i], 30_000))
        calls = []

        def set_health(index, reason, value):
            records[index]["health"] = value
            if index == 0:
                # A later native-side change removes the second planned target.
                records[1]["health"] = 100
            return True

        result = apply_transaction(lambda i: records[i], plan, set_health, lambda *_: True, lambda: None, calls.append)
        self.assertEqual(result.status, "partial")
        self.assertEqual(calls, [])
        self.assertIn(NO_DEDUCTION, result.message)


    def test_structural_companion_repack_is_deterministic_and_non_resource_stable(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "vv4hc_builder", ROOT / "scripts" / "build_vv4_full_heal_candidate.py"
        )
        builder = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(builder)
        base = builder.PARENT_DLL.read_bytes()
        candidate, digest = builder.build_resource_only_companion(base)
        self.assertEqual(digest, "165F327783DFECAB4C42DB28D6F926BCA46397F725F036BFC367BB659384C0AC")
        import pefile
        pe = pefile.PE(data=candidate)
        icon_type = next(x for x in pe.DIRECTORY_ENTRY_RESOURCE.entries if x.id == 14)
        self.assertIn(110, [x.id for x in icon_type.directory.entries])
        raw, size, _, base_leaves = builder._dll_resource_leaves(base)
        _, _, _, cand_leaves = builder._dll_resource_leaves(candidate)
        expected_icons = {
            46: "68FED72757B4A8A28F69ABFB7A9ED4133647676EAE7665F44BA6D8931929DD23",
            47: "7B599B3876B44BECA595FCE3ED7DFC984C99E014A057F6ED0BA25CA507F49B73",
            48: "1D4C17E4E54C623485E9D7D8FE613D6D67F5511521256BBA8572B9EC76D70634",
            49: "0122D77CF881F79BFD488BE98E917AB76BF2049AE5AF3CC44228AF3A35D70595",
        }
        for ident, expected_hash in expected_icons.items():
            blob = next(x["blob"] for x in cand_leaves if x["path"] == (3, ident, 1033))
            self.assertEqual(builder.sha(blob), expected_hash)
        for ident, expected in ((201, 46), (203, 36)):
            blob = next(x["blob"] for x in cand_leaves if x["path"] == (5, ident, 1033))
            self.assertEqual(struct.unpack_from("<H", blob, 16)[0], expected)
            text = blob.decode("utf-16le", errors="ignore")
            self.assertIn("Origins Upgrades", text)
            self.assertIn("Full Heal / Cure All", text)
            self.assertIn("30,000 tech points", text)
            self.assertIn("Buy", text)
            self.assertIn(struct.pack("<H", 1005), blob)
            self.assertLess(
                blob.find("Full Heal / Cure All".encode("utf-16le")),
                blob.find("All Villagers".encode("utf-16le")),
            )
        # The structural repack grows .rsrc by the certified aligned span.
        # Only derived resource/relocation layout fields and checksum change;
        # all other headers and all bytes outside the resource section remain
        # byte-identical (with the relocated tail compared at its new offset).
        if len(candidate) != len(base):
            self.assertEqual(len(candidate), 298496)
            delta = len(candidate) - len(base)
            pe = struct.unpack_from("<I", base, 0x3C)[0]
            table = pe + 24 + struct.unpack_from("<H", base, pe + 20)[0]
            count = struct.unpack_from("<H", base, pe + 6)[0]
            rsrc_header = reloc_header = None
            for index in range(count):
                off = table + index * 40
                name = base[off:off + 8].rstrip(b"\0")
                if name == b".rsrc":
                    rsrc_header = off
                elif name == b".reloc":
                    reloc_header = off
            self.assertIsNotNone(rsrc_header)
            self.assertIsNotNone(reloc_header)
            normalized_candidate = bytearray(candidate[:raw])
            normalized_base = bytearray(base[:raw])
            # The structural move is allowed to change only the derived PE
            # layout fields: .rsrc virtual/raw size, .reloc RVA/raw pointer,
            # SizeOfImage, relocation directory RVA, and checksum.
            normalized_candidate[rsrc_header + 8:rsrc_header + 12] = normalized_base[rsrc_header + 8:rsrc_header + 12]
            normalized_candidate[rsrc_header + 16:rsrc_header + 20] = normalized_base[rsrc_header + 16:rsrc_header + 20]
            normalized_candidate[0x18C:0x190] = normalized_base[0x18C:0x190]
            normalized_candidate[reloc_header + 12:reloc_header + 16] = normalized_base[reloc_header + 12:reloc_header + 16]
            normalized_candidate[reloc_header + 20:reloc_header + 24] = normalized_base[reloc_header + 20:reloc_header + 24]
            normalized_candidate[pe + 0x50:pe + 0x54] = normalized_base[pe + 0x50:pe + 0x54]
            normalized_candidate[pe + 24 + 96 + 5 * 8:pe + 24 + 96 + 5 * 8 + 4] = normalized_base[pe + 24 + 96 + 5 * 8:pe + 24 + 96 + 5 * 8 + 4]
            normalized_candidate[pe + 24 + 64:pe + 24 + 68] = normalized_base[pe + 24 + 64:pe + 24 + 68]
            self.assertEqual(normalized_candidate, normalized_base)
            self.assertEqual(candidate[raw + size + delta :], base[raw + size :])
        else:
            self.assertEqual(candidate[:raw], base[:raw])
            self.assertEqual(candidate[raw + size :], base[raw + size :])
        self.assertEqual(
            next(x["blob"] for x in base_leaves if x["path"] == (5, 202, 1033)),
            next(x["blob"] for x in cand_leaves if x["path"] == (5, 202, 1033)),
        )
        pe_off = struct.unpack_from("<I", candidate, 0x3C)[0]
        sec_table = pe_off + 24 + struct.unpack_from("<H", candidate, pe_off + 20)[0]
        sections = {
            candidate[sec_table + i * 40:sec_table + i * 40 + 8].rstrip(b"\0").decode(): sec_table + i * 40
            for i in range(struct.unpack_from("<H", candidate, pe_off + 6)[0])
        }
        self.assertEqual(struct.unpack_from("<I", candidate, sections[".rsrc"] + 8)[0], 0x33800)
        self.assertEqual(struct.unpack_from("<I", candidate, sections[".rsrc"] + 12)[0], 0x17000)
        self.assertEqual(struct.unpack_from("<I", candidate, sections[".rsrc"] + 16)[0], 0x33800)
        self.assertEqual(struct.unpack_from("<I", candidate, sections[".reloc"] + 12)[0], 0x4B000)
        self.assertEqual(struct.unpack_from("<I", candidate, sections[".reloc"] + 20)[0], 0x47E00)
        self.assertEqual(struct.unpack_from("<I", candidate, pe_off + 0x50)[0], 0x4C000)
        self.assertEqual(struct.unpack_from("<I", candidate, 0x18C)[0], 0x33800)

    def test_emitted_page_decodes_contract_and_stack_intervals(self):
        import hashlib
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "vv4hc_builder_page", ROOT / "scripts" / "build_vv4_full_heal_candidate.py"
        )
        builder = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(builder)
        page, meta = builder.build_page()
        self.assertEqual(len(page), 0x1000)
        self.assertEqual(meta["helper_length"], 2053)
        self.assertEqual(
            hashlib.sha256(page[0x100:0x100 + meta["helper_length"]]).hexdigest().upper(),
            "F4271D44AB481D1441EA7D8D297AC346FCF0F2840EE9869B90EE1E875A4B403F",
        )
        self.assertEqual(hashlib.sha256(page).hexdigest().upper(), "EC7E987845C3081C435CED913CCEE951CC67B0E766FAAB363D313D0B5874A739")
        body = page[0x100:0x100 + meta["helper_length"]]
        self.assertNotIn(b"\xE9\x00\x10\x74\x00", body)  # no synthetic string-target jump
        self.assertNotIn(struct.pack("<I", 0x50EDE8), body)
        # Native addresses and ABI calls must be present in the actual
        # emitted helper, not only in the model metadata.  Relative calls are
        # checked by their decoded destinations rather than raw immediates.
        calls = {
            int(insn.op_str, 16)
            for insn in builder.Cs(builder.CS_ARCH_X86, builder.CS_MODE_32).disasm(body, builder.ENTRY_VA)
            if insn.mnemonic == "call" and insn.op_str.startswith("0x")
        }
        for address in (0x466040, 0x46AF00, 0x41E300):
            self.assertIn(address, calls)
        for address in (0x50E568, 0x4D6F88, 0x4D6DF0):
            self.assertIn(struct.pack("<I", address), body)
        self.assertIn(b"\x83\xF8\x64", body)  # exact health==100 checks
        # Scalar locals and the 0x960-byte snapshot are disjoint by contract.
        self.assertEqual(meta["stack_map"]["snapshot"], "[ebp-0xA00..ebp-0xA1] (0x960 bytes; 150 independent 16-byte slots: pointer, health, bits, active/status, sickness)")
        self.assertEqual(meta["stack_map"]["format_buffer"], "[ebp-0x1100..ebp-0xF01] (512 bytes)")
        self.assertIn("0x1200", meta["stack_map"]["frame_allocation"])
        self.assertIn("all 16 bytes remain zero", meta["stack_map"]["ineligible_slot"])

    def test_generated_page_removal_round_trips_both_parent_modes(self):
        import importlib.util
        import sys
        import tempfile
        sys.path.insert(0, str(ROOT / "src"))
        import vv_fun_patcher as patcher
        spec = importlib.util.spec_from_file_location(
            "vv4hc_builder_remove", ROOT / "scripts" / "build_vv4_full_heal_candidate.py"
        )
        builder = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(builder)
        feature = patcher.FunPatch(json.loads(MANIFEST.read_text(encoding="utf-8")))
        page, _ = builder.build_page()
        for mode, parent in builder._render_parents().items():
            candidate = bytearray(builder._patch_parent(parent, page))
            with tempfile.TemporaryDirectory(prefix="vv4hc-remove-") as temp:
                folder = Path(temp)
                companion, _ = builder.build_resource_only_companion(builder.PARENT_DLL.read_bytes())
                (folder / "VVFP Origins Icons.dll").write_bytes(companion)
                patcher._remove_feature_bytes(candidate, feature, mode, output_folder=folder)
                self.assertEqual(bytes(candidate), parent)
                self.assertEqual(patcher.sha256(folder / "VVFP Origins Icons.dll"), builder.PARENT_DLL_SHA256)

    def test_full_heal_dependency_identity_is_active_catalog_id(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        artifact_map = json.loads(MAP.read_text(encoding="utf-8"))
        expected = [
            "vv4_complete_scales_golden_fish",
            "vv4_enable_origins_exclusive_features",
            "vv4_full_mastery_all_stage_a_candidate",
            "vv4_write_village_statistics",
        ]
        self.assertEqual(manifest["dependencies"], expected)
        self.assertEqual(artifact_map["dependencies"], expected)

    def test_generated_page_hash_failure_is_atomic_for_exe_and_companion(self):
        import importlib.util
        import sys
        import tempfile
        import vv_fun_patcher as patcher
        spec = importlib.util.spec_from_file_location(
            "vv4hc_builder_corrupt", ROOT / "scripts" / "build_vv4_full_heal_candidate.py"
        )
        builder = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(builder)
        feature_raw = json.loads(MANIFEST.read_text(encoding="utf-8"))
        feature_raw["hook"]["page_sha256"] = "00" * 32
        feature = patcher.FunPatch(feature_raw)
        page, _ = builder.build_page()
        candidate = bytearray(builder._patch_parent(builder._render_parents()["collection_progression"], page))
        before_exe = bytes(candidate)
        with tempfile.TemporaryDirectory(prefix="vv4hc-corrupt-") as temp:
            folder = Path(temp)
            companion, _ = builder.build_resource_only_companion(builder.PARENT_DLL.read_bytes())
            (folder / "VVFP Origins Icons.dll").write_bytes(companion)
            before_dll = (folder / "VVFP Origins Icons.dll").read_bytes()
            with self.assertRaises(patcher.PatcherError):
                patcher._remove_feature_bytes(candidate, feature, "collection_progression", output_folder=folder)
            self.assertEqual(bytes(candidate), before_exe)
            self.assertEqual((folder / "VVFP Origins Icons.dll").read_bytes(), before_dll)

    def test_emitted_parent_has_exact_hook_suffix_and_uninstall_identity(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "vv4hc_builder_parent", ROOT / "scripts" / "build_vv4_full_heal_candidate.py"
        )
        builder = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(builder)
        page, _ = builder.build_page()
        parent = builder._render_parents()["collection_progression"]
        candidate = builder._patch_parent(parent, page)
        self.assertEqual(parent[builder.HOOK_RAW:builder.HOOK_RAW + 5], bytes.fromhex("E941FEFFFF"))
        self.assertEqual(parent[builder.HOOK_RAW + 5:builder.HOOK_RAW + 7], b"\x72\x4C")
        self.assertEqual(candidate[builder.HOOK_RAW:builder.HOOK_RAW + 5], bytes.fromhex("E9EC792B00"))
        self.assertEqual(candidate[builder.HOOK_RAW + 5:builder.HOOK_RAW + 7], b"\x72\x4C")
        self.assertEqual(builder.sha(parent), "D0F90C4666A1E2189044B6F093692E4B56C8F379BC6A4953BBB9B74D997A8092")
        self.assertEqual(builder.sha(candidate), "26E82AF29118312978A94225B3D3094511B1765C44185F416F600272A7DB80B9")

    def test_d322_lineage_proof_is_exact_and_full_mastery_boundary_is_frozen(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        proof = manifest["lineage_proof"]
        self.assertEqual(proof["source"], "D322 repository-only production resolver")
        self.assertEqual(proof["old_parents"], {
            "collection_progression": "CEBF0BC813059A13131CF75E4ECE11C8CCEE460CC98FB16BD87B03F5C20DB86B",
            "immediate_fixed": "6070D3244567815E8880168AEDCB9FF0E43F6720095AE67628089D492DA40133",
        })
        self.assertEqual(proof["new_parents"], {
            "collection_progression": "D0F90C4666A1E2189044B6F093692E4B56C8F379BC6A4953BBB9B74D997A8092",
            "immediate_fixed": "F803918BE5B356F4A3C6D12A5098594E904CDE00C87E1D14901F9CCE5107AECD",
        })
        self.assertEqual(proof["unchanged_boundary"]["raw"], "0x89288")
        self.assertEqual(proof["checksums"], {
            "collection_progression": {"old": "3B1B0F00", "new": "B2920E00"},
            "immediate_fixed": {"old": "64B40E00", "new": "DA2B0F00"},
        })
        self.assertTrue(proof["range_end_inclusive"])
        self.assertEqual(proof["protected_range_scope"], "new_parent_vs_old_parent")
        self.assertIn("0x8960F..0x89613", proof["candidate_overlay_exception"])
        self.assertEqual(proof["allowed_diff_ranges"], [
            {"raw_start": "0x158", "raw_end_exclusive": "0x15C", "purpose": "PE checksum"},
            {"raw_start": "0x664DC", "raw_end_exclusive": "0x664E2", "before": "E9A22D020090", "after": "885EFD385EFD", "purpose": "burial detour withdrawal"},
            {"raw_start": "0x89283", "raw_end_exclusive": "0x89288", "after": "0000000000", "purpose": "owned burial wrapper withdrawal"},
            {"raw_start": "0x89289", "raw_end_exclusive": "0x89294", "after": "0000000000000000000000", "purpose": "owned burial wrapper withdrawal"},
        ])
        self.assertIn({"raw": "0x89373..0x89FFF", "sha256": "DB803A81280A38F156BF24EB51135935D71CBE0E6C2BE2BE81D0A08BD5190B7C33D"}, proof["protected_full_mastery_ranges"])

    def test_d322_old_parent_hashes_reconstruct_from_only_allowed_deltas(self):
        import hashlib
        import importlib.util
        import vv_fun_patcher as patcher
        spec = importlib.util.spec_from_file_location(
            "vv4hc_builder_d322_reconstruct", ROOT / "scripts" / "build_vv4_full_heal_candidate.py"
        )
        builder = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(builder)
        stock = ROOT / "research/stock-executables/Virtual Villagers - The Tree of Life.exe"
        build = patcher.identify(stock)
        records = patcher.load_fun_patches()
        by_name = {record.name: record.id for record in records if record.game_id == "vv4"}
        ids = [by_name[name] for name in (
            "Complete Fish Scales = Golden Fish in Nets",
            "Enable Origins-Exclusive Features",
            "Grant Full Mastery to All Villagers",
            "Write Village Statistics to Text File",
        )]
        proof = json.loads(MANIFEST.read_text(encoding="utf-8"))["lineage_proof"]
        for mode, expected_old in proof["old_parents"].items():
            rendered, _ = patcher.render_patched_bytes(stock, build, mode, ids)
            reconstructed = bytearray(rendered)
            reconstructed[0x158:0x15C] = bytes.fromhex(proof["checksums"][mode]["old"])
            reconstructed[0x664DC:0x664E2] = bytes.fromhex("E9A22D020090")
            reconstructed[0x89283:0x89288] = bytes.fromhex("FF05FC6D4D")
            reconstructed[0x89289:0x89294] = bytes.fromhex("885EFD385EFDE94ED2FDFF")
            self.assertEqual(hashlib.sha256(reconstructed).hexdigest().upper(), expected_old)

    def test_d322_parent_outputs_match_production_resolver_when_available(self):
        import hashlib
        import tempfile
        import vv_fun_patcher as patcher
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "vv4hc_builder_d322", ROOT / "scripts" / "build_vv4_full_heal_candidate.py"
        )
        builder = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(builder)
        stock = ROOT / "research/stock-executables/Virtual Villagers - The Tree of Life.exe"
        build = patcher.identify(stock)
        records = patcher.load_fun_patches()
        by_name = {record.name: record.id for record in records if record.game_id == "vv4"}
        ids = [by_name[name] for name in (
            "Complete Fish Scales = Golden Fish in Nets",
            "Enable Origins-Exclusive Features",
            "Grant Full Mastery to All Villagers",
            "Write Village Statistics to Text File",
        )]
        for mode, expected in builder.PARENT_HASHES.items():
            rendered, _ = patcher.render_patched_bytes(stock, build, mode, ids)
            self.assertEqual(hashlib.sha256(bytes(rendered)).hexdigest().upper(), expected)

    def test_classifier_reloads_health_and_dependency_message_uses_stdcall(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "vv4hc_builder_classifier", ROOT / "scripts" / "build_vv4_full_heal_candidate.py"
        )
        builder = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(builder)
        page, meta = builder.build_page()
        body = page[0x100:0x100 + meta["helper_length"]]
        insns = list(builder.Cs(builder.CS_ARCH_X86, builder.CS_MODE_32).disasm(body, builder.ENTRY_VA))
        for index, insn in enumerate(insns[:-1]):
            if insn.mnemonic == "mov" and "byte ptr [esi + 0x1c48]" in insn.op_str:
                window = insns[index + 1:index + 5]
                cmp_positions = [i for i, item in enumerate(window) if item.mnemonic == "cmp" and item.op_str == "eax, 0x64"]
                if cmp_positions:
                    self.assertTrue(any("dword ptr [esi + 0x1c40]" in item.op_str for item in window[:cmp_positions[0]]), insn)
        reload_compare_pairs = [
            index for index, insn in enumerate(insns[1:], 1)
            if insn.mnemonic == "cmp" and insn.op_str == "eax, 0x64"
            and insns[index - 1].mnemonic == "mov"
            and "dword ptr [esi + 0x1c40]" in insns[index - 1].op_str
        ]
        self.assertGreaterEqual(len(reload_compare_pairs), 2)
        message_calls = [
            index for index, insn in enumerate(insns[:-1])
            if insn.mnemonic == "call" and insn.op_str == "dword ptr [ebp - 0x10]"
        ]
        self.assertTrue(any(insns[index + 1].mnemonic == "add" and insns[index + 1].op_str == "esp, 0x1200" for index in message_calls))

    def test_append_and_companion_metadata_are_operationally_complete(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        layouts = manifest["pe_append_transaction"]["layouts"]
        self.assertEqual(set(layouts), {"collection_progression", "immediate_fixed"})
        for layout in layouts.values():
            self.assertEqual(layout["original_file_size"], "0xE5000")
            self.assertEqual(layout["append_offset"], "0xE5000")
            self.assertEqual(layout["append_source"], "generated:vv4_full_heal_page")
            self.assertEqual(len(layout["header_patches"]), 3)
        companion = manifest["companion_files"][0]
        self.assertEqual(companion["source"], "generated:vv4_full_heal_companion")
        self.assertEqual(companion["restore_source"], companion["parent"])
        self.assertEqual(companion["preimage_sha256"], companion["restore_sha256"])
        self.assertEqual(json.loads(MAP.read_text(encoding="utf-8"))["companion_resource_directory_size"], "0x33800")

    def test_emitted_dialog_command5_row_has_native_order_and_geometry(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "vv4hc_builder_dialog", ROOT / "scripts" / "build_vv4_full_heal_candidate.py"
        )
        builder = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(builder)
        candidate, _ = builder.build_resource_only_companion(builder.PARENT_DLL.read_bytes())
        _, _, _, leaves = builder._dll_resource_leaves(candidate)

        def parse(blob, expected_count):
            def skip(pos):
                first = struct.unpack_from("<H", blob, pos)[0]
                if first == 0:
                    return pos + 2, None
                if first == 0xFFFF:
                    return pos + 4, struct.unpack_from("<H", blob, pos + 2)[0]
                start = pos
                pos += 2
                while struct.unpack_from("<H", blob, pos)[0] != 0:
                    pos += 2
                raw = blob[start:pos + 2]
                return pos + 2, raw[:-2].decode("utf-16le")
            pos = 26
            for _ in range(3):
                pos, _ = skip(pos)
            pos += 6
            pos, _ = skip(pos)  # variable UTF-16 typeface
            pos = (pos + 3) & ~3
            rows = []
            for _ in range(expected_count):
                pos = (pos + 3) & ~3
                y = struct.unpack_from("<h", blob, pos + 14)[0]
                ident = struct.unpack_from("<I", blob, pos + 20)[0]
                pos += 24
                pos, cls = skip(pos)
                pos, title = skip(pos)
                words = struct.unpack_from("<H", blob, pos)[0]
                pos = (pos + 2 + words * 2 + 3) & ~3
                rows.append((cls, title, ident, y))
            self.assertEqual(pos, len(blob))
            return rows

        for ident, expected_count in ((201, 46), (203, 36)):
            blob = next(item["blob"] for item in leaves if item["path"] == (5, ident, 1033))
            rows = parse(blob, expected_count)
            self.assertEqual(len(rows), expected_count)
            self.assertEqual(rows[25:30], [
                (130, 110, 0xFFFFFFFF, 168),
                (130, 109, 1105, 180),
                (130, "Full Heal / Cure All", 0xFFFFFFFF, 170),
                (130, "30,000 tech points", 0xFFFFFFFF, 182),
                (128, "Buy", 1005, 171),
            ])

if __name__ == "__main__":
    unittest.main()
