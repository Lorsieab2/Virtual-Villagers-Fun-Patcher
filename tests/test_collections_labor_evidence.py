from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from native_absent_feature_evidence import (  # noqa: E402
    GAME_IDS,
    EXPECTED_JOB_ORDER,
    EXPECTED_STOCK,
    FEATURE_SPECS,
    validate_contract,
)


CONTRACT_PATHS = {
    "complete_all_collections": ROOT / "data" / "complete_all_collections_evidence.json",
    "reset_all_collections": ROOT / "data" / "reset_all_collections_evidence.json",
    "equal_division": ROOT / "data" / "equal_division_evidence.json",
}


def _load(feature: str) -> dict:
    return json.loads(CONTRACT_PATHS[feature].read_text(encoding="utf-8"))


def _receipt(game: str, requirement: str, proof: dict) -> dict:
    return {
        "id": f"{game}.{requirement}.receipt",
        "requirement": requirement,
        "status": "verified",
        "synthetic": False,
        "stale": False,
        "source_sha256": EXPECTED_STOCK[game]["sha256"],
        "proof": proof,
        "regions": [],
    }


def _common_proof(game: str, requirement: str, feature: str) -> dict:
    stock = EXPECTED_STOCK[game]
    proofs = {
        "stock_fingerprint": {
            "exe_size": stock["size"],
            "exe_sha256": stock["sha256"],
            "full_folder_sha256": "A" * 64,
            "full_folder_manifest_sha256": "B" * 64,
            "full_folder_file_count": 100,
            "full_folder_complete": True,
        },
        "save_reload_catchup_idempotence": {
            "save_roundtrip": True,
            "reload_roundtrip": True,
            "offline_catchup": True,
            "idempotent": True,
            "failed_load_nonmutation": True,
        },
        "hook_cave_composition": {
            "hook_guard_verified": True,
            "wrong_hook_rejected": True,
            "regions_nonoverlap": True,
            "stock_mode_noop": True,
            "composition_checked": True,
            "checked_features": list(FEATURE_SPECS[feature]["composition"]),
        },
        "runtime_player_evidence": {
            "runtime_receipt_sha256": "C" * 64,
            "player_receipt_sha256": "D" * 64,
            "runtime_confirmed": True,
            "player_confirmed": True,
        },
    }
    if requirement in proofs:
        return proofs[requirement]
    if feature == "complete_all_collections":
        return {
            "collection_table_geometry": {
                "table_address": "0x700000",
                "entry_count": 3,
                "entry_stride": 8,
                "entry_ids_in_order": [0, 1, 2],
                "table_bounds_verified": True,
            },
            "missing_entry_predicate": {
                "routine_va": "0x700100",
                "call_convention": "__thiscall(manager, entry_id) -> bool",
                "return_abi": "AL true means missing",
                "missing_semantics": "exact absent flag",
                "present_semantics": "already present is false",
                "all_entries_tested": True,
            },
            "native_add_complete_writer": {
                "routine_va": "0x700200",
                "call_convention": "__thiscall(manager, entry_id)",
                "return_abi": "AL success",
                "writer_kind": "native collection entry add",
                "native_postreadback": True,
            },
            "completion_effects_separation": {
                "completion_route_proved": True,
                "population_bonus_not_completion": True,
                "award_dispatcher_not_completion": True,
                "rewards_triggered": True,
                "goals_triggered": True,
                "per_game_effects_enumerated": True,
            },
            "duplicate_reward_trophy_stat_notification": {
                "duplicate_noop": True,
                "reward_once": True,
                "goal_once": True,
                "trophy_once": True,
                "stat_once": True,
                "notification_once": True,
                "dispatch_order": ["entry", "collection", "reward", "notification"],
            },
            "confirmation_reacquire_charge": {
                "dry_run": True,
                "confirmation_idok": True,
                "identity_reacquire": True,
                "postverify": True,
                "charge_semantics": "zero_cost",
                "charge_once_or_zero": True,
                "no_charge_on_noop": True,
                "no_charge_on_failure": True,
            },
        }[requirement]
    if feature == "reset_all_collections":
        return {
            "collection_table_geometry": {
                "table_address": "0x700000",
                "entry_count": 3,
                "entry_stride": 8,
                "entry_ids_in_order": [0, 1, 2],
                "table_bounds_verified": True,
            },
            "present_entry_predicate": {
                "routine_va": "0x700100",
                "call_convention": "__thiscall(manager, entry_id) -> bool",
                "return_abi": "AL true means present",
                "present_semantics": "exact present flag",
                "absent_semantics": "already absent is false",
                "all_entries_tested": True,
            },
            "native_reset_writer": {
                "routine_va": "0x700200",
                "call_convention": "__thiscall(manager, entry_id)",
                "return_abi": "AL success",
                "writer_kind": "native collection entry reset",
                "native_postreadback": True,
            },
            "reset_effects_separation": {
                "reset_route_proved": True,
                "population_bonus_not_reset": True,
                "award_dispatcher_not_reset": True,
                "per_game_effects_enumerated": True,
            },
            "duplicate_reset_reward_goal_notification": {
                "duplicate_noop": True,
                "reward_reset_once": True,
                "goal_reset_once": True,
                "trophy_reset_once": True,
                "stat_once": True,
                "notification_once": True,
                "dispatch_order": ["entry", "collection", "reward", "goal", "notification"],
            },
            "confirmation_reacquire_charge": {
                "dry_run": True,
                "confirmation_idok": True,
                "identity_reacquire": True,
                "postverify": True,
                "charge_semantics": "one_charge",
                "charge_once_or_zero": True,
                "no_charge_on_noop": True,
                "no_charge_on_failure": True,
            },
        }[requirement]
    jobs = [{"id": job_id, "name": name} for job_id, name in EXPECTED_JOB_ORDER[game]]
    return {
        "villager_record_geometry": {
            "record_base": "0x700000",
            "record_count": 150,
            "record_stride": 100,
            "physical_order": "ascending physical slot",
            "resolver_abi": "__thiscall(manager, index) -> record*",
        },
        "sex_field_encoding": {
            "field_offset": "0x100",
            "male_value": 0,
            "female_value": 1,
            "encoding_complete": True,
            "unknown_sex_policy": "skip and report",
        },
        "eligibility_predicate": {
            "active_field": "record+active",
            "living_field": "record+signed_health",
            "status_field": "record+status",
            "current_faction_field": "record+faction" if game == "vv5" else "not_applicable",
            "predicate_order": ["current_faction", "active", "living", "status"] if game == "vv5" else ["active", "living", "status"],
            "vv5_faction_first": game == "vv5",
            "unproved_1ce1_excluded": True,
            "vv3_tribal_chief_policy": "exclude" if game == "vv3" else "not_applicable",
        },
        "job_table_policy": {
            "assignment_target": "preference_selector",
            "jobs": jobs,
            "parenting_policy": "participates in the deterministic cycle",
            "devotion_policy": "participates" if game == "vv5" else "not present",
            "complete_order_verified": True,
        },
        "deterministic_physical_cycle": {
            "physical_slot_order": "ascending",
            "cycle_order": [job_id for job_id, _name in EXPECTED_JOB_ORDER[game]],
            "remainder_policy": "first physical eligible slots receive remainder",
            "tie_policy": "physical slot order",
            "unknown_sex_policy": "skip and report",
            "deterministic": True,
            "repeat_noop": True,
        },
        "native_job_setter_effects": {
            "setter_va": "0x700200",
            "setter_abi": "__thiscall(record, job_id) -> bool",
            "readback_va": "0x700300",
            "readback_abi": "__thiscall(record) -> job_id",
            "action_queue_effect": "enumerated",
            "notification_effect": "enumerated",
            "stat_effect": "enumerated",
            "save_effect": "enumerated",
            "postverify": True,
        },
        "repeat_transaction_rollback": {
            "dry_run": True,
            "identity_reacquire": True,
            "repeat_noop": True,
            "write_order": "physical slot order",
            "rollback_truth": "explicitly verified",
            "partial_write_disclosure": "verified no partial writes",
            "funds_semantics": "zero_cost",
        },
    }[requirement]


def _complete(feature: str) -> dict:
    data = _load(feature)
    for game in FEATURE_SPECS[feature].get("game_ids", GAME_IDS):
        game_record = data["games"][game]
        game_record["stock"]["full_folder"] = {
            "status": "verified",
            "sha256": "A" * 64,
            "file_count": 100,
            "manifest_sha256": "B" * 64,
        }
        receipts = []
        for requirement in FEATURE_SPECS[feature]["requirements"]:
            receipt = _receipt(game, requirement, _common_proof(game, requirement, feature))
            receipts.append(receipt)
            item = next(item for item in game_record["requirements"] if item["id"] == requirement)
            item["status"] = "verified"
            item["evidence_ids"] = [receipt["id"]]
        game_record["receipts"] = receipts
    return data


class CollectionsLaborEvidenceTests(unittest.TestCase):
    def test_checked_in_contracts_are_structural_stops(self) -> None:
        for feature in CONTRACT_PATHS:
            with self.subTest(feature=feature):
                result = validate_contract(_load(feature), feature)
                self.assertTrue(result.schema_valid)
                self.assertFalse(result.evidence_complete)
                self.assertFalse(result.publication_allowed)
                self.assertTrue(any("full-folder fingerprint is not verified" in error for error in result.errors))

    def test_complete_evidence_still_cannot_publish_while_disabled(self) -> None:
        for feature in CONTRACT_PATHS:
            with self.subTest(feature=feature):
                result = validate_contract(_complete(feature), feature)
                self.assertTrue(result.evidence_complete, result.errors)
                self.assertFalse(result.publication_allowed)

    def test_exact_stock_fingerprints_and_job_orders_are_pinned(self) -> None:
        labor = _load("equal_division")
        for game in GAME_IDS:
            expected = EXPECTED_STOCK[game]
            self.assertEqual(labor["games"][game]["stock"]["sha256"], expected["sha256"])
            jobs = [(item["id"], item["name"]) for item in labor["games"][game]["policy"]["reviewed_preference_order"]]
            self.assertEqual(tuple(jobs), EXPECTED_JOB_ORDER[game])

    def test_synthetic_stale_and_wrong_source_receipts_are_rejected(self) -> None:
        broken = _complete("complete_all_collections")
        receipt = broken["games"]["vv3"]["receipts"][1]
        receipt["synthetic"] = True
        receipt["stale"] = True
        receipt["source_sha256"] = "F" * 64
        result = validate_contract(broken, "complete_all_collections")
        self.assertTrue(any("is synthetic" in error for error in result.errors))
        self.assertTrue(any("is stale" in error for error in result.errors))
        self.assertTrue(any("wrong source fingerprint" in error for error in result.errors))

    def test_duplicate_missing_and_overlapping_evidence_is_rejected(self) -> None:
        broken = _complete("equal_division")
        game = broken["games"]["vv4"]
        duplicate = copy.deepcopy(game["receipts"][0])
        game["receipts"].append(duplicate)
        game["requirements"][1]["evidence_ids"] = ["missing.receipt", "missing.receipt"]
        game["receipts"][2]["regions"] = [{"kind": "hook", "start": "0x700000", "length": 16}]
        game["receipts"][3]["regions"] = [{"kind": "cave", "start": "0x700008", "length": 32}]
        result = validate_contract(broken, "equal_division")
        self.assertTrue(any("duplicate evidence receipt" in error for error in result.errors))
        self.assertTrue(any("duplicate evidence ids" in error for error in result.errors))
        self.assertTrue(any("references missing evidence" in error for error in result.errors))
        self.assertTrue(any("evidence regions overlap" in error for error in result.errors))

    def test_collection_population_bonus_and_dispatcher_are_not_completion(self) -> None:
        for forbidden in ("collection_population_bonus_only", "award_or_trophy_dispatcher_only"):
            broken = _complete("complete_all_collections")
            proof = broken["games"]["vv5"]["receipts"][3]["proof"]
            proof["writer_kind"] = forbidden
            result = validate_contract(broken, "complete_all_collections")
            self.assertTrue(any(f"relies on forbidden {forbidden}" in error for error in result.errors))

    def test_collection_charge_semantics_must_be_one_charge_or_zero_cost(self) -> None:
        broken = _complete("complete_all_collections")
        receipt = next(item for item in broken["games"]["vv3"]["receipts"] if item["requirement"] == "confirmation_reacquire_charge")
        receipt["proof"]["charge_semantics"] = "unknown"
        result = validate_contract(broken, "complete_all_collections")
        self.assertTrue(any("charge semantics must be one_charge or zero_cost" in error for error in result.errors))

    def test_reset_requires_goal_and_reward_reset_proof(self) -> None:
        broken = _complete("reset_all_collections")
        receipt = next(item for item in broken["games"]["vv5"]["receipts"] if item["requirement"] == "reset_effects_separation")
        receipt["proof"]["reset_route_proved"] = False
        result = validate_contract(broken, "reset_all_collections")
        self.assertTrue(any("reset_route_proved" in error for error in result.errors))
        duplicate = next(item for item in broken["games"]["vv5"]["receipts"] if item["requirement"] == "duplicate_reset_reward_goal_notification")
        duplicate["proof"]["goal_reset_once"] = False
        result = validate_contract(broken, "reset_all_collections")
        self.assertTrue(any("goal_reset_once" in error for error in result.errors))

    def test_vv5_faction_must_be_first_and_1ce1_is_forbidden(self) -> None:
        broken = _complete("equal_division")
        receipt = next(item for item in broken["games"]["vv5"]["receipts"] if item["requirement"] == "eligibility_predicate")
        receipt["proof"]["predicate_order"] = ["active", "current_faction", "living", "status"]
        receipt["proof"]["status_field"] = "0x1CE1"
        result = validate_contract(broken, "equal_division")
        self.assertIn("vv5 eligibility must evaluate current faction first", result.errors)
        self.assertTrue(any("reuses forbidden vv5_unproved_heathen_active_byte" in error for error in result.errors))

    def test_vv3_chief_and_parenting_devotion_policies_cannot_be_unresolved(self) -> None:
        broken = _complete("equal_division")
        eligibility = next(item for item in broken["games"]["vv3"]["receipts"] if item["requirement"] == "eligibility_predicate")
        eligibility["proof"]["vv3_tribal_chief_policy"] = "unresolved"
        jobs = next(item for item in broken["games"]["vv5"]["receipts"] if item["requirement"] == "job_table_policy")
        jobs["proof"]["parenting_policy"] = ""
        jobs["proof"]["devotion_policy"] = ""
        result = validate_contract(broken, "equal_division")
        self.assertIn("vv3 Tribal Chief policy is unresolved", result.errors)
        self.assertTrue(any("Parenting policy is missing" in error for error in result.errors))
        self.assertTrue(any("Devotion policy is missing" in error for error in result.errors))

    def test_nursery_divisor_parity_is_rejected_as_unrelated(self) -> None:
        broken = _complete("equal_division")
        receipt = next(item for item in broken["games"]["vv5"]["receipts"] if item["requirement"] == "native_job_setter_effects")
        receipt["proof"]["setter_va"] = "0x425FDF"
        receipt["regions"] = [{"kind": "hook", "start": "0x425FDF", "length": 5}]
        result = validate_contract(broken, "equal_division")
        self.assertTrue(any("vv5_nursery_divisor_parity" in error for error in result.errors))

    def test_no_catalog_or_patcher_enablement_exists(self) -> None:
        statistics = (ROOT / "data" / "statistics_features.json").read_text(encoding="utf-8")
        patcher = (ROOT / "src" / "vv_fun_patcher.py").read_text(encoding="utf-8")
        for feature in ("complete_all_collections", "reset_all_collections", "equal_division"):
            self.assertNotIn(feature, statistics)
            self.assertNotIn(feature, patcher)

    def test_schemas_are_disabled_and_feature_specific(self) -> None:
        for feature, filename in (
            ("complete_all_collections", "complete_all_collections_evidence.schema.json"),
            ("reset_all_collections", "reset_all_collections_evidence.schema.json"),
            ("equal_division", "equal_division_evidence.schema.json"),
        ):
            schema = json.loads((ROOT / "data" / filename).read_text(encoding="utf-8"))
            self.assertEqual(schema["properties"]["feature"]["const"], feature)
            self.assertFalse(schema["properties"]["enabled"]["const"])
            if feature in ("complete_all_collections", "reset_all_collections"):
                expected_label = "Complete All Collectibles" if feature == "complete_all_collections" else "Reset Collectibles"
                self.assertEqual(schema["properties"]["label"]["const"], expected_label)
                self.assertEqual(schema["properties"]["price_tech_points"]["const"], 1000000)

    def test_collectibles_composition_preserves_vv2_layout_boundary(self) -> None:
        for feature in ("complete_all_collections", "reset_all_collections"):
            data = _load(feature)
            vv2_policy = data["games"]["vv2"]["policy"]
            self.assertEqual(vv2_policy["expanded_256_policy"], "existing_256_no_relocation")
            for game in ("vv3", "vv4", "vv5"):
                policy = data["games"][game]["policy"]
                self.assertEqual(policy["expanded_256_policy"], "expanded_256_relocation_evidence_required")


if __name__ == "__main__":
    unittest.main()
