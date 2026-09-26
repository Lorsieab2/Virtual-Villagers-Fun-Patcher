"""VV1's Golden Child is the villager whose record holds 0xC7 at +0x36C.

Four VV1 Origins upgrades exclude the Golden Child -- Time Warp, Set Age to 18
(per villager and village-wide), Equal Division and Change Appearance for
All's VV5-style distribution. They identified it by comparing each villager
against dword ptr [0x48B614], believed to be a "current Golden Child" pointer.
It is the villager ARRAY: the stock getter at 0x43DA30 allocates 0x3E034 bytes
for it, and record 0 is the allocation itself (vv1_sort_by.c and
vv1_parentage.c read it exactly that way). So each check matched whoever sat
in record 0. In the owner's v1.35.27 tribe that was Sef, who was not aged by a
Time Warp that aged everyone else by 120 units -- which is why his "Age at
conception" matched his current age.

The game's own test is `cmp dword ptr [rec+0x36C], 0xC7`, made in six places;
the aging tick at 0x42E5A4 is how the real Golden Child stays a child.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research/stock-executables/Virtual Villagers - A New Home.exe"
DLL_SOURCE = ROOT / "native/vv1_origins_icons/vv1_origins_icons.c"
MANIFESTS = (
    ROOT / "data/vv1_origins_feature.json",
    ROOT / "data/vv1_origins_village_wide_upgrades.json",
)
IMAGE_BASE = 0x400000
GAME_CHECKS = (0x41FBDC, 0x42242D, 0x424B56, 0x42E5A4, 0x438982, 0x43C7AF)

try:
    import pefile
    from capstone import CS_ARCH_X86, CS_MODE_32, Cs

    HAVE_TOOLS = True
except ImportError:  # pragma: no cover - optional analysis tools
    HAVE_TOOLS = False


class VV1GoldenChildIsARecordFlag(unittest.TestCase):
    @unittest.skipUnless(HAVE_TOOLS and STOCK.is_file(), "stock VV1 or pefile/capstone absent")
    def test_the_game_tests_the_flag_itself(self) -> None:
        pe = pefile.PE(str(STOCK))
        raw = STOCK.read_bytes()
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        for address in GAME_CHECKS:
            with self.subTest(address=hex(address)):
                offset = pe.get_offset_from_rva(address - IMAGE_BASE)
                (instruction,) = list(md.disasm(raw[offset:offset + 16], address, 1))
                self.assertEqual(instruction.mnemonic, "cmp")
                self.assertTrue(instruction.op_str.endswith("0x36c], 0xc7"), instruction.op_str)

    @unittest.skipUnless(HAVE_TOOLS and STOCK.is_file(), "stock VV1 or pefile/capstone absent")
    def test_0x48b614_is_the_villager_array(self) -> None:
        """The getter allocates the whole 0x3E034-byte table into it."""
        pe = pefile.PE(str(STOCK))
        raw = STOCK.read_bytes()
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        offset = pe.get_offset_from_rva(0x43DA46 - IMAGE_BASE)
        text = [f"{i.mnemonic} {i.op_str}" for i in md.disasm(raw[offset:offset + 0x50], 0x43DA46)]
        self.assertIn("mov eax, dword ptr [0x48b614]", text)
        self.assertIn("push 0x3e034", text)
        self.assertIn("mov dword ptr [0x48b614], eax", text)

    def test_no_shipped_vv1_code_compares_against_0x48b614(self) -> None:
        for manifest in MANIFESTS:
            with self.subTest(manifest=manifest.name):
                text = json.dumps(json.loads(manifest.read_text(encoding="utf-8"))).upper()
                # cmp reg, dword ptr [0x48B614] encodes the address little-endian.
                self.assertNotIn("14B64800", text)

    def test_the_shipped_exe_code_tests_the_flag(self) -> None:
        # cmp dword ptr [edx|ebx|esi + 0x36C], 0xC7
        patterns = ("81BA6C030000C7000000", "81BB6C030000C7000000", "81BE6C030000C7000000")
        total = 0
        for manifest in MANIFESTS:
            text = json.dumps(json.loads(manifest.read_text(encoding="utf-8"))).upper()
            total += sum(text.count(p) for p in patterns)
        self.assertEqual(total, 4, "Set Age x1, Equal Division x2, village-wide age x1")

    def test_the_dll_tests_the_flag(self) -> None:
        source = DLL_SOURCE.read_text(encoding="utf-8")
        self.assertIn("#define VV_GOLDEN_CHILD_OFFSET 0x36C", source)
        self.assertIn("#define VV_GOLDEN_CHILD_MARK   0xC7", source)
        self.assertNotIn("VV_GOLDEN_CHILD_PTR", source)
        self.assertNotIn("(*(unsigned char **)0x0048B614)", source)


if __name__ == "__main__":
    unittest.main()
