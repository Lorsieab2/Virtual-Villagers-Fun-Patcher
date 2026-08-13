from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

import vv3_expanded_256_evidence as evidence_module
from vv3_expanded_256_contract import VV3_RECORD_BOUND_PATCHES, VV3_STOCK_SAVE_PATCHES
from vv3_expanded_256_evidence import (
    EXPORTER_MANIFEST_SCHEMA,
    EXPORTER_MANIFEST_SCHEMA_VERSION,
    EXPORTER_PRODUCER,
    REQUIRED_CONSUMER_CLAIMS,
    REQUIRED_INDEX_PATHS,
    REQUIRED_LOADER_CLAIMS,
    REQUIRED_PADDING_PATHS,
    REQUIRED_RUNTIME_GATES,
    VV3_PROTOTYPE_SHA256,
    VV3_REQUIRED_PATCHES,
    VV3_SOURCE_SHA256,
    VV3_STOCK_SIZE,
    canonical_exporter_manifest_bytes,
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


def _manifest_body(bundle: dict) -> dict:
    expectations = []
    for item in bundle["coverage"]["exact_stock_operands_xrefs"]:
        expectations.append(
            {
                "file_offset": item["file_offset"],
                "ea": item["ea"],
                "raw_bytes": item["raw_bytes"],
                "xrefs": copy.deepcopy(item["xrefs"]),
            }
        )
    return {
        "schema": EXPORTER_MANIFEST_SCHEMA,
        "schema_version": EXPORTER_MANIFEST_SCHEMA_VERSION,
        "producer": EXPORTER_PRODUCER,
        "exporter_version": "unit-exporter-1",
        "run_id": "unit-run-1",
        "input_kind": "exact_stock_executable",
        "status": "complete",
        "synthetic": False,
        "ambiguous": False,
        "incomplete": False,
        "reconciled": True,
        "source_sha256": VV3_SOURCE_SHA256,
        "source_size": VV3_STOCK_SIZE,
        "prototype_sha256": VV3_PROTOTYPE_SHA256,
        "operand_expectations": expectations,
    }


def _manifest(bundle: dict) -> dict:
    body = _manifest_body(bundle)
    return {
        **body,
        "manifest_sha256": hashlib.sha256(canonical_exporter_manifest_bytes(body)).hexdigest().upper(),
    }


def _authenticated_fixture(root: Path) -> tuple[Path, dict, Path, Path]:
    bundle = _bundle()
    artifact = root / "captures" / "unit-capture.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"runtime-capture")
    artifact_hash = hashlib.sha256(artifact.read_bytes()).hexdigest().upper()
    bundle["runtime_evidence"][0].update(
        {
            "status": "verified",
            "incomplete": False,
            "kind": "runtime-capture",
            "size": artifact.stat().st_size,
            "sha256": artifact_hash,
        }
    )
    manifest = _manifest(bundle)
    manifest_path = root / "manifests" / "exporter.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_bytes = canonical_json_bytes(manifest)
    manifest_path.write_bytes(manifest_bytes)
    manifest_file_hash = hashlib.sha256(manifest_bytes).hexdigest().upper()
    bundle["exporter_manifest"].update(
        {
            "size": len(manifest_bytes),
            "sha256": manifest_file_hash,
        }
    )
    bundle["provenance"].update(
        {
            "producer": manifest["producer"],
            "run_id": manifest["run_id"],
            "manifest_sha256": manifest["manifest_sha256"],
            "manifest_file_sha256": manifest_file_hash,
        }
    )
    evidence_path = root / "evidence.json"
    evidence_path.write_bytes(canonical_json_bytes(bundle))
    return evidence_path, bundle, manifest_path, artifact


def _rewrite_manifest_fixture(root: Path, bundle: dict, manifest_path: Path, mutate: object) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    mutate(manifest)
    body = dict(manifest)
    body.pop("manifest_sha256", None)
    manifest["manifest_sha256"] = hashlib.sha256(canonical_exporter_manifest_bytes(body)).hexdigest().upper()
    manifest_bytes = canonical_json_bytes(manifest)
    manifest_path.write_bytes(manifest_bytes)
    manifest_file_hash = hashlib.sha256(manifest_bytes).hexdigest().upper()
    bundle["exporter_manifest"].update({"size": len(manifest_bytes), "sha256": manifest_file_hash})
    bundle["provenance"].update(
        {
            "producer": manifest["producer"],
            "run_id": manifest["run_id"],
            "manifest_sha256": manifest["manifest_sha256"],
            "manifest_file_sha256": manifest_file_hash,
        }
    )
    (root / "evidence.json").write_bytes(canonical_json_bytes(bundle))


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
                "xrefs": [
                    {"ea": f"0x{0x401000 + index:X}", "kind": "code"},
                    {"ea": f"0x{0x402000 + index:X}", "kind": "data"},
                ],
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
            "run_id": "unit-run-1",
            "manifest_sha256": "0" * 64,
            "manifest_file_sha256": "0" * 64,
        },
        "source_sha256": VV3_SOURCE_SHA256,
        "prototype_sha256": VV3_PROTOTYPE_SHA256,
        "stock": {"sha256": VV3_SOURCE_SHA256, "size": VV3_STOCK_SIZE, "imagebase": "0x400000"},
        "exporter_manifest": {
            "path": "manifests/exporter.json",
            "size": 1,
            "sha256": "0" * 64,
        },
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
        self.assertFalse(result.static_valid)
        self.assertFalse(result.runtime_ready)
        self.assertFalse(result.valid)
        self.assertFalse(result.publication_ready)
        self.assertFalse(publication_ready_with_evidence(_bundle()))

    def test_authenticated_manifest_and_runtime_artifact_bind_static_validity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, _, _, _ = _authenticated_fixture(root)
            result = validate_evidence_file(path, catalog_root=root)
        self.assertTrue(result.static_valid)
        self.assertFalse(result.runtime_ready)
        self.assertFalse(result.valid)
        self.assertFalse(result.publication_ready)

    def test_cli_binds_explicit_catalog_root_and_remains_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, _, _, _ = _authenticated_fixture(root)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "validate_vv3_expanded_evidence.py"),
                    str(path),
                    "--catalog-root",
                    str(root),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(completed.returncode, 1)
        output = json.loads(completed.stdout)
        self.assertTrue(output["static_valid"])
        self.assertFalse(output["runtime_ready"])
        self.assertFalse(output["publication_ready"])

    def test_in_memory_fixture_can_never_be_static_valid(self) -> None:
        bundle = _bundle()
        bundle["provenance"]["producer"] = "untrusted fixture"
        result = validate_vv3_evidence(bundle)
        self.assertFalse(result.static_valid)
        self.assertTrue(any("canonical evidence file" in error for error in result.errors))

    def test_missing_runtime_artifact_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, _, _, artifact = _authenticated_fixture(root)
            artifact.unlink()
            result = validate_evidence_file(path, catalog_root=root)
        self.assertFalse(result.static_valid)
        self.assertTrue(any("runtime_artifacts[0] inventory failed" in error for error in result.errors))

    def test_runtime_artifact_declared_size_and_hash_must_match(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, _, _, artifact = _authenticated_fixture(root)
            artifact.write_bytes(b"substituted-runtime-artifact")
            result = validate_evidence_file(path, catalog_root=root)
        self.assertFalse(result.static_valid)
        self.assertTrue(any("declared size does not match" in error for error in result.errors))
        self.assertTrue(any("declared SHA-256 does not match" in error for error in result.errors))

    def test_runtime_artifact_mutation_between_inventory_reads_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, _, _, artifact = _authenticated_fixture(root)
            original_inventory = evidence_module.inventory_evidence_file
            calls = [0]

            def mutate_after_first_inventory(value: Path, *, root: Path) -> object:
                result = original_inventory(value, root=root)
                calls[0] += 1
                if calls[0] == 1:
                    artifact.write_bytes(b"mutated-after-inventory")
                return result

            with mock.patch.object(
                evidence_module,
                "inventory_evidence_file",
                side_effect=mutate_after_first_inventory,
            ):
                result = validate_evidence_file(path, catalog_root=root)
        self.assertFalse(result.static_valid)
        self.assertTrue(any("changed between inventory reads" in error for error in result.errors))

    def test_runtime_artifact_symlink_substitution_fails_closed_when_supported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, _, _, artifact = _authenticated_fixture(root)
            replacement = root / "replacement.json"
            replacement.write_bytes(artifact.read_bytes())
            artifact.unlink()
            try:
                artifact.symlink_to(replacement)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"platform does not permit symlink creation: {exc}")
            self.assertTrue(artifact.is_symlink(), "symlink substitution returned without a symlink")
            result = validate_evidence_file(path, catalog_root=root)
        self.assertFalse(result.static_valid)
        self.assertTrue(any("symlink or reparse" in error for error in result.errors))

    def test_exporter_manifest_symlink_substitution_fails_closed_when_supported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, bundle, manifest_path, _ = _authenticated_fixture(root)
            replacement = root / "replacement-manifest.json"
            replacement.write_bytes(manifest_path.read_bytes())
            manifest_path.unlink()
            try:
                manifest_path.symlink_to(replacement)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"platform does not permit symlink creation: {exc}")
            self.assertTrue(manifest_path.is_symlink(), "symlink substitution returned without a symlink")
            result = validate_evidence_file(path, catalog_root=root)
        self.assertFalse(result.static_valid)
        self.assertTrue(any("symlink or reparse" in error for error in result.errors))

    def test_provenance_must_match_authenticated_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, bundle, _, _ = _authenticated_fixture(root)
            bundle["provenance"]["run_id"] = "substituted-run"
            path.write_bytes(canonical_json_bytes(bundle))
            result = validate_evidence_file(path, catalog_root=root)
        self.assertFalse(result.static_valid)
        self.assertTrue(any("provenance.run_id" in error for error in result.errors))

    def test_provenance_missing_or_extra_fields_fail_closed(self) -> None:
        for label in ("missing digest", "extra field"):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                path, bundle, _, _ = _authenticated_fixture(root)
                if label == "missing digest":
                    bundle["provenance"].pop("manifest_sha256")
                else:
                    bundle["provenance"]["unexpected"] = "reject"
                path.write_bytes(canonical_json_bytes(bundle))
                result = validate_evidence_file(path, catalog_root=root)
            self.assertFalse(result.static_valid)
            self.assertTrue(any("provenance" in error for error in result.errors), result.errors)

    def test_exporter_manifest_extra_field_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, bundle, manifest_path, _ = _authenticated_fixture(root)

            def add_extra(manifest: dict) -> None:
                manifest["unexpected"] = "reject"

            _rewrite_manifest_fixture(root, bundle, manifest_path, add_extra)
            result = validate_evidence_file(path, catalog_root=root)
        self.assertFalse(result.static_valid)
        self.assertTrue(any("contains unknown keys" in error for error in result.errors))

    def test_manifest_source_identity_and_digest_are_bound(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, bundle, manifest_path, _ = _authenticated_fixture(root)

            def substitute_source(manifest: dict) -> None:
                manifest["source_sha256"] = "A" * 64

            _rewrite_manifest_fixture(root, bundle, manifest_path, substitute_source)
            result = validate_evidence_file(path, catalog_root=root)
        self.assertFalse(result.static_valid)
        self.assertTrue(any("source_sha256 does not match VV3" in error for error in result.errors))

    def test_manifest_reordered_xrefs_fails_even_with_recomputed_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, bundle, manifest_path, _ = _authenticated_fixture(root)

            def reorder_xrefs(manifest: dict) -> None:
                manifest["operand_expectations"][0]["xrefs"].reverse()

            _rewrite_manifest_fixture(root, bundle, manifest_path, reorder_xrefs)
            result = validate_evidence_file(path, catalog_root=root)
        self.assertFalse(result.static_valid)
        self.assertTrue(any("xrefs must be in canonical order" in error for error in result.errors))

    def test_exact_operands_require_manifest_ea_and_complete_ordered_xrefs(self) -> None:
        mutations = {
            "substituted EA": lambda item: item.update({"ea": "0xDEADBEEF"}),
            "omitted xref": lambda item: item["xrefs"].pop(),
            "extra xref": lambda item: item["xrefs"].append({"ea": "0xDEAD0000", "kind": "code"}),
            "substituted xref": lambda item: item["xrefs"][0].update({"ea": "0xDEAD0001", "kind": "data"}),
            "reordered xrefs": lambda item: item["xrefs"].reverse(),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                path, bundle, _, _ = _authenticated_fixture(root)
                mutate(bundle["coverage"]["exact_stock_operands_xrefs"][0])
                path.write_bytes(canonical_json_bytes(bundle))
                result = validate_evidence_file(path, catalog_root=root)
            self.assertFalse(result.static_valid)
            self.assertTrue(
                any("authenticated exporter manifest" in error for error in result.errors),
                result.errors,
            )

    def test_runtime_hashes_use_canonical_uppercase(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, bundle, _, _ = _authenticated_fixture(root)
            bundle["runtime_evidence"][0]["sha256"] = bundle["runtime_evidence"][0]["sha256"].lower()
            path.write_bytes(canonical_json_bytes(bundle))
            result = validate_evidence_file(path, catalog_root=root)
        self.assertFalse(result.static_valid)
        self.assertTrue(any("canonical uppercase" in error for error in result.errors))

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
        self.assertFalse(result.static_valid)
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
        manifest_schema = json.loads(
            (ROOT / "data" / "vv3_expanded_256_exporter_manifest.schema.json").read_text(encoding="utf-8")
        )
        self.assertEqual(schema["properties"]["source_sha256"]["const"], VV3_SOURCE_SHA256)
        self.assertEqual(schema["properties"]["prototype_sha256"]["const"], VV3_PROTOTYPE_SHA256)
        self.assertEqual(
            schema["properties"]["coverage"]["properties"]["loader_abi_branches"]["$ref"],
            "#/$defs/loader_section",
        )
        self.assertFalse(schema["$defs"]["loader_claim"]["additionalProperties"])
        self.assertFalse(schema["$defs"]["observation"]["additionalProperties"])
        self.assertIn("not", schema["$defs"]["catalog_path"])
        self.assertEqual(manifest_schema["properties"]["schema"]["const"], EXPORTER_MANIFEST_SCHEMA)
        self.assertEqual(manifest_schema["properties"]["producer"]["const"], EXPORTER_PRODUCER)
        self.assertIn("operand_expectations", manifest_schema["required"])
        self.assertEqual(manifest_schema["properties"]["source_size"]["const"], VV3_STOCK_SIZE)

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
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, bundle, _, _ = _authenticated_fixture(root)
            original_validate = evidence_module._validate_vv3_evidence

            def mutate_after_read(value: dict, **kwargs: object) -> object:
                result = original_validate(value, **kwargs)
                mutated = copy.deepcopy(value)
                mutated["ida_export"]["references"] = [{"mutation": True}]
                path.write_bytes(canonical_json_bytes(mutated))
                return result

            with mock.patch.object(evidence_module, "_validate_vv3_evidence", side_effect=mutate_after_read):
                result = validate_evidence_file(path, catalog_root=root)
            self.assertFalse(result.valid)
            self.assertTrue(
                any("changed between inventory, read, and validation" in error for error in result.errors),
                result.errors,
            )


if __name__ == "__main__":
    unittest.main()
