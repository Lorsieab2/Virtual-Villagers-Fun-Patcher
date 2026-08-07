"""Disabled, no-launch capture harness for VV4/VV5 Expanded-256 evidence.

The harness never starts a game, opens an executable, mutates a save, or
changes the canonical publication contract.  ``dry-run`` prints the exact
player checkpoint plan without touching a folder or save tree.  ``preflight``
hashes a complete self-contained folder and, optionally, an authorized
``* - Modded`` save tree.  ``capture`` pauses for explicit player
acknowledgements between no-follow before/after save snapshots and writes an
unsigned candidate packet only after every checkpoint has been observed.

There is deliberately no JSON observation-input mode.  Runtime facts are
derived from files or recorded through the interactive checkpoint prompts;
synthetic, inferred, developer-only, and manually injected observations are
rejected by the packet validator.  The output is a candidate for a later
authorized authentication step and always carries publication=false fields.
"""

from __future__ import annotations

import argparse
import datetime as _datetime
import getpass
import hashlib
import json
import os
import re
import stat
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import validate_expanded_runtime_evidence as contract_validator


HARNESS_SCHEMA = "vvfp.expanded_256_runtime_capture.v1"
HARNESS_VERSION = "x45-runtime-capture-harness.v1"
FOLDER_INVENTORY_SCHEMA = "vvfp.runtime_capture_folder_inventory.v1"
MODES = (
    "experimental_expanded_256",
    "experimental_expanded_256_progression",
)
REQUIRED_ROLES = (
    "stock_executable",
    "expanded_executable_immediate",
    "expanded_executable_progression",
    "companion_dll",
    "runtime_inventory",
    "checksum_list",
    "patch_log",
    "transparency_log",
    "player_readme",
)
ROLE_SET = set(REQUIRED_ROLES)
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
RECEIPT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{5,127}$")
REPARSE_FLAG = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
CHECKPOINT_PROMPT_VERSION = "x45-player-checkpoint-v1"


class CaptureError(ValueError):
    """Raised when a capture precondition or observation is unsafe."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_sha256(value: Mapping[str, object], *, remove_key: str | None = None) -> str:
    """Return the uppercase SHA-256 of canonical UTF-8 JSON."""

    copy_value = json.loads(json.dumps(dict(value), ensure_ascii=False))
    if remove_key == "canonical_sha256" and isinstance(copy_value.get("integrity"), Mapping):
        copy_value["integrity"].pop(remove_key, None)
    elif remove_key:
        copy_value.pop(remove_key, None)
    return hashlib.sha256(_canonical_bytes(copy_value)).hexdigest().upper()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CaptureError(message)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _is_reparse_point(path: Path) -> bool:
    try:
        info = os.lstat(path)
    except OSError as exc:
        raise CaptureError(f"cannot inspect path without following reparse points: {path}") from exc
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & REPARSE_FLAG)


def _safe_relative(value: object, label: str) -> str:
    _require(isinstance(value, str) and value, f"{label} must be a non-empty relative path")
    normalized = value.replace("\\", "/")
    parsed = PurePosixPath(normalized)
    _require(not parsed.is_absolute() and re.match(r"^[A-Za-z]:", normalized) is None, f"{label} must be relative")
    _require(".." not in parsed.parts and normalized not in {"", "."}, f"{label} may not traverse parents")
    return normalized


def _safe_root(value: Path, label: str) -> Path:
    root = Path(value)
    _require(not _is_reparse_point(root), f"{label} may not be a symlink or reparse point")
    try:
        info = os.stat(root, follow_symlinks=False)
    except OSError as exc:
        raise CaptureError(f"{label} is not accessible") from exc
    _require(stat.S_ISDIR(info.st_mode), f"{label} must be a directory")
    return root


def _safe_child(root: Path, relative: str, label: str) -> Path:
    normalized = _safe_relative(relative, label)
    child = root.joinpath(*PurePosixPath(normalized).parts)
    current = root
    for component in PurePosixPath(normalized).parts:
        current = current / component
        _require(not _is_reparse_point(current), f"{label} contains a symlink or reparse point: {normalized}")
    return child


def _stable_file_identity(path: Path, relative: str) -> tuple[int, str, str]:
    _require(not _is_reparse_point(path), f"reparse point rejected: {relative}")
    try:
        first_size = os.stat(path, follow_symlinks=False).st_size
        first_hash = _sha256_file(path)
        second_size = os.stat(path, follow_symlinks=False).st_size
        second_hash = _sha256_file(path)
    except OSError as exc:
        raise CaptureError(f"file is not stable/readable: {relative}") from exc
    _require(first_size == second_size, f"file changed during re-read: {relative}")
    _require(first_hash == second_hash, f"file hash changed during re-read: {relative}")
    return first_size, first_hash, second_hash


def _walk_no_reparse(root: Path) -> tuple[list[str], list[str]]:
    """Return all directory and file paths without following reparse points."""

    directories: list[str] = []
    files: list[str] = []
    stack: list[tuple[Path, str]] = [(root, "")]
    while stack:
        current, current_relative = stack.pop()
        try:
            entries = sorted(os.scandir(current), key=lambda entry: entry.name.casefold())
        except OSError as exc:
            raise CaptureError(f"cannot enumerate folder without following reparse points: {current}") from exc
        for entry in entries:
            relative = f"{current_relative}/{entry.name}".lstrip("/")
            relative = _safe_relative(relative, "inventory path")
            path = Path(entry.path)
            if _is_reparse_point(path):
                raise CaptureError(f"reparse point rejected from complete inventory: {relative}")
            try:
                info = entry.stat(follow_symlinks=False)
            except OSError as exc:
                raise CaptureError(f"cannot stat inventory path: {relative}") from exc
            if stat.S_ISDIR(info.st_mode):
                directories.append(relative)
                stack.append((path, relative))
            elif stat.S_ISREG(info.st_mode):
                files.append(relative)
            else:
                raise CaptureError(f"unsupported non-file/non-directory entry: {relative}")
    return sorted(directories), sorted(files)


def _load_contract() -> dict[str, object]:
    try:
        document = json.loads(contract_validator.CONTRACT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CaptureError("canonical Expanded-256 runtime contract is unreadable") from exc
    try:
        contract_validator.validate_contract(document, root=ROOT)
    except contract_validator.RuntimeEvidenceError as exc:
        raise CaptureError(f"canonical Expanded-256 runtime contract failed validation: {exc}") from exc
    return document


def _game(contract: Mapping[str, object], game_id: str) -> Mapping[str, object]:
    games = contract.get("games")
    _require(isinstance(games, Mapping) and game_id in games, f"unsupported game: {game_id}")
    game = games[game_id]
    _require(isinstance(game, Mapping), f"game contract is invalid: {game_id}")
    return game


def _parse_roles(values: Sequence[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        _require(isinstance(value, str) and "=" in value, "each --role must be ROLE=RELATIVE_PATH")
        role, relative = value.split("=", 1)
        _require(role in ROLE_SET, f"unsupported required inventory role: {role}")
        _require(role not in result, f"duplicate inventory role: {role}")
        result[role] = _safe_relative(relative, f"role path {role}")
    _require(set(result) == ROLE_SET, "partial folder role map; all nine required roles are mandatory")
    _require(len(set(result.values())) == len(result), "two required roles point to one file")
    return dict(sorted(result.items()))


def _validate_role_name(role: str, path: Path, game: Mapping[str, object]) -> None:
    name = path.name
    if role == "stock_executable":
        expected = str(game["stock_fingerprint"]["filename"])
        _require(name == expected, f"stock executable filename mismatch: expected {expected}")
    elif role == "companion_dll":
        required_dlls = game["required_folder_inventory"]["required_dlls"]
        expected = str(required_dlls[0]["name"])
        _require(name == expected, f"companion DLL filename mismatch: expected {expected}")
    elif role == "expanded_executable_immediate" or role == "expanded_executable_progression":
        _require(path.suffix.casefold() == ".exe", f"expanded executable must be an .exe: {name}")
    elif role == "runtime_inventory":
        _require(name == "runtime-inventory.json", "runtime inventory must be named runtime-inventory.json")
    elif role == "checksum_list":
        _require(name == "SHA256SUMS.txt", "checksum list must be named SHA256SUMS.txt")


def _expected_role_identity(role: str, game: Mapping[str, object]) -> tuple[int, str]:
    if role == "stock_executable":
        record = game["stock_fingerprint"]
    elif role == "expanded_executable_immediate":
        record = game["expanded_fingerprints"]["experimental_expanded_256"]
    elif role == "expanded_executable_progression":
        record = game["expanded_fingerprints"]["experimental_expanded_256_progression"]
    elif role == "companion_dll":
        record = game["required_folder_inventory"]["required_dlls"][0]
        return (-1, str(record["sha256"]))
    else:
        return (-1, "")
    return int(record["size"]), str(record["sha256"])


def _folder_record(root: Path, relative: str, role: str) -> dict[str, object]:
    path = _safe_child(root, relative, f"folder inventory {relative}")
    size, digest, reread = _stable_file_identity(path, relative)
    return {
        "path": relative,
        "role": role,
        "size": size,
        "sha256": digest,
        "re_read_sha256": reread,
        "is_symlink": False,
        "is_reparse_point": False,
        "provenance": "authenticated_runtime_artifact",
    }


def _build_artifact_inventory(records: Sequence[Mapping[str, object]]) -> dict[str, object]:
    required_records = [record for record in records if record.get("role") in ROLE_SET]
    return {
        "schema_version": "vvfp.runtime_artifact_inventory.v1",
        "status": "observed",
        "complete": True,
        "follow_symlinks": False,
        "no_follow": True,
        "re_read_required": True,
        "records": [dict(record) for record in sorted(required_records, key=lambda item: str(item["path"]))],
    }


def _relocation_proof(game: Mapping[str, object]) -> dict[str, object]:
    ledger = game["relocation_ledger"]
    relative = _safe_relative(ledger["path"], "relocation ledger path")
    source_path = _safe_child(ROOT, relative, "relocation ledger")
    try:
        source = json.loads(source_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CaptureError("relocation ledger source is unreadable") from exc
    rows = contract_validator._json_pointer(source, str(ledger["json_pointer"]))
    _require(isinstance(rows, list), "relocation ledger rows are not a list")
    row_digests = [
        {"index": index, "row_sha256": _sha256_bytes(_canonical_bytes(row))}
        for index, row in enumerate(rows)
    ]
    recomputed = _sha256_bytes(_canonical_bytes(rows))
    _require(len(rows) == int(ledger["count"]), "relocation ledger count changed")
    _require(recomputed == str(ledger["ledger_sha256"]), "relocation ledger digest changed")
    return {
        "source_path": relative,
        "json_pointer": str(ledger["json_pointer"]),
        "count": len(rows),
        "ledger_sha256": recomputed,
        "rows": row_digests,
    }


def _inventory_digest(inventory: Mapping[str, object]) -> str:
    return canonical_sha256(inventory, remove_key="canonical_sha256")


def _preflight_folder(
    contract: Mapping[str, object],
    game_id: str,
    folder: Path,
    role_paths: Mapping[str, str],
) -> dict[str, object]:
    game = _game(contract, game_id)
    _require(set(role_paths) == ROLE_SET, "partial folder role map; all nine required roles are mandatory")
    _require(len(set(role_paths.values())) == len(role_paths), "two required roles point to one file")
    root = _safe_root(folder, "complete game folder")
    resolved_roles: dict[str, Path] = {}
    for role, relative in role_paths.items():
        path = _safe_child(root, relative, f"role path {role}")
        _require(path.is_file(), f"required folder artifact is missing: {relative}")
        _validate_role_name(role, path, game)
        resolved_roles[role] = path
    directories, files = _walk_no_reparse(root)
    file_set = set(files)
    for role, relative in role_paths.items():
        _require(relative in file_set, f"required folder artifact is not in complete inventory: {relative}")
    records = [
        _folder_record(root, relative, next((role for role, path in role_paths.items() if path == relative), "supporting_runtime_artifact"))
        for relative in files
    ]
    full_inventory: dict[str, object] = {
        "schema_version": FOLDER_INVENTORY_SCHEMA,
        "status": "observed",
        "complete": True,
        "no_unrecorded_files": True,
        "follow_symlinks": False,
        "no_follow": True,
        "re_read_required": True,
        "root_name": root.name,
        "directory_paths": directories,
        "physical_file_count": len(files),
        "records": records,
    }
    full_inventory["canonical_sha256"] = _inventory_digest(full_inventory)
    artifact_inventory = _build_artifact_inventory(records)
    try:
        contract_validator.validate_artifact_inventory(artifact_inventory, game, root=root)
    except contract_validator.RuntimeEvidenceError as exc:
        raise CaptureError(str(exc)) from exc
    for role, relative in role_paths.items():
        expected_size, expected_hash = _expected_role_identity(role, game)
        if expected_size >= 0:
            record = next(record for record in records if record["path"] == relative)
            _require(record["size"] == expected_size, f"exact {role} size mismatch: {relative}")
            _require(record["sha256"] == expected_hash, f"exact {role} SHA-256 mismatch: {relative}")
    return {
        "status": "ready",
        "game_id": game_id,
        "folder_name": root.name,
        "role_paths": dict(sorted(role_paths.items())),
        "artifact_inventory": artifact_inventory,
        "full_folder_inventory": full_inventory,
        "relocation_proof": _relocation_proof(game),
        "launch_automatic": False,
        "publication": {"enabled": False, "runtime_go": False, "player_go": False, "eligible": False},
    }


def _checkpoint_plan(game: Mapping[str, object], game_id: str, mode: str) -> list[dict[str, object]]:
    _require(mode in MODES, f"unsupported Expanded-256 mode: {mode}")
    expanded = game["expanded_fingerprints"][mode]
    feature_id = game["runtime_evidence"]["gates"]["current_origins_behavior"]["feature_id"]
    ledger = game["relocation_ledger"]
    return [
        {
            "id": "stock_import_conversion",
            "stage": 1,
            "instruction": "Player manually imports the authorized stock save through the exact stock executable and confirms conversion completes.",
            "assertions": {"stock_sha256": game["stock_fingerprint"]["sha256"], "conversion_observed": True},
        },
        {
            "id": "expanded_save_reload",
            "stage": 2,
            "instruction": "Player manually uses the selected expanded executable, saves, closes/reloads, and confirms the save returns.",
            "assertions": {"mode": mode, "expanded_sha256": expanded["sha256"], "reload_observed": True},
        },
        {
            "id": "offline_catchup",
            "stage": 3,
            "instruction": "Player manually leaves the game offline, returns after the planned interval, and confirms catch-up behavior.",
            "assertions": {"catchup_observed": True},
        },
        {
            "id": "failed_load_nonmutation",
            "stage": 4,
            "instruction": "Player manually performs the authorized failed-load test and confirms the save tree is unchanged.",
            "assertions": {"nonmutation_required": True},
        },
        {
            "id": "save_rotation",
            "stage": 5,
            "instruction": "Player manually performs the save-rotation test and confirms the expected backup/rotation behavior.",
            "assertions": {"rotation_observed": True},
        },
        {
            "id": "late_record_boundaries",
            "stage": 6,
            "instruction": "Player manually validates late records 149, 150, 254, and 255 at the required boundary points.",
            "assertions": {"indices": [149, 150, 254, 255]},
        },
        {
            "id": "current_origins_behavior",
            "stage": 7,
            "instruction": "Player manually validates current Origins behavior after the relocation path is active.",
            "assertions": {"feature_id": feature_id},
        },
        {
            "id": "relocation_proof",
            "stage": 8,
            "instruction": "Player manually confirms the current Origins relocation proof is present for every ledger row.",
            "assertions": {
                "count": int(ledger["count"]),
                "ledger_sha256": ledger["ledger_sha256"],
                "row_proof_required": True,
            },
        },
        {
            "id": "player_runtime_receipts",
            "stage": 9,
            "instruction": "Player manually reviews every preceding checkpoint and confirms this packet reflects direct observation of this exact build.",
            "assertions": {"all_prior_checkpoints_reviewed": True},
        },
    ]


def _validate_modded_save_root(save_root: Path) -> Path:
    root = Path(save_root)
    _require(root.name.endswith(" - Modded"), "save root must be an authorized '* - Modded' directory")
    return _safe_root(root, "authorized Modded save root")


def snapshot_save_tree(save_root: Path) -> dict[str, object]:
    """Snapshot an authorized save tree without following symlinks/reparse points."""

    root = _validate_modded_save_root(save_root)
    directories, files = _walk_no_reparse(root)
    entries: list[dict[str, object]] = [
        {"path": relative, "kind": "directory", "is_reparse_point": False}
        for relative in directories
    ]
    for relative in files:
        size, digest, reread = _stable_file_identity(_safe_child(root, relative, "save snapshot"), relative)
        entries.append(
            {
                "path": relative,
                "kind": "file",
                "size": size,
                "sha256": digest,
                "re_read_sha256": reread,
                "is_reparse_point": False,
            }
        )
    entries.sort(key=lambda item: str(item["path"]))
    snapshot: dict[str, object] = {
        "schema_version": "vvfp.modded_save_tree_snapshot.v1",
        "root_name": root.name,
        "follow_symlinks": False,
        "no_follow": True,
        "re_read_required": True,
        "entries": entries,
    }
    snapshot["canonical_sha256"] = canonical_sha256(snapshot, remove_key="canonical_sha256")
    _validate_snapshot(snapshot)
    return snapshot


def _snapshot_changed(before: Mapping[str, object], after: Mapping[str, object]) -> bool:
    return before.get("canonical_sha256") != after.get("canonical_sha256")


def _snapshot_delta(before: Mapping[str, object], after: Mapping[str, object]) -> list[str]:
    before_entries = {str(entry["path"]): entry for entry in before["entries"]}
    after_entries = {str(entry["path"]): entry for entry in after["entries"]}
    return sorted(
        path
        for path in set(before_entries) | set(after_entries)
        if before_entries.get(path) != after_entries.get(path)
    )


def _validate_snapshot(snapshot: Mapping[str, object]) -> None:
    _require(snapshot.get("schema_version") == "vvfp.modded_save_tree_snapshot.v1", "save snapshot schema is unsupported")
    _require(isinstance(snapshot.get("root_name"), str) and str(snapshot["root_name"]).endswith(" - Modded"), "save snapshot is not Modded-scoped")
    _require(snapshot.get("follow_symlinks") is False and snapshot.get("no_follow") is True, "save snapshot no-follow policy is unsafe")
    _require(snapshot.get("re_read_required") is True, "save snapshot re-read policy is missing")
    entries = snapshot.get("entries")
    _require(isinstance(entries, list), "save snapshot entries are missing")
    paths: list[str] = []
    for entry in entries:
        _require(isinstance(entry, Mapping), "save snapshot entry is not an object")
        relative = _safe_relative(entry.get("path"), "save snapshot path")
        paths.append(relative)
        _require(entry.get("is_reparse_point") is False, f"save snapshot reparse flag is unsafe: {relative}")
        kind = entry.get("kind")
        if kind == "directory":
            _require(set(entry) == {"path", "kind", "is_reparse_point"}, f"directory snapshot fields are invalid: {relative}")
        elif kind == "file":
            _require(isinstance(entry.get("size"), int) and entry["size"] >= 0, f"save snapshot size is invalid: {relative}")
            digest = str(entry.get("sha256"))
            reread = str(entry.get("re_read_sha256"))
            _require(contract_validator.SHA256_RE.fullmatch(digest) is not None, f"save snapshot hash is invalid: {relative}")
            _require(digest == reread, f"save snapshot re-read differs: {relative}")
        else:
            raise CaptureError(f"save snapshot entry kind is unsupported: {relative}")
    _require(paths == sorted(paths) and len(paths) == len(set(paths)), "save snapshot paths are not canonical and unique")
    _require(snapshot.get("canonical_sha256") == canonical_sha256(snapshot, remove_key="canonical_sha256"), "save snapshot digest is stale")


def _timestamp(clock: Callable[[], _datetime.datetime]) -> str:
    value = clock()
    if value.tzinfo is None:
        value = value.replace(tzinfo=_datetime.timezone.utc)
    return value.astimezone(_datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def _receipt_id(game_id: str, mode: str, captured_at: str) -> str:
    token = captured_at.replace("-", "").replace(":", "").replace(".", "")
    token = token.replace("Z", "")
    return f"x45-{game_id}-{mode}-{token}"


def _make_runtime_evidence(
    contract: Mapping[str, object],
    game_id: str,
    mode: str,
    preflight: Mapping[str, object],
    observations: Sequence[Mapping[str, object]],
    source_commit: str,
    operator: str,
    captured_at: str,
) -> dict[str, object]:
    game = _game(contract, game_id)
    receipt_id = _receipt_id(game_id, mode, captured_at)
    producer = {
        "receipt_id": receipt_id,
        "producer_type": "player_runtime_receipt",
        "operator": operator,
        "captured_at": captured_at,
        "source_commit": source_commit,
        "capture_tool": f"{HARNESS_VERSION}",
        "provenance": "player_observed_exact_build",
        "synthetic": False,
    }
    refs = {str(item["id"]): f"{receipt_id}:{item['id']}" for item in observations}
    by_id = {str(item["id"]): item for item in observations}
    gates: dict[str, object] = {
        "stock_import_conversion": {
            "status": "observed",
            "receipt_refs": [refs["stock_import_conversion"]],
            "assertions": by_id["stock_import_conversion"]["assertions"],
        },
        "expanded_save_reload": {
            "status": "observed",
            "receipt_refs": [refs["expanded_save_reload"]],
            "assertions": by_id["expanded_save_reload"]["assertions"],
        },
        "offline_catchup": {
            "status": "observed",
            "receipt_refs": [refs["offline_catchup"]],
            "assertions": by_id["offline_catchup"]["assertions"],
        },
        "failed_load_nonmutation": {
            "status": "observed",
            "receipt_refs": [refs["failed_load_nonmutation"]],
            "assertions": {"nonmutation": True},
        },
        "save_rotation": {
            "status": "observed",
            "receipt_refs": [refs["save_rotation"]],
            "assertions": {"rotation_observed": True},
        },
        "late_record_boundaries": {
            "status": "observed",
            "receipt_refs": [refs["late_record_boundaries"]],
            "assertions": {"indices": [149, 150, 254, 255]},
        },
        "padding_unreachable_records": {
            "status": "not_applicable",
            "applicable": False,
            "reason": f"{game_id.upper()} has no VV3-style four-record padding reservation",
            "receipt_refs": [],
        },
        "current_origins_behavior": {
            "status": "observed",
            "receipt_refs": [refs["current_origins_behavior"]],
            "assertions": by_id["current_origins_behavior"]["assertions"],
        },
        "relocation_receipt": {
            "status": "observed",
            "receipt_refs": [refs["relocation_proof"]],
            "assertions": {
                "count": int(game["relocation_ledger"]["count"]),
                "ledger_sha256": game["relocation_ledger"]["ledger_sha256"],
                "row_sha256": [row["row_sha256"] for row in preflight["relocation_proof"]["rows"]],
            },
        },
        "player_runtime_receipts": {
            "status": "observed",
            "receipt_refs": [refs["player_runtime_receipts"]],
            "assertions": {"checkpoint_ids": [item["id"] for item in observations]},
        },
    }
    evidence: dict[str, object] = {
        "status": "observed",
        "evidence_class": "player_runtime_receipt",
        "producer": producer,
        "artifact_inventory": preflight["artifact_inventory"],
        "player_receipts": [
            {
                "receipt_ref": refs[str(item["id"])],
                "checkpoint_id": item["id"],
                "player_confirmed": True,
                "observation_source": "interactive_player_confirmation",
                "synthetic": False,
            }
            for item in observations
        ],
        "gates": gates,
    }
    evidence["receipt_sha256"] = canonical_sha256(evidence, remove_key="receipt_sha256")
    return evidence


def validate_unsigned_candidate(packet: Mapping[str, object], contract: Mapping[str, object]) -> None:
    """Validate the harness packet without treating it as publication evidence."""

    _require(packet.get("schema_version") == HARNESS_SCHEMA, "capture packet schema is unsupported")
    _require(packet.get("harness_version") == HARNESS_VERSION, "capture packet harness version is unsupported")
    _require(packet.get("status") == "unsigned_candidate", "capture packet is not explicitly unsigned")
    publication = packet.get("publication")
    _require(isinstance(publication, Mapping), "capture packet publication guard is missing")
    _require(all(publication.get(key) is False for key in ("enabled", "runtime_go", "player_go", "eligible")), "capture packet publication guard was relaxed")
    authentication = packet.get("authentication")
    _require(isinstance(authentication, Mapping), "capture packet authentication state is missing")
    _require(authentication.get("status") == "unsigned_candidate" and authentication.get("authenticated") is False and authentication.get("signature") is None, "capture packet authentication state is unsafe")
    game_id = packet.get("game_id")
    mode = packet.get("mode")
    _require(isinstance(game_id, str) and game_id in {"vv4", "vv5"}, "capture packet game is unsupported")
    _require(mode in MODES, "capture packet mode is unsupported")
    game = _game(contract, game_id)
    binding = packet.get("contract_binding")
    _require(isinstance(binding, Mapping), "capture packet contract binding is missing")
    _require(binding.get("schema_version") == contract["schema_version"], "capture packet contract schema binding is stale")
    _require(binding.get("canonical_sha256") == contract["integrity"]["canonical_sha256"], "capture packet contract digest binding is stale")
    preflight = packet.get("preflight")
    _require(isinstance(preflight, Mapping) and preflight.get("status") == "ready", "capture packet preflight is incomplete")
    full_inventory = preflight.get("full_folder_inventory")
    _require(isinstance(full_inventory, Mapping) and full_inventory.get("complete") is True and full_inventory.get("no_unrecorded_files") is True, "capture packet folder inventory is incomplete")
    _require(full_inventory.get("follow_symlinks") is False and full_inventory.get("no_follow") is True and full_inventory.get("re_read_required") is True, "capture packet folder inventory no-follow policy is unsafe")
    full_records = full_inventory.get("records")
    _require(isinstance(full_records, list) and len(full_records) == full_inventory.get("physical_file_count"), "capture packet full-folder records are incomplete")
    full_paths: list[str] = []
    for record in full_records:
        _require(isinstance(record, Mapping), "capture packet full-folder record is not an object")
        relative = _safe_relative(record.get("path"), "capture packet full-folder path")
        full_paths.append(relative)
        _require(record.get("is_symlink") is False and record.get("is_reparse_point") is False, f"capture packet full-folder path is unsafe: {relative}")
        _require(record.get("provenance") == "authenticated_runtime_artifact", f"capture packet full-folder provenance is unsafe: {relative}")
        _require(contract_validator.SHA256_RE.fullmatch(str(record.get("sha256"))) is not None and record.get("sha256") == record.get("re_read_sha256"), f"capture packet full-folder hash is unstable: {relative}")
    _require(len(full_paths) == len(set(full_paths)), "capture packet full-folder paths are duplicated")
    _require(full_inventory.get("canonical_sha256") == _inventory_digest(full_inventory), "capture packet folder inventory digest is stale")
    artifact_inventory = preflight.get("artifact_inventory")
    _require(isinstance(artifact_inventory, Mapping), "capture packet required artifact inventory is missing")
    try:
        contract_validator.validate_artifact_inventory(artifact_inventory, game)
    except contract_validator.RuntimeEvidenceError as exc:
        raise CaptureError(str(exc)) from exc
    observations = packet.get("checkpoints")
    _require(isinstance(observations, list), "capture packet checkpoints are missing")
    expected = _checkpoint_plan(game, game_id, str(mode))
    expected_ids = [item["id"] for item in expected]
    actual_ids = [item.get("id") for item in observations if isinstance(item, Mapping)]
    _require(actual_ids == expected_ids, "capture packet checkpoint sequence is incomplete or reordered")
    for index, observation in enumerate(observations):
        _require(isinstance(observation, Mapping), "capture packet checkpoint is not an object")
        expected_checkpoint = expected[index]
        _require(observation.get("stage") == expected_checkpoint["stage"], f"checkpoint stage is stale: {observation.get('id')}")
        _require(observation.get("assertions") == expected_checkpoint["assertions"], f"checkpoint assertions were manually changed: {observation.get('id')}")
        _require(observation.get("status") == "observed", "capture packet checkpoint is not observed")
        _require(observation.get("player_confirmed") is True, "capture packet checkpoint lacks explicit player confirmation")
        _require(observation.get("observation_source") == "interactive_player_confirmation", "capture packet checkpoint source is not interactive")
        _require(observation.get("synthetic") is False, "synthetic checkpoint cannot be emitted")
        _require(observation.get("manual_fields") is None, "manual field injection is forbidden")
        _require(observation.get("acknowledgement") == f"OBSERVED:{observation['id']}", "checkpoint acknowledgement is invalid")
        for field in ("save_before", "save_after"):
            snapshot = observation.get(field)
            _require(isinstance(snapshot, Mapping), f"checkpoint {observation['id']} lacks {field} snapshot")
            _validate_snapshot(snapshot)
        changed = _snapshot_changed(observation["save_before"], observation["save_after"])
        _require(observation.get("save_changed") is changed, f"checkpoint save-change flag is stale: {observation['id']}")
        _require(observation.get("changed_paths") == _snapshot_delta(observation["save_before"], observation["save_after"]), f"checkpoint save delta is stale: {observation['id']}")
        if observation["id"] == "failed_load_nonmutation":
            _require(not changed, "failed-load checkpoint is not nonmutating")
        if observation["id"] in {"stock_import_conversion", "offline_catchup", "save_rotation"}:
            _require(changed, f"checkpoint requires a changed save tree: {observation['id']}")
    relocation = preflight.get("relocation_proof")
    expected_relocation = _relocation_proof(game)
    _require(relocation == expected_relocation, "capture packet relocation proof was manually changed")
    runtime_evidence = packet.get("runtime_evidence")
    _require(isinstance(runtime_evidence, Mapping), "capture packet runtime evidence is missing")
    _require(runtime_evidence.get("status") == "observed" and runtime_evidence.get("evidence_class") == "player_runtime_receipt", "capture packet runtime evidence class is unsafe")
    _require(runtime_evidence.get("artifact_inventory") == artifact_inventory, "capture packet runtime artifact inventory does not match preflight")
    _require(runtime_evidence.get("receipt_sha256") == canonical_sha256(runtime_evidence, remove_key="receipt_sha256"), "capture packet runtime receipt digest is stale")
    producer = runtime_evidence.get("producer")
    _require(isinstance(producer, Mapping) and producer.get("synthetic") is False and producer.get("provenance") == "player_observed_exact_build", "capture packet producer is not exact player provenance")
    _require(producer.get("producer_type") == "player_runtime_receipt" and producer.get("capture_tool") == HARNESS_VERSION, "capture packet producer identity is stale")
    _require(COMMIT_RE.fullmatch(str(producer.get("source_commit"))) is not None, "capture packet source commit is not full-length")
    _require(RECEIPT_ID_RE.fullmatch(str(producer.get("receipt_id"))) is not None, "capture packet receipt id is invalid")
    gates = runtime_evidence.get("gates")
    _require(isinstance(gates, Mapping) and set(gates) == contract_validator.GATES, "capture packet runtime gate set is incomplete")
    _require(gates["late_record_boundaries"]["assertions"] == {"indices": [149, 150, 254, 255]}, "capture packet late-record assertion is stale")
    _require(gates["current_origins_behavior"]["assertions"] == {"feature_id": game["runtime_evidence"]["gates"]["current_origins_behavior"]["feature_id"]}, "capture packet Origins feature assertion is stale")
    relocation_assertions = gates["relocation_receipt"]["assertions"]
    _require(relocation_assertions["count"] == expected_relocation["count"], "capture packet relocation count is stale")
    _require(relocation_assertions["ledger_sha256"] == expected_relocation["ledger_sha256"], "capture packet relocation digest is stale")
    _require(relocation_assertions["row_sha256"] == [row["row_sha256"] for row in expected_relocation["rows"]], "capture packet relocation row proof is stale")
    _require(gates["padding_unreachable_records"]["status"] == "not_applicable" and gates["padding_unreachable_records"]["applicable"] is False, "capture packet padding gate was relaxed")
    player_receipts = runtime_evidence.get("player_receipts")
    expected_receipts = [
        {
            "receipt_ref": f"{producer['receipt_id']}:{item['id']}",
            "checkpoint_id": item["id"],
            "player_confirmed": True,
            "observation_source": "interactive_player_confirmation",
            "synthetic": False,
        }
        for item in observations
    ]
    _require(player_receipts == expected_receipts, "capture packet player receipt list was manually changed")
    _require("manual_observation" not in packet and "synthetic_fixture" not in packet, "manual or synthetic evidence field is forbidden")
    integrity = packet.get("integrity")
    _require(isinstance(integrity, Mapping), "capture packet integrity record is missing")
    _require(integrity.get("canonical_sha256") == canonical_sha256(packet, remove_key="canonical_sha256"), "capture packet canonical digest is stale")


def capture_candidate(
    *,
    contract: Mapping[str, object],
    game_id: str,
    mode: str,
    folder: Path,
    save_root: Path,
    role_paths: Mapping[str, str],
    source_commit: str,
    prompt: Callable[[str], str],
    clock: Callable[[], _datetime.datetime] = _datetime.datetime.now,
    operator: str | None = None,
) -> dict[str, object]:
    """Interactively capture an unsigned candidate without launching anything."""

    _require(COMMIT_RE.fullmatch(source_commit) is not None, "source commit must be a full 40-character lowercase SHA-1")
    authorized_save_root = _validate_modded_save_root(save_root)
    preflight = _preflight_folder(contract, game_id, folder, role_paths)
    game = _game(contract, game_id)
    captured_at = _timestamp(clock)
    observations: list[dict[str, object]] = []
    for plan in _checkpoint_plan(game, game_id, mode):
        before = snapshot_save_tree(authorized_save_root)
        expected_token = f"OBSERVED:{plan['id']}"
        response = prompt(
            f"{plan['instruction']} Type {expected_token} when directly observed: "
        )
        _require(response.strip() == expected_token, f"checkpoint acknowledgement rejected: {plan['id']}")
        after = snapshot_save_tree(authorized_save_root)
        changed = _snapshot_changed(before, after)
        if plan["id"] == "failed_load_nonmutation":
            _require(not changed, "failed-load checkpoint changed the save tree; no candidate emitted")
        if plan["id"] in {"stock_import_conversion", "offline_catchup", "save_rotation"}:
            _require(changed, f"{plan['id']} requires a changed before/after save snapshot")
        observations.append(
            {
                "id": plan["id"],
                "stage": plan["stage"],
                "status": "observed",
                "player_confirmed": True,
                "observation_source": "interactive_player_confirmation",
                "synthetic": False,
                "manual_fields": None,
                "acknowledgement": expected_token,
                "assertions": plan["assertions"],
                "save_before": before,
                "save_after": after,
                "save_changed": changed,
                "changed_paths": _snapshot_delta(before, after),
            }
        )
    runtime_evidence = _make_runtime_evidence(
        contract,
        game_id,
        mode,
        preflight,
        observations,
        source_commit,
        operator or getpass.getuser(),
        captured_at,
    )
    packet: dict[str, object] = {
        "schema_version": HARNESS_SCHEMA,
        "harness_version": HARNESS_VERSION,
        "status": "unsigned_candidate",
        "game_id": game_id,
        "mode": mode,
        "contract_binding": {
            "schema_version": contract["schema_version"],
            "canonical_sha256": contract["integrity"]["canonical_sha256"],
        },
        "authentication": {
            "status": "unsigned_candidate",
            "authenticated": False,
            "signature": None,
            "next_step": "authorized independent authentication and contract integration",
        },
        "publication": {"enabled": False, "runtime_go": False, "player_go": False, "eligible": False},
        "preflight": preflight,
        "checkpoints": observations,
        "runtime_evidence": runtime_evidence,
        "integrity": {
            "canonicalization": "UTF-8 JSON with sorted keys and compact separators; integrity.canonical_sha256 is excluded from its own digest",
        },
    }
    packet["integrity"]["canonical_sha256"] = canonical_sha256(packet, remove_key="canonical_sha256")
    validate_unsigned_candidate(packet, contract)
    return packet


def _write_canonical(path: Path, value: Mapping[str, object]) -> None:
    _require(not path.exists(), f"refusing to overwrite existing capture output: {path}")
    _require(path.parent.is_dir(), f"capture output parent does not exist: {path.parent}")
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(_canonical_bytes(value).decode("utf-8"))
            handle.write("\n")
    except OSError as exc:
        raise CaptureError(f"cannot write capture output: {path}") from exc


def _outside(path: Path, root: Path, label: str) -> None:
    path_absolute = os.path.abspath(path)
    root_absolute = os.path.abspath(root)
    try:
        inside = os.path.commonpath([path_absolute, root_absolute]) == root_absolute
    except ValueError:
        inside = False
    _require(not inside, f"{label} may not be inside the source tree: {path}")


def _dry_run(game_id: str, mode: str) -> dict[str, object]:
    contract = _load_contract()
    game = _game(contract, game_id)
    return {
        "schema_version": HARNESS_SCHEMA,
        "status": "dry_run",
        "game_id": game_id,
        "mode": mode,
        "contract_binding": {
            "schema_version": contract["schema_version"],
            "canonical_sha256": contract["integrity"]["canonical_sha256"],
        },
        "launch_automatic": False,
        "save_policy": {
            "required_suffix": " - Modded",
            "follow_symlinks": False,
            "no_follow": True,
            "snapshot_before_after": True,
            "non_modded_access": "rejected before filesystem inspection",
        },
        "publication": {"enabled": False, "runtime_go": False, "player_go": False, "eligible": False},
        "required_roles": list(REQUIRED_ROLES),
        "checkpoints": _checkpoint_plan(game, game_id, mode),
        "emission": "capture emits only an unsigned candidate after all interactive player confirmations; authentication and GO remain external",
    }


def _role_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--role",
        action="append",
        required=True,
        metavar="ROLE=RELATIVE_PATH",
        help="repeat for all nine required folder roles; paths are relative and no-follow",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    dry_run = subparsers.add_parser("dry-run", help="print the staged plan without reading folders or saves")
    dry_run.add_argument("--game", choices=("vv4", "vv5"), required=True)
    dry_run.add_argument("--mode", choices=MODES, required=True)

    preflight = subparsers.add_parser("preflight", help="verify a complete folder and optional Modded save root")
    preflight.add_argument("--game", choices=("vv4", "vv5"), required=True)
    preflight.add_argument("--mode", choices=MODES, required=True)
    preflight.add_argument("--folder", type=Path, required=True)
    preflight.add_argument("--save-root", type=Path)
    _role_arguments(preflight)

    capture = subparsers.add_parser("capture", help="interactive no-launch capture of an unsigned candidate")
    capture.add_argument("--game", choices=("vv4", "vv5"), required=True)
    capture.add_argument("--mode", choices=MODES, required=True)
    capture.add_argument("--folder", type=Path, required=True)
    capture.add_argument("--save-root", type=Path, required=True)
    capture.add_argument("--output", type=Path, required=True)
    capture.add_argument("--source-commit", required=True, help="full lowercase 40-hex source commit")
    _role_arguments(capture)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        contract = _load_contract()
        if args.command == "dry-run":
            print(json.dumps(_dry_run(args.game, args.mode), ensure_ascii=False, sort_keys=True, indent=2))
            return 0
        role_paths = _parse_roles(args.role)
        if args.command == "preflight":
            if args.save_root is not None:
                save_root = _validate_modded_save_root(args.save_root)
                _outside(args.folder, save_root, "game folder")
            result = _preflight_folder(contract, args.game, args.folder, role_paths)
            if args.save_root is not None:
                result["save_snapshot"] = snapshot_save_tree(args.save_root)
            print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            return 0
        _outside(args.output, args.folder, "capture output")
        _outside(args.output, args.save_root, "capture output")
        packet = capture_candidate(
            contract=contract,
            game_id=args.game,
            mode=args.mode,
            folder=args.folder,
            save_root=args.save_root,
            role_paths=role_paths,
            source_commit=args.source_commit,
            prompt=input,
        )
        _write_canonical(args.output, packet)
        print(json.dumps({"status": packet["status"], "output": str(args.output), "publication_eligible": False}, sort_keys=True))
        return 0
    except CaptureError as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
