"""Fix the wrong-exe-name access-violation crash (VV2 / The Lost Children).

Root cause: the game reads its own module filename via GetModuleFileNameA and
derives name-gated behaviour from the BASENAME (save folder Documents\\LDW\\<base>\\,
and an init/identity path).  Renaming the exe (e.g. "…- Modded.exe") makes the
basename mismatch the expected name, so initialization diverges, leaving engine
subsystems NULL; multiple later code paths then dereference those NULLs / walk
unterminated record arrays → 0xC0000005 at 0x44C823, 0x45FC1B, 0x4615BC, …

Fix (root): wrap GetModuleFileNameA so it always reports the EXPECTED basename
("Virtual Villagers - The Lost Children.exe") while keeping the real directory.
Assets still load from the real folder (they use the directory); the save folder
and name-gated init use the correct name → the game initializes exactly as if the
exe had the stock name, under ANY actual filename.  No behaviour change otherwise.

Implementation: a small .text cave holds the fixed basename + a stdcall wrapper
that calls the real GetModuleFileNameA (via the intact IAT), then overwrites the
buffer's basename (after the last '\\') with the fixed name and returns the new
length.  All 5 `call [GetModuleFileNameA]` sites are redirected to the wrapper.

Usage: python fix_exe_name_crash.py <exe path>
"""
from __future__ import annotations
import struct, sys, shutil, os
from pathlib import Path
import keystone
import pefile

IMAGE_BASE = 0x400000
GMFN_IAT = 0x47411C                         # IAT slot for GetModuleFileNameA
CALL_SITES = [0x402A6D, 0x402BD4, 0x46D9E7, 0x46DF55, 0x46FCD7]
CALL_ORIG = bytes.fromhex("ff151c414700")   # call dword ptr [0x47411c]
FIXED_NAME = b"Virtual Villagers - The Lost Children.exe\x00"


def _find_cave(data: bytes, path: Path, need: int) -> int:
    pe = pefile.PE(str(path), fast_load=True)
    for s in pe.sections:
        if not (s.Characteristics & 0x20000000) or s.Name.rstrip(b"\0") != b".text":
            continue
        seg = data[s.PointerToRawData:s.PointerToRawData + s.SizeOfRawData]
        i = 0
        while i < len(seg):
            if seg[i] == 0:
                j = i
                while j < len(seg) and seg[j] == 0:
                    j += 1
                if j - i >= need + 4:
                    return IMAGE_BASE + s.VirtualAddress + i + 2   # small alignment margin
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


def patch(path: Path) -> None:
    data = bytearray(path.read_bytes())
    ks = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)

    def foff(va): return va - IMAGE_BASE
    def asm(code, addr): return bytes(ks.asm(code, addr=addr)[0])

    for s in CALL_SITES:
        if data[foff(s):foff(s) + 6] != CALL_ORIG:
            raise SystemExit(f"call site 0x{s:X} != expected (already patched/other build): {data[foff(s):foff(s)+6].hex()}")

    cave = _find_cave(bytes(data), path, need=len(FIXED_NAME) + 96)
    name_va = cave
    code_va = (cave + len(FIXED_NAME) + 3) & ~3

    # stdcall wrapper: GetModuleFileNameA(hModule,lpFilename,nSize) -> len; rewrites basename.
    wrapper = f"""
        push dword ptr [esp+0xc]              /* nSize */
        push dword ptr [esp+0xc]              /* lpFilename */
        push dword ptr [esp+0xc]              /* hModule */
        call dword ptr [0x{GMFN_IAT:X}]       /* real GetModuleFileNameA -> buffer filled */
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
        mov  eax, edx                         /* return new length (excl. null) */
        sub  eax, dword ptr [esp+0x10]
        dec  eax
        pop  edi
        pop  esi
        ret  0xc
    """
    code = asm(wrapper, code_va)
    total = (code_va - cave) + len(code)
    assert data[foff(cave):foff(cave) + total] == b"\0" * total, "cave not free!"

    data[foff(name_va):foff(name_va) + len(FIXED_NAME)] = FIXED_NAME
    data[foff(code_va):foff(code_va) + len(code)] = code
    for s in CALL_SITES:
        hook = asm(f"call 0x{code_va:X}", s)
        hook = hook + b"\x90" * (6 - len(hook))
        assert len(hook) == 6
        data[foff(s):foff(s) + 6] = hook

    csum, csum_off = _pe_checksum(data)
    struct.pack_into("<I", data, csum_off, csum)

    bak = path.with_suffix(path.suffix + ".namecrash-bak")
    if not bak.exists():
        shutil.copy2(path, bak)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)
    print(f"patched {path.name}: name@0x{name_va:X} wrapper@0x{code_va:X} ({len(code)}B); "
          f"{len(CALL_SITES)} call sites redirected; checksum 0x{csum:08X}")


if __name__ == "__main__":
    patch(Path(sys.argv[1]))
