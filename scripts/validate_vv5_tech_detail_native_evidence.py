"""Fail-closed validator for disabled VV5 Tech/Detail native evidence."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_PATH = ROOT / "data" / "vv5_tech_detail_native_evidence.json"
SCHEMA_PATH = ROOT / "data" / "vv5_tech_detail_native_evidence.schema.json"
STOCK_SHA256 = "92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D"
STOCK = {
    "filename": "Virtual Villagers - New Believers.exe",
    "size": 991232,
    "sha256": STOCK_SHA256,
}
CONTRACT = {
    "resource": "0x6A", "dimensions": [96, 39], "local": [137, 2],
    "message": 8, "event": 13, "factory_va": "0x401BD0",
    "ownership_va": "0x40C680", "tech_constructor_va": "0x4405F0",
    "tech_handler_va": "0x4415F0", "tech_dialog_target_va": "0x7B22C0",
    "detail_draw_va": "0x44B250", "detail_mouse_callsite_va": "0x44B560",
    "detail_dialog_target_va": "0x7B2600", "forbidden_old_hook_va": "0x44BC20",
    "forbidden_old_hook_raw": "0x4BC20",
    "forbidden_old_hook_preimage": "83EC18A1A8974D00",
    "forbidden_old_hook_continuation_va": "0x44BC28",
}
TOP_KEYS = {
    "id", "game_id", "enabled", "catalog_hidden", "catalog_enabled",
    "publication_ready", "native_output", "status", "stock",
    "folder_evidence", "native_contract", "native_proof", "player_receipts",
    "composition",
}
FOLDER_KEYS = {"authenticated", "complete_folder_verified", "inventory_schema", "file_count", "total_size", "unexpected_files", "manifest_sha256", "authentication_receipt_sha256"}
PROOF_KEYS = {
    "folder_manifest_sha256", "disassembly_artifact_sha256", "instruction_map_sha256",
    "lifecycle_trace_sha256", "overlap_report_sha256",
    "constructor_stock_bytes", "constructor_continuation_va",
    "handler_stock_bytes", "handler_continuation_va",
    "detail_callsite_stock_bytes", "detail_callsite_continuation_va",
    "instruction_boundaries_verified", "thiscall_receiver_verified",
    "message_abi_verified", "register_stack_preservation_verified",
    "child_ownership_verified", "child_destructor_verified",
    "range_overlap_verified", "forbidden_old_hook_rejected",
}
RECEIPT_KEYS = {
    "mode", "action", "stock_sha256", "folder_manifest_sha256",
    "click_reached", "dialog_visible", "owner_verified", "centered",
    "restore_verified", "receipt_sha256",
}
COMPOSITION = {
    "full_mastery_range": "0xF2000-0xF4000",
    "running_range": "0xF4000-0xF6000",
    "ui_ranges": [], "full_heal_ranges": [], "candidate_hooks": [],
    "candidate_caves": [], "patches": [],
}


def _keys(value: object, expected: set[str], label: str) -> dict[str, object]:
    if type(value) is not dict or set(value) != expected:
        raise ValueError(f"{label} schema keys are not exact")
    return value


def _sha(value: object, label: str, *, optional: bool = False) -> str | None:
    if optional and value is None:
        return None
    if type(value) is not str or re.fullmatch(r"[0-9A-F]{64}", value) is None:
        raise ValueError(f"{label} must be uppercase SHA-256")
    return value


def _bytes(value: object, label: str) -> bool:
    if value is None:
        return False
    if type(value) is not str or not value or len(value) % 2 or re.fullmatch(r"[0-9A-F]+", value) is None:
        raise ValueError(f"{label} must be non-empty even-length uppercase hex")
    return True


def _va(value: object, label: str) -> bool:
    if value is None:
        return False
    if type(value) is not str or re.fullmatch(r"0x[0-9A-F]+", value) is None:
        raise ValueError(f"{label} must be an uppercase hexadecimal VA")
    return True


def validate_evidence(record: object) -> bool:
    item = _keys(record, TOP_KEYS, "evidence")
    exact = {
        "id": "vv5_tech_detail_native_evidence_gate", "game_id": "vv5",
        "enabled": False, "catalog_hidden": True, "catalog_enabled": False,
        "publication_ready": False, "native_output": False,
        "status": "pending authenticated full-folder native evidence and player receipts",
    }
    for key, expected in exact.items():
        if type(item[key]) is not type(expected) or item[key] != expected:
            raise ValueError(f"evidence.{key} is not exact")
    if item["stock"] != STOCK or any(type(item["stock"][k]) is not type(v) for k, v in STOCK.items()):
        raise ValueError("stock fingerprint is not exact")
    if item["native_contract"] != CONTRACT:
        raise ValueError("native contract addresses/resource/message are not exact")
    folder = _keys(item["folder_evidence"], FOLDER_KEYS, "folder_evidence")
    for key in ("authenticated", "complete_folder_verified"):
        if type(folder[key]) is not bool:
            raise ValueError(f"folder_evidence.{key} must be exact bool")
    folder_manifest = _sha(folder["manifest_sha256"], "folder manifest", optional=True)
    folder_receipt = _sha(folder["authentication_receipt_sha256"], "folder authentication receipt", optional=True)
    if folder["inventory_schema"] != "vvfp.full-folder-inventory.v1":
        raise ValueError("folder inventory schema is not exact")
    for key in ("file_count", "total_size"):
        if folder[key] is not None and (type(folder[key]) is not int or folder[key] <= 0):
            raise ValueError(f"folder_evidence.{key} must be a positive exact int or null")
    if type(folder["unexpected_files"]) is not list or any(type(v) is not str or not v for v in folder["unexpected_files"]):
        raise ValueError("folder_evidence.unexpected_files must be exact text entries")
    folder_complete = bool(folder["authenticated"] and folder["complete_folder_verified"] and folder_manifest is not None and folder_receipt is not None and folder["file_count"] is not None and folder["total_size"] is not None and folder["unexpected_files"] == [])

    proof = _keys(item["native_proof"], PROOF_KEYS, "native_proof")
    proof_hashes = [
        _sha(proof[key], f"native_proof.{key}", optional=True)
        for key in ("disassembly_artifact_sha256", "instruction_map_sha256", "lifecycle_trace_sha256", "overlap_report_sha256")
    ]
    proof_folder_hash = _sha(proof["folder_manifest_sha256"], "native_proof.folder_manifest_sha256", optional=True)
    if proof_folder_hash is not None and proof_folder_hash != folder_manifest:
        raise ValueError("native proof is not bound to the authenticated folder manifest")
    byte_values = [_bytes(proof[k], k) for k in ("constructor_stock_bytes", "handler_stock_bytes", "detail_callsite_stock_bytes")]
    continuation_values = [_va(proof[k], k) for k in ("constructor_continuation_va", "handler_continuation_va", "detail_callsite_continuation_va")]
    byte_complete = all(byte_values)
    continuation_complete = all(continuation_values)
    flags = [
        "instruction_boundaries_verified", "thiscall_receiver_verified",
        "message_abi_verified", "register_stack_preservation_verified",
        "child_ownership_verified", "child_destructor_verified",
        "range_overlap_verified", "forbidden_old_hook_rejected",
    ]
    for key in flags:
        if type(proof[key]) is not bool:
            raise ValueError(f"native_proof.{key} must be exact bool")
    if proof["forbidden_old_hook_rejected"] is not True:
        raise ValueError("old/current 0x44BC20 must be explicitly rejected")
    proof_complete = bool(byte_complete and continuation_complete and proof_folder_hash is not None and all(proof_hashes) and all(proof[k] for k in flags))

    receipts = _keys(item["player_receipts"], {"tech_windowed", "tech_fullscreen", "detail_windowed", "detail_fullscreen"}, "player_receipts")
    receipt_complete = True
    for key, mode, action in (
        ("tech_windowed", "windowed", "tech"), ("tech_fullscreen", "fullscreen", "tech"),
        ("detail_windowed", "windowed", "detail"), ("detail_fullscreen", "fullscreen", "detail"),
    ):
        receipt = receipts[key]
        if receipt is None:
            receipt_complete = False
            continue
        value = _keys(receipt, RECEIPT_KEYS, f"player_receipts.{key}")
        if value["mode"] != mode or value["action"] != action or value["stock_sha256"] != STOCK_SHA256:
            raise ValueError(f"player_receipts.{key} identity is not exact")
        if value["folder_manifest_sha256"] != folder_manifest:
            raise ValueError(f"player_receipts.{key} is not bound to the authenticated folder")
        for flag in ("click_reached", "dialog_visible", "owner_verified", "centered", "restore_verified"):
            if type(value[flag]) is not bool or value[flag] is not True:
                raise ValueError(f"player_receipts.{key}.{flag} must be verified true")
        _sha(value["receipt_sha256"], f"player_receipts.{key}.receipt_sha256")

    if item["composition"] != COMPOSITION:
        raise ValueError("composition must preserve final FM/Running ranges and claim no UI/Full Heal bytes")
    return bool(folder_complete and proof_complete and receipt_complete)


def load_and_validate(path: Path = EVIDENCE_PATH) -> tuple[dict[str, object], bool]:
    if not SCHEMA_PATH.is_file():
        raise ValueError("evidence schema is missing")
    record = json.loads(path.read_text(encoding="utf-8"))
    return record, validate_evidence(record)


if __name__ == "__main__":
    _, complete = load_and_validate()
    print(json.dumps({"evidence_complete": complete, "publication_ready": False, "native_output": False}, sort_keys=True))
