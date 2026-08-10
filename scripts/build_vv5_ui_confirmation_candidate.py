"""Build the disabled VV5 UI/individual-transaction candidate evidence."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from vv5_individual_transactions import transaction_contracts
from validate_vv5_tech_detail_native_evidence import load_and_validate as load_native_evidence


ROOT = Path(__file__).resolve().parents[1]
ACTIVE_BASE = ROOT / "data" / "vv5_origins_feature.json"
OUTPUT = ROOT / "outputs" / "vv5-ui-confirmation-candidate"
OUTPUT_MANIFEST = OUTPUT / "candidate.json"
STOCK_SHA256 = "92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D"
STOCK_FILENAME = "Virtual Villagers - New Believers.exe"
STOCK_SIZE = 991232
STOCK_SOURCE_RELATIVE = "research/stock-executables/Virtual Villagers - New Believers.exe"
ACTIVE_BASE_SHA256 = "F9643E2B7D115B6ECDDD4D8AD4BFFC73F2FF6937995E40E991041B6AF6463D44"
ACTIVE_PAYLOAD_SHA256 = "831EB4C8C7190B1683B005492A0D8C67492F2CFF265D3D35E16A86006452D4A5"
FULL_MASTERY_MAP_SHA256 = "8FF2564204C8AF58B996645606A4D1012740B401382619ED777A1F0E3820E62F"
FULL_MASTERY_FEATURE_SHA256 = "F7AA12A5D11C5AC735EB4E7A356C4A8E180A0332ED678FABDAA6EED4F9DAFF8D"
RUNNING_MAP_SHA256 = "7D8A30C80CF14EB84DAC62AC324ED476F60E92B543A0B9DA3870F5184339F358"
FULL_MASTERY_PARENT_HASHES = {
    "collection_progression": "857E22D7C361B802508BF789C3CC486E42E76021F5AA579BB1D16CC6E0D017A0",
    "immediate_fixed": "E93822F752F730ECB751EBAA87021194C992984721B4370FF0015D5FC4BB2E9A",
}
PAYLOAD_OFFSET = 0xDB000
PAYLOAD_SIZE = 0x1000
TECH_EVENT = 13
DETAIL_EVENT = 13
DETAIL_INPUT_METHOD_VA = 0x44B560
DETAIL_INPUT_METHOD_ENTRY_BYTES = "83EC44535556BD7F03000057BF580300"
CURRENT_DETAIL_HOOK_VA = 0x44BC20
CURRENT_DETAIL_HOOK_RAW_OFFSET = 0x4BC20
CURRENT_DETAIL_HOOK_PREIMAGE = "83EC18A1A8974D00"
CURRENT_DETAIL_CONTINUATION_VA = 0x44BC28
CURRENT_DETAIL_HOOK_DETOUR = "E99B643600909090"
CURRENT_DETAIL_HOOK_TARGET_VA = 0x7B20C0
FULL_MASTERY_MAP_PATH = ROOT / "data" / "candidates" / "vv5_full_mastery_all_candidate_map.json"
RUNNING_MAP_PATH = ROOT / "data" / "candidates" / "vv5_individual_running_candidate_map.json"
FULL_MASTERY_FEATURE_PATH = ROOT / "data" / "candidates" / "vv5_full_mastery_all_candidate.json"
RUNTIME_STATUS = "pending; no package or player validation"
DETAIL_STATUS = "mechanical offline evidence only; runtime and player receipt STOP"
STOCK_STATUS = "exact stock executable is not repository-owned in this checkout"
EXPECTED_CALL_CONVENTION = [
    "preserve ECX=EDI before native 0x44FA20 thiscall",
    "preserve native 0x401BD0 factory and 0x40C680 ownership registration",
    "preserve ret 8 and original handler fallback prologues",
]

MANIFEST_KEYS = {
    "id", "game_id", "name", "enabled", "catalog_hidden", "catalog_enabled",
    "runtime_status", "allowed_modes", "unsupported_patch_modes", "expanded_fail_closed",
    "dependencies", "source", "stock_fingerprint", "native_routing",
    "native_transaction_bindings", "native_evidence_gate", "composition_guard", "individual_actions", "implementation",
}
NATIVE_EVIDENCE_GATE_KEYS = {"path", "status", "evidence_complete", "publication_ready", "native_output"}
SOURCE_KEYS = {"stock_sha256", "active_base", "active_payload_sha256", "bound_payload_sha256"}
STOCK_FINGERPRINT_KEYS = {"filename", "size", "sha256", "source", "source_present", "source_bound", "status"}
NATIVE_ROUTING_KEYS = {"message", "tech", "detail", "patches", "emitted_hooks", "call_convention"}
ROUTE_KEYS = {"resource", "dimensions", "local", "event", "factory", "ownership", "status"}
DETAIL_ROUTE_KEYS = ROUTE_KEYS | {
    "stock_input_method_entry", "stock_input_method_entry_bytes", "stock_input_stack_locals",
    "stock_input_cleanup", "stock_vtable", "stock_destructor", "stock_draw",
    "stock_event_method", "stock_event_cleanup", "stock_xref_to_7B22C0",
    "stock_xref_to_7B2600", "candidate_route", "candidate_callsite",
    "candidate_callsite_raw", "candidate_hook_preimage", "candidate_hook_detour",
    "candidate_continuation", "candidate_guard", "candidate_fallback_replay",
    "offline_install_verified", "offline_uninstall_verified", "hot_uninstall_verified",
    "event_dispatcher", "event_vtable_slot", "control_inner_offsets",
    "constructor_registration", "teardown_chain",
    "current_emitted_hook", "proposed_hook", "evidence",
    "candidate_caves", "candidate_hooks",
}
DETAIL_EVIDENCE_KEYS = {
    "stock_sha256", "preimage_va", "preimage", "continuation_va", "continuation_bytes",
    "hook_length", "instruction_boundary_verified", "abi_verified", "ownership_verified",
    "child_destructor_verified", "native_target_va", "va_raw_relationship_verified",
}
NATIVE_BINDING_KEYS = {"stock_sha256", "selected_index", "record_offsets", "writers", "status"}
SELECTED_INDEX_KEYS = {"manager_getter_va", "selected_index_offset", "index_validator_va", "record_resolver_va", "record_base_va", "abi"}
RECORD_OFFSET_KEYS = {"active", "health", "heathen_active", "faction", "age", "age_companion", "age_timer", "skills", "likes", "dislikes"}
WRITER_KEYS = {"skill", "tech_charge"}
SKILL_WRITER_KEYS = {"va", "abi"}
CHARGE_WRITER_KEYS = {"funds_va", "va", "abi"}
COMPOSITION_KEYS = {"stock_sha256", "base_parent", "full_mastery", "running", "full_heal", "ranges"}
BASE_PARENT_KEYS = {"feature", "manifest", "manifest_sha256"}
FULL_MASTERY_KEYS = {"feature", "map", "map_sha256", "parent_hashes", "owned_range"}
RUNNING_KEYS = {"feature", "map", "map_sha256", "parent_hash", "owned_range"}
FULL_HEAL_KEYS = {"feature", "status", "ranges"}
RANGE_KEYS = {"name", "start", "end", "owner", "address_space", "alignment"}
CANDIDATE_RANGE_KEYS = RANGE_KEYS | {"va", "raw_offset", "length", "preimage"}
IMPLEMENTATION_KEYS = {"transaction_engine", "native_writer_policy", "save_policy"}
CONTRACT_COMMON_KEYS = {
    "sequence", "confirmation_results", "record_reacquire", "pre_confirmation_snapshot", "funds_reacquire",
    "required_callbacks", "before_reacquire", "before_funds_reacquire", "charge_verification",
    "native_effects", "no_charge_suffix", "no_charge_results", "price", "dry_run", "postverify",
}
CONTRACT_ACTION_KEYS = {
    "youth": CONTRACT_COMMON_KEYS,
    "full_mastery": CONTRACT_COMMON_KEYS,
    "running": CONTRACT_COMMON_KEYS | {"existing_running_cleanup"},
    "age_18": CONTRACT_COMMON_KEYS,
}

NATIVE_TRANSACTION_BINDINGS = {
    "stock_sha256": STOCK_SHA256,
    "selected_index": {
        "manager_getter_va": "0x425950",
        "selected_index_offset": "0x17E24",
        "index_validator_va": "0x471840",
        "record_resolver_va": "0x46F950",
        "record_base_va": "0x554190",
        "abi": "sub_425950() -> manager +0x17E24 -> sub_471840(index) -> sub_46F950(index) record pointer",
    },
    "record_offsets": {
        "active": "0x1CD4",
        "health": "0x1C40",
        "heathen_active": "0x1CE1",
        "faction": "0x1CEC",
        "age": "0x1B8C",
        "age_companion": "0x1C3C",
        "age_timer": "0x1C4C",
        "skills": ["0x1C5C", "0x1C60", "0x1C64", "0x1C68", "0x1C6C", "0x1C70"],
        "likes": ["0x1F5C", "0x1F60", "0x1F64"],
        "dislikes": ["0x1F68", "0x1F6C", "0x1F70"],
    },
    "writers": {
        "skill": {
            "va": "0x475730",
            "abi": "ECX=record+0x1C5C; push Float32 delta; push skill index; call native writer",
        },
        "tech_charge": {
            "funds_va": "0x51D5F8",
            "va": "0x4237B0",
            "abi": "ECX=0x51D5F8; push signed negative price; call exactly once",
        },
    },
    "status": "static binding only; no native output, write, readback, or rollback is emitted",
}

STOCK_FINGERPRINT = {
    "filename": STOCK_FILENAME,
    "size": STOCK_SIZE,
    "sha256": STOCK_SHA256,
    "source": STOCK_SOURCE_RELATIVE,
    "source_present": False,
    "source_bound": False,
    "status": STOCK_STATUS,
}

KNOWN_OCCUPIED_RANGES = (
    {"name": "origins_shr_payload", "start": 0xDB000, "end": 0xDC000, "owner": "vv5_enable_origins_exclusive_features", "address_space": "raw"},
    {"name": "full_mastery_append_page", "start": 0xF2000, "end": 0xF4000, "owner": "vv5_full_mastery_all_stage_a_candidate", "address_space": "raw"},
    {"name": "running_append_page", "start": 0xF4000, "end": 0xF6000, "owner": "vv5_individual_grant_running_candidate", "address_space": "raw"},
    {"name": "tech_constructor_hook", "start": 0x40A24, "end": 0x40A2A, "owner": "vv5_enable_origins_exclusive_features", "address_space": "raw"},
    {"name": "tech_event_hook", "start": 0x415F0, "end": 0x415F8, "owner": "vv5_enable_origins_exclusive_features", "address_space": "raw"},
    {"name": "detail_constructor_hook", "start": 0x4AF12, "end": 0x4AF18, "owner": "vv5_enable_origins_exclusive_features", "address_space": "raw"},
    {"name": "current_detail_hook", "start": 0x4BC20, "end": 0x4BC28, "owner": "vv5_enable_origins_exclusive_features", "address_space": "raw"},
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _known_keys(value: object, expected: set[str], label: str) -> dict[str, object]:
    if type(value) is not dict:
        raise ValueError(f"{label} must be an exact object")
    actual = set(value)
    missing = expected - actual
    unknown = actual - expected
    if missing or unknown:
        raise ValueError(
            f"{label} schema mismatch; missing={sorted(missing)!r}, unknown={sorted(unknown)!r}"
        )
    return value


def _allowed_keys(value: object, allowed: set[str], label: str) -> dict[str, object]:
    if type(value) is not dict:
        raise ValueError(f"{label} must be an exact object")
    unknown = set(value) - allowed
    if unknown:
        raise ValueError(f"{label} schema mismatch; unknown={sorted(unknown)!r}")
    return value


def _strict_structure(actual: object, expected: object, label: str) -> None:
    """Compare a static contract without Python bool/int coercion."""

    if type(actual) is not type(expected):
        raise ValueError(f"{label} has the wrong exact type")
    if isinstance(expected, dict):
        if set(actual) != set(expected):
            raise ValueError(f"{label} schema keys are not exact")
        for key in expected:
            _strict_structure(actual[key], expected[key], f"{label}.{key}")
        return
    if isinstance(expected, (list, tuple)):
        if len(actual) != len(expected):
            raise ValueError(f"{label} length is not exact")
        for index, (actual_item, expected_item) in enumerate(zip(actual, expected)):
            _strict_structure(actual_item, expected_item, f"{label}[{index}]")
        return
    if actual != expected:
        raise ValueError(f"{label} is not exact")


def _exact_bool(value: object, label: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{label} must be an exact bool")
    return value


def _exact_int(value: object, label: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{label} must be an exact int")
    return value


def _exact_str(value: object, label: str, *, non_empty: bool = True) -> str:
    if type(value) is not str or (non_empty and not value):
        raise ValueError(f"{label} must be an exact non-empty string")
    return value


def active_payload() -> bytes:
    manifest = json.loads(ACTIVE_BASE.read_text(encoding="utf-8"))
    patch = next(item for item in manifest["patches"] if item["offset"] == "0xDB000")
    payload = bytes.fromhex(patch["after"]).ljust(PAYLOAD_SIZE, b"\0")
    if len(payload) != PAYLOAD_SIZE:
        raise RuntimeError(f"VV5 active Origins payload must be {PAYLOAD_SIZE:#x} bytes")
    return payload


def bound_payload() -> tuple[bytes, list[dict[str, str]]]:
    """Bind the exact native route without emitting an unguarded hook."""

    payload = active_payload()
    if payload[0x0B] != TECH_EVENT or payload[0xCB] != DETAIL_EVENT or payload[0x128] != DETAIL_EVENT:
        raise RuntimeError("VV5 UI event bytes do not match the native 13/13 binding")
    return payload, []


def _number(value: object, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be an integer address")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError as exc:
            raise ValueError(f"{field} must be an integer address") from exc
    raise ValueError(f"{field} must be an integer address")


def _validate_alignment(start: int, end: int, entry: dict[str, object], label: str) -> None:
    alignment_value = entry.get("alignment", 1)
    alignment = _number(alignment_value, f"{label}.alignment")
    if alignment <= 0:
        raise ValueError(f"{label}.alignment must be positive")
    if start % alignment or end % alignment:
        raise ValueError(f"{label} violates its alignment")


def _range(entry: dict[str, object], label: str) -> tuple[int, int]:
    if type(entry) is not dict:
        raise ValueError(f"{label} must be an exact object")
    if "start" in entry and "end" in entry:
        start = _number(entry["start"], f"{label}.start")
        end = _number(entry["end"], f"{label}.end")
    elif "start" in entry and "length" in entry:
        start = _number(entry["start"], f"{label}.start")
        end = start + _number(entry["length"], f"{label}.length")
    elif "va" in entry and "length" in entry:
        start = _number(entry["va"], f"{label}.va")
        end = start + _number(entry["length"], f"{label}.length")
    elif "raw_offset" in entry and "length" in entry:
        start = _number(entry["raw_offset"], f"{label}.raw_offset")
        end = start + _number(entry["length"], f"{label}.length")
    else:
        raise ValueError(f"{label} must provide start/end or an address and length")
    if start < 0 or end < 0:
        raise ValueError(f"{label} cannot use a negative address")
    if end <= start:
        raise ValueError(f"{label} has an empty or reversed range")
    _validate_alignment(start, end, entry, label)
    return start, end


def _overlaps(left: tuple[int, int], right: tuple[int, int]) -> bool:
    return max(left[0], right[0]) < min(left[1], right[1])


def _ranges(entry: dict[str, object], label: str) -> list[tuple[str, int, int]]:
    """Return comparable raw/VA ranges without mixing address spaces."""

    if type(entry) is not dict:
        raise ValueError(f"{label} must be an exact object")
    if "va" in entry and "raw_offset" in entry:
        length = _number(entry.get("length"), f"{label}.length")
        va = _number(entry["va"], f"{label}.va")
        raw = _number(entry["raw_offset"], f"{label}.raw_offset")
        if va < 0 or raw < 0 or length <= 0:
            raise ValueError(f"{label} has an empty range")
        _validate_alignment(va, va + length, entry, f"{label}.va")
        _validate_alignment(raw, raw + length, entry, f"{label}.raw_offset")
        return [("va", va, va + length), ("raw", raw, raw + length)]
    start, end = _range(entry, label)
    address_space = entry.get("address_space", "raw")
    if type(address_space) is not str or address_space not in {"raw", "va"}:
        raise ValueError(f"{label}.address_space must be raw or va")
    return [(address_space, start, end)]


def validate_cave_hook_overlaps(
    caves: list[dict[str, object]],
    hooks: list[dict[str, object]],
    occupied: tuple[dict[str, object], ...] = KNOWN_OCCUPIED_RANGES,
) -> None:
    """Reject candidate cave/hook ranges that collide with known bytes or each other."""

    entries = [
        ("cave", entry, _ranges(entry, f"cave[{index}]"))
        for index, entry in enumerate(caves)
    ] + [
        ("hook", entry, _ranges(entry, f"hook[{index}]"))
        for index, entry in enumerate(hooks)
    ]
    for kind, entry, current_ranges in entries:
        _allowed_keys(entry, CANDIDATE_RANGE_KEYS, f"{kind} range")
        if "name" in entry:
            _exact_str(entry["name"], f"{kind} range.name")
        if "owner" in entry:
            _exact_str(entry["owner"], f"{kind} range.owner")
        if "preimage" in entry:
            _exact_str(entry["preimage"], f"{kind} range.preimage")
        name = entry.get("name", f"{kind}")
        for occupied_entry in occupied:
            occupied_ranges = _ranges(occupied_entry, f"occupied {occupied_entry['name']}")
            for space, current_start, current_end in current_ranges:
                for occupied_space, occupied_start, occupied_end in occupied_ranges:
                    if space == occupied_space and _overlaps(
                        (current_start, current_end), (occupied_start, occupied_end)
                    ):
                        raise ValueError(
                            f"{kind} {name!r} overlaps occupied {space} range "
                            f"{occupied_entry['name']} ({occupied_start:#x}-{occupied_end:#x})"
                        )
    for index, (_, left_entry, left_ranges) in enumerate(entries):
        for _, right_entry, right_ranges in entries[index + 1 :]:
            for left_space, left_start, left_end in left_ranges:
                for right_space, right_start, right_end in right_ranges:
                    if left_space == right_space and _overlaps(
                        (left_start, left_end), (right_start, right_end)
                    ):
                        raise ValueError(
                            f"candidate ranges {left_entry.get('name', index)!r} and "
                            f"{right_entry.get('name', 'candidate')!r} overlap in {left_space} space"
                        )


def validate_native_route_contract(native: dict[str, object]) -> None:
    """Guard each native UI route independently against the proven binding."""

    _known_keys(native, NATIVE_ROUTING_KEYS, "native_routing")
    if type(native.get("message")) is not int or native.get("message") != 8:
        raise ValueError("native UI routing must use message 8")
    _strict_structure(native.get("patches"), [], "native_routing.patches")
    _strict_structure(native.get("emitted_hooks"), [], "native_routing.emitted_hooks")
    _strict_structure(native.get("call_convention"), EXPECTED_CALL_CONVENTION, "native_routing.call_convention")
    for name in ("tech", "detail"):
        route = native.get(name)
        if not isinstance(route, dict):
            raise ValueError(f"native_routing.{name} is required")
        _known_keys(route, DETAIL_ROUTE_KEYS if name == "detail" else ROUTE_KEYS, f"native_routing.{name}")
        expected = {
            "resource": "0x6A",
            "dimensions": [96, 39],
            "local": [137, 2],
            "event": 13,
            "factory": "0x401BD0",
            "ownership": "0x40C680",
        }
        for field, value in expected.items():
            _strict_structure(route.get(field), value, f"native_routing.{name}.{field}")
        if name == "detail":
            if route.get("stock_input_method_entry") != f"0x{DETAIL_INPUT_METHOD_VA:X}":
                raise ValueError("native_routing.detail must identify stock input method entry 0x44B560")
            if route.get("stock_input_method_entry_bytes") != DETAIL_INPUT_METHOD_ENTRY_BYTES:
                raise ValueError("native_routing.detail stock input method entry bytes are not exact")
            expected_offline = {
                "candidate_route": f"0x{CURRENT_DETAIL_HOOK_TARGET_VA:X}",
                "candidate_callsite": f"0x{CURRENT_DETAIL_HOOK_VA:X}",
                "candidate_callsite_raw": f"0x{CURRENT_DETAIL_HOOK_RAW_OFFSET:X}",
                "candidate_hook_preimage": CURRENT_DETAIL_HOOK_PREIMAGE,
                "candidate_hook_detour": CURRENT_DETAIL_HOOK_DETOUR,
                "candidate_continuation": f"0x{CURRENT_DETAIL_CONTINUATION_VA:X}",
                "candidate_guard": {"message": 8, "control_id": 13},
                "candidate_fallback_replay": CURRENT_DETAIL_HOOK_PREIMAGE,
                "offline_install_verified": True,
                "offline_uninstall_verified": True,
                "hot_uninstall_verified": False,
                "event_dispatcher": {"range": "[0x4019B8,0x4019CF)", "size": 23, "sha256": "F2EB107944977E8CBCE7CAD450EC6D1D046880727EBDE36A939CF5DC5DDC907F", "call": "[0x4019CD,0x4019CF)"},
                "event_vtable_slot": "0x49A5A0",
                "control_inner_offsets": {"id": "+0x4", "parent": "+0x20"},
                "constructor_registration": {"raw": "0x4AF12", "receiver": "ESI", "control_id": 13},
                "teardown_chain": ["0x44B9F0", "0x44AF30", "0x40C7F0", "0x40C830"],
            }
            for field, value in expected_offline.items():
                _strict_structure(route.get(field), value, f"native_routing.detail.{field}")
            if route.get("current_emitted_hook") != f"0x{CURRENT_DETAIL_HOOK_VA:X}":
                raise ValueError("native_routing.detail current helper binding is not exact")
            if route.get("status") != DETAIL_STATUS:
                raise ValueError("native_routing.detail.status is not exact")
        elif route.get("status") != "native route preserved":
            raise ValueError("native_routing.tech.status is not exact")


def validate_native_transaction_bindings(bindings: dict[str, object]) -> None:
    """Require the exact static resolver/writer/ABI binding without emitting it."""

    _known_keys(bindings, NATIVE_BINDING_KEYS, "native_transaction_bindings")
    _known_keys(bindings["selected_index"], SELECTED_INDEX_KEYS, "native_transaction_bindings.selected_index")
    _known_keys(bindings["record_offsets"], RECORD_OFFSET_KEYS, "native_transaction_bindings.record_offsets")
    _known_keys(bindings["writers"], WRITER_KEYS, "native_transaction_bindings.writers")
    _known_keys(bindings["writers"]["skill"], SKILL_WRITER_KEYS, "native_transaction_bindings.writers.skill")
    _known_keys(bindings["writers"]["tech_charge"], CHARGE_WRITER_KEYS, "native_transaction_bindings.writers.tech_charge")
    _strict_structure(bindings, NATIVE_TRANSACTION_BINDINGS, "native_transaction_bindings")


def validate_stock_fingerprint(fingerprint: dict[str, object], *, enabled: bool) -> None:
    _known_keys(fingerprint, STOCK_FINGERPRINT_KEYS, "stock_fingerprint")
    if type(enabled) is not bool:
        raise ValueError("stock fingerprint enablement flag must be an exact bool")
    for field in ("filename", "sha256", "source", "status"):
        _exact_str(fingerprint.get(field), f"stock_fingerprint.{field}")
    if fingerprint.get("filename") != STOCK_FILENAME:
        raise ValueError("stock filename binding is not exact")
    if type(fingerprint.get("size")) is not int or fingerprint.get("size") != STOCK_SIZE or fingerprint.get("sha256") != STOCK_SHA256:
        raise ValueError("stock size/SHA-256 binding is not exact")
    if fingerprint.get("source") != STOCK_SOURCE_RELATIVE:
        raise ValueError("stock source path binding is not exact")
    if fingerprint.get("status") != STOCK_STATUS:
        raise ValueError("stock fingerprint status is not exact")
    if type(fingerprint.get("source_present")) is not bool or type(fingerprint.get("source_bound")) is not bool:
        raise ValueError("stock source flags must be exact bools")
    if fingerprint.get("source_present") is not fingerprint.get("source_bound"):
        raise ValueError("stock source presence and binding state disagree")
    if enabled and fingerprint.get("source_bound") is not True:
        raise ValueError("enablement requires repository-owned exact stock evidence")


def validate_composition_guard(composition: dict[str, object]) -> None:
    """Bind parent hashes and owned ranges before any candidate composition."""

    _known_keys(composition, COMPOSITION_KEYS, "composition_guard")
    if composition.get("stock_sha256") != STOCK_SHA256:
        raise ValueError("composition guard must bind the exact stock SHA-256")
    base = composition.get("base_parent")
    _known_keys(base, BASE_PARENT_KEYS, "composition_guard.base_parent")
    _strict_structure(base, {
        "feature": "vv5_enable_origins_exclusive_features",
        "manifest": "data/vv5_origins_feature.json",
        "manifest_sha256": ACTIVE_BASE_SHA256,
    }, "composition_guard.base_parent")
    mastery = composition.get("full_mastery")
    _known_keys(mastery, FULL_MASTERY_KEYS, "composition_guard.full_mastery")
    _strict_structure(mastery, {
        "feature": "vv5_full_mastery_all_stage_a_candidate",
        "map": "data/candidates/vv5_full_mastery_all_candidate_map.json",
        "map_sha256": FULL_MASTERY_MAP_SHA256,
        "parent_hashes": FULL_MASTERY_PARENT_HASHES,
        "owned_range": "0xF2000-0xF4000",
    }, "composition_guard.full_mastery")
    running = composition.get("running")
    _known_keys(running, RUNNING_KEYS, "composition_guard.running")
    _strict_structure(running, {
        "feature": "vv5_individual_grant_running_candidate",
        "map": "data/candidates/vv5_individual_running_candidate_map.json",
        "map_sha256": RUNNING_MAP_SHA256,
        "parent_hash": FULL_MASTERY_PARENT_HASHES["collection_progression"],
        "owned_range": "0xF4000-0xF6000",
    }, "composition_guard.running")
    full_heal = composition.get("full_heal")
    _known_keys(full_heal, FULL_HEAL_KEYS, "composition_guard.full_heal")
    _strict_structure(full_heal, {
        "feature": "vv5_full_heal",
        "status": "absent; no candidate bytes claimed",
        "ranges": [],
    }, "composition_guard.full_heal")
    ranges = composition.get("ranges")
    if ranges != list(KNOWN_OCCUPIED_RANGES):
        raise ValueError("composition range ownership does not match the exact inventory")
    if type(ranges) is not list:
        raise ValueError("composition ranges must be an exact list")
    for index, entry in enumerate(ranges):
        _known_keys(entry, RANGE_KEYS - {"alignment"}, f"composition_guard.ranges[{index}]")
        _exact_str(entry.get("name"), f"composition_guard.ranges[{index}].name")
        _exact_str(entry.get("owner"), f"composition_guard.ranges[{index}].owner")
        if entry.get("address_space") != "raw":
            raise ValueError(f"composition_guard.ranges[{index}].address_space must be raw")
        _range(entry, f"composition_guard.ranges[{index}]")
    validate_cave_hook_overlaps(list(ranges), [], ())
    for path, expected_hash in (
        (FULL_MASTERY_MAP_PATH, FULL_MASTERY_MAP_SHA256),
        (RUNNING_MAP_PATH, RUNNING_MAP_SHA256),
        (FULL_MASTERY_FEATURE_PATH, FULL_MASTERY_FEATURE_SHA256),
    ):
        if not path.is_file() or sha(path.read_bytes()) != expected_hash:
            raise ValueError(f"composition source hash is not exact: {path.as_posix()}")
    mastery_map = json.loads(FULL_MASTERY_MAP_PATH.read_text(encoding="utf-8"))
    _strict_structure(mastery_map.get("source"), {
        "size": STOCK_SIZE,
        "sha256": STOCK_SHA256,
    }, "Full Mastery map source")
    _strict_structure(mastery_map.get("active_base"), {
        "path": "data/vv5_origins_feature.json",
        "size": ACTIVE_BASE.stat().st_size,
        "sha256": ACTIVE_BASE_SHA256,
    }, "Full Mastery map active_base")
    if mastery_map.get("feature_manifest_sha256") != FULL_MASTERY_FEATURE_SHA256:
        raise ValueError("Full Mastery feature manifest hash is not exact")
    running_map = json.loads(RUNNING_MAP_PATH.read_text(encoding="utf-8"))
    candidate = running_map.get("candidate")
    if not isinstance(candidate, dict) or candidate.get("parent_hashes") != {
        "collection_progression": FULL_MASTERY_PARENT_HASHES["collection_progression"]
    }:
        raise ValueError("Running map parent hash is not exact")


def validate_source_hashes(source: dict[str, object]) -> None:
    """Bind both declared hashes and the repository-owned source bytes."""

    _known_keys(source, SOURCE_KEYS, "source")
    _strict_structure(
        source,
        {
            "stock_sha256": STOCK_SHA256,
            "active_base": "data/vv5_origins_feature.json",
            "active_payload_sha256": ACTIVE_PAYLOAD_SHA256,
            "bound_payload_sha256": ACTIVE_PAYLOAD_SHA256,
        },
        "source",
    )
    if sha(ACTIVE_BASE.read_bytes()) != ACTIVE_BASE_SHA256:
        raise ValueError("repository-owned active base hash is not exact")
    if sha(active_payload()) != ACTIVE_PAYLOAD_SHA256:
        raise ValueError("repository-owned active payload hash is not exact")


def validate_transaction_contracts(contracts: object) -> None:
    """Require every action's static contract, including both callbacks."""

    if type(contracts) is not dict or set(contracts) != set(CONTRACT_ACTION_KEYS):
        raise ValueError("individual_actions must contain the exact four action contracts")
    expected = transaction_contracts()
    for action, expected_keys in CONTRACT_ACTION_KEYS.items():
        contract = contracts[action]
        _known_keys(contract, expected_keys, f"individual_actions.{action}")
        _strict_structure(contract, expected[action], f"individual_actions.{action}")


def validate_detail_enablement(manifest: dict[str, object]) -> None:
    """Fail closed unless native Detail evidence is complete and non-reused."""

    native = manifest.get("native_routing")
    if not isinstance(native, dict):
        raise ValueError("native_routing is required")
    detail = native.get("detail")
    if not isinstance(detail, dict):
        raise ValueError("native_routing.detail is required")
    validate_native_route_contract(native)
    _known_keys(detail, DETAIL_ROUTE_KEYS, "native_routing.detail")
    evidence = detail.get("evidence")
    _known_keys(evidence, DETAIL_EVIDENCE_KEYS, "native_routing.detail.evidence")
    caves = detail.get("candidate_caves")
    hooks = detail.get("candidate_hooks")
    if type(caves) is not list or type(hooks) is not list:
        raise ValueError("Detail candidate caves and hooks must be exact lists")
    enabled = manifest.get("enabled")
    if type(enabled) is not bool:
        raise ValueError("candidate enabled must be an exact bool")
    if not enabled:
        _strict_structure(detail.get("proposed_hook"), None, "native_routing.detail.proposed_hook")
        _strict_structure(evidence, {
            "stock_sha256": STOCK_SHA256,
            "preimage_va": None,
            "preimage": None,
            "continuation_va": None,
            "continuation_bytes": None,
            "hook_length": None,
            "instruction_boundary_verified": False,
            "abi_verified": False,
            "ownership_verified": False,
            "child_destructor_verified": False,
            "native_target_va": None,
            "va_raw_relationship_verified": False,
        }, "native_routing.detail.evidence")
        _strict_structure(caves, [], "native_routing.detail.candidate_caves")
        _strict_structure(hooks, [], "native_routing.detail.candidate_hooks")
        return

    proposed = detail.get("proposed_hook")
    if not isinstance(proposed, dict):
        raise ValueError("enabled Detail requires a proposed guarded hook")
    _allowed_keys(proposed, CANDIDATE_RANGE_KEYS, "native_routing.detail.proposed_hook")
    for field in ("va", "raw_offset"):
        if field not in proposed:
            raise ValueError(f"proposed_hook.{field} is required")
    if type(proposed.get("length")) is not int:
        raise ValueError("proposed_hook.length must be an exact int")
    hook_va = _number(proposed.get("va"), "proposed_hook.va")
    hook_raw = _number(proposed.get("raw_offset"), "proposed_hook.raw_offset")
    if hook_va != CURRENT_DETAIL_HOOK_VA or hook_raw != CURRENT_DETAIL_HOOK_RAW_OFFSET:
        raise ValueError("enabled Detail must use the exact offline 0x44BC20 event detour")
    if hook_va == DETAIL_INPUT_METHOD_VA:
        raise ValueError("0x44B560 is a stock method entry, not a proven candidate callsite")

    if evidence.get("stock_sha256") != STOCK_SHA256:
        raise ValueError("Detail evidence must bind the exact stock build")
    preimage = evidence.get("preimage")
    continuation = evidence.get("continuation_bytes")
    if not isinstance(preimage, str) or not preimage or not isinstance(continuation, str) or not continuation:
        raise ValueError("Detail requires exact preimage and continuation bytes")
    try:
        preimage_bytes = bytes.fromhex(preimage)
        continuation_bytes = bytes.fromhex(continuation)
    except ValueError as exc:
        raise ValueError("Detail preimage and continuation must be hex bytes") from exc
    if not preimage_bytes or not continuation_bytes:
        raise ValueError("Detail preimage and continuation must be non-empty bytes")
    hook_length = _exact_int(evidence.get("hook_length"), "detail evidence.hook_length")
    if len(preimage_bytes) != hook_length:
        raise ValueError("Detail preimage length must equal the guarded hook length")
    continuation_va = _number(evidence.get("continuation_va"), "detail evidence.continuation_va")
    if continuation_va != CURRENT_DETAIL_CONTINUATION_VA:
        raise ValueError("Detail continuation must be exact 0x44BC28")
    for field in (
        "instruction_boundary_verified",
        "abi_verified",
        "ownership_verified",
        "child_destructor_verified",
        "va_raw_relationship_verified",
    ):
        if evidence.get(field) is not True:
            raise ValueError(f"Detail evidence must verify {field}")
    if preimage.upper() != CURRENT_DETAIL_HOOK_PREIMAGE:
        raise ValueError("Detail preimage must equal the exact 0x44BC20 stock bytes")
    proposed_preimage = proposed.get("preimage")
    if proposed_preimage is not None and proposed_preimage.upper() != CURRENT_DETAIL_HOOK_PREIMAGE:
        raise ValueError("proposed Detail preimage must equal the exact stock bytes")
    validate_cave_hook_overlaps(
        caves,
        [proposed, *hooks],
    )
    fingerprint = manifest.get("stock_fingerprint")
    if not isinstance(fingerprint, dict):
        raise ValueError("enabled Detail requires stock fingerprint evidence")
    validate_stock_fingerprint(fingerprint, enabled=True)


def validate_candidate_manifest(manifest: dict[str, object]) -> None:
    _known_keys(manifest, MANIFEST_KEYS, "candidate manifest")
    for field in ("enabled", "catalog_hidden", "catalog_enabled", "expanded_fail_closed"):
        _exact_bool(manifest.get(field), f"candidate manifest.{field}")
    if manifest["enabled"] is not False:
        raise ValueError("candidate must remain disabled")
    if manifest["catalog_hidden"] is not True:
        raise ValueError("candidate must remain catalog-hidden")
    if manifest["catalog_enabled"] is not False:
        raise ValueError("candidate catalog must remain disabled")
    if manifest["expanded_fail_closed"] is not True:
        raise ValueError("expanded modes must remain fail-closed")
    if manifest.get("runtime_status") != RUNTIME_STATUS:
        raise ValueError("candidate runtime status must remain pending")
    _strict_structure(manifest.get("allowed_modes"), ["collection_progression", "immediate_fixed"], "candidate manifest.allowed_modes")
    _strict_structure(
        manifest.get("unsupported_patch_modes"),
        ["experimental_expanded_256", "experimental_expanded_256_progression"],
        "candidate manifest.unsupported_patch_modes",
    )
    _strict_structure(manifest.get("dependencies"), ["vv5_enable_origins_exclusive_features"], "candidate manifest.dependencies")
    _exact_str(manifest.get("id"), "candidate manifest.id")
    _exact_str(manifest.get("game_id"), "candidate manifest.game_id")
    _exact_str(manifest.get("name"), "candidate manifest.name")
    if manifest["id"] != "vv5_ui_confirmation_candidate":
        raise ValueError("candidate manifest.id is not exact")
    if manifest["game_id"] != "vv5":
        raise ValueError("candidate manifest.game_id is not exact")
    if manifest["name"] != "DISABLED Candidate: VV5 UI and Individual Confirmations":
        raise ValueError("candidate manifest.name is not exact")
    source = manifest.get("source")
    if not isinstance(source, dict):
        raise ValueError("source is required")
    validate_source_hashes(source)
    native = manifest.get("native_routing")
    if not isinstance(native, dict):
        raise ValueError("native_routing is required")
    detail = native.get("detail")
    if not isinstance(detail, dict):
        raise ValueError("native_routing.detail is required")
    caves = detail.get("candidate_caves", [])
    hooks = detail.get("candidate_hooks", [])
    if not isinstance(caves, list) or not isinstance(hooks, list):
        raise ValueError("candidate caves and hooks must be lists")
    validate_native_route_contract(native)
    if native.get("patches") != [] or native.get("emitted_hooks") != []:
        raise ValueError("disabled candidate must emit no native hook or patch")
    fingerprint = manifest.get("stock_fingerprint")
    if not isinstance(fingerprint, dict):
        raise ValueError("stock fingerprint is required")
    validate_stock_fingerprint(fingerprint, enabled=manifest["enabled"])
    bindings = manifest.get("native_transaction_bindings")
    if not isinstance(bindings, dict):
        raise ValueError("native transaction bindings are required")
    validate_native_transaction_bindings(bindings)
    composition = manifest.get("composition_guard")
    if not isinstance(composition, dict):
        raise ValueError("composition guard is required")
    validate_composition_guard(composition)
    validate_cave_hook_overlaps(caves, hooks)
    validate_detail_enablement(manifest)
    gate = _known_keys(manifest.get("native_evidence_gate"), NATIVE_EVIDENCE_GATE_KEYS, "native_evidence_gate")
    expected_gate = {
        "path": "data/vv5_tech_detail_native_evidence.json",
        "status": "absent/pending authenticated evidence; no native output",
        "evidence_complete": False,
        "publication_ready": False,
        "native_output": False,
    }
    _strict_structure(gate, expected_gate, "native_evidence_gate")
    _, evidence_complete = load_native_evidence()
    if evidence_complete:
        raise ValueError("pending UI candidate cannot accept completed evidence without an independent enablement review")
    validate_transaction_contracts(manifest.get("individual_actions"))
    implementation = manifest.get("implementation")
    _known_keys(implementation, IMPLEMENTATION_KEYS, "implementation")
    _strict_structure(implementation, {
        "transaction_engine": "src/vv5_individual_transactions.py",
        "native_writer_policy": "reference-only; native writes, readbacks, rollback, and output wiring are not implemented",
        "save_policy": "no save reads or writes are performed by the reference engine",
    }, "implementation")


def build_manifest() -> dict[str, object]:
    original = active_payload()
    payload, changes = bound_payload()
    manifest = {
        "id": "vv5_ui_confirmation_candidate",
        "game_id": "vv5",
        "name": "DISABLED Candidate: VV5 UI and Individual Confirmations",
        "enabled": False,
        "catalog_hidden": True,
        "catalog_enabled": False,
        "runtime_status": RUNTIME_STATUS,
        "allowed_modes": ["collection_progression", "immediate_fixed"],
        "unsupported_patch_modes": [
            "experimental_expanded_256",
            "experimental_expanded_256_progression",
        ],
        "expanded_fail_closed": True,
        "dependencies": ["vv5_enable_origins_exclusive_features"],
        "source": {
            "stock_sha256": STOCK_SHA256,
            "active_base": "data/vv5_origins_feature.json",
            "active_payload_sha256": sha(original),
            "bound_payload_sha256": sha(payload),
        },
        "stock_fingerprint": STOCK_FINGERPRINT,
        "native_routing": {
            "message": 8,
            "tech": {
                "resource": "0x6A",
                "dimensions": [96, 39],
                "local": [137, 2],
                "event": 13,
                "factory": "0x401BD0",
                "ownership": "0x40C680",
                "status": "native route preserved",
            },
            "detail": {
                "resource": "0x6A",
                "dimensions": [96, 39],
                "local": [137, 2],
                "event": DETAIL_EVENT,
                "factory": "0x401BD0",
                "ownership": "0x40C680",
                "stock_input_method_entry": f"0x{DETAIL_INPUT_METHOD_VA:X}",
                "stock_input_method_entry_bytes": DETAIL_INPUT_METHOD_ENTRY_BYTES,
                "stock_input_stack_locals": "0x44",
                "stock_input_cleanup": "ret 0xC",
                "stock_vtable": "0x49A590",
                "stock_destructor": "0x44B9F0",
                "stock_draw": "0x44B250",
                "stock_event_method": "0x44BC20",
                "stock_event_cleanup": "ret 8",
                "stock_xref_to_7B22C0": False,
                "stock_xref_to_7B2600": False,
                "candidate_route": f"0x{CURRENT_DETAIL_HOOK_TARGET_VA:X}",
                "candidate_callsite": f"0x{CURRENT_DETAIL_HOOK_VA:X}",
                "candidate_callsite_raw": f"0x{CURRENT_DETAIL_HOOK_RAW_OFFSET:X}",
                "candidate_hook_preimage": CURRENT_DETAIL_HOOK_PREIMAGE,
                "candidate_hook_detour": CURRENT_DETAIL_HOOK_DETOUR,
                "candidate_continuation": f"0x{CURRENT_DETAIL_CONTINUATION_VA:X}",
                "candidate_guard": {"message": 8, "control_id": 13},
                "candidate_fallback_replay": CURRENT_DETAIL_HOOK_PREIMAGE,
                "offline_install_verified": True,
                "offline_uninstall_verified": True,
                "hot_uninstall_verified": False,
                "event_dispatcher": {"range": "[0x4019B8,0x4019CF)", "size": 23, "sha256": "F2EB107944977E8CBCE7CAD450EC6D1D046880727EBDE36A939CF5DC5DDC907F", "call": "[0x4019CD,0x4019CF)"},
                "event_vtable_slot": "0x49A5A0",
                "control_inner_offsets": {"id": "+0x4", "parent": "+0x20"},
                "constructor_registration": {"raw": "0x4AF12", "receiver": "ESI", "control_id": 13},
                "teardown_chain": ["0x44B9F0", "0x44AF30", "0x40C7F0", "0x40C830"],
                "current_emitted_hook": f"0x{CURRENT_DETAIL_HOOK_VA:X}",
                "status": DETAIL_STATUS,
                "proposed_hook": None,
                "evidence": {
                    "stock_sha256": STOCK_SHA256,
                    "preimage_va": None,
                    "preimage": None,
                    "continuation_va": None,
                    "continuation_bytes": None,
                    "hook_length": None,
                    "instruction_boundary_verified": False,
                    "abi_verified": False,
                    "ownership_verified": False,
                    "child_destructor_verified": False,
                    "native_target_va": None,
                    "va_raw_relationship_verified": False,
                },
                "candidate_caves": [],
                "candidate_hooks": [],
            },
            "patches": changes,
            "emitted_hooks": [],
            "call_convention": EXPECTED_CALL_CONVENTION,
        },
        "native_transaction_bindings": NATIVE_TRANSACTION_BINDINGS,
        "native_evidence_gate": {
            "path": "data/vv5_tech_detail_native_evidence.json",
            "status": "absent/pending authenticated evidence; no native output",
            "evidence_complete": False,
            "publication_ready": False,
            "native_output": False,
        },
        "composition_guard": {
            "stock_sha256": STOCK_SHA256,
            "base_parent": {
                "feature": "vv5_enable_origins_exclusive_features",
                "manifest": "data/vv5_origins_feature.json",
                "manifest_sha256": ACTIVE_BASE_SHA256,
            },
            "full_mastery": {
                "feature": "vv5_full_mastery_all_stage_a_candidate",
                "map": "data/candidates/vv5_full_mastery_all_candidate_map.json",
                "map_sha256": FULL_MASTERY_MAP_SHA256,
                "parent_hashes": FULL_MASTERY_PARENT_HASHES,
                "owned_range": "0xF2000-0xF4000",
            },
            "running": {
                "feature": "vv5_individual_grant_running_candidate",
                "map": "data/candidates/vv5_individual_running_candidate_map.json",
                "map_sha256": RUNNING_MAP_SHA256,
                "parent_hash": FULL_MASTERY_PARENT_HASHES["collection_progression"],
                "owned_range": "0xF4000-0xF6000",
            },
            "full_heal": {
                "feature": "vv5_full_heal",
                "status": "absent; no candidate bytes claimed",
                "ranges": [],
            },
            "ranges": list(KNOWN_OCCUPIED_RANGES),
        },
        "individual_actions": transaction_contracts(),
        "implementation": {
            "transaction_engine": "src/vv5_individual_transactions.py",
            "native_writer_policy": "reference-only; native writes, readbacks, rollback, and output wiring are not implemented",
            "save_policy": "no save reads or writes are performed by the reference engine",
        },
    }
    validate_candidate_manifest(manifest)
    return manifest


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    OUTPUT_MANIFEST.write_text(json.dumps(build_manifest(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT_MANIFEST), "sha256": sha(OUTPUT_MANIFEST.read_bytes())}, indent=2))


if __name__ == "__main__":
    main()
