#!/usr/bin/env python3
"""Map IDA-named CEvent vtables in a PE file to their function entries."""

from __future__ import annotations

import argparse
import re
import struct
from pathlib import Path


VTABLE_RE = re.compile(
    r"(?P<va>[0-9A-F]{8}).*?C7 00 (?P<bytes>(?:[0-9A-F]{2} ){3}[0-9A-F]{2})"
    r".*?CEvent(?P<name>[A-Za-z0-9_]+)::`vftable'",
)


def u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def pe_layout(data: bytes) -> tuple[int, list[tuple[int, int, int, int]]]:
    pe_offset = u32(data, 0x3C)
    if data[pe_offset : pe_offset + 4] != b"PE\0\0":
        raise ValueError("not a PE file")
    section_count = u16(data, pe_offset + 6)
    optional_size = u16(data, pe_offset + 20)
    optional = pe_offset + 24
    if u16(data, optional) != 0x10B:
        raise ValueError("only PE32 executables are supported")
    image_base = u32(data, optional + 28)
    section_table = optional + optional_size
    sections = []
    for index in range(section_count):
        entry = section_table + index * 40
        virtual_size = u32(data, entry + 8)
        virtual_address = u32(data, entry + 12)
        raw_size = u32(data, entry + 16)
        raw_offset = u32(data, entry + 20)
        sections.append((virtual_address, virtual_size, raw_offset, raw_size))
    return image_base, sections


def rva_to_offset(
    rva: int, sections: list[tuple[int, int, int, int]]
) -> int:
    for virtual_address, virtual_size, raw_offset, raw_size in sections:
        span = max(virtual_size, raw_size)
        if virtual_address <= rva < virtual_address + span:
            return raw_offset + rva - virtual_address
    raise ValueError(f"RVA 0x{rva:X} is outside mapped sections")


def load_function_names(path: Path) -> dict[int, str]:
    names: dict[int, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        fields = line.split("\t")
        if len(fields) >= 2 and fields[0].startswith("0x"):
            names[int(fields[0], 16)] = fields[1]
    return names


def load_vtables(path: Path) -> list[tuple[str, int]]:
    matches: dict[str, int] = {}
    text = path.read_text(encoding="utf-8", errors="replace")
    for match in VTABLE_RE.finditer(text):
        raw = bytes.fromhex(match.group("bytes"))
        matches[match.group("name")] = int.from_bytes(raw, "little")
    return sorted(matches.items())


def resolve_target(
    target: int,
    data: bytes,
    image_base: int,
    sections: list[tuple[int, int, int, int]],
) -> tuple[int, str]:
    """Follow a short chain of direct relative JMP thunks."""
    hops = []
    for _ in range(4):
        offset = rva_to_offset(target - image_base, sections)
        if data[offset] != 0xE9:
            break
        displacement = struct.unpack_from("<i", data, offset + 1)[0]
        destination = target + 5 + displacement
        hops.append(f"0x{target:08X}")
        target = destination
    return target, "->".join(hops)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("exe", type=Path)
    parser.add_argument("assembly", type=Path)
    parser.add_argument("functions", type=Path)
    parser.add_argument("--contains", default="")
    parser.add_argument("--entries", type=int, default=12)
    args = parser.parse_args()

    data = args.exe.read_bytes()
    image_base, sections = pe_layout(data)
    function_names = load_function_names(args.functions)
    needle = args.contains.casefold()

    for name, vtable_va in load_vtables(args.assembly):
        if needle and needle not in name.casefold():
            continue
        offset = rva_to_offset(vtable_va - image_base, sections)
        entries = []
        for index in range(args.entries):
            target = u32(data, offset + index * 4)
            if not image_base <= target < image_base + 0x1000000:
                break
            resolved, hops = resolve_target(target, data, image_base, sections)
            label = function_names.get(resolved, f"0x{resolved:08X}")
            if hops:
                label = f"{hops}->{label}"
            entries.append(f"{index}:{label}")
        print(f"CEvent{name}\t0x{vtable_va:08X}\t" + "\t".join(entries))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
