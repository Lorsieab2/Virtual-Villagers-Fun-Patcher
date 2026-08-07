"""Validate the disabled VV5 Full Heal native-ABI evidence gate."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_PATH = ROOT / "data" / "vv5_full_heal_native_abi_evidence.json"
SCHEMA_PATH = ROOT / "data" / "vv5_full_heal_native_abi_evidence.schema.json"
STOCK_SHA256 = "92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D"
TOP_KEYS = {"id", "game_id", "enabled", "catalog_hidden", "catalog_enabled", "publication_ready", "native_output", "status", "stock", "folder_evidence", "record_contract", "native_abis", "transaction_evidence", "messages", "ui_lifecycle", "composition"}
FOLDER_KEYS = {"schema", "authenticated", "complete", "file_count", "total_size", "unexpected_files", "manifest_sha256", "receipt_sha256"}
RECORD_KEYS = {"count", "stride", "active_offset", "faction_offset", "health_offset", "forbidden_unproved_offset", "exclusion_policy", "read_order", "sickness_offset", "sickness_semantic"}
ABI_KEYS = {"record_world_resolver", "sickness_clearer", "health_setter", "people_cured", "funds_account"}
COMMON_ABI = {"va", "stock_bytes", "continuation_va", "calling_convention", "artifact_sha256"}
TRANSACTION_KEYS = {"folder_manifest_sha256", "dry_run_artifact_sha256", "confirmation_artifact_sha256", "postverify_artifact_sha256", "partial_rollback_artifact_sha256", "predicted_actual_counts_verified", "overlap_counts_both_verified", "deduction_after_postverify_verified", "partial_effect_boundary_verified", "rollback_disclosure_verified"}
MESSAGE_KEYS = {"label", "prompt", "sick_result", "partial_result", "singular_plural_verified"}
UI_KEYS = {"resource", "dimensions", "local", "event", "factory_va", "ownership_va", "windowed_receipt_sha256", "fullscreen_receipt_sha256", "owner_verified", "centering_verified", "fullscreen_restore_verified", "child_destructor_verified"}
COMPOSITION_KEYS = {"origins_range", "full_mastery_range", "running_range", "ui_ranges", "full_heal_ranges", "patches", "hooks", "caves", "overlap_report_sha256", "expanded_rejected", "expanded_lifecycle_verified"}


def _keys(value: object, expected: set[str], label: str) -> dict[str, object]:
    if type(value) is not dict or set(value) != expected:
        raise ValueError(f"{label} schema keys are not exact")
    return value


def _sha(value: object, label: str, *, optional: bool = True) -> str | None:
    if optional and value is None:
        return None
    if type(value) is not str or re.fullmatch(r"[0-9A-F]{64}", value) is None:
        raise ValueError(f"{label} must be uppercase SHA-256")
    return value


def _hex(value: object, label: str, *, va: bool = False) -> bool:
    if value is None:
        return False
    pattern = r"0x[0-9A-F]+" if va else r"(?:[0-9A-F]{2})+"
    if type(value) is not str or re.fullmatch(pattern, value) is None:
        raise ValueError(f"{label} is not exact uppercase hexadecimal evidence")
    return True


def _flag(value: object, label: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{label} must be exact bool")
    return value


def _common_abi(value: object, extra: set[str], label: str) -> tuple[dict[str, object], bool]:
    item = _keys(value, COMMON_ABI | extra, label)
    present = [
        _hex(item["va"], f"{label}.va", va=True),
        _hex(item["stock_bytes"], f"{label}.stock_bytes"),
        _hex(item["continuation_va"], f"{label}.continuation_va", va=True),
        type(item["calling_convention"]) is str and bool(item["calling_convention"]),
        _sha(item["artifact_sha256"], f"{label}.artifact_sha256") is not None,
    ]
    if item["calling_convention"] is not None and (type(item["calling_convention"]) is not str or not item["calling_convention"]):
        raise ValueError(f"{label}.calling_convention must be non-empty text or null")
    return item, all(present)


def validate_evidence(record: object) -> bool:
    item = _keys(record, TOP_KEYS, "evidence")
    expected_top = {
        "id": "vv5_full_heal_native_abi_evidence_gate", "game_id": "vv5",
        "enabled": False, "catalog_hidden": True, "catalog_enabled": False,
        "publication_ready": False, "native_output": False,
        "status": "STOP: native Full Heal ABIs and player lifecycle evidence are unproved",
    }
    for key, expected in expected_top.items():
        if type(item[key]) is not type(expected) or item[key] != expected:
            raise ValueError(f"evidence.{key} is not exact")
    if item["stock"] != {"filename": "Virtual Villagers - New Believers.exe", "size": 991232, "sha256": STOCK_SHA256}:
        raise ValueError("stock fingerprint is not exact")

    folder = _keys(item["folder_evidence"], FOLDER_KEYS, "folder_evidence")
    if folder["schema"] != "vvfp.full-folder-inventory.v1":
        raise ValueError("folder schema is not exact")
    for key in ("authenticated", "complete"):
        _flag(folder[key], f"folder_evidence.{key}")
    for key in ("file_count", "total_size"):
        if folder[key] is not None and (type(folder[key]) is not int or folder[key] <= 0):
            raise ValueError(f"folder_evidence.{key} must be positive exact int or null")
    if type(folder["unexpected_files"]) is not list or any(type(v) is not str or not v for v in folder["unexpected_files"]):
        raise ValueError("unexpected_files must be exact text entries")
    folder_hash = _sha(folder["manifest_sha256"], "folder manifest")
    folder_receipt = _sha(folder["receipt_sha256"], "folder receipt")
    folder_complete = bool(folder["authenticated"] and folder["complete"] and folder["file_count"] and folder["total_size"] and folder["unexpected_files"] == [] and folder_hash and folder_receipt)

    contract = _keys(item["record_contract"], RECORD_KEYS, "record_contract")
    exact_record = {"count": 150, "stride": "0x2F44", "active_offset": "0x1CD4", "faction_offset": "0x1CEC", "health_offset": "0x1C40", "forbidden_unproved_offset": "0x1CE1", "exclusion_policy": {"never_read": ["0x1CE1"], "never_write": ["0x1CE1"], "never_use_as_eligibility_guard": ["0x1CE1"], "status": "unproved and excluded"}, "read_order": ["active", "faction_equals_zero", "positive_health", "native_sickness"]}
    for key, expected in exact_record.items():
        if contract[key] != expected or type(contract[key]) is not type(expected):
            raise ValueError(f"record_contract.{key} is not exact")
    sickness_known = _hex(contract["sickness_offset"], "record_contract.sickness_offset", va=True)
    if contract["sickness_offset"] == "0x1CE1":
        raise ValueError("unproved +0x1CE1 cannot be used as the sickness field")
    if contract["sickness_semantic"] is not None and (type(contract["sickness_semantic"]) is not str or not contract["sickness_semantic"]):
        raise ValueError("sickness semantic must be non-empty text or null")
    sickness_known = sickness_known and type(contract["sickness_semantic"]) is str

    abis = _keys(item["native_abis"], ABI_KEYS, "native_abis")
    resolver, resolver_complete = _common_abi(abis["record_world_resolver"], {"stable_identity_verified"}, "record_world_resolver")
    resolver_complete = resolver_complete and _flag(resolver["stable_identity_verified"], "stable_identity_verified")
    clearer, clearer_complete = _common_abi(abis["sickness_clearer"], {"exact_clear_readback_verified"}, "sickness_clearer")
    clearer_complete = clearer_complete and _flag(clearer["exact_clear_readback_verified"], "exact_clear_readback_verified")
    health, health_complete = _common_abi(abis["health_setter"], {"target_health", "exact_readback_verified"}, "health_setter")
    if type(health["target_health"]) is not int or health["target_health"] != 100:
        raise ValueError("health target must be exact integer 100")
    health_complete = health_complete and _flag(health["exact_readback_verified"], "exact_readback_verified")

    people = _keys(abis["people_cured"], {"increment_va", "readback_va", "stock_bytes", "calling_convention", "artifact_sha256", "stat_verified", "trophy_behavior_verified", "notification_behavior_verified"}, "people_cured")
    people_fields = [_hex(people[k], f"people_cured.{k}", va=True) for k in ("increment_va", "readback_va")]
    people_fields.append(_hex(people["stock_bytes"], "people_cured.stock_bytes"))
    if people["calling_convention"] is not None and (type(people["calling_convention"]) is not str or not people["calling_convention"]):
        raise ValueError("people_cured.calling_convention must be text or null")
    people_fields.extend([type(people["calling_convention"]) is str, _sha(people["artifact_sha256"], "people_cured.artifact") is not None])
    people_flags = [_flag(people[k], f"people_cured.{k}") for k in ("stat_verified", "trophy_behavior_verified", "notification_behavior_verified")]
    people_complete = all(people_fields) and all(people_flags)

    funds = _keys(abis["funds_account"], {"getter_va", "deduction_va", "stock_bytes", "calling_convention", "artifact_sha256", "price", "one_deduction_readback_verified"}, "funds_account")
    if type(funds["price"]) is not int or funds["price"] != 30000:
        raise ValueError("price must be exact integer 30000")
    funds_fields = [_hex(funds[k], f"funds_account.{k}", va=True) for k in ("getter_va", "deduction_va")]
    funds_fields.append(_hex(funds["stock_bytes"], "funds_account.stock_bytes"))
    if funds["calling_convention"] is not None and (type(funds["calling_convention"]) is not str or not funds["calling_convention"]):
        raise ValueError("funds calling convention must be text or null")
    funds_complete = all(funds_fields) and type(funds["calling_convention"]) is str and _sha(funds["artifact_sha256"], "funds artifact") is not None and _flag(funds["one_deduction_readback_verified"], "one_deduction_readback_verified")

    tx = _keys(item["transaction_evidence"], TRANSACTION_KEYS, "transaction_evidence")
    tx_folder = _sha(tx["folder_manifest_sha256"], "transaction folder manifest")
    if tx_folder is not None and tx_folder != folder_hash:
        raise ValueError("transaction evidence is not bound to the complete folder")
    tx_hashes = [_sha(tx[k], f"transaction_evidence.{k}") for k in ("dry_run_artifact_sha256", "confirmation_artifact_sha256", "postverify_artifact_sha256", "partial_rollback_artifact_sha256")]
    tx_flags = [_flag(tx[k], f"transaction_evidence.{k}") for k in ("predicted_actual_counts_verified", "overlap_counts_both_verified", "deduction_after_postverify_verified", "partial_effect_boundary_verified", "rollback_disclosure_verified")]
    tx_complete = tx_folder is not None and all(tx_hashes) and all(tx_flags)

    messages = _keys(item["messages"], MESSAGE_KEYS, "messages")
    expected_messages = {"label": "Full Heal / Cure All", "prompt": "Full Heal / Cure All will cure X sick villagers and restore Y partial-health villagers to exactly 100 for 30,000 tech points?", "sick_result": "X sick villagers were cured", "partial_result": "Y partial-health villagers were restored to exactly 100"}
    if any(messages[k] != value for k, value in expected_messages.items()):
        raise ValueError("Full Heal wording is not exact")
    messages_complete = _flag(messages["singular_plural_verified"], "singular_plural_verified")

    ui = _keys(item["ui_lifecycle"], UI_KEYS, "ui_lifecycle")
    expected_ui = {"resource": "0x6A", "dimensions": [96, 39], "local": [137, 2], "event": 13, "factory_va": "0x401BD0", "ownership_va": "0x40C680"}
    if any(ui[k] != value or type(ui[k]) is not type(value) for k, value in expected_ui.items()):
        raise ValueError("Tech control resource/ownership contract is not exact")
    ui_receipts = [_sha(ui[k], f"ui_lifecycle.{k}") for k in ("windowed_receipt_sha256", "fullscreen_receipt_sha256")]
    ui_flags = [_flag(ui[k], f"ui_lifecycle.{k}") for k in ("owner_verified", "centering_verified", "fullscreen_restore_verified", "child_destructor_verified")]
    ui_complete = all(ui_receipts) and all(ui_flags)

    composition = _keys(item["composition"], COMPOSITION_KEYS, "composition")
    expected_composition = {"origins_range": "0xDB000-0xDC000", "full_mastery_range": "0xF2000-0xF4000", "running_range": "0xF4000-0xF6000", "ui_ranges": [], "full_heal_ranges": [], "patches": [], "hooks": [], "caves": [], "expanded_rejected": True}
    for key, expected in expected_composition.items():
        if composition[key] != expected or type(composition[key]) is not type(expected):
            raise ValueError(f"composition.{key} is not exact")
    overlap = _sha(composition["overlap_report_sha256"], "composition.overlap_report_sha256")
    expanded_lifecycle = _flag(composition["expanded_lifecycle_verified"], "expanded_lifecycle_verified")
    composition_complete = overlap is not None and expanded_lifecycle

    return bool(folder_complete and sickness_known and resolver_complete and clearer_complete and health_complete and people_complete and funds_complete and tx_complete and messages_complete and ui_complete and composition_complete)


def load_and_validate(path: Path = EVIDENCE_PATH) -> tuple[dict[str, object], bool]:
    if not SCHEMA_PATH.is_file():
        raise ValueError("Full Heal native ABI schema is missing")
    record = json.loads(path.read_text(encoding="utf-8"))
    return record, validate_evidence(record)


if __name__ == "__main__":
    _, complete = load_and_validate()
    print(json.dumps({"evidence_complete": complete, "publication_ready": False, "native_output": False}, sort_keys=True))
