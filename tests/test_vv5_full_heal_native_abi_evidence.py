from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_vv5_full_heal_contract import build_manifest as build_full_heal  # noqa: E402
from build_vv5_ui_confirmation_candidate import build_manifest as build_ui  # noqa: E402
from validate_vv5_full_heal_native_abi_evidence import EVIDENCE_PATH, SCHEMA_PATH, validate_evidence  # noqa: E402


class VV5FullHealNativeAbiEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.record = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))

    def test_checked_in_gate_is_null_stop_and_existing_models_remain_reference_only(self) -> None:
        self.assertFalse(validate_evidence(self.record))
        self.assertTrue(SCHEMA_PATH.is_file())
        for key, expected in (("enabled", False), ("catalog_hidden", True), ("catalog_enabled", False), ("publication_ready", False), ("native_output", False)):
            self.assertIs(self.record[key], expected)
        self.assertEqual(build_ui()["individual_actions"].keys(), {"youth", "full_mastery", "running", "age_18"})
        full_heal = build_full_heal()
        self.assertEqual(full_heal["native_routing"]["patches"], [])
        self.assertEqual(full_heal["native_routing"]["candidate_hooks"], [])
        self.assertEqual(full_heal["composition_guard"]["full_heal"]["owned_range"], [])
        self.assertIn("unproven callbacks only", full_heal["implementation"]["native_writer_policy"])

    def test_record_gate_is_faction_first_and_unproved_offset_is_forbidden(self) -> None:
        contract = self.record["record_contract"]
        self.assertEqual(contract["read_order"], ["active", "faction_equals_zero", "positive_health", "native_sickness"])
        self.assertEqual(contract["faction_offset"], "0x1CEC")
        self.assertEqual(contract["forbidden_unproved_offset"], "0x1CE1")
        self.assertEqual(contract["exclusion_policy"]["never_read"], ["0x1CE1"])
        mutated = copy.deepcopy(self.record); mutated["record_contract"]["sickness_offset"] = "0x1CE1"
        with self.assertRaises(ValueError):
            validate_evidence(mutated)

    def test_types_flags_ranges_and_native_output_fail_closed(self) -> None:
        mutations = []
        for key, value in (("enabled", True), ("catalog_hidden", False), ("catalog_enabled", True), ("publication_ready", True), ("native_output", True)):
            item = copy.deepcopy(self.record); item[key] = value; mutations.append(item)
        item = copy.deepcopy(self.record); item["unexpected"] = 1; mutations.append(item)
        item = copy.deepcopy(self.record); item["folder_evidence"]["file_count"] = True; mutations.append(item)
        item = copy.deepcopy(self.record); item["native_abis"]["health_setter"]["target_health"] = 99; mutations.append(item)
        item = copy.deepcopy(self.record); item["native_abis"]["funds_account"]["price"] = 30000.0; mutations.append(item)
        item = copy.deepcopy(self.record); item["composition"]["full_heal_ranges"] = ["0x100-0x200"]; mutations.append(item)
        item = copy.deepcopy(self.record); item["composition"]["expanded_rejected"] = False; mutations.append(item)
        for mutated in mutations:
            with self.assertRaises(ValueError):
                validate_evidence(mutated)

    def test_complete_native_evidence_requires_every_abi_receipt_and_lifecycle(self) -> None:
        item = copy.deepcopy(self.record)
        folder_hash = "A" * 64
        item["folder_evidence"].update(authenticated=True, complete=True, file_count=10, total_size=1_000_000, manifest_sha256=folder_hash, receipt_sha256="B" * 64)
        item["record_contract"].update(sickness_offset="0x1234", sickness_semantic="exact nonzero means currently sick")
        for name in ("record_world_resolver", "sickness_clearer", "health_setter"):
            abi = item["native_abis"][name]
            abi.update(va="0x401000", stock_bytes="90", continuation_va="0x401001", calling_convention="thiscall", artifact_sha256="C" * 64)
            for key in abi:
                if key.endswith("_verified"):
                    abi[key] = True
        people = item["native_abis"]["people_cured"]
        people.update(increment_va="0x401100", readback_va="0x401200", stock_bytes="90", calling_convention="thiscall", artifact_sha256="D" * 64, stat_verified=True, trophy_behavior_verified=True, notification_behavior_verified=True)
        funds = item["native_abis"]["funds_account"]
        funds.update(getter_va="0x401300", deduction_va="0x401400", stock_bytes="90", calling_convention="thiscall", artifact_sha256="E" * 64, one_deduction_readback_verified=True)
        tx = item["transaction_evidence"]
        tx["folder_manifest_sha256"] = folder_hash
        for key in ("dry_run_artifact_sha256", "confirmation_artifact_sha256", "postverify_artifact_sha256", "partial_rollback_artifact_sha256"):
            tx[key] = "F" * 64
        for key in tx:
            if key.endswith("_verified"):
                tx[key] = True
        item["messages"]["singular_plural_verified"] = True
        ui = item["ui_lifecycle"]
        ui.update(windowed_receipt_sha256="1" * 64, fullscreen_receipt_sha256="2" * 64, owner_verified=True, centering_verified=True, fullscreen_restore_verified=True, child_destructor_verified=True)
        item["composition"].update(overlap_report_sha256="3" * 64, expanded_lifecycle_verified=True)
        self.assertTrue(validate_evidence(item))

        for path in (("native_abis", "sickness_clearer", "artifact_sha256"), ("native_abis", "people_cured", "trophy_behavior_verified"), ("transaction_evidence", "overlap_counts_both_verified"), ("ui_lifecycle", "fullscreen_restore_verified"), ("composition", "expanded_lifecycle_verified")):
            mutated = copy.deepcopy(item); target = mutated
            for key in path[:-1]: target = target[key]
            target[path[-1]] = None if path[-1].endswith("sha256") else False
            self.assertFalse(validate_evidence(mutated))


if __name__ == "__main__":
    unittest.main()
