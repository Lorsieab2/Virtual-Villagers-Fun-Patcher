"""Assemble the exact-build VV1 Origins-exclusive feature patch.

This is a developer helper. It emits guarded manifest edits and a patched
research executable; the user-facing patcher consumes the emitted edits.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - A New Home.exe"
OUT_DIR = ROOT / "research" / "vv1-origins-apk"
OUT_EXE = OUT_DIR / "Virtual Villagers - A New Home - Origins Feature Research.exe"
OUT_JSON = OUT_DIR / "vv1-origins-feature-patches.json"
MANIFEST_JSON = ROOT / "data" / "vv1_origins_feature.json"

sys.path.insert(0, str(ROOT / ".tools" / "keystone"))
sys.path.insert(0, str(ROOT / ".tools" / "keystone-runtime"))
from keystone import KS_ARCH_X86, KS_MODE_32, Ks  # noqa: E402


IMAGE_BASE = 0x400000
CODE_FILE_OFFSET = 0x56900
CODE_VA = IMAGE_BASE + CODE_FILE_OFFSET
STRINGS_FILE_OFFSET = 0x85D30
STRINGS_VA = IMAGE_BASE + STRINGS_FILE_OFFSET
SHR_FILE_OFFSET = 0x8B000
SHR_RVA = 0x8D000
HEAL_CAVE_FILE_OFFSET = 0x8B004
HEAL_CAVE_STUB_VA = IMAGE_BASE + SHR_RVA + (
    HEAL_CAVE_FILE_OFFSET - SHR_FILE_OFFSET
)
CURE_ENTRY_FILE_OFFSET = 0x8B530
CURE_ENTRY_VA = IMAGE_BASE + SHR_RVA + (CURE_ENTRY_FILE_OFFSET - SHR_FILE_OFFSET)
HEAL_CAVE_VA = CURE_ENTRY_VA
VILLAGE_WIDE_SIGNATURE_VA = IMAGE_BASE + SHR_RVA + 0x180
VILLAGE_WIDE_ENTRY_VA = IMAGE_BASE + SHR_RVA + 0x1A0
# Fixed scratch dwords in the confirmed-unused gap between the optional
# village-wide payload's entry dispatch and its running_va (see
# scripts/build_village_wide_origins_features.py's report_running_granted/
# report_mastery_counts/report_age_granted, which write these -- this is
# the VV1-only opt-in side of that shared, cross-game generator). There is
# no free register left at running_va's, mastery_va's, or age_va's return
# point to carry these counts back through directly, so they are read from
# fixed memory here instead, after the call returns. Also doubles as the
# "did anything actually change" signal each of the three village-wide
# rows now needs: the 1,000,000-point charge is only taken once the
# relevant granted count is confirmed nonzero, matching every other row's
# own no-charge-if-no-change guard.
RUNNING_GRANTED_VA = VILLAGE_WIDE_ENTRY_VA + 0x30
MASTERY_GRANTED_VA = VILLAGE_WIDE_ENTRY_VA + 0x38
MASTERY_ALREADY_VA = VILLAGE_WIDE_ENTRY_VA + 0x3C
AGE_GRANTED_VA = VILLAGE_WIDE_ENTRY_VA + 0x40
AGE_ALREADY_VA = VILLAGE_WIDE_ENTRY_VA + 0x44
# Must exactly match build_village_wide_origins_features.py's own
# age_golden_child_va = entry_va + 0x48 (entry_va there and
# VILLAGE_WIDE_ENTRY_VA here are the same address for VV1).
AGE_GOLDEN_CHILD_VA = VILLAGE_WIDE_ENTRY_VA + 0x48
# This exact VV1 build's own module-static singleton pointer to the current
# Golden Child's villager record -- dword ptr [GOLDEN_CHILD_SINGLETON_VA]
# holds that record's address (0 if none exists yet). Confirmed via a live
# memory scan (found the address, then found this stable pointer to it) and
# via static disassembly of its lazy-getter/destructor pair at 0x43da37 /
# 0x43da9d-0x43dac6. This is the stock game's own global, not anything we
# allocate -- unlike RUNNING_GRANTED_VA and friends above, it is never
# written by our own code, only read and compared against.
GOLDEN_CHILD_SINGLETON_VA = 0x48B614
VILLAGE_PREFLIGHT_FILE_OFFSET = 0x8B009
VILLAGE_PREFLIGHT_VA = IMAGE_BASE + SHR_RVA + (
    VILLAGE_PREFLIGHT_FILE_OFFSET - SHR_FILE_OFFSET
)
BARREL_PENDING_FILE_OFFSET = 0x8B700
BARREL_PENDING_VA = IMAGE_BASE + SHR_RVA + (
    BARREL_PENDING_FILE_OFFSET - SHR_FILE_OFFSET
)
# Reported: the native Barrel of Babies event used to fire within a
# fraction of a second of the Tech screen closing (barrel_main_helper_code
# is hooked into the stock main-village update, confirmed via decompiling
# it to be a genuine per-frame tick -- it rolls per-frame chances for
# ambient butterfly/particle spawns, not something that only runs once a
# game-day like Island Event's own native scheduling field does), leaving
# no time to read the purchase confirmation before the full-screen event
# took over. Unlike Island Event, Barrel of Babies is not a native random
# encounter with its own slow scheduler to hook into instead -- decompiling
# its constructor/run/teardown trio confirms it is a hand-built event
# screen, not a scheduled one -- so the fix is a real elapsed-tick delay of
# its own: this dword counts ticks while BARREL_PENDING_VA is in its
# "Tech screen has closed" state, and the event is only actually shown
# once it crosses BARREL_DELAY_TICKS.
BARREL_DELAY_COUNTER_FILE_OFFSET = 0x8B704
BARREL_DELAY_COUNTER_VA = IMAGE_BASE + SHR_RVA + (
    BARREL_DELAY_COUNTER_FILE_OFFSET - SHR_FILE_OFFSET
)
BARREL_DELAY_TICKS = 180
BARREL_MAIN_HELPER_FILE_OFFSET = 0x8B710
BARREL_MAIN_HELPER_VA = IMAGE_BASE + SHR_RVA + (
    BARREL_MAIN_HELPER_FILE_OFFSET - SHR_FILE_OFFSET
)
# Equal Division of Labor (Tech screen rows 9/10): BARREL_MAIN_HELPER_VA's
# own code ends well under 0x8B77E, leaving a genuinely free 386-byte gap
# up to BARREL_CLOSE_HELPER_FILE_OFFSET (0x8B900) -- placed here rather
# than in the confirmed-unused 0x8B07E-0x8B530 gap, which belongs to the
# separate, optional village-wide extension payload
# (scripts/build_village_wide_origins_features.py's own payload_offset)
# and must stay free for it. equal_division_core does the actual work
# (226 bytes, measured via keystone); its own fixed table/scratch data
# sits safely after it with room to spare before BARREL_CLOSE_HELPER_VA.
EQUAL_DIVISION_CORE_FILE_OFFSET = 0x8B790
EQUAL_DIVISION_CORE_VA = IMAGE_BASE + SHR_RVA + (
    EQUAL_DIVISION_CORE_FILE_OFFSET - SHR_FILE_OFFSET
)
# The single job-preference code (1-5) each of the 5 real skills uses at
# villager-record offset +0x3D0 -- decompiled in full via the stock
# game's own lazy dispatch jump table at 0x41fb60 (five branches, one per
# code, each reading the matching skill DWORD at +0x3BC/+0x3C0/+0x3C4/
# +0x3C8/+0x3CC) and cross-checked live: a running game's own Villager
# Detail screen showed "Building" checked for a specific villager, and
# reading that exact villager's record over ReadProcessMemory (read-only)
# confirmed +0x3D0 held 4 at the same moment -- matching this table's own
# code for Building. In on-screen order (Farming, Building, Research,
# Healing, Breeding), the codes are 1, 4, 3, 5, 2; the "No Parenting" row
# just treats this as a 4-entry table, cycling Farming/Building/Research/
# Healing without ever reaching the trailing Breeding entry.
EQUAL_DIVISION_TABLE_FILE_OFFSET = 0x8B8A0
EQUAL_DIVISION_TABLE_VA = IMAGE_BASE + SHR_RVA + (
    EQUAL_DIVISION_TABLE_FILE_OFFSET - SHR_FILE_OFFSET
)
EQUAL_DIVISION_TABLE_BYTES = bytes([1, 4, 3, 5, 2])
EQUAL_DIVISION_N_FILE_OFFSET = 0x8B8A8
EQUAL_DIVISION_N_VA = IMAGE_BASE + SHR_RVA + (
    EQUAL_DIVISION_N_FILE_OFFSET - SHR_FILE_OFFSET
)
EQUAL_DIVISION_GRANTED_FILE_OFFSET = 0x8B8AC
EQUAL_DIVISION_GRANTED_VA = IMAGE_BASE + SHR_RVA + (
    EQUAL_DIVISION_GRANTED_FILE_OFFSET - SHR_FILE_OFFSET
)
EQUAL_DIVISION_GOLDEN_SKIPPED_FILE_OFFSET = 0x8B8B0
EQUAL_DIVISION_GOLDEN_SKIPPED_VA = IMAGE_BASE + SHR_RVA + (
    EQUAL_DIVISION_GOLDEN_SKIPPED_FILE_OFFSET - SHR_FILE_OFFSET
)
# Per-job, per-gender counters: 5 dwords each, indexed by table position
# (0=Farming, 1=Building, 2=Research, 3=Healing, 4=Breeding -- the same
# index EQUAL_DIVISION_TABLE_BYTES/esi already use, so no separate
# code-to-position lookup is needed). ShowOriginsEqualDivisionResult
# reads both arrays directly to report exactly how many of each gender
# were set to each job.
EQUAL_DIVISION_MALE_COUNTS_FILE_OFFSET = 0x8B8B4
EQUAL_DIVISION_MALE_COUNTS_VA = IMAGE_BASE + SHR_RVA + (
    EQUAL_DIVISION_MALE_COUNTS_FILE_OFFSET - SHR_FILE_OFFSET
)
EQUAL_DIVISION_FEMALE_COUNTS_FILE_OFFSET = 0x8B8C8
EQUAL_DIVISION_FEMALE_COUNTS_VA = IMAGE_BASE + SHR_RVA + (
    EQUAL_DIVISION_FEMALE_COUNTS_FILE_OFFSET - SHR_FILE_OFFSET
)
# D166 fix: VV1 previously fired the native Barrel of Babies event the
# instant the token was set, with no check that the Tech-screen Upgrades
# dialog (whose own "Buy" click just set that token) had actually closed.
# That let the native event's own modal loop start while the Upgrades
# dialog's modal loop was still live on the stack -- exact-build VV2 avoids
# this with a two-stage token advanced only from the Tech screen's own
# close branch (0x437DA there); VV1 had no equivalent second stage. This
# adds one, hooked into the exact-build close branch it corresponds to.
BARREL_CLOSE_HELPER_FILE_OFFSET = 0x8B900
BARREL_CLOSE_HELPER_VA = IMAGE_BASE + SHR_RVA + (
    BARREL_CLOSE_HELPER_FILE_OFFSET - SHR_FILE_OFFSET
)
# Villager Details "Change Appearance" -- a dedicated router/helper pair in
# .shr, entirely separate from detail_menu's own shared, tightly-budgeted
# code cave (which the other four rows' charge/apply logic already nearly
# fills). detail_menu's own inline footprint for this row is just the one
# "cmp ebx, 4 / je APPEARANCE_ROUTER_VA" dispatch -- everything else,
# including the row's own success messaging and loop-back, lives here:
#   APPEARANCE_ROUTER_VA: what detail_menu jumps to directly. Calls the
#     helper below, then either shows the same "Purchased." message every
#     other successful row shows and jumps back into detail_menu's loop,
#     or (on cancel/failure) jumps back silently -- without ever returning
#     control to detail_menu's own code, so its cave carries none of this
#     row's logic. Depends on exactly one fact about detail_menu's
#     internal layout: detail_loop is always its first label, 5 bytes in
#     (three pushes + "mov esi, ecx"), regardless of what else in the
#     function grows or shrinks -- computed below, not hardcoded blind.
#   APPEARANCE_HELPER_VA: resolves and calls the icons DLL's picker
#     export; unchanged from before, just renumbered now that the router
#     sits ahead of it.
# Placed here (well past the Barrel close helper, which ends well under
# 0x8B980) since .shr has ~1.7KB genuinely unused past the last Barrel
# helper.
APPEARANCE_ROUTER_FILE_OFFSET = 0x8BA00
APPEARANCE_ROUTER_VA = IMAGE_BASE + SHR_RVA + (
    APPEARANCE_ROUTER_FILE_OFFSET - SHR_FILE_OFFSET
)
APPEARANCE_HELPER_FILE_OFFSET = 0x8BA80
APPEARANCE_HELPER_VA = IMAGE_BASE + SHR_RVA + (
    APPEARANCE_HELPER_FILE_OFFSET - SHR_FILE_OFFSET
)
DETAIL_MENU_VA = CODE_VA + 0x521
DETAIL_LOOP_VA = DETAIL_MENU_VA + 5  # push ebx; push esi; push edi; mov esi, ecx
# Shared "this makes a permanent change" Yes/No gate: every purchasable row
# on both the Tech screen (menu, including its Village-Wide rows) and the
# Villager Details screen (detail_menu) calls this immediately after the
# row picker returns a selection, before any owned-check or charge logic
# runs. Kept as a single .shr helper so each of menu/detail_menu's own
# tight .text caves only ever pay for a "call/test/je" (the resolve-and-
# prompt logic itself lives here, where there's room), the same shape as
# appearance_helper_code and cure_all already use for their own DLL calls.
CONFIRM_HELPER_FILE_OFFSET = 0x8BB00
CONFIRM_HELPER_VA = IMAGE_BASE + SHR_RVA + (
    CONFIRM_HELPER_FILE_OFFSET - SHR_FILE_OFFSET
)
# Unified "would this row actually change anything" check for all four
# non-Change-Appearance Villager Details rows, replacing the old inline
# Running-only slot scan in detail_menu (which is why this fits here
# despite detail_menu's own cave being just as tight as menu's -- the
# logic moved out, it didn't just grow). Takes ebx=row (0-3), edx=villager
# record ptr, both already live at detail_menu's own call site. Returns
# 0 (blocked/unavailable -- Running with no free Like slot and not
# already liking it), 1 (would change, proceed to charge), or 2 (already
# at the target state, no charge needed).
DETAIL_PREFLIGHT_FILE_OFFSET = 0x8BC00
DETAIL_PREFLIGHT_VA = IMAGE_BASE + SHR_RVA + (
    DETAIL_PREFLIGHT_FILE_OFFSET - SHR_FILE_OFFSET
)
RUNNING_PREFERENCE_ID = 38  # exact-build preference-table evidence: 0x7B260
# The stock game's own "can one more villager fit" check (decompiled in
# full at 0x43A1A0): population < 15 always fits; 15/25/50 each need their
# housing-tier flag (+0x9FE8/+0x9FF0/+0x9FF8); above that, "cmp eax, 0x5A"
# (90, the real stock cap) at this exact address -- the one byte-patched by
# the patcher's own "collection_progression"/"immediate_fixed" patch_modes
# (data/builds.json's vv1.variants) to raise it to 256. Barrel of Babies'
# own population-capacity guard mirrors this function's first three tiers
# directly (same flags, same 15/25/50 breakpoints -- those never change
# across patch_modes) and reads this exact byte at runtime for the final
# tier instead of assuming which patch_mode is active.
VILLAGE_POPULATION_CAP_CHECK_VA = 0x43A1AE
# menu's own cave has no room left to inline the mode-aware final-tier
# comparison (needs a 32-bit immediate for the 256-cap modes, which alone
# doesn't fit), so it lives here instead -- menu just calls it with
# eax = current population (already computed there via 0x41CF90) and
# gets back eax = 1 (room for one more tier's worth) or 0 (blocked).
POPULATION_FINAL_TIER_FILE_OFFSET = 0x8BD00
POPULATION_FINAL_TIER_VA = IMAGE_BASE + SHR_RVA + (
    POPULATION_FINAL_TIER_FILE_OFFSET - SHR_FILE_OFFSET
)
# menu's own cave has no room to inline Equal Division's own afford-check
# and charge/dispatch/result logic (unlike rows 6-8, this isn't part of
# the shared village-wide extension ABI, so it can't reuse
# VILLAGE_PREFLIGHT_VA/do_village_wide either) -- menu just does
# "cmp ebx, 9 / jb menu_dispatch_normal / call this / jmp menu_loop"
# and this owns everything else, including its own flat 1,000,000-point
# afford check (matching rows 6-8's own inline check exactly) and its own
# no-charge-if-nobody-eligible guard (measured 125 bytes via keystone;
# placed in the confirmed-unused 220-byte gap after POPULATION_FINAL_TIER,
# well ahead of ROW_MESSAGE_HELPER_FILE_OFFSET below).
EQUAL_DIVISION_DISPATCH_FILE_OFFSET = 0x8BD30
EQUAL_DIVISION_DISPATCH_VA = IMAGE_BASE + SHR_RVA + (
    EQUAL_DIVISION_DISPATCH_FILE_OFFSET - SHR_FILE_OFFSET
)
# Generic "<row> completed."/no-change/removed/blocked result box, replacing
# what used to be five separate fixed ASM strings (purchase_complete/
# removed/no_change/event_queued/running_unavailable) plus the ASM call
# site that used to invoke the now-removed ShowOriginsAgeResult export --
# every one of those call sites now forwards (is_detail, row, status) here
# instead, and the icons DLL's ShowOriginsRowMessage picks the OFFICIAL-
# spreadsheet-exact wording per row. .shr's raw section is 0x1000 bytes
# (0x8B000-0x8BFFF); the last other helper (POPULATION_FINAL_TIER) is well
# under 0x100 bytes long, so 0x100 of spacing after it is generous.
ROW_MESSAGE_HELPER_FILE_OFFSET = 0x8BE00
ROW_MESSAGE_HELPER_VA = IMAGE_BASE + SHR_RVA + (
    ROW_MESSAGE_HELPER_FILE_OFFSET - SHR_FILE_OFFSET
)
# Details "Grant Running" tail: when a villager's 4 Like slots are all full
# and Running isn't one of them, DETAIL_PREFLIGHT_VA's own scan has no room
# left to also check Dislikes without exceeding its own cave -- so it tail-
# jumps here instead (this is the last thing DETAIL_PREFLIGHT_VA does, so a
# plain jmp -- not call -- correctly hands its own eventual `ret` straight
# back to detail_menu, matching a normal tail call). Per the OFFICIAL
# spreadsheet's own documented edge case, a Running Dislike is still
# cleared for free even though the Like can't be added; returns eax=2
# (blocked, no dislike to report) or eax=5 (blocked, dislike cleared) --
# both are ShowOriginsRowMessage status values, forwarded to it unchanged.
RUNNING_DISLIKE_CLEAR_FILE_OFFSET = 0x8BE80
RUNNING_DISLIKE_CLEAR_VA = IMAGE_BASE + SHR_RVA + (
    RUNNING_DISLIKE_CLEAR_FILE_OFFSET - SHR_FILE_OFFSET
)
VV1_NATIVE_SKILL_WRITER_VA = 0x437230
VV1_SKILL_FIELDS = (
    (0x3BC, 2),  # Parenting
    (0x3C0, 4),  # Building
    (0x3C4, 1),  # Farming
    (0x3C8, 5),  # Healing
    (0x3CC, 3),  # Research
)

# Cosmetic head-mask overlay (Change Appearance's Mask row, see
# vv1_origins_icons.c's VV_MASK_OFFSET). Placed after RUNNING_DISLIKE_CLEAR,
# the last currently-used .shr sub-cave -- 0x8BE80 + len(running_dislike_
# clear_code) = 0x8BEA8, confirmed all-zero for 190+ bytes up to .shr's own
# raw-section end (0x8BFFF) by a full-file zero-run scan against every
# patch offset already claimed by this manifest.
MASK_OVERLAY_FILE_OFFSET = 0x8BEA8
MASK_OVERLAY_VA = IMAGE_BASE + SHR_RVA + (
    MASK_OVERLAY_FILE_OFFSET - SHR_FILE_OFFSET
)
MASK_SURFACES_VA = MASK_OVERLAY_VA  # 5 x SDL_Surface* cache, NULL until first load
# Every asset filename string anywhere in the stock exe is bare (no "/" or
# "\\" -- confirmed via a full-binary string scan), yet the actual files all
# live under Images/ on disk, so the native loader constructs that prefix at
# load time rather than relying on a CWD that already is Images/. Matching
# that same convention ("Images/mN.png") is the one relative-path shape
# already proven to work for every other asset this game loads.
#
# ONE shared path, not five. The five companion sheets differ only in a single
# digit, so the draw hook writes that digit in place before calling IMG_Load.
# Five separate 16-byte strings cost 80 bytes of a 344-byte cave that the real
# SDL_UpperBlit draw needs; this costs 16 bytes and two instructions.
MASK_PATH_VA = MASK_OVERLAY_VA + 0x14  # "Images/m1.png" + NUL
MASK_PATH_DIGIT_VA = MASK_PATH_VA + 8  # the '1' in "m1.png", overwritten per choice
# Playtested: the first build drew the mask right after the occupied check
# (before the native head/body/clothing draw for that same iteration), so the
# native head painted right over it every frame -- invisible, not broken.
# Split into two hooks instead: the stash hook (at the occupied check) only
# validates the choice and records what to draw, because registers cannot
# carry a value across the rest of the iteration (several draw branches
# repurpose EDI/EAX for their own scratch). The draw itself happens later,
# strictly after all native drawing for that villager is done.
#
# The stash hook records the SCREEN POSITION too, not just the record. It is
# the only one of the three hooks that runs with both the villager record and
# the village object in registers, so it is the only place the position can be
# computed at all: screen = record.xy - village.scroll_xy, exactly the
# subtraction every native draw call in sub_437790 performs (confirmed at the
# head-draw site 0x437d67/0x437d70, which does "sub edx,[ebx+0xc]" /
# "sub ecx,[ebx+8]" against this same object).
MASK_PENDING_RECORD_VA = MASK_OVERLAY_VA + 0x24  # 0 = nothing pending, else record ptr
MASK_PENDING_CHOICE_VA = MASK_OVERLAY_VA + 0x28  # 1..5, valid only when RECORD != 0
MASK_PENDING_X_VA = MASK_OVERLAY_VA + 0x2C  # villager screen x
MASK_PENDING_Y_VA = MASK_OVERLAY_VA + 0x30  # villager screen y
MASK_PENDING_FRAME_VA = MASK_OVERLAY_VA + 0x34  # facing column, record +0x34
# Ground truth, refreshed every real frame: FUN_00409060 (the actual main
# per-frame tick -- confirmed via Ghidra to be the function that calls
# FUN_00403830, which itself does SDL_UpdateTexture/RenderClear/RenderCopy/
# RenderPresent) reads *(its own esi + 0x30) at 0x40913c and pushes that exact
# value as FUN_00403830's surface argument one instruction later -- there is no
# more direct proof obtainable that a pointer *is* the real, currently
# presented destination surface than reading it at the literal call site that
# presents it. MASK_THIRD_DETOUR below reproduces that read and additionally
# stashes it here, once per real frame, so the draw hook (which runs in a
# different object's context -- FUN_00423390's own esi+0x30 was proven by
# direct ReadProcessMemory inspection to be a stable but garbage 0x0BAD0D60,
# 10/10 samples over ~2s) can use this cached value instead of recomputing the
# same pointer from a context where it is not reliably valid. The surface is
# allocated once for the process lifetime, so a one-frame-old cached copy is
# still the right address -- only its contents change per frame.
DEST_SURFACE_CACHE_VA = MASK_OVERLAY_VA + 0x38
MASK_HOOK_VA = MASK_OVERLAY_VA + 0x3C  # stash-only hook (occupied-check splice)
# Sheet geometry, and it is deliberately VV1's OWN head-atlas geometry:
# male_heads.png/female_heads.png are 280x1300 = 7 columns x 20 rows of 40x65
# (verified empirically -- the fully transparent separator columns land on
# multiples of 40, and the 20 content bands start ~65 apart). The generated
# mask sheets (scripts/build_vv1_heathen_mask_sheets.py) use the same cell
# grid, so the blit is a straight cell-for-cell overlay and all alignment
# lives in the art rather than in this assembly.
MASK_CELL_W = 40
# The sheets are built from supplied art that was authored against VV1's own
# head atlas (see scripts/build_vv1_heathen_mask_sheets.py). Its cell spans
# every colour's art, including the Tribal Chief headdress, so it is taller
# than the 65px head cell -- the plumes rise well above the head.
MASK_CELL_H = 160
# Vertical alignment, derived rather than guessed, and now anchored to the
# supplied art rather than to a face-fraction estimate.
#
# The native head draw at 0x438107-0x438150 computes its destination as
#     x = record[+4] - village[+8]
#     y = record[+8] - village[+0xc] + 0x27
# The mask cell's top sits 83px above the head cell's top (the highest of
# the five colours' per-facing offsets), so the cell is drawn at
# 0x27 - 83, i.e. 44px ABOVE the villager's own y.
#
# Getting this wrong is not subtle: the first build stashed the raw y with no
# offset at all, which would have drawn every mask 39px above its villager.
MASK_DRAW_Y_OFFSET = -44
# The village/camera object hanging off the villager manager. Its +8/+0xC are
# the scroll offsets every native draw in sub_437790 subtracts.
VILLAGE_OBJECT_OFFSET = 0x3E010
VILLAGER_FACING_OFFSET = 0x34  # head-draw column (row is +0x360)
# MASK_BACKEDGE_HOOK_VA is NOT a fixed offset -- it's wherever
# mask_hook_code actually ends, computed from its real assembled length
# once main() assembles it. A hardcoded guess here bit us once already:
# the stash hook is 61 bytes, not the 60 (0x3C) originally assumed, which
# shifted every call/jmp target inside the draw hook by exactly 1 byte
# (every one of them silently landed 1 byte into the middle of its real
# target instruction -- confirmed via disassembly, that's what actually
# broke the mask never appearing in the first live playtest of this
# two-hook design). Computing it from the real length can't drift again.

# Splice point 1: sub_437790's per-villager render loop, immediately after
# its own occupied-flag check (JNZ 0x4388CE if byte [eax+0x28] != 1). EAX
# already holds the record base pointer and ESI the manager base at this
# exact instruction -- both are read-only inputs for the mask hook and
# both must come back unchanged for the native loop to resume correctly
# (confirmed via Ghidra + capstone cross-check of sub_437790's real
# function boundary; an earlier same-session guess at this boundary via
# raw linear disassembly landed on the wrong function entirely).
MASK_DETOUR_FILE_OFFSET = 0x377B8
MASK_DETOUR_VA = IMAGE_BASE + MASK_DETOUR_FILE_OFFSET
MASK_DETOUR_ORIGINAL_BYTES = bytes.fromhex("0F8510110000")  # JNZ 0x4388CE
MASK_NATIVE_SKIP_TARGET_VA = 0x4388CE  # original JNZ target (continue loop)
MASK_RESUME_VA = 0x4377BE  # instruction right after the displaced JNZ

# Splice point 2: NOT inside sub_437790 (see below for why). Right after
# FUN_00423390's own "call 0x437790" returns, at 0x424103. Playtested:
# the original splice-point-2 design (inside sub_437790's own loop back-
# edge) fired correctly and wrote real pixels (confirmed via direct
# ReadProcessMemory inspection of the surface's pixel buffer -- the fill
# color landed exactly as written) but never appeared on screen, because
# sub_437790's own "esi" is a DIFFERENT, nested sub-object
# (*(app_object+0x20)) from the actual app_object the game's own present
# path (FUN_00409060 -> FUN_00403830 -> SDL_UpdateTexture/RenderCopy/
# RenderPresent, all confirmed via Ghidra) uses -- the real displayed
# surface is *(app_object+0x30), and there's no way to recover app_object
# from sub_437790's esi (it's a pointer VALUE stored inside app_object,
# not an address offset from it).
#
# FUN_00423390 IS called with app_object directly (its own "esi" register
# is just its fastcall param_1), and sub_437790 is confirmed callee-saved
# on ESI (push esi at entry / pop esi at exit) -- so immediately after
# FUN_00423390's own "call 0x437790" returns, its "esi" is still
# app_object, unclobbered by the callee. That gives a single, trivial
# dereference (*(esi+0x30)) for the correct surface instead of the wrong
# 3-level chain the original design used -- and 0x42410d, a few
# instructions later in this same function, independently reads the same
# esi+0x30 field for an unrelated purpose, confirming it's a real,
# actively-used field at this exact point.
MASK_BACKEDGE_DETOUR_FILE_OFFSET = 0x24103
MASK_BACKEDGE_DETOUR_VA = IMAGE_BASE + MASK_BACKEDGE_DETOUR_FILE_OFFSET
MASK_BACKEDGE_DETOUR_ORIGINAL_BYTES = bytes.fromhex("8B4E086A00")  # mov ecx,[esi+8] ; push 0
MASK_BACKEDGE_RESUME_VA = 0x424108  # native "call 0x41ab20" right after the displaced pair

# Splice point 3: FUN_00409060, the true main per-frame tick (confirmed via
# Ghidra decompile -- it drives mouse/cursor state, the frame-timing
# SDL_Delay pair, and calls FUN_00403830, which does the real
# SDL_UpdateTexture/RenderClear/RenderCopy/RenderPresent chain). Playtested:
# splice point 2 (FUN_00423390's own esi+0x30) read a stable but obviously
# invalid surface (0x0BAD0D60, w=904 h=0 pitch=0 pixels=0x5D9, 10/10 samples
# over ~2s -- not a race, genuinely the wrong/uninitialized value at that
# point in the frame lifecycle). This splice doesn't replace splice point 2
# -- it feeds it. FUN_00409060's own esi is its fastcall param_1, and
# 0x40913c ("mov ecx,[esi+0x30]") is decompiled as literally the surface
# argument passed to FUN_00403830 one instruction later ("call 0x403830" at
# 0x409145) -- there is no more direct evidence a pointer is the real,
# currently-presented surface than reading it at its own presentation call
# site. This hook reproduces that exact 3-instruction sequence unchanged
# (native behavior bit-for-bit identical) and additionally stashes the same
# value into DEST_SURFACE_CACHE_VA. mask_backedge_hook_code (splice point 2)
# now reads that cache instead of recomputing esi+0x30 in its own,
# apparently-unreliable context.
MASK_THIRD_DETOUR_FILE_OFFSET = 0x913C
MASK_THIRD_DETOUR_VA = IMAGE_BASE + MASK_THIRD_DETOUR_FILE_OFFSET
MASK_THIRD_DETOUR_ORIGINAL_BYTES = bytes.fromhex("8B4E30518BCE")
# mov ecx,[esi+0x30] ; push ecx ; mov ecx,esi
MASK_THIRD_RESUME_VA = 0x409142  # native "mov [esi+0x78],eax" right after the displaced trio

# Callable import thunks (jmp dword ptr [IAT slot]) for SDL2/SDL2_image --
# found via Ghidra decompiling FUN_00403d00 (SDL_UpperBlit(src, srcrect,
# dst, dstrect), the primitive under every native sprite blit in this
# build) back to its real caller; grepping the raw .text bytes for a
# direct reference to either IAT slot finds nothing because application
# code calls these fixed jump-table thunks, never the IAT slot itself.
SDL_UPPERBLIT_THUNK_VA = 0x44A9AC
IMG_LOAD_THUNK_VA = 0x44AA78


def assemble(source: str, address: int) -> bytes:
    encoding, _ = Ks(KS_ARCH_X86, KS_MODE_32).asm(source, address)
    return bytes(encoding)


def rel32_jump(source_va: int, target_va: int) -> bytes:
    return b"\xE9" + int(target_va - (source_va + 5)).to_bytes(4, "little", signed=True)


def add_c_string(blob: bytearray, labels: dict[str, int], name: str, value: str) -> None:
    labels[name] = STRINGS_VA + len(blob)
    blob.extend(value.encode("ascii") + b"\0")


def main() -> None:
    original = STOCK.read_bytes()
    strings = bytearray()
    s: dict[str, int] = {}
    add_c_string(strings, s, "button_label", "Upgrades")
    add_c_string(strings, s, "detail_button_label", "Upgrades")
    add_c_string(strings, s, "title", "Origins Upgrades")
    add_c_string(strings, s, "detail_title", "Villager Upgrades")
    add_c_string(strings, s, "not_enough", "Not enough tech points.")
    add_c_string(
        strings,
        s,
        "paused",
        "Time Warp is unavailable while the game is paused.",
    )
    add_c_string(
        strings,
        s,
        "show_icon_dialog_state",
        "ShowOriginsUpgradeMenuState",
    )
    add_c_string(strings, s, "icons_dll", "VVFP VV1 Origins Icons.dll")
    add_c_string(strings, s, "show_icon_dialog_legacy", "ShowOriginsUpgradeMenu")
    add_c_string(strings, s, "show_result_export", "ShowOriginsVillageWideResult")
    add_c_string(strings, s, "show_mastery_result_export", "ShowOriginsMasteryResult")
    add_c_string(strings, s, "show_row_message_export", "ShowOriginsRowMessage")
    add_c_string(strings, s, "show_age_result_export", "ShowOriginsAgeResult")
    add_c_string(
        strings,
        s,
        "show_equal_division_result_export",
        "ShowOriginsEqualDivisionResult",
    )
    add_c_string(strings, s, "show_appearance_picker", "ShowOriginsAppearancePicker")
    add_c_string(strings, s, "show_cure_result", "ShowOriginsCureResult")
    add_c_string(strings, s, "confirm_export", "ShowOriginsPermanentChangeConfirm")
    add_c_string(
        strings,
        s,
        "cure_no_change",
        "Everyone is at full health already. No villagers are sick. "
        "No tech points have been deducted.",
    )

    # tech_cost_table/detail_cost_table are the only tables the charge
    # logic actually reads (legacy_charge indexes tech_cost_table by row;
    # cure_gated below indexes it directly for row 5's cost). A prior
    # per-row name table/format string pair was built here too, but
    # nothing ever read it -- every row's player-visible label always
    # came from the .rc dialog's own hardcoded LTEXT, never from these
    # strings -- so it was dead weight taking up this block's tight
    # budget; removed rather than kept "just in case".
    #
    # detail_costs needs all 5 detail_menu rows, not just the first 4:
    # confirm_helper_code (see below) indexes this table by row for every
    # detail_menu row unconditionally, including row 4 (Change
    # Appearance), before detail_menu's own dispatch ever reaches
    # APPEARANCE_ROUTER_VA -- a 4-entry table left row 4's confirm dialog
    # reading one dword past the table's end (0, since that lands exactly
    # on the first unpatched byte past the strings cave, confirmed by
    # rendering the patch and reading the raw bytes there), showing
    # "Change Appearance for 0 tech points?" instead of the real cost.
    # 5000 matches appearance_helper_code's own hardcoded charge exactly.
    tech_costs = [50000, 30000, 75000, 500000, 500000, 30000]
    detail_costs = [50000, 100000, 40000, 50000, 5000]
    while len(strings) % 4:
        strings.append(0)
    s["tech_cost_table"] = STRINGS_VA + len(strings)
    for value in tech_costs:
        strings.extend(value.to_bytes(4, "little"))
    s["detail_cost_table"] = STRINGS_VA + len(strings)
    for value in detail_costs:
        strings.extend(value.to_bytes(4, "little"))
    if len(strings) > 0x2D0:
        raise RuntimeError(f"string/data block is too large: {len(strings)} bytes")

    # Fixed entry points inside the one guarded executable cave.
    handler_hook = CODE_VA
    constructor_hook = CODE_VA + 0x30
    menu = CODE_VA + 0xC0
    show_dialog = CODE_VA + 0x304
    tech_increment = CODE_VA + 0x360
    food_increment = CODE_VA + 0x3B0
    event_dispatch_hook = CODE_VA + 0x450
    detail_handler_hook = CODE_VA + 0x490
    detail_constructor_hook = CODE_VA + 0x4C0
    detail_menu = DETAIL_MENU_VA

    code = bytearray(b"\x00" * 0x700)

    def put(va: int, source: str) -> None:
        payload = assemble(source, va)
        start = va - CODE_VA
        end = start + len(payload)
        if end > len(code):
            raise RuntimeError(
                f"code at {va:#x} ({len(payload):#x} bytes, end {end:#x}) exceeds cave"
            )
        if any(code[start:end]):
            raise RuntimeError(f"code overlap at {va:#x} (payload {len(payload):#x} bytes)")
        code[start:end] = payload

    put(
        handler_hook,
        f"""
            cmp dword ptr [esp + 4], 8
            jne original_handler
            mov eax, dword ptr [esp + 8]
            cmp eax, 2
            jne original_handler
            call 0x{menu:X}
            xor eax, eax
            ret 8
        original_handler:
            cmp dword ptr [esp + 4], 8
            jmp 0x435AB5
        """,
    )

    put(
        constructor_hook,
        f"""
            push 0x14
            call 0x44AF03
            add esp, 4
            test eax, eax
            je constructor_done
            push 0
            push esi
            push 563
            push 138
            push 0x459340
            push 2
            mov ecx, eax
            call 0x4019B0
            mov edi, eax
            push 0
            push 0xFF555555
            push 0xFF555555
            push 0xFF000000
            push 0x{s['button_label']:X}
            mov ecx, edi
            call 0x4015B0
            push edi
            mov ecx, esi
            call 0x40AB80
        constructor_done:
            mov ecx, dword ptr [esp + 0x20]
            pop edi
            mov eax, esi
            pop esi
            pop ebp
            pop ebx
            mov dword ptr fs:[0], ecx
            add esp, 0x1C
            ret
        """,
    )

    put(
        menu,
        f"""
            push ebx
            push esi
            push edi
            mov esi, ecx
        menu_loop:
            xor edi, edi
            mov eax, dword ptr [esi + 0x0C]
            cmp dword ptr [eax + 0xAD48], 0
            je tech_not_owned_for_menu
            or edi, 8
        tech_not_owned_for_menu:
            mov eax, dword ptr [esi + 0x0C]
            cmp dword ptr [eax + 0xAD4C], 0
            je food_not_owned_for_menu
            or edi, 16
        food_not_owned_for_menu:
            push edi
            push 0
            call 0x{show_dialog:X}
            cmp eax, -1
            je menu_done
            mov ebx, eax
            # Confirmation is deferred to charge: now (only reached on a
            # real Buy, never on Remove -- see charge:'s own comment) so
            # it can show the row's real cost, which isn't known here for
            # rows 6-8 (Village-Wide, 1,000,000 flat, not in tech_cost_table).

            mov edi, dword ptr [esi + 0x0C]
            cmp ebx, 3
            jae check_owned
            cmp ebx, 2
            jne charge
            mov ecx, edi
            call 0x41CF90
            cmp eax, 12
            jbe charge
            cmp byte ptr [edi + 0x9FE8], 1
            jne population_capacity
            cmp eax, 22
            jbe charge
            cmp byte ptr [edi + 0x9FF0], 1
            jne population_capacity
            cmp eax, 47
            jbe charge
            cmp byte ptr [edi + 0x9FF8], 1
            jne population_capacity
            # The final tier's own ceiling isn't fixed at 256 the way the
            # first three tiers (15/25/50) are -- it's whichever patch_mode
            # the player picked at apply time, applied as a *separate* set
            # of patches this feature's own build has no visibility into.
            # No room to inline that check here (needs a 32-bit immediate
            # for the 256-cap modes alone), so it lives in its own .shr
            # helper instead; eax is already the population count from the
            # 0x41CF90 call above, exactly what that helper wants.
            call 0x{POPULATION_FINAL_TIER_VA:X}
            test eax, eax
            jz population_capacity
            jmp charge

        check_owned:
            cmp ebx, 5
            jae charge
            mov eax, dword ptr [esi + 0x0C]
            cmp ebx, 4
            je check_food_owned
            cmp dword ptr [eax + 0xAD48], 0
            jne remove_doubler
            jmp charge
        check_food_owned:
            cmp dword ptr [eax + 0xAD4C], 0
            jne remove_doubler
        charge:
            # Time Warp has one real no-op case: the game is paused. The
            # stock game-speed field at +0xA318 (the same field Time Warp's
            # own do_time_warp branch already reads) is set to the literal
            # sentinel 999 while paused -- confirmed by disassembling every
            # site in the stock exe that reads or writes this field, not
            # assumed from another game's own offset for the same concept.
            cmp ebx, 0
            jne skip_pause_check
            cmp dword ptr [edi + 0xA318], 999
            jne skip_pause_check
            mov eax, 0x{s['paused']:X}
            jmp show_string_and_done
        skip_pause_check:
            # Confirm here, not at the row pick: this is the Buy path only
            # (Remove never reaches charge: at all -- see remove_doubler).
            # confirm_helper_code looks the row's real cost up itself.
            push ebx
            push 0
            call 0x{CONFIRM_HELPER_VA:X}
            test eax, eax
            je menu_loop
            cmp ebx, 5
            je cure_gated
            # Equal Division of Labor (rows 9/10) isn't part of the shared
            # village-wide extension ABI the way rows 6-8 are, so it can't
            # reuse VILLAGE_PREFLIGHT_VA/do_village_wide below -- checked
            # and dispatched entirely by its own .shr helper instead,
            # which owns its own afford check, charge, and result.
            cmp ebx, 9
            jb menu_dispatch_normal
            call 0x{EQUAL_DIVISION_DISPATCH_VA:X}
            jmp menu_loop
        menu_dispatch_normal:
            cmp ebx, 6
            jb legacy_charge
            cmp ebx, 8
            ja menu_loop
            call 0x{VILLAGE_PREFLIGHT_VA:X}
            test eax, eax
            jz menu_loop
            # Afford-it-at-all check only, same as every other row -- the
            # real charge is conditional now, owned by village_wide itself
            # once it knows whether this specific row actually changed
            # anything (see village_wide's own comment).
            cmp dword ptr [edi + 0xA2FC], 1000000
            jb insufficient
            jmp do_village_wide
        cure_gated:
            # Unlike every other row, Cure's own tech-point deduction is
            # not unconditional here: whether anything was actually sick
            # or below full health is only known after the helper below
            # scans the village, so the helper itself owns the charge
            # (only once it knows there is something to charge for) and
            # its own two-outcome messaging instead of this generic
            # charge-then-act path. Only the ordinary "can't even afford
            # it" gate stays here, matching every other row's own
            # insufficient-funds check before it ever runs anything.
            mov eax, dword ptr [0x{s['tech_cost_table']:X} + 5*4]
            cmp dword ptr [edi + 0xA2FC], eax
            jb insufficient
            call 0x{HEAL_CAVE_VA:X}
            jmp menu_done
        legacy_charge:
            mov eax, dword ptr [0x{s['tech_cost_table']:X} + ebx*4]
            cmp dword ptr [edi + 0xA2FC], eax
            jb insufficient
            sub dword ptr [edi + 0xA2FC], eax

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
            cmp ebx, 8
            ja menu_loop
            jmp do_village_wide


        do_time_warp:
            mov eax, 21600
            mov ecx, dword ptr [edi + 0xA318]
            cmp ecx, 3
            jne time_not_three
            mov eax, 10800
        time_not_three:
            cmp ecx, 10
            jne time_apply
            mov eax, 36000
        time_apply:
            sub dword ptr [0x4860F0], eax
            jmp success

        do_island_event:
            mov dword ptr [edi + 0xA300], 0
            jmp success

        do_barrel:
            mov byte ptr [0x{BARREL_PENDING_VA:X}], 1
            mov dword ptr [0x{BARREL_DELAY_COUNTER_VA:X}], 0
            jmp success

        do_tech_doubler:
            mov dword ptr [edi + 0xAD48], 1
            jmp success
        do_village_wide:
            call 0x{HEAL_CAVE_VA:X}
            jmp menu_done
        do_food_doubler:
            or dword ptr [edi + 0xAD4C], 1
            jmp success

        remove_doubler:
            cmp ebx, 4
            je remove_food_doubler
            mov dword ptr [edi + 0xAD48], 0
            jmp removed_success
        remove_food_doubler:
            mov dword ptr [edi + 0xAD4C], 0
        removed_success:
            push 3
            push ebx
            push 0
            call 0x{ROW_MESSAGE_HELPER_VA:X}
            jmp menu_done

        success:
            push 0
            push ebx
            push 0
            call 0x{ROW_MESSAGE_HELPER_VA:X}
            jmp menu_done
        insufficient:
            mov eax, 0x{s['not_enough']:X}
        show_string_and_done:
            push 0
            push 0x{s['title']:X}
            push eax
            call 0x452DB6
            add esp, 0x0C
            jmp menu_done
        population_capacity:
            push 4
            push 2
            push 0
            call 0x{ROW_MESSAGE_HELPER_VA:X}
            jmp menu_done

        menu_done:
            pop edi
            pop esi
            pop ebx
            ret
        """,
    )

    put(
        show_dialog,
        f"""
            push ebx
            push esi
            push 0x{s['icons_dll']:X}
            call dword ptr [0x457010]
            test eax, eax
            je icon_dialog_fallback
            mov edx, 0x{s['show_icon_dialog_legacy']:X}
            cmp dword ptr [esp + 0x0C], 0
            jne icon_dialog_export_selected
            mov edx, 0x{s['show_icon_dialog_state']:X}
            cmp dword ptr [0x{VILLAGE_WIDE_SIGNATURE_VA:X}], 0x50465656
            jne icon_dialog_export_selected
            or dword ptr [esp + 0x10], 0x20000
        icon_dialog_export_selected:
            push edx
            push eax
            call dword ptr [0x4570D4]
            test eax, eax
            je icon_dialog_fallback
            push dword ptr [esp + 0x10]
            push dword ptr [esp + 0x10]
            call eax
            pop esi
            pop ebx
            ret 8
        icon_dialog_fallback:
            mov eax, -1
            pop esi
            pop ebx
            ret 8
        """,
    )

    put(
        tech_increment,
        f"""
            push ebx
            mov ebx, ecx
            mov eax, dword ptr [esp + 8]
            test eax, eax
            jle tech_apply
            cmp dword ptr [esp + 4], 0x428194
            je tech_apply
            cmp dword ptr [esp + 4], 0x41A378
            je tech_apply
            cmp dword ptr [esp + 4], 0x42BB18
            je tech_apply
            cmp dword ptr [ebx + 0xAD48], 0
            jz tech_apply
            shl dword ptr [esp + 8], 1
        tech_apply:
            mov eax, dword ptr [esp + 8]
            add dword ptr [ebx + 0xA2FC], eax
            add dword ptr [ebx + 0x9E20], eax
            pop ebx
            ret 4
        """,
    )

    put(
        food_increment,
        f"""
            push ebx
            mov ebx, ecx
            mov eax, dword ptr [esp + 8]
            test eax, eax
            jle food_apply
            cmp dword ptr [esp + 4], 0x4281DA
            je food_apply
            cmp dword ptr [esp + 4], 0x419459
            je food_apply
            cmp dword ptr [esp + 4], 0x419F14
            je food_apply
            cmp dword ptr [esp + 4], 0x42B86A
            je food_apply
            cmp dword ptr [ebx + 0xAD4C], 0
            jz food_apply
            shl dword ptr [esp + 8], 1
        food_apply:
            mov eax, dword ptr [esp + 8]
            add dword ptr [ebx + 0xA2EC], eax
            add dword ptr [ebx + 0x9E28], eax
            pop ebx
            ret 4
        """,
    )

    put(
        event_dispatch_hook,
        """
            cmp dword ptr [esp + 8], 0x7F4B1A2C
            jne original_event_dispatch
            push 10
            push 12
            call 0x427CA0
            ret 8
        original_event_dispatch:
            mov eax, dword ptr [esp + 4]
            cmp eax, 1
            jmp 0x428477
        """,
    )

    put(
        detail_handler_hook,
        f"""
            cmp dword ptr [esp + 4], 8
            jne original_detail_handler
            mov eax, dword ptr [esp + 8]
            cmp eax, 6
            jne original_detail_handler
            call 0x{detail_menu:X}
            xor eax, eax
            ret 8
        original_detail_handler:
            mov eax, dword ptr [esp + 4]
            push ebx
            jmp 0x44A705
        """,
    )

    put(
        detail_constructor_hook,
        f"""
            push 0x14
            call 0x44AF03
            add esp, 4
            test eax, eax
            je detail_constructor_done
            push 0
            push esi
            push 563
            push 120
            push 0x459340
            push 6
            mov ecx, eax
            call 0x4019B0
            mov edi, eax
            push 0
            push 0xFF555555
            push 0xFF555555
            push 0xFF000000
            push 0x{s['detail_button_label']:X}
            mov ecx, edi
            call 0x4015B0
            push edi
            mov ecx, esi
            call 0x40AB80
        detail_constructor_done:
            mov ecx, dword ptr [esp + 0x1C]
            pop edi
            mov eax, esi
            pop esi
            pop ebx
            mov dword ptr fs:[0], ecx
            add esp, 0x1C
            ret
        """,
    )

    put(
        detail_menu,
        f"""
            push ebx
            push esi
            push edi
            mov esi, ecx
        detail_loop:
            mov eax, dword ptr [esi + 0x0C]
            mov ecx, dword ptr [eax + 0xAD34]
            cmp ecx, 0x100
            jae detail_done
            imul ecx, ecx, 0x3D8
            mov edx, dword ptr [esi + 0x10]
            add edx, ecx
            cmp byte ptr [edx + 0x28], 0
            je detail_done
            push edx
            push 1
            call 0x{show_dialog:X}
            cmp eax, -1
            je detail_done
            mov ebx, eax

            push ebx
            push 1
            call 0x{CONFIRM_HELPER_VA:X}
            test eax, eax
            je detail_loop

            mov edi, dword ptr [esi + 0x0C]
            mov ecx, dword ptr [edi + 0xAD34]
            imul ecx, ecx, 0x3D8
            mov edx, dword ptr [esi + 0x10]
            add edx, ecx
            cmp ebx, 4
            je 0x{APPEARANCE_ROUTER_VA:X}
            call 0x{DETAIL_PREFLIGHT_VA:X}
            cmp eax, 100
            je detail_charge
            # Anything else is already the exact ShowOriginsRowMessage
            # status to display (1=no-change, 2=blocked, 5=blocked-but-
            # dislike-removed) -- no charge, no translation needed.
            jmp detail_row_message
        detail_charge:
            mov eax, dword ptr [0x{s['detail_cost_table']:X} + ebx*4]
            cmp dword ptr [edi + 0xA2FC], eax
            jb detail_insufficient
            sub dword ptr [edi + 0xA2FC], eax
            cmp ebx, 0
            je detail_youth
            cmp ebx, 1
            je detail_mastery
            cmp ebx, 2
            jne detail_age_18
            lea ecx, [edx + 0x398]
            mov eax, 4
        running_find_like_slot:
            cmp dword ptr [ecx], {RUNNING_PREFERENCE_ID}
            je running_remove_dislikes
            cmp dword ptr [ecx], -1
            je running_store_like
            add ecx, 4
            dec eax
            jne running_find_like_slot
            # Unreachable in practice -- DETAIL_PREFLIGHT_VA (or its own
            # RUNNING_DISLIKE_CLEAR_VA tail) already confirmed a free Like
            # slot exists before returning 100/"proceed to charge", so this
            # loop always finds one. Kept as a defensive fallback only.
            mov eax, 2
            jmp detail_row_message
        running_store_like:
            mov dword ptr [ecx], {RUNNING_PREFERENCE_ID}
        running_remove_dislikes:
            lea ecx, [edx + 0x3A8]
            mov eax, 4
        running_dislike_loop:
            cmp dword ptr [ecx], {RUNNING_PREFERENCE_ID}
            jne running_next_dislike
            mov dword ptr [ecx], -1
        running_next_dislike:
            add ecx, 4
            dec eax
            jne running_dislike_loop
            jmp detail_success

        detail_age_18:
            mov dword ptr [edx + 0x348], 360
            mov dword ptr [edx + 0x34C], 360
            cmp dword ptr [edx + 0x358], 0
            je detail_success
            mov dword ptr [edx + 0x358], 318
            jmp detail_success

        detail_youth:
            mov eax, dword ptr [edx + 0x348]
            sub eax, 700
            cmp eax, 100
            jge detail_youth_ready
            mov eax, 100
        detail_youth_ready:
            mov dword ptr [edx + 0x348], eax
            cmp dword ptr [edx + 0x358], 0
            je detail_youth_not_pregnant
            lea ecx, [eax - 1]
            mov dword ptr [edx + 0x34C], ecx
            sub eax, 42
            mov dword ptr [edx + 0x358], eax
            jmp detail_success
        detail_youth_not_pregnant:
            mov dword ptr [edx + 0x34C], eax
            jmp detail_success

        detail_mastery:
            mov dword ptr [edx + 0x3BC], 100
            mov dword ptr [edx + 0x3C0], 100
            mov dword ptr [edx + 0x3C4], 100
            mov dword ptr [edx + 0x3C8], 100
            mov dword ptr [edx + 0x3CC], 100
            jmp detail_success

        detail_success:
            xor eax, eax
            jmp detail_row_message
        detail_insufficient:
            mov eax, 0x{s['not_enough']:X}
            push 0
            push 0x{s['detail_title']:X}
            push eax
            call 0x452DB6
            add esp, 0x0C
            jmp detail_loop
        detail_row_message:
            push eax
            push ebx
            push 1
            call 0x{ROW_MESSAGE_HELPER_VA:X}
            jmp detail_loop
        detail_done:
            pop edi
            pop esi
            pop ebx
            ret
        """,
    )

    patches: list[dict[str, str]] = []

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
            mov dword ptr [edi + 0xAD4C], 1
            ret
        village_wide:
            # None of the three rows charge upfront any more (the generic
            # dispatch that calls this only ever checked affordability, see
            # charge:/skip_pause_check) -- each branch below now owns its
            # own charge, taken only once its own granted count (already
            # computed by the native scan just below) confirms something
            # actually changed, exactly the same shape cure_all uses for
            # Full Heal/Cure.
            push ebx
            push ebp
            push ecx
            push edx
            push esi
            push edi
            mov eax, ebx
            mov ecx, dword ptr [edi + 0xADE8]
            test ecx, ecx
            je village_result_done
            mov edx, 256
            call 0x{VILLAGE_WIDE_ENTRY_VA:X}
            # VILLAGE_WIDE_ENTRY_VA returns three counts in eax/ecx/edx that
            # every branch below needs to survive the icons-dll resolution
            # call (which clobbers eax/ecx/edx as scratch) and, for Running,
            # the result-callback argument pushes further down -- so they're
            # parked in ebp/esi/edi respectively. edi is *also* still the
            # only copy of the village state pointer the charge below needs
            # ([edi + 0xA2FC] is the tech-point balance): overwriting it here
            # destroyed that pointer, so every successful village-wide
            # charge wrote the deduction through a small counter value
            # instead and crashed. The original edi is never actually lost
            # though -- it's the last thing pushed at this block's own
            # entry above, and nothing between here and any of the three
            # charge sites below unbalances the stack (every push before a
            # call here is matched by that call's own self-cleaning ret n,
            # same as ebp/esi already rely on to survive that stretch), so
            # [esp] is a reliable second copy of it for as long as this
            # register gets reused for the edx return value.
            mov ebp, eax
            mov edi, edx
            mov esi, ecx
            # Resolve the icons DLL handle once here rather than once per
            # row below -- by the time we get here, ShowOriginsPermanent-
            # ChangeConfirm has already loaded it successfully, so this is
            # only ever a formality, not a real failure path.
            push 0x{s['icons_dll']:X}
            call dword ptr [0x457010]
            mov edx, eax
            test edx, edx
            je village_result_done
            cmp ebx, 7
            je village_mastery_result
            cmp ebx, 8
            je village_age_result

            mov eax, dword ptr [0x{RUNNING_GRANTED_VA:X}]
            test eax, eax
            jz village_no_change
            # eax is dead here (only needed for the jz test just above) --
            # see the comment above the call that fills edi with the
            # already_running_skipped count instead of the state pointer:
            # [esp] is still that original pointer. pop/push instead of a
            # plain mov reload is a non-destructive peek at the top of the
            # stack that costs one byte less (this cave has none to spare):
            # pop reads it into eax and leaves esp exactly where push then
            # puts it right back, so nothing above [esp] shifts.
            pop eax
            push eax
            sub dword ptr [eax + 0xA2FC], 1000000
            push 0x{s['show_result_export']:X}
            push edx
            call dword ptr [0x4570D4]
            test eax, eax
            je village_result_done
            push esi
            push edi
            push ebp
            mov ecx, dword ptr [0x{RUNNING_GRANTED_VA:X}]
            push ecx
            push ebx
            call eax
            jmp village_result_done

        village_mastery_result:
            mov eax, dword ptr [0x{MASTERY_GRANTED_VA:X}]
            test eax, eax
            jz village_no_change
            # Same state-pointer reload as the Running branch above --
            # MASTERY_GRANTED_VA is re-read from memory below rather than
            # reused from eax, so clobbering it here is safe.
            pop eax
            push eax
            sub dword ptr [eax + 0xA2FC], 1000000
            push 0x{s['show_mastery_result_export']:X}
            push edx
            call dword ptr [0x4570D4]
            test eax, eax
            je village_result_done
            mov ecx, dword ptr [0x{MASTERY_ALREADY_VA:X}]
            push ecx
            mov ecx, dword ptr [0x{MASTERY_GRANTED_VA:X}]
            push ecx
            call eax
            jmp village_result_done

        village_age_result:
            mov eax, dword ptr [0x{AGE_GRANTED_VA:X}]
            test eax, eax
            jz village_no_change
            # Reviewer finding (P2): the previous ordering here charged
            # 1,000,000 tech points before resolving ShowOriginsAgeResult
            # by name -- if this exe payload were ever paired with a
            # stale companion DLL that predates this export (e.g. the one
            # from just before it was restored), GetProcAddress fails,
            # this falls straight to village_result_done, and the player
            # is charged with no result dialog at all, no way to tell
            # whether anything happened. The patcher's own apply() always
            # deploys the exe and its pinned-hash companion DLL from the
            # same manifest together, so this exact skew shouldn't occur
            # in normal use, but resolving before charging is strictly
            # safer and costs nothing extra to do. ebp is free in this
            # branch specifically (unlike Running's own result call just
            # above, which needs it as one of its own arguments), so it
            # holds the resolved export across the charge below.
            push 0x{s['show_age_result_export']:X}
            push edx
            call dword ptr [0x4570D4]
            test eax, eax
            je village_result_done
            mov ebp, eax
            # Same state-pointer reload as the Running branch above --
            # AGE_GRANTED_VA is re-read from memory below rather than
            # reused from eax, so clobbering it here is safe.
            pop eax
            push eax
            sub dword ptr [eax + 0xA2FC], 1000000
            # stdcall pushes right-to-left: ShowOriginsAgeResult(granted,
            # already, golden_child), so golden_child goes on the stack
            # first (deepest), then already, then granted. push m32
            # directly (6 bytes) instead of mov ecx,[addr]/push ecx (7
            # bytes) -- this cave (CURE_ENTRY_VA up to BARREL_PENDING_VA)
            # has no spare room for the extra byte per argument now that
            # there are three instead of two.
            push dword ptr [0x{AGE_GOLDEN_CHILD_VA:X}]
            push dword ptr [0x{AGE_ALREADY_VA:X}]
            push dword ptr [0x{AGE_GRANTED_VA:X}]
            call ebp
            jmp village_result_done

        village_no_change:
            push 1
            push ebx
            push 0
            call 0x{ROW_MESSAGE_HELPER_VA:X}

        village_result_done:
            pop edi
            pop esi
            pop edx
            pop ecx
            pop ebp
            pop ebx
            ret
        cure_all:
            # Full Heal/Cure All Villagers: unlike the old Cure, health is
            # now restored to full (100) for anyone below it, not just
            # anyone below 80 -- and unlike every other row, this helper
            # (not the generic dispatch that called it) owns the charge,
            # since whether there is anything to charge for is only known
            # after this scan. eax tracks how many villagers had sickness
            # cleared, ebp tracks how many had health restored; the two
            # are reported and charged for separately, and if both are
            # zero nothing is charged at all.
            push ebx
            push ebp
            push ecx
            push edx
            push esi
            push edi
            xor eax, eax
            xor ebp, ebp
            mov edx, dword ptr [edi + 0xADE8]
            test edx, edx
            je cure_check_result
            mov ecx, 256
        cure_loop:
            cmp byte ptr [edx + 0x28], 0
            je cure_next
            cmp dword ptr [edx + 0x344], 0
            jle cure_next
            cmp dword ptr [edx + 0x344], 100
            jge cure_health_done
            mov dword ptr [edx + 0x344], 100
            inc ebp
        cure_health_done:
            cmp byte ptr [edx + 0x354], 0
            je cure_next
            mov byte ptr [edx + 0x354], 0
            inc dword ptr [edi + 0x9E2C]
            inc eax
        cure_next:
            add edx, 0x3D8
            dec ecx
            jne cure_loop
        cure_check_result:
            mov ecx, eax
            or ecx, ebp
            jne cure_resolve
            mov eax, 0x{s['cure_no_change']:X}
            push 0
            push 0x{s['title']:X}
            push eax
            call 0x452DB6
            add esp, 0x0C
            jmp cure_done
        cure_resolve:
            mov ebx, eax
            mov esi, ebp
            push 0x{s['icons_dll']:X}
            call dword ptr [0x457010]
            test eax, eax
            je cure_done
            push 0x{s['show_cure_result']:X}
            push eax
            call dword ptr [0x4570D4]
            test eax, eax
            je cure_done
            sub dword ptr [edi + 0xA2FC], 30000
            push esi
            push ebx
            call eax
        cure_done:
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
            mov eax, 0x{s['show_result_export']:X}
            push 0x{s['icons_dll']:X}
            call dword ptr [0x457010]
            test eax, eax
            je preflight_invalid
            push 0x{s['show_result_export']:X}
            push eax
            call dword ptr [0x4570D4]
            test eax, eax
            je preflight_invalid
            mov eax, 1
            ret
        preflight_invalid:
            xor eax, eax
            ret
        """,
        VILLAGE_PREFLIGHT_VA,
    )
    barrel_main_helper_code = assemble(
        f"""
            call 0x448600
            cmp byte ptr [0x{BARREL_PENDING_VA:X}], 2
            jne barrel_main_done
            inc dword ptr [0x{BARREL_DELAY_COUNTER_VA:X}]
            cmp dword ptr [0x{BARREL_DELAY_COUNTER_VA:X}], {BARREL_DELAY_TICKS}
            jb barrel_main_done
            pushad
            mov esi, dword ptr [esp + 4]
            push 0x50F0
            call 0x44AF03
            add esp, 4
            test eax, eax
            je barrel_main_restore
            mov ebx, eax
            push 0x7F4B1A2C
            push 1
            mov ecx, ebx
            call 0x4286B0
            push 0
            push esi
            mov ecx, ebx
            call 0x401AB0
            mov ecx, ebx
            call 0x427620
            mov byte ptr [0x{BARREL_PENDING_VA:X}], 0
            mov dword ptr [0x{BARREL_DELAY_COUNTER_VA:X}], 0
        barrel_main_restore:
            popad
        barrel_main_done:
            jmp 0x424044
        """,
        BARREL_MAIN_HELPER_VA,
    )
    barrel_close_helper_code = assemble(
        f"""
            mov ecx, dword ptr [esi + 0x14]
            push 0x45
            call 0x431470
            push 0
            mov ecx, esi
            call 0x40AE10
            mov eax, dword ptr [esi + 0x0C]
            mov dword ptr [eax + 0xACB4], 1
            cmp byte ptr [0x{BARREL_PENDING_VA:X}], 1
            jne barrel_close_done
            mov byte ptr [0x{BARREL_PENDING_VA:X}], 2
            mov dword ptr [0x{BARREL_DELAY_COUNTER_VA:X}], 0
        barrel_close_done:
            jmp 0x435DCD
        """,
        BARREL_CLOSE_HELPER_VA,
    )
    appearance_router_code = assemble(
        f"""
            call 0x{APPEARANCE_HELPER_VA:X}
            cmp eax, 1
            je appearance_router_changed
            cmp eax, 2
            je appearance_router_no_change
            jmp 0x{DETAIL_LOOP_VA:X}
        appearance_router_changed:
            push 0
            push 4
            push 1
            call 0x{ROW_MESSAGE_HELPER_VA:X}
            jmp 0x{DETAIL_LOOP_VA:X}
        appearance_router_no_change:
            push 1
            push 4
            push 1
            call 0x{ROW_MESSAGE_HELPER_VA:X}
            jmp 0x{DETAIL_LOOP_VA:X}
        """,
        APPEARANCE_ROUTER_VA,
    )
    appearance_helper_code = assemble(
        f"""
            cmp dword ptr [edi + 0xA2FC], 5000
            jb appearance_insufficient
            mov ebx, edx
            push 0x{s['icons_dll']:X}
            call dword ptr [0x457010]
            test eax, eax
            je appearance_fail
            push 0x{s['show_appearance_picker']:X}
            push eax
            call dword ptr [0x4570D4]
            test eax, eax
            je appearance_fail
            push ebx
            call eax
            # eax is 0 (cancelled), 1 (changed), or 2 (OK but nothing
            # changed) -- only the changed case charges; the other two
            # pass straight through to the router unmodified (0 is silent,
            # matching a plain Cancel; 2 still gets its own no-change
            # message from the router, just no charge).
            cmp eax, 1
            jne appearance_fail
            sub dword ptr [edi + 0xA2FC], 5000
            ret
        appearance_insufficient:
            mov eax, 0x{s['not_enough']:X}
            push 0
            push 0x{s['detail_title']:X}
            push eax
            call 0x452DB6
            add esp, 0x0C
            xor eax, eax
        appearance_fail:
            ret
        """,
        APPEARANCE_HELPER_VA,
    )
    confirm_helper_code = assemble(
        f"""
            # Takes only (is_detail, row) from the caller -- [esp+4]/[esp+8]
            # at entry -- and looks the row's real cost up itself (tech vs
            # detail cost table), rather than making menu/detail_menu do
            # that lookup themselves: both of their own caves were too
            # tight to afford it, and .shr has room to spare.
            mov ecx, dword ptr [esp + 8]
            cmp dword ptr [esp + 4], 0
            jne confirm_detail_cost
            cmp ecx, 6
            jb confirm_tech_cost
            mov edx, 1000000
            jmp confirm_cost_done
        confirm_tech_cost:
            mov edx, dword ptr [0x{s['tech_cost_table']:X} + ecx*4]
            jmp confirm_cost_done
        confirm_detail_cost:
            mov edx, dword ptr [0x{s['detail_cost_table']:X} + ecx*4]
        confirm_cost_done:
            push edx
            push 0x{s['icons_dll']:X}
            call dword ptr [0x457010]
            test eax, eax
            je confirm_fail_cleanup
            push 0x{s['confirm_export']:X}
            push eax
            call dword ptr [0x4570D4]
            test eax, eax
            je confirm_fail_cleanup
            push dword ptr [esp + 0]
            push dword ptr [esp + 16]
            push dword ptr [esp + 16]
            call eax
            add esp, 4
            ret 8
        confirm_fail_cleanup:
            add esp, 4
            xor eax, eax
            ret 8
        """,
        CONFIRM_HELPER_VA,
    )
    detail_preflight_code = assemble(
        f"""
            cmp ebx, 0
            je preflight_youth
            cmp ebx, 1
            je preflight_mastery
            cmp ebx, 2
            je preflight_running
            # Set Age to 18 (ebx==3, the only row left here): the Golden
            # Child is hardcoded to stay a child and must never be aged up,
            # so this is checked first and independently of the current-age
            # comparisons below -- it's a categorical exclusion, not an
            # already-18 case, and returns status 6
            # (VV1_ROWMSG_IS_GOLDEN_CHILD) directly with no charge, the
            # same "not 100, so already the exact status to display"
            # convention this function's own caller documents above.
            # push imm8/pop eax (3 bytes) instead of mov eax,imm32 (5
            # bytes) here and in preflight_no_change/preflight_change below
            # -- this function's .shr cave has a fixed 256-byte budget
            # (POPULATION_FINAL_TIER_VA sits immediately after it) with no
            # slack for the naive encoding once this branch is added.
            cmp edx, dword ptr [0x{GOLDEN_CHILD_SINGLETON_VA:X}]
            jne preflight_age_check
            push 6
            pop eax
            ret
        preflight_age_check:
            cmp dword ptr [edx + 0x348], 360
            jne preflight_change
            cmp dword ptr [edx + 0x34C], 360
            jne preflight_change
            mov eax, dword ptr [edx + 0x358]
            test eax, eax
            je preflight_no_change
            cmp eax, 318
            jne preflight_change
            jmp preflight_no_change

        preflight_youth:
            mov ecx, dword ptr [edx + 0x348]
            mov eax, ecx
            sub eax, 700
            cmp eax, 100
            jge preflight_youth_target
            mov eax, 100
        preflight_youth_target:
            cmp ecx, eax
            jne preflight_change
            cmp dword ptr [edx + 0x358], 0
            jne preflight_youth_pregnant
            cmp dword ptr [edx + 0x34C], eax
            jne preflight_change
            jmp preflight_no_change
        preflight_youth_pregnant:
            lea ecx, [eax - 1]
            cmp dword ptr [edx + 0x34C], ecx
            jne preflight_change
            sub eax, 42
            cmp dword ptr [edx + 0x358], eax
            jne preflight_change
            jmp preflight_no_change

        preflight_mastery:
            cmp dword ptr [edx + 0x3BC], 100
            jne preflight_change
            cmp dword ptr [edx + 0x3C0], 100
            jne preflight_change
            cmp dword ptr [edx + 0x3C4], 100
            jne preflight_change
            cmp dword ptr [edx + 0x3C8], 100
            jne preflight_change
            cmp dword ptr [edx + 0x3CC], 100
            jne preflight_change
            jmp preflight_no_change

        preflight_running:
            lea eax, [edx + 0x398]
            mov ecx, 4
        preflight_running_scan:
            cmp dword ptr [eax], {RUNNING_PREFERENCE_ID}
            je preflight_no_change
            cmp dword ptr [eax], -1
            je preflight_change
            add eax, 4
            dec ecx
            jne preflight_running_scan
            jmp 0x{RUNNING_DISLIKE_CLEAR_VA:X}

        preflight_no_change:
            push 1
            pop eax
            ret
        preflight_change:
            push 100
            pop eax
            ret
        """,
        DETAIL_PREFLIGHT_VA,
    )
    running_dislike_clear_code = assemble(
        f"""
            lea eax, [edx + 0x3A8]
            mov ecx, 4
        dislike_scan:
            cmp dword ptr [eax], {RUNNING_PREFERENCE_ID}
            je dislike_found
            add eax, 4
            dec ecx
            jne dislike_scan
            mov eax, 2
            ret
        dislike_found:
            mov dword ptr [eax], -1
            mov eax, 5
            ret
        """,
        RUNNING_DISLIKE_CLEAR_VA,
    )
    # menu's own no-room-to-inline final population tier (see its own call
    # site's comment). Takes eax = current population, returns eax = 1
    # (room for one more Barrel of Babies -- 3 children) or 0 (blocked).
    # 0x{VILLAGE_POPULATION_CAP_CHECK_VA:X}'s opcode byte distinguishes
    # "stock" patch_mode (still the native 83 F8 5A = cmp eax,0x5A=90,
    # unpatched) from "collection_progression"/"immediate_fixed" (both
    # replace it with EB 76 90 = a jmp, raising the real cap to 256) --
    # rendered and diffed all three patch_modes to confirm both forms
    # exactly. This is a plain data read at a fixed address, not a call
    # into any native object.
    population_final_tier_code = assemble(
        f"""
            cmp byte ptr [0x{VILLAGE_POPULATION_CAP_CHECK_VA:X}], 0x83
            jne population_final_tier_expanded
            cmp eax, 87
            ja population_final_tier_blocked
            mov eax, 1
            ret
        population_final_tier_expanded:
            cmp eax, 253
            ja population_final_tier_blocked
            mov eax, 1
            ret
        population_final_tier_blocked:
            xor eax, eax
            ret
        """,
        POPULATION_FINAL_TIER_VA,
    )
    patch(
        POPULATION_FINAL_TIER_FILE_OFFSET,
        b"\0" * len(population_final_tier_code),
        population_final_tier_code,
        "check whether Barrel of Babies' final population tier (above the 15/25/50 housing-flag tiers) has room for 3 more children under whichever patch_mode is actually installed, not just the collection_progression/immediate_fixed 256 cap",
    )
    # Equal Division of Labor: two passes (male, then non-male) over active,
    # living, non-Golden-Child villagers, cyclically assigning the job-
    # preference code table[esi] to each and wrapping esi back to 0 every
    # N entries -- running each gender through its own independent cycle
    # is what actually gives "an equal number of males/females per
    # profession" (a single population-wide cycle can't guarantee that on
    # its own, since gender isn't evenly interleaved in record order).
    # 0x48B614 is this exact VV1 build's own module-static singleton
    # pointer to the current Golden Child's villager record (confirmed via
    # live memory scan + disassembly of its lazy-getter/destructor pair at
    # 0x43da37/0x43da9d-0x43dac6 -- see the Golden Child age-exclusion
    # feature's own record of this, which reached main independently of
    # this one). Only pass 1 counts a Golden Child match into
    # EQUAL_DIVISION_GOLDEN_SKIPPED_VA -- the same record is visited once
    # per pass (both passes scan the full record array), so counting in
    # both would double the reported skip count for what is always exactly
    # one villager.
    equal_division_core_code = assemble(
        f"""
            push ebx
            push esi
            mov dword ptr [0x{EQUAL_DIVISION_N_VA:X}], ecx
            mov dword ptr [0x{EQUAL_DIVISION_GRANTED_VA:X}], 0
            mov dword ptr [0x{EQUAL_DIVISION_GOLDEN_SKIPPED_VA:X}], 0
            # EQUAL_DIVISION_MALE_COUNTS_VA and _FEMALE_COUNTS_VA are laid
            # out contiguously (5 dwords each, back to back), so all 10 can
            # be zeroed in one small indexed loop instead of 10 unrolled
            # movs.
            xor eax, eax
            mov ecx, 10
        equal_division_zero_counts:
            mov dword ptr [eax*4 + 0x{EQUAL_DIVISION_MALE_COUNTS_VA:X}], 0
            inc eax
            dec ecx
            jne equal_division_zero_counts
            xor esi, esi
            mov ebx, dword ptr [edi + 0xADE8]
            test ebx, ebx
            je equal_division_pass2
            mov ecx, 256
        equal_division_loop1:
            cmp byte ptr [ebx + 0x28], 0
            je equal_division_next1
            cmp dword ptr [ebx + 0x344], 0
            jle equal_division_next1
            cmp ebx, dword ptr [0x48B614]
            jne equal_division_check_gender1
            inc dword ptr [0x{EQUAL_DIVISION_GOLDEN_SKIPPED_VA:X}]
            jmp equal_division_next1
        equal_division_check_gender1:
            cmp dword ptr [ebx + 0x350], 1
            jne equal_division_next1
            movzx eax, byte ptr [esi + 0x{EQUAL_DIVISION_TABLE_VA:X}]
            mov dword ptr [ebx + 0x3D0], eax
            inc dword ptr [0x{EQUAL_DIVISION_GRANTED_VA:X}]
            inc dword ptr [esi*4 + 0x{EQUAL_DIVISION_MALE_COUNTS_VA:X}]
            inc esi
            cmp esi, dword ptr [0x{EQUAL_DIVISION_N_VA:X}]
            jne equal_division_next1
            xor esi, esi
        equal_division_next1:
            add ebx, 0x3D8
            dec ecx
            jne equal_division_loop1
        equal_division_pass2:
            xor esi, esi
            mov ebx, dword ptr [edi + 0xADE8]
            test ebx, ebx
            je equal_division_done
            mov ecx, 256
        equal_division_loop2:
            cmp byte ptr [ebx + 0x28], 0
            je equal_division_next2
            cmp dword ptr [ebx + 0x344], 0
            jle equal_division_next2
            cmp ebx, dword ptr [0x48B614]
            je equal_division_next2
            cmp dword ptr [ebx + 0x350], 1
            je equal_division_next2
            movzx eax, byte ptr [esi + 0x{EQUAL_DIVISION_TABLE_VA:X}]
            mov dword ptr [ebx + 0x3D0], eax
            inc dword ptr [0x{EQUAL_DIVISION_GRANTED_VA:X}]
            inc dword ptr [esi*4 + 0x{EQUAL_DIVISION_FEMALE_COUNTS_VA:X}]
            inc esi
            cmp esi, dword ptr [0x{EQUAL_DIVISION_N_VA:X}]
            jne equal_division_next2
            xor esi, esi
        equal_division_next2:
            add ebx, 0x3D8
            dec ecx
            jne equal_division_loop2
        equal_division_done:
            mov eax, dword ptr [0x{EQUAL_DIVISION_GRANTED_VA:X}]
            mov edx, dword ptr [0x{EQUAL_DIVISION_GOLDEN_SKIPPED_VA:X}]
            pop esi
            pop ebx
            ret
        """,
        EQUAL_DIVISION_CORE_VA,
    )
    patch(
        EQUAL_DIVISION_CORE_FILE_OFFSET,
        b"\0" * len(equal_division_core_code),
        equal_division_core_code,
        "Equal Division of Labor: cyclically assign the job-preference code table[esi] to each eligible (active, alive, non-Golden-Child) villager, running males and non-males through independent cycles for gender balance per profession",
    )
    patch(
        EQUAL_DIVISION_TABLE_FILE_OFFSET,
        b"\0" * len(EQUAL_DIVISION_TABLE_BYTES),
        EQUAL_DIVISION_TABLE_BYTES,
        "Equal Division of Labor's own job-preference code table, in on-screen Skills order (Farming, Building, Research, Healing, Breeding) -- codes 1, 4, 3, 5, 2",
    )
    # menu's own "cmp ebx, 9 / jb menu_dispatch_normal / call this / jmp
    # menu_loop" insert (see menu's own dispatch below) hands off entirely
    # to this helper for rows 9 and 10 -- unlike rows 6-8, Equal Division
    # isn't part of the shared village-wide extension ABI, so it owns its
    # own flat 1,000,000-point afford check (mirrors rows 6-8's own inline
    # check exactly) and its own no-charge-if-nobody-eligible guard,
    # instead of routing through VILLAGE_PREFLIGHT_VA/do_village_wide.
    equal_division_dispatch_code = assemble(
        f"""
            push ebx
            push esi
            push ebp
            cmp dword ptr [edi + 0xA2FC], 1000000
            jae equal_division_funds_ok
            mov eax, 0x{s['not_enough']:X}
            push 0
            push 0x{s['title']:X}
            push eax
            call 0x452DB6
            add esp, 0x0C
            jmp equal_division_dispatch_done
        equal_division_funds_ok:
            mov ecx, 5
            mov ebp, 1
            cmp ebx, 10
            jne equal_division_call_core
            mov ecx, 4
            xor ebp, ebp
        equal_division_call_core:
            call 0x{EQUAL_DIVISION_CORE_VA:X}
            test eax, eax
            jnz equal_division_has_granted
            push 1
            push ebx
            push 0
            call 0x{ROW_MESSAGE_HELPER_VA:X}
            jmp equal_division_dispatch_done
        equal_division_has_granted:
            mov ebx, eax
            mov esi, edx
            sub dword ptr [edi + 0xA2FC], 1000000
            push 0x{s['icons_dll']:X}
            call dword ptr [0x457010]
            test eax, eax
            je equal_division_dispatch_done
            push 0x{s['show_equal_division_result_export']:X}
            push eax
            call dword ptr [0x4570D4]
            test eax, eax
            je equal_division_dispatch_done
            push 0x{EQUAL_DIVISION_FEMALE_COUNTS_VA:X}
            push 0x{EQUAL_DIVISION_MALE_COUNTS_VA:X}
            push ebp
            push esi
            push ebx
            call eax
        equal_division_dispatch_done:
            pop ebp
            pop esi
            pop ebx
            ret
        """,
        EQUAL_DIVISION_DISPATCH_VA,
    )
    patch(
        EQUAL_DIVISION_DISPATCH_FILE_OFFSET,
        b"\0" * len(equal_division_dispatch_code),
        equal_division_dispatch_code,
        "Equal Division of Labor's own afford-check/charge/dispatch-by-row/result helper for Tech screen rows 9 (Includes Parenting, N=5) and 10 (No Parenting, N=4)",
    )
    # Forwards (is_detail, row, status) -- pushed by every plain-completion/
    # no-change/removed/blocked call site in menu, detail_menu, the
    # village-wide dispatch, and the appearance router -- to the icons
    # DLL's ShowOriginsRowMessage export, which knows each row's exact
    # OFFICIAL-spreadsheet wording. Same resolve-then-call shape as
    # confirm_helper_code below, just simpler: no cost-table lookup, the
    # three incoming args are forwarded to the export unchanged.
    row_message_helper_code = assemble(
        f"""
            push 0x{s['icons_dll']:X}
            call dword ptr [0x457010]
            test eax, eax
            je row_message_fail
            push 0x{s['show_row_message_export']:X}
            push eax
            call dword ptr [0x4570D4]
            test eax, eax
            je row_message_fail
            push dword ptr [esp + 0x0C]
            push dword ptr [esp + 0x0C]
            push dword ptr [esp + 0x0C]
            call eax
            ret 0x0C
        row_message_fail:
            ret 0x0C
        """,
        ROW_MESSAGE_HELPER_VA,
    )
    patch(
        ROW_MESSAGE_HELPER_FILE_OFFSET,
        b"\0" * len(row_message_helper_code),
        row_message_helper_code,
        "resolve and invoke the icons DLL's shared ShowOriginsRowMessage export, forwarding (is_detail, row, status) unchanged -- the generic completion/no-change/removed/blocked result box every plain-wording row now routes through",
    )
    patch(
        HEAL_CAVE_FILE_OFFSET,
        b"\0" * 5,
        rel32_jump(HEAL_CAVE_STUB_VA, CURE_ENTRY_VA),
        "redirect the shared VV1 Cure/village-wide dispatch stub to its certified helper after the optional Origins reserve",
    )
    patch(
        CONFIRM_HELPER_FILE_OFFSET,
        b"\0" * len(confirm_helper_code),
        confirm_helper_code,
        "resolve and invoke the icons DLL's shared permanent-change Yes/No confirmation, called by both menu and detail_menu immediately after a row is picked and before any owned-check or charge",
    )
    patch(
        DETAIL_PREFLIGHT_FILE_OFFSET,
        b"\0" * len(detail_preflight_code),
        detail_preflight_code,
        "check whether a detail_menu row (Grant Youth, Grant Full Mastery, Grant Running, Set Age 18) would actually change the selected villager before detail_menu charges for it, returning 100=would change/proceed to charge, or a ShowOriginsRowMessage status to display directly with no charge (1=no-change, 2=blocked/Running Dislike-free case tail-jumps to RUNNING_DISLIKE_CLEAR_VA which also returns 5=blocked-but-dislike-removed)",
    )
    patch(
        RUNNING_DISLIKE_CLEAR_FILE_OFFSET,
        b"\0" * len(running_dislike_clear_code),
        running_dislike_clear_code,
        "Details Grant Running: when all 4 Like slots are full, clear any Running Dislike for free (OFFICIAL spreadsheet edge case) and report whether one was actually cleared; tail-jumped into from DETAIL_PREFLIGHT_VA's own exhausted Like-slot scan",
    )

    # --- Cosmetic head-mask overlay (Change Appearance's Mask row) ---
    #
    # +0x374 (VV_MASK_OFFSET in vv1_origins_icons.c) is the player's chosen
    # mask (0=none, 1..5=variant), written by the Change Appearance dialog.
    # This hook is purely additive: it never reads or writes any field the
    # native engine itself uses for anything else (deliberately NOT the
    # real nursing-baby-icon flag at +0x29 -- see vv1_origins_icons.c's own
    # comment on VV_MASK_OFFSET for why that would have been wrong). It
    # draws by calling SDL_UpperBlit directly with a real SDL_Surface* from
    # IMG_Load, rather than replicating the game's own multi-level sprite-
    # wrapper class -- confirmed via Ghidra that IMG_Load/SDL_UpperBlit are
    # both directly callable at fixed addresses in this exact build (no
    # GetProcAddress needed).
    #
    # First live playtest (draw hook spliced right at the occupied check,
    # a single site) showed the picker/persistence working but no visible
    # mask -- the native head/body/clothing draw for that SAME iteration
    # happens *after* that splice point, so it painted right over the
    # mask every frame. Split into two hooks: this splice only validates
    # the choice and stashes (record pointer, choice) in cave memory --
    # several draw branches later in the same iteration repurpose
    # EDI/EAX/etc. for their own scratch, so a register can't reliably
    # carry the value across the rest of the iteration. The actual draw
    # happens in the second hook, at the loop's own back-edge (confirmed
    # via a full-.text xref scan to be the single point every one of the
    # loop's 19 distinct draw/skip branches converges on), strictly after
    # all native drawing for that iteration is done.
    mask_surfaces_data = b"\0" * 20
    # One shared path; the draw hook rewrites the digit before each IMG_Load.
    mask_path_data = b"Images/m1.png\0".ljust(16, b"\0")
    # PENDING_RECORD, PENDING_CHOICE, PENDING_X, PENDING_Y, PENDING_FRAME,
    # DEST_SURFACE_CACHE.
    mask_pending_data = b"\0" * 24
    mask_hook_code = assemble(
        f"""
            jnz {MASK_NATIVE_SKIP_TARGET_VA:#x}
            movzx edx, byte ptr [eax + 0x374]
            test edx, edx
            jz mask_resume
            cmp edx, 5
            ja mask_resume
            # Only ever SET the pending slot, never clear it here. This hook
            # fires once per occupied villager per frame (up to 256 times), so
            # clearing on every villager without a mask -- the original
            # behaviour -- meant whichever villager was iterated LAST won,
            # regardless of whether IT had a mask, and the draw hook (which
            # runs once per frame, after the whole loop) almost always saw 0.
            # Only a villager that DOES have a valid choice may touch the slot.
            push ecx
            mov ecx, dword ptr [esi + {VILLAGE_OBJECT_OFFSET:#x}]
            mov dword ptr [{MASK_PENDING_RECORD_VA:#x}], eax
            mov dword ptr [{MASK_PENDING_CHOICE_VA:#x}], edx
            # screen = record.xy - village.scroll_xy, the same subtraction the
            # native head draw performs at 0x438146/0x438126, plus the
            # mask-cell alignment offset (see MASK_DRAW_Y_OFFSET).
            mov edx, dword ptr [eax + 4]
            sub edx, dword ptr [ecx + 8]
            mov dword ptr [{MASK_PENDING_X_VA:#x}], edx
            mov edx, dword ptr [eax + 8]
            sub edx, dword ptr [ecx + 0xc]
            add edx, {MASK_DRAW_Y_OFFSET}
            mov dword ptr [{MASK_PENDING_Y_VA:#x}], edx
            mov edx, dword ptr [eax + {VILLAGER_FACING_OFFSET:#x}]
            mov dword ptr [{MASK_PENDING_FRAME_VA:#x}], edx
            pop ecx
        mask_resume:
            jmp {MASK_RESUME_VA:#x}
        """,
        MASK_HOOK_VA,
    )
    # Computed from mask_hook_code's real assembled length -- see the comment
    # on MASK_HOOK_VA's declaration for why this must never be hardcoded.
    mask_backedge_hook_va = MASK_HOOK_VA + len(mask_hook_code)
    # The draw. Runs once per frame, after sub_437790 has finished every
    # villager, so nothing native paints over it. Everything it needs was
    # stashed by the hook above; the destination surface comes from the
    # per-frame cache written at the real present call site.
    #
    # SDL_UpperBlit(src, srcrect, dst, dstrect) is cdecl, so the caller pops:
    # 16 bytes of arguments plus the two 16-byte SDL_Rects built on the stack.
    # An SDL_Rect is {{x, y, w, h}}, so the fields are pushed in reverse
    # (h, w, y, x) to leave x at the lowest address.
    mask_backedge_hook_code = assemble(
        f"""
            mov ecx, dword ptr [esi + 8]
            push 0
            cmp dword ptr [{MASK_PENDING_RECORD_VA:#x}], 0
            je mask2_done
            pushad
            mov ebx, dword ptr [{MASK_PENDING_CHOICE_VA:#x}]
            mov eax, dword ptr [{MASK_SURFACES_VA - 4:#x} + ebx*4]
            test eax, eax
            jnz mask2_have_surface
            # Lazy load, once per colour per process. IMG_Load returns NULL on
            # a missing or broken file; that NULL stays in the cache and the
            # draw below is skipped, so a missing companion sheet degrades to
            # "no mask" instead of crashing.
            mov al, bl
            add al, 0x30
            mov byte ptr [{MASK_PATH_DIGIT_VA:#x}], al
            push {MASK_PATH_VA:#x}
            call {IMG_LOAD_THUNK_VA:#x}
            add esp, 4
            mov dword ptr [{MASK_SURFACES_VA - 4:#x} + ebx*4], eax
        mask2_have_surface:
            test eax, eax
            jz mask2_skip
            mov edx, dword ptr [{DEST_SURFACE_CACHE_VA:#x}]
            test edx, edx
            jz mask2_skip
            # src rect: this facing's cell in the sheet
            mov ecx, dword ptr [{MASK_PENDING_FRAME_VA:#x}]
            imul ecx, ecx, {MASK_CELL_W}
            push {MASK_CELL_H}
            push {MASK_CELL_W}
            push 0
            push ecx
            mov edi, esp
            # dst rect: the villager's own screen position
            push {MASK_CELL_H}
            push {MASK_CELL_W}
            push dword ptr [{MASK_PENDING_Y_VA:#x}]
            push dword ptr [{MASK_PENDING_X_VA:#x}]
            mov ecx, esp
            push ecx
            push edx
            push edi
            push eax
            call {SDL_UPPERBLIT_THUNK_VA:#x}
            add esp, 48
        mask2_skip:
            mov dword ptr [{MASK_PENDING_RECORD_VA:#x}], 0
            popad
        mask2_done:
            jmp {MASK_BACKEDGE_RESUME_VA:#x}
        """,
        mask_backedge_hook_va,
    )
    # Splice point 3 (see MASK_THIRD_DETOUR_* above): reproduces
    # FUN_00409060's own displaced "mov ecx,[esi+0x30] / push ecx /
    # mov ecx,esi" exactly, plus one extra store to cache that same value
    # for the draw hook to consume.
    mask_frame_cache_va = mask_backedge_hook_va + len(mask_backedge_hook_code)
    mask_frame_cache_code = assemble(
        f"""
            mov ecx, dword ptr [esi + 0x30]
            mov dword ptr [{DEST_SURFACE_CACHE_VA:#x}], ecx
            push ecx
            mov ecx, esi
            jmp {MASK_THIRD_RESUME_VA:#x}
        """,
        mask_frame_cache_va,
    )
    mask_overlay_blob = (
        mask_surfaces_data
        + mask_path_data
        + mask_pending_data
        + mask_hook_code
        + mask_backedge_hook_code
        + mask_frame_cache_code
    )
    patch(
        MASK_OVERLAY_FILE_OFFSET,
        b"\0" * len(mask_overlay_blob),
        mask_overlay_blob,
        "cosmetic head-mask overlay: 5 cached SDL_Surface* + 5 short companion-PNG filenames + a 2-dword pending-draw slot, then the stash-only occupied-check hook and the draw hook that runs at the loop's back-edge -- lazy-IMG_Load's a mask PNG once per colour (cached forever after), blits it with SDL_UpperBlit onto the same destination surface the native per-frame render already targets, strictly after that iteration's native head/body/clothing draw so it isn't painted over; never touches +0x29/+0x2A/+0x344 (the real nursing-baby-icon state) or any other engine field",
    )
    mask_detour_code = assemble(
        f"""
            jmp {MASK_HOOK_VA:#x}
            nop
        """,
        MASK_DETOUR_VA,
    )
    patch(
        MASK_DETOUR_FILE_OFFSET,
        MASK_DETOUR_ORIGINAL_BYTES,
        mask_detour_code,
        "splice the mask-overlay stash hook into sub_437790's per-villager render loop right after its own occupied-flag check -- the hook's own first instruction reproduces the displaced JNZ exactly (same flags, same target), so occupied/unoccupied behavior is bit-for-bit unchanged; EAX (record pointer) and ESI (manager base) are the only registers the native loop needs intact on return, neither is modified by this hook",
    )
    mask_backedge_detour_code = assemble(
        f"""
            jmp {mask_backedge_hook_va:#x}
        """,
        MASK_BACKEDGE_DETOUR_VA,
    )
    patch(
        MASK_BACKEDGE_DETOUR_FILE_OFFSET,
        MASK_BACKEDGE_DETOUR_ORIGINAL_BYTES,
        mask_backedge_detour_code,
        "splice the mask-overlay draw hook into FUN_00423390 right after its own 'call sub_437790' returns. Reproduces the displaced 'mov ecx,[esi+8] / push 0' pair exactly before resuming the native call that follows; the draw itself now targets DEST_SURFACE_CACHE_VA (see MASK_THIRD_DETOUR below) rather than this function's own esi+0x30, which direct ReadProcessMemory inspection proved reads a stable but invalid surface here (0x0BAD0D60, w=904 h=0 pitch=0 pixels=0x5D9, 10/10 samples)",
    )
    mask_frame_cache_detour_code = assemble(
        f"""
            jmp {mask_frame_cache_va:#x}
            nop
        """,
        MASK_THIRD_DETOUR_VA,
    )
    patch(
        MASK_THIRD_DETOUR_FILE_OFFSET,
        MASK_THIRD_DETOUR_ORIGINAL_BYTES,
        mask_frame_cache_detour_code,
        "splice into FUN_00409060 (the true main per-frame tick) immediately before its own call to FUN_00403830 (the function that does the real SDL_UpdateTexture/RenderClear/RenderCopy/RenderPresent chain) -- reproduces the displaced 'mov ecx,[esi+0x30] / push ecx / mov ecx,esi' trio exactly (native presentation is bit-for-bit unchanged) and additionally caches that same, definitively-correct destination-surface pointer into DEST_SURFACE_CACHE_VA for the mask draw hook (splice point 2) to consume",
    )

    patch(
        CURE_ENTRY_FILE_OFFSET,
        b"\0" * len(cure_code),
        cure_code,
        "Full Heal/Cure All Villagers: restore every active living VV1 villager below 100 health to 100 and clear sickness, reporting each count separately and charging 30,000 tech points only if at least one villager actually needed either; charges and deducts nothing when nobody did",
    )
    patch(
        VILLAGE_PREFLIGHT_FILE_OFFSET,
        b"\0" * len(preflight_code),
        preflight_code,
        "validate the complete optional Origins header and result-export dependency before any village-wide charge",
    )
    patch(
        BARREL_PENDING_FILE_OFFSET,
        b"\0",
        b"\0",
        "reserve the process-local one-shot VV1 Barrel event token",
    )
    patch(
        BARREL_DELAY_COUNTER_FILE_OFFSET,
        b"\0" * 4,
        b"\0" * 4,
        f"reserve the process-local VV1 Barrel event delay counter: the main-village update owner is a genuine per-frame tick, so the queued event now waits {BARREL_DELAY_TICKS} ticks after the Tech screen closes instead of firing on the very next one, giving the purchase confirmation time to be read first",
    )
    patch(
        BARREL_MAIN_HELPER_FILE_OFFSET,
        b"\0" * len(barrel_main_helper_code),
        barrel_main_helper_code,
        f"consume the deferred VV1 Barrel token from the stock main-village update owner, waiting {BARREL_DELAY_TICKS} of its own per-frame ticks after the Tech screen closes before actually showing the event",
    )
    patch(
        BARREL_CLOSE_HELPER_FILE_OFFSET,
        b"\0" * len(barrel_close_helper_code),
        barrel_close_helper_code,
        "advance the purchased Barrel token only after the stock Technologies screen closes",
    )
    patch(
        APPEARANCE_ROUTER_FILE_OFFSET,
        b"\0" * len(appearance_router_code),
        appearance_router_code,
        "dedicated Change Appearance dispatch, isolated from detail_menu's own shared, byte-constrained cave: calls the picker helper, then either shows the row's success message and returns to the Upgrades loop, or returns there silently on cancel/failure",
    )
    patch(
        APPEARANCE_HELPER_FILE_OFFSET,
        b"\0" * len(appearance_helper_code),
        appearance_helper_code,
        "resolve and invoke the icons DLL's Change Appearance picker export for the given villager",
    )
    patch(
        0x35ACA,
        bytes.fromhex("8B4E146A45"),
        rel32_jump(0x435ACA, BARREL_CLOSE_HELPER_VA),
        "route the stock Technologies-screen close branch through the Barrel token advance helper",
    )
    patch(
        0x220,
        bytes.fromhex("30ED0200"),
        bytes.fromhex("00F00200"),
        "extend the mapped .rdata VirtualSize to cover the Origins strings tail",
    )
    patch(
        0x270,
        bytes.fromhex("04000000"),
        bytes.fromhex("00100000"),
        "map the complete VV1 .shr helper page used by Origins runtime code",
    )
    patch(
        0x28C,
        bytes.fromhex("400000D0"),
        bytes.fromhex("600000F0"),
        "mark the mapped VV1 .shr helper page executable while retaining its stock data permissions",
    )

    patch(
        0x35AB0,
        bytes.fromhex("837C240408"),
        rel32_jump(0x435AB0, handler_hook),
        "route Tech-screen messages through the guarded Origins Upgrades button handler",
    )
    patch(
        0x358DC,
        bytes.fromhex("8B4C24205F"),
        rel32_jump(0x4358DC, constructor_hook),
        "append the stock-styled Origins Upgrades button before the Tech-screen constructor epilogue",
    )
    patch(
        0x4A700,
        bytes.fromhex("8B44240453"),
        rel32_jump(0x44A700, detail_handler_hook),
        "route Villager Detail messages through the guarded villager-upgrade button handler",
    )
    patch(
        0x4A5FA,
        bytes.fromhex("8B4C241C5F"),
        rel32_jump(0x44A5FA, detail_constructor_hook),
        "append the stock-styled Villager Upgrades button before the Detail-screen constructor epilogue",
    )
    patch(
        0x1D120,
        original[0x1D120 : 0x1D125],
        rel32_jump(0x41D120, tech_increment),
        "double eligible positive earned tech deltas",
    )
    patch(
        0x1D140,
        original[0x1D140 : 0x1D145],
        rel32_jump(0x41D140, food_increment),
        "double eligible positive food-source deltas",
    )
    patch(
        0x28470,
        bytes.fromhex("8B44240483F801"),
        rel32_jump(0x428470, event_dispatch_hook) + b"\x90\x90",
        "route the marked Barrel of Babies request through the native event result path",
    )
    patch(
        0x2403F,
        bytes.fromhex("E8BC450200"),
        rel32_jump(0x42403F, BARREL_MAIN_HELPER_VA),
        "consume a queued Barrel of Babies event only from the stock main-village update owner",
    )
    patch(
        CODE_FILE_OFFSET,
        b"\x00" * len(code),
        bytes(code),
        "install the guarded Origins-exclusive Tech and Villager Detail menus and upgrade implementations",
    )
    patch(
        STRINGS_FILE_OFFSET,
        b"\x00" * len(strings),
        bytes(strings),
        "install Origins upgrade labels, descriptions, costs, and save-scoped doubler state",
    )

    rendered = bytearray(original)
    for item in patches:
        offset = int(item["offset"], 16)
        payload = bytes.fromhex(item["after"])
        rendered[offset : offset + len(payload)] = payload
    OUT_EXE.write_bytes(rendered)
    rendered_json = json.dumps(patches, indent=2) + "\n"
    manifest = {
        "id": "vv1_enable_origins_exclusive_features",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": "vv1",
        "running_preference_id": RUNNING_PREFERENCE_ID,
        "running_preference_evidence": {"source": "exact stock executable embedded preference table", "table_file_offset": "0x7B260", "entry_name": "running"},
        "name": "Enable Origins-Exclusive Features",
        "description": "Adds Origins-style Upgrades buttons to the Tech and Villager Details screens. The Tech menu offers Food and Tech Point Doublers for 500,000 tech points each; only scientist tech production and farmer food production are doubled, while Island Events, story/puzzle discoveries (Whale, berries, mushroom, device), one-time milestone-dialog rewards, Duplicate Collectibles, and Golden Child gains remain unchanged. The Village-Wide menu adds Running, Full Mastery, and Make Villagers Young Adults.",
        "output_tag": "Origins Exclusive Features",
        "companion_files": [
            {
                "source": "assets/origins/VVFP VV1 Origins Icons.dll",
                "destination": "VVFP VV1 Origins Icons.dll",
                "sha256": hashlib.sha256(
                    (ROOT / "assets" / "origins" / "VVFP VV1 Origins Icons.dll").read_bytes()
                ).hexdigest().upper(),
            }
        ] + [
            {
                "source": f"assets/origins/m{n}.png",
                "destination": f"Images/m{n}.png",
                "sha256": hashlib.sha256(
                    (ROOT / "assets" / "origins" / f"m{n}.png").read_bytes()
                ).hexdigest().upper(),
            }
            for n in range(1, 6)
        ],
        "doubler_evidence": {
            "positive_tech_writer": "0x41D120",
            "positive_food_writer": "0x41D140",
            "collection_adjustment": "not independently recorded; no exact callsite claim",
            "island_event_producers": ["0x428194 tech", "0x4281DA food"],
            "story_puzzle_producers": [
                "0x41A378 tech (berries/mushroom/device discovery choice dispatcher)",
                "0x419459 food (Whale puzzle: harvest outcome)",
                "0x419F14 food (berries/mushroom/device discovery choice dispatcher)",
            ],
            "milestone_dialog_producers": ["0x42BB18 tech", "0x42B86A food (fixed one-time 2-choice reward dialog)"],
            "tech_exclusions": [
                "Golden Child tech-point gain (no tech award route in this exact build)",
                "Duplicate Collectibles tech-point gain (no duplicate-collectible tech writer route in this exact build)",
                "Island Event tech-point gain (return 0x428194)",
                "Story/puzzle discovery tech-point gain (return 0x41A378)",
                "One-time milestone dialog tech-point gain (return 0x42BB18)",
            ],
            "hook_status": "GO: exact-build positive writer wrappers double eligible positive deltas once; Island Event, story-puzzle, and one-time-milestone returns remain native; runtime/player confirmation pending",
        },
        "doubler_composition_contract": {
            "stacking": [
                "positive earned tech deltas only",
                "positive food-source deltas only",
            ],
            "exclusions": [
                "Golden Child tech-point gain",
                "Island Event tech-point gain",
                "Duplicate Collectibles tech-point gain",
                "Story/puzzle discovery tech-point and food-point gain (Whale, berries, mushroom, device-discovery choices)",
                "One-time milestone dialog tech-point and food-point gain",
            ],
            "food_mastery_status": "confirmed absent for this fingerprint; no Food Mastery-like food transform",
            "status": "GO: exact-build positive writer wrappers double eligible positive deltas once; Island Event returns remain native; runtime/player confirmation pending",
        },
        "doubler_purchase_status": {
            "new_purchase": "available at 500,000 tech points for each doubler",
            "existing_owned": "removable at zero cost with zero refund",
            "repurchase": "available again at 500,000 tech points after removal",
        },
        "patches": patches,
    }
    OUT_JSON.write_text(rendered_json, encoding="utf-8")
    MANIFEST_JSON.write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(f"code bytes used: {max(i for i, value in enumerate(code) if value) + 1:#x}/0x700")
    print(f"string bytes used: {len(strings):#x}/0x2d0")
    print(OUT_JSON)
    print(MANIFEST_JSON)
    print(OUT_EXE)


if __name__ == "__main__":
    main()
