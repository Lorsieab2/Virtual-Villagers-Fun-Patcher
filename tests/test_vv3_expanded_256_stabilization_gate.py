import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "stabilization", ROOT / "scripts" / "validate_vv3_expanded_256_stabilization_gate.py"
)
GATE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(GATE)


class VV3StabilizationGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = json.loads(
            (ROOT / "data" / "vv3_expanded_256_stabilization_gate.json").read_text(encoding="utf-8")
        )

    def test_contract_validates_and_stays_stop(self):
        result = GATE.validate(self.document)
        self.assertEqual(1263, result["manifest_patches"])
        self.assertEqual({"vv4": 13, "vv5": 66}, result["foreign_ledgers"])
        self.assertFalse(result["gate_ready"])
        self.assertFalse(result["runtime_go"])
        self.assertFalse(result["player_go"])
        self.assertFalse(result["publication_ready"])
        self.assertEqual("STOP", result["status"])

    def test_geometry_is_corrected_full_capacity_reference(self):
        self.assertEqual(
            ("0x11C", "0x7864", 255, [256, 257, 258, 259], "0x19464", "0x1A4B4", "0x1A4C0"),
            tuple(self.document["geometry"][key] for key in (
                "record_size", "records_offset", "logical_last", "padding_indices",
                "tail_offset", "expanded_body_size", "expanded_file_size",
            )),
        )

    def test_foreign_ledgers_and_db1a4_are_exact_invariants(self):
        foreign = self.document["relocation_invariants"]["foreign_preservation"]
        self.assertEqual("pending_containment_integration", foreign["status"])
        self.assertEqual(13, foreign["vv4"]["count"])
        self.assertEqual(66, foreign["vv5"]["count"])
        row = foreign["vv5_db1a4"]
        self.assertEqual(
            ("0xDB1A4", "7267C6FF", "rel32", "0x8EB1A3", "0x41891A"),
            tuple(row[key] for key in ("offset", "before", "kind", "source_virtual_address", "target_expanded_virtual_address")),
        )

    def test_contract_refuses_relaxed_foreign_or_stop_state(self):
        altered = json.loads(json.dumps(self.document))
        altered["relocation_invariants"]["foreign_preservation"]["vv5"]["count"] = 23
        with self.assertRaises(GATE.StabilizationGateError):
            GATE.validate(altered)
        altered = json.loads(json.dumps(self.document))
        altered["relocation_invariants"]["foreign_preservation"]["vv5_db1a4"]["target_expanded_virtual_address"] = "0x418920"
        with self.assertRaises(GATE.StabilizationGateError):
            GATE.validate(altered)
        altered = json.loads(json.dumps(self.document))
        altered["decision"]["runtime_go"] = True
        with self.assertRaises(GATE.StabilizationGateError):
            GATE.validate(altered)

    def test_schema_and_docs_are_present(self):
        schema = json.loads((ROOT / "data" / "vv3_expanded_256_stabilization_gate.schema.json").read_text(encoding="utf-8"))
        self.assertEqual("vvfp.vv3_expanded_256_stabilization_gate", schema["$id"])
        self.assertIn("pending_containment_integration", (ROOT / "docs" / "vv3-expanded-256-stabilization-gate.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
