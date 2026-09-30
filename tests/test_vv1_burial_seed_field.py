"""A New Home's Villagers Buried baseline reads the field the game itself counts.

Villagers Buried now lives in the slot's statistics .dat
(native/statistics_export/statistics_store.c). When that file has no entry
yet, the count starts from the larger of the frozen counter an earlier build
kept at manager+0x9E84 and the graves the 50-slot memorial still holds.
Until v1.35.40 the memorial walk started at manager+0xA340 and added the
shared +0x1C occupancy offset, landing inside the NEXT grave's name -- always
zero there -- so every A New Home save was seeded with 0. The game's own
recount, sub_41CF10, tests manager+0xA340 + i*0x2C. This runs that routine in
an emulator over random memorials and checks the store's walk (as written in
the source) counts exactly the same graves, and that a save the old seed
stamped with 0 is corrected by the max rather than trusted.
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
STORE = ROOT / "native" / "statistics_export" / "statistics_store.c"
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - A New Home.exe"
MANAGER, STACK, RET = 0x20000000, 0x30000000, 0x40000000


def _store_walk() -> tuple[int, int, int, int]:
    """(memorial base, stride, occupancy offset, capacity) from VV1's layout."""
    text = STORE.read_text(encoding="utf-8")
    block = text[text.index("{ GAME_VV1, 0, 0, 0,"):]
    block = block[:block.index("},\n    /*")]
    m = re.search(r"\n\s*1, (0x[0-9A-Fa-f]+)u, (0x[0-9A-Fa-f]+)u, (0x[0-9A-Fa-f]+)u, (\d+)u,", block)
    assert m, "VV1's memorial layout not found in statistics_store.c"
    return int(m.group(1), 16), int(m.group(2), 16), int(m.group(3), 16), int(m.group(4))


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
    def test_the_baseline_walks_the_graves_the_game_counts(self):
        base, stride, occupancy, capacity = _store_walk()
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
            seed = sum(1 for i in range(capacity)
                       if memory.get(base + i * stride + occupancy, 0) != 0)
            with self.subTest(trial=trial):
                self.assertEqual(seed, _game_recount(occupied))

    def test_a_save_the_old_seed_stamped_with_zero_is_corrected(self):
        """The start is max(frozen counter, memorial), so a frozen 0 from the
        old wrong-offset seed never hides the graves the game holds."""
        text = STORE.read_text(encoding="utf-8")
        self.assertIn('{ VVS_BURIED, "villagers_buried", 0x9E9Cu, 0x9E84u, 0x9E88u }', text)
        body = text[text.index("static long long migration_value("):]
        body = body[:body.index("\n}\n")]
        self.assertIn("long long memorial = count_memorial(c, g);", body)
        self.assertIn("if (memorial > value) {", body)


if __name__ == "__main__":
    unittest.main()
