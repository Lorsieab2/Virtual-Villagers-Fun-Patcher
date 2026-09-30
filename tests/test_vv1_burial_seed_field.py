"""A New Home's Villagers Buried seed reads the field the game itself counts.

The exporter seeds the lifetime burial counter once per save from the
50-slot memorial.  Until v1.35.40 it walked the graves from manager+0xA340
and added the shared +0x1C occupancy offset, landing inside the NEXT grave's
name -- always zero there -- so every A New Home save was seeded with 0.  The
game's own recount, sub_41CF10, tests manager+0xA340 + i*0x2C.  This runs that
routine in an emulator over random memorials and checks the exporter's walk
(as written in the source) counts exactly the same graves, and that a save
stamped by the old seed ('VBS1') is seeded once more under the new marker.
"""
from __future__ import annotations

import random
import re
import struct
import unittest
from pathlib import Path

import pefile
from unicorn import UC_ARCH_X86, UC_MODE_32, Uc
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_ESP

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "native" / "statistics_export" / "statistics_export.c"
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - A New Home.exe"
MANAGER, STACK, RET = 0x20000000, 0x30000000, 0x40000000


def _exporter_walk() -> tuple[int, int, int, int]:
    """(graves base offset, stride, capacity, marker) from write_vv1's call."""
    text = SOURCE.read_text(encoding="utf-8")
    m = re.search(r"seeded_burial_total\(manager, 0x9E84u, 0x9E88u,\s*manager \+ (0x[0-9A-Fa-f]+)u, "
                  r"(0x[0-9A-Fa-f]+)u, (\d+)u,\s*\(int\)(\w+)\)", text)
    assert m, "write_vv1's seed call not found"
    marker = int(re.search(r"#define %s (0x[0-9A-Fa-f]+)" % m.group(4), text).group(1), 16)
    return int(m.group(1), 16), int(m.group(2), 16), int(m.group(3)), marker


def _game_recount(occupied: list[int]) -> int:
    pe = pefile.PE(str(STOCK), fast_load=True)
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    image = pe.get_memory_mapped_image()
    mu.mem_map(0x400000, (len(image) + 0xFFF) & ~0xFFF)
    mu.mem_write(0x400000, image)
    mu.mem_map(MANAGER, 0x20000)
    mu.mem_map(STACK - 0x1000, 0x2000)
    mu.mem_map(RET, 0x1000)
    for i, v in enumerate(occupied):
        mu.mem_write(MANAGER + 0xA340 + i * 0x2C, struct.pack("<I", v))
    mu.mem_write(STACK, struct.pack("<I", RET))
    mu.reg_write(UC_X86_REG_ESP, STACK)
    mu.reg_write(UC_X86_REG_ECX, MANAGER)
    mu.emu_start(0x41CF10, RET, count=2000)
    return mu.reg_read(UC_X86_REG_EAX)


class BurialSeedFieldTests(unittest.TestCase):
    def test_the_seed_walks_the_graves_the_game_counts(self):
        base, stride, capacity, _ = _exporter_walk()
        self.assertEqual((stride, capacity), (0x2C, 50))
        rng = random.Random(3)
        for trial in range(60):
            occupied = [rng.choice([0, 0, rng.randint(1, 2000)]) for _ in range(50)]
            memory = {}
            for i, v in enumerate(occupied):
                memory[0xA340 + i * 0x2C] = v
                # the grave's name bytes sit before its occupancy dword; fill
                # them so a walk that strays into a name cannot read zero
                memory[0xA31C + i * 0x2C] = 0x6F6E6154 if v else 0
            seed = sum(1 for i in range(capacity) if memory.get(base + i * stride + 0x1C, 0) != 0)
            with self.subTest(trial=trial):
                self.assertEqual(seed, _game_recount(occupied))

    def test_saves_stamped_by_the_old_seed_are_seeded_again(self):
        _, _, _, marker = _exporter_walk()
        self.assertNotEqual(marker, 0x56425331, "a VBS1 save must not be treated as correctly seeded")
        self.assertEqual(struct.pack(">I", marker), b"VBS2")


if __name__ == "__main__":
    unittest.main()
