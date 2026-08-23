"""Fix the wrong-exe-name access-violation crash for VV5 (New Believers).

Root cause (diagnosed by the VV2 chat, confirmed present in VV5): the game reads
its own module filename via GetModuleFileNameA and derives name-gated behaviour
from the BASENAME -- the save folder Documents\\LDW\\<basename>\\ AND a name-gated
init/identity path. Renaming the exe (e.g. "... - Modded.exe" or a playtest
name) makes the basename mismatch the expected name, so initialization diverges,
leaving engine subsystems NULL; later code paths then dereference those NULLs and
walk unterminated record arrays -> 0xC0000005. VV5 caps its record scans at 150
so it may not always hard-fault the same way VV2 does, but it shares the same
basename-gated init root and must be immune under any filename.

Fix (root, name-independent): wrap GetModuleFileNameA so it always reports the
EXPECTED basename ("Virtual Villagers - New Believers.exe") while keeping the
REAL directory. Assets still load from the real folder (they use the directory);
the save folder and name-gated init use the correct name -> the game initializes
exactly as if the exe had the stock name, under ANY actual filename. No other
behaviour changes.

Implementation: a small .text cave holds the fixed basename + a stdcall wrapper
that calls the real GetModuleFileNameA (via the intact IAT), then overwrites the
buffer's basename (after the last '\\') with the fixed name and returns the new
length. Every `call [GetModuleFileNameA]` site is redirected to the wrapper.

The IAT slot and all call sites are discovered automatically, so this works on
the stock exe or any patched/deployed build (run it LAST, after VVFP features, so
the cave finder avoids feature caves). Idempotent: re-running finds no remaining
`call [IAT]` sites and reports nothing to do.

Usage: python scripts/fix_vv5_exe_name_crash.py <exe path> [--name "<Basename>.exe"]
"""
from __future__ import annotations

import argparse
import os
import shutil
import struct
import sys
from pathlib import Path

import keystone
import pefile

IMAGE_BASE = 0x400000
DEFAULT_NAME = "Virtual Villagers - New Believers.exe"


def _gmfn_iat(pe: pefile.PE) -> int:
    for d in pe.DIRECTORY_ENTRY_IMPORT:
        for imp in d.imports:
            if imp.name and imp.name.decode(errors="replace") == "GetModuleFileNameA":
                return imp.address
    raise SystemExit("this exe does not import GetModuleFileNameA")


def _text_section(pe: pefile.PE):
    for s in pe.sections:
        if s.Name.rstrip(b"\0") == b".text":
            return s
    raise SystemExit("no .text section")


def _call_sites(data: bytes, iat_va: int) -> list[int]:
    """Every `call dword ptr [iat_va]` (FF 15 <iat>) as a virtual address."""
    pattern = b"\xFF\x15" + struct.pack("<I", iat_va)
    out, start = [], 0
    while True:
        start = data.find(pattern, start)
        if start < 0:
            break
        out.append(IMAGE_BASE + start)  # .text is mapped 1:1 at file offset here
        start += 1
    return out


def _find_cave(data: bytes, text, need: int) -> int:
    seg = data[text.PointerToRawData:text.PointerToRawData + text.SizeOfRawData]
    i = 0
    while i < len(seg):
        if seg[i] == 0:
            j = i
            while j < len(seg) and seg[j] == 0:
                j += 1
            if j - i >= need + 4:
                return IMAGE_BASE + text.VirtualAddress + i + 2  # small alignment margin
            i = j
        else:
            i += 1
    raise SystemExit("no free .text cave found")


def _pe_checksum(buf: bytearray) -> tuple[int, int]:
    off = struct.unpack_from("<I", buf, 0x3C)[0]
    csum_off = off + 24 + 64
    struct.pack_into("<I", buf, csum_off, 0)
    total = 0
    padded = bytes(buf) + (b"\0" if len(buf) % 2 else b"")
    for i in range(0, len(padded), 2):
        total += padded[i] | (padded[i + 1] << 8)
        total = (total & 0xFFFF) + (total >> 16)
    total = (total & 0xFFFF) + (total >> 16)
    return ((total & 0xFFFF) + len(buf)) & 0xFFFFFFFF, csum_off


def build(data: bytearray, fixed_name: bytes) -> bytearray:
    """Return patched bytes (also usable as a pure transform for tests)."""
    # .text is loaded 1:1 with its file offset in these builds (VA == file off).
    pe = pefile.PE(data=bytes(data), fast_load=True)
    pe.parse_data_directories(
        directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]]
    )
    text = _text_section(pe)
    if text.PointerToRawData != text.VirtualAddress:
        raise SystemExit("unexpected .text mapping (VA != raw); site math would be wrong")
    iat = _gmfn_iat(pe)
    # Idempotency: once the wrapper is installed it contains its own legitimate
    # `call [IAT]`; re-running must not redirect that. The embedded fixed-name
    # string is the marker that the fix is already present.
    if fixed_name.rstrip(b"\x00") in bytes(data):
        print("already fixed (fixed basename string present) -- nothing to do")
        return data
    sites = _call_sites(bytes(data), iat)
    if not sites:
        print("no `call [GetModuleFileNameA]` sites remain -- already fixed / nothing to do")
        return data

    ks = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)

    def foff(va: int) -> int:
        return va - IMAGE_BASE

    def asm(code: str, addr: int) -> bytes:
        return bytes(ks.asm(code, addr=addr)[0])

    cave = _find_cave(bytes(data), text, need=len(fixed_name) + 128)
    name_va = cave
    code_va = (cave + len(fixed_name) + 3) & ~3

    wrapper = f"""
        push dword ptr [esp+0xc]              /* nSize */
        push dword ptr [esp+0xc]              /* lpFilename */
        push dword ptr [esp+0xc]              /* hModule */
        call dword ptr [0x{iat:X}]            /* real GetModuleFileNameA fills buffer */
        push esi
        push edi
        mov  edi, dword ptr [esp+0x10]        /* lpFilename */
        mov  edx, edi                         /* edx = basename start (default: buffer start) */
    scan:
        mov  cl, byte ptr [edi]
        test cl, cl
        je   done
        cmp  cl, 0x5c                         /* '\\' */
        jne  noslash
        lea  edx, [edi+1]
    noslash:
        inc  edi
        jmp  scan
    done:
        mov  esi, 0x{name_va:X}               /* fixed basename */
    cpy:
        mov  cl, byte ptr [esi]
        mov  byte ptr [edx], cl
        inc  esi
        inc  edx
        test cl, cl
        jne  cpy
        mov  eax, edx                         /* new length (excl. null) */
        sub  eax, dword ptr [esp+0x10]
        dec  eax
        pop  edi
        pop  esi
        ret  0xc
    """
    code = asm(wrapper, code_va)
    span = (code_va - cave) + len(code)
    if data[foff(cave):foff(cave) + span] != b"\0" * span:
        raise SystemExit("chosen cave is not free!")

    data[foff(name_va):foff(name_va) + len(fixed_name)] = fixed_name
    data[foff(code_va):foff(code_va) + len(code)] = code
    for s in sites:
        hook = asm(f"call 0x{code_va:X}", s)
        hook = hook + b"\x90" * (6 - len(hook))
        assert len(hook) == 6, "redirect hook must be 6 bytes"
        data[foff(s):foff(s) + 6] = hook

    csum, csum_off = _pe_checksum(data)
    struct.pack_into("<I", data, csum_off, csum)
    print(
        f"redirected {len(sites)} GetModuleFileNameA call sites "
        f"({', '.join(hex(s) for s in sites)}); "
        f"name@0x{name_va:X} wrapper@0x{code_va:X} ({len(code)}B); checksum 0x{csum:08X}"
    )
    return data


def patch(path: Path, name: str) -> None:
    data = bytearray(path.read_bytes())
    out = build(data, name.encode("ascii") + b"\x00")
    bak = path.with_suffix(path.suffix + ".namecrash-bak")
    if not bak.exists():
        shutil.copy2(path, bak)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(out)
    os.replace(tmp, path)
    print(f"patched {path.name} (backup: {bak.name})")


def main() -> None:
    ap = argparse.ArgumentParser(description="Fix the VV5 wrong-exe-name AV crash.")
    ap.add_argument("exe", type=Path, help="the VV5 exe to fix in place")
    ap.add_argument("--name", default=DEFAULT_NAME, help="expected basename to report")
    args = ap.parse_args()
    patch(args.exe, args.name)


if __name__ == "__main__":
    main()
