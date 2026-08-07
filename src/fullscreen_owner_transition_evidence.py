"""Disabled evidence gate for future VV3-VV5 fullscreen modal ownership work."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Mapping

SCHEMA = "vvfp.fullscreen_owner_transition_evidence"
VERSION = 1
GAMES = ("vv3", "vv4", "vv5")
ROUTES = ("tech", "detail", "full_mastery", "full_heal", "active_modal_upgrades")
SCENARIOS = ("cancel", "no_op", "success", "failure", "foreground_change", "restore_failure")
HASH = re.compile(r"^[0-9A-F]{64}$")
STOCK = {
    "vv3": ("Virtual Villagers - The Secret City.exe", 831488, "8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503"),
    "vv4": ("Virtual Villagers - The Tree of Life.exe", 929792, "6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220"),
    "vv5": ("Virtual Villagers - New Believers.exe", 991232, "92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D"),
}
STATIC_WRAPPERS = {
    "vv3": {"tech": "923F8CC4F371B20D92DE276B3D7176DAEDDA305D77C799164D9FCB8D3BA27F82", "detail": "D14CBD322AE2661FCECBA6FAB306CB4029B988118C244A191A1225ECDD6559FB", "page": "D76FD21C6630FCCDE5AB840616217F51A775A86C827A83E5512B68B8D2990011"},
    "vv4": {"tech": "6434441BC49F81C0B9A9C80DE7433FE9C48475500F318CF24C3A1B3E399E1336", "detail": "78E1C51CE00E1080AE3B9DA6FDFECDFD53A65DC03432E0AE489FD2A52584E858", "page": "2A722F2867BECFAA35CC46EE2B4B7D50056063142E983B11F447221E1AD13512"},
    "vv5": {},
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
    if not _mapping(flags) or set(flags) != {"enabled", "publication", "native_emission", "runtime_verified", "player_verified"} or any(value is not False for value in flags.values()):
        errors.append("all feature/publication/native/runtime/player flags must be explicitly false")
    games = data.get("games")
    if not _mapping(games) or set(games) != set(GAMES):
        errors.append("exact vv3/vv4/vv5 game set required")
        games = {}
    for game in GAMES:
        record = games.get(game, {}) if _mapping(games) else {}
        expected_name, expected_size, expected_sha = STOCK[game]
        fp = record.get("stock_full_folder", {}) if _mapping(record) else {}
        if fp.get("exe_name") != expected_name or fp.get("exe_size") != expected_size or fp.get("exe_sha256") != expected_sha:
            errors.append(f"{game}: exact stock executable fingerprint missing")
        if fp.get("full_folder_sha256") is not None or fp.get("file_count") is not None or fp.get("verified") is not False:
            errors.append(f"{game}: full-folder evidence must remain empty/pending")
        wrappers = record.get("static_wrapper_candidates") if _mapping(record) else None
        if wrappers != STATIC_WRAPPERS[game]:
            errors.append(f"{game}: static wrapper candidate hashes differ")
        routes = record.get("routes") if _mapping(record) else None
        if not isinstance(routes, list) or [item.get("id") for item in routes if _mapping(item)] != list(ROUTES):
            errors.append(f"{game}: exact modal route inventory required")
            routes = []
        for route in routes:
            if not _mapping(route):
                continue
            if route.get("status") != "pending" or route.get("receipts") != [] or route.get("ranges") != []:
                errors.append(f"{game}/{route.get('id')}: evidence must be empty/pending")
            requirements = route.get("requirements", {})
            required = {
                "sdl_window_not_hwnd", "same_process_hwnd_captured_before_modal", "same_hwnd_reused_for_dialogbox_messagebox",
                "monitor_work_area_centering_clamping", "sdl_get_window_flags_exact_abi_mask", "leave_enter_exact_callee_abi_state_byte",
                "fresh_singleton_outer_engine_window_reacquisition", "original_target_return_preserved", "one_guarded_restore_after_successful_leave",
                "destructor_tls_cleanup", "composition_ranges_proved",
            }
            if not _mapping(requirements) or set(requirements) != required or any(value is not False for value in requirements.values()):
                errors.append(f"{game}/{route.get('id')}: exact false requirement set required")
            scenarios = route.get("required_receipt_scenarios")
            if scenarios != {"windowed": list(SCENARIOS), "fullscreen": list(SCENARIOS)}:
                errors.append(f"{game}/{route.get('id')}: complete windowed/fullscreen scenario matrix required")
        if record.get("evidence_receipts") != [] or record.get("gap_status") != "STOP":
            errors.append(f"{game}: receipts must be empty and status STOP")
    regions = data.get("composition_regions")
    if regions != []:
        errors.append("composition regions must remain empty until exact evidence exists")
    schema_valid = not errors
    return Result(schema_valid, False, False, tuple(errors))

def validate_contract_file(path: Path) -> Result:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return Result(False, False, False, (f"contract unreadable: {exc}",))
    if not _mapping(value):
        return Result(False, False, False, ("contract root must be an object",))
    return validate_contract(value)
