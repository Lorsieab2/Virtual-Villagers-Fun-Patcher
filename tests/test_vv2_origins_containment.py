from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import (  # noqa: E402
    PatcherError,
    get_fun_patch,
    load_builds,
    load_fun_patches,
    load_patch_modes,
    render_patched_bytes,
    resolve_fun_patch_ids,
)
from vv_fun_patcher_gui import group_fun_patches  # noqa: E402


DISABLED = {
    "vv2_enable_origins_exclusive_features",
    "vv2_origins_village_wide_upgrades",
}
REMAINING = {
    "vv2_birth_control",
    "vv2_easier_healing_mastery",
    "vv2_teaching_children_grants_skill",
    "vv2_hospital_recovery_heals",
    "vv2_gong_of_wonder_coconuts_fix",
    "vv2_full_mastery_all_stage_a_candidate",
    "vv2_write_village_statistics",
}


class VV2OriginsContainmentTests(unittest.TestCase):
    def test_standalone_records_are_disabled_and_generator_sources_preserve_it(self) -> None:
        for filename, feature_id in (
            ("vv2_origins_feature.json", "vv2_enable_origins_exclusive_features"),
            ("vv2_origins_village_wide_upgrades.json", "vv2_origins_village_wide_upgrades"),
        ):
            with self.subTest(feature=feature_id):
                record = json.loads((ROOT / "data" / filename).read_text(encoding="utf-8"))
                self.assertEqual(record["id"], feature_id)
                self.assertIs(record["enabled"], False)
                self.assertTrue(record["patches"])

        source_feature = (ROOT / "scripts" / "build_vv2_origins_feature.py").read_text(encoding="utf-8")
        source_village = (ROOT / "scripts" / "build_village_wide_origins_features.py").read_text(encoding="utf-8")
        self.assertIn('"enabled": False', source_feature)
        self.assertIn('feature["enabled"] = False', source_village)

    def test_disabled_ids_are_absent_from_catalog_gui_cli_and_dependency_resolution(self) -> None:
        catalog_ids = {patch.id for patch in load_fun_patches()}
        self.assertTrue(DISABLED.isdisjoint(catalog_ids))
        self.assertTrue(REMAINING.issubset(catalog_ids))
        grouped = group_fun_patches(load_builds(), load_fun_patches())
        grouped_ids = {patch.id for _, patches in grouped for patch in patches}
        self.assertTrue(DISABLED.isdisjoint(grouped_ids))
        result = subprocess.run(
            [sys.executable, "src/vv_fun_patcher.py", "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        for feature_id in DISABLED:
            self.assertNotIn(feature_id, result.stdout)
            with self.subTest(feature=feature_id):
                with self.assertRaisesRegex(PatcherError, "Unknown optional patch"):
                    resolve_fun_patch_ids([feature_id], game_id="vv2")
                with self.assertRaisesRegex(PatcherError, "Unknown fun patch"):
                    get_fun_patch(feature_id)

    def test_crash_trigger_and_readiness_boundaries_are_documented(self) -> None:
        docs = [
            ROOT / "README.md",
            ROOT / "docs" / "origins-playtest-readiness.md",
            ROOT / "docs" / "origins-player-runtime-checklist.md",
            ROOT / "docs" / "transparency-log.md",
        ]
        for path in docs:
            text = path.read_text(encoding="utf-8")
            folded = " ".join(text.split())
            self.assertIn("Time Warp", text)
            self.assertIn("Food Point Doubler", text)
            self.assertIn("crash", text.casefold())
            self.assertIn("purchased/success dialog", folded)
            self.assertIn("does not infer whether", folded)
        transparency = (ROOT / "docs" / "transparency-log.md").read_text(encoding="utf-8")
        for feature_id in DISABLED:
            self.assertNotIn(f"#### {feature_id}", transparency)
        readiness = (ROOT / "docs" / "origins-playtest-readiness.md").read_text(encoding="utf-8")
        self.assertIn("displacing several helper/header references by `0x2000`", " ".join(readiness.split()))
        self.assertIn("not certified as the complete explanation", transparency)

    def test_remaining_vv2_features_render_without_disabled_owners_or_origins_companion(self) -> None:
        build = next(item for item in load_builds() if item.id == "vv2")
        source = ROOT / "research" / "stock-executables" / build.input_name
        catalog = load_fun_patches()
        remaining = [patch.id for patch in catalog if patch.game_id == "vv2"]
        self.assertEqual(set(remaining), REMAINING)
        disabled_offsets = set()
        for filename in ("vv2_origins_feature.json", "vv2_origins_village_wide_upgrades.json"):
            record = json.loads((ROOT / "data" / filename).read_text(encoding="utf-8"))
            disabled_offsets.update(int(item["offset"], 0) for item in record["patches"])
        for mode in load_patch_modes():
            with self.subTest(mode=mode.id):
                rendered, applied = render_patched_bytes(source, build, mode.id, remaining)
                self.assertEqual(len(rendered), build.size + 0x2000)
                owners = {item["owner"] for item in applied}
                self.assertTrue(DISABLED.isdisjoint({owner.removeprefix("feature:") for owner in owners}))
                disabled_owner_offsets = {
                    int(item["offset"], 0)
                    for item in applied
                    if item["owner"].removeprefix("feature:") in DISABLED
                }
                self.assertTrue(disabled_offsets.isdisjoint(disabled_owner_offsets))
        with tempfile.TemporaryDirectory() as temp:
            game = Path(temp) / build.title
            game.mkdir()
            copied = game / build.input_name
            copied.write_bytes(source.read_bytes())
            from vv_fun_patcher import apply_patch  # noqa: PLC0415

            output, log_path = apply_patch(copied, "collection_progression", fun_patch_ids=remaining)
            self.assertFalse((output.parent / "VVFP Origins Icons.dll").exists())
            log = json.loads(log_path.read_text(encoding="utf-8"))
            self.assertTrue(DISABLED.isdisjoint(log["fun_patches"]))
            self.assertFalse(any(item["feature"] in DISABLED for item in log["companion_files"]))
            self.assertFalse(any("Origins Icons.dll" in item["path"] for item in log["companion_files"]))


if __name__ == "__main__":
    unittest.main()
