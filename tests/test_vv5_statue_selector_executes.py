"""VV5 Statue Drops: Normal Action or Honoring, RUN from the rendered executable.

Stock New Believers dispatches a villager dropped on a COMPLETED statue with
`push 0x9D` (Polishing the Statue) at two sites, 0x46BF9A and 0x4796EB; an
upgradeable statue is dispatched with `push 0xA0` (Honoring) at 0x46C45D and
0x46CDED.  The row replaces each completed-statue push with a call through a
trampoline to a selector at 0x494840 that calls the game's own RNG(2) and
leaves 0x9D or 0xA0 on the stack exactly where the push would have.

Each site is executed in an emulator from the patched call, with only the C
runtime's rand() replaced by a controlled value (the game's own RNG wrapper at
0x403660 still reduces it modulo its argument).  An even rand() must give
Honoring and an odd one Polishing, so both outcomes are reachable; the site
must resume at the byte after the original five-byte push with ESP four bytes
lower and the registers the following code reads (ECX, EBX, ESI, EDI, EBP)
unchanged.  EAX and EDX are clobbered, which is harmless: the next thing either
site reaches is the dispatcher 0x465580, which loads both from its own
arguments before reading them -- pinned here from the stock bytes.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

import capstone
import pefile
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
from unicorn.x86_const import (
    UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDI, UC_X86_REG_EIP,
    UC_X86_REG_ESI, UC_X86_REG_ESP,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import vv_fun_patcher as vfp  # noqa: E402

EXE = ROOT / "research" / "stock-executables" / "Virtual Villagers - New Believers.exe"
FEATURE = "vv5_statue_polishing_or_honoring"
SITES = (0x46BF9A, 0x4796EB)
POLISHING, HONORING = 0x9D, 0xA0
RNG = 0x403660                  # the game's RNG(n) wrapper: rand() % n
SCRATCH = 0x0F000000
RAND_VALUE = SCRATCH
RNG_ARGS = SCRATCH + 0x10
STACK_TOP = 0x10800000
CS = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
KEPT = dict(ecx=UC_X86_REG_ECX, ebx=UC_X86_REG_EBX, esi=UC_X86_REG_ESI,
            edi=UC_X86_REG_EDI, ebp=UC_X86_REG_EBP)


def _render(with_row: bool) -> bytes:
    build = next(b for b in vfp.load_builds() if b.id == "vv5")
    rendered, applied = vfp.render_patched_bytes(EXE, build, "immediate_fixed", [FEATURE] if with_row else [])
    assert (f"feature:{FEATURE}" in {r["owner"] for r in applied}) == with_row
    return bytes(rendered)


def _crt_rand(image: bytes) -> int:
    """The C runtime rand() the RNG wrapper calls, decoded from the image."""
    pe = pefile.PE(data=image, fast_load=True)
    o = pe.get_offset_from_rva(RNG - 0x400000)
    calls = [i for i in CS.disasm(image[o:o + 0x20], RNG) if i.mnemonic == "call"]
    return int(calls[0].op_str, 16)


def _run(image: bytes, site: int, rand_value: int) -> dict:
    pe = pefile.PE(data=image)
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    mu.mem_map(0x400000, (pe.OPTIONAL_HEADER.SizeOfImage + 0xFFF) & ~0xFFF)
    mu.mem_write(0x400000, image[:pe.OPTIONAL_HEADER.SizeOfHeaders])
    for section in pe.sections:
        mu.mem_write(0x400000 + section.VirtualAddress, section.get_data())
    mu.mem_map(SCRATCH, 0x1000)
    mu.mem_map(STACK_TOP - 0x10000, 0x10000)
    rand = _crt_rand(image)
    # mov eax, [RAND_VALUE] ; ret
    mu.mem_write(rand, b"\xA1" + struct.pack("<I", RAND_VALUE) + b"\xC3")
    mu.mem_write(RAND_VALUE, struct.pack("<I", rand_value))
    rng_args = []

    def hook(uc, address, size, _):
        if address == RNG:
            esp = uc.reg_read(UC_X86_REG_ESP)
            rng_args.append(struct.unpack("<i", uc.mem_read(esp + 4, 4))[0])

    mu.hook_add(UC_HOOK_CODE, hook)
    esp = STACK_TOP - 0x200
    mu.mem_write(esp, struct.pack("<I", 0xCAFEF00D))
    mu.reg_write(UC_X86_REG_ESP, esp)
    sentinels = dict(ecx=0x11111111, ebx=0x22222222, esi=0x33333333, edi=0x44444444, ebp=0x55555555)
    for name, value in sentinels.items():
        mu.reg_write(KEPT[name], value)
    mu.emu_start(site, site + 5, count=2000)
    end = mu.reg_read(UC_X86_REG_ESP)
    return dict(
        eip=mu.reg_read(UC_X86_REG_EIP),
        esp_delta=esp - end,
        pushed=struct.unpack("<I", mu.mem_read(end, 4))[0],
        below=struct.unpack("<I", mu.mem_read(end + 4, 4))[0],
        kept={name: mu.reg_read(reg) for name, reg in KEPT.items()} == sentinels,
        rng_args=rng_args,
    )


class StatueSelectorExecutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stock = _render(False)
        cls.patched = _render(True)

    def test_stock_pushes_polishing_for_a_completed_statue_and_honoring_for_an_upgradeable_one(self):
        pe = pefile.PE(data=self.stock, fast_load=True)
        for va, action in ((0x46BF9A, POLISHING), (0x4796EB, POLISHING),
                           (0x46C45D, HONORING), (0x46CDED, HONORING)):
            o = pe.get_offset_from_rva(va - 0x400000)
            self.assertEqual(self.stock[o:o + 5], b"\x68" + struct.pack("<I", action), hex(va))
        # The dispatcher both sites reach next loads EDX and EAX from its own
        # arguments before any read, so the selector clobbering them is dead.
        o = pe.get_offset_from_rva(0x465580 - 0x400000)
        self.assertEqual(self.stock[o:o + 8], bytes.fromhex("8B5424088B442404"))

    def test_stock_sites_always_push_polishing(self):
        for site in SITES:
            for rand_value in (4660, 4661):
                with self.subTest(site=hex(site), rand=rand_value):
                    r = _run(self.stock, site, rand_value)
                    self.assertEqual((r["pushed"], r["esp_delta"], r["rng_args"]), (POLISHING, 4, []))

    def test_a_completed_statue_rolls_rng2_and_both_outcomes_are_reachable(self):
        # Which parity maps to which action is not the requirement -- a coin
        # flip either way round is the same 50/50 -- so the test asks only
        # that one RNG(2) result always gives one action and the other result
        # the other, and that the two actions are exactly Polishing and
        # Honoring.
        for site in SITES:
            by_roll = {0: set(), 1: set()}
            for rand_value in (0, 2, 4660, 0x7FFE, 1, 3, 4661, 0x7FFF):
                with self.subTest(site=hex(site), rand=rand_value):
                    r = _run(self.patched, site, rand_value)
                    self.assertEqual(r["rng_args"], [2], "exactly one RNG(2) roll")
                    self.assertIn(r["pushed"], (POLISHING, HONORING))
                    self.assertEqual(r["eip"], site + 5, "resumes after the replaced push")
                    self.assertEqual(r["esp_delta"], 4, "nets exactly one pushed dword, like the push")
                    self.assertEqual(r["below"], 0xCAFEF00D, "the caller's stack is untouched")
                    self.assertTrue(r["kept"], "ECX/EBX/ESI/EDI/EBP must survive")
                    by_roll[rand_value % 2].add(r["pushed"])
            with self.subTest(site=hex(site)):
                self.assertEqual(len(by_roll[0]), 1, f"RNG(2)=0 gave {by_roll[0]}")
                self.assertEqual(len(by_roll[1]), 1, f"RNG(2)=1 gave {by_roll[1]}")
                self.assertEqual(by_roll[0] | by_roll[1], {POLISHING, HONORING},
                                 "both Polishing and Honoring must be reachable")


if __name__ == "__main__":
    unittest.main()
