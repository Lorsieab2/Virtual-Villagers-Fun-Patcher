"""VV2 Heathen-mask overlay — STAGE 1 render-hook proof (UNVERIFIED).

Proves the render hook fires and can inject an extra villager draw in the
VILLAGE view, before any mask atlas / UI work.  It hooks the universal draw
thunk (0x4095B0), and — only when the caller is inside the village villager-draw
FUN_00445b50 and the atlas arg is one of the head atlases — draws that villager's
head a second time, shifted UP 0x30px (a floating head over every villager).
If floating heads appear on the villagers walking around, the hook + draw
primitive + caller/atlas gating are all proven, and we swap the shifted head for
a real mask atlas gated by the per-villager +0x588 byte.

Writes NO villager state. Output is a checksum-fixed test exe for live playtest.

RE anchors (stock "Virtual Villagers - The Lost Children.exe", IB 0x400000):
  - Draw thunk 0x4095B0: `mov ecx,[ecx] ; jmp 0x408940` (real draw; ret 0x14 =
    5 stack args: atlas, x, y, rowIndex, frame; ecx = pointer-to-drawobj).
  - Village villager draw FUN_00445b50 (0x445B50..0x4478DF); esi=gameCtx,
    edi=villager loop index; drawobj-ptr = [esi+0xe574d0]; head atlases =
    [esi+0xe574a0 / 0xe574ac / 0xe574b4]; body atlases = a4/a8/b0.
  - Code cave: 0x473C40 (.text slack, 0x3C0 free, all zero).
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

import keystone

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Lost Children.exe"
IMAGE_BASE = 0x400000
# ADULT draw thunk: `mov ecx,[ecx]; jmp 0x408940` (real draw ret 0x14 = 5 stack args:
#   atlas, x, y, row, frame).  Used by full-size (adult/teen) villager draws.
THUNK_VA = 0x4095B0
THUNK_LEN = 0x4095B7 - 0x4095B0   # 7 bytes: mov ecx,[ecx] (2) + jmp rel32 (5)
REAL_DRAW = 0x408940        # thunk target (the actual draw; ret 0x14)
# CHILD/scaled draw thunk: `mov ecx,[ecx]; jmp 0x408cf0` (real draw ret 0x1c = 7 stack
#   args: atlas, x, y, headIdx, 3, scaledRow, 1).  A SCALED blit (fmul [0x474454]) — this
#   is why small children render smaller, and why the adult hook never sees them.
CHILD_THUNK_VA = 0x409600
CHILD_THUNK_LEN = 0x409607 - 0x409600
CHILD_REAL_DRAW = 0x408CF0
CAVE_VA = 0x473C40
CALLER_LO, CALLER_HI = 0x445B50, 0x4478DF   # FUN_00445b50 (village villager draw)
DRAWOBJ_PTR = 0xE574D0      # [esi+...] = pointer-to-drawobj
HEAD_ATLASES = (0xE574A0, 0xE574A8, 0xE574AC, 0xE574B0, 0xE574B4)
FLOAT_DY = 0x30


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


def build(out_path: Path) -> None:
    data = bytearray(STOCK.read_bytes())
    ks = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)

    # On entry (jumped to from a `call 0x4095B0`): [esp]=retaddr, [esp+4]=atlas,
    # [esp+8]=x, [esp+0xC]=y, [esp+0x10]=row, [esp+0x14]=frame; ecx=drawobj-ptr,
    # esi=gameCtx, edi=villager idx (in the FUN_00445b50 caller).
    cave_asm = f"""
        push eax
        mov  eax, [esp+4]                 /* return address */
        cmp  eax, 0x{CALLER_LO:X}
        jb   orig
        cmp  eax, 0x{CALLER_HI:X}
        ja   orig
        /* atlas-independent head test: is the row arg == this villager's head
           index (+0x548)?  record = esi + [esi+edi*4+0xe57090]*0xe48c. */
        mov  eax, [esi+edi*4+0xe57090]    /* villager slot index */
        imul eax, eax, 0xe48c
        add  eax, esi                     /* record base */
        mov  eax, [eax+0x548]             /* head index */
        cmp  eax, [esp+0x14]              /* == row arg? */
        jne  orig
        mov  eax, [esp+8]                 /* atlas arg -> must be a head atlas */
        cmp  eax, [esi+0x{HEAD_ATLASES[0]:X}]
        je   floater
        cmp  eax, [esi+0x{HEAD_ATLASES[1]:X}]
        je   floater
        cmp  eax, [esi+0x{HEAD_ATLASES[2]:X}]
        je   floater
        cmp  eax, [esi+0x{HEAD_ATLASES[3]:X}]
        je   floater
        cmp  eax, [esi+0x{HEAD_ATLASES[4]:X}]
        je   floater
    orig:
        pop  eax
        mov  ecx, [ecx]                   /* replicate thunk deref */
        jmp  0x{REAL_DRAW:X}              /* original draw (ret 0x14 -> caller) */
    floater:
        /* draw the head shifted up: 5 args from [esp+0x18] each (esp shifts +4/push) */
        push dword ptr [esp+0x18]         /* frame */
        push dword ptr [esp+0x18]         /* row */
        mov  eax, [esp+0x18]              /* y */
        sub  eax, 0x{FLOAT_DY:X}
        push eax                          /* y - 0x30 (float up) */
        push dword ptr [esp+0x18]         /* x */
        push dword ptr [esp+0x18]         /* atlas */
        mov  ecx, [esi+0x{DRAWOBJ_PTR:X}]
        mov  ecx, [ecx]                   /* deref (thunk already does this) */
        call 0x{REAL_DRAW:X}             /* floating head draw (ret 0x14 cleans 5 args) */
        pop  eax                          /* restore eax; esp -> retaddr, orig args */
        mov  ecx, [esi+0x{DRAWOBJ_PTR:X}]/* restore drawobj-ptr for the original draw */
        mov  ecx, [ecx]
        jmp  0x{REAL_DRAW:X}             /* original head draw */
    """
    cave_bytes, _ = ks.asm(cave_asm, addr=CAVE_VA)
    cave_bytes = bytes(cave_bytes)

    # CHILD cave stub (placed right after the adult stub in the same .text slack).
    # Children reach the draw via CHILD_THUNK (0x409600 -> 0x408cf0, ret 0x1c = 7 args:
    #   atlas, x, y, headIdx, 3, scaledRow, 1).  Same caller-range + head-atlas gate; then
    #   re-issue the 7-arg scaled draw with y shifted up 0x30 (floating head, auto-scaled).
    # After `push eax`, the 7 args sit at [esp+8..+0x20]; pushing them in reverse each has
    # its source land at a constant [esp+0x20] (verified: base+off + 4*pushes == 0x20).
    child_va = CAVE_VA + len(cave_bytes)
    child_asm = f"""
        push eax
        mov  eax, [esp+4]                 /* return address */
        cmp  eax, 0x{CALLER_LO:X}
        jb   corig
        cmp  eax, 0x{CALLER_HI:X}
        ja   corig
        mov  eax, [esp+8]                 /* atlas arg -> must be a head atlas */
        cmp  eax, [esi+0x{HEAD_ATLASES[0]:X}]
        je   cfloat
        cmp  eax, [esi+0x{HEAD_ATLASES[1]:X}]
        je   cfloat
        cmp  eax, [esi+0x{HEAD_ATLASES[2]:X}]
        je   cfloat
        cmp  eax, [esi+0x{HEAD_ATLASES[3]:X}]
        je   cfloat
        cmp  eax, [esi+0x{HEAD_ATLASES[4]:X}]
        je   cfloat
    corig:
        pop  eax
        mov  ecx, [ecx]
        jmp  0x{CHILD_REAL_DRAW:X}
    cfloat:
        push dword ptr [esp+0x20]         /* arg7 = 1 */
        push dword ptr [esp+0x20]         /* arg6 = scaledRow */
        push dword ptr [esp+0x20]         /* arg5 = 3 */
        push dword ptr [esp+0x20]         /* arg4 = headIdx */
        mov  eax, [esp+0x20]              /* arg3 = y */
        sub  eax, 0x{FLOAT_DY:X}
        push eax                          /* y - 0x30 (float up) */
        push dword ptr [esp+0x20]         /* arg2 = x */
        push dword ptr [esp+0x20]         /* arg1 = atlas */
        mov  ecx, [esi+0x{DRAWOBJ_PTR:X}]
        mov  ecx, [ecx]
        call 0x{CHILD_REAL_DRAW:X}       /* scaled floating-head draw (ret 0x1c) */
        pop  eax
        mov  ecx, [esi+0x{DRAWOBJ_PTR:X}]
        mov  ecx, [ecx]
        jmp  0x{CHILD_REAL_DRAW:X}
    """
    child_bytes, _ = ks.asm(child_asm, addr=child_va)
    child_bytes = bytes(child_bytes)
    total = len(cave_bytes) + len(child_bytes)
    assert total <= 0x3C0, f"caves too big: {total:#x}"

    hook, _ = ks.asm(f"jmp 0x{CAVE_VA:X}", addr=THUNK_VA)
    hook = bytes(hook) + b"\x90" * (THUNK_LEN - len(hook))
    assert len(hook) == THUNK_LEN
    child_hook, _ = ks.asm(f"jmp 0x{child_va:X}", addr=CHILD_THUNK_VA)
    child_hook = bytes(child_hook) + b"\x90" * (CHILD_THUNK_LEN - len(child_hook))
    assert len(child_hook) == CHILD_THUNK_LEN

    def foff(va: int) -> int:
        return va - IMAGE_BASE      # .text raw offset == RVA here

    # sanity: cave region must be free (all zero) and both thunks must be the known bytes
    assert data[foff(CAVE_VA):foff(CAVE_VA) + total] == b"\0" * total, "cave not free!"
    assert data[foff(THUNK_VA):foff(THUNK_VA) + 2] == b"\x8b\x09", "adult thunk prologue moved!"
    assert data[foff(CHILD_THUNK_VA):foff(CHILD_THUNK_VA) + 2] == b"\x8b\x09", "child thunk prologue moved!"

    data[foff(CAVE_VA):foff(CAVE_VA) + len(cave_bytes)] = cave_bytes
    data[foff(child_va):foff(child_va) + len(child_bytes)] = child_bytes
    data[foff(THUNK_VA):foff(THUNK_VA) + THUNK_LEN] = hook
    data[foff(CHILD_THUNK_VA):foff(CHILD_THUNK_VA) + CHILD_THUNK_LEN] = child_hook

    csum, csum_off = _pe_checksum(data)
    struct.pack_into("<I", data, csum_off, csum)

    out_path.write_bytes(data)
    print(f"adult cave {len(cave_bytes)} B @ 0x{CAVE_VA:X}; child cave {len(child_bytes)} B @ 0x{child_va:X} (total {total} B)")
    print(f"adult hook @ 0x{THUNK_VA:X}; child hook @ 0x{CHILD_THUNK_VA:X}")
    print(f"PE checksum = 0x{csum:08X}")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "scratchpad_vv2_mask_stage1.exe"
    build(out)
