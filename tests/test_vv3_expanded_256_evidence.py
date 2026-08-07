from __future__ import annotations

import copy
import unittest

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
    publication_ready_with_evidence,
    validate_vv3_evidence,
)


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


if __name__ == "__main__":
    unittest.main()
