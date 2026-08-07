"""Fail-closed validation for future VV3 Expanded-256 evidence bundles.

This module consumes a JSON bundle assembled from the read-only IDA exporter
and reconciler.  It validates provenance, exact-build identity, guarded stock
operands, native coverage categories, and runtime-gate attestations.  It never
opens a game executable, save, or game folder.

The existing static contract remains authoritative.  In particular,
``publication_ready()`` from :mod:`vv3_expanded_256_contract` is still false
on the current checkout, so this module cannot enable publication by itself.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from vv3_expanded_256_contract import (
    VV3_RECORD_BOUND_PATCHES,
    VV3_SOURCE_SHA256,
    VV3_STOCK_SAVE_PATCHES,
    publication_ready as static_publication_ready,
)


EVIDENCE_SCHEMA = "vvfp.vv3_expanded_256_evidence"
EVIDENCE_SCHEMA_VERSION = 1
VV3_PROTOTYPE_SHA256 = (
    "6EE3361A7AC35F441763647C1E2FC9EC49569DE5EF372BDB41D243D03002D601"
)
VV3_STOCK_SIZE = 831_488
VV3_REQUIRED_PATCHES = {
    **VV3_STOCK_SAVE_PATCHES,
    **VV3_RECORD_BOUND_PATCHES,
}

REQUIRED_LOADER_CLAIMS = (
    "load_hook_0x28949",
    "fallback_body_0x7B3B1",
    "post_load_copy_0x28961",
    "stock_size_branch",
    "expanded_size_branch",
    "failure_branch",
)
REQUIRED_INDEX_PATHS = (
    "selection",
    "sorted_roster",
    "detail_navigation",
    "planner_action_queue",
    "pairing_pregnancy",
    "birth_death",
    "skeleton_memorial",
    "event_puzzle",
    "statistics",
    "callbacks",
)
REQUIRED_CONSUMER_CLAIMS = (
    "selectors",
    "planner_action_queue",
    "callbacks",
    "statistics",
    "serializer",
)
REQUIRED_PADDING_PATHS = (
    "construction",
    "selection",
    "serialization",
    "population_counting",
    "statistics",
)
REQUIRED_RUNTIME_GATES = (
    "load_hang_resolved",
    "stock_import_expanded_reload",
    "offline_catch_up",
    "failed_load_nonmutation",
    "late_record_matrix",
    "player_runtime_validation",
)

_HEX = re.compile(r"^(?:0x)?[0-9A-Fa-f]+$")
_SHA256 = re.compile(r"^[0-9A-Fa-f]{64}$")
_STATUS = "verified"


@dataclass(frozen=True)
class EvidenceValidation:
    """Machine-readable result for a candidate evidence bundle."""

    errors: tuple[str, ...]
    static_valid: bool
    runtime_ready: bool
    publication_ready: bool

    @property
    def valid(self) -> bool:
        """Return true only when static evidence and runtime gates both pass."""

        return not self.errors and self.static_valid and self.runtime_ready

    def as_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "static_valid": self.static_valid,
            "runtime_ready": self.runtime_ready,
            "publication_ready": self.publication_ready,
            "error_count": len(self.errors),
            "errors": list(self.errors),
        }


def _error(errors: list[str], message: str) -> None:
    errors.append(message)


def _hex_int(value: Any, field: str, errors: list[str]) -> int | None:
    if isinstance(value, bool):
        _error(errors, f"{field} must be a hexadecimal integer")
        return None
    if isinstance(value, int):
        if value < 0:
            _error(errors, f"{field} must not be negative")
            return None
        return value
    if isinstance(value, str) and _HEX.fullmatch(value):
        return int(value, 16)
    _error(errors, f"{field} must be a hexadecimal integer")
    return None


def _sha256(value: Any, field: str, errors: list[str]) -> str | None:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        _error(errors, f"{field} must be a 64-hex SHA-256 digest")
        return None
    return value.upper()


def _hex_bytes(value: Any, field: str, errors: list[str]) -> bytes | None:
    if not isinstance(value, str) or len(value) % 2 or not value:
        _error(errors, f"{field} must be a non-empty even-length hex byte string")
        return None
    try:
        return bytes.fromhex(value)
    except ValueError:
        _error(errors, f"{field} must contain only hexadecimal bytes")
        return None


def _require_mapping(value: Any, field: str, errors: list[str]) -> Mapping[str, Any] | None:
    if not isinstance(value, Mapping):
        _error(errors, f"{field} must be an object")
        return None
    return value


def _require_nonempty_string(value: Any, field: str, errors: list[str]) -> str | None:
    if not isinstance(value, str) or not value.strip():
        _error(errors, f"{field} must be a non-empty string")
        return None
    return value


def _validate_provenance(bundle: Mapping[str, Any], errors: list[str]) -> None:
    provenance = _require_mapping(bundle.get("provenance"), "provenance", errors)
    if provenance is None:
        return
    if provenance.get("status") != "complete":
        _error(errors, "provenance.status must be complete")
    for key in ("synthetic", "ambiguous", "incomplete"):
        if provenance.get(key) is not False:
            _error(errors, f"provenance.{key} must be false")
    if provenance.get("reconciled") is not True:
        _error(errors, "provenance.reconciled must be true")
    if provenance.get("input_kind") != "exact_stock_executable":
        _error(errors, "provenance.input_kind must be exact_stock_executable")
    _require_nonempty_string(provenance.get("producer"), "provenance.producer", errors)


def _validate_fingerprint(bundle: Mapping[str, Any], errors: list[str]) -> None:
    if bundle.get("schema") != EVIDENCE_SCHEMA:
        _error(errors, "schema identifier does not match the VV3 evidence schema")
    if bundle.get("schema_version") != EVIDENCE_SCHEMA_VERSION:
        _error(errors, "schema_version is unsupported")
    if bundle.get("game_id") != "vv3":
        _error(errors, "game_id must be vv3")

    source = _sha256(bundle.get("source_sha256"), "source_sha256", errors)
    prototype = _sha256(bundle.get("prototype_sha256"), "prototype_sha256", errors)
    if source is not None and source != VV3_SOURCE_SHA256:
        _error(errors, "source_sha256 does not match the reviewed VV3 stock build")
    if prototype is not None and prototype != VV3_PROTOTYPE_SHA256:
        _error(errors, "prototype_sha256 does not match the reviewed VV3 prototype")

    stock = _require_mapping(bundle.get("stock"), "stock", errors)
    if stock is None:
        return
    stock_hash = _sha256(stock.get("sha256"), "stock.sha256", errors)
    if stock_hash is not None and stock_hash != VV3_SOURCE_SHA256:
        _error(errors, "stock.sha256 does not match source_sha256")
    if stock.get("size") != VV3_STOCK_SIZE:
        _error(errors, f"stock.size must be {VV3_STOCK_SIZE}")
    _hex_int(stock.get("imagebase"), "stock.imagebase", errors)


def _validate_reconcile(bundle: Mapping[str, Any], errors: list[str]) -> None:
    reconcile = _require_mapping(bundle.get("reconcile"), "reconcile", errors)
    if reconcile is None:
        return
    if reconcile.get("game_id") != "vv3":
        _error(errors, "reconcile.game_id must be vv3")

    manifest = _require_mapping(reconcile.get("manifest"), "reconcile.manifest", errors)
    if manifest is not None:
        if manifest.get("source_sha256") != VV3_SOURCE_SHA256:
            _error(errors, "reconcile.manifest.source_sha256 mismatches VV3")
        if manifest.get("prototype_sha256") != VV3_PROTOTYPE_SHA256:
            _error(errors, "reconcile.manifest.prototype_sha256 mismatches VV3")
        if manifest.get("declared_patch_count") != 1263:
            _error(errors, "reconcile.manifest.declared_patch_count must be 1263")
        if manifest.get("actual_patch_count") != 1263:
            _error(errors, "reconcile.manifest.actual_patch_count must be 1263")
        if manifest.get("guard_errors") != []:
            _error(errors, "reconcile.manifest.guard_errors must be empty")
        if manifest.get("overlaps") != []:
            _error(errors, "reconcile.manifest.overlaps must be empty")

    ida_summary = _require_mapping(reconcile.get("ida_export"), "reconcile.ida_export", errors)
    if ida_summary is not None:
        if ida_summary.get("unmatched_moving_references") != []:
            _error(errors, "reconcile.ida_export.unmatched_moving_references must be empty")
        if ida_summary.get("unpatched_population_sized_constants") != []:
            _error(errors, "reconcile.ida_export.unpatched_population_sized_constants must be empty")


def _validate_export(bundle: Mapping[str, Any], errors: list[str]) -> None:
    exported = _require_mapping(bundle.get("ida_export"), "ida_export", errors)
    if exported is None:
        return
    heads = exported.get("decoded_instruction_heads")
    if not isinstance(heads, int) or heads <= 0:
        _error(errors, "ida_export.decoded_instruction_heads must be positive")
    segment_bytes = exported.get("executable_segment_bytes")
    if not isinstance(segment_bytes, int) or segment_bytes <= 0:
        _error(errors, "ida_export.executable_segment_bytes must be positive")
    if not isinstance(exported.get("references"), list):
        _error(errors, "ida_export.references must be a list")
    if not isinstance(exported.get("constants"), list):
        _error(errors, "ida_export.constants must be a list")


def _validate_observation(
    observation: Any,
    field: str,
    errors: list[str],
) -> tuple[int, int] | None:
    item = _require_mapping(observation, field, errors)
    if item is None:
        return None
    if item.get("status") != _STATUS:
        _error(errors, f"{field}.status must be verified")
    for key in ("synthetic", "ambiguous", "incomplete"):
        if item.get(key) is not False:
            _error(errors, f"{field}.{key} must be false")
    ea = _hex_int(item.get("ea"), f"{field}.ea", errors)
    file_offset = _hex_int(item.get("file_offset"), f"{field}.file_offset", errors)
    raw = _hex_bytes(item.get("raw_bytes"), f"{field}.raw_bytes", errors)
    xrefs = item.get("xrefs")
    if not isinstance(xrefs, list) or not xrefs:
        _error(errors, f"{field}.xrefs must be a non-empty list")
    else:
        seen_xrefs: set[int] = set()
        for index, xref in enumerate(xrefs):
            xref_map = _require_mapping(xref, f"{field}.xrefs[{index}]", errors)
            if xref_map is None:
                continue
            xref_ea = _hex_int(xref_map.get("ea"), f"{field}.xrefs[{index}].ea", errors)
            _require_nonempty_string(xref_map.get("kind"), f"{field}.xrefs[{index}].kind", errors)
            if xref_ea is not None:
                if xref_ea in seen_xrefs:
                    _error(errors, f"{field}.xrefs contains duplicate EA 0x{xref_ea:X}")
                seen_xrefs.add(xref_ea)
    if ea is None or file_offset is None or raw is None:
        return None
    return ea, file_offset


def _claims_for(
    coverage: Mapping[str, Any],
    category: str,
    errors: list[str],
) -> list[Mapping[str, Any]]:
    section = _require_mapping(coverage.get(category), f"coverage.{category}", errors)
    if section is None:
        return []
    if section.get("status") != _STATUS:
        _error(errors, f"coverage.{category}.status must be verified")
    claims = section.get("claims")
    if not isinstance(claims, list):
        _error(errors, f"coverage.{category}.claims must be a list")
        return []
    result: list[Mapping[str, Any]] = []
    seen: set[str] = set()
    for index, claim in enumerate(claims):
        claim_map = _require_mapping(claim, f"coverage.{category}.claims[{index}]", errors)
        if claim_map is None:
            continue
        claim_id = claim_map.get("id")
        if not isinstance(claim_id, str) or not claim_id:
            _error(errors, f"coverage.{category}.claims[{index}].id is required")
            continue
        if claim_id in seen:
            _error(errors, f"coverage.{category} contains duplicate claim {claim_id}")
        seen.add(claim_id)
        result.append(claim_map)
    return result


def _validate_claim_observations(
    category: str,
    claims: Sequence[Mapping[str, Any]],
    required_ids: Sequence[str],
    errors: list[str],
) -> dict[str, Mapping[str, Any]]:
    by_id = {str(claim["id"]): claim for claim in claims if "id" in claim}
    for required in required_ids:
        if required not in by_id:
            _error(errors, f"coverage.{category} is missing required claim {required}")
    seen_locations: set[tuple[int, int]] = set()
    for claim_id, claim in by_id.items():
        prefix = f"coverage.{category}.{claim_id}"
        if claim.get("status") != _STATUS:
            _error(errors, f"{prefix}.status must be verified")
        for key in ("synthetic", "ambiguous", "incomplete"):
            if claim.get(key) is not False:
                _error(errors, f"{prefix}.{key} must be false")
        observations = claim.get("observations")
        if not isinstance(observations, list) or not observations:
            _error(errors, f"{prefix}.observations must be a non-empty list")
            continue
        for index, observation in enumerate(observations):
            location = _validate_observation(observation, f"{prefix}.observations[{index}]", errors)
            if location is not None:
                if location in seen_locations:
                    _error(errors, f"{category} contains duplicate observation at {location}")
                seen_locations.add(location)
    return by_id


def _validate_loader(coverage: Mapping[str, Any], errors: list[str]) -> None:
    claims = _claims_for(coverage, "loader_abi_branches", errors)
    by_id = _validate_claim_observations(
        "loader_abi_branches", claims, REQUIRED_LOADER_CLAIMS, errors
    )
    for claim_id, claim in by_id.items():
        prefix = f"coverage.loader_abi_branches.{claim_id}"
        abi = claim.get("abi")
        if not isinstance(abi, Mapping):
            _error(errors, f"{prefix}.abi must be an object")
        else:
            _require_nonempty_string(abi.get("calling_convention"), f"{prefix}.abi.calling_convention", errors)
            _require_nonempty_string(abi.get("return_semantics"), f"{prefix}.abi.return_semantics", errors)
        branches = claim.get("branches")
        if not isinstance(branches, list) or not branches:
            _error(errors, f"{prefix}.branches must be a non-empty list")
        else:
            for index, branch in enumerate(branches):
                branch_map = _require_mapping(branch, f"{prefix}.branches[{index}]", errors)
                if branch_map is None:
                    continue
                for key in ("condition", "outcome", "target"):
                    _require_nonempty_string(branch_map.get(key), f"{prefix}.branches[{index}].{key}", errors)


def _validate_indices(coverage: Mapping[str, Any], errors: list[str]) -> None:
    claims = _claims_for(coverage, "stored_index_width_sentinel_paths", errors)
    by_id = _validate_claim_observations(
        "stored_index_width_sentinel_paths", claims, REQUIRED_INDEX_PATHS, errors
    )
    for claim_id, claim in by_id.items():
        prefix = f"coverage.stored_index_width_sentinel_paths.{claim_id}"
        width = claim.get("width_bits")
        if not isinstance(width, int) or width not in {8, 16, 32, 64}:
            _error(errors, f"{prefix}.width_bits must be an explicit 8/16/32/64-bit width")
        sentinel = _require_mapping(claim.get("sentinel"), f"{prefix}.sentinel", errors)
        if sentinel is not None:
            kind = sentinel.get("kind")
            if kind not in {"none", "value"}:
                _error(errors, f"{prefix}.sentinel.kind must be none or value")
            if kind == "value" and not isinstance(sentinel.get("value"), int):
                _error(errors, f"{prefix}.sentinel.value must be an integer")
        _require_nonempty_string(claim.get("semantics"), f"{prefix}.semantics", errors)


def _validate_consumers(coverage: Mapping[str, Any], errors: list[str]) -> None:
    claims = _claims_for(coverage, "selectors_queues_callbacks_stats_serializer", errors)
    by_id = _validate_claim_observations(
        "selectors_queues_callbacks_stats_serializer", claims, REQUIRED_CONSUMER_CLAIMS, errors
    )
    for claim_id, claim in by_id.items():
        _require_nonempty_string(
            claim.get("semantics"),
            f"coverage.selectors_queues_callbacks_stats_serializer.{claim_id}.semantics",
            errors,
        )


def _validate_padding(coverage: Mapping[str, Any], errors: list[str]) -> None:
    claims = _claims_for(coverage, "padding_reachability", errors)
    by_id = _validate_claim_observations(
        "padding_reachability", claims, REQUIRED_PADDING_PATHS, errors
    )
    for claim_id, claim in by_id.items():
        prefix = f"coverage.padding_reachability.{claim_id}"
        if claim.get("reachable") is not False:
            _error(errors, f"{prefix}.reachable must be false")
        if claim.get("max_logical_index") != 255:
            _error(errors, f"{prefix}.max_logical_index must be 255")
        if claim.get("padding_indices") != [256, 257, 258, 259]:
            _error(errors, f"{prefix}.padding_indices must be [256, 257, 258, 259]")


def _validate_exact_operands(coverage: Mapping[str, Any], errors: list[str]) -> None:
    raw = coverage.get("exact_stock_operands_xrefs")
    if not isinstance(raw, list):
        _error(errors, "coverage.exact_stock_operands_xrefs must be a list")
        return
    by_offset: dict[int, Mapping[str, Any]] = {}
    for index, item in enumerate(raw):
        field = f"coverage.exact_stock_operands_xrefs[{index}]"
        item_map = _require_mapping(item, field, errors)
        if item_map is None:
            continue
        offset = _hex_int(item_map.get("file_offset"), f"{field}.file_offset", errors)
        location = _validate_observation(item_map, field, errors)
        if offset is None or location is None:
            continue
        if offset in by_offset:
            _error(errors, f"exact stock operand offset 0x{offset:X} is duplicated")
        by_offset[offset] = item_map
    for offset, expected in VV3_REQUIRED_PATCHES.items():
        item = by_offset.get(offset)
        if item is None:
            _error(errors, f"exact stock operand 0x{offset:X} is missing")
            continue
        actual = _hex_bytes(item.get("raw_bytes"), f"exact stock operand 0x{offset:X}.raw_bytes", errors)
        expected_bytes = bytes.fromhex(expected["before"])
        if actual is not None and actual != expected_bytes:
            _error(errors, f"exact stock operand 0x{offset:X} raw bytes mismatch the contract")
    unexpected = sorted(set(by_offset) - set(VV3_REQUIRED_PATCHES))
    for offset in unexpected:
        _error(errors, f"exact stock operand 0x{offset:X} is not a reviewed VV3 operand")


def _validate_runtime_gates(bundle: Mapping[str, Any], errors: list[str]) -> bool:
    runtime_evidence = bundle.get("runtime_evidence")
    catalog_ids: set[str] = set()
    catalog_valid = True
    if not isinstance(runtime_evidence, list):
        _error(errors, "runtime_gates.evidence_catalog must be a list")
        catalog_valid = False
    else:
        for index, item in enumerate(runtime_evidence):
            field = f"runtime_gates.evidence_catalog[{index}]"
            evidence = _require_mapping(item, field, errors)
            if evidence is None:
                continue
            evidence_id = evidence.get("id")
            if not isinstance(evidence_id, str) or not evidence_id:
                _error(errors, f"{field}.id must be a non-empty string")
                catalog_valid = False
                continue
            if evidence_id in catalog_ids:
                _error(errors, f"runtime evidence id {evidence_id} is duplicated")
                catalog_valid = False
            catalog_ids.add(evidence_id)
            if evidence.get("status") != _STATUS:
                _error(errors, f"{field}.status must be verified")
                catalog_valid = False
            for key in ("synthetic", "ambiguous", "incomplete"):
                if evidence.get(key) is not False:
                    _error(errors, f"{field}.{key} must be false")
                    catalog_valid = False
            _require_nonempty_string(evidence.get("kind"), f"{field}.kind", errors)
            if not isinstance(evidence.get("kind"), str) or not evidence.get("kind").strip():
                catalog_valid = False
            if _sha256(evidence.get("sha256"), f"{field}.sha256", errors) is None:
                catalog_valid = False

    gates = _require_mapping(bundle.get("runtime_gates"), "runtime_gates", errors)
    if gates is None:
        return False
    ready = True
    for gate_id in REQUIRED_RUNTIME_GATES:
        gate = _require_mapping(gates.get(gate_id), f"runtime_gates.{gate_id}", errors)
        if gate is None:
            ready = False
            continue
        if gate.get("status") != _STATUS:
            _error(errors, f"runtime_gates.{gate_id}.status must be verified")
            ready = False
        for key in ("synthetic", "ambiguous", "incomplete"):
            if gate.get(key) is not False:
                _error(errors, f"runtime_gates.{gate_id}.{key} must be false")
                ready = False
        gate_evidence_ids = gate.get("evidence_ids")
        if not isinstance(gate_evidence_ids, list) or not gate_evidence_ids or not all(
            isinstance(value, str) and value for value in gate_evidence_ids
        ):
            _error(errors, f"runtime_gates.{gate_id}.evidence_ids must be non-empty")
            ready = False
        elif any(value not in catalog_ids for value in gate_evidence_ids):
            missing = sorted(set(gate_evidence_ids) - catalog_ids)
            if missing:
                _error(errors, f"runtime_gates.{gate_id}.evidence_ids are not in the evidence catalog: {missing}")
                ready = False
    unexpected = set(gates) - set(REQUIRED_RUNTIME_GATES)
    if unexpected:
        _error(errors, f"runtime_gates contains unknown keys: {sorted(unexpected)}")
        ready = False
    return ready and catalog_valid


def validate_vv3_evidence(bundle: Mapping[str, Any]) -> EvidenceValidation:
    """Validate a future IDA/reconciler evidence bundle without game files."""

    errors: list[str] = []
    if not isinstance(bundle, Mapping):
        return EvidenceValidation(("evidence bundle must be an object",), False, False, False)

    _validate_provenance(bundle, errors)
    _validate_fingerprint(bundle, errors)
    _validate_reconcile(bundle, errors)
    _validate_export(bundle, errors)
    coverage = _require_mapping(bundle.get("coverage"), "coverage", errors)
    if coverage is not None:
        _validate_loader(coverage, errors)
        _validate_indices(coverage, errors)
        _validate_consumers(coverage, errors)
        _validate_padding(coverage, errors)
        _validate_exact_operands(coverage, errors)
    runtime_ready = _validate_runtime_gates(bundle, errors)
    static_valid = not errors or all(error.startswith("runtime_gates.") for error in errors)
    # Static validity must not accidentally pass when a required runtime object
    # is absent; the distinction is useful only for diagnostics.
    if "runtime_gates" not in bundle:
        static_valid = False
    publication = not errors and static_valid and runtime_ready and static_publication_ready()
    return EvidenceValidation(tuple(errors), static_valid, runtime_ready, publication)


def publication_ready_with_evidence(bundle: Mapping[str, Any]) -> bool:
    """Return the conservative publication decision for a validated bundle."""

    result = validate_vv3_evidence(bundle)
    return result.publication_ready


def load_evidence(path: Path) -> Mapping[str, Any]:
    """Load JSON evidence; callers still receive validation errors separately."""

    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError("evidence JSON root must be an object")
    return value
