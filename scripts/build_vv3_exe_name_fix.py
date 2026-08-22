"""VV3 renamed-exe fix — make the game report the EXPECTED exe basename.

Base-game crash class (identified by the VV2 session, PR #98): the game derives
its save folder AND several init paths from the exe basename
(FUN_00402cf0: GetModuleFileNameA -> strip path+ext -> Documents\...\<basename>\).
Under a renamed exe the wrong basename makes init diverge (VV2 AV'd at NULL
engine subsystems even with a fresh save folder). VV3's villager scans are
bounded (so no scan-overrun AV), but a renamed VV3 build still gets a SEPARATE,
empty save folder and any name-gated init would still diverge.

Fix (name-independent, transparent): wrap GetModuleFileNameA so it always writes
the EXPECTED basename while keeping the real directory. Assets resolve from the
directory (name-independent), so they're unaffected; the save folder + any
name-gated init now behave exactly as under the stock exe name, under ANY
filename.

  - Cave: fixed basename "Virtual Villagers - The Secret City.exe\0" + a stub.
  - Stub (stdcall, ret 0xc): re-push the 3 args, call the real API via the intact
    IAT slot, scan the returned buffer for the last '\', overwrite the basename
    after it with the fixed string, set eax = new length. Preserves esi/edi.
  - Redirect all `call dword [GMFN_IAT]` sites to `call <stub>`.
  - Recompute the PE checksum.

GMFN_IAT = 0x47C130; 8 call sites. Composes with the mask stage2 patch (its
stub is elsewhere in the same .text slack; this finds free zeros after it).
"""
from __future__ import annotations

import struct
from pathlib import Path

from keystone import Ks, KS_ARCH_X86, KS_MODE_32

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Secret City.exe"
IMAGE_BASE = 0x400000

GMFN_IAT = 0x47C130
EXPECTED_NAME = b"Virtual Villagers - The Secret City.exe\x00"

_ks = Ks(KS_ARCH_X86, KS_MODE_32)


def asm(code: str, addr: int) -> bytes:
    enc, _ = _ks.asm(code, addr)
    return bytes(enc)


def _pe_checksum(buf: bytearray) -> tuple[int, int]:
    pe = struct.unpack_from("<I", buf, 0x3C)[0]
    off = pe + 24 + 0x40
    struct.pack_into("<I", buf, off, 0)
    total = 0
    for i in range(0, len(buf) & ~1, 2):
        total += struct.unpack_from("<H", buf, i)[0]
        total = (total & 0xFFFF) + (total >> 16)
    if len(buf) & 1:
        total += buf[-1]
        total = (total & 0xFFFF) + (total >> 16)
    return ((total & 0xFFFF) + len(buf)) & 0xFFFFFFFF, off


def _text_bounds(data: bytes) -> tuple[int, int, int]:
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    ns = struct.unpack_from("<H", data, pe + 6)[0]
    opt = struct.unpack_from("<H", data, pe + 20)[0]
    sec = pe + 24 + opt
    for i in range(ns):
        o = sec + i * 40
        nm = data[o:o + 8].rstrip(b"\0").decode("latin1")
        if nm == ".text":
            vva = struct.unpack_from("<I", data, o + 12)[0]
            rraw = struct.unpack_from("<I", data, o + 20)[0]
            rsz = struct.unpack_from("<I", data, o + 16)[0]
            return IMAGE_BASE + vva, rraw, rsz
    raise RuntimeError("no .text")


def _find_cave(data: bytes, need: int) -> int:
    """VA of a free zero run of at least `need` bytes in .text."""
    tva, rraw, rsz = _text_bounds(data)
    i = rraw
    end = rraw + rsz
    while i < end:
        if data[i] == 0:
            j = i
            while j < end and data[j] == 0:
                j += 1
            if j - i >= need:
                return tva + (i - rraw)
            i = j
        else:
            i += 1
    raise RuntimeError("no free cave")


def build(in_path: Path, out_path: Path) -> None:
    data = bytearray(in_path.read_bytes())

    def foff(va: int) -> int:
        return va - IMAGE_BASE

    need = len(EXPECTED_NAME) + 0x60
    name_va = _find_cave(data, need)
    name_va = (name_va + 3) & ~3
    stub_va = name_va + ((len(EXPECTED_NAME) + 3) & ~3)

    stub = f"""
        push dword ptr [esp+0xc]
        push dword ptr [esp+0xc]
        push dword ptr [esp+0xc]
        call dword ptr [0x{GMFN_IAT:X}]     /* real GetModuleFileNameA (IAT intact) */
        push esi
        push edi
        mov  edi, dword ptr [esp+0x10]       /* lpFilename */
        mov  esi, edi
        mov  ecx, edi                        /* write pos = start (no '\\' fallback) */
    scan_lp:
        mov  al, byte ptr [esi]
        test al, al
        je   scan_done
        inc  esi
        cmp  al, 0x5c
        jne  scan_lp
        mov  ecx, esi                        /* char after the last '\\' */
        jmp  scan_lp
    scan_done:
        mov  esi, 0x{name_va:X}              /* fixed basename */
    copy_lp:
        mov  al, byte ptr [esi]
        mov  byte ptr [ecx], al
        inc  esi
        inc  ecx
        test al, al
        jne  copy_lp
        lea  eax, [ecx-1]
        sub  eax, dword ptr [esp+0x10]       /* new length (excl NUL) */
        pop  edi
        pop  esi
        ret  0xc
    """
    stub_bytes = asm(stub, stub_va)
    end = stub_va + len(stub_bytes)

    # collect the ORIGINAL `call dword [GMFN_IAT]` sites BEFORE writing the stub,
    # so the stub's own real-API call (also ff15 <iat>) is NOT redirected (that would
    # make the stub recurse into itself). The cave is still all zeros here.
    needle = b"\xff\x15" + struct.pack("<I", GMFN_IAT)
    tva, rraw, rsz = _text_bounds(data)
    site_offsets = []
    i = rraw
    while True:
        j = data.find(needle, i, rraw + rsz)
        if j < 0:
            break
        site_offsets.append(j)
        i = j + 6

    assert data[foff(name_va):foff(end)] == b"\0" * (end - name_va), "cave not free"
    data[foff(name_va):foff(name_va) + len(EXPECTED_NAME)] = EXPECTED_NAME
    data[foff(stub_va):foff(stub_va) + len(stub_bytes)] = stub_bytes

    # redirect each original site -> call stub (e8 rel32 + nop = 6 bytes)
    for j in site_offsets:
        site_va = IMAGE_BASE + tva + (j - rraw)
        call = asm(f"call 0x{stub_va:X}", site_va) + b"\x90"
        assert len(call) == 6
        data[j:j + 6] = call
    sites = len(site_offsets)

    csum, off = _pe_checksum(data)
    struct.pack_into("<I", data, off, csum)
    out_path.write_bytes(data)
    print(f"exe-name fix: {out_path.name}")
    print(f"  name @0x{name_va:X}, stub @0x{stub_va:X} ({len(stub_bytes)}B), redirected {sites} call sites")


if __name__ == "__main__":
    import sys
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else STOCK
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else (ROOT / "vv3_namefix.exe")
    build(src, dst)
