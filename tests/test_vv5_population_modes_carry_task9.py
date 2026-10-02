"""New Believers: every population mode carries the Task9 hooks.

The Task9 page is appended in all three population modes (the patcher maps
"stock" to the collection-progression layout), but its eight mode hooks were
declared only for collection_progression and immediate_fixed.  In the stock
mode a Barrel of Babies charged 75,000 tech points and never arrived (nothing
turned the purchase token into the selector's marker), one Island or Barrel
purchase locked both rows as pending for good (the saved 0x3C bits never
retired), the Heathen masks never drew, and no runtime companion was ever
installed.  The owner: every patch works in all three population modes.

Pinned here, on the executables the patcher renders:

* the stock render differs from collection_progression ONLY where the
  population modes' own variant patches differ (and in the PE checksum), so
  everything proven for collection_progression -- masks, portraits, slot
  capture, the newborn clear -- holds for stock byte for byte;
* emulated in every mode: the Tech-screen close hands a purchased Barrel's
  token to the selector, the selector then forces the Barrel event; a
  purchased Island hands over and retires once delivered, so the rows unlock.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

import pefile
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EIP, UC_X86_REG_ESI, UC_X86_REG_ESP

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - New Believers.exe"
MODES = ("stock", "collection_progression", "immediate_fixed")
ROWS = ["vv5_enable_origins_exclusive_features"]
OWNERSHIP = 0x51D388
MANAGER = 0x30000000
STACK = 0x0F000000
_RENDERS: dict[str, bytes] = {}


def render(mode: str) -> bytes:
    if mode not in _RENDERS:
        import vv_fun_patcher as vfp
        build = next(b for b in vfp.load_builds() if b.id == "vv5")
        _RENDERS[mode] = bytes(vfp.render_patched_bytes(STOCK, build, mode, ROWS)[0])
    return _RENDERS[mode]


class Game:
    """The rendered image mapped; 0x425950 (the village-event manager getter)
    and the RNG 0x403660 are scripted."""

    def __init__(self, mode: str) -> None:
        pe = pefile.PE(data=render(mode))
        image = pe.get_memory_mapped_image()
        self.uc = uc = Uc(UC_ARCH_X86, UC_MODE_32)
        uc.mem_map(0x400000, (len(image) + 0xFFFF) & ~0xFFFF)
        uc.mem_write(0x400000, image)
        uc.mem_map(MANAGER, 0x20000)
        uc.mem_map(STACK - 0x10000, 0x20000)
        self.stop = None
        uc.hook_add(UC_HOOK_CODE, self._hook)

    def _hook(self, uc, address, size, _):
        if address == self.stop or (isinstance(self.stop, frozenset) and address in self.stop):
            uc.emu_stop()
        elif address == 0x425950:                       # thiscall-free getter: eax = manager
            sp = uc.reg_read(UC_X86_REG_ESP)
            uc.reg_write(UC_X86_REG_EAX, MANAGER)
            uc.reg_write(UC_X86_REG_EIP, struct.unpack("<I", uc.mem_read(sp, 4))[0])
            uc.reg_write(UC_X86_REG_ESP, sp + 4)
        elif address == 0x403660:                       # rand(n), cdecl
            sp = uc.reg_read(UC_X86_REG_ESP)
            uc.reg_write(UC_X86_REG_EAX, 0)
            uc.reg_write(UC_X86_REG_EIP, struct.unpack("<I", uc.mem_read(sp, 4))[0])
            uc.reg_write(UC_X86_REG_ESP, sp + 4)

    def u32(self, va: int) -> int:
        return struct.unpack("<I", self.uc.mem_read(va, 4))[0]

    def w32(self, va: int, value: int) -> None:
        self.uc.mem_write(va, struct.pack("<I", value))

    def close_tech_screen(self) -> None:
        """The Technologies screen's close handler, at its `mov ecx, 0x51F440`."""
        self.stop = 0x44161C
        self.uc.reg_write(UC_X86_REG_ESP, STACK)
        self.uc.emu_start(0x441617, 0, count=10000)
        assert self.uc.reg_read(UC_X86_REG_EIP) == 0x44161C
        assert self.uc.reg_read(UC_X86_REG_ECX) == 0x51F440

    def select_event(self, natural: int) -> int:
        """The village-event selector at 0x41890F: eax indexes the candidate
        table at [esp+0x14]; returns the chosen index (esi).

        A natural choice rejoins the stock code at 0x41891A; a purchased
        Barrel goes straight to the presenter at 0x41895B, past the stock
        Chutes Without Ladders override (v1.35.45)."""
        self.stop = frozenset((0x41891A, 0x41895B))
        esp = STACK - 0x100
        self.uc.mem_write(esp, b"\0" * 0x14 + struct.pack("<I", natural))
        self.uc.reg_write(UC_X86_REG_ESP, esp)
        self.uc.reg_write(UC_X86_REG_EAX, 0)
        self.uc.emu_start(0x41890F, 0, count=10000)
        assert self.uc.reg_read(UC_X86_REG_EIP) in self.stop
        return self.uc.reg_read(UC_X86_REG_ESI)


@unittest.skipUnless(STOCK.is_file(), "stock executable fixture is unavailable")
class PopulationModesCarryTask9(unittest.TestCase):

    def test_stock_differs_from_collection_progression_only_in_population_bytes(self):
        import vv_fun_patcher as vfp
        build = next(b for b in vfp.load_builds() if b.id == "vv5")
        allowed = []
        for mode in MODES:
            for patch in build.raw["variants"][mode].get("patches", []):
                start = int(patch["offset"], 16)
                allowed.append((start, start + len(bytes.fromhex(patch["after"]))))
        allowed.append((0x150, 0x154))                  # the PE checksum
        a, b = render("stock"), render("collection_progression")
        self.assertEqual(len(a), len(b))
        stray = [i for i in range(len(a)) if a[i] != b[i]
                 and not any(lo <= i < hi for lo, hi in allowed)]
        self.assertEqual(stray, [], f"stock differs outside the population bytes at {stray[:8]}")

    def test_every_mode_hooks_the_eight_task9_sites(self):
        sites = (0x441617, 0x472481, 0x472B0F, 0x472B57, 0x466E05, 0x4687F0, 0x403600)
        for mode in MODES:
            image = render(mode)
            with self.subTest(mode=mode):
                for va in sites:
                    # The portrait head draw (0x466E05) is a retargeted call.
                    hook = 0xE8 if va == 0x466E05 else 0xE9
                    self.assertEqual(image[va - 0x400000], hook, f"{mode}: no hook at {va:#x}")
                    target = va + 5 + struct.unpack("<i", image[va - 0x3FFFFF: va - 0x3FFFFB])[0]
                    self.assertTrue(0x7C9000 <= target < 0x7D1000, f"{mode}: {va:#x} -> {target:#x}")
                self.assertNotEqual(image[0xD2FA8:0xD2FB8], bytes(16), f"{mode}: no sprite 0x155 record")

    def test_a_purchased_barrel_arrives(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                game = Game(mode)
                game.w32(OWNERSHIP, 0x8 | 0x3)          # Barrel token, and two doublers owned
                game.w32(MANAGER + 0x17D3C, 500)
                game.close_tech_screen()
                self.assertEqual(game.u32(OWNERSHIP), 0x4 | 0x3)     # token -> selector marker
                self.assertEqual(game.u32(MANAGER + 0x17D3C), 0)      # the next event is due
                self.assertEqual(game.select_event(natural=7), 0x1A)  # the forced Barrel event
                self.assertEqual(game.u32(OWNERSHIP), 0x3)            # marker consumed
                self.assertEqual(game.select_event(natural=7), 7)     # then the game chooses again

    def test_a_purchased_island_unlocks_the_rows_once_delivered(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                game = Game(mode)
                game.w32(OWNERSHIP, 0x10)               # Island purchase token
                game.w32(MANAGER + 0x17D3C, 0)          # due
                game.close_tech_screen()
                self.assertEqual(game.u32(OWNERSHIP) & 0x3C, 0x20)   # handed to delivery
                game.close_tech_screen()                 # not delivered yet: still pending
                self.assertEqual(game.u32(OWNERSHIP) & 0x3C, 0x20)
                game.w32(MANAGER + 0x17D3C, 900)         # the scheduler ran the event
                game.close_tech_screen()
                self.assertEqual(game.u32(OWNERSHIP) & 0x3C, 0)      # rows buyable again

    def test_an_ordinary_close_changes_nothing(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                game = Game(mode)
                game.w32(OWNERSHIP, 0x3)
                game.w32(MANAGER + 0x17D3C, 123)
                game.close_tech_screen()
                self.assertEqual((game.u32(OWNERSHIP), game.u32(MANAGER + 0x17D3C)), (0x3, 123))


if __name__ == "__main__":
    unittest.main()
