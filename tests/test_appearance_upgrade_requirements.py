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

    def test_vv1_appearance_audit_is_exact_build_stop(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        required = [
            "disassembly commit `8888682`",
            "record `+0x364`",
            "record `+0x360`",
            "RNG(19)",
            "RNG(20)",
            "Status/action 199",
            "clone path copies both",
            "sub_437790",
            "sub_449140 -> sub_437340",
            "`+0xAD34`",
            "Strange Berries",
            "Change Outfit and Change Head therefore remain",
            "exact save/load serializer mapping",
            "custom chooser/preview",
            "safe composable cave/new-section placement",
            "Do not\ninfer young/old catalogs",
        ]
        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        self.assertIn("independent **STOP**", text)
        self.assertIn("1EC790B927741081D5CE13A48FB76983A4FD4336EA08F89317872643760AF03D", text)

    def test_vv2_appearance_audit_is_independent_exact_build_stop(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        required = [
            "VV2 exact-build appearance audit",
            "724,992-byte build",
            "46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677",
            "independent **STOP**",
            "record stride is `0xE48C`",
            "record `+0x54C`",
            "Native action 69 costs exactly **5,000 tech points**",
            "sub_4229D0",
            "sub_422890",
            "native range of `0..29`",
            "197,488 bytes",
            "not a final user catalog",
            "head/genetics DWORD candidate is record `+0x548`",
            "old/young resources",
            "genetics-warning callback",
            "head feels strange",
            "no direct caller xref",
            "vanilla-save compatibility",
            "Change Outfit and Change Head therefore remain\nSTOP for VV2",
        ]
        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_vv3_change_outfit_audit_is_exact_build_stop(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        required = [
            "VV3 Change Outfit exact-build audit",
            "831,488-byte build",
            "8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503",
            "independent **STOP**",
            "The Clothing Hut",
            "Choose\nan outfit for your villager!",
            "Do you want to spend 5000 tech points to change\nthis villager's clothes?",
            "Getting new clothes!",
            "Not enough tech points\nto make new clothes!",
            "Male/female body resources",
            "young/old head assets",
            "sub_4227F0",
            "sub_4228F0",
            "literal `0x1388` (5,000)",
            "0x004228A2`/`0x228A2",
            "[eax+0x12FB0]",
            "does **not** prove a clothing purchase",
            "selected-villager identity",
            "outfit-field write",
            "Change Outfit remains STOP",
            "sex/age/special/invalid catalog classification",
            "world, Detail, and chooser",
            "stock and expanded-256 layouts",
            "this audit is Outfit-only",
        ]
        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

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
            current_manifest = json.loads(path.read_text(encoding="utf-8"))
            before_manifest = json.loads(before)
            executable_keys = (
                "patches",
                "companion_files",
                "output_tag",
                "running_preference_id",
                "running_preference_evidence",
            )
            if relative.endswith("_origins_village_wide_upgrades.json"):
                # The five village-wide payloads are intentionally corrected
                # in the current slice. Their guards and ownership metadata
                # remain unchanged; only their generated payload bytes differ.
                current_patch = current_manifest["patches"][0]
                before_patch = before_manifest["patches"][0]
                for patch_key in ("offset", "before", "purpose"):
                    self.assertEqual(
                        current_patch.get(patch_key),
                        before_patch.get(patch_key),
                        f"{relative}:patches[0].{patch_key}",
                    )
                continue
            for key in executable_keys:
                self.assertEqual(current_manifest.get(key), before_manifest.get(key), f"{relative}:{key}")


if __name__ == "__main__":
    unittest.main()
