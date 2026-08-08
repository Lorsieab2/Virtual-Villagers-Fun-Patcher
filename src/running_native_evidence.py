"""Fail-closed binding of copied stock inputs to authenticated native exports.

This module only inventories a caller-declared copied game folder and validates
an already-produced JSON export.  It never launches a game, invokes IDA or
Ghidra, reads saves, emits native code, or writes an evidence artifact.

The generic export proves source bytes and ABI-shaped rows only.  It does not
prove Running's preference semantics, selected-index resolver, world identity,
account identity, balance readback, runtime behavior, or player behavior.  A
valid generic export therefore remains a STOP binding until a separate
semantic evidence adapter proves those requirements.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "data" / "authenticated_native_export.schema.json"
QUERY_PATH = ROOT / "data" / "native_evidence_queries.json"
SUPPORTED_EXPORT_GAMES = ("vv3", "vv4", "vv5")
EXPECTED_SCHEMA_ID = "vvfp.authenticated-native-export.v1"
EXPECTED_QUERY_SCHEMA_ID = "vvfp.native-evidence-queries.v1"
EXPECTED_QUERY_OUTPUT = (
    "function_bounds",
    "ea",
    "file_offset",
    "raw_bytes",
    "instructions",
    "callers",
    "xrefs",
    "registers",
    "stack_cleanup",
    "call_convention",
)
RUNNING_QUERY_IDS = (
    "selected_index_and_world_resolver",
    "funds_getter",
    "funds_deduction_setter",
    "preference_setter_readback_queue",
    "confirmation_result_abi",
    "postverify_fault_boundary",
)
EXPORT_ROW_KEYS = frozenset(
    {
        "query_id",
        "status",
        "function_start_ea",
        "function_end_ea",
        "file_offset",
        "raw_bytes",
        "instructions",
        "callers",
        "xrefs",
        "registers",
        "stack_cleanup",
        "call_convention",
    }
)
HEX64 = re.compile(r"^[0-9A-F]{64}$")
HEX_BYTES = re.compile(r"^(?:[0-9A-F]{2})+$")
HEX_ADDRESS = re.compile(r"^0x[0-9A-Fa-f]+$")


class EvidenceBindingError(ValueError):
    """A copied-input or native-export invariant was not proven."""


@dataclass(frozen=True)
class RunningEvidenceBinding:
    """Truthful result of binding one candidate to one copied input/export."""

    game_id: str
    status: str = "STOP"
    enabled: bool = False
    catalog_enabled: bool = False
    catalog_hidden: bool = True
    native_output: bool = False
    runtime_verified: bool = False
    player_verified: bool = False
    export_valid: bool = False
    semantic_proof_complete: bool = False
    inventory_sha256: str | None = None
    export_artifact_sha256: str | None = None
    resolved_queries: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()

    @property
    def enablement_ready(self) -> bool:
        """Generic export validity never silently enables a Running binding."""

        return (
            self.status == "GO"
            and self.enabled
            and self.catalog_enabled
            and self.export_valid
            and self.semantic_proof_complete
        )


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _is_reparse(path: Path) -> bool:
    try:
        attrs = getattr(path.lstat(), "st_file_attributes", 0)
    except OSError:
        return False
    return path.is_symlink() or bool(attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def read_no_follow(path: Path) -> bytes:
    """Read one stable regular file without accepting links or reparses."""

    before = path.lstat()
    if _is_reparse(path) or not stat.S_ISREG(before.st_mode):
        raise EvidenceBindingError(f"non-regular or linked artifact rejected: {path}")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        opened = os.fstat(fd)
        if (before.st_dev, before.st_ino, before.st_size) != (
            opened.st_dev,
            opened.st_ino,
            opened.st_size,
        ):
            raise EvidenceBindingError(f"artifact identity changed while opening: {path}")
        chunks: list[bytes] = []
        while True:
            block = os.read(fd, 1024 * 1024)
            if not block:
                break
            chunks.append(block)
        after = os.fstat(fd)
        if (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        ):
            raise EvidenceBindingError(f"artifact changed while hashing: {path}")
        return b"".join(chunks)
    finally:
        os.close(fd)


def _manifest_fingerprint(manifest: Mapping[str, Any]) -> tuple[str, int, str]:
    exact = manifest.get("exact_build") or manifest.get("stock_fingerprint") or manifest.get("fingerprint")
    if not isinstance(exact, Mapping):
        raise EvidenceBindingError("running manifest has no exact stock fingerprint")
    name = exact.get("filename", exact.get("file_name", exact.get("input_name")))
    size = exact.get("size")
    digest = exact.get("sha256")
    if type(name) is not str or not name:
        raise EvidenceBindingError("exact stock executable name is invalid")
    if type(size) is not int or isinstance(size, bool) or size <= 0:
        raise EvidenceBindingError("exact stock executable size is invalid")
    if type(digest) is not str or not HEX64.fullmatch(digest):
        raise EvidenceBindingError("exact stock executable SHA-256 must be uppercase")
    return name, size, digest


def inventory_copied_input(
    workspace_root: Path,
    game_folder: Path,
    game_id: str,
    manifest: Mapping[str, Any],
) -> tuple[dict[str, Any], bytes]:
    """Inventory a copied game folder and return its executable bytes."""

    if game_id not in SUPPORTED_EXPORT_GAMES:
        raise EvidenceBindingError(
            "authenticated native export schema covers VV3-VV5 only; VV1/VV2 remain STOP"
        )
    manifest_game = manifest.get("game_id")
    if manifest_game is not None and manifest_game != game_id:
        raise EvidenceBindingError("running manifest game identity does not match requested game")
    if manifest.get("eligibility_gate_order") != "before_preference_access":
        raise EvidenceBindingError("running manifest does not declare eligibility before preference access")
    if manifest.get("enabled") is True or manifest.get("catalog_enabled") is True:
        raise EvidenceBindingError("enabled or catalog-visible Running manifest is rejected")
    root = workspace_root.resolve(strict=True)
    folder_input = Path(game_folder)
    if _is_reparse(folder_input):
        raise EvidenceBindingError("copied game folder cannot be a link or reparse point")
    folder = folder_input.resolve(strict=True)
    if folder == root or not _inside(folder, root):
        raise EvidenceBindingError("copied game folder must be a child of workspace root")
    expected_name, expected_size, expected_sha = _manifest_fingerprint(manifest)
    files: list[dict[str, Any]] = []
    for current, directories, names in os.walk(folder, followlinks=False):
        current_path = Path(current)
        for name in directories:
            if _is_reparse(current_path / name):
                raise EvidenceBindingError(f"linked directory rejected: {current_path / name}")
        for name in names:
            path = current_path / name
            payload = read_no_follow(path)
            files.append(
                {
                    "path": path.relative_to(folder).as_posix(),
                    "size": len(payload),
                    "sha256": sha(payload),
                }
            )
    files.sort(key=lambda item: item["path"].casefold())
    if not files:
        raise EvidenceBindingError("copied game folder cannot be empty")
    executable = next(
        (item for item in files if item["path"].casefold() == expected_name.casefold()),
        None,
    )
    if executable is None:
        raise EvidenceBindingError("exact stock executable is missing from copied input")
    if executable != {
        "path": executable["path"],
        "size": expected_size,
        "sha256": expected_sha,
    }:
        raise EvidenceBindingError("exact stock executable fingerprint mismatch")
    inventory = {
        "schema": "vvfp.full-folder-inventory.v1",
        "game": game_id,
        "root_name": folder.name,
        "file_count": len(files),
        "files": files,
    }
    inventory["inventory_sha256"] = sha(canonical_json(inventory))
    return inventory, read_no_follow(folder / executable["path"])


def _load_json(path: Path, label: str) -> Any:
    try:
        return json.loads(read_no_follow(path).decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, EvidenceBindingError) as exc:
        raise EvidenceBindingError(f"{label} could not be read: {exc}") from exc


def _address(value: object, field: str) -> int:
    if type(value) is not str or not HEX_ADDRESS.fullmatch(value):
        raise EvidenceBindingError(f"{field} must be a canonical hexadecimal address string")
    return int(value, 16)


def _validate_export(
    export: Mapping[str, Any],
    inventory: Mapping[str, Any],
    executable: bytes,
    schema: Mapping[str, Any],
    queries: Mapping[str, Any],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    errors: list[str] = []
    expected_top = frozenset(schema["required"])
    if (
        schema.get("$id") != EXPECTED_SCHEMA_ID
        or schema.get("type") != "object"
        or schema.get("additionalProperties") is not False
        or expected_top
        != frozenset(
            {
                "schema",
                "generated_by",
                "synthetic",
                "manual",
                "game",
                "inventory_sha256",
                "functions",
                "artifact_sha256",
            }
        )
        or frozenset(schema.get("properties", {})) != expected_top
    ):
        errors.append("authenticated native export schema is weakened or unexpected")
    if frozenset(export) != expected_top:
        errors.append("native export top-level keys do not match the authenticated schema")
    if export.get("schema") != EXPECTED_SCHEMA_ID:
        errors.append("native export schema identifier mismatch")
    if export.get("generated_by") not in {"ida_python", "ghidra"}:
        errors.append("native export generator is not authorized")
    if export.get("synthetic") is not False or export.get("manual") is not False:
        errors.append("synthetic or manual native export rejected")
    if export.get("game") != inventory.get("game"):
        errors.append("native export game binding mismatch")
    inventory_sha = export.get("inventory_sha256")
    if type(inventory_sha) is not str or not HEX64.fullmatch(inventory_sha):
        errors.append("native export inventory hash is invalid")
    elif inventory_sha != inventory.get("inventory_sha256"):
        errors.append("native export inventory hash mismatch")
    artifact_sha = export.get("artifact_sha256")
    if type(artifact_sha) is not str or not HEX64.fullmatch(artifact_sha):
        errors.append("native export artifact hash is invalid")
    elif artifact_sha != sha(canonical_json({key: value for key, value in export.items() if key != "artifact_sha256"})):
        errors.append("native export artifact hash mismatch")

    query_rows = queries.get("queries")
    query_ids = tuple(
        item.get("id") for item in query_rows
        if isinstance(item, Mapping) and type(item.get("id")) is str
    ) if isinstance(query_rows, list) else ()
    if queries.get("schema") != EXPECTED_QUERY_SCHEMA_ID:
        errors.append("native query schema identifier mismatch")
    if queries.get("games") != list(SUPPORTED_EXPORT_GAMES):
        errors.append("native query game set is unexpected")
    for query in query_rows if isinstance(query_rows, list) else []:
        if (
            not isinstance(query, Mapping)
            or frozenset(query) != frozenset({"id", "required", "search", "output"})
            or query.get("required") is not True
            or query.get("search")
            != {"symbols": [], "strings": [], "constants": [], "xrefs": True}
            or tuple(query.get("output", ())) != EXPECTED_QUERY_OUTPUT
        ):
            errors.append("native query row schema is weakened or unexpected")
            break
    if query_ids != tuple(item.get("id") for item in queries.get("queries", []) if isinstance(item, Mapping)):
        errors.append("native query identifiers are malformed or duplicated")
    if query_ids != tuple(
        (
            "selected_index_and_world_resolver",
            "funds_getter",
            "funds_deduction_setter",
            "age_setter_companions_oldest",
            "preference_setter_readback_queue",
            "confirmation_result_abi",
            "postverify_fault_boundary",
            "fullscreen_leave_enter_owner",
            "stored_indices",
            "save_loader_serializer",
        )
    ):
        errors.append("native query set is incomplete or reordered")

    rows = export.get("functions")
    expected_rows = query_ids
    if not isinstance(rows, list) or tuple(
        row.get("query_id") for row in rows if isinstance(row, Mapping)
    ) != expected_rows:
        errors.append("native export rows are incomplete, duplicated, or reordered")
        rows = []
    for row in rows:
        if not isinstance(row, Mapping) or frozenset(row) != EXPORT_ROW_KEYS:
            errors.append("native export row shape is incomplete or has extra fields")
            continue
        query_id = row.get("query_id")
        if row.get("status") != "resolved":
            errors.append(f"{query_id}: query is not resolved")
            continue
        try:
            start = _address(row.get("function_start_ea"), f"{query_id} function start")
            end = _address(row.get("function_end_ea"), f"{query_id} function end")
            offset = _address(row.get("file_offset"), f"{query_id} file offset")
            raw_hex = row.get("raw_bytes")
            if type(raw_hex) is not str or not HEX_BYTES.fullmatch(raw_hex):
                raise EvidenceBindingError("raw bytes are not canonical uppercase hex")
            raw = bytes.fromhex(raw_hex)
            if end <= start or executable[offset : offset + len(raw)] != raw:
                raise EvidenceBindingError("bounds or source-byte equality failed")
            if not isinstance(row.get("instructions"), list) or not row["instructions"]:
                raise EvidenceBindingError("instruction proof is empty")
            if not isinstance(row.get("callers"), list) or not isinstance(row.get("xrefs"), list):
                raise EvidenceBindingError("caller/xref proof is malformed")
            if not isinstance(row.get("registers"), Mapping) or not row["registers"]:
                raise EvidenceBindingError("register proof is empty")
            for field in ("stack_cleanup", "call_convention"):
                value = row.get(field)
                if type(value) is not str or not value or "REVIEW_REQUIRED" in value:
                    raise EvidenceBindingError(f"{field} proof is missing")
        except (EvidenceBindingError, TypeError, ValueError, OverflowError) as exc:
            errors.append(f"{query_id}: {exc}")
    resolved = tuple(row.get("query_id") for row in rows if isinstance(row, Mapping) and row.get("status") == "resolved")
    return tuple(errors), resolved


def bind_running_evidence(
    game_id: str,
    manifest: Mapping[str, Any],
    workspace_root: Path,
    game_folder: Path,
    export_path: Path,
    *,
    schema_path: Path = SCHEMA_PATH,
    query_path: Path = QUERY_PATH,
) -> RunningEvidenceBinding:
    """Bind one copied input/export pair without ever enabling the binding."""

    if type(game_id) is not str or not game_id:
        return RunningEvidenceBinding("invalid", errors=("game id is invalid",))
    base = RunningEvidenceBinding(game_id)
    if game_id not in SUPPORTED_EXPORT_GAMES:
        return RunningEvidenceBinding(
            game_id,
            errors=("authenticated export schema covers VV3-VV5 only; VV1/VV2 remain STOP",),
        )
    try:
        inventory, executable = inventory_copied_input(
            workspace_root, game_folder, game_id, manifest
        )
        root = workspace_root.resolve(strict=True)
        export_input = Path(export_path)
        if _is_reparse(export_input):
            raise EvidenceBindingError("native export cannot be a link or reparse point")
        export_file = export_input.resolve(strict=True)
        if not _inside(export_file, root):
            raise EvidenceBindingError("native export must be inside the declared workspace root")
        schema = _load_json(schema_path, "authenticated native export schema")
        queries = _load_json(query_path, "native query manifest")
        export = _load_json(export_file, "native export")
        if not isinstance(schema, Mapping) or not isinstance(queries, Mapping) or not isinstance(export, Mapping):
            raise EvidenceBindingError("schema, query manifest, and export must be objects")
        errors, resolved = _validate_export(export, inventory, executable, schema, queries)
        errors = tuple(errors) + (
            "generic native export does not prove Running semantics, runtime behavior, or player behavior",
        )
        return RunningEvidenceBinding(
            game_id,
            export_valid=not errors[:-1],
            inventory_sha256=inventory["inventory_sha256"],
            export_artifact_sha256=export.get("artifact_sha256") if isinstance(export.get("artifact_sha256"), str) else None,
            resolved_queries=resolved,
            errors=errors,
        )
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        EvidenceBindingError,
        TypeError,
        ValueError,
        KeyError,
        AttributeError,
    ) as exc:
        return RunningEvidenceBinding(game_id, errors=(str(exc),))


__all__ = [
    "EvidenceBindingError",
    "RUNNING_QUERY_IDS",
    "RunningEvidenceBinding",
    "bind_running_evidence",
    "canonical_json",
    "inventory_copied_input",
    "read_no_follow",
    "sha",
]
