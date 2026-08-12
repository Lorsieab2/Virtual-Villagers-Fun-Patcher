from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import (  # noqa: E402
    PatcherError,
    load_builds,
    load_fun_patches,
    render_patched_bytes,
    resolve_fun_patch_ids,
)
from vv_fun_patcher_gui import group_fun_patches  # noqa: E402

STOCK = ROOT / "research" / "stock-executables"
GAME_IDS = tuple(f"vv{game}" for game in range(1, 6))


def raw_record(game_id: str) -> dict:
    return json.loads(
        (ROOT / "data" / f"{game_id}_origins_village_wide_upgrades.json").read_text(
            encoding="utf-8"
        )
    )


class VillageWidePlaytestCatalogTests(unittest.TestCase):
    def test_all_five_records_are_enabled_for_requested_playtest(self) -> None:
        catalog = load_fun_patches()
        catalog_ids = {patch.id for patch in catalog}
        for game_id in GAME_IDS:
            with self.subTest(game=game_id):
                base_id = f"{game_id}_enable_origins_exclusive_features"
                wide_id = f"{game_id}_origins_village_wide_upgrades"
                self.assertIn(base_id, catalog_ids)
                self.assertIn(wide_id, catalog_ids)

                base = json.loads(
                    (ROOT / "data" / f"{game_id}_origins_feature.json").read_text(
                        encoding="utf-8"
                    )
                )
                wide = raw_record(game_id)
                self.assertIs(base.get("enabled", True), True)
                self.assertIs(base.get("catalog_enabled", True), True)
                self.assertIs(base.get("catalog_hidden", False), False)
                self.assertIs(wide["enabled"], True)
                self.assertTrue(wide["patches"])
                self.assertEqual(
                    wide["dependencies"],
                    [base_id],
                )
                for label in (
                    "All Villagers Like Running",
                    "Grant Full Mastery to All Villagers",
                    "All Villagers are 18",
                    "1,000,000",
                ):
                    self.assertIn(label, wide["description"])

    def test_catalog_gui_cli_and_dependency_resolution_exposes_all_records(self) -> None:
        catalog = load_fun_patches()
        catalog_ids = {patch.id for patch in catalog}
        grouped = group_fun_patches(load_builds(), catalog)
        grouped_ids = {patch.id for _, patches in grouped for patch in patches}
        self.assertTrue(catalog_ids.issubset(grouped_ids))
        help_text = subprocess.check_output(
            [sys.executable, str(ROOT / "src" / "vv_fun_patcher.py"), "dry-run", "--help"],
            cwd=ROOT,
            text=True,
        )
        for game_id in GAME_IDS:
            base_id = f"{game_id}_enable_origins_exclusive_features"
            wide_id = f"{game_id}_origins_village_wide_upgrades"
            self.assertIn(base_id, help_text)
            self.assertIn(wide_id, help_text)
            selected = resolve_fun_patch_ids(
                [base_id, wide_id], game_id=game_id, patches=catalog
            )
            self.assertEqual(selected, [base_id, wide_id])

    def test_origins_pairs_render_without_overlapping_payloads(self) -> None:
        for build in load_builds():
            source = STOCK / build.input_name
            before = source.read_bytes()
            base_id = f"{build.id}_enable_origins_exclusive_features"
            wide_id = f"{build.id}_origins_village_wide_upgrades"
            selected = resolve_fun_patch_ids([base_id, wide_id], game_id=build.id)
            expected_owner_names = {f"feature:{base_id}", f"feature:{wide_id}"}
            modes = ["collection_progression", "immediate_fixed"]
            if build.id in {"vv1", "vv2"}:
                modes.insert(0, "stock")
            for mode in modes:
                with self.subTest(game=build.id, mode=mode):
                    rendered, applied = render_patched_bytes(
                        source, build, mode, selected
                    )
                    self.assertGreaterEqual(len(rendered), build.size)
                    self.assertEqual(source.read_bytes(), before)
                    owners = {item["owner"] for item in applied}
                    self.assertTrue(expected_owner_names.issubset(owners))
                    wide_record = raw_record(build.id)
                    wide_patch = wide_record["patches"][0]
                    wide_offset = int(wide_patch["offset"], 0)
                    wide_length = len(bytes.fromhex(wide_patch["after"]))
                    self.assertTrue(
                        any(
                            item["owner"] == f"feature:{wide_id}"
                            and int(item["offset"], 0) == wide_offset
                            and len(bytes.fromhex(item["after"])) == wide_length
                            for item in applied
                        )
                    )

            if build.id in {"vv3", "vv4", "vv5"}:
                with self.subTest(game=build.id, mode="stock"):
                    with self.assertRaisesRegex(PatcherError, "has no append layout"):
                        render_patched_bytes(source, build, "stock", selected)

    def test_base_origins_is_still_independently_composable(self) -> None:
        for build in load_builds():
            base_id = f"{build.id}_enable_origins_exclusive_features"
            mode = "stock" if build.id in {"vv1", "vv2"} else "collection_progression"
            _, applied = render_patched_bytes(
                STOCK / build.input_name, build, mode, [base_id]
            )
            self.assertIn(f"feature:{base_id}", {item["owner"] for item in applied})

    def test_companion_hash_and_payload_contract_remain_exact(self) -> None:
        companion = ROOT / "assets" / "origins" / "VVFP Origins Icons.dll"
        expected_hash = hashlib.sha256(companion.read_bytes()).hexdigest().upper()
        for game_id in GAME_IDS:
            with self.subTest(game=game_id):
                base = json.loads(
                    (ROOT / "data" / f"{game_id}_origins_feature.json").read_text(
                        encoding="utf-8"
                    )
                )
                wide = raw_record(game_id)
                self.assertEqual(base["companion_files"][0]["sha256"], expected_hash)
                self.assertEqual(wide["patches"][0]["purpose"].startswith("install the optional"), True)
                self.assertEqual(
                    len(bytes.fromhex(wide["patches"][0]["before"])),
                    len(bytes.fromhex(wide["patches"][0]["after"])),
                )


if __name__ == "__main__":
    unittest.main()
