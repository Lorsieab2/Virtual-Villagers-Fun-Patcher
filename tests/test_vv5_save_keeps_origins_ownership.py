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
        self.entry = PAGE_VA + t9.OFF["slot_capture"]
        self.uc.hook_add(UC_HOOK_CODE, lambda uc, addr, size, _: uc.emu_stop() if addr == RESUME else None)

    def build_path(self, slot: int) -> None:
        esp = STACK + 0x8000
        self.uc.mem_write(esp, struct.pack("<II", 0x403999, slot))   # return address, slot
        self.uc.reg_write(UC_X86_REG_ESP, esp)
        self.uc.emu_start(self.entry, RESUME, count=200)
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

    def test_switching_villages_still_drops_the_old_ownership(self) -> None:
        game = SlotCapture()
        game.build_path(1)
        game.owned = 0x3
        game.build_path(3)                 # load a different village
        self.assertEqual((game.owned, game.captured), (0, 3))


if __name__ == "__main__":
    unittest.main()
