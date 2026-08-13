"""Fail-closed additive evidence gate for the disabled VV5 UI routes.

This validator is deliberately separate from the UI and native-evidence
builders.  It checks their current disabled contracts and records the
identity/account/fullscreen requirements that must be proven before any
native route can be emitted.  It performs no native, runtime, package, or
save operation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
GATE_PATH = ROOT / "data" / "vv5_ui_native_stabilization_gate.json"
SCHEMA_PATH = ROOT / "data" / "vv5_ui_native_stabilization_gate.schema.json"
TECH_DETAIL_PATH = ROOT / "data" / "vv5_tech_detail_native_evidence.json"
FULL_HEAL_PATH = ROOT / "data" / "vv5_full_heal_native_abi_evidence.json"
FULL_MASTERY_MAP_PATH = ROOT / "data" / "candidates" / "vv5_full_mastery_all_candidate_map.json"
FULL_MASTERY_FEATURE_PATH = ROOT / "data" / "candidates" / "vv5_full_mastery_all_candidate.json"
STOCK_SHA256 = "92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D"
STOCK = {
    "filename": "Virtual Villagers - New Believers.exe",
    "size": 991232,
    "sha256": STOCK_SHA256,
}
ACTIONS = ["youth", "full_mastery", "running", "age_18"]
RESOURCE = {
    "asset": "Images\\btn_trophies.png",
    "resource_id": "0x6A",
    "dimensions": [96, 39],
    "local": [137, 2],
    "tech": {"event": 13, "factory_va": "0x401BD0", "ownership_va": "0x40C680"},
    "detail": {"event": 13, "factory_va": "0x401BD0", "ownership_va": "0x40C680"},
}
SEQUENCE = [
    "dry_run_snapshot",
    "idok_confirmation",
    "before_reacquire",
    "before_funds_reacquire",
    "first_write_identity_check",
    "like_write_postverify",
    "dislike_write_identity_check",
    "final_postverify",
    "deduction",
    "deduction_readback",
    "rollback_or_disclosure",
]
IDENTITY_FIELDS = ["selected_index", "world_identity", "record_pointer", "account_identity"]
IDENTITY_STAGES = [
    "plan", "reacquire", "first_write", "like_postverify", "dislike_write",
    "final_postverify", "deduction", "rollback_restore",
]
FAIL_CLOSED_STAGES = [
    "first_write", "like_postverify", "full_postverify", "pre_deduction",
    "charge_readback", "rollback_restore",
]


def _keys(value: object, expected: set[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != expected:
        raise ValueError(f"{label} schema keys are not exact")
    return value


def _strict(actual: object, expected: object, label: str) -> None:
    """Compare with exact Python types so bool cannot satisfy an int field."""

    if type(actual) is not type(expected):
        raise ValueError(f"{label} has the wrong exact type")
    if isinstance(expected, dict):
        if set(actual) != set(expected):
            raise ValueError(f"{label} schema keys are not exact")
        for key, expected_value in expected.items():
            _strict(actual[key], expected_value, f"{label}.{key}")
    elif isinstance(expected, list):
        if len(actual) != len(expected):
            raise ValueError(f"{label} length is not exact")
        for index, (actual_value, expected_value) in enumerate(zip(actual, expected)):
            _strict(actual_value, expected_value, f"{label}[{index}]")
    elif actual != expected:
        raise ValueError(f"{label} is not exact")


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"missing evidence file: {path.as_posix()}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise ValueError(f"{path.as_posix()} must contain an exact object")
    return value


def validate_world_identity(value: object) -> int:
    """Validate the additive callback contract's positive world identity."""

    if type(value) is not int or value <= 0:
        raise ValueError("world_identity must be an exact positive non-bool int")
    return value


def validate_selection_callback_result(value: object) -> tuple[object, object, int, str]:
    """Validate `(world, record, selected_index, resolved_pointer)` only."""

    if type(value) is not tuple or len(value) != 4:
        raise ValueError("selection callback must return exactly four tuple values")
    validate_world_identity(value[0])
    if type(value[2]) is not int:
        raise ValueError("selected_index must be an exact int")
    if type(value[3]) is not str or not value[3]:
        raise ValueError("resolved_pointer must be a non-empty exact string")
    return value


def validate_account_balance_callback_result(value: object) -> tuple[int, object, int]:
    """Validate `(world, account, balance)` without reading or changing state."""

    if type(value) is not tuple or len(value) != 3:
        raise ValueError("account/balance callback must return exactly three tuple values")
    validate_world_identity(value[0])
    if type(value[2]) is not int:
        raise ValueError("balance must be an exact int")
    return value


def validate_deduction_callback_arguments(value: object) -> tuple[int, object, int]:
    """Validate `(world, account, amount)` for a future deduction adapter."""

    if type(value) is not tuple or len(value) != 3:
        raise ValueError("deduction callback must receive exactly three values")
    validate_world_identity(value[0])
    if type(value[2]) is not int:
        raise ValueError("deduction amount must be an exact int")
    return value


def _validate_resource_caption(gate: dict[str, Any]) -> None:
    resource = _keys(
        gate["resource_caption"],
        {"asset", "resource_id", "dimensions", "local", "tech", "detail", "caption_text", "caption_verified", "caption_status"},
        "resource_caption",
    )
    _strict({key: resource[key] for key in RESOURCE}, RESOURCE, "resource_caption.binding")
    _strict(resource["caption_text"], None, "resource_caption.caption_text")
    _strict(resource["caption_verified"], False, "resource_caption.caption_verified")
    _strict(resource["caption_status"], "pending authenticated caption evidence", "resource_caption.caption_status")

    for path in (FULL_MASTERY_MAP_PATH, FULL_MASTERY_FEATURE_PATH):
        source = _load(path)
        geometry = source.get("ui_geometry_contract")
        if type(geometry) is not dict:
            raise ValueError(f"{path.name} has no UI geometry contract")
        if geometry.get("asset") not in {"Images\\btn_trophies.png", "native cached Images\\btn_trophies.png"}:
            raise ValueError(f"{path.name} asset binding is not exact")
        if geometry.get("resource_id") != RESOURCE["resource_id"]:
            raise ValueError(f"{path.name} resource binding is not exact")
        if geometry.get("native_dimensions") != RESOURCE["dimensions"]:
            raise ValueError(f"{path.name} dimensions are not exact")
        for route_name in ("tech", "detail"):
            route = geometry.get(route_name)
            if type(route) is not dict:
                raise ValueError(f"{path.name} missing {route_name} geometry")
            _strict(
                {key: route.get(key) for key in ("local_x", "local_y", "event", "factory", "ownership")},
                {"local_x": 137, "local_y": 2, "event": 13, "factory": "0x401BD0", "ownership": "0x40C680"},
                f"{path.name}.{route_name}",
            )


def _validate_detail(gate: dict[str, Any]) -> None:
    detail = _keys(
        gate["detail_evidence"],
        {
            "input_method_entry_va", "input_method_entry_bytes", "input_method_semantics", "input_event13_route",
            "event_method_range", "event_method_size", "event_method_sha256", "event_method_entry_bytes",
            "event_method_cleanup", "event_vtable_slot_va", "dispatcher_range", "dispatcher_size",
            "dispatcher_sha256", "dispatcher_call_range", "ownership", "offline_detour",
            "stock_xref_to_7B22C0", "stock_xref_to_7B2600", "status",
        },
        "detail_evidence",
    )
    _strict(
        {key: detail[key] for key in (
            "input_method_entry_va", "input_method_entry_bytes", "input_method_semantics", "input_event13_route",
            "event_method_range", "event_method_size", "event_method_sha256", "event_method_entry_bytes",
            "event_method_cleanup", "event_vtable_slot_va", "dispatcher_range", "dispatcher_size",
            "dispatcher_sha256", "dispatcher_call_range", "stock_xref_to_7B22C0", "stock_xref_to_7B2600", "status",
        )},
        {
            "input_method_entry_va": "0x44B560",
            "input_method_entry_bytes": "83EC44535556BD7F03000057BF580300",
            "input_method_semantics": "Detail input/hit-test method entry; not an event-13 route",
            "input_event13_route": False,
            "event_method_range": "[0x44BC20,0x44BD4C)",
            "event_method_size": 300,
            "event_method_sha256": "DE25D2B76DC7E6337F40F06CBF25FCDCEC411BD9D7F1E7DC78406C157501DC74",
            "event_method_entry_bytes": "83EC18A1A8974D00",
            "event_method_cleanup": "ret 8",
            "event_vtable_slot_va": "0x49A5A0",
            "dispatcher_range": "[0x4019B8,0x4019CF)",
            "dispatcher_size": 23,
            "dispatcher_sha256": "F2EB107944977E8CBCE7CAD450EC6D1D046880727EBDE36A939CF5DC5DDC907F",
            "dispatcher_call_range": "[0x4019CD,0x4019CF)",
            "stock_xref_to_7B22C0": False,
            "stock_xref_to_7B2600": False,
            "status": "mechanical offline evidence only; runtime and player receipt STOP",
        },
        "detail_evidence.static",
    )
    _strict(detail["ownership"], {
        "factory_va": "0x401BD0", "registration_va": "0x40C680", "inner_id_offset": "+0x4",
        "inner_parent_offset": "+0x20", "dispatcher_vtable_offset": "+0x0C", "constructor_control_id": 13,
        "teardown_chain": ["0x44B9F0", "0x44AF30", "0x40C7F0", "0x40C830"],
    }, "detail_evidence.ownership")
    _strict(detail["offline_detour"], {
        "raw_offset": "0x4BC20", "preimage": "83EC18A1A8974D00", "detour": "E99B643600909090",
        "target_va": "0x7B20C0", "continuation_va": "0x44BC28", "guard": {"message": 8, "control_id": 13},
        "fallback_replay": "83EC18A1A8974D00", "install_verified": True, "uninstall_verified": True,
        "hot_uninstall_verified": False,
    }, "detail_evidence.offline_detour")

    native_record = _load(TECH_DETAIL_PATH)
    if native_record.get("native_contract", {}).get("detail_input_method_entry_va") != "0x44B560":
        raise ValueError("current Tech/Detail evidence lost the 0x44B560 method-entry binding")
    if native_record.get("native_proof", {}).get("method_entry_rejected_as_callsite") is not True:
        raise ValueError("current Tech/Detail evidence must reject 0x44B560 event routing")
    if native_record.get("native_proof", {}).get("event_method_offline_detour_verified") is not True:
        raise ValueError("current Tech/Detail evidence lost D339 offline event proof")


def _validate_c260(gate: dict[str, Any]) -> None:
    _strict(gate["c260_rejection"], {
        "bad_pointer_va": "0x7B2A64", "authenticated_string_va": "0x7B2A63",
        "requested_symbol": "DL_GetWindowFlags", "repair_status": "rejected; static-only evidence",
        "repair_output": [], "menu_reached": False, "runtime_verified": False,
    }, "c260_rejection")


def _validate_transactions(gate: dict[str, Any]) -> None:
    tx = _keys(
        gate["transaction_contract"],
        {
            "sequence", "confirmation_results", "identity_fields", "exact_identity_required_at",
            "full_record_snapshot_required", "before_reacquire_required", "before_funds_reacquire_required",
            "world_identity_rule", "selection_callback", "account_balance_callback", "deduction_callback",
            "callback_exception_policy", "fail_closed_stages", "funds_snapshot_exact_required", "one_deduction_only", "deduction_after_final_postverify",
            "charge_truth", "unknown_charge_text", "rollback_policy", "reference_model", "running_existing_like_cleanup",
        },
        "transaction_contract",
    )
    _strict(tx["sequence"], SEQUENCE, "transaction_contract.sequence")
    _strict(tx["confirmation_results"], {"idok": 1, "cancel": [0, 2]}, "transaction_contract.confirmation_results")
    _strict(tx["identity_fields"], IDENTITY_FIELDS, "transaction_contract.identity_fields")
    _strict(tx["exact_identity_required_at"], IDENTITY_STAGES, "transaction_contract.exact_identity_required_at")
    _strict(tx["world_identity_rule"], "exact non-bool positive world_identity; bool, zero, negative, and float values reject", "transaction_contract.world_identity_rule")
    _strict(tx["selection_callback"], {"returns": ["world_identity", "record", "selected_index", "resolved_pointer"], "shape": "(world, record, selected_index, resolved_pointer)"}, "transaction_contract.selection_callback")
    _strict(tx["account_balance_callback"], {"returns": ["world_identity", "account_identity", "balance"], "shape": "(world, account, balance)"}, "transaction_contract.account_balance_callback")
    _strict(tx["deduction_callback"], {"arguments": ["world_identity", "account_identity", "amount"], "shape": "(world, account, amount)"}, "transaction_contract.deduction_callback")
    _strict(tx["callback_exception_policy"], "callback exception or world/selection/account mismatch fails closed before first write and at every later guarded stage", "transaction_contract.callback_exception_policy")
    _strict(tx["fail_closed_stages"], FAIL_CLOSED_STAGES, "transaction_contract.fail_closed_stages")
    for field in ("full_record_snapshot_required", "before_reacquire_required", "before_funds_reacquire_required", "funds_snapshot_exact_required", "one_deduction_only", "deduction_after_final_postverify"):
        if type(tx[field]) is not bool or tx[field] is not True:
            raise ValueError(f"transaction_contract.{field} must be exact true")
    _strict(tx["charge_truth"], "truthful only from exact balance-before/after readback; otherwise unknown", "transaction_contract.charge_truth")
    _strict(tx["unknown_charge_text"], "The tech-point charge outcome is unknown; no no-charge claim is permitted without exact balance readback.", "transaction_contract.unknown_charge_text")
    _strict(tx["rollback_policy"], {
        "native_rollback_verified": False, "partial_effect_disclosure_required": True,
        "no_charge_claim_requires_exact_balance_readback": True,
        "status": "reference-only; native writes, readback, and rollback are not implemented",
    }, "transaction_contract.rollback_policy")
    _strict(tx["reference_model"], {
        "path": "src/vv5_individual_transactions.py", "selected_index_and_record_pointer_reacquire": True,
        "full_snapshot_reacquire": True, "account_identity_token": None, "later_stage_identity_verified": False,
        "native_write": False, "native_readback": False, "native_rollback": False,
        "status": "reference arithmetic only; no native effect is claimed",
    }, "transaction_contract.reference_model")
    _strict(tx["running_existing_like_cleanup"], {
        "current_reference_model": "changed_and_charged", "binding_required_before_native_charge": True,
        "native_charge_allowed": False,
        "status": "pending explicit Running binding for Like/Dislike cleanup semantics",
    }, "transaction_contract.running_existing_like_cleanup")

    from build_vv5_ui_confirmation_candidate import build_manifest
    from vv5_individual_transactions import transaction_contracts

    manifest = build_manifest()
    if manifest["enabled"] is not False or manifest["catalog_enabled"] is not False or manifest["native_routing"]["emitted_hooks"] != []:
        raise ValueError("current UI candidate is not disabled/no-output")
    if set(manifest["individual_actions"]) != set(ACTIONS):
        raise ValueError("current UI candidate does not preserve exactly four actions")
    contracts = transaction_contracts()
    if set(contracts) != set(ACTIONS):
        raise ValueError("reference model action set is not exact")
    for action in ACTIONS:
        contract = contracts[action]
        if contract["confirmation_results"] != {"idok": 1, "cancel": [0, 2]}:
            raise ValueError(f"{action} confirmation results are not exact")
        if contract["required_callbacks"] != ["before_reacquire", "before_funds_reacquire"]:
            raise ValueError(f"{action} mandatory callback order is not exact")
        if "native write" not in contract["native_effects"] or "native readback" not in contract["native_effects"] or "rollback" not in contract["native_effects"]:
            raise ValueError(f"{action} native-effect disclosure is incomplete")


def _validate_fullscreen(gate: dict[str, Any]) -> None:
    _strict(gate["fullscreen_owner"], {
        "owner_abi": {
            "begin": "zero-arg stdcall BeginOriginsOwner",
            "get": "zero-arg stdcall GetOriginsOwner",
            "end": "zero-arg stdcall EndOriginsOwner",
        },
        "capture_before_leave": True,
        "same_process_revalidation": True,
        "no_foreground_fallback": True,
        "single_terminal_cleanup": True,
        "cleanup_scope": "one centralized wrapper epilogue after every post-Begin route",
        "owner_output": [],
        "player_receipts": {"tech_windowed": None, "tech_fullscreen": None, "detail_windowed": None, "detail_fullscreen": None},
        "status": "pending authenticated owner and player evidence",
    }, "fullscreen_owner")


def _validate_full_heal(gate: dict[str, Any]) -> None:
    _strict(gate["full_heal"], {
        "path": "data/vv5_full_heal_native_abi_evidence.json", "enabled": False, "catalog_hidden": True,
        "catalog_enabled": False, "publication_ready": False, "native_output": False,
        "hooks": [], "caves": [], "patches": [], "ranges": [], "native_abi_evidence_complete": False,
    }, "full_heal")
    evidence = _load(FULL_HEAL_PATH)
    for field, expected in (("enabled", False), ("catalog_hidden", True), ("catalog_enabled", False), ("publication_ready", False), ("native_output", False)):
        if type(evidence.get(field)) is not bool or evidence[field] is not expected:
            raise ValueError(f"Full Heal evidence {field} is not fail-closed")
    composition = evidence.get("composition")
    if type(composition) is not dict or any(composition.get(field) != [] for field in ("ui_ranges", "full_heal_ranges", "hooks", "caves", "patches")):
        raise ValueError("Full Heal evidence claims native output")


def validate_gate(record: object) -> bool:
    gate = _keys(record, {
        "id", "game_id", "enabled", "catalog_hidden", "catalog_enabled", "publication_ready", "native_output", "status",
        "actions", "stock", "resource_caption", "detail_evidence", "c260_rejection", "transaction_contract",
        "fullscreen_owner", "full_heal", "composition",
    }, "stabilization gate")
    _strict({key: gate[key] for key in ("id", "game_id", "enabled", "catalog_hidden", "catalog_enabled", "publication_ready", "native_output", "status", "actions", "stock")}, {
        "id": "vv5_ui_native_stabilization_gate", "game_id": "vv5", "enabled": False, "catalog_hidden": True,
        "catalog_enabled": False, "publication_ready": False, "native_output": False,
        "status": "disabled; additive evidence gate only", "actions": ACTIONS, "stock": STOCK,
    }, "stabilization gate.identity")
    composition = _keys(gate["composition"], {"stock_sha256", "full_mastery_range", "running_range", "ui_ranges", "full_heal_ranges", "hooks", "caves", "patches", "expanded_rejected"}, "composition")
    _strict(composition, {
        "stock_sha256": STOCK_SHA256, "full_mastery_range": "0xF2000-0xF4000", "running_range": "0xF4000-0xF6000",
        "ui_ranges": [], "full_heal_ranges": [], "hooks": [], "caves": [], "patches": [], "expanded_rejected": True,
    }, "composition")
    _validate_resource_caption(gate)
    _validate_detail(gate)
    _validate_c260(gate)
    _validate_transactions(gate)
    _validate_fullscreen(gate)
    _validate_full_heal(gate)

    from validate_vv5_tech_detail_native_evidence import load_and_validate

    _, evidence_complete = load_and_validate()
    if evidence_complete:
        raise ValueError("Tech/Detail evidence is unexpectedly complete; independent enablement review is required")
    return True


def load_and_validate(path: Path = GATE_PATH) -> tuple[dict[str, Any], bool]:
    if not SCHEMA_PATH.is_file():
        raise ValueError("stabilization gate schema is missing")
    record = _load(path)
    return record, validate_gate(record)


if __name__ == "__main__":
    _, valid = load_and_validate()
    print(json.dumps({"valid": valid, "enabled": False, "native_output": False, "publication_ready": False}, sort_keys=True))
