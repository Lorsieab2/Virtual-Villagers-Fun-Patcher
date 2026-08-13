from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
import unittest
from pathlib import Path

from capstone import CS_ARCH_X86, CS_MODE_32, Cs

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import (  # noqa: E402
    FunPatch,
    PatcherError,
    _remove_feature_bytes,
    load_builds,
    load_fun_patches,
    render_patched_bytes,
    resolve_fun_patch_ids,
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def load_builder():
    path = ROOT / "scripts" / "build_vv3_individual_running_candidate.py"
    spec = importlib.util.spec_from_file_location("vv3_individual_running_builder", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load VV3 individual Running generator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class VV3IndividualGrantRunningCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = load_builder()
        cls.manifest_path = ROOT / "data" / "candidates" / "vv3_individual_grant_running_candidate.json"
        cls.map_path = ROOT / "data" / "candidates" / "vv3_individual_grant_running_candidate_map.json"
        cls.doc_path = ROOT / "docs" / "vv3-individual-running-stage-a-candidate.md"
        cls.raw = json.loads(cls.manifest_path.read_text(encoding="utf-8"))
        cls.artifact = json.loads(cls.map_path.read_text(encoding="utf-8"))
        cls.feature = FunPatch(cls.raw)
        cls.stock = cls.builder.STOCK
        cls.build = next(item for item in load_builds() if item.id == "vv3")
        cls.full_base = FunPatch(
            json.loads(
                (ROOT / "data" / "candidates" / "vv3_origins_full_mastery_base_candidate.json")
                .read_text(encoding="utf-8")
            )
        )
        cls.full_feature = FunPatch(
            json.loads(
                (ROOT / "data" / "candidates" / "vv3_full_mastery_all_candidate.json")
                .read_text(encoding="utf-8")
            )
        )

    def test_canonical_blobs_and_natural_layout(self) -> None:
        helper, strings, string_blob = self.builder._build_helper()
        region, region_map = self.builder._build_owned_region()
        self.assertEqual(len(helper), 0x271)
        self.assertEqual(sha(helper), "B03DCCF47903326E95A192A8458FD504E80B5D592784072D47525C217202B544")
        self.assertEqual(len(string_blob), 0x2E7)
        self.assertEqual(sha(string_blob), "52CB94EFF2FAC50C91B0C4CDF8D3CC973348F5ECE6BC3BAA0B74307FC1ACDC50")
        self.assertEqual(len(region), 0x700)
        self.assertEqual(sha(region), "76339C8FFBE0FF92F3F1EB2CC27A4E0600E33DCC936716DA94BBB0BD5D1AB050")
        self.assertEqual(region[0x271:0x400], b"\0" * (0x400 - 0x271))
        self.assertEqual(region[0x6E7:], b"\0" * 0x19)
        self.assertEqual(region_map["canonical_blob_layout"], {
            "helper_offset": "0x0",
            "helper_length": "0x271",
            "strings_offset": "0x400",
            "strings_length": "0x2E7",
            "tail_offset": "0x6E7",
            "tail_length": "0x19",
        })
        expected = {
            "success": "Running was granted.",
            "already": "This villager already likes Running.\r\nNo tech points have been deducted.",
            "no_empty": "This villager has no empty Like slot.\r\nNo tech points have been deducted.",
            "invalid": "No valid living villager is selected.\r\nNo tech points have been deducted.",
            "selection_changed": "The selection or villager state changed during confirmation.\r\nNo tech points have been deducted.",
            "likes_changed": "The villager Likes changed during confirmation.\r\nNo tech points have been deducted.",
            "insufficient": "Not enough tech points.\r\nNo tech points have been deducted.",
            "cancel": "Grant Running was canceled.\r\nNo tech points have been deducted.",
            "write_failure": "Running could not be verified.\r\nNo tech points have been deducted.",
        }
        for name, value in expected.items():
            start = strings[name] - self.builder.STRINGS_VA
            end = string_blob.index(b"\0", start)
            self.assertEqual(string_blob[start:end].decode("ascii"), value)

    def test_canonical_disassembly_and_nonoverlapping_locals(self) -> None:
        helper, _, _ = self.builder._build_helper()
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        md.detail = True
        instructions = list(md.disasm(helper, self.builder.HELPER_VA))
        self.assertEqual(instructions[0].mnemonic, "cmp")
        self.assertEqual(instructions[0].op_str, "ebx, 2")
        self.assertEqual(instructions[1].mnemonic, "jne")
        self.assertEqual(instructions[1].operands[0].imm, self.builder.NON_COMMAND2_VA)
        frame = next(item for item in instructions if item.mnemonic == "sub" and item.op_str == "esp, 0x1c")
        self.assertEqual(frame.op_str, "esp, 0x1c")
        self.assertEqual(helper.count(b"\xff\x55\xf0"), 2)
        self.assertNotIn(b"\xff\x55\xec", helper)
        self.assertNotIn(b"\xff\x55\xe4", helper)
        self.assertNotIn(b"\xfc\x0f", helper)
        self.assertNotIn(b"\x94\x0e", helper)
        intervals = {
            "message_box": (-0x10, -0x0C),
            "selected_index": (-0x14, -0x10),
            "record": (-0x18, -0x14),
            "first_empty": (-0x1C, -0x18),
            "snapshot0": (-0x20, -0x1C),
            "snapshot1": (-0x24, -0x20),
            "snapshot2": (-0x28, -0x24),
        }
        names = list(intervals)
        for index, left_name in enumerate(names):
            left = intervals[left_name]
            for right_name in names[index + 1 :]:
                right = intervals[right_name]
                self.assertTrue(left[1] <= right[0] or right[1] <= left[0], (left_name, right_name))
        self.assertEqual(self.artifact["stack_frame"]["saved_message_box"], "-0x10")
        self.assertEqual(self.artifact["semantic_guards"]["message_box_pointer"], "[ebp-0x10]")

    def test_exact_two_feature_ranges_and_withdrawn_static_state(self) -> None:
        self.assertFalse(self.raw["enabled"])
        self.assertTrue(self.raw["catalog_hidden"])
        self.assertFalse(self.raw["catalog_enabled"])
        self.assertEqual(self.raw["revocation"]["status"], "withdrawn")
        self.assertIn("Dislikes", self.raw["revocation"]["reason"])
        self.assertEqual(self.raw["supported_modes"], ["collection_progression", "immediate_fixed"])
        self.assertEqual(self.raw["runtime_player_status"], "pending")
        self.assertEqual(len(self.raw["patches"]), 2)
        hook, owned = self.raw["patches"]
        self.assertEqual(hook["before"], "83FB027525")
        self.assertEqual(hook["after"], "E938C02300")
        self.assertEqual(sha(bytes.fromhex(hook["after"])), "DB0F47AADB04629EB6FD5966547F11CF32A7DC445E8D8641621925B76C816DA1")
        self.assertEqual(int(owned["offset"], 0), 0xCB900)
        self.assertEqual(len(bytes.fromhex(owned["after"])), 0x700)
        self.assertEqual(sha(bytes.fromhex(owned["after"])), "76339C8FFBE0FF92F3F1EB2CC27A4E0600E33DCC936716DA94BBB0BD5D1AB050")
        self.assertEqual(self.raw["unsupported_patch_modes"], list(self.builder.EXPANDED_MODES))
        self.assertEqual(self.raw["result_messages"]["success"], "Running was granted.")
        self.assertNotIn("inactive_or_dead", self.raw["result_messages"]["distinct"])
        self.assertEqual(self.raw["result_messages"]["aliases"]["inactive_or_dead"], "invalid_selection")
        self.assertEqual(self.artifact["feature_owned_ranges"][0]["file_offset"], "0xA38C3")
        self.assertEqual(self.artifact["feature_owned_ranges"][1]["file_offset"], "0xCB900")
        self.assertEqual(self.artifact["mutation_accounting"]["feature_owned_range_count"], 2)
        self.assertEqual(self.artifact["mutation_accounting"]["physical_diff_range_count"], 3)
        transaction = self.raw["transaction_contract"]
        self.assertEqual(
            {key: transaction[key] for key in ("command", "price", "action", "repeatable", "ownership", "remove")},
            {
                "command": 2,
                "price": 40_000,
                "action": "Buy",
                "repeatable": True,
                "ownership": None,
                "remove": False,
            },
        )
        self.assertEqual(
            list(transaction)[:6],
            ["command", "price", "action", "repeatable", "ownership", "remove"],
        )

    def test_withdrawn_candidate_is_absent_from_catalog_and_excludes_village_wide(self) -> None:
        patches = load_fun_patches()
        by_id = {patch.id: patch for patch in patches}
        self.assertNotIn("vv3_individual_grant_running_candidate", by_id)
        self.assertIn("vv3_enable_origins_exclusive_features", by_id)
        self.assertIn("vv3_full_mastery_all_stage_a_candidate", by_id)
        self.assertNotIn("vv3_all_villagers_like_running", by_id)
        self.assertIn("vv3_origins_village_wide_upgrades", by_id)
        with self.assertRaisesRegex(PatcherError, "Unknown optional patch"):
            resolve_fun_patch_ids(
                ["vv3_individual_grant_running_candidate"],
                game_id="vv3",
                patches=patches,
            )
        with self.assertRaisesRegex(PatcherError, "Unknown optional patch"):
            resolve_fun_patch_ids(["vv3_all_villagers_like_running"], patches=patches)
        self.assertEqual(self.raw["revocation"]["superseded_by"], "vv3_individual_grant_running_revised_candidate")

    def test_buy_contract_mutations_fail_before_source_read(self) -> None:
        mutations = {
            "command": lambda contract: contract.__setitem__("command", 3),
            "price": lambda contract: contract.__setitem__("price", 40_001),
            "action": lambda contract: contract.__setitem__("action", "buy"),
            "repeatable": lambda contract: contract.__setitem__("repeatable", False),
            "ownership": lambda contract: contract.__setitem__("ownership", "owned"),
            "remove": lambda contract: contract.__setitem__("remove", True),
            "missing_key": lambda contract: contract.pop("remove"),
            "extra_key": lambda contract: contract.__setitem__("unexpected", True),
        }
        missing_source = ROOT / "outputs" / "__c179_missing_vv3_source__.exe"
        self.assertFalse(missing_source.exists())
        for name, mutate in mutations.items():
            for mode in ("collection_progression", "immediate_fixed"):
                for source in (self.stock, missing_source):
                    with self.subTest(mutation=name, mode=mode, source=source.name):
                        raw = copy.deepcopy(self.raw)
                        mutate(raw["transaction_contract"])
                        with self.assertRaisesRegex(
                            PatcherError,
                            "Buy transaction contract",
                        ):
                            render_patched_bytes(
                                source,
                                self.build,
                                mode,
                                _fun_patches_override=[
                                    self.full_base,
                                    self.full_feature,
                                    FunPatch(raw),
                                ],
                            )

    def test_checksum_accounting_has_three_ranges_and_rejects_pin_mutations(self) -> None:
        expected_checksums = {
            "collection_progression": ("E9AC0D00", "93790D00"),
            "immediate_fixed": ("E8EE0C00", "91BB0D00"),
        }
        for mode, (pre_pin, candidate_pin) in expected_checksums.items():
            with self.subTest(mode=mode):
                pre, _ = render_patched_bytes(
                    self.stock, self.build, mode, _fun_patches_override=[self.full_base, self.full_feature]
                )
                rendered, _ = render_patched_bytes(
                    self.stock, self.build, mode, _fun_patches_override=[self.full_base, self.full_feature, self.feature]
                )
                accounting = self.builder._accounted_physical_ranges(pre, rendered, mode)
                self.assertEqual(len(accounting), 3)
                self.assertEqual(len(self.artifact["rendered"][mode]["physical_diff_ranges"]), 3)
                self.assertEqual(len(self.artifact["rendered"][mode]["feature_owned_ranges"]), 2)
                self.assertEqual(bytes(pre[0x160:0x164]).hex().upper(), pre_pin)
                self.assertEqual(bytes(rendered[0x160:0x164]).hex().upper(), candidate_pin)
                accounted = set()
                for item in accounting:
                    start = int(str(item["raw_offset"]), 0)
                    accounted.update(range(start, start + int(item["length"])))
                self.assertEqual(
                    [
                        offset
                        for offset, (left, right) in enumerate(zip(pre, rendered))
                        if left != right and offset not in accounted
                    ],
                    [],
                )
                bad = bytearray(rendered)
                bad[0x160] ^= 1
                with self.assertRaisesRegex(RuntimeError, "PE checksum pin mismatch"):
                    self.builder._accounted_physical_ranges(pre, bad, mode)

    def test_stock_modes_render_and_uninstall_exact(self) -> None:
        for mode, expected in self.builder.PRE_RUNNING_SHA256.items():
            with self.subTest(mode=mode):
                pre, _ = render_patched_bytes(
                    self.stock, self.build, mode, _fun_patches_override=[self.full_base, self.full_feature]
                )
                self.assertEqual(sha(bytes(pre)), expected)
                rendered, _ = render_patched_bytes(
                    self.stock, self.build, mode, _fun_patches_override=[self.full_base, self.full_feature, self.feature]
                )
                self.assertEqual(sha(bytes(rendered)), self.artifact["rendered"][mode]["sha256"])
                removed = bytearray(rendered)
                _remove_feature_bytes(removed, self.feature, mode)
                self.assertEqual(bytes(removed), bytes(pre))
        for mode in self.builder.EXPANDED_MODES:
            with self.subTest(mode=mode):
                with self.assertRaises(PatcherError):
                    render_patched_bytes(
                        self.stock, self.build, mode, _fun_patches_override=[self.full_base, self.full_feature, self.feature]
                    )

    def test_manifest_mutations_fail_closed_before_output(self) -> None:
        stock_before = sha(self.stock.read_bytes())
        for mutate in ("helper_sha256", "strings_sha256", "stack_frame", "owned_after"):
            with self.subTest(mutate=mutate):
                raw = copy.deepcopy(self.raw)
                if mutate == "helper_sha256":
                    raw["patches"][1]["helper_sha256"] = "0" * 64
                elif mutate == "strings_sha256":
                    raw["patches"][1]["strings_sha256"] = "0" * 64
                elif mutate == "stack_frame":
                    raw["owned_region"]["stack_frame"]["saved_message_box"] = "-0x1C"
                else:
                    after = bytearray.fromhex(raw["patches"][1]["after"])
                    after[0] ^= 1
                    raw["patches"][1]["after"] = after.hex().upper()
                with self.assertRaises(PatcherError):
                    render_patched_bytes(
                        self.stock,
                        self.build,
                        "collection_progression",
                        _fun_patches_override=[self.full_base, self.full_feature, FunPatch(raw)],
                    )
        self.assertEqual(sha(self.stock.read_bytes()), stock_before)

    def test_authoritative_metadata_mutations_fail_before_normal_render(self) -> None:
        """Every D170-controlled field is checked before any output mutation."""

        mutations = [
            (
                "candidate_checksum",
                lambda raw: raw["mutation_accounting"]["checksum_range"]["per_mode"]
                ["collection_progression"].__setitem__("candidate", "00000000"),
            ),
            (
                "success",
                lambda raw: raw["result_messages"].__setitem__("success", "WRONG"),
            ),
            (
                "alias",
                lambda raw: raw["result_messages"]["aliases"].__setitem__(
                    "inactive_or_dead", "selection_changed"
                ),
            ),
            (
                "no_charge_suffix",
                lambda raw: raw["result_messages"].__setitem__(
                    "no_charge_suffix", "WRONG"
                ),
            ),
            (
                "invalid_selection_text",
                lambda raw: raw["result_messages"].__setitem__(
                    "invalid_selection_text", "WRONG"
                ),
            ),
            (
                "distinct_results",
                lambda raw: raw["result_messages"]["distinct"].append("inactive_or_dead"),
            ),
            (
                "feature_range_count",
                lambda raw: raw["mutation_accounting"].__setitem__(
                    "feature_owned_range_count", 3
                ),
            ),
            (
                "feature_range_ownership",
                lambda raw: raw["mutation_accounting"]["feature_owned_ranges"][0].__setitem__(
                    "purpose", "foreign"
                ),
            ),
            (
                "physical_range_count",
                lambda raw: raw["mutation_accounting"].__setitem__(
                    "physical_diff_range_count", 2
                ),
            ),
            (
                "checksum_range",
                lambda raw: raw["mutation_accounting"]["checksum_range"].__setitem__(
                    "raw_offset", "0x161"
                ),
            ),
            (
                "checksum_mode_pin",
                lambda raw: raw["mutation_accounting"]["checksum_range"]["per_mode"]
                ["immediate_fixed"].__setitem__("pre", "00000000"),
            ),
            (
                "accounting_rule",
                lambda raw: raw["mutation_accounting"].__setitem__("rule", "WRONG"),
            ),
        ]
        for name, mutate in mutations:
            for mode in ("collection_progression", "immediate_fixed"):
                with self.subTest(mutation=name, mode=mode):
                    raw = copy.deepcopy(self.raw)
                    mutate(raw)
                    stock_before = sha(self.stock.read_bytes())
                    with self.assertRaises(PatcherError):
                        render_patched_bytes(
                            self.stock,
                            self.build,
                            mode,
                            _fun_patches_override=[
                                self.full_base,
                                self.full_feature,
                                FunPatch(raw),
                            ],
                        )
                    self.assertEqual(sha(self.stock.read_bytes()), stock_before)


if __name__ == "__main__":
    unittest.main()
