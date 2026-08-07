import copy, json, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from vv_catalog_runtime_coverage_gate import EvidenceError, EXPECTED_IDS, validate

class RuntimeCoverageGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((ROOT / "data/candidates/vv1_vv2_catalog_runtime_coverage_gate.json").read_text(encoding="utf-8"))

    def test_tracked_gate_is_valid_and_empty(self):
        validate(self.data)
        self.assertEqual({r["patch_id"] for r in self.data["catalog_snapshot"]}, EXPECTED_IDS)
        self.assertEqual(self.data["receipt_contract"]["receipts"], [])

    def test_enablement_and_publication_fail(self):
        for field in ("enabled","catalog_enabled","publication_allowed","runtime_ready","player_verified","native_output"):
            bad=copy.deepcopy(self.data); bad[field]=True
            with self.assertRaises(EvidenceError): validate(bad)

    def test_missing_duplicate_or_invented_patch_fails(self):
        for mutate in ("missing","duplicate","invented"):
            bad=copy.deepcopy(self.data)
            if mutate == "missing": bad["catalog_snapshot"].pop()
            elif mutate == "duplicate": bad["catalog_snapshot"][-1]=copy.deepcopy(bad["catalog_snapshot"][0])
            else: bad["catalog_snapshot"][0]["patch_id"]="vv1_invented"
            with self.assertRaises(EvidenceError): validate(bad)

    def test_partial_dimensions_fail(self):
        for field in self.data["required_dimensions"]:
            bad=copy.deepcopy(self.data); bad["required_dimensions"][field].pop()
            with self.assertRaises(EvidenceError): validate(bad)

    def test_missing_patch_scenarios_or_mode_fails(self):
        bad=copy.deepcopy(self.data); bad["patch_specific_scenarios"].pop(next(iter(EXPECTED_IDS)))
        with self.assertRaises(EvidenceError): validate(bad)
        bad=copy.deepcopy(self.data); bad["public_modes"].pop()
        with self.assertRaises(EvidenceError): validate(bad)

    def test_synthetic_manual_or_tracked_receipt_fails(self):
        for field in ("synthetic","manual_or_reconstructed"):
            bad=copy.deepcopy(self.data); bad["receipt_contract"][field]=True
            with self.assertRaises(EvidenceError): validate(bad)
        bad=copy.deepcopy(self.data); bad["receipt_contract"]["receipts"]=[{"claim":"synthetic"}]
        with self.assertRaises(EvidenceError): validate(bad)

    def test_untrusted_folder_claim_fails(self):
        bad=copy.deepcopy(self.data); bad["authenticated_inputs"]["vv1"]["stock_executable_sha256"]="0"*64
        with self.assertRaises(EvidenceError): validate(bad)

if __name__ == "__main__": unittest.main()
