from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from vv3_expanded_256_contract import VV3_RECORD_BOUND_PATCHES, VV3_STOCK_SAVE_PATCHES
from vv3_expanded_256_evidence import (
    REQUIRED_CONSUMER_CLAIMS,
    REQUIRED_INDEX_PATHS,
    REQUIRED_LOADER_CLAIMS,
    REQUIRED_PADDING_PATHS,
    REQUIRED_RUNTIME_GATES,
    VV3_PROTOTYPE_SHA256,
    VV3_REQUIRED_PATCHES,
    VV3_SOURCE_SHA256,
    VV3_STOCK_SIZE,
    canonical_json_bytes,
    inventory_evidence_file,
    publication_ready_with_evidence,
    validate_evidence_file,
    validate_vv3_evidence,
)


ROOT = Path(__file__).resolve().parents[1]


def _observation(offset: int, raw_bytes: str) -> dict:
    return {
        "status": "verified",
        "synthetic": False,
        "ambiguous": False,
        "incomplete": False,
        "ea": f"0x{0x400000 + offset:X}",
        "file_offset": f"0x{offset:X}",
        "raw_bytes": raw_bytes,
        "xrefs": [{"ea": "0x401000", "kind": "code"}],
    }


def _claim(claim_id: str, offset: int = 0x1000) -> dict:
    return {
        "id": claim_id,
        "status": "verified",
        "synthetic": False,
        "ambiguous": False,
        "incomplete": False,
        "observations": [_observation(offset, "90")],
        "semantics": "native evidence is explicit",
    }


def _loader_claim(claim_id: str, offset: int) -> dict:
    claim = _claim(claim_id, offset)
    claim["abi"] = {
        "calling_convention": "cdecl",
        "return_semantics": "native result",
    }
    claim["branches"] = [
        {"condition": "reviewed condition", "outcome": "reviewed outcome", "target": "reviewed target"}
    ]
    return claim


def _runtime_gate() -> dict:
    return {
        "status": "pending",
        "synthetic": False,
        "ambiguous": False,
        "incomplete": True,
        "evidence_ids": [],
    }


def _bundle() -> dict:
    exact_operands = []
    for index, (offset, expected) in enumerate(sorted(VV3_REQUIRED_PATCHES.items())):
        exact_operands.append(
            {
                "status": "verified",
                "synthetic": False,
                "ambiguous": False,
                "incomplete": False,
                "ea": f"0x{0x400000 + offset:X}",
                "file_offset": f"0x{offset:X}",
                "raw_bytes": expected["before"],
                "xrefs": [{"ea": f"0x{0x401000 + index:X}", "kind": "code"}],
            }
        )
    return {
        "schema": "vvfp.vv3_expanded_256_evidence",
        "schema_version": 1,
        "game_id": "vv3",
        "provenance": {
            "producer": "unit fixture",
            "input_kind": "exact_stock_executable",
            "status": "complete",
            "synthetic": False,
            "ambiguous": False,
            "incomplete": False,
            "reconciled": True,
        },
        "source_sha256": VV3_SOURCE_SHA256,
        "prototype_sha256": VV3_PROTOTYPE_SHA256,
        "stock": {"sha256": VV3_SOURCE_SHA256, "size": VV3_STOCK_SIZE, "imagebase": "0x400000"},
        "ida_export": {
            "decoded_instruction_heads": 1,
            "executable_segment_bytes": 1,
            "references": [],
            "constants": [],
        },
        "reconcile": {
            "game_id": "vv3",
            "manifest": {
                "source_sha256": VV3_SOURCE_SHA256,
                "prototype_sha256": VV3_PROTOTYPE_SHA256,
                "declared_patch_count": 1263,
                "actual_patch_count": 1263,
                "guard_errors": [],
                "overlaps": [],
            },
            "ida_export": {
                "unmatched_moving_references": [],
                "unpatched_population_sized_constants": [],
            },
        },
        "coverage": {
            "loader_abi_branches": {
                "status": "verified",
                "claims": [_loader_claim(claim_id, 0x28949 + index) for index, claim_id in enumerate(REQUIRED_LOADER_CLAIMS)],
            },
            "stored_index_width_sentinel_paths": {
                "status": "verified",
                "claims": [
                    {**_claim(claim_id, 0x5000 + index), "width_bits": 32, "sentinel": {"kind": "none"}}
                    for index, claim_id in enumerate(REQUIRED_INDEX_PATHS)
                ],
            },
            "selectors_queues_callbacks_stats_serializer": {
                "status": "verified",
                "claims": [_claim(claim_id, 0x6000 + index) for index, claim_id in enumerate(REQUIRED_CONSUMER_CLAIMS)],
            },
            "padding_reachability": {
                "status": "verified",
                "claims": [
                    {
                        **_claim(claim_id, 0x7000 + index),
                        "reachable": False,
                        "max_logical_index": 255,
                        "padding_indices": [256, 257, 258, 259],
                    }
                    for index, claim_id in enumerate(REQUIRED_PADDING_PATHS)
                ],
            },
            "exact_stock_operands_xrefs": exact_operands,
        },
        "runtime_evidence": [
            {
                "id": "unit-capture",
                "status": "pending",
                "synthetic": False,
                "ambiguous": False,
                "incomplete": True,
                "kind": "unit-fixture",
                "path": "captures/unit-capture.json",
                "size": 1,
                "sha256": "0" * 64,
            }
        ],
        "runtime_gates": {gate_id: _runtime_gate() for gate_id in REQUIRED_RUNTIME_GATES},
    }


class VV3Expanded256EvidenceTests(unittest.TestCase):
    def test_complete_shape_is_still_not_publication_ready_with_runtime_pending(self) -> None:
        result = validate_vv3_evidence(_bundle())
        self.assertTrue(result.static_valid)
        self.assertFalse(result.runtime_ready)
        self.assertFalse(result.valid)
        self.assertFalse(result.publication_ready)
        self.assertFalse(publication_ready_with_evidence(_bundle()))

    def test_missing_category_fails_closed(self) -> None:
        bundle = _bundle()
        del bundle["coverage"]["stored_index_width_sentinel_paths"]
        result = validate_vv3_evidence(bundle)
        self.assertFalse(result.static_valid)
        self.assertTrue(any("stored_index_width_sentinel_paths" in error for error in result.errors))

    def test_duplicate_claim_and_observation_fail_closed(self) -> None:
        bundle = _bundle()
        claims = bundle["coverage"]["selectors_queues_callbacks_stats_serializer"]["claims"]
        claims.append(copy.deepcopy(claims[0]))
        operands = bundle["coverage"]["exact_stock_operands_xrefs"]
        operands.append(copy.deepcopy(operands[0]))
        result = validate_vv3_evidence(bundle)
        self.assertFalse(result.static_valid)
        self.assertTrue(any("duplicate claim" in error for error in result.errors))
        self.assertTrue(any("is duplicated" in error for error in result.errors))

    def test_duplicate_xref_ea_fails_closed(self) -> None:
        bundle = _bundle()
        xrefs = bundle["coverage"]["loader_abi_branches"]["claims"][0]["observations"][0]["xrefs"]
        xrefs.append(copy.deepcopy(xrefs[0]))
        result = validate_vv3_evidence(bundle)
        self.assertFalse(result.static_valid)
        self.assertTrue(any("xrefs contains duplicate EA" in error for error in result.errors))

    def test_same_claim_duplicate_observation_fails_closed(self) -> None:
        bundle = _bundle()
        observations = bundle["coverage"]["selectors_queues_callbacks_stats_serializer"]["claims"][0]["observations"]
        observations.append(copy.deepcopy(observations[0]))
        result = validate_vv3_evidence(bundle)
        self.assertFalse(result.static_valid)
        self.assertTrue(any("contains duplicate observation at" in error for error in result.errors))

    def test_synthetic_ambiguous_and_incomplete_evidence_is_rejected(self) -> None:
        bundle = _bundle()
        bundle["provenance"]["synthetic"] = True
        bundle["coverage"]["loader_abi_branches"]["claims"][0]["ambiguous"] = True
        bundle["coverage"]["padding_reachability"]["claims"][0]["incomplete"] = True
        result = validate_vv3_evidence(bundle)
        self.assertFalse(result.static_valid)
        self.assertTrue(any("provenance.synthetic" in error for error in result.errors))
        self.assertTrue(any("ambiguous" in error for error in result.errors))
        self.assertTrue(any("incomplete" in error for error in result.errors))

    def test_hash_raw_bytes_and_xrefs_must_match_exact_contract(self) -> None:
        bundle = _bundle()
        bundle["stock"]["sha256"] = "0" * 64
        bundle["coverage"]["exact_stock_operands_xrefs"][0]["raw_bytes"] = "CC"
        bundle["coverage"]["exact_stock_operands_xrefs"][1]["xrefs"] = []
        result = validate_vv3_evidence(bundle)
        self.assertFalse(result.static_valid)
        self.assertTrue(any("stock.sha256" in error for error in result.errors))
        self.assertTrue(any("raw bytes mismatch" in error for error in result.errors))
        self.assertTrue(any("xrefs must be a non-empty list" in error for error in result.errors))

    def test_runtime_gate_requires_verified_non_synthetic_attestation(self) -> None:
        bundle = _bundle()
        gate = bundle["runtime_gates"]["load_hang_resolved"]
        gate.update({"status": "verified", "incomplete": False, "evidence_ids": ["capture-1"]})
        result = validate_vv3_evidence(bundle)
        self.assertTrue(result.static_valid)
        self.assertFalse(result.runtime_ready)
        self.assertTrue(any("runtime_gates.stock_import_expanded_reload" in error for error in result.errors))

    def test_invalid_runtime_catalog_cannot_count_as_ready(self) -> None:
        bundle = _bundle()
        for gate in bundle["runtime_gates"].values():
            gate.update({"status": "verified", "incomplete": False, "evidence_ids": ["unit-capture"]})
        result = validate_vv3_evidence(bundle)
        self.assertFalse(result.runtime_ready)
        self.assertFalse(result.valid)
        self.assertTrue(any("evidence_catalog[0].status" in error for error in result.errors))

    def test_contract_patch_sets_are_not_mutated_by_evidence_tooling(self) -> None:
        self.assertEqual(set(VV3_STOCK_SAVE_PATCHES) | set(VV3_RECORD_BOUND_PATCHES), set(VV3_REQUIRED_PATCHES))

    def test_duplicate_json_keys_fail_before_canonical_validation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evidence.json"
            path.write_bytes(b'{"schema":"vvfp.vv3_expanded_256_evidence","schema":"vvfp.vv3_expanded_256_evidence"}')
            with self.assertRaisesRegex(ValueError, "duplicate JSON object key"):
                from vv3_expanded_256_evidence import load_evidence

                load_evidence(path)

    def test_bool_values_cannot_coerce_into_integer_contract_fields(self) -> None:
        bundle = _bundle()
        bundle["schema_version"] = True
        bundle["ida_export"]["decoded_instruction_heads"] = True
        bundle["coverage"]["stored_index_width_sentinel_paths"]["claims"][0]["sentinel"] = {
            "kind": "value",
            "value": True,
        }
        result = validate_vv3_evidence(bundle)
        self.assertFalse(result.static_valid)
        self.assertTrue(any("schema_version must be an integer" in error for error in result.errors))
        self.assertTrue(any("decoded_instruction_heads must be an integer" in error for error in result.errors))
        self.assertTrue(any("sentinel.value must be an integer" in error for error in result.errors))

    def test_catalog_paths_are_relative_canonical_and_non_reparse_like(self) -> None:
        for invalid in ("../escape.json", "/absolute.json", "C:/absolute.json", "//?/C:/escape.json", "captures\\evidence.json"):
            with self.subTest(invalid=invalid):
                bundle = _bundle()
                bundle["runtime_evidence"][0]["path"] = invalid
                result = validate_vv3_evidence(bundle)
                self.assertFalse(result.runtime_ready)
                self.assertFalse(result.valid)
                self.assertTrue(any("runtime_gates.evidence_catalog[0].path is invalid" in error for error in result.errors))

    def test_extra_schema_keys_fail_closed_at_nested_boundaries(self) -> None:
        bundle = _bundle()
        bundle["ida_export"]["unexpected"] = "reject me"
        bundle["coverage"]["loader_abi_branches"]["claims"][0]["abi"]["unexpected"] = "reject me"
        bundle["runtime_evidence"][0]["unexpected"] = "reject me"
        result = validate_vv3_evidence(bundle)
        self.assertFalse(result.static_valid)
        self.assertTrue(any("ida_export contains unknown keys" in error for error in result.errors))
        self.assertTrue(any(".abi contains unknown keys" in error for error in result.errors))
        self.assertTrue(any("evidence_catalog[0] contains unknown keys" in error for error in result.errors))

    def test_one_artifact_hash_cannot_satisfy_multiple_runtime_gates(self) -> None:
        bundle = _bundle()
        for gate in bundle["runtime_gates"].values():
            gate.update({"status": "verified", "incomplete": False, "evidence_ids": ["unit-capture"]})
        result = validate_vv3_evidence(bundle)
        self.assertFalse(result.runtime_ready)
        self.assertTrue(any("reused across gates" in error for error in result.errors))

    def test_duplicate_catalog_path_fails_closed(self) -> None:
        bundle = _bundle()
        duplicate = copy.deepcopy(bundle["runtime_evidence"][0])
        duplicate.update({"id": "unit-capture-2", "sha256": "1" * 64})
        bundle["runtime_evidence"].append(duplicate)
        result = validate_vv3_evidence(bundle)
        self.assertFalse(result.runtime_ready)
        self.assertTrue(any("runtime evidence path captures/unit-capture.json is duplicated" in error for error in result.errors))

    def test_duplicate_catalog_hash_fails_closed(self) -> None:
        bundle = _bundle()
        duplicate = copy.deepcopy(bundle["runtime_evidence"][0])
        duplicate.update({"id": "unit-capture-2", "path": "captures/unit-capture-2.json"})
        bundle["runtime_evidence"].append(duplicate)
        result = validate_vv3_evidence(bundle)
        self.assertFalse(result.runtime_ready)
        self.assertTrue(any("runtime evidence artifact hash" in error and "reused by" in error for error in result.errors))

    def test_declarative_schema_pins_shape_and_reviewed_fingerprints(self) -> None:
        schema = json.loads(
            (ROOT / "data" / "vv3_expanded_256_evidence.schema.json").read_text(encoding="utf-8")
        )
        self.assertEqual(schema["properties"]["source_sha256"]["const"], VV3_SOURCE_SHA256)
        self.assertEqual(schema["properties"]["prototype_sha256"]["const"], VV3_PROTOTYPE_SHA256)
        self.assertEqual(
            schema["properties"]["coverage"]["properties"]["loader_abi_branches"]["$ref"],
            "#/$defs/loader_section",
        )
        self.assertFalse(schema["$defs"]["loader_claim"]["additionalProperties"])
        self.assertFalse(schema["$defs"]["observation"]["additionalProperties"])
        self.assertIn("not", schema["properties"]["runtime_evidence"]["items"]["properties"]["path"])

    def test_reordered_json_is_not_accepted_as_canonical_evidence(self) -> None:
        bundle = {"z": 1, "a": 2}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reordered.json"
            path.write_text(json.dumps(bundle, separators=(",", ":")), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "canonical key ordering"):
                from vv3_expanded_256_evidence import load_evidence

                load_evidence(path)
            path.write_bytes(canonical_json_bytes(bundle))
            from vv3_expanded_256_evidence import load_evidence

            self.assertEqual(load_evidence(path), bundle)

    def test_file_identity_mismatch_after_hash_read_fails_closed(self) -> None:
        before = SimpleNamespace(st_mode=0o100644, st_dev=1, st_ino=2, st_size=3, st_mtime_ns=4, st_ctime_ns=5)
        after = SimpleNamespace(st_mode=0o100644, st_dev=1, st_ino=99, st_size=3, st_mtime_ns=4, st_ctime_ns=5)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "capture.json"
            path.write_bytes(b"abc")
            with mock.patch("vv3_expanded_256_evidence.os.fstat", side_effect=[before, after]):
                with self.assertRaisesRegex(ValueError, "changed during hash read"):
                    inventory_evidence_file(Path("capture.json"), root=root)

    def test_real_symlink_is_rejected_when_platform_supports_creation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target.json"
            link = root / "link.json"
            target.write_bytes(b"artifact")
            try:
                link.symlink_to(target)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"platform does not permit symlink creation: {exc}")
            self.assertTrue(link.is_symlink(), "symlink creation returned without a symlink")
            with self.assertRaisesRegex(ValueError, "reparse|symlink"):
                inventory_evidence_file(Path("link.json"), root=root)

    def test_evidence_file_mutation_between_inventory_read_and_validation_fails_closed(self) -> None:
        bundle = _bundle()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evidence.json"
            path.write_bytes(canonical_json_bytes(bundle))
            original_validate = validate_vv3_evidence

            def mutate_after_read(value: dict) -> object:
                result = original_validate(value)
                mutated = copy.deepcopy(value)
                mutated["ida_export"]["references"] = [{"mutation": True}]
                path.write_bytes(canonical_json_bytes(mutated))
                return result

            with mock.patch("vv3_expanded_256_evidence.validate_vv3_evidence", side_effect=mutate_after_read):
                result = validate_evidence_file(path)
            self.assertFalse(result.valid)
            self.assertTrue(any("changed between inventory, read, and validation" in error for error in result.errors))


if __name__ == "__main__":
    unittest.main()
