"""Validate the disabled VV3 Expanded-256 stored-index/padding evidence gate.

This validator reads repository contracts and explicitly supplied evidence
files only.  It never launches the game, opens saves, emits native code, or
changes runtime/player/publication state.
"""

from __future__ import annotations

from dataclasses import dataclass
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import stat
import sys
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv3_expanded_256_evidence import (  # noqa: E402
    REQUIRED_INDEX_PATHS,
    REQUIRED_PADDING_PATHS,
    VV3_PROTOTYPE_SHA256,
    VV3_SOURCE_SHA256,
    canonical_json_bytes,
    load_evidence,
)
from vv3_expanded_256_runtime_capture import (  # noqa: E402
    RECEIPT_SCHEMA,
    STAGE_REQUIREMENTS,
    authenticate_exporter_anchor,
)


CONTRACT_PATH = ROOT / "data" / "vv3_expanded_256_stored_index_gate.json"
CONTRACT_SCHEMA = "vvfp.vv3_expanded_256_stored_index_gate"
CONTRACT_SCHEMA_VERSION = 1
CANDIDATE_SCHEMA = "vvfp.vv3_expanded_256_stored_index_evidence"
CANDIDATE_SCHEMA_VERSION = 1
BASE_EVIDENCE_COMMIT = "8444df9c314f8ee9a6a29930a9d1be1e70e6adb7"
RECEIPT_HARNESS_COMMIT = "0940bb5328217aee7a08963ce22c7dddc3ca4503"
SERIALIZER_ID = "serializer"
RECEIPT_STAGE_IDS = ("padding_unreachable_records", "stored_index_sentinel_paths")
PADDING_INDICES = (256, 257, 258, 259)
SOURCE_PATHS = (
    "data/vv3_expanded_256_evidence.schema.json",
    "data/vv3_expanded_256_exporter_manifest.schema.json",
    "data/vv3_expanded_256_runtime_receipt.schema.json",
    "data/vv3_expanded_256_stored_index_evidence.schema.json",
    "data/vv3_expanded_256_stored_index_gate.schema.json",
    "src/vv3_expanded_256_evidence.py",
    "src/vv3_expanded_256_runtime_capture.py",
)
_SHA = re.compile(r"^[0-9A-F]{64}$")
_HEX = re.compile(r"^(?:0x)?[0-9A-Fa-f]+$")
_HEX_BYTES = re.compile(r"^(?:[0-9A-F]{2})+$")
_REPARSE_POINT = 0x0400


class StoredIndexGateError(ValueError):
    """Raised for malformed, incomplete, synthetic, or unauthenticated evidence."""


@dataclass(frozen=True)
class CandidateValidation:
    errors: tuple[str, ...]
    structural_valid: bool
    authenticated_source: bool
    gate_ready: bool
    runtime_go: bool = False
    player_go: bool = False
    publication_ready: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "structural_valid": self.structural_valid,
            "authenticated_source": self.authenticated_source,
            "gate_ready": self.gate_ready,
            "runtime_go": self.runtime_go,
            "player_go": self.player_go,
            "publication_ready": self.publication_ready,
            "status": "STOP",
            "error_count": len(self.errors),
            "errors": list(self.errors),
        }


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise StoredIndexGateError(message)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        _require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load_json(path: Path, *, canonical: bool) -> Mapping[str, Any]:
    raw = Path(path).read_bytes()
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StoredIndexGateError(f"invalid JSON: {path}") from exc
    _require(isinstance(value, Mapping), f"JSON root must be an object: {path}")
    if canonical:
        _require(raw == canonical_json_bytes(value), f"candidate evidence JSON is not canonical: {path}")
    return value


def _canonical_digest(document: Mapping[str, Any]) -> str:
    body = copy.deepcopy(dict(document))
    integrity = body.get("integrity")
    if isinstance(integrity, dict):
        integrity.pop("canonical_sha256", None)
    return hashlib.sha256(canonical_json_bytes(body)).hexdigest().upper()


def _is_reparse(result: os.stat_result) -> bool:
    return stat.S_ISLNK(result.st_mode) or bool(
        getattr(result, "st_file_attributes", 0) & _REPARSE_POINT
    )


def _safe_repo_path(value: object) -> str:
    _require(isinstance(value, str) and bool(value), "source path must be non-empty")
    assert isinstance(value, str)
    windows = PureWindowsPath(value)
    parts = value.split("/")
    _require("\\" not in value and not value.startswith("/") and not windows.drive and not windows.root, "source path must be repository-relative")
    _require(all(part not in {"", ".", ".."} and ":" not in part for part in parts), "source path contains traversal or a stream")
    return value


def _sha(value: object, label: str) -> str:
    _require(isinstance(value, str) and _SHA.fullmatch(value) is not None, f"{label} must be uppercase SHA-256")
    return str(value)


def _strict_int(value: object, label: str) -> int:
    _require(type(value) is int and int(value) >= 0, f"{label} must be a nonnegative integer")
    return int(value)


def _hex_int(value: object, label: str) -> int:
    if type(value) is int:
        _require(int(value) >= 0, f"{label} must not be negative")
        return int(value)
    _require(isinstance(value, str) and _HEX.fullmatch(value) is not None, f"{label} must be a hexadecimal integer")
    return int(str(value), 16)


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), f"{label} must be an object")
    return value  # type: ignore[return-value]


def _exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    _require(actual == expected, f"{label} keys mismatch: missing={sorted(expected - actual)} extra={sorted(actual - expected)}")


def _hash_repo_file(relative: str, root: Path) -> str:
    path = root.joinpath(*PurePosixPath(relative).parts)
    result = os.lstat(path)
    _require(not _is_reparse(result) and stat.S_ISREG(result.st_mode), f"source provenance path is not a regular no-follow file: {relative}")
    try:
        text = path.read_bytes().decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise StoredIndexGateError(f"source provenance path is not valid UTF-8: {relative}") from exc
    canonical = text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
    return hashlib.sha256(canonical).hexdigest().upper()


def authenticate_candidate_anchor(evidence_path: Path, catalog_root: Path) -> dict[str, object]:
    """Authenticate the 8444 bundle and expose its verified artifact IDs."""

    anchor = authenticate_exporter_anchor(evidence_path, catalog_root)
    bundle = load_evidence(evidence_path)
    runtime_evidence = bundle.get("runtime_evidence")
    _require(isinstance(runtime_evidence, list) and bool(runtime_evidence), "authenticated evidence artifact catalog is empty")
    artifact_ids: list[str] = []
    for item in runtime_evidence:
        record = _mapping(item, "runtime_evidence item")
        artifact_id = record.get("id")
        _require(isinstance(artifact_id, str) and bool(artifact_id), "authenticated evidence artifact ID is invalid")
        artifact_ids.append(artifact_id)
    _require(len(set(artifact_ids)) == len(artifact_ids), "authenticated evidence artifact IDs are duplicated")
    return {**anchor, "artifact_ids": sorted(artifact_ids)}


def validate_contract(document: Mapping[str, Any], *, root: Path = ROOT) -> dict[str, object]:
    """Validate the repository-owned STOP contract and its dependency hashes."""

    _exact_keys(document, {"schema", "schema_version", "contract_id", "contract_status", "integrity", "publication", "source_provenance", "evidence_policy", "reviewed_expectations", "paths", "serializer_binding", "padding_contract", "runtime_evidence"}, "contract")
    _require(document.get("schema") == CONTRACT_SCHEMA and document.get("schema_version") == CONTRACT_SCHEMA_VERSION, "stored-index gate schema is unsupported")
    _require(document.get("contract_id") == "x3-vv3-expanded-256-stored-index-padding-gate", "stored-index contract identity mismatch")
    _require(document.get("contract_status") == "static_contract_only", "stored-index contract is not disabled")
    integrity = _mapping(document.get("integrity"), "integrity")
    _exact_keys(integrity, {"canonicalization", "canonical_sha256"}, "integrity")
    _require(_sha(integrity.get("canonical_sha256"), "integrity.canonical_sha256") == _canonical_digest(document), "stored-index contract canonical digest is stale")
    publication = _mapping(document.get("publication"), "publication")
    _exact_keys(publication, {"enabled", "runtime_go", "player_go", "eligible", "reason"}, "publication")
    _require(publication.get("enabled") is False and publication.get("runtime_go") is False and publication.get("player_go") is False and publication.get("eligible") is False, "stored-index publication boundary was relaxed")

    source = _mapping(document.get("source_provenance"), "source_provenance")
    _exact_keys(source, {"authenticated_evidence_commit", "runtime_receipt_commit", "source_sha256", "prototype_sha256", "receipt_schema", "required_receipt_stage_ids", "source_files"}, "source_provenance")
    _require(source.get("authenticated_evidence_commit") == BASE_EVIDENCE_COMMIT, "8444 authenticated-evidence dependency mismatch")
    _require(source.get("runtime_receipt_commit") == RECEIPT_HARNESS_COMMIT, "0940 runtime-receipt dependency mismatch")
    _require(source.get("source_sha256") == VV3_SOURCE_SHA256 and source.get("prototype_sha256") == VV3_PROTOTYPE_SHA256, "VV3 source identity mismatch")
    _require(source.get("receipt_schema") == RECEIPT_SCHEMA, "runtime receipt schema identity mismatch")
    stage_ids = [stage_id for stage_id, _ in STAGE_REQUIREMENTS]
    _require(all(stage_id in stage_ids for stage_id in RECEIPT_STAGE_IDS), "runtime receipt stages are missing")
    _require(source.get("required_receipt_stage_ids") == list(RECEIPT_STAGE_IDS), "runtime receipt stage binding mismatch")
    source_files = source.get("source_files")
    _require(isinstance(source_files, list) and len(source_files) == 7, "source provenance file set is incomplete")
    seen_paths: set[str] = set()
    observed_source_paths: list[str] = []
    for item in source_files:
        record = _mapping(item, "source_provenance.source_files item")
        _exact_keys(record, {"path", "sha256"}, "source_provenance.source_files item")
        relative = _safe_repo_path(record.get("path"))
        _require(relative not in seen_paths, f"source provenance path is duplicated: {relative}")
        seen_paths.add(relative)
        observed_source_paths.append(relative)
        _require(_hash_repo_file(relative, root) == _sha(record.get("sha256"), f"source provenance {relative}"), f"source provenance hash mismatch: {relative}")
    _require(observed_source_paths == list(SOURCE_PATHS), "source provenance files are reordered, missing, or substituted")

    policy = _mapping(document.get("evidence_policy"), "evidence_policy")
    _exact_keys(policy, {"game_id", "required_evidence_class", "forbidden_assumptions", "require_complete_xref_sets", "require_authenticated_exporter_provenance"}, "evidence_policy")
    _require(policy.get("game_id") == "vv3", "stored-index policy is not VV3-specific")
    _require(policy.get("required_evidence_class") == "authenticated_vv3_native_observation", "stored-index evidence class is not exact")
    _require(policy.get("forbidden_assumptions") == ["byte_0xFF_sentinel_inference", "vv5_dword_minus_one_borrowing", "cross_game_width_or_sentinel_borrowing"], "forbidden inference policy changed")
    _require(policy.get("require_complete_xref_sets") is True and policy.get("require_authenticated_exporter_provenance") is True, "xref/provenance policy was relaxed")

    expectations = _mapping(document.get("reviewed_expectations"), "reviewed_expectations")
    _exact_keys(expectations, {"status", "reason", "widths", "sentinels", "exact_eas", "complete_xrefs"}, "reviewed_expectations")
    _require(expectations.get("status") == "absent" and expectations.get("widths") is None and expectations.get("sentinels") is None and expectations.get("exact_eas") is None and expectations.get("complete_xrefs") is None, "unreviewed stored-index expectations were populated")

    paths = document.get("paths")
    _require(isinstance(paths, list) and len(paths) == len(REQUIRED_INDEX_PATHS), "stored-index path set is incomplete")
    for ordinal, (expected_id, raw) in enumerate(zip(REQUIRED_INDEX_PATHS, paths), start=1):
        item = _mapping(raw, f"paths[{ordinal - 1}]")
        _exact_keys(item, {"ordinal", "id", "status", "expected_width_bits", "expected_sentinel", "expected_observation_eas", "expected_complete_xrefs", "record_255", "evidence_refs"}, f"paths[{ordinal - 1}]")
        _require(item.get("ordinal") == ordinal and item.get("id") == expected_id, "stored-index paths are reordered or substituted")
        _require(item.get("status") == "evidence_absent" and item.get("expected_width_bits") is None and item.get("expected_sentinel") is None, f"stored-index path overclaims reviewed evidence: {expected_id}")
        _require(item.get("expected_observation_eas") == [] and item.get("expected_complete_xrefs") == [] and item.get("evidence_refs") == [], f"stored-index path contains unauthenticated evidence: {expected_id}")
        record_255 = _mapping(item.get("record_255"), f"paths.{expected_id}.record_255")
        _require(record_255 == {"status": "unproven", "accepted": None, "saveable": None, "observation_refs": []}, f"record 255 is overclaimed: {expected_id}")

    serializer = _mapping(document.get("serializer_binding"), "serializer_binding")
    _require(serializer == {"id": SERIALIZER_ID, "status": "evidence_absent", "record_255_saved": None, "padding_saved": None, "expected_observation_eas": [], "expected_complete_xrefs": [], "evidence_refs": []}, "serializer binding is overclaimed or incomplete")
    padding = _mapping(document.get("padding_contract"), "padding_contract")
    _exact_keys(padding, {"logical_max_index", "indices", "status", "reachable", "saveable", "required_paths", "observation_refs"}, "padding_contract")
    _require(padding.get("logical_max_index") == 255 and padding.get("indices") == list(PADDING_INDICES), "padding index contract changed")
    _require(padding.get("status") == "evidence_absent" and padding.get("reachable") is None and padding.get("saveable") is None and padding.get("observation_refs") == [], "padding reachability/saveability is overclaimed")
    _require(padding.get("required_paths") == list(REQUIRED_PADDING_PATHS), "padding proof path set is incomplete")
    runtime = _mapping(document.get("runtime_evidence"), "runtime_evidence")
    _require(runtime == {"status": "absent", "candidate": None, "authenticated_source": False, "structural_valid": False, "gate_ready": False}, "canonical runtime evidence must remain absent and STOP")
    return {"contract_valid": True, "paths": len(paths), "gate_ready": False, "runtime_go": False, "player_go": False, "publication_ready": False, "status": "STOP"}


def _validate_observations(
    observations: object,
    label: str,
    errors: list[str],
    allowed_artifacts: set[str],
) -> None:
    try:
        _require(isinstance(observations, list) and bool(observations), f"{label} must contain observations")
        seen_locations: set[tuple[int, int]] = set()
        for index, raw in enumerate(observations):
            item = _mapping(raw, f"{label}[{index}]")
            _exact_keys(item, {"ea", "file_offset", "raw_bytes", "artifact_id", "xref_set_complete", "xrefs"}, f"{label}[{index}]")
            ea = _hex_int(item.get("ea"), f"{label}[{index}].ea")
            offset = _hex_int(item.get("file_offset"), f"{label}[{index}].file_offset")
            _require((ea, offset) not in seen_locations, f"{label} contains a duplicate observation")
            seen_locations.add((ea, offset))
            _require(isinstance(item.get("raw_bytes"), str) and _HEX_BYTES.fullmatch(str(item.get("raw_bytes"))) is not None, f"{label}[{index}].raw_bytes must be uppercase bytes")
            _require(isinstance(item.get("artifact_id"), str) and bool(item.get("artifact_id")), f"{label}[{index}].artifact_id is missing")
            _require(item.get("artifact_id") in allowed_artifacts, f"{label}[{index}].artifact_id is not authenticated")
            _require(item.get("xref_set_complete") is True, f"{label}[{index}] xref set is not declared complete")
            xrefs = item.get("xrefs")
            _require(isinstance(xrefs, list) and bool(xrefs), f"{label}[{index}].xrefs must be complete and nonempty")
            previous: tuple[int, str] | None = None
            seen: set[tuple[int, str]] = set()
            seen_eas: set[int] = set()
            for xref_index, raw_xref in enumerate(xrefs):
                xref = _mapping(raw_xref, f"{label}[{index}].xrefs[{xref_index}]")
                _exact_keys(xref, {"ea", "kind"}, f"{label}[{index}].xrefs[{xref_index}]")
                key = (_hex_int(xref.get("ea"), f"{label}[{index}].xrefs[{xref_index}].ea"), str(xref.get("kind")))
                _require(isinstance(xref.get("kind"), str) and bool(xref.get("kind")), f"{label}[{index}].xrefs[{xref_index}].kind is missing")
                _require(key not in seen and key[0] not in seen_eas and (previous is None or key > previous), f"{label}[{index}].xrefs are duplicated or not canonical")
                seen.add(key)
                seen_eas.add(key[0])
                previous = key
    except StoredIndexGateError as exc:
        errors.append(str(exc))


def validate_candidate(
    candidate: Mapping[str, Any],
    contract: Mapping[str, Any],
    authenticated_anchor: Mapping[str, object] | None,
) -> CandidateValidation:
    """Validate exact candidate shape; remain STOP while reviewed expectations are absent."""

    errors: list[str] = []
    authenticated = authenticated_anchor is not None
    allowed_artifacts = set(authenticated_anchor.get("artifact_ids", [])) if authenticated_anchor else set()
    try:
        _exact_keys(candidate, {"schema", "schema_version", "status", "evidence_class", "synthetic", "ambiguous", "incomplete", "provenance", "paths", "serializer_binding", "padding_records", "receipt_binding"}, "candidate")
        _require(candidate.get("schema") == CANDIDATE_SCHEMA and candidate.get("schema_version") == CANDIDATE_SCHEMA_VERSION, "candidate schema is unsupported")
        _require(candidate.get("status") == "observed" and candidate.get("evidence_class") == "authenticated_vv3_native_observation", "candidate evidence class/status is not exact")
        _require(candidate.get("synthetic") is False and candidate.get("ambiguous") is False and candidate.get("incomplete") is False, "candidate is synthetic, ambiguous, or incomplete")
        provenance = _mapping(candidate.get("provenance"), "provenance")
        _exact_keys(provenance, {"game_id", "source_sha256", "prototype_sha256", "evidence_sha256", "exporter_manifest_sha256", "exporter_manifest_file_sha256", "exporter_producer", "exporter_run_id", "authenticated_by"}, "provenance")
        _require(authenticated_anchor is not None, "candidate source provenance was not authenticated from files")
        assert authenticated_anchor is not None
        _require(bool(allowed_artifacts), "authenticated evidence artifact catalog is empty")
        _require(provenance.get("game_id") == "vv3" and provenance.get("authenticated_by") == "validate_evidence_file", "candidate provenance is not authenticated VV3 evidence")
        for key in ("source_sha256", "prototype_sha256", "evidence_sha256", "exporter_manifest_sha256", "exporter_manifest_file_sha256", "exporter_producer", "exporter_run_id"):
            _require(provenance.get(key) == authenticated_anchor.get(key), f"candidate provenance mismatch: {key}")
    except StoredIndexGateError as exc:
        errors.append(str(exc))

    paths = candidate.get("paths")
    if not isinstance(paths, list) or len(paths) != len(REQUIRED_INDEX_PATHS):
        errors.append("candidate must contain exactly all ten stored-index paths")
        paths = []
    for ordinal, expected_id in enumerate(REQUIRED_INDEX_PATHS, start=1):
        if ordinal > len(paths):
            break
        try:
            item = _mapping(paths[ordinal - 1], f"paths[{ordinal - 1}]")
            _exact_keys(item, {"ordinal", "id", "status", "derivation", "width_bits", "sentinel", "record_255", "observations"}, f"paths[{ordinal - 1}]")
            _require(item.get("ordinal") == ordinal and item.get("id") == expected_id and item.get("status") == "observed", "candidate paths are reordered, substituted, or pending")
            derivation = _mapping(item.get("derivation"), f"paths.{expected_id}.derivation")
            _require(derivation == {"game_id": "vv3", "source_kind": "authenticated_native_observation", "cross_game_source": None, "inferred": False}, f"{expected_id} width/sentinel is inferred or cross-game")
            width = _strict_int(item.get("width_bits"), f"paths.{expected_id}.width_bits")
            _require(width in {8, 16, 32, 64}, f"paths.{expected_id}.width_bits is not explicit")
            sentinel = _mapping(item.get("sentinel"), f"paths.{expected_id}.sentinel")
            _exact_keys(sentinel, {"kind", "width_bits", "signed", "value", "raw_bytes", "source", "observation_refs"}, f"paths.{expected_id}.sentinel")
            _require(sentinel.get("kind") in {"none", "value"} and sentinel.get("width_bits") == width, f"paths.{expected_id}.sentinel encoding mismatch")
            _require(type(sentinel.get("signed")) is bool and sentinel.get("source") == "authenticated_vv3_observation", f"paths.{expected_id}.sentinel source/sign is not exact")
            refs = sentinel.get("observation_refs")
            _require(isinstance(refs, list) and bool(refs) and all(isinstance(ref, str) and ref for ref in refs), f"paths.{expected_id}.sentinel evidence refs are missing")
            _require(set(refs).issubset(allowed_artifacts), f"paths.{expected_id}.sentinel evidence refs are not authenticated")
            if sentinel.get("kind") == "value":
                _require(type(sentinel.get("value")) is int, f"paths.{expected_id}.sentinel value must be an explicit integer")
                raw_bytes = sentinel.get("raw_bytes")
                _require(isinstance(raw_bytes, str) and _HEX_BYTES.fullmatch(raw_bytes) is not None and len(raw_bytes) == width // 4, f"paths.{expected_id}.sentinel raw bytes do not match width")
            else:
                _require(sentinel.get("value") is None and sentinel.get("raw_bytes") is None, f"paths.{expected_id}.sentinel none must not invent bytes/value")
            record = _mapping(item.get("record_255"), f"paths.{expected_id}.record_255")
            _exact_keys(record, {"accepted", "saveable", "observation_refs"}, f"paths.{expected_id}.record_255")
            _require(record.get("accepted") is True and record.get("saveable") is True and isinstance(record.get("observation_refs"), list) and bool(record.get("observation_refs")), f"paths.{expected_id} lacks exact record-255 acceptance/save evidence")
            _require(set(record.get("observation_refs", [])).issubset(allowed_artifacts), f"paths.{expected_id}.record_255 evidence refs are not authenticated")
            _validate_observations(item.get("observations"), f"paths.{expected_id}.observations", errors, allowed_artifacts)
        except StoredIndexGateError as exc:
            errors.append(str(exc))

    try:
        serializer = _mapping(candidate.get("serializer_binding"), "serializer_binding")
        _exact_keys(serializer, {"id", "status", "record_255_saved", "padding_saved", "observations"}, "serializer_binding")
        _require(serializer.get("id") == SERIALIZER_ID and serializer.get("status") == "observed", "serializer binding is missing")
        _require(serializer.get("record_255_saved") is True and serializer.get("padding_saved") is False, "serializer record-255/padding behavior is not exact")
        _validate_observations(serializer.get("observations"), "serializer_binding.observations", errors, allowed_artifacts)
    except StoredIndexGateError as exc:
        errors.append(str(exc))

    padding = candidate.get("padding_records")
    if not isinstance(padding, list) or len(padding) != len(PADDING_INDICES):
        errors.append("candidate must contain exactly padding records 256-259")
    else:
        for expected_index, raw in zip(PADDING_INDICES, padding):
            try:
                item = _mapping(raw, f"padding_records.{expected_index}")
                _exact_keys(item, {"index", "reachable", "saveable", "required_path_refs", "observation_refs"}, f"padding_records.{expected_index}")
                _require(item.get("index") == expected_index and item.get("reachable") is False and item.get("saveable") is False, f"padding record {expected_index} is not proved unreachable/non-saveable")
                _require(item.get("required_path_refs") == list(REQUIRED_PADDING_PATHS), f"padding record {expected_index} proof paths are incomplete")
                _require(isinstance(item.get("observation_refs"), list) and bool(item.get("observation_refs")), f"padding record {expected_index} evidence refs are missing")
                _require(set(item.get("observation_refs", [])).issubset(allowed_artifacts), f"padding record {expected_index} evidence refs are not authenticated")
            except StoredIndexGateError as exc:
                errors.append(str(exc))

    try:
        receipt = _mapping(candidate.get("receipt_binding"), "receipt_binding")
        _exact_keys(receipt, {"schema", "schema_sha256", "receipt_id", "stage_ids", "player_confirmed"}, "receipt_binding")
        source = _mapping(contract.get("source_provenance"), "contract.source_provenance")
        receipt_hash = next(item["sha256"] for item in source["source_files"] if item["path"] == "data/vv3_expanded_256_runtime_receipt.schema.json")
        _require(receipt.get("schema") == RECEIPT_SCHEMA and receipt.get("schema_sha256") == receipt_hash, "candidate receipt schema binding mismatch")
        _require(isinstance(receipt.get("receipt_id"), str) and bool(receipt.get("receipt_id")), "candidate receipt ID is missing")
        _require(receipt.get("stage_ids") == list(RECEIPT_STAGE_IDS), "candidate receipt stage binding is incomplete")
        _require(receipt.get("player_confirmed") is True, "candidate lacks explicit player validation")
    except (StoredIndexGateError, StopIteration, TypeError, KeyError) as exc:
        errors.append(str(exc) or "candidate receipt binding is invalid")

    structural_valid = not errors
    expectations = contract.get("reviewed_expectations")
    reviewed = isinstance(expectations, Mapping) and expectations.get("status") == "reviewed"
    gate_ready = structural_valid and authenticated and reviewed
    return CandidateValidation(tuple(errors), structural_valid, authenticated, gate_ready)


def load_contract(path: Path = CONTRACT_PATH) -> Mapping[str, Any]:
    return _load_json(path, canonical=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the disabled VV3 stored-index/padding evidence gate.")
    parser.add_argument("--contract", type=Path, default=CONTRACT_PATH)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--authenticated-evidence-json", type=Path)
    parser.add_argument("--catalog-root", type=Path)
    args = parser.parse_args(argv)
    try:
        contract = load_contract(args.contract)
        summary = validate_contract(contract)
        if args.candidate is None:
            print(json.dumps(summary, sort_keys=True))
            return 0
        _require(args.authenticated_evidence_json is not None and args.catalog_root is not None, "candidate validation requires --authenticated-evidence-json and --catalog-root")
        candidate = _load_json(args.candidate, canonical=True)
        anchor = authenticate_candidate_anchor(args.authenticated_evidence_json, args.catalog_root)
        result = validate_candidate(candidate, contract, anchor)
        print(json.dumps(result.as_dict(), sort_keys=True))
        return 1
    except (OSError, StoredIndexGateError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"contract_valid": False, "gate_ready": False, "runtime_go": False, "player_go": False, "publication_ready": False, "status": "STOP", "error": str(exc)}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
