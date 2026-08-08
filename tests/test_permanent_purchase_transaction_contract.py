from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

import permanent_purchase_transaction_contract as contract


ROOT = Path(__file__).resolve().parents[1]


class PermanentPurchaseContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = contract.load_contract()

    def test_checked_in_contract_is_exact_but_every_action_stops(self):
        result = contract.validate_contract(self.raw)
        self.assertTrue(result.schema_valid, result.errors)
        self.assertFalse(result.publication_allowed)
        self.assertEqual(len(result.actions), 5 * 19)
        self.assertTrue(all(not action.evidence_complete for action in result.actions))
        self.assertTrue(all(action.missing == contract.REQUIREMENTS for action in result.actions))

    def test_inventory_has_exact_labels_prices_and_policies(self):
        actions = {row["id"]: row for row in self.raw["action_definitions"]}
        expected = {
            "time_warp": ("Time Warp - Advances 3 Villager Years", 50000, "buy_only"),
            "island_event": ("Island Event", 30000, "buy_only"),
            "barrel_of_babies": ("Barrel of Babies", 75000, "buy_only"),
            "tech_point_doubler": ("Tech Point Doubler", 500000, "buy_or_owned_remove"),
            "food_point_doubler": ("Food Point Doubler", 500000, "buy_or_owned_remove"),
            "full_heal": ("Full Heal", 30000, "buy_only"),
            "grant_youth": ("Grant Youth", 50000, "buy_only"),
            "grant_full_mastery": ("Grant Full Mastery", 100000, "buy_only"),
            "grant_running": ("Grant Running", 40000, "buy_only"),
            "set_age_18": ("Set Age to 18", 50000, "buy_only"),
            "all_running": ("All Villagers Like Running", 1000000, "buy_only"),
            "all_full_mastery": ("Grant Full Mastery to All Villagers", 1000000, "buy_only"),
            "all_age_18": ("All Villagers Are 18", 1000000, "buy_only"),
            "complete_all_collections": ("Complete All Collectibles", 1000000, "buy_only"),
            "reset_all_collections": ("Reset Collectibles", 1000000, "buy_only"),
        }
        for action_id, values in expected.items():
            self.assertEqual((actions[action_id]["label"], actions[action_id]["price"], actions[action_id]["button_policy"]), values)
        self.assertEqual(actions["complete_all_collections"]["repeatability"], "repeatable")
        self.assertEqual(actions["reset_all_collections"]["repeatability"], "repeatable")
        self.assertIsNone(actions["equal_division"]["price"])

    def test_only_doublers_allow_remove(self):
        removable = [row["id"] for row in self.raw["action_definitions"] if row["button_policy"] == "buy_or_owned_remove"]
        self.assertEqual(removable, ["tech_point_doubler", "food_point_doubler"])

    def test_collectibles_scope_is_vv2_through_vv5_and_hidden(self):
        for game in ("vv2", "vv3", "vv4", "vv5"):
            bindings = {row["id"]: row for row in self.raw["games"][game]}
            self.assertEqual(bindings["complete_all_collections"]["availability"], "absent_proposed")
            self.assertEqual(bindings["reset_all_collections"]["availability"], "absent_proposed")
        for row in self.raw["games"]["vv1"]:
            if row["id"] in {"complete_all_collections", "reset_all_collections"}:
                self.assertEqual(row["availability"], "not_applicable")

    def test_strict_root_and_action_schema_rejects_pollution(self):
        for mutate in (
            lambda x: x.update(enabled=True),
            lambda x: x.pop("catalog_hidden"),
            lambda x: x.update(unexpected=True),
            lambda x: x["action_definitions"][0].update(price=True),
            lambda x: x["action_definitions"][0].update(button_policy="remove"),
            lambda x: x["action_definitions"][0]["requirements"].reverse(),
            lambda x: x["games"]["vv1"][0].update(unexpected=True),
            lambda x: x["games"]["vv1"][0].update(evidence={"unknown": []}),
        ):
            with self.subTest(mutate=mutate):
                raw = copy.deepcopy(self.raw); mutate(raw)
                self.assertFalse(contract.validate_contract(raw).schema_valid)

    def test_each_requirement_is_independently_missing_and_complete_never_publishes(self):
        raw = copy.deepcopy(self.raw)
        binding = raw["games"]["vv5"][0]
        binding["evidence"] = {name: [f"receipt:{name}"] for name in contract.REQUIREMENTS}
        result = contract.validate_contract(raw)
        target = next(item for item in result.actions if item.game == "vv5" and item.action_id == "time_warp")
        self.assertTrue(target.evidence_complete)
        self.assertFalse(result.publication_allowed)
        for name in contract.REQUIREMENTS:
            changed = copy.deepcopy(raw); changed["games"]["vv5"][0]["evidence"][name] = []
            target = next(item for item in contract.validate_contract(changed).actions if item.game == "vv5" and item.action_id == "time_warp")
            self.assertEqual(target.missing, (name,))

    def test_catalog_isolation_is_structural(self):
        patcher = (ROOT / "src" / "vv_fun_patcher.py").read_text(encoding="utf-8")
        self.assertNotIn("permanent_purchase_transaction_contract", patcher)
        self.assertFalse(any(path.name == "permanent_purchase_transaction_contract.py" for path in (ROOT / "src").glob("vv_fun_patcher*.py")))

    def test_schema_and_json_are_parseable_and_reference_only(self):
        schema = json.loads((ROOT / "data" / "permanent_purchase_transaction_contract.schema.json").read_text(encoding="utf-8"))
        self.assertFalse(schema["properties"]["publication_allowed"]["const"])
        self.assertFalse(self.raw["publication_allowed"])


if __name__ == "__main__":
    unittest.main()
