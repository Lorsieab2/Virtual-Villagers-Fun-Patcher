"""Publication-false evidence gate for reusable VV3-VV5 action primitives."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping

SCHEMA = "vvfp.transaction_primitives_native_evidence"
VERSION = 1
GAMES = ("vv3", "vv4", "vv5")
PRIMITIVES = (
    "selected_record_identity", "eligibility_order", "funds_transaction",
    "age_mutation", "preference_mutation", "confirmation_result_abi",
    "postverify_partial_effect_boundary",
)
ACTION_FAMILIES = (
    "permanent_tech", "youth", "full_mastery", "running", "age_18", "full_heal",
)
PROOF_FIELDS = (
    "function_va", "file_offset", "guard_bytes", "call_convention", "registers",
    "stack_cleanup", "xrefs", "full_folder_provenance", "runtime_receipts",
)
STOCK = {
    "vv3": {"exe_name": "Virtual Villagers - The Secret City.exe", "exe_size": 831488, "exe_sha256": "8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503"},
    "vv4": {"exe_name": "Virtual Villagers - The Tree of Life.exe", "exe_size": 929792, "exe_sha256": "6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220"},
    "vv5": {"exe_name": "Virtual Villagers - New Believers.exe", "exe_size": 991232, "exe_sha256": "92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D"},
}

@dataclass(frozen=True)
class Result:
    schema_valid: bool
    evidence_complete: bool
    publication_allowed: bool
    errors: tuple[str, ...]

def _mapping(value: Any) -> bool:
    return isinstance(value, Mapping)

def validate_contract(data: Mapping[str, Any]) -> Result:
    errors: list[str] = []
    if data.get("schema") != SCHEMA or data.get("version") != VERSION:
        errors.append("schema/version mismatch")
    flags = data.get("flags")
    expected_flags = {"enabled": False, "publication": False, "native_emission": False, "runtime_verified": False, "player_verified": False}
    if flags != expected_flags:
        errors.append("all enablement/publication/native/runtime/player flags must be false")
    if data.get("action_families") != list(ACTION_FAMILIES):
        errors.append("exact C337 action-family binding required")
    games = data.get("games")
    if not _mapping(games) or set(games) != set(GAMES):
        errors.append("exact vv3/vv4/vv5 set required")
        games = {}
    for game in GAMES:
        record = games.get(game, {}) if _mapping(games) else {}
        if record.get("stock") != STOCK[game]:
            errors.append(f"{game}: exact stock fingerprint required")
        if record.get("full_folder_sha256") is not None or record.get("full_folder_file_count") is not None or record.get("full_folder_verified") is not False:
            errors.append(f"{game}: full-folder provenance must remain null/pending")
        if record.get("status") != "STOP" or record.get("runtime_receipts") != []:
            errors.append(f"{game}: status/receipts must remain STOP/empty")
        primitives = record.get("primitives")
        if not _mapping(primitives) or list(primitives) != list(PRIMITIVES):
            errors.append(f"{game}: exact ordered primitive set required")
            primitives = {}
        for primitive in PRIMITIVES:
            row = primitives.get(primitive, {}) if _mapping(primitives) else {}
            if row.get("status") != "STOP" or row.get("proof") != {field: None if field != "runtime_receipts" else [] for field in PROOF_FIELDS}:
                errors.append(f"{game}/{primitive}: proof row must remain null/STOP")
            if row.get("direct_store_qualifies") is not False or row.get("adjacent_skill_writer_qualifies") is not False:
                errors.append(f"{game}/{primitive}: direct stores and adjacent skill writers are forbidden")
        order = record.get("eligibility_required_order")
        expected = ["faction:+0x1CEC", "active", "living", "status"] if game == "vv5" else ["active", "living", "status"]
        if order != expected:
            errors.append(f"{game}: eligibility order mismatch")
        serialized = json.dumps(record, sort_keys=True)
        if "+0x1CE1" in serialized or "0x1CE1" in serialized:
            errors.append(f"{game}: unproved +0x1CE1 is forbidden")
        requirements = record.get("semantic_requirements")
        required_keys = {
            "stable_selected_index_manager_record_identity", "native_account_getter_deduction_setter_readback_notification",
            "native_age_setter_companion_timer_catchup_oldest", "native_like_dislike_setter_readback_queue_notification",
            "native_confirmation_exact_result_abi", "postverify_and_partial_effect_boundary",
        }
        if not _mapping(requirements) or set(requirements) != required_keys or any(value is not False for value in requirements.values()):
            errors.append(f"{game}: exact false semantic requirements required")
    valid = not errors
    return Result(valid, False, False, tuple(errors))

def validate_contract_file(path: Path) -> Result:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return Result(False, False, False, (f"contract unreadable: {exc}",))
    if not _mapping(data):
        return Result(False, False, False, ("contract root must be an object",))
    return validate_contract(data)
