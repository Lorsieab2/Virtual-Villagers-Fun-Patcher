from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_vv5_ui_native_stabilization_gate import (  # noqa: E402
    GATE_PATH,
    SCHEMA_PATH,
    load_and_validate,
    validate_account_balance_callback_result,
    validate_deduction_callback_arguments,
    validate_gate,
    validate_selection_callback_result,
    validate_world_identity,
)


class VV5UiNativeStabilizationGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gate = json.loads(GATE_PATH.read_text(encoding="utf-8"))

    def test_gate_is_disabled_four_action_and_schema_strict(self) -> None:
        gate, valid = load_and_validate()
        self.assertTrue(valid)
        self.assertFalse(gate["enabled"])
        self.assertTrue(gate["catalog_hidden"])
        self.assertFalse(gate["catalog_enabled"])
        self.assertFalse(gate["publication_ready"])
        self.assertFalse(gate["native_output"])
        self.assertEqual(gate["actions"], ["youth", "full_mastery", "running", "age_18"])
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertFalse(schema["additionalProperties"])
        self.assertTrue(all(definition.get("additionalProperties") is False for definition in schema["$defs"].values() if "additionalProperties" in definition))

    def assert_rejected(self, mutate) -> None:
        mutated = copy.deepcopy(self.gate)
        mutate(mutated)
        with self.assertRaises(ValueError):
            validate_gate(mutated)

    def test_d339_detail_method_and_ownership_are_exact(self) -> None:
        detail = self.gate["detail_evidence"]
        self.assertEqual(detail["input_method_entry_va"], "0x44B560")
        self.assertFalse(detail["input_event13_route"])
        self.assertEqual(detail["event_method_range"], "[0x44BC20,0x44BD4C)")
        self.assertEqual(detail["event_method_size"], 300)
        self.assertEqual(detail["event_method_sha256"], "DE25D2B76DC7E6337F40F06CBF25FCDCEC411BD9D7F1E7DC78406C157501DC74")
        self.assertEqual(detail["dispatcher_range"], "[0x4019B8,0x4019CF)")
        self.assertEqual(detail["dispatcher_call_range"], "[0x4019CD,0x4019CF)")
        self.assertEqual(detail["ownership"]["teardown_chain"], ["0x44B9F0", "0x44AF30", "0x40C7F0", "0x40C830"])
        self.assertEqual(detail["offline_detour"]["guard"], {"message": 8, "control_id": 13})
        self.assertFalse(detail["offline_detour"]["hot_uninstall_verified"])

    def test_detail_input_route_and_old_candidate_are_rejected(self) -> None:
        self.assert_rejected(lambda item: item["detail_evidence"].update({"input_event13_route": True}))
        self.assert_rejected(lambda item: item["detail_evidence"]["offline_detour"].update({"raw_offset": "0x44B560"}))
        self.assert_rejected(lambda item: item["detail_evidence"].update({"event_method_size": 301}))

    def test_c260_pointer_repair_remains_static_rejected_no_output(self) -> None:
        defect = self.gate["c260_rejection"]
        self.assertEqual((defect["bad_pointer_va"], defect["authenticated_string_va"]), ("0x7B2A64", "0x7B2A63"))
        self.assertEqual(defect["requested_symbol"], "DL_GetWindowFlags")
        self.assertEqual(defect["repair_output"], [])
        self.assert_rejected(lambda item: item["c260_rejection"]["repair_output"].append("64->63"))
        self.assert_rejected(lambda item: item["c260_rejection"].update({"runtime_verified": True}))

    def test_resource_caption_and_disabled_native_arrays_are_fail_closed(self) -> None:
        resource = self.gate["resource_caption"]
        self.assertEqual((resource["resource_id"], resource["dimensions"], resource["local"]), ("0x6A", [96, 39], [137, 2]))
        self.assertEqual(resource["asset"], "Images\\btn_trophies.png")
        self.assertIsNone(resource["caption_text"])
        self.assertFalse(resource["caption_verified"])
        for key in ("hooks", "caves", "patches", "ui_ranges", "full_heal_ranges"):
            self.assertEqual(self.gate["composition"][key], [])
        self.assert_rejected(lambda item: item["resource_caption"].update({"caption_verified": True}))
        self.assert_rejected(lambda item: item["composition"]["ui_ranges"].append("0x1000-0x1001"))
        self.assert_rejected(lambda item: item["full_heal"].update({"native_output": True}))

    def test_identity_funds_charge_and_rollback_gate_is_complete_but_reference_only(self) -> None:
        tx = self.gate["transaction_contract"]
        self.assertEqual(tx["confirmation_results"], {"idok": 1, "cancel": [0, 2]})
        self.assertEqual(tx["identity_fields"], ["selected_index", "world_identity", "record_pointer", "account_identity"])
        self.assertEqual(tx["exact_identity_required_at"], ["plan", "reacquire", "first_write", "like_postverify", "dislike_write", "final_postverify", "deduction", "rollback_restore"])
        self.assertTrue(tx["before_reacquire_required"])
        self.assertTrue(tx["before_funds_reacquire_required"])
        self.assertTrue(tx["funds_snapshot_exact_required"])
        self.assertTrue(tx["one_deduction_only"])
        self.assertTrue(tx["deduction_after_final_postverify"])
        self.assertIsNone(tx["reference_model"]["account_identity_token"])
        self.assertFalse(tx["reference_model"]["later_stage_identity_verified"])
        self.assertFalse(tx["rollback_policy"]["native_rollback_verified"])
        self.assertFalse(tx["reference_model"]["native_write"])
        self.assert_rejected(lambda item: item["transaction_contract"].update({"before_reacquire_required": False}))
        self.assert_rejected(lambda item: item["transaction_contract"].update({"before_funds_reacquire_required": False}))
        self.assert_rejected(lambda item: item["transaction_contract"]["exact_identity_required_at"].remove("deduction"))
        self.assert_rejected(lambda item: item["transaction_contract"]["reference_model"].update({"account_identity_token": "account"}))
        self.assert_rejected(lambda item: item["transaction_contract"]["rollback_policy"].update({"native_rollback_verified": True}))

    def test_world_bound_callback_shapes_reject_bool_mismatch_and_exceptions_by_contract(self) -> None:
        self.assertEqual(validate_world_identity(7), 7)
        for value in (True, 0, -1, 7.0, "7"):
            with self.subTest(world_identity=value):
                with self.assertRaises(ValueError):
                    validate_world_identity(value)
        self.assertEqual(validate_selection_callback_result((7, object(), 3, "ptr-3"))[2:], (3, "ptr-3"))
        self.assertEqual(validate_account_balance_callback_result((7, object(), 100_000))[2], 100_000)
        self.assertEqual(validate_deduction_callback_arguments((7, object(), 40_000))[2], 40_000)
        for callback, value in (
            (validate_selection_callback_result, (True, object(), 3, "ptr-3")),
            (validate_selection_callback_result, (7, object(), 3.0, "ptr-3")),
            (validate_selection_callback_result, (7, object(), 3, "")),
            (validate_account_balance_callback_result, (7, object(), True)),
            (validate_deduction_callback_arguments, (0, object(), 40_000)),
            (validate_deduction_callback_arguments, (7, object(), 40_000.0)),
        ):
            with self.subTest(callback=callback.__name__, value=value):
                with self.assertRaises(ValueError):
                    callback(value)
        tx = self.gate["transaction_contract"]
        self.assertEqual(tx["selection_callback"]["shape"], "(world, record, selected_index, resolved_pointer)")
        self.assertEqual(tx["account_balance_callback"]["shape"], "(world, account, balance)")
        self.assertEqual(tx["deduction_callback"]["shape"], "(world, account, amount)")
        self.assertEqual(tx["fail_closed_stages"], ["first_write", "like_postverify", "full_postverify", "pre_deduction", "charge_readback", "rollback_restore"])
        self.assert_rejected(lambda item: item["transaction_contract"]["selection_callback"].update({"shape": "(record, index)"}))

    def test_running_cleanup_requires_explicit_binding_before_native_charge(self) -> None:
        cleanup = self.gate["transaction_contract"]["running_existing_like_cleanup"]
        self.assertEqual(cleanup["current_reference_model"], "changed_and_charged")
        self.assertTrue(cleanup["binding_required_before_native_charge"])
        self.assertFalse(cleanup["native_charge_allowed"])
        self.assert_rejected(lambda item: item["transaction_contract"]["running_existing_like_cleanup"].update({"native_charge_allowed": True}))

    def test_fullscreen_owner_is_contract_only_and_has_no_foreground_fallback(self) -> None:
        owner = self.gate["fullscreen_owner"]
        self.assertTrue(owner["capture_before_leave"])
        self.assertTrue(owner["same_process_revalidation"])
        self.assertTrue(owner["no_foreground_fallback"])
        self.assertTrue(owner["single_terminal_cleanup"])
        self.assertEqual(owner["owner_output"], [])
        self.assertTrue(all(value is None for value in owner["player_receipts"].values()))
        self.assert_rejected(lambda item: item["fullscreen_owner"].update({"no_foreground_fallback": False}))
        self.assert_rejected(lambda item: item["fullscreen_owner"]["owner_output"].append("native"))

    def test_exact_types_reject_bool_int_and_fifth_action(self) -> None:
        self.assert_rejected(lambda item: item["detail_evidence"].update({"event_method_size": True}))
        self.assert_rejected(lambda item: item["resource_caption"].update({"dimensions": [96.0, 39]}))
        self.assert_rejected(lambda item: item.update({"actions": ["youth", "full_mastery", "running", "age_18", "full_heal"]}))
        self.assert_rejected(lambda item: item.update({"enabled": True}))


if __name__ == "__main__":
    unittest.main()
