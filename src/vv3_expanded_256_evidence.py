"""Fail-closed validation for future VV3 Expanded-256 evidence bundles.

This module consumes a canonical JSON bundle assembled from the read-only IDA
exporter and reconciler.  File-bound validation additionally authenticates a
root-relative exporter manifest and every runtime-gate artifact with stable
no-follow inventories and re-reads.  It validates provenance, exact-build
identity, guarded stock operands, native coverage categories, and runtime-gate
attestations.  It never opens a game executable, save, or game folder.

The existing static contract remains authoritative.  In particular,
``publication_ready()`` from :mod:`vv3_expanded_256_contract` is still false
on the current checkout, so this module cannot enable publication by itself.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
from pathlib import PurePosixPath
from pathlib import PureWindowsPath
import re
import stat
from typing import Any, Mapping, Sequence

from vv3_expanded_256_contract import (
    VV3_RECORD_BOUND_PATCHES,
    VV3_SOURCE_SHA256,
    VV3_STOCK_SAVE_PATCHES,
    publication_ready as static_publication_ready,
)


EVIDENCE_SCHEMA = "vvfp.vv3_expanded_256_evidence"
EVIDENCE_SCHEMA_VERSION = 1
EXPORTER_MANIFEST_SCHEMA = "vvfp.vv3_expanded_256_exporter_manifest"
EXPORTER_MANIFEST_SCHEMA_VERSION = 1
EXPORTER_PRODUCER = "vv3-ida-exporter"
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
_SHA256 = re.compile(r"^[0-9A-F]{64}$")
_STATUS = "verified"
_REPARSE_POINT = 0x0400

_BUNDLE_KEYS = {
    "schema",
    "schema_version",
    "game_id",
    "provenance",
    "source_sha256",
    "prototype_sha256",
    "stock",
    "exporter_manifest",
    "ida_export",
    "reconcile",
    "coverage",
    "runtime_evidence",
    "runtime_gates",
}
_PROVENANCE_KEYS = {
    "producer",
    "input_kind",
    "status",
    "synthetic",
    "ambiguous",
    "incomplete",
    "reconciled",
    "run_id",
    "manifest_sha256",
    "manifest_file_sha256",
}
_EXPORTER_MANIFEST_CATALOG_KEYS = {"path", "size", "sha256"}
_EXPORTER_MANIFEST_KEYS = {
    "schema",
    "schema_version",
    "producer",
    "exporter_version",
    "run_id",
    "input_kind",
    "status",
    "synthetic",
    "ambiguous",
    "incomplete",
    "reconciled",
    "source_sha256",
    "source_size",
    "prototype_sha256",
    "operand_expectations",
    "manifest_sha256",
}
_OPERAND_EXPECTATION_KEYS = {"file_offset", "ea", "raw_bytes", "xrefs"}
_STOCK_KEYS = {"sha256", "size", "imagebase"}
_IDA_EXPORT_KEYS = {
    "decoded_instruction_heads",
    "executable_segment_bytes",
    "references",
    "constants",
}
_RECONCILE_KEYS = {"game_id", "manifest", "ida_export"}
_MANIFEST_KEYS = {
    "source_sha256",
    "prototype_sha256",
    "declared_patch_count",
    "actual_patch_count",
    "guard_errors",
    "overlaps",
}
_RECONCILE_IDA_KEYS = {
    "unmatched_moving_references",
    "unpatched_population_sized_constants",
}
_COVERAGE_KEYS = {
    "loader_abi_branches",
    "stored_index_width_sentinel_paths",
    "selectors_queues_callbacks_stats_serializer",
    "padding_reachability",
    "exact_stock_operands_xrefs",
}
_SECTION_KEYS = {"status", "claims"}
_COMMON_CLAIM_KEYS = {
    "id",
    "status",
    "synthetic",
    "ambiguous",
    "incomplete",
    "observations",
    "semantics",
}
_OBSERVATION_KEYS = {
    "status",
    "synthetic",
    "ambiguous",
    "incomplete",
    "ea",
    "file_offset",
    "raw_bytes",
    "xrefs",
}
_XREF_KEYS = {"ea", "kind"}
_ABI_KEYS = {"calling_convention", "return_semantics"}
_BRANCH_KEYS = {"condition", "outcome", "target"}
_SENTINEL_KEYS = {"kind", "value"}
_RUNTIME_EVIDENCE_KEYS = {
    "id",
    "status",
    "synthetic",
    "ambiguous",
    "incomplete",
    "kind",
    "path",
    "size",
    "sha256",
}
_RUNTIME_GATE_KEYS = {"status", "synthetic", "ambiguous", "incomplete", "evidence_ids"}


@dataclass(frozen=True)
class EvidenceFileInventory:
    """Stable identity and digest captured for one evidence artifact."""

    path: str
    size: int
    sha256: str
    identity: tuple[int, int]
    signature: tuple[int, int, int, int]

    def as_dict(self) -> dict[str, Any]:
        """Return only portable catalog fields, excluding OS identity details."""

        return {"path": self.path, "size": self.size, "sha256": self.sha256}


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


def _reject_extra_keys(
    value: Mapping[str, Any],
    allowed: set[str],
    field: str,
    errors: list[str],
) -> None:
    unexpected = sorted(str(key) for key in value if key not in allowed)
    if unexpected:
        _error(errors, f"{field} contains unknown keys: {unexpected}")


def _strict_int(value: Any, field: str, errors: list[str], *, minimum: int | None = None) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        _error(errors, f"{field} must be an integer")
        return None
    if minimum is not None and value < minimum:
        _error(errors, f"{field} must be at least {minimum}")
        return None
    return value


def _canonical_catalog_path(value: Any) -> str:
    """Return a portable relative catalog path or raise a validation error."""

    if not isinstance(value, str) or not value:
        raise ValueError("catalog path must be a non-empty string")
    if "\x00" in value or any(ord(character) < 0x20 for character in value):
        raise ValueError("catalog path contains control characters")
    if "\\" in value:
        raise ValueError("catalog path must use forward slashes")
    windows = PureWindowsPath(value)
    lowered = value.casefold()
    if (
        value.startswith("/")
        or windows.drive
        or windows.root
        or lowered.startswith(("//?/", "//./"))
    ):
        raise ValueError("catalog path must be relative and non-reparse")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("catalog path contains traversal or ambiguous segments")
    if any(":" in part for part in parts):
        raise ValueError("catalog path contains a drive or stream separator")
    if any(PureWindowsPath(part).is_reserved() for part in parts):
        raise ValueError("catalog path contains a reserved or reparse-like name")
    return value


def _validate_catalog_path(value: Any, field: str, errors: list[str]) -> str | None:
    try:
        return _canonical_catalog_path(value)
    except ValueError as exc:
        _error(errors, f"{field} is invalid: {exc}")
        return None


def _is_reparse_like(stat_result: os.stat_result) -> bool:
    return stat.S_ISLNK(stat_result.st_mode) or bool(
        getattr(stat_result, "st_file_attributes", 0) & _REPARSE_POINT
    )


def _file_identity(stat_result: os.stat_result) -> tuple[int, int]:
    return int(stat_result.st_dev), int(stat_result.st_ino)


def _file_signature(stat_result: os.stat_result) -> tuple[int, int, int, int]:
    return (
        *_file_identity(stat_result),
        int(stat_result.st_size),
        int(stat_result.st_mtime_ns),
    )


def _validated_catalog_root(root: Path) -> Path:
    """Resolve a regular directory root without following a reparse root."""

    root = Path(root)
    root_stat = os.lstat(root)
    if _is_reparse_like(root_stat):
        raise ValueError("catalog root must not be a symlink or reparse point")
    if not stat.S_ISDIR(root_stat.st_mode):
        raise ValueError("catalog root must be a directory")
    return root.resolve(strict=True)


def _stable_file_read(path: Path, *, catalog_root: Path | None = None) -> tuple[bytes, EvidenceFileInventory]:
    """Read and hash a regular file while detecting replacement or mutation."""

    relative_path: str | None = None
    target = path
    if catalog_root is not None:
        relative_path = _canonical_catalog_path(str(path))
        root = _validated_catalog_root(catalog_root)
        target = root.joinpath(*relative_path.split("/"))
        resolved = target.resolve(strict=True)
        try:
            if os.path.commonpath((str(root), str(resolved))) != str(root):
                raise ValueError("catalog path resolves outside its root")
        except ValueError as exc:
            raise ValueError("catalog path resolves outside its root") from exc
        current = root
        for part in relative_path.split("/"):
            current = current / part
            current_stat = os.lstat(current)
            if _is_reparse_like(current_stat):
                raise ValueError("catalog path traverses a reparse-like entry")
    target_stat = os.lstat(target)
    if _is_reparse_like(target_stat):
        raise ValueError("evidence file must not be a symlink or reparse point")
    if not stat.S_ISREG(target_stat.st_mode):
        raise ValueError("evidence file must be a regular file")

    digest = hashlib.sha256()
    chunks: list[bytes] = []
    with target.open("rb") as stream:
        before = os.fstat(stream.fileno())
        if _is_reparse_like(before):
            raise ValueError("opened evidence file is a reparse point")
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            chunks.append(chunk)
        after = os.fstat(stream.fileno())
    after_path_stat = os.lstat(target)
    before_signature = _file_signature(before)
    after_signature = _file_signature(after)
    if before_signature != after_signature:
        raise ValueError("evidence file identity or metadata changed during hash read")
    if _is_reparse_like(after_path_stat) or _file_signature(after_path_stat) != after_signature:
        raise ValueError("evidence file identity changed after hash read")
    inventory = EvidenceFileInventory(
        relative_path or str(path),
        len(b"".join(chunks)),
        digest.hexdigest().upper(),
        _file_identity(after),
        after_signature,
    )
    return b"".join(chunks), inventory


def inventory_evidence_file(path: Path, *, root: Path) -> EvidenceFileInventory:
    """Inventory a catalog artifact without allowing traversal or reparse paths."""

    _, inventory = _stable_file_read(path, catalog_root=root)
    return inventory


def _load_exporter_manifest(
    bundle: Mapping[str, Any],
    *,
    catalog_root: Path,
    errors: list[str],
) -> tuple[Mapping[str, Any] | None, EvidenceFileInventory | None]:
    catalog = _validate_exporter_manifest_catalog(bundle, errors)
    if catalog is None:
        return None, None
    path, declared_size, declared_hash = catalog
    try:
        raw, inventory = _stable_file_read(PurePosixPath(path), catalog_root=catalog_root)
    except (OSError, ValueError) as exc:
        _error(errors, f"exporter manifest inventory failed for {path}: {exc}")
        return None, None
    if inventory.path != path:
        _error(errors, "exporter manifest path does not match its canonical catalog path")
    if inventory.size != declared_size:
        _error(errors, f"exporter manifest size mismatch for {path}")
    if inventory.sha256 != declared_hash:
        _error(errors, f"exporter manifest SHA-256 mismatch for {path}")
    try:
        manifest_value = _parse_canonical_json(raw)
    except ValueError as exc:
        _error(errors, f"exporter manifest JSON is not canonical: {exc}")
        return None, inventory
    _validate_exporter_manifest(manifest_value, errors)
    return manifest_value, inventory


def _inventory_runtime_artifacts(
    bundle: Mapping[str, Any],
    *,
    catalog_root: Path,
    errors: list[str],
) -> dict[str, EvidenceFileInventory]:
    raw = bundle.get("runtime_evidence")
    if not isinstance(raw, list):
        return {}
    inventories: dict[str, EvidenceFileInventory] = {}
    for index, item in enumerate(raw):
        field = f"runtime_artifacts[{index}]"
        if not isinstance(item, Mapping):
            continue
        evidence_id = item.get("id")
        path = _validate_catalog_path(item.get("path"), f"{field}.path", errors)
        if not isinstance(evidence_id, str) or not evidence_id or path is None:
            continue
        try:
            inventory = inventory_evidence_file(PurePosixPath(path), root=catalog_root)
        except (OSError, ValueError) as exc:
            _error(errors, f"{field} inventory failed for {path}: {exc}")
            continue
        declared_size = _strict_int(item.get("size"), f"{field}.size", errors, minimum=0)
        declared_hash = _sha256(item.get("sha256"), f"{field}.sha256", errors)
        if inventory.path != path:
            _error(errors, f"{field} path does not match the canonical catalog path")
        if declared_size is not None and inventory.size != declared_size:
            _error(errors, f"{field} declared size does not match the inventory")
        if declared_hash is not None and inventory.sha256 != declared_hash:
            _error(errors, f"{field} declared SHA-256 does not match the inventory")
        inventories[evidence_id] = inventory
    return inventories


def _compare_artifact_inventories(
    first: Mapping[str, EvidenceFileInventory],
    second: Mapping[str, EvidenceFileInventory],
    errors: list[str],
) -> None:
    if set(first) != set(second):
        _error(errors, "runtime artifact catalog changed between inventory reads")
        return
    for evidence_id in sorted(first):
        if first[evidence_id] != second[evidence_id]:
            _error(errors, f"runtime artifact {evidence_id} changed between inventory reads")


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key!r}")
        result[key] = value
    return result


def canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    """Serialize evidence JSON deterministically for hash-bound artifacts."""

    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"evidence JSON cannot be canonicalized: {exc}") from exc


def canonical_exporter_manifest_bytes(manifest: Mapping[str, Any]) -> bytes:
    """Serialize the exporter manifest body, excluding its self-digest."""

    body = dict(manifest)
    body.pop("manifest_sha256", None)
    return canonical_json_bytes(body)


def _parse_canonical_json(raw: bytes) -> Mapping[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_json_keys)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"evidence JSON is not valid or contains duplicate keys: {exc}") from exc
    if not isinstance(value, Mapping):
        raise ValueError("evidence JSON root must be an object")
    if raw != canonical_json_bytes(value):
        raise ValueError("evidence JSON must use canonical key ordering and separators")
    return value


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
        _error(errors, f"{field} must be a canonical uppercase 64-hex SHA-256 digest")
        return None
    return value


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


def _validate_exporter_manifest_catalog(
    bundle: Mapping[str, Any],
    errors: list[str],
) -> tuple[str, int, str] | None:
    catalog = _require_mapping(bundle.get("exporter_manifest"), "exporter_manifest", errors)
    if catalog is None:
        return None
    _reject_extra_keys(catalog, _EXPORTER_MANIFEST_CATALOG_KEYS, "exporter_manifest", errors)
    path = _validate_catalog_path(catalog.get("path"), "exporter_manifest.path", errors)
    size = _strict_int(catalog.get("size"), "exporter_manifest.size", errors, minimum=1)
    digest = _sha256(catalog.get("sha256"), "exporter_manifest.sha256", errors)
    if path is None or size is None or digest is None:
        return None
    return path, size, digest


def _validate_exporter_manifest(
    manifest: Mapping[str, Any],
    errors: list[str],
) -> Mapping[str, Any]:
    _reject_extra_keys(manifest, _EXPORTER_MANIFEST_KEYS, "exporter_manifest.file", errors)
    if manifest.get("schema") != EXPORTER_MANIFEST_SCHEMA:
        _error(errors, "exporter_manifest.file.schema is unsupported")
    schema_version = _strict_int(
        manifest.get("schema_version"),
        "exporter_manifest.file.schema_version",
        errors,
    )
    if schema_version is not None and schema_version != EXPORTER_MANIFEST_SCHEMA_VERSION:
        _error(errors, "exporter_manifest.file.schema_version is unsupported")
    if manifest.get("producer") != EXPORTER_PRODUCER:
        _error(errors, f"exporter_manifest.file.producer must be {EXPORTER_PRODUCER}")
    _require_nonempty_string(
        manifest.get("exporter_version"),
        "exporter_manifest.file.exporter_version",
        errors,
    )
    _require_nonempty_string(manifest.get("run_id"), "exporter_manifest.file.run_id", errors)
    if manifest.get("input_kind") != "exact_stock_executable":
        _error(errors, "exporter_manifest.file.input_kind must be exact_stock_executable")
    if manifest.get("status") != "complete":
        _error(errors, "exporter_manifest.file.status must be complete")
    for key in ("synthetic", "ambiguous", "incomplete"):
        if manifest.get(key) is not False:
            _error(errors, f"exporter_manifest.file.{key} must be false")
    if manifest.get("reconciled") is not True:
        _error(errors, "exporter_manifest.file.reconciled must be true")

    source = _sha256(manifest.get("source_sha256"), "exporter_manifest.file.source_sha256", errors)
    if source is not None and source != VV3_SOURCE_SHA256:
        _error(errors, "exporter_manifest.file.source_sha256 does not match VV3")
    source_size = _strict_int(
        manifest.get("source_size"),
        "exporter_manifest.file.source_size",
        errors,
        minimum=1,
    )
    if source_size is not None and source_size != VV3_STOCK_SIZE:
        _error(errors, f"exporter_manifest.file.source_size must be {VV3_STOCK_SIZE}")
    prototype = _sha256(
        manifest.get("prototype_sha256"),
        "exporter_manifest.file.prototype_sha256",
        errors,
    )
    if prototype is not None and prototype != VV3_PROTOTYPE_SHA256:
        _error(errors, "exporter_manifest.file.prototype_sha256 does not match VV3")

    expectations = manifest.get("operand_expectations")
    seen_offsets: set[int] = set()
    previous_offset = -1
    if not isinstance(expectations, list) or not expectations:
        _error(errors, "exporter_manifest.file.operand_expectations must be a non-empty list")
        expectations = []
    for index, expectation in enumerate(expectations):
        field = f"exporter_manifest.file.operand_expectations[{index}]"
        item = _require_mapping(expectation, field, errors)
        if item is None:
            continue
        _reject_extra_keys(item, _OPERAND_EXPECTATION_KEYS, field, errors)
        offset = _hex_int(item.get("file_offset"), f"{field}.file_offset", errors)
        ea = _hex_int(item.get("ea"), f"{field}.ea", errors)
        raw_bytes = _hex_bytes(item.get("raw_bytes"), f"{field}.raw_bytes", errors)
        if offset is not None:
            if offset <= previous_offset:
                _error(errors, f"{field}.file_offset entries must be in canonical order")
            previous_offset = max(previous_offset, offset)
            if offset in seen_offsets:
                _error(errors, f"exporter manifest operand offset 0x{offset:X} is duplicated")
            seen_offsets.add(offset)
            expected_patch = VV3_REQUIRED_PATCHES.get(offset)
            if expected_patch is None:
                _error(errors, f"exporter manifest operand offset 0x{offset:X} is not reviewed")
            elif raw_bytes is not None and raw_bytes != bytes.fromhex(expected_patch["before"]):
                _error(errors, f"{field}.raw_bytes does not match the reviewed VV3 operand")
        xrefs = item.get("xrefs")
        if not isinstance(xrefs, list) or not xrefs:
            _error(errors, f"{field}.xrefs must be a non-empty list")
            continue
        seen_xrefs: set[tuple[int, str]] = set()
        seen_xref_eas: set[int] = set()
        previous_xref: tuple[int, str] | None = None
        for xref_index, xref in enumerate(xrefs):
            xref_field = f"{field}.xrefs[{xref_index}]"
            xref_map = _require_mapping(xref, xref_field, errors)
            if xref_map is None:
                continue
            _reject_extra_keys(xref_map, _XREF_KEYS, xref_field, errors)
            xref_ea = _hex_int(xref_map.get("ea"), f"{xref_field}.ea", errors)
            kind = _require_nonempty_string(xref_map.get("kind"), f"{xref_field}.kind", errors)
            if xref_ea is None or kind is None:
                continue
            key = (xref_ea, kind)
            if previous_xref is not None and key <= previous_xref:
                _error(errors, f"{field}.xrefs must be in canonical order")
            previous_xref = key
            if key in seen_xrefs or xref_ea in seen_xref_eas:
                _error(errors, f"{field}.xrefs contains a duplicate expected EA")
            seen_xrefs.add(key)
            seen_xref_eas.add(xref_ea)
        if ea is None:
            continue

    missing_offsets = sorted(set(VV3_REQUIRED_PATCHES) - seen_offsets)
    if missing_offsets:
        _error(errors, f"exporter manifest is missing reviewed operands: {missing_offsets}")
    unexpected_offsets = sorted(seen_offsets - set(VV3_REQUIRED_PATCHES))
    if unexpected_offsets:
        _error(errors, f"exporter manifest contains unexpected operands: {unexpected_offsets}")

    manifest_digest = _sha256(
        manifest.get("manifest_sha256"),
        "exporter_manifest.file.manifest_sha256",
        errors,
    )
    if manifest_digest is not None:
        calculated = hashlib.sha256(canonical_exporter_manifest_bytes(manifest)).hexdigest().upper()
        if manifest_digest != calculated:
            _error(errors, "exporter_manifest.file.manifest_sha256 does not match canonical manifest bytes")
    return manifest


def _validate_provenance(
    bundle: Mapping[str, Any],
    errors: list[str],
    *,
    exporter_manifest: Mapping[str, Any] | None = None,
    manifest_file_sha256: str | None = None,
) -> None:
    provenance = _require_mapping(bundle.get("provenance"), "provenance", errors)
    if provenance is None:
        return
    _reject_extra_keys(provenance, _PROVENANCE_KEYS, "provenance", errors)
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
    _require_nonempty_string(provenance.get("run_id"), "provenance.run_id", errors)
    manifest_digest = _sha256(provenance.get("manifest_sha256"), "provenance.manifest_sha256", errors)
    manifest_file_digest = _sha256(
        provenance.get("manifest_file_sha256"),
        "provenance.manifest_file_sha256",
        errors,
    )
    if exporter_manifest is None:
        _error(errors, "provenance exporter manifest has not been authenticated from a file")
        return
    if provenance.get("producer") != exporter_manifest.get("producer"):
        _error(errors, "provenance.producer does not match the authenticated exporter manifest")
    if provenance.get("run_id") != exporter_manifest.get("run_id"):
        _error(errors, "provenance.run_id does not match the authenticated exporter manifest")
    if manifest_digest is not None and manifest_digest != exporter_manifest.get("manifest_sha256"):
        _error(errors, "provenance.manifest_sha256 does not match the authenticated exporter manifest")
    if manifest_file_digest is not None and manifest_file_digest != manifest_file_sha256:
        _error(errors, "provenance.manifest_file_sha256 does not match the manifest file inventory")


def _validate_fingerprint(bundle: Mapping[str, Any], errors: list[str]) -> None:
    if bundle.get("schema") != EVIDENCE_SCHEMA:
        _error(errors, "schema identifier does not match the VV3 evidence schema")
    schema_version = _strict_int(bundle.get("schema_version"), "schema_version", errors)
    if schema_version is not None and schema_version != EVIDENCE_SCHEMA_VERSION:
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
    _reject_extra_keys(stock, _STOCK_KEYS, "stock", errors)
    stock_hash = _sha256(stock.get("sha256"), "stock.sha256", errors)
    if stock_hash is not None and stock_hash != VV3_SOURCE_SHA256:
        _error(errors, "stock.sha256 does not match source_sha256")
    stock_size = _strict_int(stock.get("size"), "stock.size", errors)
    if stock_size is not None and stock_size != VV3_STOCK_SIZE:
        _error(errors, f"stock.size must be {VV3_STOCK_SIZE}")
    _hex_int(stock.get("imagebase"), "stock.imagebase", errors)


def _validate_reconcile(bundle: Mapping[str, Any], errors: list[str]) -> None:
    reconcile = _require_mapping(bundle.get("reconcile"), "reconcile", errors)
    if reconcile is None:
        return
    _reject_extra_keys(reconcile, _RECONCILE_KEYS, "reconcile", errors)
    if reconcile.get("game_id") != "vv3":
        _error(errors, "reconcile.game_id must be vv3")

    manifest = _require_mapping(reconcile.get("manifest"), "reconcile.manifest", errors)
    if manifest is not None:
        _reject_extra_keys(manifest, _MANIFEST_KEYS, "reconcile.manifest", errors)
        if manifest.get("source_sha256") != VV3_SOURCE_SHA256:
            _error(errors, "reconcile.manifest.source_sha256 mismatches VV3")
        if manifest.get("prototype_sha256") != VV3_PROTOTYPE_SHA256:
            _error(errors, "reconcile.manifest.prototype_sha256 mismatches VV3")
        declared_count = _strict_int(
            manifest.get("declared_patch_count"),
            "reconcile.manifest.declared_patch_count",
            errors,
            minimum=0,
        )
        if declared_count is not None and declared_count != 1263:
            _error(errors, "reconcile.manifest.declared_patch_count must be 1263")
        actual_count = _strict_int(
            manifest.get("actual_patch_count"),
            "reconcile.manifest.actual_patch_count",
            errors,
            minimum=0,
        )
        if actual_count is not None and actual_count != 1263:
            _error(errors, "reconcile.manifest.actual_patch_count must be 1263")
        if manifest.get("guard_errors") != []:
            _error(errors, "reconcile.manifest.guard_errors must be empty")
        if manifest.get("overlaps") != []:
            _error(errors, "reconcile.manifest.overlaps must be empty")

    ida_summary = _require_mapping(reconcile.get("ida_export"), "reconcile.ida_export", errors)
    if ida_summary is not None:
        _reject_extra_keys(ida_summary, _RECONCILE_IDA_KEYS, "reconcile.ida_export", errors)
        if ida_summary.get("unmatched_moving_references") != []:
            _error(errors, "reconcile.ida_export.unmatched_moving_references must be empty")
        if ida_summary.get("unpatched_population_sized_constants") != []:
            _error(errors, "reconcile.ida_export.unpatched_population_sized_constants must be empty")


def _validate_export(bundle: Mapping[str, Any], errors: list[str]) -> None:
    exported = _require_mapping(bundle.get("ida_export"), "ida_export", errors)
    if exported is None:
        return
    _reject_extra_keys(exported, _IDA_EXPORT_KEYS, "ida_export", errors)
    heads = exported.get("decoded_instruction_heads")
    if _strict_int(heads, "ida_export.decoded_instruction_heads", errors, minimum=1) is None:
        _error(errors, "ida_export.decoded_instruction_heads must be positive")
    segment_bytes = exported.get("executable_segment_bytes")
    if _strict_int(segment_bytes, "ida_export.executable_segment_bytes", errors, minimum=1) is None:
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
    _reject_extra_keys(item, _OBSERVATION_KEYS, field, errors)
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
            _reject_extra_keys(xref_map, _XREF_KEYS, f"{field}.xrefs[{index}]", errors)
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
    if category != "exact_stock_operands_xrefs":
        _reject_extra_keys(section, _SECTION_KEYS, f"coverage.{category}", errors)
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
        allowed = set(_COMMON_CLAIM_KEYS)
        if category == "loader_abi_branches":
            allowed.update({"abi", "branches"})
        elif category == "stored_index_width_sentinel_paths":
            allowed.update({"width_bits", "sentinel"})
        elif category == "padding_reachability":
            allowed.update({"reachable", "max_logical_index", "padding_indices"})
        _reject_extra_keys(claim_map, allowed, f"coverage.{category}.claims[{index}]", errors)
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
            _reject_extra_keys(abi, _ABI_KEYS, f"{prefix}.abi", errors)
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
                _reject_extra_keys(branch_map, _BRANCH_KEYS, f"{prefix}.branches[{index}]", errors)
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
        if isinstance(width, bool) or not isinstance(width, int) or width not in {8, 16, 32, 64}:
            _error(errors, f"{prefix}.width_bits must be an explicit 8/16/32/64-bit width")
        sentinel = _require_mapping(claim.get("sentinel"), f"{prefix}.sentinel", errors)
        if sentinel is not None:
            _reject_extra_keys(sentinel, _SENTINEL_KEYS, f"{prefix}.sentinel", errors)
            kind = sentinel.get("kind")
            if kind not in {"none", "value"}:
                _error(errors, f"{prefix}.sentinel.kind must be none or value")
            if kind == "value" and (
                isinstance(sentinel.get("value"), bool) or not isinstance(sentinel.get("value"), int)
            ):
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


def _validate_exact_operands(
    coverage: Mapping[str, Any],
    errors: list[str],
    *,
    exporter_manifest: Mapping[str, Any] | None = None,
) -> None:
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

    if exporter_manifest is None:
        _error(errors, "exact stock operands require an authenticated exporter manifest")
        return
    expectations = exporter_manifest.get("operand_expectations")
    if not isinstance(expectations, list):
        _error(errors, "authenticated exporter manifest operand expectations are missing")
        return
    expected_by_offset: dict[int, Mapping[str, Any]] = {}
    for expectation in expectations:
        if not isinstance(expectation, Mapping):
            continue
        offset = _hex_int(expectation.get("file_offset"), "exporter manifest operand file_offset", errors)
        if offset is not None:
            expected_by_offset[offset] = expectation
    if set(expected_by_offset) != set(by_offset):
        _error(errors, "exact stock operand offsets do not match the authenticated exporter manifest")
    for offset, expected in expected_by_offset.items():
        actual = by_offset.get(offset)
        if actual is None:
            continue
        expected_ea = _hex_int(
            expected.get("ea"),
            f"authenticated exporter operand 0x{offset:X}.ea",
            errors,
        )
        actual_ea = _hex_int(actual.get("ea"), f"exact stock operand 0x{offset:X}.ea", errors)
        if expected_ea is not None and actual_ea is not None and expected_ea != actual_ea:
            _error(errors, f"exact stock operand 0x{offset:X} EA does not match the authenticated exporter manifest")
        expected_xrefs = expected.get("xrefs")
        actual_xrefs = actual.get("xrefs")
        if not isinstance(expected_xrefs, list) or not isinstance(actual_xrefs, list):
            continue

        def xref_tuple_list(value: list[Any], field: str) -> list[tuple[int, str]]:
            tuples: list[tuple[int, str]] = []
            for index, xref in enumerate(value):
                if not isinstance(xref, Mapping):
                    continue
                xref_ea = _hex_int(xref.get("ea"), f"{field}[{index}].ea", errors)
                kind = _require_nonempty_string(xref.get("kind"), f"{field}[{index}].kind", errors)
                if xref_ea is not None and kind is not None:
                    tuples.append((xref_ea, kind))
            return tuples

        expected_tuples = xref_tuple_list(
            expected_xrefs,
            f"authenticated exporter operand 0x{offset:X}.xrefs",
        )
        actual_tuples = xref_tuple_list(actual_xrefs, f"exact stock operand 0x{offset:X}.xrefs")
        if actual_tuples != expected_tuples:
            _error(errors, f"exact stock operand 0x{offset:X} xrefs do not match the authenticated exporter manifest")


def _validate_runtime_gates(bundle: Mapping[str, Any], errors: list[str]) -> bool:
    runtime_evidence = bundle.get("runtime_evidence")
    catalog_ids: set[str] = set()
    catalog_by_id: dict[str, tuple[str, str]] = {}
    catalog_paths: set[str] = set()
    catalog_hashes: dict[str, str] = {}
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
            _reject_extra_keys(evidence, _RUNTIME_EVIDENCE_KEYS, field, errors)
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
            evidence_path = _validate_catalog_path(evidence.get("path"), f"{field}.path", errors)
            if evidence_path is None:
                catalog_valid = False
            evidence_size = _strict_int(evidence.get("size"), f"{field}.size", errors, minimum=0)
            if evidence_size is None:
                catalog_valid = False
            evidence_hash = _sha256(evidence.get("sha256"), f"{field}.sha256", errors)
            if evidence_hash is None:
                catalog_valid = False
            if evidence_path is not None:
                if evidence_path in catalog_paths:
                    _error(errors, f"runtime evidence path {evidence_path} is duplicated")
                    catalog_valid = False
                catalog_paths.add(evidence_path)
            if evidence_hash is not None:
                prior_id = catalog_hashes.get(evidence_hash)
                if prior_id is not None and prior_id != evidence_id:
                    _error(errors, f"runtime evidence artifact hash {evidence_hash} is reused by {prior_id} and {evidence_id}")
                    catalog_valid = False
                catalog_hashes[evidence_hash] = evidence_id
            if evidence_hash is not None and evidence_path is not None:
                catalog_by_id[evidence_id] = (evidence_hash, evidence_path)

    gates = _require_mapping(bundle.get("runtime_gates"), "runtime_gates", errors)
    if gates is None:
        return False
    ready = True
    used_hashes: dict[str, str] = {}
    for gate_id in REQUIRED_RUNTIME_GATES:
        gate = _require_mapping(gates.get(gate_id), f"runtime_gates.{gate_id}", errors)
        if gate is None:
            ready = False
            continue
        _reject_extra_keys(gate, _RUNTIME_GATE_KEYS, f"runtime_gates.{gate_id}", errors)
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
        if isinstance(gate_evidence_ids, list):
            if len(set(gate_evidence_ids)) != len(gate_evidence_ids):
                _error(errors, f"runtime_gates.{gate_id}.evidence_ids contains duplicates")
                ready = False
            for evidence_id in gate_evidence_ids:
                artifact = catalog_by_id.get(evidence_id)
                if artifact is None:
                    continue
                artifact_hash, _ = artifact
                prior_gate = used_hashes.get(artifact_hash)
                if prior_gate is not None and prior_gate != gate_id:
                    _error(
                        errors,
                        f"runtime evidence artifact hash {artifact_hash} is reused across gates "
                        f"{prior_gate} and {gate_id}",
                    )
                    ready = False
                used_hashes[artifact_hash] = gate_id
    unexpected = set(gates) - set(REQUIRED_RUNTIME_GATES)
    if unexpected:
        _error(errors, f"runtime_gates contains unknown keys: {sorted(unexpected)}")
        ready = False
    return ready and catalog_valid


def _validate_vv3_evidence(
    bundle: Mapping[str, Any],
    *,
    exporter_manifest: Mapping[str, Any] | None,
    manifest_file_sha256: str | None,
    authenticated_catalog: bool,
    authentication_errors: Sequence[str] = (),
) -> EvidenceValidation:
    errors: list[str] = list(authentication_errors)
    if not isinstance(bundle, Mapping):
        return EvidenceValidation(("evidence bundle must be an object",), False, False, False)

    _reject_extra_keys(bundle, _BUNDLE_KEYS, "evidence", errors)
    _validate_exporter_manifest_catalog(bundle, errors)
    _validate_provenance(
        bundle,
        errors,
        exporter_manifest=exporter_manifest,
        manifest_file_sha256=manifest_file_sha256,
    )
    _validate_fingerprint(bundle, errors)
    _validate_reconcile(bundle, errors)
    _validate_export(bundle, errors)
    coverage = _require_mapping(bundle.get("coverage"), "coverage", errors)
    if coverage is not None:
        _reject_extra_keys(coverage, _COVERAGE_KEYS, "coverage", errors)
        _validate_loader(coverage, errors)
        _validate_indices(coverage, errors)
        _validate_consumers(coverage, errors)
        _validate_padding(coverage, errors)
        _validate_exact_operands(coverage, errors, exporter_manifest=exporter_manifest)
    runtime_ready = _validate_runtime_gates(bundle, errors)
    structural_errors = [error for error in errors if not error.startswith("runtime_gates.")]
    static_valid = authenticated_catalog and exporter_manifest is not None and not structural_errors
    if "runtime_gates" not in bundle or not authenticated_catalog:
        static_valid = False
    publication = not errors and static_valid and runtime_ready and static_publication_ready()
    return EvidenceValidation(tuple(errors), static_valid, runtime_ready, publication)


def validate_vv3_evidence(bundle: Mapping[str, Any]) -> EvidenceValidation:
    """Validate structure only; direct mappings are never authenticated or static-valid."""

    return _validate_vv3_evidence(
        bundle,
        exporter_manifest=None,
        manifest_file_sha256=None,
        authenticated_catalog=False,
        authentication_errors=("authentication requires a canonical evidence file and exporter manifest",),
    )


def publication_ready_with_evidence(bundle: Mapping[str, Any]) -> bool:
    """Return the conservative publication decision for a validated bundle."""

    result = validate_vv3_evidence(bundle)
    return result.publication_ready


def load_evidence(path: Path) -> Mapping[str, Any]:
    """Load one stable, duplicate-free, canonical evidence JSON object."""

    raw, _ = _stable_file_read(path)
    return _parse_canonical_json(raw)


def validate_evidence_file(path: Path, *, catalog_root: Path | None = None) -> EvidenceValidation:
    """Authenticate a canonical evidence file and every referenced artifact."""

    try:
        root = _validated_catalog_root(catalog_root or Path(path).parent)
        raw, initial = _stable_file_read(path)
        bundle = _parse_canonical_json(raw)
        authentication_errors: list[str] = []
        exporter_manifest, manifest_inventory = _load_exporter_manifest(
            bundle,
            catalog_root=root,
            errors=authentication_errors,
        )
        initial_artifacts = _inventory_runtime_artifacts(
            bundle,
            catalog_root=root,
            errors=authentication_errors,
        )
        result = _validate_vv3_evidence(
            bundle,
            exporter_manifest=exporter_manifest,
            manifest_file_sha256=manifest_inventory.sha256 if manifest_inventory else None,
            authenticated_catalog=not authentication_errors and manifest_inventory is not None,
            authentication_errors=authentication_errors,
        )
        final_errors: list[str] = []
        final_manifest, final_manifest_inventory = _load_exporter_manifest(
            bundle,
            catalog_root=root,
            errors=final_errors,
        )
        final_artifacts = _inventory_runtime_artifacts(
            bundle,
            catalog_root=root,
            errors=final_errors,
        )
        if manifest_inventory != final_manifest_inventory or exporter_manifest != final_manifest:
            _error(final_errors, "exporter manifest changed between inventory reads")
        _compare_artifact_inventories(initial_artifacts, final_artifacts, final_errors)
        _, final = _stable_file_read(path)
    except (OSError, ValueError) as exc:
        return EvidenceValidation((str(exc),), False, False, False)
    if final_errors:
        return EvidenceValidation((*result.errors, *final_errors), False, False, False)
    if initial != final:
        return EvidenceValidation(
            (*result.errors, "evidence file identity or bytes changed between inventory, read, and validation"),
            False,
            False,
            False,
        )
    return result
