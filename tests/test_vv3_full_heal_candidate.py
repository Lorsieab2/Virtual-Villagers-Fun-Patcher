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

    def test_disabled_hidden_and_exact_pins(self) -> None:
        self.assertFalse(self.raw["enabled"])
        self.assertTrue(self.raw["catalog_hidden"])
        self.assertFalse(self.raw["catalog_enabled"])
        self.assertEqual(sha(self.manifest_path.read_bytes()), v.VV3_FULL_HEAL_MANIFEST_SHA256)
        self.assertEqual(sha(self.map_path.read_bytes()), v.VV3_FULL_HEAL_MAP_SHA256)
        self.assertEqual(self.raw["transaction"], v.VV3_FULL_HEAL_TRANSACTION)
        self.assertEqual(self.raw["messages"], v.VV3_FULL_HEAL_MESSAGES)
        self.assertEqual(self.raw["result_helper"], v.VV3_FULL_HEAL_RESULT_HELPER)
        self.assertEqual(self.raw["health_setter"], v.VV3_FULL_HEAL_HEALTH_SETTER)
        self.assertEqual(self.raw["eligibility"], v.VV3_FULL_HEAL_ELIGIBILITY)
        self.assertEqual(self.raw["sickness"], v.VV3_FULL_HEAL_SICKNESS)
        self.assertEqual(self.raw["base_chain"]["running_composed_parent_helper_sha256"], v.VV3_FULL_HEAL_COMPOSED_PARENT_HELPER_SHA256)
        self.assertEqual(self.raw["base_chain"]["stock_cure_cave_preimage_sha256"], v.VV3_FULL_HEAL_STOCK_CURE_CAVE_PREIMAGE_SHA256)
        self.assertEqual(self.raw["record_zero_resolver"], v.VV3_FULL_HEAL_RECORD_ZERO_RESOLVER)
        self.assertEqual(self.raw["messagebox_resolution"], v.VV3_FULL_HEAL_MESSAGEBOX_RESOLUTION)
        self.assertEqual(self.raw["mutation_accounting"], v.VV3_FULL_HEAL_MUTATION_ACCOUNTING)
        self.assertNotIn(v.VV3_FULL_HEAL_CANDIDATE_ID, {item.id for item in v.load_fun_patches()})

    def test_both_stock_modes_emit_hook_and_cave(self) -> None:
        for mode in ("collection_progression", "immediate_fixed"):
            rendered = self._render(mode)
            self.assertEqual(rendered[0xA35EF : 0xA35F6], v.VV3_FULL_HEAL_HOOK_AFTER)
            self.assertEqual(
                sha(bytes(rendered[0x7B721 : 0x7B721 + v.VV3_FULL_HEAL_CAVE_LENGTH])),
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
        cave = bytes.fromhex(self.raw["patches"][1]["after"])
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
        self.assertEqual(cave.count(bytes.fromhex("FF80FC040000")), 1)
        self.assertEqual(cave.count(bytes.fromhex("C745D896000000")), 1)
        self.assertEqual(cave.count(bytes.fromhex("FF4DD8")), 1)

    def test_layout_hash_and_internal_control_flow_stay_before_strings(self) -> None:
        cave = bytes.fromhex(self.raw["patches"][1]["after"])
        layout = self.raw["patches"][1]["layout"]
        helper_length = layout["helper_length"]
        strings_offset = int(layout["strings_offset"], 0)
        self.assertLess(helper_length, strings_offset)
        self.assertEqual(sha(cave[:helper_length]), layout["helper_sha256"])
        self.assertEqual(sha(cave), layout["region_sha256"])
        self.assertEqual(layout["tail_zero_length"], v.VV3_FULL_HEAL_TAIL_ZERO_LENGTH)
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        md.detail = True
        instructions = list(md.disasm(cave[:helper_length], 0x47B721))
        self.assertEqual(sum(item.size for item in instructions), helper_length)
        starts = {item.address for item in instructions}
        code_end = 0x47B721 + strings_offset
        for item in instructions:
            self.assertLessEqual(item.address + item.size, code_end)
            if not (item.group(CS_GRP_CALL) or item.group(CS_GRP_JUMP)):
                continue
            if not item.operands or item.operands[0].type != X86_OP_IMM:
                continue
            target = item.operands[0].imm
            if 0x47B721 <= target < 0x47B721 + len(cave):
                self.assertLess(target, code_end)
                self.assertIn(target, starts)
        self.assertEqual(layout["internal_target_offsets"], v.VV3_FULL_HEAL_INTERNAL_TARGET_OFFSETS)
        self.assertEqual(layout["epilogue_offset"], v.VV3_FULL_HEAL_HELPER_EPILOGUE_OFFSET)
        self.assertEqual(layout["instruction_count"], v.VV3_FULL_HEAL_HELPER_INSTRUCTION_COUNT)
        self.assertEqual(len([item for item in instructions if item.group(CS_GRP_CALL) and item.operands and item.operands[0].type == X86_OP_IMM and item.operands[0].imm == 0x4A3400]), 2)
        self.assertEqual(len([item for item in instructions if item.group(CS_GRP_CALL) and item.operands and item.operands[0].type == X86_OP_IMM and item.operands[0].imm == 0x427130]), 1)
        for mode in ("collection_progression", "immediate_fixed"):
            rendered_cave = bytes(self._render(mode)[0x7B721 : 0x7B721 + v.VV3_FULL_HEAL_CAVE_LENGTH])
            self.assertEqual(rendered_cave, cave)
            rendered_instructions = list(md.disasm(rendered_cave[:helper_length], 0x47B721))
            self.assertEqual(sum(item.size for item in rendered_instructions), helper_length)

    def test_mutation_counter_is_local_and_sickness_manager_precedes_clear(self) -> None:
        cave = bytes.fromhex(self.raw["patches"][1]["after"])
        self.assertEqual(cave.count(bytes.fromhex("C745D896000000")), 1)
        self.assertEqual(cave.count(bytes.fromhex("FF4DD8")), 1)
        self.assertEqual(cave.count(bytes.fromhex("FF80FC040000")), 1)
        clear = bytes.fromhex("C687890E000000")
        clear_at = cave.find(clear)
        self.assertGreater(clear_at, 0)
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        md.detail = True
        getter_targets = []
        for item in md.disasm(cave, 0x47B721):
            if not item.group(CS_GRP_CALL) or not item.operands:
                continue
            if item.operands[0].type == X86_OP_IMM and item.operands[0].imm == 0x428B60:
                getter_targets.append(item.address - 0x47B721)
        self.assertTrue(any(offset < clear_at for offset in getter_targets))
        decoded = list(md.disasm(cave, 0x47B721))
        clear_index = next(i for i, item in enumerate(decoded) if item.address - 0x47B721 == clear_at)
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
        self.assertEqual(self.raw["sickness"]["mutation_loop_counter_local"], "[ebp-0x28]")
        self.assertEqual(self.raw["sickness"]["mutation_loop_counter_bound"], 150)
        self.assertTrue(self.raw["sickness"]["manager_null_means_no_sickness_write"])

    def test_model_scans_exactly_150_and_counts_sick_records(self) -> None:
        def model(records: list[tuple[int, int, int]]) -> tuple[int, int, int]:
            self.assertEqual(len(records), 150)
            snapshot = []
            for active, health, sick in records:
                if active != 0 and health > 0:
                    snapshot.append((health, sick))
                else:
                    snapshot.append((0, 0))
            changed = [item for item in snapshot if item != (0, 0) and item != (100, 0)]
            sick_changes = sum(1 for health, sick in changed if sick != 0)
            return len(snapshot), len(changed), sick_changes

        clean = [(1, 100, 0)] * 150
        one_sick = clean.copy()
        one_sick[149] = (1, 100, 1)
        three_sick = clean.copy()
        three_sick[0] = (1, 90, 2)
        three_sick[75] = (1, 100, 1)
        three_sick[149] = (1, 80, 3)
        health_only = clean.copy()
        health_only[149] = (1, 90, 0)
        self.assertEqual(model(clean), (150, 0, 0))
        self.assertEqual(model(one_sick), (150, 1, 1))
        self.assertEqual(model(three_sick), (150, 3, 3))
        self.assertEqual(model(health_only), (150, 1, 0))

    def test_all_reason_strings_and_partial_write_limit_are_present(self) -> None:
        cave = bytes.fromhex(self.raw["patches"][1]["after"])
        for text in (
            "All eligible villagers are already healthy and free of sickness.",
            "No valid living non-skeleton villagers are available.",
            "Not enough tech points.",
            "Cure All was canceled.",
            "Villager state changed during confirmation.",
            "Cure verification failed; some native changes may already have occurred.",
            "Cure dependencies are unavailable.",
            "Full Heal was granted to all eligible villagers.",
            "No tech points have been deducted.",
        ):
            self.assertIn(text.encode("ascii"), cave)
        self.assertIn("rollback is not claimed", self.raw["partial_failure_limit"])

    def test_rendered_hashes_checksum_and_only_three_physical_ranges(self) -> None:
        for mode in ("collection_progression", "immediate_fixed"):
            parent = bytes(self._render_without_candidate(mode))
            candidate = bytes(self._render(mode))
            accounting = self.raw["mutation_accounting"]
            self.assertEqual(sha(candidate), accounting["rendered_sha256"][mode])
            self.assertEqual(candidate[0x160:0x164].hex().upper(), accounting["checksum_transitions"][mode]["after"])
            self.assertEqual(parent[0x160:0x164].hex().upper(), accounting["checksum_transitions"][mode]["before"])
            owned = [(0xA35EF, 0xA35F6), (0x7B721, 0x7B721 + v.VV3_FULL_HEAL_CAVE_LENGTH), (0x160, 0x164)]
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
            mutated_map["cave"]["length"] = 1
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
        cave = bytes.fromhex(self.raw["patches"][1]["after"])
        self.assertIn(b"\x6A\xFF\x6A\x64", cave)
        self.assertNotIn(b"\x94\x0E", cave)
        self.assertNotIn(b"\xFC\x0F", cave)
        self.assertNotIn(b"\xA0\x00\x00\x00", cave)
        self.assertIn("full_record+0xE6C", self.raw["health_setter"]["ecx"])
        self.assertEqual(self.raw["health_setter"]["forbidden"], "full_record+0xA0")
        self.assertEqual(self.raw["result_helper"]["va"], "0x4A3400")


if __name__ == "__main__":
    unittest.main()
