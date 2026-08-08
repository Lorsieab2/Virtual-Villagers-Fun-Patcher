from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from scripts import validate_vv2_vv5_collectibles_expanded256_disassembly_plan as module


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "data" / "vv2_vv5_collectibles_expanded256_disassembly_plan.json"


class CollectiblesExpandedPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.document = json.loads(PLAN.read_text(encoding="utf-8"))

    def test_canonical_plan_is_disabled_stop(self) -> None:
        module.validate(self.document, ROOT)
        self.assertEqual(self.document["status"], "STOP")
        self.assertFalse(self.document["scope"]["native_output"])
        self.assertFalse(self.document["publication"]["publication_ready"])

    def test_exact_ten_ordered_queries(self) -> None:
        self.assertEqual(len(self.document["ordered_queries"]), 10)
        self.assertEqual([q["order"] for q in self.document["ordered_queries"]], list(range(1, 11)))
        self.assertEqual(self.document["ordered_queries"][0]["family"], "resolver")
        self.assertEqual(self.document["ordered_queries"][4]["family"], "writer")
        self.assertEqual(self.document["ordered_queries"][6]["family"], "transaction")
        self.assertEqual(self.document["ordered_queries"][7]["family"], "save")

    def test_all_four_games_bind_builds_and_have_absent_folders(self) -> None:
        module.validate(self.document, ROOT)
        for game in ("vv2", "vv3", "vv4", "vv5"):
            self.assertEqual(self.document["games"][game]["folder_binding"]["status"], "absent_stop")
            self.assertEqual(self.document["games"][game]["folder_binding"]["inventory_sha256"], None)

    def test_native_query_map_is_empty_until_authenticated_export(self) -> None:
        for game in self.document["games"].values():
            self.assertEqual(game["queries"], {})

    def test_publication_enablement_is_rejected(self) -> None:
        bad = copy.deepcopy(self.document)
        bad["publication"]["enabled"] = True
        with self.assertRaisesRegex(module.PlanError, "publication guard"):
            module.validate(bad, ROOT)

    def test_scope_enablement_is_rejected(self) -> None:
        bad = copy.deepcopy(self.document)
        bad["scope"]["native_output"] = True
        with self.assertRaisesRegex(module.PlanError, "scope.native_output"):
            module.validate(bad, ROOT)

    def test_query_reordering_is_rejected(self) -> None:
        bad = copy.deepcopy(self.document)
        bad["ordered_queries"][0], bad["ordered_queries"][1] = bad["ordered_queries"][1], bad["ordered_queries"][0]
        with self.assertRaisesRegex(module.PlanError, "ordered query list"):
            module.validate(bad, ROOT)

    def test_stale_stock_fingerprint_is_rejected(self) -> None:
        bad = copy.deepcopy(self.document)
        bad["games"]["vv5"]["stock"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(module.PlanError, "vv5 stock binding"):
            module.validate(bad, ROOT)

    def test_parent_unknown_is_allowed_only_as_stop(self) -> None:
        bad = copy.deepcopy(self.document)
        bad["games"]["vv5"]["expanded_parent"] = {"status": "resolved", "sha256": "0" * 64, "size": 1}
        with self.assertRaisesRegex(module.PlanError, "parent status"):
            module.validate(bad, ROOT)

    def test_known_ledger_digest_must_be_uppercase_sha(self) -> None:
        bad = copy.deepcopy(self.document)
        bad["games"]["vv5"]["known_ledgers"][0]["ledger_sha256"] = "bad"
        with self.assertRaisesRegex(module.PlanError, "vv5 ledger"):
            module.validate(bad, ROOT)

    def test_no_manual_native_rows_can_be_smuggled_in(self) -> None:
        bad = copy.deepcopy(self.document)
        bad["games"]["vv4"]["queries"] = {"resolver_selected_world": {"va": "0x401000"}}
        with self.assertRaisesRegex(module.PlanError, "native queries must remain empty"):
            module.validate(bad, ROOT)


if __name__ == "__main__":
    unittest.main()
