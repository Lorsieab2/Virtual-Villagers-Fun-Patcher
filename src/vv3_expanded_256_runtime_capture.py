"""Prepare fail-closed VV3 Expanded-256 runtime capture checklists.

The harness authenticates static evidence and inventories only paths explicitly
provided by the operator.  It never launches a process, discovers save roots,
opens save files, signs runtime evidence, or changes publication/runtime gates.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import stat
from typing import Any, Mapping, Sequence

from vv3_expanded_256_contract import VV3_SOURCE_SHA256
from vv3_expanded_256_evidence import (
    REQUIRED_INDEX_PATHS,
    VV3_PROTOTYPE_SHA256,
    canonical_json_bytes,
    inventory_evidence_file,
    load_evidence,
    validate_evidence_file,
)


FOLDER_INVENTORY_SCHEMA = "vvfp.vv3_expanded_256_folder_inventory"
RECEIPT_SCHEMA = "vvfp.vv3_expanded_256_runtime_capture_receipt"
SCHEMA_VERSION = 1
GAME_FOLDER_NAME = "Virtual Villagers - The Secret City - Modded 256"
MODDED_SAVE_ROOT_NAME = GAME_FOLDER_NAME
STOCK_EXE_NAME = "Virtual Villagers - The Secret City.exe"
ENTRY_EXE_NAME = "Virtual Villagers - The Secret City - Modded 256.exe"
COMPANION_NAME = "VVFP Origins Icons.dll"
COMPANION_SHA256 = "2ED1100E7F2EA5B8E522C2DE11F6B00CA8A02B968319C251365E9EFD634BCAF9"
STOCK_SIZE = 831_488
COMPANION_SIZE = 295_936
_SHA256 = re.compile(r"^[0-9A-F]{64}$")
_REPARSE_POINT = 0x0400


@dataclass(frozen=True)
class FolderContract:
    folder_name: str
    stock_exe_name: str
    entry_exe_name: str
    companion_name: str
    source_sha256: str
    source_size: int
    companion_sha256: str
    companion_size: int
    role_counts: Mapping[str, int]

    @property
    def physical_files(self) -> int:
        return sum(self.role_counts.values())


VV3_FOLDER_CONTRACT = FolderContract(
    folder_name=GAME_FOLDER_NAME,
    stock_exe_name=STOCK_EXE_NAME,
    entry_exe_name=ENTRY_EXE_NAME,
    companion_name=COMPANION_NAME,
    source_sha256=VV3_SOURCE_SHA256,
    source_size=STOCK_SIZE,
    companion_sha256=COMPANION_SHA256,
    companion_size=COMPANION_SIZE,
    role_counts={
        "stock_executable": 1,
        "retained_game_asset": 411,
        "entry_executable": 1,
        "companion_dll": 1,
        "patch_log": 1,
        "transparency_log": 1,
        "player_readme": 1,
        "runtime_inventory": 1,
        "checksum_list": 1,
    },
)

STAGE_REQUIREMENTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "loader_hang_instruction_call_state",
        (
            "capture the exact faulting/hanging instruction EA and raw bytes",
            "capture the caller EA, return address, branch path, thread ID, registers, and stack state",
            "record whether the hang reproduced and whether the reviewed loader path completed",
        ),
    ),
    (
        "stock_import",
        (
            "identify the stock-layout input by pre-read size and SHA-256",
            "record the exact stock-to-expanded branch and successful one-time import result",
            "preserve before/after receipt references without treating static files as runtime proof",
        ),
    ),
    (
        "expanded_save_reload",
        (
            "record expanded save creation, exact size, SHA-256, and successful reload",
            "record record-count and record-255 persistence after reload",
        ),
    ),
    (
        "offline_catch_up",
        (
            "record pre-close and post-reload clocks and elapsed interval",
            "record the completed offline-catch-up route and late-record state after catch-up",
        ),
    ),
    (
        "failed_load_nonmutation",
        (
            "supply a deliberately rejected load and its rejection branch",
            "prove active save and in-memory state hashes are unchanged after failure",
        ),
    ),
    (
        "save_rotation",
        (
            "record primary/backup rotation order and exact before/after hashes",
            "record recovery behavior without overwriting unrelated save generations",
        ),
    ),
    (
        "late_record_boundaries",
        (
            "exercise and persist logical records 149, 150, 254, and 255",
            "record selection, update, save, reload, and offline-catch-up results for each index",
        ),
    ),
    (
        "padding_unreachable_records",
        (
            "prove logical maximum index 255",
            "prove padding indices 256, 257, 258, and 259 are unreachable by construction, selection, serialization, population counting, and statistics",
        ),
    ),
    (
        "stored_index_sentinel_paths",
        tuple(f"capture width and sentinel behavior for {path}" for path in REQUIRED_INDEX_PATHS),
    ),
    (
        "current_origins_behavior",
        (
            "identify vv3_enable_origins_exclusive_features and its exact companion DLL",
            "record current visible and unavailable Origins behavior without inferring unobserved outcomes",
        ),
    ),
    (
        "explicit_player_validation",
        (
            "record an explicit player confirmation tied to this receipt and exact build",
            "keep runtime/player/publication GO false until an independently authorized validator accepts complete observations",
        ),
    ),
)


class CaptureHarnessError(ValueError):
    """Raised when a preflight input is unsafe, incomplete, or unauthenticated."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CaptureHarnessError(message)


def _is_reparse_like(result: os.stat_result) -> bool:
    return stat.S_ISLNK(result.st_mode) or bool(
        getattr(result, "st_file_attributes", 0) & _REPARSE_POINT
    )


def _plain_directory(path: Path, label: str) -> Path:
    candidate = Path(path).absolute()
    current = Path(candidate.anchor)
    for part in candidate.parts[1:]:
        current /= part
        try:
            result = os.lstat(current)
        except OSError as exc:
            raise CaptureHarnessError(f"{label} does not exist: {candidate}") from exc
        _require(not _is_reparse_like(result), f"{label} traverses a symlink or reparse point")
    final = os.lstat(candidate)
    _require(stat.S_ISDIR(final.st_mode), f"{label} must be a directory")
    return candidate


def _canonical_relative(value: object, label: str) -> str:
    _require(isinstance(value, str) and bool(value), f"{label} must be a non-empty string")
    assert isinstance(value, str)
    _require("\\" not in value, f"{label} must use forward slashes")
    windows = PureWindowsPath(value)
    parts = value.split("/")
    _require(not value.startswith("/") and not windows.drive and not windows.root, f"{label} must be relative")
    _require(all(part not in {"", ".", ".."} for part in parts), f"{label} contains traversal or ambiguous segments")
    _require(all(":" not in part and not PureWindowsPath(part).is_reserved() for part in parts), f"{label} contains a reserved or stream-like segment")
    _require(all(ord(character) >= 0x20 for character in value), f"{label} contains control characters")
    return value


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), f"{label} must be an object")
    return value  # type: ignore[return-value]


def _exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    _require(actual == expected, f"{label} keys mismatch: missing={sorted(expected - actual)} extra={sorted(actual - expected)}")


def _sha(value: object, label: str) -> str:
    _require(isinstance(value, str) and _SHA256.fullmatch(value) is not None, f"{label} must be canonical uppercase SHA-256")
    return str(value)


def _walk_plain_files(root: Path) -> list[str]:
    files: list[str] = []

    def visit(directory: Path, prefix: PurePosixPath) -> None:
        try:
            entries = sorted(os.scandir(directory), key=lambda item: item.name.casefold())
        except OSError as exc:
            raise CaptureHarnessError(f"game folder inventory failed: {directory}") from exc
        for entry in entries:
            result = entry.stat(follow_symlinks=False)
            _require(not _is_reparse_like(result), f"game folder contains a symlink or reparse point: {entry.name}")
            relative = prefix / entry.name
            if stat.S_ISDIR(result.st_mode):
                visit(Path(entry.path), relative)
            elif stat.S_ISREG(result.st_mode):
                files.append(relative.as_posix())
            else:
                raise CaptureHarnessError(f"game folder contains a non-regular entry: {relative.as_posix()}")

    visit(root, PurePosixPath())
    return sorted(files)


def authenticate_exporter_anchor(evidence_path: Path, catalog_root: Path) -> dict[str, object]:
    """Return a stable anchor only for a file-authenticated static evidence bundle."""

    root = _plain_directory(catalog_root, "catalog root")
    first = validate_evidence_file(Path(evidence_path), catalog_root=root)
    _require(first.static_valid, "VV3 static evidence/exporter manifest is not authenticated")
    bundle = load_evidence(Path(evidence_path))
    manifest_catalog = _mapping(bundle.get("exporter_manifest"), "exporter_manifest")
    relative = _canonical_relative(manifest_catalog.get("path"), "exporter_manifest.path")
    manifest = load_evidence(root.joinpath(*relative.split("/")))
    second = validate_evidence_file(Path(evidence_path), catalog_root=root)
    _require(second.static_valid, "VV3 static evidence/exporter manifest changed or failed revalidation")
    _require(first == second, "VV3 evidence validation changed between authentication reads")
    provenance = _mapping(bundle.get("provenance"), "provenance")
    _require(manifest.get("manifest_sha256") == provenance.get("manifest_sha256"), "exporter manifest/provenance digest mismatch")
    return {
        "evidence_sha256": hashlib.sha256(canonical_json_bytes(bundle)).hexdigest().upper(),
        "exporter_manifest_path": relative,
        "exporter_manifest_sha256": _sha(manifest.get("manifest_sha256"), "manifest_sha256"),
        "exporter_manifest_file_sha256": _sha(manifest_catalog.get("sha256"), "exporter_manifest.sha256"),
        "exporter_producer": manifest.get("producer"),
        "exporter_run_id": manifest.get("run_id"),
        "source_sha256": manifest.get("source_sha256"),
        "prototype_sha256": manifest.get("prototype_sha256"),
    }


def validate_folder_inventory_document(
    document: Mapping[str, Any],
    anchor: Mapping[str, object],
    *,
    contract: FolderContract = VV3_FOLDER_CONTRACT,
) -> dict[str, Mapping[str, Any]]:
    """Validate the declarative complete-folder inventory before filesystem reads."""

    _exact_keys(
        document,
        {
            "schema", "schema_version", "status", "complete", "synthetic", "ambiguous",
            "folder_name", "source_sha256", "prototype_sha256", "exporter_manifest_sha256",
            "exporter_manifest_file_sha256", "physical_files", "records",
        },
        "folder inventory",
    )
    _require(document.get("schema") == FOLDER_INVENTORY_SCHEMA, "folder inventory schema is unsupported")
    _require(document.get("schema_version") == SCHEMA_VERSION, "folder inventory schema version is unsupported")
    _require(document.get("status") == "complete" and document.get("complete") is True, "folder inventory must declare exact completeness")
    _require(document.get("synthetic") is False and document.get("ambiguous") is False, "folder inventory cannot be synthetic or ambiguous")
    _require(document.get("folder_name") == contract.folder_name, "folder inventory name is not the exact VV3 Modded 256 folder")
    _require(document.get("source_sha256") == anchor.get("source_sha256") == contract.source_sha256, "folder inventory stock identity is not authenticated")
    _require(document.get("prototype_sha256") == anchor.get("prototype_sha256") == VV3_PROTOTYPE_SHA256, "folder inventory prototype identity is not authenticated")
    _require(document.get("exporter_manifest_sha256") == anchor.get("exporter_manifest_sha256"), "folder inventory exporter-manifest digest mismatch")
    _require(document.get("exporter_manifest_file_sha256") == anchor.get("exporter_manifest_file_sha256"), "folder inventory exporter-manifest file digest mismatch")
    _require(type(document.get("physical_files")) is int and document.get("physical_files") == contract.physical_files, f"folder inventory must declare exactly {contract.physical_files} files")
    records = document.get("records")
    _require(isinstance(records, list) and len(records) == contract.physical_files, f"folder inventory must contain exactly {contract.physical_files} records")
    by_path: dict[str, Mapping[str, Any]] = {}
    role_counts = {role: 0 for role in contract.role_counts}
    previous = ""
    for index, raw in enumerate(records):
        record = _mapping(raw, f"folder inventory records[{index}]")
        _exact_keys(record, {"path", "role", "size", "sha256"}, f"folder inventory records[{index}]")
        relative = _canonical_relative(record.get("path"), f"folder inventory records[{index}].path")
        _require(relative > previous, "folder inventory records must use unique canonical path order")
        previous = relative
        _require(relative not in by_path, f"folder inventory path is duplicated: {relative}")
        role = record.get("role")
        _require(isinstance(role, str) and role in role_counts, f"folder inventory role is not required: {role}")
        _require(type(record.get("size")) is int and int(record["size"]) >= 0, f"folder inventory size is invalid: {relative}")
        _sha(record.get("sha256"), f"folder inventory {relative}.sha256")
        by_path[relative] = record
        role_counts[str(role)] += 1
    _require(role_counts == dict(contract.role_counts), f"folder inventory role counts mismatch: {role_counts}")
    special = {
        "stock_executable": (contract.stock_exe_name, contract.source_size, contract.source_sha256),
        "entry_executable": (contract.entry_exe_name, None, None),
        "companion_dll": (contract.companion_name, contract.companion_size, contract.companion_sha256),
    }
    for role, (expected_path, expected_size, expected_hash) in special.items():
        matching = [(path, record) for path, record in by_path.items() if record["role"] == role]
        _require(len(matching) == 1 and matching[0][0] == expected_path, f"folder inventory {role} path mismatch")
        record = matching[0][1]
        if expected_size is not None:
            _require(record["size"] == expected_size, f"folder inventory {role} size mismatch")
        if expected_hash is not None:
            _require(record["sha256"] == expected_hash, f"folder inventory {role} SHA-256 mismatch")
    return by_path


def preflight_complete_game_folder(
    game_folder: Path,
    inventory_document: Mapping[str, Any],
    anchor: Mapping[str, object],
    *,
    contract: FolderContract = VV3_FOLDER_CONTRACT,
) -> dict[str, object]:
    """Hash and re-read every explicitly inventoried game-folder file."""

    root = _plain_directory(game_folder, "game folder")
    _require(root.name == contract.folder_name, "game folder is not the exact VV3 Modded 256 folder")
    by_path = validate_folder_inventory_document(inventory_document, anchor, contract=contract)
    actual_paths = _walk_plain_files(root)
    _require(set(actual_paths) == set(by_path), f"game folder is partial or has extras: missing={sorted(set(by_path) - set(actual_paths))} extra={sorted(set(actual_paths) - set(by_path))}")
    first: dict[str, object] = {}
    for relative in actual_paths:
        inventory = inventory_evidence_file(PurePosixPath(relative), root=root)
        declared = by_path[relative]
        _require(inventory.size == declared["size"], f"game folder size mismatch: {relative}")
        _require(inventory.sha256 == declared["sha256"], f"game folder SHA-256 mismatch: {relative}")
        first[relative] = inventory
    _require(actual_paths == _walk_plain_files(root), "game folder path set changed during preflight")
    for relative in actual_paths:
        second = inventory_evidence_file(PurePosixPath(relative), root=root)
        _require(first[relative] == second, f"game folder file changed during re-read: {relative}")
    entry = next(record for record in by_path.values() if record["role"] == "entry_executable")
    return {
        "status": "verified_inventory_only",
        "complete": True,
        "folder_name": root.name,
        "physical_files": len(actual_paths),
        "role_counts": dict(contract.role_counts),
        "entry_executable": contract.entry_exe_name,
        "entry_sha256": entry["sha256"],
        "no_follow": True,
        "re_read_verified": True,
    }


def preflight_modded_save_root(save_root: Path) -> dict[str, object]:
    """Validate only explicit path metadata; never enumerate or open save files."""

    root = _plain_directory(save_root, "Modded save root")
    _require(root.name == MODDED_SAVE_ROOT_NAME, "save root must be the explicit VV3 Modded 256 folder")
    return {
        "status": "path_preflight_only",
        "explicitly_supplied": True,
        "folder_name": root.name,
        "path": str(root),
        "contents_accessed": False,
        "reparse_free": True,
    }


def pending_stages() -> list[dict[str, object]]:
    return [
        {
            "ordinal": index,
            "id": stage_id,
            "status": "pending",
            "required_assertions": list(requirements),
            "observation_refs": [],
            "artifact_refs": [],
            "operator_notes": None,
            "player_confirmed": False,
        }
        for index, (stage_id, requirements) in enumerate(STAGE_REQUIREMENTS, start=1)
    ]


def build_pending_receipt(
    anchor: Mapping[str, object],
    folder_preflight: Mapping[str, object],
    save_root_preflight: Mapping[str, object],
) -> dict[str, object]:
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "receipt_id": None,
        "receipt_status": "pending",
        "evidence_class": "staged_checklist_only",
        "template_only": True,
        "generated_at": None,
        "authorization": {
            "dry_run": True,
            "launch_permitted": False,
            "save_content_access_permitted": False,
            "auto_discovery_permitted": False,
        },
        "authenticated_static_anchor": dict(anchor),
        "folder_preflight": dict(folder_preflight),
        "modded_save_root_preflight": dict(save_root_preflight),
        "stages": pending_stages(),
        "integrity": {
            "signed": False,
            "canonical_sha256": None,
            "signature": None,
        },
        "decision": {
            "runtime_go": False,
            "player_go": False,
            "publication_ready": False,
            "status": "STOP",
            "reason": "No real player/runtime observations or independently validated signed receipt are present.",
        },
    }
    validate_pending_receipt(receipt)
    return receipt


def validate_pending_receipt(receipt: Mapping[str, Any]) -> None:
    """Accept only the unsigned, observation-empty, publication-false template state."""

    _exact_keys(
        receipt,
        {
            "schema", "schema_version", "receipt_id", "receipt_status", "evidence_class",
            "template_only", "generated_at", "authorization", "authenticated_static_anchor",
            "folder_preflight", "modded_save_root_preflight", "stages", "integrity", "decision",
        },
        "receipt",
    )
    _require(receipt.get("schema") == RECEIPT_SCHEMA and receipt.get("schema_version") == SCHEMA_VERSION, "runtime receipt schema is unsupported")
    _require(receipt.get("receipt_id") is None and receipt.get("generated_at") is None, "pending receipt cannot claim an issued identity or capture time")
    _require(receipt.get("receipt_status") == "pending" and receipt.get("evidence_class") == "staged_checklist_only" and receipt.get("template_only") is True, "runtime receipt is not a pending template")
    authorization = _mapping(receipt.get("authorization"), "authorization")
    _require(authorization == {"dry_run": True, "launch_permitted": False, "save_content_access_permitted": False, "auto_discovery_permitted": False}, "pending receipt authorization boundary was relaxed")
    anchor = _mapping(receipt.get("authenticated_static_anchor"), "authenticated_static_anchor")
    _exact_keys(anchor, {"evidence_sha256", "exporter_manifest_path", "exporter_manifest_sha256", "exporter_manifest_file_sha256", "exporter_producer", "exporter_run_id", "source_sha256", "prototype_sha256"}, "authenticated_static_anchor")
    for field in ("evidence_sha256", "exporter_manifest_sha256", "exporter_manifest_file_sha256"):
        _sha(anchor.get(field), f"authenticated_static_anchor.{field}")
    _canonical_relative(anchor.get("exporter_manifest_path"), "authenticated_static_anchor.exporter_manifest_path")
    _require(anchor.get("exporter_producer") == "vv3-ida-exporter", "authenticated static anchor producer mismatch")
    _require(isinstance(anchor.get("exporter_run_id"), str) and bool(anchor.get("exporter_run_id")), "authenticated static anchor run ID is missing")
    _require(anchor.get("source_sha256") == VV3_SOURCE_SHA256 and anchor.get("prototype_sha256") == VV3_PROTOTYPE_SHA256, "authenticated static anchor VV3 identity mismatch")
    folder = _mapping(receipt.get("folder_preflight"), "folder_preflight")
    _exact_keys(folder, {"status", "complete", "folder_name", "physical_files", "role_counts", "entry_executable", "entry_sha256", "no_follow", "re_read_verified", "inventory_sha256"}, "folder_preflight")
    _require(folder.get("status") == "verified_inventory_only" and folder.get("complete") is True, "folder preflight is not complete")
    _require(folder.get("folder_name") == GAME_FOLDER_NAME and folder.get("physical_files") == VV3_FOLDER_CONTRACT.physical_files, "folder preflight does not match the exact complete VV3 folder")
    _require(folder.get("role_counts") == dict(VV3_FOLDER_CONTRACT.role_counts), "folder preflight role counts mismatch")
    _require(folder.get("entry_executable") == ENTRY_EXE_NAME, "folder preflight entry executable mismatch")
    _sha(folder.get("entry_sha256"), "folder_preflight.entry_sha256")
    _sha(folder.get("inventory_sha256"), "folder_preflight.inventory_sha256")
    _require(folder.get("no_follow") is True and folder.get("re_read_verified") is True, "folder preflight no-follow/re-read guarantees are missing")
    save_root = _mapping(receipt.get("modded_save_root_preflight"), "modded_save_root_preflight")
    _exact_keys(save_root, {"status", "explicitly_supplied", "folder_name", "path", "contents_accessed", "reparse_free"}, "modded_save_root_preflight")
    _require(save_root.get("status") == "path_preflight_only" and save_root.get("explicitly_supplied") is True, "Modded save root was not explicitly preflighted")
    _require(save_root.get("folder_name") == MODDED_SAVE_ROOT_NAME and isinstance(save_root.get("path"), str) and bool(save_root.get("path")), "Modded save root identity is invalid")
    _require(save_root.get("contents_accessed") is False and save_root.get("reparse_free") is True, "Modded save root boundary was relaxed")
    stages = receipt.get("stages")
    _require(isinstance(stages, list) and len(stages) == len(STAGE_REQUIREMENTS), "runtime receipt stage set is incomplete")
    for index, ((expected_id, expected_requirements), raw) in enumerate(zip(STAGE_REQUIREMENTS, stages), start=1):
        stage = _mapping(raw, f"stages[{index - 1}]")
        _exact_keys(stage, {"ordinal", "id", "status", "required_assertions", "observation_refs", "artifact_refs", "operator_notes", "player_confirmed"}, f"stages[{index - 1}]")
        _require(stage.get("ordinal") == index and stage.get("id") == expected_id, "runtime receipt stages are reordered or substituted")
        _require(stage.get("status") == "pending", f"runtime receipt stage cannot claim observation: {expected_id}")
        _require(stage.get("required_assertions") == list(expected_requirements), f"runtime receipt requirements changed: {expected_id}")
        _require(stage.get("observation_refs") == [] and stage.get("artifact_refs") == [] and stage.get("operator_notes") is None and stage.get("player_confirmed") is False, f"pending runtime receipt stage contains claimed evidence: {expected_id}")
    integrity = _mapping(receipt.get("integrity"), "integrity")
    _require(integrity == {"signed": False, "canonical_sha256": None, "signature": None}, "pending receipt must remain unsigned and unhashed")
    decision = _mapping(receipt.get("decision"), "decision")
    _require(decision.get("runtime_go") is False and decision.get("player_go") is False and decision.get("publication_ready") is False and decision.get("status") == "STOP", "pending receipt cannot set runtime/player/publication GO")


def prepare_dry_run_receipt(
    *,
    evidence_path: Path,
    catalog_root: Path,
    game_folder: Path,
    folder_inventory_path: Path,
    modded_save_root: Path,
    contract: FolderContract = VV3_FOLDER_CONTRACT,
) -> dict[str, object]:
    anchor = authenticate_exporter_anchor(evidence_path, catalog_root)
    inventory_before = load_evidence(folder_inventory_path)
    inventory_digest = hashlib.sha256(canonical_json_bytes(inventory_before)).hexdigest().upper()
    folder = preflight_complete_game_folder(game_folder, inventory_before, anchor, contract=contract)
    inventory_after = load_evidence(folder_inventory_path)
    _require(inventory_before == inventory_after, "folder inventory changed during preflight")
    folder = {**folder, "inventory_sha256": inventory_digest}
    save_root = preflight_modded_save_root(modded_save_root)
    return build_pending_receipt(anchor, folder, save_root)


def receipt_bytes(receipt: Mapping[str, object]) -> bytes:
    """Return deterministic bytes for transport without issuing a receipt digest."""

    validate_pending_receipt(receipt)
    return canonical_json_bytes(receipt) + b"\n"
