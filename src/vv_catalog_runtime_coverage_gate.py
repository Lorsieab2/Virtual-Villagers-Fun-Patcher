"""Fail-closed validator for the disabled VV1/VV2 catalog runtime gate."""
from __future__ import annotations

import json
from pathlib import Path

EXPECTED_IDS = {
    "vv1_school_lessons_grant_skill", "vv1_continue_research_at_max_technologies",
    "vv1_f6_clothing_change_cheat", "vv1_magic_fruit_alters_mortality",
    "vv1_builder_action_fixes", "vv1_full_mastery_all_stage_a_candidate",
    "vv1_write_village_statistics", "vv2_easier_healing_mastery",
    "vv2_teaching_children_grants_skill", "vv2_hospital_recovery_heals",
    "vv2_birth_control", "vv2_gong_of_wonder_coconuts_fix",
    "vv2_full_mastery_all_stage_a_candidate", "vv2_write_village_statistics",
}
DIMENSIONS = {
    "display_modes": {"windowed", "fullscreen"},
    "save_states": {"new_game", "existing_save", "save_reload", "offline_catchup"},
    "outcomes": {"success", "no_op", "failure"},
    "installation": {"standalone", "uninstall"},
    "composition": {"supported_mode", "select_all", "coinstalled_catalog_patch"},
}

class EvidenceError(ValueError):
    pass

def validate(data: dict) -> None:
    false_fields = ("enabled", "catalog_enabled", "publication_allowed", "runtime_ready", "player_verified", "native_output")
    if data.get("status") != "STOP" or data.get("catalog_hidden") is not True or any(data.get(k) is not False for k in false_fields):
        raise EvidenceError("gate must remain disabled, hidden, unpublished, and STOP")
    if data.get("source_binding", {}).get("catalog_commit") != "e43464eb21667aba619d63272a808b0540ccf015":
        raise EvidenceError("catalog snapshot is not bound to exact C348")
    for game in ("vv1", "vv2"):
        item = data.get("authenticated_inputs", {}).get(game, {})
        if item.get("complete_folder_inventory") is not None or item.get("stock_executable_sha256") is not None or item.get("required_dlls") != []:
            raise EvidenceError("tracked gate must not contain unauthenticated or synthetic folder evidence")
    rows = data.get("catalog_snapshot", [])
    ids = [row.get("patch_id") for row in rows]
    if len(ids) != len(set(ids)) or set(ids) != EXPECTED_IDS:
        raise EvidenceError("catalog snapshot must contain each exact C348 VV1/VV2 patch once")
    modes = data.get("public_modes", [])
    if set(modes) != {"collection_progression", "immediate_fixed", "experimental_expanded_256", "experimental_expanded_256_progression"}:
        raise EvidenceError("the four public output modes must be pinned")
    if set(data.get("stock_only_patch_ids", [])) != {"vv1_full_mastery_all_stage_a_candidate", "vv2_full_mastery_all_stage_a_candidate"}:
        raise EvidenceError("exact stock-only Full Mastery exclusions must be pinned")
    scenarios = data.get("patch_specific_scenarios", {})
    if set(scenarios) != EXPECTED_IDS or any(not isinstance(v, list) or not v for v in scenarios.values()):
        raise EvidenceError("every catalog patch requires a nonempty exact scenario set")
    dimensions = data.get("required_dimensions", {})
    for key, values in DIMENSIONS.items():
        if set(dimensions.get(key, [])) != values:
            raise EvidenceError(f"missing or altered runtime dimension: {key}")
    receipt = data.get("receipt_contract", {})
    if receipt.get("provenance") != "authenticated_player_runtime_capture" or receipt.get("synthetic") is not False or receipt.get("manual_or_reconstructed") is not False:
        raise EvidenceError("synthetic, manual, or unauthenticated receipts are forbidden")
    if receipt.get("receipts") != []:
        raise EvidenceError("tracked disabled gate must contain no player receipts")
    if len(receipt.get("required_assertions", [])) != 9:
        raise EvidenceError("complete crash/save/uninstall/composition assertions are required")

def validate_file(path: str | Path) -> None:
    validate(json.loads(Path(path).read_text(encoding="utf-8")))
