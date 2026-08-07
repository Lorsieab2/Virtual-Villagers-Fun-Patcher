from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_full_heal_evidence_gate import (  # noqa: E402
    CONTRACT_PATH,
    EXPECTED_STOCK,
    EvidenceGateError,
    REPLACEMENT_LABEL,
    assert_enablement_blocked,
    contract_sha256,
    load_contract,
    validate_candidate_evidence,
)


class VV1VV2FullHealEvidenceGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = load_contract()

    def test_tracked_contract_is_disabled_empty_and_exactly_scoped(self) -> None:
        self.assertFalse(self.contract["enabled"])
        self.assertFalse(self.contract["catalog_enabled"])
        self.assertTrue(self.contract["catalog_hidden"])
        self.assertFalse(self.contract["native_output"])
        self.assertEqual(self.contract["status"], "STOP")
        self.assertEqual(self.contract["public_choices"], [])
        self.assertEqual(self.contract["evidence_records"], [])
        self.assertEqual(set(self.contract["games"]), {"vv1", "vv2"})
        self.assertEqual(self.contract["replacement_contract"]["label"], REPLACEMENT_LABEL)
        self.assertEqual(self.contract["replacement_contract"]["price"], 30000)
        self.assertTrue(self.contract["replacement_contract"]["overlap_counted_in_both"])
        self.assertEqual(self.contract["legacy_cure_policy"]["status"], "legacy-sickness-only")
        self.assertFalse(self.contract["legacy_cure_policy"]["is_full_heal_replacement"])

    def test_stock_fingerprints_are_exact_and_folder_inventory_is_required(self) -> None:
        for game_id, expected in EXPECTED_STOCK.items():
            self.assertEqual(self.contract["games"][game_id]["stock_executable"], expected)
        schema = self.contract["candidate_schema"]
        self.assertIn("folder_inventory", schema["required_paths"])
        self.assertEqual(schema["folder_inventory"]["scope"], "full-game-folder")
        self.assertTrue(schema["folder_inventory"]["complete"])
        self.assertTrue(schema["folder_inventory"]["all_dlls"])

    def test_exact_wording_is_natural_and_rejects_legacy_label(self) -> None:
        wording = self.contract["wording"]
        self.assertEqual(wording["label"], REPLACEMENT_LABEL)
        self.assertEqual(wording["no_deduction_suffix"], "No tech points have been deducted.")
        self.assertEqual(wording["plural_nouns"]["eligible_villager"]["one"], "eligible villager")
        self.assertEqual(wording["plural_nouns"]["eligible_villager"]["other"], "eligible villagers")
        self.assertEqual(wording["plural_nouns"]["partial_health_villager"]["one"], "partial-health villager")
        self.assertNotIn("Cure all Villagers", json.dumps(wording))

    def test_contract_sha256_is_stable_for_handoff(self) -> None:
        digest = contract_sha256()
        self.assertEqual(len(digest), 64)
        self.assertEqual(digest, digest.upper())
        self.assertEqual(CONTRACT_PATH, ROOT / "data" / "candidates" / "vv1_vv2_full_heal_evidence_gate.json")

    def test_candidate_missing_required_evidence_fails_closed(self) -> None:
        with self.assertRaisesRegex(EvidenceGateError, "candidate: missing required keys"):
            validate_candidate_evidence({})

    def test_candidate_wrong_stock_fingerprint_fails_closed(self) -> None:
        candidate = self._synthetic_candidate()
        candidate["stock"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(EvidenceGateError, "stock: does not match"):
            validate_candidate_evidence(candidate)

    def test_candidate_incomplete_full_folder_dll_inventory_fails_closed(self) -> None:
        candidate = self._synthetic_candidate()
        candidate["folder_inventory"]["all_dlls"] = False
        with self.assertRaisesRegex(EvidenceGateError, "folder_inventory.all_dlls"):
            validate_candidate_evidence(candidate)

    def test_candidate_raw_health_write_fails_closed(self) -> None:
        candidate = self._synthetic_candidate()
        candidate["native"]["raw_health_write"] = True
        with self.assertRaisesRegex(EvidenceGateError, "native.raw_health_write"):
            validate_candidate_evidence(candidate)

    def test_candidate_missing_overlap_counter_fails_closed(self) -> None:
        candidate = self._synthetic_candidate()
        del candidate["counters"]["overlap_counted_in_both"]
        with self.assertRaisesRegex(EvidenceGateError, "counters(?:\\.overlap_counted_in_both|: missing required keys: overlap_counted_in_both)"):
            validate_candidate_evidence(candidate)

    def test_candidate_non_idok_confirmation_fails_closed(self) -> None:
        candidate = self._synthetic_candidate()
        candidate["transaction"]["confirmation"]["non_idok_no_charge"] = False
        with self.assertRaisesRegex(EvidenceGateError, "transaction.confirmation.non_idok_no_charge"):
            validate_candidate_evidence(candidate)

    def test_candidate_non_exact_confirmation_abi_fails_closed(self) -> None:
        candidate = self._synthetic_candidate()
        candidate["transaction"]["confirmation"]["abi"] = "MessageBox return"
        with self.assertRaisesRegex(EvidenceGateError, "transaction.confirmation.abi"):
            validate_candidate_evidence(candidate)

    def test_candidate_missing_fullscreen_owner_validation_fails_closed(self) -> None:
        candidate = self._synthetic_candidate()
        candidate["fullscreen"]["same_process_validated"] = False
        with self.assertRaisesRegex(EvidenceGateError, "fullscreen.same_process_validated"):
            validate_candidate_evidence(candidate)

    def test_candidate_missing_identity_reacquisition_fails_closed(self) -> None:
        candidate = self._synthetic_candidate()
        candidate["transaction"]["identity_reacquisition"]["same_world_state"] = ""
        with self.assertRaisesRegex(EvidenceGateError, "transaction.identity_reacquisition.same_world_state"):
            validate_candidate_evidence(candidate)

    def test_candidate_preverify_deduction_fails_closed(self) -> None:
        candidate = self._synthetic_candidate()
        candidate["transaction"]["postverify_before_deduction"] = False
        with self.assertRaisesRegex(EvidenceGateError, "transaction.postverify_before_deduction"):
            validate_candidate_evidence(candidate)

    def test_candidate_rollback_claim_fails_closed(self) -> None:
        candidate = self._synthetic_candidate()
        candidate["transaction"]["failure"]["rollback_claim"] = "complete"
        with self.assertRaisesRegex(EvidenceGateError, "transaction.failure.rollback_claim"):
            validate_candidate_evidence(candidate)

    def test_candidate_stale_resource_label_fails_closed(self) -> None:
        candidate = self._synthetic_candidate()
        candidate["resource"]["legacy_label_absent"] = False
        with self.assertRaisesRegex(EvidenceGateError, "resource.legacy_label_absent"):
            validate_candidate_evidence(candidate)

    def test_candidate_missing_hook_cave_owner_fails_closed(self) -> None:
        candidate = self._synthetic_candidate()
        candidate["ownership"]["cave_owner"] = ""
        with self.assertRaisesRegex(EvidenceGateError, "ownership.cave_owner"):
            validate_candidate_evidence(candidate)

    def test_synthetic_evidence_fails_even_when_structure_is_complete(self) -> None:
        candidate = self._synthetic_candidate()
        candidate["evidence_origin"]["synthetic"] = True
        candidate["evidence_origin"]["repository_owned"] = False
        with self.assertRaisesRegex(EvidenceGateError, "candidate.evidence_origin.repository_owned"):
            validate_candidate_evidence(candidate)

    def test_enablement_is_always_blocked(self) -> None:
        candidate = self._synthetic_candidate()
        with self.assertRaisesRegex(EvidenceGateError, "STOP: VV1/VV2 Full Heal evidence gate is disabled"):
            assert_enablement_blocked(candidate)

    def test_gate_is_not_a_public_catalog_record(self) -> None:
        self.assertNotIn("vv1_vv2_full_heal_evidence_gate", self.contract["public_choices"])
        self.assertFalse(self.contract["native_output"])
        self.assertFalse((ROOT / "data" / "candidates" / "VVFP VV1 Full Heal Candidate.dll").exists())
        self.assertFalse((ROOT / "data" / "candidates" / "VVFP VV2 Full Heal Candidate.dll").exists())
        builds = ROOT / "data" / "builds.json"
        if builds.exists():
            self.assertNotIn("vv1_vv2_full_heal_evidence_gate", builds.read_text(encoding="utf-8"))
        loader = ROOT / "src" / "vv_fun_patcher.py"
        self.assertNotIn("vv1_vv2_full_heal_evidence_gate", loader.read_text(encoding="utf-8"))

    @staticmethod
    def _synthetic_candidate() -> dict[str, object]:
        """A deliberately synthetic complete shape; it must never validate."""

        wording = load_contract()["wording"]
        legacy = load_contract()["legacy_cure_policy"]
        return {
            "schema_version": 1,
            "game_id": "vv1",
            "status": "STOP",
            "enabled": False,
            "catalog_enabled": False,
            "catalog_hidden": True,
            "native_output": False,
            "evidence_origin": {
                "repository_owned": True,
                "synthetic": False,
                "method": "repository-owned disassembly/resource export",
                "review_status": "independent review pending",
            },
            "source_artifacts": [
                {"path": "research/stock-executables/Virtual Villagers - A New Home.exe", "kind": "stock-executable", "sha256": EXPECTED_STOCK["vv1"]["sha256"]},
                {"path": "native/export.txt", "kind": "native-disassembly-export", "sha256": "A" * 64},
            ],
            "stock": copy.deepcopy(EXPECTED_STOCK["vv1"]),
            "folder_inventory": {
                "scope": "full-game-folder",
                "complete": True,
                "all_dlls": True,
                "dll_count": 1,
                "dll_inventory_sha256": "B" * 64,
                "dlls": [{"path": "VVFP Origins Icons.dll", "size": 295936, "sha256": "C" * 64}],
            },
            "native": {
                "health_setter": {
                    "address": "0x401234",
                    "calling_convention": "thiscall",
                    "receiver": "ECX=record",
                    "arguments": "push reason; push 100",
                    "return_contract": "ret 8",
                    "target_value": 100,
                    "abi_verified": True,
                    "side_effects": ["native health state changes"],
                },
                "sickness_people_cured": {
                    "sickness_field": "+0x100",
                    "clear_route": "native sickness setter",
                    "people_cured_field": "+0x200",
                    "increment_timing": "after verified clear",
                    "postverify": "sickness 0",
                    "abi_verified": True,
                    "increment_per_verified_clear": True,
                },
                "raw_health_write": False,
                "postverify": {
                    "fresh_identity_reacquisition": "same record identity",
                    "health": "100",
                    "sickness": "0",
                    "before_deduction": True,
                },
            },
            "fullscreen": {
                "owner_hwnd_capture": "captured owner HWND before fullscreen transition",
                "is_window_validated": True,
                "same_process_validated": True,
                "monitor_work_area": "owner monitor work area",
                "center_clamp": "centered and clamped within work area",
                "leave_fullscreen": "recorded exact prior fullscreen/window state before dialog",
                "dialog_message_owner": "dialog and messages owned by the validated game HWND",
                "restore_window_state": "restored exact prior fullscreen/window state on close",
                "lifetime_cleanup": "destructor and uninstall release owner state and restore safely",
                "failure_no_mutation": True,
            },
            "eligibility": {
                "active": "active != 0",
                "living": "living record",
                "believer": "current believer",
                "golden_child": "explicit exclusion gate",
                "health_positive": "health > 0",
                "partial_health_range": "1..99",
                "health_100_preserved": True,
                "sickness_nonzero": "sickness != 0",
                "physical_enumeration": "physical order through native resolver",
            },
            "counters": {
                "predicted_sickness": "sickness != 0",
                "predicted_partial_health": "health in 1..99",
                "verified_sickness": "verified sickness clear",
                "verified_partial_health": "verified health 100",
                "overlap_counted_in_both": True,
                "prediction_before_deduction": True,
                "verified_before_deduction": True,
            },
            "transaction": {
                "confirmation": {"abi": "IDOK-only", "idok_only": True, "cancel_no_mutation": True, "non_idok_no_charge": True},
                "identity_reacquisition": {"same_selected_villager": "selected identity", "same_world_state": "manager/world identity", "boundaries": ["post-confirmation", "pre-write"], "identity_fields": "index and record identity"},
                "funds_recheck": True,
                "postverify_before_deduction": True,
                "deduction": {"price": 30000, "calls": 1, "after_postverify": True, "native_abi": "native tech writer"},
                "failure": {"no_charge": True, "partial_effects_disclosed": True, "rollback_claim": "not claimed", "failure_message": wording["failure"]},
            },
            "wording": wording,
            "resource": {"dialog_id": 201, "control_id": 1005, "label": REPLACEMENT_LABEL, "price_text": "30,000 tech points", "parent_sha256": "D" * 64, "candidate_sha256": "E" * 64, "candidate_size": 295936, "legacy_label_absent": True, "resource_202_unchanged": True},
            "ownership": {"hook_owner": "full-heal-owner", "cave_owner": "full-heal-owner", "resource_owner": "full-heal-owner", "composition_owner": "full-heal-owner", "parent_identity": "parent hash", "owned_ranges": ["0x100..0x200"], "removal_identity": "restore parent hash", "hook_preimage_sha256": "F" * 64, "cave_sha256": "0" * 64, "composition_order": ["parent", "full-heal-owner"], "expanded_rejected": True, "mode_fingerprint": "exact supported mode", "disjoint_ranges": True, "collision_fail_closed": True, "gong_island_unchanged": True, "legacy_route_dominated_before_price": True},
            "legacy_cure_policy": legacy,
        }


if __name__ == "__main__":
    unittest.main()
