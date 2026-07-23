from __future__ import annotations

import hashlib
import json
import shutil
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import (  # noqa: E402
    DEFAULT_PATCH_MODE,
    PatcherError,
    apply_all,
    apply_patch,
    dry_run,
    dry_run_all,
    get_patch_variant,
    identify,
    load_builds,
    load_fun_patches,
    load_patch_modes,
    render_patched_bytes,
    validate_all_sources,
)

STOCK = ROOT / "research" / "stock-executables"
MODES = ("collection_progression", "immediate_fixed")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


class ManifestTests(unittest.TestCase):
    def test_modes_names_targets_and_safety_guards(self) -> None:
        builds = load_builds()
        self.assertEqual([build.id for build in builds], ["vv1", "vv2", "vv3", "vv4", "vv5"])
        self.assertEqual([mode.id for mode in load_patch_modes()], list(MODES))
        self.assertEqual(DEFAULT_PATCH_MODE, "collection_progression")
        for build in builds:
            self.assertEqual(build.absolute_maximum, build.villager_slots)
            self.assertEqual(len(build.safety_patches), 4)
            for mode in MODES:
                variant = get_patch_variant(build, mode)
                suffix = "Modified Max Pop.exe" if mode == MODES[0] else "Fixed Max Pop.exe"
                self.assertEqual(variant["output_name"], f"{build.title} - {suffix}")
            if build.id == "vv1":
                self.assertFalse(get_patch_variant(build, MODES[0])["bonuses_affect_maximum"])
            else:
                self.assertTrue(get_patch_variant(build, MODES[0])["bonuses_affect_maximum"])
            self.assertFalse(get_patch_variant(build, MODES[1])["bonuses_affect_maximum"])

    def test_unknown_file_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "unknown.exe"
            path.write_bytes(b"MZ" + b"\0" * 200)
            with self.assertRaises(PatcherError):
                identify(path)


class StockIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        for build in load_builds():
            path = STOCK / build.input_name
            if not path.is_file():
                self.skipTest(f"Missing research stock executable: {path}")

    def copy_game_folders(self, root: Path) -> dict[str, Path]:
        result = {}
        for build in load_builds():
            folder = root / build.id
            folder.mkdir(parents=True)
            shutil.copy2(STOCK / build.input_name, folder / build.input_name)
            result[build.id] = folder
        return result

    def assert_no_outputs(self, folders: dict[str, Path]) -> None:
        for build in load_builds():
            for mode in MODES:
                output = folders[build.id] / get_patch_variant(build, mode)["output_name"]
                self.assertFalse(output.exists())
                self.assertFalse(output.with_suffix(".patch-log.json").exists())

    def test_both_modes_render_all_five_with_exact_guards(self) -> None:
        for build in load_builds():
            source = STOCK / build.input_name
            self.assertEqual(identify(source).id, build.id)
            original = source.read_bytes()
            for mode in MODES:
                with self.subTest(game=build.id, mode=mode):
                    rendered, applied = render_patched_bytes(source, build, mode)
                    expected_count = len(build.safety_patches) + len(
                        get_patch_variant(build, mode)["patches"]
                    )
                    self.assertEqual(len(applied), expected_count)
                    self.assertEqual(len(rendered), len(original))
                    self.assertNotEqual(rendered, original)
                    checksum_offset = struct.unpack_from("<I", rendered, 0x3C)[0] + 24 + 64
                    self.assertNotEqual(struct.unpack_from("<I", rendered, checksum_offset)[0], 0)
                    preview = dry_run(source, mode)
                    self.assertEqual(preview["patch_mode"], mode)
                    self.assertEqual(preview["absolute_maximum"], build.villager_slots)
                    self.assertEqual(preview["villager_slots"], build.villager_slots)
                    self.assertIn("remaining villager slots", preview["multiple_birth_saturation"])

    def test_immediate_mode_fixed_arithmetic(self) -> None:
        checks = {
            "vv2": (0x4B378, bytes.fromhex("BFA6000000")),
            "vv3": (0x5FEA2, bytes.fromhex("BE3C000000")),
            "vv4": (0x683AA, bytes.fromhex("BE3C000000")),
            "vv5": (0x72C04, bytes.fromhex("BE3C000000")),
        }
        for build in load_builds():
            if build.id not in checks:
                continue
            offset, expected = checks[build.id]
            rendered, _ = render_patched_bytes(
                STOCK / build.input_name, build, "immediate_fixed"
            )
            self.assertEqual(bytes(rendered[offset : offset + len(expected)]), expected)

    def test_vv5_progression_uses_true_135_base_detour(self) -> None:
        build = next(build for build in load_builds() if build.id == "vv5")
        rendered, _ = render_patched_bytes(
            STOCK / build.input_name, build, "collection_progression"
        )
        self.assertEqual(
            bytes(rendered[0x72C49:0x72C50]),
            bytes.fromhex("E9321802009090"),
        )
        self.assertEqual(
            bytes(rendered[0x94480:0x94493]),
            bytes.fromhex("81C6870000003BDE0F8CC8E7FDFFE9BDE7FDFF"),
        )
        self.assertEqual(
            [135 + bonus for bonus in (0, 5, 10, 15)],
            [135, 140, 145, 150],
        )

    def test_saturation_thresholds_fill_but_never_exceed_slots(self) -> None:
        for build in load_builds():
            cap = build.villager_slots
            for population in range(cap - 4, cap):
                remaining = cap - population
                for rolled in (1, 2, 3):
                    delivered = min(rolled, remaining)
                    self.assertGreaterEqual(delivered, 1)
                    self.assertLessEqual(population + delivered, cap)
                    self.assertEqual(population + delivered, min(population + rolled, cap))

    def test_both_outputs_coexist_beside_originals(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            folders = self.copy_game_folders(Path(temp))
            source_hashes = {
                build.id: digest(folders[build.id] / build.input_name)
                for build in load_builds()
            }
            for mode in MODES:
                results = apply_all(folders, mode)
                self.assertEqual(len(results), 5)
            for build in load_builds():
                source = folders[build.id] / build.input_name
                self.assertEqual(digest(source), source_hashes[build.id])
                for mode in MODES:
                    output = folders[build.id] / get_patch_variant(build, mode)["output_name"]
                    self.assertTrue(output.is_file())
                    log = json.loads(output.with_suffix(".patch-log.json").read_text())
                    self.assertEqual(log["patch_mode"], mode)
                    self.assertEqual(log["output_path"], str(output))
                    self.assertEqual(log["villager_slots"], build.villager_slots)

    def test_bulk_dry_run_is_no_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            folders = self.copy_game_folders(Path(temp))
            for mode in MODES:
                results = dry_run_all(folders, mode)
                self.assertEqual(len(results), 5)
            self.assert_no_outputs(folders)

    def test_invalid_bulk_input_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            folders = self.copy_game_folders(Path(temp))
            bad = folders["vv5"] / load_builds()[-1].input_name
            bad.write_bytes(bad.read_bytes()[:-1] + bytes([bad.read_bytes()[-1] ^ 1]))
            with self.assertRaises(PatcherError):
                apply_all(folders, DEFAULT_PATCH_MODE)
            self.assert_no_outputs(folders)

    def test_existing_selected_mode_output_is_atomic_no_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            folders = self.copy_game_folders(Path(temp))
            first = load_builds()[0]
            sentinel = folders[first.id] / get_patch_variant(first, DEFAULT_PATCH_MODE)["output_name"]
            sentinel.write_bytes(b"sentinel")
            with self.assertRaises(PatcherError):
                apply_all(folders, DEFAULT_PATCH_MODE)
            self.assertEqual(sentinel.read_bytes(), b"sentinel")
            for build in load_builds()[1:]:
                output = folders[build.id] / get_patch_variant(build, DEFAULT_PATCH_MODE)["output_name"]
                self.assertFalse(output.exists())

    def test_folder_validation_requires_the_expected_exe(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            folders = self.copy_game_folders(Path(temp))
            build = load_builds()[2]
            (folders[build.id] / build.input_name).unlink()
            with self.assertRaises(PatcherError):
                validate_all_sources(folders)
            self.assert_no_outputs(folders)

    def test_single_apply_uses_selected_mode_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            build = load_builds()[3]
            source = Path(temp) / build.input_name
            shutil.copy2(STOCK / build.input_name, source)
            output, log = apply_patch(source, "immediate_fixed")
            self.assertEqual(output.name, get_patch_variant(build, "immediate_fixed")["output_name"])
            self.assertTrue(log.is_file())
            self.assertTrue(source.is_file())

    def test_vv1_school_lessons_grant_skill_is_guarded_and_additive(self) -> None:
        feature_id = "vv1_school_lessons_grant_skill"
        feature = next(patch for patch in load_fun_patches() if patch.id == feature_id)
        build = next(build for build in load_builds() if build.id == "vv1")
        source = STOCK / build.input_name
        rendered, applied = render_patched_bytes(source, build, DEFAULT_PATCH_MODE, [feature_id])
        self.assertEqual(len(applied), len(build.safety_patches) + len(get_patch_variant(build, DEFAULT_PATCH_MODE)["patches"]) + len(feature.patches))
        self.assertEqual(bytes(rendered[0x44BF2:0x44BF8]), bytes.fromhex("E9E919010090"))
        self.assertEqual(bytes(rendered[0x565E0:0x5660D]), bytes.fromhex("606A64E828C9FAFF83C40499B905000000F7F98D8493B00000008338647D02FF00616A646A006A00E9EBE5FEFF"))
        preview = dry_run(source, DEFAULT_PATCH_MODE, [feature_id])
        self.assertEqual(preview["output_name"], "Virtual Villagers - A New Home - Modified Max Pop + School Grants Skill.exe")

    def test_vv1_continue_research_at_max_technologies_is_guarded(self) -> None:
        feature_id = "vv1_continue_research_at_max_technologies"
        build = next(build for build in load_builds() if build.id == "vv1")
        source = STOCK / build.input_name
        rendered, _ = render_patched_bytes(source, build, DEFAULT_PATCH_MODE, [feature_id])
        self.assertEqual(rendered[0x47488], 0x13)
        preview = dry_run(source, DEFAULT_PATCH_MODE, [feature_id])
        self.assertEqual(preview["output_name"], "Virtual Villagers - A New Home - Modified Max Pop + Continue Max-Tech Research.exe")

    def test_vv1_fun_patches_combine_without_overlap(self) -> None:
        feature_ids = ["vv1_school_lessons_grant_skill", "vv1_continue_research_at_max_technologies"]
        build = next(build for build in load_builds() if build.id == "vv1")
        rendered, _ = render_patched_bytes(STOCK / build.input_name, build, DEFAULT_PATCH_MODE, feature_ids)
        self.assertEqual(bytes(rendered[0x44BF2:0x44BF8]), bytes.fromhex("E9E919010090"))
        self.assertEqual(rendered[0x47488], 0x13)
        preview = dry_run(STOCK / build.input_name, DEFAULT_PATCH_MODE, feature_ids)
        self.assertEqual(preview["output_name"], "Virtual Villagers - A New Home - Modified Max Pop + School Grants Skill + Continue Max-Tech Research.exe")

    def test_vv2_easier_healing_mastery_is_guarded_and_additive(self) -> None:
        feature_id = "vv2_easier_healing_mastery"
        feature = next(patch for patch in load_fun_patches() if patch.id == feature_id)
        build = next(build for build in load_builds() if build.id == "vv2")
        source = STOCK / build.input_name
        rendered, applied = render_patched_bytes(
            source, build, DEFAULT_PATCH_MODE, [feature_id]
        )
        self.assertEqual(
            len(applied),
            len(build.safety_patches)
            + len(get_patch_variant(build, DEFAULT_PATCH_MODE)["patches"])
            + len(feature.patches),
        )
        self.assertEqual(
            bytes(rendered[0x604AD:0x604B6]),
            bytes.fromhex("E9EE37010090909090"),
        )
        self.assertEqual(
            bytes(rendered[0x73CA0:0x73CC4]),
            bytes.fromhex(
                "8BC569C08CE40000C78430E0070000090000006A64558BCE"
                "E8D3C8FEFF5F5D5B5EC20800"
            ),
        )
        preview = dry_run(source, DEFAULT_PATCH_MODE, [feature_id])
        self.assertEqual(preview["fun_patches"], [feature_id])
        self.assertEqual(
            preview["output_name"],
            "Virtual Villagers - The Lost Children - Modified Max Pop + Easier Healing.exe",
        )

    def test_vv2_easier_healing_output_and_log_preserve_original(self) -> None:
        feature_id = "vv2_easier_healing_mastery"
        build = next(build for build in load_builds() if build.id == "vv2")
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / build.input_name
            shutil.copy2(STOCK / build.input_name, source)
            original_hash = digest(source)
            output, log_path = apply_patch(
                source,
                DEFAULT_PATCH_MODE,
                fun_patch_ids=[feature_id],
            )
            self.assertEqual(digest(source), original_hash)
            self.assertIn("Easier Healing", output.name)
            log = json.loads(log_path.read_text())
            self.assertEqual(log["fun_patches"], [feature_id])
            self.assertEqual(log["fun_patch_names"], ["Easier Healing Mastery"])
            self.assertEqual(len(log["patches"]), 8)

    def test_vv2_teaching_children_grants_skill_is_guarded_and_additive(self) -> None:
        feature_id = "vv2_teaching_children_grants_skill"
        feature = next(patch for patch in load_fun_patches() if patch.id == feature_id)
        build = next(build for build in load_builds() if build.id == "vv2")
        source = STOCK / build.input_name
        rendered, applied = render_patched_bytes(
            source, build, DEFAULT_PATCH_MODE, [feature_id]
        )
        self.assertEqual(
            len(applied),
            len(build.safety_patches)
            + len(get_patch_variant(build, DEFAULT_PATCH_MODE)["patches"])
            + len(feature.patches),
        )
        self.assertEqual(
            bytes(rendered[0x4A7FA:0x4A7FF]),
            bytes.fromhex("E9D1940200"),
        )
        self.assertEqual(
            bytes(rendered[0x73CD0:0x73CFC]),
            bytes.fromhex(
                "606A64E8C8F4F8FF83C40499B905000000F7F98D8493DC070000"
                "8338647D02FF00616896000000E9036BFDFF"
            ),
        )
        preview = dry_run(source, DEFAULT_PATCH_MODE, [feature_id])
        self.assertEqual(preview["fun_patches"], [feature_id])
        self.assertEqual(
            preview["output_name"],
            "Virtual Villagers - The Lost Children - Modified Max Pop + Teaching Grants Skill.exe",
        )

    def test_vv2_fun_patches_combine_without_overlap(self) -> None:
        feature_ids = [
            "vv2_easier_healing_mastery",
            "vv2_teaching_children_grants_skill",
        ]
        build = next(build for build in load_builds() if build.id == "vv2")
        source = STOCK / build.input_name
        rendered, applied = render_patched_bytes(
            source, build, DEFAULT_PATCH_MODE, feature_ids
        )
        feature_patch_count = sum(
            len(patch.patches)
            for patch in load_fun_patches()
            if patch.id in feature_ids
        )
        self.assertEqual(
            len(applied),
            len(build.safety_patches)
            + len(get_patch_variant(build, DEFAULT_PATCH_MODE)["patches"])
            + feature_patch_count,
        )
        self.assertEqual(bytes(rendered[0x73CA0:0x73CC4]), bytes.fromhex(
            "8BC569C08CE40000C78430E0070000090000006A64558BCEE8D3C8FEFF5F5D5B5EC20800"
        ))
        self.assertEqual(bytes(rendered[0x73CD0:0x73CFC]), bytes.fromhex(
            "606A64E8C8F4F8FF83C40499B905000000F7F98D8493DC0700008338647D02FF00616896000000E9036BFDFF"
        ))
        preview = dry_run(source, DEFAULT_PATCH_MODE, feature_ids)
        self.assertEqual(preview["fun_patches"], feature_ids)
        self.assertEqual(
            preview["output_name"],
            "Virtual Villagers - The Lost Children - Modified Max Pop + Easier Healing + Teaching Grants Skill.exe",
        )

    def test_vv5_heathen_mommy_puzzle_is_guarded_and_additive(self) -> None:
        feature_id = "vv5_heathen_mommy_puzzle"
        feature = next(patch for patch in load_fun_patches() if patch.id == feature_id)
        build = next(build for build in load_builds() if build.id == "vv5")
        source = STOCK / build.input_name
        rendered, applied = render_patched_bytes(
            source, build, DEFAULT_PATCH_MODE, [feature_id]
        )
        self.assertEqual(
            len(applied),
            len(build.safety_patches)
            + len(get_patch_variant(build, DEFAULT_PATCH_MODE)["patches"])
            + len(feature.patches),
        )
        self.assertEqual(
            bytes(rendered[0x48F16:0x48F1B]),
            bytes.fromhex("E965B40400"),
        )
        self.assertEqual(
            bytes(rendered[0x94380:0x943D4]),
            bytes.fromhex(
                "6A11B908E05100E8F46AFAFF84C07416E81BB8FBFF68C5010000"
                "68710300006858010000EB14E805B8FBFF68C50100006871030000"
                "68570100008BC8E88FB8FBFF8B4F0850E8661AF7FFB9680F5200"
                "E9474BFBFF"
            ),
        )
        preview = dry_run(source, DEFAULT_PATCH_MODE, [feature_id])
        self.assertEqual(preview["fun_patches"], [feature_id])
        self.assertEqual(
            preview["output_name"],
            "Virtual Villagers - New Believers - Modified Max Pop + Heathen Mommy.exe",
        )

    def test_vv5_easier_devotee_training_is_guarded_and_additive(self) -> None:
        feature_id = "vv5_easier_devotee_training"
        feature = next(patch for patch in load_fun_patches() if patch.id == feature_id)
        build = next(build for build in load_builds() if build.id == "vv5")
        source = STOCK / build.input_name
        rendered, applied = render_patched_bytes(
            source, build, DEFAULT_PATCH_MODE, [feature_id]
        )
        self.assertEqual(
            len(applied),
            len(build.safety_patches)
            + len(get_patch_variant(build, DEFAULT_PATCH_MODE)["patches"])
            + len(feature.patches),
        )
        self.assertEqual(
            bytes(rendered[0x6F1DD:0x6F1E6]),
            bytes.fromhex("E91E52020090909090"),
        )
        self.assertEqual(
            bytes(rendered[0x6F1F5:0x6F1FC]),
            bytes.fromhex("E9465202009090"),
        )
        self.assertEqual(
            bytes(rendered[0x94400:0x9441B]),
            bytes.fromhex(
                "83B9FC1C00000D74083999701C00007E05E9D0ADFDFFE91FAEFDFF"
            ),
        )
        self.assertEqual(
            bytes(rendered[0x94440:0x94460]),
            bytes.fromhex(
                "8B8E881B000083B9FC1C00000D7405E9BAADFDFF6A64E805F2F6FFE99CADFDFF"
            ),
        )
        preview = dry_run(source, DEFAULT_PATCH_MODE, [feature_id])
        self.assertEqual(preview["fun_patches"], [feature_id])
        self.assertEqual(
            preview["output_name"],
            "Virtual Villagers - New Believers - Modified Max Pop + Easier Devotee.exe",
        )

    def test_vv5_fun_patches_combine_without_overlap(self) -> None:
        feature_ids = [
            "vv5_heathen_mommy_puzzle",
            "vv5_easier_devotee_training",
        ]
        build = next(build for build in load_builds() if build.id == "vv5")
        source = STOCK / build.input_name
        rendered, applied = render_patched_bytes(
            source, build, DEFAULT_PATCH_MODE, feature_ids
        )
        feature_patch_count = sum(
            len(patch.patches)
            for patch in load_fun_patches()
            if patch.id in feature_ids
        )
        self.assertEqual(
            len(applied),
            len(build.safety_patches)
            + len(get_patch_variant(build, DEFAULT_PATCH_MODE)["patches"])
            + feature_patch_count,
        )
        self.assertEqual(bytes(rendered[0x48F16:0x48F1B]), bytes.fromhex("E965B40400"))
        self.assertEqual(bytes(rendered[0x6F1DD:0x6F1E6]), bytes.fromhex("E91E52020090909090"))
        self.assertEqual(bytes(rendered[0x94440:0x94460]), bytes.fromhex(
            "8B8E881B000083B9FC1C00000D7405E9BAADFDFF6A64E805F2F6FFE99CADFDFF"
        ))
        preview = dry_run(source, DEFAULT_PATCH_MODE, feature_ids)
        self.assertEqual(preview["fun_patches"], feature_ids)
        self.assertEqual(
            preview["output_name"],
            "Virtual Villagers - New Believers - Modified Max Pop + Heathen Mommy + Easier Devotee.exe",
        )

    def test_bulk_feature_applies_only_to_its_game(self) -> None:
        feature_id = "vv2_easier_healing_mastery"
        with tempfile.TemporaryDirectory() as temp:
            folders = self.copy_game_folders(Path(temp))
            previews = dry_run_all(folders, DEFAULT_PATCH_MODE, [feature_id])
            by_game = {result["game"]: result for result in previews}
            for build in load_builds():
                expected = [feature_id] if build.id == "vv2" else []
                self.assertEqual(by_game[build.title]["fun_patches"], expected)
            results = apply_all(
                folders,
                DEFAULT_PATCH_MODE,
                fun_patch_ids=[feature_id],
            )
            self.assertEqual(len(results), 5)
            self.assertTrue(any("Easier Healing" in output.name for output, _ in results))


if __name__ == "__main__":
    unittest.main()
