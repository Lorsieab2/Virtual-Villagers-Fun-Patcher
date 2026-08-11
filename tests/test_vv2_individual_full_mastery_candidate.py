from __future__ import annotations

import hashlib
import importlib.util
import json
import struct
import sys
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch as mock_patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / ".tools" / "capstone-runtime"))

from capstone import CS_ARCH_X86, CS_MODE_32, Cs  # noqa: E402
from capstone.x86_const import X86_OP_IMM  # noqa: E402
import vv_fun_patcher as patcher  # noqa: E402
from vv_fun_patcher import FunPatch, PatcherError, load_builds, load_fun_patches, render_patched_bytes  # noqa: E402


STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Lost Children.exe"
MANIFEST = ROOT / "data" / "candidates" / "vv2_individual_full_mastery_candidate.json"
MAP = ROOT / "data" / "candidates" / "vv2_individual_full_mastery_candidate_map.json"
GENERATOR = ROOT / "scripts" / "build_vv2_individual_full_mastery_candidate.py"
PARENT_MANIFEST = ROOT / "data" / "candidates" / "vv2_full_mastery_all_candidate.json"
PARENT_DLL = ROOT / "data" / "candidates" / "VVFP VV2 Full Mastery Candidate.dll"
MODES = ("collection_progression", "immediate_fixed")
EXPANDED = ("experimental_expanded_256", "experimental_expanded_256_progression")
SKILLS = ("farming", "building", "research", "healing", "parenting")


def sha(payload: bytes | bytearray) -> str:
    return hashlib.sha256(payload).hexdigest().upper()


def load_generator():
    spec = importlib.util.spec_from_file_location("vv2_individual_mastery_builder", GENERATOR)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def transaction_model(
    record: dict[str, object],
    balance: int,
    confirm: int,
    *,
    after_confirm: dict[str, object] | None = None,
    after_writes_valid: bool = True,
    after_evaluator_valid: bool = True,
) -> tuple[str, int, int]:
    """Small behavioral oracle for the emitted transaction gates."""
    if not record["active"] or int(record["health"]) <= 0 or record["totem"]:
        return "invalid", balance, 0
    skills = record["skills"]
    assert isinstance(skills, dict)
    if any(int(skills[name]) < 0 or int(skills[name]) > 100 for name in SKILLS):
        return "invalid", balance, 0
    changed = sum(int(skills[name]) != 100 for name in SKILLS)
    if changed == 0:
        return "noop", balance, 0
    if balance < 100_000:
        return "insufficient", balance, 0
    if confirm != 1:
        return "cancel", balance, 0
    if after_confirm is not None and after_confirm != record:
        return "race", balance, 0
    for name in SKILLS:
        if int(skills[name]) != 100:
            skills[name] = 100
    if not after_writes_valid or not after_evaluator_valid:
        return "failure", balance, changed
    return "committed", balance - 100_000, changed


class VV2IndividualFullMasteryCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.map = json.loads(MAP.read_text(encoding="utf-8"))
        cls.parent_raw = json.loads(PARENT_MANIFEST.read_text(encoding="utf-8"))
        cls.feature = FunPatch(cls.raw)
        cls.parent = FunPatch(cls.parent_raw)
        cls.build = next(item for item in load_builds() if item.id == "vv2")
        cls.patches = {int(item["offset"], 0): item for item in cls.raw["patches"]}
        cls.helper = bytes.fromhex(cls.patches[0xB2300]["after"])
        disassembler = Cs(CS_ARCH_X86, CS_MODE_32)
        disassembler.detail = True
        cls.instructions = list(disassembler.disasm(cls.helper, 0x4B4300))

    def test_public_catalog_route_is_separate_and_dependency_ordered(self) -> None:
        self.assertEqual(self.raw["id"], "vv2_individual_full_mastery_candidate")
        self.assertTrue(self.raw["enabled"])
        self.assertFalse(self.raw["catalog_hidden"])
        self.assertTrue(self.raw["catalog_enabled"])
        self.assertEqual(self.raw["dependencies"], ["vv2_full_mastery_all_stage_a_candidate"])
        self.assertEqual(self.raw["companion_files"], [])
        loaded = {item.id: item for item in load_fun_patches()}
        self.assertIn(self.raw["id"], loaded)
        self.assertNotIn("vv2_enable_origins_exclusive_features", loaded)
        self.assertEqual(
            patcher.resolve_fun_patch_ids(
                ["vv2_full_mastery_all_stage_a_candidate", self.raw["id"]],
                game_id="vv2",
            ),
            ["vv2_full_mastery_all_stage_a_candidate", self.raw["id"]],
        )
        with self.assertRaisesRegex(PatcherError, "requires prerequisite"):
            patcher.resolve_fun_patch_ids([self.raw["id"]], game_id="vv2")

    def test_generator_reproduces_manifest_and_map_without_writing(self) -> None:
        module = load_generator()
        manifest, mapping = module.build_manifest()
        self.assertEqual(manifest, self.raw)
        self.assertEqual(mapping, self.map)

    def test_parent_artifacts_and_certified_village_wide_metadata_are_unchanged(self) -> None:
        self.assertEqual(
            patcher.source_text_sha256(PARENT_MANIFEST.read_bytes()),
            patcher.VV2_FULL_MASTERY_MANIFEST_SHA256,
        )
        self.assertEqual(sha(PARENT_DLL.read_bytes()), patcher.VV2_FULL_MASTERY_CERTIFIED_SHA256["dll"])
        self.assertEqual(
            self.raw["parent_chain"]["parent_static_acceptance_sha256"],
            {
                mode: self.parent_raw["static_acceptance"]["rendered_candidates"][mode]["candidate_sha256"]
                for mode in MODES
            },
        )
        self.assertEqual(
            [(item["offset"], item["before"], item["after"]) for item in self.parent_raw["patches"]],
            [
                ("0x435EF", "8B4C24205F", "E94CFA0600"),
                ("0x437C0", "837C240408", "E93BF80600"),
            ],
        )

    def test_detail_hooks_use_proved_alignment_and_collision_guard(self) -> None:
        self.assertEqual(self.patches[0x67624]["before"], "8B4C242088")
        self.assertEqual(self.patches[0x67624]["after"], "E917CC0400")
        self.assertEqual(self.patches[0x67720]["before"], "837C240408")
        self.assertEqual(self.patches[0x67720]["after"], "E9DBCA0400")
        handler = bytes.fromhex(self.patches[0xB2200]["after"])
        self.assertTrue(handler.startswith(bytes.fromhex("837C2404087511837C240806750A")))
        self.assertTrue(handler.endswith(bytes.fromhex("837C240408E90335FBFF")))
        constructor = bytes.fromhex(self.patches[0xB2240]["after"])
        # The thiscall arguments are pushed right-to-left: emitted 563 then
        # 140 therefore decodes to formal X=140, Y=563.
        self.assertIn(bytes.fromhex("6A00566833020000688C00000068E86347006A06"), constructor)
        disassembler = Cs(CS_ARCH_X86, CS_MODE_32)
        disassembler.detail = True
        instructions = list(disassembler.disasm(constructor, 0x4B4240))
        create_index = next(
            index
            for index, insn in enumerate(instructions)
            if insn.mnemonic == "call"
            and insn.operands[0].type == X86_OP_IMM
            and insn.operands[0].imm == 0x4019D0
        )
        pushed_immediates = [
            insn.operands[0].imm
            for insn in instructions[create_index - 8:create_index]
            if insn.mnemonic == "push" and insn.operands[0].type == X86_OP_IMM
        ]
        formal_immediates = list(reversed(pushed_immediates))
        self.assertEqual(formal_immediates[:4], [6, 0x4763E8, 140, 563])
        self.assertEqual(self.raw["static_evidence"]["detail_alignment"]["placement"], "X=140/Y=563")
        self.assertEqual(self.raw["transaction_contract"]["detail_event"], 8)
        self.assertEqual(self.raw["transaction_contract"]["button_id"], 6)

    def test_overlay_owns_only_zero_parent_space_after_command_seven(self) -> None:
        parent_page = bytes.fromhex(
            self.parent_raw["pe_append_transaction"]["layouts"]["collection_progression"]["append_bytes"]
        )
        self.assertTrue(all(value == 0 for value in parent_page[0x1200:]))
        for raw in (0xB2200, 0xB2240, 0xB2300, 0xB2D00):
            patch = self.patches[raw]
            self.assertEqual(set(bytes.fromhex(patch["before"])), {0})
        ranges = []
        for item in self.raw["patches"]:
            start = int(item["offset"], 0)
            end = start + len(bytes.fromhex(item["after"]))
            for prior_start, prior_end in ranges:
                self.assertFalse(start < prior_end and prior_start < end)
            ranges.append((start, end))
        self.assertLessEqual(max(end for _start, end in ranges if _start >= 0xB1000), 0xB3000)

    def test_native_calls_are_exact_and_ordered(self) -> None:
        calls = [
            (insn.address, insn.operands[0].imm)
            for insn in self.instructions
            if insn.mnemonic == "call" and insn.operands and insn.operands[0].type == X86_OP_IMM
        ]
        targets = [target for _address, target in calls]
        self.assertEqual(targets.count(0x44F4E0), 4)
        self.assertEqual(targets.count(0x445430), 5)
        self.assertEqual(targets.count(0x44D4C0), 1)
        self.assertEqual(targets.count(0x426290), 1)
        last_writer = max(address for address, target in calls if target == 0x445430)
        evaluator = next(address for address, target in calls if target == 0x44D4C0)
        deduction = next(address for address, target in calls if target == 0x426290)
        self.assertLess(last_writer, evaluator)
        self.assertLess(evaluator, deduction)
        contract = self.raw["transaction_contract"]
        self.assertIn("exactly once", contract["native_evaluator"])
        self.assertIn("semantically required", contract["native_evaluator"])
        self.assertIn("exactly once", contract["native_tech_writer"])

    def test_changed_only_native_writes_exact_100_and_no_raw_skill_store(self) -> None:
        for field in (0x7E4, 0x7E8, 0x7EC, 0x7F0, 0x7F4):
            self.assertNotIn(b"\xC7\x86" + field.to_bytes(4, "little") + (100).to_bytes(4, "little"), self.helper)
        generator_source = GENERATOR.read_text(encoding="utf-8")
        self.assertEqual(generator_source.count('"call 0x445430"'), 1)
        self.assertIn('"cmp eax, 100", f"je write_{index}_done"', generator_source)
        self.assertIn('"mov ebx, 100", "sub ebx, eax"', generator_source)
        self.assertEqual(
            self.raw["transaction_contract"]["skills"],
            {
                "farming": "+0x7E4 -> native skill 3",
                "building": "+0x7E8 -> native skill 2",
                "research": "+0x7EC -> native skill 1",
                "healing": "+0x7F0 -> native skill 5",
                "parenting": "+0x7F4 -> native skill 4",
            },
        )

    def test_no_change_precedes_funds_and_confirmation_in_emitted_source(self) -> None:
        source = GENERATOR.read_text(encoding="utf-8")
        no_change = source.index('"cmp dword ptr [ebp-0x54], 0", "je noop"')
        funds = source.index('"mov esi, dword ptr [ebp-0x18]", "mov eax, dword ptr [esi+0x2EADC]"')
        confirmation = source.index('"push 1", f"push 0x{strings[\'caption\']:X}"')
        first_writer = source.index('"call 0x445430"')
        evaluator = source.index('"call 0x44D4C0"')
        final_funds = source.index('f"cmp dword ptr [esi+0x2EADC], {PRICE}"')
        deduction = source.index('"call 0x426290"')
        self.assertLess(no_change, funds)
        self.assertLess(funds, confirmation)
        self.assertLess(confirmation, first_writer)
        self.assertLess(first_writer, evaluator)
        self.assertLess(evaluator, final_funds)
        self.assertLess(final_funds, deduction)

    def test_selection_identity_and_eligibility_are_reacquired_at_every_boundary(self) -> None:
        source = GENERATOR.read_text(encoding="utf-8")
        self.assertGreaterEqual(source.count('"call 0x44F4E0"'), 4)
        self.assertGreaterEqual(source.count('"cmp eax, dword ptr [ebp-0x1C]"'), 3)
        self.assertGreaterEqual(source.count('"cmp edi, dword ptr [ebp-0x20]"'), 3)
        self.assertGreaterEqual(source.count('"cmp eax, dword ptr [ebp-0x24]"'), 3)
        self.assertGreaterEqual(source.count('"cmp eax, dword ptr [ebp-0x28]"'), 3)
        eligibility = self.raw["transaction_contract"]["eligibility_before_skills"]
        self.assertEqual(
            eligibility,
            ["byte +0x30 != 0", "signed dword +0x52C > 0", "byte +0x558 == 0"],
        )
        self.assertIn("No immutable per-record villager identifier has been proved", (ROOT / "docs" / "vv2-individual-full-mastery-candidate.md").read_text(encoding="utf-8"))

    def test_semantic_failure_matrix_and_single_charge(self) -> None:
        base = {
            "active": True,
            "health": 100,
            "totem": False,
            "job": 3,
            "skills": dict(zip(SKILLS, (99, 100, 88, 0, 100))),
        }
        self.assertEqual(transaction_model(deepcopy(base), 200_000, 1), ("committed", 100_000, 3))
        mastered = deepcopy(base)
        mastered["skills"] = {name: 100 for name in SKILLS}
        self.assertEqual(transaction_model(mastered, 0, 1), ("noop", 0, 0))
        self.assertEqual(transaction_model(deepcopy(base), 99_999, 1), ("insufficient", 99_999, 0))
        for result in (0, 2, -1, 99):
            self.assertEqual(transaction_model(deepcopy(base), 200_000, result), ("cancel", 200_000, 0))
        changed = deepcopy(base)
        changed["health"] = 99
        self.assertEqual(transaction_model(deepcopy(base), 200_000, 1, after_confirm=changed), ("race", 200_000, 0))
        self.assertEqual(transaction_model(deepcopy(base), 200_000, 1, after_writes_valid=False), ("failure", 200_000, 3))
        for key, value in (("active", False), ("health", 0), ("totem", True)):
            record = deepcopy(base)
            record[key] = value
            self.assertEqual(transaction_model(record, 200_000, 1), ("invalid", 200_000, 0))

    def test_both_stock_compositions_preserve_parent_tech_and_command7_bytes(self) -> None:
        for mode in MODES:
            with self.subTest(mode=mode):
                parent_bytes, _ = render_patched_bytes(
                    STOCK, self.build, mode, _fun_patches_override=[self.parent]
                )
                candidate, applied = render_patched_bytes(
                    STOCK, self.build, mode, _fun_patches_override=[self.parent, self.feature]
                )
                self.assertEqual(sha(parent_bytes), self.raw["rendered_modes"][mode]["parent_sha256"])
                self.assertEqual(sha(candidate), self.raw["rendered_modes"][mode]["candidate_sha256"])
                self.assertEqual(candidate[0x435EF:0x435F4], parent_bytes[0x435EF:0x435F4])
                self.assertEqual(candidate[0x437C0:0x437C5], parent_bytes[0x437C0:0x437C5])
                self.assertEqual(candidate[0xB1000:0xB2200], parent_bytes[0xB1000:0xB2200])
                self.assertEqual(len(candidate), len(parent_bytes))
                self.assertEqual(
                    {item["owner"] for item in applied if item["owner"].startswith("feature:")},
                    {
                        "feature:vv2_full_mastery_all_stage_a_candidate",
                        "feature:vv2_individual_full_mastery_candidate",
                    },
                )

    def test_expanded_modes_reject_before_variant_catalog_or_source_access(self) -> None:
        for mode in EXPANDED:
            with self.subTest(mode=mode), \
                    mock_patch.object(patcher, "get_patch_variant", side_effect=AssertionError("variant accessed")), \
                    mock_patch.object(patcher, "_selected_fun_patches", side_effect=AssertionError("catalog accessed")):
                with self.assertRaisesRegex(PatcherError, "stock modes only"):
                    render_patched_bytes(
                        ROOT / "does-not-exist.exe",
                        self.build,
                        mode,
                        ["vv2_full_mastery_all_stage_a_candidate", self.raw["id"]],
                    )

    def test_player_status_and_parent_hash_discrepancy_are_not_overclaimed(self) -> None:
        self.assertEqual(self.raw["runtime_player_status"], "pending")
        self.assertIn("runtime/player confirmation pending", self.raw["certification_status"])
        self.assertNotEqual(
            self.raw["parent_chain"]["parent_static_acceptance_sha256"],
            self.raw["parent_chain"]["parent_current_rendered_sha256"],
        )
        self.assertIn("source/static", self.raw["evidence_status"])

    def test_parent_hash_drift_is_exactly_one_safety_range_plus_checksum(self) -> None:
        drift = self.raw["parent_chain"]["parent_render_drift"]
        self.assertEqual(drift["commit"], "f9e5fd90bc998361b58c9c4849800dbd8cda6764")
        self.assertEqual(drift["owner"], "automatic:safety")
        self.assertEqual(drift["raw_offset"], "0x73D00")
        self.assertEqual(drift["current_length"], 47)
        self.assertEqual(drift["accepted_payload_length"], 27)
        self.assertEqual(drift["accepted_zero_tail_length"], 20)
        accepted = bytes.fromhex(drift["accepted_payload_hex"])
        current = bytes.fromhex(drift["current_payload_hex"])
        for mode in MODES:
            with self.subTest(mode=mode):
                parent, applied = render_patched_bytes(
                    STOCK, self.build, mode, _fun_patches_override=[self.parent]
                )
                owner = next(item for item in applied if item["offset"] == "0x73D00")
                self.assertEqual(owner["owner"], "automatic:safety")
                self.assertEqual(bytes(parent[0x73D00:0x73D00 + 47]), current)
                checksum_offset, _ = patcher._pe_checksum_layout(parent)
                self.assertEqual(checksum_offset, 0x148)
                self.assertEqual(
                    f"0x{struct.unpack_from('<I', parent, checksum_offset)[0]:08X}",
                    drift["current_checksums"][mode],
                )
                reconstructed = bytearray(parent)
                reconstructed[0x73D00:0x73D00 + 47] = accepted + bytes(20)
                struct.pack_into("<I", reconstructed, checksum_offset, 0)
                struct.pack_into("<I", reconstructed, checksum_offset, patcher.pe_checksum(reconstructed))
                self.assertEqual(
                    sha(reconstructed),
                    self.raw["parent_chain"]["parent_static_acceptance_sha256"][mode],
                )
                self.assertEqual(
                    f"0x{struct.unpack_from('<I', reconstructed, checksum_offset)[0]:08X}",
                    drift["accepted_checksums"][mode],
                )

    def test_child_and_current_parent_uninstall_roundtrips_are_exact(self) -> None:
        for mode in MODES:
            with self.subTest(mode=mode):
                baseline, _ = render_patched_bytes(STOCK, self.build, mode)
                parent, _ = render_patched_bytes(
                    STOCK, self.build, mode, ["vv2_full_mastery_all_stage_a_candidate"]
                )
                child, _ = render_patched_bytes(
                    STOCK,
                    self.build,
                    mode,
                    ["vv2_full_mastery_all_stage_a_candidate", self.raw["id"]],
                )
                child_removed = bytearray(child)
                patcher._remove_feature_bytes(child_removed, self.feature, mode)
                self.assertEqual(child_removed, parent)
                self.assertEqual(
                    sha(child_removed), self.raw["rendered_modes"][mode]["uninstall_target_sha256"]
                )
                parent_removed = bytearray(parent)
                patcher._remove_feature_bytes(parent_removed, self.parent, mode)
                self.assertEqual(parent_removed, baseline)
                self.assertEqual(
                    sha(parent_removed),
                    self.raw["rendered_modes"][mode]["parent_uninstall_target_sha256"],
                )


if __name__ == "__main__":
    unittest.main()
