"""Locate likely statistics blocks in Virtual Villagers save files."""

from __future__ import annotations

import argparse
import struct
from pathlib import Path


def pe_va_to_offset(payload: bytes, va: int) -> int:
    pe_offset = struct.unpack_from("<I", payload, 0x3C)[0]
    section_count = struct.unpack_from("<H", payload, pe_offset + 6)[0]
    optional_size = struct.unpack_from("<H", payload, pe_offset + 20)[0]
    optional = pe_offset + 24
    image_base = struct.unpack_from("<I", payload, optional + 28)[0]
    rva = va - image_base
    section_table = optional + optional_size
    for index in range(section_count):
        header = section_table + index * 40
        virtual_size, virtual_address, raw_size, raw_offset = struct.unpack_from(
            "<IIII", payload, header + 8
        )
        if virtual_address <= rva < virtual_address + max(virtual_size, raw_size):
            return raw_offset + rva - virtual_address
    raise ValueError(f"VA {va:#x} is not backed by a PE section")


def pe_offset_to_va(payload: bytes, raw_offset: int) -> int:
    pe_offset = struct.unpack_from("<I", payload, 0x3C)[0]
    section_count = struct.unpack_from("<H", payload, pe_offset + 6)[0]
    optional_size = struct.unpack_from("<H", payload, pe_offset + 20)[0]
    optional = pe_offset + 24
    image_base = struct.unpack_from("<I", payload, optional + 28)[0]
    section_table = optional + optional_size
    for index in range(section_count):
        header = section_table + index * 40
        virtual_size, virtual_address, raw_size, section_raw = struct.unpack_from(
            "<IIII", payload, header + 8
        )
        if section_raw <= raw_offset < section_raw + raw_size:
            return image_base + virtual_address + raw_offset - section_raw
    raise ValueError(f"raw offset {raw_offset:#x} is not backed by a PE section")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("save", type=Path)
    parser.add_argument("--start", type=int)
    parser.add_argument("--end", type=int)
    parser.add_argument("--values", nargs="*", type=int)
    parser.add_argument("--exe-va", type=lambda value: int(value, 0))
    args = parser.parse_args()

    payload = args.save.read_bytes()
    if args.exe_va is not None:
        raw_offset = pe_va_to_offset(payload, args.exe_va)
        needle = struct.pack("<I", args.exe_va)
        pointers = [
            offset
            for offset in range(len(payload) - 3)
            if payload.startswith(needle, offset)
        ]
        pointer_details = [
            (hex(offset), hex(pe_offset_to_va(payload, offset))) for offset in pointers
        ]
        print(f"raw_offset={raw_offset:#x} pointers={pointer_details}")
        return
    if args.values:
        wanted = set(args.values)
        hits = []
        for offset in range(len(payload) - 3):
            value = struct.unpack_from("<I", payload, offset)[0]
            if value in wanted:
                hits.append((offset, value))
        counts: dict[int, int] = {}
        left = 0
        best: tuple[int, int] | None = None
        for right, (_, value) in enumerate(hits):
            counts[value] = counts.get(value, 0) + 1
            while len(counts) == len(wanted):
                span = hits[right][0] - hits[left][0]
                if best is None or span < best[1] - best[0]:
                    best = (left, right)
                left_value = hits[left][1]
                counts[left_value] -= 1
                if counts[left_value] == 0:
                    del counts[left_value]
                left += 1
        if best is None:
            found = sorted({value for _, value in hits})
            print(f"missing={sorted(wanted - set(found))} found={found}")
            return
        chosen = hits[best[0] : best[1] + 1]
        print(f"span={chosen[-1][0] - chosen[0][0]} bytes")
        for offset, value in chosen:
            print(f"{offset:08X} {offset:7d} {value:10d}")
        return

    if args.start is None or args.end is None:
        parser.error("use --values or both --start and --end")
    end = min(args.end, len(payload) - 3)
    for offset in range(args.start, end, 4):
        value = struct.unpack_from("<I", payload, offset)[0]
        if value:
            print(f"{offset:08X} {offset:7d} {value:10d}")


if __name__ == "__main__":
    main()
