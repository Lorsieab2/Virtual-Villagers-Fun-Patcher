"""Validate the fail-closed VV4/VV5 Expanded-256 stored-index gate.

This validator consumes committed static contracts and optional future evidence
rows.  It never launches a game, reads a save, emits a package, or changes a
publication flag.  Manifest bound edits are candidate evidence only; an
observed path also needs exact function/instruction/operand/storage/sentinel/
xref fields and authenticated player runtime receipts.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Mapping


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "data" / "expanded_256_stored_index_evidence.json"
SHA256_RE = re.compile(r"^[0-9A-F]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
HEX_RE = re.compile(r"^0x[0-9A-F]+$")
CATEGORIES = (
    "selection",
    "roster",
    "detail",
    "queue_actions",
    "pairing_pregnancy",
    "birth_death",
    "skeleton_memorial",
    "events_puzzles",
    "statistics",
    "callbacks",
    "serializer_load_catchup",
)
REQUIRED_ROW_FIELDS = {
    "path_id",
    "category",
    "function_name",
    "function_ea",
    "instruction_ea",
    "operand_file_offset",
    "operand_width_bits",
    "storage_width_bits",
    "sentinel",
    "xrefs",
    "record_255",
    "indices_256_259",
    "runtime_receipt_refs",
    "source",
    "synthetic",
}
CATEGORY_FIELDS = {
    "category",
    "status",
    "candidate_edit_refs",
    "expected_path_count",
    "path_ledger_sha256",
    "evidence_rows",
    "missing_evidence",
}
EXPECTED_STOCK = {
    "vv4": (
        "Virtual Villagers - The Tree of Life.exe",
        929792,
        "6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220",
    ),
    "vv5": (
        "Virtual Villagers - New Believers.exe",
        991232,
        "92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D",
    ),
}
EXPECTED_RELOCATIONS = {
    "vv4": ("data/vv4_origins_feature.json", 13, "CEE01F4AEC59CB1CEE0F42E3DDDB3A24615261E628ED0629C1BFAABF421A897D"),
    "vv5": ("data/vv5_origins_feature.json", 66, "A5DF4E109D32E2BC9FDE36E2BA3139230B6E6CD89DE4C3FF784846F4CE803740"),
}
EXPECTED_CANDIDATE_OFFSETS = {
    "vv4": {
        "selection": {
            "0x66045", "0x6683F", "0x66845", "0x66A0F", "0x66A15",
            "0x66AE0", "0x66AE6", "0x669CC", "0x66E6F", "0x66F11",
            "0x66C9C",
        },
        "serializer_load_catchup": {"0x1FC19", "0x8910D"},
    },
    "vv5": {
        "selection": {
            "0x6F955", "0x70280", "0x70291", "0x70381", "0x704F6",
            "0x7058C", "0x705DF", "0x70700", "0x708FC", "0x70AFC",
            "0x70BB6", "0x71D77",
        },
        "serializer_load_catchup": {"0x25709", "0x9466C", "0x6FA75"},
    },
}
RUNTIME_CONTRACT_SHA256 = "C70F0BD0CDDFF921B215FA178D725A57EC2AEE380C575FFD1D56D8F282562B60"
HARNESS_SHA256 = "719DAD95AC6AB2D2E1CC9F64DECF1BB894CC4A98B5B7662A3A84402B2C5CA321"


class StoredIndexEvidenceError(ValueError):
    """Raised when the stored-index contract is stale, incomplete, or unsafe."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise StoredIndexEvidenceError(message)


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonical_sha256(value: Mapping[str, object], *, remove_key: str) -> str:
    copy_value = copy.deepcopy(dict(value))
    if remove_key == "canonical_sha256" and isinstance(copy_value.get("integrity"), Mapping):
        copy_value["integrity"].pop(remove_key, None)
    else:
        copy_value.pop(remove_key, None)
    return hashlib.sha256(_canonical_bytes(copy_value)).hexdigest().upper()


def evidence_row_sha256(row: Mapping[str, object]) -> str:
    copy_row = copy.deepcopy(dict(row))
    source = copy_row.get("source")
    if isinstance(source, Mapping):
        source.pop("row_sha256", None)
    return hashlib.sha256(_canonical_bytes(copy_row)).hexdigest().upper()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _sha(value: object, label: str) -> str:
    _require(isinstance(value, str) and SHA256_RE.fullmatch(value) is not None, f"{label} must be uppercase SHA-256")
    return value


def _hex(value: object, label: str) -> str:
    _require(isinstance(value, str) and HEX_RE.fullmatch(value) is not None, f"{label} must be uppercase hexadecimal")
    return value


def _normalized_offset(value: object) -> str:
    _require(isinstance(value, str), "manifest offset must be a string")
    try:
        return f"0x{int(value, 16):X}"
    except ValueError as exc:
        raise StoredIndexEvidenceError(f"manifest offset is invalid: {value}") from exc


def _mapping(value: object, label: str) -> Mapping[str, object]:
    _require(isinstance(value, Mapping), f"{label} must be an object")
    return value


def _safe_relative(value: object, label: str) -> str:
    _require(isinstance(value, str) and value, f"{label} must be a non-empty path")
    normalized = value.replace("\\", "/")
    parsed = PurePosixPath(normalized)
    _require(not parsed.is_absolute() and ".." not in parsed.parts, f"{label} must be relative without parent traversal")
    return normalized


def _json_pointer(value: object, pointer: str) -> object:
    _require(pointer.startswith("/"), "JSON pointer must start with '/'")
    current = value
    for token in pointer[1:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, Mapping):
            _require(token in current, f"JSON pointer is missing: {pointer}")
            current = current[token]
        elif isinstance(current, list):
            _require(token.isdigit() and int(token) < len(current), f"JSON pointer index is missing: {pointer}")
            current = current[int(token)]
        else:
            raise StoredIndexEvidenceError(f"JSON pointer cannot descend: {pointer}")
    return current


def _source_path(root: Path, relative: object, label: str) -> Path:
    normalized = _safe_relative(relative, label)
    path = root.joinpath(*PurePosixPath(normalized).parts)
    _require(path.is_file() and not path.is_symlink(), f"{label} is missing or a symlink: {normalized}")
    return path


def _validate_source_provenance(document: Mapping[str, object], root: Path) -> None:
    provenance = _mapping(document.get("source_provenance"), "source_provenance")
    _require(COMMIT_RE.fullmatch(str(provenance.get("implementation_base_commit"))) is not None, "implementation base commit is not full-length")
    schema = _mapping(provenance.get("schema"), "source_provenance.schema")
    schema_path = _source_path(root, schema.get("path"), "schema path")
    _require(_sha256(schema_path) == _sha(schema.get("sha256"), "schema SHA-256"), "stored-index schema hash is stale")
    schema_json = json.loads(schema_path.read_text(encoding="utf-8"))
    _require(schema_json.get("$id") == document.get("schema_version"), "stored-index schema id is stale")
    source_files = provenance.get("source_files")
    _require(isinstance(source_files, list) and source_files, "source provenance file list is missing")
    seen: set[str] = set()
    for raw_record in source_files:
        record = _mapping(raw_record, "source provenance record")
        relative = _safe_relative(record.get("path"), "source provenance path")
        _require(relative not in seen, f"duplicate source provenance path: {relative}")
        seen.add(relative)
        path = _source_path(root, relative, "source provenance path")
        _require(_sha256(path) == _sha(record.get("sha256"), f"source provenance hash {relative}"), f"source provenance hash is stale: {relative}")


def _validate_relocation(game_id: str, game: Mapping[str, object], root: Path) -> None:
    ledger = _mapping(game.get("relocation_ledger"), f"{game_id}.relocation_ledger")
    expected_path, expected_count, expected_digest = EXPECTED_RELOCATIONS[game_id]
    _require(ledger.get("path") == expected_path, f"{game_id} relocation path is stale")
    _require(ledger.get("count") == expected_count, f"{game_id} relocation count is stale")
    _require(ledger.get("ledger_sha256") == expected_digest, f"{game_id} relocation digest is stale")
    source = json.loads(_source_path(root, expected_path, f"{game_id} relocation source").read_text(encoding="utf-8"))
    rows = _json_pointer(source, str(ledger.get("json_pointer")))
    _require(isinstance(rows, list) and len(rows) == expected_count, f"{game_id} relocation rows are incomplete")
    digest = hashlib.sha256(_canonical_bytes(rows)).hexdigest().upper()
    _require(digest == expected_digest, f"{game_id} relocation rows have changed")


def _validate_candidate_edits(game_id: str, game: Mapping[str, object], manifest: Mapping[str, object]) -> dict[str, set[str]]:
    edits = game.get("candidate_static_edits")
    _require(isinstance(edits, list), f"{game_id} candidate static edits are missing")
    manifest_game = _mapping(_mapping(manifest.get("games"), "expanded manifest games").get(game_id), f"expanded manifest {game_id}")
    patches = manifest_game.get("patches")
    _require(isinstance(patches, list), f"expanded manifest patches are missing: {game_id}")
    by_offset = {_normalized_offset(row["offset"]): row for row in patches}
    expected_by_category = EXPECTED_CANDIDATE_OFFSETS[game_id]
    expected_offsets = set().union(*expected_by_category.values())
    ids: set[str] = set()
    offsets: set[str] = set()
    refs_by_category: dict[str, set[str]] = {category: set() for category in CATEGORIES}
    for raw_edit in edits:
        edit = _mapping(raw_edit, f"{game_id} candidate edit")
        edit_id = str(edit.get("id"))
        category = str(edit.get("category"))
        offset = _normalized_offset(edit.get("manifest_offset"))
        _require(edit_id not in ids, f"duplicate candidate edit id: {game_id}/{edit_id}")
        _require(offset not in offsets, f"duplicate candidate edit offset: {game_id}/{offset}")
        _require(category in CATEGORIES, f"candidate edit category is unknown: {game_id}/{category}")
        _require(edit.get("qualifying_evidence") is False, f"candidate edit was overclaimed as evidence: {game_id}/{offset}")
        _require(offset in by_offset, f"candidate edit is missing from expanded manifest: {game_id}/{offset}")
        row_digest = hashlib.sha256(_canonical_bytes(by_offset[offset])).hexdigest().upper()
        _require(row_digest == _sha(edit.get("manifest_row_sha256"), f"candidate edit digest {game_id}/{offset}"), f"candidate edit digest is stale: {game_id}/{offset}")
        ids.add(edit_id)
        offsets.add(offset)
        refs_by_category[category].add(edit_id)
    _require(offsets == expected_offsets, f"{game_id} candidate edit set is missing or has extras")
    for category, expected in expected_by_category.items():
        actual = {_normalized_offset(edit["manifest_offset"]) for edit in edits if edit.get("category") == category}
        _require(actual == expected, f"{game_id} candidate edit category partition is stale: {category}")
    return refs_by_category


def _validate_evidence_row(
    row: Mapping[str, object],
    *,
    game_id: str,
    category: str,
    root: Path,
) -> str:
    _require(set(row) == REQUIRED_ROW_FIELDS, f"evidence row fields are incomplete or injected: {game_id}/{category}")
    path_id = row.get("path_id")
    _require(isinstance(path_id, str) and path_id.startswith(f"{game_id}-"), f"evidence path id is not game-scoped: {game_id}/{category}")
    _require(row.get("category") == category, f"evidence row category is stale: {path_id}")
    _require(isinstance(row.get("function_name"), str) and row["function_name"], f"evidence function name is missing: {path_id}")
    for field in ("function_ea", "instruction_ea", "operand_file_offset"):
        _hex(row.get(field), f"evidence {field}: {path_id}")
    operand_width = row.get("operand_width_bits")
    storage_width = row.get("storage_width_bits")
    _require(operand_width in {8, 16, 32} and storage_width in {8, 16, 32}, f"evidence width is unsupported: {path_id}")
    sentinel = _mapping(row.get("sentinel"), f"evidence sentinel: {path_id}")
    _require(set(sentinel) == {"width_bits", "encoding", "unsigned_value", "meaning"}, f"evidence sentinel fields are incomplete: {path_id}")
    _require(sentinel.get("width_bits") == storage_width, f"evidence sentinel width differs from storage: {path_id}")
    if sentinel.get("encoding") == "none":
        _require(sentinel.get("unsigned_value") is None and sentinel.get("meaning") == "none", f"none-sentinel encoding is invalid: {path_id}")
    else:
        _require(sentinel.get("encoding") in {"unsigned", "twos_complement"}, f"evidence sentinel encoding is invalid: {path_id}")
        _require(isinstance(sentinel.get("unsigned_value"), int) and sentinel.get("meaning") == "no_record", f"evidence sentinel value is invalid: {path_id}")
        _require(0 <= int(sentinel["unsigned_value"]) < (1 << int(storage_width)), f"evidence sentinel exceeds its width: {path_id}")
    record_255 = _mapping(row.get("record_255"), f"record-255 proof: {path_id}")
    padding = _mapping(row.get("indices_256_259"), f"256-259 proof: {path_id}")
    _require(record_255.get("accepted") is True and isinstance(record_255.get("proof"), str) and record_255["proof"], f"record 255 is not proved accepted: {path_id}")
    _require(padding.get("unreachable") is True and padding.get("non_saveable") is True and isinstance(padding.get("proof"), str) and padding["proof"], f"indices 256-259 are not proved unreachable/non-saveable: {path_id}")
    if storage_width == 8 and sentinel.get("unsigned_value") == 0xFF:
        raise StoredIndexEvidenceError(f"byte 0xFF is ambiguous with valid record 255: {path_id}")
    xrefs = row.get("xrefs")
    _require(isinstance(xrefs, list) and xrefs, f"evidence xrefs are missing: {path_id}")
    xref_keys: set[tuple[str, str]] = set()
    for raw_xref in xrefs:
        xref = _mapping(raw_xref, f"evidence xref: {path_id}")
        _require(set(xref) == {"from_function", "from_ea", "kind"}, f"evidence xref fields are incomplete: {path_id}")
        _require(isinstance(xref.get("from_function"), str) and xref["from_function"], f"evidence xref function is missing: {path_id}")
        from_ea = _hex(xref.get("from_ea"), f"evidence xref EA: {path_id}")
        _require(xref.get("kind") in {"call", "jump", "data", "callback", "serializer"}, f"evidence xref kind is invalid: {path_id}")
        key = (from_ea, str(xref["kind"]))
        _require(key not in xref_keys, f"duplicate evidence xref: {path_id}/{from_ea}")
        xref_keys.add(key)
    refs = row.get("runtime_receipt_refs")
    _require(isinstance(refs, list) and refs and all(isinstance(ref, str) and ref for ref in refs), f"runtime receipt refs are missing: {path_id}")
    _require(len(refs) == len(set(refs)), f"runtime receipt refs are duplicated: {path_id}")
    _require(row.get("synthetic") is False, f"synthetic evidence is forbidden: {path_id}")
    source = _mapping(row.get("source"), f"evidence source: {path_id}")
    _require(source.get("provenance") == "exact_ida_plus_player_runtime_receipt", f"evidence provenance is not exact/player-observed: {path_id}")
    artifact = _source_path(root, source.get("artifact"), f"evidence source artifact: {path_id}")
    _require(_sha256(artifact) == _sha(source.get("sha256"), f"evidence source hash: {path_id}"), f"evidence source hash is stale: {path_id}")
    _require(evidence_row_sha256(row) == _sha(source.get("row_sha256"), f"evidence row digest: {path_id}"), f"evidence row digest is stale: {path_id}")
    return path_id


def _validate_index_model(game_id: str, game: Mapping[str, object]) -> None:
    model = _mapping(game.get("index_model"), f"{game_id}.index_model")
    if game_id == "vv4":
        _require(model.get("status") == "unknown_stop", "VV4 index model must remain independently unknown")
        _require(model.get("storage_width_bits") is None and model.get("sentinel") is None, "VV5 width/sentinel was generalized to VV4")
        _require(model.get("cited_static_fragments") == [], "VV4 has uncited stored-index fragments")
        _require(model.get("generalizable_from_vv5") is False, "VV5 index evidence was generalized to VV4")
        return
    _require(model.get("status") == "partial_static_stop", "VV5 partial index model was overclaimed")
    _require(model.get("storage_width_bits") == 32, "VV5 cited index width is stale")
    sentinel = _mapping(model.get("sentinel"), "VV5 cited sentinel")
    _require(sentinel == {"width_bits": 32, "encoding": "twos_complement", "unsigned_value": 4294967295, "meaning": "no_record"}, "VV5 cited DWORD/-1 sentinel is stale")
    fragments = model.get("cited_static_fragments")
    _require(isinstance(fragments, list) and len(fragments) == 3, "VV5 cited fragments are incomplete")
    by_id = {fragment.get("path_id"): fragment for fragment in fragments if isinstance(fragment, Mapping)}
    _require(set(by_id) == {"record_lookup", "selected_villager", "pending_record_list"}, "VV5 cited fragment ids are stale")
    _require(by_id["record_lookup"].get("function_name") == "sub_46F950" and by_id["record_lookup"].get("function_ea") == "0x46F950", "VV5 record-lookup citation is stale")
    _require(by_id["selected_villager"].get("function_name") == "sub_4708F0" and by_id["selected_villager"].get("function_ea") == "0x4708F0", "VV5 selected-villager citation is stale")
    _require(by_id["pending_record_list"].get("function_name") is None and by_id["pending_record_list"].get("function_ea") is None, "VV5 pending-list unknown function was invented")
    _require(model.get("generalizable_to_other_paths") is False and model.get("generalizable_to_vv4") is False, "VV5 DWORD evidence was generalized outside cited paths")


def _validate_game(game_id: str, game: Mapping[str, object], *, root: Path, manifest: Mapping[str, object]) -> dict[str, object]:
    stock = _mapping(game.get("stock_fingerprint"), f"{game_id}.stock_fingerprint")
    expected_name, expected_size, expected_hash = EXPECTED_STOCK[game_id]
    _require((stock.get("filename"), stock.get("size"), stock.get("sha256")) == (expected_name, expected_size, expected_hash), f"{game_id} stock fingerprint is stale")
    folder = _mapping(game.get("full_folder_fingerprint"), f"{game_id}.full_folder_fingerprint")
    _require(folder.get("required_role_count") == 9 and folder.get("inventory_schema") == "vvfp.runtime_capture_folder_inventory.v1", f"{game_id} full-folder requirements are stale")
    capture = _mapping(game.get("runtime_capture_binding"), f"{game_id}.runtime_capture_binding")
    _require(capture.get("schema_version") == "vvfp.expanded_256_runtime_capture.v1", f"{game_id} runtime capture schema is stale")
    _require(capture.get("harness_path") == "scripts/capture_expanded_runtime_evidence.py" and capture.get("harness_sha256") == HARNESS_SHA256, f"{game_id} runtime capture harness binding is stale")
    _require(capture.get("contract_canonical_sha256") == RUNTIME_CONTRACT_SHA256, f"{game_id} runtime evidence contract binding is stale")
    if folder.get("status") == "absent_stop":
        _require(folder.get("canonical_inventory_sha256") is None and folder.get("runtime_receipt_sha256") is None, f"{game_id} absent folder evidence has hashes")
    else:
        _require(folder.get("status") == "observed_exact", f"{game_id} full-folder status is unsupported")
        _sha(folder.get("canonical_inventory_sha256"), f"{game_id} full-folder digest")
        _sha(folder.get("runtime_receipt_sha256"), f"{game_id} full-folder receipt digest")
    if capture.get("status") == "absent_stop":
        _require(capture.get("capture_packet_sha256") is None and capture.get("authenticated") is False, f"{game_id} absent runtime capture is overclaimed")
    else:
        _require(capture.get("status") == "observed_authenticated" and capture.get("authenticated") is True, f"{game_id} runtime capture is not authenticated")
        _sha(capture.get("capture_packet_sha256"), f"{game_id} capture packet digest")
    _validate_relocation(game_id, game, root)
    layout = _mapping(game.get("layout_boundary"), f"{game_id}.layout_boundary")
    _require((layout.get("logical_records"), layout.get("physical_records"), layout.get("padding_records")) == (256, 256, 0), f"{game_id} layout count or padding claim is stale")
    record_255 = _mapping(layout.get("record_255"), f"{game_id}.record_255")
    padding = _mapping(layout.get("indices_256_259"), f"{game_id}.indices_256_259")
    _require(record_255.get("layout_state") == "allocated", f"{game_id} record 255 is not allocated")
    _require(padding.get("layout_state") == "outside_record_pool", f"{game_id} indices 256-259 were treated as records/padding")
    if record_255.get("path_acceptance_proof") == "observed_complete" or padding.get("unreachable_proof") == "observed_complete" or padding.get("non_saveable_proof") == "observed_complete":
        _require(folder.get("status") == "observed_exact" and capture.get("status") == "observed_authenticated", f"{game_id} padding/reachability was claimed without exact runtime evidence")
    else:
        _require(record_255.get("path_acceptance_proof") == "partial_static_stop", f"{game_id} record-255 proof status is invalid")
        _require(padding.get("unreachable_proof") == "absent_stop" and padding.get("non_saveable_proof") == "absent_stop", f"{game_id} 256-259 proof status is invalid")
    _validate_index_model(game_id, game)
    refs_by_category = _validate_candidate_edits(game_id, game, manifest)
    categories = game.get("path_categories")
    _require(isinstance(categories, list), f"{game_id} path categories are missing")
    category_names = [category.get("category") for category in categories if isinstance(category, Mapping)]
    _require(tuple(category_names) == CATEGORIES, f"{game_id} path categories are missing, duplicated, or reordered")
    path_ids: set[str] = set()
    complete = 0
    for raw_category in categories:
        category = _mapping(raw_category, f"{game_id} path category")
        _require(set(category) == CATEGORY_FIELDS, f"{game_id} category fields are incomplete or injected")
        name = str(category["category"])
        refs = category.get("candidate_edit_refs")
        _require(isinstance(refs, list) and set(refs) == refs_by_category[name] and len(refs) == len(set(refs)), f"{game_id} candidate edit refs are incomplete or duplicated: {name}")
        rows = category.get("evidence_rows")
        missing = category.get("missing_evidence")
        _require(isinstance(rows, list) and isinstance(missing, list), f"{game_id} evidence rows/missing list is invalid: {name}")
        for raw_row in rows:
            row = _mapping(raw_row, f"{game_id} evidence row")
            path_id = _validate_evidence_row(row, game_id=game_id, category=name, root=root)
            _require(path_id not in path_ids, f"duplicate stored-index path id: {game_id}/{path_id}")
            path_ids.add(path_id)
        status = category.get("status")
        if status == "observed_complete":
            _require(rows and not missing, f"{game_id} observed category lacks complete evidence: {name}")
            expected_path_count = category.get("expected_path_count")
            _require(isinstance(expected_path_count, int) and expected_path_count > 0, f"{game_id} observed category lacks an exact path count: {name}")
            _require(len(rows) == expected_path_count, f"{game_id} observed category path count is incomplete: {name}")
            ledger_digest = hashlib.sha256(_canonical_bytes(rows)).hexdigest().upper()
            _require(category.get("path_ledger_sha256") == ledger_digest, f"{game_id} observed category path ledger digest is stale: {name}")
            complete += 1
        else:
            _require(status in {"unknown_stop", "partial_static_stop"}, f"{game_id} category status is unsupported: {name}")
            _require(not rows and missing, f"{game_id} STOP category contains evidence or lacks a blocker: {name}")
            _require(category.get("expected_path_count") is None and category.get("path_ledger_sha256") is None, f"{game_id} STOP category claims an exact path ledger: {name}")
    if complete:
        _require(folder.get("status") == "observed_exact" and capture.get("status") == "observed_authenticated", f"{game_id} completed path category lacks exact folder/runtime evidence")
    return {
        "candidate_edits": len(game["candidate_static_edits"]),
        "categories_complete": complete,
        "categories_total": len(CATEGORIES),
        "relocations": EXPECTED_RELOCATIONS[game_id][1],
        "status": "STOP" if complete != len(CATEGORIES) else "EVIDENCE_COMPLETE_PUBLICATION_STILL_FALSE",
    }


def validate_contract(document: Mapping[str, object], *, root: Path | None = None) -> dict[str, object]:
    root = (root or ROOT).resolve()
    _require(document.get("schema_version") == "vvfp.expanded_256_stored_index_evidence.v1", "stored-index schema version is unsupported")
    _require(document.get("contract_id") == "x45-vv4-vv5-expanded-256-stored-index-evidence", "stored-index contract id is stale")
    integrity = _mapping(document.get("integrity"), "integrity")
    _require(integrity.get("canonical_sha256") == canonical_sha256(document, remove_key="canonical_sha256"), "stored-index contract canonical digest is stale")
    publication = _mapping(document.get("publication"), "publication")
    _require(all(publication.get(field) is False for field in ("enabled", "runtime_go", "player_go", "eligible")), "stored-index publication guard was relaxed")
    policy = _mapping(document.get("evidence_policy"), "evidence_policy")
    _require(policy.get("required_categories") == list(CATEGORIES), "stored-index required category list is stale")
    _require(set(policy.get("required_observed_row_fields", [])) == REQUIRED_ROW_FIELDS, "stored-index required row fields are stale")
    _require(policy.get("synthetic_evidence") == "forbidden" and policy.get("manual_field_injection") == "forbidden", "stored-index evidence policy was relaxed")
    _validate_source_provenance(document, root)
    manifest = json.loads((root / "data" / "expanded_256.json").read_text(encoding="utf-8"))
    games = _mapping(document.get("games"), "games")
    _require(set(games) == {"vv4", "vv5"}, "stored-index contract must contain exactly VV4 and VV5")
    summaries = {
        game_id: _validate_game(game_id, _mapping(games[game_id], f"games.{game_id}"), root=root, manifest=manifest)
        for game_id in ("vv4", "vv5")
    }
    all_complete = all(summary["categories_complete"] == len(CATEGORIES) for summary in summaries.values())
    if document.get("status") == "observed_complete":
        _require(all_complete, "stored-index contract status is complete while required paths remain STOP")
    else:
        _require(document.get("status") == "static_partial_stop" and not all_complete, "stored-index contract STOP status is inconsistent")
    return {
        "schema_version": document["schema_version"],
        "status": "STOP" if not all_complete else "EVIDENCE_COMPLETE_PUBLICATION_STILL_FALSE",
        "publication_eligible": False,
        "games": summaries,
    }


def main() -> int:
    try:
        document = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        result = validate_contract(document, root=ROOT)
    except (OSError, json.JSONDecodeError, StoredIndexEvidenceError) as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
