"""Disabled evidence gates for absent VV2-VV5 native features.

The contracts validated here are evidence metadata only.  They cannot emit a
patch, publish a catalog feature, launch a game, or access a save.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Mapping


GAME_IDS = ("vv3", "vv4", "vv5")
COLLECTION_GAME_IDS = ("vv2", "vv3", "vv4", "vv5")
HASH_RE = re.compile(r"^[0-9A-Fa-f]{64}$")

EXPECTED_STOCK: dict[str, dict[str, Any]] = {
    "vv2": {
        "exe_name": "Virtual Villagers - The Lost Children.exe",
        "size": 724992,
        "imagebase": 0x400000,
        "sha256": "46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677",
    },
    "vv3": {
        "exe_name": "Virtual Villagers - The Secret City.exe",
        "size": 831488,
        "imagebase": 0x400000,
        "sha256": "8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503",
    },
    "vv4": {
        "exe_name": "Virtual Villagers - The Tree of Life.exe",
        "size": 929792,
        "imagebase": 0x400000,
        "sha256": "6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220",
    },
    "vv5": {
        "exe_name": "Virtual Villagers - New Believers.exe",
        "size": 991232,
        "imagebase": 0x400000,
        "sha256": "92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D",
    },
}

COLLECTIONS_REQUIREMENTS = (
    "stock_fingerprint",
    "collection_table_geometry",
    "missing_entry_predicate",
    "native_add_complete_writer",
    "completion_effects_separation",
    "duplicate_reward_trophy_stat_notification",
    "confirmation_reacquire_charge",
    "save_reload_catchup_idempotence",
    "hook_cave_composition",
    "runtime_player_evidence",
)

RESET_COLLECTIONS_REQUIREMENTS = (
    "stock_fingerprint",
    "collection_table_geometry",
    "present_entry_predicate",
    "native_reset_writer",
    "reset_effects_separation",
    "duplicate_reset_reward_goal_notification",
    "confirmation_reacquire_charge",
    "save_reload_catchup_idempotence",
    "hook_cave_composition",
    "runtime_player_evidence",
)

LABOR_REQUIREMENTS = (
    "stock_fingerprint",
    "villager_record_geometry",
    "sex_field_encoding",
    "eligibility_predicate",
    "job_table_policy",
    "deterministic_physical_cycle",
    "native_job_setter_effects",
    "repeat_transaction_rollback",
    "save_reload_catchup_idempotence",
    "hook_cave_composition",
    "runtime_player_evidence",
)

FEATURE_SPECS: dict[str, dict[str, Any]] = {
    "complete_all_collections": {
        "schema": "vvfp.complete_all_collections_evidence",
        "requirements": COLLECTIONS_REQUIREMENTS,
        "composition": ("statistics_export", "origins", "expanded_256"),
        "game_ids": COLLECTION_GAME_IDS,
        "required_root": ("label", "price_tech_points", "screen", "button_policy", "repeatability"),
        "metadata": {
            "label": "Complete All Collectibles",
            "price_tech_points": 1_000_000,
            "screen": "village_wide",
            "button_policy": "buy_only",
            "repeatability": "repeatable",
        },
        "forbidden": {
            "collection_population_bonus_only": ("all", "semantic_role", None),
            "award_or_trophy_dispatcher_only": ("all", "semantic_role", None),
        },
    },
    "reset_all_collections": {
        "schema": "vvfp.reset_all_collections_evidence",
        "requirements": RESET_COLLECTIONS_REQUIREMENTS,
        "composition": ("statistics_export", "origins", "expanded_256"),
        "game_ids": COLLECTION_GAME_IDS,
        "required_root": ("label", "price_tech_points", "screen", "button_policy", "repeatability"),
        "metadata": {
            "label": "Reset Collectibles",
            "price_tech_points": 1_000_000,
            "screen": "village_wide",
            "button_policy": "buy_only",
            "repeatability": "repeatable",
        },
        "forbidden": {
            "collection_population_bonus_only": ("all", "semantic_role", None),
            "award_or_trophy_dispatcher_only": ("all", "semantic_role", None),
        },
    },
    "equal_division": {
        "schema": "vvfp.equal_division_evidence",
        "requirements": LABOR_REQUIREMENTS,
        "composition": ("full_mastery", "grant_running", "full_heal"),
        "game_ids": GAME_IDS,
        "forbidden": {
            "vv5_nursery_divisor_parity": ("vv5", "code_address", 0x425FDF),
            "vv5_unproved_heathen_active_byte": ("vv5", "field_offset", 0x1CE1),
        },
    },
}

EXPECTED_JOB_ORDER: dict[str, tuple[tuple[int, str], ...]] = {
    "vv3": (
        (0, "Farming"),
        (1, "Building"),
        (2, "Research"),
        (3, "Healing"),
        (4, "Parenting"),
    ),
    "vv4": (
        (0, "Farming"),
        (1, "Parenting"),
        (2, "Healing"),
        (3, "Research"),
        (4, "Building"),
    ),
    "vv5": (
        (0, "Healing"),
        (1, "Parenting"),
        (2, "Farming"),
        (3, "Research"),
        (4, "Building"),
        (5, "Devotion"),
    ),
}


PROOF_FIELDS: dict[str, tuple[str, ...]] = {
    "stock_fingerprint": (
        "exe_size", "exe_sha256", "full_folder_sha256",
        "full_folder_manifest_sha256", "full_folder_file_count",
        "full_folder_complete",
    ),
    "collection_table_geometry": (
        "table_address", "entry_count", "entry_stride", "entry_ids_in_order",
        "table_bounds_verified",
    ),
    "missing_entry_predicate": (
        "routine_va", "call_convention", "return_abi", "missing_semantics",
        "present_semantics", "all_entries_tested",
    ),
    "present_entry_predicate": (
        "routine_va", "call_convention", "return_abi", "present_semantics",
        "absent_semantics", "all_entries_tested",
    ),
    "native_add_complete_writer": (
        "routine_va", "call_convention", "return_abi", "writer_kind",
        "native_postreadback",
    ),
    "native_reset_writer": (
        "routine_va", "call_convention", "return_abi", "writer_kind",
        "native_postreadback",
    ),
    "completion_effects_separation": (
        "completion_route_proved", "population_bonus_not_completion",
        "award_dispatcher_not_completion", "rewards_triggered", "goals_triggered",
        "per_game_effects_enumerated",
    ),
    "reset_effects_separation": (
        "reset_route_proved", "population_bonus_not_reset",
        "award_dispatcher_not_reset", "per_game_effects_enumerated",
    ),
    "duplicate_reward_trophy_stat_notification": (
        "duplicate_noop", "reward_once", "goal_once", "trophy_once", "stat_once",
        "notification_once", "dispatch_order",
    ),
    "duplicate_reset_reward_goal_notification": (
        "duplicate_noop", "reward_reset_once", "goal_reset_once",
        "trophy_reset_once", "stat_once", "notification_once", "dispatch_order",
    ),
    "confirmation_reacquire_charge": (
        "dry_run", "confirmation_idok", "identity_reacquire", "postverify",
        "charge_semantics", "charge_once_or_zero", "no_charge_on_noop",
        "no_charge_on_failure",
    ),
    "villager_record_geometry": (
        "record_base", "record_count", "record_stride", "physical_order",
        "resolver_abi",
    ),
    "sex_field_encoding": (
        "field_offset", "male_value", "female_value", "encoding_complete",
        "unknown_sex_policy",
    ),
    "eligibility_predicate": (
        "active_field", "living_field", "status_field", "current_faction_field",
        "predicate_order", "vv5_faction_first", "unproved_1ce1_excluded",
        "vv3_tribal_chief_policy",
    ),
    "job_table_policy": (
        "assignment_target", "jobs", "parenting_policy", "devotion_policy",
        "complete_order_verified",
    ),
    "deterministic_physical_cycle": (
        "physical_slot_order", "cycle_order", "remainder_policy", "tie_policy",
        "unknown_sex_policy", "deterministic", "repeat_noop",
    ),
    "native_job_setter_effects": (
        "setter_va", "setter_abi", "readback_va", "readback_abi",
        "action_queue_effect", "notification_effect", "stat_effect", "save_effect",
        "postverify",
    ),
    "repeat_transaction_rollback": (
        "dry_run", "identity_reacquire", "repeat_noop", "write_order",
        "rollback_truth", "partial_write_disclosure", "funds_semantics",
    ),
    "save_reload_catchup_idempotence": (
        "save_roundtrip", "reload_roundtrip", "offline_catchup", "idempotent",
        "failed_load_nonmutation",
    ),
    "hook_cave_composition": (
        "hook_guard_verified", "wrong_hook_rejected", "regions_nonoverlap",
        "stock_mode_noop", "composition_checked", "checked_features",
    ),
    "runtime_player_evidence": (
        "runtime_receipt_sha256", "player_receipt_sha256", "runtime_confirmed",
        "player_confirmed",
    ),
}

TRUE_PROOF_FIELDS = {
    "full_folder_complete", "table_bounds_verified", "all_entries_tested",
    "native_postreadback", "completion_route_proved",
    "population_bonus_not_completion", "award_dispatcher_not_completion",
    "rewards_triggered", "goals_triggered", "per_game_effects_enumerated",
    "duplicate_noop", "reward_once", "goal_once", "trophy_once", "stat_once",
    "notification_once", "dry_run",
    "reset_route_proved", "population_bonus_not_reset", "award_dispatcher_not_reset",
    "reward_reset_once", "goal_reset_once", "trophy_reset_once",
    "confirmation_idok", "identity_reacquire", "postverify",
    "charge_once_or_zero", "no_charge_on_noop", "no_charge_on_failure",
    "encoding_complete", "unproved_1ce1_excluded",
    "complete_order_verified", "deterministic", "repeat_noop",
    "save_roundtrip", "reload_roundtrip", "offline_catchup", "idempotent",
    "failed_load_nonmutation", "hook_guard_verified", "wrong_hook_rejected",
    "regions_nonoverlap", "stock_mode_noop", "composition_checked",
    "runtime_confirmed", "player_confirmed",
}


@dataclass(frozen=True)
class ValidationResult:
    schema_valid: bool
    evidence_complete: bool
    publication_allowed: bool
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_valid": self.schema_valid,
            "evidence_complete": self.evidence_complete,
            "publication_allowed": self.publication_allowed,
            "valid": self.publication_allowed,
            "error_count": len(self.errors),
            "errors": list(self.errors),
        }


def _mapping(value: Any) -> bool:
    return isinstance(value, Mapping)


def _hash(value: Any) -> bool:
    return isinstance(value, str) and HASH_RE.fullmatch(value) is not None


def _address(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError:
            return None
    return None


def _proof_addresses(value: Any, key: str = "") -> list[tuple[str, int]]:
    found: list[tuple[str, int]] = []
    if _mapping(value):
        for child_key, child in value.items():
            found.extend(_proof_addresses(child, str(child_key)))
    elif isinstance(value, list):
        for child in value:
            found.extend(_proof_addresses(child, key))
    elif any(token in key.lower() for token in ("address", "offset", "field", "routine", "setter", "readback", "base", "start", "va")):
        parsed = _address(value)
        if parsed is not None:
            found.append((key, parsed))
    return found


def _proof_strings(value: Any) -> set[str]:
    found: set[str] = set()
    if _mapping(value):
        for child in value.values():
            found.update(_proof_strings(child))
    elif isinstance(value, list):
        for child in value:
            found.update(_proof_strings(child))
    elif isinstance(value, str):
        found.add(value)
    return found


def _shape_errors(data: Any, feature: str) -> list[str]:
    if feature not in FEATURE_SPECS:
        return [f"unknown feature {feature}"]
    if not _mapping(data):
        return ["root must be an object"]
    required = {
        "schema", "schema_version", "feature", "enabled", "publication",
        "games", "forbidden_routes", "composition_features",
    }
    required.update(FEATURE_SPECS[feature].get("required_root", ()))
    errors = [f"root missing {key}" for key in sorted(required - set(data))]
    errors.extend(f"root has unexpected key {key}" for key in sorted(set(data) - required))
    if errors:
        return errors
    spec = FEATURE_SPECS[feature]
    if data.get("schema") != spec["schema"]:
        errors.append("schema identifier is wrong")
    if data.get("schema_version") != 1:
        errors.append("schema version is wrong")
    if data.get("feature") != feature:
        errors.append("feature identifier is wrong")
    if data.get("enabled") is not False:
        errors.append("evidence contract must remain disabled")
    for key, expected in FEATURE_SPECS[feature].get("metadata", {}).items():
        if data.get(key) != expected:
            errors.append(f"{feature} metadata {key} is not exact")
    publication = data.get("publication")
    if not _mapping(publication) or publication.get("status") != "disabled":
        errors.append("publication must remain disabled")
    elif not isinstance(publication.get("reason"), str) or not publication["reason"].strip():
        errors.append("publication disabled reason is required")
    games = data.get("games")
    expected_games = FEATURE_SPECS[feature].get("game_ids", GAME_IDS)
    if not _mapping(games) or set(games) != set(expected_games):
        errors.append(f"games must contain exactly {', '.join(expected_games)}")
    if not isinstance(data.get("forbidden_routes"), list):
        errors.append("forbidden_routes must be an array")
    if tuple(data.get("composition_features", ())) != spec["composition"]:
        errors.append("composition feature set is not exact")
    return errors


def _validate_forbidden_routes(data: Mapping[str, Any], feature: str) -> list[str]:
    expected = FEATURE_SPECS[feature]["forbidden"]
    actual: dict[str, tuple[str, str, int | None]] = {}
    errors: list[str] = []
    for item in data["forbidden_routes"]:
        if not _mapping(item):
            errors.append("forbidden route must be an object")
            continue
        route_id = item.get("id")
        if not isinstance(route_id, str):
            errors.append("forbidden route id is missing")
            continue
        if route_id in actual:
            errors.append(f"duplicate forbidden route {route_id}")
        actual[route_id] = (
            str(item.get("game_id")),
            str(item.get("kind")),
            _address(item.get("value")),
        )
    if set(actual) != set(expected):
        errors.append("forbidden route set is incomplete or has extras")
    for route_id, expected_value in expected.items():
        if route_id in actual and actual[route_id] != expected_value:
            errors.append(f"forbidden route {route_id} is not exact")
    return errors


def _validate_stock(game: str, stock: Any) -> list[str]:
    if not _mapping(stock):
        return [f"{game}.stock must be an object"]
    errors: list[str] = []
    expected = EXPECTED_STOCK[game]
    for key in ("exe_name", "size", "imagebase", "sha256"):
        if stock.get(key) != expected[key]:
            errors.append(f"{game} stock {key} is not exact")
    folder = stock.get("full_folder")
    if not _mapping(folder):
        return errors + [f"{game} full-folder fingerprint is missing"]
    if folder.get("status") != "verified":
        errors.append(f"{game} full-folder fingerprint is not verified")
    if not _hash(folder.get("sha256")):
        errors.append(f"{game} full-folder SHA-256 is missing or malformed")
    if not _hash(folder.get("manifest_sha256")):
        errors.append(f"{game} full-folder manifest SHA-256 is missing or malformed")
    if not isinstance(folder.get("file_count"), int) or folder.get("file_count", 0) < 1:
        errors.append(f"{game} full-folder file count is missing")
    return errors


def _validate_policy(game: str, policy: Any, feature: str) -> list[str]:
    if not _mapping(policy):
        return [f"{game}.policy must be an object"]
    errors: list[str] = []
    if feature in ("complete_all_collections", "reset_all_collections"):
        expected = {
            "population_bonus_is_completion": False,
            "award_dispatcher_is_completion": False,
        }
        if feature == "reset_all_collections":
            expected = {
                "population_bonus_is_reset": False,
                "award_dispatcher_is_reset": False,
            }
        expected["expanded_256_policy"] = (
            "existing_256_no_relocation" if game == "vv2"
            else "expanded_256_relocation_evidence_required"
        )
        if dict(policy) != expected:
            errors.append(f"{game} {feature} separation policy is not exact")
    else:
        jobs = policy.get("reviewed_preference_order")
        expected_jobs = [
            {"id": job_id, "name": name}
            for job_id, name in EXPECTED_JOB_ORDER[game]
        ]
        if jobs != expected_jobs:
            errors.append(f"{game} reviewed preference job order is not exact")
        if policy.get("assignment_target") != "preference_selector":
            errors.append(f"{game} Equal Division assignment target is not exact")
        if policy.get("parenting_policy") != "evidence_required":
            errors.append(f"{game} Parenting policy must remain evidence-required")
        devotion = "evidence_required" if game == "vv5" else "not_present_do_not_synthesize"
        if policy.get("devotion_policy") != devotion:
            errors.append(f"{game} Devotion policy is not exact")
        if policy.get("nursery_divisor_related") is not False:
            errors.append(f"{game} nursery divisor must remain unrelated")
    return errors


def _validate_proof(game: str, requirement: str, proof: Any, feature: str) -> list[str]:
    if not _mapping(proof):
        return [f"{game}.{requirement} proof must be an object"]
    fields = PROOF_FIELDS.get(requirement)
    if fields is None:
        return [f"{game} unknown proof requirement {requirement}"]
    errors = [f"{game}.{requirement} missing proof field {key}" for key in fields if key not in proof]
    if errors:
        return errors
    for key in fields:
        if key in TRUE_PROOF_FIELDS and proof[key] is not True:
            errors.append(f"{game}.{requirement} does not prove {key}")
    if requirement == "stock_fingerprint":
        if proof["exe_size"] != EXPECTED_STOCK[game]["size"]:
            errors.append(f"{game} stock proof size is wrong")
        if proof["exe_sha256"] != EXPECTED_STOCK[game]["sha256"]:
            errors.append(f"{game} stock proof SHA-256 is wrong")
        for key in ("full_folder_sha256", "full_folder_manifest_sha256"):
            if not _hash(proof[key]):
                errors.append(f"{game} stock proof {key} is malformed")
        if not isinstance(proof["full_folder_file_count"], int) or proof["full_folder_file_count"] < 1:
            errors.append(f"{game} stock proof file count is invalid")
    elif requirement == "collection_table_geometry":
        if not isinstance(proof["entry_count"], int) or proof["entry_count"] < 1:
            errors.append(f"{game} collection entry count is invalid")
        if not isinstance(proof["entry_ids_in_order"], list) or len(proof["entry_ids_in_order"]) != proof["entry_count"]:
            errors.append(f"{game} collection table count/order is inconsistent")
    elif requirement == "present_entry_predicate":
        if proof["present_semantics"] == proof["absent_semantics"]:
            errors.append(f"{game} present/absent collection semantics are not distinct")
    elif requirement == "reset_effects_separation":
        for key in ("reset_route_proved", "population_bonus_not_reset", "award_dispatcher_not_reset", "per_game_effects_enumerated"):
            if proof[key] is not True:
                errors.append(f"{game} reset effects proof does not prove {key}")
    elif requirement == "duplicate_reset_reward_goal_notification":
        for key in ("duplicate_noop", "reward_reset_once", "goal_reset_once", "trophy_reset_once", "stat_once", "notification_once"):
            if proof[key] is not True:
                errors.append(f"{game} reset effect proof does not prove {key}")
    elif requirement == "confirmation_reacquire_charge":
        if proof["charge_semantics"] not in ("one_charge", "zero_cost"):
            errors.append(f"{game} collections charge semantics must be one_charge or zero_cost")
    elif requirement == "sex_field_encoding":
        if proof["male_value"] == proof["female_value"]:
            errors.append(f"{game} sex encoding values are not distinct")
        if not isinstance(proof["unknown_sex_policy"], str) or not proof["unknown_sex_policy"].strip():
            errors.append(f"{game} unknown-sex policy is missing")
    elif requirement == "eligibility_predicate":
        if proof["unproved_1ce1_excluded"] is not True:
            errors.append(f"{game} unproved +0x1CE1 gate is not excluded")
        if game == "vv5":
            order = proof["predicate_order"]
            if not isinstance(order, list) or not order or order[0] != "current_faction":
                errors.append("vv5 eligibility must evaluate current faction first")
            if proof["vv5_faction_first"] is not True:
                errors.append("vv5 faction-first proof is missing")
        elif proof["vv5_faction_first"] is not False:
            errors.append(f"{game} must not claim the VV5 faction-first rule")
        chief = proof["vv3_tribal_chief_policy"]
        if game == "vv3" and chief not in ("exclude", "include_with_native_proof"):
            errors.append("vv3 Tribal Chief policy is unresolved")
        if game != "vv3" and chief != "not_applicable":
            errors.append(f"{game} Tribal Chief policy must be not_applicable")
    elif requirement == "job_table_policy":
        expected_jobs = [{"id": job_id, "name": name} for job_id, name in EXPECTED_JOB_ORDER[game]]
        if proof["jobs"] != expected_jobs:
            errors.append(f"{game} complete job ID/order table is wrong")
        if proof["assignment_target"] != "preference_selector":
            errors.append(f"{game} job assignment target is wrong")
        if not isinstance(proof["parenting_policy"], str) or not proof["parenting_policy"].strip():
            errors.append(f"{game} Parenting policy is missing")
        if not isinstance(proof["devotion_policy"], str) or not proof["devotion_policy"].strip():
            errors.append(f"{game} Devotion policy is missing")
    elif requirement == "hook_cave_composition":
        if tuple(proof["checked_features"]) != FEATURE_SPECS[feature]["composition"]:
            errors.append(f"{game} hook/cave composition feature set is wrong")
    elif requirement == "runtime_player_evidence":
        for key in ("runtime_receipt_sha256", "player_receipt_sha256"):
            if not _hash(proof[key]):
                errors.append(f"{game}.{requirement} {key} is malformed")
    return errors


def _validate_game(game: str, record: Any, feature: str) -> list[str]:
    if not _mapping(record):
        return [f"{game} record must be an object"]
    required_keys = {"stock", "policy", "requirements", "receipts"}
    errors = [f"{game} missing {key}" for key in sorted(required_keys - set(record))]
    errors.extend(f"{game} has unexpected key {key}" for key in sorted(set(record) - required_keys))
    if errors:
        return errors
    errors.extend(_validate_stock(game, record["stock"]))
    errors.extend(_validate_policy(game, record["policy"], feature))
    requirements = record["requirements"]
    receipts = record["receipts"]
    if not isinstance(requirements, list) or not isinstance(receipts, list):
        return errors + [f"{game} requirements and receipts must be arrays"]
    expected_requirements = FEATURE_SPECS[feature]["requirements"]
    requirement_map: dict[str, Mapping[str, Any]] = {}
    for item in requirements:
        if not _mapping(item) or not isinstance(item.get("id"), str):
            errors.append(f"{game} requirement is malformed")
            continue
        requirement_id = item["id"]
        if requirement_id in requirement_map:
            errors.append(f"{game} duplicate requirement {requirement_id}")
        requirement_map[requirement_id] = item
    if set(requirement_map) != set(expected_requirements):
        errors.append(f"{game} requirement set is incomplete or has extras")

    receipt_map: dict[str, Mapping[str, Any]] = {}
    receipt_by_requirement: dict[str, list[Mapping[str, Any]]] = {}
    regions: list[tuple[int, int, str]] = []
    forbidden = FEATURE_SPECS[feature]["forbidden"]
    for receipt in receipts:
        if not _mapping(receipt) or not isinstance(receipt.get("id"), str):
            errors.append(f"{game} receipt is malformed")
            continue
        receipt_id = receipt["id"]
        requirement = receipt.get("requirement")
        if receipt_id in receipt_map:
            errors.append(f"{game} duplicate evidence receipt {receipt_id}")
        receipt_map[receipt_id] = receipt
        if requirement not in expected_requirements:
            errors.append(f"{game} receipt {receipt_id} has unknown requirement")
        else:
            receipt_by_requirement.setdefault(requirement, []).append(receipt)
        if receipt.get("status") != "verified":
            errors.append(f"{game} receipt {receipt_id} is not verified")
        if receipt.get("synthetic") is not False:
            errors.append(f"{game} receipt {receipt_id} is synthetic")
        if receipt.get("stale") is not False:
            errors.append(f"{game} receipt {receipt_id} is stale")
        if receipt.get("source_sha256") != EXPECTED_STOCK[game]["sha256"]:
            errors.append(f"{game} receipt {receipt_id} has wrong source fingerprint")
        errors.extend(_validate_proof(game, str(requirement), receipt.get("proof"), feature))
        proof_strings = _proof_strings(receipt.get("proof", {}))
        for route_id, (route_game, kind, _route_value) in forbidden.items():
            if kind == "semantic_role" and route_game in ("all", game) and route_id in proof_strings:
                errors.append(f"{game} receipt {receipt_id} relies on forbidden {route_id}")
        for key, value in _proof_addresses(receipt.get("proof", {})):
            for route_id, (route_game, _kind, route_value) in forbidden.items():
                if route_value is not None and route_game in ("all", game) and value == route_value:
                    errors.append(f"{game} receipt {receipt_id} reuses forbidden {route_id} ({key})")
        receipt_regions = receipt.get("regions")
        if not isinstance(receipt_regions, list):
            errors.append(f"{game} receipt {receipt_id} regions must be an array")
            continue
        for region in receipt_regions:
            if not _mapping(region):
                errors.append(f"{game} receipt {receipt_id} region is malformed")
                continue
            start = _address(region.get("start"))
            length = region.get("length")
            if start is None or not isinstance(length, int) or length <= 0:
                errors.append(f"{game} receipt {receipt_id} region is invalid")
                continue
            end = start + length
            for route_id, (route_game, kind, route_value) in forbidden.items():
                if kind == "code_address" and route_game in ("all", game) and route_value is not None and start <= route_value < end:
                    errors.append(f"{game} receipt {receipt_id} overlaps forbidden {route_id}")
            regions.append((start, end, receipt_id))
    for index, (left_start, left_end, left_id) in enumerate(regions):
        for right_start, right_end, right_id in regions[index + 1:]:
            if left_start < right_end and right_start < left_end:
                errors.append(f"{game} evidence regions overlap: {left_id} and {right_id}")

    for requirement in expected_requirements:
        item = requirement_map.get(requirement)
        if item is None:
            continue
        evidence_ids = item.get("evidence_ids")
        if not isinstance(evidence_ids, list):
            errors.append(f"{game}.{requirement} evidence_ids must be an array")
            continue
        if len(evidence_ids) != len({repr(value) for value in evidence_ids}):
            errors.append(f"{game}.{requirement} has duplicate evidence ids")
        for evidence_id in evidence_ids:
            if evidence_id not in receipt_map:
                errors.append(f"{game}.{requirement} references missing evidence {evidence_id}")
        if item.get("status") != "verified":
            errors.append(f"{game}.{requirement} is not verified")
        matched = receipt_by_requirement.get(requirement, [])
        if item.get("status") == "verified" and (len(matched) != 1 or len(evidence_ids) != 1):
            errors.append(f"{game}.{requirement} must have exactly one canonical receipt")
        if matched and item.get("status") == "verified" and matched[0].get("id") not in evidence_ids:
            errors.append(f"{game}.{requirement} does not reference its canonical receipt")
    return errors


def validate_contract(data: Mapping[str, Any], feature: str) -> ValidationResult:
    shape_errors = _shape_errors(data, feature)
    if shape_errors:
        return ValidationResult(False, False, False, tuple(shape_errors))
    errors = _validate_forbidden_routes(data, feature)
    for game in FEATURE_SPECS[feature].get("game_ids", GAME_IDS):
        errors.extend(_validate_game(game, data["games"][game], feature))
    evidence_complete = not errors
    return ValidationResult(True, evidence_complete, False, tuple(errors))


def validate_contract_file(path: Path, feature: str) -> ValidationResult:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return ValidationResult(False, False, False, (str(exc),))
    return validate_contract(data, feature)


def publication_ready(_feature: str) -> bool:
    return False
