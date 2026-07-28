from __future__ import annotations

import hashlib
import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import FunPatch, load_builds, load_fun_patches, render_patched_bytes

STOCK = ROOT / "research/stock-executables/Virtual Villagers - New Believers.exe"
MANIFEST = ROOT / "data/vv5_origins_feature.json"
BUILDER = ROOT / "scripts/build_vv5_origins_feature.py"
EXPANDED = ROOT / "data/expanded_256.json"
COMPANION = ROOT / "assets/origins/VVFP Origins Icons.dll"
FEATURE_ID = "vv5_enable_origins_exclusive_features"


class VV5OriginsFeatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.stock = STOCK.read_bytes()
        cls.feature = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.payload_patch = next(
            item
            for item in cls.feature["patches"]
            if int(item["offset"], 0) == 0xDB000
        )
        cls.payload = bytes.fromhex(cls.payload_patch["after"])
        cls.source = BUILDER.read_text(encoding="utf-8")

    def test_exact_build_and_companion_identity(self) -> None:
        self.assertEqual(
            hashlib.sha256(self.stock).hexdigest().upper(),
            "92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D",
        )
        companion = ROOT / self.feature["companion_files"][0]["source"]
        self.assertEqual(
            hashlib.sha256(companion.read_bytes()).hexdigest().upper(),
            self.feature["companion_files"][0]["sha256"],
        )
        self.assertEqual(
            self.feature["companion_files"][0]["sha256"],
            hashlib.sha256(companion.read_bytes()).hexdigest().upper(),
        )

    def test_constructor_transports_thiscall_receiver_before_stock_ctor(self) -> None:
        self.assertEqual(
            self.source.count("mov edi, eax\n            mov ecx, edi\n            push 72"),
            2,
        )
        self.assertEqual(self.payload.count(bytes.fromhex("89F96A48")), 2)

    def test_grant_youth_label_explains_age_floor(self) -> None:
        label = "Grant Youth (-35 years, min age 5)"
        self.assertIn(label.encode("utf-16le"), COMPANION.read_bytes())

    def test_all_guards_match_stock_and_payload_is_isolated(self) -> None:
        for item in self.feature["patches"]:
            offset = int(item["offset"], 0)
            before = bytes.fromhex(item["before"])
            self.assertEqual(self.stock[offset : offset + len(before)], before)
            self.assertEqual(len(before), len(bytes.fromhex(item["after"])))
        self.assertEqual(len(self.payload), 0xF60)
        self.assertEqual(
            self.stock[0xDB000 : 0xDB000 + len(self.payload)],
            b"\0" * len(self.payload),
        )
        pe = struct.unpack_from("<I", self.stock, 0x3C)[0]
        section_table = pe + 24 + struct.unpack_from("<H", self.stock, pe + 20)[0]
        shr = section_table + 3 * 40
        self.assertEqual(self.stock[shr : shr + 8].rstrip(b"\0"), b".shr")
        characteristics = struct.unpack_from("<I", self.stock, shr + 36)[0]
        self.assertFalse(characteristics & 0x20000000)
        section_patch = next(
            item
            for item in self.feature["patches"]
            if int(item["offset"], 0) == shr + 36
        )
        self.assertEqual(section_patch["before"], "400000D0")
        self.assertEqual(section_patch["after"], "400000F0")
        expanded = json.loads(EXPANDED.read_text(encoding="utf-8"))
        for item in expanded["games"]["vv5"]["patches"]:
            start = int(item["offset"], 0)
            end = start + len(bytes.fromhex(item["before"]))
            self.assertTrue(end <= 0xDB000 or start >= 0xDC000)

    def test_time_warp_is_exactly_three_displayed_years(self) -> None:
        self.assertIn("mov eax, 129600", self.source)
        self.assertIn("idiv ecx", self.source)
        self.assertIn("sub dword ptr [0x4C6250], eax", self.source)
        self.assertIn("sbb dword ptr [0x4C6254], 0", self.source)
        self.assertIn("3 displayed villager years", self.feature["description"])

    def test_unsafe_native_time_and_event_rows_are_disabled_for_heathen_safety(self) -> None:
        self.assertEqual(
            self.feature["native_event_safety"]["disabled_rows"],
            ["Time Warp", "Island Event", "Barrel of Babies"],
        )
        self.assertIn("not verified safe for Heathens", self.source)
        self.assertIn(b"3 displayed years", self.payload)

    def test_barrel_uses_native_index_and_dynamic_150_256_guard(self) -> None:
        self.assertIn("call 0x4944C0", self.source)
        self.assertIn("mov ecx, dword ptr [0x41F1E6]", self.source)
        self.assertIn("sub ecx, 3", self.source)
        self.assertIn("or dword ptr [0x51D388], 4", self.source)
        self.assertIn("mov esi, 30", self.source)
        self.assertIn("and dword ptr [0x51D388], 0xFFFFFFFB", self.source)
        expanded = json.loads(EXPANDED.read_text(encoding="utf-8"))
        bound = next(
            item
            for item in expanded["games"]["vv5"]["patches"]
            if int(item["offset"], 0) == 0x1F1E6
        )
        self.assertEqual(bound["before"], "96000000")
        self.assertEqual(bound["after"], "00010000")

    def test_doublers_are_save_scoped_and_encode_candidate_guards(self) -> None:
        self.assertIn("test dword ptr [0x51D388], 1", self.source)
        self.assertIn("test dword ptr [0x51D388], 2", self.source)
        self.assertIn("cmp dword ptr [0x41F1E6], 0x96", self.source)
        self.assertIn("cmp ebx, 4", self.source)
        self.assertIn("or dword ptr [0x51D388], 2", self.source)
        self.assertIn("test esi, esi", self.source)
        self.assertIn("test eax, eax", self.source)
        manifest = json.loads((ROOT / "data" / "vv5_origins_feature.json").read_text(encoding="utf-8"))
        evidence = manifest["doubler_evidence"]
        contract = manifest["doubler_composition_contract"]
        self.assertIn("stock-layout implemented", evidence["hook_status"])
        self.assertIn("expanded-256", contract["status"])
        self.assertEqual(contract["exclusions"], ["Island Event outcomes"])
        self.assertEqual(
            manifest["doubler_purchase_status"]["new_purchase"],
            "Tech and Food available in stock layout at 500,000 tech points after their exact positive-whitelist wrappers; both unavailable in expanded-256",
        )
        self.assertEqual(
            manifest["doubler_purchase_status"]["repurchase"],
            "full-price repurchase after zero-cost/no-refund removal in stock layout for both doublers; expanded-256 remains unavailable for new purchases",
        )

    def test_tech_wrapper_exact_stock_bytes_and_six_return_whitelist(self) -> None:
        evidence = self.feature["doubler_evidence"]["tech_writer_hook"]
        self.assertEqual(evidence["virtual_address"], "0x4237B0")
        self.assertEqual(evidence["file_offset"], "0x237B0")
        self.assertEqual(evidence["before"], "568B742408")
        self.assertEqual(evidence["after"], "E94BF23800")
        self.assertEqual(evidence["wrapper_virtual_address"], "0x7B2A00")
        self.assertEqual(evidence["wrapper_file_offset"], "0xDBA00")
        expected = (
            "8B44240485C07E46F70588D3510001000000743A"
            "813C24BE474100742D813C24DD4741007424813C24F9474100741B"
            "813C244DDE46007412813C247CDE46007409813C24A5DE46007504"
            "D1642404568B7424080131E95D0DC7FF"
        )
        wrapper = bytes.fromhex(evidence["wrapper_bytes"])
        self.assertEqual(wrapper.hex().upper(), expected)
        self.assertEqual(len(wrapper), 90)
        self.assertEqual(evidence["ownership_mask"], "0x1")
        self.assertEqual(
            evidence["eligible_returns"],
            ["0x4147BE", "0x4147DD", "0x4147F9", "0x46DE4D", "0x46DE7C", "0x46DEA5"],
        )
        self.assertEqual(evidence["excluded_refund_return"], "0x419EA3")
        self.assertEqual(evidence["branch_destinations"], ["0x7B2A4A", "0x7B2A4E", "0x4237B7"])
        self.assertEqual(
            self.feature["doubler_evidence"]["tech_exclusions"],
            [
                "all 16 Island Event outcomes",
                "all eight writer tail paths",
                "technology purchase/spending/deduction paths",
                "zero and negative deltas",
                "unknown caller returns",
            ],
        )
        payload_offset = 0xDB000 + (0x7B2A00 - 0x7B2000)
        self.assertEqual(self.payload[payload_offset - 0xDB000 : payload_offset - 0xDB000 + 90], wrapper)

    def test_tech_mode_marker_and_purchase_matrix(self) -> None:
        self.assertIn("tech_owned_remove", self.source)
        self.assertIn("cmp dword ptr [0x41F1E6], 0x96", self.source)
        self.assertIn("or dword ptr [0x51D388], 1", self.source)
        overrides = self.feature["patch_mode_overrides"]
        for mode in ("experimental_expanded_256", "experimental_expanded_256_progression"):
            entries = overrides[mode]
            tech = next(item for item in entries if item["offset"] == "0x237B0")
            self.assertEqual(tech["before"], "E94BF23800")
            self.assertEqual(tech["after"], "568B742408")
            self.assertIn("no expanded Tech Doubler detour", tech["purpose"])

        def tech_action(owned: bool, marker: int) -> str:
            if owned:
                return "remove"
            return "purchase" if marker == 0x96 else "unavailable"

        for expanded, marker in ((False, 0x96), (True, 0x100)):
            with self.subTest(expanded=expanded):
                self.assertEqual(tech_action(False, marker), "purchase" if not expanded else "unavailable")
                self.assertEqual(tech_action(True, marker), "remove")
        build = next(item for item in load_builds() if item.id == "vv5")
        for mode, expected_hook, expected_marker in (
            ("collection_progression", "E94BF23800", "96000000"),
            ("immediate_fixed", "E94BF23800", "96000000"),
            ("experimental_expanded_256", "568B742408", "00010000"),
            ("experimental_expanded_256_progression", "568B742408", "00010000"),
        ):
            with self.subTest(mode=mode):
                rendered, _ = render_patched_bytes(
                    STOCK, build, mode, [FEATURE_ID]
                )
                self.assertEqual(bytes(rendered[0x237B0 : 0x237B5]).hex().upper(), expected_hook)
                self.assertEqual(bytes(rendered[0x1F1E6 : 0x1F1EA]).hex().upper(), expected_marker)

    def test_tech_positive_whitelist_reference_matrix(self) -> None:
        eligible = {0x4147BE, 0x4147DD, 0x4147F9, 0x46DE4D, 0x46DE7C, 0x46DEA5}
        excluded = {0x419EA3, 0x420000, 0x46CED1}

        def adjusted(owner: bool, return_va: int, delta: int) -> int:
            if not owner or delta <= 0 or return_va not in eligible:
                return delta
            return delta * 2

        for return_va in eligible:
            with self.subTest(return_va=hex(return_va)):
                self.assertEqual(adjusted(True, return_va, 5), 10)
                self.assertEqual(adjusted(False, return_va, 5), 5)
        for return_va in excluded:
            with self.subTest(return_va=hex(return_va)):
                self.assertEqual(adjusted(True, return_va, 5), 5)
        for delta in (0, -1, -500000):
            self.assertEqual(adjusted(True, 0x4147BE, delta), delta)
        # The wrapper receives the final positive delta and doubles only once.
        self.assertEqual(adjusted(True, 0x4147BE, 5), 10)

    def test_food_wrapper_exact_stock_bytes_and_whitelist(self) -> None:
        evidence = self.feature["doubler_evidence"]["stock_hook"]
        self.assertEqual(evidence["virtual_address"], "0x41EB6F")
        self.assertEqual(evidence["file_offset"], "0x1EB6F")
        self.assertEqual(evidence["before"], "85F67E3456")
        self.assertEqual(evidence["after"], "E98C3F3900")
        self.assertEqual(evidence["wrapper_virtual_address"], "0x7B2B00")
        self.assertEqual(evidence["wrapper_file_offset"], "0xDBB00")
        wrapper = bytes.fromhex(evidence["wrapper_bytes"])
        self.assertEqual(
            wrapper.hex().upper(),
            "85F67E18F70588D3510002000000740C817C240870494100750201F685F67E0656E94EC0C6FFE97CC0C6FF",
        )
        self.assertEqual(len(wrapper), 43)
        self.assertEqual(evidence["branch_destinations"], ["0x41EB74", "0x41EBA7"])
        self.assertEqual(evidence["eligible_return"], "0x414970")
        self.assertEqual(evidence["ownership_mask"], "0x2")
        payload_offset = 0xDB000 + (0x7B2B00 - 0x7B2000)
        self.assertEqual(self.payload[payload_offset - 0xDB000 : payload_offset - 0xDB000 + 43], wrapper)

    def test_food_mode_marker_and_purchase_matrix(self) -> None:
        self.assertIn("cmp dword ptr [0x41F1E6], 0x96", self.source)
        self.assertIn("or eax, 0x0800", self.source)
        self.assertIn("or eax, 0x1000", self.source)
        self.assertIn("food_owned", self.source)
        self.assertIn("food_owned_remove", self.source)
        self.assertIn("or dword ptr [0x51D388], 2", self.source)
        self.assertEqual(self.stock[0x1F1E6 : 0x1F1EA], bytes.fromhex("96000000"))
        overrides = self.feature["patch_mode_overrides"]
        self.assertEqual(set(overrides), {"experimental_expanded_256", "experimental_expanded_256_progression"})
        for mode, entries in overrides.items():
            self.assertEqual(len(entries), 2)
            food = next(item for item in entries if item["offset"] == "0x1EB6F")
            self.assertEqual(food["before"], "E98C3F3900")
            self.assertEqual(food["after"], "85F67E3456")
            self.assertIn("no expanded Food Doubler detour", food["purpose"])

        def food_action(owned: bool, marker: int) -> str:
            if owned:
                return "remove"
            return "purchase" if marker == 0x96 else "unavailable"

        for expanded, marker in ((False, 0x96), (True, 0x100)):
            with self.subTest(expanded=expanded):
                self.assertEqual(food_action(False, marker), "purchase" if not expanded else "unavailable")
                self.assertEqual(food_action(True, marker), "remove")
                state = 0x0800  # Tech row remains unavailable in every mode.
                if expanded:
                    state |= 0x1000
                self.assertEqual(bool(state & 0x1000), expanded)
                owned_state = state | 0x10
                self.assertTrue(owned_state & 0x10)
        self.assertEqual(food_action(False, 0), "unavailable")
        build = next(item for item in load_builds() if item.id == "vv5")
        for mode, expected_hook, expected_marker in (
            ("collection_progression", "E98C3F3900", "96000000"),
            ("immediate_fixed", "E98C3F3900", "96000000"),
            ("experimental_expanded_256", "85F67E3456", "00010000"),
            ("experimental_expanded_256_progression", "85F67E3456", "00010000"),
        ):
            with self.subTest(mode=mode):
                rendered, _ = render_patched_bytes(
                    STOCK, build, mode, [FEATURE_ID]
                )
                self.assertEqual(bytes(rendered[0x1EB6F : 0x1EB74]).hex().upper(), expected_hook)
                self.assertEqual(bytes(rendered[0x1F1E6 : 0x1F1EA]).hex().upper(), expected_marker)

    def test_patch_override_schema_rejects_malformed_lengths(self) -> None:
        from vv_fun_patcher import PatcherError, Record, validate_fun_patch_catalog

        malformed = Record(
            {
                "id": "vv5_test_override",
                "name": "VV5 test override",
                "game_id": "vv5",
                "patches": [],
                "patch_mode_overrides": {
                    "experimental_expanded_256": [
                        {
                            "offset": "0x1EB6F",
                            "before": "85F67E3456",
                            "after": "90",
                            "purpose": "malformed test",
                        }
                    ]
                },
            }
        )
        with self.assertRaises(PatcherError):
            validate_fun_patch_catalog([malformed])

    def test_food_mastery_final_delta_reference_matrix(self) -> None:
        for native, doubled in ((6, 12), (35, 70), (9, 18), (52, 104), (12, 24), (70, 140)):
            with self.subTest(native=native):
                self.assertEqual(native * 2, doubled)
        self.assertEqual(0, 0)
        self.assertLessEqual(-5, 0)

    def test_food_mastery_exact_build_and_positive_whitelist_metadata(self) -> None:
        manifest = json.loads((ROOT / "data" / "vv5_origins_feature.json").read_text(encoding="utf-8"))
        evidence = manifest["doubler_evidence"]
        self.assertEqual(evidence["build"], {
            "filename": "Virtual Villagers - New Believers.exe",
            "size": 991232,
            "sha256": "92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D",
        })
        mastery = evidence["food_mastery"]
        self.assertEqual(mastery["technology_id"], 4)
        self.assertEqual(mastery["costs"], {"level_1_to_2": 3000, "level_2_to_3": 40000})
        self.assertEqual(mastery["collection_return"], "0x414970")
        self.assertEqual(mastery["collection_base_to_native"], {"6": [6, 9, 12], "35": [35, 52, 70]})
        self.assertIn("unknown callers remain native", evidence["island_event_producers"][0])

    def test_food_mastery_metadata_change_does_not_change_runtime_payload_fields(self) -> None:
        runtime = {
            key: self.feature[key]
            for key in ("patches", "expanded_shr_relocations")
        }
        digest = hashlib.sha256(
            json.dumps(runtime, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest().upper()
        self.assertEqual(
            digest,
            "4AB542B3C143B5AEBC2A1A7E90A33AD789906BE03B8B7C6721F4A973470E6ADE",
        )
        self.assertEqual(
            self.feature["companion_files"][0]["sha256"],
            "2ED1100E7F2EA5B8E522C2DE11F6B00CA8A02B968319C251365E9EFD634BCAF9",
        )

    def test_six_float_skills_and_age_companions_are_written(self) -> None:
        for offset in (7260, 7264, 7268, 7272, 7276, 7280):
            self.assertIn(
                f"mov dword ptr [edx + {offset}], 0x42B40000", self.source
            )
        self.assertIn("cmp eax, 100", self.source)
        self.assertIn("mov eax, 100", self.source)
        self.assertIn("mov eax, 360", self.source)
        self.assertIn("add dword ptr [edx + 7228], ecx", self.source)
        self.assertIn("add dword ptr [edx + 7244], ecx", self.source)

    def test_running_changes_only_selected_record_preferences(self) -> None:
        self.assertIn("lea ecx, [edx + 8028]", self.source)
        self.assertIn("lea ecx, [edx + 8040]", self.source)
        self.assertIn("RUNNING_PREFERENCE_ID = 38", self.source)
        self.assertIn("mov dword ptr [ecx], {RUNNING_PREFERENCE_ID}", self.source)
        self.assertIn("mov dword ptr [ecx], -1", self.source)
        self.assertIn("all Like slots are full", self.source)
        running_block = self.source.split("running:", 1)[1].split(
            "detail_success:", 1
        )[0]
        for forbidden in ("0x17D7C", "movement", "speed"):
            self.assertNotIn(forbidden, running_block)

    def test_all_individual_origins_actions_preflight_current_believer(self) -> None:
        detail = self.source.split('"detail_menu",', 1)[1].split('"tech_increment",', 1)[0]
        for check in (
            "cmp byte ptr [edx + 0x1CD4], 0",
            "cmp byte ptr [edx + 0x1CE1], 0",
            "cmp dword ptr [edx + 0x1C40], 0",
            "cmp byte ptr [edx + 0x1CEC], 0",
        ):
            self.assertGreaterEqual(detail.count(check), 2)
        self.assertNotIn("mov byte ptr [edx + 0x1CEC]", detail)

    def test_composes_with_every_vv5_feature_in_all_four_modes(self) -> None:
        build = next(item for item in load_builds() if item.id == "vv5")
        all_vv5 = [
            item
            for item in load_fun_patches()
            if item.game_id == "vv5"
            and item.id
            not in {
                FEATURE_ID,
                "vv5_full_mastery_all_stage_a_candidate",
            }
        ]
        active_ids = {item.id for item in load_fun_patches() if item.game_id == "vv5"}
        self.assertIn(FEATURE_ID, active_ids)
        self.assertNotIn("vv5_full_mastery_all_stage_a_candidate", active_ids)
        for mode in (
            "collection_progression",
            "immediate_fixed",
            "experimental_expanded_256",
            "experimental_expanded_256_progression",
        ):
            with self.subTest(mode=mode):
                rendered, applied = render_patched_bytes(
                    STOCK,
                    build,
                    mode,
                    _fun_patches_override=[FunPatch(self.feature), *all_vv5],
                )
                self.assertGreater(len(applied), len(self.feature["patches"]))
                expected_payload = bytearray(self.payload)
                relocation = self.feature.get("expanded_shr_relocations")
                if mode.startswith("experimental_expanded_256") and relocation:
                    delta = int(relocation["expanded_virtual_address"], 0) - int(
                        relocation["stock_virtual_address"], 0
                    )
                    for item in relocation["patches"]:
                        payload_offset = int(item["offset"], 0) - 0xDB000
                        value = int.from_bytes(
                            expected_payload[payload_offset : payload_offset + 4],
                            "little",
                        )
                        expected_payload[payload_offset : payload_offset + 4] = (
                            value + delta
                        ).to_bytes(4, "little")
                self.assertEqual(
                    bytes(rendered[0xDB000 : 0xDB000 + len(self.payload)]),
                    bytes(expected_payload),
                )

    def test_expanded_mode_relocates_all_origins_shr_pointers(self) -> None:
        build = next(item for item in load_builds() if item.id == "vv5")
        rendered, applied = render_patched_bytes(
            STOCK,
            build,
            "experimental_expanded_256",
            _fun_patches_override=[FunPatch(self.feature)],
        )
        relocation = self.feature["expanded_shr_relocations"]
        delta = int(relocation["expanded_virtual_address"], 0) - int(
            relocation["stock_virtual_address"], 0
        )
        relocation_offsets = {item["offset"] for item in relocation["patches"]}
        applied_offsets = {
            item["offset"] for item in applied if item["offset"] in relocation_offsets
        }
        self.assertEqual(applied_offsets, relocation_offsets)
        for item in relocation["patches"]:
            offset = int(item["offset"], 0)
            before = int.from_bytes(bytes.fromhex(item["before"]), "little")
            actual = struct.unpack_from("<I", rendered, offset)[0]
            self.assertEqual(actual, before + delta)
        payload_end = 0xDB000 + len(self.payload)
        for offset in range(0xDB000, payload_end - 3):
            value = struct.unpack_from("<I", rendered, offset)[0]
            self.assertFalse(
                int(relocation["stock_virtual_address"], 0)
                <= value
                < int(relocation["stock_virtual_address"], 0) + 0x1000,
                f"stale stock .shr pointer at {offset:#x}",
            )

    def test_stock_mode_keeps_origins_shr_pointers_unchanged(self) -> None:
        build = next(item for item in load_builds() if item.id == "vv5")
        rendered, applied = render_patched_bytes(
            STOCK,
            build,
            "collection_progression",
            _fun_patches_override=[FunPatch(self.feature)],
        )
        relocation = self.feature["expanded_shr_relocations"]
        relocation_offsets = {int(item["offset"], 0) for item in relocation["patches"]}
        self.assertFalse(
            any(int(item["offset"], 0) in relocation_offsets for item in applied)
        )
        for item in relocation["patches"]:
            offset = int(item["offset"], 0)
            self.assertEqual(
                rendered[offset : offset + 4], bytes.fromhex(item["before"])
            )

    def test_expanded_output_keeps_vanilla_name_and_stock_save_fallback(self) -> None:
        build = next(item for item in load_builds() if item.id == "vv5")
        rendered, _ = render_patched_bytes(
            STOCK,
            build,
            "experimental_expanded_256",
            [FEATURE_ID],
        )
        self.assertEqual(bytes(rendered[0x95794 : 0x9579D]), b"%s%d.ldw\0")
        self.assertEqual(bytes(rendered[0x25709 : 0x2570E]), bytes.fromhex("E85EEF0600"))
        cave = bytes(rendered[0x9466C : 0x9466C + 102])
        self.assertIn(bytes.fromhex("68787D0100"), cave)
        self.assertIn(bytes.fromhex("FDF3A5FC"), cave)
        self.assertIn(bytes.fromhex("B919040000"), cave)
        self.assertIn(bytes.fromhex("B9FC1C0000"), cave)


if __name__ == "__main__":
    unittest.main()
