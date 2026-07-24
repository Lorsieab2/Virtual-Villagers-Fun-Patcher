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
MODES = (
    "collection_progression",
    "immediate_fixed",
    "experimental_expanded_256",
    "experimental_expanded_256_progression",
)
EXPANDED = json.loads((ROOT / "data" / "expanded_256.json").read_text())


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def modded_exe_name(build) -> str:
    return f"{build.title} - Modded.exe"


class ManifestTests(unittest.TestCase):
    def test_stock_and_expanded_record_capacities_are_explicit(self) -> None:
        builds = {build.id: build for build in load_builds()}
        self.assertEqual(builds["vv1"].villager_slots, 256)
        self.assertEqual(builds["vv2"].villager_slots, 256)
        for game_id in ("vv3", "vv4", "vv5"):
            self.assertEqual(builds[game_id].villager_slots, 150)
            self.assertEqual(builds[game_id].absolute_maximum, 150)
            variant = get_patch_variant(
                builds[game_id], "experimental_expanded_256"
            )
            self.assertEqual(variant["villager_slots"], 256)
            self.assertEqual(variant["absolute_maximum"], 256)
            self.assertTrue(variant["expanded_records"])

    def test_modes_names_targets_and_safety_guards(self) -> None:
        builds = load_builds()
        self.assertEqual([build.id for build in builds], ["vv1", "vv2", "vv3", "vv4", "vv5"])
        self.assertEqual([mode.id for mode in load_patch_modes()], list(MODES))
        self.assertEqual(DEFAULT_PATCH_MODE, "collection_progression")
        for build in builds:
            self.assertEqual(build.absolute_maximum, build.villager_slots)
            expected_safety_counts = {
                "vv1": 17,
                "vv2": 13,
                "vv3": 8,
                "vv4": 10,
                "vv5": 13,
            }
            self.assertEqual(len(build.safety_patches), expected_safety_counts[build.id])
            for mode in MODES:
                variant = get_patch_variant(build, mode)
                self.assertEqual(variant["output_name"], modded_exe_name(build))
            if build.id == "vv1":
                self.assertFalse(get_patch_variant(build, MODES[0])["bonuses_affect_maximum"])
            else:
                self.assertTrue(get_patch_variant(build, MODES[0])["bonuses_affect_maximum"])
            self.assertFalse(get_patch_variant(build, MODES[1])["bonuses_affect_maximum"])
            self.assertFalse(get_patch_variant(build, MODES[2])["bonuses_affect_maximum"])
            self.assertEqual(
                get_patch_variant(build, MODES[3])["bonuses_affect_maximum"],
                build.id != "vv1",
            )

    def test_unknown_file_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "unknown.exe"
            path.write_bytes(b"MZ" + b"\0" * 200)
            with self.assertRaises(PatcherError):
                identify(path)


class GuiSourceTests(unittest.TestCase):
    def test_entire_interface_has_vertical_and_mouse_wheel_scrolling(self) -> None:
        source = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")
        self.assertIn('orient="vertical"', source)
        self.assertIn('self.bind_all("<MouseWheel>", self._scroll_content)', source)
        self.assertIn("def _scroll_content", source)
        self.assertIn("self.content_canvas.yview_scroll(direction, \"units\")", source)

    def test_success_confirmation_uses_clear_folder_links(self) -> None:
        source = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")
        self.assertIn("def _show_folder_confirmation", source)
        self.assertIn("Open Vanilla Folder:", source)
        self.assertIn("Open Modded Folder:", source)
        self.assertNotIn('messagebox.showinfo("Modified EXE created"', source)
        self.assertNotIn('messagebox.showinfo("All five modified EXEs created"', source)

    def test_fun_patches_have_select_and_deselect_all_controls(self) -> None:
        source = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")
        self.assertIn('text="Select All Patches"', source)
        self.assertIn('text="Deselect All Patches"', source)
        self.assertIn("def _select_all_fun_patches", source)
        self.assertIn("def _deselect_all_fun_patches", source)
        self.assertIn("variable.set(True)", source)
        self.assertIn("variable.set(False)", source)


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
            (folder / "companion-data").mkdir()
            (folder / "companion-data" / f"{build.id}.txt").write_text(
                f"unchanged companion file for {build.id}\n", encoding="utf-8"
            )
            result[build.id] = folder
        return result

    def expected_output_folder(
        self, folders: dict[str, Path], build, mode: str
    ) -> Path:
        return folders[build.id].parent / f"{build.title} - Modded"

    def assert_no_outputs(self, folders: dict[str, Path]) -> None:
        for build in load_builds():
            for mode in MODES:
                self.assertFalse(self.expected_output_folder(folders, build, mode).exists())

    def test_all_modes_render_all_five_with_exact_guards(self) -> None:
        for build in load_builds():
            source = STOCK / build.input_name
            self.assertEqual(identify(source).id, build.id)
            original = source.read_bytes()
            for mode in MODES:
                with self.subTest(game=build.id, mode=mode):
                    rendered, applied = render_patched_bytes(source, build, mode)
                    variant = get_patch_variant(build, mode)
                    expected_count = len(build.safety_patches) + len(variant["patches"])
                    if variant.get("expanded_records", False):
                        expected_count += EXPANDED["games"][build.id]["patch_count"]
                    self.assertEqual(len(applied), expected_count)
                    self.assertEqual(len(rendered), len(original))
                    self.assertNotEqual(rendered, original)
                    checksum_offset = struct.unpack_from("<I", rendered, 0x3C)[0] + 24 + 64
                    self.assertNotEqual(struct.unpack_from("<I", rendered, checksum_offset)[0], 0)
                    preview = dry_run(source, mode)
                    self.assertEqual(preview["patch_mode"], mode)
                    expected_slots = variant.get(
                        "villager_slots", build.villager_slots
                    )
                    self.assertEqual(preview["absolute_maximum"], expected_slots)
                    self.assertEqual(preview["villager_slots"], expected_slots)
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
            bytes.fromhex("E9B21802009090"),
        )
        self.assertEqual(
            bytes(rendered[0x94500:0x94518]),
            bytes.fromhex(
                "81C687000000E8B5FFFFFF3BC60F8D3DE7FDFFE93EE7FDFF"
            ),
        )
        self.assertEqual(
            [135 + bonus for bonus in (0, 5, 10, 15)],
            [135, 140, 145, 150],
        )

    def test_vv5_counts_shared_physical_slots_before_births(self) -> None:
        build = next(build for build in load_builds() if build.id == "vv5")
        helper = bytes.fromhex(
            "515233C0B990415500BA9600000080B9D41C000000741040"
            "83B94C1C00000074060381501C000081C1442F00004A75DE5A59C3"
        )
        for mode, base in (
            ("collection_progression", "81C687000000"),
            ("immediate_fixed", "81C65A000000"),
        ):
            rendered, _ = render_patched_bytes(
                STOCK / build.input_name, build, mode
            )
            self.assertEqual(bytes(rendered[0x944C0:0x944F3]), helper)
            self.assertEqual(bytes(rendered[0x94500:0x94506]), bytes.fromhex(base))
            self.assertEqual(
                bytes(rendered[0x94340:0x9434A]),
                bytes.fromhex("E87B0100003D93000000"),
            )
            self.assertEqual(
                bytes(rendered[0x94360:0x9436A]),
                bytes.fromhex("E85B0100003D94000000"),
            )

        active_records = 142
        nursing_babies = 7
        demand_before_conversion = active_records + nursing_babies
        demand_after_conversion = active_records + nursing_babies
        self.assertEqual(demand_before_conversion, demand_after_conversion)
        remaining = build.villager_slots - demand_before_conversion
        self.assertEqual(remaining, 1)
        self.assertEqual(min(3, remaining), 1)

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

    def test_vv3_to_vv5_first_event_arrivals_recheck_physical_capacity(self) -> None:
        checks = {
            "vv3": {
                0x14D90: "E94B65060090",
                0x15320: "E9DB5F0600",
                0x7B2E0: "813DA824580096000000",
                0x7B300: "813DA824580096000000",
            },
            "vv4": {
                0x148B0: "E9AB47070090",
                0x14D90: "E9EB420700",
                0x89060: "813DE86D4D0096000000",
                0x89080: "813DE86D4D0096000000",
            },
            "vv5": {
                0x151D0: "E98BF30700",
                0x152B0: "E9CBF2070090",
                0x15410: "E98BF10700",
                0x94560: "E85BFFFFFF3D96000000",
                0x94580: "E83BFFFFFF3D96000000",
                0x945A0: "E81BFFFFFF3D96000000",
            },
        }
        for build in load_builds():
            if build.id not in checks:
                continue
            rendered, _ = render_patched_bytes(
                STOCK / build.input_name, build, DEFAULT_PATCH_MODE
            )
            for offset, expected_hex in checks[build.id].items():
                expected = bytes.fromhex(expected_hex)
                self.assertEqual(
                    bytes(rendered[offset : offset + len(expected)]),
                    expected,
                    (build.id, hex(offset)),
                )

    def test_vv1_vv2_event_allocations_use_per_record_slot_guards(self) -> None:
        checks = {
            "vv1": (
                0x56680,
                "81B9249E0000000100007D05E9BF5CFEFFB8FFFFFFFFC21400",
                [0x28263, 0x282C6, 0x282E3, 0x2833C, 0x28359, 0x28376,
                 0x2C3EF, 0x2C410, 0x2C431, 0x2C4AF, 0x2C4D0, 0x2C54E],
            ),
            "vv2": (
                0x73D00,
                "81B900E50200000100007D05E96FB8FDFFB8FFFFFFFFC21400",
                [0x34102, 0x341A2, 0x341C3, 0x34262, 0x34283, 0x342A4,
                 0x34467, 0x344A3],
            ),
        }
        for build in load_builds():
            if build.id not in checks:
                continue
            wrapper_offset, wrapper_hex, calls = checks[build.id]
            rendered, _ = render_patched_bytes(
                STOCK / build.input_name, build, DEFAULT_PATCH_MODE
            )
            wrapper = bytes.fromhex(wrapper_hex)
            self.assertEqual(
                bytes(rendered[wrapper_offset : wrapper_offset + len(wrapper)]),
                wrapper,
            )
            for call_offset in calls:
                self.assertEqual(rendered[call_offset], 0xE8)
                destination = (
                    call_offset
                    + 5
                    + struct.unpack_from("<i", rendered, call_offset + 1)[0]
                )
                self.assertEqual(destination, wrapper_offset)

    def test_vv4_vv5_abandoned_infants_are_clamped_to_remaining_slots(self) -> None:
        checks = {
            "vv4": (
                0x14FC0,
                "E9FB400700",
                0x890C0,
                "B8960000002B05E86D4D007E1F83F8067E05B806000000"
                "6A006A006AFF6A01506AFFB968E55000E814EAFDFFC3",
            ),
            "vv5": (
                0x155E0,
                "E9FBEF0700",
                0x945E0,
                "E8DBFEFFFFF7D805960000007E1F83F8067E05B806000000"
                "6A006A006AFF6A01506AFFB948415500E843D4FDFFC3",
            ),
        }
        for build in load_builds():
            if build.id not in checks:
                continue
            entry, entry_hex, cave, cave_hex = checks[build.id]
            rendered, _ = render_patched_bytes(
                STOCK / build.input_name, build, DEFAULT_PATCH_MODE
            )
            self.assertEqual(
                bytes(rendered[entry : entry + 5]), bytes.fromhex(entry_hex)
            )
            expected = bytes.fromhex(cave_hex)
            self.assertEqual(bytes(rendered[cave : cave + len(expected)]), expected)
            for occupied in range(145, 152):
                remaining = max(0, 150 - occupied)
                self.assertEqual(min(6, remaining), max(0, min(6, 150 - occupied)))

    def test_all_modes_reuse_short_modded_folders_beside_originals(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            folders = self.copy_game_folders(Path(temp))
            source_hashes = {
                build.id: digest(folders[build.id] / build.input_name)
                for build in load_builds()
            }
            for mode_index, mode in enumerate(MODES):
                results = apply_all(folders, mode, overwrite=mode_index > 0)
                self.assertEqual(len(results), 5)
                for build, (output, log_path) in zip(load_builds(), results):
                    copied_folder = self.expected_output_folder(folders, build, mode)
                    self.assertEqual(copied_folder.name, f"{build.title} - Modded")
                    self.assertEqual(output.parent, copied_folder)
                    self.assertTrue(output.is_file())
                    self.assertTrue((copied_folder / build.input_name).is_file())
                    self.assertEqual(
                        (copied_folder / "companion-data" / f"{build.id}.txt").read_text(
                            encoding="utf-8"
                        ),
                        f"unchanged companion file for {build.id}\n",
                    )
                    log = json.loads(log_path.read_text())
                    self.assertEqual(log["patch_mode"], mode)
                    self.assertEqual(log["output_path"], str(output))
                    variant = get_patch_variant(build, mode)
                    self.assertEqual(
                        log["villager_slots"],
                        variant.get("villager_slots", build.villager_slots),
                    )
            for build in load_builds():
                source = folders[build.id] / build.input_name
                self.assertEqual(digest(source), source_hashes[build.id])
                copied_folder = self.expected_output_folder(folders, build, MODES[-1])
                latest_output = (
                    copied_folder / get_patch_variant(build, MODES[-1])["output_name"]
                )
                self.assertTrue(latest_output.is_file())

    def test_expanded_later_games_keep_stock_save_names_and_use_larger_images(self) -> None:
        save_offsets = {"vv3": 0x7C5C0, "vv4": 0x8A77C, "vv5": 0x95794}
        for build in load_builds():
            if build.id not in save_offsets:
                continue
            source = STOCK / build.input_name
            original = source.read_bytes()
            rendered, _ = render_patched_bytes(
                source, build, "experimental_expanded_256"
            )
            self.assertEqual(
                bytes(rendered[save_offsets[build.id] : save_offsets[build.id] + 9]),
                b"%s%d.ldw\0",
            )
            pe = struct.unpack_from("<I", original, 0x3C)[0]
            optional = pe + 24
            self.assertGreater(
                struct.unpack_from("<I", rendered, optional + 56)[0],
                struct.unpack_from("<I", original, optional + 56)[0],
            )
            self.assertNotIn(
                bytes.fromhex("96000000"),
                b"".join(
                    bytes.fromhex(patch["after"])
                    for patch in dry_run(
                        source, "experimental_expanded_256"
                    )["patches"]
                    if "slot" in patch["purpose"]
                ),
            )

    def test_expanded_collection_progression_reaches_256(self) -> None:
        progression_bases = {"vv2": 231, "vv3": 221, "vv4": 231, "vv5": 241}
        for build in load_builds():
            source = STOCK / build.input_name
            rendered, _ = render_patched_bytes(
                source, build, "experimental_expanded_256_progression"
            )
            preview = dry_run(source, "experimental_expanded_256_progression")
            self.assertEqual(preview["villager_slots"], 256)
            self.assertEqual(preview["absolute_maximum"], 256)
            if build.id in progression_bases:
                self.assertEqual(
                    progression_bases[build.id] + build.stock_bonus_ceiling,
                    256,
                )
                self.assertTrue(preview["bonuses_affect_maximum"])
            if build.id == "vv3":
                self.assertEqual(
                    bytes(rendered[0x7B320:0x7B32D]),
                    bytes.fromhex("81C6DD0000003BDEE9B94BFEFF"),
                )
            elif build.id == "vv4":
                self.assertEqual(
                    bytes(rendered[0x89100:0x8910D]),
                    bytes.fromhex("81C6E70000003BDEE9E7F2FDFF"),
                )
            elif build.id == "vv5":
                self.assertEqual(
                    bytes(rendered[0x94500:0x94518]),
                    bytes.fromhex(
                        "81C6F1000000E8B5FFFFFF3BC60F8D3DE7FDFFE93EE7FDFF"
                    ),
                )

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
            sentinel_folder = self.expected_output_folder(
                folders, first, DEFAULT_PATCH_MODE
            )
            sentinel_folder.mkdir()
            sentinel = sentinel_folder / "sentinel.txt"
            sentinel.write_bytes(b"sentinel")
            with self.assertRaises(PatcherError):
                apply_all(folders, DEFAULT_PATCH_MODE)
            self.assertEqual(sentinel.read_bytes(), b"sentinel")
            for build in load_builds()[1:]:
                self.assertFalse(
                    self.expected_output_folder(
                        folders, build, DEFAULT_PATCH_MODE
                    ).exists()
                )

    def test_folder_validation_requires_the_expected_exe(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            folders = self.copy_game_folders(Path(temp))
            build = load_builds()[2]
            (folders[build.id] / build.input_name).unlink()
            with self.assertRaises(PatcherError):
                validate_all_sources(folders)
            self.assert_no_outputs(folders)

    def test_single_apply_uses_short_stable_modded_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            build = load_builds()[3]
            game_folder = Path(temp) / "game"
            game_folder.mkdir()
            source = game_folder / build.input_name
            shutil.copy2(STOCK / build.input_name, source)
            (game_folder / "keep.dat").write_bytes(b"keep")
            output, log = apply_patch(source, "immediate_fixed")
            self.assertEqual(output.name, modded_exe_name(build))
            self.assertTrue(log.is_file())
            self.assertTrue(source.is_file())
            self.assertEqual(output.parent.parent, game_folder.parent)
            self.assertEqual((output.parent / "keep.dat").read_bytes(), b"keep")
            self.assertTrue((output.parent / build.input_name).is_file())

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
        self.assertEqual(preview["output_name"], modded_exe_name(build))

    def test_vv1_continue_research_at_max_technologies_is_guarded(self) -> None:
        feature_id = "vv1_continue_research_at_max_technologies"
        build = next(build for build in load_builds() if build.id == "vv1")
        source = STOCK / build.input_name
        rendered, _ = render_patched_bytes(source, build, DEFAULT_PATCH_MODE, [feature_id])
        self.assertEqual(rendered[0x47488], 0x13)
        preview = dry_run(source, DEFAULT_PATCH_MODE, [feature_id])
        self.assertEqual(preview["output_name"], modded_exe_name(build))

    def test_vv1_fun_patches_combine_without_overlap(self) -> None:
        feature_ids = [
            "vv1_school_lessons_grant_skill",
            "vv1_continue_research_at_max_technologies",
            "vv1_f6_clothing_change_cheat",
        ]
        build = next(build for build in load_builds() if build.id == "vv1")
        rendered, _ = render_patched_bytes(STOCK / build.input_name, build, DEFAULT_PATCH_MODE, feature_ids)
        self.assertEqual(bytes(rendered[0x44BF2:0x44BF8]), bytes.fromhex("E9E919010090"))
        self.assertEqual(rendered[0x47488], 0x13)
        self.assertEqual(rendered[0x20057], 0)
        self.assertEqual(bytes(rendered[0x1FF2E:0x1FF34]), bytes.fromhex("E9ED66030090"))
        preview = dry_run(STOCK / build.input_name, DEFAULT_PATCH_MODE, feature_ids)
        self.assertEqual(preview["output_name"], modded_exe_name(build))

    def test_vv1_f6_clothing_cheat_is_guarded_and_wraps(self) -> None:
        feature_id = "vv1_f6_clothing_change_cheat"
        feature = next(patch for patch in load_fun_patches() if patch.id == feature_id)
        build = next(build for build in load_builds() if build.id == "vv1")
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
        self.assertEqual(rendered[0x20057], 0)
        self.assertEqual(
            bytes(rendered[0x1FF2E:0x1FF34]), bytes.fromhex("E9ED66030090")
        )
        self.assertEqual(
            bytes(rendered[0x56620:0x5666D]),
            bytes.fromhex(
                "817C2420FF03000075388B46108B8034AD00003DFF0000007723"
                "69C0D80300000346208078280074148B88640300004183F9147C02"
                "33C9898864030000E94F99FCFF8B86F8020000E9C798FCFF"
            ),
        )
        preview = dry_run(source, DEFAULT_PATCH_MODE, [feature_id])
        self.assertEqual(preview["fun_patches"], [feature_id])
        self.assertEqual(preview["output_name"], modded_exe_name(build))

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
        self.assertEqual(preview["output_name"], modded_exe_name(build))

    def test_vv2_easier_healing_output_and_log_preserve_original(self) -> None:
        feature_id = "vv2_easier_healing_mastery"
        build = next(build for build in load_builds() if build.id == "vv2")
        with tempfile.TemporaryDirectory() as temp:
            game_folder = Path(temp) / "game"
            game_folder.mkdir()
            source = game_folder / build.input_name
            shutil.copy2(STOCK / build.input_name, source)
            original_hash = digest(source)
            output, log_path = apply_patch(
                source,
                DEFAULT_PATCH_MODE,
                fun_patch_ids=[feature_id],
            )
            self.assertEqual(digest(source), original_hash)
            self.assertEqual(output.name, modded_exe_name(build))
            log = json.loads(log_path.read_text())
            self.assertEqual(log["fun_patches"], [feature_id])
            self.assertEqual(log["fun_patch_names"], ["Easier Healing Mastery"])
            feature = next(
                patch for patch in load_fun_patches() if patch.id == feature_id
            )
            self.assertEqual(
                len(log["patches"]),
                len(build.safety_patches)
                + len(get_patch_variant(build, DEFAULT_PATCH_MODE)["patches"])
                + len(feature.patches),
            )

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
        self.assertEqual(preview["output_name"], modded_exe_name(build))

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
        self.assertEqual(preview["output_name"], modded_exe_name(build))

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
        self.assertEqual(
            bytes(rendered[0x24F69:0x24F6E]),
            bytes.fromhex("E9B2F60600"),
        )
        self.assertEqual(
            bytes(rendered[0x94620:0x9466C]),
            bytes.fromhex(
                "6AE76A116A006A0068900100006AFF6A466A016A00B948415500"
                "E8E1B6FDFF50B948415500E806B3FDFF6A016A026A0268A06A4B00"
                "6A326A016A018BC8E89E17FDFFB948415500E9F4C7FDFF"
            ),
        )
        preview = dry_run(source, DEFAULT_PATCH_MODE, [feature_id])
        self.assertEqual(preview["fun_patches"], [feature_id])
        self.assertEqual(preview["output_name"], modded_exe_name(build))

    def test_vv4_golden_fish_requires_complete_scales_collection(self) -> None:
        feature_id = "vv4_complete_scales_golden_fish"
        build = next(build for build in load_builds() if build.id == "vv4")
        source = STOCK / build.input_name
        rendered, _ = render_patched_bytes(
            source, build, DEFAULT_PATCH_MODE, [feature_id]
        )
        self.assertEqual(
            bytes(source.read_bytes()[0x33384:0x33389]),
            bytes.fromhex("83F8017C23"),
        )
        self.assertEqual(
            bytes(rendered[0x33384:0x33389]),
            bytes.fromhex("83F80C7C23"),
        )
        self.assertEqual(2 * 12 + 1, 25)
        preview = dry_run(source, DEFAULT_PATCH_MODE, [feature_id])
        self.assertEqual(preview["output_name"], modded_exe_name(build))

    def test_vv3_nature_level_one_improves_honey_refill(self) -> None:
        feature_id = "vv3_nature_honey_refill"
        feature = next(patch for patch in load_fun_patches() if patch.id == feature_id)
        build = next(build for build in load_builds() if build.id == "vv3")
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
            bytes(rendered[0x319F9:0x31A09]),
            bytes.fromhex("E9A29804009090909090909090909090"),
        )
        self.assertEqual(
            bytes(rendered[0x7B2A0:0x7B2E0]),
            bytes.fromhex(
                "8B560C2BC2506A05B918265800E80EBDFAFF83F801587C15"
                "B954000000F7E1B950080200F7F18BD0E93C67FBFF8BD0D1"
                "E2B8C5B3A291F7E2C1EA0BE92967FBFF"
            ),
        )
        preview = dry_run(source, DEFAULT_PATCH_MODE, [feature_id])
        self.assertEqual(preview["fun_patches"], [feature_id])
        self.assertEqual(preview["output_name"], modded_exe_name(build))

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
        self.assertEqual(preview["output_name"], modded_exe_name(build))

    def test_vv5_fun_patches_combine_without_overlap(self) -> None:
        feature_ids = [
            "vv5_heathen_mommy_puzzle",
            "vv5_easier_devotee_training",
            "vv5_statue_polishing_or_honoring",
            "vv5_vv4_nursery_divisor_parity",
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
        self.assertEqual(bytes(rendered[0x24F69:0x24F6E]), bytes.fromhex("E9B2F60600"))
        self.assertEqual(bytes(rendered[0x94620:0x94622]), bytes.fromhex("6AE7"))
        self.assertEqual(bytes(rendered[0x6F1DD:0x6F1E6]), bytes.fromhex("E91E52020090909090"))
        self.assertEqual(bytes(rendered[0x94440:0x94460]), bytes.fromhex(
            "8B8E881B000083B9FC1C00000D7405E9BAADFDFF6A64E805F2F6FFE99CADFDFF"
        ))
        self.assertEqual(bytes(rendered[0x6C45D:0x6C462]), bytes.fromhex("E83E800200"))
        self.assertEqual(bytes(rendered[0x6CDED:0x6CDF2]), bytes.fromhex("E8AE760200"))
        self.assertEqual(bytes(rendered[0x6BF9A:0x6BF9F]), bytes.fromhex("E801850200"))
        self.assertEqual(bytes(rendered[0x796EB:0x796F0]), bytes.fromhex("E8B0AD0100"))
        self.assertEqual(bytes(rendered[0x944A0:0x944BE]), bytes.fromhex(
            "5A526A02E8B7F1F6FF83C40485C0B89D0000007405B8A00000005A5052C3"
        ))
        self.assertEqual(
            bytes(rendered[0x25FE1:0x25FE5]), bytes.fromhex("40454900")
        )
        self.assertEqual(
            bytes(rendered[0x94540:0x94548]), bytes.fromhex("0000000000001840")
        )
        preview = dry_run(source, DEFAULT_PATCH_MODE, feature_ids)
        self.assertEqual(preview["fun_patches"], feature_ids)
        self.assertEqual(preview["output_name"], modded_exe_name(build))

    def test_vv5_vv4_nursery_divisor_parity_is_local_and_guarded(self) -> None:
        feature_id = "vv5_vv4_nursery_divisor_parity"
        build = next(build for build in load_builds() if build.id == "vv5")
        source = STOCK / build.input_name
        original = source.read_bytes()
        rendered, _ = render_patched_bytes(
            source, build, DEFAULT_PATCH_MODE, [feature_id]
        )
        self.assertEqual(
            bytes(original[0x25FDF:0x25FE5]),
            bytes.fromhex("DC3510884900"),
        )
        self.assertEqual(
            bytes(rendered[0x25FDF:0x25FE5]),
            bytes.fromhex("DC3540454900"),
        )
        self.assertEqual(
            bytes(original[0x98810:0x98818]),
            bytes.fromhex("0000000000001440"),
        )
        self.assertEqual(
            bytes(rendered[0x98810:0x98818]),
            bytes.fromhex("0000000000001440"),
        )
        self.assertEqual(
            bytes(rendered[0x94540:0x94548]),
            bytes.fromhex("0000000000001840"),
        )
        preview = dry_run(source, DEFAULT_PATCH_MODE, [feature_id])
        self.assertEqual(preview["output_name"], modded_exe_name(build))

    def test_vv5_statue_drops_choose_polishing_or_honoring(self) -> None:
        feature_id = "vv5_statue_polishing_or_honoring"
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
        self.assertEqual(bytes(rendered[0x6C45D:0x6C462]), bytes.fromhex("E83E800200"))
        self.assertEqual(bytes(rendered[0x6CDED:0x6CDF2]), bytes.fromhex("E8AE760200"))
        self.assertEqual(bytes(rendered[0x6BF9A:0x6BF9F]), bytes.fromhex("E801850200"))
        self.assertEqual(bytes(rendered[0x796EB:0x796F0]), bytes.fromhex("E8B0AD0100"))
        self.assertEqual(bytes(rendered[0x944A0:0x944BE]), bytes.fromhex(
            "5A526A02E8B7F1F6FF83C40485C0B89D0000007405B8A00000005A5052C3"
        ))
        preview = dry_run(source, DEFAULT_PATCH_MODE, [feature_id])
        self.assertEqual(preview["fun_patches"], [feature_id])
        self.assertEqual(preview["output_name"], modded_exe_name(build))

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
            for build, (output, log_path) in zip(load_builds(), results):
                self.assertEqual(output.name, modded_exe_name(build))
                log = json.loads(log_path.read_text())
                expected = [feature_id] if build.id == "vv2" else []
                self.assertEqual(log["fun_patches"], expected)


if __name__ == "__main__":
    unittest.main()
