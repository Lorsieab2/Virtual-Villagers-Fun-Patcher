from __future__ import annotations

import copy
import datetime as dt
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import capture_expanded_runtime_evidence as MODULE


ROOT = Path(__file__).resolve().parents[1]
SOURCE_COMMIT = "c4f7215" + "0" * 33
FIXED_TIME = dt.datetime(2026, 8, 7, 12, 0, 0, tzinfo=dt.timezone.utc)


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _fixture_contract_and_folder(root: Path) -> tuple[dict[str, object], dict[str, str]]:
    contract = copy.deepcopy(MODULE._load_contract())
    game = contract["games"]["vv4"]
    payloads = {
        "stock_executable": ("Virtual Villagers - The Tree of Life.exe", b"fixture-stock"),
        "expanded_executable_immediate": ("expanded-immediate.exe", b"fixture-immediate"),
        "expanded_executable_progression": ("expanded-progression.exe", b"fixture-progression"),
        "companion_dll": ("VVFP Origins Icons.dll", b"fixture-dll"),
        "runtime_inventory": ("runtime-inventory.json", b"{}"),
        "checksum_list": ("SHA256SUMS.txt", b"fixture-checksums"),
        "patch_log": ("candidate.patch-log.json", b"fixture-patch-log"),
        "transparency_log": ("VVFP Transparency Log.txt", b"fixture-transparency"),
        "player_readme": ("README.txt", b"fixture-readme"),
    }
    role_paths: dict[str, str] = {}
    for role, (name, data) in payloads.items():
        (root / name).write_bytes(data)
        role_paths[role] = name
    game["stock_fingerprint"].update({"size": len(payloads["stock_executable"][1]), "sha256": _digest(payloads["stock_executable"][1])})
    game["expanded_fingerprints"]["experimental_expanded_256"].update({"size": len(payloads["expanded_executable_immediate"][1]), "sha256": _digest(payloads["expanded_executable_immediate"][1])})
    game["expanded_fingerprints"]["experimental_expanded_256_progression"].update({"size": len(payloads["expanded_executable_progression"][1]), "sha256": _digest(payloads["expanded_executable_progression"][1])})
    game["required_folder_inventory"]["required_dlls"][0]["sha256"] = _digest(payloads["companion_dll"][1])
    return contract, role_paths


def _modded_save(root: Path) -> Path:
    save_root = root / "Fixture Village - Modded"
    save_root.mkdir()
    (save_root / "state.sav").write_bytes(b"initial")
    return save_root


class ExpandedRuntimeCaptureHarnessTests(unittest.TestCase):
    def test_dry_run_is_plan_only_and_pins_all_checkpoints(self) -> None:
        result = MODULE._dry_run("vv5", "experimental_expanded_256_progression")
        self.assertEqual(result["status"], "dry_run")
        self.assertFalse(result["launch_automatic"])
        self.assertEqual(
            [item["id"] for item in result["checkpoints"]],
            [
                "stock_import_conversion",
                "expanded_save_reload",
                "offline_catchup",
                "failed_load_nonmutation",
                "save_rotation",
                "late_record_boundaries",
                "current_origins_behavior",
                "relocation_proof",
                "player_runtime_receipts",
            ],
        )
        self.assertEqual(result["checkpoints"][5]["assertions"]["indices"], [149, 150, 254, 255])
        self.assertFalse(result["publication"]["eligible"])

    def test_role_map_refuses_partial_absolute_duplicate_and_parent_paths(self) -> None:
        with self.assertRaisesRegex(MODULE.CaptureError, "all nine required roles"):
            MODULE._parse_roles(["stock_executable=stock.exe"])
        with self.assertRaisesRegex(MODULE.CaptureError, "must be relative"):
            MODULE._parse_roles(["stock_executable=C:/stock.exe"])
        values = [f"{role}={role}.bin" for role in MODULE.REQUIRED_ROLES]
        values[-1] = "player_readme=../README.txt"
        with self.assertRaisesRegex(MODULE.CaptureError, "may not traverse"):
            MODULE._parse_roles(values)
        values[-1] = "player_readme=stock_executable.bin"
        with self.assertRaisesRegex(MODULE.CaptureError, "point to one file"):
            MODULE._parse_roles(values)

    def test_non_modded_save_is_rejected_before_tree_access(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            invalid = Path(temporary) / "Village - Stock"
            invalid.mkdir()
            with mock.patch.object(MODULE, "_safe_root", side_effect=AssertionError("tree access")):
                with self.assertRaisesRegex(MODULE.CaptureError, r"authorized '\* - Modded'"):
                    MODULE.snapshot_save_tree(invalid)

    def test_reparse_entry_stops_no_follow_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "Village - Modded"
            root.mkdir()
            blocked = root / "blocked"
            blocked.mkdir()
            with mock.patch.object(MODULE, "_is_reparse_point", side_effect=lambda path: path.name == "blocked"):
                with self.assertRaisesRegex(MODULE.CaptureError, "reparse point rejected"):
                    MODULE.snapshot_save_tree(root)

    def test_preflight_requires_exact_identities_and_records_extra_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / "VV4 Complete Folder"
            folder.mkdir()
            contract, roles = _fixture_contract_and_folder(folder)
            (folder / "supporting-runtime.dat").write_bytes(b"support")
            result = MODULE._preflight_folder(contract, "vv4", folder, roles)
            self.assertTrue(result["full_folder_inventory"]["complete"])
            self.assertTrue(result["full_folder_inventory"]["no_unrecorded_files"])
            self.assertEqual(result["full_folder_inventory"]["physical_file_count"], 10)
            self.assertEqual(result["artifact_inventory"]["schema_version"], "vvfp.runtime_artifact_inventory.v1")
            self.assertEqual(result["relocation_proof"]["count"], 13)
            self.assertEqual(len(result["relocation_proof"]["rows"]), 13)

    def test_preflight_refuses_partial_folder_even_when_files_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / "VV4 Partial Folder"
            folder.mkdir()
            contract, roles = _fixture_contract_and_folder(folder)
            roles.pop("player_readme")
            with self.assertRaisesRegex(MODULE.CaptureError, "all nine required roles"):
                MODULE._preflight_folder(contract, "vv4", folder, roles)

    def test_capture_requires_all_interactive_observations_and_emits_unsigned_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folder = root / "VV4 Complete Folder"
            folder.mkdir()
            contract, roles = _fixture_contract_and_folder(folder)
            save_root = _modded_save(root)
            changed_stages = {"stock_import_conversion", "offline_catchup", "save_rotation"}

            def prompt(message: str) -> str:
                checkpoint = message.split("OBSERVED:", 1)[1].split(" ", 1)[0]
                if checkpoint in changed_stages:
                    path = save_root / "state.sav"
                    path.write_bytes(path.read_bytes() + checkpoint.encode("ascii"))
                return f"OBSERVED:{checkpoint}"

            packet = MODULE.capture_candidate(
                contract=contract,
                game_id="vv4",
                mode="experimental_expanded_256",
                folder=folder,
                save_root=save_root,
                role_paths=roles,
                source_commit=SOURCE_COMMIT,
                prompt=prompt,
                clock=lambda: FIXED_TIME,
                operator="player",
            )
            self.assertEqual(packet["status"], "unsigned_candidate")
            self.assertFalse(packet["authentication"]["authenticated"])
            self.assertFalse(packet["publication"]["eligible"])
            self.assertEqual(packet["runtime_evidence"]["gates"]["relocation_receipt"]["assertions"]["count"], 13)
            self.assertEqual(len(packet["runtime_evidence"]["gates"]["relocation_receipt"]["assertions"]["row_sha256"]), 13)
            failed = next(item for item in packet["checkpoints"] if item["id"] == "failed_load_nonmutation")
            self.assertEqual(failed["save_before"]["canonical_sha256"], failed["save_after"]["canonical_sha256"])
            self.assertEqual(packet["integrity"]["canonical_sha256"], MODULE.canonical_sha256(packet, remove_key="canonical_sha256"))
            output = root / "unsigned-candidate.json"
            MODULE._write_canonical(output, packet)
            self.assertEqual(output.read_bytes(), MODULE._canonical_bytes(packet) + b"\n")
            with self.assertRaisesRegex(MODULE.CaptureError, "refusing to overwrite"):
                MODULE._write_canonical(output, packet)

    def test_capture_stops_when_failed_load_mutates_save_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folder = root / "VV4 Complete Folder"
            folder.mkdir()
            contract, roles = _fixture_contract_and_folder(folder)
            save_root = _modded_save(root)

            def prompt(message: str) -> str:
                checkpoint = message.split("OBSERVED:", 1)[1].split(" ", 1)[0]
                if checkpoint in {"stock_import_conversion", "offline_catchup", "save_rotation", "failed_load_nonmutation"}:
                    path = save_root / "state.sav"
                    path.write_bytes(path.read_bytes() + b"changed")
                return f"OBSERVED:{checkpoint}"

            with self.assertRaisesRegex(MODULE.CaptureError, "failed-load checkpoint changed"):
                MODULE.capture_candidate(
                    contract=contract,
                    game_id="vv4",
                    mode="experimental_expanded_256",
                    folder=folder,
                    save_root=save_root,
                    role_paths=roles,
                    source_commit=SOURCE_COMMIT,
                    prompt=prompt,
                    clock=lambda: FIXED_TIME,
                    operator="player",
                )

    def test_candidate_rejects_manual_or_synthetic_field_injection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folder = root / "VV4 Complete Folder"
            folder.mkdir()
            contract, roles = _fixture_contract_and_folder(folder)
            save_root = _modded_save(root)
            changed_stages = {"stock_import_conversion", "offline_catchup", "save_rotation"}

            def prompt(message: str) -> str:
                checkpoint = message.split("OBSERVED:", 1)[1].split(" ", 1)[0]
                if checkpoint in changed_stages:
                    path = save_root / "state.sav"
                    path.write_bytes(path.read_bytes() + checkpoint.encode("ascii"))
                return f"OBSERVED:{checkpoint}"

            packet = MODULE.capture_candidate(
                contract=contract,
                game_id="vv4",
                mode="experimental_expanded_256",
                folder=folder,
                save_root=save_root,
                role_paths=roles,
                source_commit=SOURCE_COMMIT,
                prompt=prompt,
                clock=lambda: FIXED_TIME,
                operator="player",
            )
            manual = copy.deepcopy(packet)
            manual["checkpoints"][0]["manual_fields"] = {"stock_imported": True}
            with self.assertRaisesRegex(MODULE.CaptureError, "manual field injection"):
                MODULE.validate_unsigned_candidate(manual, contract)
            synthetic = copy.deepcopy(packet)
            synthetic["checkpoints"][0]["synthetic"] = True
            with self.assertRaisesRegex(MODULE.CaptureError, "synthetic checkpoint"):
                MODULE.validate_unsigned_candidate(synthetic, contract)
            late = copy.deepcopy(packet)
            late["runtime_evidence"]["gates"]["late_record_boundaries"]["assertions"]["indices"] = [149, 150]
            late["runtime_evidence"]["receipt_sha256"] = MODULE.canonical_sha256(late["runtime_evidence"], remove_key="receipt_sha256")
            with self.assertRaisesRegex(MODULE.CaptureError, "late-record assertion"):
                MODULE.validate_unsigned_candidate(late, contract)
            relocation = copy.deepcopy(packet)
            relocation["preflight"]["relocation_proof"]["rows"].pop()
            with self.assertRaisesRegex(MODULE.CaptureError, "relocation proof"):
                MODULE.validate_unsigned_candidate(relocation, contract)

    def test_harness_has_no_automatic_launch_or_json_observation_loader(self) -> None:
        source = (ROOT / "scripts" / "capture_expanded_runtime_evidence.py").read_text(encoding="utf-8")
        self.assertNotIn("subprocess", source)
        self.assertNotIn("Popen", source)
        self.assertNotIn("os.system", source)
        with self.assertRaises(SystemExit):
            MODULE.build_parser().parse_args(["capture", "--observation-file", "manual.json"])


if __name__ == "__main__":
    unittest.main()
