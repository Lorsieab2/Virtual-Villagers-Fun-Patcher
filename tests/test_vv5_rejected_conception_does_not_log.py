"""Execute the emitted VV5 trampoline with accepted and rejected game calls."""

import json
import struct
import unittest
from pathlib import Path

try:
    from keystone import KS_ARCH_X86, KS_MODE_32, Ks
    from unicorn import UC_ARCH_X86, UC_MODE_32, Uc
    from unicorn.x86_const import (
        UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX,
        UC_X86_REG_EDI, UC_X86_REG_EIP, UC_X86_REG_ESI, UC_X86_REG_ESP,
    )
except ImportError:  # pragma: no cover - optional local emulator
    Ks = Uc = None

ROOT = Path(__file__).resolve().parents[1]
PAGE = 0x7C9000
CONCEPTION = 0x465E00
TOTAL = 0x51D360
RECORDS = 0x554148
IAT_MODULE = 0x4951D8
IAT_PROC = 0x4951DC
FAKE_MODULE = 0x700000
FAKE_PROC = 0x700100
FAKE_EXPORT = 0x700200
DECISION = 0x700800
SAVED_ARGS = 0x700810
EXPORT_CALLS = 0x700840
EXPORT_ARGS = 0x700844
STACK = 0x1000F000
RETURN = 0x7FF000
MOTHER = 0x66A000
FATHER = 0x60B000
EBX_SENTINEL = 0xB16B00B5
EAX_FROM_GAME = 0xC0FFEE42


def word(value):
    return struct.pack("<I", value)


def assemble(source, address):
    code, _ = Ks(KS_ARCH_X86, KS_MODE_32).asm(source, address)
    return bytes(code)


@unittest.skipIf(Uc is None, "keystone and unicorn are needed")
class Vv5RejectedConceptionDoesNotLog(unittest.TestCase):
    def setUp(self):
        manifest = json.loads((ROOT / "data" / "vv5_parentage_feature.json").read_text())
        layout = manifest["features"][0]["pe_append_transaction"]["layouts"]["stock"]
        page = bytes.fromhex(layout["append_bytes"])

        self.mu = Uc(UC_ARCH_X86, UC_MODE_32)
        mu = self.mu
        mu.mem_map(0x400000, 0x400000)
        mu.mem_map(0x10000000, 0x10000)
        mu.mem_write(PAGE, page)
        mu.mem_write(CONCEPTION, assemble(f"""
            mov eax, [esp+4]
            mov [{SAVED_ARGS}], eax
            mov eax, [esp+8]
            mov [{SAVED_ARGS+4}], eax
            mov eax, [esp+0x1c]
            mov [{SAVED_ARGS+24}], eax
            mov eax, [{DECISION}]
            test eax, eax
            jz rejected
            cmp dword ptr [esp+0x1c], 0
            jne rejected
            add dword ptr [{TOTAL}], 2
        rejected:
            mov eax, {EAX_FROM_GAME}
            ret 0x1c
        """, CONCEPTION))
        mu.mem_write(FAKE_MODULE, assemble("mov eax, 0x700700; ret 4", FAKE_MODULE))
        mu.mem_write(FAKE_PROC, assemble(f"mov eax, {FAKE_EXPORT}; ret 8", FAKE_PROC))
        mu.mem_write(FAKE_EXPORT, assemble(f"""
            inc dword ptr [{EXPORT_CALLS}]
            mov eax, [esp+4]
            mov [{EXPORT_ARGS}], eax
            mov eax, [esp+8]
            mov [{EXPORT_ARGS+4}], eax
            mov eax, [esp+12]
            mov [{EXPORT_ARGS+8}], eax
            mov eax, [esp+16]
            mov [{EXPORT_ARGS+12}], eax
            mov eax, 1
            ret 16
        """, FAKE_EXPORT))
        mu.mem_write(IAT_MODULE, word(FAKE_MODULE))
        mu.mem_write(IAT_PROC, word(FAKE_PROC))
        mu.mem_write(TOTAL, word(100))

    def read(self, address):
        return struct.unpack("<I", self.mu.mem_read(address, 4))[0]

    def run_case(self, accepted, suppressed=0):
        mu = self.mu
        mu.mem_write(DECISION, word(int(accepted)))
        original_args = [11, 22, 33, 44, 55, 66, suppressed]
        mu.mem_write(STACK, word(RETURN) + b"".join(word(v) for v in original_args))
        mu.reg_write(UC_X86_REG_ESP, STACK)
        mu.reg_write(UC_X86_REG_ECX, MOTHER)
        mu.reg_write(UC_X86_REG_EBP, MOTHER)
        mu.reg_write(UC_X86_REG_ESI, FATHER)
        mu.reg_write(UC_X86_REG_EDI, 0xAABBCCDD)
        mu.reg_write(UC_X86_REG_EBX, EBX_SENTINEL)
        mu.reg_write(UC_X86_REG_EAX, 0x12345678)
        mu.emu_start(PAGE, RETURN, count=200)

        self.assertEqual(mu.reg_read(UC_X86_REG_EIP), RETURN)
        self.assertEqual(mu.reg_read(UC_X86_REG_ESP), STACK + 32)
        self.assertEqual(mu.reg_read(UC_X86_REG_EBX), EBX_SENTINEL)
        self.assertEqual(mu.reg_read(UC_X86_REG_EBP), MOTHER)
        self.assertEqual(mu.reg_read(UC_X86_REG_ESI), FATHER)
        self.assertEqual(mu.reg_read(UC_X86_REG_EDI), 0xAABBCCDD)
        self.assertEqual(mu.reg_read(UC_X86_REG_EAX), EAX_FROM_GAME)
        self.assertEqual(self.read(SAVED_ARGS), 11)
        self.assertEqual(self.read(SAVED_ARGS + 4), 22)
        self.assertEqual(self.read(SAVED_ARGS + 24), suppressed)

    def test_rejected_attempt_does_not_call_logger(self):
        self.run_case(accepted=False)
        self.assertEqual(self.read(TOTAL), 100)
        self.assertEqual(self.read(EXPORT_CALLS), 0)

    def test_accepted_pregnancy_passes_both_parents_to_logger(self):
        self.run_case(accepted=True)
        self.assertEqual(self.read(TOTAL), 102)
        self.assertEqual(self.read(EXPORT_CALLS), 1)
        self.assertEqual([self.read(EXPORT_ARGS + 4*i) for i in range(4)],
                         [5, RECORDS, MOTHER, FATHER])

    def test_village_seeding_stays_excluded(self):
        self.run_case(accepted=True, suppressed=1)
        self.assertEqual(self.read(TOTAL), 100)
        self.assertEqual(self.read(EXPORT_CALLS), 0)
