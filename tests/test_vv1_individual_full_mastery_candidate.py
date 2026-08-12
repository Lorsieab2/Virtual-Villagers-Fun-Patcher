from __future__ import annotations

import hashlib
import importlib.util
import json
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


STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - A New Home.exe"
MANIFEST = ROOT / "data" / "candidates" / "vv1_individual_full_mastery_candidate.json"
MAP = ROOT / "data" / "candidates" / "vv1_individual_full_mastery_candidate_map.json"
GENERATOR = ROOT / "scripts" / "build_vv1_individual_full_mastery_candidate.py"
PARENT_MANIFEST = ROOT / "data" / "candidates" / "vv1_full_mastery_all_candidate.json"
PARENT_MAP = ROOT / "data" / "candidates" / "vv1_full_mastery_all_candidate_map.json"
PARENT_DLL = ROOT / "data" / "candidates" / "VVFP VV1 Full Mastery Candidate.dll"
MODES = ("collection_progression", "immediate_fixed")
EXPANDED = ("experimental_expanded_256", "experimental_expanded_256_progression")
SKILLS = ("parenting", "building", "farming", "healing", "research")


def sha(payload: bytes | bytearray) -> str:
    return hashlib.sha256(payload).hexdigest().upper()


def load_generator():
    spec = importlib.util.spec_from_file_location("vv1_individual_mastery_builder", GENERATOR)
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
    final_balance: int | None = None,
) -> tuple[str, int, int]:
    if not record["active"] or int(record["health"]) <= 0 or record["golden_child"]:
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
    post_balance = balance if final_balance is None else final_balance
    if not after_writes_valid or post_balance < 100_000:
        return "failure", post_balance, changed
    return "committed", post_balance - 100_000, changed


class VV1IndividualFullMasteryCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.map = json.loads(MAP.read_text(encoding="utf-8"))
        cls.parent_raw = json.loads(PARENT_MANIFEST.read_text(encoding="utf-8"))
        cls.feature = FunPatch(cls.raw)
        cls.parent = FunPatch(cls.parent_raw)
        cls.build = next(item for item in load_builds() if item.id == "vv1")
        cls.patches = {int(item["offset"], 0): item for item in cls.raw["patches"]}
        cls.helper = bytes.fromhex(cls.patches[0x8EB80]["after"])
        disassembler = Cs(CS_ARCH_X86, CS_MODE_32)
        disassembler.detail = True
        cls.instructions = list(disassembler.disasm(cls.helper, 0x490B80))

    def test_public_catalog_route_is_directly_parented_and_origins_free(self) -> None:
        self.assertEqual(self.raw["id"], "vv1_individual_full_mastery_candidate")
        self.assertEqual(self.raw["dependencies"], ["vv1_full_mastery_all_stage_a_candidate"])
        self.assertEqual(
            set(self.raw["conflicts"]),
            {
                "vv1_enable_origins_exclusive_features",
                "vv1_origins_village_wide_upgrades",
                "vv1_full_mastery_origins_composition",
            },
        )
        loaded = {item.id: item for item in load_fun_patches()}
        self.assertIn(self.raw["id"], loaded)
        self.assertNotIn("vv1_enable_origins_exclusive_features", loaded)
        self.assertEqual(
            patcher.resolve_fun_patch_ids(
                ["vv1_full_mastery_all_stage_a_candidate", self.raw["id"]], game_id="vv1"
            ),
            ["vv1_full_mastery_all_stage_a_candidate", self.raw["id"]],
        )
        with self.assertRaisesRegex(PatcherError, "requires prerequisite"):
            patcher.resolve_fun_patch_ids([self.raw["id"]], game_id="vv1")

    def test_generator_reproduces_manifest_and_map_without_writing(self) -> None:
        manifest, mapping = load_generator().build_manifest()
        self.assertEqual(manifest, self.raw)
        self.assertEqual(mapping, self.map)

    def test_loader_pins_child_and_exact_parent_artifacts(self) -> None:
        self.assertEqual(
            patcher.source_text_sha256(MANIFEST.read_bytes()),
            patcher.VV1_INDIVIDUAL_FULL_MASTERY_MANIFEST_SHA256,
        )
        self.assertEqual(
            patcher.source_text_sha256(MAP.read_bytes()),
            patcher.VV1_INDIVIDUAL_FULL_MASTERY_MAP_SHA256,
        )
        self.assertEqual(
            patcher.source_text_sha256(PARENT_MANIFEST.read_bytes()),
            patcher.VV1_INDIVIDUAL_FULL_MASTERY_PARENT_ARTIFACT_SHA256["manifest"],
        )
        self.assertEqual(
            patcher.source_text_sha256(PARENT_MAP.read_bytes()),
            patcher.VV1_INDIVIDUAL_FULL_MASTERY_PARENT_ARTIFACT_SHA256["map"],
        )
        self.assertEqual(
            sha(PARENT_DLL.read_bytes()),
            patcher.VV1_INDIVIDUAL_FULL_MASTERY_PARENT_ARTIFACT_SHA256["dll"],
        )

    def test_detail_hooks_alignment_cfg_and_assigned_zero_space(self) -> None:
        self.assertEqual(self.patches[0x4A5FA]["before"], "8B4C241C5F")
        self.assertEqual(self.patches[0x4A700]["before"], "8B44240453")
        self.assertEqual(self.raw["static_evidence"]["detail_alignment"]["placement"], "X=120/Y=563")
        parent_page = bytes.fromhex(
            self.parent_raw["pe_append_transaction"]["layouts"][MODES[0]]["append_bytes"]
        )
        self.assertEqual(set(parent_page[0xA80:]), {0})
        ranges: list[tuple[int, int]] = []
        for item in self.raw["patches"]:
            start = int(item["offset"], 0)
            payload = bytes.fromhex(item["after"])
            end = start + len(payload)
            for prior_start, prior_end in ranges:
                self.assertFalse(start < prior_end and prior_start < end)
            ranges.append((start, end))
            if start >= 0x8EA80:
                self.assertFalse(any(bytes.fromhex(item["before"])))
                self.assertLessEqual(end, 0x90000)
        constructor = bytes.fromhex(self.patches[0x8EAC0]["after"])
        self.assertIn(bytes.fromhex("6A005668330200006A7868409345006A06"), constructor)
        for raw, va in ((0x8EA80, 0x490A80), (0x8EAC0, 0x490AC0), (0x8EB80, 0x490B80)):
            code = bytes.fromhex(self.patches[raw]["after"])
            disassembler = Cs(CS_ARCH_X86, CS_MODE_32)
            disassembler.detail = True
            insns = list(disassembler.disasm(code, va))
            self.assertEqual(sum(insn.size for insn in insns), len(code))
            for insn in insns:
                if insn.mnemonic.startswith("j") and insn.operands and insn.operands[0].type == X86_OP_IMM:
                    target = insn.operands[0].imm
                    self.assertTrue(va <= target <= va + len(code) or target in {0x44A705})

    def test_native_writer_abi_is_changed_only_and_exact_100(self) -> None:
        calls = [
            (insn.address, insn.operands[0].imm)
            for insn in self.instructions
            if insn.mnemonic == "call" and insn.operands and insn.operands[0].type == X86_OP_IMM
        ]
        targets = [target for _address, target in calls]
        self.assertEqual(targets.count(0x437230), 5)
        self.assertNotIn(0x41D120, targets)
        source = GENERATOR.read_text(encoding="utf-8")
        self.assertEqual(source.count('"call 0x437230"'), 1)
        self.assertIn('"mov ecx, dword ptr [ebp-0x20]", "call 0x437230"', source)
        self.assertIn('"push ebx", f"push {skill_id}", "push dword ptr [ebp-0x1C]"', source)
        self.assertIn('"mov ebx, 100", "sub ebx, eax"', source)
        self.assertIn("ret 0x0C", self.raw["transaction_contract"]["native_skill_writer"])
        for field in (0x3BC, 0x3C0, 0x3C4, 0x3C8, 0x3CC, 0x3D0):
            self.assertNotIn(b"\xC7\x86" + field.to_bytes(4, "little"), self.helper)

    def test_full_reacquisition_preference_and_single_direct_charge(self) -> None:
        source = GENERATOR.read_text(encoding="utf-8")
        self.assertGreaterEqual(source.count('"cmp edi, dword ptr [esi+0xADE8]"'), 3)
        self.assertGreaterEqual(source.count('"cmp eax, dword ptr [ebp-0x1C]"'), 2)
        self.assertGreaterEqual(source.count('"cmp eax, dword ptr [ebp-0x24]"'), 2)
        self.assertGreaterEqual(source.count('"cmp eax, dword ptr [ebp-0x38]"'), 2)
        self.assertEqual(source.count('f"sub dword ptr [esi+0xA2FC], {PRICE}"'), 1)
        self.assertNotIn("call 0x41D120", source)
        self.assertNotIn("0x9E20]", source)
        no_change = source.index('"cmp dword ptr [ebp-0x50], 0", "je noop"')
        confirmation = source.index('"push 1", f"push 0x{strings[\'caption\']:X}"')
        writer = source.index('"call 0x437230"')
        postverify = source.index('f"cmp dword ptr [edi+0x{offset:X}], 100"')
        final_funds = source.index('f"cmp dword ptr [esi+0xA2FC], {PRICE}"')
        deduction = source.index('f"sub dword ptr [esi+0xA2FC], {PRICE}"')
        self.assertLess(no_change, confirmation)
        self.assertLess(confirmation, writer)
        self.assertLess(writer, postverify)
        self.assertLess(postverify, final_funds)
        self.assertLess(final_funds, deduction)

    def test_semantic_failure_model_is_no_charge_on_every_failure(self) -> None:
        base = {
            "active": True,
            "health": 100,
            "golden_child": False,
            "preference": 4,
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
        changed["preference"] = 2
        self.assertEqual(
            transaction_model(deepcopy(base), 200_000, 1, after_confirm=changed),
            ("race", 200_000, 0),
        )
        self.assertEqual(
            transaction_model(deepcopy(base), 200_000, 1, after_writes_valid=False),
            ("failure", 200_000, 3),
        )
        self.assertEqual(
            transaction_model(deepcopy(base), 200_000, 1, final_balance=99_999),
            ("failure", 99_999, 3),
        )
        for key, value in (("active", False), ("health", 0), ("golden_child", True)):
            record = deepcopy(base)
            record[key] = value
            self.assertEqual(transaction_model(record, 200_000, 1), ("invalid", 200_000, 0))

    def test_both_stock_compositions_preserve_parent_and_uninstall_exactly(self) -> None:
        for mode in MODES:
            with self.subTest(mode=mode):
                baseline, _ = render_patched_bytes(STOCK, self.build, mode)
                parent, _ = render_patched_bytes(
                    STOCK, self.build, mode, _fun_patches_override=[self.parent]
                )
                candidate, applied = render_patched_bytes(
                    STOCK, self.build, mode, _fun_patches_override=[self.parent, self.feature]
                )
                self.assertEqual(sha(parent), self.raw["rendered_modes"][mode]["parent_sha256"])
                self.assertEqual(sha(candidate), self.raw["rendered_modes"][mode]["candidate_sha256"])
                self.assertEqual(candidate[0x358DC:0x358E1], parent[0x358DC:0x358E1])
                self.assertEqual(candidate[0x35AB0:0x35AB5], parent[0x35AB0:0x35AB5])
                self.assertEqual(candidate[0x8E000:0x8EA80], parent[0x8E000:0x8EA80])
                self.assertEqual(sha(PARENT_DLL.read_bytes()), self.raw["parent_chain"]["parent_dll_sha256"])
                self.assertEqual(
                    {item["owner"] for item in applied if item["owner"].startswith("feature:")},
                    {
                        "feature:vv1_full_mastery_all_stage_a_candidate",
                        "feature:vv1_individual_full_mastery_candidate",
                    },
                )
                child_removed = bytearray(candidate)
                patcher._remove_feature_bytes(child_removed, self.feature, mode)
                self.assertEqual(child_removed, parent)
                parent_removed = bytearray(parent)
                patcher._remove_feature_bytes(parent_removed, self.parent, mode)
                self.assertEqual(parent_removed, baseline)

    def test_expanded_rejects_before_variant_catalog_manifest_or_source_access(self) -> None:
        for mode in EXPANDED:
            with self.subTest(mode=mode), \
                    mock_patch.object(patcher, "get_patch_variant", side_effect=AssertionError("variant accessed")), \
                    mock_patch.object(patcher, "_selected_fun_patches", side_effect=AssertionError("catalog accessed")):
                with self.assertRaisesRegex(PatcherError, "stock modes only"):
                    render_patched_bytes(
                        ROOT / "does-not-exist.exe",
                        self.build,
                        mode,
                        ["vv1_full_mastery_all_stage_a_candidate", self.raw["id"]],
                    )

    def test_legacy_origins_owners_are_explicit_runtime_conflicts(self) -> None:
        for path in (
            ROOT / "data" / "vv1_origins_feature.json",
            ROOT / "data" / "vv1_origins_village_wide_upgrades.json",
            ROOT / "data" / "candidates" / "vv1_full_mastery_origins_composition.json",
        ):
            legacy = FunPatch(json.loads(path.read_text(encoding="utf-8")))
            with self.subTest(feature=legacy.id), self.assertRaisesRegex(PatcherError, "conflicts"):
                render_patched_bytes(
                    STOCK,
                    self.build,
                    MODES[0],
                    _fun_patches_override=[self.parent, self.feature, legacy],
                )


if __name__ == "__main__":
    unittest.main()
