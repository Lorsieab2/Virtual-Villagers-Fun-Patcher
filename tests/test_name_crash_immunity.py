from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher as patcher  # noqa: E402

try:
    from capstone import CS_ARCH_X86, CS_MODE_32, Cs

    HAVE_CAPSTONE = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_CAPSTONE = False


IMAGE_BASE = 0x400000
EXPECTED_BASENAME = "Virtual Villagers - The Secret City.exe"


def _synthetic_pe() -> bytearray:
    """Build a tiny PE containing one import and two executable API calls."""
    data = bytearray(0x5000)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 0x80)
    data[0x80:0x84] = b"PE\0\0"
    coff = 0x84
    struct.pack_into("<H", data, coff + 2, 1)  # one section
    struct.pack_into("<H", data, coff + 16, 0xE0)  # optional-header size
    optional = coff + 20
    struct.pack_into("<H", data, optional, 0x10B)
    struct.pack_into("<I", data, optional + 28, IMAGE_BASE)
    struct.pack_into("<I", data, optional + 92, 16)
    struct.pack_into("<II", data, optional + 96 + 8, 0x1800, 0x100)

    section = optional + 0xE0
    data[section : section + 8] = b".text\0\0\0"
    struct.pack_into("<I", data, section + 8, 0x4000)  # virtual size
    struct.pack_into("<I", data, section + 12, 0x1000)  # RVA
    struct.pack_into("<I", data, section + 16, 0x4000)  # raw size
    struct.pack_into("<I", data, section + 20, 0x400)  # raw offset
    struct.pack_into("<I", data, section + 36, 0x60000020)  # executable/readable

    def raw(rva: int) -> int:
        return 0x400 + (rva - 0x1000)

    # IMAGE_IMPORT_DESCRIPTOR -> INT, module name, IAT.
    struct.pack_into("<IIIII", data, raw(0x1800), 0x1900, 0, 0, 0x1C00, 0x1A00)
    struct.pack_into("<II", data, raw(0x1900), 0x1C00, 0)
    data[raw(0x1C00) + 2 : raw(0x1C00) + 2 + len(b"GetModuleFileNameA\0")] = b"GetModuleFileNameA\0"

    iat_va = IMAGE_BASE + 0x1A00
    for rva in (0x2000, 0x2010):
        data[raw(rva) : raw(rva) + 2] = b"\xFF\x15"
        struct.pack_into("<I", data, raw(rva) + 2, iat_va)
    return data


@unittest.skipUnless(HAVE_CAPSTONE, "requires Capstone")
class NameCrashWrapperTests(unittest.TestCase):
    def _instructions(self, name_len: int = 10):
        blob = patcher._nci_wrapper(0x401A00, 0x500000, name_len)
        return blob, list(Cs(CS_ARCH_X86, CS_MODE_32).disasm(blob, 0x600000))

    def test_success_failure_and_truncation_paths_are_bounded(self) -> None:
        blob, ins = self._instructions()
        self.assertTrue(blob)
        text = [(item.mnemonic, item.op_str) for item in ins]
        fail = next(
            item.address
            for item in ins
            if item.mnemonic == "mov"
            and item.op_str == "eax, dword ptr [esp + 0xc]"
        )
        self.assertNotIn("eax, dword ptr [esp + 0x10]", text)
        self.assertIn(("mov", "edi, dword ptr [esp + 0x18]"), text)
        self.assertIn(("mov", "ecx, dword ptr [esp + 0x1c]"), text)

        # API failure, API-reported truncation, nSize == 0, a scan reaching the
        # nSize boundary, and replacement truncation all branch to the same
        # original-return restore.
        expected_branches = (
            ("test", "eax, eax", "je"),
            ("test", "ecx, ecx", "je"),
            ("cmp", "eax, ecx", "jae"),
            ("cmp", "edi, ebp", "jae"),
            ("cmp", "eax, ebp", "ja"),
        )
        for compare, operand, branch in expected_branches:
            with self.subTest(compare=compare, operand=operand):
                index = next(
                    i
                    for i, item in enumerate(ins)
                    if item.mnemonic == compare and item.op_str == operand
                )
                self.assertEqual(ins[index + 1].mnemonic, branch)
                self.assertEqual(int(ins[index + 1].op_str, 16), fail)

        write_index = next(
            i
            for i, item in enumerate(ins)
            if item.mnemonic == "mov" and item.op_str == "byte ptr [edx], al"
        )
        capacity_index = next(
            i
            for i, item in enumerate(ins)
            if item.mnemonic == "cmp" and item.op_str == "eax, ebp"
        )
        self.assertGreater(write_index, capacity_index)
        self.assertIn(("ret", "0xc"), text)

    def test_every_name_guard_write_is_in_the_applied_ledger(self) -> None:
        data = _synthetic_pe()
        applied: list[dict[str, str]] = []
        result = patcher._apply_name_crash_immunity(
            data, EXPECTED_BASENAME, applied
        )
        self.assertEqual(result["status"], "applied")
        self.assertEqual(len(applied), len(result["writes"]))
        self.assertEqual(
            len({row["offset"] for row in applied}),
            len(applied),
        )
        for row in applied:
            self.assertEqual(row["purpose"], "wrong-exe-name crash immunity")
            self.assertEqual(row["owner"], "automatic:name_crash_immunity")
        self.assertEqual(len(result["call_sites"]), 2)
        name_to_code = result["wrapper_va"] - result["name_va"]
        wrapper_length = len(
            patcher._nci_wrapper(
                result["iat_va"], result["name_va"], len(EXPECTED_BASENAME) + 1
            )
        )
        self.assertEqual(
            len(result["writes"][1]["after"]) // 2,
            wrapper_length,
        )
        self.assertGreaterEqual(name_to_code, len(EXPECTED_BASENAME) + 1)

    def test_finalizer_rejects_unapplied_immunity(self) -> None:
        for reason in ("not a PE32 image", "no GetModuleFileNameA import", "no code cave"):
            with self.subTest(reason=reason), patch.object(
                patcher,
                "_apply_name_crash_immunity",
                return_value={"status": "skipped", "reason": reason},
            ):
                with self.assertRaises(patcher.PatcherError):
                    patcher._require_name_crash_immunity(
                        bytearray(), EXPECTED_BASENAME, []
                    )

        for result in (
            {"status": "applied"},
            {"status": "skipped", "reason": "already immune"},
        ):
            with self.subTest(result=result), patch.object(
                patcher,
                "_apply_name_crash_immunity",
                return_value=result,
            ):
                self.assertEqual(
                    patcher._require_name_crash_immunity(
                        bytearray(), EXPECTED_BASENAME, []
                    ),
                    result,
                )


if __name__ == "__main__":
    unittest.main()
