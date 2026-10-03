"""Run The Secret City's own villager-table code in an emulator, stock or 256.

Shared by the 256 Villagers (Experimental) tests.  A `Machine` maps a rendered
executable the way the loader would (every section at its address, zero-fill
past the file bytes), plus a heap, a stack and a return landing.  The
manager's address and the slot count are read from the executable's own
instructions -- `mov ecx, MANAGER` at 0x4279B3 and the slot count at 0x42883A,
the two places the companions read them -- so one test body drives a stock
150-slot image and a 256 image alike.
"""
from __future__ import annotations

import struct
import sys
from functools import lru_cache
from pathlib import Path
from typing import Callable

import pefile
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, UC_PROT_ALL, Uc
from unicorn.x86_const import (
    UC_X86_REG_EAX,
    UC_X86_REG_EBP,
    UC_X86_REG_EBX,
    UC_X86_REG_ECX,
    UC_X86_REG_EDI,
    UC_X86_REG_EDX,
    UC_X86_REG_EIP,
    UC_X86_REG_ESI,
    UC_X86_REG_ESP,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import vv_fun_patcher as vfp  # noqa: E402

EXE = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Secret City.exe"
FEATURE = "vv3_population_256"
MODES = ("stock", "collection_progression", "immediate_fixed")
STRIDE = 0x1F8C
COMPACT = 0x11C
STOCK_PAYLOAD = 0x12F1C
PAYLOAD_256 = 0x1A4B4

HEAP = 0x20000000
HEAP_SIZE = 0x02000000
STACK_TOP = 0x10800000
STACK_SIZE = 0x00200000
RETURN = 0x0F000000
REGS = {
    "eax": UC_X86_REG_EAX, "ebx": UC_X86_REG_EBX, "ecx": UC_X86_REG_ECX,
    "edx": UC_X86_REG_EDX, "esi": UC_X86_REG_ESI, "edi": UC_X86_REG_EDI,
    "ebp": UC_X86_REG_EBP, "esp": UC_X86_REG_ESP, "eip": UC_X86_REG_EIP,
}


def public_vv3_ids() -> list[str]:
    return [
        patch.id
        for patch in vfp.load_public_fun_patches()
        if patch.raw.get("game_id") == "vv3" and patch.id != FEATURE
    ]


@lru_cache(maxsize=None)
def render(mode: str, with_256: bool, with_everything: bool = False) -> bytes:
    """The Secret City rendered in `mode`, with or without 256 Villagers,
    alone or with every other public VV3 patch."""
    build = next(b for b in vfp.load_builds() if b.id == "vv3")
    ids = ([FEATURE] if with_256 else []) + (public_vv3_ids() if with_everything else [])
    data, _ = vfp.render_patched_bytes(EXE, build, mode, ids)
    return bytes(data)


class Machine:
    def __init__(self, image: bytes) -> None:
        pe = pefile.PE(data=image)
        self.mu = Uc(UC_ARCH_X86, UC_MODE_32)
        size = (pe.OPTIONAL_HEADER.SizeOfImage + 0xFFF) & ~0xFFF
        self.mu.mem_map(0x400000, size, UC_PROT_ALL)
        self.mu.mem_write(0x400000, image[: pe.OPTIONAL_HEADER.SizeOfHeaders])
        for section in pe.sections:
            # page-granular, like the loader: the slack after VirtualSize is mapped
            raw = section.get_data()[: (section.Misc_VirtualSize + 0xFFF) & ~0xFFF]
            if raw:
                self.mu.mem_write(0x400000 + section.VirtualAddress, raw)
        self.mu.mem_map(HEAP, HEAP_SIZE)
        self.mu.mem_map(STACK_TOP - STACK_SIZE, STACK_SIZE)
        self.mu.mem_map(RETURN, 0x1000)
        self.mu.mem_write(RETURN, b"\xF4")
        self.mu.mem_map(0, 0x1000)            # fs:[0] for SEH prologues
        self.heap_next = HEAP
        self.stubs: dict[int, Callable[["Machine"], tuple[int, int]]] = {}
        self.calls: list[tuple[int, int]] = []
        # Every import lands on its own address, and reaching one the test did
        # not script stops the run with its name.
        self.api: dict[int, str] = {}
        api = 0x0E000000
        self.mu.mem_map(api, 0x10000)
        for entry in getattr(pe, "DIRECTORY_ENTRY_IMPORT", []):
            for imp in entry.imports:
                stub = api + 16 * len(self.api)
                self.api[stub] = (imp.name or b"?").decode()
                self.put32(imp.address, stub)

        def unscripted(uc, address, size, _):
            uc.emu_stop()
            self.api_error = self.api.get(address, hex(address))

        self.api_error = None
        self.mu.hook_add(UC_HOOK_CODE, unscripted, begin=api, end=api + 0xFFFF)
        self.manager = self.u32(0x4279B4)
        self.slots = self.u32(0x42883A)
        self.records = 260 if self.slots == 256 else 150
        assert self.u8(0x4279B3) == 0xB9

    # memory
    def read(self, va: int, n: int) -> bytes:
        return bytes(self.mu.mem_read(va, n))

    def write(self, va: int, data: bytes) -> None:
        self.mu.mem_write(va, bytes(data))

    def u8(self, va: int) -> int:
        return self.read(va, 1)[0]

    def u32(self, va: int) -> int:
        return struct.unpack("<I", self.read(va, 4))[0]

    def i32(self, va: int) -> int:
        return struct.unpack("<i", self.read(va, 4))[0]

    def put8(self, va: int, value: int) -> None:
        self.write(va, bytes([value & 0xFF]))

    def put32(self, va: int, value: int) -> None:
        self.write(va, struct.pack("<I", value & 0xFFFFFFFF))

    def alloc(self, n: int) -> int:
        at = self.heap_next
        self.heap_next = (at + n + 0x1000) & ~0xFFF
        self.write(at, bytes(n))
        return at

    def rec(self, index: int) -> int:
        return self.manager + 0x14 + index * STRIDE

    def reg(self, name: str) -> int:
        return self.mu.reg_read(REGS[name])

    def set_reg(self, name: str, value: int) -> None:
        self.mu.reg_write(REGS[name], value & 0xFFFFFFFF)

    def arg(self, i: int) -> int:
        return self.u32(self.reg("esp") + 4 + 4 * i)

    # stubs
    def stub(self, va: int, fn: Callable[["Machine"], tuple[int, int]]) -> None:
        """Replace the routine at `va`: fn returns (eax, bytes the callee pops)."""
        self.stubs[va] = fn

        def hook(uc, address, size, _):
            value, pop = self.stubs[address](self)
            esp = self.reg("esp")
            ret = self.u32(esp)
            self.calls.append((address, ret))
            self.set_reg("eax", value)
            self.set_reg("esp", esp + 4 + pop)
            self.set_reg("eip", ret)

        self.mu.hook_add(UC_HOOK_CODE, hook, begin=va, end=va)

    def standard_stubs(self, rolls: Callable[[int], int] | None = None) -> None:
        """The game object, the singletons a record reset asks for, the game
        clock, and the game's RNG wrapper (cdecl rand(n): `rolls(n)`, default 0)."""
        self.game = self.alloc(0x13000)
        self.stub(0x428B60, lambda m: (m.game, 0))
        for getter in (0x42F740, 0x40B8B0, 0x42EE10):
            block = self.alloc(0x100)
            self.stub(getter, lambda m, b=block: (b, 0))
        self.stub(0x403330, lambda m: (1_000_000, 0))   # the game clock (seconds)
        roll = rolls or (lambda n: 0)
        self.rng_calls: list[int] = []

        def rng(m: "Machine") -> tuple[int, int]:
            n = m.arg(0)
            m.rng_calls.append(n)
            return roll(n) % max(n, 1), 0

        self.stub(0x4032D0, rng)

    # running
    def call(self, va: int, args: list[int] = (), *, ecx: int | None = None,
             regs: dict[str, int] | None = None, limit: int = 20_000_000) -> int:
        esp = STACK_TOP - 0x10000
        for value in reversed(list(args)):
            esp -= 4
            self.put32(esp, value)
        esp -= 4
        self.put32(esp, RETURN)
        self.set_reg("esp", esp)
        if ecx is not None:
            self.set_reg("ecx", ecx)
        for name, value in (regs or {}).items():
            self.set_reg(name, value)
        self.mu.emu_start(va, RETURN, count=limit)
        if self.api_error:
            raise AssertionError(f"0x{va:X} reached the unscripted import {self.api_error}")
        if self.reg("eip") != RETURN:
            raise AssertionError(f"0x{va:X} did not return (eip 0x{self.reg('eip'):X})")
        return self.reg("eax")

    def run_until(self, start: int, until: int, *, esp: int, limit: int = 20_000_000) -> None:
        self.set_reg("esp", esp)
        self.mu.emu_start(start, until, count=limit)
        if self.api_error:
            raise AssertionError(f"0x{start:X} reached the unscripted import {self.api_error}")
        if self.reg("eip") != until:
            raise AssertionError(f"0x{start:X} did not reach 0x{until:X} (eip 0x{self.reg('eip'):X})")

    # villagers
    def villager(self, index: int, *, health: int = 50, sex: int = 0, age: int = 300,
                 pregnant: int = 0, babies: int = 0) -> int:
        record = self.rec(index)
        self.put8(record + 0xF10, 1)           # active
        self.put32(record + 0xE78, health)     # alive while > 0
        self.put32(record + 0xDC8, sex)        # 0 male, 1 female (sex counter)
        self.put32(record + 0xDC4, age)
        self.put32(record + 0xE8C, pregnant)
        self.put32(record + 0xE90, babies)
        return record
