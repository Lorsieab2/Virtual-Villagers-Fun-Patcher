from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from native_statistics_mutation_evidence import (  # noqa: E402
    EXPECTED_STOCK,
    REQUIRED_REQUIREMENTS,
    validate_contract,
    validate_export_manifest,
)


def _receipt(game: str, requirement: str, proof: dict | None = None) -> dict:
    return {
        "id": f"{game}.{requirement}.receipt",
        "requirement": requirement,
        "status": "verified",
        "synthetic": False,
        "stale": False,
        "source_sha256": EXPECTED_STOCK[game]["sha256"],
        "proof": proof or {},
        "regions": [],
    }


def _complete_proof(requirement: str) -> dict:
    safe = {
        "routine_va": "0x700000",
        "call_convention": "__thiscall(this, skeleton, context) -> bool",
        "return_abi": "AL success; no-success leaves counter unchanged",
        "success_boundary": True,
        "counter_field_offset": "0x1C",
        "exactly_once_guard": True,
        "not_withdrawn_delayed_retirement": True,
        "duplicate_semantics": "same skeleton success is a no-op after the saved identity marker",
        "failed_pickup_nonmutation": True,
        "exactly_once": True,
        "update_routine_va": "0x700010",
        "field_offset": "0x20",
        "semantics": "persisted_lifetime_maximum",
        "native_update": True,
        "readback_postverify": True,
        "save_scoped": True,
        "baseline_field_offset": "0x600000",
        "initialized_marker_offset": "0x600004",
        "dedicated": True,
        "owner": "native_statistics_mutation",
        "atomic_pair": True,
        "overlap_regions": [],
        "not_origins_reserved": True,
        "load_routine_va": "0x700020",
        "save_routine_va": "0x700030",
        "baseline_and_marker_same_transaction": True,
        "field_roundtrip": True,
        "reload_round_trip": True,
        "offline_catchup": True,
        "idempotent": True,
        "duplicate_migration_noop": True,
        "unchanged_on_failed_load": True,
        "no_partial_marker": True,
        "no_partial_baseline": True,
        "stock_import": True,
        "expanded_reload": True,
        "expanded_offline_catchup": True,
        "record_bounds": True,
        "hook_guard_verified": True,
        "hook_cave_no_overlap": True,
        "wrong_hook_rejected": True,
        "stock_mode_noop": True,
        "composition_checked": True,
        "ownership": "dedicated statistics mutation cave",
        "runtime_receipt_sha256": "A" * 64,
        "player_receipt_sha256": "B" * 64,
        "runtime_confirmed": True,
        "player_confirmed": True,
    }
    if requirement == "stock_fingerprint":
        return {
            "exe_size": 831488,
            "exe_sha256": "A" * 64,
            "full_folder_sha256": "C" * 64,
            "full_folder_manifest_sha256": "D" * 64,
            "full_folder_file_count": 100,
            "full_folder_complete": True,
        }
    return {key: value for key, value in safe.items() if key in {
        "earliest_successful_skeleton_pickup_abi": {
            "routine_va", "call_convention", "return_abi", "success_boundary",
            "counter_field_offset", "exactly_once_guard", "not_withdrawn_delayed_retirement",
        },
        "buried_exactly_once": {
            "success_boundary", "duplicate_semantics", "failed_pickup_nonmutation",
            "exactly_once", "counter_field_offset",
        },
        "oldest_lifetime_max_updater": {
            "update_routine_va", "field_offset", "semantics", "native_update",
            "readback_postverify", "save_scoped",
        },
        "memorial_storage_ownership": {
            "baseline_field_offset", "initialized_marker_offset", "dedicated", "owner",
            "atomic_pair", "overlap_regions", "not_origins_reserved",
        },
        "atomic_save_load_serializer": {
            "load_routine_va", "save_routine_va", "atomic_pair",
            "baseline_and_marker_same_transaction", "field_roundtrip",
        },
        "reload_offline_catchup_idempotence": {
            "reload_round_trip", "offline_catchup", "idempotent", "duplicate_migration_noop",
        },
        "failed_load_nonmutation": {
            "unchanged_on_failed_load", "no_partial_marker", "no_partial_baseline",
        },
        "expanded_256_compatibility": {
            "stock_import", "expanded_reload", "expanded_offline_catchup", "record_bounds",
        },
        "hook_cave_composition": {
            "hook_guard_verified", "hook_cave_no_overlap", "wrong_hook_rejected",
            "stock_mode_noop", "composition_checked", "ownership",
        },
        "runtime_player_evidence": {
            "runtime_receipt_sha256", "player_receipt_sha256", "runtime_confirmed", "player_confirmed",
        },
    }[requirement]}


class NativeStatisticsMutationEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = json.loads(
            (ROOT / "data" / "native_statistics_mutation_evidence.json").read_text(
                encoding="utf-8"
            )
        )

    def test_checked_in_contract_is_structural_stop_and_never_publishable(self) -> None:
        result = validate_contract(self.data)
        self.assertTrue(result.schema_valid)
        self.assertFalse(result.evidence_complete)
        self.assertFalse(result.publication_allowed)
        self.assertIn("vv3 full-folder fingerprint is not verified", result.errors)
        self.assertIn("vv5.runtime_player_evidence is not verified", result.errors)

    def test_exact_stock_fingerprints_are_pinned(self) -> None:
        for game, expected in EXPECTED_STOCK.items():
            self.assertEqual(self.data["games"][game]["stock"]["size"], expected["size"])
            self.assertEqual(self.data["games"][game]["stock"]["sha256"], expected["sha256"])
        broken = copy.deepcopy(self.data)
        broken["games"]["vv4"]["stock"]["sha256"] = "0" * 64
        result = validate_contract(broken)
        self.assertIn("vv4 executable SHA-256 is not exact", result.errors)

    def test_synthetic_receipt_is_rejected(self) -> None:
        broken = copy.deepcopy(self.data)
        receipt = _receipt("vv3", "buried_exactly_once")
        receipt["synthetic"] = True
        broken["games"]["vv3"]["receipts"] = [receipt]
        result = validate_contract(broken)
        self.assertIn("vv3 receipt vv3.buried_exactly_once.receipt is synthetic", result.errors)

    def test_duplicate_receipt_id_is_rejected(self) -> None:
        broken = copy.deepcopy(self.data)
        receipt = _receipt("vv4", "buried_exactly_once")
        broken["games"]["vv4"]["receipts"] = [receipt, copy.deepcopy(receipt)]
        result = validate_contract(broken)
        self.assertIn("vv4 duplicate evidence receipt vv4.buried_exactly_once.receipt", result.errors)

    def test_overlapping_hook_and_cave_regions_are_rejected(self) -> None:
        broken = copy.deepcopy(self.data)
        first = _receipt("vv5", "hook_cave_composition", _complete_proof("hook_cave_composition"))
        second = _receipt("vv5", "runtime_player_evidence", _complete_proof("runtime_player_evidence"))
        first["regions"] = [{"kind": "hook", "start": "0x700000", "length": 16}]
        second["regions"] = [{"kind": "cave", "start": "0x70000C", "length": 32}]
        broken["games"]["vv5"]["receipts"] = [first, second]
        result = validate_contract(broken)
        self.assertTrue(any("evidence regions overlap" in error for error in result.errors))

    def test_stale_receipt_and_wrong_source_fingerprint_are_rejected(self) -> None:
        broken = copy.deepcopy(self.data)
        receipt = _receipt("vv3", "buried_exactly_once")
        receipt["stale"] = True
        receipt["source_sha256"] = "F" * 64
        broken["games"]["vv3"]["receipts"] = [receipt]
        result = validate_contract(broken)
        self.assertIn("vv3 receipt vv3.buried_exactly_once.receipt is stale", result.errors)
        self.assertIn("vv3 receipt vv3.buried_exactly_once.receipt has the wrong source fingerprint", result.errors)

    def test_withdrawn_delayed_retirement_hook_is_rejected(self) -> None:
        broken = copy.deepcopy(self.data)
        proof = _complete_proof("earliest_successful_skeleton_pickup_abi")
        proof["hook_offset"] = "0x5F45B"
        receipt = _receipt("vv3", "earliest_successful_skeleton_pickup_abi", proof)
        broken["games"]["vv3"]["receipts"] = [receipt]
        result = validate_contract(broken)
        self.assertTrue(any("reuses withdrawn hook 0x5f45b" in error for error in result.errors))

    def test_origins_reserve_reuse_is_rejected(self) -> None:
        broken = copy.deepcopy(self.data)
        proof = _complete_proof("memorial_storage_ownership")
        proof["baseline_field_offset"] = "0x4D6E10"
        receipt = _receipt("vv4", "memorial_storage_ownership", proof)
        broken["games"]["vv4"]["receipts"] = [receipt]
        result = validate_contract(broken)
        self.assertTrue(any("reuses protected Origins field 0x4d6e10" in error for error in result.errors))

    def test_duplicate_requirement_evidence_ids_are_rejected(self) -> None:
        broken = copy.deepcopy(self.data)
        requirement = broken["games"]["vv5"]["requirements"][2]
        requirement["status"] = "verified"
        requirement["evidence_ids"] = ["vv5.same", "vv5.same"]
        result = validate_contract(broken)
        self.assertIn("vv5.buried_exactly_once has duplicate evidence ids", result.errors)

    def test_complete_evidence_still_cannot_publish_while_disabled(self) -> None:
        complete = copy.deepcopy(self.data)
        for game in ("vv3", "vv4", "vv5"):
            stock = complete["games"][game]["stock"]
            stock["full_folder"] = {
                "status": "verified",
                "sha256": "C" * 64,
                "file_count": 100,
                "manifest_sha256": "D" * 64,
            }
            receipts = []
            for requirement in REQUIRED_REQUIREMENTS:
                receipt_id = f"{game}.{requirement}.receipt"
                receipts.append(_receipt(game, requirement, _complete_proof(requirement)))
                for item in complete["games"][game]["requirements"]:
                    if item["id"] == requirement:
                        item["status"] = "verified"
                        item["evidence_ids"] = [receipt_id]
            stock_proof = next(
                receipt["proof"]
                for receipt in receipts
                if receipt["requirement"] == "stock_fingerprint"
            )
            stock_proof["exe_size"] = stock["size"]
            stock_proof["exe_sha256"] = stock["sha256"]
            stock["full_folder"]["sha256"] = stock_proof["full_folder_sha256"]
            stock["full_folder"]["manifest_sha256"] = stock_proof["full_folder_manifest_sha256"]
            stock["full_folder"]["file_count"] = stock_proof["full_folder_file_count"]
            stock["full_folder"]["status"] = "verified"
            stock["full_folder"]["sha256"] = "C" * 64
            stock["full_folder"]["manifest_sha256"] = "D" * 64
            complete["games"][game]["receipts"] = receipts
        result = validate_contract(complete)
        self.assertTrue(result.evidence_complete, result.errors)
        self.assertFalse(result.publication_allowed)

    def test_existing_statistics_catalog_has_no_native_mutation_entry(self) -> None:
        manifest = json.loads(
            (ROOT / "data" / "statistics_features.json").read_text(encoding="utf-8")
        )
        self.assertEqual(validate_export_manifest(manifest), ())
        self.assertFalse(
            any("native_statistics_mutation" in str(feature.get("id", "")) for feature in manifest["features"])
        )


if __name__ == "__main__":
    unittest.main()

