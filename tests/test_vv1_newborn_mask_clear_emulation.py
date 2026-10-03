"""Run VV1's newborn mask-clear caves from the allocators' own entries.

A New Home creates villagers through two allocators, each of which takes the
first free record itself:

  * sub_43C350 -- every single/first child of a birth, every event or barrel
    child and every founding villager;
  * sub_43C840 -- the twin (0x42F021) and the triplet (0x42F06D), copied from
    the previous child.

The Origins row splices each one just after its record is chosen (0x43C393
and 0x43C881) to a cave that clears the patch-owned mask nibble of the
chosen index, so a baby reusing a dead villager's record does not inherit
its mask.

Both allocators keep the chosen index in a local written as [esp+0x10], and
both run `push 0x4e` before the splice, so at the splice the index is at
[esp+0x14] and [esp+0x10] is the caller's saved EBX; after the cave's pushad
it is [esp+0x34].  The first version read [esp+0x30] -- the caller's EBX --
so a birth (EBX 0, or a record pointer) cleared villager 0's mask or nothing,
never the newborn's.  And sub_43C840 had no guard at all, so a twin or
triplet kept the stale nibble.

This test renders the patcher's real output in all three population modes,
with the Origins row alone and with every VV1 public patch, executes each
stock allocator from its entry through the splice and cave to the stock
resume address, and checks the mask table bit for bit against a run of the
unpatched allocator.  Skipped (not failed) when the optional `unicorn`
package is unavailable.
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
        UC_X86_REG_EDI, UC_X86_REG_EDX, UC_X86_REG_EIP, UC_X86_REG_ESI, UC_X86_REG_ESP,
    )

    HAVE_UNICORN = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_UNICORN = False

STOCK_CANDIDATES = (
    ROOT / "inputs" / "vv1-stock-copy" / "Virtual Villagers - A New Home.exe",
    ROOT / "research" / "stock-executables" / "Virtual Villagers - A New Home.exe",
)
MODES = ("stock", "immediate_fixed", "collection_progression")
ORIGINS = "vv1_enable_origins_exclusive_features"

# (allocator entry, splice, stock resume after the displaced stores, stock bytes)
ALLOCATORS = {
    "sub_43C350": (0x43C350, 0x43C393, 0x43C39B, "C6462801C6462900"),
    "sub_43C840": (0x43C840, 0x43C881, 0x43C888, "C6462801885E29"),
}
MASK_TABLE = 0x491000          # .vv1md + 0x00, 256 nibbles
MASK_BIRTH_DIRTY = 0x4911FC    # .vv1md + 0x1FC
RECORD_SIZE = 0x3D8
MANAGER = 0x20000000           # the allocator's ECX; record i's occupied byte at +0x28 + i*0x3D8
STACK = 0x30000000
RETURN_SENTINEL = 0x7EEE0000
REGS = ("EAX", "EBX", "ECX", "EDX", "ESI", "EDI", "EBP", "ESP")
# Caller EBX values: small indices that are not the newborn (an event child),
# a record pointer (the golden-child site), 0 (every first child of a birth).
CALLER_EBX = (0, 1, 3, 7, 0x10000000 + 5 * RECORD_SIZE)


def _stock() -> Path | None:
    return next((path for path in STOCK_CANDIDATES if path.is_file()), None)


def _render(mode: str, every_public_patch: bool) -> bytes:
    import vv_fun_patcher as patcher

    builds = {build.id: build for build in patcher.load_builds()}
    if every_public_patch:
        ids = [item.id for item in patcher.load_fun_patches() if item.game_id == "vv1"]
    else:
        ids = [ORIGINS]
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


def _run(image: bytes, allocator: str, *, caller_ebx: int, free_index: int, table: bytes) -> dict:
    entry, _, resume, _ = ALLOCATORS[allocator]
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
    mu.emu_start(entry, resume, count=10000)
    if mu.reg_read(UC_X86_REG_EIP) != resume:
        raise AssertionError(f"{allocator} stopped at {mu.reg_read(UC_X86_REG_EIP):#x}, not {resume:#x}")
    return dict(
        table=bytes(mu.mem_read(MASK_TABLE, 128)),
        dirty=mu.mem_read(MASK_BIRTH_DIRTY, 1)[0],
        regs={name: mu.reg_read(globals()[f"UC_X86_REG_{name}"]) for name in REGS},
        stack=bytes(mu.mem_read(esp - 0x60, 0x80)),
        record=(mu.reg_read(UC_X86_REG_ESI) - MANAGER) // RECORD_SIZE,
        manager=bytes(mu.mem_read(MANAGER, 0x100 * RECORD_SIZE)),
        writes=writes,
    )


@unittest.skipUnless(HAVE_UNICORN, "unicorn is not installed")
@unittest.skipUnless(_stock() is not None, "the stock VV1 executable is not available")
class VV1NewbornMaskClearEmulation(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.stock = _stock().read_bytes()
        cls.images = {
            (mode, "every public patch" if every else "Origins alone"): _render(mode, every)
            for mode in MODES
            for every in (False, True)
        }

    def _table(self, value: int = 0x55) -> bytes:
        return bytes([value]) * 128

    def test_both_splices_replace_their_guarded_stock_bytes_in_every_render(self) -> None:
        for (mode, family), image in self.images.items():
            for allocator, (_, splice, resume, before) in ALLOCATORS.items():
                with self.subTest(mode=mode, family=family, allocator=allocator):
                    raw = splice - 0x400000
                    length = resume - splice
                    self.assertEqual(self.stock[raw:raw + length].hex().upper(), before)
                    self.assertEqual(image[raw], 0xE9)
                    self.assertEqual(image[raw + 5:raw + length], b"\x90" * (length - 5))

    def test_only_the_new_babys_own_nibble_is_cleared(self) -> None:
        for (mode, family), image in self.images.items():
            for allocator in ALLOCATORS:
                for free_index in (0, 1, 3, 7, 200, 255):
                    for caller_ebx in CALLER_EBX + (free_index,):
                        with self.subTest(mode=mode, family=family, allocator=allocator,
                                          free=free_index, ebx=hex(caller_ebx)):
                            before = self._table()
                            result = _run(image, allocator, caller_ebx=caller_ebx,
                                          free_index=free_index, table=before)
                            self.assertEqual(result["record"], free_index)
                            changed = [i for i in range(256)
                                       if _nibble(before, i) != _nibble(result["table"], i)]
                            self.assertEqual(changed, [free_index])
                            self.assertEqual(_nibble(result["table"], free_index), 0)
                            self.assertEqual(result["dirty"], 1)

    def test_an_already_clear_nibble_is_left_alone_and_not_marked_dirty(self) -> None:
        for (mode, family), image in self.images.items():
            for allocator in ALLOCATORS:
                for free_index in (2, 3):
                    with self.subTest(mode=mode, family=family, allocator=allocator, free=free_index):
                        table = bytearray(self._table())
                        table[free_index >> 1] &= 0x0F if free_index & 1 else 0xF0
                        result = _run(image, allocator, caller_ebx=free_index ^ 1,
                                      free_index=free_index, table=bytes(table))
                        self.assertEqual(result["table"], bytes(table))
                        self.assertEqual(result["dirty"], 0)

    def test_registers_stack_and_game_writes_match_the_stock_allocator(self) -> None:
        for allocator in ALLOCATORS:
            for free_index in (1, 3):
                stock = _run(self.stock, allocator, caller_ebx=1, free_index=free_index,
                             table=self._table())
                for (mode, family), image in self.images.items():
                    with self.subTest(mode=mode, family=family, allocator=allocator, free=free_index):
                        patched = _run(image, allocator, caller_ebx=1, free_index=free_index,
                                       table=self._table())
                        self.assertEqual(patched["regs"], stock["regs"])
                        # Everything at and above ESP is the game's; below is dead.
                        self.assertEqual(patched["stack"][0x60:], stock["stack"][0x60:])
                        game_writes = [a for a in patched["writes"]
                                       if not (MASK_TABLE <= a < MASK_TABLE + 0x200) and a < STACK]
                        stock_writes = [a for a in stock["writes"] if a < STACK]
                        self.assertEqual(game_writes, stock_writes)
                        self.assertEqual(patched["manager"], stock["manager"])
                        # The stock run never touches the mask table.
                        self.assertEqual(stock["table"], self._table())


if __name__ == "__main__":
    unittest.main()
