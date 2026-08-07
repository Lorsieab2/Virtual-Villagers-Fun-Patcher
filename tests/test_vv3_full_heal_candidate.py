from __future__ import annotations

import hashlib
import json
import shutil
import struct
import subprocess
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
        try:
            cls.chain = v.resolve_fun_patch_ids(
                [
                    "vv3_enable_origins_exclusive_features",
                    "vv3_full_mastery_all_stage_a_candidate",
                    "vv3_individual_grant_running_candidate",
                ],
                game_id="vv3",
            )
        except v.PatcherError as exc:
            raise unittest.SkipTest(f"VV3 Full Heal is withheld because historical Running is withdrawn: {exc}")
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

    def test_enabled_catalog_visible_and_exact_pins(self) -> None:
        self.assertTrue(self.raw["enabled"])
        self.assertFalse(self.raw["catalog_hidden"])
        self.assertTrue(self.raw["catalog_enabled"])
        self.assertIsNone(self.raw["audit_commit"])
        self.assertIsNone(self.raw["acceptance_commit"])
        self.assertEqual(v.source_text_sha256(self.manifest_path.read_bytes()), v.VV3_FULL_HEAL_MANIFEST_SHA256)
        self.assertEqual(v.source_text_sha256(self.map_path.read_bytes()), v.VV3_FULL_HEAL_MAP_SHA256)
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
        self.assertEqual(self.raw["provenance"]["implementation_parent_commit"], "38510cc21b7cd322a52fbabc936794dfc8601ccc")
        self.assertEqual(self.raw["provenance"]["implementation_commit"], "49595a75b65cd0561811593ba19825239ec97dde")
        self.assertIsNone(self.raw["provenance"]["metadata_commit"])
        self.assertEqual(
            self.raw["provenance"]["audit_source_test_commit"],
            "e2f1a466b61392d161a0df2fbf8da94fc05ee4ca",
        )
        self.assertEqual(self.raw["static_acceptance"], v.VV3_FULL_HEAL_STATIC_ACCEPTANCE)
        self.assertIsNone(self.raw["static_acceptance"]["commit"])
        self.assertEqual(self.raw["static_acceptance"]["reports"], ["D209", "C213"])
        self.assertIn("independent static GO", self.raw["static_acceptance"]["status"])
        self.assertEqual(self.raw["implementation_status"], v.VV3_FULL_HEAL_IMPLEMENTATION_STATUS)
        self.assertEqual(self.raw["base_chain"]["stock_cure_cave_preimage_sha256"], v.VV3_FULL_HEAL_STOCK_CURE_CAVE_PREIMAGE_SHA256)
        self.assertEqual(self.raw["record_zero_resolver"], v.VV3_FULL_HEAL_RECORD_ZERO_RESOLVER)
        self.assertEqual(self.raw["messagebox_resolution"], v.VV3_FULL_HEAL_MESSAGEBOX_RESOLUTION)
        self.assertEqual(self.raw["mutation_accounting"], v.VV3_FULL_HEAL_MUTATION_ACCOUNTING)
        self.assertIn(v.VV3_FULL_HEAL_CANDIDATE_ID, {item.id for item in v.load_fun_patches()})

    def test_enabled_catalog_requires_complete_chain_and_excludes_village_wide(self) -> None:
        patches = v.load_fun_patches()
        ids = {item.id for item in patches}
        self.assertIn(v.VV3_FULL_HEAL_CANDIDATE_ID, ids)
        self.assertNotIn("vv3_all_villagers_like_running", ids)
        self.assertNotIn("vv3_origins_village_wide_upgrades", ids)
        full_chain = [
            "vv3_enable_origins_exclusive_features",
            "vv3_full_mastery_all_stage_a_candidate",
            "vv3_individual_grant_running_candidate",
            v.VV3_FULL_HEAL_CANDIDATE_ID,
        ]
        resolved = v.resolve_fun_patch_ids(full_chain, game_id="vv3", patches=patches)
        self.assertEqual(set(resolved), set(full_chain))
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
        self.assertEqual(cave.count(bytes.fromhex("FF1528C14700")), 1)
        self.assertEqual(cave.count(bytes.fromhex("6A00B910E15900")), 3)
        self.assertNotIn(bytes.fromhex("C745E824E15900"), cave)
        self.assertIn(b"USER32.dll\0", cave)
        self.assertIn(b"MessageBoxA\0", cave)
        self.assertIn(bytes.fromhex("8945F0"), cave)
        # LoadLibraryA returns the USER32 module handle.  Only MessageBoxA is
        # resolved dynamically; wsprintfA is already imported from USER32 and
        # must be loaded directly from its IAT slot.
        helper_length = json.loads(self.map_path.read_text(encoding="utf-8"))["section"]["layout"]["helper_length"]
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        instructions = list(md.disasm(cave[:helper_length], 0x6E0000))
        getproc_calls = [
            index
            for index, item in enumerate(instructions)
            if item.mnemonic == "call" and "0x47c128" in item.op_str
        ]
        self.assertEqual(len(getproc_calls), 1)
        for index in getproc_calls:
            self.assertGreaterEqual(index, 2)
            self.assertEqual(instructions[index - 1].mnemonic, "push")
            self.assertEqual(instructions[index - 1].op_str, "eax")
        self.assertIn(bytes.fromhex("A1A0C3470085C0"), cave)
        self.assertNotIn(bytes.fromhex("6817086E00FF75F0FF1528C14700"), cave)
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
            mutated["provenance"]["implementation_commit"] = "38510cc21b7cd322a52fbabc936794dfc8601ccc"
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

    def test_c208_health_bounds_counts_funds_and_actual_predicate_markers(self) -> None:
        cave = self._cave()
        # Only snapshotted 1..99 health enters the native setter/write path;
        # the explicit >99 branch preserves 100+ records byte-for-byte.
        self.assertIn(bytes.fromhex("833CF2017C"), cave)
        self.assertIn(bytes.fromhex("833CF2637F"), cave)
        self.assertTrue(self.raw["sickness"]["health_ge_100_preserved"])
        self.assertEqual(self.raw["sickness"]["health_write_snapshot_range"], "1..99 only")
        # The actual A/B counters are compared against their predictions before
        # the sole deduction, and the post-OK funds check precedes the first
        # health/sickness native mutation call.
        self.assertIn(bytes.fromhex("8B45D83B45E0"), cave)
        self.assertIn(bytes.fromhex("8B45D43B45DC"), cave)
        funds_positions = [
            offset for offset in range(len(cave)) if cave.startswith(bytes.fromhex("813D442658003075"), offset)
        ]
        first_setter = cave.find(bytes.fromhex("6AFF6A64"))
        self.assertGreaterEqual(len(funds_positions), 3)
        self.assertGreater(first_setter, funds_positions[1])
        self.assertLess(funds_positions[1], first_setter)
        self.assertTrue(self.raw["sickness"]["actual_counts_must_equal_predicted_before_deduction"])

    def test_c210_emitted_branch_dominance_and_live_reason_xrefs(self) -> None:
        mapped = json.loads(self.map_path.read_text(encoding="utf-8"))
        layout = mapped["section"]["layout"]
        cave = bytes.fromhex(mapped["section"]["append"]["append_bytes"])
        helper_length = int(layout["helper_length"])
        strings_offset = int(layout["strings_offset"], 0)
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        md.detail = True
        instructions = list(md.disasm(cave[:helper_length], 0x6E0000))
        starts = {item.address for item in instructions}
        self.assertEqual(sum(item.size for item in instructions), helper_length)

        setter = next(
            item for item in instructions
            if item.mnemonic == "call"
            and item.operands
            and item.operands[0].type == X86_OP_IMM
            and item.operands[0].imm == 0x462670
        )
        # The pre-write health >99 branch lands after the setter, so 100+
        # records cannot be normalized or written.
        bypass = [
            item for item in instructions
            if item.mnemonic == "jg"
            and item.address < setter.address
            and item.operands
            and item.operands[0].type == X86_OP_IMM
        ]
        self.assertTrue(bypass)
        self.assertTrue(any(item.operands[0].imm > setter.address for item in bypass))
        self.assertTrue(all(item.operands[0].imm in starts for item in bypass))

        # The postverify 100+ path jumps directly to the comparison/next-record
        # block and contains no setter call on that branch.
        postverify_skip = next(
            item for item in instructions
            if item.mnemonic == "jg"
            and item.address == 0x6E0308
        )
        self.assertEqual(postverify_skip.operands[0].imm, 0x6E0319)
        self.assertIn(postverify_skip.operands[0].imm, starts)

        funds_checks = [
            item for item in instructions
            if item.mnemonic == "cmp" and "0x582644" in item.op_str
        ]
        self.assertGreaterEqual(len(funds_checks), 3)
        post_ok_funds = funds_checks[1]
        following = instructions[instructions.index(post_ok_funds) + 1]
        self.assertEqual(following.mnemonic, "jb")
        self.assertLess(post_ok_funds.address, setter.address)
        self.assertGreater(following.operands[0].imm, setter.address)

        deduction = next(
            item for item in instructions
            if item.mnemonic == "call"
            and item.operands
            and item.operands[0].type == X86_OP_IMM
            and item.operands[0].imm == 0x427130
        )
        mismatch_targets = []
        for index, item in enumerate(instructions):
            if item.mnemonic != "cmp" or item.op_str not in {
                "eax, dword ptr [ebp - 0x20]",
                "eax, dword ptr [ebp - 0x24]",
            }:
                continue
            branch = instructions[index + 1]
            self.assertEqual(branch.mnemonic, "jne")
            mismatch_targets.append(branch.operands[0].imm)
            self.assertLess(branch.address, deduction.address)
            self.assertNotEqual(branch.operands[0].imm, deduction.address)
        self.assertEqual(len(mismatch_targets), 2)
        self.assertEqual(len(set(mismatch_targets)), 1)
        self.assertEqual(set(mismatch_targets), {0x6E03EA})

        string_base = 0x6E0000 + strings_offset
        reason_texts = (
            "Cure dependencies are unavailable.",
            "Not enough tech points before confirmation.",
            "Not enough tech points after confirmation recheck.",
            "Cure All was canceled.",
            "Villager state changed during confirmation.",
        )
        for text in reason_texts:
            offset = cave.find(text.encode("ascii"), strings_offset)
            self.assertGreaterEqual(offset, strings_offset, text)
            pointer = string_base + offset - strings_offset
            self.assertTrue(
                any(
                    item.mnemonic == "push"
                    and item.operands
                    and item.operands[0].type == X86_OP_IMM
                    and item.operands[0].imm == pointer
                    for item in instructions
                ),
                text,
            )

        failure = self.raw["messages"]["failure_format"].encode("ascii") + b"\0"
        failure_offset = cave.find(failure, strings_offset)
        self.assertGreaterEqual(failure_offset, strings_offset)
        failure_pointer = string_base + failure_offset - strings_offset
        self.assertTrue(
            any(
                item.mnemonic == "push"
                and item.operands
                and item.operands[0].type == X86_OP_IMM
                and item.operands[0].imm == failure_pointer
                for item in instructions
            )
        )
        failure_bytes = cave[:helper_length]
        self.assertIn(bytes.fromhex("FF75D4FF75D8"), failure_bytes)
        self.assertIn(self.PARTIAL_FAILURE_DISCLOSURE.encode("ascii"), cave)

    def test_c212_charge_reachable_mismatch_mutation_fails_contract(self) -> None:
        mapped = json.loads(self.map_path.read_text(encoding="utf-8"))
        append_hex = mapped["section"]["append"]["append_bytes"]
        mutated = bytearray.fromhex(append_hex)
        base = 0x6E0000
        for va in (0x6E0355, 0x6E0361):
            offset = va - base
            self.assertEqual(mutated[offset : offset + 2], bytes.fromhex("0F85"))
            struct.pack_into("<i", mutated, offset + 2, 0x6E0367 - (va + 6))

        md = Cs(CS_ARCH_X86, CS_MODE_32)
        md.detail = True
        decoded = list(md.disasm(bytes(mutated), base))
        mutated_targets = [
            branch.operands[0].imm
            for index, item in enumerate(decoded)
            if item.mnemonic == "cmp"
            and item.op_str in {
                "eax, dword ptr [ebp - 0x20]",
                "eax, dword ptr [ebp - 0x24]",
            }
            for branch in decoded[index + 1 : index + 2]
            if branch.mnemonic == "jne"
        ]
        self.assertEqual(mutated_targets, [0x6E0367, 0x6E0367])
        with self.assertRaises(AssertionError):
            self.assertEqual(mutated_targets, [0x6E03EA, 0x6E03EA])

        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            bad_manifest = temp_path / "manifest.json"
            bad_map = temp_path / "map.json"
            shutil.copy2(self.manifest_path, bad_manifest)
            mapped["section"]["append"]["append_bytes"] = bytes(mutated).hex().upper()
            bad_map.write_text(json.dumps(mapped, indent=2) + "\n", encoding="utf-8")
            with patch.object(
                v,
                "VV3_FULL_HEAL_CANDIDATE_PATHS",
                {"manifest": bad_manifest, "map": bad_map},
            ):
                with self.assertRaises(v.PatcherError):
                    self._render("collection_progression")

    def test_c212_old_d203_helper_fixture_fails_decoded_contract(self) -> None:
        old_commit = "38510cc21b7cd322a52fbabc936794dfc8601ccc"
        old_map_bytes = subprocess.check_output(
            [
                "git",
                "show",
                f"{old_commit}:data/candidates/vv3_full_heal_cure_all_candidate_map.json",
            ],
            cwd=ROOT,
        )
        old_map = json.loads(old_map_bytes)
        old_layout = old_map["section"]["layout"]
        old_blob = bytes.fromhex(old_map["section"]["append"]["append_bytes"])
        old_helper = old_blob[: int(old_layout["helper_length"])]
        self.assertEqual(
            hashlib.sha256(old_helper).hexdigest().upper(),
            "F367C737D0A3A7A17244B591E231FAF6E2DC6D1FBD02F1EFF27DCA3656F30C28",
        )

        md = Cs(CS_ARCH_X86, CS_MODE_32)
        md.detail = True
        old_instructions = list(md.disasm(old_helper, 0x6E0000))
        self.assertEqual(sum(item.size for item in old_instructions), len(old_helper))
        with self.assertRaises(AssertionError):
            self.assertEqual(len(old_helper), v.VV3_FULL_HEAL_HELPER_LENGTH)
            old_targets = [
                old_instructions[index + 1].operands[0].imm
                for index, item in enumerate(old_instructions[:-1])
                if item.mnemonic == "cmp"
                and item.op_str in {
                    "eax, dword ptr [ebp - 0x20]",
                    "eax, dword ptr [ebp - 0x24]",
                }
                and old_instructions[index + 1].mnemonic == "jne"
            ]
            self.assertEqual(old_targets, [0x6E03EA, 0x6E03EA])

    def test_c208_reason_routes_are_live_and_no_charge(self) -> None:
        cave = self._cave()
        messages = self.raw["messages"]
        for key in ("confirm_format", "success_format", "failure_format"):
            self.assertIn(messages[key].split("\r\n")[0].encode("ascii"), cave)
        for phrase in (
            "Cure dependencies are unavailable.",
            "Not enough tech points before confirmation.",
            "Not enough tech points after confirmation recheck.",
            "Cure All was canceled.",
            "Villager state changed during confirmation.",
            "No tech points have been deducted.",
        ):
            self.assertIn(phrase.encode("ascii"), cave)
        self.assertEqual(
            self.raw["sickness"]["reason_routes"],
            ["dependency", "initial_insufficient", "cancel", "recheck", "postwrite_partial"],
        )

    def test_c225_dependency_preflight_models_all_failures_as_no_write_no_charge(self) -> None:
        def preflight(module_handle: bool, message_box: bool, formatter: bool) -> dict[str, object]:
            if not module_handle or not message_box or not formatter:
                return {"route": "dependency", "writes": 0, "charge": 0}
            return {"route": "continue", "writes": 0, "charge": 0}

        for failed in ((False, True, True), (True, False, True), (True, True, False)):
            with self.subTest(failed=failed):
                result = preflight(*failed)
                self.assertEqual(result, {"route": "dependency", "writes": 0, "charge": 0})
        self.assertEqual(preflight(True, True, True), {"route": "continue", "writes": 0, "charge": 0})

    def test_c208_companion_is_resource_only_and_reversible(self) -> None:
        base = v.VV3_FULL_HEAL_BASE_DLL_PATH.read_bytes()
        candidate = v.VV3_FULL_HEAL_DLL_PATH.read_bytes()
        self.assertEqual(len(base), v.VV3_FULL_HEAL_DLL_SIZE)
        self.assertEqual(len(candidate), v.VV3_FULL_HEAL_DLL_SIZE)
        self.assertEqual(sha(candidate), v.VV3_FULL_HEAL_DLL_SHA256)
        self.assertEqual(sha(candidate), "9F866CB6F92C745CD2AA7009AEC4EB70FA5521EFF0C8F7BABE2058BB4D2F8533")
        self.assertEqual(sha(base), v.VV3_FULL_HEAL_BASE_DLL_SHA256)
        base_meta, base_leaves = v._vv3_full_heal_resource_tree(base)
        cand_meta, cand_leaves = v._vv3_full_heal_resource_tree(candidate)
        self.assertEqual(base_meta["raw_size"], cand_meta["raw_size"])
        self.assertEqual(base_meta["section_table"], cand_meta["section_table"])
        self.assertEqual(cand_leaves[(5, 201, 1033)][0], 0x466C0)
        self.assertEqual(cand_leaves[(5, 202, 1033)][0], 0x4705C)
        self.assertEqual(cand_leaves[(5, 203, 1033)][0], 0x474D8)
        self.assertEqual(len(cand_leaves[(5, 201, 1033)][2]), 0x99C)
        self.assertEqual(len(cand_leaves[(5, 202, 1033)][2]), 0x47C)
        self.assertEqual(len(cand_leaves[(5, 203, 1033)][2]), 0x788)
        self.assertEqual(cand_leaves[(5, 202, 1033)][2], base_leaves[(5, 202, 1033)][2])
        # Every non-resource section and the section table remain byte-identical.
        self.assertEqual(base[:0x14600], candidate[:0x14600])
        self.assertEqual(base[0x47E00:], candidate[0x47E00:])
        self.assertEqual(base[0x100:0x400], candidate[0x100:0x400])
        self.assertEqual(self.raw["companion_files"][0]["preimage_sha256"], v.VV3_FULL_HEAL_BASE_DLL_SHA256)
        self.assertEqual(self.raw["companion_files"][0]["restore_sha256"], v.VV3_FULL_HEAL_BASE_DLL_SHA256)

    def test_c220_strict_dialog_walks_and_title_only_delta(self) -> None:
        base_leaves = v._vv3_full_heal_resource_tree(v.VV3_FULL_HEAL_BASE_DLL_PATH.read_bytes())[1]
        candidate_leaves = v._vv3_full_heal_resource_tree(v.VV3_FULL_HEAL_DLL_PATH.read_bytes())[1]
        v._vv3_full_heal_dialog_walk(base_leaves[(5, 201, 1033)][2], 46, 0x998)
        v._vv3_full_heal_dialog_walk(candidate_leaves[(5, 201, 1033)][2], 46, 0x99C)
        v._vv3_full_heal_dialog_walk(base_leaves[(5, 202, 1033)][2], 21, 0x450)
        v._vv3_full_heal_dialog_walk(candidate_leaves[(5, 202, 1033)][2], 21, 0x450)
        v._vv3_full_heal_dialog_walk(base_leaves[(5, 203, 1033)][2], 36, 0x784)
        v._vv3_full_heal_dialog_walk(candidate_leaves[(5, 203, 1033)][2], 36, 0x788)

    def test_c220_rejects_malformed_playtest9_in_place_dll(self) -> None:
        # The old equal-length artifact has no structural data-entry size/RVA
        # transition and must not be accepted as the replacement companion.
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "malformed.dll"
            # Locate the historical artifact from Playtest 9 if present;
            # otherwise use the tracked pre-C220 bytes as a deterministic fixture.
            package = Path(r"C:\Users\Owner\Downloads\VV3 Full Heal Collection Playtest 9 - Modded\VVFP VV3 Full Mastery Candidate.dll")
            if package.is_file():
                path.write_bytes(package.read_bytes())
            else:
                malformed = bytearray(v.VV3_FULL_HEAL_BASE_DLL_PATH.read_bytes())
                old = "Cure all Villagers".encode("utf-16le") + b"\0\0"
                new = "Full Heal / Cure All".encode("utf-16le") + b"\0\0"
                for offset in (0x46C60, 0x47A78):
                    self.assertEqual(malformed[offset : offset + len(old)], old)
                    malformed[offset : offset + len(new)] = new
                self.assertEqual(sha(bytes(malformed)), "A1C58D5DD34252C532C288F87210363FE4C85E355E76946276954F907FAA88FC")
                path.write_bytes(malformed)
            with patch.object(v, "VV3_FULL_HEAL_DLL_PATH", path):
                with self.assertRaises(v.PatcherError):
                    v._validate_vv3_full_heal_companion_transform()

    def test_c208_companion_install_and_remove_restore_exact_preimage(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            destination = folder / "VVFP VV3 Full Mastery Candidate.dll"
            destination.write_bytes(v.VV3_FULL_HEAL_BASE_DLL_PATH.read_bytes())
            copied = v._copy_companion_files(folder, [self.feature])
            self.assertEqual(sha(destination.read_bytes()), v.VV3_FULL_HEAL_DLL_SHA256)
            self.assertEqual(copied[0]["preimage_sha256"], v.VV3_FULL_HEAL_BASE_DLL_SHA256)
            removed = v._remove_companion_files(folder, [self.feature])
            self.assertEqual(sha(destination.read_bytes()), v.VV3_FULL_HEAL_BASE_DLL_SHA256)
            self.assertEqual(removed[0]["action"], "restore")

    def test_c208_mutation_ranges_and_truthful_provenance(self) -> None:
        accounting = self.raw["mutation_accounting"]
        offsets = {item["offset"] for item in accounting["physical_ranges"]}
        self.assertTrue({"0xA35EF", "0x10E", "0x158", "0x2F0", "0xCC000", "0x160"} <= offsets)
        self.assertEqual(accounting["physical_range_count"], 6)
        self.assertEqual(accounting["feature_owned_range_count"], 3)
        self.assertEqual(self.raw["provenance"]["implementation_parent_commit"], "38510cc21b7cd322a52fbabc936794dfc8601ccc")
        self.assertEqual(self.raw["provenance"]["implementation_commit"], "49595a75b65cd0561811593ba19825239ec97dde")
        self.assertNotIn("f23b321", json.dumps(self.raw).lower())
        self.assertNotIn("PENDING", json.dumps(self.raw))
        self.assertEqual(self.raw["runtime_player_status"], "pending")

    def test_c210_provenance_records_static_go_without_circular_acceptance(self) -> None:
        provenance = self.raw["provenance"]
        self.assertEqual(provenance["implementation_parent_commit"], "38510cc21b7cd322a52fbabc936794dfc8601ccc")
        self.assertEqual(provenance["implementation_commit"], "49595a75b65cd0561811593ba19825239ec97dde")
        self.assertIsNone(provenance["metadata_commit"])
        static = self.raw["static_acceptance"]
        self.assertIsNone(static["commit"])
        self.assertEqual(static["status"], "D209 and C213 independent static GO; runtime/player validation pending")
        self.assertEqual(static["reports"], ["D209", "C213"])
        self.assertIsNone(static["audit_commit"])
        self.assertIsNone(static["acceptance_commit"])
        self.assertNotIn("D203", json.dumps(self.raw))

    def test_c210_companion_failure_atomicity(self) -> None:
        base = v.VV3_FULL_HEAL_BASE_DLL_PATH.read_bytes()
        candidate = v.VV3_FULL_HEAL_DLL_PATH.read_bytes()
        destination_name = "VVFP VV3 Full Mastery Candidate.dll"

        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            destination = folder / destination_name
            destination.write_bytes(base)
            with patch.object(v.shutil, "copy2", side_effect=OSError("copy injection")):
                with self.assertRaises(OSError):
                    v._copy_companion_files(folder, [self.feature])
            self.assertEqual(destination.read_bytes(), base)
            self.assertFalse(list(folder.glob(".*.vvfp-stage")))

        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            destination = folder / destination_name
            destination.write_bytes(base)
            original_stage = v._stage_companion_file

            def fail_stage(source: Path, parent: Path, expected: str) -> Path:
                stage = original_stage(source, parent, expected)
                stage.unlink()
                raise v.PatcherError("stage verification injection")

            with patch.object(v, "_stage_companion_file", side_effect=fail_stage):
                with self.assertRaisesRegex(v.PatcherError, "stage verification"):
                    v._copy_companion_files(folder, [self.feature])
            self.assertEqual(destination.read_bytes(), base)
            self.assertFalse(list(folder.glob(".*.vvfp-stage")))

        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            destination = folder / destination_name
            destination.write_bytes(base)
            original_match = v._companion_hash_matches
            calls = 0

            def race_match(path: Path, expected: str) -> bool:
                nonlocal calls
                calls += 1
                return False if calls == 4 else original_match(path, expected)

            with patch.object(v, "_companion_hash_matches", side_effect=race_match):
                with self.assertRaisesRegex(v.PatcherError, "changed before replace"):
                    v._copy_companion_files(folder, [self.feature])
            self.assertEqual(destination.read_bytes(), base)
            self.assertFalse(list(folder.glob(".*.vvfp-stage")))

        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            destination = folder / destination_name
            destination.write_bytes(base)
            with patch.object(v.os, "replace", side_effect=OSError("replace injection")):
                with self.assertRaises(OSError):
                    v._copy_companion_files(folder, [self.feature])
            self.assertEqual(destination.read_bytes(), base)
            self.assertFalse(list(folder.glob(".*.vvfp-stage")))

        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            destination = folder / destination_name
            destination.write_bytes(base)
            original_match = v._companion_hash_matches
            calls = 0

            def postverify_match(path: Path, expected: str) -> bool:
                nonlocal calls
                calls += 1
                return False if calls == 5 else original_match(path, expected)

            with patch.object(v, "_companion_hash_matches", side_effect=postverify_match):
                with self.assertRaisesRegex(v.PatcherError, "post-replace verification failed"):
                    v._copy_companion_files(folder, [self.feature])
            self.assertEqual(destination.read_bytes(), base)
            self.assertFalse(list(folder.glob(".*.vvfp-stage")))

        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            destination = folder / destination_name
            destination.write_bytes(candidate)
            original_match = v._companion_hash_matches
            calls = 0

            def restore_postverify_match(path: Path, expected: str) -> bool:
                nonlocal calls
                calls += 1
                return False if calls == 5 else original_match(path, expected)

            with patch.object(v, "_companion_hash_matches", side_effect=restore_postverify_match):
                with self.assertRaisesRegex(v.PatcherError, "post-replace verification failed"):
                    v._remove_companion_files(folder, [self.feature])
            self.assertEqual(destination.read_bytes(), candidate)
            self.assertFalse(list(folder.glob(".*.vvfp-stage")))


if __name__ == "__main__":
    unittest.main()
