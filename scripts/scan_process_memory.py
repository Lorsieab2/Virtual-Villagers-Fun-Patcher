"""Find a file byte range in a running Windows process."""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
from pathlib import Path


PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
MEM_COMMIT = 0x1000
PAGE_GUARD = 0x100
PAGE_NOACCESS = 0x01


class MemoryBasicInformation(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", wintypes.DWORD),
        ("PartitionId", wintypes.WORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", wintypes.DWORD),
        ("Protect", wintypes.DWORD),
        ("Type", wintypes.DWORD),
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pid", type=int)
    parser.add_argument("needle_file", type=Path)
    parser.add_argument("offset", type=lambda value: int(value, 0))
    parser.add_argument("length", type=lambda value: int(value, 0))
    parser.add_argument("--count-only", action="store_true")
    args = parser.parse_args()

    needle = args.needle_file.read_bytes()[args.offset : args.offset + args.length]
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    process = kernel32.OpenProcess(
        PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, args.pid
    )
    if not process:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        address = 0
        information = MemoryBasicInformation()
        hits: list[int] = []
        while address < 0x80000000:
            result = kernel32.VirtualQueryEx(
                process,
                ctypes.c_void_p(address),
                ctypes.byref(information),
                ctypes.sizeof(information),
            )
            if not result:
                break
            base = int(information.BaseAddress or 0)
            size = int(information.RegionSize)
            readable = (
                information.State == MEM_COMMIT
                and not information.Protect & PAGE_GUARD
                and information.Protect != PAGE_NOACCESS
            )
            if readable and 0 < size <= 64 * 1024 * 1024:
                buffer = ctypes.create_string_buffer(size)
                read = ctypes.c_size_t()
                if kernel32.ReadProcessMemory(
                    process,
                    ctypes.c_void_p(base),
                    buffer,
                    size,
                    ctypes.byref(read),
                ):
                    data = buffer.raw[: read.value]
                    start = 0
                    while True:
                        found = data.find(needle, start)
                        if found < 0:
                            break
                        hits.append(base + found)
                        start = found + 1
            address = base + max(size, 0x1000)
        if args.count_only:
            print(len(hits))
        else:
            for hit in hits:
                print(f"0x{hit:08X}")
        return 0 if hits else 1
    finally:
        kernel32.CloseHandle(process)


if __name__ == "__main__":
    raise SystemExit(main())
