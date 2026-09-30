"""Statistics rows count exactly what their labels say (owner, 2026-09-29).

Runs the patcher's rendered bytes (Write Village Statistics rows) in an
emulator:

* The Lost Children, Points Earned: the research path taken when
  [container+0x2EA7C] == 3 called the award routine 0x426290 -- which already
  adds the amount to spendable tech (+0x2EADC) and Points Earned (+0x2E4FC) --
  and then added it to +0x2E4FC again at 0x463742.  Now it is counted once,
  and spendable tech is unchanged.
* The Secret City / The Tree of Life / New Believers, People Cured: the +1
  ran after a failed healing roll too.  Now only a cure counts, and a failed
  roll still continues exactly where the stock code does.

Each check also runs on the stock bytes, which must show the old behaviour,
so the checks can fail.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

import pefile
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
from unicorn.x86_const import (
    UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EDI, UC_X86_REG_EIP, UC_X86_REG_ESI, UC_X86_REG_ESP,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import vv_fun_patcher as vfp  # noqa: E402

STOCK = ROOT / "research" / "stock-executables"
NAMES = {2: "The Lost Children", 3: "The Secret City", 4: "The Tree of Life", 5: "New Believers"}
HEAP, STACK = 0x20000000, 0x10000000
_IMAGES: dict = {}


def image(game: int, patched: bool) -> bytes:
    key = (game, patched)
    if key not in _IMAGES:
        exe = STOCK / f"Virtual Villagers - {NAMES[game]}.exe"
        if patched:
            build = next(b for b in vfp.load_builds() if b.id == f"vv{game}")
            data, _ = vfp.render_patched_bytes(exe, build, "immediate_fixed", [f"vv{game}_write_village_statistics"])
            data = bytes(data)
        else:
            data = exe.read_bytes()
        _IMAGES[key] = pefile.PE(data=data, fast_load=True).get_memory_mapped_image()
    return _IMAGES[key]


def machine(game: int, patched: bool) -> Uc:
    img = image(game, patched)
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    mu.mem_map(0x400000, (len(img) + 0xFFF) & ~0xFFF)
    mu.mem_write(0x400000, img)
    mu.mem_map(HEAP, 0x4000000)
    mu.mem_map(STACK - 0x10000, 0x20000)
    mu.reg_write(UC_X86_REG_ESP, STACK)
    return mu


def rd(mu, a):
    return struct.unpack("<i", mu.mem_read(a, 4))[0]


class LostChildrenPointsEarnedTests(unittest.TestCase):
    # 0x463734: push edi; mov ecx,ebp; call 0x426290; mov eax,[esi+0xE574D4];
    # (stock: add [eax+0x2E4FC],edi); jmp 0x4637C5
    def run_path(self, patched, amount=37):
        mu = machine(2, patched)
        container = HEAP + 0x100000
        esi = HEAP
        mu.mem_write(esi + 0xE574D4, struct.pack("<I", container))
        mu.reg_write(UC_X86_REG_ESI, esi)
        mu.reg_write(UC_X86_REG_EBP, container)
        mu.reg_write(UC_X86_REG_EDI, amount)
        mu.emu_start(0x463734, 0x4637C5, count=200)
        return rd(mu, container + 0x2E4FC), rd(mu, container + 0x2EADC)

    def test_the_award_is_counted_once(self):
        self.assertEqual(self.run_path(True), (37, 37), "Points Earned once, spendable tech once")

    def test_stock_counted_it_twice(self):
        self.assertEqual(self.run_path(False), (74, 37))


class PeopleCuredTests(unittest.TestCase):
    # (je site, the +1's target address, counter address, instruction after the +1)
    SITES = {3: (0x45B968, 0x5824B0, 0x45B977), 4: (0x465179, 0x4D6DF0, 0x465189),
             5: (0x46E1F9, 0x51D368, 0x46E209)}

    def run_branch(self, game, patched, cured):
        je, counter, after = self.SITES[game]
        mu = machine(game, patched)
        mu.reg_write(UC_X86_REG_EDI, HEAP + 0x1000)          # the villager record the success path clears
        mu.reg_write(UC_X86_REG_EAX, 1 if cured else 0)
        mu.emu_start(je - 2, after, count=20)                 # test al, al; je ...
        return rd(mu, counter), mu.reg_read(UC_X86_REG_EIP)

    def test_only_a_cure_counts(self):
        for game in self.SITES:
            with self.subTest(game=game):
                self.assertEqual(self.run_branch(game, True, cured=True)[0], 1)
                self.assertEqual(self.run_branch(game, True, cured=False)[0], 0)
                # both outcomes continue where stock goes after the +1
                self.assertEqual(self.run_branch(game, True, cured=False)[1], self.SITES[game][2])

    def test_stock_counted_failures(self):
        for game in self.SITES:
            with self.subTest(game=game):
                self.assertEqual(self.run_branch(game, False, cured=False)[0], 1)


class SecretCityOriginsCureCountsTests(unittest.TestCase):
    """The Secret City's Origins "Cure all" credits People Cured where the
    stock cure does: the live statistics block (0x5824A0) +0x10. It used to
    increment [manager+0x4FC], the block's save-time copy (manager+0x4EC),
    which every save overwrites from the live block -- so Origins cures were
    never counted (corruption audit, 2026-09-30)."""

    LIVE_INC = bytes.fromhex("FF05B0245800")      # inc dword ptr [0x5824B0]
    COPY_INC = bytes.fromhex("FF87FC040000")      # inc dword ptr [edi+0x4FC]

    def test_the_stock_cure_increments_the_same_live_counter(self):
        path = STOCK / "Virtual Villagers - The Secret City.exe"
        if not path.exists():
            self.skipTest("stock executable not available")
        pe = pefile.PE(str(path), fast_load=True)
        off = pe.get_offset_from_rva(0x45B971 - pe.OPTIONAL_HEADER.ImageBase)
        self.assertEqual(pe.__data__[off:off + 6], self.LIVE_INC)

    def test_the_origins_cure_increments_the_live_counter(self):
        import json
        manifest = json.loads((ROOT / "data" / "vv3_origins_feature.json").read_text(encoding="utf-8"))
        cure = [bytes.fromhex(p["after"]) for p in manifest["patches"] if "clear sickness" in p.get("purpose", "")]
        self.assertEqual(len(cure), 1)
        self.assertEqual(cure[0].count(self.LIVE_INC), 1)
        for patch in manifest["patches"]:
            self.assertNotIn(self.COPY_INC, bytes.fromhex(patch["after"]), patch.get("purpose"))


if __name__ == "__main__":
    unittest.main()
