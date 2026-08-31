"""MSVC inline assembly indexes arrays by BYTE, not by element.

`__asm { push arr[4] }` does not push `arr[4]`. It pushes the dword at
`arr + 4 bytes`, which for an int array is element 1 -- and `arr[5]` is an
UNALIGNED read straddling elements 1 and 2.

VV3's village-view mask draw was written that way. The shipped DLL pushed six
arguments from `[ebp-0x24]` down to `[ebp-0x1f]`, one byte apart instead of
four, so the renderer received garbage for x, y, row, column and scale; only
element 0 was right, by coincidence. The mask column fix that commit advertised
could never have taken effect.

Two guards, because either alone is escapable:

  * the SOURCE must not push an indexed array element, since the notation reads
    as element access to everyone who has not been bitten by this; and
  * the SHIPPED DLL must not contain a run of consecutive local pushes spaced
    one byte apart, which is the fingerprint of the bug surviving a rebuild.
"""
from __future__ import annotations

import re
import struct
import unittest
from pathlib import Path

from capstone import Cs, CS_ARCH_X86, CS_MODE_32

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "native"
VV3_DLL = ROOT / "data" / "candidates" / "VVFP VV3 Full Mastery Candidate.dll"

# `push name[12]` / `mov eax, name[4]` inside inline assembly.
INDEXED = re.compile(
    r"^\s*(?:push|pop|mov|lea|add|sub|cmp|test|and|or|xor)\s+"
    r"(?:[a-z]{2,3},\s*)?[A-Za-z_][A-Za-z0-9_]*\[\d+\]\s*(?:/\*.*)?$"
)


def _text_section(image: bytes):
    pe = struct.unpack_from("<I", image, 0x3C)[0]
    count = struct.unpack_from("<H", image, pe + 6)[0]
    opt = struct.unpack_from("<H", image, pe + 20)[0]
    base = struct.unpack_from("<I", image, pe + 24 + 28)[0]
    for i in range(count):
        off = pe + 24 + opt + i * 40
        if image[off : off + 8].rstrip(b"\0") == b".text":
            vsize, va, rsize, ptr = struct.unpack_from("<IIII", image, off + 8)
            return base + va, ptr, rsize
    raise AssertionError("no .text section")


def _asm_blocks(text: str) -> list[str]:
    """The bodies of every `__asm { ... }` block in a C source."""
    blocks, index = [], 0
    while True:
        start = text.find("__asm", index)
        if start == -1:
            return blocks
        brace = text.find("{", start)
        if brace == -1:
            return blocks
        depth, i = 0, brace
        while i < len(text):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        blocks.append(text[brace + 1 : i])
        index = i + 1


class InlineAsmArrayIndexingTests(unittest.TestCase):
    def test_no_inline_asm_indexes_an_array(self) -> None:
        offenders = []
        for source in sorted(NATIVE.rglob("*.c")):
            text = source.read_text(encoding="utf-8", errors="replace")
            for block in _asm_blocks(text):
                for line in block.splitlines():
                    if INDEXED.match(line):
                        offenders.append(f"{source.relative_to(ROOT)}: {line.strip()}")
        self.assertEqual(
            offenders,
            [],
            "inline assembly indexes an array by element, but MSVC reads the "
            "subscript as a BYTE offset; copy the values into scalars first:\n"
            + "\n".join(offenders),
        )

    def test_the_asm_block_scanner_actually_finds_blocks(self) -> None:
        """Without this the test above passes by scanning nothing."""
        seen = 0
        for source in sorted(NATIVE.rglob("*.c")):
            seen += len(_asm_blocks(source.read_text(encoding="utf-8", errors="replace")))
        self.assertGreater(seen, 8, "the __asm block scanner found almost nothing")

    def test_the_pattern_matches_the_shape_that_shipped(self) -> None:
        """Positive control for the regex."""
        self.assertTrue(INDEXED.match("        push mask_args[5]"))
        self.assertTrue(INDEXED.match("        mov eax, mask_args[16]"))
        self.assertIsNone(INDEXED.match("        push arg5"))
        self.assertIsNone(INDEXED.match("        mov ecx, VV3_WORLD_MGR"))

    @unittest.skipUnless(VV3_DLL.is_file(), "VV3 companion DLL is not built")
    def test_the_shipped_vv3_dll_has_no_byte_spaced_push_run(self) -> None:
        image = VV3_DLL.read_bytes()
        base_va, ptr, size = _text_section(image)
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        decoded = list(md.disasm(image[ptr : ptr + size], base_va))

        def local_offset(instruction):
            if instruction.mnemonic != "push" or "ebp -" not in instruction.op_str:
                return None
            return int(instruction.op_str.split("- ")[1].rstrip("]"), 16)

        runs, checked = [], 0
        for i in range(len(decoded) - 3):
            offsets = [local_offset(x) for x in decoded[i : i + 4]]
            if any(o is None for o in offsets):
                continue
            checked += 1
            gaps = {offsets[k] - offsets[k + 1] for k in range(3)}
            if gaps == {1}:
                runs.append(hex(decoded[i].address))
        self.assertEqual(
            runs,
            [],
            "consecutive local pushes one byte apart in the shipped VV3 DLL -- "
            "that is the MSVC array-subscript bug back again, at: "
            + ", ".join(runs),
        )
        self.assertGreater(
            checked, 0, "no local push runs were examined; the scan is broken"
        )


if __name__ == "__main__":
    unittest.main()
