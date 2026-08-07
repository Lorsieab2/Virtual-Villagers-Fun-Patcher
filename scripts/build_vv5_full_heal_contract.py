"""Build and validate the disabled VV5 Full Heal / Cure All contract.

The generated JSON is evidence only and is written under ``outputs/``.  This
builder emits no PE bytes, native hooks, catalog entry, package, or save
change.  It binds the contract to the exact VV5 stock/base/composition inputs
already used by the disabled UI candidate.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from vv5_full_heal import (  # noqa: E402
    PRICE,
    callback_contract,
    message_contract,
    record_contract,
    transaction_contract,
)
from build_vv5_ui_confirmation_candidate import (  # noqa: E402
    ACTIVE_BASE,
    ACTIVE_BASE_SHA256,
    ACTIVE_PAYLOAD_SHA256,
    FULL_MASTERY_FEATURE_PATH,
    FULL_MASTERY_FEATURE_SHA256,
    FULL_MASTERY_MAP_PATH,
    FULL_MASTERY_MAP_SHA256,
    FULL_MASTERY_PARENT_HASHES,
    KNOWN_OCCUPIED_RANGES,
    RUNNING_MAP_PATH,
    RUNNING_MAP_SHA256,
    STOCK_SHA256,
    build_manifest as build_ui_manifest,
    sha,
    validate_cave_hook_overlaps,
)
from canonical_source_hash import (  # noqa: E402
    CANONICAL_SOURCE_HASH_RULE,
    canonical_source_sha256,
)


OUTPUT = ROOT / "outputs" / "vv5-full-heal-contract"
OUTPUT_MANIFEST = OUTPUT / "candidate.json"
STOCK_SIZE = 991232
STOCK_FILENAME = "Virtual Villagers - New Believers.exe"
STOCK_SOURCE = "research/stock-executables/Virtual Villagers - New Believers.exe"
UI_BUILDER_PATH = ROOT / "scripts" / "build_vv5_ui_confirmation_candidate.py"
UI_MODEL_PATH = ROOT / "src" / "vv5_individual_transactions.py"
FULL_HEAL_MODEL_PATH = ROOT / "src" / "vv5_full_heal.py"
UI_BUILDER_SHA256 = "AF46AFDDD3870ABB849F232564C8D055A4EC3D7F4C52A4947CE14692D15FE2DE"
UI_MODEL_SHA256 = "D78FE2E5B36E3B3FB0AD72C21A0D46343E83A2A854DA09DB0E6003353708209C"
FULL_HEAL_MODEL_SHA256 = "B395B2342F805189A2C34C7C76529663CC173BD590B50731AD6F4407DFBE99BF"

MANIFEST_KEYS = {
    "id", "game_id", "name", "enabled", "catalog_hidden", "catalog_enabled",
    "runtime_status", "allowed_modes", "unsupported_patch_modes", "expanded_fail_closed",
    "dependencies", "source", "stock_fingerprint", "record_contract",
    "native_callbacks", "native_routing", "composition_guard", "transaction",
    "messages", "implementation",
}
SOURCE_KEYS = {"stock_sha256", "active_base", "active_base_sha256", "active_payload_sha256", "source_hash_rule", "model_sha256"}
STOCK_KEYS = {"filename", "size", "sha256", "source", "source_present", "source_bound", "status"}
NATIVE_KEYS = {"patches", "emitted_hooks", "candidate_caves", "candidate_hooks", "status"}
COMPOSITION_KEYS = {"stock_sha256", "base_parent", "ui_chain", "full_mastery", "running", "full_heal", "ranges"}
BASE_PARENT_KEYS = {"feature", "manifest", "manifest_sha256", "payload_sha256"}
UI_CHAIN_KEYS = {"feature", "builder", "builder_sha256", "model", "model_sha256", "status"}
FULL_MASTERY_KEYS = {"feature", "map", "map_sha256", "parent_hashes", "owned_range"}
RUNNING_KEYS = {"feature", "map", "map_sha256", "parent_hash", "owned_range"}
FULL_HEAL_KEYS = {"feature", "status", "owned_range"}
RANGE_KEYS = {"name", "start", "end", "owner", "address_space"}
IMPLEMENTATION_KEYS = {"transaction_engine", "native_writer_policy", "save_policy", "catalog_policy"}

RUNTIME_STATUS = "pending; no package or player validation"
STOCK_FINGERPRINT = {
    "filename": STOCK_FILENAME,
    "size": STOCK_SIZE,
    "sha256": STOCK_SHA256,
    "source": STOCK_SOURCE,
    "source_present": False,
    "source_bound": False,
    "status": "exact stock executable is not repository-owned in this checkout",
}


def _strict_structure(actual: object, expected: object, label: str) -> None:
    if type(actual) is not type(expected):
        raise ValueError(f"{label} has the wrong exact type")
    if isinstance(expected, dict):
        if set(actual) != set(expected):
            raise ValueError(f"{label} schema keys are not exact")
        for key in expected:
            _strict_structure(actual[key], expected[key], f"{label}.{key}")
    elif isinstance(expected, list):
        if len(actual) != len(expected):
            raise ValueError(f"{label} length is not exact")
        for index, (item, expected_item) in enumerate(zip(actual, expected)):
            _strict_structure(item, expected_item, f"{label}[{index}]")
    elif actual != expected:
        raise ValueError(f"{label} is not exact")


def _known_keys(value: object, expected: set[str], label: str) -> None:
    if type(value) is not dict or set(value) != expected:
        raise ValueError(f"{label} schema keys are not exact")


def _exact_bool(value: object, label: str) -> None:
    if type(value) is not bool:
        raise ValueError(f"{label} must be an exact bool")


def _exact_int(value: object, label: str) -> None:
    if type(value) is not int:
        raise ValueError(f"{label} must be an exact int")


def _validate_hash(path: Path, expected: str, label: str, *, source_text: bool = False) -> None:
    actual = canonical_source_sha256(path) if source_text and path.is_file() else (sha(path.read_bytes()) if path.is_file() else None)
    if actual != expected:
        raise ValueError(f"{label} hash is not exact")


def _validate_ranges(ranges: object) -> None:
    if type(ranges) is not list or ranges != list(KNOWN_OCCUPIED_RANGES):
        raise ValueError("composition ranges must equal the existing owned-range inventory")
    for index, entry in enumerate(ranges):
        _known_keys(entry, RANGE_KEYS, f"composition_guard.ranges[{index}]")
        for field in ("name", "owner", "address_space"):
            if type(entry[field]) is not str or not entry[field]:
                raise ValueError(f"composition range {field} must be exact non-empty text")
        if entry["address_space"] != "raw":
            raise ValueError("composition range address space must be raw")
        _exact_int(entry["start"], f"composition range {index}.start")
        _exact_int(entry["end"], f"composition range {index}.end")
        if entry["start"] < 0 or entry["end"] <= entry["start"]:
            raise ValueError("composition range bounds are invalid")
    validate_cave_hook_overlaps(list(ranges), [], ())


def validate_manifest(manifest: dict[str, object]) -> None:
    _known_keys(manifest, MANIFEST_KEYS, "Full Heal manifest")
    for field in ("enabled", "catalog_hidden", "catalog_enabled", "expanded_fail_closed"):
        _exact_bool(manifest[field], f"Full Heal manifest.{field}")
    if manifest["enabled"] is not False or manifest["catalog_hidden"] is not True or manifest["catalog_enabled"] is not False:
        raise ValueError("Full Heal candidate must remain disabled and catalog-hidden")
    if manifest["expanded_fail_closed"] is not True:
        raise ValueError("Full Heal Expanded modes must remain fail-closed")
    if manifest["runtime_status"] != RUNTIME_STATUS:
        raise ValueError("Full Heal runtime status must remain pending")
    _strict_structure(manifest["allowed_modes"], ["collection_progression", "immediate_fixed"], "allowed_modes")
    _strict_structure(manifest["unsupported_patch_modes"], ["experimental_expanded_256", "experimental_expanded_256_progression"], "unsupported_patch_modes")
    _strict_structure(manifest["dependencies"], ["vv5_enable_origins_exclusive_features"], "dependencies")
    _strict_structure(manifest["source"], {
        "stock_sha256": STOCK_SHA256,
        "active_base": "data/vv5_origins_feature.json",
        "active_base_sha256": ACTIVE_BASE_SHA256,
        "active_payload_sha256": ACTIVE_PAYLOAD_SHA256,
        "source_hash_rule": CANONICAL_SOURCE_HASH_RULE,
        "model_sha256": FULL_HEAL_MODEL_SHA256,
    }, "source")
    source = manifest["source"]
    _validate_hash(ACTIVE_BASE, ACTIVE_BASE_SHA256, "active base")
    if sha(ACTIVE_BASE.read_bytes()) != source["active_base_sha256"]:
        raise ValueError("active base source hash is not exact")
    _validate_hash(FULL_HEAL_MODEL_PATH, FULL_HEAL_MODEL_SHA256, "Full Heal model", source_text=True)
    _strict_structure(manifest["stock_fingerprint"], STOCK_FINGERPRINT, "stock_fingerprint")
    _known_keys(manifest["record_contract"], set(record_contract()), "record_contract")
    _strict_structure(manifest["record_contract"], record_contract(), "record_contract")
    if "0x1CE1" in json.dumps(manifest["record_contract"], sort_keys=True):
        raise ValueError("unproved +0x1CE1 must not appear in the Full Heal record contract")
    _known_keys(manifest["native_callbacks"], set(callback_contract()), "native_callbacks")
    _strict_structure(manifest["native_callbacks"], callback_contract(), "native_callbacks")
    _known_keys(manifest["native_routing"], NATIVE_KEYS, "native_routing")
    _strict_structure(manifest["native_routing"]["patches"], [], "native_routing.patches")
    _strict_structure(manifest["native_routing"]["emitted_hooks"], [], "native_routing.emitted_hooks")
    _strict_structure(manifest["native_routing"]["candidate_caves"], [], "native_routing.candidate_caves")
    _strict_structure(manifest["native_routing"]["candidate_hooks"], [], "native_routing.candidate_hooks")
    if manifest["native_routing"]["status"] != "disabled; no native output, hooks, or catalog choice":
        raise ValueError("native output status is not disabled")
    _known_keys(manifest["transaction"], set(transaction_contract()), "transaction")
    _strict_structure(manifest["transaction"], transaction_contract(), "transaction")
    _known_keys(manifest["messages"], set(message_contract()), "messages")
    _strict_structure(manifest["messages"], message_contract(), "messages")
    composition = manifest["composition_guard"]
    _known_keys(composition, COMPOSITION_KEYS, "composition_guard")
    _strict_structure(composition["base_parent"], {
        "feature": "vv5_enable_origins_exclusive_features",
        "manifest": "data/vv5_origins_feature.json",
        "manifest_sha256": ACTIVE_BASE_SHA256,
        "payload_sha256": ACTIVE_PAYLOAD_SHA256,
    }, "composition_guard.base_parent")
    _strict_structure(composition["ui_chain"], {
        "feature": "vv5_ui_confirmation_candidate",
        "builder": "scripts/build_vv5_ui_confirmation_candidate.py",
        "builder_sha256": UI_BUILDER_SHA256,
        "model": "src/vv5_individual_transactions.py",
        "model_sha256": UI_MODEL_SHA256,
        "status": "disabled; native patches and emitted hooks remain empty",
    }, "composition_guard.ui_chain")
    _strict_structure(composition["full_mastery"], {
        "feature": "vv5_full_mastery_all_stage_a_candidate",
        "map": "data/candidates/vv5_full_mastery_all_candidate_map.json",
        "map_sha256": FULL_MASTERY_MAP_SHA256,
        "parent_hashes": FULL_MASTERY_PARENT_HASHES,
        "owned_range": "0xF2000-0xF4000",
    }, "composition_guard.full_mastery")
    _strict_structure(composition["running"], {
        "feature": "vv5_individual_grant_running_candidate",
        "map": "data/candidates/vv5_individual_running_candidate_map.json",
        "map_sha256": RUNNING_MAP_SHA256,
        "parent_hash": FULL_MASTERY_PARENT_HASHES["collection_progression"],
        "owned_range": "0xF4000-0xF6000",
    }, "composition_guard.running")
    _strict_structure(composition["full_heal"], {
        "feature": "vv5_full_heal_cure_all_reference_contract",
        "status": "disabled; no candidate bytes claimed",
        "owned_range": [],
    }, "composition_guard.full_heal")
    if composition["stock_sha256"] != STOCK_SHA256:
        raise ValueError("composition stock hash is not exact")
    _validate_ranges(composition["ranges"])
    _validate_hash(UI_BUILDER_PATH, UI_BUILDER_SHA256, "UI builder", source_text=True)
    _validate_hash(UI_MODEL_PATH, UI_MODEL_SHA256, "UI transaction model", source_text=True)
    _validate_hash(FULL_MASTERY_MAP_PATH, FULL_MASTERY_MAP_SHA256, "Full Mastery map")
    _validate_hash(FULL_MASTERY_FEATURE_PATH, FULL_MASTERY_FEATURE_SHA256, "Full Mastery feature")
    _validate_hash(RUNNING_MAP_PATH, RUNNING_MAP_SHA256, "Running map")
    ui = build_ui_manifest()
    if ui["enabled"] is not False or ui["catalog_hidden"] is not True or ui["catalog_enabled"] is not False:
        raise ValueError("Full Heal composition requires the UI chain to remain disabled and hidden")
    if ui["native_routing"]["patches"] != [] or ui["native_routing"]["emitted_hooks"] != []:
        raise ValueError("Full Heal composition cannot accept UI native output")
    _known_keys(manifest["implementation"], IMPLEMENTATION_KEYS, "implementation")
    _strict_structure(manifest["implementation"], {
        "transaction_engine": "src/vv5_full_heal.py",
        "native_writer_policy": "unproven callbacks only; no native writes, readbacks, rollback, hooks, or output",
        "save_policy": "no save reads or writes are performed",
        "catalog_policy": "catalog-hidden and disabled; no catalog choice is emitted",
    }, "implementation")


def build_manifest() -> dict[str, object]:
    manifest = {
        "id": "vv5_full_heal_cure_all_reference_contract",
        "game_id": "vv5",
        "name": "DISABLED Candidate: VV5 Full Heal / Cure All",
        "enabled": False,
        "catalog_hidden": True,
        "catalog_enabled": False,
        "runtime_status": RUNTIME_STATUS,
        "allowed_modes": ["collection_progression", "immediate_fixed"],
        "unsupported_patch_modes": ["experimental_expanded_256", "experimental_expanded_256_progression"],
        "expanded_fail_closed": True,
        "dependencies": ["vv5_enable_origins_exclusive_features"],
        "source": {
            "stock_sha256": STOCK_SHA256,
            "active_base": "data/vv5_origins_feature.json",
            "active_base_sha256": ACTIVE_BASE_SHA256,
            "active_payload_sha256": ACTIVE_PAYLOAD_SHA256,
            "source_hash_rule": CANONICAL_SOURCE_HASH_RULE,
            "model_sha256": FULL_HEAL_MODEL_SHA256,
        },
        "stock_fingerprint": STOCK_FINGERPRINT,
        "record_contract": record_contract(),
        "native_callbacks": callback_contract(),
        "native_routing": {
            "patches": [],
            "emitted_hooks": [],
            "candidate_caves": [],
            "candidate_hooks": [],
            "status": "disabled; no native output, hooks, or catalog choice",
        },
        "composition_guard": {
            "stock_sha256": STOCK_SHA256,
            "base_parent": {
                "feature": "vv5_enable_origins_exclusive_features",
                "manifest": "data/vv5_origins_feature.json",
                "manifest_sha256": ACTIVE_BASE_SHA256,
                "payload_sha256": ACTIVE_PAYLOAD_SHA256,
            },
            "ui_chain": {
                "feature": "vv5_ui_confirmation_candidate",
                "builder": "scripts/build_vv5_ui_confirmation_candidate.py",
                "builder_sha256": UI_BUILDER_SHA256,
                "model": "src/vv5_individual_transactions.py",
                "model_sha256": UI_MODEL_SHA256,
                "status": "disabled; native patches and emitted hooks remain empty",
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
                "feature": "vv5_full_heal_cure_all_reference_contract",
                "status": "disabled; no candidate bytes claimed",
                "owned_range": [],
            },
            "ranges": list(KNOWN_OCCUPIED_RANGES),
        },
        "transaction": transaction_contract(),
        "messages": message_contract(),
        "implementation": {
            "transaction_engine": "src/vv5_full_heal.py",
            "native_writer_policy": "unproven callbacks only; no native writes, readbacks, rollback, hooks, or output",
            "save_policy": "no save reads or writes are performed",
            "catalog_policy": "catalog-hidden and disabled; no catalog choice is emitted",
        },
    }
    validate_manifest(manifest)
    return manifest


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    OUTPUT_MANIFEST.write_text(json.dumps(build_manifest(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT_MANIFEST), "sha256": sha(OUTPUT_MANIFEST.read_bytes())}, indent=2))


if __name__ == "__main__":
    main()
