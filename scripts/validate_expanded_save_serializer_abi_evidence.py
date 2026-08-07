#!/usr/bin/env python3
"""Fail-closed validator for VV4/VV5 Expanded-256 save/serializer ABI evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "data" / "expanded_256_save_serializer_abi_evidence.json"
SCHEMA_VERSION = "vvfp.expanded_256_save_serializer_abi_evidence.v1"
REQUIREMENTS = ["save_layout_sizes", "loader_abi", "stock_import_conversion", "writer_record_count_tail", "serializer_bounds", "deserializer_bounds", "padding_non_saveability", "integrity_transform", "slot_rotation_atomicity", "failed_load_nonmutation", "offline_catchup_ordering", "manager_pool_identity_reload", "current_origins_behavior", "complete_folder_runtime_player_receipts"]
NATIVE_FIELDS = {"row_id", "requirement", "function_name", "function_ea", "instruction_ea", "file_offset", "preimage", "calling_convention", "return_semantics", "failure_semantics", "xrefs", "artifact", "runtime_receipt_refs", "player_receipt_refs", "synthetic"}
GAME_PINS = {
    "vv4": {"stock": ("Virtual Villagers - The Tree of Life.exe", 929792, "6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220"), "expanded": ((929792, "602824F514BFAB80883805B16C01D1E572752261A155262778CF8D535C41D887"), (929792, "AC430442DE23406236903CAA6FC9A992D52DCF3269A95ED345A9EF6F18B9C30A")), "relocation": (13, "CEE01F4AEC59CB1CEE0F42E3DDDB3A24615261E628ED0629C1BFAABF421A897D")},
    "vv5": {"stock": ("Virtual Villagers - New Believers.exe", 991232, "92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D"), "expanded": ((991232, "44042572653782B20A200799785F437D4D76B46F20384D597B8093F27CC88C89"), (991232, "6BF9E0EB9BC7D3C373E32C3A7377C9A7EA35C1FA889EEDBF9B2819A25BC43E86")), "relocation": (66, "A5DF4E109D32E2BC9FDE36E2BA3139230B6E6CD89DE4C3FF784846F4CE803740")},
}

class SaveSerializerEvidenceError(ValueError):
    pass

def _bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()

def sha(value: Any) -> str:
    return hashlib.sha256(_bytes(value)).hexdigest().upper()

def contract_sha(doc: dict[str, Any]) -> str:
    copy = json.loads(json.dumps(doc)); copy["integrity"]["canonical_sha256"] = None
    return sha(copy)

def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()

def fail(condition: bool, message: str) -> None:
    if condition: raise SaveSerializerEvidenceError(message)

def validate_contract(doc: dict[str, Any], root: Path = ROOT) -> dict[str, Any]:
    fail(doc.get("schema_version") != SCHEMA_VERSION, "schema version mismatch")
    fail(doc.get("status") not in {"evidence_empty_stop", "partial_stop", "observed_complete_stop"}, "invalid contract status")
    pub = doc.get("publication", {})
    fail(any(pub.get(k) is not False for k in ("enabled", "runtime_go", "player_go", "eligible")), "publication must remain false")
    fail(doc.get("policy", {}).get("native_emission") is not False, "native emission must remain disabled")
    fail(doc.get("required_requirements") != REQUIREMENTS, "required requirement set/order mismatch")
    fail(doc.get("integrity", {}).get("canonical_sha256") != contract_sha(doc), "canonical contract digest is stale")
    bindings = doc.get("bindings", {})
    for key in ("schema", "stored_index_contract", "runtime_contract", "runtime_harness"):
        item = bindings.get(key, {}); path = root / item.get("path", "")
        fail(not path.is_file() or file_sha(path) != item.get("file_sha256"), f"{key} binding is stale")
    stored = json.loads((root / bindings["stored_index_contract"]["path"]).read_text(encoding="utf-8"))
    runtime = json.loads((root / bindings["runtime_contract"]["path"]).read_text(encoding="utf-8"))
    fail(stored["integrity"]["canonical_sha256"] != bindings["stored_index_contract"]["canonical_sha256"], "stored-index canonical binding is stale")
    fail(runtime["integrity"]["canonical_sha256"] != bindings["runtime_contract"]["canonical_sha256"], "runtime canonical binding is stale")
    summary = {}
    all_complete = True
    for game, pins in GAME_PINS.items():
        value = doc.get("games", {}).get(game, {})
        stock = value.get("stock_fingerprint", {})
        fail((stock.get("filename"), stock.get("size"), stock.get("sha256")) != pins["stock"], f"{game} stock fingerprint mismatch")
        expanded = value.get("expanded_fingerprints", {})
        got = tuple((expanded.get(mode, {}).get("size"), expanded.get(mode, {}).get("sha256")) for mode in ("experimental_expanded_256", "experimental_expanded_256_progression"))
        fail(got != pins["expanded"], f"{game} expanded fingerprints mismatch")
        reloc = value.get("relocation_ledger", {})
        fail((reloc.get("count"), reloc.get("ledger_sha256")) != pins["relocation"], f"{game} relocation ledger mismatch")
        fail(file_sha(root / reloc.get("path", "")) != reloc.get("file_sha256"), f"{game} relocation artifact is stale")
        matrix = value.get("evidence_matrix", [])
        fail([x.get("requirement") for x in matrix] != REQUIREMENTS, f"{game} missing, duplicate, or reordered requirements")
        seen = set(); complete = 0
        for entry in matrix:
            requirement = entry["requirement"]; rows = entry.get("native_rows", [])
            fail(entry.get("status") not in {"unknown_stop", "partial_stop", "observed_complete"}, f"{game} {requirement} invalid status")
            if entry["status"] != "observed_complete":
                fail(rows or entry.get("expected_row_count") is not None or entry.get("row_ledger_sha256") is not None, f"{game} {requirement} nonqualifying rows must remain empty")
                fail(not entry.get("missing_evidence"), f"{game} {requirement} missing-evidence list is empty")
                continue
            complete += 1
            fail(not rows or entry.get("expected_row_count") != len(rows), f"{game} {requirement} native row count is incomplete")
            fail(entry.get("row_ledger_sha256") != sha(rows), f"{game} {requirement} native row ledger digest is stale")
            fail(not entry.get("runtime_receipt_refs") or not entry.get("player_receipt_refs"), f"{game} {requirement} authenticated receipts are missing")
            fail(entry.get("missing_evidence") != [], f"{game} {requirement} cannot be complete with missing evidence")
            for row in rows:
                fail(set(row) != NATIVE_FIELDS, f"{game} {requirement} native fields are incomplete or injected")
                fail(row["requirement"] != requirement or row["row_id"] in seen, f"{game} duplicate or misclassified native row")
                seen.add(row["row_id"])
                fail(row["synthetic"] is not False, f"{game} synthetic evidence is forbidden")
                fail(not all(row.get(k) for k in ("function_name", "function_ea", "instruction_ea", "file_offset", "preimage", "calling_convention", "return_semantics", "failure_semantics", "xrefs", "runtime_receipt_refs", "player_receipt_refs")), f"{game} {requirement} exact native evidence is incomplete")
                artifact = row.get("artifact", {}); source = root / artifact.get("path", "")
                fail(artifact.get("evidence_class") != "authenticated_native_artifact" or not source.is_file() or file_sha(source) != artifact.get("sha256"), f"{game} {requirement} exact artifact is unauthenticated or stale")
        folder = value.get("complete_folder", {})
        layout = value.get("save_layout", {})
        if complete:
            fail(folder.get("status") != "observed_complete" or folder.get("authenticated") is not True or not folder.get("inventory_sha256"), f"{game} complete-folder receipt is absent")
            fail(layout.get("status") != "observed_complete" or any(layout.get(k) is None for k in ("stock_size", "expanded_size", "stock_layout_sha256", "expanded_layout_sha256")), f"{game} exact save layouts are absent")
        all_complete &= complete == len(REQUIREMENTS)
        summary[game] = {"requirements_complete": complete, "requirements_total": len(REQUIREMENTS), "relocations": reloc["count"], "status": "STOP"}
    fail(all_complete, "this evidence contract cannot enable GO or publication")
    return {"schema_version": SCHEMA_VERSION, "games": summary, "publication_eligible": False, "status": "STOP"}

def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("contract", nargs="?", type=Path, default=CONTRACT)
    args = parser.parse_args(); print(json.dumps(validate_contract(json.loads(args.contract.read_text(encoding="utf-8"))), sort_keys=True)); return 0

if __name__ == "__main__": raise SystemExit(main())
