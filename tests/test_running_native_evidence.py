from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from running_native_evidence import (  # noqa: E402
    RUNNING_QUERY_IDS,
    bind_running_evidence,
    canonical_json,
    inventory_copied_input,
    sha,
)


class RunningNativeEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = json.loads(
            (ROOT / "data" / "candidates" / "vv3_individual_grant_running_binding.json").read_text()
        )
        self.queries = json.loads((ROOT / "data" / "native_evidence_queries.json").read_text())
        self.schema = ROOT / "data" / "authenticated_native_export.schema.json"
        self.query_path = ROOT / "data" / "native_evidence_queries.json"

    def _fixture(self) -> tuple[Path, Path, Path, dict, bytes]:
        root = Path(tempfile.mkdtemp())
        folder = root / "vv3-stock-copy"
        folder.mkdir()
        executable = b"MZ" + bytes(range(64))
        (folder / "fixture.exe").write_bytes(executable)
        (folder / "readme.txt").write_bytes(b"copied stock input")
        manifest = copy.deepcopy(self.manifest)
        manifest["exact_build"]["filename"] = "fixture.exe"
        manifest["exact_build"]["size"] = len(executable)
        manifest["exact_build"]["sha256"] = sha(executable)
        inventory, source_bytes = inventory_copied_input(root, folder, "vv3", manifest)
        rows = []
        for query in self.queries["queries"]:
            rows.append(
                {
                    "query_id": query["id"],
                    "status": "resolved",
                    "function_start_ea": "0x401000",
                    "function_end_ea": "0x401002",
                    "file_offset": "0x0",
                    "raw_bytes": source_bytes[:2].hex().upper(),
                    "instructions": [{"ea": "0x401000", "text": "dec eax"}],
                    "callers": [],
                    "xrefs": [],
                    "registers": {"inputs": ["ecx"], "outputs": ["eax"]},
                    "stack_cleanup": "callee ret 4",
                    "call_convention": "__thiscall",
                }
            )
        export = {
            "schema": "vvfp.authenticated-native-export.v1",
            "generated_by": "ida_python",
            "synthetic": False,
            "manual": False,
            "game": "vv3",
            "inventory_sha256": inventory["inventory_sha256"],
            "functions": rows,
        }
        export["artifact_sha256"] = sha(canonical_json(export))
        export_path = root / "vv3-export.json"
        export_path.write_bytes(canonical_json(export))
        return root, folder, export_path, manifest, export

    def test_valid_generic_export_binds_source_but_remains_stop(self) -> None:
        root, folder, export_path, manifest, _ = self._fixture()
        binding = bind_running_evidence(
            "vv3", manifest, root, folder, export_path,
            schema_path=self.schema, query_path=self.query_path,
        )
        self.assertTrue(binding.export_valid)
        self.assertEqual(binding.resolved_queries, tuple(item["id"] for item in self.queries["queries"]))
        self.assertEqual(binding.inventory_sha256 and len(binding.inventory_sha256), 64)
        self.assertEqual(binding.status, "STOP")
        self.assertFalse(binding.enabled)
        self.assertFalse(binding.catalog_enabled)
        self.assertTrue(binding.catalog_hidden)
        self.assertFalse(binding.native_output)
        self.assertFalse(binding.runtime_verified)
        self.assertFalse(binding.player_verified)
        self.assertFalse(binding.semantic_proof_complete)
        self.assertFalse(binding.enablement_ready)
        self.assertIn("does not prove Running semantics", " ".join(binding.errors))

    def test_vv1_vv2_are_stop_when_schema_has_no_export_game(self) -> None:
        for game_id in ("vv1", "vv2"):
            binding = bind_running_evidence(game_id, {}, Path("."), Path("."), Path("."))
            self.assertEqual(binding.status, "STOP")
            self.assertFalse(binding.export_valid)
            self.assertIn("VV3-VV5 only", " ".join(binding.errors))

    def test_wrong_copy_and_outside_export_fail_closed(self) -> None:
        root, folder, export_path, manifest, _ = self._fixture()
        wrong = folder / "fixture.exe"
        wrong.write_bytes(b"changed")
        rejected = bind_running_evidence(
            "vv3", manifest, root, folder, export_path,
            schema_path=self.schema, query_path=self.query_path,
        )
        self.assertFalse(rejected.export_valid)
        self.assertFalse(rejected.enablement_ready)
        root2, folder2, export_path2, manifest2, export2 = self._fixture()
        outside = Path(tempfile.mkdtemp()) / "outside.json"
        outside.write_bytes(canonical_json(export2))
        rejected = bind_running_evidence(
            "vv3", manifest2, root2, folder2, outside,
            schema_path=self.schema, query_path=self.query_path,
        )
        self.assertFalse(rejected.export_valid)
        self.assertIn("inside the declared workspace root", " ".join(rejected.errors))

    def test_export_tampering_is_rejected_without_repair_or_write(self) -> None:
        root, folder, export_path, manifest, export = self._fixture()
        cases = []
        item = copy.deepcopy(export); item["synthetic"] = True; cases.append(item)
        item = copy.deepcopy(export); item["manual"] = True; cases.append(item)
        item = copy.deepcopy(export); item["functions"].pop(); cases.append(item)
        item = copy.deepcopy(export); item["functions"][0]["raw_bytes"] = "FFFF"; cases.append(item)
        item = copy.deepcopy(export); item["functions"][0]["registers"] = {}; cases.append(item)
        item = copy.deepcopy(export); item["functions"][0]["file_offset"] = 0; cases.append(item)
        item = copy.deepcopy(export); item["artifact_sha256"] = "0" * 64; cases.append(item)
        original = export_path.read_bytes()
        for item in cases:
            export_path.write_bytes(canonical_json(item))
            binding = bind_running_evidence(
                "vv3", manifest, root, folder, export_path,
                schema_path=self.schema, query_path=self.query_path,
            )
            self.assertFalse(binding.export_valid)
            self.assertFalse(binding.enablement_ready)
        export_path.write_bytes(original)
        self.assertEqual(export_path.read_bytes(), original)

    def test_query_set_covers_running_identity_account_requirements(self) -> None:
        query_ids = tuple(item["id"] for item in self.queries["queries"])
        for required in RUNNING_QUERY_IDS:
            self.assertIn(required, query_ids)
        self.assertEqual(
            RUNNING_QUERY_IDS,
            (
                "selected_index_and_world_resolver",
                "funds_getter",
                "funds_deduction_setter",
                "preference_setter_readback_queue",
                "confirmation_result_abi",
                "postverify_fault_boundary",
            ),
        )

    def test_weakened_schema_or_query_manifest_fails_closed(self) -> None:
        root, folder, export_path, manifest, _ = self._fixture()
        weak_schema = root / "weak-schema.json"
        schema = copy.deepcopy(json.loads(self.schema.read_text()))
        schema["required"] = schema["required"][:-1]
        weak_schema.write_bytes(canonical_json(schema))
        binding = bind_running_evidence(
            "vv3", manifest, root, folder, export_path,
            schema_path=weak_schema, query_path=self.query_path,
        )
        self.assertFalse(binding.export_valid)
        self.assertIn("weakened", " ".join(binding.errors))

    def test_manifest_identity_order_and_enablement_are_fail_closed(self) -> None:
        root, folder, export_path, manifest, _ = self._fixture()
        for mutation, expected in (
            ({"game_id": "vv4"}, "game identity"),
            ({"eligibility_gate_order": "after_preference_access"}, "eligibility"),
            ({"enabled": True}, "enabled"),
            ({"catalog_enabled": True}, "enabled"),
        ):
            item = copy.deepcopy(manifest)
            item.update(mutation)
            binding = bind_running_evidence(
                "vv3", item, root, folder, export_path,
                schema_path=self.schema, query_path=self.query_path,
            )
            self.assertFalse(binding.export_valid)
            self.assertIn(expected, " ".join(binding.errors))

        weak_queries = root / "weak-queries.json"
        queries = copy.deepcopy(self.queries)
        queries["queries"][0]["output"] = []
        weak_queries.write_bytes(canonical_json(queries))
        binding = bind_running_evidence(
            "vv3", manifest, root, folder, export_path,
            schema_path=self.schema, query_path=weak_queries,
        )
        self.assertFalse(binding.export_valid)
        self.assertIn("weakened", " ".join(binding.errors))


if __name__ == "__main__":
    unittest.main()
