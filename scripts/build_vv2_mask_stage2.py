"""VV2 Heathen-mask overlay — STAGE 2: real mask atlas draw (UNVERIFIED alignment).

Builds on the proven stage-1 dual render hook (adult 0x4095B0->0x408940 5-arg +
child 0x409600->0x408CF0 7-arg, gated to head draws in FUN_00445b50).  Stage 2:

  1. INIT DETOUR at the asset-load tail (0x44c5e6): one-time load our dedicated
     mask atlas `Images/heathen_masks.png` (320x440) via the engine's own path
     loader 0x40a270("heathen_masks.png", cols=8, rows=5) -> cell 40x88; store the
     returned atlas object pointer in a code-cave dword MASK_ATLAS_PTR.
  2. DRAW: in both head-draw stubs, instead of re-drawing the head, draw the mask
     atlas at the head anchor (same frame/facing + x, y lifted MASK_DY) so the mask
     sits on the villager's face; feathers rise above.  Head still draws under it.

STAGE 2 hardcodes ONE mask row for EVERY villager (MASK_ROW_TEST) — no gate byte
/ chooser yet — purely to confirm the atlas loads, draws, scales (children) and
aligns.  Writes NO villager state.  Checksum-fixed test exe for live playtest.

Loader 0x40a270(this=ecx, filename, cols, rows): cellW = imgW/cols, cellH = imgH/rows
  (verified: [esi+0x10]=width/[esi+8], [esi+0x14]=height/[esi+0xc]); ret 0xc.
Allocator 0x467f83(size) cdecl -> ptr in eax (caller cleans 4).
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

import keystone

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Lost Children.exe"
IMAGE_BASE = 0x400000

# --- render hooks (proven in stage 1) --------------------------------------
THUNK_VA = 0x4095B0
THUNK_LEN = 0x4095B7 - 0x4095B0
REAL_DRAW = 0x408940              # adult real draw, ret 0x14 (atlas,x,y,row,frame)
CHILD_THUNK_VA = 0x409600
CHILD_THUNK_LEN = 0x409607 - 0x409600
CHILD_REAL_DRAW = 0x408CF0        # child real draw, ret 0x1c (atlas,x,y,headIdx,3,scaledRow,1)
# ADULT stub range = the in-world village compositor ONLY.  It derefs the villager record as
# esi + [esi+edi*4+0xe57090]*0xe48c, which is valid only where edi is the villager LOOP INDEX
# (true in FUN_00445B50).  In the portrait fn edi is a record POINTER, so that deref would read
# a wild address — hence the adult stub must never run there (it doesn't: the portrait draws
# through the 0x409600 scaled thunk, handled by the child stub below).
CALLER_LO, CALLER_HI = 0x445B50, 0x4478DF
# CHILD stub range additionally covers FUN_00445540 (0x445540..0x445B4F) = the DETAILS/portrait
# screen, which draws head+body via the same 0x409600 scaled thunk at fixed coords (x=0x78,
# y=0xF2, head atlases 0xE574AC/0xE574A8).  It was excluded by the old 0x445B50 lower bound —
# that is exactly why the mask never appeared on the Details screen.  The child stub gates only
# on the atlas being a head atlas (no record deref), so it is safe across both functions.
CHILD_CALLER_LO, CHILD_CALLER_HI = 0x445540, 0x4478DF
DRAWOBJ_PTR = 0xE574D0
HEAD_ATLASES = (0xE574A0, 0xE574A8, 0xE574AC, 0xE574B0, 0xE574B4)
MASK_BYTE_OFF = 0x680             # unused per-villager record byte = mask choice (0=none, 1..5)
# NOTE: do NOT use 0x588 — it lies INSIDE the villager-name string buffer (+0x564, 66-byte cap
# via the string-copy at 0x4682bd; default name "Biggles" @0x476774). A stored gate there would
# be wiped by any rename/reload and could corrupt a >=36-char name. 0x680 sits deep in the
# unreferenced 0x5f8..0x6e8 record gap, clear of every string buffer (verified: zero disp refs).

# --- init detour (asset-load tail) -----------------------------------------
INIT_VA = 0x44C5E6                # `mov [esi+0xe574d8], eax` (6 bytes)
INIT_LEN = 0x44C5EC - 0x44C5E6    # 6 bytes displaced
INIT_RET = 0x44C5EC              # continue here after the detour
LAST_ATLAS_GLOBAL = 0xE574D8      # the store we displaced (eax = last atlas ptr)
ALLOC = 0x467F83                  # operator new (cdecl size)
LOADER = 0x40A270                 # path atlas loader (thiscall; ret 0xc)
ATLAS_COLS, ATLAS_ROWS = 8, 5     # 320/8=40 wide, 440/5=88 tall

# --- cave layout -----------------------------------------------------------
CAVE_VA = 0x473C40                # .text slack, 0x3C0 free
MASK_ATLAS_PTR = CAVE_VA          # dword: loaded atlas obj ptr (0 until init)
FNAME_VA = CAVE_VA + 4            # "heathen_masks.png\0"
FNAME = b"heathen_masks.png\x00"

# --- tunables (live-iterate) ----------------------------------------------
MASK_ROW_TEST = 4                 # 0 Blue,1 Orange,2 Red,3 Purple,4 Chief (hardcoded for stage 2)
# The mask atlas cell is TALLER than the head cell (40x88) with each mask's face anchored at
# cell-y 56; the head's face is at cell-y 24.  So the mask must be lifted by (56-24)=32px so
# its face lands on the villager's face.  Adults draw unscaled -> fixed 32px.  Children draw
# through the SCALED path (scale s = arg6*0.01), so the lift must scale too: 32*s ~= (arg6*41)>>7
# (matches 32*s within a pixel across the whole child age range).
ADULT_MASK_DY = 0x2A              # 42 (raised from 32 — was landing on the chest)
CHILD_DY_MUL, CHILD_DY_SHIFT = 54, 7   # in-world child: 42*s ~= (arg6*54)>>7
# The Details/portrait draw (caller < 0x445B50) goes through the SAME scaled thunk but pushes
# arg6 = 2*(age/7)+0xA0 = DOUBLE the in-world scaledRow, so the same multiplier double-lifts and
# the mask flies above the head.  Give the portrait its own (smaller) multiplier; tune to taste.
PORTRAIT_DY_MUL = 54


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


def build(out_path: Path, force_row: int | None = None) -> None:
    data = bytearray(STOCK.read_bytes())
    ks = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)

    def asm(code: str, addr: int) -> bytes:
        b, _ = ks.asm(code, addr=addr)
        return bytes(b)

    # Gate/row fragments. Default = per-villager gate on the record byte (which
    # nothing writes yet, so no masks show). force_row (playtest QA) bypasses the
    # gate and paints a fixed mask on EVERY villager, WRITING NO RECORD BYTE — so
    # +0x{MASK_BYTE_OFF:X} stays 0 for the live-verification IDA read.
    if force_row is None:
        A_GATE = (f"movzx edx, byte ptr [eax+0x{MASK_BYTE_OFF:X}]\n"
                  "        test edx, edx\n        jz aorig")
        A_ROW = (f"mov  eax, [esi+edi*4+0xe57090]\n"
                 "        imul eax, eax, 0xe48c\n        add  eax, esi\n"
                 f"        movzx eax, byte ptr [eax+0x{MASK_BYTE_OFF:X}]\n"
                 "        dec  eax")
        C_GATE = (f"cmp  dword ptr [esp+4], 0x{CALLER_LO:X}\n"
                  "        jb   c_prt1\n"
                  "        mov  eax, [esi+edi*4+0xe57090]\n"
                  "        imul eax, eax, 0xe48c\n        add  eax, esi\n"
                  "        jmp  c_rec1\n    c_prt1:\n        mov  eax, edi\n"
                  f"    c_rec1:\n        movzx eax, byte ptr [eax+0x{MASK_BYTE_OFF:X}]\n"
                  "        test eax, eax\n        jz   corig")
        C_ROW = (f"cmp  dword ptr [esp], 0x{CALLER_LO:X}\n"
                 "        jb   c_prt2\n"
                 "        mov  eax, [esi+edi*4+0xe57090]\n"
                 "        imul eax, eax, 0xe48c\n        add  eax, esi\n"
                 "        jmp  c_rec2\n    c_prt2:\n        mov  eax, edi\n"
                 f"    c_rec2:\n        movzx eax, byte ptr [eax+0x{MASK_BYTE_OFF:X}]\n"
                 "        dec  eax")
    else:
        A_GATE = "/* force_row: no gate */"
        A_ROW = f"mov  eax, {force_row}"
        C_GATE = "/* force_row: no gate */"
        C_ROW = f"mov  eax, {force_row}"

    # code starts after the ptr dword + filename string (4-aligned)
    code0 = (FNAME_VA + len(FNAME) + 3) & ~3

    # ---- ADULT head stub: draw mask (row MASK_ROW_TEST) then original head ----
    # entry: jumped from `call 0x4095B0`; [esp]=ret,[+4]=atlas,[+8]=x,[+c]=y,[+10]=row,[+14]=frame
    #        ecx=drawobj-ptr, esi=gameCtx, edi=villager idx.
    adult_asm = f"""
        push eax
        mov  eax, [esp+4]
        cmp  eax, 0x{CALLER_LO:X}
        jb   aorig
        cmp  eax, 0x{CALLER_HI:X}
        ja   aorig
        mov  eax, [esi+edi*4+0xe57090]
        imul eax, eax, 0xe48c
        add  eax, esi                         /* eax = villager record base */
        mov  edx, [eax+0x548]                 /* head index */
        cmp  edx, [esp+0x14]                  /* row arg == head index? */
        jne  aorig
        mov  edx, [esp+8]                     /* atlas arg in head set? */
        cmp  edx, [esi+0x{HEAD_ATLASES[0]:X}]
        je   a_have
        cmp  edx, [esi+0x{HEAD_ATLASES[1]:X}]
        je   a_have
        cmp  edx, [esi+0x{HEAD_ATLASES[2]:X}]
        je   a_have
        cmp  edx, [esi+0x{HEAD_ATLASES[3]:X}]
        je   a_have
        cmp  edx, [esi+0x{HEAD_ATLASES[4]:X}]
        je   a_have
    aorig:
        pop  eax
        mov  ecx, [ecx]
        jmp  0x{REAL_DRAW:X}
    a_have:
        {A_GATE}
    amask:
        pop  eax                              /* [esp]=ret, [+4..+14]=atlas,x,y,row,frame */
        /* 1) original HEAD first (so the mask paints ON TOP) */
        push dword ptr [esp+0x14]             /* frame */
        push dword ptr [esp+0x14]             /* row */
        push dword ptr [esp+0x14]             /* y */
        push dword ptr [esp+0x14]             /* x */
        push dword ptr [esp+0x14]             /* atlas */
        mov  ecx, [esi+0x{DRAWOBJ_PTR:X}]
        mov  ecx, [ecx]
        call 0x{REAL_DRAW:X}                 /* head draw (ret 0x14) */
        /* 2) MASK on top: identical x,y,frame; row = maskByte-1; atlas=mask */
        mov  eax, [0x{MASK_ATLAS_PTR:X}]
        test eax, eax
        jz   adone
        {A_ROW}                               /* eax = mask row (byte-1, or forced) */
        push dword ptr [esp+0x14]             /* frame */
        push eax                              /* mask row */
        mov  edx, [esp+0x14]                  /* y */
        sub  edx, 0x{ADULT_MASK_DY:X}
        push edx
        push dword ptr [esp+0x14]             /* x */
        push dword ptr [0x{MASK_ATLAS_PTR:X}] /* mask atlas */
        mov  ecx, [esi+0x{DRAWOBJ_PTR:X}]
        mov  ecx, [ecx]
        call 0x{REAL_DRAW:X}                 /* mask draw (ret 0x14) */
    adone:
        ret  0x14                            /* return to caller, clean original 5 args */
    """
    adult = asm(adult_asm, code0)
    child_va = code0 + len(adult)

    # ---- CHILD head stub: draw mask via scaled path, then original head ----
    # entry: [esp]=ret,[+4]=atlas,[+8]=x,[+c]=y,[+10]=headIdx,[+14]=3,[+18]=scaledRow,[+1c]=1
    child_asm = f"""
        push eax
        mov  eax, [esp+4]
        cmp  eax, 0x{CHILD_CALLER_LO:X}
        jb   corig
        cmp  eax, 0x{CHILD_CALLER_HI:X}
        ja   corig
        mov  eax, [esp+8]
        cmp  eax, [esi+0x{HEAD_ATLASES[0]:X}]
        je   c_have
        cmp  eax, [esi+0x{HEAD_ATLASES[1]:X}]
        je   c_have
        cmp  eax, [esi+0x{HEAD_ATLASES[2]:X}]
        je   c_have
        cmp  eax, [esi+0x{HEAD_ATLASES[3]:X}]
        je   c_have
        cmp  eax, [esi+0x{HEAD_ATLASES[4]:X}]
        je   c_have
    corig:
        pop  eax
        mov  ecx, [ecx]
        jmp  0x{CHILD_REAL_DRAW:X}
    c_have:
        /* record base: village (caller>=0x445b50) = esi+[esi+edi*4+0xe57090]*0xe48c with
           edi=villager index; portrait (caller<0x445b50) = edi (holds the record base). */
        {C_GATE}
    cmask:
        pop  eax                              /* [esp]=ret, [+4..+1c]=atlas,x,y,headIdx,3,scaledRow,1 */
        /* 1) original HEAD first (all 7 args unchanged) so mask paints on top */
        push dword ptr [esp+0x1c]             /* arg7 = 1 */
        push dword ptr [esp+0x1c]             /* arg6 = scaledRow (scale) */
        push dword ptr [esp+0x1c]             /* arg5 = 3 */
        push dword ptr [esp+0x1c]             /* arg4 = headIdx */
        push dword ptr [esp+0x1c]             /* arg3 = y */
        push dword ptr [esp+0x1c]             /* arg2 = x */
        push dword ptr [esp+0x1c]             /* arg1 = atlas */
        mov  ecx, [esi+0x{DRAWOBJ_PTR:X}]
        mov  ecx, [ecx]
        call 0x{CHILD_REAL_DRAW:X}           /* head draw (ret 0x1c) */
        /* 2) MASK on top: same x,y,scale(arg6); atlas=mask; row selector arg4=mask row */
        mov  eax, [0x{MASK_ATLAS_PTR:X}]
        test eax, eax
        jz   cdone
        /* mask row = [record+gate]-1 (or forced); record via caller branch ([esp]=ret here) */
        {C_ROW}                               /* eax = mask row (survives the next 3 pushes) */
        push dword ptr [esp+0x1c]             /* arg7 = 1 */
        push dword ptr [esp+0x1c]             /* arg6 = scaledRow (same scale) */
        push dword ptr [esp+0x1c]             /* arg5 = 3 */
        push eax                              /* arg4 = mask row (was headIdx) */
        /* arg3 = y - lift; lift = arg6*mul>>7, mul depends on caller (in-world vs portrait) */
        mov  eax, [esp+0x28]                  /* arg6 = scaledRow (age-scale) */
        mov  edx, 0x{CHILD_DY_MUL:X}          /* in-world child multiplier (default) */
        cmp  dword ptr [esp+0x10], 0x{CALLER_LO:X}   /* caller retaddr < village fn? => portrait */
        jae  lmul
        mov  edx, 0x{PORTRAIT_DY_MUL:X}       /* Details/portrait multiplier */
    lmul:
        imul eax, edx
        sar  eax, 0x{CHILD_DY_SHIFT:X}
        mov  edx, [esp+0x1c]                  /* y */
        sub  edx, eax
        push edx
        push dword ptr [esp+0x1c]             /* arg2 = x */
        push dword ptr [0x{MASK_ATLAS_PTR:X}] /* arg1 = mask atlas */
        mov  ecx, [esi+0x{DRAWOBJ_PTR:X}]
        mov  ecx, [ecx]
        call 0x{CHILD_REAL_DRAW:X}           /* mask draw (ret 0x1c) */
    cdone:
        ret  0x1c                            /* return to caller, clean original 7 args */
    """
    child = asm(child_asm, child_va)
    init_va = child_va + len(child)

    # ---- INIT stub: displaced store + one-time mask atlas load ----
    init_asm = f"""
        mov  dword ptr [esi+0x{LAST_ATLAS_GLOBAL:X}], eax   /* displaced original store */
        pushad
        push 0x34
        call 0x{ALLOC:X}                      /* new(0x34) -> eax */
        add  esp, 4
        mov  ecx, eax                         /* this = obj */
        push 0x{ATLAS_ROWS:X}                 /* rows */
        push 0x{ATLAS_COLS:X}                 /* cols */
        push 0x{FNAME_VA:X}                   /* "heathen_masks.png" */
        call 0x{LOADER:X}                    /* -> eax = atlas obj (ret 0xc) */
        mov  [0x{MASK_ATLAS_PTR:X}], eax
        popad
        jmp  0x{INIT_RET:X}
    """
    init = asm(init_asm, init_va)
    end = init_va + len(init)
    total = end - CAVE_VA
    assert total <= 0x3C0, f"cave overflow: {total:#x}"

    # ---- hooks ----
    def patch_thunk(va: int, tlen: int, dst: int, label: str):
        h = asm(f"jmp 0x{dst:X}", addr=va)
        h = h + b"\x90" * (tlen - len(h))
        assert len(h) == tlen
        assert data[va - IMAGE_BASE:va - IMAGE_BASE + 2] == b"\x8b\x09", f"{label} thunk moved!"
        data[va - IMAGE_BASE:va - IMAGE_BASE + tlen] = h

    init_hook = asm(f"jmp 0x{init_va:X}", addr=INIT_VA)
    init_hook = init_hook + b"\x90" * (INIT_LEN - len(init_hook))
    assert len(init_hook) == INIT_LEN
    assert data[INIT_VA - IMAGE_BASE:INIT_VA - IMAGE_BASE + 2] == b"\x89\x86", "init detour site moved!"

    def foff(va: int) -> int:
        return va - IMAGE_BASE

    # cave region free?
    assert data[foff(CAVE_VA):foff(CAVE_VA) + total] == b"\0" * total, "cave not free!"

    # write cave: ptr(0) + filename + code
    struct.pack_into("<I", data, foff(MASK_ATLAS_PTR), 0)
    data[foff(FNAME_VA):foff(FNAME_VA) + len(FNAME)] = FNAME
    data[foff(code0):foff(code0) + len(adult)] = adult
    data[foff(child_va):foff(child_va) + len(child)] = child
    data[foff(init_va):foff(init_va) + len(init)] = init

    # write hooks
    patch_thunk(THUNK_VA, THUNK_LEN, code0, "adult")
    patch_thunk(CHILD_THUNK_VA, CHILD_THUNK_LEN, child_va, "child")
    data[foff(INIT_VA):foff(INIT_VA) + INIT_LEN] = init_hook

    # MASK_ATLAS_PTR lives in the cave (.text), which is read-only by default; the init
    # stub STORES the loaded atlas pointer there at runtime -> set IMAGE_SCN_MEM_WRITE on
    # the section that contains the cave so that store doesn't access-violate.
    pe_off = struct.unpack_from("<I", data, 0x3C)[0]
    num_sec = struct.unpack_from("<H", data, pe_off + 6)[0]
    opt_size = struct.unpack_from("<H", data, pe_off + 20)[0]
    sec_tbl = pe_off + 24 + opt_size
    cave_rva = CAVE_VA - IMAGE_BASE
    made_writable = None
    for i in range(num_sec):
        sh = sec_tbl + i * 40
        rva = struct.unpack_from("<I", data, sh + 12)[0]
        vsz = struct.unpack_from("<I", data, sh + 8)[0]
        rawsz = struct.unpack_from("<I", data, sh + 16)[0]
        # cave lives in .text's alignment padding (past VirtualSize) -> use max span
        span = ((max(vsz, rawsz) + 0xFFF) & ~0xFFF)
        if rva <= cave_rva < rva + span:
            ch_off = sh + 36
            ch = struct.unpack_from("<I", data, ch_off)[0]
            struct.pack_into("<I", data, ch_off, ch | 0x80000000)  # MEM_WRITE
            made_writable = data[sh:sh + 8].rstrip(b"\0").decode("latin1")
            break
    assert made_writable, "cave section not found!"

    csum, csum_off = _pe_checksum(data)
    struct.pack_into("<I", data, csum_off, csum)
    out_path.write_bytes(data)

    print(f"cave total {total} B @ 0x{CAVE_VA:X} (limit 0x3C0)")
    print(f"  ptr@0x{MASK_ATLAS_PTR:X} fname@0x{FNAME_VA:X} adult@0x{code0:X} child@0x{child_va:X} init@0x{init_va:X}")
    print(f"hooks: adult 0x{THUNK_VA:X}, child 0x{CHILD_THUNK_VA:X}, init 0x{INIT_VA:X}")
    print(f"section '{made_writable}' set writable (for MASK_ATLAS_PTR store)")
    if force_row is None:
        print(f"gate = per-villager byte [rec+0x{MASK_BYTE_OFF:X}] (0=no mask); nothing writes it yet")
    else:
        print(f"FORCE-ROW playtest: row {force_row} on EVERY villager; NO record byte written")
    print(f"PE checksum = 0x{csum:08X}")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    args = sys.argv[1:]
    force_row = None
    if "--force-row" in args:
        i = args.index("--force-row")
        force_row = int(args[i + 1])
        del args[i:i + 2]
    out = Path(args[0]) if args else ROOT / "scratchpad_vv2_mask_stage2.exe"
    build(out, force_row=force_row)
