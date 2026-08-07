"""Build the disabled VV5 UI/individual-transaction candidate evidence."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from vv5_individual_transactions import transaction_contracts


ROOT = Path(__file__).resolve().parents[1]
ACTIVE_BASE = ROOT / "data" / "vv5_origins_feature.json"
OUTPUT = ROOT / "outputs" / "vv5-ui-confirmation-candidate"
OUTPUT_MANIFEST = OUTPUT / "candidate.json"
STOCK_SHA256 = "92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D"
STOCK_FILENAME = "Virtual Villagers - New Believers.exe"
STOCK_SIZE = 991232
STOCK_SOURCE_RELATIVE = "research/stock-executables/Virtual Villagers - New Believers.exe"
ACTIVE_BASE_SHA256 = "797456C51CA86A7C802B7B6F2B0C8FCDFFF1C1E205923FA9A1F3E0A503FDB823"
FULL_MASTERY_MAP_SHA256 = "70B87F7F4F6CC0E4BA0F083F42670E0EC1B9B7A7C683068DB3D835C41FA80167"
RUNNING_MAP_SHA256 = "7D8A30C80CF14EB84DAC62AC324ED476F60E92B543A0B9DA3870F5184339F358"
FULL_MASTERY_PARENT_HASHES = {
    "collection_progression": "857E22D7C361B802508BF789C3CC486E42E76021F5AA579BB1D16CC6E0D017A0",
    "immediate_fixed": "E93822F752F730ECB751EBAA87021194C992984721B4370FF0015D5FC4BB2E9A",
}
PAYLOAD_OFFSET = 0xDB000
PAYLOAD_SIZE = 0x1000
TECH_EVENT = 13
DETAIL_EVENT = 13
DETAIL_NATIVE_HANDLER_VA = 0x44B560
DETAIL_NATIVE_HANDLER_RAW_OFFSET = 0xB560
CURRENT_DETAIL_HOOK_VA = 0x44BC20
CURRENT_DETAIL_HOOK_RAW_OFFSET = 0x4BC20
CURRENT_DETAIL_HOOK_PREIMAGE = "83EC18A1A8974D00"
CURRENT_DETAIL_CONTINUATION_VA = 0x44BC28

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
    "status": "exact stock executable is not repository-owned in this checkout",
}

KNOWN_OCCUPIED_RANGES = (
    {"name": "origins_shr_payload", "start": 0xDB000, "end": 0xDC000, "owner": "vv5_enable_origins_exclusive_features"},
    {"name": "full_mastery_append_page", "start": 0xF2000, "end": 0xF4000, "owner": "vv5_full_mastery_all_stage_a_candidate"},
    {"name": "running_append_page", "start": 0xF4000, "end": 0xF6000, "owner": "vv5_individual_grant_running_candidate"},
    {"name": "tech_constructor_hook", "start": 0x40A24, "end": 0x40A2A, "owner": "vv5_enable_origins_exclusive_features"},
    {"name": "tech_event_hook", "start": 0x415F0, "end": 0x415F8, "owner": "vv5_enable_origins_exclusive_features"},
    {"name": "detail_constructor_hook", "start": 0x4AF12, "end": 0x4AF18, "owner": "vv5_enable_origins_exclusive_features"},
    {"name": "current_detail_hook", "start": 0x4BC20, "end": 0x4BC28, "owner": "vv5_enable_origins_exclusive_features"},
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


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


def _range(entry: dict[str, object], label: str) -> tuple[int, int]:
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
    if end <= start:
        raise ValueError(f"{label} has an empty or reversed range")
    return start, end


def _overlaps(left: tuple[int, int], right: tuple[int, int]) -> bool:
    return max(left[0], right[0]) < min(left[1], right[1])


def _ranges(entry: dict[str, object], label: str) -> list[tuple[str, int, int]]:
    """Return comparable raw/VA ranges without mixing address spaces."""

    if "va" in entry and "raw_offset" in entry:
        length = _number(entry.get("length"), f"{label}.length")
        va = _number(entry["va"], f"{label}.va")
        raw = _number(entry["raw_offset"], f"{label}.raw_offset")
        if length <= 0:
            raise ValueError(f"{label} has an empty range")
        return [("va", va, va + length), ("raw", raw, raw + length)]
    start, end = _range(entry, label)
    address_space = entry.get("address_space", "raw")
    if address_space not in {"raw", "va"}:
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

    if native.get("message") != 8:
        raise ValueError("native UI routing must use message 8")
    for name in ("tech", "detail"):
        route = native.get(name)
        if not isinstance(route, dict):
            raise ValueError(f"native_routing.{name} is required")
        if route.get("resource") != "0x6A":
            raise ValueError(f"native_routing.{name} must use resource 0x6A")
        if route.get("dimensions") != [96, 39]:
            raise ValueError(f"native_routing.{name} dimensions are not the proven 96x39")
        if route.get("local") != [137, 2]:
            raise ValueError(f"native_routing.{name} local geometry is not the proven (137,2)")
        if route.get("event") != 13:
            raise ValueError(f"native_routing.{name} must use event 13")
        if route.get("factory") != "0x401BD0":
            raise ValueError(f"native_routing.{name} must use factory 0x401BD0")
        if route.get("ownership") != "0x40C680":
            raise ValueError(f"native_routing.{name} must use ownership 0x40C680")


def validate_native_transaction_bindings(bindings: dict[str, object]) -> None:
    """Require the exact static resolver/writer/ABI binding without emitting it."""

    if bindings.get("stock_sha256") != STOCK_SHA256:
        raise ValueError("native transaction bindings must use the exact stock SHA-256")
    selected = bindings.get("selected_index")
    if not isinstance(selected, dict) or selected != NATIVE_TRANSACTION_BINDINGS["selected_index"]:
        raise ValueError("selected-index resolver ABI/offset binding is incomplete")
    if bindings.get("record_offsets") != NATIVE_TRANSACTION_BINDINGS["record_offsets"]:
        raise ValueError("record field offsets are incomplete or changed")
    if bindings.get("writers") != NATIVE_TRANSACTION_BINDINGS["writers"]:
        raise ValueError("native writer/charge ABI binding is incomplete")
    if bindings.get("status") != NATIVE_TRANSACTION_BINDINGS["status"]:
        raise ValueError("native transaction binding must remain static-only")


def validate_stock_fingerprint(fingerprint: dict[str, object], *, enabled: bool) -> None:
    if fingerprint.get("filename") != STOCK_FILENAME:
        raise ValueError("stock filename binding is not exact")
    if fingerprint.get("size") != STOCK_SIZE or fingerprint.get("sha256") != STOCK_SHA256:
        raise ValueError("stock size/SHA-256 binding is not exact")
    if fingerprint.get("source") != STOCK_SOURCE_RELATIVE:
        raise ValueError("stock source path binding is not exact")
    if fingerprint.get("source_present") is not fingerprint.get("source_bound"):
        raise ValueError("stock source presence and binding state disagree")
    if enabled and fingerprint.get("source_bound") is not True:
        raise ValueError("enablement requires repository-owned exact stock evidence")


def validate_composition_guard(composition: dict[str, object]) -> None:
    """Bind parent hashes and owned ranges before any candidate composition."""

    if composition.get("stock_sha256") != STOCK_SHA256:
        raise ValueError("composition guard must bind the exact stock SHA-256")
    base = composition.get("base_parent")
    if not isinstance(base, dict) or base.get("manifest_sha256") != ACTIVE_BASE_SHA256:
        raise ValueError("composition guard base parent hash is not exact")
    mastery = composition.get("full_mastery")
    if not isinstance(mastery, dict) or mastery.get("map_sha256") != FULL_MASTERY_MAP_SHA256:
        raise ValueError("Full Mastery composition map hash is not exact")
    if mastery.get("parent_hashes") != FULL_MASTERY_PARENT_HASHES:
        raise ValueError("Full Mastery parent hashes are incomplete")
    running = composition.get("running")
    if not isinstance(running, dict) or running.get("map_sha256") != RUNNING_MAP_SHA256:
        raise ValueError("Running composition map hash is not exact")
    if running.get("parent_hash") != FULL_MASTERY_PARENT_HASHES["collection_progression"]:
        raise ValueError("Running parent hash is not the exact Full Mastery composition")
    full_heal = composition.get("full_heal")
    if not isinstance(full_heal, dict) or full_heal.get("status") != "absent; no candidate bytes claimed":
        raise ValueError("Full Heal must remain explicitly absent and disabled")
    if full_heal.get("ranges") != []:
        raise ValueError("Full Heal cannot claim an unowned range")
    ranges = composition.get("ranges")
    if ranges != list(KNOWN_OCCUPIED_RANGES):
        raise ValueError("composition range ownership does not match the exact inventory")
    validate_cave_hook_overlaps(list(ranges), [], ())


def validate_detail_enablement(manifest: dict[str, object]) -> None:
    """Fail closed unless native Detail evidence is complete and non-reused."""

    native = manifest.get("native_routing")
    if not isinstance(native, dict):
        raise ValueError("native_routing is required")
    detail = native.get("detail")
    if not isinstance(detail, dict):
        raise ValueError("native_routing.detail is required")
    validate_native_route_contract(native)
    if not manifest.get("enabled", False):
        if native.get("patches"):
            raise ValueError("disabled candidate cannot emit native patches")
        return

    if detail.get("native_handler") != f"0x{DETAIL_NATIVE_HANDLER_VA:X}":
        raise ValueError("enabled Detail must target native sub_44B560")
    proposed = detail.get("proposed_hook")
    if not isinstance(proposed, dict):
        raise ValueError("enabled Detail requires a proposed guarded hook")
    hook_va = _number(proposed.get("va"), "proposed_hook.va")
    hook_raw = _number(proposed.get("raw_offset"), "proposed_hook.raw_offset")
    if hook_va == CURRENT_DETAIL_HOOK_VA or hook_raw == CURRENT_DETAIL_HOOK_RAW_OFFSET:
        raise ValueError("0x44BC20 is the existing hook and cannot be reused")
    if hook_va != DETAIL_NATIVE_HANDLER_VA or hook_raw != DETAIL_NATIVE_HANDLER_RAW_OFFSET:
        raise ValueError("enabled Detail hook must bind the exact 0x44B560 entry")

    evidence = detail.get("evidence")
    if not isinstance(evidence, dict):
        raise ValueError("enabled Detail requires exact native evidence")
    if evidence.get("stock_sha256") != STOCK_SHA256:
        raise ValueError("Detail evidence must bind the exact stock build")
    if _number(evidence.get("preimage_va"), "detail evidence.preimage_va") != DETAIL_NATIVE_HANDLER_VA:
        raise ValueError("Detail preimage must be located at 0x44B560")
    preimage = evidence.get("preimage")
    continuation = evidence.get("continuation_bytes")
    if not isinstance(preimage, str) or not preimage or not isinstance(continuation, str) or not continuation:
        raise ValueError("Detail requires exact preimage and continuation bytes")
    try:
        preimage_bytes = bytes.fromhex(preimage)
        bytes.fromhex(continuation)
    except ValueError as exc:
        raise ValueError("Detail preimage and continuation must be hex bytes") from exc
    hook_length = _number(evidence.get("hook_length"), "detail evidence.hook_length")
    if len(preimage_bytes) != hook_length:
        raise ValueError("Detail preimage length must equal the guarded hook length")
    continuation_va = _number(evidence.get("continuation_va"), "detail evidence.continuation_va")
    if continuation_va == CURRENT_DETAIL_CONTINUATION_VA:
        raise ValueError("Detail cannot reuse the 0x44BC20 continuation")
    for field in (
        "instruction_boundary_verified",
        "abi_verified",
        "ownership_verified",
        "child_destructor_verified",
    ):
        if evidence.get(field) is not True:
            raise ValueError(f"Detail evidence must verify {field}")
    if preimage.upper() == CURRENT_DETAIL_HOOK_PREIMAGE:
        raise ValueError("0x44BC20 preimage bytes cannot be reused")
    if proposed.get("preimage", "").upper() == CURRENT_DETAIL_HOOK_PREIMAGE:
        raise ValueError("0x44BC20 preimage bytes cannot be reused")
    validate_cave_hook_overlaps(
        detail.get("candidate_caves", []),
        [proposed, *detail.get("candidate_hooks", [])],
    )
    fingerprint = manifest.get("stock_fingerprint")
    if not isinstance(fingerprint, dict):
        raise ValueError("enabled Detail requires stock fingerprint evidence")
    validate_stock_fingerprint(fingerprint, enabled=True)


def validate_candidate_manifest(manifest: dict[str, object]) -> None:
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
    fingerprint = manifest.get("stock_fingerprint")
    if not isinstance(fingerprint, dict):
        raise ValueError("stock fingerprint is required")
    validate_stock_fingerprint(fingerprint, enabled=bool(manifest.get("enabled", False)))
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
        "runtime_status": "pending; no package or player validation",
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
                "native_handler": f"0x{DETAIL_NATIVE_HANDLER_VA:X}",
                "current_emitted_hook": f"0x{CURRENT_DETAIL_HOOK_VA:X}",
                "status": "disabled pending exact guarded preimage for the native Detail handler",
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
                },
                "candidate_caves": [],
                "candidate_hooks": [],
            },
            "patches": changes,
            "call_convention": [
                "preserve ECX=EDI before native 0x44FA20 thiscall",
                "preserve native 0x401BD0 factory and 0x40C680 ownership registration",
                "preserve ret 8 and original handler fallback prologues",
            ],
        },
        "native_transaction_bindings": NATIVE_TRANSACTION_BINDINGS,
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
