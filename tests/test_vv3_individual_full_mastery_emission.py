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
        cls.insns = list(Cs(CS_ARCH_X86, CS_MODE_32).disasm(cls.helper, 0x6E2100))

    def test_dispatcher_and_metadata_are_exact_disabled_composition(self):
        b = self.builder
        self.assertEqual(b.DISPATCHER.hex().upper(), "83FB010F84F700000083FB020F84EED8FFFFE9D618DCFF")
        self.assertEqual(b.HOOK_BEFORE, bytes.fromhex("E938C02300"))
        self.assertEqual(b.HOOK_AFTER, bytes.fromhex("E938E72300"))
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        mapping = json.loads(MAP.read_text(encoding="utf-8"))
        self.assertFalse(manifest["enabled"])
        self.assertTrue(manifest["catalog_hidden"])
        self.assertEqual(manifest["dependencies"], ["vv3_individual_grant_running_candidate"])
        self.assertEqual(manifest["base_chain"]["collection_progression_parent_sha256"], "8DD1CE07C885DDA3DD038D0B2F5C4F019D8C5BAC5DCA29F9799CE0C7909D2CEA")
        self.assertEqual(manifest["base_chain"]["immediate_fixed_parent_sha256"], "78758FD0003842AEFAC092A47874329C9C103F9AD46483E6ECA71291EFD3E382")
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

    def test_confirmation_and_final_funds_precede_mutation_and_charge(self):
        addresses = {i.address: i for i in self.insns}
        writer_addrs = [i.address for i in self.insns if i.mnemonic == "call" and i.op_str == "0x455740"]
        evaluator = next(i.address for i in self.insns if i.mnemonic == "call" and i.op_str == "0x462500")
        deduction = next(i.address for i in self.insns if i.mnemonic == "call" and i.op_str == "0x427130")
        self.assertTrue(any(i.mnemonic == "cmp" and i.op_str == "eax, 2" for i in self.insns))
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


if __name__ == "__main__":
    unittest.main()
