from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load_release_module():
    path = ROOT / "scripts" / "build_release.py"
    spec = importlib.util.spec_from_file_location("vvfp_build_release", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReleaseManifestTests(unittest.TestCase):
    def test_release_manifest_contains_every_active_origins_manifest(self) -> None:
        release = load_release_module()
        expected = {
            f"data/vv{game}_origins_feature.json" for game in range(1, 6)
        }
        self.assertTrue(expected.issubset(set(release.FILES)))
        self.assertIn("data/vv3_origins_village_wide_upgrades.json", release.FILES)
        for historical in (
            "data/candidates/vv3_full_mastery_all_candidate.json",
            "data/candidates/vv3_individual_full_mastery_candidate.json",
            "data/candidates/vv3_individual_grant_running_candidate.json",
            "data/candidates/vv3_full_heal_cure_all_candidate.json",
            "data/candidates/vv4_origins_full_mastery_base_candidate.json",
            "data/candidates/vv4_full_mastery_all_candidate.json",
            "data/candidates/vv4_full_mastery_all_candidate_map.json",
            "data/candidates/VVFP VV4 Full Mastery Candidate.dll",
            "data/candidates/vv4_full_heal_cure_all_candidate.json",
            "data/candidates/vv4_full_heal_cure_all_candidate_map.json",
        ):
            self.assertNotIn(historical, release.FILES)

    def test_release_manifest_contains_current_breeding_research_note(self) -> None:
        release = load_release_module()
        self.assertIn("docs/villager-breeding-overhaul-research.md", release.FILES)

    def test_release_manifest_contains_transparency_system(self) -> None:
        release = load_release_module()
        self.assertIn("docs/transparency-log.md", release.FILES)
        self.assertIn("docs/origins-playtest-readiness.md", release.FILES)
        self.assertIn("src/transparency.py", release.FILES)

    def test_release_manifest_paths_exist(self) -> None:
        release = load_release_module()
        missing = [relative for relative in release.FILES if not (ROOT / relative).is_file()]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
