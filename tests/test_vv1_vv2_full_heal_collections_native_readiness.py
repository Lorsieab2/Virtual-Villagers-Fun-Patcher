import copy, json, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from vv_full_heal_collections_native_readiness import ReadinessError, validate_manifest, reject_candidate_export

class FullHealCollectionsReadinessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((ROOT / "data/native_evidence/vv1_vv2_full_heal_collections_query_manifest.json").read_text(encoding="utf-8"))

    def test_disabled_empty_manifest_is_valid(self):
        validate_manifest(self.manifest)
        self.assertEqual(self.manifest["evidence_records"], [])

    def test_enablement_or_publication_fails(self):
        for field in ("enabled", "publication_allowed", "native_output"):
            bad = copy.deepcopy(self.manifest); bad[field] = True
            with self.assertRaises(ReadinessError): validate_manifest(bad)

    def test_missing_collection_route_query_fails(self):
        bad = copy.deepcopy(self.manifest); bad["required_topics"]["complete_collections"].pop()
        with self.assertRaises(ReadinessError): validate_manifest(bad)

    def test_missing_health_or_people_cured_query_fails(self):
        for query in ("health_to_100_setter", "people_cured_increment", "sickness_clear_route"):
            bad = copy.deepcopy(self.manifest); bad["required_topics"]["full_heal"].remove(query)
            with self.assertRaises(ReadinessError): validate_manifest(bad)

    def test_synthetic_folder_or_dll_identity_fails(self):
        for field, value in (("inventory_sha256", "A" * 64), ("dll_inventory_sha256", "B" * 64)):
            bad = copy.deepcopy(self.manifest); bad["folder_requirements"][field] = value
            with self.assertRaises(ReadinessError): validate_manifest(bad)

    def test_declared_native_field_contracts_fail_closed(self):
        for field in ("required_function_fields", "required_instruction_fields", "allowed_status"):
            with self.subTest(field=field):
                bad = copy.deepcopy(self.manifest)
                bad[field] = []
                with self.assertRaises(ReadinessError): validate_manifest(bad)

    def test_dll_identity_wording_fails_closed(self):
        bad = copy.deepcopy(self.manifest)
        bad["folder_requirements"]["dll_identity_status"] = "unknown"
        with self.assertRaises(ReadinessError): validate_manifest(bad)

    def test_legacy_cure_cannot_be_recast(self):
        bad = copy.deepcopy(self.manifest); bad["legacy_cure_policy"]["full_heal"] = True
        with self.assertRaises(ReadinessError): validate_manifest(bad)

    def test_nonempty_export_is_rejected_by_empty_gate(self):
        reject_candidate_export(None); reject_candidate_export({})
        with self.assertRaises(ReadinessError): reject_candidate_export({"synthetic": True})

if __name__ == "__main__": unittest.main()
