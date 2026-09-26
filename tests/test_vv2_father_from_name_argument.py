"""VV2's conception hook recovers the father's record from the name argument.

sub_44B980, VV2's conception routine, takes the father's NAME as its fifth
argument and sprintf's it onto the mother (0x44BA20 reads [esp+0x1C]). Every
caller that holds the father's record builds that argument as
`lea reg, [father + 0x564]` -- a pointer to the name field inside his record --
so the record is that argument minus 0x564.

The hook used to select the father by return address, and knew four of the six
callers. The Love Note's pregnancy (0x422006) was not among them, so the
owner's first v1.35.27 VV2 tribe logged the father's age, likes and dislikes as
"(not captured for this birth)". The Gong (0x44EB3E) passes the game's own "?"
placeholder string, which is not inside any record, so it must and does stay
fatherless.

Pinned two ways: the stock callers still build argument 5 the way the rule
assumes (when the stock executable is present), and the shipped trampoline
applies the rule.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data/vv2_parentage_feature.json"
STOCK = ROOT / "research/stock-executables/Virtual Villagers - The Lost Children.exe"
IMAGE_BASE = 0x400000

try:
    import pefile
    from capstone import CS_ARCH_X86, CS_MODE_32, Cs

    HAVE_TOOLS = True
except ImportError:  # pragma: no cover - optional analysis tools
    HAVE_TOOLS = False

# caller -> the register whose record is argument 5, or None for a caller whose
# argument 5 is not a record's name.
CALLERS = {
    0x422006: "eax",   # Love Note
    0x44EB3E: None,    # Gong grants life
    0x44F8F0: "ebx",
    0x44F930: "edi",
    0x464A38: "edi",
    0x464C4D: "edi",
}
CONCEPTION_ROUTINE = 0x44B980


class VV2FatherFromNameArgument(unittest.TestCase):
    def trampoline(self) -> bytes:
        feature = json.loads(MANIFEST.read_text(encoding="utf-8"))["features"][0]
        patches = feature["composition_patches"]["vv2_enable_origins_exclusive_features"]
        (cave,) = [p for p in patches if p["offset"].upper() == "0XB241A"]
        return bytes.fromhex(cave["after"])

    def test_the_trampoline_takes_argument_five_minus_the_name_offset(self) -> None:
        code = self.trampoline()
        # mov edx,[esp+0x3C] ; test edx,edx ; jz +6 ; sub edx,0x564 ; push edx
        self.assertIn(bytes.fromhex("8B54243C85D2740681EA6405000052"), code)

    def test_the_return_address_selector_is_gone(self) -> None:
        code = self.trampoline()
        for address in (0x44F8F5, 0x44F935, 0x464A3D, 0x464C52):
            self.assertNotIn(address.to_bytes(4, "little"), code)

    @unittest.skipUnless(HAVE_TOOLS and STOCK.is_file(), "stock VV2 or pefile/capstone absent")
    def test_every_stock_caller_builds_argument_five_as_the_rule_assumes(self) -> None:
        pe = pefile.PE(str(STOCK))
        raw = STOCK.read_bytes()
        md = Cs(CS_ARCH_X86, CS_MODE_32)

        text = [s for s in pe.sections if s.Name.startswith(b".text")][0]
        start = IMAGE_BASE + text.VirtualAddress
        data = text.get_data()
        found = set()
        for i in range(len(data) - 5):
            if data[i] == 0xE8:
                rel = int.from_bytes(data[i + 1:i + 5], "little", signed=True)
                if start + i + 5 + rel == CONCEPTION_ROUTINE:
                    found.add(start + i)
        self.assertEqual(found, set(CALLERS), "the set of stock callers changed")

        for call, register in CALLERS.items():
            with self.subTest(caller=hex(call)):
                instructions = None
                for back in range(0x90, 0x40, -1):
                    offset = pe.get_offset_from_rva(call - back - IMAGE_BASE)
                    decoded = list(md.disasm(raw[offset:offset + back + 5], call - back))
                    if decoded and decoded[-1].address == call:
                        instructions = decoded
                        break
                self.assertIsNotNone(instructions)
                if register is None:
                    # The Gong. Its argument 5 is `push 0x476290`, the game's
                    # own "?" placeholder in .rdata -- not a name inside any
                    # record, so the companion's slot check refuses
                    # 0x476290 - 0x564 and the birth stays fatherless. (Its
                    # argument list is interleaved with a separate cdecl call,
                    # push 0x32 / call 0x4031A0 / add esp,4, so the pushes
                    # cannot simply be counted here.)
                    self.assertTrue(any(
                        x.mnemonic == "push" and x.op_str == "0x476290"
                        for x in instructions))
                    offset = pe.get_offset_from_rva(0x476290 - IMAGE_BASE)
                    self.assertEqual(raw[offset:offset + 2], b"?\x00")
                    continue
                pushes = [x for x in instructions if x.mnemonic == "push"]
                fifth = pushes[-5]  # pushed right to left: arg1 is last
                lea = [
                    x for x in instructions
                    if x.address < fifth.address
                    and x.mnemonic == "lea"
                    and x.op_str == f"{fifth.op_str}, [{register} + 0x564]"
                ]
                self.assertTrue(lea, f"argument 5 at {call:#x} is not [{register} + 0x564]")


if __name__ == "__main__":
    unittest.main()
