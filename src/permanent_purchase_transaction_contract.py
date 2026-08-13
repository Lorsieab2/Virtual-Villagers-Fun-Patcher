"""Disabled universal contract for permanent Origins-style purchases.

This module is deliberately not imported by the patcher.  It validates
reference evidence one action at a time and can never publish or enable an
action.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping


CONTRACT_PATH = Path(__file__).resolve().parents[1] / "data" / "permanent_purchase_transaction_contract.json"
GAMES = ("vv1", "vv2", "vv3", "vv4", "vv5")
REQUIREMENTS = (
    "dry_run", "natural_prompt", "idok_only", "context_reacquire",
    "eligibility_before_reads", "native_setter", "native_readback",
    "notification_and_stats", "postverify", "single_deduction",
    "no_charge_exits", "rollback_and_disclosure", "fullscreen_lifecycle",
    "composition_and_expanded",
)
ROOT_KEYS = {"schema", "schema_version", "enabled", "catalog_enabled", "catalog_hidden",
             "runtime_ready", "player_verified", "publication_allowed", "action_definitions", "games"}
ACTION_KEYS = {"id", "screen", "label", "price", "price_status", "repeatability", "button_policy", "requirements"}
BINDING_KEYS = {"id", "availability", "evidence"}


@dataclass(frozen=True)
class ActionResult:
    game: str
    action_id: str
    schema_valid: bool
    evidence_complete: bool
    missing: tuple[str, ...]


@dataclass(frozen=True)
class ContractResult:
    schema_valid: bool
    publication_allowed: bool
    actions: tuple[ActionResult, ...]
    errors: tuple[str, ...]


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_contract(raw: Mapping[str, Any]) -> ContractResult:
    errors: list[str] = []
    results: list[ActionResult] = []
    if set(raw) != ROOT_KEYS:
        errors.append("root key set is not exact")
    if raw.get("schema") != "vvfp.permanent_purchase_transaction_contract" or raw.get("schema_version") != 1:
        errors.append("schema identity is invalid")
    if any(raw.get(key) is not value for key, value in (
        ("enabled", False), ("catalog_enabled", False), ("catalog_hidden", True),
        ("runtime_ready", False), ("player_verified", False), ("publication_allowed", False),
    )):
        errors.append("contract must remain disabled, hidden, and unpublished")
    definitions = raw.get("action_definitions")
    games = raw.get("games")
    if not isinstance(definitions, list) or not isinstance(games, dict) or tuple(games) != GAMES:
        errors.append("action/game inventory is malformed")
        return ContractResult(False, False, tuple(), tuple(errors))
    by_id: dict[str, Mapping[str, Any]] = {}
    for action in definitions:
        if not isinstance(action, dict) or set(action) != ACTION_KEYS:
            errors.append("action definition key set is not exact")
            continue
        action_id = action.get("id")
        if not isinstance(action_id, str) or action_id in by_id:
            errors.append("action ids must be unique strings")
            continue
        if (action.get("screen") not in {"tech", "individual", "village_wide", "unproven"}
                or not isinstance(action.get("label"), str) or not action["label"]
                or action.get("repeatability") not in {"repeatable", "permanent_toggle", "one_shot", "unproven"}
                or action.get("button_policy") not in {"buy_only", "buy_or_owned_remove", "unproven"}
                or action.get("price_status") not in {"exact", "unproven"}
                or (action.get("price_status") == "exact" and (type(action.get("price")) is not int or action["price"] < 0))
                or (action.get("price_status") == "unproven" and action.get("price") is not None)
                or action.get("requirements") != list(REQUIREMENTS)):
            errors.append(f"{action_id}: metadata or requirement order is invalid")
            continue
        by_id[action_id] = action
    expected_ids = list(by_id)
    for game in GAMES:
        bindings = games.get(game)
        if not isinstance(bindings, list) or [item.get("id") for item in bindings if isinstance(item, dict)] != expected_ids:
            errors.append(f"{game}: binding inventory/order differs from definitions")
            continue
        for binding in bindings:
            action_id = str(binding.get("id"))
            local_errors: list[str] = []
            if set(binding) != BINDING_KEYS or binding.get("availability") not in {"legacy_unsafe", "disabled_candidate", "absent_proposed", "static_only", "not_applicable"}:
                local_errors.append("binding schema/status")
            evidence = binding.get("evidence")
            if not isinstance(evidence, dict) or not set(evidence).issubset(REQUIREMENTS) or any(not isinstance(value, list) for value in evidence.values()):
                local_errors.append("evidence key set")
                evidence = {}
            missing = tuple(req for req in REQUIREMENTS if not isinstance(evidence.get(req), list) or not evidence.get(req))
            results.append(ActionResult(game, action_id, not local_errors, not local_errors and not missing, missing + tuple(local_errors)))
    schema_valid = not errors and all(item.schema_valid for item in results)
    # Reference-only by construction, even if a synthetic object fills every receipt.
    return ContractResult(schema_valid, False, tuple(results), tuple(errors))


def missing_evidence_matrix(raw: Mapping[str, Any]) -> dict[str, dict[str, tuple[str, ...]]]:
    result = validate_contract(raw)
    matrix = {game: {} for game in GAMES}
    for item in result.actions:
        matrix[item.game][item.action_id] = item.missing
    return matrix
