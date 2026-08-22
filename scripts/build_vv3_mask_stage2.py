"""VV3 Heathen-mask render — VV2 separate-atlas method, Detail/portrait surface.

Adapted from VV2 PR #97 (build_vv2_mask_stage2.py). Instead of appending rows to
the head atlas (which desyncs the sprite-table row count -> white blob in-village
+ garbled head on Details), this loads a DEDICATED mask atlas and draws the mask
ON TOP of the head through the game's own child/scaled draw thunk.

VV3 addresses (Ghidra/capstone confirmed):
  child thunk 0x409FB0 (mov ecx,[ecx]; jmp 0x4093A0), ret 0x1c, 7 args
    (atlas, x=0x78, y=0xF2, headRow, facing, headY-scale, 1) -- Detail FUN_004568e0
  real draw       0x4093A0     atlas loader   0x40AF10(this,fname,cols,rows) ret 0xc
  allocator       0x46EC93(size)              surface via 0x40AD80/0x40B3D0
  head atlases    [0x6C5D40/44/48/4C]  drawobj = [villager+0x1F7C]
  per-villager    [villager+0xED0] (0=none, else mask row = byte-1)
  scale const     _DAT_0047c614 = 0.01  ->  lift = (headY*54)>>7  (~= 42*scale)

Mask atlas: Images/heathen_masks.png, 8 cols x 5 rows, cell 40x128 (built by
build_vv3_mask_atlas_separate). Lazy-loaded on the first masked portrait draw,
so no asset-load detour is needed.

Village-map masks are a separate follow-up (VV3's village uses the name-based
anim system 0x42E440, not this thunk). UNVERIFIED in-game (render hooks only
prove out live); the lift MUL (54) is tunable.
"""
from __future__ import annotations

import struct
from pathlib import Path

from keystone import Ks, KS_ARCH_X86, KS_MODE_32

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Secret City.exe"
IMAGE_BASE = 0x400000

CHILD_THUNK_VA = 0x409FB0
CHILD_THUNK_LEN = 0x409FB7 - 0x409FB0     # 7 bytes (jmp is 5, pad to 7)
CHILD_REAL_DRAW = 0x4093A0
REAL_RET = 0x1C

CALLER_LO, CALLER_HI = 0x4568E0, 0x456BC0  # Detail compositor FUN_004568e0
HEAD_ATLASES = (0x6C5D40, 0x6C5D44, 0x6C5D48, 0x6C5D4C)
DRAWOBJ_OFF = 0x1F7C
MASK_BYTE_OFF = 0xED0

ALLOC = 0x46EC93
LOADER = 0x40AF10
ATLAS_COLS, ATLAS_ROWS = 8, 5

MASK_DY_MUL, MASK_DY_SHIFT = 54, 7        # lift = (headY * 54) >> 7  (~42*scale)

CAVE_VA = 0x47B254                         # VA (RVA 0x7B254); free 0xDAC zero-run in stock .text
MASK_ATLAS_PTR = CAVE_VA                   # dword, 0 until lazy-loaded
FNAME_VA = CAVE_VA + 4
FNAME = b"heathen_masks.png\x00"

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


def build(out_path: Path) -> None:
    data = bytearray(STOCK.read_bytes())

    def foff(va: int) -> int:
        return va - IMAGE_BASE

    # ---- child stub ----
    code_va = FNAME_VA + ((len(FNAME) + 3) & ~3)   # 4-align the code
    head_cmp = "\n".join(
        f"cmp eax, dword ptr [0x{g:X}]\n je cmaskchk" for g in HEAD_ATLASES
    )
    stub = f"""
        push eax
        mov  eax, [esp+4]
        cmp  eax, 0x{CALLER_LO:X}
        jb   corig
        cmp  eax, 0x{CALLER_HI:X}
        ja   corig
        mov  eax, [esp+8]
        {head_cmp}
        jmp  corig
    cmaskchk:
        movzx eax, byte ptr [esi+0x{MASK_BYTE_OFF:X}]
        test eax, eax
        jz   corig
        jmp  cmask
    corig:
        pop  eax
        mov  ecx, [ecx]
        jmp  0x{CHILD_REAL_DRAW:X}
    cmask:
        pop  eax
        /* 1) original HEAD first (7 args unchanged) so the mask paints on top */
        push dword ptr [esp+0x1c]
        push dword ptr [esp+0x1c]
        push dword ptr [esp+0x1c]
        push dword ptr [esp+0x1c]
        push dword ptr [esp+0x1c]
        push dword ptr [esp+0x1c]
        push dword ptr [esp+0x1c]
        mov  ecx, [esi+0x{DRAWOBJ_OFF:X}]
        mov  ecx, [ecx]
        call 0x{CHILD_REAL_DRAW:X}
        /* 2) lazy-load the mask atlas the first time */
        mov  eax, [0x{MASK_ATLAS_PTR:X}]
        test eax, eax
        jnz  have_atlas
        pushad
        push 0x34
        call 0x{ALLOC:X}
        add  esp, 4
        mov  ecx, eax
        push 0x{ATLAS_ROWS:X}
        push 0x{ATLAS_COLS:X}
        push 0x{FNAME_VA:X}
        call 0x{LOADER:X}
        mov  [0x{MASK_ATLAS_PTR:X}], eax
        popad
        mov  eax, [0x{MASK_ATLAS_PTR:X}]
    have_atlas:
        test eax, eax
        jz   cdone
        /* 3) MASK on top: same x/frame/scale; row=mask; y lifted (scaled) */
        push dword ptr [esp+0x1c]              /* arg7 = 1 */
        push dword ptr [esp+0x1c]              /* arg6 = headY (scale) */
        push dword ptr [esp+0x1c]              /* arg5 = facing */
        movzx eax, byte ptr [esi+0x{MASK_BYTE_OFF:X}]
        dec  eax
        push eax                               /* arg4 = mask row (byte-1) */
        mov  eax, [esp+0x28]                   /* arg6 = headY (scale) */
        imul eax, 0x{MASK_DY_MUL:X}
        sar  eax, 0x{MASK_DY_SHIFT:X}
        mov  edx, [esp+0x1c]                   /* arg3 = y */
        sub  edx, eax                          /* y - lift */
        push edx                               /* arg3 = lifted y */
        push dword ptr [esp+0x1c]              /* arg2 = x */
        push dword ptr [0x{MASK_ATLAS_PTR:X}]  /* arg1 = mask atlas */
        mov  ecx, [esi+0x{DRAWOBJ_OFF:X}]
        mov  ecx, [ecx]
        call 0x{CHILD_REAL_DRAW:X}
    cdone:
        ret  0x{REAL_RET:X}
    """
    stub_bytes = asm(stub, code_va)
    end = code_va + len(stub_bytes)
    total = end - CAVE_VA
    assert total <= 0xDAC, f"cave overflow: {total:#x}"

    # cave must be free zeros
    assert data[foff(CAVE_VA):foff(CAVE_VA) + total] == b"\0" * total, "cave not free"

    # write cave: ptr(0) + filename + code
    struct.pack_into("<I", data, foff(MASK_ATLAS_PTR), 0)
    data[foff(FNAME_VA):foff(FNAME_VA) + len(FNAME)] = FNAME
    data[foff(code_va):foff(code_va) + len(stub_bytes)] = stub_bytes

    # hook the child thunk (mov ecx,[ecx] = 8B 09) -> jmp stub + nops
    assert data[foff(CHILD_THUNK_VA):foff(CHILD_THUNK_VA) + 2] == b"\x8b\x09", "child thunk moved"
    hook = asm(f"jmp 0x{code_va:X}", CHILD_THUNK_VA)
    hook = hook + b"\x90" * (CHILD_THUNK_LEN - len(hook))
    data[foff(CHILD_THUNK_VA):foff(CHILD_THUNK_VA) + CHILD_THUNK_LEN] = hook

    # .text needs MEM_WRITE (the stub stores the atlas ptr into the cave)
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    ns = struct.unpack_from("<H", data, pe + 6)[0]
    opt = struct.unpack_from("<H", data, pe + 20)[0]
    sec = pe + 24 + opt
    for i in range(ns):
        o = sec + i * 40
        nm = data[o:o + 8].rstrip(b"\0").decode("latin1")
        if nm == ".text":
            ch = struct.unpack_from("<I", data, o + 36)[0]
            struct.pack_into("<I", data, o + 36, ch | 0x80000000)  # IMAGE_SCN_MEM_WRITE

    csum, off = _pe_checksum(data)
    struct.pack_into("<I", data, off, csum)
    out_path.write_bytes(data)
    print(f"stage2 written: {out_path.name}")
    print(f"  cave {total} B @ 0x{CAVE_VA:X} (limit 0xDAC); hook child thunk 0x{CHILD_THUNK_VA:X}")
    print(f"  atlas Images/heathen_masks.png ({ATLAS_COLS}x{ATLAS_ROWS}); lift MUL={MASK_DY_MUL}")


if __name__ == "__main__":
    import sys
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else (ROOT / "vv3_mask_stage2.exe")
    build(out)
