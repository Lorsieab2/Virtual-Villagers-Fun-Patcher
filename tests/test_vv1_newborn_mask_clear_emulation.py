"""Run VV1's newborn mask-clear cave from sub_43C350's own entry.

A New Home creates every villager -- each birth, each event or barrel child,
each founding villager -- through sub_43C350, which takes the first free
record.  The Origins row splices 0x43C393 (just after that record is chosen)
to a cave that clears the patch-owned mask nibble of the chosen index, so a
newborn reusing a dead villager's record does not inherit its mask.

The cave reads the chosen index from sub_43C350's stack local.  The local is
written as [esp+0x10] by 0x43C36E/0x43C384, but 0x43C391 `push 0x4e` runs
before the splice, so at the splice it is [esp+0x14] and [esp+0x10] is the
caller's saved EBX; after the cave's pushad it is [esp+0x34].  The first
version read [esp+0x30] -- the caller's EBX -- so a birth (EBX = a record
pointer) never cleared the newborn's nibble, and an event child created with
a small EBX wiped some OTHER villager's mask.

This test renders the patcher's real output in all three population modes,
executes the stock allocator from its entry through the splice and cave to
the stock resume address, and checks the mask table bit for bit.
Skipped (not failed) when the optional `unicorn` package is unavailable.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

try:  # optional dependency
    from unicorn import UC_ARCH_X86, UC_HOOK_MEM_WRITE, UC_MODE_32, Uc
    from unicorn.x86_const import (
        UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX,
        UC_X86_REG_EDI, UC_X86_REG_EDX, UC_X86_REG_ESI, UC_X86_REG_ESP,
    )

    HAVE_UNICORN = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_UNICORN = False

STOCK_CANDIDATES = (
    ROOT / "inputs" / "vv1-stock-copy" / "Virtual Villagers - A New Home.exe",
    ROOT / "research" / "stock-executables" / "Virtual Villagers - A New Home.exe",
)
MODES = ("stock", "immediate_fixed", "collection_progression")

ALLOCATOR = 0x43C350
SPLICE = 0x43C393
RESUME = 0x43C39B
MASK_TABLE = 0x491000          # .vv1md + 0x00, 256 nibbles
MASK_BIRTH_DIRTY = 0x4911FC    # .vv1md + 0x1FC
RECORD_SIZE = 0x3D8
MANAGER = 0x20000000           # sub_43C350's ECX; record i's occupied byte at +0x28 + i*0x3D8
STACK = 0x30000000
RETURN_SENTINEL = 0x7EEE0000
REGS = ("EAX", "EBX", "ECX", "EDX", "ESI", "EDI", "EBP", "ESP")


def _stock() -> Path | None:
    return next((path for path in STOCK_CANDIDATES if path.is_file()), None)


def _render(mode: str) -> bytes:
    import vv_fun_patcher as patcher

    builds = {build.id: build for build in patcher.load_builds()}
    ids = [item.id for item in patcher.load_fun_patches() if item.game_id == "vv1"]
    rendered, _ = patcher.render_patched_bytes(_stock(), builds["vv1"], mode, ids)
    return bytes(rendered)


def _sections(image: bytes):
    pe = struct.unpack_from("<I", image, 0x3C)[0]
    count = struct.unpack_from("<H", image, pe + 6)[0]
    optional = struct.unpack_from("<H", image, pe + 20)[0]
    base = struct.unpack_from("<I", image, pe + 24 + 28)[0]
    table = pe + 24 + optional
    for index in range(count):
        entry = table + 40 * index
        vsize, rva, rsize, raw = struct.unpack_from("<IIII", image, entry + 8)
        yield base, rva, max(vsize, rsize), raw, rsize


def _nibble(table: bytes, index: int) -> int:
    return (table[index >> 1] >> (4 if index & 1 else 0)) & 0xF


def _run(image: bytes, *, caller_ebx: int, free_index: int, table: bytes) -> dict:
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    for base, rva, size, raw, rsize in _sections(image):
        start = (base + rva) & ~0xFFF
        end = (base + rva + size + 0xFFF) & ~0xFFF
        mu.mem_map(start, end - start)
        mu.mem_write(base + rva, image[raw:raw + rsize])
    if not any(start <= MASK_TABLE < end for start, end, _ in mu.mem_regions()):
        mu.mem_map(MASK_TABLE, 0x1000)  # the stock baseline has no .vv1md
    mu.mem_map(MANAGER, 0x100000)
    for index in range(free_index):
        mu.mem_write(MANAGER + 0x28 + index * RECORD_SIZE, b"\x01")
    mu.mem_map(STACK, 0x10000)
    esp = STACK + 0x8000
    args = struct.pack("<5I", 0xC7, 0, 0, 0, 0)
    mu.mem_write(esp, struct.pack("<I", RETURN_SENTINEL) + args)
    mu.mem_write(MASK_TABLE, table)
    mu.mem_write(MASK_BIRTH_DIRTY, b"\x00")
    regs = dict(EAX=0x11111111, EBX=caller_ebx, ECX=MANAGER, EDX=0x44444444,
                ESI=0x55555555, EDI=0x66666666, EBP=0x77777777, ESP=esp)
    for name, value in regs.items():
        mu.reg_write(globals()[f"UC_X86_REG_{name}"], value)
    writes: list[int] = []
    mu.hook_add(UC_HOOK_MEM_WRITE, lambda uc, access, address, size, value, data:
                writes.append(address))
    mu.emu_start(ALLOCATOR, RESUME, count=10000)
    return dict(
        table=bytes(mu.mem_read(MASK_TABLE, 128)),
        dirty=mu.mem_read(MASK_BIRTH_DIRTY, 1)[0],
        regs={name: mu.reg_read(globals()[f"UC_X86_REG_{name}"]) for name in REGS},
        stack=bytes(mu.mem_read(esp - 0x60, 0x80)),
        record=(mu.reg_read(UC_X86_REG_ESI) - MANAGER) // RECORD_SIZE,
        writes=writes,
    )


@unittest.skipUnless(HAVE_UNICORN, "unicorn is not installed")
@unittest.skipUnless(_stock() is not None, "the stock VV1 executable is not available")
class VV1NewbornMaskClearEmulation(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.stock = _stock().read_bytes()
        cls.images = {mode: _render(mode) for mode in MODES}

    def _table(self, value: int = 0x55) -> bytes:
        return bytes([value]) * 128

    def test_splice_is_present_in_every_population_mode(self) -> None:
        for mode, image in self.images.items():
            with self.subTest(mode=mode):
                raw = SPLICE - 0x400000
                self.assertEqual(image[raw], 0xE9)
                self.assertNotEqual(image[raw:raw + 8], self.stock[raw:raw + 8])

    def test_only_the_newborns_own_nibble_is_cleared(self) -> None:
        # Caller EBX values: small indices that are NOT the newborn (an event
        # child), the newborn's own index, a record pointer (every birth), 0.
        for mode, image in self.images.items():
            for free_index in (0, 1, 3, 7, 200, 255):
                for caller_ebx in (0, 1, 3, 7, 0x10000000 + 5 * RECORD_SIZE, free_index):
                    with self.subTest(mode=mode, free=free_index, ebx=hex(caller_ebx)):
                        before = self._table()
                        result = _run(image, caller_ebx=caller_ebx, free_index=free_index, table=before)
                        self.assertEqual(result["record"], free_index)
                        changed = [i for i in range(256)
                                   if _nibble(before, i) != _nibble(result["table"], i)]
                        self.assertEqual(changed, [free_index])
                        self.assertEqual(_nibble(result["table"], free_index), 0)
                        self.assertEqual(result["dirty"], 1)

    def test_an_already_clear_nibble_is_left_alone_and_not_marked_dirty(self) -> None:
        for mode, image in self.images.items():
            for free_index in (2, 3):
                with self.subTest(mode=mode, free=free_index):
                    table = bytearray(self._table())
                    table[free_index >> 1] &= 0x0F if free_index & 1 else 0xF0
                    result = _run(image, caller_ebx=free_index ^ 1, free_index=free_index,
                                  table=bytes(table))
                    self.assertEqual(result["table"], bytes(table))
                    self.assertEqual(result["dirty"], 0)

    def test_registers_stack_and_record_match_the_stock_allocator(self) -> None:
        stock = _run(self.stock, caller_ebx=1, free_index=3, table=self._table())
        for mode, image in self.images.items():
            with self.subTest(mode=mode):
                patched = _run(image, caller_ebx=1, free_index=3, table=self._table())
                self.assertEqual(patched["regs"], stock["regs"])
                # Everything at and above ESP is the game's; below is dead.
                self.assertEqual(patched["stack"][0x60:], stock["stack"][0x60:])
                game_writes = [a for a in patched["writes"]
                               if not (MASK_TABLE <= a < MASK_TABLE + 0x200) and a < STACK]
                stock_writes = [a for a in stock["writes"] if a < STACK]
                self.assertEqual(game_writes, stock_writes)


if __name__ == "__main__":
    unittest.main()
