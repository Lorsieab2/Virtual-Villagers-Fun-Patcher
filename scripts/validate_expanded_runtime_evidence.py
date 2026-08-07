"""Validate the fail-closed VV4/VV5 Expanded-256 runtime-evidence contract.

This module validates canonical JSON and supplied artifact inventories only. It
does not launch an executable, open a save, perform conversion, or publish a
package. Runtime/player receipts must be supplied by an independently
authorized producer; static renders and synthetic fixtures are never GO
evidence.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

try:
    from scripts.source_text_hash import source_text_sha256
except ModuleNotFoundError:  # direct script execution
    from source_text_hash import source_text_sha256


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "data" / "expanded_256_runtime_evidence.json"
SHA256_RE = re.compile(r"^[0-9A-F]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
RECEIPT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{5,127}$")
MODES = {
    "experimental_expanded_256",
    "experimental_expanded_256_progression",
}
GATES = {
    "stock_import_conversion",
    "expanded_save_reload",
    "offline_catchup",
    "failed_load_nonmutation",
    "save_rotation",
    "late_record_boundaries",
    "padding_unreachable_records",
    "current_origins_behavior",
    "relocation_receipt",
    "player_runtime_receipts",
}
OBSERVED_GATES = GATES - {"padding_unreachable_records"}


class RuntimeEvidenceError(ValueError):
    """Raised when evidence is absent, stale, incomplete, or untrusted."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_sha256(value: Mapping[str, object], *, remove_key: str) -> str:
    """Hash canonical JSON after removing one self-hash field."""

    copy_value = copy.deepcopy(dict(value))
    if remove_key == "canonical_sha256" and isinstance(copy_value.get("integrity"), Mapping):
        copy_value["integrity"].pop(remove_key, None)
    else:
        copy_value.pop(remove_key, None)
    return hashlib.sha256(_canonical_bytes(copy_value)).hexdigest().upper()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeEvidenceError(message)


def _mapping(value: object, label: str) -> Mapping[str, object]:
    _require(isinstance(value, Mapping), f"{label} must be an object")
    return value


def _string(value: object, label: str) -> str:
    _require(isinstance(value, str) and bool(value), f"{label} must be a non-empty string")
    return value


def _sha(value: object, label: str) -> str:
    result = _string(value, label)
    _require(SHA256_RE.fullmatch(result) is not None, f"{label} must be uppercase SHA-256")
    return result


def _safe_relative(path: object, label: str) -> str:
    value = _string(path, label).replace("\\", "/")
    parsed = PurePosixPath(value)
    _require(not parsed.is_absolute(), f"{label} must be relative")
    _require(".." not in parsed.parts, f"{label} may not traverse parents")
    _require(value not in {"", "."}, f"{label} may not be empty")
    return value


def _json_pointer(value: object, pointer: str) -> object:
    current = value
    _require(pointer.startswith("/"), "source JSON pointer must start with '/'")
    for token in pointer[1:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, Mapping):
            _require(token in current, f"source JSON pointer is missing: {pointer}")
            current = current[token]
        elif isinstance(current, list):
            _require(token.isdigit(), f"source JSON pointer index is invalid: {pointer}")
            index = int(token)
            _require(index < len(current), f"source JSON pointer index is missing: {pointer}")
            current = current[index]
        else:
            raise RuntimeEvidenceError(f"source JSON pointer cannot descend: {pointer}")
    return current


def _assert_no_symlink_components(root: Path, relative: str) -> Path:
    root = root.resolve()
    _require(not root.is_symlink(), "artifact inventory root may not be a symlink")
    path = root
    for component in PurePosixPath(relative).parts:
        path /= component
        _require(not path.is_symlink(), f"artifact inventory symlink/junction rejected: {relative}")
    return path


def _stable_file_identity(root: Path, relative: str) -> tuple[int, str, str]:
    path = _assert_no_symlink_components(root, relative)
    _require(path.is_file(), f"artifact inventory file is missing: {relative}")
    first_size = path.stat().st_size
    first_hash = _sha256(path)
    second_size = path.stat().st_size
    second_hash = _sha256(path)
    _require(first_size == second_size, f"artifact changed during re-read: {relative}")
    _require(first_hash == second_hash, f"artifact hash changed during re-read: {relative}")
    return first_size, first_hash, second_hash


def _expected_artifact_identities(game: Mapping[str, object]) -> dict[str, tuple[int, str]]:
    stock = _mapping(game["stock_fingerprint"], "stock_fingerprint")
    identities = {
        "stock_executable": (int(stock["size"]), _sha(stock["sha256"], "stock_fingerprint.sha256")),
    }
    for mode, fingerprint in _mapping(game["expanded_fingerprints"], "expanded_fingerprints").items():
        record = _mapping(fingerprint, f"expanded_fingerprints.{mode}")
        role = f"expanded_executable_{mode.removeprefix('experimental_expanded_256_') or 'immediate'}"
        if mode == "experimental_expanded_256":
            role = "expanded_executable_immediate"
        elif mode == "experimental_expanded_256_progression":
            role = "expanded_executable_progression"
        identities[role] = (int(record["size"]), _sha(record["sha256"], f"expanded_fingerprints.{mode}.sha256"))
    return identities


def validate_artifact_inventory(
    inventory: Mapping[str, object],
    game: Mapping[str, object],
    *,
    root: Path | None = None,
) -> dict[str, object]:
    """Validate a complete no-follow, stable, re-readable artifact inventory."""

    _require(inventory.get("schema_version") == "vvfp.runtime_artifact_inventory.v1", "artifact inventory schema is unsupported")
    _require(inventory.get("status") == "observed", "artifact inventory is not observed")
    _require(inventory.get("complete") is True, "artifact inventory is incomplete")
    _require(inventory.get("follow_symlinks") is False, "artifact inventory must disable symlink following")
    _require(inventory.get("no_follow") is True, "artifact inventory must be no-follow")
    _require(inventory.get("re_read_required") is True, "artifact inventory must require re-read")
    records = inventory.get("records")
    _require(isinstance(records, list) and records, "artifact inventory records are missing")
    required = _mapping(game["required_folder_inventory"], "required_folder_inventory")
    required_roles = _mapping(required["required_roles"], "required_folder_inventory.required_roles")
    counts: dict[str, int] = {str(role): 0 for role in required_roles}
    paths: set[str] = set()
    identities = _expected_artifact_identities(game)
    for index, raw_record in enumerate(records):
        record = _mapping(raw_record, f"artifact inventory record {index}")
        relative = _safe_relative(record.get("path"), f"artifact inventory record {index}.path")
        _require(relative not in paths, f"artifact inventory path is duplicated: {relative}")
        paths.add(relative)
        role = _string(record.get("role"), f"artifact inventory record {index}.role")
        _require(role in required_roles, f"artifact inventory role is not required: {role}")
        counts[role] += 1
        size = record.get("size")
        _require(isinstance(size, int) and size >= 0, f"artifact inventory size is invalid: {relative}")
        digest = _sha(record.get("sha256"), f"artifact inventory {relative}.sha256")
        reread = _sha(record.get("re_read_sha256"), f"artifact inventory {relative}.re_read_sha256")
        _require(digest == reread, f"artifact inventory re-read digest differs: {relative}")
        _require(record.get("is_symlink") is False, f"artifact inventory symlink flag is unsafe: {relative}")
        _require(record.get("provenance") == "authenticated_runtime_artifact", f"artifact provenance is not authenticated: {relative}")
        if role in identities:
            expected_size, expected_hash = identities[role]
            _require(size == expected_size, f"artifact size does not match {role}: {relative}")
            _require(digest == expected_hash, f"artifact hash does not match {role}: {relative}")
        if root is not None:
            actual_size, actual_hash, actual_reread = _stable_file_identity(root, relative)
            _require((size, digest, reread) == (actual_size, actual_hash, actual_reread), f"artifact inventory identity mismatch: {relative}")
    for role, expected_count in required_roles.items():
        _require(counts.get(str(role), 0) == int(expected_count), f"artifact inventory role count mismatch: {role}")
    required_dlls = required.get("required_dlls")
    _require(isinstance(required_dlls, list) and required_dlls, "required DLL inventory is missing")
    for expected_dll in required_dlls:
        dll = _mapping(expected_dll, "required_folder_inventory.required_dlls item")
        name = _string(dll.get("name"), "required DLL name")
        expected_hash = _sha(dll.get("sha256"), f"required DLL {name}.sha256")
        matches = [record for record in records if record.get("role") == "companion_dll" and PurePosixPath(str(record["path"])).name.casefold() == name.casefold()]
        _require(len(matches) == 1, f"required DLL is missing or duplicated: {name}")
        _require(matches[0].get("sha256") == expected_hash, f"required DLL hash mismatch: {name}")
    return {"complete": True, "records": len(records), "roles": counts}


def _validate_producer(producer: Mapping[str, object]) -> None:
    for field in (
        "receipt_id",
        "producer_type",
        "operator",
        "captured_at",
        "source_commit",
        "capture_tool",
        "provenance",
    ):
        _string(producer.get(field), f"runtime receipt producer.{field}")
    _require(RECEIPT_ID_RE.fullmatch(str(producer["receipt_id"])) is not None, "runtime receipt id is invalid")
    _require(producer.get("producer_type") == "player_runtime_receipt", "runtime receipt producer type is not authorized")
    _require(COMMIT_RE.fullmatch(str(producer["source_commit"])) is not None, "runtime receipt source commit is not full-length")
    _require(producer.get("synthetic") is False, "synthetic evidence cannot be a runtime receipt")
    _require(producer.get("provenance") == "player_observed_exact_build", "runtime receipt provenance is not player-observed exact-build evidence")


def _validate_observed_gate(
    name: str,
    gate: Mapping[str, object],
    game: Mapping[str, object],
) -> None:
    _require(gate.get("status") == "observed", f"runtime gate is not observed: {name}")
    refs = gate.get("receipt_refs")
    _require(isinstance(refs, list) and all(isinstance(ref, str) and ref for ref in refs), f"runtime gate receipts are missing: {name}")
    assertions = _mapping(gate.get("assertions"), f"runtime gate assertions: {name}")
    if name == "late_record_boundaries":
        _require(assertions.get("indices") == [149, 150, 254, 255], "late-record receipt indices are incomplete")
    elif name == "relocation_receipt":
        ledger = _mapping(game["relocation_ledger"], "relocation_ledger")
        _require(assertions.get("count") == ledger["count"], "runtime relocation count is incomplete")
        _require(assertions.get("ledger_sha256") == ledger["ledger_sha256"], "runtime relocation ledger digest is stale")
    elif name == "current_origins_behavior":
        _require(assertions.get("feature_id") == game["runtime_evidence"]["gates"][name].get("feature_id"), "current Origins feature identity is stale")


def _validate_runtime_evidence(game: Mapping[str, object]) -> dict[str, object]:
    evidence = _mapping(game["runtime_evidence"], "runtime_evidence")
    status = evidence.get("status")
    gates = _mapping(evidence.get("gates"), "runtime_evidence.gates")
    _require(set(gates) == GATES, "runtime evidence gate set is incomplete or has extras")
    if status == "absent":
        _require(evidence.get("evidence_class") is None, "absent runtime evidence has a class")
        _require(evidence.get("producer") is None, "absent runtime evidence has a producer")
        _require(evidence.get("artifact_inventory") is None, "absent runtime evidence has an inventory")
        _require(evidence.get("player_receipts") == [], "absent runtime evidence has player receipts")
        for name, gate in gates.items():
            record = _mapping(gate, f"runtime_evidence.gates.{name}")
            expected = "not_applicable" if name == "padding_unreachable_records" else "absent"
            _require(record.get("status") == expected, f"canonical runtime gate is not fail-closed: {name}")
            _require(record.get("receipt_refs") == [], f"absent runtime gate has receipt refs: {name}")
        return {"observed": False, "runtime_go": False, "player_go": False}
    _require(status == "observed", "runtime evidence status is unsupported")
    _require(evidence.get("evidence_class") == "player_runtime_receipt", "runtime evidence class is not authorized")
    producer = _mapping(evidence.get("producer"), "runtime_evidence.producer")
    _validate_producer(producer)
    receipt_digest = _sha(evidence.get("receipt_sha256"), "runtime_evidence.receipt_sha256")
    _require(receipt_digest == canonical_sha256(evidence, remove_key="receipt_sha256"), "runtime receipt canonical digest is stale")
    inventory = _mapping(evidence.get("artifact_inventory"), "runtime_evidence.artifact_inventory")
    validate_artifact_inventory(inventory, game)
    for name in OBSERVED_GATES:
        _validate_observed_gate(name, _mapping(gates[name], f"runtime_evidence.gates.{name}"), game)
    padding = _mapping(gates["padding_unreachable_records"], "runtime_evidence.gates.padding_unreachable_records")
    _require(padding.get("status") == "not_applicable" and padding.get("applicable") is False, "VV4/VV5 padding gate must remain explicit not-applicable")
    receipts = evidence.get("player_receipts")
    _require(isinstance(receipts, list) and receipts, "explicit player runtime receipts are missing")
    for index, receipt in enumerate(receipts):
        record = _mapping(receipt, f"player_receipts[{index}]")
        _require(record.get("player_confirmed") is True, "player receipt is not explicit player validation")
        _string(record.get("receipt_ref"), f"player_receipts[{index}].receipt_ref")
    return {"observed": True, "runtime_go": True, "player_go": True}


def validate_contract(document: Mapping[str, object], *, root: Path | None = None) -> dict[str, object]:
    """Validate the canonical contract and optional repository source identities."""

    _require(document.get("schema_version") == "vvfp.expanded_256_runtime_evidence.v1", "runtime evidence schema is unsupported")
    integrity = _mapping(document.get("integrity"), "integrity")
    expected_digest = _sha(integrity.get("canonical_sha256"), "integrity.canonical_sha256")
    _require(expected_digest == canonical_sha256(document, remove_key="canonical_sha256"), "canonical runtime evidence JSON digest is stale")
    publication = _mapping(document.get("publication"), "publication")
    _require(publication.get("enabled") is False, "Expanded-256 publication must remain false")
    _require(publication.get("runtime_go") is False and publication.get("player_go") is False and publication.get("eligible") is False, "publication fail-closed fields were relaxed")
    policy = _mapping(document.get("evidence_policy"), "evidence_policy")
    _require(policy.get("required_observed_class") == "player_runtime_receipt", "runtime evidence producer class is not pinned")
    source = _mapping(document.get("source_provenance"), "source_provenance")
    _require(COMMIT_RE.fullmatch(str(source.get("implementation_base_commit"))) is not None, "implementation base commit is not full-length")
    root = (root or ROOT).resolve()
    source_files = source.get("source_files")
    _require(isinstance(source_files, list) and source_files, "runtime source provenance files are missing")
    for item in source_files:
        record = _mapping(item, "source_provenance.source_files item")
        relative = _safe_relative(record.get("path"), "source provenance path")
        path = _assert_no_symlink_components(root, relative)
        _require(path.is_file(), f"runtime source provenance file is missing: {relative}")
        _require(source_text_sha256(path) == _sha(record.get("sha256"), f"source provenance {relative}.sha256"), f"runtime source provenance hash mismatch: {relative}")
    games = _mapping(document.get("games"), "games")
    _require(set(games) == {"vv4", "vv5"}, "runtime evidence must cover exactly VV4 and VV5")
    summaries: dict[str, object] = {}
    for game_id, raw_game in games.items():
        game = _mapping(raw_game, f"games.{game_id}")
        stock = _mapping(game.get("stock_fingerprint"), f"games.{game_id}.stock_fingerprint")
        _require(isinstance(stock.get("size"), int) and stock["size"] > 0, f"stock fingerprint size is invalid: {game_id}")
        _sha(stock.get("sha256"), f"games.{game_id}.stock_fingerprint.sha256")
        expanded = _mapping(game.get("expanded_fingerprints"), f"games.{game_id}.expanded_fingerprints")
        _require(set(expanded) == MODES, f"expanded fingerprint mode set is incomplete: {game_id}")
        for mode, raw_fingerprint in expanded.items():
            fingerprint = _mapping(raw_fingerprint, f"games.{game_id}.expanded_fingerprints.{mode}")
            _sha(fingerprint.get("sha256"), f"games.{game_id}.expanded_fingerprints.{mode}.sha256")
            _require(fingerprint.get("evidence_class") == "static_render_candidate", f"expanded fingerprint is overclaimed: {game_id}/{mode}")
            _require(fingerprint.get("runtime_receipt_required") is True, f"runtime receipt requirement is missing: {game_id}/{mode}")
        ledger = _mapping(game.get("relocation_ledger"), f"games.{game_id}.relocation_ledger")
        relative = _safe_relative(ledger.get("path"), f"games.{game_id}.relocation_ledger.path")
        source_json = json.loads(_assert_no_symlink_components(root, relative).read_text(encoding="utf-8"))
        rows = _json_pointer(source_json, str(ledger["json_pointer"]))
        _require(isinstance(rows, list), f"relocation ledger rows are not a list: {game_id}")
        _require(len(rows) == int(ledger["count"]), f"relocation row count mismatch: {game_id}")
        source_relocation = _mapping(_json_pointer(source_json, "/expanded_shr_relocations"), f"{game_id}.expanded_shr_relocations")
        _require(source_relocation.get("ledger_sha256") == ledger["ledger_sha256"], f"relocation ledger digest mismatch: {game_id}")
        expected_rows_digest = hashlib.sha256(_canonical_bytes(rows)).hexdigest().upper()
        _require(expected_rows_digest == str(ledger["ledger_sha256"]), f"relocation ledger canonical digest mismatch: {game_id}")
        inventory = _mapping(game.get("required_folder_inventory"), f"games.{game_id}.required_folder_inventory")
        _require(inventory.get("status") == "absent" and inventory.get("complete") is False and inventory.get("inventory") is None, f"canonical artifact inventory must remain absent: {game_id}")
        _require(_validate_runtime_evidence(game)["observed"] is False, f"canonical runtime evidence unexpectedly observed: {game_id}")
        summaries[game_id] = {"relocations": len(rows), "runtime_observed": False, "publication_eligible": False}
    return {"schema_version": document["schema_version"], "games": summaries, "publication_eligible": False}


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, object]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    _require(isinstance(value, dict), "runtime evidence contract root must be an object")
    return value


def main(argv: list[str] | None = None) -> int:
    del argv
    try:
        summary = validate_contract(load_contract())
    except (OSError, json.JSONDecodeError, RuntimeEvidenceError) as exc:
        print(f"FAIL: {exc}")
        return 1
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
