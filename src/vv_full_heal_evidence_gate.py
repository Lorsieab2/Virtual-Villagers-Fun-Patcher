"""Fail-closed evidence gate for future VV1/VV2 Full Heal replacements.

This module is intentionally outside the public catalog and native emit path.
The tracked JSON is a disabled contract, not an implementation claim. A future
candidate may be structurally audited with :func:`validate_candidate_evidence`,
but this scope has no enablement operation and emits no native bytes.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "data" / "candidates" / "vv1_vv2_full_heal_evidence_gate.json"

EXPECTED_STOCK = {
    "vv1": {
        "filename": "Virtual Villagers - A New Home.exe",
        "size": 581632,
        "sha256": "1EC790B927741081D5CE13A48FB76983A4FD4336EA08F89317872643760AF03D",
    },
    "vv2": {
        "filename": "Virtual Villagers - The Lost Children.exe",
        "size": 724992,
        "sha256": "46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677",
    },
}

LEGACY_LABEL = "Cure all Villagers"
REPLACEMENT_LABEL = "Full Heal / Cure All"
PRICE = 30_000
NO_DEDUCTION = "No tech points have been deducted."
HEX64 = re.compile(r"^[0-9A-F]{64}$")

CONTRACT_KEYS = {
    "schema_version",
    "id",
    "name",
    "status",
    "enabled",
    "catalog_enabled",
    "catalog_hidden",
    "native_output",
    "certification_status",
    "evidence_status",
    "public_choices",
    "legacy_cure_policy",
    "replacement_contract",
    "wording",
    "games",
    "candidate_schema",
    "evidence_records",
}

CANDIDATE_REQUIRED_PATHS = (
    "schema_version",
    "game_id",
    "status",
    "enabled",
    "catalog_enabled",
    "catalog_hidden",
    "native_output",
    "evidence_origin",
    "source_artifacts",
    "stock",
    "folder_inventory",
    "native.health_setter",
    "native.sickness_people_cured",
    "native.raw_health_write",
    "native.postverify",
    "fullscreen.owner_hwnd_capture",
    "fullscreen.is_window_validated",
    "fullscreen.same_process_validated",
    "fullscreen.monitor_work_area",
    "fullscreen.center_clamp",
    "fullscreen.leave_fullscreen",
    "fullscreen.dialog_message_owner",
    "fullscreen.restore_window_state",
    "fullscreen.lifetime_cleanup",
    "fullscreen.failure_no_mutation",
    "eligibility.active",
    "eligibility.living",
    "eligibility.believer",
    "eligibility.golden_child",
    "eligibility.health_positive",
    "eligibility.partial_health_range",
    "eligibility.health_100_preserved",
    "eligibility.sickness_nonzero",
    "eligibility.physical_enumeration",
    "counters.predicted_sickness",
    "counters.predicted_partial_health",
    "counters.verified_sickness",
    "counters.verified_partial_health",
    "counters.overlap_counted_in_both",
    "counters.prediction_before_deduction",
    "counters.verified_before_deduction",
    "transaction.confirmation",
    "transaction.identity_reacquisition",
    "transaction.funds_recheck",
    "transaction.postverify_before_deduction",
    "transaction.deduction",
    "transaction.failure",
    "wording",
    "resource",
    "ownership",
    "legacy_cure_policy",
)

FORBIDDEN_PLACEHOLDERS = (
    "todo",
    "tbd",
    "unknown",
    "synthetic",
    "invented",
    "placeholder",
    "not recorded",
    "address unavailable",
)


class EvidenceGateError(ValueError):
    """Raised when evidence is incomplete, synthetic, or unsafe to expose."""


def _error(path: str, message: str) -> EvidenceGateError:
    return EvidenceGateError(f"{path}: {message}")


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise _error(path, "must be an object")
    return value


def _exact_keys(value: Mapping[str, Any], expected: set[str], path: str) -> None:
    actual = set(value)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing:
        raise _error(path, f"missing required keys: {', '.join(missing)}")
    if extra:
        raise _error(path, f"unknown keys are not allowed: {', '.join(extra)}")


def _get(value: Mapping[str, Any], path: str) -> Any:
    current: Any = value
    for member in path.split("."):
        if not isinstance(current, Mapping) or member not in current:
            raise _error(path, "missing required evidence")
        current = current[member]
    return current


def _bool(value: Any, path: str, expected: bool | None = None) -> None:
    if type(value) is not bool:
        raise _error(path, "must be a JSON boolean")
    if expected is not None and value is not expected:
        raise _error(path, f"must be {str(expected).lower()}")


def _text(value: Any, path: str, *, nonempty: bool = True) -> str:
    if not isinstance(value, str) or (nonempty and not value.strip()):
        raise _error(path, "must be a non-empty string")
    return value


def _hex(value: Any, path: str) -> str:
    text = _text(value, path)
    if HEX64.fullmatch(text) is None:
        raise _error(path, "must be 64 uppercase hexadecimal characters")
    return text


def _positive_int(value: Any, path: str) -> int:
    if type(value) is not int or value <= 0:
        raise _error(path, "must be a positive integer")
    return value


def _no_forbidden_placeholder(value: Any, path: str) -> None:
    if isinstance(value, str):
        folded = value.casefold()
        for token in FORBIDDEN_PLACEHOLDERS:
            if token in folded:
                raise _error(path, f"contains forbidden synthetic/placeholder token {token!r}")
    elif isinstance(value, Mapping):
        for key, child in value.items():
            _no_forbidden_placeholder(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _no_forbidden_placeholder(child, f"{path}[{index}]")


def _validate_wording(wording: Mapping[str, Any], path: str = "wording") -> None:
    expected = {
        "label",
        "no_deduction_suffix",
        "plural_nouns",
        "confirmation",
        "success",
        "no_change",
        "failure",
    }
    _exact_keys(wording, expected, path)
    if wording["label"] != REPLACEMENT_LABEL:
        raise _error(f"{path}.label", f"must be exactly {REPLACEMENT_LABEL!r}")
    if wording["no_deduction_suffix"] != NO_DEDUCTION:
        raise _error(f"{path}.no_deduction_suffix", "does not match the exact no-charge suffix")
    nouns = _mapping(wording["plural_nouns"], f"{path}.plural_nouns")
    _exact_keys(nouns, {"eligible_villager", "partial_health_villager"}, f"{path}.plural_nouns")
    for noun_name, expected_forms in (
        (
            "eligible_villager",
            {"zero": "eligible villagers", "one": "eligible villager", "other": "eligible villagers"},
        ),
        (
            "partial_health_villager",
            {"zero": "partial-health villagers", "one": "partial-health villager", "other": "partial-health villagers"},
        ),
    ):
        forms = _mapping(nouns[noun_name], f"{path}.plural_nouns.{noun_name}")
        _exact_keys(forms, {"zero", "one", "other"}, f"{path}.plural_nouns.{noun_name}")
        if dict(forms) != expected_forms:
            raise _error(f"{path}.plural_nouns.{noun_name}", "has unsafe singular/plural forms")
    for name in ("confirmation", "success", "failure"):
        text = _text(wording[name], f"{path}.{name}")
        for token in ("{sick_count}", "{eligible_villager_noun}", "{partial_count}", "{partial_health_villager_noun}"):
            if token not in text:
                raise _error(f"{path}.{name}", f"must contain {token}")
        if REPLACEMENT_LABEL not in text:
            raise _error(f"{path}.{name}", "must contain the replacement label")
    if NO_DEDUCTION not in wording["no_change"] or NO_DEDUCTION not in wording["failure"]:
        raise _error(path, "no-change and failure messages require the exact no-charge suffix")
    if LEGACY_LABEL in json.dumps(wording, ensure_ascii=False):
        raise _error(path, "must not contain the legacy Cure label")


def _validate_disabled_contract(raw: Mapping[str, Any]) -> None:
    _exact_keys(raw, CONTRACT_KEYS, "contract")
    if raw["schema_version"] != 1:
        raise _error("contract.schema_version", "unsupported schema version")
    if raw["id"] != "vv1_vv2_full_heal_evidence_gate":
        raise _error("contract.id", "unexpected gate id")
    for key, expected in (
        ("status", "STOP"),
        ("enabled", False),
        ("catalog_enabled", False),
        ("catalog_hidden", True),
        ("native_output", False),
    ):
        value = raw[key]
        if type(value) is not type(expected) or value != expected:
            raise _error(f"contract.{key}", f"must be {expected!r}")
    if raw["public_choices"] != [] or raw["evidence_records"] != []:
        raise _error("contract", "disabled gate may not expose choices or evidence records")
    legacy = _mapping(raw["legacy_cure_policy"], "contract.legacy_cure_policy")
    _exact_keys(
        legacy,
        {
            "label",
            "status",
            "is_full_heal_replacement",
            "replacement_catalog_enabled",
            "replacement_native_output",
            "must_be_dominated_before_replacement_price_lookup",
            "must_not_be_described_as_full_heal",
        },
        "contract.legacy_cure_policy",
    )
    if legacy["label"] != LEGACY_LABEL or legacy["status"] != "legacy-sickness-only":
        raise _error("contract.legacy_cure_policy", "legacy Cure identity is not explicit")
    for key in (
        "is_full_heal_replacement",
        "replacement_catalog_enabled",
        "replacement_native_output",
    ):
        _bool(legacy[key], f"contract.legacy_cure_policy.{key}", False)
    for key in (
        "must_be_dominated_before_replacement_price_lookup",
        "must_not_be_described_as_full_heal",
    ):
        _bool(legacy[key], f"contract.legacy_cure_policy.{key}", True)

    replacement = _mapping(raw["replacement_contract"], "contract.replacement_contract")
    _exact_keys(
        replacement,
        {"label", "command", "price", "action", "repeatable", "ownership", "remove", "overlap_counted_in_both", "partial_health_range", "health_100_preserved", "no_charge_on_failure", "rollback_claim"},
        "contract.replacement_contract",
    )
    exact = {
        "label": REPLACEMENT_LABEL,
        "command": 5,
        "price": PRICE,
        "action": "Buy",
        "repeatable": True,
        "ownership": None,
        "remove": False,
        "overlap_counted_in_both": True,
        "partial_health_range": "1..99",
        "health_100_preserved": True,
        "no_charge_on_failure": True,
        "rollback_claim": "not claimed",
    }
    if dict(replacement) != exact:
        raise _error("contract.replacement_contract", "replacement contract drifted from the required fail-closed values")
    _validate_wording(_mapping(raw["wording"], "contract.wording"), "contract.wording")

    games = _mapping(raw["games"], "contract.games")
    if set(games) != set(EXPECTED_STOCK):
        raise _error("contract.games", "must contain exactly VV1 and VV2")
    for game_id, expected_stock in EXPECTED_STOCK.items():
        game = _mapping(games[game_id], f"contract.games.{game_id}")
        _exact_keys(game, {"stock_executable"}, f"contract.games.{game_id}")
        stock = _mapping(game["stock_executable"], f"contract.games.{game_id}.stock_executable")
        _exact_keys(stock, {"filename", "size", "sha256"}, f"contract.games.{game_id}.stock_executable")
        if dict(stock) != expected_stock:
            raise _error(f"contract.games.{game_id}.stock_executable", "stock fingerprint does not match the exact supported build")

    schema = _mapping(raw["candidate_schema"], "contract.candidate_schema")
    _exact_keys(schema, {"required_paths", "exact_values", "folder_inventory", "native", "fullscreen", "transaction", "resource", "ownership"}, "contract.candidate_schema")
    if tuple(schema["required_paths"]) != CANDIDATE_REQUIRED_PATHS:
        raise _error("contract.candidate_schema.required_paths", "required evidence paths drifted")
    expected_exact = {
        "schema_version": 1,
        "status": "STOP",
        "enabled": False,
        "catalog_enabled": False,
        "catalog_hidden": True,
        "native_output": False,
        "replacement_label": REPLACEMENT_LABEL,
        "price": PRICE,
        "command": 5,
        "remove": False,
        "partial_health_range": "1..99",
        "overlap_counted_in_both": True,
        "no_charge_on_failure": True,
        "rollback_claim": "not claimed",
    }
    if schema["exact_values"] != expected_exact:
        raise _error("contract.candidate_schema.exact_values", "exact candidate gates drifted")


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    """Load and validate the disabled contract without catalog registration."""

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceGateError(f"contract: cannot load JSON: {exc}") from exc
    if not isinstance(raw, Mapping):
        raise _error("contract", "root must be an object")
    _validate_disabled_contract(raw)
    return dict(raw)


def _validate_source_artifacts(value: Any) -> None:
    if not isinstance(value, list) or not value:
        raise _error("source_artifacts", "complete repository-owned source artifacts are required")
    for index, item_value in enumerate(value):
        item = _mapping(item_value, f"source_artifacts[{index}]")
        _exact_keys(item, {"path", "kind", "sha256"}, f"source_artifacts[{index}]")
        path = _text(item["path"], f"source_artifacts[{index}].path")
        if Path(path).is_absolute() or ".." in Path(path).parts:
            raise _error(f"source_artifacts[{index}].path", "must be a repository-relative path")
        _text(item["kind"], f"source_artifacts[{index}].kind")
        _hex(item["sha256"], f"source_artifacts[{index}].sha256")


def _validate_folder_inventory(value: Any) -> None:
    inventory = _mapping(value, "folder_inventory")
    _exact_keys(inventory, {"scope", "complete", "all_dlls", "dll_count", "dll_inventory_sha256", "dlls"}, "folder_inventory")
    if inventory["scope"] != "full-game-folder":
        raise _error("folder_inventory.scope", "must cover the complete game folder")
    _bool(inventory["complete"], "folder_inventory.complete", True)
    _bool(inventory["all_dlls"], "folder_inventory.all_dlls", True)
    _positive_int(inventory["dll_count"], "folder_inventory.dll_count")
    _hex(inventory["dll_inventory_sha256"], "folder_inventory.dll_inventory_sha256")
    dlls = inventory["dlls"]
    if not isinstance(dlls, list) or len(dlls) != inventory["dll_count"]:
        raise _error("folder_inventory.dlls", "must enumerate every DLL in the full game folder")
    for index, item_value in enumerate(dlls):
        item = _mapping(item_value, f"folder_inventory.dlls[{index}]")
        _exact_keys(item, {"path", "size", "sha256"}, f"folder_inventory.dlls[{index}]")
        path = _text(item["path"], f"folder_inventory.dlls[{index}].path")
        if Path(path).is_absolute() or ".." in Path(path).parts or not path.casefold().endswith(".dll"):
            raise _error(f"folder_inventory.dlls[{index}].path", "must be a relative DLL path")
        _positive_int(item["size"], f"folder_inventory.dlls[{index}].size")
        _hex(item["sha256"], f"folder_inventory.dlls[{index}].sha256")


def _validate_native(value: Any) -> None:
    native = _mapping(value, "native")
    _exact_keys(native, {"health_setter", "sickness_people_cured", "raw_health_write", "postverify"}, "native")
    health = _mapping(native["health_setter"], "native.health_setter")
    _exact_keys(
        health,
        {"address", "calling_convention", "receiver", "arguments", "return_contract", "target_value", "abi_verified", "side_effects"},
        "native.health_setter",
    )
    for key in ("address", "calling_convention", "receiver", "arguments", "return_contract"):
        _text(health.get(key), f"native.health_setter.{key}")
    if health.get("target_value") != 100:
        raise _error("native.health_setter.target_value", "native setter must write exact health 100")
    _bool(health.get("abi_verified"), "native.health_setter.abi_verified", True)
    effects = health["side_effects"]
    if not isinstance(effects, list) or not effects:
        raise _error("native.health_setter.side_effects", "setter side effects must be enumerated")
    for index, effect in enumerate(effects):
        _text(effect, f"native.health_setter.side_effects[{index}]")
    sickness = _mapping(native["sickness_people_cured"], "native.sickness_people_cured")
    _exact_keys(
        sickness,
        {"sickness_field", "clear_route", "people_cured_field", "increment_timing", "postverify", "abi_verified", "increment_per_verified_clear"},
        "native.sickness_people_cured",
    )
    for key in ("sickness_field", "clear_route", "people_cured_field", "increment_timing", "postverify"):
        _text(sickness.get(key), f"native.sickness_people_cured.{key}")
    _bool(sickness.get("abi_verified"), "native.sickness_people_cured.abi_verified", True)
    _bool(sickness.get("increment_per_verified_clear"), "native.sickness_people_cured.increment_per_verified_clear", True)
    _bool(native["raw_health_write"], "native.raw_health_write", False)
    postverify = _mapping(native["postverify"], "native.postverify")
    _exact_keys(postverify, {"fresh_identity_reacquisition", "health", "sickness", "before_deduction"}, "native.postverify")
    for key in ("fresh_identity_reacquisition", "health", "sickness"):
        _text(postverify.get(key), f"native.postverify.{key}")
    if postverify["health"] != "100" or postverify["sickness"] != "0":
        raise _error("native.postverify", "postverification must require health 100 and sickness 0")
    _bool(postverify.get("before_deduction"), "native.postverify.before_deduction", True)


def _validate_eligibility(value: Any) -> None:
    eligibility = _mapping(value, "eligibility")
    expected = {"active", "living", "believer", "golden_child", "health_positive", "partial_health_range", "health_100_preserved", "sickness_nonzero", "physical_enumeration"}
    _exact_keys(eligibility, expected, "eligibility")
    for key in ("active", "living", "believer", "golden_child", "health_positive", "sickness_nonzero", "physical_enumeration"):
        _text(eligibility[key], f"eligibility.{key}")
    if eligibility["partial_health_range"] != "1..99":
        raise _error("eligibility.partial_health_range", "partial health must be exactly 1..99")
    _bool(eligibility["health_100_preserved"], "eligibility.health_100_preserved", True)


def _validate_counters(value: Any) -> None:
    counters = _mapping(value, "counters")
    expected = {"predicted_sickness", "predicted_partial_health", "verified_sickness", "verified_partial_health", "overlap_counted_in_both", "prediction_before_deduction", "verified_before_deduction"}
    _exact_keys(counters, expected, "counters")
    for key in ("predicted_sickness", "predicted_partial_health", "verified_sickness", "verified_partial_health"):
        _text(counters[key], f"counters.{key}")
    for key in ("overlap_counted_in_both", "prediction_before_deduction", "verified_before_deduction"):
        _bool(counters[key], f"counters.{key}", True)


def _validate_transaction(value: Any) -> None:
    transaction = _mapping(value, "transaction")
    _exact_keys(transaction, {"confirmation", "identity_reacquisition", "funds_recheck", "postverify_before_deduction", "deduction", "failure"}, "transaction")
    confirmation = _mapping(transaction["confirmation"], "transaction.confirmation")
    _exact_keys(confirmation, {"abi", "idok_only", "cancel_no_mutation", "non_idok_no_charge"}, "transaction.confirmation")
    _text(confirmation["abi"], "transaction.confirmation.abi")
    if confirmation["abi"] != "IDOK-only":
        raise _error("transaction.confirmation.abi", "confirmation ABI must be exactly IDOK-only")
    for key in ("idok_only", "cancel_no_mutation", "non_idok_no_charge"):
        _bool(confirmation[key], f"transaction.confirmation.{key}", True)
    identity = _mapping(transaction["identity_reacquisition"], "transaction.identity_reacquisition")
    _exact_keys(identity, {"same_selected_villager", "same_world_state", "boundaries", "identity_fields"}, "transaction.identity_reacquisition")
    for key in ("same_selected_villager", "same_world_state"):
        _text(identity[key], f"transaction.identity_reacquisition.{key}")
    if not isinstance(identity["boundaries"], list) or not identity["boundaries"]:
        raise _error("transaction.identity_reacquisition.boundaries", "reacquisition boundaries must be enumerated")
    _text(identity["identity_fields"], "transaction.identity_reacquisition.identity_fields")
    _bool(transaction["funds_recheck"], "transaction.funds_recheck", True)
    _bool(transaction["postverify_before_deduction"], "transaction.postverify_before_deduction", True)
    deduction = _mapping(transaction["deduction"], "transaction.deduction")
    _exact_keys(deduction, {"price", "calls", "after_postverify", "native_abi"}, "transaction.deduction")
    if deduction["price"] != PRICE or deduction["calls"] != 1:
        raise _error("transaction.deduction", "deduction must be exactly one 30,000-point call")
    _bool(deduction["after_postverify"], "transaction.deduction.after_postverify", True)
    _text(deduction["native_abi"], "transaction.deduction.native_abi")
    failure = _mapping(transaction["failure"], "transaction.failure")
    _exact_keys(failure, {"no_charge", "partial_effects_disclosed", "rollback_claim", "failure_message"}, "transaction.failure")
    _bool(failure["no_charge"], "transaction.failure.no_charge", True)
    _bool(failure["partial_effects_disclosed"], "transaction.failure.partial_effects_disclosed", True)
    if failure["rollback_claim"] != "not claimed":
        raise _error("transaction.failure.rollback_claim", "complete rollback may not be claimed")
    failure_message = _text(failure["failure_message"], "transaction.failure.failure_message")
    folded = failure_message.casefold()
    for required in (NO_DEDUCTION.casefold(), "earlier verified", "complete rollback"):
        if required not in folded:
            raise _error("transaction.failure.failure_message", f"must disclose {required!r}")


def _validate_fullscreen(value: Any) -> None:
    fullscreen = _mapping(value, "fullscreen")
    expected = {
        "owner_hwnd_capture",
        "is_window_validated",
        "same_process_validated",
        "monitor_work_area",
        "center_clamp",
        "leave_fullscreen",
        "dialog_message_owner",
        "restore_window_state",
        "lifetime_cleanup",
        "failure_no_mutation",
    }
    _exact_keys(fullscreen, expected, "fullscreen")
    for key in (
        "owner_hwnd_capture",
        "monitor_work_area",
        "center_clamp",
        "leave_fullscreen",
        "dialog_message_owner",
        "restore_window_state",
        "lifetime_cleanup",
    ):
        _text(fullscreen[key], f"fullscreen.{key}")
    for key in ("is_window_validated", "same_process_validated", "failure_no_mutation"):
        _bool(fullscreen[key], f"fullscreen.{key}", True)


def _validate_resource(value: Any) -> None:
    resource = _mapping(value, "resource")
    expected = {"dialog_id", "control_id", "label", "price_text", "parent_sha256", "candidate_sha256", "candidate_size", "legacy_label_absent", "resource_202_unchanged"}
    _exact_keys(resource, expected, "resource")
    if resource["dialog_id"] != 201 or resource["control_id"] != 1005:
        raise _error("resource", "replacement must own resource 201 control 1005")
    if resource["label"] != REPLACEMENT_LABEL or resource["price_text"] != "30,000 tech points":
        raise _error("resource", "replacement label/price text is not exact")
    _hex(resource["parent_sha256"], "resource.parent_sha256")
    _hex(resource["candidate_sha256"], "resource.candidate_sha256")
    _positive_int(resource["candidate_size"], "resource.candidate_size")
    _bool(resource["legacy_label_absent"], "resource.legacy_label_absent", True)
    _bool(resource["resource_202_unchanged"], "resource.resource_202_unchanged", True)
    if LEGACY_LABEL in json.dumps(resource, ensure_ascii=False):
        raise _error("resource", "replacement resource must not contain the legacy Cure label")


def _validate_ownership(value: Any) -> None:
    ownership = _mapping(value, "ownership")
    expected = {
        "hook_owner",
        "cave_owner",
        "resource_owner",
        "composition_owner",
        "parent_identity",
        "owned_ranges",
        "removal_identity",
        "hook_preimage_sha256",
        "cave_sha256",
        "composition_order",
        "expanded_rejected",
        "mode_fingerprint",
        "disjoint_ranges",
        "collision_fail_closed",
        "gong_island_unchanged",
        "legacy_route_dominated_before_price",
    }
    _exact_keys(ownership, expected, "ownership")
    for key in ("hook_owner", "cave_owner", "resource_owner", "composition_owner", "parent_identity", "removal_identity"):
        _text(ownership[key], f"ownership.{key}")
    if not isinstance(ownership["owned_ranges"], list) or not ownership["owned_ranges"]:
        raise _error("ownership.owned_ranges", "hook/cave ownership ranges are required")
    _hex(ownership["hook_preimage_sha256"], "ownership.hook_preimage_sha256")
    _hex(ownership["cave_sha256"], "ownership.cave_sha256")
    if not isinstance(ownership["composition_order"], list) or not ownership["composition_order"]:
        raise _error("ownership.composition_order", "composition dependency order is required")
    for index, dependency in enumerate(ownership["composition_order"]):
        _text(dependency, f"ownership.composition_order[{index}]")
    _text(ownership["mode_fingerprint"], "ownership.mode_fingerprint")
    _bool(ownership["expanded_rejected"], "ownership.expanded_rejected", True)
    _bool(ownership["disjoint_ranges"], "ownership.disjoint_ranges", True)
    for key in ("collision_fail_closed", "gong_island_unchanged", "legacy_route_dominated_before_price"):
        _bool(ownership[key], f"ownership.{key}", True)


def validate_candidate_evidence(candidate: Mapping[str, Any], contract: Mapping[str, Any] | None = None) -> None:
    """Validate a future evidence record while keeping it disabled.

    This validates evidence shape and exact transaction/resource requirements; it
    never registers, emits, or enables a candidate. Synthetic provenance is
    rejected even when the structural fields look complete.
    """

    if contract is None:
        contract = load_contract()
    _validate_disabled_contract(contract)
    if not isinstance(candidate, Mapping):
        raise _error("candidate", "root must be an object")
    expected_keys = {path.split(".")[0] for path in CANDIDATE_REQUIRED_PATHS}
    expected_keys.update({"schema_version", "game_id", "status", "enabled", "catalog_enabled", "catalog_hidden", "native_output", "evidence_origin", "source_artifacts", "stock", "folder_inventory", "native", "fullscreen", "eligibility", "counters", "transaction", "wording", "resource", "ownership", "legacy_cure_policy"})
    _exact_keys(candidate, expected_keys, "candidate")
    if candidate["schema_version"] != 1:
        raise _error("candidate.schema_version", "unsupported schema version")
    game_id = candidate["game_id"]
    if game_id not in EXPECTED_STOCK:
        raise _error("candidate.game_id", "only VV1 and VV2 are in scope")
    for key, expected in (("status", "STOP"), ("enabled", False), ("catalog_enabled", False), ("catalog_hidden", True), ("native_output", False)):
        if type(candidate[key]) is not type(expected) or candidate[key] != expected:
            raise _error(f"candidate.{key}", f"must be {expected!r}")
    _validate_source_artifacts(candidate["source_artifacts"])
    stock = _mapping(candidate["stock"], "stock")
    _exact_keys(stock, {"filename", "size", "sha256"}, "stock")
    if dict(stock) != EXPECTED_STOCK[game_id]:
        raise _error("stock", "does not match the exact stock fingerprint for this game")
    _validate_folder_inventory(candidate["folder_inventory"])
    _validate_native(candidate["native"])
    _validate_fullscreen(candidate["fullscreen"])
    _validate_eligibility(candidate["eligibility"])
    _validate_counters(candidate["counters"])
    _validate_transaction(candidate["transaction"])
    if candidate["wording"] != contract["wording"]:
        raise _error("candidate.wording", "must equal the exact gate wording contract")
    _validate_wording(_mapping(candidate["wording"], "candidate.wording"), "candidate.wording")
    _validate_resource(candidate["resource"])
    _validate_ownership(candidate["ownership"])
    if candidate["legacy_cure_policy"] != contract["legacy_cure_policy"]:
        raise _error("candidate.legacy_cure_policy", "legacy Cure policy must remain explicit and unchanged")
    _no_forbidden_placeholder(candidate, "candidate")
    origin = _mapping(candidate["evidence_origin"], "candidate.evidence_origin")
    _exact_keys(origin, {"repository_owned", "synthetic", "method", "review_status"}, "candidate.evidence_origin")
    _bool(origin["repository_owned"], "candidate.evidence_origin.repository_owned", True)
    _bool(origin["synthetic"], "candidate.evidence_origin.synthetic", False)
    if origin["method"] != "repository-owned disassembly/resource export":
        raise _error("candidate.evidence_origin.method", "unsupported evidence method")
    if origin["review_status"] != "independent review pending":
        raise _error("candidate.evidence_origin.review_status", "runtime/independent review state must remain explicit")


def assert_enablement_blocked(candidate: Mapping[str, Any]) -> None:
    """Always STOP: this scope has no enablement or native-output operation."""

    validate_candidate_evidence(candidate)
    raise EvidenceGateError("STOP: VV1/VV2 Full Heal evidence gate is disabled; no catalog or native output is permitted")


def contract_sha256(path: Path = CONTRACT_PATH) -> str:
    """Return the exact contract-file SHA-256 for handoff and provenance."""

    return hashlib.sha256(path.read_bytes()).hexdigest().upper()
