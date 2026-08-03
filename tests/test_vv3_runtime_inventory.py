from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "build_vv3_runtime_inventory", ROOT / "scripts" / "build_vv3_runtime_inventory.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class VV3RuntimeInventoryTests(unittest.TestCase):
    def _tree(self, root: Path) -> None:
        for index in range(412):
            path = root / "stock" / f"file-{index:03d}.bin"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(bytes([index % 251]))
        current = {
            "game.exe": "entry_executable",
            "candidate.dll": "companion_dll",
            "patch-log.json": "patch_log",
            "transparency.txt": "transparency_log",
            "README.txt": "player_readme",
        }
        for name in current:
            (root / name).write_bytes(name.encode("ascii"))
        (root / MODULE.INVENTORY_NAME).write_text("{}", encoding="utf-8")
        (root / MODULE.CHECKSUMS_NAME).write_text("", encoding="utf-8")

    def test_schema_contains_accounting_roles_and_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._tree(root)
            inventory, records = MODULE.build_inventory(
                root,
                entry_executable="game.exe",
                source_archive={"filename": "stock.zip", "sha256": "ZIP"},
                excluded_source_members=["old.exe"],
                generated_payload_roles={
                    "game.exe": "entry_executable",
                    "candidate.dll": "companion_dll",
                    "patch-log.json": "patch_log",
                    "transparency.txt": "transparency_log",
                    "README.txt": "player_readme",
                },
                generated_file_roles={
                    "game.exe": "entry_executable",
                    "candidate.dll": "companion_dll",
                    "patch-log.json": "patch_log",
                    "transparency.txt": "transparency_log",
                    "README.txt": "player_readme",
                    "runtime-inventory.json": "runtime_inventory",
                    "SHA256SUMS.txt": "checksum_list",
                },
                preimage_identities={"stock_exe_sha256": "EXE"},
                dependency_chain=["Origins", "Full Mastery", "Grant Running", "Full Heal"],
                commits={"design": "D", "implementation": "I", "static_acceptance": "S", "enablement": "E", "package": "P"},
                identities={"manifest_sha256": "M", "map_sha256": "A", "dll_sha256": "D"},
                save_route="Documents\\LDW\\game - Modded\\",
                catalog_status={"enabled": True, "catalog_hidden": False},
                runtime_player_status="pending",
            )
            self.assertEqual(inventory["schema"], MODULE.SCHEMA_VERSION)
            self.assertEqual(inventory["source_archive"]["runtime_members"], 417)
            self.assertEqual(inventory["source_archive"]["outer_evidence_files"], 2)
            self.assertEqual(inventory["derivation"]["retained_stock_files"], 412)
            self.assertEqual(inventory["derivation"]["current_files"], 7)
            self.assertEqual(len(records), 417)
            self.assertTrue(all("role" in record and record["role"] for record in records))
            generated = {item["path"]: item for item in inventory["generated_file_roles"]}
            self.assertEqual(len(generated), 7)
            self.assertIsNone(generated["runtime-inventory.json"]["sha256"])
            self.assertEqual(inventory["dependency_chain"], ["Origins", "Full Mastery", "Grant Running", "Full Heal"])
            self.assertEqual(inventory["runtime_player_status"], "pending")

    def test_wrong_role_count_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._tree(root)
            with self.assertRaises(ValueError):
                MODULE.build_inventory(
                    root,
                    entry_executable="game.exe",
                    source_archive={},
                    excluded_source_members=[],
                    generated_payload_roles={"game.exe": "entry_executable"},
                    generated_file_roles={"game.exe": "entry_executable"},
                    preimage_identities={}, dependency_chain=[], commits={}, identities={},
                    save_route="", catalog_status={}, runtime_player_status="pending",
                )

