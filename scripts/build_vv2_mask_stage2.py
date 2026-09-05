"""VV2 Heathen-mask overlay — STAGE 2: real mask atlas draw (UNVERIFIED alignment).

Builds on the proven stage-1 dual render hook (adult 0x4095B0->0x408940 5-arg +
child 0x409600->0x408CF0 7-arg, gated to head draws in FUN_00445b50).  Stage 2:

  1. INIT DETOUR at the asset-load tail (0x44c5e6): one-time load our dedicated
     mask atlas `Images/heathen_masks.png` (520x725) via the engine's own path
     loader 0x40a270("heathen_masks.png", cols=8, rows=5) -> cell 65x145; store the
     returned atlas object pointer in a patch-owned `.mtab` dword MASK_ATLAS_PTR.
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
#
# UPPER BOUND raised 0x4478DF -> 0x449060 (2026-08-26).  A full audit of every call site of the
# two head-draw thunks found 68 sites that push a HEAD atlas, spanning 0x44564B..0x449049 — but
# the old 0x4478DF ceiling excluded 25 of them (0x447ADD..0x449049).  Those are the ALTERNATE
# POSE renderers (swimming / sitting / lying down / bending), so a masked villager lost the mask
# the moment they left the walking pose.  Owner PSA: "the masks should follow the head at all
# times ... when villagers jump or bend down ... when swimming and any other edge cases."
# Safety checked before widening: those functions use the SAME conventions as the already-gated
# region — esi = gameCtx (they read [esi+0xE574A8] / [esi+0xE574D0]) and they reference the
# villager index table 0xE57090 34 times — so the stub's `[esi+edi*4+0xE57090]` record lookup is
# valid there too.  No non-head draw sites exist above the last head site, so nothing else is
# swept in.  The ADULT gate is deliberately NOT widened: all 29 of its sites were already inside,
# and its record deref is only valid where edi is the loop index.
CHILD_CALLER_LO, CHILD_CALLER_HI = 0x445540, 0x449060
DRAWOBJ_PTR = 0xE574D0
HEAD_ATLASES = (0xE574A0, 0xE574A8, 0xE574AC, 0xE574B0, 0xE574B4)
MASK_BYTE_OFF = 0x480             # unused per-villager record byte = mask choice (0=none, 1..5)
# VERIFIED FREE via LIVE process read (131 active villagers in varied states + 125 empty slots):
# +0x480 reads 0 on EVERY slot and has no record-field disp refs; it sits mid-way in a 191-byte
# all-zero record gap (0x43d..0x4fc). 4-aligned => low byte of its dword.
# REJECTED earlier offsets — both fooled the static "zero disp refs" test:
#   0x588: INSIDE the villager-name buffer (+0x564, 66-byte cap via 0x4682bd) — wiped on
#          rename/reload, could corrupt a long name.
#   0x680: static-clean but LIVE reads 0xFF on every active villager (enclosing dword
#          0xFFFFFFFF, a -1 sentinel written by a bulk init invisible to displacement scans).
# Lesson: a record byte MUST pass the live read, not just static no-refs.

# --- init detour (asset-load tail) -----------------------------------------
INIT_VA = 0x44C5E6                # `mov [esi+0xe574d8], eax` (6 bytes)
INIT_LEN = 0x44C5EC - 0x44C5E6    # 6 bytes displaced
INIT_RET = 0x44C5EC              # continue here after the detour
LAST_ATLAS_GLOBAL = 0xE574D8      # the store we displaced (eax = last atlas ptr)
ALLOC = 0x467F83                  # operator new (cdecl size)
LOADER = 0x40A270                 # path atlas loader (thiscall; ret 0xc)
ATLAS_COLS, ATLAS_ROWS = 8, 5     # 520/8=65 wide, 725/5=145 tall
MASK_ROW_COUNT = ATLAS_ROWS + 1  # table byte: 0=none, 1..5=atlas rows
# VV5-standard mask cell: 65x145, 8 facing columns x 5 colour rows, used as the
# artist laid it out (no re-packing). The cell is much larger than the 40x65 head
# cell, so the draw subtracts MASK_PAD_X/ADULT_MASK_DY to register it on the head.
# VV5's cell (65x145) is larger than VV2's head cell (40x65). VV5 can draw at the
# head's raw x/y because their head cell IS that size; on VV2 the cell origins do
# not coincide, so drawing at raw x/y puts the mask down-and-right of the head
# (observed in-game). These constants re-register VV5's cell onto VV2's head cell;
# they are the equivalent of VV5's "draw at the head anchor", not extra tuning.
MASK_PAD_X = 0                    # X registration is baked per-facing into the atlas

# --- cave layout -----------------------------------------------------------
# Mask code + filename live in an appended R/X section (.vvmk), NOT the shared game
# .text cave (0x473C40) — that cave is occupied in the Origins build. The atlas
# pointer and sidecar state live in the appended R/W `.mtab` section. MASK_ATLAS_PTR
# / FNAME_VA are assigned per-build inside build() from the appended section's VA.
FNAME = b"heathen_masks.png\x00"
# Startup mask-restore: the init detour LoadLibrary's the Origins DLL and calls its
# Vv2MaskRestore export (loads the sidecar into .mtab), so saved masks reappear from
# game launch. Fail-open: on the stock build (no DLL) LoadLibraryA returns 0 and we
# skip. Uses the exe's own kernel32 IAT slots (present in stock + Origins builds).
DLLNAME = b"VVFP VV2 Origins Icons.dll\x00"
RESTORE_STR = b"Vv2MaskRestore\x00"
EXTRACT_STR = b"Vv2ExtractAtlas\x00"
SAVE_STR = b"Vv2MaskSaveSidecar\x00"
LOADLIBRARYA_IAT = 0x474010
GETPROCADDRESS_IAT = 0x4740D4

# --- tunables (live-iterate) ----------------------------------------------
MASK_ROW_TEST = 4                 # 0 Blue,1 Orange,2 Red,3 Purple,4 Chief (hardcoded for stage 2)
# The mask atlas cell is TALLER than the head cell (40x65). The atlas builder bakes
# each frame's face anchor and per-colour art lift into the 65x145 cell. The draw
# still lifts the whole cell by LIFT=42: adults use a fixed lift; children and
# portraits scale it with the head so the face stays registered at every age.
ADULT_MASK_DY = 0x2A              # 42, matches LIFT in the atlas builder
CHILD_DY_MUL, CHILD_DY_SHIFT = 54, 7   # 42px lift at full scale, scaled with the head
# The Details/portrait draw (caller < 0x445B50) goes through the SAME scaled thunk but pushes
# arg6 = 2*(age/7)+0xA0 = DOUBLE the in-world scaledRow, so the same multiplier double-lifts and
# the mask flies above the head.  Give the portrait its own (smaller) multiplier; tune to taste.
PORTRAIT_DY_MUL = 54   # same geometric lift as the village (42px at full scale)
# The mask atlas is baked/tuned for the 1x village view; the Details portrait draws the same
# atlas larger, leaving masks a touch high+left there.  Nudge masks down+right on the portrait
# path ONLY (caller < 0x445B50).  Tune to taste.
# These are build inputs, not runtime knobs.  They were previously read from
# PMDX/PMDY environment variables, which the manifest's builder_sha256 cannot
# detect: that pin covers this file's source text only, so a build run with a
# different PMDX/PMDY produced different append bytes while still matching the
# pinned identity.  Keeping them literal makes the generated page reproducible
# from the checked-in source alone.
PORTRAIT_MASK_DX = 8    # Details mask: move right to center on the face
PORTRAIT_MASK_DY = 30   # Details mask: move down to center on the face
# The atlas builder places each frame so its FACE region sits at the head's face
# anchor in HEAD-CELL coords, offset down by LIFT. Drawing that
# cell at (x, y - LIFT*scale) therefore lands the mask's face on the head's face at
# EVERY scale -- verified algebraically at scale 1.0/1.5/2.0, delta 0.00 on both axes.
# The old 17/40 were cell-size corrections (65x145 mask vs 40x65 head) from BEFORE
# the registration was baked in; with baked art they are a double correction.
# Per-mask portrait (Details) fine-alignment — masks drift a little differently on
# the age-scaled portrait, so each colour gets its own extra nudge ON TOP of the
# uniform PMDX/PMDY (village view unaffected — this is portrait-branch only).
# Rows: 0 Blue, 1 Orange, 2 Red, 3 Purple, 4 Chief.  +down / +left (left = subtracted).
PURPLE_PORTRAIT_EXTRA = 0    # purple extra down (was 6, +3 live)
ORANGE_PORTRAIT_DY = 0      # orange extra down
RED_PORTRAIT_DY = 0         # red extra down
RED_PORTRAIT_DX = 0         # red extra LEFT
CHIEF_PORTRAIT_DX = 0       # chief extra LEFT


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


def _append_section(data: bytearray, name: bytes, vsize: int,
                    chars: int = 0xC0000040) -> tuple[int, int]:
    """Append a zero-filled section and return (absolute VA, raw file offset).
    Guaranteed game-untouchable: no compiled code can reference a VA that did not
    exist at build time. `chars` = section flags (default init-data|R|W; pass
    0xE0000020 for code|R|W|X). Used for the patch-owned mask table AND the mask
    render code, so NOTHING lives in the shared game .text cave (which the Origins
    build already occupies). NOTE: an appended section's file offset != its RVA,
    so callers must use the returned raw offset (not VA-ImageBase) to write it."""
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    num = struct.unpack_from("<H", data, pe + 6)[0]
    opt = pe + 24
    opt_size = struct.unpack_from("<H", data, pe + 20)[0]
    sec_align = struct.unpack_from("<I", data, opt + 32)[0]
    file_align = struct.unpack_from("<I", data, opt + 36)[0]
    sec_tbl = opt + opt_size

    def a(x, n):
        return (x + n - 1) & ~(n - 1)

    max_va = max_raw = 0
    for i in range(num):
        sh = sec_tbl + i * 40
        va = struct.unpack_from("<I", data, sh + 12)[0]
        vsz = struct.unpack_from("<I", data, sh + 8)[0]
        praw = struct.unpack_from("<I", data, sh + 20)[0]
        rsz = struct.unpack_from("<I", data, sh + 16)[0]
        max_va = max(max_va, va + vsz)
        max_raw = max(max_raw, praw + rsz)
    new_va = a(max_va, sec_align)
    new_raw = a(max_raw, file_align)
    raw_size = a(vsize, file_align)
    new_hdr = sec_tbl + num * 40
    first_raw = min(
        struct.unpack_from("<I", data, sec_tbl + i * 40 + 20)[0]
        for i in range(num)
        if struct.unpack_from("<I", data, sec_tbl + i * 40 + 20)[0] > 0
    )
    assert new_hdr + 40 <= first_raw, "no room in header for a new section"
    if len(data) < new_raw:
        data += b"\0" * (new_raw - len(data))
    data += b"\0" * raw_size
    hdr = bytearray(40)
    hdr[0 : len(name)] = name
    struct.pack_into("<I", hdr, 8, vsize)         # VirtualSize
    struct.pack_into("<I", hdr, 12, new_va)       # VirtualAddress (RVA)
    struct.pack_into("<I", hdr, 16, raw_size)     # SizeOfRawData
    struct.pack_into("<I", hdr, 20, new_raw)      # PointerToRawData
    struct.pack_into("<I", hdr, 36, chars)        # section characteristics
    data[new_hdr : new_hdr + 40] = hdr
    struct.pack_into("<H", data, pe + 6, num + 1)          # NumberOfSections
    struct.pack_into("<I", data, opt + 56, a(new_va + vsize, sec_align))  # SizeOfImage
    return IMAGE_BASE + new_va, new_raw


def build(out_path: Path, force_row: int | None = None, src_exe: Path | None = None) -> None:
    # Base exe: stock by default, but the mask hooks (thunks 0x4095B0/0x409600, init
    # detour 0x44C5E6) are byte-identical in the Origins/Modded build, and the mask
    # code/table now live in appended sections (not the occupied 0x473C40 cave), so
    # this same builder applies to the Modded exe too — pass src_exe.
    data = bytearray((src_exe or STOCK).read_bytes())
    ks = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)

    def asm(code: str, addr: int) -> bytes:
        b, _ = ks.asm(code, addr=addr)
        return bytes(b)

    # Patch-owned per-villager mask table (256 bytes) in a NEW appended PE section,
    # so the mask CHOICE never touches villager records or ANY game data (the game
    # cannot reference a VA that did not exist at build time). Indexed by record
    # index 0..255; value 0=no mask, 1..5 = mask row+1. Zero at load = no masks.
    MASK_TABLE_VA, _ = _append_section(data, b".mtab", 0x1000)
    SCRATCH_VA = MASK_TABLE_VA + 0xF00   # dword scratch: current mask row (for per-mask portrait offset)
    # 256-byte "seen-alive" latch (one byte per record index) in the R/W .mtab.
    # The per-frame sweep sets it when a slot is observed active, and only clears
    # a slot's mask once it has been seen active AND then goes free — so a reused
    # dead slot can't leak its old mask onto a newborn, while masks are NOT wiped
    # on load/menu frames (where every slot momentarily reads free before the
    # village populates and before the sidecar restore runs).
    SEEN_ALIVE_VA = MASK_TABLE_VA + 0x100
    # Mask RENDER CODE goes in its OWN appended R/W/X section — NOT the shared game
    # .text cave at 0x473C40 (which the Origins build already occupies). Self-contained:
    # atlas-obj pointer + "heathen_masks.png" filename + the adult/child/init stubs.
    # .vvmk is R + X ONLY (no write) — W^X-clean so AV (Malwarebytes) won't quarantine
    # a writable+executable section. The one runtime write (atlas ptr) goes to .mtab (R/W).
    CODE_SEC_VA, CODE_RAW = _append_section(data, b".vvmk", 0x1000, 0x60000020)
    MASK_ATLAS_PTR = MASK_TABLE_VA + 0xF08  # dword in .mtab (R/W): atlas obj ptr (0 until init)
    # Save-slot tracking, so village 2 can never show -- or overwrite -- village 1's
    # masks. The save-path builder publishes the slot; the per-frame sweep reloads
    # the sidecar when it changes. The DLL reads SLOT_VA to pick vv2_masks_<slot>.dat.
    SLOT_VA     = MASK_TABLE_VA + 0xF10   # dword: current save slot (0 = none yet)
    LOADED_VA   = MASK_TABLE_VA + 0xF14   # byte: 1 = sidecar loaded for SLOT_VA
    RESTORE_FN  = MASK_TABLE_VA + 0xF18   # dword: cached Vv2MaskRestore address
    SAVE_FN     = MASK_TABLE_VA + 0xF1C   # dword: cached Vv2MaskSaveSidecar address
    SWEEP_CLEARED_VA = MASK_TABLE_VA + 0xF20  # byte: sweep cleared at least one mask
    FNAME_VA = CODE_SEC_VA                   # "heathen_masks.png\0" (read-only in the R+X section)
    DLLNAME_VA = FNAME_VA + len(FNAME)       # "VVFP VV2 Origins Icons.dll\0"
    RESTORE_STR_VA = DLLNAME_VA + len(DLLNAME)  # "Vv2MaskRestore\0"
    EXTRACT_STR_VA = RESTORE_STR_VA + len(RESTORE_STR)  # "Vv2ExtractAtlas\0"
    SAVE_STR_VA = EXTRACT_STR_VA + len(EXTRACT_STR)  # "Vv2MaskSaveSidecar\0"

    def cfoff(va: int) -> int:            # file offset of a VA inside the appended code section
        return CODE_RAW + (va - CODE_SEC_VA)

    # Gate/row fragments. Default = per-villager gate on the PATCH-OWNED mask table
    # indexed by record index (village: recIdx = [esi+edi*4+0xe57090]; portrait:
    # recIdx = (record_base edi - gameCtx esi)/0xe48c). No villager record byte is
    # ever read or written. force_row (playtest QA) paints a fixed mask on everyone.
    if force_row is None:
        A_GATE = ("mov  edx, [esi+edi*4+0xe57090]\n"
                  f"        movzx edx, byte ptr [edx+0x{MASK_TABLE_VA:X}]\n"
                  f"        cmp  edx, {MASK_ROW_COUNT}\n"
                  "        jae  aorig\n"
                  "        test edx, edx\n        jz aorig")
        A_ROW = ("mov  eax, [esi+edi*4+0xe57090]\n"
                 f"        movzx eax, byte ptr [eax+0x{MASK_TABLE_VA:X}]\n"
                 f"        cmp  eax, {MASK_ROW_COUNT}\n"
                 "        jae  adone\n"
                 "        dec  eax")
        C_GATE = (f"cmp  dword ptr [esp+4], 0x{CALLER_LO:X}\n"
                  "        jb   cg_prt\n"
                  "        mov  eax, [esi+edi*4+0xe57090]\n"
                  "        jmp  cg_have\n"
                  "    cg_prt:\n"
                  "        mov  eax, edi\n        sub  eax, esi\n"
                  "        push ecx\n        push edx\n"
                  "        xor  edx, edx\n        mov  ecx, 0xe48c\n        div  ecx\n"
                  "        pop  edx\n        pop  ecx\n"
                  "    cg_have:\n"
                  f"        movzx eax, byte ptr [eax+0x{MASK_TABLE_VA:X}]\n"
                  f"        cmp  eax, {MASK_ROW_COUNT}\n"
                  "        jae  corig\n"
                  "        test eax, eax\n        jz   corig")
        C_ROW = (f"cmp  dword ptr [esp], 0x{CALLER_LO:X}\n"
                 "        jb   cr_prt\n"
                 "        mov  eax, [esi+edi*4+0xe57090]\n"
                 "        jmp  cr_have\n"
                 "    cr_prt:\n"
                 "        mov  eax, edi\n        sub  eax, esi\n"
                 "        push ecx\n"
                 "        xor  edx, edx\n        mov  ecx, 0xe48c\n        div  ecx\n"
                 "        pop  ecx\n"
                 "    cr_have:\n"
                 f"        movzx eax, byte ptr [eax+0x{MASK_TABLE_VA:X}]\n"
                 f"        cmp  eax, {MASK_ROW_COUNT}\n"
                 "        jae  cdone\n"
                 "        dec  eax")
    else:
        A_GATE = "/* force_row: no gate */"
        A_ROW = f"mov  eax, {force_row}"
        C_GATE = "/* force_row: no gate */"
        C_ROW = f"mov  eax, {force_row}"

    # code starts after the ptr dword + filename string (4-aligned)
    code0 = (EXTRACT_STR_VA + len(EXTRACT_STR) + 3) & ~3

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
        mov  edx, [esp+0x14]                  /* x */
        sub  edx, 0x{MASK_PAD_X:X}            /* undo the wider mask cell's inset */
        push edx
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
        mov  dword ptr [0x{SCRATCH_VA:X}], eax   /* stash row for per-mask portrait nudge */
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
        sub  edx, eax                         /* y - lift */
        cmp  dword ptr [esp+0x10], 0x{CALLER_LO:X}   /* portrait? (caller-ret @ +0x10) */
        jae  y_ok
        add  edx, 0x{PORTRAIT_MASK_DY:X}      /* portrait: nudge mask down (all masks) */
        mov  ecx, [0x{SCRATCH_VA:X}]          /* mask row */
        cmp  ecx, 1                           /* orange? */
        je   y_orange
        cmp  ecx, 2                           /* red? */
        je   y_red
        cmp  ecx, 3                           /* purple? */
        je   y_purple
        jmp  y_ok                             /* blue/chief: no extra down */
    y_orange:
        add  edx, 0x{ORANGE_PORTRAIT_DY:X}
        jmp  y_ok
    y_red:
        add  edx, 0x{RED_PORTRAIT_DY:X}
        jmp  y_ok
    y_purple:
        add  edx, 0x{PURPLE_PORTRAIT_EXTRA:X}
    y_ok:
        push edx                              /* arg3 = y */
        mov  edx, [esp+0x1c]                  /* arg2 = x (caller-ret @ +0x14 now) */
        cmp  dword ptr [esp+0x14], 0x{CALLER_LO:X}
        jae  x_ok
        add  edx, 0x{PORTRAIT_MASK_DX:X}      /* portrait: nudge mask right (all masks) */
        mov  ecx, [0x{SCRATCH_VA:X}]          /* mask row (reload) */
        cmp  ecx, 2                           /* red? extra left */
        je   x_red
        cmp  ecx, 4                           /* chief? extra left */
        je   x_chief
        jmp  x_ok
    x_red:
        sub  edx, 0x{RED_PORTRAIT_DX:X}
        jmp  x_ok
    x_chief:
        sub  edx, 0x{CHIEF_PORTRAIT_DX:X}
    x_ok:
        sub  edx, 0x{MASK_PAD_X:X}            /* undo the wider mask cell's inset */
        push edx                              /* arg2 = x */
        push dword ptr [0x{MASK_ATLAS_PTR:X}] /* arg1 = mask atlas */
        mov  ecx, [esi+0x{DRAWOBJ_PTR:X}]
        mov  ecx, [ecx]
        call 0x{CHILD_REAL_DRAW:X}           /* mask draw (ret 0x1c) */
    cdone:
        ret  0x1c                            /* return to caller, clean original 7 args */
    """
    child = asm(child_asm, child_va)
    init_va = child_va + len(child)

    # ---- INIT stub: displaced store + self-extract atlas + atlas load + restore ----
    init_asm = f"""
        mov  dword ptr [esi+0x{LAST_ATLAS_GLOBAL:X}], eax   /* displaced original store */
        pushad
        /* (1) self-extract the mask atlas to <game>\\Images if missing, or migrate
           one exact obsolete 320x440 bundled atlas. Current/custom art is preserved;
           no manual asset deploy is needed. LoadLibrary the DLL + call Vv2ExtractAtlas
           BEFORE the atlas load below. Fail-open: no DLL (stock build) -> skip. */
        push 0x{DLLNAME_VA:X}
        call dword ptr [0x{LOADLIBRARYA_IAT:X}]
        test eax, eax
        jz   after_extract
        push 0x{EXTRACT_STR_VA:X}
        push eax
        call dword ptr [0x{GETPROCADDRESS_IAT:X}]
        test eax, eax
        jz   after_extract
        call eax                             /* Vv2ExtractAtlas() */
    after_extract:
        /* (2) load the atlas as a game sprite object */
        push 0x34
        call 0x{ALLOC:X}                      /* new(0x34) -> eax */
        add  esp, 4
        mov  ecx, eax                         /* this = obj */
        push 0x{ATLAS_ROWS:X}                 /* rows */
        push 0x{ATLAS_COLS:X}                 /* cols */
        push 0x{FNAME_VA:X}                   /* "heathen_masks.png" */
        call 0x{LOADER:X}                    /* -> eax = atlas obj (ret 0xc) */
        mov  [0x{MASK_ATLAS_PTR:X}], eax
        /* (3) restore saved masks: LoadLibrary again (cheap; refcounts) + Vv2MaskRestore
           (loads sidecar -> .mtab). Fail-open: no DLL -> skip. */
        push 0x{DLLNAME_VA:X}
        call dword ptr [0x{LOADLIBRARYA_IAT:X}]
        test eax, eax
        jz   no_restore
        push 0x{RESTORE_STR_VA:X}
        push eax
        call dword ptr [0x{GETPROCADDRESS_IAT:X}]
        test eax, eax
        jz   no_restore
        mov  dword ptr [0x{RESTORE_FN:X}], eax   /* cache for the per-frame reload */
        push 0x{DLLNAME_VA:X}
        call dword ptr [0x{LOADLIBRARYA_IAT:X}]
        test eax, eax
        jz   no_restore
        push 0x{SAVE_STR_VA:X}
        push eax                             /* HMODULE for GetProcAddress */
        call dword ptr [0x{GETPROCADDRESS_IAT:X}]
        test eax, eax
        jz   no_restore
        mov  dword ptr [0x{SAVE_FN:X}], eax
    no_restore:
        popad
        jmp  0x{INIT_RET:X}
    """
    init = asm(init_asm, init_va)
    sweep_va = init_va + len(init)

    # ---- SWEEP stub: per-frame free-slot guard (detoured from the village
    # compositor entry 0x445B50, a thiscall with ECX = gameCtx = record[0] base;
    # record[i] = ECX + i*0xE48C, active flag at +0x30). Read-only over records;
    # the only writes are to the R/W .mtab (mask + seen-alive latch), so .vvmk
    # stays R+X (W^X-clean). Replays the 5 displaced entry bytes, then resumes at
    # 0x445B55. ----
    COMPOSITOR_VA = 0x445B50
    sweep_asm = f"""
        pushad
        mov  byte ptr [0x{SWEEP_CLEARED_VA:X}], 0
        /* Slot changed (or first village)? Reload the sidecar before masking.
           Done HERE, not at the save-path hook: that hook fires during load, before
           the villager records exist, so reading there would key against absent
           records. By the first compositor frame they are populated. */
        cmp  byte ptr [0x{LOADED_VA:X}], 0
        jne  slot_ready
        mov  eax, [0x{RESTORE_FN:X}]
        test eax, eax
        jz   slot_ready                      /* no DLL -> nothing to load */
        call eax                             /* Vv2MaskRestore(): reads vv2_masks_<slot>.dat */
        mov  byte ptr [0x{LOADED_VA:X}], 1
    slot_ready:
        /* Vv2MaskRestore is stdcall and may clobber volatile ECX.  Reload the
           compositor receiver saved by pushad (+0x18 in its stack frame)
           before touching record[0].  The old `mov edx, ecx` caused the
           observed first-frame AV at RVA 0xB437C after restore returned. */
        mov  edx, [esp+0x18]                 /* edx = original record[0] base */
        xor  esi, esi                        /* esi = record index i */
    sweep_loop:
        cmp  byte ptr [edx+0x30], 0          /* active flag: 0 = free/dead */
        jne  slot_alive
        cmp  byte ptr [esi+0x{SEEN_ALIVE_VA:X}], 0
        je   slot_next                       /* never seen alive -> leave (load frame) */
        mov  byte ptr [esi+0x{MASK_TABLE_VA:X}], 0   /* died: clear its mask */
        mov  byte ptr [esi+0x{SEEN_ALIVE_VA:X}], 0   /* reset latch for reuse */
        mov  byte ptr [0x{SWEEP_CLEARED_VA:X}], 1
        jmp  slot_next
    slot_alive:
        mov  byte ptr [esi+0x{SEEN_ALIVE_VA:X}], 1   /* latch: seen active */
    slot_next:
        add  edx, 0xE48C
        inc  esi
        cmp  esi, 0x100
        jb   sweep_loop
        /* A dead/reused record must not regain its old mask from the sidecar
           on the next reload. Persist a single post-sweep snapshot only when
           this pass actually cleared one or more masks. */
        cmp  byte ptr [0x{SWEEP_CLEARED_VA:X}], 0
        je   sweep_save_done
        mov  eax, [0x{SAVE_FN:X}]
        test eax, eax
        jz   sweep_save_done
        call eax                             /* Vv2MaskSaveSidecar() */
    sweep_save_done:
        popad
        push ebx                             /* displaced 0x445B50 prologue */
        push ebp
        push esi
        mov  esi, ecx
        jmp  0x{COMPOSITOR_VA + 5:X}
    """
    sweep = asm(sweep_asm, sweep_va)
    slot_va = sweep_va + len(sweep)

    # ---- SLOT stub: detour of the save-path builder 0x403160, the ONLY "%s%d.ldw"
    # builder. arg1 [esp+4] is the slot. Slot 0 is the meta file, never a village, so
    # it is ignored -- capturing it would clobber the real village slot. On a CHANGE we
    # only clear the loaded flag; the sweep does the actual reload on the next frame,
    # because this fires mid-load before the villager records exist. Replays the 6
    # displaced bytes and resumes at 0x403166. ----
    SAVEPATH_VA = 0x403160
    BARREL_PENDING_VA = 0x49C700
    BARREL_UPGRADE_FLAG_VA = 0x49C704
    BARREL_CUE_COUNTER_VA = 0x49C708
    slot_asm = f"""
        push eax
        mov  eax, [esp+8]                    /* +8: our push shifted esp; arg1 = slot */
        test eax, eax
        jz   slot_done                       /* slot 0 = meta file, not a village */
        cmp  eax, [0x{SLOT_VA:X}]
        je   slot_done                       /* same village -> keep masks loaded */
        mov  [0x{SLOT_VA:X}], eax            /* new village */
        mov  byte ptr [0x{LOADED_VA:X}], 0   /* re-arm: sweep reloads next frame */
        /* Queued-event state is per-SAVE but lives in the executable, so it
           follows the player into the next village unless cleared here: the row
           would read "Unavailable" for an event another save bought, and the
           cue counter would carry over and deliver it into a village that never
           paid for it. Absolute stores only -- no register operand, so the
           displaced bytes and the resume are untouched. */
        mov  byte ptr [0x{BARREL_PENDING_VA:X}], 0
        mov  byte ptr [0x{BARREL_UPGRADE_FLAG_VA:X}], 0
        mov  dword ptr [0x{BARREL_CUE_COUNTER_VA:X}], 0
    slot_done:
        pop  eax
        mov  eax, dword ptr [esp+4]          /* displaced */
        mov  edx, dword ptr [ecx]            /* displaced */
        jmp  0x{SAVEPATH_VA + 6:X}
    """
    slot_stub = asm(slot_asm, slot_va)
    end = slot_va + len(slot_stub)
    total = end - CODE_SEC_VA
    assert total <= 0x1000, f".vvmk code section overflow: {total:#x}"
    data[cfoff(slot_va):cfoff(slot_va) + len(slot_stub)] = slot_stub
    # (hook written below, with the other detours)

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

    def foff(va: int) -> int:            # .text hook sites map VA-ImageBase -> file offset
        return va - IMAGE_BASE

    # write the appended .vvmk (R+X) section: filename + stubs. The atlas-ptr dword
    # lives in .mtab (R/W, zero-init) and is filled by the init stub at runtime.
    data[cfoff(FNAME_VA):cfoff(FNAME_VA) + len(FNAME)] = FNAME
    data[cfoff(DLLNAME_VA):cfoff(DLLNAME_VA) + len(DLLNAME)] = DLLNAME
    data[cfoff(RESTORE_STR_VA):cfoff(RESTORE_STR_VA) + len(RESTORE_STR)] = RESTORE_STR
    data[cfoff(EXTRACT_STR_VA):cfoff(EXTRACT_STR_VA) + len(EXTRACT_STR)] = EXTRACT_STR
    data[cfoff(SAVE_STR_VA):cfoff(SAVE_STR_VA) + len(SAVE_STR)] = SAVE_STR
    data[cfoff(code0):cfoff(code0) + len(adult)] = adult
    data[cfoff(child_va):cfoff(child_va) + len(child)] = child
    data[cfoff(init_va):cfoff(init_va) + len(init)] = init
    data[cfoff(sweep_va):cfoff(sweep_va) + len(sweep)] = sweep

    # write hooks (jmp from the fixed .text thunk/init sites into the .vvmk stubs)
    patch_thunk(THUNK_VA, THUNK_LEN, code0, "adult")
    patch_thunk(CHILD_THUNK_VA, CHILD_THUNK_LEN, child_va, "child")
    data[foff(INIT_VA):foff(INIT_VA) + INIT_LEN] = init_hook

    # detour the village compositor entry (0x445B50) into the sweep stub. Its first
    # 5 bytes are `push ebx; push ebp; push esi; mov esi,ecx` (53 55 56 8B F1),
    # replayed at the end of the sweep stub before resuming at 0x445B55.
    # detour the save-path builder (0x403160) into the slot stub. Its first 6 bytes
    # are `mov eax,[esp+4]; mov edx,[ecx]` (8B 44 24 04 8B 11), replayed in the stub
    # before resuming at 0x403166.
    sp_off = SAVEPATH_VA - IMAGE_BASE
    assert bytes(data[sp_off:sp_off + 6]) == bytes([0x8B,0x44,0x24,0x04,0x8B,0x11]),         "save-path builder 0x403160 moved!"
    sp_hook = asm(f"jmp 0x{slot_va:X}", addr=SAVEPATH_VA).ljust(6, bytes([0x90]))
    data[sp_off:sp_off + 6] = sp_hook

    comp_off = COMPOSITOR_VA - IMAGE_BASE
    assert bytes(data[comp_off:comp_off + 5]) == b"\x53\x55\x56\x8b\xf1", \
        "compositor entry 0x445B50 moved!"
    comp_hook = asm(f"jmp 0x{sweep_va:X}", addr=COMPOSITOR_VA)
    assert len(comp_hook) == 5
    data[comp_off:comp_off + 5] = comp_hook

    csum, csum_off = _pe_checksum(data)
    struct.pack_into("<I", data, csum_off, csum)
    out_path.write_bytes(data)

    print(f".vvmk code section {total} B @ 0x{CODE_SEC_VA:X} (limit 0x1000); .mtab table @ 0x{MASK_TABLE_VA:X}")
    print(f"  ptr@0x{MASK_ATLAS_PTR:X} fname@0x{FNAME_VA:X} adult@0x{code0:X} child@0x{child_va:X} init@0x{init_va:X}")
    print(f"hooks: adult 0x{THUNK_VA:X}, child 0x{CHILD_THUNK_VA:X}, init 0x{INIT_VA:X}")
    if force_row is None:
        print(f"gate = PATCH-OWNED table @0x{MASK_TABLE_VA:X} indexed by record index "
              f"(0=no mask); villager records untouched")
    else:
        print(f"FORCE-ROW playtest: row {force_row} on EVERY villager")
    print(f"PE checksum = 0x{csum:08X}")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    args = sys.argv[1:]
    force_row = None
    if "--force-row" in args:
        i = args.index("--force-row")
        force_row = int(args[i + 1])
        del args[i:i + 2]
    src_exe = None
    if "--input" in args:
        i = args.index("--input")
        src_exe = Path(args[i + 1])
        del args[i:i + 2]
    out = Path(args[0]) if args else ROOT / "scratchpad_vv2_mask_stage2.exe"
    build(out, force_row=force_row, src_exe=src_exe)
