"""Fail-closed evidence gate for future VV3/VV4/VV5 statistics mutation.

This module validates evidence metadata only.  It never reads or patches a
game executable, never enables a catalog feature, and never treats the
existing text exporter as a native statistics writer.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Mapping


CONTRACT_SCHEMA = "vvfp.native_statistics_mutation_evidence"
CONTRACT_VERSION = 1
GAME_IDS = ("vv3", "vv4", "vv5")
HASH_RE = re.compile(r"^[0-9A-Fa-f]{64}$")

EXPECTED_STOCK: dict[str, dict[str, Any]] = {
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

REQUIRED_REQUIREMENTS = (
    "stock_fingerprint",
    "earliest_successful_skeleton_pickup_abi",
    "buried_exactly_once",
    "oldest_lifetime_max_updater",
    "memorial_storage_ownership",
    "atomic_save_load_serializer",
    "reload_offline_catchup_idempotence",
    "failed_load_nonmutation",
    "expanded_256_compatibility",
    "hook_cave_composition",
    "runtime_player_evidence",
)

WITHDRAWN_HOOKS: dict[str, tuple[int, str]] = {
    "vv3": (0x5F45B, "881EE9B8010000"),
    "vv4": (0x664DC, "885EFD385EFD"),
    "vv5": (0x6FF12, "889ED41C0000"),
}

# These are runtime addresses from the reviewed inherited statistics reserve.
# The VV4 value is also the exact serialized global reserve address.
PROTECTED_FIELDS: dict[str, dict[int, str]] = {
    "vv3": {0x5824D0: "Origins"},
    "vv4": {0x4D6E10: "Origins"},
    "vv5": {
        0x51D388: "Origins",
        0x51D38C: "Heathens Converted",
    },
}


@dataclass(frozen=True)
class ValidationResult:
    """Separate structural validity, evidence completeness, and publication."""

    schema_valid: bool
    evidence_complete: bool
    publication_allowed: bool
    errors: tuple[str, ...]

    @property
    def valid(self) -> bool:
        """Compatibility alias: a disabled or incomplete gate is not valid-to-publish."""

        return self.publication_allowed

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_valid": self.schema_valid,
            "evidence_complete": self.evidence_complete,
            "publication_allowed": self.publication_allowed,
            "valid": self.valid,
            "error_count": len(self.errors),
            "errors": list(self.errors),
        }


def _is_mapping(value: Any) -> bool:
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


def _proof_values(value: Any, key: str = "") -> list[tuple[str, int]]:
    """Collect address-like proof values for protected/withdrawn collision checks."""

    found: list[tuple[str, int]] = []
    if isinstance(value, Mapping):
        for child_key, child_value in value.items():
            found.extend(_proof_values(child_value, str(child_key)))
    elif isinstance(value, list):
        for child_value in value:
            found.extend(_proof_values(child_value, key))
    elif any(token in key.lower() for token in ("address", "offset", "field", "routine", "hook", "cave", "start")):
        parsed = _address(value)
        if parsed is not None:
            found.append((key, parsed))
    return found


def _shape_errors(data: Any) -> list[str]:
    errors: list[str] = []
    if not _is_mapping(data):
        return ["root must be an object"]
    required = {
        "schema",
        "schema_version",
        "feature",
        "enabled",
        "publication",
        "games",
        "withdrawn_hooks",
        "protected_fields",
    }
    missing = sorted(required - set(data))
    extra = sorted(set(data) - required)
    errors.extend(f"root missing {key}" for key in missing)
    errors.extend(f"root has unexpected key {key}" for key in extra)
    if errors:
        return errors
    if data.get("schema") != CONTRACT_SCHEMA:
        errors.append("schema identifier is wrong")
    if data.get("schema_version") != CONTRACT_VERSION:
        errors.append("schema version is wrong")
    if data.get("feature") != "native_statistics_mutation":
        errors.append("feature identifier is wrong")
    if data.get("enabled") is not False:
        errors.append("native statistics mutation contract must remain disabled")
    publication = data.get("publication")
    if not _is_mapping(publication):
        errors.append("publication must be an object")
    else:
        if publication.get("status") != "disabled":
            errors.append("publication status must remain disabled")
        if not isinstance(publication.get("reason"), str) or not publication["reason"].strip():
            errors.append("publication disabled reason is required")
    games = data.get("games")
    if not _is_mapping(games):
        errors.append("games must be an object")
    elif set(games) != set(GAME_IDS):
        errors.append("games must contain exactly vv3, vv4, and vv5")
    for collection_name in ("withdrawn_hooks", "protected_fields"):
        if not isinstance(data.get(collection_name), list):
            errors.append(f"{collection_name} must be an array")
    return errors


def _validate_global_guards(data: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    withdrawn = data.get("withdrawn_hooks", [])
    seen_withdrawn: set[tuple[str, int]] = set()
    for item in withdrawn:
        if not _is_mapping(item):
            errors.append("withdrawn hook entry must be an object")
            continue
        game = item.get("game_id")
        offset = _address(item.get("offset"))
        guard = str(item.get("guard", "")).upper()
        expected = WITHDRAWN_HOOKS.get(game)
        if expected is None or offset is None:
            errors.append("withdrawn hook has an unknown game or offset")
            continue
        if (game, offset) in seen_withdrawn:
            errors.append(f"duplicate withdrawn hook {game}:{offset:#x}")
        seen_withdrawn.add((game, offset))
        if expected != (offset, guard):
            errors.append(f"withdrawn hook guard mismatch for {game}:{offset:#x}")
    if seen_withdrawn != {(game, offset) for game, (offset, _guard) in WITHDRAWN_HOOKS.items()}:
        errors.append("withdrawn delayed corpse-retirement hook set is incomplete")

    protected = data.get("protected_fields", [])
    seen_protected: set[tuple[str, int]] = set()
    expected_protected = {
        (game, address): owner
        for game, fields in PROTECTED_FIELDS.items()
        for address, owner in fields.items()
    }
    for item in protected:
        if not _is_mapping(item):
            errors.append("protected field entry must be an object")
            continue
        game = item.get("game_id")
        address = _address(item.get("address"))
        owner = item.get("owner")
        if address is None or (game, address) not in expected_protected:
            errors.append("protected field list contains an unknown address")
            continue
        if expected_protected[(game, address)] != owner:
            errors.append(f"protected field owner mismatch for {game}:{address:#x}")
        if (game, address) in seen_protected:
            errors.append(f"duplicate protected field {game}:{address:#x}")
        seen_protected.add((game, address))
    if seen_protected != set(expected_protected):
        errors.append("protected Origins/statistics field set is incomplete")
    return errors


def _validate_stock(game: str, stock: Any, errors: list[str]) -> None:
    expected = EXPECTED_STOCK[game]
    if not _is_mapping(stock):
        errors.append(f"{game}.stock must be an object")
        return
    for key in ("exe_name", "size", "imagebase", "sha256", "full_folder"):
        if key not in stock:
            errors.append(f"{game}.stock missing {key}")
    if stock.get("exe_name") != expected["exe_name"]:
        errors.append(f"{game} executable name is not exact")
    if stock.get("size") != expected["size"]:
        errors.append(f"{game} executable size is not exact")
    if stock.get("imagebase") != expected["imagebase"]:
        errors.append(f"{game} executable image base is not exact")
    if stock.get("sha256") != expected["sha256"]:
        errors.append(f"{game} executable SHA-256 is not exact")
    folder = stock.get("full_folder")
    if not _is_mapping(folder):
        errors.append(f"{game} full-folder fingerprint is missing")
        return
    if folder.get("status") != "verified":
        errors.append(f"{game} full-folder fingerprint is not verified")
    if not _hash(folder.get("sha256")):
        errors.append(f"{game} full-folder SHA-256 is missing or malformed")
    if not isinstance(folder.get("file_count"), int) or folder.get("file_count", 0) < 1:
        errors.append(f"{game} full-folder file count is missing")
    if not _hash(folder.get("manifest_sha256")):
        errors.append(f"{game} full-folder manifest SHA-256 is missing or malformed")


def _required_proof_errors(requirement: str, proof: Any, game: str) -> list[str]:
    if not _is_mapping(proof):
        return [f"{game}.{requirement} proof must be an object"]
    required: dict[str, tuple[str, ...]] = {
        "stock_fingerprint": (
            "exe_size", "exe_sha256", "full_folder_sha256",
            "full_folder_manifest_sha256", "full_folder_file_count",
            "full_folder_complete",
        ),
        "earliest_successful_skeleton_pickup_abi": (
            "routine_va", "call_convention", "return_abi", "success_boundary",
            "counter_field_offset", "exactly_once_guard",
            "not_withdrawn_delayed_retirement",
        ),
        "buried_exactly_once": (
            "success_boundary", "duplicate_semantics", "failed_pickup_nonmutation",
            "exactly_once", "counter_field_offset",
        ),
        "oldest_lifetime_max_updater": (
            "update_routine_va", "field_offset", "semantics", "native_update",
            "readback_postverify", "save_scoped",
        ),
        "memorial_storage_ownership": (
            "baseline_field_offset", "initialized_marker_offset", "dedicated",
            "owner", "atomic_pair", "overlap_regions", "not_origins_reserved",
        ),
        "atomic_save_load_serializer": (
            "load_routine_va", "save_routine_va", "atomic_pair",
            "baseline_and_marker_same_transaction", "field_roundtrip",
        ),
        "reload_offline_catchup_idempotence": (
            "reload_round_trip", "offline_catchup", "idempotent",
            "duplicate_migration_noop",
        ),
        "failed_load_nonmutation": (
            "unchanged_on_failed_load", "no_partial_marker", "no_partial_baseline",
        ),
        "expanded_256_compatibility": (
            "stock_import", "expanded_reload", "expanded_offline_catchup",
            "record_bounds",
        ),
        "hook_cave_composition": (
            "hook_guard_verified", "hook_cave_no_overlap", "wrong_hook_rejected",
            "stock_mode_noop", "composition_checked", "ownership",
        ),
        "runtime_player_evidence": (
            "runtime_receipt_sha256", "player_receipt_sha256",
            "runtime_confirmed", "player_confirmed",
        ),
    }
    if requirement not in required:
        return [f"{game} receipt has unknown requirement {requirement}"]
    errors: list[str] = []
    for key in required[requirement]:
        if key not in proof:
            errors.append(f"{game}.{requirement} missing proof field {key}")
    if errors:
        return errors
    if requirement == "stock_fingerprint":
        if not _hash(proof["exe_sha256"]):
            errors.append(f"{game}.stock_fingerprint exe SHA-256 is malformed")
        if not _hash(proof["full_folder_sha256"]) or not _hash(proof["full_folder_manifest_sha256"]):
            errors.append(f"{game}.stock_fingerprint full-folder hashes are malformed")
        if not isinstance(proof["full_folder_file_count"], int) or proof["full_folder_file_count"] < 1:
            errors.append(f"{game}.stock_fingerprint file count is invalid")
        if proof["full_folder_complete"] is not True:
            errors.append(f"{game}.stock_fingerprint full folder is not complete")
    elif requirement == "earliest_successful_skeleton_pickup_abi":
        for key in ("success_boundary", "exactly_once_guard", "not_withdrawn_delayed_retirement"):
            if proof[key] is not True:
                errors.append(f"{game}.{requirement} does not prove {key}")
        for key in ("call_convention", "return_abi"):
            if not isinstance(proof[key], str) or not proof[key].strip():
                errors.append(f"{game}.{requirement} has no exact {key}")
    elif requirement == "buried_exactly_once":
        for key in ("success_boundary", "failed_pickup_nonmutation", "exactly_once"):
            if proof[key] is not True:
                errors.append(f"{game}.{requirement} does not prove {key}")
        if not isinstance(proof["duplicate_semantics"], str) or not proof["duplicate_semantics"].strip():
            errors.append(f"{game}.{requirement} duplicate semantics are missing")
    elif requirement == "oldest_lifetime_max_updater":
        if proof["semantics"] != "persisted_lifetime_maximum":
            errors.append(f"{game}.oldest_lifetime_max_updater is not a persisted lifetime maximum")
        for key in ("native_update", "readback_postverify", "save_scoped"):
            if proof[key] is not True:
                errors.append(f"{game}.{requirement} does not prove {key}")
    elif requirement == "memorial_storage_ownership":
        if proof["dedicated"] is not True or proof["atomic_pair"] is not True:
            errors.append(f"{game}.{requirement} is not dedicated and atomic")
        if proof["owner"] != "native_statistics_mutation":
            errors.append(f"{game}.{requirement} owner is not dedicated native statistics mutation")
        if proof["overlap_regions"] != [] or proof["not_origins_reserved"] is not True:
            errors.append(f"{game}.{requirement} overlaps a protected field or region")
    elif requirement == "atomic_save_load_serializer":
        for key in ("atomic_pair", "baseline_and_marker_same_transaction", "field_roundtrip"):
            if proof[key] is not True:
                errors.append(f"{game}.{requirement} does not prove {key}")
    elif requirement == "reload_offline_catchup_idempotence":
        for key in ("reload_round_trip", "offline_catchup", "idempotent", "duplicate_migration_noop"):
            if proof[key] is not True:
                errors.append(f"{game}.{requirement} does not prove {key}")
    elif requirement == "failed_load_nonmutation":
        for key in ("unchanged_on_failed_load", "no_partial_marker", "no_partial_baseline"):
            if proof[key] is not True:
                errors.append(f"{game}.{requirement} does not prove {key}")
    elif requirement == "expanded_256_compatibility":
        for key in ("stock_import", "expanded_reload", "expanded_offline_catchup", "record_bounds"):
            if proof[key] is not True:
                errors.append(f"{game}.{requirement} does not prove {key}")
    elif requirement == "hook_cave_composition":
        for key in ("hook_guard_verified", "hook_cave_no_overlap", "wrong_hook_rejected", "stock_mode_noop", "composition_checked"):
            if proof[key] is not True:
                errors.append(f"{game}.{requirement} does not prove {key}")
        if not isinstance(proof["ownership"], str) or not proof["ownership"].strip():
            errors.append(f"{game}.{requirement} has no hook/cave owner")
    elif requirement == "runtime_player_evidence":
        for key in ("runtime_receipt_sha256", "player_receipt_sha256"):
            if not _hash(proof[key]):
                errors.append(f"{game}.{requirement} has a malformed {key}")
        for key in ("runtime_confirmed", "player_confirmed"):
            if proof[key] is not True:
                errors.append(f"{game}.{requirement} does not prove {key}")
    return errors


def _validate_game(game: str, record: Any, global_data: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if not _is_mapping(record):
        return [f"{game} record must be an object"]
    required = {"stock", "requirements", "receipts"}
    errors.extend(f"{game} missing {key}" for key in sorted(required - set(record)))
    errors.extend(f"{game} has unexpected key {key}" for key in sorted(set(record) - required))
    if errors:
        return errors
    _validate_stock(game, record["stock"], errors)
    requirements = record["requirements"]
    receipts = record["receipts"]
    if not isinstance(requirements, list):
        errors.append(f"{game}.requirements must be an array")
        return errors
    if not isinstance(receipts, list):
        errors.append(f"{game}.receipts must be an array")
        return errors
    requirement_map: dict[str, Mapping[str, Any]] = {}
    for item in requirements:
        if not _is_mapping(item):
            errors.append(f"{game} requirement must be an object")
            continue
        requirement_id = item.get("id")
        if not isinstance(requirement_id, str) or not requirement_id:
            errors.append(f"{game} requirement id is missing")
            continue
        if requirement_id in requirement_map:
            errors.append(f"{game} duplicate requirement {requirement_id}")
        requirement_map[requirement_id] = item
    if set(requirement_map) != set(REQUIRED_REQUIREMENTS):
        errors.append(f"{game} requirement set is incomplete or has extras")

    receipt_map: dict[str, Mapping[str, Any]] = {}
    receipt_by_requirement: dict[str, list[Mapping[str, Any]]] = {}
    regions: list[tuple[int, int, str]] = []
    forbidden_offset = WITHDRAWN_HOOKS[game][0]
    protected = PROTECTED_FIELDS[game]
    for receipt in receipts:
        if not _is_mapping(receipt):
            errors.append(f"{game} receipt must be an object")
            continue
        receipt_id = receipt.get("id")
        requirement = receipt.get("requirement")
        if not isinstance(receipt_id, str) or not receipt_id:
            errors.append(f"{game} receipt id is missing")
            continue
        if receipt_id in receipt_map:
            errors.append(f"{game} duplicate evidence receipt {receipt_id}")
        receipt_map[receipt_id] = receipt
        if requirement not in REQUIRED_REQUIREMENTS:
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
            errors.append(f"{game} receipt {receipt_id} has the wrong source fingerprint")
        errors.extend(_required_proof_errors(str(requirement), receipt.get("proof"), game))
        if requirement == "stock_fingerprint" and _is_mapping(receipt.get("proof")):
            proof = receipt["proof"]
            if proof.get("exe_size") != EXPECTED_STOCK[game]["size"]:
                errors.append(f"{game} stock receipt {receipt_id} has the wrong executable size")
            if proof.get("exe_sha256") != EXPECTED_STOCK[game]["sha256"]:
                errors.append(f"{game} stock receipt {receipt_id} has the wrong executable fingerprint")
            folder = record["stock"].get("full_folder", {})
            if _is_mapping(folder):
                for key in ("full_folder_sha256", "full_folder_manifest_sha256", "full_folder_file_count"):
                    direct_key = {
                        "full_folder_sha256": "sha256",
                        "full_folder_manifest_sha256": "manifest_sha256",
                        "full_folder_file_count": "file_count",
                    }[key]
                    if proof.get(key) != folder.get(direct_key):
                        errors.append(f"{game} stock receipt {receipt_id} disagrees with the direct full-folder fingerprint")
        for key, value in _proof_values(receipt.get("proof", {})):
            if value == forbidden_offset:
                errors.append(f"{game} receipt {receipt_id} reuses withdrawn hook {value:#x} ({key})")
            if value in protected:
                errors.append(f"{game} receipt {receipt_id} reuses protected {protected[value]} field {value:#x} ({key})")
        receipt_regions = receipt.get("regions")
        if not isinstance(receipt_regions, list):
            errors.append(f"{game} receipt {receipt_id} regions must be an array")
            continue
        for region in receipt_regions:
            if not _is_mapping(region):
                errors.append(f"{game} receipt {receipt_id} region must be an object")
                continue
            start = _address(region.get("start"))
            length = region.get("length")
            if start is None or not isinstance(length, int) or length <= 0:
                errors.append(f"{game} receipt {receipt_id} has an invalid region")
                continue
            end = start + length
            if start <= forbidden_offset < end:
                errors.append(f"{game} receipt {receipt_id} overlaps withdrawn hook {forbidden_offset:#x}")
            for protected_address, owner in protected.items():
                if start <= protected_address < end:
                    errors.append(f"{game} receipt {receipt_id} overlaps protected {owner} field {protected_address:#x}")
            regions.append((start, end, receipt_id))
    for left_index, (left_start, left_end, left_id) in enumerate(regions):
        for right_start, right_end, right_id in regions[left_index + 1 :]:
            if left_start < right_end and right_start < left_end:
                errors.append(f"{game} evidence regions overlap: {left_id} and {right_id}")

    for requirement in REQUIRED_REQUIREMENTS:
        item = requirement_map.get(requirement)
        if item is None:
            continue
        evidence_ids = item.get("evidence_ids")
        if not isinstance(evidence_ids, list):
            errors.append(f"{game}.{requirement} evidence_ids must be an array")
            continue
        if any(not isinstance(evidence_id, str) for evidence_id in evidence_ids):
            errors.append(f"{game}.{requirement} evidence ids must be strings")
        if len(evidence_ids) != len({repr(evidence_id) for evidence_id in evidence_ids}):
            errors.append(f"{game}.{requirement} has duplicate evidence ids")
        for evidence_id in evidence_ids:
            if evidence_id not in receipt_map:
                errors.append(f"{game}.{requirement} references missing evidence {evidence_id}")
        if item.get("status") != "verified":
            errors.append(f"{game}.{requirement} is not verified")
        matched = receipt_by_requirement.get(requirement, [])
        if item.get("status") == "verified" and len(matched) != 1:
            errors.append(f"{game}.{requirement} must have exactly one verified receipt")
        if item.get("status") == "verified" and len(evidence_ids) != 1:
            errors.append(f"{game}.{requirement} must name exactly one receipt")
        if matched and item.get("status") == "verified" and matched[0].get("id") not in evidence_ids:
            errors.append(f"{game}.{requirement} does not reference its receipt")
    return errors


def validate_contract(data: Mapping[str, Any]) -> ValidationResult:
    """Validate contract shape and all evidence gates without enabling anything."""

    shape_errors = _shape_errors(data)
    if shape_errors:
        return ValidationResult(False, False, False, tuple(shape_errors))
    errors = _validate_global_guards(data)
    games = data["games"]
    for game in GAME_IDS:
        errors.extend(_validate_game(game, games[game], data))
    schema_valid = not errors or not any(error.startswith(("root", "schema", "feature", "publication", "games", "withdrawn_hooks", "protected_fields")) for error in errors)
    # A complete evidence bundle has no validation errors after the structural
    # guards, but this contract intentionally cannot publish while disabled.
    evidence_complete = not errors
    publication_allowed = bool(data.get("enabled")) and evidence_complete
    if not data.get("enabled"):
        publication_allowed = False
    return ValidationResult(schema_valid, evidence_complete, publication_allowed, tuple(errors))


def load_contract(path: Path) -> Mapping[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_contract_file(path: Path) -> ValidationResult:
    try:
        data = load_contract(path)
    except (OSError, json.JSONDecodeError) as exc:
        return ValidationResult(False, False, False, (str(exc),))
    return validate_contract(data)


def validate_export_manifest(manifest: Mapping[str, Any]) -> tuple[str, ...]:
    """Ensure the existing statistics catalog remains separate from this gate."""

    errors: list[str] = []
    features = manifest.get("features")
    if not isinstance(features, list):
        return ("statistics manifest features must be an array",)
    for feature in features:
        if not isinstance(feature, Mapping):
            errors.append("statistics manifest contains a non-object feature")
            continue
        feature_id = str(feature.get("id", ""))
        if "native_statistics_mutation" in feature_id:
            errors.append("native statistics mutation must not be a catalog feature")
        if feature.get("enabled") is True and feature_id == "native_statistics_mutation":
            errors.append("native statistics mutation catalog entry is enabled")
    return tuple(errors)


def publication_ready() -> bool:
    """The current contract is deliberately disabled, so publication is never ready."""

    return False
