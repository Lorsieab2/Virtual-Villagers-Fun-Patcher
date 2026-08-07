from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_vv5_ui_confirmation_candidate import build_manifest, validate_candidate_manifest  # noqa: E402
from validate_vv5_tech_detail_native_evidence import (  # noqa: E402
    EVIDENCE_PATH, SCHEMA_PATH, STOCK_SHA256, load_and_validate, validate_evidence,
)


class VV5TechDetailNativeEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.record = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))

    def test_pending_record_is_exact_disabled_and_ui_only_links_absent_gate(self) -> None:
        _, complete = load_and_validate()
        self.assertFalse(complete)
        self.assertTrue(SCHEMA_PATH.is_file())
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        contract_schema = schema["$defs"]["contract"]
        self.assertFalse(contract_schema["additionalProperties"])
        self.assertEqual(set(contract_schema["required"]), set(self.record["native_contract"]))
        for key, value in self.record["native_contract"].items():
            self.assertEqual(contract_schema["properties"][key]["const"], value)
        for key, value in (("enabled", False), ("catalog_hidden", True), ("catalog_enabled", False), ("publication_ready", False), ("native_output", False)):
            self.assertIs(self.record[key], value)
        manifest = build_manifest()
        self.assertEqual(set(manifest["individual_actions"]), {"youth", "full_mastery", "running", "age_18"})
        self.assertEqual(manifest["native_routing"]["patches"], [])
        self.assertEqual(manifest["native_routing"]["emitted_hooks"], [])
        self.assertEqual(manifest["native_evidence_gate"]["evidence_complete"], False)
        for field, value in (("evidence_complete", True), ("publication_ready", True), ("native_output", True)):
            mutated = copy.deepcopy(manifest); mutated["native_evidence_gate"][field] = value
            with self.assertRaises(ValueError):
                validate_candidate_manifest(mutated)

    def test_exact_stock_methods_and_unknown_candidate_route_are_pinned(self) -> None:
        contract = self.record["native_contract"]
        self.assertEqual((contract["resource"], contract["dimensions"], contract["local"]), ("0x6A", [96, 39], [137, 2]))
        self.assertEqual((contract["message"], contract["event"]), (8, 13))
        self.assertEqual(contract["tech_constructor_va"], "0x4405F0")
        self.assertEqual(contract["tech_handler_va"], "0x4415F0")
        self.assertEqual(contract["detail_draw_va"], "0x44B250")
        self.assertEqual(contract["detail_input_method_entry_va"], "0x44B560")
        self.assertEqual(contract["detail_input_method_entry_bytes"], "83EC44535556BD7F03000057BF580300")
        self.assertEqual(contract["detail_input_nonvolatile_saves"], ["EBX", "EBP", "ESI", "EDI"])
        self.assertEqual((contract["detail_input_stack_locals"], contract["detail_input_cleanup"]), ("0x44", "ret 0xC"))
        self.assertEqual((contract["detail_vtable_va"], contract["detail_destructor_va"], contract["detail_event_method_va"]), ("0x49A590", "0x44B9F0", "0x44BC20"))
        self.assertEqual((contract["candidate_callsite_va"], contract["candidate_callsite_raw"], contract["candidate_route_va"]), ("0x44BC20", "0x4BC20", "0x7B20C0"))
        self.assertEqual((contract["candidate_hook_preimage"], contract["candidate_hook_detour"], contract["candidate_continuation_va"]), ("83EC18A1A8974D00", "E99B643600909090", "0x44BC28"))
        self.assertEqual((contract["candidate_guard_message"], contract["candidate_guard_control_id"]), (8, 13))
        self.assertTrue(contract["offline_install_verified"])
        self.assertTrue(contract["offline_uninstall_verified"])
        self.assertFalse(contract["hot_uninstall_verified"])
        self.assertEqual(contract["detail_event_method_sha256"], "DE25D2B76DC7E6337F40F06CBF25FCDCEC411BD9D7F1E7DC78406C157501DC74")
        self.assertEqual((contract["detail_dispatcher_range"], contract["detail_dispatcher_size"], contract["detail_dispatcher_sha256"]), ("[0x4019B8,0x4019CF)", 23, "F2EB107944977E8CBCE7CAD450EC6D1D046880727EBDE36A939CF5DC5DDC907F"))
        self.assertFalse(contract["stock_xref_to_7B22C0"])
        self.assertFalse(contract["stock_xref_to_7B2600"])
        self.assertEqual((contract["rejected_candidate_window_flags_pointer_va"], contract["authenticated_window_flags_string_va"], contract["rejected_candidate_requested_symbol"]), ("0x7B2A64", "0x7B2A63", "DL_GetWindowFlags"))
        for field in ("factory_va", "ownership_va", "detail_input_method_entry_va"):
            mutated = copy.deepcopy(self.record)
            mutated["native_contract"][field] = "0x0"
            with self.assertRaises(ValueError):
                validate_evidence(mutated)

    def test_strict_schema_types_unknown_keys_and_no_output_are_fail_closed(self) -> None:
        mutations = []
        for field, value in (("enabled", True), ("catalog_hidden", False), ("catalog_enabled", True), ("publication_ready", True), ("native_output", True)):
            item = copy.deepcopy(self.record); item[field] = value; mutations.append(item)
        item = copy.deepcopy(self.record); item["unexpected"] = True; mutations.append(item)
        item = copy.deepcopy(self.record); item["folder_evidence"]["authenticated"] = 1; mutations.append(item)
        item = copy.deepcopy(self.record); item["composition"]["candidate_hooks"] = [{"va": "0x44B560"}]; mutations.append(item)
        item = copy.deepcopy(self.record); item["native_proof"]["method_entry_rejected_as_callsite"] = False; item["native_proof"]["constructor_stock_bytes"] = "AA"; mutations.append(item)
        item = copy.deepcopy(self.record); item["native_contract"]["rejected_candidate_window_flags_pointer_va"] = "0x7B2A63"; mutations.append(item)
        item = copy.deepcopy(self.record); item["native_contract"]["candidate_callsite_va"] = "0x44B560"; mutations.append(item)
        item = copy.deepcopy(self.record); item["native_contract"]["hot_uninstall_verified"] = True; mutations.append(item)
        item = copy.deepcopy(self.record); item["native_contract"]["candidate_guard_control_id"] = 12; mutations.append(item)
        for mutated in mutations:
            with self.assertRaises(ValueError):
                validate_evidence(mutated)

    def test_all_proof_and_four_authenticated_player_receipts_are_required(self) -> None:
        complete = copy.deepcopy(self.record)
        folder_hash = "A" * 64
        complete["folder_evidence"] = {
            "authenticated": True, "complete_folder_verified": True,
            "inventory_schema": "vvfp.full-folder-inventory.v1", "file_count": 10,
            "total_size": 1_000_000, "unexpected_files": [],
            "manifest_sha256": folder_hash, "authentication_receipt_sha256": "B" * 64,
        }
        proof = complete["native_proof"]
        proof["folder_manifest_sha256"] = folder_hash
        for key in ("disassembly_artifact_sha256", "instruction_map_sha256", "lifecycle_trace_sha256", "overlap_report_sha256"):
            proof[key] = "D" * 64
        for key in ("constructor_stock_bytes", "handler_stock_bytes"):
            proof[key] = "90"
        for key in ("constructor_continuation_va", "handler_continuation_va"):
            proof[key] = "0x401000"
        for key in ("candidate_executable_sha256", "candidate_folder_manifest_sha256", "candidate_machine_export_sha256"):
            proof[key] = "E" * 64
        for key in proof:
            if key.endswith("_verified") or key.endswith("_rejected_as_callsite"):
                proof[key] = True
        proof["event_method_offline_detour_verified"] = True
        for key, mode, action in (
            ("tech_windowed", "windowed", "tech"), ("tech_fullscreen", "fullscreen", "tech"),
            ("detail_windowed", "windowed", "detail"), ("detail_fullscreen", "fullscreen", "detail"),
        ):
            complete["player_receipts"][key] = {
                "mode": mode, "action": action, "stock_sha256": STOCK_SHA256,
                "folder_manifest_sha256": folder_hash, "click_reached": True,
                "dialog_visible": True, "owner_verified": True, "centered": True,
                "restore_verified": True, "receipt_sha256": "C" * 64,
            }
        self.assertTrue(validate_evidence(complete))
        for receipt in complete["player_receipts"]:
            mutated = copy.deepcopy(complete); mutated["player_receipts"][receipt] = None
            self.assertFalse(validate_evidence(mutated))
        mutated = copy.deepcopy(complete); mutated["player_receipts"]["detail_fullscreen"]["restore_verified"] = False
        with self.assertRaises(ValueError):
            validate_evidence(mutated)


if __name__ == "__main__":
    unittest.main()
