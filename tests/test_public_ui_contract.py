from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher as patcher


class PublicUiContractTests(unittest.TestCase):
    def test_authoritative_status_is_fail_closed(self):
        status = json.loads((ROOT / "data/public-ui-status.json").read_text(encoding="utf-8"))
        self.assertEqual(status["policy"]["time_warp_caption"], "Time Warp - Advances 3 Villager Years")
        self.assertEqual(status["policy"]["remove_allowed_only_for"], ["Food Doubler", "Tech Doubler"])
        self.assertEqual(status["games"]["vv3"]["running"], "disabled_hidden")
        self.assertNotEqual(status["games"]["vv3"]["full_heal"], "public")
        self.assertEqual(status["games"]["vv4"]["full_heal"], "disabled_hidden")
        self.assertEqual(status["games"]["vv5"]["full_mastery"], "disabled_hidden")
        self.assertEqual(status["games"]["vv5"]["tech_detail_click_route"], "stop_unproved")

    def test_collectibles_are_explicitly_hidden_without_catalog_entries(self):
        status = json.loads((ROOT / "data/public-ui-status.json").read_text(encoding="utf-8"))
        for game in ("vv2", "vv3", "vv4", "vv5"):
            self.assertEqual(
                status["games"][game]["collectibles"],
                {
                    "reset_all_collections": "disabled_hidden",
                    "complete_all_collections": "disabled_hidden",
                },
            )

        # The status table is metadata only: neither planned action is a
        # resolver/catalog entry or a native output route.
        patcher_source = (ROOT / "src/vv_fun_patcher.py").read_text(encoding="utf-8")
        builds_source = (ROOT / "data/builds.json").read_text(encoding="utf-8")
        for action_id in ("reset_all_collections", "complete_all_collections"):
            self.assertNotIn(action_id, patcher_source)
            self.assertNotIn(action_id, builds_source)

    def test_vv3_vv4_composed_sources_use_only_exact_time_warp_caption(self):
        old = "Time Warp - 3 villager years"
        exact = "Time Warp - Advances 3 Villager Years"
        for game in ("vv3", "vv4"):
            resource = (ROOT / f"native/{game}_full_mastery_candidate/{game}_full_mastery_candidate.rc").read_text(encoding="utf-8")
            self.assertNotIn(old, resource)
            self.assertEqual(resource.count(exact), 2)

    def test_permanent_button_sources_never_emit_done_or_unrestricted_remove(self):
        for game in ("vv3", "vv4", "vv5"):
            source = (ROOT / f"native/{game}_full_mastery_candidate/{game}_full_mastery_candidate.c").read_text(encoding="utf-8")
            self.assertNotIn('"Done"', source)
            self.assertEqual(source.count('SetDlgItemTextA(window, ID_BUY_FIRST + row, "Remove")'), 1)
            self.assertIn("row == 3 || row == 4", source)

    def test_stale_but_strictly_disabled_vv4_full_heal_does_not_abort_or_publish(self):
        manifest = {"id": patcher.VV4_FULL_HEAL_CANDIDATE_ID, "enabled": False, "catalog_hidden": True, "catalog_enabled": False, "stale": True}
        artifact = {"candidate_id": patcher.VV4_FULL_HEAL_CANDIDATE_ID, "candidate_enabled": False, "catalog_hidden": True, "catalog_enabled": False, "stale": True}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mp, ap = root / "manifest.json", root / "map.json"
            mp.write_text(json.dumps(manifest), encoding="utf-8")
            ap.write_text(json.dumps(artifact), encoding="utf-8")
            with patch.dict(patcher.VV4_FULL_HEAL_CANDIDATE_PATHS, {"manifest": mp, "map": ap}):
                self.assertIsNone(patcher._certified_vv4_full_heal_record({"id": "unused"}, {"id": "unused"}))

    def test_malformed_or_disagreeing_vv4_full_heal_fails_closed(self):
        cases = [
            ("{", "{}"),
            (json.dumps({"id": patcher.VV4_FULL_HEAL_CANDIDATE_ID, "enabled": False, "catalog_hidden": True, "catalog_enabled": False}),
             json.dumps({"candidate_id": patcher.VV4_FULL_HEAL_CANDIDATE_ID, "candidate_enabled": True, "catalog_hidden": False, "catalog_enabled": True})),
            (json.dumps({"id": patcher.VV4_FULL_HEAL_CANDIDATE_ID, "enabled": True, "catalog_hidden": False, "catalog_enabled": True}),
             json.dumps({"candidate_id": patcher.VV4_FULL_HEAL_CANDIDATE_ID, "candidate_enabled": True, "catalog_hidden": False, "catalog_enabled": True})),
        ]
        for manifest, artifact in cases:
            with self.subTest(manifest=manifest):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    mp, ap = root / "manifest.json", root / "map.json"
                    mp.write_text(manifest, encoding="utf-8")
                    ap.write_text(artifact, encoding="utf-8")
                    with patch.dict(patcher.VV4_FULL_HEAL_CANDIDATE_PATHS, {"manifest": mp, "map": ap}):
                        with self.assertRaises(patcher.PatcherError):
                            patcher._certified_vv4_full_heal_record({"id": "unused"}, {"id": "unused"})

    def test_disabled_full_heal_absent_from_loader_gui_cli_and_select_all(self):
        source = (ROOT / "src/vv_fun_patcher.py").read_text(encoding="utf-8")
        gui = (ROOT / "src/vv_fun_patcher_gui.py").read_text(encoding="utf-8")
        self.assertIn("load_fun_patches()", source)
        self.assertIn("load_fun_patches()", gui)
        # The VV2 stale-pin lane is unrelated to this VV3-VV5 containment test.
        with patch.object(patcher, "_certified_vv2_full_mastery_record", return_value=None):
            records = patcher.load_fun_patches()
        ids = {record.id for record in records}
        self.assertNotIn(patcher.VV4_FULL_HEAL_CANDIDATE_ID, ids)

    def test_disabled_vv3_full_heal_is_not_documented_as_available_cli_id(self):
        readme_lines = (ROOT / "README.md").read_text(encoding="utf-8").splitlines()
        available_line = next(line for line in readme_lines if "The available IDs are" in line)
        self.assertNotIn(patcher.VV3_FULL_HEAL_CANDIDATE_ID, available_line)
        self.assertIn("not a CLI or catalog ID", "\n".join(readme_lines))

    def test_hidden_vv3_full_heal_cannot_enter_catalog_when_stale_enabled(self):
        stale_hidden = {
            "id": patcher.VV3_FULL_HEAL_CANDIDATE_ID,
            "game_id": "vv3",
            "name": "Full Heal / Cure All",
            "enabled": True,
            "catalog_hidden": True,
            "catalog_enabled": False,
            "patches": [],
            "patch_mode_overrides": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate = root / "vv3-full-heal.json"
            running = root / "vv3-running.json"
            candidate.write_text(json.dumps(stale_hidden), encoding="utf-8")
            running.write_text(json.dumps({"enabled": True}), encoding="utf-8")
            with (
                patch.dict(patcher.VV3_FULL_HEAL_CANDIDATE_PATHS, {"manifest": candidate}),
                patch.dict(patcher.VV3_INDIVIDUAL_RUNNING_CANDIDATE_PATHS, {"manifest": running}),
                patch.object(patcher, "_manifest", return_value={"fun_patches": []}),
                patch.object(patcher, "ORIGINS_FEATURE_PATHS", []),
                patch.object(patcher, "ORIGINS_VILLAGE_WIDE_FEATURE_PATHS", []),
                patch.object(patcher, "STATISTICS_FEATURES_PATH", root / "missing-statistics.json"),
                patch.object(patcher, "_validate_vv3_individual_full_mastery_candidate", return_value=None),
                patch.object(patcher, "_certified_vv1_full_mastery_record", return_value=None),
                patch.object(patcher, "_certified_vv2_full_mastery_record", return_value=None),
            ):
                records = patcher._load_fun_patch_records()
            self.assertNotIn(patcher.VV3_FULL_HEAL_CANDIDATE_ID, {record.id for record in records})


if __name__ == "__main__":
    unittest.main()
