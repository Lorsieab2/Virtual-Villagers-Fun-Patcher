import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs" / "vv3-vv5-expanded-256-implementation-gates.md"
OVERVIEW = ROOT / "docs" / "experimental-256-cap-research.md"
README = ROOT / "README.md"
MANIFEST = ROOT / "data" / "expanded_256.json"


class Expanded256ImplementationGateTests(unittest.TestCase):
    def test_exact_builds_and_manifest_counts_are_documented(self):
        report = REPORT.read_text(encoding="utf-8")
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        expected = {
            "vv3": (
                "8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503",
                1263,
            ),
            "vv4": (
                "6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220",
                1771,
            ),
            "vv5": (
                "92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D",
                1951,
            ),
        }
        for game_id, (digest, patch_count) in expected.items():
            game = manifest["games"][game_id]
            self.assertEqual(game["source_sha256"], digest)
            self.assertEqual(game["patch_count"], patch_count)
            self.assertEqual(len(game["patches"]), patch_count)
            self.assertIn(digest, report)
            self.assertIn(f"{patch_count:,}", report)

    def test_release_boundary_and_relocation_blockers_are_explicit(self):
        report = REPORT.read_text(encoding="utf-8")
        overview = OVERVIEW.read_text(encoding="utf-8")
        readme = README.read_text(encoding="utf-8")

        self.assertIn("**VV3: ON HOLD. VV4: ON HOLD. VV5: ON HOLD.**", report)
        self.assertIn("Four real decoded absolute operands remain", report)
        self.assertIn("**Thirty-six cross-section branches remain", report)
        self.assertIn("All 43 omissions must be repaired atomically", report)
        self.assertIn("ON HOLD — do not package or release", overview)
        self.assertIn("Expanded-256 release status", readme)
        self.assertNotIn(
            "the three current self-contained expanded game folders pass",
            overview,
        )

    def test_reproducible_evidence_tools_are_present(self):
        tools = (
            "audit_expanded_shr_relocations.py",
            "ida_export_expanded_gate_refs.py",
            "ida_inspect_offsets.py",
            "reconcile_expanded_256_gate_refs.py",
            "render_expanded_256_gate_variants.py",
            "run_idalib_expanded_gate_refs.py",
            "run_idalib_inspect_offsets.py",
        )
        report = REPORT.read_text(encoding="utf-8")
        for name in tools:
            self.assertTrue((ROOT / "scripts" / name).is_file())
            self.assertIn(f"`scripts/{name}`", report)


if __name__ == "__main__":
    unittest.main()
