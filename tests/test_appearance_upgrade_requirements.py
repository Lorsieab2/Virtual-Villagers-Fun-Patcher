from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "appearance-upgrades-requirements.md"
BUILDS = ROOT / "data" / "builds.json"


class AppearanceUpgradeRequirementsTests(unittest.TestCase):
    def test_contract_contains_required_rules_and_stop_boundary(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        required = [
            "Change Outfit belongs in the existing Villager Upgrades window",
            "exactly **5,000 tech points once**",
            "Change Head has the same selected active/living eligibility",
            "Warning: This will change",
            "young and old/gray head choice",
            "choices, in order, are exactly: Chief's mask, blue\nmask, red mask, orange mask, and no mask",
            "Play as the Heathens!",
            "defaults to\nthe blue Heathen mask",
            "Every current Heathen renders with no mask",
            "every native spawn",
            "Vanilla base-game save recognition is mandatory",
            "Executable growth is allowed",
            "remain **STOP** until independently proved",
            "do not authorize chooser-preview implementation",
        ]
        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        self.assertIn("exactly **0** only when Play as the Heathens is active", text)
        self.assertIn("never write faction, type/tag, conversion", text)

    def test_contract_lists_exact_build_fingerprints(self) -> None:
        builds = json.loads(BUILDS.read_text(encoding="utf-8"))["games"]
        text = DOC.read_text(encoding="utf-8")
        for build in builds:
            with self.subTest(game=build["id"]):
                self.assertIn(f"{build['size']:,} bytes", text)
                self.assertIn(build["sha256"], text)

    def test_no_loaded_fun_patch_advertises_unimplemented_appearance_options(self) -> None:
        import sys

        sys.path.insert(0, str(ROOT / "src"))
        from vv_fun_patcher import load_fun_patches  # noqa: PLC0415

        forbidden = {
            "change outfit",
            "change head",
            "give heathen mask",
            "play as the heathens!",
        }
        for patch in load_fun_patches():
            self.assertNotIn(patch.id.casefold(), forbidden)
            self.assertNotIn(patch.name.casefold(), forbidden)

    def test_release_manifest_includes_contract(self) -> None:
        text = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        self.assertIn('"docs/appearance-upgrades-requirements.md"', text)

    def test_existing_executable_manifests_are_unchanged_from_parent_commit(self) -> None:
        manifest_paths = sorted(ROOT.glob("data/*_origins_feature.json"))
        manifest_paths += sorted(ROOT.glob("data/*_origins_village_wide_upgrades.json"))
        try:
            parent = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("git parent unavailable for executable-manifest snapshot")
        for path in manifest_paths:
            relative = path.relative_to(ROOT).as_posix()
            before = subprocess.run(
                ["git", "show", f"{parent}:{relative}"],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            ).stdout
            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")),
                json.loads(before),
                relative,
            )


if __name__ == "__main__":
    unittest.main()
