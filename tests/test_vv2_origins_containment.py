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


PUBLIC = {
    "vv1_enable_origins_exclusive_features",
    "vv1_origins_village_wide_upgrades",
    "vv2_enable_origins_exclusive_features",
    "vv2_origins_village_wide_upgrades",
}
REMAINING = {
    "vv2_birth_control",
    "vv2_easier_healing_mastery",
    "vv2_teaching_children_grants_skill",
    "vv2_hospital_recovery_heals",
    "vv2_gong_of_wonder_coconuts_fix",
    "vv2_write_village_statistics",
}


class VV1VV2OriginsPlaytestTests(unittest.TestCase):
    def test_standalone_records_are_enabled_for_requested_playtest(self) -> None:
        for filename, feature_id in (
            ("vv1_origins_feature.json", "vv1_enable_origins_exclusive_features"),
            ("vv1_origins_village_wide_upgrades.json", "vv1_origins_village_wide_upgrades"),
            ("vv2_origins_feature.json", "vv2_enable_origins_exclusive_features"),
            ("vv2_origins_village_wide_upgrades.json", "vv2_origins_village_wide_upgrades"),
        ):
            with self.subTest(feature=feature_id):
                record = json.loads((ROOT / "data" / filename).read_text(encoding="utf-8"))
                self.assertEqual(record["id"], feature_id)
                self.assertIs(record.get("enabled", True), True)
                self.assertTrue(record["patches"])
                if "origins_feature" in filename:
                    self.assertIs(record["catalog_enabled"], True)
                    self.assertIs(record["catalog_hidden"], False)
                    # These are shipped (no longer confirmation-pending): the
                    # description is the real user-facing Origins Upgrades blurb.
                    self.assertIn(
                        "Adds Origins-style Upgrades buttons", record["description"]
                    )

        source_vv1 = (ROOT / "scripts" / "build_vv1_origins_feature.py").read_text(encoding="utf-8")
        source_vv2 = (ROOT / "scripts" / "build_vv2_origins_feature.py").read_text(encoding="utf-8")
        source_village = (ROOT / "scripts" / "build_village_wide_origins_features.py").read_text(encoding="utf-8")
        for source in (source_vv1, source_vv2):
            self.assertIn('"enabled": True', source)
            self.assertIn('"catalog_enabled": True', source)
            self.assertIn('"catalog_hidden": False', source)
        self.assertIn('feature["enabled"] = enabled', source_village)
        self.assertIn("enabled = True", source_village)

    def test_public_ids_are_catalog_gui_cli_and_dependency_resolvable(self) -> None:
        catalog = load_fun_patches()
        catalog_ids = {item.id for item in catalog}
        self.assertTrue(PUBLIC.issubset(catalog_ids))
        self.assertTrue(PUBLIC.issubset({item.id for _, items in group_fun_patches(load_builds(), catalog) for item in items}))
        help_text = subprocess.check_output(
            [sys.executable, "src/vv_fun_patcher.py", "dry-run", "--help"],
            cwd=ROOT,
            text=True,
        )
        for feature_id in PUBLIC:
            if feature_id.endswith("_origins_village_wide_upgrades"):
                self.assertIn(feature_id, help_text)
            else:
                self.assertNotIn(feature_id, help_text)
            request = (
                [f"{feature_id[:3]}_enable_origins_exclusive_features", feature_id]
                if feature_id.endswith("_origins_village_wide_upgrades")
                else [feature_id]
            )
            self.assertEqual(
                resolve_fun_patch_ids(request, game_id=feature_id[:3], patches=catalog),
                request,
            )
            self.assertEqual(get_fun_patch(feature_id).id, feature_id)

        for feature_id in (
            "vv1_full_mastery_all_stage_a_candidate",
            "vv2_full_mastery_all_stage_a_candidate",
            "vv2_individual_full_mastery_candidate",
        ):
            with self.subTest(feature=feature_id):
                self.assertNotIn(feature_id, catalog_ids)
                with self.assertRaises(PatcherError):
                    get_fun_patch(feature_id)

    def test_crash_trigger_and_playtest_boundaries_are_documented(self) -> None:
        docs = [
            ROOT / "README.md",
            ROOT / "docs" / "origins-playtest-readiness.md",
            ROOT / "docs" / "origins-player-runtime-checklist.md",
            ROOT / "docs" / "transparency-log.md",
        ]
        for path in docs:
            text = path.read_text(encoding="utf-8")
            folded = " ".join(text.split()).casefold()
            self.assertIn("time warp", folded)
            self.assertIn("food point doubler", folded)
            self.assertIn("crash", folded)
            self.assertIn("purchased/success dialog", folded)
            self.assertIn("playtest", folded)
            self.assertIn("runtime", folded)

    def test_remaining_vv2_features_render_without_origins_owners(self) -> None:
        build = next(item for item in load_builds() if item.id == "vv2")
        source = ROOT / "research" / "stock-executables" / build.input_name
        catalog = load_fun_patches()
        remaining = [
            patch.id
            for patch in catalog
            if patch.game_id == "vv2"
            and patch.id not in {
                "vv2_full_mastery_all_stage_a_candidate",
                "vv2_individual_full_mastery_candidate",
                *PUBLIC,
            }
        ]
        self.assertEqual(set(remaining), REMAINING)
        public_offsets = set()
        for filename in ("vv2_origins_feature.json", "vv2_origins_village_wide_upgrades.json"):
            record = json.loads((ROOT / "data" / filename).read_text(encoding="utf-8"))
            public_offsets.update(int(item["offset"], 0) for item in record["patches"])
        for mode in load_patch_modes():
            with self.subTest(mode=mode.id):
                rendered, applied = render_patched_bytes(source, build, mode.id, remaining)
                self.assertEqual(len(rendered), build.size)
                owners = {item["owner"].removeprefix("feature:") for item in applied}
                self.assertTrue(PUBLIC.isdisjoint(owners))
                self.assertTrue(
                    public_offsets.isdisjoint(
                        {
                            int(item["offset"], 0)
                            for item in applied
                            if item["owner"].removeprefix("feature:") in PUBLIC
                        }
                    )
                )
        with tempfile.TemporaryDirectory() as temp:
            game = Path(temp) / build.title
            game.mkdir()
            copied = game / build.input_name
            copied.write_bytes(source.read_bytes())
            from vv_fun_patcher import apply_patch  # noqa: PLC0415

            output, log_path = apply_patch(copied, "collection_progression", fun_patch_ids=remaining)
            self.assertFalse((output.parent / "VVFP VV2 Origins Icons.dll").exists())
            self.assertFalse((output.parent / "VVFP Origins Icons.dll").exists())
            log = json.loads(log_path.read_text(encoding="utf-8"))
            self.assertTrue(PUBLIC.isdisjoint(log["fun_patches"]))


if __name__ == "__main__":
    unittest.main()
