from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import (  # noqa: E402
    PatcherError,
    load_fun_patches,
    resolve_fun_patch_ids,
)


class GrantRunningCatalogContainmentTests(unittest.TestCase):
    BINDINGS = tuple(
        ROOT / "data" / "candidates" / f"vv{game}_individual_grant_running_binding.json"
        for game in range(1, 6)
    )
    WITHDRAWN_CANDIDATES = (
        ROOT / "data" / "candidates" / "vv3_all_villagers_like_running_candidate.json",
        ROOT / "data" / "candidates" / "vv3_individual_grant_running_candidate.json",
        ROOT / "data" / "candidates" / "vv3_individual_grant_running_revised_candidate.json",
        ROOT / "data" / "candidates" / "vv5_individual_running_candidate.json",
        ROOT / "data" / "candidates" / "vv3_full_heal_cure_all_candidate.json",
    )
    VILLAGE_WIDE = tuple(
        ROOT / "data" / f"vv{game}_origins_village_wide_upgrades.json"
        for game in range(1, 6)
    )
    PUBLIC_TEXT = (
        ROOT / "README.md",
        ROOT / "How to Use.txt",
        *(ROOT / "data" / f"vv{game}_origins_feature.json" for game in range(1, 6)),
        *(ROOT / "data" / f"vv{game}_origins_village_wide_upgrades.json" for game in range(1, 6)),
        ROOT / "docs" / "vv3-full-heal-candidate.md",
        ROOT / "docs" / "transparency-log.md",
        ROOT / "scripts" / "build_vv1_origins_feature.py",
        ROOT / "scripts" / "build_vv2_origins_feature.py",
        ROOT / "scripts" / "build_vv3_origins_feature.py",
        ROOT / "scripts" / "build_vv4_origins_feature.py",
        ROOT / "scripts" / "build_vv5_origins_feature.py",
        ROOT / "scripts" / "build_village_wide_origins_features.py",
        ROOT / "scripts" / "build_vv3_full_heal_candidate.py",
    )

    def test_all_new_bindings_are_stop_hidden_and_not_catalog_resolvable(self) -> None:
        catalog = load_fun_patches()
        catalog_ids = {item.id for item in catalog}
        for path in self.BINDINGS:
            with self.subTest(path=path.name):
                raw = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(raw["status"], "STOP")
                self.assertFalse(raw["enabled"])
                self.assertFalse(raw["catalog_enabled"])
                self.assertTrue(raw["catalog_hidden"])
                self.assertNotIn(raw["id"], catalog_ids)
                with self.assertRaises(PatcherError):
                    resolve_fun_patch_ids([raw["id"]], game_id=raw["game_id"], patches=catalog)

    def test_withdrawn_running_and_dependent_candidates_are_disabled_and_absent(self) -> None:
        catalog = load_fun_patches()
        catalog_ids = {item.id for item in catalog}
        for path in (*self.WITHDRAWN_CANDIDATES, *self.VILLAGE_WIDE):
            with self.subTest(path=path.name):
                raw = json.loads(path.read_text(encoding="utf-8"))
                self.assertFalse(raw.get("enabled", False))
                self.assertFalse(raw.get("catalog_enabled", False))
                self.assertTrue(raw.get("catalog_hidden", True))
                self.assertNotIn(raw["id"], catalog_ids)
                with self.assertRaises(PatcherError):
                    resolve_fun_patch_ids([raw["id"]], game_id=raw.get("game_id"), patches=catalog)

    def test_public_text_has_no_stale_running_availability_claims(self) -> None:
        forbidden = (
            "enabled/catalog-visible `vv3_individual_grant_running_candidate`",
            "the enabled/catalog-visible `vv3_individual_grant_running_candidate`",
            "vv3_full_heal_cure_all_candidate` is enabled/catalog-visible",
            "\"Full Heal / Cure All\" is enabled/catalog-visible",
            "VV3 All Villagers Like Running is enabled",
            "Grant Running to Selected Villager\". The VV3 selected-villager Running",
            "Grant Running only uses an available",
            "Grant Running only adds",
            "certified command-5 Full Heal / Cure All transaction replaces it",
            "Adds Villager Upgrades for Grant Youth, Grant Full Mastery, Grant Running, and Set Age to 18",
            "enabled static candidate; runtime pending",
        )
        for path in self.PUBLIC_TEXT:
            with self.subTest(path=path.name):
                text = path.read_text(encoding="utf-8").casefold()
                for phrase in forbidden:
                    self.assertNotIn(phrase.casefold(), text, f"stale claim in {path}: {phrase}")

    def test_full_heal_metadata_is_candidate_only_and_blocked_by_withdrawn_running(self) -> None:
        manifest = json.loads(self.WITHDRAWN_CANDIDATES[-1].read_text(encoding="utf-8"))
        artifact_map = json.loads(
            (ROOT / "data" / "candidates" / "vv3_full_heal_cure_all_candidate_map.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertFalse(manifest["enabled"])
        self.assertTrue(manifest["catalog_hidden"])
        self.assertFalse(manifest["catalog_enabled"])
        self.assertEqual(manifest["dependencies"], ["vv3_individual_grant_running_candidate"])
        self.assertFalse(artifact_map["candidate_enabled"])
        self.assertTrue(artifact_map["catalog_hidden"])
        self.assertFalse(artifact_map["catalog_enabled"])


if __name__ == "__main__":
    unittest.main()
