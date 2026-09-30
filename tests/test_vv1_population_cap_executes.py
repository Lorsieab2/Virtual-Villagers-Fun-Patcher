"""VV1 population cap per patch mode, RUN from the rendered executable.

A New Home's "may another villager be born" check at 0x43A1A0 counts the living
population (0x41CF90) and refuses at 90 with `cmp eax,0x5A` at 0x43A1AE; below
that it applies the stock housing tiers (15, 25 and 50 need the village flags
at +0x9FE8, +0x9FF0 and +0x9FF8).  The Collection Progression and Immediate
Fixed modes jump from 0x43A1AE to a cave at 0x43A226 that compares with 256
instead and jumps back to the stock `jl` at 0x43A1B1; Stock mode keeps 90.

Each mode's render is run in an emulator with only the population counter
replaced, at populations either side of each boundary.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

import pefile
from unicorn import UC_ARCH_X86, UC_MODE_32, Uc
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_ESP

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import vv_fun_patcher as vfp  # noqa: E402

EXE = ROOT / "research" / "stock-executables" / "Virtual Villagers - A New Home.exe"
CHECK = 0x43A1A0
COUNT = 0x41CF90
CAP = {"stock": 90, "collection_progression": 256, "immediate_fixed": 256}
SCRATCH = 0x0F000000
POPULATION = SCRATCH
RETURN = SCRATCH + 0x800
VILLAGE = 0x20000000
STATE = 0x21000000
STACK_TOP = 0x10800000


def _render(mode: str) -> bytes:
    build = next(b for b in vfp.load_builds() if b.id == "vv1")
    rendered, _ = vfp.render_patched_bytes(EXE, build, mode, [])
    return bytes(rendered)


def _may_grow(image: bytes, population: int, housing: bool = True) -> bool:
    pe = pefile.PE(data=image)
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    mu.mem_map(0x400000, (pe.OPTIONAL_HEADER.SizeOfImage + 0xFFF) & ~0xFFF)
    mu.mem_write(0x400000, image[:pe.OPTIONAL_HEADER.SizeOfHeaders])
    for section in pe.sections:
        mu.mem_write(0x400000 + section.VirtualAddress, section.get_data())
    for base, size in ((SCRATCH, 0x1000), (VILLAGE, 0x40000), (STATE, 0x10000),
                       (STACK_TOP - 0x10000, 0x10000)):
        mu.mem_map(base, size)
    mu.mem_write(RETURN, b"\xF4")
    # the population counter: mov eax, [POPULATION] ; ret
    mu.mem_write(COUNT, b"\xA1" + struct.pack("<I", POPULATION) + b"\xC3")
    mu.mem_write(POPULATION, struct.pack("<I", population))
    mu.mem_write(VILLAGE + 0x3E010, struct.pack("<I", STATE))
    for flag in (0x9FE8, 0x9FF0, 0x9FF8):
        mu.mem_write(STATE + flag, b"\x01" if housing else b"\x00")
    esp = STACK_TOP - 0x100
    mu.mem_write(esp, struct.pack("<I", RETURN))
    mu.reg_write(UC_X86_REG_ESP, esp)
    mu.reg_write(UC_X86_REG_ECX, VILLAGE)
    mu.emu_start(CHECK, RETURN, count=1000)
    return bool(mu.reg_read(UC_X86_REG_EAX) & 0xFF)


class VV1PopulationCapExecutes(unittest.TestCase):
    def test_each_mode_refuses_at_its_own_cap_and_not_before(self):
        for mode, cap in CAP.items():
            image = _render(mode)
            for population, expected in ((0, True), (cap - 1, True), (cap, False), (cap + 1, False),
                                         (89, True), (90, cap > 90), (255, cap > 255), (256, False)):
                with self.subTest(mode=mode, population=population):
                    self.assertEqual(_may_grow(image, population), expected)

    def test_each_mode_keeps_the_stock_housing_tiers_below_the_cap(self):
        for mode in CAP:
            image = _render(mode)
            for population, expected in ((14, True), (15, False), (25, False), (50, False), (89, False)):
                with self.subTest(mode=mode, population=population):
                    self.assertEqual(_may_grow(image, population, housing=False), expected)

    def test_stock_mode_leaves_the_stock_compare_in_place(self):
        pe = pefile.PE(str(EXE), fast_load=True)
        o = pe.get_offset_from_rva(0x43A1AE - 0x400000)
        self.assertEqual(EXE.read_bytes()[o:o + 3], bytes.fromhex("83F85A"))
        self.assertEqual(_render("stock")[o:o + 3], bytes.fromhex("83F85A"))


if __name__ == "__main__":
    unittest.main()
