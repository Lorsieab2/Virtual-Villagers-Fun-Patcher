from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import vv3_expanded_256_runtime_capture as capture
from vv3_expanded_256_evidence import EvidenceValidation, canonical_json_bytes


ROOT = Path(__file__).resolve().parents[1]
CLI_SPEC = importlib.util.spec_from_file_location(
    "prepare_vv3_expanded_runtime_capture_cli",
    ROOT / "scripts" / "prepare_vv3_expanded_runtime_capture.py",
)
CLI = importlib.util.module_from_spec(CLI_SPEC)
assert CLI_SPEC and CLI_SPEC.loader
CLI_SPEC.loader.exec_module(CLI)


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _anchor(source_sha256: str) -> dict[str, object]:
    return {
        "evidence_sha256": "A" * 64,
        "exporter_manifest_path": "manifests/exporter.json",
        "exporter_manifest_sha256": "B" * 64,
        "exporter_manifest_file_sha256": "C" * 64,
        "exporter_producer": "vv3-ida-exporter",
        "exporter_run_id": "test-run",
        "source_sha256": source_sha256,
        "prototype_sha256": capture.VV3_PROTOTYPE_SHA256,
    }


class RuntimeCaptureHarnessTests(unittest.TestCase):
    def _pending_components(self) -> tuple[dict[str, object], dict[str, object]]:
        folder = {
            "status": "verified_inventory_only", "complete": True,
            "folder_name": capture.GAME_FOLDER_NAME, "physical_files": 419,
            "role_counts": dict(capture.VV3_FOLDER_CONTRACT.role_counts),
            "entry_executable": capture.ENTRY_EXE_NAME, "entry_sha256": "D" * 64,
            "no_follow": True, "re_read_verified": True, "inventory_sha256": "E" * 64,
        }
        save = {
            "status": "path_preflight_only", "explicitly_supplied": True,
            "folder_name": capture.MODDED_SAVE_ROOT_NAME, "path": "X:/explicit/Modded 256",
            "contents_accessed": False, "reparse_free": True,
        }
        return folder, save

    def _fixture(self, parent: Path) -> tuple[Path, capture.FolderContract, dict[str, object], dict[str, object]]:
        folder = parent / "VV3 Test - Modded 256"
        folder.mkdir()
        payloads = {
            "stock.exe": ("stock_executable", b"stock"),
            "asset.bin": ("retained_game_asset", b"asset"),
            "entry.exe": ("entry_executable", b"entry"),
            "companion.dll": ("companion_dll", b"dll"),
            "patch-log.json": ("patch_log", b"patch"),
            "transparency.txt": ("transparency_log", b"transparency"),
            "README.txt": ("player_readme", b"readme"),
            "runtime-inventory.json": ("runtime_inventory", b"inventory"),
            "SHA256SUMS.txt": ("checksum_list", b"checksums"),
        }
        records = []
        for name, (role, data) in payloads.items():
            path = folder / name
            path.write_bytes(data)
            records.append({"path": name, "role": role, "size": len(data), "sha256": _digest(data)})
        records.sort(key=lambda item: item["path"])
        contract = capture.FolderContract(
            folder_name=folder.name,
            stock_exe_name="stock.exe",
            entry_exe_name="entry.exe",
            companion_name="companion.dll",
            source_sha256=_digest(b"stock"),
            source_size=len(b"stock"),
            companion_sha256=_digest(b"dll"),
            companion_size=len(b"dll"),
            role_counts={
                "stock_executable": 1,
                "retained_game_asset": 1,
                "entry_executable": 1,
                "companion_dll": 1,
                "patch_log": 1,
                "transparency_log": 1,
                "player_readme": 1,
                "runtime_inventory": 1,
                "checksum_list": 1,
            },
        )
        anchor = _anchor(contract.source_sha256)
        inventory = {
            "schema": capture.FOLDER_INVENTORY_SCHEMA,
            "schema_version": capture.SCHEMA_VERSION,
            "status": "complete",
            "complete": True,
            "synthetic": False,
            "ambiguous": False,
            "folder_name": folder.name,
            "source_sha256": contract.source_sha256,
            "prototype_sha256": capture.VV3_PROTOTYPE_SHA256,
            "exporter_manifest_sha256": anchor["exporter_manifest_sha256"],
            "exporter_manifest_file_sha256": anchor["exporter_manifest_file_sha256"],
            "physical_files": contract.physical_files,
            "records": records,
        }
        return folder, contract, anchor, inventory

    def test_production_contract_requires_exact_complete_folder(self) -> None:
        contract = capture.VV3_FOLDER_CONTRACT
        self.assertEqual(contract.physical_files, 419)
        self.assertEqual(contract.role_counts["retained_game_asset"], 411)
        self.assertEqual(contract.source_sha256, "8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503")
        self.assertEqual(contract.companion_sha256, "2ED1100E7F2EA5B8E522C2DE11F6B00CA8A02B968319C251365E9EFD634BCAF9")
        self.assertEqual(contract.folder_name, capture.MODDED_SAVE_ROOT_NAME)

    def test_complete_temporary_folder_is_hashed_and_reread(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder, contract, anchor, inventory = self._fixture(Path(temporary))
            result = capture.preflight_complete_game_folder(folder, inventory, anchor, contract=contract)
        self.assertTrue(result["complete"])
        self.assertTrue(result["no_follow"])
        self.assertTrue(result["re_read_verified"])
        self.assertEqual(result["physical_files"], 9)

    def test_partial_or_extra_folder_is_refused(self) -> None:
        for mode in ("partial", "extra"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temporary:
                folder, contract, anchor, inventory = self._fixture(Path(temporary))
                if mode == "partial":
                    (folder / "asset.bin").unlink()
                else:
                    (folder / "unexpected.bin").write_bytes(b"extra")
                with self.assertRaisesRegex(capture.CaptureHarnessError, "partial or has extras"):
                    capture.preflight_complete_game_folder(folder, inventory, anchor, contract=contract)

    def test_partial_inventory_cannot_redefine_completeness(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder, contract, anchor, inventory = self._fixture(Path(temporary))
            inventory["records"].pop()
            inventory["physical_files"] = 8
            with self.assertRaisesRegex(capture.CaptureHarnessError, "exactly 9 files"):
                capture.preflight_complete_game_folder(folder, inventory, anchor, contract=contract)

    def test_wrong_stock_and_companion_identities_are_refused(self) -> None:
        for role in ("stock_executable", "companion_dll"):
            with self.subTest(role=role), tempfile.TemporaryDirectory() as temporary:
                _, contract, anchor, inventory = self._fixture(Path(temporary))
                record = next(item for item in inventory["records"] if item["role"] == role)
                record["sha256"] = "0" * 64
                with self.assertRaisesRegex(capture.CaptureHarnessError, "SHA-256 mismatch"):
                    capture.validate_folder_inventory_document(inventory, anchor, contract=contract)

    def test_folder_inventory_must_bind_authenticated_manifest_and_non_synthetic_status(self) -> None:
        for label in ("manifest", "synthetic"):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary:
                _, contract, anchor, inventory = self._fixture(Path(temporary))
                if label == "manifest":
                    inventory["exporter_manifest_sha256"] = "0" * 64
                else:
                    inventory["synthetic"] = True
                with self.assertRaises(capture.CaptureHarnessError):
                    capture.validate_folder_inventory_document(inventory, anchor, contract=contract)

    def test_folder_bytes_must_match_declared_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder, contract, anchor, inventory = self._fixture(Path(temporary))
            (folder / "asset.bin").write_bytes(b"substituted")
            with self.assertRaisesRegex(capture.CaptureHarnessError, "size mismatch|SHA-256 mismatch"):
                capture.preflight_complete_game_folder(folder, inventory, anchor, contract=contract)

    def test_folder_file_mutation_between_inventory_reads_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder, contract, anchor, inventory = self._fixture(Path(temporary))
            original = capture.inventory_evidence_file
            mutated = [False]

            def mutate_after_first(path: Path, *, root: Path) -> object:
                result = original(path, root=root)
                if str(path) == "asset.bin" and not mutated[0]:
                    (folder / "asset.bin").write_bytes(b"other")
                    mutated[0] = True
                return result

            with mock.patch.object(capture, "inventory_evidence_file", side_effect=mutate_after_first):
                with self.assertRaisesRegex(capture.CaptureHarnessError, "changed during re-read"):
                    capture.preflight_complete_game_folder(folder, inventory, anchor, contract=contract)

    def test_game_folder_name_must_be_exact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder, contract, anchor, inventory = self._fixture(Path(temporary))
            wrong_contract = capture.FolderContract(
                **{**contract.__dict__, "folder_name": "Expected Exact - Modded 256"}
            )
            with self.assertRaisesRegex(capture.CaptureHarnessError, "not the exact VV3 Modded 256 folder"):
                capture.preflight_complete_game_folder(folder, inventory, anchor, contract=wrong_contract)

    def test_duplicate_reordered_and_extra_inventory_fields_fail_closed(self) -> None:
        mutations = {
            "duplicate": lambda inventory: inventory["records"].__setitem__(1, copy.deepcopy(inventory["records"][0])),
            "reordered": lambda inventory: inventory["records"].reverse(),
            "extra": lambda inventory: inventory.update({"unexpected": True}),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary:
                _, contract, anchor, inventory = self._fixture(Path(temporary))
                mutate(inventory)
                with self.assertRaises(capture.CaptureHarnessError):
                    capture.validate_folder_inventory_document(inventory, anchor, contract=contract)

    def test_boolean_file_counts_and_sizes_do_not_coerce(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            _, contract, anchor, inventory = self._fixture(Path(temporary))
            inventory["physical_files"] = True
            with self.assertRaisesRegex(capture.CaptureHarnessError, "exactly 9 files"):
                capture.validate_folder_inventory_document(inventory, anchor, contract=contract)
            inventory["physical_files"] = 9
            inventory["records"][0]["size"] = True
            with self.assertRaisesRegex(capture.CaptureHarnessError, "size is invalid"):
                capture.validate_folder_inventory_document(inventory, anchor, contract=contract)

    def test_real_game_folder_symlink_is_rejected_when_supported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder, contract, anchor, inventory = self._fixture(Path(temporary))
            target = folder / "target.bin"
            target.write_bytes(b"asset")
            link = folder / "asset.bin"
            link.unlink()
            try:
                link.symlink_to(target)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"platform does not permit symlink creation: {exc}")
            with self.assertRaisesRegex(capture.CaptureHarnessError, "symlink or reparse"):
                capture.preflight_complete_game_folder(folder, inventory, anchor, contract=contract)

    def test_save_root_accepts_only_explicit_exact_modded_path_without_listing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / capture.MODDED_SAVE_ROOT_NAME
            root.mkdir()
            with mock.patch.object(os, "scandir", side_effect=AssertionError("save contents were listed")):
                result = capture.preflight_modded_save_root(root)
        self.assertFalse(result["contents_accessed"])
        self.assertTrue(result["explicitly_supplied"])

    def test_vanilla_or_generic_save_root_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "Virtual Villagers - The Secret City"
            root.mkdir()
            with self.assertRaisesRegex(capture.CaptureHarnessError, "explicit VV3 Modded 256"):
                capture.preflight_modded_save_root(root)

    def test_real_save_root_symlink_is_rejected_when_supported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            target = parent / "target"
            target.mkdir()
            link = parent / capture.MODDED_SAVE_ROOT_NAME
            try:
                link.symlink_to(target, target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"platform does not permit symlink creation: {exc}")
            with self.assertRaisesRegex(capture.CaptureHarnessError, "symlink or reparse"):
                capture.preflight_modded_save_root(link)

    def test_pending_receipt_contains_every_required_stage_and_is_stop(self) -> None:
        anchor = _anchor(capture.VV3_SOURCE_SHA256)
        folder, save = self._pending_components()
        receipt = capture.build_pending_receipt(anchor, folder, save)
        self.assertEqual([stage["id"] for stage in receipt["stages"]], [stage[0] for stage in capture.STAGE_REQUIREMENTS])
        self.assertTrue(all(stage["status"] == "pending" for stage in receipt["stages"]))
        self.assertFalse(receipt["integrity"]["signed"])
        self.assertEqual(receipt["decision"]["status"], "STOP")
        self.assertFalse(receipt["decision"]["runtime_go"])
        self.assertFalse(receipt["decision"]["player_go"])
        self.assertFalse(receipt["decision"]["publication_ready"])

    def test_pending_validator_rejects_observations_signatures_and_go(self) -> None:
        anchor = _anchor(capture.VV3_SOURCE_SHA256)
        folder, save = self._pending_components()
        receipt = capture.build_pending_receipt(anchor, folder, save)
        mutations = {
            "observation": lambda value: value["stages"][0]["observation_refs"].append("fake"),
            "observed": lambda value: value["stages"][0].update({"status": "observed"}),
            "signed": lambda value: value["integrity"].update({"signed": True}),
            "runtime go": lambda value: value["decision"].update({"runtime_go": True}),
            "player": lambda value: value["stages"][-1].update({"player_confirmed": True}),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                changed = copy.deepcopy(receipt)
                mutate(changed)
                with self.assertRaises(capture.CaptureHarnessError):
                    capture.validate_pending_receipt(changed)

    def test_in_memory_or_failed_static_evidence_cannot_anchor_capture(self) -> None:
        failed = EvidenceValidation(("not authenticated",), False, False, False)
        with tempfile.TemporaryDirectory() as temporary, mock.patch.object(
            capture, "validate_evidence_file", return_value=failed
        ):
            root = Path(temporary)
            with self.assertRaisesRegex(capture.CaptureHarnessError, "not authenticated"):
                capture.authenticate_exporter_anchor(root / "evidence.json", root)

    def test_folder_inventory_mutation_between_reads_is_rejected(self) -> None:
        before = {"a": 1}
        after = {"a": 2}
        with mock.patch.object(capture, "authenticate_exporter_anchor", return_value=_anchor(capture.VV3_SOURCE_SHA256)), mock.patch.object(
            capture, "load_evidence", side_effect=[before, after]
        ), mock.patch.object(capture, "preflight_complete_game_folder", return_value={}), mock.patch.object(
            capture, "preflight_modded_save_root", return_value={}
        ):
            with self.assertRaisesRegex(capture.CaptureHarnessError, "changed during preflight"):
                capture.prepare_dry_run_receipt(
                    evidence_path=Path("evidence.json"), catalog_root=Path("catalog"),
                    game_folder=Path("game"), folder_inventory_path=Path("inventory.json"),
                    modded_save_root=Path("save"),
                )

    def test_cli_requires_explicit_dry_run_before_any_path_access(self) -> None:
        completed = subprocess.run(
            [
                sys.executable, str(ROOT / "scripts" / "prepare_vv3_expanded_runtime_capture.py"),
                "--evidence-json", "missing", "--catalog-root", "missing",
                "--game-folder", "missing", "--folder-inventory", "missing",
                "--modded-save-root", "missing",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("--dry-run is mandatory", completed.stderr)

    def test_cli_dry_run_prints_only_the_pending_template(self) -> None:
        folder, save = self._pending_components()
        receipt = capture.build_pending_receipt(_anchor(capture.VV3_SOURCE_SHA256), folder, save)

        class Output:
            def __init__(self) -> None:
                self.buffer = io.BytesIO()

        output = Output()
        with mock.patch.object(CLI, "prepare_dry_run_receipt", return_value=receipt), mock.patch.object(
            CLI.sys, "stdout", output
        ):
            result = CLI.main([
                "--dry-run", "--evidence-json", "evidence.json", "--catalog-root", "catalog",
                "--game-folder", "game", "--folder-inventory", "inventory.json",
                "--modded-save-root", "save",
            ])
        self.assertEqual(result, 0)
        emitted = json.loads(output.buffer.getvalue())
        self.assertEqual(emitted["receipt_status"], "pending")
        self.assertEqual(emitted["decision"]["status"], "STOP")

    def test_schema_and_docs_preserve_pending_no_launch_boundary(self) -> None:
        schema = json.loads((ROOT / "data" / "vv3_expanded_256_runtime_receipt.schema.json").read_text(encoding="utf-8"))
        folder_schema = json.loads((ROOT / "data" / "vv3_expanded_256_folder_inventory.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["receipt_status"]["const"], "pending")
        self.assertFalse(schema["properties"]["integrity"]["properties"]["signed"]["const"])
        self.assertFalse(schema["properties"]["decision"]["properties"]["runtime_go"]["const"])
        self.assertEqual(schema["properties"]["folder_preflight"]["properties"]["physical_files"]["const"], 419)
        self.assertEqual(folder_schema["properties"]["physical_files"]["const"], 419)
        self.assertEqual(folder_schema["properties"]["records"]["minItems"], 419)
        docs = (ROOT / "docs" / "vv3-expanded-256-runtime-capture-harness.md").read_text(encoding="utf-8")
        flat = " ".join(docs.split())
        self.assertIn("no code path that launches the game", flat)
        self.assertIn("does not list the directory or open any save", flat)
        self.assertIn("records 149, 150, 254, and 255", flat)
        self.assertIn("padding indices 256-259", flat)

    def test_source_contains_no_launch_or_save_discovery_primitive(self) -> None:
        source = (ROOT / "src" / "vv3_expanded_256_runtime_capture.py").read_text(encoding="utf-8")
        cli = (ROOT / "scripts" / "prepare_vv3_expanded_runtime_capture.py").read_text(encoding="utf-8")
        for forbidden in ("import subprocess", "os.startfile", "Popen(", "VVFP_LDW_SAVE_ROOT", "expanduser()"):
            self.assertNotIn(forbidden, source)
            self.assertNotIn(forbidden, cli)

    def test_receipt_transport_is_canonical_but_unsigned(self) -> None:
        folder, save = self._pending_components()
        receipt = capture.build_pending_receipt(_anchor(capture.VV3_SOURCE_SHA256), folder, save)
        raw = capture.receipt_bytes(receipt)
        self.assertEqual(raw, canonical_json_bytes(receipt) + b"\n")
        self.assertIsNone(receipt["integrity"]["canonical_sha256"])
        self.assertIsNone(receipt["integrity"]["signature"])


if __name__ == "__main__":
    unittest.main()
