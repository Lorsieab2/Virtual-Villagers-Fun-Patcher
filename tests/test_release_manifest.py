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
    def test_release_manifest_rejects_executable_members(self) -> None:
        release = load_release_module()
        release._assert_no_executable_members(release.FILES)
        for member in ("stock.exe", "STOCK.EXE", "nested/stock.ExE"):
            with self.subTest(member=member):
                with self.assertRaisesRegex(RuntimeError, "executable members"):
                    release._assert_no_executable_members([member])

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

    def test_release_manifest_bundles_every_fun_patch_manifest(self) -> None:
        """Every JSON manifest the fun-patch loader reads must ship in the
        release, or the patch silently never appears in the packaged patcher
        (this is exactly how the VV4 Optional Text Changes patch went missing:
        its assets shipped but data/vv4_text_changes.json did not)."""
        import sys

        sys.path.insert(0, str(ROOT / "src"))
        import vv_fun_patcher as vfp  # noqa: E402

        release = load_release_module()
        bundled = set(release.FILES)
        paths: list[Path] = []
        for tup in (vfp.ORIGINS_FEATURE_PATHS,
                    vfp.ORIGINS_VILLAGE_WIDE_FEATURE_PATHS,
                    vfp.TEXT_CHANGES_FEATURE_PATHS):
            paths.extend(tup)
        paths.append(vfp.STATISTICS_FEATURES_PATH)
        missing = []
        for p in paths:
            if not p.is_file():
                continue  # only guard manifests that actually exist on disk
            rel = p.resolve().relative_to(ROOT.resolve()).as_posix()
            if rel not in bundled:
                missing.append(rel)
        self.assertEqual(missing, [], f"fun-patch manifests absent from release bundle: {missing}")

    def test_release_manifest_bundles_every_fun_patch_companion_file(self) -> None:
        """Asset-swap fun patches (e.g. VV4 Optional Text, VV5 Guardians of
        Isola) ship no executable patches; their companion source/restore
        files must be in the release bundle or the patch cannot be applied
        or reverted by an end user."""
        import sys

        sys.path.insert(0, str(ROOT / "src"))
        from vv_fun_patcher import load_fun_patches  # noqa: E402

        release = load_release_module()
        bundled = set(release.FILES)
        missing: dict[str, list[str]] = {}
        for patch in load_fun_patches():
            for companion in patch.raw.get("companion_files", []):
                for key in ("source", "restore_source"):
                    path = companion.get(key)
                    if path and path not in bundled:
                        missing.setdefault(patch.id, []).append(path)
        self.assertEqual(missing, {}, f"companion files absent from release bundle: {missing}")


if __name__ == "__main__":
    unittest.main()
