"""Clothmaking Unlocks at Science Level 3 (The Tree of Life): the vines' drop refuses below Science 3.  The traces are in
scripts/build_vv4_clothmaking_at_science_3_feature.py.

The drop handler 0x436D40 (its first case) is run stock and patched in unicorn at Science 1, 2 and 3 with the Clothing
Hut finished and unfinished; the action it starts (0x45DEC0's first argument) is recorded: 0x1A with the refusal
string 0x249, or 0x7A, cutting the pulpy vines.
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
import vv_fun_patcher_gui as gui  # noqa: E402

try:
    import pefile
    from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
    from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_EIP, UC_X86_REG_ESP
    HAVE = True
except ImportError:  # pragma: no cover
    HAVE = False

EXE = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Tree of Life.exe"
FEATURE = json.loads((ROOT / "data" / "vv4_clothmaking_at_science_3_feature.json").read_text("utf-8"))
HANDLER, FINISHED, START_ACTION, SCIENCE = 0x436D40, 0x438960, 0x45DEC0, 0x4D6F5C
STACK, RETURN = 0x0100_0000, 0x0100_F000


def drop(patched: bool, science: int, finished: bool) -> tuple[int, int]:
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
    uc.mem_map(SCIENCE & ~0xFFF, 0x1000)
    uc.mem_write(SCIENCE, struct.pack("<i", science))
    uc.mem_map(STACK, 0x10000)
    got = []

    def hook(uc, address, size, _):
        esp = uc.reg_read(UC_X86_REG_ESP)
        ret = struct.unpack("<I", uc.mem_read(esp, 4))[0]
        if address == FINISHED:                      # thiscall, 1 argument
            uc.reg_write(UC_X86_REG_EAX, int(finished))
            uc.reg_write(UC_X86_REG_ESP, esp + 8)
        elif address == START_ACTION:                # thiscall, 2 arguments: the action, a pointer to its data
            action = struct.unpack("<i", uc.mem_read(esp + 4, 4))[0]
            arg = struct.unpack("<I", uc.mem_read(esp + 8, 4))[0]
            got.append((action, struct.unpack("<i", uc.mem_read(arg, 4))[0]))
            uc.reg_write(UC_X86_REG_ESP, esp + 12)
        else:
            return
        uc.reg_write(UC_X86_REG_EIP, ret)

    uc.hook_add(UC_HOOK_CODE, hook)
    esp = STACK + 0x8000
    uc.mem_write(esp, struct.pack("<III", RETURN, 0, 0x0100_4000))   # return, case 0, the villager
    uc.reg_write(UC_X86_REG_ESP, esp)
    uc.emu_start(HANDLER, RETURN, count=200)
    assert len(got) == 1, got
    return got[0]


@unittest.skipUnless(HAVE, "unicorn / pefile not installed")
class Drop(unittest.TestCase):
    def setUp(self) -> None:
        if not EXE.is_file():
            self.skipTest("stock executable not present")

    def test_stock(self) -> None:
        for science in (1, 2, 3):
            self.assertEqual(drop(False, science, True)[0], 0x7A)
            self.assertEqual(drop(False, science, False), (0x1A, 0x249))

    def test_patched_waits_for_science_3(self) -> None:
        for science in (1, 2):
            self.assertEqual(drop(True, science, True), (0x1A, 0x249), science)
            self.assertEqual(drop(True, science, False), (0x1A, 0x249), science)
        self.assertEqual(drop(True, 3, True)[0], 0x7A)
        self.assertEqual(drop(True, 3, False), (0x1A, 0x249))


class Catalog(unittest.TestCase):
    def test_defaults_pair_and_classic(self) -> None:
        self.assertIn("vv4_clothmaking_at_science_3", {p.id for p in patcher.load_public_fun_patches()})
        self.assertFalse(gui.default_fun_patch_selection("vv4_clothmaking_at_science_3"))
        self.assertTrue(gui.owners_default_fun_patch_selection("vv4_clothmaking_at_science_3"))
        self.assertFalse(gui.owners_default_fun_patch_selection("vv4_no_fishing_at_science_2"))
        self.assertEqual(gui.UNTICKING_CONFLICT_IDS["vv4_clothmaking_at_science_3"], "vv4_no_fishing_at_science_2")
        classic = json.loads((ROOT / "data" / "vv4_classic_vv_difficulty_feature.json").read_text("utf-8"))
        self.assertIn("vv4_clothmaking_at_science_3", classic["dependencies"])
        self.assertNotIn("vv4_no_fishing_at_science_2", classic["dependencies"])


if __name__ == "__main__":
    unittest.main()
