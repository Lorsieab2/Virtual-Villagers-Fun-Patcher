"""No shipped companion DLL gives one function a stack frame of 64 KB or more.

The companions run on the GAME's thread, on its 1 MB stack (every game's executable reserves 0x100000), and often
from deep inside the game: the Statistics and Population exports run inside the save, and The Lost Children's save
routine alone already holds a 193 KB frame there.  The exporters once kept their 64 KB path buffers on the stack --
about 900 KB between them at a save -- which overflowed a 256 KB stack in population_export_harness.c (c00000fd).
Large buffers are static or on the heap instead.

Read from the shipped DLLs themselves: every `mov eax, N ; call _chkstk` (MSVC's probe for frames of 4 KB and more)
and every `sub esp, N`.
"""
from __future__ import annotations

import re
import struct
import unittest
from pathlib import Path

import pefile

ROOT = Path(__file__).resolve().parents[1]
LIMIT = 0x10000
# MSVC's x86 _chkstk / _alloca_probe: push ecx ; lea ecx, [esp+4] (today's), or cmp eax, 0x1000 (the games' own,
# an older MSVC).
CHKSTK = (bytes.fromhex("518D4C2404"), bytes.fromhex("3D00100000"))


def shipped_dlls() -> list[Path]:
    return sorted((ROOT / "assets").rglob("*.dll")) + sorted((ROOT / "data" / "candidates").glob("*.dll"))


def large_frames(path: Path) -> list[tuple[int, int]]:
    pe = pefile.PE(str(path), fast_load=True)
    base = pe.OPTIONAL_HEADER.ImageBase
    image = pe.get_memory_mapped_image()
    found = []
    for section in pe.sections:
        if not section.Characteristics & 0x20000000:
            continue
        data = section.get_data()
        va = base + section.VirtualAddress
        for m in re.finditer(rb"\xB8(....)\xE8(....)", data, re.S):
            size = struct.unpack("<I", m.group(1))[0]
            target = va + m.start() + 10 + struct.unpack("<i", m.group(2))[0] - base
            if size >= LIMIT and 0 <= target < len(image) and bytes(image[target:target + 6]).startswith(CHKSTK):
                found.append((va + m.start(), size))
        for m in re.finditer(rb"\x81\xEC(....)", data, re.S):
            size = struct.unpack("<I", m.group(1))[0]
            if LIMIT <= size < 0x1000000:
                found.append((va + m.start(), size))
    return found


class CompanionStackFrames(unittest.TestCase):
    def test_the_check_sees_a_large_frame(self):
        """The reader is not blind: the stock Lost Children save routine's 0x30434-byte frame is seen."""
        stock = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Lost Children.exe"
        if not stock.is_file():
            self.skipTest(f"stock executable not available: {stock.name}")
        self.assertIn(0x30434, [n for a, n in large_frames(stock) if 0x4249A0 <= a < 0x4249C0])

    def test_no_companion_frame_reaches_64_kb(self):
        dlls = shipped_dlls()
        self.assertGreater(len(dlls), 50)
        for dll in dlls:
            with self.subTest(dll=dll.name):
                self.assertEqual([], [f"{a:#x}: {n:#x} bytes" for a, n in large_frames(dll)])


if __name__ == "__main__":
    unittest.main()
