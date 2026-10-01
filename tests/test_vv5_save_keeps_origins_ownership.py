"""New Believers: saving never drops the Origins upgrades the player owns.

The task9 slot_capture detour on the save-path builder (0x403600) clears the
Origins ownership word 0x51D388 when the save slot CHANGES, so one village's
doublers cannot show as owned in another. But the stock file writer
(0x403940) calls that builder with slot+0x14 for the backup file before the
slot's own path, so with no range gate every save looked like two slot
changes and cleared the word: paid doublers vanished from memory after the
first save and from the save file after the next (corruption audit,
2026-09-30). The Secret City and The Tree of Life already accept only slots
1..5.

This runs the real slot_capture bytes from the built page in an emulator.
"""
from __future__ import annotations

import importlib.util
import struct
import sys
import unittest
from pathlib import Path

import pefile
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
from unicorn.x86_const import UC_X86_REG_EIP, UC_X86_REG_ESP

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location(
    "vv5_task9_native_actions_ownership", ROOT / "scripts/build_vv5_task9_native_actions.py"
)
assert SPEC and SPEC.loader
t9 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(t9)

PAGE_VA = 0x7C9000
OWNERSHIP = 0x51D388
RESUME = 0x403606
STACK = 0x10000000
STUBS = 0x7E000000
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - New Believers.exe"


class SlotCapture:
    def __init__(self) -> None:
        page, _ = t9.build_page(PAGE_VA)
        self.uc = Uc(UC_ARCH_X86, UC_MODE_32)
        self.uc.mem_map(PAGE_VA, (len(page) + 0xFFF) & ~0xFFF)
        self.uc.mem_write(PAGE_VA, bytes(page))
        self.uc.mem_map(0x51D000, 0x1000)
        self.uc.mem_map(0x7B1000, 0x1000)
        self.uc.mem_map(0x403000, 0x1000)
        self.uc.mem_map(STACK, 0x10000)
        # kernel32 through the stock IAT (companion_install, which every path
        # build calls): LoadLibraryA answers `module` (0: the companion is not
        # shipped), GetProcAddress the scripted export, which counts its calls.
        self.uc.mem_map(0x495000, 0x1000)
        self.uc.mem_map(STUBS, 0x1000)
        self.uc.mem_write(STUBS, b"\xA1" + struct.pack("<I", STUBS + 0x800) + b"\xC2\x04\x00")   # LoadLibraryA
        self.uc.mem_write(STUBS + 0x10, b"\xB8" + struct.pack("<I", STUBS + 0x20) + b"\xC2\x08\x00")  # GetProcAddress
        self.uc.mem_write(STUBS + 0x20, b"\xFF\x05" + struct.pack("<I", STUBS + 0x804) + b"\x31\xC0\x31\xC9\x31\xD2\xC3")
        self.uc.mem_write(0x4951E0, struct.pack("<I", STUBS))
        self.uc.mem_write(0x4951DC, struct.pack("<I", STUBS + 0x10))
        self.module = 0
        self.entry = PAGE_VA + t9.OFF["slot_capture"]
        self.uc.hook_add(UC_HOOK_CODE, lambda uc, addr, size, _: uc.emu_stop() if addr == RESUME else None)

    @property
    def module(self) -> int:
        return struct.unpack("<I", self.uc.mem_read(STUBS + 0x800, 4))[0]

    @module.setter
    def module(self, value: int) -> None:
        self.uc.mem_write(STUBS + 0x800, struct.pack("<I", value))

    @property
    def installs(self) -> int:
        return struct.unpack("<I", self.uc.mem_read(STUBS + 0x804, 4))[0]

    def build_path(self, slot: int) -> None:
        esp = STACK + 0x8000
        self.uc.mem_write(esp, struct.pack("<II", 0x403999, slot))   # return address, slot
        self.uc.reg_write(UC_X86_REG_ESP, esp)
        self.uc.emu_start(self.entry, RESUME, count=400)
        assert self.uc.reg_read(UC_X86_REG_EIP) == RESUME
        assert self.uc.reg_read(UC_X86_REG_ESP) == esp - 0x104         # displaced prologue replayed

    def save(self, slot: int) -> None:
        # the stock writer's order: backup path (slot+0x14), then the slot's own path twice
        for built in (slot + 0x14, slot, slot):
            self.build_path(built)

    @property
    def owned(self) -> int:
        return struct.unpack("<I", self.uc.mem_read(OWNERSHIP, 4))[0]

    @owned.setter
    def owned(self, value: int) -> None:
        self.uc.mem_write(OWNERSHIP, struct.pack("<I", value))

    @property
    def captured(self) -> int:
        return struct.unpack("<I", self.uc.mem_read(t9.SLOT_SCRATCH, 4))[0]


class NewBelieversSaveKeepsOriginsOwnershipTests(unittest.TestCase):
    def test_the_stock_writer_builds_the_backup_path_first(self) -> None:
        if not STOCK.exists():
            self.skipTest("stock executable not available")
        pe = pefile.PE(str(STOCK), fast_load=True)
        off = pe.get_offset_from_rva(0x40396C - 0x400000)
        self.assertEqual(pe.__data__[off:off + 3], bytes.fromhex("8D5F14"))   # lea ebx, [edi+0x14]

    def test_saving_keeps_the_upgrades_the_player_owns(self) -> None:
        game = SlotCapture()
        game.build_path(2)                 # load village 2
        game.owned = 0x3                   # buy the Tech and Food doublers
        for _ in range(3):
            game.save(2)
            self.assertEqual(game.owned, 0x3)
            self.assertEqual(game.captured, 2)

    def test_the_meta_file_changes_nothing(self) -> None:
        game = SlotCapture()
        game.build_path(4)
        game.owned = 0x1
        game.build_path(0)
        self.assertEqual((game.owned, game.captured), (0x1, 4))

    def test_every_path_build_asks_the_companion_to_install(self) -> None:
        """The runtime companions are installed from here, before the
        village-entry catch-up (see companion_install); the companion's
        bridge installs once, so asking on every build is harmless.  The
        thiscall's registers reach the stock prologue unchanged."""
        from unicorn.x86_const import (UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDI,
                                       UC_X86_REG_EDX, UC_X86_REG_ESI)
        game = SlotCapture()
        game.build_path(2)                 # no companion shipped: nothing to ask
        self.assertEqual(game.installs, 0)
        game.module = 0x12340000
        regs = {UC_X86_REG_ECX: 0x11, UC_X86_REG_EDX: 0x22, UC_X86_REG_EBX: 0x33, UC_X86_REG_ESI: 0x44,
                UC_X86_REG_EDI: 0x55, UC_X86_REG_EBP: 0x66}
        for slot in (0, 2, 2 + 0x14, 3):
            for reg, value in regs.items():
                game.uc.reg_write(reg, value)
            game.build_path(slot)
            for reg, value in regs.items():
                self.assertEqual(game.uc.reg_read(reg), value)
        self.assertEqual(game.installs, 4)

    def test_switching_villages_still_drops_the_old_ownership(self) -> None:
        game = SlotCapture()
        game.build_path(1)
        game.owned = 0x3
        game.build_path(3)                 # load a different village
        self.assertEqual((game.owned, game.captured), (0, 3))


if __name__ == "__main__":
    unittest.main()
