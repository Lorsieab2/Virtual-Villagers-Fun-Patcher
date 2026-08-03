from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / ".tools" / "capstone"))

import vv_fun_patcher as v  # noqa: E402
from capstone import CS_ARCH_X86, CS_MODE_32, CS_GRP_CALL, CS_GRP_JUMP, Cs  # noqa: E402
from capstone.x86_const import X86_OP_IMM  # noqa: E402


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


class VV3FullHealCandidateTests(unittest.TestCase):
    PARTIAL_FAILURE_DISCLOSURE = (
        "If native writes begin and a later write or postverification fails, earlier "
        "verified health, sickness, or People Cured effects may remain. No tech points "
        "are deducted on that failure, but complete rollback of native side effects is "
        "not claimed."
    )
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest_path = v.VV3_FULL_HEAL_CANDIDATE_PATHS["manifest"]
        cls.map_path = v.VV3_FULL_HEAL_CANDIDATE_PATHS["map"]
        cls.raw = json.loads(cls.manifest_path.read_text(encoding="utf-8"))
        cls.feature = v.FunPatch(cls.raw)
        cls.build = next(item for item in v.load_builds() if item.id == "vv3")
        cls.stock = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Secret City.exe"
        cls.chain = v.resolve_fun_patch_ids(
            [
                "vv3_enable_origins_exclusive_features",
                "vv3_full_mastery_all_stage_a_candidate",
                "vv3_individual_grant_running_candidate",
            ],
            game_id="vv3",
        )
        cls.chain_features = list(v._selected_fun_patches(cls.build, cls.chain))

    def _render(self, mode: str) -> bytearray:
        return v.render_patched_bytes(
            self.stock,
            self.build,
            mode,
            self.chain,
            _fun_patches_override=[*self.chain_features, self.feature],
        )[0]

    def _cave(self) -> bytes:
        return bytes.fromhex(
            self.raw["pe_append_transaction"]["layouts"]["collection_progression"]["append_bytes"]
        )

    def test_disabled_catalog_hidden_and_exact_pins(self) -> None:
        self.assertFalse(self.raw["enabled"])
        self.assertTrue(self.raw["catalog_hidden"])
        self.assertFalse(self.raw["catalog_enabled"])
        self.assertEqual(sha(self.manifest_path.read_bytes()), v.VV3_FULL_HEAL_MANIFEST_SHA256)
        self.assertEqual(sha(self.map_path.read_bytes()), v.VV3_FULL_HEAL_MAP_SHA256)
        self.assertEqual(self.raw["transaction"], v.VV3_FULL_HEAL_TRANSACTION)
        self.assertEqual(self.raw["messages"], v.VV3_FULL_HEAL_MESSAGES)
        self.assertEqual(self.raw["partial_failure_limit"], v.VV3_FULL_HEAL_PARTIAL_FAILURE_DISCLOSURE)
        self.assertEqual(self.raw["rollback_disclosure"], v.VV3_FULL_HEAL_PARTIAL_FAILURE_DISCLOSURE)
        self.assertEqual(self.raw["result_helper"], v.VV3_FULL_HEAL_RESULT_HELPER)
        self.assertEqual(self.raw["health_setter"], v.VV3_FULL_HEAL_HEALTH_SETTER)
        self.assertEqual(self.raw["eligibility"], v.VV3_FULL_HEAL_ELIGIBILITY)
        self.assertEqual(self.raw["sickness"], v.VV3_FULL_HEAL_SICKNESS)
        self.assertEqual(self.raw["base_chain"]["running_composed_parent_helper_sha256"], v.VV3_FULL_HEAL_COMPOSED_PARENT_HELPER_SHA256)
        self.assertEqual(self.raw["base_chain"]["stock_zero_preimage_legacy_range_sha256"], v.VV3_FULL_HEAL_STOCK_ZERO_PREIMAGE_LEGACY_RANGE_SHA256)
        self.assertEqual(self.raw["provenance"], v.VV3_FULL_HEAL_PROVENANCE)
        self.assertEqual(self.raw["provenance"]["design_source_commit"], "64c1266503c49ba1456f6294683a1f6773eba5d6")
        self.assertEqual(self.raw["provenance"]["implementation_base_commit"], "ea6125489a60a3bdbb7f4c72e2619a798d23d5f6")
        self.assertIsNone(self.raw["provenance"]["metadata_commit"])
        self.assertEqual(self.raw["static_acceptance"], v.VV3_FULL_HEAL_STATIC_ACCEPTANCE)
        self.assertEqual(self.raw["base_chain"]["stock_cure_cave_preimage_sha256"], v.VV3_FULL_HEAL_STOCK_CURE_CAVE_PREIMAGE_SHA256)
        self.assertEqual(self.raw["record_zero_resolver"], v.VV3_FULL_HEAL_RECORD_ZERO_RESOLVER)
        self.assertEqual(self.raw["messagebox_resolution"], v.VV3_FULL_HEAL_MESSAGEBOX_RESOLUTION)
        self.assertEqual(self.raw["mutation_accounting"], v.VV3_FULL_HEAL_MUTATION_ACCOUNTING)
        self.assertNotIn(v.VV3_FULL_HEAL_CANDIDATE_ID, {item.id for item in v.load_fun_patches()})

    def test_disabled_catalog_requires_complete_chain_and_excludes_village_wide(self) -> None:
        patches = v.load_fun_patches()
        ids = {item.id for item in patches}
        self.assertNotIn(v.VV3_FULL_HEAL_CANDIDATE_ID, ids)
        self.assertNotIn("vv3_all_villagers_like_running", ids)
        self.assertNotIn("vv3_origins_village_wide_upgrades", ids)
        full_chain = [
            "vv3_enable_origins_exclusive_features",
            "vv3_full_mastery_all_stage_a_candidate",
            "vv3_individual_grant_running_candidate",
            v.VV3_FULL_HEAL_CANDIDATE_ID,
        ]
        with self.assertRaises(v.PatcherError):
            v.resolve_fun_patch_ids(full_chain, game_id="vv3", patches=patches)
        with self.assertRaisesRegex(v.PatcherError, "Grant Running.*Full Mastery"):
            v.resolve_fun_patch_ids(
                ["vv3_individual_grant_running_candidate"], game_id="vv3", patches=patches
            )

    def test_both_stock_modes_emit_hook_and_cave(self) -> None:
        for mode in ("collection_progression", "immediate_fixed"):
            rendered = self._render(mode)
            parent = self._render_without_candidate(mode)
            self.assertEqual(
                sha(bytes(parent[v.VV3_FULL_HEAL_LEGACY_START : v.VV3_FULL_HEAL_LEGACY_END_OFFSET])),
                v.VV3_FULL_HEAL_LEGACY_PRESERVED_RANGE_SHA256,
            )
            self.assertEqual(
                sha(self.stock.read_bytes()[v.VV3_FULL_HEAL_LEGACY_START : v.VV3_FULL_HEAL_LEGACY_END_OFFSET]),
                v.VV3_FULL_HEAL_STOCK_ZERO_PREIMAGE_LEGACY_RANGE_SHA256,
            )
            self.assertEqual(rendered[0xA35EF : 0xA35F6], v.VV3_FULL_HEAL_HOOK_AFTER)
            self.assertEqual(
                sha(bytes(rendered[v.VV3_FULL_HEAL_CAVE_OFFSET_INT : v.VV3_FULL_HEAL_CAVE_OFFSET_INT + v.VV3_FULL_HEAL_CAVE_LENGTH])),
                v.VV3_FULL_HEAL_CAVE_SHA256,
            )
            self.assertEqual(
                bytes(rendered[0x7B664 : 0x7B721]),
                bytes(
                    self._render_without_candidate(mode)[0x7B664 : 0x7B721]
                ),
            )

    def test_both_stock_modes_render_deterministically(self) -> None:
        for mode in ("collection_progression", "immediate_fixed"):
            first = bytes(self._render(mode))
            second = bytes(self._render(mode))
            self.assertEqual(first, second)

    def test_d183_exact_shim_api_width_and_fresh_pool_markers(self) -> None:
        cave = self._cave()
        self.assertIn(v.VV3_FULL_HEAL_NON5_SHIM, cave)
        self.assertNotIn(bytes.fromhex("8B04BD543F4A00"), cave)
        self.assertEqual(cave.count(bytes.fromhex("80BF100F000000")), 3)
        self.assertNotIn(bytes.fromhex("83BF100F00000000"), cave)
        self.assertEqual(cave.count(bytes.fromhex("FF1524C14700")), 1)
        self.assertEqual(cave.count(bytes.fromhex("FF1528C14700")), 2)
        self.assertEqual(cave.count(bytes.fromhex("6A00B910E15900")), 3)
        self.assertNotIn(bytes.fromhex("C745E824E15900"), cave)
        self.assertIn(b"USER32.dll\0", cave)
        self.assertIn(b"MessageBoxA\0", cave)
        self.assertIn(bytes.fromhex("8945F0"), cave)
        self.assertEqual(cave.count(bytes.fromhex("FF80FC040000")), 1)
        self.assertEqual(cave.count(bytes.fromhex("C745D096000000")), 1)
        self.assertEqual(cave.count(bytes.fromhex("FF4DD0")), 1)

    def test_layout_hash_and_internal_control_flow_stay_before_strings(self) -> None:
        cave = self._cave()
        layout = json.loads(self.map_path.read_text(encoding="utf-8"))["section"]["layout"]
        helper_length = layout["helper_length"]
        strings_offset = int(layout["strings_offset"], 0)
        self.assertLess(helper_length, strings_offset)
        self.assertEqual(sha(cave[:helper_length]), layout["helper_sha256"])
        self.assertEqual(sha(cave), layout["region_sha256"])
        self.assertEqual(layout["tail_zero_length"], v.VV3_FULL_HEAL_TAIL_ZERO_LENGTH)
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        md.detail = True
        instructions = list(md.disasm(cave[:helper_length], 0x6E0000))
        self.assertEqual(sum(item.size for item in instructions), helper_length)
        starts = {item.address for item in instructions}
        code_end = 0x6E0000 + strings_offset
        for item in instructions:
            self.assertLessEqual(item.address + item.size, code_end)
            if not (item.group(CS_GRP_CALL) or item.group(CS_GRP_JUMP)):
                continue
            if not item.operands or item.operands[0].type != X86_OP_IMM:
                continue
            target = item.operands[0].imm
            if 0x6E0000 <= target < 0x6E0000 + len(cave):
                self.assertLess(target, code_end)
                self.assertIn(target, starts)
        self.assertEqual(layout["internal_target_offsets"], v.VV3_FULL_HEAL_INTERNAL_TARGET_OFFSETS)
        self.assertEqual(layout["epilogue_offset"], v.VV3_FULL_HEAL_HELPER_EPILOGUE_OFFSET)
        self.assertEqual(layout["instruction_count"], v.VV3_FULL_HEAL_HELPER_INSTRUCTION_COUNT)
        self.assertEqual(len([item for item in instructions if item.group(CS_GRP_CALL) and item.operands and item.operands[0].type == X86_OP_IMM and item.operands[0].imm == 0x4A3400]), 3)
        self.assertEqual(len([item for item in instructions if item.group(CS_GRP_CALL) and item.operands and item.operands[0].type == X86_OP_IMM and item.operands[0].imm == 0x427130]), 1)
        for mode in ("collection_progression", "immediate_fixed"):
            rendered_cave = bytes(self._render(mode)[v.VV3_FULL_HEAL_CAVE_OFFSET_INT : v.VV3_FULL_HEAL_CAVE_OFFSET_INT + v.VV3_FULL_HEAL_CAVE_LENGTH])
            self.assertEqual(rendered_cave, cave)
            rendered_instructions = list(md.disasm(rendered_cave[:helper_length], 0x6E0000))
            self.assertEqual(sum(item.size for item in rendered_instructions), helper_length)

    def test_mutation_counter_is_local_and_sickness_manager_precedes_clear(self) -> None:
        cave = self._cave()
        self.assertEqual(cave.count(bytes.fromhex("C745D096000000")), 1)
        self.assertEqual(cave.count(bytes.fromhex("FF4DD0")), 1)
        self.assertEqual(cave.count(bytes.fromhex("FF80FC040000")), 1)
        clear = bytes.fromhex("C687890E000000")
        clear_at = cave.find(clear)
        self.assertGreater(clear_at, 0)
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        md.detail = True
        getter_targets = []
        for item in md.disasm(cave, 0x6E0000):
            if not item.group(CS_GRP_CALL) or not item.operands:
                continue
            if item.operands[0].type == X86_OP_IMM and item.operands[0].imm == 0x428B60:
                getter_targets.append(item.address - 0x6E0000)
        self.assertTrue(any(offset < clear_at for offset in getter_targets))
        decoded = list(md.disasm(cave, 0x6E0000))
        clear_index = next(i for i, item in enumerate(decoded) if item.address - 0x6E0000 == clear_at)
        self.assertGreaterEqual(clear_index, 3)
        self.assertEqual(decoded[clear_index - 1].mnemonic, "je")
        self.assertEqual(decoded[clear_index - 2].mnemonic, "test")
        self.assertEqual(decoded[clear_index - 3].mnemonic, "call")
        self.assertTrue(
            decoded[clear_index - 3].operands
            and decoded[clear_index - 3].operands[0].type == X86_OP_IMM
            and decoded[clear_index - 3].operands[0].imm == 0x428B60
        )
        self.assertEqual(self.raw["sickness"]["manager_acquired_before_clear"], True)
        self.assertEqual(self.raw["sickness"]["mutation_loop_counter_local"], "[ebp-0x30]")
        self.assertEqual(self.raw["sickness"]["mutation_loop_counter_bound"], 150)
        self.assertTrue(self.raw["sickness"]["manager_null_means_no_sickness_write"])

    def test_model_scans_exactly_150_and_counts_overlap_a_and_b(self) -> None:
        def model(records: list[tuple[int, int, int]]) -> tuple[int, int]:
            self.assertEqual(len(records), 150)
            count_a = count_b = 0
            for active, health, sick in records:
                if active != 0 and health > 0:
                    count_a += sick != 0
                    count_b += 1 <= health <= 99
            return count_a, count_b

        clean = [(1, 100, 0)] * 150
        one_sick = clean.copy()
        one_sick[149] = (1, 100, 1)
        three_sick = clean.copy()
        three_sick[0] = (1, 90, 2)
        three_sick[75] = (1, 100, 1)
        three_sick[149] = (1, 80, 3)
        health_only = clean.copy()
        health_only[149] = (1, 90, 0)
        self.assertEqual(model(clean), (0, 0))
        self.assertEqual(model(one_sick), (1, 0))
        self.assertEqual(model(three_sick), (3, 2))
        self.assertEqual(model(health_only), (0, 1))

    def test_all_reason_strings_and_partial_write_limit_are_present(self) -> None:
        cave = self._cave()
        for text in (
            "Full Heal / Cure All will clear sickness from %u eligible villagers and restore %u partial-health villagers for 30,000 tech points?",
            "Full Heal / Cure All completed: %u sickness clears and %u full-health restores were verified.",
            "Full Heal / Cure All failed after %u sickness clears and %u full-health restores were verified.",
            "No tech points have been deducted.",
        ):
            self.assertIn(text.encode("ascii"), cave)
        self.assertIn("not claimed", self.raw["partial_failure_limit"])
        self.assertEqual(self.raw["partial_failure_limit"], self.PARTIAL_FAILURE_DISCLOSURE)
        self.assertEqual(self.raw["rollback_disclosure"], self.PARTIAL_FAILURE_DISCLOSURE)
        self.assertIn(self.PARTIAL_FAILURE_DISCLOSURE.encode("ascii"), cave)

    def test_partial_write_disclosure_is_exact_and_player_facing(self) -> None:
        self.assertEqual(self.raw["partial_failure_limit"], self.PARTIAL_FAILURE_DISCLOSURE)
        self.assertEqual(self.raw["rollback_disclosure"], self.PARTIAL_FAILURE_DISCLOSURE)
        doc = (ROOT / "docs" / "vv3-full-heal-candidate.md").read_text(encoding="utf-8")
        self.assertIn(self.PARTIAL_FAILURE_DISCLOSURE, doc)
        transparency = (ROOT / "docs" / "transparency-log.md").read_text(encoding="utf-8")
        self.assertIn(self.PARTIAL_FAILURE_DISCLOSURE, transparency)

    def test_map_carries_exact_partial_write_disclosure(self) -> None:
        mapped = json.loads(self.map_path.read_text(encoding="utf-8"))
        self.assertEqual(mapped["partial_failure_limit"], self.PARTIAL_FAILURE_DISCLOSURE)
        self.assertEqual(mapped["rollback_disclosure"], self.PARTIAL_FAILURE_DISCLOSURE)

    def test_rendered_hashes_checksum_and_only_three_physical_ranges(self) -> None:
        for mode in ("collection_progression", "immediate_fixed"):
            parent = bytes(self._render_without_candidate(mode))
            candidate = bytes(self._render(mode))
            accounting = self.raw["mutation_accounting"]
            self.assertEqual(sha(candidate), accounting["rendered_sha256"][mode])
            self.assertEqual(candidate[0x160:0x164].hex().upper(), accounting["checksum_transitions"][mode]["after"])
            self.assertEqual(parent[0x160:0x164].hex().upper(), accounting["checksum_transitions"][mode]["before"])
            owned = [(0xA35EF, 0xA35F6), (0x10E, 0x110), (0x158, 0x15C), (0x2F0, 0x318), (v.VV3_FULL_HEAL_CAVE_OFFSET_INT, v.VV3_FULL_HEAL_CAVE_OFFSET_INT + v.VV3_FULL_HEAL_CAVE_LENGTH), (0x160, 0x164)]
            for offset in range(len(parent)):
                if any(start <= offset < end for start, end in owned):
                    continue
                self.assertEqual(parent[offset], candidate[offset], hex(offset))

    def test_direct_remove_round_trip_restores_exact_parent(self) -> None:
        expected = {
            "collection_progression": "3644A56FE17F843DB67662E4309C3C2B41AE7ADD5FDD60EF2B6789DE2BA15FDC",
            "immediate_fixed": "059230146E8CC36E06E5473AE187D081E337DB90638B227FBA799B9C82B58C1C",
        }
        for mode in expected:
            restored = bytearray(self._render(mode))
            v._remove_feature_bytes(restored, self.feature, mode)
            self.assertEqual(sha(bytes(restored)), expected[mode])

    def test_unknown_source_and_map_corruption_fail_before_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            bad_source = temp_path / "bad.exe"
            source = bytearray(self.stock.read_bytes())
            source[0x200] ^= 0x01
            bad_source.write_bytes(source)
            with self.assertRaises(v.PatcherError):
                v.render_patched_bytes(
                    bad_source,
                    self.build,
                    "collection_progression",
                    self.chain,
                    _fun_patches_override=[*self.chain_features, self.feature],
                )
            bad_manifest = temp_path / "manifest.json"
            bad_map = temp_path / "map.json"
            shutil.copy2(self.manifest_path, bad_manifest)
            mutated_map = dict(json.loads(self.map_path.read_text(encoding="utf-8")))
            mutated_map["section"]["length"] = 1
            bad_map.write_text(json.dumps(mutated_map, indent=2) + "\n", encoding="utf-8")
            with patch.object(v, "VV3_FULL_HEAL_CANDIDATE_PATHS", {"manifest": bad_manifest, "map": bad_map}):
                with self.assertRaises(v.PatcherError):
                    self._render("immediate_fixed")

    def _render_without_candidate(self, mode: str) -> bytearray:
        return v.render_patched_bytes(
            self.stock,
            self.build,
            mode,
            self.chain,
            _fun_patches_override=self.chain_features,
        )[0]

    def test_expanded_rejects_before_candidate_output(self) -> None:
        with self.assertRaises(v.PatcherError):
            self._render("experimental_expanded_256")
        with self.assertRaises(v.PatcherError):
            self._render("experimental_expanded_256_progression")

    def test_manifest_mutation_refuses_before_render(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            bad_manifest = temp_path / "manifest.json"
            bad_map = temp_path / "map.json"
            mutated = dict(self.raw)
            mutated["price"] = 1
            bad_manifest.write_text(json.dumps(mutated, indent=2) + "\n", encoding="utf-8")
            shutil.copy2(self.map_path, bad_map)
            with patch.object(
                v,
                "VV3_FULL_HEAL_CANDIDATE_PATHS",
                {"manifest": bad_manifest, "map": bad_map},
            ):
                with self.assertRaises(v.PatcherError):
                    self._render("collection_progression")

    def _assert_map_mutation_refuses(self, field: str, value: str) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            bad_manifest = temp_path / "manifest.json"
            bad_map = temp_path / "map.json"
            shutil.copy2(self.manifest_path, bad_manifest)
            mutated_map = json.loads(self.map_path.read_text(encoding="utf-8"))
            if field == "legacy_preserved_range":
                mutated_map[field]["sha256"] = value
            else:
                mutated_map[field]["sha256"] = value
            bad_map.write_text(json.dumps(mutated_map, indent=2) + "\n", encoding="utf-8")
            with patch.object(
                v,
                "VV3_FULL_HEAL_CANDIDATE_PATHS",
                {"manifest": bad_manifest, "map": bad_map},
            ):
                with self.assertRaises(v.PatcherError):
                    self._render("collection_progression")

    def test_legacy_preserved_range_mutation_refuses_before_render(self) -> None:
        self._assert_map_mutation_refuses(
            "legacy_preserved_range", v.VV3_FULL_HEAL_STOCK_ZERO_PREIMAGE_LEGACY_RANGE_SHA256
        )

    def test_stock_zero_preimage_legacy_range_mutation_refuses_before_render(self) -> None:
        self._assert_map_mutation_refuses(
            "stock_zero_preimage_legacy_range", v.VV3_FULL_HEAL_LEGACY_PRESERVED_RANGE_SHA256
        )

    def test_provenance_mutation_refuses_before_render(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            bad_manifest = temp_path / "manifest.json"
            bad_map = temp_path / "map.json"
            mutated = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            mutated["provenance"]["implementation_base_commit"] = "0" * 40
            bad_manifest.write_text(json.dumps(mutated, indent=2) + "\n", encoding="utf-8")
            shutil.copy2(self.map_path, bad_map)
            with patch.object(
                v,
                "VV3_FULL_HEAL_CANDIDATE_PATHS",
                {"manifest": bad_manifest, "map": bad_map},
            ):
                with self.assertRaises(v.PatcherError):
                    self._render("immediate_fixed")

    def test_missing_companion_refuses_before_render(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(v, "VV3_FULL_HEAL_DLL_PATH", Path(temp) / "missing.dll"):
                with self.assertRaises(v.PatcherError):
                    self._render("collection_progression")

    def test_corrupt_companion_refuses_before_render(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            corrupt = Path(temp) / "candidate.dll"
            corrupt.write_bytes(b"corrupt companion")
            with patch.object(v, "VV3_FULL_HEAL_DLL_PATH", corrupt):
                with self.assertRaises(v.PatcherError):
                    self._render("immediate_fixed")

    def test_native_and_forbidden_markers(self) -> None:
        cave = self._cave()
        self.assertIn(b"\x6A\xFF\x6A\x64", cave)
        self.assertNotIn(b"\x94\x0E", cave)
        self.assertNotIn(b"\xFC\x0F", cave)
        self.assertNotIn(b"\xA0\x00\x00\x00", cave)
        self.assertIn("full_record+0xE6C", self.raw["health_setter"]["ecx"])
        self.assertEqual(self.raw["health_setter"]["forbidden"], "full_record+0xA0")
        self.assertEqual(self.raw["result_helper"]["va"], "0x4A3400")

    def test_companion_dialog_resources_use_exact_label(self) -> None:
        dll = v.VV3_FULL_HEAL_DLL_PATH.read_bytes()
        self.assertGreaterEqual(dll.count("Full Heal / Cure All".encode("utf-16le")), 2)
        self.assertNotIn("Cure all Villagers".encode("utf-16le"), dll)


if __name__ == "__main__":
    unittest.main()
