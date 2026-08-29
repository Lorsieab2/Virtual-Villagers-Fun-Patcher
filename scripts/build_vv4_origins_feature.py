"""Assemble the exact-build VV4 Origins-exclusive feature patch."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research/stock-executables/Virtual Villagers - The Tree of Life.exe"
OUT_DIR = ROOT / "research/vv4-origins"
OUT_EXE = OUT_DIR / "Virtual Villagers - The Tree of Life - Origins Research.exe"
OUT_JSON = OUT_DIR / "vv4-origins-feature-patches.json"
MANIFEST_JSON = ROOT / "data/vv4_origins_feature.json"

sys.path.insert(0, str(ROOT / ".tools/keystone"))
sys.path.insert(0, str(ROOT / ".tools/keystone-runtime"))
from keystone import KS_ARCH_X86, KS_MODE_32, Ks  # noqa: E402


IMAGE_BASE = 0x400000
PAYLOAD_FILE_OFFSET = 0x89373
PAYLOAD_VA = IMAGE_BASE + PAYLOAD_FILE_OFFSET
PAYLOAD_SIZE = 0xC8D
STRINGS_OFFSET = 0xA00
STRINGS_VA = PAYLOAD_VA + STRINGS_OFFSET
HEAL_CAVE_FILE_OFFSET = 0xCC004
HEAL_CAVE_VA = 0x728004
NATIVE_TECH_TAIL_FILE_OFFSET = 0xCC160
# D166 fix: this cave lives in .shr, whose raw file offset does NOT map
# 1:1 to its runtime VA (raw 0xCC000 maps to RVA 0x328000, i.e. VA
# 0x728000 -- see HEAL_CAVE_VA/VILLAGE_PREFLIGHT_VA a few lines below,
# which correctly hardcode their own .shr VAs the same way). This used to
# read "IMAGE_BASE + NATIVE_TECH_TAIL_FILE_OFFSET" = 0x4CC160, which is a
# real VA -- but inside .data, not .shr. Every "bypass the Tech/Food
# Doubler for an Island Event tail-jump" patch below jumps here; with the
# old value they jumped into unrelated .data bytes instead of this cave.
NATIVE_TECH_TAIL_VA = 0x728160
NATIVE_FOOD_TAIL_FILE_OFFSET = 0xCC170
NATIVE_FOOD_TAIL_VA = 0x728170
CURE_ENTRY_FILE_OFFSET = HEAL_CAVE_FILE_OFFSET
CURE_ENTRY_VA = HEAL_CAVE_VA
EXPANDED_HEAL_CAVE_VA = 0x85A004
SHR_STOCK_VA = 0x728000
SHR_EXPANDED_VA = 0x85A000
VILLAGE_WIDE_SIGNATURE_VA = 0x728220
VILLAGE_WIDE_ENTRY_VA = 0x728240
VILLAGE_PREFLIGHT_FILE_OFFSET = 0xCC180
VILLAGE_PREFLIGHT_VA = 0x728180
# Change Appearance picker-caller lives in the free tail of the .shr helper
# page (the origins feature already maps/marks this whole page executable),
# well past the village-wide payload which ends near 0xCC740 / 0x728740.
APPEARANCE_HELPER_FILE_OFFSET = 0xCC760
APPEARANCE_HELPER_VA = 0x728760
# Deferred Barrel of Babies. A purchased barrel is CUED after a short delay and
# then presented as the game's own native barrel event (the pop-up/animation),
# whose native multi-tick lifecycle delivers the 3 children -- exactly like a
# random barrel, just triggered on demand. do_barrel sets a countdown token in the
# free .shr tail; the barrel_cue helper is spliced onto the game's REAL event
# scheduler tick (0x43FBE5 -> 0x418000) and drains the token each pass. When it
# reaches zero it ARMS the barrel (BARREL_ARMED_VA) so the barrel's eligibility
# check (hooked at 0x414D50) reports eligible; the scheduler then collects, picks,
# presents (0x417790) and activates (0x401D40) the barrel through its own code, so
# the full native event + 3-child spawn (0x414D90) runs in the correct context.
# The scheduler picks randomly among eligible events, so the barrel stays armed
# until it is actually presented -- detected by the per-index cooldown byte the
# scheduler sets on the event it fired (BARREL_COOLDOWN_VA) -- then disarms, so
# exactly one barrel fires. Room is re-checked (mode-aware capacity gate) before
# arming so a full village silently drops the pending barrel instead of overflowing.
#
# NOTE the earlier splice targeted 0x44098C -> 0x4182B0, which is NOT the tick that
# actually drives event scheduling during play (the token never drained there); the
# real driver is 0x43FBE5 -> 0x418000 (0x418000's only caller).
# byte: set by do_barrel so the PURCHASED barrel's spawn always delivers 3 (see
# the 0x414D90 detour below); natural barrels leave it 0 and are unchanged.
BARREL_UPGRADE_FLAG_VA = 0x728B00
BARREL_ARMED_VA = 0x728B04            # byte: barrel is armed-eligible until presented
# Per-event cooldown byte the scheduler sets on the event it presents
# (`mov byte [esi+0x4CC9F4],1`, esi=event index); barrel index 25 -> 0x4CC9F4+0x19.
BARREL_COOLDOWN_VA = 0x4CCA0D
BARREL_COUNTDOWN_FILE_OFFSET = 0xCCB10
BARREL_COUNTDOWN_VA = 0x728B10
# The purchased barrel must ALWAYS deliver 3, so it bypasses the game's tiered
# population gate (0x468350, which caps growth by owned population upgrades). The
# stock barrel spawn (0x414D90) calls 0x468350 before child 2 and before child 3;
# those two INTERNAL calls are redirected to flag-gated checks (0x414D90's entry is
# already owned by an automatic:safety detour, so it cannot be spliced). When the
# purchased-barrel flag is set the checks report "room" -- but still bounded by the
# 150-slot villager record array, since overflowing that array is what corrupted
# saves before -- so all 3 spawn; the second check clears the flag. Natural barrels
# leave the flag 0 and fall through to the stock 0x468350 unchanged.
BARREL_CHECK1_FILE_OFFSET = 0xCCB40
BARREL_CHECK1_VA = 0x728B40
BARREL_CHECK2_FILE_OFFSET = 0xCCB60
BARREL_CHECK2_VA = 0x728B60
BARREL_RECORD_LIMIT = 150               # villager record array size (0x467499 imm)
# Barrel purchase gate: refuse (no charge) only when the 3 children would not fit
# in the record array. The tiered growth cap is intentionally NOT used here -- the
# purchased barrel is allowed to push past it, up to the array limit.
BARREL_CAPACITY_FILE_OFFSET = 0xCCC00
BARREL_CAPACITY_VA = 0x728C00
BARREL_CHILDREN = 3                     # the barrel delivers 3 children
# Complete / Reset All Collections tech rows (9/10). The collectible + goal
# work lives in the companion DLL (ApplyVV4CompleteCollections @101 /
# ApplyVV4ResetCollections @102, which also show the OFFICIAL result box); this
# .shr stub loads the DLL and calls the requested export by ORDINAL (EAX), so no
# new payload strings are needed.
COLLECTIONS_APPLY_FILE_OFFSET = 0xCCD00
COLLECTIONS_APPLY_VA = 0x728D00
COLLECTIONS_COMPLETE_ORDINAL = 101
COLLECTIONS_RESET_ORDINAL = 102
# Scratch .shr slot holding the selected villager's record pointer while the
# Villager (details) menu is open, so the companion DLL can act on that record
# for the "Likes full but a Running dislike was removed" no-change case.
VV4_DETAIL_RECORD_FILE_OFFSET = 0xCCD40
VV4_DETAIL_RECORD_VA = 0x728D40
EXPANDED_VILLAGE_WIDE_ENTRY_VA = 0x85A240
EXPANDED_VILLAGE_PREFLIGHT_VA = 0x85A180
RUNNING_PREFERENCE_ID = 38  # exact-build preference-table evidence: 0xA0CD8
VV4_MASTER_VALUE = 0x42C80000  # Float32 100.0
VV4_NATIVE_SKILL_WRITER_VA = 0x46AD80
VV4_DETAIL_HANDLER_RELOC_OFFSET = 0x235
VV4_RESULT_HELPER_OFFSET = 0x8F3
VV4_RESULT_HELPER_VA = PAYLOAD_VA + VV4_RESULT_HELPER_OFFSET

# --- Heathen-mask cosmetic overlay (thunk-reuse render via companion DLL) ----
# The mask is drawn THROUGH the game's own head-draw thunk (0x409A70) right after
# each head, reusing the head's x/y/facing/TRANSFORM -> the mask inherits the
# game's per-view scroll + scale for free (a raw SDL blit did not, so masks were
# absent in the scrolled world and too small on the scaled portrait). The mask
# atlas is built once as a game ldwImageGrid sprite object (DLL FUN_0040ABA0);
# its object pointer is published to a .shr slot the head cave reads. No villager
# fields written; no atlas/row changes; other features untouched. Caves live in
# the free RWX .shr tail past collections_apply @0x728D00 / detail scratch 0x728D40.
MASK_DLL_ORD_CACHE = 110               # Vv4MaskCacheSurface@4 (sweep + sidecar, per frame)
MASK_DLL_ORD_GET = 114                 # Vv4MaskGetForRecord@4 (ensure atlas + return mask)
MASK_DRAW_THUNK_VA = 0x409A70          # native head-draw thunk (mov ecx,[ecx]; jmp 0x408c40)
MASK_DRAW_REAL = 0x408C40              # the real draw (reads atlas geometry from ecx=this)
MASK_HEAD_CALL_SITES = (0x45F702, 0x45F9CA)  # walking-world twin + panel-portrait twin
MASK_PRESENT_SITE = 0x409458           # `call 0x4046f0` (E8 93B2FFFF); ecx=screen_obj
MASK_PRESENT_CALLEE = 0x4046F0
MASK_LIFT = 0                          # y-lift for face align (atlas is pre-aligned; tune live)
LOADLIBRARYA_THUNK = 0x48A1E0          # call dword ptr [..] (matches collections_apply)
GETPROCADDRESS_THUNK = 0x48A1DC
# .shr data slots (runtime-written; zero at load; page is RWX). 12 dwords,
# 0x728D60..0x728D90 (caves start at 0x728D90):
MASK_SLOT_HMOD = 0x728D60              # HMODULE of the companion DLL
MASK_SLOT_CACHE_PTR = 0x728D64         # resolved Vv4MaskCacheSurface
MASK_SLOT_GET_PTR = 0x728D68           # resolved Vv4MaskGetForRecord
MASK_SLOT_RESOLVED = 0x728D6C          # byte flag: 0 = not yet resolved
MASK_SLOT_ATLAS = 0x728D70             # mask ldwImageGrid obj ptr (DLL publishes here)
# head-cave scratch (saved across the native head draw; single-threaded render,
# non-reentrant, so one shared set serves both twins):
MASK_S_ECX = 0x728D74
MASK_S_ESI = 0x728D78
MASK_S_X = 0x728D7C
MASK_S_Y = 0x728D80
MASK_S_FRAME = 0x728D84                # head facing
MASK_S_TRANSFORM = 0x728D88            # head transform (scroll + scale)
MASK_S_RET = 0x728D8C
# caves (VA / file offset; .shr maps file 0xCC000 -> VA 0x728000):
MASK_RESOLVE_VA = 0x728D90            # ~0x48 bytes -> ends ~0x728DD8
MASK_RESOLVE_FILE_OFFSET = 0xCCD90
MASK_PRESENT_VA = 0x728DE0            # ~0x1B bytes -> ends ~0x728DFB
MASK_PRESENT_FILE_OFFSET = 0xCCDE0
MASK_HEAD_VA = 0x728E10              # ~0x70 bytes -> ends ~0x728E80 (< page end 0x729000)
MASK_HEAD_FILE_OFFSET = 0xCCE10
# --- Walking-WORLD mask (the deferred compositor, separate from the twins) -----
# The visible village villagers are NOT drawn by the FUN_0045f550 twins (that is an
# immediate pass the world paints over) but by FUN_00467da0, run per-villager from
# the queue flush FUN_0044c420 (case 6). Right after its head draw it issues a
# camera-transforming world blit FUN_0044C790 (thiscall, ecx=world mgr 0x4DB9F8,
# ret 0x1c) at the head's world position (EDI/EBP, anchor-adjusted). We WRAP that
# call: run the original, then -- if the villager (esi=record) has a mask -- re-
# issue the SAME blit with arg1=mask atlas and arg4=mask row, so the mask inherits
# the camera scroll/zoom/z-order/clip for free and lands in the final composite.
MASK_WORLD_SITE = 0x468263            # the LAST/topmost head world-blit in FUN_00467da0
                                      # (ECX=[ESI+0x1BB8]=head, drawn at the head's own
                                      # anchor pos EDI/EBP + head scale) -- wrapping THIS
                                      # draws the mask AFTER the head (in front), at the
                                      # head's exact position + scale (tracks head, scales
                                      # with head height on children). 0x4681F9 was an
                                      # earlier body layer the head then painted over.
MASK_WORLD_CALLEE = 0x44C790          # camera world blit; thiscall(mgr; sprite,x,y,idx,frame,f,f)
MASK_WORLD_LIFT = 0                   # head-hook: mask already at the head anchor; ~0 lift
                                      # (mask art is head-aligned). Tune small if needed.
                                      # (masks drew on the chest at 0). World units ->
                                      # c790 scales by camera zoom, so this holds across
                                      # zoom; tune on an adult, add scale-by-arg6 for kids
MASK_WORLD_FACING = 5                 # atlas COLUMN pinned to the front frame: the
                                      # layer's own arg5 is a WALK-ANIMATION frame (mask
                                      # cycled per step); pin to front for a stable mask
                                      # (per-facing LUT is a later refinement, like VV3)
MASK_WORLD_VA = 0x728EB0             # cave in the free .shr tail (head cave ends 0x728EA6)
MASK_WORLD_FILE_OFFSET = 0xCCEB0
# world-cave scratch (mgr/rec/ret + the 7 blit args + fp scratch), past the
# ~0xd4-byte cave (0x728EB0..0x728F84), at 0x728F88..0x728FB4 (< page end 0x729000):
MASK_W_MGR = 0x728F98
MASK_W_REC = 0x728F9C
MASK_W_RET = 0x728FA0
MASK_W_A1 = 0x728FA4                 # arg1 = sprite  (we swap to the mask atlas)
MASK_W_A2 = 0x728FA8                 # arg2 = world x
MASK_W_A3 = 0x728FAC                 # arg3 = world y (we subtract the lift)
MASK_W_A4 = 0x728FB0                 # arg4 = ROW (we set to mask-1; 0-based)
MASK_W_A5 = 0x728FB4                 # arg5 = the resolved sprite frame (unused for column now)
MASK_W_A6 = 0x728FB8                 # arg6 = float (the head/blit SCALE; lift scales by it)
MASK_W_A7 = 0x728FBC                 # arg7 = float
MASK_W_SCRATCH = 0x728FC0            # fistp target for the scaled lift (< page end 0x729000)
# Per-mask vertical nudge table (signed bytes, rows blue/orange/red/purple/chief =
# mask value 1..5, indexed by mask-1). Added at draw time so a tall mask (chief)
# whose face sits low in its uniform cell can be lifted without re-cutting the
# atlas -- the whole-cell shift keeps feathers from clipping. Positive = UP.
# Live-tunable: change the bytes + re-apply the patch, no atlas rebuild.
# (Siblings VV1/VV2/VV3/VV5 all place final alignment in a draw-time nudge.)
MASK_DY_TABLE = 0x728FC4             # 5 signed bytes at 0x728FC4..0x728FC8 (< 0x729000)
MASK_DY_VALUES = (34, 34, 34, 34, 34)  # uniform SCALED vertical re-seat (VV5-measured dy): mask-face-y minus head-face-y, 65x145 cell (X re-seat baked in atlas)

# --- DETAILS bighead mask (portrait FUN_0043cdf0) --------------------------
# Hook the portrait HEAD draw (call 0x409A70 __thiscall, ecx=drawmgr 0x4E00E0) at
# 0x43CFDE; reissue it with the mask atlas obj so the mask rides the bighead at
# its own (large) scale (VV5: pass-through position/scale, same as the village).
# Column = a Details-only facing (right/front/left) -> mask cols 5/6/7; row=color.
# Cave in the big free .shr gap 0x7287A1..0x728B10 (879 bytes).
VV4_DETAIL_MASK_SITE = 0x43CFDE       # `call 0x409A70` (head draw) in FUN_0043cdf0
VV4_DETAIL_MASK_CALLEE = 0x409A70
VV4_DETAIL_MASK_VA = 0x7287A1
VV4_DETAIL_MASK_FILE_OFFSET = 0xCC7A1
VV4_REC_ARRAY_BASE = 0x50E5AC         # villager record array base
VV4_REC_STRIDE = 0x2E3C
VV4_DETAIL_FACING_COL = 1             # FRONT col of the dedicated 3-col bighead atlas (= 8-col frame 6, bighead-res); [right=0,front=1,left=2]
MASK_SLOT_BIGHEAD_ATLAS = 0x728A3C    # dedicated bighead atlas obj ptr (DLL publishes here; free slot past D_TMP)
# scratch (mgr/ret/6 args/index/mask), past the cave:
D_MGR = 0x728A00
D_RET = 0x728A04
D_A1 = 0x728A08                       # atlas (head; we swap to mask)
D_A2 = 0x728A0C                       # x
D_A3 = 0x728A10                       # y
D_A4 = 0x728A14                       # head field
D_A5 = 0x728A18                       # frame
D_A6 = 0x728A1C                       # scale
D_IDX = 0x728A20                      # villager index (param_1 = [ebp+8])
D_MASK = 0x728A24                     # mask-1 (row)
D_SCALE = 0x728A28                    # float scale multiplier (bighead face / mask face)
D_A6S = 0x728A2C                      # scaled arg6 (D_A6 * D_SCALE) for the mask draw
D_LIFTX = 0x728A30                    # float: mask_x = D_A2 - LIFTX * headScale (seat X)
D_LIFTY = 0x728A34                    # float: mask_y = D_A3 - LIFTY * headScale (seat Y)
D_TMP = 0x728A38                      # fistp scratch for the scaled lifts
# DIAGNOSTIC caller-capture: FUN_00409A70 is a thunk (mov ecx,[ecx]; jmp 0x408C40).
# Splice its entry to a cave that dedups the caller's return address into a ring,
# so the per-frame ANIMATED-portrait head-draw caller (which is NOT 0x43CFDE)
# reveals itself. Free .shr gap 0x728A60..0x728D40.
CALLER_CAPTURE_ENABLED = False        # diagnostic toggle (.shr too packed to fit 8 caves)
# Ring + caves in the LOW .shr (0x728100..0x728800): the 0x728A00+ region is used by
# the mask/scratch/record patches (a cave at 0x728BD8 collided), but the low .shr is
# free. .shr maps file 0xCC000 -> VA 0x728000.
CALLER_RING_COUNT = 0x728100          # dword: how many unique caller returns
CALLER_RING = 0x728104                # up to 40 dword caller return addresses
# The 8 sibling blit thunks (VS5's map); the bighead draws through one of them, so
# splice ALL of them. Each cave logs the caller return (dedup) then replays
# `mov ecx,[ecx]; jmp <target>`. Caves 0x40 apart from 0x728200.
CALLER_THUNKS = [
    (0x409960, 0x4086C0), (0x4099F0, 0x4088F0), (0x409A30, 0x408A30),
    (0x409A70, 0x408C40), (0x409AD0, 0x408CF0), (0x409BD0, 0x409700),
    (0x409F90, 0x409370), (0x409FA0, 0x409470),
]
CALLER_CAVES = [0x728200 + i * 0x40 for i in range(len(CALLER_THUNKS))]
import struct as _struct
D_SCALE_VALUE = _struct.pack("<f", 1.5)   # dedicated bighead-res atlas at head arg6 * 1.5 (VV5 landed)
# Seat the SCALED mask's face onto the bighead's face: offset = headFace_incell -
# maskFace_incell * scale, times the head's own scale arg (so children auto-seat).
# bighead face ~(30,28) in its 60px cell; mask face ~(35,53) in the 65px cell:
# X = 35*2.6 - 30 = 61 ; Y = 53*2.6 - 28 = 110. Owner-tunable.
D_LIFTX_VALUE = _struct.pack("<f", 0.15)  # seat for 8-col col5 face (~35,53) @1.3x, int arg6; tune
D_LIFTY_VALUE = _struct.pack("<f", 0.40)  # seat for 8-col col5 face @1.3x; tune

# IDA Pro 9.4 decoded the four current-feature absolute operands that are not
# owned by the generated payload/preflight helpers. They are explicit
# operands, not results of a raw byte sweep.
VV4_ALL_FEATURE_ABSOLUTE_RELOCATIONS = (
    (0x89546, "20827200", 0x489544, 0x728220, 0x85A220),
    (0xCC1AF, "34827200", 0x7281AD, 0x728234, 0x85A234),
    (0xCC1B8, "38827200", 0x7281B6, 0x728238, 0x85A238),
    (0xCC1C1, "3C827200", 0x7281BF, 0x72823C, 0x85A23C),
)


def assemble(source: str, address: int) -> bytes:
    encoding, _ = Ks(KS_ARCH_X86, KS_MODE_32).asm(source, address)
    return bytes(encoding)


def rel32_jump(source_va: int, target_va: int) -> bytes:
    return b"\xE9" + int(target_va - source_va - 5).to_bytes(
        4, "little", signed=True
    )


def rel32_call(source_va: int, target_va: int) -> bytes:
    return b"\xE8" + int(target_va - source_va - 5).to_bytes(
        4, "little", signed=True
    )


def mask_resolve_cave(icons_dll_va: int) -> bytes:
    """Load the companion DLL and resolve the two mask exports by ORDINAL, once.
    Guarded by MASK_SLOT_RESOLVED so it is a cheap flag-check ret on every later
    call. Preserves ebx (the only callee-saved reg it uses); clobbers eax/ecx/edx
    and flags -- callers save what they need around the `call`. On LoadLibrary
    failure it leaves the flag 0 and retries next frame."""
    return assemble(
        f"""
            cmp byte ptr [{MASK_SLOT_RESOLVED}], 0
            jne mr_done
            push ebx
            push 0x{icons_dll_va:X}
            call dword ptr [{LOADLIBRARYA_THUNK}]
            test eax, eax
            jz mr_fail
            mov dword ptr [{MASK_SLOT_HMOD}], eax
            push {MASK_DLL_ORD_CACHE}
            push eax
            call dword ptr [{GETPROCADDRESS_THUNK}]
            mov dword ptr [{MASK_SLOT_CACHE_PTR}], eax
            push {MASK_DLL_ORD_GET}
            push dword ptr [{MASK_SLOT_HMOD}]
            call dword ptr [{GETPROCADDRESS_THUNK}]
            mov dword ptr [{MASK_SLOT_GET_PTR}], eax
            mov byte ptr [{MASK_SLOT_RESOLVED}], 1
        mr_fail:
            pop ebx
        mr_done:
            ret
        """,
        MASK_RESOLVE_VA,
    )


def mask_present_cave() -> bytes:
    """Spliced onto `call 0x4046f0` at MASK_PRESENT_SITE. Entry: ecx=screen_obj
    (thiscall this), [esp]=return(0x40945d), [esp+4]=surface(=[screen_obj+0x30]).
    Resolves the DLL, hands the live render-target surface to Vv4MaskCacheSurface
    (which also runs the clear-on-death sweep), then tail-jumps into the real
    present so ecx/stack are exactly what 0x4046f0 expects."""
    return assemble(
        f"""
            push ecx
            call 0x{MASK_RESOLVE_VA:X}
            mov eax, dword ptr [{MASK_SLOT_CACHE_PTR}]
            test eax, eax
            jz mp_skip
            push dword ptr [esp+8]
            call eax
        mp_skip:
            pop ecx
            jmp 0x{MASK_PRESENT_CALLEE:X}
        """,
        MASK_PRESENT_VA,
    )


def mask_head_cave() -> bytes:
    """Spliced onto BOTH head-draw twins (`call 0x409a70`). Entry: ecx=this
    (sprite mgr), esi=villager record, [esp]=site return, [esp+4..]=stdcall draw
    args (atlas, x, y, idx, frame=facing, transform, 0). It draws the head
    normally (swap the return to post_head, tail into the native thunk which
    returns via ret 0x1c), then draws the villager's mask reusing the head's
    x/y/facing/transform (so scroll+scale are inherited), with idx=mask_row,
    y-=lift. CRITICAL: the mask is drawn by calling the REAL draw 0x408c40
    DIRECTLY with ecx = the mask atlas object -- NOT through the thunk 0x409A70.
    0x408c40 reads the atlas geometry+surface from `this` (ecx); the thunk's
    `mov ecx,[ecx]` turns ecx into the HEAD atlas, so routing the mask through it
    would just redraw the head. The mask value + atlas object come from the DLL
    (Vv4MaskGetForRecord ensures the multi-file atlas is built and published to
    MASK_SLOT_ATLAS). All guarded: no export / mask<=0 / atlas 0 -> nothing drawn.
    Single-threaded, non-reentrant -> one shared scratch set."""

    def src(post_head: int) -> str:
        y_expr = (f"push dword ptr [{MASK_S_Y}]" if MASK_LIFT == 0 else
                  f"mov eax, dword ptr [{MASK_S_Y}]\n            sub eax, {MASK_LIFT}\n            push eax")
        return f"""
            mov dword ptr [{MASK_S_ECX}], ecx
            mov dword ptr [{MASK_S_ESI}], esi
            mov eax, [esp+8]
            mov dword ptr [{MASK_S_X}], eax
            mov eax, [esp+0xC]
            mov dword ptr [{MASK_S_Y}], eax
            mov eax, [esp+0x14]
            mov dword ptr [{MASK_S_FRAME}], eax
            mov eax, [esp+0x18]
            mov dword ptr [{MASK_S_TRANSFORM}], eax
            mov eax, [esp]
            mov dword ptr [{MASK_S_RET}], eax
            mov dword ptr [esp], {post_head}
            jmp 0x{MASK_DRAW_THUNK_VA:X}
        post_head:
            call 0x{MASK_RESOLVE_VA:X}
            mov eax, dword ptr [{MASK_SLOT_GET_PTR}]
            test eax, eax
            jz mh_done
            push dword ptr [{MASK_S_ESI}]
            call eax
            test eax, eax
            jle mh_done
            dec eax
            mov edx, dword ptr [{MASK_SLOT_ATLAS}]
            test edx, edx
            jz mh_done
            push 0
            push dword ptr [{MASK_S_TRANSFORM}]
            push dword ptr [{MASK_S_FRAME}]
            push eax
            {y_expr}
            push dword ptr [{MASK_S_X}]
            push edx
            mov ecx, dword ptr [{MASK_S_ECX}]
            call 0x{MASK_DRAW_THUNK_VA:X}
        mh_done:
            jmp dword ptr [{MASK_S_RET}]
        """
    prologue = src(0).split("post_head:")[0]
    post_head = MASK_HEAD_VA + len(assemble(prologue, MASK_HEAD_VA))
    return assemble(src(post_head), MASK_HEAD_VA)


def mask_world_cave() -> bytes:
    """Spliced onto FUN_00467da0's LAST head world-blit `call 0x44C790` at
    0x468263 (the topmost head layer, so the mask lands in front). Entry: ecx=world
    mgr (0x4DB9F8), esi=villager record, [esp]=site return (0x468268),
    [esp+4..+0x1c]=the 7 blit args
    (sprite,x,y,idx,frame,f,f). It runs the ORIGINAL blit, then -- if the villager
    has a mask and the atlas is built -- re-issues 0x44C790 with the SAME ecx/args
    except arg1=mask atlas obj, arg4=mask row (mask-1), arg3=y-lift. So the mask
    rides the exact camera-transformed world draw the head just used (scroll/zoom/
    z/clip inherited), landing in the FINAL composite instead of an early pass the
    world repaints. All guarded (no export / mask<=0 / atlas 0 -> nothing extra
    drawn). Preserves esi/edi/ebp/ebx (only eax/ecx/edx touched, all caller-saved
    across the original call)."""
    def src(post_orig: int) -> str:
        # y = worldY - MASK_DY[mask-1]*scale. eax still holds mask-1 here (already
        # pushed as arg4), so it indexes the signed per-mask lift table; positive =
        # UP. SCALED by the head's own blit scale (arg6) so the lift seats the mask
        # on the head at every villager size (children/carried). The mask uses its
        # own tall 65x145 cell whose face sits ~68px down from the cell top, so this
        # lift is large (~face-y minus head-face-y). FPU balanced (fild/fistp).
        y3 = (f"movsx eax, byte ptr [eax + {MASK_DY_TABLE}]\n"
              f"            push eax\n"
              f"            fild dword ptr [esp]\n"
              f"            add esp, 4\n"
              f"            fmul dword ptr [{MASK_W_A6}]\n"
              f"            fistp dword ptr [{MASK_W_SCRATCH}]\n"
              f"            mov ecx, dword ptr [{MASK_W_A3}]\n"
              f"            sub ecx, dword ptr [{MASK_W_SCRATCH}]\n"
              f"            push ecx")
        return f"""
            mov dword ptr [{MASK_W_MGR}], ecx
            mov dword ptr [{MASK_W_REC}], esi
            mov eax, [esp]
            mov dword ptr [{MASK_W_RET}], eax
            mov eax, [esp+4]
            mov dword ptr [{MASK_W_A1}], eax
            mov eax, [esp+8]
            mov dword ptr [{MASK_W_A2}], eax
            mov eax, [esp+0xC]
            mov dword ptr [{MASK_W_A3}], eax
            mov eax, [esp+0x10]
            mov dword ptr [{MASK_W_A4}], eax
            mov eax, [esp+0x14]
            mov dword ptr [{MASK_W_A5}], eax
            mov eax, [esp+0x18]
            mov dword ptr [{MASK_W_A6}], eax
            mov eax, [esp+0x1C]
            mov dword ptr [{MASK_W_A7}], eax
            mov dword ptr [esp], {post_orig}
            jmp 0x{MASK_WORLD_CALLEE:X}
        post_orig:
            call 0x{MASK_RESOLVE_VA:X}
            mov eax, dword ptr [{MASK_SLOT_GET_PTR}]
            test eax, eax
            jz mw_done
            push dword ptr [{MASK_W_REC}]
            call eax
            test eax, eax
            jle mw_done
            dec eax
            mov edx, dword ptr [{MASK_SLOT_ATLAS}]
            test edx, edx
            jz mw_done
            push dword ptr [{MASK_W_A7}]
            push dword ptr [{MASK_W_A6}]
            mov ecx, dword ptr [{MASK_W_REC}]
            mov ecx, dword ptr [ecx + 0x1CD4]
            and ecx, 7
            push ecx
            push eax
            {y3}
            push dword ptr [{MASK_W_A2}]
            push edx
            mov ecx, dword ptr [{MASK_W_MGR}]
            call 0x{MASK_WORLD_CALLEE:X}
        mw_done:
            jmp dword ptr [{MASK_W_RET}]
        """
    prologue = src(0).split("post_orig:")[0]
    post_orig = MASK_WORLD_VA + len(assemble(prologue, MASK_WORLD_VA))
    return assemble(src(post_orig), MASK_WORLD_VA)


def mask_detail_cave() -> bytes:
    """Spliced onto the Details portrait HEAD draw `call 0x409A70` at 0x43CFDE
    (__thiscall, ecx=drawmgr 0x4E00E0, callee-cleans 6 args). Entry: ecx=drawmgr,
    [esp]=site return (0x43CFE3), [esp+4..+0x18]=6 head args (atlas,x,y,head,
    frame,scale), [ebp+8]=param_1=villager index. Runs the original head draw,
    then -- if the selected villager has a mask -- reissues 0x409A70 with arg1=
    mask atlas obj, arg4=mask row, arg5=facing col, reusing the head's x/y/scale
    so the mask rides the bighead at its own large portrait scale (VV5 method).

    FACING = the head's OWN frame arg (D_A5) & 7 -- NOT a fixed constant. Per the
    FUN_0043cdf0 decompile, the portrait head frame is the resolver FUN_0044e960's
    output (called with fixed facing + sex + variant; no per-villager facing input,
    so the portrait is effectively fixed-facing). `& 7` extracts the facing COLUMN
    because VV4's head atlas is exactly 8 columns -- if that ever changes, this
    breaks. The only non-facing term folded into the Details frame is the age
    offset local_20 = (age<0x44c)-1 & 8, which is always a multiple of 8, so `& 7`
    strips it and the facing survives age-independently. (No anim term is folded in
    here, unlike the world path.)"""
    def src(post_orig: int) -> str:
        return f"""
            mov dword ptr [{D_MGR}], ecx
            mov eax, [esp+4]
            mov dword ptr [{D_A1}], eax
            mov eax, [esp+8]
            mov dword ptr [{D_A2}], eax
            mov eax, [esp+0xC]
            mov dword ptr [{D_A3}], eax
            mov eax, [esp+0x10]
            mov dword ptr [{D_A4}], eax
            mov eax, [esp+0x14]
            mov dword ptr [{D_A5}], eax
            mov eax, [esp+0x18]
            mov dword ptr [{D_A6}], eax
            mov eax, [esp]
            mov dword ptr [{D_RET}], eax
            mov eax, [ebp+8]
            mov dword ptr [{D_IDX}], eax
            mov dword ptr [esp], {post_orig}
            mov ecx, dword ptr [{D_MGR}]
            jmp 0x{VV4_DETAIL_MASK_CALLEE:X}
        post_orig:
            call 0x{MASK_RESOLVE_VA:X}
            mov eax, dword ptr [{MASK_SLOT_GET_PTR}]
            test eax, eax
            jz det_done
            mov eax, dword ptr [{D_IDX}]
            imul eax, eax, {VV4_REC_STRIDE}
            add eax, {VV4_REC_ARRAY_BASE}
            push eax
            mov eax, dword ptr [{MASK_SLOT_GET_PTR}]
            call eax
            test eax, eax
            jle det_done
            dec eax
            mov dword ptr [{D_MASK}], eax
            mov edx, dword ptr [{MASK_SLOT_BIGHEAD_ATLAS}]
            test edx, edx
            jz det_done
            fild dword ptr [{D_A6}]
            fmul dword ptr [{D_SCALE}]
            fistp dword ptr [{D_A6S}]
            push dword ptr [{D_A6S}]
            push {VV4_DETAIL_FACING_COL}
            push dword ptr [{D_MASK}]
            fild dword ptr [{D_A6}]
            fmul dword ptr [{D_LIFTY}]
            fistp dword ptr [{D_TMP}]
            mov ecx, dword ptr [{D_A3}]
            sub ecx, dword ptr [{D_TMP}]
            push ecx
            fild dword ptr [{D_A6}]
            fmul dword ptr [{D_LIFTX}]
            fistp dword ptr [{D_TMP}]
            mov ecx, dword ptr [{D_A2}]
            sub ecx, dword ptr [{D_TMP}]
            push ecx
            push edx
            mov ecx, dword ptr [{D_MGR}]
            call 0x{VV4_DETAIL_MASK_CALLEE:X}
        det_done:
            jmp dword ptr [{D_RET}]
        """
    prologue = src(0).split("post_orig:")[0]
    post_orig = VV4_DETAIL_MASK_VA + len(assemble(prologue, VV4_DETAIL_MASK_VA))
    return assemble(src(post_orig), VV4_DETAIL_MASK_VA)


def caller_capture_cave(cave_va: int, target_va: int) -> bytes:
    """Diagnostic: spliced onto a blit-thunk entry. Dedups the caller's return
    address ([esp] at entry, since we JMP in) into the shared ring at CALLER_RING,
    then replays the thunk (mov ecx,[ecx]; jmp <target_va>). The DLL present hook
    dumps the ring so the bighead's per-frame draw caller is identifiable across
    all 8 sibling thunks."""
    src = f"""
            pushfd
            pushad
            mov ebx, dword ptr [esp+0x24]
            mov esi, {CALLER_RING}
            mov ecx, dword ptr [{CALLER_RING_COUNT}]
            xor edi, edi
            test ecx, ecx
            jz cc_add
        cc_scan:
            cmp dword ptr [esi+edi*4], ebx
            je cc_out
            inc edi
            cmp edi, ecx
            jl cc_scan
        cc_add:
            cmp ecx, 40
            jge cc_out
            mov dword ptr [esi+ecx*4], ebx
            inc dword ptr [{CALLER_RING_COUNT}]
        cc_out:
            popad
            popfd
            mov ecx, dword ptr [ecx]
            jmp 0x{target_va:X}
    """
    return assemble(src, cave_va)


def add_c_string(blob: bytearray, labels: dict[str, int], name: str, value: str) -> None:
    labels[name] = STRINGS_VA + len(blob)
    blob.extend(value.encode("ascii") + b"\0")


def main() -> None:
    original = STOCK.read_bytes()
    expected_sha256 = (
        "6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220"
    )
    actual_sha256 = hashlib.sha256(original).hexdigest().upper()
    if actual_sha256 != expected_sha256:
        raise RuntimeError(
            f"stock SHA-256 mismatch: expected {expected_sha256}, got {actual_sha256}"
        )
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    strings = bytearray()
    s: dict[str, int] = {}
    for name, value in (
        ("button_label", "Upgrades"),
        ("tech_title", "Origins Upgrades"),
        ("detail_title", "Villager Upgrades"),
        ("purchased", "Purchased."),
        ("removed", "Removed."),
        ("not_enough", "Not enough tech points."),
        ("paused", "Time Warp is unavailable while the game is paused."),
        ("capacity", "The village population is already at maximum capacity."),
        ("running_unavailable", "Running cannot be added."),
        ("icons_dll", "VVFP VV4 Origins Icons.dll"),
        ("show_dialog_export", "ShowOriginsUpgradeMenuState"),
        ("show_result_export", "ShowOriginsVillageWideResult"),
        ("message_export", "ShowOriginsUpgradeMessage"),
        ("cure_all", "Full Heal/Cure All Villagers"),
        ("show_appearance_picker", "ShowOriginsAppearancePicker"),
        ("show_cure_result", "ShowOriginsCureResult"),
    ):
        add_c_string(strings, s, name, value)
    while len(strings) % 4:
        strings.append(0)
    s["tech_costs"] = STRINGS_VA + len(strings)
    for value in (50000, 30000, 75000, 500000, 500000, 30000):
        strings.extend(value.to_bytes(4, "little"))
    s["detail_costs"] = STRINGS_VA + len(strings)
    for value in (50000, 100000, 40000, 50000, 5000):
        strings.extend(value.to_bytes(4, "little"))
    if len(strings) > PAYLOAD_SIZE - STRINGS_OFFSET:
        raise RuntimeError("VV4 Origins strings exceed the validated cave")

    tech_handler = PAYLOAD_VA + 0x000
    tech_constructor = PAYLOAD_VA + 0x040
    detail_handler = PAYLOAD_VA + 0x0C0
    detail_constructor = PAYLOAD_VA + 0x100
    barrel_eligibility = PAYLOAD_VA + 0x180
    show_dialog = PAYLOAD_VA + 0x1B0
    show_message = PAYLOAD_VA + 0x200
    tech_menu = PAYLOAD_VA + 0x260
    detail_menu = PAYLOAD_VA + 0x500
    tech_increment = PAYLOAD_VA + 0x890
    food_increment = PAYLOAD_VA + 0x930

    code = bytearray(b"\0" * STRINGS_OFFSET)
    occupied = bytearray(b"\0" * STRINGS_OFFSET)

    def put(va: int, source: str) -> None:
        payload = assemble(source, va)
        start = va - PAYLOAD_VA
        end = start + len(payload)
        if start < 0 or end > len(code):
            raise RuntimeError(f"code at {va:#x} exceeds the VV4 Origins code block")
        if any(occupied[start:end]):
            raise RuntimeError(f"code overlap at {va:#x}, size {len(payload):#x}")
        code[start:end] = payload
        occupied[start:end] = b"\1" * len(payload)

    put(
        tech_handler,
        f"""
            cmp dword ptr [esp + 4], 8
            jne original
            cmp dword ptr [esp + 8], 13
            jne original
            call 0x{tech_menu:X}
            xor eax, eax
            ret 8
        original:
            push edi
            mov edi, ecx
            call 0x44DA20
            jmp 0x43E9F8
        """,
    )
    put(
        tech_constructor,
        f"""
            push 0x14
            call 0x470C5C
            add esp, 4
            test eax, eax
            je done
            push 0x3F800000
            push 0
            push 13
            push 0x{s['button_label']:X}
            push 572
            push 560
            push esi
            mov ecx, eax
            call 0x40D8A0
            push eax
            mov ecx, esi
            call 0x40C190
        done:
            mov eax, esi
            mov ecx, dword ptr [esp + 0x4C]
            jmp 0x43E16B
        """,
    )
    put(
        detail_handler,
        f"""
            cmp dword ptr [esp + 4], 8
            jne original
            cmp dword ptr [esp + 8], 2
            jne original
            call 0x{detail_menu:X}
            xor eax, eax
            ret 8
        original:
            sub esp, 0x18
            mov eax, dword ptr [0x4C9FBC]
            jmp 0x448618
        """,
    )
    put(
        detail_constructor,
        f"""
            push 0x14
            call 0x470C5C
            add esp, 4
            test eax, eax
            je done
            push 0x3F800000
            push 0
            push 2
            push 0x{s['button_label']:X}
            push 520
            push 600
            push esi
            mov ecx, eax
            call 0x40D8A0
            push eax
            mov ecx, esi
            call 0x40C190
        done:
            mov dword ptr [0x4D905C], 0
            mov dword ptr [0x4D9058], 0
            mov eax, esi
            jmp 0x447A33
        """,
    )
    put(
        barrel_eligibility,
        f"""
            cmp byte ptr [0x{BARREL_ARMED_VA:X}], 0
            jz original
            mov al, 1
            ret
        original:
            mov ecx, 0x50E568
            jmp 0x414D55
        """,
    )
    put(
        show_dialog,
        f"""
            push ebx
            push esi
            push 0x{s['icons_dll']:X}
            call dword ptr [0x48A1E0]
            test eax, eax
            je unavailable
            push 0x{s['show_dialog_export']:X}
            push eax
            call dword ptr [0x48A1DC]
            test eax, eax
            je unavailable
            cmp dword ptr [0x{VILLAGE_WIDE_SIGNATURE_VA:X}], 0x50465656
            jne no_village_wide
            or dword ptr [esp + 0x10], 0xA0000
        no_village_wide:
            push dword ptr [esp + 0x10]
            push dword ptr [esp + 0x10]
            call eax
            pop esi
            pop ebx
            ret 8
        unavailable:
            mov eax, -1
            pop esi
            pop ebx
            ret 8
        """,
    )
    # Single source of truth for the status popup helper. It is placed at
    # `show_message` AND copied verbatim into the pinned result-helper cave
    # (see below). Every reference is absolute (string VAs, IAT slots) or an
    # internal rel8 jump, so the bytes are position-independent -- deriving the
    # cave copy from this same source keeps its baked string VAs in lockstep
    # with the current string table instead of rotting when strings shift.
    show_message_source = f"""
            push ebx
            push esi
            mov ebx, dword ptr [esp + 0x0C]
            mov esi, dword ptr [esp + 0x10]
            push 0x{s['icons_dll']:X}
            call dword ptr [0x48A1E0]
            test eax, eax
            je done
            push 0x{s['message_export']:X}
            push eax
            call dword ptr [0x48A1DC]
            test eax, eax
            je done
            push esi
            push ebx
            call eax
        done:
            pop esi
            pop ebx
            ret 8
        """
    put(show_message, show_message_source)
    put(
        tech_menu,
        f"""
            push ebx
            push esi
            push edi
            push ebp
            mov esi, ecx
        menu_loop:
            xor eax, eax
            test dword ptr [0x4D6E10], 1
            jz tech_not_owned
            or eax, 8
        tech_not_owned:
            test dword ptr [0x4D6E10], 2
            jz food_not_owned
            or eax, 16
        food_not_owned:
            # Tech/Food Doublers must be purchasable when unowned: show the
            # default "Buy" control (owned rows still resolve to "Remove" via
            # the eax bit-3/bit-4 owned flags set above).  The former
            # `or eax, 0x1800` set the row 3/4 "Unavailable" flags
            # unconditionally, which blocked both doublers from ever being
            # bought no matter how many tech points the player had.
            push eax
            push 0
            call 0x{show_dialog:X}
            cmp eax, -1
            je menu_done
            mov ebx, eax
            cmp ebx, 3
            jb preflight
            cmp ebx, 5
            jae preflight
            cmp ebx, 4
            je maybe_remove_food
            test dword ptr [0x4D6E10], 1
            jz preflight
            and dword ptr [0x4D6E10], 0xFFFFFFFE
            mov eax, 0x{s['removed']:X}
            jmp status
        maybe_remove_food:
            test dword ptr [0x4D6E10], 2
            jz preflight
            and dword ptr [0x4D6E10], 0xFFFFFFFD
            mov eax, 0x{s['removed']:X}
            jmp status
        preflight:
            cmp ebx, 0
            jne maybe_barrel
            call 0x41FE70
            cmp dword ptr [eax + 0x17110], 999
            jne charge
            mov eax, 0x{s['paused']:X}
            jmp status
        maybe_barrel:
            cmp ebx, 2
            jne charge
            call 0x{BARREL_CAPACITY_VA:X}
            test eax, eax
            jnz charge
            mov eax, 0x{s['capacity']:X}
            jmp status
        charge:
            cmp ebx, 9
            jae do_collections
            cmp ebx, 6
            jb legacy_charge
            cmp ebx, 8
            ja menu_loop
            call 0x{VILLAGE_PREFLIGHT_VA:X}
            test eax, eax
            jz menu_loop
            cmp dword ptr [0x4D6F88], 1000000
            jb insufficient
            mov eax, -1000000
            push eax
            mov ecx, 0x4D6F88
            call 0x41E300
            jmp do_village_wide
        do_collections:
            cmp dword ptr [0x4D6F88], 1000000
            jb insufficient
            mov eax, -1000000
            push eax
            mov ecx, 0x4D6F88
            call 0x41E300
            # Rows 9-12 map to DLL ordinals 101-104 (9=Complete, 10=Reset
            # Collections, 11=Equal Division +Parenting, 12=Equal Division
            # -Parenting): ordinal = ebx + 92.
            lea eax, [ebx + 92]
            call 0x{COLLECTIONS_APPLY_VA:X}
            test eax, eax
            jnz menu_done
            # DLL reported no change (already fully found / already cleared /
            # no eligible villagers): refund the 1,000,000 directly.
            add dword ptr [0x4D6F88], 1000000
            jmp menu_done
        legacy_charge:
            mov eax, dword ptr [0x{s['tech_costs']:X} + ebx*4]
            cmp dword ptr [0x4D6F88], eax
            jb insufficient
            neg eax
            push eax
            mov ecx, 0x4D6F88
            call 0x41E300
            cmp ebx, 0
            je do_time_warp
            cmp ebx, 1
            je do_island_event
            cmp ebx, 2
            je do_barrel
            cmp ebx, 3
            je do_tech_doubler
            cmp ebx, 4
            je do_food_doubler
            cmp ebx, 5
            je do_cure
            call 0x{HEAL_CAVE_VA:X}
            nop
            jmp success


        do_cure:
            call 0x{HEAL_CAVE_VA:X}
            jmp menu_done
        do_village_wide:
            call 0x{HEAL_CAVE_VA:X}
            jmp menu_done
        do_time_warp:
            call 0x41FE70
            mov eax, dword ptr [eax + 0x17110]
            cmp eax, 3
            je time_apply
            cmp eax, 10
            je time_apply
            mov eax, 6
        time_apply:
            imul eax, eax, 3600
            sub dword ptr [0x4B8230], eax
            sbb dword ptr [0x4B8234], 0
            jmp success
        do_island_event:
            call 0x41FE70
            mov dword ptr [eax + 0x170E0], 0
            jmp success
        do_barrel:
            # Arm the barrel, flag this as the PURCHASED barrel (so its spawn always
            # delivers 3 via the 0x414D90 detour), then cue the game's own event
            # check to fire now by setting the island-event target time to 0 (exactly
            # how the Island Event upgrade triggers an event -- [world+0x170E0]=0).
            # barrel_cue then presents the NATIVE barrel event (index 25); its
            # lifecycle runs 0x414D90, which the detour turns into the 3-child spawn.
            mov byte ptr [0x{BARREL_ARMED_VA:X}], 1
            mov byte ptr [0x{BARREL_UPGRADE_FLAG_VA:X}], 1
            mov byte ptr [0x{BARREL_COOLDOWN_VA:X}], 0
            call 0x41FE70
            mov dword ptr [eax + 0x170E0], 0
            jmp success
        do_tech_doubler:
            or dword ptr [0x4D6E10], 1
            jmp success
        do_food_doubler:
            or byte ptr [0x4D6E10], 2
        success:
            mov eax, 0x{s['purchased']:X}
            jmp status
        insufficient:
            mov eax, 0x{s['not_enough']:X}
            jmp status
        status:
            push eax
            push 0x{s['tech_title']:X}
            call 0x{show_message:X}
            jmp menu_done
        menu_done:
            pop ebp
            pop edi
            pop esi
            pop ebx
            ret
        """,
    )
    put(
        detail_menu,
        f"""
            push ebx
            push esi
            push edi
            push ebp
            mov esi, ecx
        detail_loop:
            call 0x41FE70
            mov ecx, dword ptr [eax + 0x171B0]
            cmp ecx, dword ptr [0x467499]
            jae detail_done
            push ecx
            mov ecx, 0x50E568
            call 0x466040
            test eax, eax
            je detail_done
            mov edx, eax
            cmp byte ptr [edx + 0x1CC4], 0
            je detail_done
            xor edi, edi
            cmp dword ptr [edx + 0x1B8C], 100
            ja youth_not_done
            or edi, 1
        youth_not_done:
            cmp dword ptr [edx + 0x1C5C], 0x{VV4_MASTER_VALUE:X}
            jne mastery_not_done
            cmp dword ptr [edx + 0x1C60], 0x{VV4_MASTER_VALUE:X}
            jne mastery_not_done
            cmp dword ptr [edx + 0x1C64], 0x{VV4_MASTER_VALUE:X}
            jne mastery_not_done
            cmp dword ptr [edx + 0x1C68], 0x{VV4_MASTER_VALUE:X}
            jne mastery_not_done
            cmp dword ptr [edx + 0x1C6C], 0x{VV4_MASTER_VALUE:X}
            jne mastery_not_done
            or edi, 2
        mastery_not_done:
            xor ebp, ebp
            lea eax, [edx + 0x1E60]
            mov ecx, 3
        like_scan:
            cmp dword ptr [eax], {RUNNING_PREFERENCE_ID}
            je like_found
            cmp dword ptr [eax], -1
            jne like_next
            or ebp, 1
        like_next:
            add eax, 4
            dec ecx
            jne like_scan
            test ebp, 1
            jnz running_state
            or edi, 0x400
            jmp running_state
        like_found:
            or ebp, 2
        running_state:
            lea eax, [edx + 0x1E6C]
            mov ecx, 3
        dislike_scan:
            cmp dword ptr [eax], {RUNNING_PREFERENCE_ID}
            jne dislike_next
            or ebp, 4
        dislike_next:
            add eax, 4
            dec ecx
            jne dislike_scan
            test ebp, 2
            jz age_state
            test ebp, 4
            jnz age_state
            or edi, 4
        age_state:
            cmp dword ptr [edx + 0x1B8C], 360
            jne age_done
            or edi, 8
        age_done:
            test ebp, 4
            jz record_store
            or edi, 0x2000
        record_store:
            mov dword ptr [0x{VV4_DETAIL_RECORD_VA:X}], edx
        show:
            push edi
            push 1
            call 0x{show_dialog:X}
            cmp eax, -1
            je detail_done
            mov ebx, eax
            call 0x41FE70
            mov ecx, dword ptr [eax + 0x171B0]
            cmp ecx, dword ptr [0x467499]
            jae detail_done
            push ecx
            mov ecx, 0x50E568
            call 0x466040
            test eax, eax
            je detail_done
            mov edx, eax
            cmp ebx, 4
            je detail_appearance
            cmp ebx, 2
            jne detail_charge
            lea eax, [edx + 0x1E60]
            mov ecx, 3
        running_preflight:
            cmp dword ptr [eax], {RUNNING_PREFERENCE_ID}
            je running_already
            cmp dword ptr [eax], -1
            je detail_charge
            add eax, 4
            dec ecx
            jne running_preflight
            mov eax, 0x{s['running_unavailable']:X}
            jmp detail_status
        running_already:
            mov eax, 0x{s['running_unavailable']:X}
            jmp detail_status
        detail_charge:
            mov eax, dword ptr [0x{s['detail_costs']:X} + ebx*4]
            cmp dword ptr [0x4D6F88], eax
            jb detail_insufficient
            neg eax
            push eax
            mov ecx, 0x4D6F88
            call 0x41E300
            cmp ebx, 0
            je youth
            cmp ebx, 1
            je mastery
            cmp ebx, 2
            je running
            mov dword ptr [edx + 0x1B8C], 360
            jmp detail_success
        detail_appearance:
            cmp dword ptr [0x4D6F88], 5000
            jb detail_insufficient
            call 0x{APPEARANCE_HELPER_VA:X}
            test eax, eax
            je detail_loop
            jmp detail_success
        youth:
            mov eax, dword ptr [edx + 0x1B8C]
            sub eax, 700
            cmp eax, 100
            jge youth_ready
            mov eax, 100
        youth_ready:
            mov dword ptr [edx + 0x1B8C], eax
            jmp detail_success
        mastery:
            push esi
            mov esi, edx
            {
                ''.join(
                    f"""
            cmp dword ptr [esi + 0x{offset:X}], 0x{VV4_MASTER_VALUE:X}
            je detail_mastery_next_{index}
            push 0x{VV4_MASTER_VALUE:X}
            fld dword ptr [esp]
            fsub dword ptr [esi + 0x{offset:X}]
            fstp dword ptr [esp]
            push {index}
            lea ecx, [esi + 0x1C5C]
            call 0x{VV4_NATIVE_SKILL_WRITER_VA:X}
        detail_mastery_next_{index}:
                    """
                    for index, offset in enumerate((0x1C5C, 0x1C60, 0x1C64, 0x1C68, 0x1C6C))
                )
            }
            cmp dword ptr [esi + 0x1C5C], 0x{VV4_MASTER_VALUE:X}
            jne detail_mastery_failed
            cmp dword ptr [esi + 0x1C60], 0x{VV4_MASTER_VALUE:X}
            jne detail_mastery_failed
            cmp dword ptr [esi + 0x1C64], 0x{VV4_MASTER_VALUE:X}
            jne detail_mastery_failed
            cmp dword ptr [esi + 0x1C68], 0x{VV4_MASTER_VALUE:X}
            jne detail_mastery_failed
            cmp dword ptr [esi + 0x1C6C], 0x{VV4_MASTER_VALUE:X}
            jne detail_mastery_failed
            pop esi
            jmp detail_success
        detail_mastery_failed:
            pop esi
            mov eax, 0x{s['not_enough']:X}
            jmp detail_status
        running:
            # A free Like slot was proven in the pre-charge running_preflight.
            # Grant Running through the game's managed like helpers (add-to-
            # likes 0x45D2D0, remove-from-dislikes 0x45D1C0) rather than raw
            # array writes, which corrupt the like state and crash the game.
            # Both are thiscall/ret 4 and clobber EAX/ECX/EDX, so preserve the
            # record pointer (EDX) across them on the stack.
            push edx
            push {RUNNING_PREFERENCE_ID}
            lea ecx, [edx + 0x1E60]
            call 0x45D2D0
            mov edx, dword ptr [esp]
            push {RUNNING_PREFERENCE_ID}
            lea ecx, [edx + 0x1E6C]
            call 0x45D1C0
            add esp, 4
        detail_success:
            mov eax, 0x{s['purchased']:X}
            jmp detail_status
        detail_insufficient:
            mov eax, 0x{s['not_enough']:X}
        detail_status:
            push eax
            push 0x{s['detail_title']:X}
            call 0x{show_message:X}
            jmp detail_loop
        detail_done:
            pop ebp
            pop edi
            pop esi
            pop ebx
            ret
        """,
    )
    tech_exclusions = (
        0x41447C,
        0x414498,
        0x4144B4,
        0x414A2D,
        0x464E5D,
        0x464E87,
        0x464EB0,
    )
    tech_checks = "\n".join(
        f"cmp dword ptr [esp], 0x{return_va:X}\nje apply" for return_va in tech_exclusions
    )
    put(
        tech_increment,
        f"""
            mov eax, dword ptr [esp + 4]
            test eax, eax
            jle apply
            test dword ptr [0x4D6E10], 1
            jz apply
            {tech_checks}
            shl dword ptr [esp + 4], 1
        apply:
            push esi
            mov esi, dword ptr [esp + 8]
            add dword ptr [ecx], esi
            jmp 0x41E307
        """,
    )
    food_exclusions = (
        0x41494E,
        0x4643EB,
        0x464438,
        0x464497,
        0x464510,
        0x464578,
        0x4645B5,
        0x464600,
    )
    food_checks = "\n".join(
        f"cmp dword ptr [esp + 8], 0x{return_va:X}\nje apply"
        for return_va in food_exclusions
    )
    put(
        food_increment,
        f"""
            test esi, esi
            jle apply
            test dword ptr [0x4D6E10], 2
            jz apply
            {food_checks}
            add esi, esi
        apply:
            test esi, esi
            jle nonpositive
            push esi
            jmp 0x41D954
        nonpositive:
            jmp 0x41D987
        """,
    )

    payload = code + strings
    # The exact VV4 UI audit found that the old generic control factory
    # (0x40D8A0) is not the native VV4 button ABI.  Reuse the independently
    # assembled native factory/destructor/result-helper blocks while keeping
    # this current menu payload as their input.  The helper only replaces its
    # certified zero caves and preserves the stock event fall-through code.
    sys.path.insert(0, str(ROOT / "scripts"))
    from build_vv4_full_mastery_candidate import build_ui_payload  # noqa: E402

    payload, ui_metadata = build_ui_payload(
        bytes(payload), repair_result_helper=False
    )
    payload = bytearray(payload)
    # Copy the status popup helper into the pinned cave. Derive it from the
    # exact source used for `show_message` (position-independent) so its baked
    # string VAs always match the current string table -- a frozen hex blob
    # here silently rotted whenever a string was added/removed, pointing
    # LoadLibrary at the wrong string so no popup ever appeared.
    result_helper_bytes = assemble(show_message_source, VV4_RESULT_HELPER_VA)
    if any(payload[VV4_RESULT_HELPER_OFFSET : VV4_RESULT_HELPER_OFFSET + len(result_helper_bytes)]):
        raise RuntimeError("VV4 result-helper cave is not zero")
    payload[VV4_RESULT_HELPER_OFFSET : VV4_RESULT_HELPER_OFFSET + len(result_helper_bytes)] = result_helper_bytes
    result_repairs = []
    for call_offset in range(len(payload) - 4):
        if payload[call_offset] != 0xE8:
            continue
        source_va = PAYLOAD_VA + call_offset
        target_va = source_va + 5 + int.from_bytes(
            payload[call_offset + 1 : call_offset + 5], "little", signed=True
        )
        if target_va != 0x489573:
            continue
        replacement = VV4_RESULT_HELPER_VA - (source_va + 5)
        payload[call_offset + 1 : call_offset + 5] = replacement.to_bytes(
            4, "little", signed=True
        )
        result_repairs.append(f"0x{source_va:X}")
    if len(result_repairs) != 2:
        raise RuntimeError(f"expected two VV4 result-helper call repairs, got {result_repairs}")
    ui_metadata["result_helper"] = {
        "offset": f"0x{VV4_RESULT_HELPER_OFFSET:X}",
        "virtual_address": f"0x{PAYLOAD_VA + VV4_RESULT_HELPER_OFFSET:X}",
        "sha256": hashlib.sha256(result_helper_bytes).hexdigest().upper(),
        "call_sites": result_repairs,
    }
    payload = bytes(payload)
    expanded_shr_relocations: list[dict[str, str]] = []
    # The payload calls the Cure helper in the stock .shr mapping.  VV4's
    # expanded executable maps that section at a different VA, so preserve
    # the guarded rel32 operand and let the renderer retarget it after the
    # expanded population manifest has been applied.
    for payload_offset in range(len(payload) - 4):
        if payload[payload_offset] != 0xE8:
            continue
        rel = int.from_bytes(
            payload[payload_offset + 1 : payload_offset + 5], "little", signed=True
        )
        source_va = PAYLOAD_VA + payload_offset
        target_va = source_va + 5 + rel
        expanded_target = {
            HEAL_CAVE_VA: EXPANDED_HEAL_CAVE_VA,
            VILLAGE_PREFLIGHT_VA: EXPANDED_VILLAGE_PREFLIGHT_VA,
            VILLAGE_WIDE_ENTRY_VA: EXPANDED_VILLAGE_WIDE_ENTRY_VA,
        }.get(target_va)
        if expanded_target is not None:
            expanded_shr_relocations.append(
                {
                    "offset": f"0x{PAYLOAD_FILE_OFFSET + payload_offset + 1:X}",
                    "before": payload[payload_offset + 1 : payload_offset + 5].hex().upper(),
                    "kind": "rel32",
                    "source_virtual_address": f"0x{source_va:X}",
                    "target_stock_virtual_address": f"0x{target_va:X}",
                    "target_expanded_virtual_address": f"0x{expanded_target:X}",
                    "purpose": "relocate VV4 Origins .shr helper call for expanded 256 mode",
                }
            )
    patches: list[dict[str, str | int]] = []

    def patch(offset: int, before: bytes, after: bytes, purpose: str) -> None:
        actual = original[offset : offset + len(before)]
        if actual != before:
            raise RuntimeError(
                f"guard mismatch at {offset:#x}: expected {before.hex()}, got {actual.hex()}"
            )
        if len(before) != len(after):
            raise RuntimeError(f"length mismatch at {offset:#x}")
        patches.append(
            {
                "offset": f"0x{offset:X}",
                "before": before.hex().upper(),
                "after": after.hex().upper(),
                "purpose": purpose,
            }
        )

    cure_code = assemble(
        f"""
            cmp ebx, 5
            je cure_all
            cmp ebx, 6
            jae village_wide
            or dword ptr [0x4D6E10], 2
            ret
        village_wide:
            push ebx
            push ebp
            push ecx
            push edx
            push esi
            push edi
            mov eax, ebx
            mov ecx, 0x50E5AC
            mov edx, dword ptr [0x42001C]
            call 0x{VILLAGE_WIDE_ENTRY_VA:X}
            mov ebp, eax
            mov edi, edx
            mov esi, ecx
            mov eax, 0x{s['show_result_export']:X}
            push 0x{s['icons_dll']:X}
            call dword ptr [0x48A1E0]
            test eax, eax
            je village_result_done
            push 0x{s['show_result_export']:X}
            push eax
            call dword ptr [0x48A1DC]
            test eax, eax
            je village_result_done
            push esi
            push edi
            push ebp
            push ebx
            call eax
        village_result_done:
            pop edi
            pop esi
            pop edx
            pop ecx
            pop ebp
            pop ebx
            ret
        cure_all:
            push ebx
            push ebp
            push ecx
            push edx
            push esi
            push edi
            xor ebp, ebp
            xor edi, edi
            mov edx, 0x50E5AC
            mov ecx, dword ptr [0x42001C]
        cure_loop:
            mov esi, edx
            cmp byte ptr [esi + 0x1CC4], 0
            je cure_next
            cmp byte ptr [esi + 0x1CC7], 0
            jne cure_next
            cmp dword ptr [esi + 0x1C40], 0
            jle cure_next
            cmp dword ptr [esi + 0x1C40], 100
            jge cure_health_done
            # Native VV4 health setter: ECX=record+0x1C34, push -1 and
            # target 100, callee ret 8.  Save the walker state (ecx loop
            # counter, ebp restored count, edi sickness count) because this
            # is a native call, not an inline field assignment.
            push ecx
            push ebp
            push edi
            lea eax, [esi + 0x1C34]
            mov ecx, eax
            push -1
            push 100
            call 0x46AF00
            pop edi
            pop ebp
            pop ecx
            cmp dword ptr [esi + 0x1C40], 100
            jne cure_health_done
            inc ebp
        cure_health_done:
            cmp byte ptr [esi + 0x1C48], 0
            je cure_next
            mov byte ptr [esi + 0x1C48], 0
            inc dword ptr [0x4D6DF0]
            inc edi
        cure_next:
            mov edx, esi
            add edx, 0x2E3C
            dec ecx
            jne cure_loop
            # ebp = villagers restored to full health, edi = villagers whose
            # sickness was cleared.  Let the companion DLL format+show the
            # exact two-line result (or the all-healthy notice); it returns 1
            # when anything was done, 0 when nothing was (both counts zero).
            push 0x{s['icons_dll']:X}
            call dword ptr [0x48A1E0]
            test eax, eax
            je cure_ret
            push 0x{s['show_cure_result']:X}
            push eax
            call dword ptr [0x48A1DC]
            test eax, eax
            je cure_ret
            push ebp
            push edi
            call eax
            test eax, eax
            jnz cure_ret
            # Nothing to heal: refund the 30,000 the tech menu already charged.
            # Add directly (not through the doubler-hooked 0x41E300, which would
            # double a positive delta when the Tech Doubler is active).
            add dword ptr [0x4D6F88], 30000
        cure_ret:
            pop edi
            pop esi
            pop edx
            pop ecx
            pop ebp
            pop ebx
            ret
        """,
        HEAL_CAVE_VA,
    )
    preflight_code = assemble(
        f"""
            cmp dword ptr [0x{VILLAGE_WIDE_SIGNATURE_VA:X}], 0x50465656
            jne preflight_invalid
            cmp dword ptr [0x{VILLAGE_WIDE_SIGNATURE_VA + 4:X}], 0x0055574F
            jne preflight_invalid
            cmp dword ptr [0x{VILLAGE_WIDE_SIGNATURE_VA + 8:X}], 0x00200001
            jne preflight_invalid
            cmp dword ptr [0x{VILLAGE_WIDE_SIGNATURE_VA + 0x10:X}], 3
            jne preflight_invalid
            cmp dword ptr [0x{VILLAGE_WIDE_SIGNATURE_VA + 0x14:X}], 0
            jne preflight_invalid
            cmp dword ptr [0x{VILLAGE_WIDE_SIGNATURE_VA + 0x18:X}], 0
            jne preflight_invalid
            cmp dword ptr [0x{VILLAGE_WIDE_SIGNATURE_VA + 0x1C:X}], 0
            jne preflight_invalid
            push 0x{s['icons_dll']:X}
            call dword ptr [0x48A1E0]
            test eax, eax
            je preflight_invalid
            push 100
            push eax
            call dword ptr [0x48A1DC]
            test eax, eax
            je preflight_invalid
            push ebx
            call eax
            ret
        preflight_invalid:
            xor eax, eax
            ret
        """,
        VILLAGE_PREFLIGHT_VA,
    )
    native_tech_tail = assemble(
        """
            push esi
            mov esi, dword ptr [esp + 8]
            jmp 0x41E305
        """,
        NATIVE_TECH_TAIL_VA,
    )
    native_food_tail = assemble(
        """
            push esi
            mov esi, dword ptr [esp + 8]
            jmp 0x41D925
        """,
        NATIVE_FOOD_TAIL_VA,
    )
    # Change Appearance picker-caller: edx holds the resolved villager record
    # pointer on entry.  Loads the companion DLL, calls the head+body picker
    # (which previews live and returns 1 on OK / 0 on Cancel/close), and only
    # then charges the 5,000 -- so Cancel/close costs nothing.  The caller does
    # the funds precheck before this runs.
    appearance_helper = assemble(
        f"""
            mov ebx, edx
            push 0x{s['icons_dll']:X}
            call dword ptr [0x48A1E0]
            test eax, eax
            je appearance_fail
            push 0x{s['show_appearance_picker']:X}
            push eax
            call dword ptr [0x48A1DC]
            test eax, eax
            je appearance_fail
            push ebx
            call eax
            test eax, eax
            je appearance_fail
            mov eax, -5000
            push eax
            mov ecx, 0x4D6F88
            call 0x41E300
            mov eax, 1
            ret
        appearance_fail:
            xor eax, eax
            ret
        """,
        APPEARANCE_HELPER_VA,
    )
    # Deferred-Barrel countdown, spliced into the per-tick event loop in front of
    # the natural presenter (0x4182B0). ECX (event manager) and the stack arg it
    # was called with are untouched, so the tail jmp reaches 0x4182B0 with the
    # exact frame it expects (0x4182B0 ends `ret 4`, returning to 0x440991). Each
    # tick it drains the purchase token; on the tick it reaches 0 it arms the
    # barrel for that single loop pass, so the loop presents exactly one barrel in
    # the real world context. Otherwise the barrel stays disarmed.
    # Spliced onto the game's real event-scheduler tick in place of `call 0x418000`
    # (at 0x43FBE5, ECX = event manager). Each pass it drains the purchase token;
    # when the token reaches zero it arms the barrel (if the village still has room)
    # so the barrel's eligibility hook reports eligible and the scheduler -- which
    # this helper tail-jumps into -- presents the native barrel event. The scheduler
    # picks randomly among eligible events, so the barrel stays armed across passes
    # until it is actually presented, detected by the per-event cooldown byte the
    # scheduler sets on the event it fired; then it disarms so exactly one barrel
    # fires. ECX must survive for the tail jmp to 0x418000.
    barrel_cue = assemble(
        f"""
            cmp byte ptr [0x{BARREL_ARMED_VA:X}], 0
            jz cue_scheduler
            # Armed: present the NATIVE barrel event (index 25) exactly the way the
            # scheduler presents a picked event -- 0x418190 checks its eligibility
            # (hooked at 0x414D50, true while armed), shows the event pop-up
            # ("Daredevil Barrel of Babies") via the present fn (0x417790) and
            # activates its lifecycle (0x401D40), which runs the native 3-child
            # spawn. ECX = the event manager the stock code just loaded (0x43FBE3);
            # the present/activate param is the object it pushed at 0x43FBDD, which
            # is still at [esp+4] here. 0x418190 cleans its own two args (ret 8);
            # we then disarm and `ret 4` -- the replaced `call 0x418000` is
            # __stdcall ret 4 (it cleans that pushed arg), so a plain `ret` would
            # leave it and corrupt the event fn frame (the /GS crash seen before).
            mov eax, dword ptr [esp + 4]
            push 25
            push eax
            call 0x418190
            mov byte ptr [0x{BARREL_ARMED_VA:X}], 0
            ret 4
        cue_scheduler:
            jmp 0x418000
        """,
        BARREL_COUNTDOWN_VA,
    )
    # Mode-aware Barrel capacity gate, called from the purchase preflight. Returns
    # eax=1 when the village can accommodate 3 more, eax=0 otherwise. The cap and
    # population are both taken the way the native barrel gate (0x468350) does, so
    # the answer tracks the build's actual population mode and in-game bonuses.
    # ESI preserved for the payload caller; 0x4143F0 / 0x467610 preserve ESI.
    barrel_capacity = assemble(
        f"""
            push esi
            mov ecx, 0x50E568
            call 0x467610
            add eax, {BARREL_CHILDREN}
            cmp eax, {BARREL_RECORD_LIMIT}
            jle cap_ok
            xor eax, eax
            pop esi
            ret
        cap_ok:
            mov eax, 1
            pop esi
            ret
        """,
        BARREL_CAPACITY_VA,
    )
    # Flag-gated replacements for the two internal 0x468350 room-checks inside the
    # stock barrel spawn (called before child 2 and before child 3), thiscall with
    # ECX = villager manager 0x50E568 like the stock check. When the purchased-barrel
    # flag is clear they tail-call the stock 0x468350 so natural barrels keep the
    # tiered growth cap. When set they report "room" (al=1) so the purchased barrel
    # ignores the tier cap -- but only while population (0x467610) is below the
    # 150-slot record array, so it can never overflow. barrel_check2 (before child 3,
    # always reached) also clears the flag so it applies to exactly one barrel.
    _gated_check_body = f"""
            call 0x467610
            cmp eax, {BARREL_RECORD_LIMIT}
            jge chk_full
            mov al, 1
            ret
        chk_full:
            xor al, al
            ret
        chk_normal:
            jmp 0x468350
    """
    barrel_check1 = assemble(
        f"""
            cmp byte ptr [0x{BARREL_UPGRADE_FLAG_VA:X}], 0
            jz chk_normal
            {_gated_check_body}
        """,
        BARREL_CHECK1_VA,
    )
    barrel_check2 = assemble(
        f"""
            cmp byte ptr [0x{BARREL_UPGRADE_FLAG_VA:X}], 0
            jz chk_normal
            mov byte ptr [0x{BARREL_UPGRADE_FLAG_VA:X}], 0
            {_gated_check_body}
        """,
        BARREL_CHECK2_VA,
    )
    # Load the companion DLL and call the collections export whose ordinal is in
    # EAX (101 = Complete, 102 = Reset). The export applies the change and shows
    # its own OFFICIAL result box, so the caller only charges and closes.
    collections_apply = assemble(
        f"""
            push ebx
            mov ebx, eax
            push 0x{s['icons_dll']:X}
            call dword ptr [0x48A1E0]
            test eax, eax
            jz coll_done
            push ebx
            push eax
            call dword ptr [0x48A1DC]
            test eax, eax
            jz coll_done
            call eax
        coll_done:
            pop ebx
            ret
        """,
        COLLECTIONS_APPLY_VA,
    )
    # The Cure and preflight helpers themselves are in the stock .shr section,
    # outside the main Origins payload scanner.  Record their exact internal
    # .shr references so expanded mode can retarget them after the section move.
    for target_va in (
        VILLAGE_WIDE_SIGNATURE_VA,
        VILLAGE_WIDE_SIGNATURE_VA + 4,
        VILLAGE_WIDE_SIGNATURE_VA + 8,
        VILLAGE_WIDE_SIGNATURE_VA + 0x10,
    ):
        purpose = "relocate VV4 Origins preflight header pointer for expanded 256 mode"
        needle = target_va.to_bytes(4, "little")
        cursor = 0
        while True:
            found = preflight_code.find(needle, cursor)
            if found < 0:
                break
            expanded_shr_relocations.append(
                {
                    "offset": f"0x{VILLAGE_PREFLIGHT_FILE_OFFSET + found:X}",
                    "before": needle.hex().upper(),
                    "kind": "absolute",
                    "source_virtual_address": f"0x{VILLAGE_PREFLIGHT_VA + found:X}",
                    "target_stock_virtual_address": f"0x{target_va:X}",
                    "target_expanded_virtual_address": f"0x{target_va + (EXPANDED_HEAL_CAVE_VA - HEAL_CAVE_VA):X}",
                    "purpose": purpose,
                }
            )
            cursor = found + 1
    for index in range(len(cure_code) - 4):
        if cure_code[index] != 0xE8:
            continue
        rel = int.from_bytes(cure_code[index + 1 : index + 5], "little", signed=True)
        source_va = CURE_ENTRY_VA + index
        target_va = source_va + 5 + rel
        if target_va != VILLAGE_WIDE_ENTRY_VA:
            continue
        expanded_shr_relocations.append(
            {
                "offset": f"0x{CURE_ENTRY_FILE_OFFSET + index + 1:X}",
                "before": cure_code[index + 1 : index + 5].hex().upper(),
                "kind": "rel32",
                "source_virtual_address": f"0x{source_va:X}",
                "target_stock_virtual_address": f"0x{target_va:X}",
                "purpose": "relocate VV4 Origins village-wide helper call for expanded 256 mode",
            }
        )
    for offset, before, source_va, target_stock_va, target_expanded_va in VV4_ALL_FEATURE_ABSOLUTE_RELOCATIONS:
        expanded_shr_relocations.append(
            {
                "offset": f"0x{offset:X}",
                "before": before,
                "kind": "absolute",
                "source_virtual_address": f"0x{source_va:X}",
                "target_stock_virtual_address": f"0x{target_stock_va:X}",
                "target_expanded_virtual_address": f"0x{target_expanded_va:X}",
                "purpose": "relocate VV4 current Origins all-feature .shr absolute operand for expanded 256 mode",
            }
        )
    patch(
        HEAL_CAVE_FILE_OFFSET,
        b"\0" * len(cure_code),
        cure_code,
        "restore every living villager below 100 health to 100 through the native setter, clear sickness, and update People Cured",
    )
    patch(
        NATIVE_TECH_TAIL_FILE_OFFSET,
        b"\0" * len(native_tech_tail),
        native_tech_tail,
        "keep Island Event tech rewards on the native tech path",
    )
    patch(
        NATIVE_FOOD_TAIL_FILE_OFFSET,
        b"\0" * len(native_food_tail),
        native_food_tail,
        "keep Island Event food rewards on the native food path",
    )
    for offset in (0x4156F8, 0x415862, 0x41586F, 0x415A81, 0x415B46, 0x415D8C, 0x416722, 0x416735):
        patch(
            offset - IMAGE_BASE,
            original[offset - IMAGE_BASE : offset - IMAGE_BASE + 5],
            rel32_jump(offset, NATIVE_TECH_TAIL_VA),
            "bypass the Tech Doubler for an Island Event tail-jump",
        )
    patch(
        0x41520E - IMAGE_BASE,
        original[0x41520E - IMAGE_BASE : 0x41520E - IMAGE_BASE + 5],
        rel32_jump(0x41520E, NATIVE_FOOD_TAIL_VA),
        "bypass the Food Doubler for an Island Event tail-jump",
    )
    patch(
        VILLAGE_PREFLIGHT_FILE_OFFSET,
        b"\0" * len(preflight_code),
        preflight_code,
        "validate the complete optional Origins header and result-export dependency before any village-wide charge",
    )
    patch(
        APPEARANCE_HELPER_FILE_OFFSET,
        b"\0" * len(appearance_helper),
        appearance_helper,
        "Change Appearance: call the companion head+body picker for the selected villager and charge 5,000 only on OK",
    )

    patch(0x244, bytes.fromhex("40000040"), bytes.fromhex("40000060"),
          "make the mapped .text cave executable for the Origins payload")
    # D166 fix: every VV4 Origins helper placed in this file (Cure at
    # 0xCC004, Island Event tech/food exclusions at 0xCC160/0xCC170, the
    # village-wide preflight validator at 0xCC180, and the entire
    # village-wide extension cave) is written into the .shr section. The
    # PE section header for .shr was never patched to make it executable
    # or to extend its declared VirtualSize past 4 bytes -- unlike every
    # other one of the five games, which each extend and mark their own
    # equivalent section executable. An independent PE re-parse of the
    # rendered output confirmed: exec=False, VirtualSize=4 bytes, no patch
    # anywhere in the repository touches the .shr section-header entry's
    # VirtualSize (file offset 0x278) or Characteristics (file offset
    # 0x294) fields. Every call/jmp into this cave would fail under
    # standard Windows DEP enforcement for a section not marked
    # executable. Fixed identically to VV1/VV2/VV3's own .shr patches.
    patch(0x278, bytes.fromhex("04000000"), bytes.fromhex("00100000"),
          "map the complete VV4 .shr helper page used by Origins runtime code")
    patch(0x294, bytes.fromhex("400000D0"), bytes.fromhex("600000F0"),
          "mark the mapped VV4 .shr helper page executable while retaining its stock data permissions")
    patch(0x14D50, bytes.fromhex("B968E55000"), rel32_jump(0x414D50, barrel_eligibility),
          "admit the Barrel of Babies event while the purchased-barrel token is armed")
    patch(BARREL_COUNTDOWN_FILE_OFFSET, b"\0" * len(barrel_cue), barrel_cue,
          "Barrel cue (spliced on the event scheduler): when armed, present the native barrel event (index 25) directly so its pop-up shows and its lifecycle runs the spawn")
    patch(BARREL_CAPACITY_FILE_OFFSET, b"\0" * len(barrel_capacity), barrel_capacity,
          "Barrel purchase gate: refuse (no charge) only when population (0x467610) + 3 would exceed the 150-slot record array")
    patch(BARREL_CHECK1_FILE_OFFSET, b"\0" * len(barrel_check1), barrel_check1,
          "purchased-barrel room-check 1 (before child 2): report room up to the record array when the purchase flag is set, else the stock tiered check")
    patch(BARREL_CHECK2_FILE_OFFSET, b"\0" * len(barrel_check2), barrel_check2,
          "purchased-barrel room-check 2 (before child 3): as check 1, and clears the purchase flag so it applies to exactly one barrel")
    patch(0x14DCA, bytes.fromhex("E881350500"), rel32_call(0x414DCA, BARREL_CHECK1_VA),
          "route the stock barrel spawn's first internal room-check through the purchased-barrel gate")
    patch(0x14E0D, bytes.fromhex("E83E350500"), rel32_call(0x414E0D, BARREL_CHECK2_VA),
          "route the stock barrel spawn's second internal room-check through the purchased-barrel gate")
    patch(COLLECTIONS_APPLY_FILE_OFFSET, b"\0" * len(collections_apply), collections_apply,
          "Complete/Reset Collections: load the companion DLL and call the collections export by ordinal (EAX=101 complete / 102 reset)")
    patch(VV4_DETAIL_RECORD_FILE_OFFSET, b"\0" * 4, b"\0" * 4,
          "scratch slot for the open detail-menu villager record pointer (DLL running-dislike no-change case)")
    # Heathen-mask cosmetic overlay (SDL blit via companion DLL). Three tiny
    # caves in the free RWX .shr tail; NO villager-record writes, NO atlas/row
    # changes, so no existing upgrade/menu/patch is touched. The DLL owns the
    # mask side-table, the clear-on-death sweep, and the SDL blit.
    mask_resolve = mask_resolve_cave(s["icons_dll"])
    patch(MASK_RESOLVE_FILE_OFFSET, b"\0" * len(mask_resolve), mask_resolve,
          "Heathen mask: resolve cave -- LoadLibraryA the companion DLL and GetProcAddress Vv4MaskCacheSurface(@110)/Vv4MaskDrawRecord(@112) by ordinal, once (guarded)")
    mask_present = mask_present_cave()
    patch(MASK_PRESENT_FILE_OFFSET, b"\0" * len(mask_present), mask_present,
          "Heathen mask: present cave -- cache the live render-target surface [screen_obj+0x30] into the DLL (also runs the clear-on-death sweep), then tail-call the real present")
    mask_head = mask_head_cave()
    patch(MASK_HEAD_FILE_OFFSET, b"\0" * len(mask_head), mask_head,
          "Heathen mask: head cave -- draw the head normally then Vv4MaskDrawRecord(esi,x,y,frame,100) (fingerprint-checked; mask=0 draws nothing); no villager fields written")
    patch(MASK_PRESENT_SITE - IMAGE_BASE,
          rel32_call(MASK_PRESENT_SITE, MASK_PRESENT_CALLEE),
          rel32_call(MASK_PRESENT_SITE, MASK_PRESENT_VA),
          f"Heathen mask: route the present call at {MASK_PRESENT_SITE:#x} through the surface-cache cave")
    for site in MASK_HEAD_CALL_SITES:
        patch(site - IMAGE_BASE,
              rel32_call(site, MASK_DRAW_THUNK_VA), rel32_call(site, MASK_HEAD_VA),
              f"Heathen mask: route the head-draw call at {site:#x} through the mask head cave")
    # Walking-WORLD mask: wrap the deferred compositor's post-head camera blit so
    # the mask renders on the actual village villagers (the twins above are an
    # early pass the world repaints over).
    mask_world = mask_world_cave()
    patch(MASK_WORLD_FILE_OFFSET, b"\0" * len(mask_world), mask_world,
          "Heathen mask: WORLD cave -- wrap FUN_00467da0's post-head camera world-blit (0x44C790) and re-issue it with arg1=mask atlas + arg4=mask row + y-lift so the walking-village mask lands in the deferred composite")
    # Initialise the per-mask vertical-nudge table (chief +7 up). Lives just past
    # the cave + scratch in the .shr tail; assert the cave never reaches it.
    _shr_delta = MASK_WORLD_VA - MASK_WORLD_FILE_OFFSET
    _dy_file = MASK_DY_TABLE - _shr_delta
    assert MASK_WORLD_FILE_OFFSET + len(mask_world) <= _dy_file, \
        "world cave grew into the per-mask DY table -- relocate the table/scratch"
    patch(_dy_file, b"\0" * len(MASK_DY_VALUES),
          bytes(v & 0xFF for v in MASK_DY_VALUES),
          "Heathen mask: per-mask vertical nudge table (blue/orange/red/purple/chief; chief +7 up)")
    patch(MASK_WORLD_SITE - IMAGE_BASE,
          rel32_call(MASK_WORLD_SITE, MASK_WORLD_CALLEE),
          rel32_call(MASK_WORLD_SITE, MASK_WORLD_VA),
          f"Heathen mask: route the world compositor's post-head blit at {MASK_WORLD_SITE:#x} through the world mask cave")
    # Detail-portrait (big) head draw: hook the head draw `call 0x409A70` at
    # 0x43CFDE, run it, then reissue with the mask atlas so the mask rides the
    # bighead at its own portrait scale (STAGE 1: front col 6; facing refine TODO).
    mask_detail = mask_detail_cave()
    patch(VV4_DETAIL_MASK_FILE_OFFSET, b"\0" * len(mask_detail), mask_detail,
          "Heathen mask: DETAILS cave -- wrap the portrait head draw (0x409A70 @0x43CFDE) and reissue it with the mask atlas obj so the mask overlays the bighead at the head's own position/scale")
    _d_scale_file = D_SCALE - (VV4_DETAIL_MASK_VA - VV4_DETAIL_MASK_FILE_OFFSET)
    assert VV4_DETAIL_MASK_FILE_OFFSET + len(mask_detail) <= _d_scale_file, \
        "Details cave grew into the D_SCALE constant"
    patch(_d_scale_file, b"\0" * 4, D_SCALE_VALUE,
          "Heathen mask: Details bighead scale multiplier (2.6x = bighead face / village mask face)")
    _shr_delta_d = VV4_DETAIL_MASK_VA - VV4_DETAIL_MASK_FILE_OFFSET
    patch(D_LIFTX - _shr_delta_d, b"\0" * 4, D_LIFTX_VALUE,
          "Heathen mask: Details bighead X seat (mask_x = head_x - LIFTX*headScale)")
    patch(D_LIFTY - _shr_delta_d, b"\0" * 4, D_LIFTY_VALUE,
          "Heathen mask: Details bighead Y seat (mask_y = head_y - LIFTY*headScale)")
    patch(VV4_DETAIL_MASK_SITE - IMAGE_BASE,
          rel32_call(VV4_DETAIL_MASK_SITE, VV4_DETAIL_MASK_CALLEE),
          rel32_call(VV4_DETAIL_MASK_SITE, VV4_DETAIL_MASK_VA),
          f"Heathen mask: route the Details portrait head draw at {VV4_DETAIL_MASK_SITE:#x} through the Details mask cave")
    # DIAGNOSTIC caller-capture (temporary): splice the 8 sibling blit thunks so the
    # bighead's per-frame portrait draw caller (through whichever thunk) is captured.
    # Caves + ring live in the LOW .shr (0x728100..0x728800), verified free of other
    # patches (the 0x728A00+ region is used by the mask/scratch/record patches).
    if CALLER_CAPTURE_ENABLED:
        _shr_va2file = MASK_WORLD_VA - MASK_WORLD_FILE_OFFSET
        for (thunk, target), cave_va in zip(CALLER_THUNKS, CALLER_CAVES):
            cc = caller_capture_cave(cave_va, target)
            patch(cave_va - _shr_va2file, b"\0" * len(cc), cc,
                  f"DIAGNOSTIC: caller-capture cave for blit thunk {thunk:#x}")
            before5 = b"\x8b\x09\xe9" + _struct.pack("<i", target - (thunk + 7))[:2]
            patch(thunk - IMAGE_BASE, before5, rel32_jump(thunk, cave_va),
                  f"DIAGNOSTIC: splice blit thunk {thunk:#x} to its caller-capture cave")
    patch(0x3FBE5, bytes.fromhex("E81684FDFF"), rel32_call(0x43FBE5, BARREL_COUNTDOWN_VA),
          "route the real event-scheduler tick (0x43FBE5 -> 0x418000) through the Barrel cue so a purchased barrel is presented naturally after its delay")
    patch(0x1D94F, bytes.fromhex("85F67E3456"), rel32_jump(0x41D94F, food_increment),
          "double eligible positive food-source deltas")
    patch(0x1E300, bytes.fromhex("568B742408"), rel32_jump(0x41E300, tech_increment),
          "double eligible positive earned tech deltas")
    patch(0x3E165, bytes.fromhex("8BC68B4C244C"),
          rel32_jump(0x43E165, tech_constructor) + b"\x90",
          "append the stock-styled Upgrades control to the Tech screen")
    patch(0x3E9F0, bytes.fromhex("578BF9E828F00000"),
          rel32_jump(0x43E9F0, tech_handler) + b"\x90\x90\x90",
          "route Tech-screen control 13 through the Origins menu")
    patch(0x47A25, bytes.fromhex("891D5C904D00891D58904D00"),
          rel32_jump(0x447A25, detail_constructor) + b"\x90" * 7,
          "append the stock-styled Upgrades control to Villager Detail")
    patch(0x3E238, bytes.fromhex("E803E1FCFF"),
          rel32_jump(0x43E238, PAYLOAD_VA + 0xC0),
          "run the certified native Tech-control destructor helper")
    patch(0x48610, bytes.fromhex("83EC18A1BC9F4C00"),
          rel32_jump(0x448610, PAYLOAD_VA + VV4_DETAIL_HANDLER_RELOC_OFFSET) + b"\x90\x90\x90",
          "route Detail-screen control 2 through the certified native-handler trampoline")
    patch(PAYLOAD_FILE_OFFSET, b"\0" * len(payload), bytes(payload),
          "install the VV4 Origins Tech and Villager upgrade menus and mechanics")

    rendered = bytearray(original)
    for item in patches:
        offset = int(str(item["offset"]), 16)
        replacement = bytes.fromhex(str(item["after"]))
        rendered[offset : offset + len(replacement)] = replacement
    OUT_EXE.write_bytes(rendered)
    OUT_JSON.write_text(json.dumps(patches, indent=2) + "\n", encoding="utf-8")

    manifest = {
        "id": "vv4_enable_origins_exclusive_features",
        "game_id": "vv4",
        "running_preference_id": RUNNING_PREFERENCE_ID,
        "running_preference_evidence": {"source": "exact stock executable embedded preference table", "table_file_offset": "0xA0CD8", "entry_name": "running"},
        "name": "Enable Origins-Exclusive Features (with Heathen Mask mod)",
        "description": "Adds Origins-style Upgrades buttons to the Tech and Villager Details screens. The Tech menu offers Time Warp, Island Event, Barrel of Babies, Food and Tech Point Doublers for 500,000 tech points each (eligible positive gains are doubled after native Food Mastery, while Island Events and Duplicate Collectibles remain unchanged), Full Heal/Cure All, Complete and Reset All Collections, and Equal Division of Labor with and without Parenting. The Village-Wide menu adds Running, Full Mastery, and Make Villagers Young Adults. The Villager Details menu grants Youth, Full Mastery, Running, Set Age to 18, and Change Appearance. This patch also includes the Heathen Mask mod: a cosmetic head-mask overlay (Blue/Orange/Red/Purple/Chief) selectable per villager in Change Appearance and en masse via the Change Appearance for All tech upgrade, rendered over the villager's head in both the village and the Details screen.",
        "output_tag": "Origins Exclusive Features",
        "ui_contract": ui_metadata,
        "native_handlers": {
            "tech_unrelated_events": "fall through to 0x43E9F8",
            "details_unrelated_events": "fall through to 0x448618",
            "skill_writer": "0x46AD80; Float32 delta + skill ordinal; ECX=record+0x1C5C; ret 8",
            "health_setter": "0x46AF00; ECX=record+0x1C34; push -1, push 100; ret 8",
            "barrel_event": "0x418190",
            "sickness_statistics": "direct sickness clear with People Cured increment; native sickness ABI remains unproven",
        },
        "companion_files": [
            {
                "source": "assets/origins/VVFP VV4 Origins Icons.dll",
                "destination": "VVFP VV4 Origins Icons.dll",
                "sha256": hashlib.sha256(
                    (ROOT / "assets/origins/VVFP VV4 Origins Icons.dll").read_bytes()
                ).hexdigest().upper(),
            },
            # Heathen-mask RENDER atlas: the exact hand-aligned mask art, 8
            # directional columns x 5 mask rows of 40x65 cells. The DLL builds a
            # game ldwImageGrid sprite from it via the MULTI-FILE ctor
            # FUN_0040ABA0(name,ext,1,1,8,5), which sprintf's "%s%d%d%s" ->
            # "<name>00.png", so it ships as vvfp_mask_atlas00.png. The multi-file
            # ctor is required: it populates the surface array at obj[0xc] where
            # the draw path (FUN_0040a990) looks; the single-file loader leaves it
            # 0 and nothing blits. Added file (no atlas swaps/row bumps) -- removed
            # on unpatch, stock atlases untouched.
            {
                "source": "assets/vv4_masks/vvfp_mask_atlas.png",
                "destination": "Images/vvfp_mask_atlas00.png",
                "sha256": hashlib.sha256(
                    (ROOT / "assets/vv4_masks/vvfp_mask_atlas.png").read_bytes()
                ).hexdigest().upper(),
            },
            # Centered 40x65 mask preview atlas for the Change Appearance chooser
            # (autocropped, ~90% fill; VV2-parity source size). Added file, so no
            # preimage/restore -- it is removed on unpatch.
            {
                "source": "assets/vv4_masks/vvfp_mask_preview.png",
                "destination": "Images/vvfp_mask_preview.png",
                "sha256": hashlib.sha256(
                    (ROOT / "assets/vv4_masks/vvfp_mask_preview.png").read_bytes()
                ).hexdigest().upper(),
            },
            # DEDICATED bighead-resolution mask atlas for the Details PORTRAIT: 3
            # facing-cols x 5 colour-rows, ~40x90 cells (same source art VV5 uses).
            # The DLL builds it via FUN_0040ABA0(name,ext,1,1,3,5) -> ships as
            # vvfp_bighead_mask_atlas00.png. Portrait draws its FRONT col (1) at the
            # head's own scale x1.5 -- crisp, correctly sized (vs the old blurry
            # village-atlas-x2.6 hack). Added file; stock art untouched.
            {
                "source": "assets/vv4_masks/vvfp_bighead_mask_atlas.png",
                "destination": "Images/vvfp_bighead_mask_atlas00.png",
                "sha256": hashlib.sha256(
                    (ROOT / "assets/vv4_masks/vvfp_bighead_mask_atlas.png").read_bytes()
                ).hexdigest().upper(),
            },
        ],
        "doubler_evidence": {
            "build": {
                "filename": "Virtual Villagers - The Tree of Life.exe",
                "size": 929792,
                "sha256": "6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220",
            },
            "positive_tech_writer": "0x41E300",
            "positive_food_writer": "0x41D920",
            "collection_adjustment": "Food Mastery is applied inside sub_41D920: level 0/1=A, level 2=A+floor(A/2), level 3=2A. Collection call 0x414660 passes pre-mastery 6/35, so any eligible doubler must follow the native transform.",
            "external_xref_inventory": {"tech": 21, "food": 23},
            "tail_jump_sites": ["0x4156F8", "0x415862", "0x41586F", "0x415A81", "0x415B46", "0x415D8C", "0x416722", "0x416735", "0x41520E"],
            "ordinary_positive_sites": {
                "tech": ["0x414477", "0x414493", "0x4144AF", "0x431A9B"],
                "food": ["0x414660", "0x436F15"],
            },
            "duplicate_collectibles": {
                "function": "sub_414410",
                "tech_returns": ["0x41447C", "0x414498", "0x4144B4"],
                "behavior": "an already-completed collectible routes to the tech writer",
            },
            "island_event_positive_sites": {
                "tech": ["0x414A28", "0x4156F8", "0x415862", "0x415A81", "0x415B46", "0x415D8C", "0x416722", "0x464E58", "0x464E82", "0x464EAB"],
                "food": ["0x414949", "0x41520E", "0x4643E6", "0x464433", "0x464492", "0x46450B", "0x464573", "0x4645B0", "0x4645FB"],
            },
            "tail_bypass_sites": {
                "tech": ["0x4156F8", "0x415862", "0x41586F", "0x415A81", "0x415B46", "0x415D8C", "0x416722", "0x416735"],
                "food": ["0x41520E"],
            },
            "hook_status": "GO: positive writer wrappers run after native Food Mastery; duplicate collectibles, direct Island Event calls, and audited Island Event tail-jumps remain native; runtime/player confirmation pending",
        },
        "doubler_composition_contract": {
            "stacking": [
                "positive earned tech deltas only",
                "positive food-source deltas only",
            ],
            "exclusions": ["Island Event tech-point gain", "Duplicate Collectibles tech-point gain"],
            "food_mastery_status": "confirmed in exact-build disassembly; native transform documented in doubler evidence",
            "status": "GO: positive writer wrappers double eligible positive deltas once after native adjustments; duplicate collectibles and audited Island Event paths remain native; runtime/player confirmation pending",
        },
        "doubler_purchase_status": {
            "new_purchase": "available at 500,000 tech points for each doubler",
            "existing_owned": "removable at zero cost with zero refund",
            "repurchase": "available again at 500,000 tech points after removal",
        },
        "patches": patches,
        "expanded_shr_relocations": {
            "stock_virtual_address": f"0x{SHR_STOCK_VA:X}",
            "expanded_virtual_address": f"0x{SHR_EXPANDED_VA:X}",
            "patches": expanded_shr_relocations,
        },
    }
    MANIFEST_JSON.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    used = max(index for index, value in enumerate(code) if value) + 1
    print(f"code bytes used: {used:#x}/{STRINGS_OFFSET:#x}")
    print(f"string bytes used: {len(strings):#x}/{PAYLOAD_SIZE - STRINGS_OFFSET:#x}")
    print(OUT_JSON)
    print(MANIFEST_JSON)
    print(OUT_EXE)


if __name__ == "__main__":
    main()
