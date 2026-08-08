"""Fail-closed validator for disabled VV5 Tech/Detail native evidence."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_PATH = ROOT / "data" / "vv5_tech_detail_native_evidence.json"
SCHEMA_PATH = ROOT / "data" / "vv5_tech_detail_native_evidence.schema.json"
STOCK_SHA256 = "92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D"
INPUT_INVENTORY_SHA256 = "9B9773905E5DA8D7A5B67FB8FD58E70093870429C60853C0023F5FFFEF3BF977"
AUTHENTICATED_EXPORT_SCHEMA = "vvfp.authenticated-native-export.v1"
STOCK = {
    "filename": "Virtual Villagers - New Believers.exe",
    "size": 991232,
    "sha256": STOCK_SHA256,
}
CONTRACT = {
    "resource": "0x6A", "dimensions": [96, 39], "local": [137, 2],
    "message": 8, "event": 13, "factory_va": "0x401BD0",
    "ownership_va": "0x40C680", "tech_constructor_va": "0x4405F0",
    "tech_handler_va": "0x4415F0", "detail_draw_va": "0x44B250",
    "detail_vtable_va": "0x49A590", "detail_destructor_va": "0x44B9F0",
    "detail_input_method_entry_va": "0x44B560",
    "detail_input_method_entry_bytes": "83EC44535556BD7F03000057BF580300",
    "detail_input_stack_locals": "0x44",
    "detail_input_nonvolatile_saves": ["EBX", "EBP", "ESI", "EDI"],
    "detail_input_cleanup": "ret 0xC", "detail_event_method_va": "0x44BC20",
    "detail_event_method_end_va": "0x44BD4C", "detail_event_method_size": 300,
    "detail_event_method_sha256": "DE25D2B76DC7E6337F40F06CBF25FCDCEC411BD9D7F1E7DC78406C157501DC74",
    "detail_event_method_entry_bytes": "83EC18A1A8974D00",
    "detail_event_cleanup": "ret 8", "detail_event_vtable_slot_va": "0x49A5A0",
    "detail_event_message": 8, "detail_event_control_id": 13,
    "detail_stock_control_fields": {"id_1": "+0x58", "id_3": "+0x5C", "id_4": "+0x60"},
    "control_inner_id_offset": "+0x4", "control_inner_parent_offset": "+0x20",
    "detail_constructor_hook_raw": "0x4AF12", "detail_constructor_receiver": "ESI",
    "detail_dispatcher_range": "[0x4019B8,0x4019CF)", "detail_dispatcher_size": 23,
    "detail_dispatcher_sha256": "F2EB107944977E8CBCE7CAD450EC6D1D046880727EBDE36A939CF5DC5DDC907F",
    "detail_dispatcher_call_range": "[0x4019CD,0x4019CF)", "detail_dispatch_vtable_offset": "+0x0C",
    "detail_teardown_chain": ["0x44B9F0", "0x44AF30", "0x40C7F0", "0x40C830"],
    "stock_xref_to_7B22C0": False, "stock_xref_to_7B2600": False,
    "candidate_route_va": "0x7B20C0", "candidate_callsite_va": "0x44BC20",
    "candidate_callsite_raw": "0x4BC20", "candidate_hook_preimage": "83EC18A1A8974D00",
    "candidate_hook_detour": "E99B643600909090", "candidate_continuation_va": "0x44BC28",
    "candidate_guard_message": 8, "candidate_guard_control_id": 13,
    "candidate_fallback_replay": "83EC18A1A8974D00",
    "offline_install_verified": True, "offline_uninstall_verified": True,
    "hot_uninstall_verified": False,
    "rejected_candidate_window_flags_pointer_va": "0x7B2A64",
    "authenticated_window_flags_string_va": "0x7B2A63",
    "rejected_candidate_requested_symbol": "DL_GetWindowFlags",
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
    "candidate_executable_sha256", "candidate_folder_manifest_sha256",
    "candidate_machine_export_sha256", "candidate_machine_export_schema",
    "candidate_machine_export_inventory_sha256",
    "instruction_boundaries_verified", "thiscall_receiver_verified",
    "message_abi_verified", "register_stack_preservation_verified",
    "child_ownership_verified", "child_destructor_verified",
    "range_overlap_verified", "method_entry_rejected_as_callsite",
    "event_method_offline_detour_verified",
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
    byte_values = [_bytes(proof[k], k) for k in ("constructor_stock_bytes", "handler_stock_bytes")]
    continuation_values = [_va(proof[k], k) for k in ("constructor_continuation_va", "handler_continuation_va")]
    candidate_hashes = [_sha(proof[k], f"native_proof.{k}", optional=True) for k in (
        "candidate_executable_sha256", "candidate_folder_manifest_sha256", "candidate_machine_export_sha256"
    )]
    export_schema = proof["candidate_machine_export_schema"]
    if export_schema is not None and export_schema != AUTHENTICATED_EXPORT_SCHEMA:
        raise ValueError("candidate machine export schema is not authenticated-native-export.v1")
    export_inventory = _sha(proof["candidate_machine_export_inventory_sha256"], "candidate machine export inventory", optional=True)
    if export_inventory is not None and export_inventory != INPUT_INVENTORY_SHA256:
        raise ValueError("candidate machine export is not bound to the verified copied-input inventory")
    binding_values = (candidate_hashes[2], export_schema, export_inventory)
    if not (all(value is None for value in binding_values) or all(value is not None for value in binding_values)):
        raise ValueError("candidate machine export hash/schema/inventory binding is incomplete")
    byte_complete = all(byte_values)
    continuation_complete = all(continuation_values)
    flags = [
        "instruction_boundaries_verified", "thiscall_receiver_verified",
        "message_abi_verified", "register_stack_preservation_verified",
        "child_ownership_verified", "child_destructor_verified",
        "range_overlap_verified", "method_entry_rejected_as_callsite",
        "event_method_offline_detour_verified",
    ]
    for key in flags:
        if type(proof[key]) is not bool:
            raise ValueError(f"native_proof.{key} must be exact bool")
    if proof["method_entry_rejected_as_callsite"] is not True:
        raise ValueError("0x44B560 must remain rejected as an event callsite")
    if proof["event_method_offline_detour_verified"] is not True:
        raise ValueError("the exact offline 0x44BC20 event detour must remain verified")
    candidate_complete = bool(all(candidate_hashes) and export_schema == AUTHENTICATED_EXPORT_SCHEMA and export_inventory == INPUT_INVENTORY_SHA256)
    proof_complete = bool(byte_complete and continuation_complete and candidate_complete and proof_folder_hash is not None and all(proof_hashes) and all(proof[k] for k in flags))

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
