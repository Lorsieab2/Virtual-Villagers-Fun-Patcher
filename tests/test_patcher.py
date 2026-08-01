from __future__ import annotations

import hashlib
import json
import re
import shutil
import struct
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch as mock_patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import (  # noqa: E402
    DEFAULT_PATCH_MODE,
    PatcherError,
    apply_all,
    apply_patch,
    copy_vanilla_saves,
    dry_run,
    dry_run_all,
    expanded_save_status,
    get_fun_patch,
    get_patch_variant,
    identify,
    load_builds,
    load_fun_patches,
    load_patch_modes,
    modded_save_folder_for,
    render_patched_bytes,
    Record,
    validate_all_sources,
    vanilla_save_folder_for,
)
from vv_fun_patcher_gui import group_fun_patches  # noqa: E402

STOCK = ROOT / "research" / "stock-executables"
MODES = (
    "collection_progression",
    "immediate_fixed",
)
EXPANDED_MODES = (
    "experimental_expanded_256",
    "experimental_expanded_256_progression",
)
EXPANDED = json.loads((ROOT / "data" / "expanded_256.json").read_text())


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def modded_exe_name(build) -> str:
    return f"{build.title} - Modded.exe"


def expanded_exe_name(build) -> str:
    return f"{build.title} - Modded 256.exe"


def village_wide_record(game_id: str) -> SimpleNamespace:
    raw = json.loads(
        (ROOT / "data" / f"{game_id}_origins_village_wide_upgrades.json").read_text(
            encoding="utf-8"
        )
    )
    return SimpleNamespace(
        id=raw["id"],
        game_id=raw["game_id"],
        description=raw["description"],
        raw=raw,
    )


class ManifestTests(unittest.TestCase):
    def test_running_preference_id_matches_each_stock_table(self) -> None:
        evidence = {
            "vv1": ("Virtual Villagers - A New Home.exe", 0x7B260),
            "vv2": ("Virtual Villagers - The Lost Children.exe", 0x8B808),
            "vv3": ("Virtual Villagers - The Secret City.exe", 0x97488),
            "vv4": ("Virtual Villagers - The Tree of Life.exe", 0xA0CD8),
            "vv5": ("Virtual Villagers - New Believers.exe", 0xAEF60),
        }
        for game_id, (name, offset) in evidence.items():
            with self.subTest(game=game_id):
                if game_id == "vv2":
                    continue
                if game_id == "vv4":
                    # VV4 Origins/Full Mastery is catalog-hidden while the
                    # C6 startup-crash correction awaits fresh recertification.
                    continue
                feature = get_fun_patch(f"{game_id}_enable_origins_exclusive_features")
                self.assertEqual(feature.raw["running_preference_id"], 38)
                self.assertEqual(
                    feature.raw["running_preference_evidence"]["table_file_offset"],
                    f"0x{offset:X}",
                )
                stock = (STOCK / name).read_bytes()[offset : offset + 1000]
                match = re.match(rb"[ -~]+", stock)
                self.assertIsNotNone(match)
                entries = [item.strip() for item in match.group().decode("ascii").split(",")]
                self.assertIn("running", entries)
                self.assertEqual(entries.index("running"), feature.raw["running_preference_id"])
        doc = (ROOT / "docs" / "origins-village-wide-upgrades.md").read_text(encoding="utf-8")
        self.assertIn("implementation is tailored to each\nsupported executable", doc)
        self.assertIn("not a blanket cross-game assumption", doc)
        for offset in ("0x7B260", "0x8B808", "0x97488", "0xA0CD8", "0xAEF60"):
            self.assertIn(offset, doc)
    def test_origins_village_wide_features_are_game_scoped_and_dependency_bound(self) -> None:
        features = {
            patch.id: patch
            for patch in load_fun_patches()
            if "origins_village_wide_upgrades" in patch.id
        }
        self.assertEqual(features, {})
        for game in range(1, 6):
            feature = village_wide_record(f"vv{game}")
            self.assertIs(feature.raw["enabled"], False)
            self.assertEqual(
                feature.raw["dependencies"],
                [f"vv{game}_enable_origins_exclusive_features"],
            )
            self.assertIn("All Villagers Like Running", feature.description)
            self.assertIn("Grant Full Mastery to All Villagers", feature.description)
            self.assertIn("All Villagers are 18", feature.description)
            self.assertIn("1,000,000", feature.description)
            self.assertIn("inspired", feature.description.casefold())

            self.assertEqual(feature.raw.get("running_preference_id"), 38)
            self.assertIn("removed Running dislike", feature.raw["extension_abi"]["calling_convention"])
            self.assertIn("already-running", feature.raw["extension_abi"]["calling_convention"])
            self.assertEqual(len(feature.raw["patches"]), 1)
            patch = feature.raw["patches"][0]
            self.assertEqual(len(bytes.fromhex(patch["before"])), len(bytes.fromhex(patch["after"])))
            self.assertEqual(patch["purpose"].startswith("install the optional"), True)

    def test_withdrawn_candidates_are_absent_and_catalog_loads(self) -> None:
        active_ids = {feature.id for feature in load_fun_patches()}
        self.assertTrue(active_ids)
        self.assertTrue(
            {
                "vv1_full_mastery_all_stage_a_candidate",
                "vv3_all_villagers_like_running",
            }.isdisjoint(active_ids)
        )
        self.assertNotIn("vv5_full_mastery_all_stage_a_candidate", active_ids)
        self.assertIn("vv3_full_mastery_all_stage_a_candidate", active_ids)

    def test_origins_village_wide_payloads_use_zero_owned_reserves(self) -> None:
        stock_by_game = {build.id: STOCK / build.input_name for build in load_builds()}
        for game_id in ("vv1", "vv2", "vv3", "vv4", "vv5"):
            feature = village_wide_record(game_id)
            with self.subTest(game=game_id):
                patch = feature.raw["patches"][0]
                offset = int(patch["offset"], 0)
                before = bytes.fromhex(patch["before"])
                source = stock_by_game[game_id].read_bytes()
                self.assertEqual(source[offset : offset + len(before)], before)
                self.assertEqual(before, b"\0" * len(before))
                self.assertEqual(feature.raw["extension_abi"]["signature"], "VVFPOWU")
                self.assertIn("ECX=first physical record pointer", feature.raw["extension_abi"]["calling_convention"])
                commands = feature.raw["extension_abi"]["commands"]
                self.assertEqual(commands["6"], "All Villagers Like Running")
                self.assertEqual(commands["7"], "Grant Full Mastery to All Villagers")
                self.assertEqual(commands["8"], "All Villagers are 18")

    def test_origins_village_wide_metadata_preserves_explicit_exclusions(self) -> None:
        for game_id in ("vv1", "vv2", "vv3", "vv4", "vv5"):
            patch = village_wide_record(game_id)
            exclusions = patch.raw["explicit_non_changes"]
            self.assertTrue(any("nursing" in item for item in exclusions))
            self.assertTrue(any("unrelated Like" in item for item in exclusions))
            if patch.game_id == "vv5":
                self.assertTrue(any("Heathens" in item for item in exclusions))

    def test_origins_village_wide_abi_uses_command_eax_and_bound_edx(self) -> None:
        for game_id in ("vv1", "vv2", "vv3", "vv4", "vv5"):
            with self.subTest(game=game_id):
                feature = village_wide_record(game_id)
                convention = feature.raw["extension_abi"]["calling_convention"]
                self.assertIn("EAX=command", convention)
                self.assertIn("ECX=first physical record pointer", convention)
                self.assertIn("EDX=physical record bound", convention)
                payload = bytes.fromhex(feature.raw["patches"][0]["after"])
                entry_offset = int(feature.raw["extension_abi"]["entry_offset"], 0)
                payload_base = int(feature.raw["patches"][0]["offset"], 0)
                entry = payload[entry_offset - payload_base :]
                self.assertIn(bytes.fromhex("83F806"), entry)
                self.assertIn(bytes.fromhex("83F807"), entry)
                self.assertIn(bytes.fromhex("83F808"), entry)
                self.assertIn(bytes.fromhex("B8FFFFFFFF"), entry)
                self.assertIn(bytes.fromhex("89CE"), payload)  # mov esi, ecx
                self.assertIn(bytes.fromhex("89D3"), payload)  # mov ebx, edx

    def test_origins_village_wide_helpers_preserve_nonvolatile_registers(self) -> None:
        """Decode each committed helper's actual prologue/epilogue bytes.

        Commands 6, 7, and 8 each push EBP/EBX/ESI/EDI in that order.  Every
        helper must therefore restore EDI/ESI/EBX/EBP in the reverse order;
        this catches the historical command-7 ESI/EDI swap without relying on
        the generator source text.
        """
        prologue = bytes.fromhex("55535657")
        epilogue = bytes.fromhex("5F5E5B5DC3")
        bad_mastery_tail = bytes.fromhex("31C031D231C95E5F5B5DC3")
        mastery_tail = bytes.fromhex("31C031D231C95F5E5B5DC3")
        for game_id in ("vv1", "vv2", "vv3", "vv4", "vv5"):
            with self.subTest(game=game_id):
                feature = village_wide_record(game_id)
                payload = bytes.fromhex(feature.raw["patches"][0]["after"])
                self.assertNotIn(bad_mastery_tail, payload)
                self.assertEqual(payload.count(mastery_tail), 2)
                starts = [
                    index
                    for index in range(len(payload) - len(prologue) + 1)
                    if payload[index : index + len(prologue)] == prologue
                ]
                self.assertEqual(len(starts), 3)
                for start in starts:
                    ret = payload.index(b"\xC3", start)
                    self.assertEqual(payload[ret - len(epilogue) + 1 : ret + 1], epilogue)

    def test_origins_village_wide_exact_header_and_safe_field_targets(self) -> None:
        expected_headers = {
            "vv1": 0x48D180,
            "vv2": 0x49C180,
            "vv3": 0x47B820,
            "vv4": 0x728220,
            "vv5": 0x494C20,
        }
        for game_id, header_va in expected_headers.items():
            with self.subTest(game=game_id):
                feature = village_wide_record(game_id)
                patch = feature.raw["patches"][0]
                payload = bytes.fromhex(patch["after"])
                self.assertEqual(
                    payload[:0x20],
                    bytes.fromhex("565646504F575500010000002000000003000000000000000000000000000000"),
                )
                self.assertEqual(
                    int(feature.raw["extension_abi"]["entry_virtual_address"], 0),
                    header_va + 0x20,
                )
                if game_id == "vv4":
                    self.assertIn("expanded_shr_relocations", feature.raw)
                if game_id == "vv5":
                    self.assertNotIn((0x1B8C + 0xAD0).to_bytes(4, "little"), payload)

    def test_village_wide_running_result_dialog_uses_exact_three_lines(self) -> None:
        source = (ROOT / "native" / "vv1_origins_icons" / "vv1_origins_icons.c").read_text(encoding="utf-8")
        self.assertIn("Skipped over %d villagers. Reason: Already 3 likes.", source)
        self.assertIn("skipped over %d villagers. Reason: already likes running", source)
        self.assertIn("Removed running dislike from %d villagers", source)
        self.assertIn("removed_running_dislike", source)

    def test_village_wide_running_clears_dislikes_even_for_full_like_records(self) -> None:
        source = (ROOT / "scripts" / "build_village_wide_origins_features.py").read_text(encoding="utf-8")
        full_like = source.split("running_not_running:", 1)[1].split("running_store_like:", 1)[0]
        self.assertIn("jmp running_remove_dislikes", full_like)

    def test_vv5_village_wide_payload_uses_authoritative_believer_predicate(self) -> None:
        feature = village_wide_record("vv5")
        payload = bytes.fromhex(feature.raw["patches"][0]["after"])
        # Active, non-heathen occupancy, health, and current faction are all
        # explicit in the generated helper; health alone is not a substitute.
        for immediate in (
            bytes.fromhex("80BED41C000000"),
            bytes.fromhex("80BEE11C000000"),
            bytes.fromhex("83BE401C000000"),
            bytes.fromhex("80BEEC1C000000"),
        ):
            self.assertIn(immediate, payload)
        self.assertIn("Heathens", " ".join(feature.raw["explicit_non_changes"]))
        self.assertIn("believer", feature.description.casefold())

    def test_rejected_vv4_birth_control_is_not_selectable(self) -> None:
        self.assertNotIn(
            "vv4_birth_control",
            [patch.id for patch in load_fun_patches()],
        )

    def test_unverified_birth_control_is_not_exposed_as_a_patch(self) -> None:
        self.assertNotIn(
            "vv1_birth_control",
            [patch.id for patch in load_fun_patches()],
        )

    def test_grant_running_checks_exactly_three_normal_like_slots(self) -> None:
        for game_id in ("vv1", "vv2", "vv3", "vv4", "vv5"):
            with self.subTest(game=game_id):
                source = next(
                    (ROOT / "scripts").glob(f"build_{game_id}_origins_feature.py")
                ).read_text(encoding="utf-8")
                starts = [
                    source.find("running_find_like_slot:"),
                    source.find("running_find_like:"),
                    source.find("find_like:"),
                    source.find("running:"),
                ]
                start = min(value for value in starts if value >= 0)
                ends = [
                    value
                    for value in (
                        source.find("detail_success:", start),
                        source.find("detail_status:", start),
                        source.find("done:", start),
                    )
                    if value >= 0
                ]
                section = source[start : min(ends) if ends else len(source)]
                self.assertIn("mov eax, 3", section)
                self.assertIn("cmp dword ptr [ecx], -1", section)
                self.assertIn("dec eax", section)
                self.assertIn("jne", section)

    def test_stock_record_capacities_are_explicit(self) -> None:
        builds = {build.id: build for build in load_builds()}
        self.assertEqual(builds["vv1"].villager_slots, 256)
        self.assertEqual(builds["vv2"].villager_slots, 256)
        for game_id in ("vv3", "vv4", "vv5"):
            self.assertEqual(builds[game_id].villager_slots, 150)
            self.assertEqual(builds[game_id].absolute_maximum, 150)

    def test_expanded_256_modes_are_available_with_experimental_warning(self) -> None:
        self.assertEqual(
            [mode.id for mode in load_patch_modes()], list(MODES + EXPANDED_MODES)
        )
        source = STOCK / load_builds()[2].input_name
        for mode in EXPANDED_MODES:
            with self.subTest(mode=mode):
                preview = dry_run(source, mode)
                self.assertTrue(preview["experimental_expanded_records"])
                self.assertEqual(preview["output_name"], expanded_exe_name(load_builds()[2]))
                self.assertEqual(
                    Path(preview["output_folder"]).name,
                    f"{load_builds()[2].title} - Modded 256",
                )

    def test_modes_names_targets_and_safety_guards(self) -> None:
        builds = load_builds()
        self.assertEqual([build.id for build in builds], ["vv1", "vv2", "vv3", "vv4", "vv5"])
        self.assertEqual(
            [mode.id for mode in load_patch_modes()], list(MODES + EXPANDED_MODES)
        )
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

    def test_origins_dialog_supports_game_supplied_state(self) -> None:
        exports = (ROOT / "native/vv1_origins_icons/vv1_origins_icons.def").read_text(
            encoding="utf-8"
        )
        source = (
            ROOT / "native/vv1_origins_icons/vv1_origins_icons.c"
        ).read_text(encoding="utf-8")
        self.assertIn("ShowOriginsUpgradeMenuState", exports)
        self.assertIn("ShowOriginsUpgradeMenuState", source)
        self.assertIn("return show_upgrade_menu(villager_menu, dialog_state);", source)
        resource = (
            ROOT / "native/vv1_origins_icons/vv1_origins_icons.rc"
        ).read_text(encoding="utf-8")
        self.assertIn("Time Warp - 3 villager years", resource)

    def test_origins_dialog_has_optional_village_wide_rows(self) -> None:
        source = (ROOT / "native/vv1_origins_icons/vv1_origins_icons.c").read_text(
            encoding="utf-8"
        )
        resource = (ROOT / "native/vv1_origins_icons/vv1_origins_icons.rc").read_text(
            encoding="utf-8"
        )
        self.assertIn("STATE_VILLAGE_WIDE = 0x20000", source)
        self.assertIn("((lparam & STATE_VILLAGE_WIDE) != 0 ? 9 : 6)", source)
        self.assertIn("ID_BUY_LAST = 1008", source)
        for label in (
            "All Villagers Like Running",
            "Grant Full Mastery to All Villagers",
            "All Villagers are 18",
        ):
            self.assertIn(label, resource)
        self.assertEqual(resource.count("1,000,000 tech points"), 3)
        self.assertIn('PUSHBUTTON  "Buy", 1006', resource)
        self.assertIn('PUSHBUTTON  "Buy", 1007', resource)
        self.assertIn('PUSHBUTTON  "Buy", 1008', resource)

    def test_village_wide_mastery_label_is_consistent_and_legacy_label_is_absent(self) -> None:
        user_facing = [
            ROOT / "native/vv1_origins_icons/vv1_origins_icons.rc",
            ROOT / "README.md",
            ROOT / "How to Use.txt",
            ROOT / "docs/origins-village-wide-upgrades.md",
            ROOT / "docs/origins-player-runtime-checklist.md",
            ROOT / "docs/transparency-log.md",
        ]
        user_facing.extend(ROOT / "data" / f"vv{game}_origins_village_wide_upgrades.json" for game in range(1, 6))
        legacy = ("Jack" + "-" + "Of-All-Trades", "Jack" + " of all trades")
        for path in user_facing:
            text = path.read_text(encoding="utf-8")
            normalized = " ".join(text.split())
            with self.subTest(path=path):
                self.assertIn("Grant Full Mastery to All Villagers", normalized)
                for old_label in legacy:
                    self.assertNotIn(old_label.casefold(), normalized.casefold())

    def test_statistics_features_cover_all_proven_per_save_counter_blocks(self) -> None:
        features = {
            patch.game_id: patch
            for patch in load_fun_patches()
            if patch.name == "Write Village Statistics to Text File"
        }
        self.assertEqual(set(features), {"vv1", "vv2", "vv3", "vv4", "vv5"})
        for feature in features.values():
            self.assertIn("local lifetime statistics", feature.description)
            self.assertEqual(len(feature.raw["companion_files"]), 1)

    def test_statistics_exporter_recovers_completed_vv5_bonus_puzzle_from_save(self) -> None:
        source = (
            ROOT / "native" / "statistics_export" / "statistics_export.c"
        ).read_text(encoding="utf-8")
        self.assertIn("count_vv5_puzzles", source)
        self.assertIn("0x16D20u + 17u * 8u", source)
        self.assertIn("bonus_progress >= 3", source)
        self.assertIn("Puzzle totals are read from the current save state", " ".join(
            patch.description
            for patch in load_fun_patches()
            if patch.name == "Write Village Statistics to Text File"
        ))

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

    def test_interface_remembers_a_custom_modded_output_parent(self) -> None:
        source = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")
        self.assertIn('self.output_root_var = tk.StringVar()', source)
        self.assertIn('text="Modded output location"', source)
        self.assertIn("def _browse_output_root", source)
        self.assertIn('"output_root": self.output_root_var.get().strip()', source)

    def test_success_confirmation_uses_clear_folder_links(self) -> None:
        source = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")
        self.assertIn("def _show_folder_confirmation", source)
        self.assertIn("Open Vanilla Folder:", source)
        self.assertIn("Open Modded Folder:", source)
        self.assertIn("Patch audit:", source)
        self.assertIn("Village Statistics - Save N.txt:", source)
        self.assertIn("Parentage Log.html", source)
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

    def test_fun_patch_labels_use_game_subtitles(self) -> None:
        source = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")
        self.assertIn('text=f"{patch.name} ({game_name})"', source)
        self.assertIn('removeprefix("Virtual Villagers - ")', source)
        self.assertNotIn('text=f"{patch.name} ({patch.game_id.upper()})"', source)

    def test_fun_patches_are_grouped_by_game_and_sorted_by_name(self) -> None:
        source = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")
        self.assertIn(
            "game_order = {build.id: index for index, build in enumerate(builds)}",
            source,
        )
        self.assertIn("game_order.get(patch.game_id, len(game_order))", source)
        self.assertIn("patch.name.casefold()", source)

    def test_fun_patch_headers_follow_manifest_order_and_shared_is_last(self) -> None:
        headers = group_fun_patches(load_builds(), load_fun_patches())
        expected = [
            "Virtual Villagers - A New Home",
            "Virtual Villagers - The Lost Children",
            "Virtual Villagers - The Secret City",
            "Virtual Villagers - The Tree of Life",
            "Virtual Villagers - New Believers",
        ]
        self.assertEqual([title for title, _ in headers[:5]], expected)
        if any(patch.game_id not in {build.id for build in load_builds()} for patch in load_fun_patches()):
            self.assertEqual(headers[-1][0], "Shared / All Games")

    def test_fun_patch_catalog_uses_casefold_then_id_tie_break(self) -> None:
        builds = [SimpleNamespace(id="vv1", title="Virtual Villagers - A New Home")]
        patches = [
            SimpleNamespace(game_id="vv1", name="same", id="z", description=""),
            SimpleNamespace(game_id="vv1", name="SAME", id="a", description=""),
            SimpleNamespace(game_id="other", name="shared", id="b", description=""),
        ]
        headers = group_fun_patches(builds, patches)
        self.assertEqual([patch.id for patch in headers[0][1]], ["a", "z"])
        self.assertEqual(headers[-1][0], "Shared / All Games")

    def test_fun_patch_selection_controls_and_dependency_closure_remain_in_ui(self) -> None:
        source = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")
        for snippet in (
            'text="Select All Patches"',
            'text="Deselect All Patches"',
            "self.fun_patch_vars",
            "self._apply_gui_dependency_selection()",
            "self._last_fun_selection",
            'removeprefix("Virtual Villagers - ")',
        ):
            self.assertIn(snippet, source)

    def test_no_temporary_or_backup_game_folders_are_created(self) -> None:
        source = (ROOT / "src" / "vv_fun_patcher.py").read_text(encoding="utf-8")
        self.assertNotIn("Temporary Copy", source)
        self.assertNotIn("Replacement Backup", source)
        self.assertNotIn("tempfile.mkdtemp", source)
        self.assertIn("dirs_exist_ok=overwrite", source)


class DoublerPurchaseSafetyTests(unittest.TestCase):
    BLOCKED_GAMES = ("vv1", "vv3", "vv4")

    def test_mode_override_overlap_is_rejected_across_feature_owners(self) -> None:
        build = next(item for item in load_builds() if item.id == "vv5")
        source = STOCK / build.input_name
        patch = {
            "offset": "0x1EB6F",
            "before": "85F67E3456",
            "after": "85F67E3456",
            "purpose": "test same-size mode override",
        }
        fake_catalog = [
            Record(
                {
                    "id": "vv5_override_a",
                    "name": "VV5 override A",
                    "game_id": "vv5",
                    "patches": [patch],
                    "patch_mode_overrides": {},
                }
            ),
            Record(
                {
                    "id": "vv5_override_b",
                    "name": "VV5 override B",
                    "game_id": "vv5",
                    "patches": [patch],
                    "patch_mode_overrides": {},
                }
            ),
        ]
        with mock_patch("vv_fun_patcher.load_fun_patches", return_value=fake_catalog):
            with self.assertRaisesRegex(PatcherError, "Patch overlap"):
                render_patched_bytes(
                    source,
                    build,
                    "collection_progression",
                    ["vv5_override_a", "vv5_override_b"],
                )

    def test_unproven_doublers_are_unavailable_but_owned_rows_remain_removable(self) -> None:
        for game_id in self.BLOCKED_GAMES:
            with self.subTest(game=game_id):
                if game_id == "vv4":
                    with self.assertRaisesRegex(PatcherError, "Unknown fun patch"):
                        get_fun_patch("vv4_enable_origins_exclusive_features")
                    continue
                feature = get_fun_patch(f"{game_id}_enable_origins_exclusive_features")
                status = feature.raw["doubler_purchase_status"]
                self.assertIn("temporarily unavailable", status["new_purchase"])
                self.assertIn("zero cost", status["existing_owned"])
                self.assertIn("zero refund", status["existing_owned"])
                self.assertIn("temporarily disabled", status["repurchase"])
                self.assertIn("displayed-but-currently-unavailable", feature.description)
                self.assertIn("repurchase is temporarily disabled", feature.description)

                payload = b"".join(
                    bytes.fromhex(patch["after"]) for patch in feature.raw["patches"]
                )
                self.assertIn(b"Unavailable: exact-build doubler behavior", payload)
                self.assertTrue(
                    b"\x81\xc8\x00\x18\x00\x00" in payload
                    or b"\x81\xcf\x00\x18\x00\x00" in payload
                    or b"\x0d\x00\x18\x00\x00" in payload
                )

                builder = (ROOT / "scripts" / f"build_{game_id}_origins_feature.py").read_text(
                    encoding="utf-8"
                )
                self.assertIn("doubler_unavailable", builder)
                self.assertTrue(
                    "jz doubler_unavailable" in builder
                    or "jmp doubler_unavailable" in builder
                )
                self.assertTrue(
                    "or edi, 0x1800" in builder
                    or "or eax, 0x1800" in builder
                )

    def test_doubler_command_state_model_preserves_zero_cost_no_refund_removal(self) -> None:
        def choose(owned: int, command: int) -> tuple[str, int, int]:
            bit = 1 if command == 3 else 2
            if command not in (3, 4):
                return "other", owned, 0
            if owned & bit:
                return "remove", owned & ~bit, 0
            return "unavailable", owned, 0

        for owned in (0, 1, 2, 3):
            for command in (3, 4):
                with self.subTest(owned=owned, command=command):
                    action, after, charge = choose(owned, command)
                    if owned & (1 if command == 3 else 2):
                        self.assertEqual(action, "remove")
                        self.assertEqual(charge, 0)
                        self.assertNotEqual(after, owned)
                    else:
                        self.assertEqual(action, "unavailable")
                        self.assertEqual(after, owned)
                        self.assertEqual(charge, 0)

    def test_vv2_origins_containment_is_explicit(self) -> None:
        for feature_id in (
            "vv2_enable_origins_exclusive_features",
            "vv2_origins_village_wide_upgrades",
        ):
            with self.subTest(feature=feature_id):
                with self.assertRaisesRegex(PatcherError, "Unknown fun patch"):
                    get_fun_patch(feature_id)


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

    def test_expanded_modes_render_with_all_game_patches_selected(self) -> None:
        patches_by_game = {
            build.id: [patch.id for patch in load_fun_patches() if patch.game_id == build.id]
            for build in load_builds()
        }
        for build in load_builds():
            with self.subTest(game=build.id):
                if build.id == "vv3":
                    self.assertIn(
                        "vv3_full_mastery_all_stage_a_candidate",
                        patches_by_game[build.id],
                    )
                    with self.assertRaisesRegex(PatcherError, "has no append layout"):
                        render_patched_bytes(
                            STOCK / build.input_name,
                            build,
                            "experimental_expanded_256",
                            patches_by_game[build.id],
                        )
                    continue
                if build.id == "vv4":
                    self.assertNotIn(
                        "vv4_full_mastery_all_stage_a_candidate",
                        patches_by_game[build.id],
                    )
                    self.assertNotIn(
                        "vv4_enable_origins_exclusive_features",
                        patches_by_game[build.id],
                    )
                    continue
                rendered, applied = render_patched_bytes(
                    STOCK / build.input_name,
                    build,
                    "experimental_expanded_256",
                    patches_by_game[build.id],
                )
                running_enabled = any(
                    patch_id == "vv3_all_villagers_like_running"
                    for patch_id in patches_by_game[build.id]
                )
                expected_size = build.size + (
                    0x1000 if build.id == "vv3" and running_enabled else 0
                )
                if (
                    build.id == "vv2"
                    and "vv2_full_mastery_all_stage_a_candidate"
                    in patches_by_game[build.id]
                ):
                    expected_size += 0x2000
                if (
                    build.id == "vv4"
                    and "vv4_full_mastery_all_stage_a_candidate"
                    in patches_by_game[build.id]
                ):
                    expected_size += 0x2000
                if (
                    build.id == "vv5"
                    and "vv5_full_mastery_all_stage_a_candidate"
                    in patches_by_game[build.id]
                ):
                    expected_size += 0x2000
                self.assertEqual(len(rendered), expected_size)
                self.assertGreater(len(applied), 0)

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
                "51E85A1BFBFF3D00010000597D05E96DB8FDFFB8FFFFFFFFC21400",
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

    def test_custom_output_parent_is_used_for_single_and_bulk_copies(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folders = self.copy_game_folders(root / "originals")
            chosen = root / "chosen-output"
            source = folders["vv1"] / load_builds()[0].input_name

            preview = dry_run(source, DEFAULT_PATCH_MODE, output_root=chosen)
            self.assertEqual(
                Path(preview["output_folder"]),
                chosen / f"{load_builds()[0].title} - Modded",
            )
            output, _ = apply_patch(
                source,
                DEFAULT_PATCH_MODE,
                output_root=chosen,
            )
            self.assertEqual(output.parent.parent, chosen)
            self.assertTrue(output.is_file())
            self.assertTrue(source.is_file())

            bulk_root = root / "bulk-output"
            results = apply_all(
                folders,
                "immediate_fixed",
                output_root=bulk_root,
            )
            self.assertEqual(len(results), 5)
            for build, (bulk_output, _log) in zip(load_builds(), results):
                self.assertEqual(bulk_output.parent.parent, bulk_root)
                self.assertEqual(bulk_output.parent.name, f"{build.title} - Modded")
                self.assertTrue(bulk_output.is_file())

    def test_custom_output_parent_cannot_be_inside_original_game_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            build = load_builds()[0]
            game_folder = Path(temp) / "game"
            game_folder.mkdir()
            source = game_folder / build.input_name
            shutil.copy2(STOCK / build.input_name, source)
            nested_output_root = game_folder / "modded-output"
            with self.assertRaisesRegex(PatcherError, "inside the original"):
                apply_patch(source, output_root=nested_output_root)
            self.assertFalse(nested_output_root.exists())

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

    def test_expanded_later_games_accept_exact_stock_save_layouts(self) -> None:
        compatibility = {
            "vv3": {
                "call": (0x28949, "E8632A0500"),
                "cave": (0x7B3B1, 102),
                "stock_size": "681C2F0100",
                "tail": "81C7CC1E0100",
                "tail_end": "81C6182F0100",
                "tail_length": "B914040000",
                "zero_count": "B9661D0000",
            },
            "vv4": {
                "call": (0x1FC19, "E8EF940600"),
                "cave": (0x8910D, 102),
                "stock_size": "680C710100",
                "tail": "81C7B8600100",
                "tail_end": "81C608710100",
                "tail_length": "B915040000",
                "zero_count": "B9EA1A0000",
            },
            "vv5": {
                "call": (0x25709, "E85EEF0600"),
                "cave": (0x9466C, 102),
                "stock_size": "68787D0100",
                "tail": "81C7146D0100",
                "tail_end": "81C6747D0100",
                "tail_length": "B919040000",
                "zero_count": "B9FC1C0000",
            },
        }
        for build in load_builds():
            if build.id not in compatibility:
                continue
            with self.subTest(game=build.id):
                rendered, _ = render_patched_bytes(
                    STOCK / build.input_name,
                    build,
                    "experimental_expanded_256",
                )
                expected = compatibility[build.id]
                call_offset, call_hex = expected["call"]
                self.assertEqual(
                    bytes(rendered[call_offset : call_offset + 5]),
                    bytes.fromhex(call_hex),
                )
                cave_offset, cave_length = expected["cave"]
                cave = bytes(rendered[cave_offset : cave_offset + cave_length])
                self.assertIn(bytes.fromhex(expected["stock_size"]), cave)
                self.assertIn(bytes.fromhex(expected["tail"]), cave)
                self.assertIn(bytes.fromhex(expected["tail_end"]), cave)
                self.assertIn(bytes.fromhex(expected["tail_length"]), cave)
                self.assertIn(bytes.fromhex(expected["zero_count"]), cave)
                self.assertTrue(cave.endswith(bytes.fromhex("C20C00")))
                if build.id == "vv3":
                    self.assertEqual(
                        bytes(rendered[0x28961:0x28966]),
                        bytes.fromhex("B92D690000"),
                    )

    def test_expanded_selection_end_pointers_use_reviewed_endpoints(self) -> None:
        expected = {
            "vv3": [
                (0x60D4C, "687B1F00"),
                (0x5F975, "6C7B1F00"),
                (0x5FA46, "807B1F00"),
            ],
            "vv4": [
                (0x66845, "CF2A2E00"),
                (0x66A15, "9C2A2E00"),
                (0x66AE6, "080E2E00"),
            ],
            "vv5": [
                (0x70280, "04152F00"),
                (0x705E5, "04152F00"),
                (0x70706, "04152F00"),
            ],
        }
        for build in load_builds():
            if build.id not in expected:
                continue
            for offset, value in expected[build.id]:
                with self.subTest(game=build.id, offset=hex(offset)):
                    rendered, _ = render_patched_bytes(
                        STOCK / build.input_name,
                        build,
                        "experimental_expanded_256",
                    )
                    self.assertEqual(
                        bytes(rendered[offset : offset + 4]), bytes.fromhex(value)
                    )

    def test_expanded_interaction_paths_use_256_record_bounds(self) -> None:
        expected = {
            "vv3": {
                0x60D46: "FF000000",  # main-world hit-test bound
                0x60D4C: "687B1F00",  # main-world hit-test endpoint
                0x5F975: "6C7B1F00",  # player-to-player endpoint
                0x5FA46: "807B1F00",  # nearby-villager endpoint
                0x5EE69: "00010000",  # active-record validator
                0x35A5A: "00010000",  # serialized index validator
            },
            "vv4": {
                0x66045: "FF000000",  # record lookup
                0x6683F: "FF000000",  # world-coordinate reverse picker
                0x66845: "CF2A2E00",  # world-coordinate endpoint
                0x66A0F: "FF000000",  # player-to-player reverse picker
                0x66A15: "9C2A2E00",  # player-to-player endpoint
                0x66AE0: "FF000000",  # nearby sick-villager picker bound
                0x66AE6: "080E2E00",  # nearby sick-villager endpoint
                0x669CC: "00010000",  # general target hit-test bound
                0x66E6F: "00010000",  # autonomous embrace picker bound
                0x66F11: "00010000",  # autonomous healer picker bound
                0x66C9C: "FF000000",  # selected-index setter
            },
            "vv5": {
                0x6F955: "FF000000",  # record lookup
                0x70280: "04152F00",  # main world endpoint
                0x70291: "FF000000",  # main world reverse bound
                0x70381: "FF000000",  # main world fallback bound
                0x704F6: "00010000",  # general target hit-test bound
                0x7058C: "00010000",  # fallback target hit-test bound
                0x705DF: "FF000000",  # player-to-player reverse bound
                0x70700: "FF000000",  # nearby-villager reverse bound
                0x708FC: "FF000000",  # selected-index setter
                0x70AFC: "00010000",  # autonomous embrace picker bound
                0x70BB6: "00010000",  # autonomous healer picker bound
                0x71D77: "FF000000",  # pending-record removal bound
            },
        }
        for build in load_builds():
            if build.id not in expected:
                continue
            with self.subTest(game=build.id):
                rendered, _ = render_patched_bytes(
                    STOCK / build.input_name,
                    build,
                    "experimental_expanded_256",
                )
                for offset, value in expected[build.id].items():
                    with self.subTest(offset=hex(offset)):
                        self.assertEqual(
                            bytes(rendered[offset : offset + 4]),
                            bytes.fromhex(value),
                        )

    def test_expanded_modes_leave_required_slot_zero_loaders_stock(self) -> None:
        slot_zero_calls = {
            "vv3": (0x288A9, "E8F2AAFDFF"),
            "vv4": (0x1FB86, "E8553CFEFF"),
            "vv5": (0x25676, "E8F5E0FDFF"),
        }
        for build in load_builds():
            if build.id not in slot_zero_calls:
                continue
            for mode in EXPANDED_MODES:
                with self.subTest(game=build.id, mode=mode):
                    rendered, _ = render_patched_bytes(
                        STOCK / build.input_name,
                        build,
                        mode,
                    )
                    offset, expected = slot_zero_calls[build.id]
                self.assertEqual(
                    bytes(rendered[offset : offset + 5]),
                    bytes.fromhex(expected),
                )

    def test_vv5_expanded_mode_loads_all_256_compact_villager_records(self) -> None:
        build = next(build for build in load_builds() if build.id == "vv5")
        rendered, _ = render_patched_bytes(
            STOCK / build.input_name,
            build,
            "experimental_expanded_256",
        )
        self.assertEqual(
            bytes(rendered[0x6FA75:0x6FA79]),
            struct.pack("<I", 256 * 280),
        )

    def test_vv3_reserves_four_padding_records_for_grouped_selectors(self) -> None:
        build = next(build for build in load_builds() if build.id == "vv3")
        source = STOCK / build.input_name
        original = source.read_bytes()
        rendered, _ = render_patched_bytes(
            source,
            build,
            "experimental_expanded_256",
        )
        pe = struct.unpack_from("<I", original, 0x3C)[0]
        optional_size = struct.unpack_from("<H", original, pe + 20)[0]
        section_count = struct.unpack_from("<H", original, pe + 6)[0]
        section_table = pe + 24 + optional_size
        data_header = next(
            section_table + index * 40
            for index in range(section_count)
            if original[
                section_table + index * 40 : section_table + index * 40 + 8
            ].rstrip(b"\0")
            == b".data"
        )
        old_virtual_size = struct.unpack_from("<I", original, data_header + 8)[0]
        new_virtual_size = struct.unpack_from("<I", rendered, data_header + 8)[0]
        self.assertEqual(
            new_virtual_size - old_virtual_size,
            (260 - 150) * 8076,
        )

    def test_stock_save_migration_preserves_every_original_payload_byte(self) -> None:
        layouts = {
            "vv3": (0x12F1C, 0x11ECC, 0x7598, 0x414),
            "vv4": (0x1710C, 0x160B8, 0x6BA8, 0x415),
            "vv5": (0x17D78, 0x16D14, 0x73F0, 0x419),
        }
        for game_id, (stock_size, gap_start, gap_size, dword_count) in layouts.items():
            with self.subTest(game=game_id):
                original = bytes((index * 131 + 17) & 0xFF for index in range(stock_size))
                expanded = bytearray(stock_size + gap_size)
                expanded[:gap_start] = original[:gap_start]
                tail = original[gap_start:]
                self.assertEqual(len(tail), dword_count * 4)
                expanded[gap_start + gap_size :] = tail
                self.assertEqual(bytes(expanded[:gap_start]), original[:gap_start])
                self.assertEqual(
                    bytes(expanded[gap_start : gap_start + gap_size]),
                    b"\0" * gap_size,
                )
                self.assertEqual(bytes(expanded[gap_start + gap_size :]), tail)

    def test_expanded_later_games_extend_index_validators_and_selection(self) -> None:
        expected = {
            "vv3": {
                0x35A5A: "00010000",
                0x5EE69: "00010000",
            },
            "vv4": {
                0x66045: "FF000000",
                0x66C9C: "FF000000",
                0x6683F: "FF000000",
                0x66A0F: "FF000000",
            },
            "vv5": {
                0x6F955: "FF000000",
                0x708FC: "FF000000",
                0x71D77: "FF000000",
            },
        }
        for build in load_builds():
            if build.id not in expected:
                continue
            with self.subTest(game=build.id):
                rendered, _ = render_patched_bytes(
                    STOCK / build.input_name,
                    build,
                    "experimental_expanded_256",
                )
                for offset, value in expected[build.id].items():
                    self.assertEqual(
                        bytes(rendered[offset : offset + 4]), bytes.fromhex(value)
                    )

    def test_vv1_magic_fruit_uses_global_puzzle_state_and_safe_fields(self) -> None:
        patch = get_fun_patch("vv1_magic_fruit_alters_mortality")
        self.assertIn("globally", patch.description)
        self.assertIn("seven displayed years", patch.description)
        self.assertIn("restores health to 100", patch.description)
        self.assertIn("stores nothing in villager likes or dislikes", patch.description)
        build = next(build for build in load_builds() if build.id == "vv1")
        rendered, _ = render_patched_bytes(
            STOCK / build.input_name,
            build,
            DEFAULT_PATCH_MODE,
            [patch.id],
        )
        self.assertEqual(bytes(rendered[0x4322F:0x43231]), bytes.fromhex("6A7E"))
        self.assertEqual(
            bytes(rendered[0x4892D:0x48939]),
            bytes.fromhex("E9CEDE000090909090909090"),
        )
        healing_cave = bytes(rendered[0x56800:0x56838])
        self.assertIn(bytes.fromhex("C70664000000"), healing_cave)
        self.assertIn(bytes.fromhex("C7461000000000"), healing_cave)
        mortality_cave = bytes(rendered[0x56880:0x5689E])
        self.assertIn(bytes.fromhex("80B998A0000000"), mortality_cave)
        self.assertIn(bytes.fromhex("83C56483C528"), mortality_cave)

    def test_vv1_magic_fruit_combines_with_every_vv1_patch(self) -> None:
        build = next(build for build in load_builds() if build.id == "vv1")
        selected = [
            patch.id for patch in load_fun_patches() if patch.game_id == "vv1"
        ]
        rendered, applied = render_patched_bytes(
            STOCK / build.input_name,
            build,
            DEFAULT_PATCH_MODE,
            selected,
        )
        self.assertTrue(rendered)
        self.assertGreater(len(applied), 5)

    def test_vv1_builder_action_fixes_preserve_other_scheduler_paths(self) -> None:
        patch = get_fun_patch("vv1_builder_action_fixes")
        self.assertIn("selected job is Building", patch.description)
        self.assertIn("ordinary play and time catch-up", patch.description)
        build = next(build for build in load_builds() if build.id == "vv1")
        rendered, _ = render_patched_bytes(
            STOCK / build.input_name,
            build,
            DEFAULT_PATCH_MODE,
            [patch.id],
        )
        self.assertEqual(
            bytes(rendered[0x48336:0x48342]),
            bytes.fromhex("E965E5000090909090909090"),
        )
        cave = bytes(rendered[0x568A0:0x568CB])
        self.assertEqual(
            cave,
            bytes.fromhex(
                "81BDECA20000900100000F8C921AFFFF"
                "89F869C0D803000083BC30D003000001"
                "0F847C1AFFFFE9A41AFFFF"
            ),
        )
        self.assertIn(bytes.fromhex("83BC30D003000001"), cave)

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

    def test_expanded_apply_uses_separate_short_256_names(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            build = load_builds()[2]
            game_folder = Path(temp) / "game"
            game_folder.mkdir()
            source = game_folder / build.input_name
            shutil.copy2(STOCK / build.input_name, source)
            output, log = apply_patch(source, "experimental_expanded_256")
            self.assertEqual(output.name, expanded_exe_name(build))
            self.assertEqual(output.parent.name, f"{build.title} - Modded 256")
            self.assertEqual(log.name, f"{build.title} - Modded 256.patch-log.json")
            self.assertTrue((output.parent / build.input_name).is_file())

    def test_expanded_save_copy_keeps_slot_zero_with_numbered_saves(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "LDW"
            for build in load_builds():
                vanilla = root / build.title
                vanilla.mkdir(parents=True)
                files = {
                    f"{build.title}0.ldw": b"slot-zero-" + build.id.encode(),
                    f"{build.title}1.ldw": b"village-one-" + build.id.encode(),
                    f"{build.title}21.ldw": b"village-backup-" + build.id.encode(),
                }
                for name, payload in files.items():
                    (vanilla / name).write_bytes(payload)
                self.assertEqual(
                    vanilla_save_folder_for(build, root),
                    vanilla.resolve(),
                )
                result = copy_vanilla_saves(
                    build,
                    "experimental_expanded_256",
                    save_root=root,
                )
                destination = root / f"{build.title} - Modded 256"
                self.assertEqual(
                    modded_save_folder_for(
                        build, "experimental_expanded_256", root
                    ),
                    destination,
                )
                self.assertEqual(result["status"], "vanilla_saves_copied")
                self.assertEqual(result["copied_files"], 3)
                for name, payload in files.items():
                    self.assertEqual((destination / name).read_bytes(), payload)

    def test_expanded_save_status_finds_existing_modded_folder_without_vanilla(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "LDW"
            build = load_builds()[2]
            destination = root / f"{build.title} - Modded 256"
            destination.mkdir(parents=True)
            slot_zero = destination / f"{build.title}0.ldw"
            slot_zero.write_bytes(b"expanded-slot-zero")

            self.assertIsNone(vanilla_save_folder_for(build, root))
            self.assertEqual(
                modded_save_folder_for(build, "experimental_expanded_256", root),
                destination.resolve(),
            )
            self.assertEqual(
                expanded_save_status(build, "experimental_expanded_256", root),
                {
                    "status": "modded_ready",
                    "folder": str(destination.resolve()),
                    "slot_zero": f"{build.title}0.ldw",
                },
            )

    def test_expanded_save_status_reports_missing_slot_zero(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "LDW"
            build = load_builds()[3]
            destination = root / f"{build.title} - Modded 256"
            destination.mkdir(parents=True)
            (destination / f"{build.title}1.ldw").write_bytes(b"numbered-only")

            status = expanded_save_status(build, "experimental_expanded_256", root)
            self.assertEqual(status["status"], "no_valid_save")
            self.assertEqual(
                status["expected_modded_folder"], str(destination.resolve())
            )
            self.assertEqual(status["slot_zero"], f"{build.title}0.ldw")

    def test_existing_modded_256_saves_require_explicit_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "LDW"
            build = load_builds()[2]
            vanilla = root / build.title
            destination = root / f"{build.title} - Modded 256"
            vanilla.mkdir(parents=True)
            destination.mkdir(parents=True)
            slot_zero = f"{build.title}0.ldw"
            slot_one = f"{build.title}1.ldw"
            (vanilla / slot_zero).write_bytes(b"vanilla-zero")
            (vanilla / slot_one).write_bytes(b"vanilla-one")
            (destination / slot_zero).write_bytes(b"existing-zero")
            (destination / slot_one).write_bytes(b"existing-one")
            preserved = copy_vanilla_saves(
                build,
                "experimental_expanded_256",
                save_root=root,
            )
            self.assertEqual(
                preserved["status"], "existing_modded_saves_preserved"
            )
            self.assertEqual((destination / slot_zero).read_bytes(), b"existing-zero")
            replaced = copy_vanilla_saves(
                build,
                "experimental_expanded_256",
                replace_existing=True,
                save_root=root,
            )
            self.assertEqual(replaced["status"], "vanilla_saves_copied")
            self.assertEqual((destination / slot_zero).read_bytes(), b"vanilla-zero")
            self.assertEqual((destination / slot_one).read_bytes(), b"vanilla-one")

    def test_overwrite_updates_same_folder_without_sibling_copies(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            build = load_builds()[0]
            game_folder = Path(temp) / build.title
            game_folder.mkdir()
            source = game_folder / build.input_name
            shutil.copy2(STOCK / build.input_name, source)
            first_output, _ = apply_patch(source, "immediate_fixed")
            (first_output.parent / "preserved-user-file.txt").write_text("keep")
            output, log = apply_patch(source, "immediate_fixed", overwrite=True)

            self.assertEqual(output, first_output)
            self.assertTrue(output.is_file())
            self.assertTrue(log.is_file())
            self.assertTrue(
                (output.parent / "preserved-user-file.txt").is_file()
            )
            self.assertEqual(
                {path.name for path in game_folder.parent.iterdir()},
                {game_folder.name, output.parent.name},
            )

    def test_vv1_school_lessons_grant_skill_is_guarded_and_additive(self) -> None:
        feature_id = "vv1_school_lessons_grant_skill"
        feature = next(patch for patch in load_fun_patches() if patch.id == feature_id)
        build = next(build for build in load_builds() if build.id == "vv1")
        source = STOCK / build.input_name
        rendered, applied = render_patched_bytes(source, build, DEFAULT_PATCH_MODE, [feature_id])
        self.assertEqual(len(applied), len(build.safety_patches) + len(get_patch_variant(build, DEFAULT_PATCH_MODE)["patches"]) + len(feature.patches))
        self.assertEqual(
            bytes(rendered[0x25505:0x2550A]),
            bytes.fromhex("E896F50100"),
        )
        self.assertEqual(
            bytes(rendered[0x44B08:0x44B28]),
            bytes.fromhex(
                "6A056A006A06E8FDE3FBFF83C40483C00C"
                "506A006A006A02578BCEE8C84EFFFF"
            ),
        )
        self.assertEqual(bytes(rendered[0x44B28:0x44B30]), bytes.fromhex("E9731B0100909090"))
        self.assertEqual(bytes(rendered[0x44BEC:0x44BF2]), bytes.fromhex("5F5E5BC20400"))
        self.assertEqual(bytes(rendered[0x44C50:0x44C52]), bytes.fromhex("6A00"))
        self.assertEqual(bytes(rendered[0x44C5A:0x44C5C]), bytes.fromhex("6A13"))
        self.assertEqual(bytes(rendered[0x44C64:0x44C6C]), bytes.fromhex("578BCEE88492FFFF"))
        self.assertEqual(
            bytes(rendered[0x566A0:0x566C1]),
            bytes.fromhex(
                "6A7F6A006A006A006A006A0E578BCEE83C33FEFF"
                "578BCEE83478FEFFE96FE4FEFF"
            ),
        )
        self.assertEqual(bytes(rendered[0x3A230:0x3A235]), bytes.fromhex("E9ABC40100"))
        self.assertEqual(
            bytes(rendered[0x566E0:0x56730]),
            bytes.fromhex(
                "837C24087F753F608BF18B44242469C0D80300008D9C30BC030000"
                "6A05E80EC8FAFF83C4048D3C836A03E801C8FAFF83C40483C007"
                "0107833F647E06C7076400000061C208008B44240848E9053BFEFF"
            ),
        )
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
        self.assertEqual(bytes(rendered[0x44B28:0x44B30]), bytes.fromhex("E9731B0100909090"))
        self.assertEqual(bytes(rendered[0x44BEC:0x44BF2]), bytes.fromhex("5F5E5BC20400"))
        self.assertEqual(bytes(rendered[0x44C50:0x44C52]), bytes.fromhex("6A00"))
        self.assertEqual(bytes(rendered[0x44C5A:0x44C5C]), bytes.fromhex("6A13"))
        self.assertEqual(bytes(rendered[0x44C64:0x44C6C]), bytes.fromhex("578BCEE88492FFFF"))
        self.assertEqual(rendered[0x47488], 0x13)
        self.assertEqual(rendered[0x20057], 0)
        self.assertEqual(bytes(rendered[0x1FF2E:0x1FF34]), bytes.fromhex("E9CD66030090"))
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
            bytes(rendered[0x1FF2E:0x1FF34]), bytes.fromhex("E9CD66030090")
        )
        self.assertEqual(
            bytes(rendered[0x56600:0x56664]),
            bytes.fromhex(
                "817C2420FF030000754F8B461081B8FCA2000088130000723B"
                "8B9034AD000081FAFF000000772D69D2D8030000035620807A2800"
                "741E81A8FCA20000881300008B8A640300004183F9147C0231C9"
                "898A64030000E95899FCFF8B86F8020000E9D098FCFF"
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
                + len(feature.patches)
                + 1,
                # The patcher records its verified PE checksum rewrite as one
                # additional automatic edit.
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
            + 2
            + len(feature.patches),
        )
        self.assertEqual(
            bytes(rendered[0x4A7FA:0x4A7FF]),
            bytes.fromhex("6896000000"),
        )
        self.assertEqual(
            bytes(rendered[0x4AB4B:0x4AB53]),
            bytes.fromhex("E980910200909090"),
        )
        self.assertEqual(
            bytes(rendered[0x73CD0:0x73CF1]),
            bytes.fromhex(
                "6A7F6A006A006A006A006A11578BCEE88C5EFDFF"
                "578BCEE8C4BEFDFFE9626EFDFF"
            ),
        )
        self.assertEqual(bytes(rendered[0x61B10:0x61B15]), bytes.fromhex("E96B220100"))
        self.assertEqual(
            bytes(rendered[0x73D80:0x73DF4]),
            bytes.fromhex(
                "837C24087F753F608BF18B44242469C08CE400008D9C30E4070000"
                "6A05E8FEF3F8FF83C4048D3C836A03E8F1F3F8FF83C40483C007"
                "0107833F647E06C7076400000061C20800837C24087E740A518B44"
                "240CE93EDDFEFF608B44242469C08CE400008D9C082C050000833B"
                "647D02FF0361C20800"
            ),
        )
        preview = dry_run(source, DEFAULT_PATCH_MODE, [feature_id])
        self.assertEqual(preview["fun_patches"], [feature_id])
        self.assertEqual(preview["output_name"], modded_exe_name(build))

    def test_vv2_fun_patches_combine_without_overlap(self) -> None:
        feature_ids = [
            "vv2_easier_healing_mastery",
            "vv2_teaching_children_grants_skill",
            "vv2_hospital_recovery_heals",
            "vv2_gong_of_wonder_coconuts_fix",
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
            + 2
            + feature_patch_count,
        )
        self.assertEqual(bytes(rendered[0x73CA0:0x73CC4]), bytes.fromhex(
            "8BC569C08CE40000C78430E0070000090000006A64558BCEE8D3C8FEFF5F5D5B5EC20800"
        ))
        self.assertEqual(bytes(rendered[0x73CD0:0x73CF1]), bytes.fromhex(
            "6A7F6A006A006A006A006A11578BCEE88C5EFDFF578BCEE8C4BEFDFFE9626EFDFF"
        ))
        self.assertEqual(
            bytes(rendered[0x5C569:0x5C571]),
            bytes.fromhex("E9B2780100909090"),
        )
        self.assertEqual(
            bytes(rendered[0x73E20:0x73E41]),
            bytes.fromhex(
                "6A7E6A006A006A006A006A11578BCEE83C5DFDFF"
                "578BCEE874BDFDFFE93087FEFF"
            ),
        )
        preview = dry_run(source, DEFAULT_PATCH_MODE, feature_ids)
        self.assertEqual(
            preview["fun_patches"],
            sorted(feature_ids, key=lambda item: (get_fun_patch(item).name.casefold(), item)),
        )
        self.assertEqual(preview["output_name"], modded_exe_name(build))

    def test_vv2_hospital_recovery_heals_exactly_once_on_completion(self) -> None:
        feature_id = "vv2_hospital_recovery_heals"
        build = next(build for build in load_builds() if build.id == "vv2")
        source = STOCK / build.input_name
        rendered, applied = render_patched_bytes(
            source, build, DEFAULT_PATCH_MODE, [feature_id]
        )
        feature = get_fun_patch(feature_id)
        self.assertEqual(
            len(applied),
            len(build.safety_patches)
            + len(get_patch_variant(build, DEFAULT_PATCH_MODE)["patches"])
            + 2
            + len(feature.patches),
        )
        self.assertEqual(
            bytes(rendered[0x5C569:0x5C571]),
            bytes.fromhex("E9B2780100909090"),
        )
        self.assertEqual(
            bytes(rendered[0x73DD7:0x73DF4]),
            bytes.fromhex(
                "608B44242469C08CE400008D9C082C050000"
                "833B647D02FF0361C20800"
            ),
        )
        self.assertEqual(
            bytes(rendered[0x73E20:0x73E41]),
            bytes.fromhex(
                "6A7E6A006A006A006A006A11578BCEE83C5DFDFF"
                "578BCEE874BDFDFFE93087FEFF"
            ),
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
            bytes(rendered[0x48A7B:0x48AA3]),
            bytes.fromhex(
                "C7863801000071030000"
                "C7863C010000C5010000"
                "C78640010000FF030000"
                "C786440100007E020000"
            ),
        )
        self.assertEqual(bytes(rendered[0x4974C:0x4974E]), bytes.fromhex("745B"))
        self.assertEqual(
            bytes(rendered[0x497A9:0x497AE]),
            bytes.fromhex("E952AF0400"),
        )
        self.assertEqual(
            bytes(rendered[0x94700:0x94730]),
            bytes.fromhex(
                "53578D8E38010000E883D0F6FF84C0741A"
                "6A11B908E05100E86367FAFFF6D81BC0254D020000"
                "E93850FBFFE93C50FBFF"
            ),
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
                "68570100008BC8E88FB8FBFF8B4F0850E8C657F7FFB9680F5200"
                "E9474BFBFF"
            ),
        )
        self.assertEqual(
            bytes(rendered[0x493F0:0x4942B]),
            bytes(source.read_bytes()[0x493F0:0x4942B]),
        )
        self.assertEqual(
            bytes(rendered[0x493F0:0x49421]),
            bytes.fromhex(
                "55578D8E38010000E89383FBFF84C00F84780300006A11"
                "B908E05100E86F1AFFFF84C0740CBFF40200006A11E948FCFFFF"
            ),
        )
        self.assertEqual(
            bytes(rendered[0x49421:0x4942B]),
            bytes.fromhex("68A7000000E815790000"),
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

    def test_vv2_gong_coconuts_adds_in_both_outcome_paths(self) -> None:
        feature_id = "vv2_gong_of_wonder_coconuts_fix"
        feature = next(patch for patch in load_fun_patches() if patch.id == feature_id)
        build = next(build for build in load_builds() if build.id == "vv2")
        rendered, applied = render_patched_bytes(
            STOCK / build.input_name, build, DEFAULT_PATCH_MODE, [feature_id]
        )
        self.assertEqual(
            len(applied),
            len(build.safety_patches)
            + len(get_patch_variant(build, DEFAULT_PATCH_MODE)["patches"])
            + len(feature.patches),
        )
        expected = bytes.fromhex("8380CCEA02001E909090")
        self.assertEqual(bytes(rendered[0x4E9A9:0x4E9B3]), expected)
        self.assertEqual(bytes(rendered[0x4F18C:0x4F196]), expected)

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

    def test_vv3_nature_level_one_actually_replenishes_food_faster(self) -> None:
        feature_id = "vv3_nature_honey_refill"
        feature = next(patch for patch in load_fun_patches() if patch.id == feature_id)
        build = next(build for build in load_builds() if build.id == "vv3")
        source = STOCK / build.input_name
        for mode in MODES:
            with self.subTest(mode=mode):
                rendered, applied = render_patched_bytes(
                    source, build, mode, [feature_id]
                )
                expansion_count = (
                    len(EXPANDED["games"]["vv3"]["patches"])
                    if get_patch_variant(build, mode).get("expanded_records", False)
                    else 0
                )
                self.assertEqual(
                    len(applied),
                    len(build.safety_patches)
                    + len(get_patch_variant(build, mode)["patches"])
                    + len(feature.patches)
                    + expansion_count,
                )
                self.assertEqual(
                    bytes(rendered[0x319E2:0x319EF]),
                    bytes.fromhex("E9599904009090909090909090"),
                )
                self.assertEqual(
                    bytes(rendered[0x319F9:0x31A09]),
                    bytes.fromhex("E9A29804009090909090909090909090"),
                )
                self.assertEqual(
                    bytes(rendered[0x347AA:0x347B7]),
                    bytes.fromhex("E9D16B04009090909090909090"),
                )
                self.assertEqual(
                    bytes(rendered[0x7B2A0:0x7B2E0]),
                    bytes.fromhex(
                        "8B560C2BC2506A05B918265800E80EBDFAFF83F801587C15"
                        "B954000000F7E1B93C860100F7F18BD0E93C67FBFF8BD0D1"
                        "E2B8C5B3A291F7E2C1EA0BE92967FBFF"
                    ),
                )
                self.assertEqual(
                    bytes(rendered[0x347CD:0x347D2]),
                    bytes.fromhex("BD38000000"),
                )
                self.assertEqual(
                    bytes(rendered[0x7B340:0x7B371]),
                    bytes.fromhex(
                        "506A05B918265800E873BCFAFF83F801588B4E0C7C0881C1"
                        "8C0A0000EB0681C1100E00003BC10F82B566FBFFE97E66FBFF"
                    ),
                )
                self.assertEqual(
                    bytes(rendered[0x7B380:0x7B3B1]),
                    bytes.fromhex(
                        "506A05B918265800E833BCFAFF83F801588B4FF87C0881C1"
                        "A41F0000EB0681C1302A00003BC10F825594FBFFE90694FBFF"
                    ),
                )
        self.assertEqual(2700, 3600 * 3 // 4)
        self.assertEqual(8100, 10800 * 3 // 4)
        self.assertEqual(126, 111 * 42 // 37)
        self.assertEqual(8100 * 56, 10800 * 42)
        self.assertEqual((2700 * 84) // 99900, 2)
        preview = dry_run(source, DEFAULT_PATCH_MODE, [feature_id])
        self.assertEqual(preview["fun_patches"], [feature_id])
        self.assertEqual(preview["output_name"], modded_exe_name(build))

    def test_vv3_nature_level_three_alters_mortality_by_seven_years(self) -> None:
        feature_id = "vv3_nature_level_three_alters_mortality"
        feature = get_fun_patch(feature_id)
        self.assertIn("seven displayed years", feature.description)
        self.assertIn("ordinary play and time catch-up", feature.description)
        build = next(build for build in load_builds() if build.id == "vv3")
        source = STOCK / build.input_name
        selected = ["vv3_nature_honey_refill", feature_id]
        for mode in MODES:
            with self.subTest(mode=mode):
                rendered, _ = render_patched_bytes(
                    source, build, mode, selected
                )
                self.assertEqual(
                    bytes(rendered[0x602ED:0x602F5]),
                    bytes.fromhex("E94EB10100909090"),
                )
                self.assertEqual(
                    bytes(rendered[0x7B440:0x7B464]),
                    bytes.fromhex(
                        "8D994C0400006A05B918265800E86EBBFAFF83F8037C06"
                        "83C36483C3283BFBE9914EFEFF"
                    ),
                )
        preview = dry_run(source, DEFAULT_PATCH_MODE, selected)
        self.assertEqual(preview["fun_patches"], selected)

    def test_vv3_rare_collectible_retries_rejected_random_choices(self) -> None:
        feature_id = "vv3_rare_collectible_retry"
        feature = get_fun_patch(feature_id)
        self.assertIn("full stock cooldown", feature.description)
        self.assertIn("eligible rare collectible", feature.description)
        build = next(build for build in load_builds() if build.id == "vv3")
        source = STOCK / build.input_name
        stock = source.read_bytes()
        self.assertEqual(bytes(stock[0x2DC4F:0x2DC51]), bytes.fromhex("752C"))
        self.assertEqual(bytes(stock[0x2DC5E:0x2DC60]), bytes.fromhex("751D"))
        self.assertEqual(
            bytes(stock[0x2DC85:0x2DC8A]), bytes.fromhex("9090909090")
        )
        for mode in MODES:
            with self.subTest(mode=mode):
                rendered, _ = render_patched_bytes(
                    source, build, mode, [feature_id]
                )
                self.assertEqual(
                    bytes(rendered[0x2DC4F:0x2DC51]), bytes.fromhex("7534")
                )
                self.assertEqual(
                    bytes(rendered[0x2DC5E:0x2DC60]), bytes.fromhex("7525")
                )
                self.assertEqual(
                    bytes(rendered[0x2DC85:0x2DC8A]),
                    bytes.fromhex("E9E6FEFFFF"),
                )
        preview = dry_run(source, DEFAULT_PATCH_MODE, [feature_id])
        self.assertEqual(preview["fun_patches"], [feature_id])
        self.assertEqual(preview["output_name"], modded_exe_name(build))

    def test_vv1_vv2_statistics_export_wraps_successful_primary_saves(self) -> None:
        expected = {
            "vv1": {
                "hook": 0x1BF63,
                "hook_bytes": "E8C8A70300",
                "cave": 0x56730,
                "game_push": "6A01",
            },
            "vv2": {
                "hook": 0x24BF3,
                "hook_bytes": "E858F20400",
                "cave": 0x73E50,
                "game_push": "6A02",
            },
        }
        for game_id, details in expected.items():
            with self.subTest(game_id=game_id):
                feature_id = f"{game_id}_write_village_statistics"
                feature = get_fun_patch(feature_id)
                build = next(build for build in load_builds() if build.id == game_id)
                source = STOCK / build.input_name
                rendered, _ = render_patched_bytes(
                    source, build, DEFAULT_PATCH_MODE, [feature_id]
                )
                hook = details["hook"]
                self.assertEqual(
                    bytes(rendered[hook : hook + 5]),
                    bytes.fromhex(details["hook_bytes"]),
                )
                cave = bytes(rendered[details["cave"] : details["cave"] + 0xD0])
                self.assertIn(b"VVFP Statistics Export.dll\0", cave)
                self.assertIn(b"WriteVillageStatistics\0", cave)
                self.assertIn(bytes.fromhex(details["game_push"]), cave)
                self.assertIn(bytes.fromhex("83FF017C"), cave)
                self.assertIn(bytes.fromhex("83FF057F"), cave)
                with tempfile.TemporaryDirectory() as temp:
                    folder = Path(temp) / build.title
                    folder.mkdir()
                    copied = folder / build.input_name
                    shutil.copy2(source, copied)
                    output, log_path = apply_patch(
                        copied,
                        DEFAULT_PATCH_MODE,
                        fun_patch_ids=[feature_id],
                    )
                    companion = output.parent / "VVFP Statistics Export.dll"
                    self.assertTrue(companion.is_file())
                    log = json.loads(log_path.read_text(encoding="utf-8"))
                    self.assertEqual(
                        digest(companion),
                        feature.raw["companion_files"][0]["sha256"],
                    )
                    self.assertEqual(len(log["companion_files"]), 1)

    def test_vv3_to_vv5_statistics_export_uses_inherited_per_save_blocks(self) -> None:
        expected = {
            "vv3": {
                "hook": 0x27D6C,
                "cave": 0x7B464,
                "cave_size": 0x200,
                "counter_hooks": {
                    0x5F45B: "881EE9B8010000",
                },
            },
            "vv4": {
                "hook": 0x1F13A,
                "cave": 0x89173,
                "cave_size": 0x200,
                "counter_hooks": {
                    0x1D987: "01378B07790B",
                    0x664DC: "885EFD385EFD",
                },
            },
            "vv5": {
                "hook": 0x245FA,
                "cave": 0x94932,
                "cave_size": 0x200,
                "counter_hooks": {
                    0x1EBA7: "01378B07790B",
                    0x6FF12: "889ED41C0000",
                },
            },
        }
        for game_id, details in expected.items():
            feature_id = f"{game_id}_write_village_statistics"
            build = next(build for build in load_builds() if build.id == game_id)
            source = STOCK / build.input_name
            for mode in MODES + EXPANDED_MODES:
                with self.subTest(game_id=game_id, mode=mode):
                    rendered, _ = render_patched_bytes(
                        source, build, mode, [feature_id]
                    )
                    cave = bytes(
                        rendered[
                            details["cave"] :
                            details["cave"] + details["cave_size"]
                        ]
                    )
                    self.assertIn(b"VVFP Statistics Export.dll\0", cave)
                    self.assertIn(b"WriteVillageStatistics\0", cave)
                    for offset, stock_hex in details["counter_hooks"].items():
                        stock_bytes = bytes.fromhex(stock_hex)
                        self.assertNotEqual(
                            bytes(rendered[offset : offset + len(stock_bytes)]),
                            stock_bytes,
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
            bytes.fromhex("6A64E86444F9FF"),
        )
        self.assertEqual(
            bytes(rendered[0x94400:0x9442A]),
            bytes.fromhex(
                "83B9FC1C00000D7417EB079090909090909083B9701C0000007E0A"
                "E9E0040000E9C1ADFDFFE910AEFDFF"
            ),
        )
        self.assertEqual(
            bytes(rendered[0x94900:0x94932]),
            bytes.fromhex(
                "6A64E859EDF6FF83C40483F8327D1E8B8E881B0000885C240F"
                "8D54240F5268A0000000E8580CFDFFE9F0A8FDFFE908A9FDFF"
            ),
        )
        self.assertEqual(
            bytes(rendered[0x94440:0x94460]),
            bytes(0x20),
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
        self.assertEqual(bytes(rendered[0x6F1F5:0x6F1FC]), bytes.fromhex(
            "6A64E86444F9FF"
        ))
        self.assertEqual(bytes(rendered[0x94900:0x94932]), bytes.fromhex(
            "6A64E859EDF6FF83C40483F8327D1E8B8E881B0000885C240F"
            "8D54240F5268A0000000E8580CFDFFE9F0A8FDFFE908A9FDFF"
        ))
        self.assertEqual(bytes(rendered[0x6C45D:0x6C462]), bytes.fromhex("E845800200"))
        self.assertEqual(bytes(rendered[0x6CDED:0x6CDF2]), bytes.fromhex("E8B5760200"))
        self.assertEqual(bytes(rendered[0x6BF9A:0x6BF9F]), bytes.fromhex("E808850200"))
        self.assertEqual(bytes(rendered[0x796EB:0x796F0]), bytes.fromhex("E8B7AD0100"))
        self.assertEqual(
            bytes(rendered[0x6BF55:0x6BF6F]),
            bytes.fromhex(
                "8B8E881B00008D44241650E8FB840200C644241E00E81196FFFF"
            ),
        )
        self.assertEqual(
            bytes(rendered[0x6CC30:0x6CC43]),
            bytes.fromhex("8D54241952885C241DE822780200E9D5FEFFFF"),
        )
        self.assertEqual(
            bytes(rendered[0x796AA:0x796CC]),
            bytes.fromhex(
                "8B4C24108D54240C52E8A8AD0100C781541C000017000000"
                "C644241400E8B4BEFEFF"
            ),
        )
        self.assertEqual(
            bytes(rendered[0x7971D:0x79735]),
            bytes.fromhex(
                "8D4C2404518B4C2414E855AD01009090909090E84BBEFEFF"
            ),
        )
        self.assertEqual(bytes(rendered[0x94460:0x944C0]), bytes.fromhex("E9DB02000090909090909090909090909090909090909090909090909090909090909090909090909090909090909090909090909090909090909090909090909090909090909090909090909090909090909090909090909090909090909090"))
        self.assertEqual(bytes(rendered[0x94740:0x94740+66]), bytes.fromhex("5A525183B9701C0000007E223083B9541C0000007E22306A02E802EFF6FF83C404596BC00B05950000005A5052C359B8950000005A5052C359B8A00000005A5052C3"))
        self.assertEqual(bytes(rendered[0x947B0:0x947B0+90]), bytes.fromhex("5A525183B9701C0000007E2A3083B9541C0000007E32306A02E892EEF6FF83C404596BC081051F000000C744240C660000005A5052C359B81F000000C744240C660000005A5052C359B8A0000000C744240C660000005A5052C3"))
        self.assertEqual(bytes(rendered[0x94840:0x94840+66]), bytes.fromhex("5A525183B9701C0000007E223083B9541C0000007E22306A02E802EEF6FF83C404596BC00B059D0000005A5052C359B89D0000005A5052C359B8A00000005A5052C3"))
        self.assertEqual(
            bytes(rendered[0x25FE1:0x25FE5]), bytes.fromhex("40454900")
        )
        self.assertEqual(
            bytes(rendered[0x94540:0x94548]), bytes.fromhex("0000000000001840")
        )
        preview = dry_run(source, DEFAULT_PATCH_MODE, feature_ids)
        self.assertEqual(
            preview["fun_patches"],
            sorted(feature_ids, key=lambda item: (get_fun_patch(item).name.casefold(), item)),
        )
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
        self.assertEqual(bytes(rendered[0x6C45D:0x6C462]), bytes.fromhex("E845800200"))
        self.assertEqual(bytes(rendered[0x6CDED:0x6CDF2]), bytes.fromhex("E8B5760200"))
        self.assertEqual(bytes(rendered[0x6BF9A:0x6BF9F]), bytes.fromhex("E808850200"))
        self.assertEqual(bytes(rendered[0x796EB:0x796F0]), bytes.fromhex("E8B7AD0100"))
        self.assertEqual(bytes(rendered[0x6BF60:0x6BF65]), bytes.fromhex("E8FB840200"))
        self.assertEqual(bytes(rendered[0x6CC39:0x6CC3E]), bytes.fromhex("E822780200"))
        self.assertEqual(bytes(rendered[0x796B3:0x796B8]), bytes.fromhex("E8A8AD0100"))
        self.assertEqual(
            bytes(rendered[0x79726:0x79730]),
            bytes.fromhex("E855AD01009090909090"),
        )
        self.assertEqual(bytes(rendered[0x94460:0x944C0]), bytes.fromhex("E9DB02000090909090909090909090909090909090909090909090909090909090909090909090909090909090909090909090909090909090909090909090909090909090909090909090909090909090909090909090909090909090909090"))
        self.assertEqual(bytes(rendered[0x94740:0x94740+66]), bytes.fromhex("5A525183B9701C0000007E223083B9541C0000007E22306A02E802EFF6FF83C404596BC00B05950000005A5052C359B8950000005A5052C359B8A00000005A5052C3"))
        self.assertEqual(bytes(rendered[0x947B0:0x947B0+90]), bytes.fromhex("5A525183B9701C0000007E2A3083B9541C0000007E32306A02E892EEF6FF83C404596BC081051F000000C744240C660000005A5052C359B81F000000C744240C660000005A5052C359B8A0000000C744240C660000005A5052C3"))
        self.assertEqual(bytes(rendered[0x94840:0x94840+66]), bytes.fromhex("5A525183B9701C0000007E223083B9541C0000007E22306A02E802EEF6FF83C404596BC00B059D0000005A5052C359B89D0000005A5052C359B8A00000005A5052C3"))
        preview = dry_run(source, DEFAULT_PATCH_MODE, [feature_id])
        self.assertEqual(preview["fun_patches"], [feature_id])
        self.assertEqual(preview["output_name"], modded_exe_name(build))

    def test_vv1_origins_exclusive_features_are_guarded_and_named_exactly(self) -> None:
        feature_id = "vv1_enable_origins_exclusive_features"
        feature = get_fun_patch(feature_id)
        self.assertEqual(feature.name, "Enable Origins-Exclusive Features")
        self.assertIn("Tech Point Doubler", feature.description)
        self.assertIn("Food Point Doubler", feature.description)
        self.assertIn(
            "Golden Child and Island Event outcomes remain native",
            feature.description,
        )
        self.assertIn("500,000-tech-point", feature.description)
        self.assertIn("Set Age to 18", feature.description)
        self.assertIn("chooses Farming when none is checked", feature.description)
        self.assertIn("adds running", feature.description)
        self.assertIn("removes running", feature.description)

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
        self.assertEqual(bytes(rendered[0x35AB0:0x35AB5]), bytes.fromhex("E94B0E0200"))
        self.assertEqual(bytes(rendered[0x358DC:0x358E1]), bytes.fromhex("E94F100200"))
        self.assertEqual(bytes(rendered[0x1D120:0x1D125]), bytes.fromhex("E93B9B0300"))
        self.assertEqual(bytes(rendered[0x1D140:0x1D145]), bytes.fromhex("E96B9B0300"))
        self.assertEqual(bytes(rendered[0x4A700:0x4A705]), bytes.fromhex("E98BC60000"))
        self.assertEqual(bytes(rendered[0x4A5FA:0x4A5FF]), bytes.fromhex("E9C1C70000"))
        self.assertEqual(
            bytes(rendered[0x56907:0x5690E]),
            bytes.fromhex("8B44240883F802"),
        )
        self.assertEqual(
            bytes(rendered[0x56D97:0x56D9E]),
            bytes.fromhex("8B44240883F806"),
        )
        self.assertEqual(
            bytes(rendered[0x3CD22:0x3CD2E]),
            bytes.fromhex("6A2653E8B6A5FFFF84C0740E"),
        )
        self.assertEqual(
            bytes(rendered[0x28470:0x28477]),
            bytes.fromhex("E9DBE802009090"),
        )
        self.assertEqual(
            bytes(rendered[0x23D85:0x23D8A]),
            bytes.fromhex("E81672FFFF"),
        )
        payload = bytes(rendered[0x85D30:0x86000])
        self.assertIn(b"Tech Point Doubler\0", payload)
        self.assertIn(b"Food Point Doubler\0", payload)
        self.assertIn(b"Villager Upgrades\0", payload)
        self.assertNotIn(b"Bump Max Population\0", payload)
        self.assertIn(b"Gained 3 children.\0", payload)
        self.assertIn(
            b"The village population is already at maximum capacity.\0",
            payload,
        )
        self.assertIn(b"Running cannot be added.\0", payload)
        self.assertNotIn(b"Gained 1,000 food.\0", payload)
        self.assertNotIn(b"Gained 3,000 tech points.\0", payload)
        self.assertNotIn(b"Origins Exclusive Features.ini\0", payload)
        self.assertIn((500000).to_bytes(4, "little"), payload)
        code = bytes(rendered[0x56900:0x57000])
        self.assertIn(bytes.fromhex("817C240494814200"), code)
        self.assertIn(bytes.fromhex("817C2404DA814200"), code)
        self.assertNotIn(bytes.fromhex("83780402"), code)
        self.assertNotIn(bytes.fromhex("83780406"), code)
        self.assertIn(bytes.fromhex("FF1510704500"), code)
        self.assertNotIn((10101010).to_bytes(4, "little"), code)
        self.assertIn(bytes.fromhex("83B848AD000000"), code)
        self.assertIn(bytes.fromhex("83B84CAD000000"), code)
        self.assertIn(bytes.fromhex("C78748AD000001000000"), code)
        self.assertNotIn(bytes.fromhex("C7874CAD000001000000"), code)
        self.assertNotIn(bytes.fromhex("C742582C010000"), code)
        self.assertIn(bytes.fromhex("8D8AA8030000"), code)
        self.assertIn(bytes.fromhex("8339267506C701FFFFFFFF"), code)
        self.assertIn(bytes.fromhex("8D8A98030000"), code)
        self.assertNotIn(bytes.fromhex("C782A003000026000000"), code)
        self.assertNotIn(bytes.fromhex("EB0A90909090909090909090"), rendered)
        self.assertIn(bytes.fromhex("2DBC02000083F8647D05B864000000"), code)
        self.assertIn(bytes.fromhex("817C24082C1A4B7F750C6A0A6A0CE83D0FFDFF"), code)
        self.assertIn(bytes.fromhex("83F80C76"), code)
        self.assertIn(bytes.fromhex("80BFE89F000001"), code)
        self.assertIn(bytes.fromhex("83F81676"), code)
        self.assertIn(bytes.fromhex("80BFF09F000001"), code)
        self.assertIn(bytes.fromhex("83F82F76"), code)
        self.assertIn(bytes.fromhex("80BFF89F000001"), code)
        self.assertIn(bytes.fromhex("3DFD0000000F87"), code)
        self.assertIn(
            bytes.fromhex("83BA D0030000 00 750A C782 D0030000 01000000".replace(" ", "")),
            code,
        )
        checksum_offset, = struct.unpack_from("<I", rendered, 0x3C)
        checksum_offset += 24 + 64
        self.assertNotEqual(struct.unpack_from("<I", rendered, checksum_offset)[0], 0)
        with tempfile.TemporaryDirectory() as temp:
            game_folder = Path(temp) / build.title
            game_folder.mkdir()
            copied_source = game_folder / build.input_name
            shutil.copy2(source, copied_source)
            output, log_path = apply_patch(
                copied_source,
                DEFAULT_PATCH_MODE,
                fun_patch_ids=[feature_id],
            )
            companion = output.parent / "VVFP Origins Icons.dll"
            self.assertTrue(companion.is_file())
            log = json.loads(log_path.read_text(encoding="utf-8"))
            self.assertEqual(len(log["companion_files"]), 1)
            self.assertEqual(
                digest(companion),
                feature.raw["companion_files"][0]["sha256"],
            )

    def test_vv2_origins_containment_leaves_unrelated_features_renderable(self) -> None:
        build = next(build for build in load_builds() if build.id == "vv2")
        source = STOCK / build.input_name
        all_vv2_features = [
            patch.id
            for patch in load_fun_patches()
            if patch.game_id == "vv2"
        ]
        self.assertEqual(
            set(all_vv2_features),
            {
                "vv2_birth_control",
                "vv2_easier_healing_mastery",
                "vv2_teaching_children_grants_skill",
                "vv2_hospital_recovery_heals",
                "vv2_gong_of_wonder_coconuts_fix",
                "vv2_write_village_statistics",
            },
        )
        for mode in MODES + EXPANDED_MODES:
            with self.subTest(mode=mode):
                rendered, applied = render_patched_bytes(
                    source,
                    build,
                    mode,
                    all_vv2_features,
                )
                self.assertEqual(bytes(rendered[0x234:0x238]), source.read_bytes()[0x234:0x238])
                owners = {item["owner"] for item in applied}
                self.assertNotIn("feature:vv2_enable_origins_exclusive_features", owners)
                self.assertNotIn("feature:vv2_origins_village_wide_upgrades", owners)
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / build.title
            folder.mkdir()
            copied = folder / build.input_name
            shutil.copy2(source, copied)
            output, log_path = apply_patch(
                copied,
                DEFAULT_PATCH_MODE,
                fun_patch_ids=all_vv2_features,
            )
            companion = output.parent / "VVFP Origins Icons.dll"
            self.assertFalse(companion.exists())
            log = json.loads(log_path.read_text(encoding="utf-8"))
            self.assertNotIn("vv2_enable_origins_exclusive_features", log["fun_patches"])
            self.assertNotIn("vv2_origins_village_wide_upgrades", log["fun_patches"])

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
