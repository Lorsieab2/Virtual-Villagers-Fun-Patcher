"""The villager byte the mask feature owns must actually be free.

The first choice, +0x374, was the second byte of the villager's NAME string
at +0x370 -- a live record read back "Nuru" there. Writing a mask value
renamed the villager, and the render's 1..5 range check then rejected the
byte (it held 'u' = 117), so nothing drew and the corruption was silent.

The reasoning that picked it was "no literal [reg + 0x374] displacement
appears in .text". That is necessary but NOT sufficient: the name is written
by a string copy, so it has no displacement reference either.

+0x3D4 is verified differently. It has exactly one reference in the whole
executable -- the record initialiser zeroing it at creation -- and nothing
reads it or writes it again. These tests pin that, and pin that the DLL and
the patch agree on the offset, since they are two files and a disagreement
would put the picker and the renderer on different bytes.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import capstone
    import pefile

    HAVE_DEPS = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_DEPS = False

STOCK = ROOT / "inputs" / "vv1-stock-copy" / "Virtual Villagers - A New Home.exe"
DLL_SOURCE = ROOT / "native" / "vv1_origins_icons" / "vv1_origins_icons.c"
PATCH_SOURCE = ROOT / "scripts" / "build_vv1_origins_feature.py"

# The one legitimate reference: the record initialiser zeroing the field.
RECORD_INITIALISER = 0x41C344
# A byte the feature must never claim: the villager's name lives here.
NAME_FIELD = 0x370


def _dll_offset() -> int:
    text = DLL_SOURCE.read_text(encoding="utf-8")
    return int(re.search(r"#define VV_MASK_OFFSET (0x[0-9A-Fa-f]+)", text).group(1), 16)


def _patch_offset() -> int:
    text = PATCH_SOURCE.read_text(encoding="utf-8")
    return int(
        re.search(r"movzx edx, byte ptr \[eax \+ (0x[0-9a-f]+)\]", text).group(1), 16
    )


class VV1MaskFieldIsFreeTests(unittest.TestCase):
    def test_dll_and_patch_agree_on_the_field(self) -> None:
        self.assertEqual(
            _dll_offset(),
            _patch_offset(),
            "the picker writes one byte and the renderer reads another",
        )

    def test_field_is_not_inside_the_name_string(self) -> None:
        offset = _dll_offset()
        self.assertFalse(
            NAME_FIELD <= offset < NAME_FIELD + 0x20,
            f"{offset:#x} lands in the villager name at {NAME_FIELD:#x}; writing "
            "there renames the villager",
        )

    @unittest.skipUnless(HAVE_DEPS, "requires capstone and pefile")
    @unittest.skipUnless(STOCK.exists(), "requires the exact-build VV1 executable")
    def test_stock_code_only_zero_initialises_the_field(self) -> None:
        offset = _dll_offset()
        pe = pefile.PE(str(STOCK), fast_load=True)
        base = pe.OPTIONAL_HEADER.ImageBase
        image = pe.get_memory_mapped_image()
        text = next(s for s in pe.sections if s.Name.rstrip(b"\x00") == b".text")
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        body = image[text.VirtualAddress : text.VirtualAddress + text.Misc_VirtualSize]
        refs = [
            (i.address, f"{i.mnemonic} {i.op_str}")
            for i in md.disasm(body, base + text.VirtualAddress)
            if f"+ {hex(offset)}]" in i.op_str
        ]
        unexpected = [r for r in refs if r[0] != RECORD_INITIALISER]
        self.assertEqual(
            unexpected,
            [],
            f"stock code touches {offset:#x} outside the record initialiser, so it "
            "is real game state, not a free byte",
        )
        self.assertEqual(
            len(refs), 1, f"expected exactly the initialiser to touch {offset:#x}"
        )


if __name__ == "__main__":
    unittest.main()
