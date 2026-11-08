"""Collectible Spawn Timing works like VV1-3 (The Tree of Life): the random spawn roll at The Secret City's 3 in 6,000.
The traces are in scripts/build_collectible_spawn_like_vv3_feature.py.

The roll block 0x41437E..0x4143E3 is run stock and patched in unicorn for fair weather, rain, fog with 0 to 12 Wind
Flute pieces and heavy weather, finding the highest rand(6000) result that still spawns.
"""
from __future__ import annotations

import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher as patcher  # noqa: E402
from vv_fun_patcher_gui import default_fun_patch_selection, owners_default_fun_patch_selection  # noqa: E402

try:
    import pefile
    from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
    from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_EIP, UC_X86_REG_ESP
    HAVE = True
except ImportError:  # pragma: no cover
    HAVE = False

EXE = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Tree of Life.exe"
FEATURE = json.loads((ROOT / "data" / "vv4_collectible_spawn_like_vv3_feature.json").read_text("utf-8"))
START, END = 0x41437E, 0x4143E3
RAND, PIECES, PLACE = 0x4036D0, 0x413B90, 0x413EE0
WEATHER, STRENGTH = 0x6C461C, 0x6C4634
_EMU = {}


def emulator(patched: bool):
    if patched not in _EMU:
        data = bytearray(EXE.read_bytes())
        if patched:
            for p in FEATURE["patches"]:
                at, before, after = int(p["offset"], 16), bytes.fromhex(p["before"]), bytes.fromhex(p["after"])
                assert data[at:at + len(before)] == before
                data[at:at + len(after)] = after
        pe = pefile.PE(data=bytes(data), fast_load=True)
        base = pe.OPTIONAL_HEADER.ImageBase
        text = next(s for s in pe.sections if s.Name.startswith(b".text"))
        lo = (base + text.VirtualAddress) & ~0xFFF
        uc = Uc(UC_ARCH_X86, UC_MODE_32)
        uc.mem_map(lo, ((base + text.VirtualAddress + text.Misc_VirtualSize + 0xFFF) & ~0xFFF) - lo)
        uc.mem_write(base + text.VirtualAddress, bytes(data[text.PointerToRawData:text.PointerToRawData
                                                           + text.SizeOfRawData][:text.Misc_VirtualSize]))
        uc.mem_map(0x6C4000, 0x1000)
        uc.mem_map(0x0100_0000, 0x10000)
        state = {"rolls": [], "pieces": 0, "placed": 0}

        def hook(uc, address, size, _):
            esp = uc.reg_read(UC_X86_REG_ESP)
            ret = struct.unpack("<I", uc.mem_read(esp, 4))[0]
            if address == RAND:                       # cdecl, caller pops
                uc.reg_write(UC_X86_REG_EAX, state["rolls"].pop(0) if state["rolls"] else 5999)
                uc.reg_write(UC_X86_REG_ESP, esp + 4)
            elif address == PIECES:                   # thiscall, 4 arguments
                uc.reg_write(UC_X86_REG_EAX, state["pieces"])
                uc.reg_write(UC_X86_REG_ESP, esp + 4 + 16)
            elif address == PLACE:                    # thiscall, ret 0xC
                state["placed"] += 1
                uc.reg_write(UC_X86_REG_ESP, esp + 4 + 12)
            else:
                return
            uc.reg_write(UC_X86_REG_EIP, ret)

        uc.hook_add(UC_HOOK_CODE, hook)
        _EMU[patched] = (uc, state)
    return _EMU[patched]


def spawns(patched: bool, weather: int, strength: int, first: int, second: int = 5999, pieces: int = 0) -> bool:
    uc, state = emulator(patched)
    uc.mem_write(WEATHER, struct.pack("<i", weather))
    uc.mem_write(STRENGTH, struct.pack("<i", strength))
    state.update(rolls=[first, second], pieces=pieces, placed=0)
    uc.reg_write(UC_X86_REG_ESP, 0x0100_8000)
    uc.emu_start(START, END, count=500)
    return state["placed"] == 1


def threshold(patched: bool, weather: int, strength: int = 0, pieces: int = 0) -> int:
    return sum(spawns(patched, weather, strength, r, pieces=pieces) for r in range(0, 30))


@unittest.skipUnless(HAVE, "unicorn / pefile not installed")
class Rolls(unittest.TestCase):
    def setUp(self) -> None:
        if not EXE.is_file():
            self.skipTest("stock executable not present")

    def test_fair_weather_and_rain_take_the_secret_citys_3(self) -> None:
        for weather in (0, 1, 2, 3, 5):
            with self.subTest(weather=weather):
                self.assertEqual(threshold(False, weather), 4)
                self.assertEqual(threshold(True, weather), 3)

    def test_fog_keeps_the_wind_flute_chance(self) -> None:
        for pieces in range(13):
            with self.subTest(pieces=pieces):
                self.assertEqual(threshold(True, 4, pieces=pieces), threshold(False, 4, pieces=pieces))
                self.assertEqual(threshold(True, 4, pieces=pieces), pieces // 2 * 4)

    def test_the_heavy_weather_second_roll(self) -> None:
        for patched, limit in ((False, 4), (True, 3)):
            hits = sum(spawns(patched, 0, 60, 5999, second=r) for r in range(30))
            self.assertEqual(hits, limit, patched)
            self.assertFalse(spawns(patched, 0, 50, 5999, second=0), "no second roll at 50 or less")


class Catalog(unittest.TestCase):
    def test_vv4_only_off_by_default_in_classic(self) -> None:
        ids = {p.id for p in patcher.load_public_fun_patches()}
        self.assertIn("vv4_collectible_spawn_like_vv3", ids)
        self.assertNotIn("vv5_collectible_spawn_like_vv3", ids)
        self.assertFalse(default_fun_patch_selection("vv4_collectible_spawn_like_vv3"))
        self.assertTrue(owners_default_fun_patch_selection("vv4_collectible_spawn_like_vv3"))
        classic = json.loads((ROOT / "data" / "vv4_classic_vv_difficulty_feature.json").read_text("utf-8"))
        self.assertIn("vv4_collectible_spawn_like_vv3", classic["dependencies"])


if __name__ == "__main__":
    unittest.main()
