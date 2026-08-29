"""Architecture-aware checks for the current upgrade-menu production contract.

The contract is checked against the active resource dialogs and native dialog
implementations.  These checks intentionally do not read or rewrite the
historical forensic/STOP evidence records.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "data" / "upgrade_menu_parity_contract.json"


def _dialog_block(resource_text: str, dialog_id: int) -> str:
    start = re.search(rf"(?m)^\s*{dialog_id}\s+DIALOGEX\b", resource_text)
    if start is None:
        raise AssertionError(f"dialog {dialog_id} is missing")
    following = resource_text[start.end() :]
    end = re.search(r"(?m)^\s*\d+\s+DIALOGEX\b", following)
    stop = start.end() + end.start() if end else len(resource_text)
    return resource_text[start.start() : stop]


def _rows(dialog: str) -> list[tuple[str, str, int]]:
    pattern = re.compile(
        r'^\s*LTEXT\s+"([^"]+)"[^\r\n]*\r?\n'
        r'\s*LTEXT\s+"([^"]+)"[^\r\n]*\r?\n'
        r'\s*PUSHBUTTON\s+"Buy"\s*,\s*(\d+)\b',
        re.MULTILINE,
    )
    return [(label, cost, int(control)) for label, cost, control in pattern.findall(dialog)]


def _joined_c_literals(source: str) -> str:
    """Join adjacent C string literals for wording checks only."""

    return re.sub(r'"\s*\r?\n\s*"', "", source)


class UpgradeMenuParityContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    def test_contract_shape_preserves_current_and_historical_boundaries(self) -> None:
        contract = self.contract
        self.assertEqual(contract["status"], "current_production_contract")
        self.assertEqual(
            set(contract["games"]), {"vv1", "vv2", "vv3", "vv4", "vv5"}
        )
        boundary = contract["source_boundary"]
        for key in (
            "shell_reference",
            "transaction_order_reference",
            "historical_evidence",
            "runtime_boundary",
        ):
            self.assertTrue(boundary[key])
        self.assertIn("not a universal transaction-order", boundary["transaction_order_reference"])
        self.assertRegex(boundary["historical_evidence"], r"STOP|forensic|player-pending")

        dialogs = contract["dialogs"]
        self.assertEqual(dialogs["captions"], {
            "tech": "Origins Upgrades",
            "details": "Villager Upgrades",
        })
        self.assertEqual(dialogs["cancel"], {
            "text": "Cancel",
            "control_id": 2,
            "result": "no_action",
        })
        self.assertEqual(dialogs["escape_hint"]["text"], "Press ESC to exit this menu.")
        self.assertTrue(dialogs["escape_hint"]["required_once_per_active_dialog"])
        self.assertIn("Do you want to buy %s for %s tech points?", dialogs["purchase_prompt"]["format"])
        self.assertEqual(dialogs["remove_action"]["button_text"], "Remove")
        self.assertEqual(dialogs["remove_action"]["confirmation"], "none")
        self.assertEqual(dialogs["remove_action"]["purchase_prompt"], "not_used")
        self.assertIn("No refund was issued.", dialogs["remove_result"]["format"])
        self.assertIn("descendants", dialogs["genetics_warnings"]["village_wide"]["format"])

        tech = contract["actions"]["tech"]
        details = contract["actions"]["details"]
        self.assertEqual([row["row"] for row in tech], list(range(14)))
        self.assertEqual([row["row"] for row in details], list(range(5)))
        for row in tech + details:
            self.assertEqual(row["cost_text"], f'{row["cost"]:,} tech points')
            self.assertEqual(row["control_id"], 1000 + row["row"])
            self.assertTrue(row["action_id"] and row["label"])

    def test_active_resources_match_contract_action_inventory_and_shell(self) -> None:
        contract = self.contract
        action_map = {
            **{row["action_id"]: row for row in contract["actions"]["tech"]},
            **{row["action_id"]: row for row in contract["actions"]["details"]},
        }
        for game, spec in contract["games"].items():
            with self.subTest(game=game):
                resource = (ROOT / spec["resource"]).read_text(encoding="utf-8")
                tech = _dialog_block(resource, spec["active_dialogs"]["tech"])
                details = _dialog_block(resource, spec["active_dialogs"]["details"])
                expected_tech = [
                    (
                        action_map[action_id]["label"],
                        action_map[action_id]["cost_text"],
                        spec.get("control_id_overrides", {}).get(
                            action_id, action_map[action_id]["control_id"]
                        ),
                    )
                    for action_id in spec["tech_action_ids"]
                ]
                expected_details = [
                    (action_map[action_id]["label"], action_map[action_id]["cost_text"], action_map[action_id]["control_id"])
                    for action_id in spec["details_action_ids"]
                ]
                self.assertEqual(_rows(tech), expected_tech)
                self.assertEqual(_rows(details), expected_details)
                if game == "vv1":
                    self.assertEqual(spec["collections"], "omitted_not_applicable")
                    self.assertNotIn("Collections", tech)
                else:
                    self.assertEqual(spec["collections"], "included")
                    self.assertIn("Complete All Collections", tech)
                    self.assertIn("Reset All Collections", tech)

                self.assertRegex(tech, r'(?m)^\s*CAPTION\s+"Origins Upgrades"\s*$')
                self.assertRegex(details, r'(?m)^\s*CAPTION\s+"Villager Upgrades"\s*$')
                for dialog in (tech, details):
                    self.assertEqual(dialog.count("Press ESC to exit this menu."), 1)
                    self.assertRegex(dialog, r'(?m)^\s*DEFPUSHBUTTON\s+"Cancel"\s*,\s*2\b')

    def test_native_bindings_prompts_warnings_remove_and_close_wiring(self) -> None:
        owner_markers = {
            "vv1": ("vv1_prep_fullscreen", "GetForegroundWindow"),
            "vv2": ("vv2_prep_fullscreen", "GetForegroundWindow"),
            "vv3": ("vv3_prep_fullscreen", "GetForegroundWindow"),
            "vv4": ("vv4_prep_fullscreen", "GetForegroundWindow"),
            "vv5": ("BeginOriginsOwner", "GetOriginsOwner", "EndOriginsOwner"),
        }
        dialogs = self.contract["dialogs"]
        for game, spec in self.contract["games"].items():
            with self.subTest(game=game):
                source = (ROOT / spec["native_source"]).read_text(encoding="utf-8")
                for kind, symbol in spec["native_dialog_symbols"].items():
                    self.assertRegex(
                        source,
                        rf"{re.escape(symbol)}(?:\s*=\s*|\s+){spec['active_dialogs'][kind]}\b",
                    )
                for marker in owner_markers[game]:
                    self.assertIn(marker, source)
                self.assertIn("DialogBoxParamA", source)
                self.assertIn("IDCANCEL", source)
                self.assertIn("WM_CLOSE", source)
                self.assertIn("EndDialog", source)

                joined = _joined_c_literals(source)
                purchase = dialogs["purchase_prompt"]["format"]
                for fragment in ("Do you want to buy", "Press OK to confirm", "or Cancel"):
                    self.assertIn(fragment, joined)
                for fragment in ("head genetics", "descendants", "Proceed?"):
                    self.assertIn(fragment, joined)
                self.assertIn("was removed.", joined)
                self.assertIn("No refund was issued.", joined)
                self.assertIn(dialogs["remove_action"]["button_text"], joined)
                self.assertNotIn("Do you want to remove", joined)
                self.assertIn("No tech points have been deducted", joined)
                self.assertIn(purchase.split("%s")[0], joined)

    def test_visibility_exceptions_and_vv5_limited_capability_are_explicit(self) -> None:
        games = self.contract["games"]
        for game in ("vv1", "vv2", "vv3", "vv4", "vv5"):
            self.assertIsInstance(games[game]["visibility_strategy"], dict)
            self.assertTrue(games[game]["visibility_strategy"]["tech"])
            self.assertTrue(games[game]["visibility_strategy"]["details"])
        self.assertIn("Done", games["vv1"]["visibility_strategy"]["details"])
        self.assertIn("disabled", games["vv3"]["visibility_strategy"]["details"])
        self.assertIn("disabled", games["vv5"]["visibility_strategy"]["details"])
        self.assertIn("clickable", games["vv2"]["visibility_strategy"]["details"])
        self.assertIn("clickable", games["vv4"]["visibility_strategy"]["details"])

        limited = games["vv5"]["expanded_limited_capability"]
        self.assertEqual(limited["policy"], "unavailable_disabled")
        self.assertEqual(limited["must_not_be"], "enabled_no_op")
        self.assertEqual(limited["state_value"], "0x400000")
        self.assertFalse(limited["button_enabled"])
        self.assertEqual(limited["tech_rows_unavailable"], list(range(6, 14)))
        self.assertEqual(limited["details_rows_unavailable"], [4])
        source = (ROOT / games["vv5"]["native_source"]).read_text(encoding="utf-8")
        self.assertIn(limited["state_symbol"], source)
        self.assertIn('SetDlgItemTextA(window, ID_BUY_FIRST + row, "Unavailable")', source)
        self.assertIn('EnableWindow(GetDlgItem(window, ID_BUY_FIRST + row), FALSE)', source)
        self.assertIn("first_unsupported_row = villager_menu ? 4 : 6", source)

    def test_vv3_dialog_203_remains_dormant(self) -> None:
        spec = self.contract["games"]["vv3"]
        self.assertEqual(spec["dormant_dialogs"]["tech_legacy_full_mastery_only"], 203)
        self.assertFalse(spec["dormant_dialogs"]["public_route"])
        resource = (ROOT / spec["resource"]).read_text(encoding="utf-8")
        self.assertIn("203 DIALOGEX", resource)
        self.assertNotEqual(spec["active_dialogs"]["tech"], 203)


if __name__ == "__main__":
    unittest.main()
