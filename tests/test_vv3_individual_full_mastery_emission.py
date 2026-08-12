from __future__ import annotations

import importlib.util
import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_vv3_individual_mastery_candidate.py"
MANIFEST = ROOT / "data" / "candidates" / "vv3_individual_full_mastery_candidate.json"
MAP = ROOT / "data" / "candidates" / "vv3_individual_full_mastery_candidate_map.json"
sys.path.insert(0, str(ROOT / ".tools" / "capstone"))
from capstone import CS_ARCH_X86, CS_MODE_32, Cs  # noqa: E402


def load_builder():
    spec = importlib.util.spec_from_file_location("vv3_individual_builder", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class VV3IndividualEmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.builder = load_builder()
        cls.page, cls.details = cls.builder.build_page()
        cls.helper = cls.page[0x100 : 0x100 + cls.details["helper_length"]]
        cls.insns = list(Cs(CS_ARCH_X86, CS_MODE_32).disasm(cls.helper, 0x6E0100))

    def test_dispatcher_and_metadata_are_exact_public_composition(self):
        b = self.builder
        self.assertEqual(b.DISPATCHER.hex().upper(), "83FB010F85E539DCFFE8F2000000E9C337DCFF")
        self.assertEqual(b.HOOK_BEFORE, bytes.fromhex("E926010000"))
        self.assertEqual(b.HOOK_AFTER, bytes.fromhex("E938C72300"))
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        mapping = json.loads(MAP.read_text(encoding="utf-8"))
        self.assertTrue(manifest["enabled"])
        self.assertFalse(manifest["catalog_hidden"])
        self.assertEqual(manifest["dependencies"], ["vv3_full_mastery_all_stage_a_candidate"])
        self.assertEqual(manifest["base_chain"]["collection_progression_parent_sha256"], "22456EEE7525066A1125EE7FA92E4EFC71CAACD81056D290EC357226889031A3")
        self.assertEqual(manifest["base_chain"]["immediate_fixed_parent_sha256"], "1FC6CEFF644928B6EFB4802E8E26D2FE2098AAEA2233D2F00AB59E9113BB9225")
        self.assertNotIn("running_command2", manifest["base_chain"])
        self.assertEqual(mapping["dispatcher"]["abi"], "cmp ebx,1; jne 0x4A39EE; call 0x6E0100; jmp 0x4A37D6")
        self.assertEqual(mapping["skill_order"], ["Farming", "Building", "Research", "Healing", "Parenting"])

    def test_helper_decodes_contiguously_and_has_native_targets(self):
        self.assertGreater(len(self.insns), 100)
        self.assertEqual(sum(i.size for i in self.insns), len(self.helper))
        calls = [i for i in self.insns if i.mnemonic == "call" and i.op_str.startswith("0x")]
        targets = [int(i.op_str, 16) for i in calls]
        for target in (0x45EE60, 0x45C840, 0x455740, 0x462500, 0x427130):
            self.assertIn(target, targets)
        self.assertEqual(targets.count(0x462500), 1)
        self.assertEqual(targets.count(0x427130), 1)
        self.assertEqual(targets.count(0x455740), 5)
        self.assertEqual(targets.count(0x45C840), 3)

    def test_callee_clean_validator_resolver_and_native_abi_operands(self):
        # 0x45EE60/0x45C840 are ret-4 routines; the caller must not clean
        # their argument.  This catches the historical double-clean sites.
        for pos, insn in enumerate(self.insns):
            if insn.mnemonic == "call" and insn.op_str in {"0x45ee60", "0x45c840"}:
                following = self.insns[pos + 1] if pos + 1 < len(self.insns) else None
                self.assertFalse(following and following.mnemonic == "add" and following.op_str.replace(" ", "") == "esp,4")

        writers = [pos for pos, insn in enumerate(self.insns) if insn.mnemonic == "call" and insn.op_str == "0x455740"]
        self.assertEqual(len(writers), 5)
        for pos in writers:
            self.assertGreaterEqual(pos, 3)
            self.assertEqual(self.insns[pos - 1].mnemonic, "lea")
            self.assertIn("ecx", self.insns[pos - 1].op_str)
            self.assertIn("[esi+0xeac]", self.insns[pos - 1].op_str.replace(" ", "").lower())
            self.assertEqual(self.insns[pos - 2].mnemonic, "push")
            self.assertEqual(self.insns[pos - 3].mnemonic, "push")

        evaluator_pos = next(pos for pos, insn in enumerate(self.insns) if insn.mnemonic == "call" and insn.op_str == "0x462500")
        self.assertEqual(self.insns[evaluator_pos - 1].mnemonic, "push")
        self.assertEqual(self.insns[evaluator_pos - 1].op_str, "esi")
        self.assertFalse(any(i.mnemonic == "mov" and i.op_str.replace(" ", "") == "ecx,esi" for i in self.insns[: evaluator_pos + 1]))

    def test_active_health_are_snapshotted_and_revalidated(self):
        normalized = lambda i: i.op_str.replace(" ", "").lower()
        stores = [i for i in self.insns if i.mnemonic == "mov" and "[ebp-0x38]" in normalized(i)]
        health_stores = [i for i in self.insns if i.mnemonic == "mov" and "[ebp-0x3c]" in normalized(i)]
        self.assertTrue(stores, "initial active snapshot missing")
        self.assertTrue(health_stores, "initial health snapshot missing")
        active_checks = [i for i in self.insns if i.mnemonic == "cmp" and "[ebp-0x38]" in normalized(i)]
        health_checks = [i for i in self.insns if i.mnemonic == "cmp" and "[ebp-0x3c]" in normalized(i)]
        self.assertGreaterEqual(len(active_checks), 2)
        self.assertGreaterEqual(len(health_checks), 2)
        self.assertNotIn("+ 0xec0]", " ".join(i.op_str.lower() for i in self.insns if i.mnemonic == "mov" and i.op_str.startswith("byte ptr [")))

    def test_confirmation_and_final_funds_precede_mutation_and_charge(self):
        addresses = {i.address: i for i in self.insns}
        writer_addrs = [i.address for i in self.insns if i.mnemonic == "call" and i.op_str == "0x455740"]
        evaluator = next(i.address for i in self.insns if i.mnemonic == "call" and i.op_str == "0x462500")
        deduction = next(i.address for i in self.insns if i.mnemonic == "call" and i.op_str == "0x427130")
        self.assertTrue(any(i.mnemonic == "cmp" and i.op_str == "eax, 1" for i in self.insns))
        self.assertFalse(any(i.mnemonic == "cmp" and i.op_str == "eax, 2" for i in self.insns))
        self.assertLess(min(i.address for i in self.insns if i.mnemonic == "cmp" and "0x582644" in i.op_str), min(writer_addrs))
        self.assertLess(evaluator, deduction)
        self.assertGreaterEqual(sum(1 for i in self.insns if i.mnemonic == "cmp" and "0x582644" in i.op_str), 3)
        self.assertNotIn(bytes.fromhex("31C083F80175"), self.helper)

    def test_stack_intervals_and_preference_are_disjoint(self):
        mapping = json.loads(MAP.read_text(encoding="utf-8"))
        intervals = list(mapping["stack_intervals"].items())
        for i, (name, (start, end)) in enumerate(intervals):
            self.assertLessEqual(start, end, name)
            for other, (ostart, oend) in intervals[i + 1 :]:
                self.assertTrue(end < ostart or oend < start, f"{name} overlaps {other}")
        self.assertNotIn(bytes.fromhex("8986C00E0000"), self.helper)
        self.assertIn(bytes.fromhex("8B86C00E0000"), self.helper)

    def test_deterministic_page_and_exact_messages(self):
        page2, details2 = self.builder.build_page()
        self.assertEqual(self.page, page2)
        self.assertEqual(self.details, details2)
        self.assertIn(b"Villager Upgrades\0", self.page)
        self.assertIn(b"Press OK to confirm, or Cancel.\0", self.page)
        self.assertIn(b"No tech points have been deducted.", self.page)
        self.assertIn(b"Full Mastery dependencies are unavailable.", self.page)

    def test_exact_stock_native_sources_and_public_parents_are_authenticated(self):
        parents, regions = self.builder.verify_source_and_parents()
        self.assertEqual(
            {mode: self.builder.sha(data) for mode, data in parents.items()},
            self.builder.PARENTS,
        )
        self.assertEqual(set(regions), set(self.builder.SOURCE_REGION_SHA256))

    def test_idok_one_dominates_first_writer_and_dependency_route_is_guarded(self):
        cmp_positions = [i.address for i in self.insns if i.mnemonic == "cmp" and i.op_str == "eax, 1"]
        writer_positions = [i.address for i in self.insns if i.mnemonic == "call" and i.op_str == "0x455740"]
        self.assertEqual(len(cmp_positions), 1)
        self.assertLess(cmp_positions[0], min(writer_positions))
        self.assertTrue(any(i.mnemonic == "cmp" and "[ebp-0x10]" in i.op_str.replace(" ", "").lower() for i in self.insns))


if __name__ == "__main__":
    unittest.main()
