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
# Two dedicated appended PE sections for the Heathen-mask feature (owner: no
# shared caves). Stock SizeOfImage = 0x90000 (image ends at VA 0x490000), file
# and section alignment both 0x1000, so these tack cleanly onto the end.
MASK_SECTION_SIZE = 0x1000
MASK_CODE_SECTION_VA = 0x490000   # .vv1mc  R-X : all mask hook/stub code
MASK_DATA_SECTION_VA = 0x491000   # .vv1md  R/W : all mask writable scratch
# .vv1mc raw data begins at file offset 0x8E000 (== stock EOF; the append tacks it
# on). Mask code caves are laid out here instead of the shared .shr gaps. VA maps
# file 0x8E000 -> 0x490000 one-to-one (both 0x1000-aligned).
MASK_CODE_FILE_BASE = 0x8E000
def mask_code_va(off: int) -> int:
    return MASK_CODE_SECTION_VA + (off - MASK_CODE_FILE_BASE)
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
# Raised by do_barrel and cleared by the count helper, so exactly one barrel
# -- the purchased one -- is forced to three children. A natural barrel keeps
# the stock dice roll. Separate from BARREL_PENDING, which is consumed when the
# event is cued rather than when the children are counted.
BARREL_UPGRADE_FLAG_FILE_OFFSET = 0x8B708
BARREL_UPGRADE_FLAG_VA = IMAGE_BASE + SHR_RVA + (
    BARREL_UPGRADE_FLAG_FILE_OFFSET - SHR_FILE_OFFSET
)
# Replaces the stock rand(100) that picks the barrel's baby count.
BARREL_COUNT_ROLL_FILE_OFFSET = 0x8B962
BARREL_COUNT_ROLL_VA = IMAGE_BASE + SHR_RVA + (
    BARREL_COUNT_ROLL_FILE_OFFSET - SHR_FILE_OFFSET
)
BARREL_COUNT_ROLL_SITE = 0x2B00C
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
# The purchased Island Event is queued a few real seconds out instead of
# being made due on the very next scheduler tick.  Zeroing the due stamp
# fired it in whatever tick the handler next ran -- which is also the tick
# a NATURAL island event can be due in, so the two presented back to back.
# 0x402F70 is the scheduler's own clock: it converts
# GetSystemTimeAsFileTime through 0x989680 (10,000,000), so it returns Unix
# epoch SECONDS -- the same units [world+0xA300] already holds and
# the same units Time Warp subtracts in.  The barrel already had a cue delay
# of its own; this gives the Island Event the matching treatment.
ISLAND_QUEUE_CLOCK_VA = 0x402F70
ISLAND_QUEUE_DELAY_SECONDS = 5
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
# Tech-menu row 11 (Change Appearance for All) -> ShowOriginsAppearanceForAll,
# same DLL-side-charge model as the per-villager picker. Stub lives in a free
# .shr gap; the menu just does "cmp ebx,11 / je / call this".
FORALL_HELPER_FILE_OFFSET = 0x8B93F  # free 0x8B93F..0x8BA00 gap
FORALL_HELPER_VA = IMAGE_BASE + SHR_RVA + (
    FORALL_HELPER_FILE_OFFSET - SHR_FILE_OFFSET
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
# Pending-purchase row states for the Tech menu. menu's own cave is full
# (inlining these two checks overran show_dialog at 0x456c04), so it just
# does "mov ecx, [esi+0x0C] / call this / or edi, eax" and this returns the
# "Unavailable" bits to merge into the menu's own state word.
PENDING_ROWS_FILE_OFFSET = 0x8BF00
PENDING_ROWS_VA = IMAGE_BASE + SHR_RVA + (
    PENDING_ROWS_FILE_OFFSET - SHR_FILE_OFFSET
)
# Time Warp (Tech row 0) is resolved in the companion DLL, which owns its
# confirmation, afford check, charge, per-villager advance and result --
# see ShowOriginsTimeWarp there for why the advance cannot be a constant.
# This stub is only the loader/dispatch pair, laid out in the free run
# above PENDING_ROWS_FILE_OFFSET's code and below the end of .shr.
TIME_WARP_HELPER_FILE_OFFSET = 0x8BF80
TIME_WARP_HELPER_VA = IMAGE_BASE + SHR_RVA + (
    TIME_WARP_HELPER_FILE_OFFSET - SHR_FILE_OFFSET
)
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
# --- W^X split: writable mask state lives in .data, not executable .shr ---
#
# Malwarebytes' behavioural engine quarantines the process the moment the
# village render loop starts, because the stash hook writes MASK_MANAGER_VA
# every frame into .shr -- a section that is simultaneously executable.
# Writing to an executable page at runtime is the classic self-modifying-code
# signature. Proven by elimination: the same patched exe with .shr merely
# marked RWX but never written survives; it is the runtime WRITE into an
# executable page that trips the heuristic, and it fires exactly when the
# village starts rendering (which is when the per-frame store begins).
#
# The fix is the W^X rule: code is executable-not-writable, data is
# writable-not-executable. Every mask datum that is written at runtime moves
# into the .data section's zero-filled BSS tail (0x48CD18..0x48CE00, already
# mapped RW and NON-executable, extended below to own the whole page). Only
# read-only constants (the companion-PNG path strings) stay in .shr, which
# Stage 3 will mark read+execute. The mask CODE stays in .shr; it references
# these VAs, so repointing the constants moves the writes with zero assembly
# edits.
DATA_SCRATCH_BASE_VA = MASK_DATA_SECTION_VA  # 0x491000: dedicated appended R/W section (.vv1md), NOT the borrowed .data BSS tail (owner: no shared caves). All derived mask-scratch VAs recompute from here; the DLL's 3 hardcoded copies (VV_MASK_TABLE/MANAGER/PORTRAIT_SCALE) must match.
# Mask writable state, laid out in .data (all zero-initialised by the loader):
MASK_TABLE_VA = DATA_SCRATCH_BASE_VA + 0x00  # 256 villagers x 4 bits = 128 bytes
MASK_TABLE_SIZE = 128
MASK_SURFACES_VA = DATA_SCRATCH_BASE_VA + 0x80  # 5 x SDL_Surface* cache
DEST_SURFACE_CACHE_VA = DATA_SCRATCH_BASE_VA + 0x94
MASK_MANAGER_VA = DATA_SCRATCH_BASE_VA + 0x98
# --- Per-frame stash LIST (fixes the one-mask-per-frame limit) ------------
# The village compositor (sub_437790) runs the stash hook once per villager,
# but the DRAW hook runs once per frame in the present path (0x424xxx), well
# after the whole villager loop. A single pending slot therefore only ever
# carried the LAST masked villager -> one mask drawn per frame. Instead the
# stash hook APPENDS (x, y, packed frame|choice) to this list, and the draw
# hook loops the list and blits every entry, then resets the count for the
# next frame. VV1's draw thunks are shared across heads/bodies/clothing (not
# head-specific like VV2's), so hooking the thunk isn't viable; this stash-
# list is the correct VV1 adaptation (VV4 uses the same fallback).
MASK_LIST_COUNT_VA = DATA_SCRATCH_BASE_VA + 0x9C  # dword: entries stashed this frame
# The per-frame stash list stores just a 1-BYTE record index per masked
# villager, not a 12-byte (x,y,frame,choice) entry.  Two reasons:
#   1. Capacity.  .data has only ~0x280 bytes before .shr.  12-byte entries cap
#      at 39 -- fine for hand-masking a few villagers, but a whole-village
#      "Change Appearance for All" distribution masks every villager (a
#      167-village wants 167), and everything past the 39th was silently
#      dropped, so most villagers rendered bare.  At 1 byte/index all 256
#      possible villagers fit (0x100 bytes) with room to spare.
#   2. Malwarebytes.  Anything that made the exe write through a runtime pointer
#      into memory outside its own image (a DLL-owned buffer) tripped a
#      code-injection heuristic and got the exe quarantined on launch.  Keeping
#      the whole list in the exe's own .data at fixed addresses -- exactly the
#      write pattern the shipped build already used -- stays clean.
# The draw hook recomputes each villager's screen x/y from its record and the
# frame's scroll (saved below), so the stash no longer needs to store them.
MASK_SCROLL_X_VA = DATA_SCRATCH_BASE_VA + 0xA0    # dword: village scroll x, saved each frame
MASK_SCROLL_Y_VA = DATA_SCRATCH_BASE_VA + 0xA4    # dword: village scroll y, saved each frame
MASK_IDX_LIST_VA = DATA_SCRATCH_BASE_VA + 0xA8     # 256 x 1-byte record index
MASK_LIST_CAP = 256          # every villager can be masked at once
# One-shot latch so the per-frame tick fires the DLL's Vv1MaskRestore (sidecar
# -> table) exactly once at startup.  Sits right after the index list; the whole
# scratch region ends at +0x1AC, still well clear of the 0x280 budget.
MASK_RESTORE_DONE_VA = MASK_IDX_LIST_VA + MASK_LIST_CAP  # +0x1A8
# Cached Vv1DrawPortraitMask pointer (0 = not yet resolved), written only by the
# exe portrait cave to its own .data -- the Malwarebytes-safe fixed-address
# pattern, same as every other slot here.
PORTRAIT_DLL_FN_VA = MASK_RESTORE_DONE_VA + 4            # +0x1AC (dword)
# Keep the former portrait-scale dword reserved so the already-reviewed village
# scratch addresses do not move. The exact-argument portrait wrapper no longer
# writes it: it preserves the complete native tuple on the caller's own stack.
PORTRAIT_RESERVED_VA = PORTRAIT_DLL_FN_VA + 4             # +0x1B0 (dword, intentionally unused)
MASK_DATA_SCRATCH_END_VA = PORTRAIT_RESERVED_VA + 4       # +0x1B4
# --- Village all-pose mask (shared-draw hook) scratch -----------------------
# The village mask must ride ON the head through EVERY pose (walk/swim/bend/sit/
# lie/idle-bob). The old blit reconstructed the villager's screen y from its
# record + a fixed -46 lift, which structurally cannot follow non-standing poses
# because each pose applies its own y offset INSIDE the head draw, not in the
# record. The fix hooks the one shared scaled draw (0x409410) every head funnels
# through and re-issues the mask from the head's own draw args (true per-pose
# x/y/facing/scale). To look up the right villager's mask at that choke point we
# stash the current villager RECORD INDEX at each village loop's per-villager
# top; the hook trusts it only when it's valid AND the sprite being drawn is a
# head atlas (stash-as-gate: Details/UI never write it, so they self-exclude).
VILLAGE_CUR_IDX_VA = MASK_DATA_SCRATCH_END_VA           # +0x1B4 dword, villager record index (0xFFFFFFFF = none)
VILLAGE_MASK_SPRITE_VA = VILLAGE_CUR_IDX_VA + 4         # +0x1B8 dword, cached mask-atlas engine sprite (0 = untried)
VILLAGE_MASK_DLL_FN_VA = VILLAGE_MASK_SPRITE_VA + 4     # +0x1BC dword, cached Vv1GetMaskSprite ptr (0 = unresolved)
VILLAGE_SURFACE_SAVE_VA = VILLAGE_MASK_DLL_FN_VA + 4    # +0x1C0 dword, deref'd renderer surface across the two sub-draws
VILLAGE_FILL_SAVE_VA = VILLAGE_SURFACE_SAVE_VA + 4      # +0x1C4 dword, caller's eax (draw fill arg) across the sub-draws
VILLAGE_MASK_ROW_VA = VILLAGE_FILL_SAVE_VA + 4          # +0x1C8 dword, mask colour row (mask-1) for the mask sub-draw
VILLAGE_DBG_CALLER_VA = VILLAGE_MASK_ROW_VA + 4         # +0x1CC dword, DIAGNOSTIC: caller of a head-atlas draw seen with an invalid stash (requires runtime trace; not evidence of a separate renderer)
VILLAGE_MASKED_BITMAP_VA = VILLAGE_DBG_CALLER_VA + 4    # +0x1D0..+0x1F0, 256-bit per-frame "already masked this villager" guard (cleared once per frame by the draw hook) so villagers drawn by more than one render pass get exactly ONE mask
VILLAGE_DRAWFN_VA = VILLAGE_MASKED_BITMAP_VA + 0x20     # +0x1F0 dword, per-entry original draw fn (0x408840 adult / 0x408740 child-alt) so one shared 5-arg body serves both thunks
VILLAGE_SCRATCH_END_VA = VILLAGE_DRAWFN_VA + 4          # +0x1F4 (inside patch-owned .vv1md R/W scratch)
# The exact-build save builder at 0x402ED0 receives the numbered save slot as
# its first argument before formatting "%s%d.ldw".  Capture that argument in
# patch-owned R/W scratch so the DLL can select a slot-specific sidecar.  Zero
# is deliberately invalid/fail-closed; the game uses numbered slots 1..5.
MASK_SAVE_SLOT_VA = DATA_SCRATCH_BASE_VA + 0x1F4
MASK_SAVE_SLOT_FIRST = 1
MASK_SAVE_SLOT_LAST = 5
# Set by the exact newborn/allocation hook when it clears a non-zero mask;
# Vv1MaskTick consumes it and persists the active sidecar (retrying on I/O
# failure). This remains in the patch-owned R/W section, never the game record.
MASK_BIRTH_DIRTY_VA = DATA_SCRATCH_BASE_VA + 0x1FC
# Cached Vv1MaskTick pointer for the live village-frame service. 0 means not
# resolved, 1 is the permanent fail-open sentinel, and any other value is the
# validated export address. It is independent of save-slot state, so slot
# changes deliberately do not clear it.
MASK_TICK_DLL_FN_VA = DATA_SCRATCH_BASE_VA + 0x1F8
# The village-mask code (two per-loop stash writes + the shared-draw hook) lives
# in the patch-owned .vv1mc R-X section, laid out contiguously with the other
# VV1 mask helpers and kept separate from the stock shared .shr section.
VILLAGE_MASK_CAVE_FILE = MASK_CODE_FILE_BASE + 0x000   # .vv1mc, 0x400 reserved
VILLAGE_MASK_CAVE_VA = mask_code_va(VILLAGE_MASK_CAVE_FILE)
# Vertical lift (screen px, subtracted from the head's own draw y) that seats the
# mask atlas cell onto the head in the village. Tuned from a screenshot like the
# Details DY; 0 = draw at the head's exact y to start.
VILLAGE_MASK_LIFT = 58   # on-head lift (subtracted from head arg3)
# The restore stub is code, so it lives in the patch-owned .vv1mc R-X section,
# NOT in the tight 344-byte village-mask cave that already overflows. Only ~6
# bytes of glue land in the hot tick hook (a jmp/call into here). pushad/popad
# inside keeps every native register intact across LoadLibrary/GetProcAddress/call.
MASK_RESTORE_STUB_FILE_OFFSET = MASK_CODE_FILE_BASE + 0x6C0  # .vv1mc, 0x60 reserved
MASK_RESTORE_STUB_VA = mask_code_va(MASK_RESTORE_STUB_FILE_OFFSET)
# = 0x48CDC0 + 0x1E0 = 0x48CFA0, which stays below .shr's base 0x48D000 (the
# .data VirtualSize is extended to cover it, but NOT up to 0x48D000 -- see the
# 0x248 patch: reaching the next section's base access-violates on launch).

MASK_OVERLAY_FILE_OFFSET = MASK_CODE_FILE_BASE + 0x400  # .vv1mc, 0x180 reserved
MASK_OVERLAY_VA = mask_code_va(MASK_OVERLAY_FILE_OFFSET)
# The draw hook grew when it moved from reading fat 12-byte stash entries to
# recomputing each masked villager's screen position from a 1-byte record index
# (the fix for the whole-village distribution + Malwarebytes constraints -- see
# MASK_IDX_LIST_VA).  Stash (117) + draw (245) + frame-cache (31) = 393 bytes no
# longer fits the 343-byte 0x8BEA8 cave, so the draw hook alone is relocated to
# a separate region in patch-owned .vv1mc; stash + frame-cache remain earlier
# in the same patch-owned code section.
MASK_DRAW_RELOC_FILE_OFFSET = MASK_CODE_FILE_BASE + 0x580  # .vv1mc, 0x40 reserved
MASK_DRAW_RELOC_VA = mask_code_va(MASK_DRAW_RELOC_FILE_OFFSET)
# The village mask THIRD hook (alternate child render path 0x4093c0 -> 0x408740)
# does NOT fit in the sequential VILLAGE_MASK_CAVE region. It lives in the
# remaining patch-owned .vv1mc tail after the draw-hook stub; the reserved
# offsets below keep the three hook families from overlapping.
THIRD_HOOK_FILE_OFFSET = MASK_CODE_FILE_BASE + 0x5C0  # .vv1mc, 0x100 reserved
THIRD_HOOK_VA = mask_code_va(THIRD_HOOK_FILE_OFFSET)
# Details-screen portrait ("bighead") mask overlay: the Details portrait renders
# through sub_437340, whose head draw at 0x43741B is the shared scaled draw
# (0x409410). This tiny cave replaces that call: it does the original head draw,
# then resolves + calls the DLL's Vv1DrawPortraitMask (which re-issues the scaled
# draw with a mask sprite built through the engine's own constructor, so the mask
# scales to the age-scaled portrait for free). The DLL fn ptr is cached in .data
# (PORTRAIT_DLL_FN_VA) so resolution happens once, not every frame.
PORTRAIT_MASK_CAVE_FILE_OFFSET = MASK_CODE_FILE_BASE + 0x720  # .vv1mc, 0x100 reserved (ends 0x820 < 0x1000)
PORTRAIT_MASK_CAVE_VA = mask_code_va(PORTRAIT_MASK_CAVE_FILE_OFFSET)
# Save-slot capture is isolated in the remaining .vv1mc tail.  It replaces
# only the two first native instructions at 0x402ED0 and replays them before
# the natural 0x402ED6 resume, preserving the save builder's ABI.
SAVE_SLOT_CAPTURE_FILE_OFFSET = MASK_CODE_FILE_BASE + 0x820
SAVE_SLOT_CAPTURE_VA = mask_code_va(SAVE_SLOT_CAPTURE_FILE_OFFSET)
SAVE_SLOT_CAPTURE_SPLICE_FILE_OFFSET = 0x2ED0
SAVE_SLOT_CAPTURE_SPLICE_VA = 0x402ED0
SAVE_SLOT_CAPTURE_RESUME_VA = 0x402ED6
# Read-only export name plus the per-frame mask-service resolver/caller. These
# occupy the otherwise-unused tail of the owned .vv1mc section, after the
# save-slot capture stub and before the section boundary.
MASK_TICK_NAME = b"Vv1MaskTick\0"
MASK_TICK_NAME_FILE_OFFSET = MASK_CODE_FILE_BASE + 0x8F0
MASK_TICK_NAME_VA = mask_code_va(MASK_TICK_NAME_FILE_OFFSET)
MASK_TICK_STUB_FILE_OFFSET = MASK_CODE_FILE_BASE + 0x900
MASK_TICK_STUB_VA = mask_code_va(MASK_TICK_STUB_FILE_OFFSET)
# Exact stock newborn/allocation boundary.  sub_43C350 selects the first free
# record, stores the live occupied byte at 0x43C393, and returns that record's
# index to every normal/event caller.  The mask hook is placed immediately
# after the two initial occupied/faction stores, while ESI is the selected
# record and the original local index remains at [esp+0x10].
MASK_NEWBORN_CLEAR_FILE_OFFSET = MASK_CODE_FILE_BASE + 0xA00
MASK_NEWBORN_CLEAR_VA = mask_code_va(MASK_NEWBORN_CLEAR_FILE_OFFSET)
MASK_NEWBORN_CLEAR_SPLICE_FILE_OFFSET = 0x3C393
MASK_NEWBORN_CLEAR_SPLICE_VA = IMAGE_BASE + MASK_NEWBORN_CLEAR_SPLICE_FILE_OFFSET
MASK_NEWBORN_CLEAR_RESUME_VA = 0x43C39B
MASK_NEWBORN_CLEAR_ORIGINAL_BYTES = bytes.fromhex("C6462801C6462900")
PORTRAIT_SCALED_DRAW_VA = 0x409410        # the engine's shared scaled sprite draw
# VV1's Details portrait mask registration is the live head Y minus the
# scale-aware cell lift, plus this fixed nudge.  Screen Y grows downward, so a
# negative value seats the mask higher on the portrait.  Keep this generator
# contract in lockstep with vv1_origins_icons.c; VV2 overrides the shared C
# source to zero because its portrait registration is already aligned.
DETAILS_MASK_Y_NUDGE_PX = -15
DETAILS_MASK_X_NUDGE_PX = 1
# Read-only companion-PNG path strings. They are genuine read-only constants,
# so they belong in .rdata, and they are added to the Origins string cave in
# main() (MASK_PATHS_VA is assigned there, right after the base strings) --
# that cave is private to this feature, unlike the .text slack, which several
# other fun-patches (population-saturation guards, school-lessons, ...) also
# claim, and unlike the mask cave, which is 5 bytes too small to also hold
# them. Five 16-byte NUL-padded strings so the draw hook can select one by
# (choice << 4) instead of writing a digit into a shared string -- an in-place
# digit write is itself a write into executable memory and would defeat the
# whole W^X split. Every asset filename in the stock exe is bare (no path
# separator), yet the files live under Images/ on disk, so the loader builds
# that prefix at load time; "Images/mN.png" is the one relative-path shape
# already proven to work for this game.
MASK_PATH_STRIDE = 0x10  # 16-byte stride so the draw hook selects by (choice<<4)
mask_paths_data = b"".join(
    f"Images/m{n}.png\0".encode("ascii").ljust(MASK_PATH_STRIDE, b"\0")
    for n in range(1, 6)
)
assert len(mask_paths_data) == 5 * MASK_PATH_STRIDE
# MASK_PATHS_VA is assigned in main() once the string cave offset is known.
# The mask cave itself holds only code.
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
# The stash hook records the SCREEN POSITION too, not just the record. It is
# the only one of the three hooks that runs with both the villager record and
# the village object in registers, so it is the only place the position can be
# computed at all: screen = record.xy - village.scroll_xy, exactly the
# subtraction every native draw call in sub_437790 performs (confirmed at the
# head-draw site 0x437d67/0x437d70, which does "sub edx,[ebx+0xc]" /
# "sub ecx,[ebx+8]" against this same object). The stash LIST lives in .data
# (see the W^X split above), written by this hook each frame.
#
# DEST_SURFACE_CACHE_VA: ground truth refreshed every real frame. FUN_00409060
# (the actual main per-frame tick -- confirmed via Ghidra to call FUN_00403830,
# which does SDL_UpdateTexture/RenderClear/RenderCopy/RenderPresent) reads
# *(its own esi + 0x30) at 0x40913c and pushes that exact value as
# FUN_00403830's surface argument one instruction later. MASK_THIRD_DETOUR
# reproduces that read and stashes it, once per real frame, so the draw hook
# (which runs in a different object's context -- FUN_00423390's own esi+0x30
# was proven by direct ReadProcessMemory inspection to be a stable but garbage
# 0x0BAD0D60) can use the cached value instead. Also in .data now.
#
# MASK_HOOK_VA: the mask code begins right after the read-only path strings in
# .shr. Computed from the strings' real length so it can never drift out of
# sync with the emitted blob (a hardcoded offset once put the hook 8 bytes off
# its assembly base, skewing every absolute branch out of it -- the resume jmp
# landed mid-instruction at 0x4377c6 instead of 0x4377be).
MASK_HOOK_VA = MASK_OVERLAY_VA  # cave holds code only; strings in .text slack

# --- Where a villager's chosen mask actually lives ---------------------
#
# NOT in the villager record. Two separate record bytes were tried and both
# turned out to be occupied by the engine, in ways that a static displacement
# scan provably cannot detect:
#
#   +0x374 sat INSIDE the villager NAME buffer (name base +0x370). Nothing
#          "referenced" it because names are written by bulk string copies,
#          not by a displacement. It silently renamed villagers.
#   +0x3D4 read as all-zero across a 40-villager sample, so it looked free.
#          Across all 210 villagers of a real save, on a FRESH LOAD with no
#          mask ever set, it read 0->196, 1->9, 3->1, 5->1, 8->1, 15->2 --
#          the save-LOAD path writes it, again via a bulk read invisible to
#          a displacement scan.
#
# A full scan of all 211 records then found 186 always-zero bytes but NO run
# of >=4 consecutive, and every one of them is the high byte of a dword
# holding a small value -- writing 1..5 into one would make the engine read
# that dword as e.g. 0x03000000. VV1's 984-byte record is simply full.
#
# So the selection lives in memory THIS PATCH owns instead (MASK_TABLE_VA,
# defined in the W^X block above): 256 villagers, one nibble each, 128 bytes.
# It lives in .data rather than executable .shr so the DLL can write it without
# a write into an executable page. Unlike a record byte, "free" here is
# provable from the build rather than inferred from a sample. The engine cannot
# touch it, so no amount of save/load or villager churn can corrupt it, and a
# stale entry is cosmetic-only by construction.
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
# The mask cell's top sits 85px above the head cell's top (the highest of
# the five colours' per-facing offsets), so the cell is drawn at
# 0x27 - 85, i.e. 46px ABOVE the villager's own y.
#
# Getting this wrong is not subtle: the first build stashed the raw y with no
# offset at all, which would have drawn every mask 39px above its villager.
MASK_DRAW_Y_OFFSET = -46
# Children (and the golden child) draw a smaller head that sits lower than an
# adult's, so the adult-tuned lift above puts the mask too high on them. The
# game's OWN child/adult boundary is age ([record+0x348]) < 0x118 -- it compares
# against exactly this constant throughout, including in the compositor/head
# draw (0x4379a7, 0x437611, 0x438970). The stash hook applies this extra
# downward nudge to any villager below that age (playtest: 3-4px).
CHILD_ADULT_AGE_THRESHOLD = 0x118
CHILD_MASK_EXTRA_DY = 9  # playtest: 4 wasn't enough, down ~5 more
# The village/camera object hanging off the villager manager. Its +8/+0xC are
# the scroll offsets every native draw in sub_437790 subtracts.
VILLAGE_OBJECT_OFFSET = 0x3E010
VILLAGER_FACING_OFFSET = 0x34  # head-draw column (row is +0x360)
# The compositor's villager-index array: record_index = [esi + slot*4 +
# 0x3DBDC]. The engine reads it at 0x437798 (loop head) and again at
# 0x4377e5, then forms the record as manager + index*0x3D8 (0x43779f).
VILLAGER_INDEX_ARRAY_OFFSET = 0x3DBDC
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


def rel32_call(source_va: int, target_va: int) -> bytes:
    """A five-byte E8 call, same displacement maths as rel32_jump."""
    return b"\xE8" + int(target_va - (source_va + 5)).to_bytes(
        4, "little", signed=True
    )

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
        "show_icon_dialog_state",
        "ShowOriginsUpgradeMenuState",
    )
    add_c_string(strings, s, "icons_dll", "VVFP VV1 Origins Icons.dll")
    add_c_string(strings, s, "vv1_mask_restore", "Vv1MaskRestore")
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
    add_c_string(strings, s, "show_appearance_for_all", "ShowOriginsAppearanceForAll")
    add_c_string(strings, s, "draw_portrait_mask", "Vv1DrawPortraitMask")
    add_c_string(strings, s, "get_mask_sprite", "Vv1GetMaskSprite")
    add_c_string(strings, s, "show_cure_result", "ShowOriginsCureResult")
    add_c_string(strings, s, "confirm_export", "ShowOriginsPermanentChangeConfirm")
    add_c_string(strings, s, "time_warp_export", "ShowOriginsTimeWarp")
    add_c_string(
        strings,
        s,
        "cure_no_change",
        "Everyone is at full health already. No villagers are sick. "
        "No tech points have been deducted.",
    )

    # Cosmetic-mask companion-PNG path strings live here in the read-only
    # string cave (.rdata), fixed 16-byte stride so the draw hook selects one
    # by (choice << 4). Aligned to a 16-byte boundary first so MASK_PATHS_VA +
    # (choice-1)*0x10 is exact. Kept out of executable memory entirely; see the
    # W^X notes on the mask overlay.
    while len(strings) % MASK_PATH_STRIDE:
        strings.append(0)
    mask_paths_va = STRINGS_VA + len(strings)
    strings.extend(mask_paths_data)

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
            # eax still holds [esi+0x0C] from the check above -- `or edi, 8`
            # does not touch it, and this cave has no bytes to spare.
            cmp dword ptr [eax + 0xAD4C], 0
            je food_not_owned_for_menu
            or edi, 16
        food_not_owned_for_menu:
            # A pending Island Event or Barrel of Babies must not be sold
            # again. Both are queued by writing a value that is already
            # there -- the countdown zeroed, the barrel flag set -- so a
            # second purchase changes nothing while still charging full
            # price. That is the reported bug.
            #
            # The refusal costs the executable no string and no dialog
            # code: the companion DLL renders the Island Event and Barrel
            # of Babies rows as disabled "Unavailable" buttons when these
            # bits are set, so the row cannot be clicked and the charge
            # path is never entered.
            call 0x{PENDING_ROWS_VA:X}
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
            # Time Warp (row 0) is handled end to end by the companion DLL:
            # what it advances, what it costs to say, and whether it may run
            # at all all depend on the game speed at this instant, and the
            # shared confirmation box below cannot vary its wording. edi is
            # the game context here (the same [esi+0x0C] every other row's
            # afford check uses), which is all the DLL needs.
            cmp ebx, 0
            jne charge_not_time_warp
            push edi
            call 0x{TIME_WARP_HELPER_VA:X}
            # 0 = the player cancelled: say nothing and reopen the menu, the
            # same as Cancel on every other row. 1 (applied) and 2 (refused
            # with the reason already shown) both close it, matching what
            # every other charge and refusal here does.
            test eax, eax
            jz menu_loop
            jmp menu_done
        charge_not_time_warp:
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
            # Row 0 (Time Warp) never reaches here -- charge: hands it to
            # the companion DLL, which owns its own paused refusal and its
            # own charge. Every other row charges normally.
            sub dword ptr [edi + 0xA2FC], eax

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


        do_island_event:
            # Queue it, do not make it due immediately (see
            # ISLAND_QUEUE_CLOCK_VA above).  edi is the world here, and the
            # clock leaves ebp/ebx/esi/edi alone, but edi is preserved by
            # hand so this cannot depend on that.
            push edi
            mov ecx, edi
            call 0x{ISLAND_QUEUE_CLOCK_VA:X}
            pop edi
            add eax, {ISLAND_QUEUE_DELAY_SECONDS}
            mov dword ptr [edi + 0xA300], eax
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
        # Offsets at/beyond the stock file size land in the appended mask sections
        # (.vv1mc/.vv1md), which are zero-filled at build time -- the stock file has
        # no bytes there to guard against, so the guard applies only to in-place edits.
        if offset < len(original):
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
            # charge:) -- each branch below now owns its
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
            # Arm the three-child override HERE, immediately before the
            # purchased barrel is dispatched -- not back at purchase time.
            # Raising it at purchase left it set for the whole deferred delay,
            # so a NATURAL barrel firing in that window would consume the
            # one-shot and the paid barrel would fall back to a random count.
            mov byte ptr [0x{BARREL_UPGRADE_FLAG_VA:X}], 1
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
    # Tech-menu row 11 (Change Appearance for All). Mirrors the per-villager
    # picker helper but for the whole village: the DLL export owns the afford
    # check, the conditional 450,000 charge and all messaging, so this stub
    # only resolves and calls it, passing the menu's game context (edi). Any
    # resolve failure is silent (same as a cancel), never crashes.
    forall_helper_code = assemble(
        f"""
            push 0x{s['icons_dll']:X}
            call dword ptr [0x457010]
            test eax, eax
            je forall_helper_done
            push 0x{s['show_appearance_for_all']:X}
            push eax
            call dword ptr [0x4570D4]
            test eax, eax
            je forall_helper_done
            push edi
            call eax
        forall_helper_done:
            ret
        """,
        FORALL_HELPER_VA,
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
            # Row 11 = Change Appearance for All: fixed 450,000, distinct from
            # the flat 1,000,000 that rows 6-10 share.
            cmp ecx, 11
            jne confirm_not_forall
            mov edx, 450000
            jmp confirm_cost_done
        confirm_not_forall:
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
            # Row 11 (Change Appearance for All) also arrives here, because the
            # menu's inline handler is full and its only spare dispatch edge is
            # the shared "ebx >= 9" branch. It has nothing to do with Equal
            # Division: hand it straight to its own helper (which owns the DLL
            # call, afford check, conditional 450,000 charge and messaging) and
            # return, before any of the Equal Division setup below.
            cmp ebx, 11
            jne equal_division_not_forall
            call 0x{FORALL_HELPER_VA:X}
            ret
        equal_division_not_forall:
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
    # Time Warp's DLL entry takes (gamectx, cost). The cost is read here
    # rather than passed in for the same reason confirm_helper_code reads it:
    # menu's own cave has no room to spare, and .shr does.
    time_warp_helper_code = assemble(
        f"""
            push 0x{s['icons_dll']:X}
            call dword ptr [0x457010]
            test eax, eax
            je time_warp_fail
            push 0x{s['time_warp_export']:X}
            push eax
            call dword ptr [0x4570D4]
            test eax, eax
            je time_warp_fail
            # Row 0's entry in the tech cost table, pushed as the second
            # __stdcall argument; the game context arrives at [esp+4] and is
            # still there once the cost is on the stack, at [esp+8].
            mov ecx, dword ptr [0x{s['tech_cost_table']:X}]
            push ecx
            push dword ptr [esp + 8]
            call eax
            ret 4
        time_warp_fail:
            ret 4
        """,
        TIME_WARP_HELPER_VA,
    )
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
    # Both the Island Event and the Barrel of Babies are queued by writing a
    # value that may already be there -- the Island countdown zeroed, the
    # barrel flag set -- so buying a second one while the first is still
    # pending changes nothing and charges full price anyway.
    #
    # Rather than refuse after the click (which needs a message string the
    # exe has no room for), this marks the rows so they cannot be clicked:
    # the icons DLL draws these two rows as disabled "Unavailable" buttons
    # disabled "Unavailable" button. Row 1 is the Island Event, row 2 the
    # Barrel of Babies, hence bits 9 (0x200) and 10 (0x400).
    #
    # Called from menu with no setup: it runs in menu's own frame, so it
    # reads the game context from [esi+0x0C] and ORs the bits straight into
    # edi, the state word menu is building. That keeps the call site to the
    # 5 bytes of the call itself -- menu's cave is full, and inlining the
    # checks (or even passing an argument) overran show_dialog.
    pending_rows_code = assemble(
        f"""
            push eax
            push ecx
            push edx
            push ebx
            mov eax, dword ptr [esi + 0x0C]
            cmp dword ptr [eax + 0xA300], 0
            jne pending_rows_barrel
            or edi, 0x800000
        pending_rows_barrel:
            cmp byte ptr [0x{BARREL_PENDING_VA:X}], 0
            je pending_rows_slots
            or edi, 0x1000000
        pending_rows_slots:
            # Three villager slots must actually be free, counting unburied
            # skeletons and pregnancies as occupants -- they hold a record even
            # though the living-population counter skips them.
            mov ecx, dword ptr [eax + 0xADE8]
            test ecx, ecx
            jz pending_rows_done
            add ecx, 0x28
            xor edx, edx
            # Scan the WHOLE 256-slot array, not just the first 90:
            # occupied records are not packed to the front, so a
            # 90-iteration scan would miss skeletons living above
            # that index. The 90 is the population clamp and belongs
            # in the comparison below, not in the loop bound.
            mov ebx, 0x100
        pending_rows_count:
            cmp byte ptr [ecx], 0
            je pending_rows_next
            inc edx
        pending_rows_next:
            add ecx, 0x3D8
            dec ebx
            jnz pending_rows_count
            cmp edx, 0x57
            jbe pending_rows_done
            or edi, 0x1000000
        pending_rows_done:
            pop ebx
            pop edx
            pop ecx
            pop eax
            ret
        """,
        PENDING_ROWS_VA,
    )
    patch(
        PENDING_ROWS_FILE_OFFSET,
        b"\0" * len(pending_rows_code),
        pending_rows_code,
        "mark the Tech menu's Island Event and Barrel of Babies rows Unavailable while one of each is already pending, so a second purchase cannot be clicked and cannot be charged for",
    )
    # Stock decides the barrel's baby count by dice: rand(100) under 33 gives
    # one child, 33..66 two, 67..99 three. A 75,000-point purchase was therefore
    # partly a coin flip regardless of room, which is the other half of the
    # reported "only 2 children" -- the slot shortage is the first half.
    #
    # Only the PURCHASED barrel is forced; a natural one still rolls. The
    # caller's own `push 0x64` / `add esp, 4` are untouched, so this pushes its
    # own argument for the real rand and cleans it up.
    barrel_count_roll_code = assemble(
        f"""
            push 0x64
            call 0x402F10
            add esp, 4
            cmp byte ptr [0x{BARREL_UPGRADE_FLAG_VA:X}], 0
            je barrel_roll_done
            mov byte ptr [0x{BARREL_UPGRADE_FLAG_VA:X}], 0
            mov eax, 0x63
        barrel_roll_done:
            ret
        """,
        BARREL_COUNT_ROLL_VA,
    )
    patch(
        BARREL_COUNT_ROLL_FILE_OFFSET,
        b"\0" * len(barrel_count_roll_code),
        barrel_count_roll_code,
        "give the purchased Barrel of Babies its full three children, leaving natural barrels on the stock random count",
    )
    patch(
        BARREL_COUNT_ROLL_SITE,
        bytes.fromhex("E8FF7EFDFF"),
        rel32_call(IMAGE_BASE + BARREL_COUNT_ROLL_SITE, BARREL_COUNT_ROLL_VA),
        "route the barrel's baby-count roll through the purchased-barrel override",
    )
    patch(
        TIME_WARP_HELPER_FILE_OFFSET,
        b"\0" * len(time_warp_helper_code),
        time_warp_helper_code,
        "resolve and invoke the icons DLL's ShowOriginsTimeWarp export, passing the game context and Time Warp's own tech cost -- the DLL owns the confirmation that names the current game speed and the years it will advance, the paused refusal, the charge, the per-villager advance, and the result",
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
    # +0x3D4 (VV_MASK_OFFSET in vv1_origins_icons.c) is the player's chosen
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
    # Surfaces/pending/dest-cache/manager all live in .data now (see the W^X
    # split), so no writable data blob is emitted here -- only the read-only
    # path strings (mask_paths_data, defined above) precede the code.
    mask_hook_code = assemble(
        f"""
            jnz {MASK_NATIVE_SKIP_TARGET_VA:#x}
            # ECX and EDX are both dead here -- the engine reloads them at
            # 0x4377c7/0x4377ca before any read -- so this needs no push/pop.
            # EAX (record), EBX (0xC7), EBP (4), ESI, EDI must all survive.
            mov dword ptr [{MASK_MANAGER_VA:#x}], esi
            # Record INDEX, formed exactly as the engine forms it two
            # instructions before this splice (0x437798) and again at
            # 0x4377e5. This is the mask table's key -- NOT the record.
            mov ecx, dword ptr [esi + edi*4 + {VILLAGER_INDEX_ARRAY_OFFSET:#x}]
            cmp ecx, {MASK_TABLE_SIZE * 2}
            jae mask_resume
            mov edx, ecx
            shr edx, 1
            movzx edx, byte ptr [edx + {MASK_TABLE_VA:#x}]
            test cl, 1
            jz mask_low_nibble
            shr edx, 4
            jmp mask_have_choice
        mask_low_nibble:
            and edx, 0xf
        mask_have_choice:
            test edx, edx
            jz mask_resume
            cmp edx, 5
            ja mask_resume
            # ecx = record index (unchanged since the load), edx = choice.
            # APPEND the 1-byte index to the in-.data stash list -- the draw
            # hook recomputes screen x/y, frame and choice from the index and
            # this frame's scroll (saved below), so nothing bigger than an
            # index is stored and all 256 possible villagers fit.  ebx (0xC7)
            # is borrowed as scratch and restored before mask_resume; eax/ebp/
            # esi/edi survive for the native loop.
            push ebx
            mov ebx, dword ptr [{MASK_LIST_COUNT_VA:#x}]
            cmp ebx, {MASK_LIST_CAP}
            jae mask_append_done          # every villager already stashed
            mov byte ptr [ebx + {MASK_IDX_LIST_VA:#x}], cl   # list[count] = index
            inc dword ptr [{MASK_LIST_COUNT_VA:#x}]          # count++
            # Save this frame's village scroll (village object at
            # [esi+VILLAGE_OBJECT]; scroll x at +8, y at +0xC) for the draw
            # hook.  Constant across the frame, so re-saving each append is
            # harmless.
            mov ebx, dword ptr [esi + {VILLAGE_OBJECT_OFFSET:#x}]
            mov ecx, dword ptr [ebx + 8]
            mov dword ptr [{MASK_SCROLL_X_VA:#x}], ecx
            mov ecx, dword ptr [ebx + 0xc]
            mov dword ptr [{MASK_SCROLL_Y_VA:#x}], ecx
        mask_append_done:
            pop ebx
        mask_resume:
            jmp {MASK_RESUME_VA:#x}
        """,
        MASK_HOOK_VA,
    )
    # The draw hook lives in its own relocated gap (it no longer fits the
    # 0x8BEA8 cave alongside stash + frame-cache); the frame-cache goes right
    # after the stash hook in that cave instead.
    mask_backedge_hook_va = MASK_DRAW_RELOC_VA
    # The draw. Runs once per frame, after sub_437790 has finished every
    # villager, so nothing native paints over it. Everything it needs was
    # stashed by the hook above; the destination surface comes from the
    # per-frame cache written at the real present call site.
    #
    # SDL_UpperBlit(src, srcrect, dst, dstrect) is cdecl, so the caller pops:
    # 16 bytes of arguments plus the two 16-byte SDL_Rects built on the stack.
    # An SDL_Rect is {{x, y, w, h}}, so the fields are pushed in reverse
    # (h, w, y, x) to leave x at the lowest address.
    # OLD BLIT FULLY RETIRED: the shared-draw hook renders every village mask on
    # the head now, so this per-frame SDL blit is gone entirely. All this stub
    # does is reproduce FUN's displaced 'mov ecx,[esi+8]; push 0', clear the
    # stash counter each frame (the stash hook still appends, so it must be
    # reset or it overflows the 1-byte index list), and resume. Tiny, so it can
    # never overflow the 0x8B080..0x8B180 draw-hook gap (the bloated loop did,
    # corrupting the neighbouring stash cave's resume jmp -> the 0x48d184 crash).
    mask_backedge_hook_code = assemble(
        f"""
            mov ecx, dword ptr [esi + 8]
            push 0
            mov dword ptr [{MASK_LIST_COUNT_VA:#x}], 0
            jmp {MASK_BACKEDGE_RESUME_VA:#x}
        """,
        mask_backedge_hook_va,
    )
    # Splice point 3 (see MASK_THIRD_DETOUR_* above): reproduces
    # FUN_00409060's own displaced "mov ecx,[esi+0x30] / push ecx /
    # mov ecx,esi" exactly, plus one extra store to cache that same value
    # for the draw hook to consume.
    mask_frame_cache_va = MASK_HOOK_VA + len(mask_hook_code)
    mask_frame_cache_code = assemble(
        f"""
            cmp byte ptr [{MASK_RESTORE_DONE_VA:#x}], 0
            jne mask_restore_skip
            call {MASK_RESTORE_STUB_VA:#x}
        mask_restore_skip:
            call {MASK_TICK_STUB_VA:#x}                 # live dead-slot/reuse sweep every village frame
            mov ecx, dword ptr [esi + 0x30]
            mov dword ptr [{DEST_SURFACE_CACHE_VA:#x}], ecx
            push ecx
            mov ecx, esi
            jmp {MASK_THIRD_RESUME_VA:#x}
        """,
        mask_frame_cache_va,
    )
    # The one-shot mask-restore stub, in the owned R-X .vv1mc section (see
    # MASK_RESTORE_STUB_VA). Runs once (the flag gates the call above). Sets the
    # flag, then pushad/popad brackets LoadLibraryA + GetProcAddress("Vv1Mask-
    # Restore") + call so EVERY native register survives (the tick's resume does
    # `mov [esi+0x78],eax`, so EAX must be preserved). Fail-open: a stock build
    # with no DLL just skips. The DLL's seen-alive latch keeps the restored
    # table from being swept on the still-empty startup frames.
    mask_restore_stub_code = assemble(
        f"""
            mov byte ptr [{MASK_RESTORE_DONE_VA:#x}], 1
            pushad
            push {s['icons_dll']:#x}
            call dword ptr [0x457010]
            test eax, eax
            je mask_restore_ret
            push {s['vv1_mask_restore']:#x}
            push eax
            call dword ptr [0x4570D4]
            test eax, eax
            je mask_restore_ret
            call eax
        mask_restore_ret:
            popad
            ret
        """,
        MASK_RESTORE_STUB_VA,
    )
    # Resolve Vv1MaskTick once and call it on every live village frame. A
    # missing DLL/export is cached as sentinel 1, so fail-open does not become
    # repeated loader work in the render loop. The DLL persists only when a
    # seen-alive slot actually transitions free with a non-zero mask.
    mask_tick_stub_code = assemble(
        f"""
            pushad
            mov eax, dword ptr [{MASK_TICK_DLL_FN_VA:#x}]
            cmp eax, 1
            je mask_tick_ret
            test eax, eax
            jnz mask_tick_call
            push {s['icons_dll']:#x}
            call dword ptr [0x457010]                   # LoadLibraryA
            test eax, eax
            jz mask_tick_missing
            push {MASK_TICK_NAME_VA:#x}
            push eax
            call dword ptr [0x4570D4]                   # GetProcAddress
            test eax, eax
            jz mask_tick_missing
            mov dword ptr [{MASK_TICK_DLL_FN_VA:#x}], eax
        mask_tick_call:
            call eax                                    # Vv1MaskTick @0
            jmp mask_tick_ret
        mask_tick_missing:
            mov dword ptr [{MASK_TICK_DLL_FN_VA:#x}], 1 # permanent fail-open sentinel
        mask_tick_ret:
            popad
            ret
        """,
        MASK_TICK_STUB_VA,
    )
    if len(mask_tick_stub_code) > 0x100:
        raise RuntimeError(
            f"VV1 mask tick stub exceeds its .vv1mc reservation: "
            f"{len(mask_tick_stub_code):#x} > 0x100"
        )
    # Clear a reused record at the game's own newborn/allocation boundary.
    # sub_43C350 selects the first free record and its exact initialization
    # starts at 0x43C393; at this point ESI is that record and the original
    # selected index is still in the function's [esp+0x10] local.  This is
    # stronger than a periodic free-slot sweep: death and birth can happen
    # between two rendered frames, so no free state is necessarily observed.
    # pushad keeps every native register and stack local intact.  The helper
    # only clears the patch-owned nibble and never writes the villager record.
    newborn_clear_code = assemble(
        f"""
            mov byte ptr [esi + 0x28], 1
            mov byte ptr [esi + 0x29], 0
            pushad
            mov ecx, dword ptr [esp + 0x30]       # sub_43C350 local index
            cmp ecx, {MASK_LIST_CAP}
            jae newborn_clear_done
            mov eax, ecx
            shr eax, 1
            mov dl, byte ptr [eax + 0x{MASK_TABLE_VA:X}]
            test cl, 1
            jz newborn_clear_low
            test dl, 0xf0
            jz newborn_clear_done
            and dl, 0x0f
            jmp newborn_clear_store
        newborn_clear_low:
            test dl, 0x0f
            jz newborn_clear_done
            and dl, 0xf0
        newborn_clear_store:
            mov byte ptr [eax + 0x{MASK_TABLE_VA:X}], dl
            mov byte ptr [0x{MASK_BIRTH_DIRTY_VA:X}], 1
        newborn_clear_done:
            popad
            jmp 0x{MASK_NEWBORN_CLEAR_RESUME_VA:X}
        """,
        MASK_NEWBORN_CLEAR_VA,
    )
    if len(newborn_clear_code) > 0x100:
        raise RuntimeError(
            f"VV1 newborn mask-clear hook exceeds its .vv1mc reservation: "
            f"{len(newborn_clear_code):#x} > 0x100"
        )
    patch(
        MASK_NEWBORN_CLEAR_FILE_OFFSET,
        b"\0" * len(newborn_clear_code),
        newborn_clear_code,
        "clear the patch-owned VV1 mask nibble at the exact sub_43C350 newborn/allocation boundary before a free record can be reused; preserves the native occupied/faction stores, all registers, and every villager-record field",
    )
    newborn_clear_detour_code = assemble(
        f"""
            jmp 0x{MASK_NEWBORN_CLEAR_VA:X}
            nop
            nop
            nop
        """,
        MASK_NEWBORN_CLEAR_SPLICE_VA,
    )
    patch(
        MASK_NEWBORN_CLEAR_SPLICE_FILE_OFFSET,
        MASK_NEWBORN_CLEAR_ORIGINAL_BYTES,
        newborn_clear_detour_code,
        "splice sub_43C350 immediately after its selected-record boundary begins; the cave replays mov [esi+0x28],1 and mov [esi+0x29],0 before clearing the corresponding patch-owned mask nibble",
    )
    # Capture the exact numbered save-slot argument before the native builder
    # formats "%s%d.ldw".  The hook is intentionally a tiny ABI-preserving
    # trampoline: it saves every register and the flags while it updates
    # patch-owned state, then replays the displaced
    # `mov eax,[esp+4]; mov edx,[ecx]` and resumes at 0x402ED6.
    #
    # ONLY numbered village slots 1..5 are published.  The same stock builder
    # also formats the META file with slot 0, and this used to normalize that to
    # zero and then store it -- which overwrote the live village slot AND ran
    # the reset below, wiping the whole in-memory mask table.  A meta write
    # therefore made every mask vanish from a running game.  Slot 0 and any
    # out-of-range value now leave the capture and the tables untouched.
    #
    # The reset still runs for a genuine village-slot change (1..5 -> a
    # different 1..5), so masks cannot leak between saves.
    save_slot_capture_code = assemble(
        f"""
            pushfd
            pushad
            mov eax, dword ptr [esp + 0x28]       # original arg1: slot
            cmp eax, {MASK_SAVE_SLOT_LAST}
            ja save_slot_done                      # >5 -> keep the live capture
            cmp eax, {MASK_SAVE_SLOT_FIRST}
            jb save_slot_done                      # 0 (meta file) -> keep it too
            cmp eax, dword ptr [{MASK_SAVE_SLOT_VA:#x}]
            je save_slot_done
            mov dword ptr [{MASK_SAVE_SLOT_VA:#x}], eax
            # Reset the exe-side restore latch and all frame/table scratch.
            # The DLL clears its own seen-alive latch when Vv1MaskRestore sees
            # this new slot, before accepting the matching sidecar.
            mov byte ptr [{MASK_RESTORE_DONE_VA:#x}], 0
            mov dword ptr [{MASK_MANAGER_VA:#x}], 0
            mov dword ptr [{MASK_LIST_COUNT_VA:#x}], 0
            mov dword ptr [{VILLAGE_CUR_IDX_VA:#x}], 0xffffffff
            mov dword ptr [{MASK_SCROLL_X_VA:#x}], 0
            mov dword ptr [{MASK_SCROLL_Y_VA:#x}], 0
            xor eax, eax
            mov edi, {MASK_TABLE_VA:#x}
            mov ecx, {MASK_TABLE_SIZE // 4}
            rep stosd
            mov edi, {VILLAGE_MASKED_BITMAP_VA:#x}
            mov ecx, 8
            rep stosd
        save_slot_done:
            popad
            popfd
            mov eax, dword ptr [esp + 4]
            mov edx, dword ptr [ecx]
            jmp {SAVE_SLOT_CAPTURE_RESUME_VA:#x}
        """,
        SAVE_SLOT_CAPTURE_VA,
    )
    patch(
        SAVE_SLOT_CAPTURE_FILE_OFFSET,
        b"\0" * len(save_slot_capture_code),
        save_slot_capture_code,
        "capture the exact VV1 numbered village save-slot argument at 0x402ED0 into .vv1md and reset the restore/frame/table state on a real slot change; slot zero (the meta file) and out-of-range values leave the live capture and mask tables untouched",
    )
    if SAVE_SLOT_CAPTURE_FILE_OFFSET + len(save_slot_capture_code) > MASK_TICK_NAME_FILE_OFFSET:
        raise RuntimeError("VV1 save-slot capture overlaps the mask tick export name")
    patch(
        MASK_RESTORE_STUB_FILE_OFFSET,
        b"\0" * len(mask_restore_stub_code),
        mask_restore_stub_code,
        "one-shot startup mask-restore stub (in owned R-X .vv1mc): fires the "
        "DLL's Vv1MaskRestore once to repopulate the .data mask table from the "
        "sidecar, so masks appear on load without opening Change Appearance",
    )
    patch(
        MASK_TICK_NAME_FILE_OFFSET,
        b"\0" * len(MASK_TICK_NAME),
        MASK_TICK_NAME,
        "read-only Vv1MaskTick export name for the live village-frame mask service",
    )
    patch(
        MASK_TICK_STUB_FILE_OFFSET,
        b"\0" * len(mask_tick_stub_code),
        mask_tick_stub_code,
        "live village-frame mask service: resolve Vv1MaskTick once, cache missing DLL/export as a fail-open sentinel, and sweep/persist dead mask slots every rendered frame",
    )
    mask_overlay_blob = (
        mask_hook_code
        + mask_frame_cache_code
    )
    # The read-only path strings were already appended to the .rdata string
    # cave above (mask_paths_va); no separate patch is needed for them here.
    patch(
        MASK_OVERLAY_FILE_OFFSET,
        b"\0" * len(mask_overlay_blob),
        mask_overlay_blob,
        "cosmetic head-mask overlay: the stash-only occupied-check hook and the per-frame destination-surface cache hook (the draw hook itself is relocated -- see below) -- lazy-IMG_Load's a mask PNG once per colour (cached in .data forever after), blits it with SDL_UpperBlit onto the same destination surface the native per-frame render already targets, strictly after that iteration's native head/body/clothing draw so it isn't painted over. All writable state (surface cache, pending-draw slot, dest-surface cache, villager-array base, and the 128-byte mask table) lives in .data, NOT in this executable .shr blob, so nothing writes into an executable page at runtime (W^X). Never touches +0x29/+0x2A/+0x344 (the real nursing-baby-icon state) or any other engine field",
    )
    patch(
        MASK_DRAW_RELOC_FILE_OFFSET,
        b"\0" * len(mask_backedge_hook_code),
        mask_backedge_hook_code,
        "cosmetic head-mask overlay draw hook, relocated to its own confirmed-zero .shr gap: it recomputes each masked villager's screen position, facing frame and colour from the 1-byte record index the stash hook left this frame plus the saved village scroll, then blits the matching mask cell; too big to sit in the 0x8BEA8 cave beside the stash and frame-cache hooks",
    )
    # --- Details-screen portrait ("bighead") mask overlay ---
    # sub_437340 renders the Details portrait head at FOUR call sites -- a 2x2
    # of age (child, [rec+0x348] < 0x118 / adult) x head-atlas flag
    # ([rec+0x350] == 1 or not). Every site is the same stdcall-style
    # `call 0x409410` with seven draw arguments. The VV5 contract is to replay
    # that complete native tuple, never reconstruct X/Y/facing from record or
    # screen constants. Replace each call with a call to ONE ABI-compatible
    # wrapper. The wrapper duplicates all seven arguments for the stock head
    # draw (so the originals remain available), then gives the DLL the original
    # renderer wrapper plus a pointer to the untouched tuple. Its `ret 0x1c`
    # exactly matches 0x409410, so all four callers resume with stock ESP and
    # callee-saved registers. esi=gameobj and edi=record are live at every site.
    PORTRAIT_HEAD_DRAW_SITES = [
        0x43741B,   # child, flag==1
        0x4374A4,   # child, flag!=1
        0x437503,   # adult, flag==1
        0x437556,   # adult, flag!=1
    ]
    portrait_wrapper_va = PORTRAIT_MASK_CAVE_VA
    portrait_wrapper = assemble(
        f"""
            push ecx                                    # preserve the exact draw-manager wrapper
            # Stack now: saved-ecx, caller-ret, original arg1..arg7. Repeatedly
            # copying [esp+0x20] walks arg7..arg1 and leaves a correctly ordered
            # seven-argument duplicate at the new top of stack.
            push dword ptr [esp + 0x20]
            push dword ptr [esp + 0x20]
            push dword ptr [esp + 0x20]
            push dword ptr [esp + 0x20]
            push dword ptr [esp + 0x20]
            push dword ptr [esp + 0x20]
            push dword ptr [esp + 0x20]
            mov ecx, dword ptr [esp + 0x1c]             # saved native renderer wrapper
            call 0x{PORTRAIT_SCALED_DRAW_VA:X}          # stock head; cleans only duplicate args
            mov eax, dword ptr [0x{PORTRAIT_DLL_FN_VA:X}]
            cmp eax, 1                                  # cached missing DLL/export sentinel
            je pwrap_done
            test eax, eax
            jnz pwrap_call
            push 0x{s['icons_dll']:X}
            call dword ptr [0x457010]                   # LoadLibraryA
            test eax, eax
            jz pwrap_missing
            push 0x{s['draw_portrait_mask']:X}
            push eax
            call dword ptr [0x4570D4]                   # GetProcAddress
            test eax, eax
            jz pwrap_missing
            mov dword ptr [0x{PORTRAIT_DLL_FN_VA:X}], eax
        pwrap_call:
            lea edx, [esp + 8]                          # untouched original arg1..arg7
            push edx                                    # arg4: tuple
            push dword ptr [esp + 4]                    # arg3: exact renderer wrapper
            push edi                                    # arg2: record
            push esi                                    # arg1: gameobj
            call eax                                    # Vv1DrawPortraitMask @16
            jmp pwrap_done
        pwrap_missing:
            mov dword ptr [0x{PORTRAIT_DLL_FN_VA:X}], 1 # permanent fail-open sentinel
        pwrap_done:
            add esp, 4                                  # discard saved renderer wrapper
            ret 0x1c                                    # stock 0x409410 ABI
        """,
        portrait_wrapper_va,
    )
    if len(portrait_wrapper) > 0x100:
        raise RuntimeError(
            f"VV1 portrait exact-argument wrapper exceeds its .vv1mc reservation: "
            f"{len(portrait_wrapper):#x} > 0x100"
        )
    patch(
        PORTRAIT_MASK_CAVE_FILE_OFFSET,
        b"\0" * len(portrait_wrapper),
        portrait_wrapper,
        "Details-screen portrait exact-argument wrapper: duplicate and replay the stock seven-argument head draw, then call Vv1DrawPortraitMask(gameobj, record, renderer, args) with the untouched native x/y/facing/scale/flag tuple; shared by all four portrait head calls.",
    )
    # Keep all four stock call sites ABI-identical: each still performs a call
    # and receives a callee-cleaned seven-argument return, only the destination
    # changes from the raw engine thunk to the exact-argument wrapper above.
    for splice_va in PORTRAIT_HEAD_DRAW_SITES:
        orig_call = assemble(f"call 0x{PORTRAIT_SCALED_DRAW_VA:X}", splice_va)
        detour = assemble(f"call 0x{portrait_wrapper_va:X}", splice_va)
        patch(
            splice_va - IMAGE_BASE,
            orig_call,
            detour,
            f"route sub_437340 portrait head-draw call at {splice_va:#x} through the shared exact-argument mask wrapper (one of the four age x atlas-flag quadrants)",
        )

    # === Village all-pose mask, Stage 1: per-villager identity stash =========
    # Each of the two village villager-render loops has a per-villager top where
    # the villager's record index is loaded into eax. Reproduce that load, stash
    # the index to VILLAGE_CUR_IDX_VA, and re-enter stock at the NATURAL resume
    # (splice + full replaced-instruction length) so the reentry audit treats it
    # as a plain resume, not a foreign re-entry. Inert until the Stage-2 hook
    # reads the slot; on its own it only writes patch-owned .data.
    _vfile = VILLAGE_MASK_CAVE_FILE
    _vva = VILLAGE_MASK_CAVE_VA
    # loop 1: sub_437790 @0x437798 (esi=gameobj, edi=loop counter live). Replaces
    # the 7-byte index load; resumes at the imul (0x43779F = splice+7).
    stash1 = assemble(
        f"""
            mov eax, dword ptr [esi + edi*4 + 0x3dbdc]
            mov dword ptr [0x{VILLAGE_CUR_IDX_VA:X}], eax
            jmp 0x43779F
        """,
        _vva,
    )
    patch(
        _vfile, b"\0" * len(stash1), stash1,
        "Village all-pose mask identity stash (loop 1): capture the current villager record index at sub_437790's per-villager top for the shared-draw hook",
    )
    patch(
        0x37798, bytes.fromhex("8b84bedcdb0300"),
        assemble(f"jmp 0x{_vva:X}\n nop\n nop", IMAGE_BASE + 0x37798),
        "splice sub_437790's per-villager top into the village-mask identity stash (loop 1)",
    )
    _vfile += len(stash1); _vva += len(stash1)
    # loop 2: second render loop @0x438900 (ebp = &villager-index element).
    # Replaces the 9-byte mov+imul; resumes after it (0x438909 = splice+9).
    stash2 = assemble(
        f"""
            mov eax, dword ptr [ebp]
            mov dword ptr [0x{VILLAGE_CUR_IDX_VA:X}], eax
            imul eax, eax, 0x3d8
            jmp 0x438909
        """,
        _vva,
    )
    patch(
        _vfile, b"\0" * len(stash2), stash2,
        "Village all-pose mask identity stash (loop 2): capture the current villager record index at the second render loop's per-villager top",
    )
    patch(
        0x38900, bytes.fromhex("8b450069c0d8030000"),
        assemble(f"jmp 0x{_vva:X}\n nop\n nop\n nop\n nop", IMAGE_BASE + 0x38900),
        "splice the second village render loop's per-villager top into the village-mask identity stash (loop 2)",
    )
    _vfile += len(stash2); _vva += len(stash2)

    # === Village all-pose mask, Stage 2: shared-draw hook ====================
    # Replaces the 0x409410 thunk (mov ecx,[ecx]; jmp 0x408af0). Every villager
    # head, in every pose, funnels through it. GATE: a valid per-villager stash
    # (only the village loops write it -> Details/UI self-exclude) AND arg1 is a
    # village head atlas ([gameobj+0x3dff8]/[0x3dff4]). When gated on a masked
    # villager: draw the head, then re-issue the mask atlas through the same
    # engine draw (0x408af0) with the head's OWN x/scale/facing (y lifted) -- so
    # the mask rides the head through walk/swim/bend/sit/lie for free. Otherwise
    # reproduce the stock thunk and pass through. Fail-open: any miss (bad stash,
    # non-head sprite, no mask, atlas not built) -> plain head draw, never crash.
    village_hook_va = _vva
    village_hook = assemble(
        f"""
            push ecx                              # save renderer (undereferenced)
            push eax                              # save fill arg
            push edx                              # scratch
            # [esp]=edx [+4]=fill [+8]=renderer [+0xc]=cret [+0x10]=arg1 ..[+0x28]=arg7
            # CALLER-ADDRESS GATE: only mask head draws issued by the VILLAGE render
            # code (sub_437790 .. loop-2 end ~0x4392CD). The Details portrait draw
            # (0x43741B, in sub_437340) and all UI/map head draws sit BELOW 0x437790,
            # so they're excluded -- otherwise the village hook also masked the
            # Details bighead (a small duplicate mask floating above the portrait)
            # and stray non-village heads (the "faded/duplicate mask" reports).
            mov edx, dword ptr [esp + 0xc]        # caller return address
            cmp edx, 0x437790
            jb vh_pass
            cmp edx, 0x4392D0
            ja vh_pass
            mov edx, dword ptr [0x{VILLAGE_CUR_IDX_VA:X}]
            cmp edx, 0x100
            jae vh_pass                           # invalid stash (incl -1)
            mov eax, dword ptr [0x{MASK_MANAGER_VA:X}]
            test eax, eax
            jz vh_pass                            # no gameobj yet
            mov edx, dword ptr [esp + 0x10]       # arg1 (sprite)
            cmp edx, dword ptr [eax + 0x3dff8]     # child head atlas (male_heads.png)
            je vh_head
            cmp edx, dword ptr [eax + 0x3dff4]     # child head atlas (female_heads.png)
            jne vh_pass
            # NOTE: 0x3dff0 and 0x3dfec are the male/female ACTION sheets (male_actions
            # /female_actions), NOT heads -- gating on them stamped masks onto action
            # sprites, which draw at body/ground level => the "mask flat on the floor,
            # only while performing an action (e.g. Exercising)" bug. Only 0x3dff8
            # (male_heads) and 0x3dff4 (female_heads) are real child heads. Bodies are
            # 0x3dfe8/0x3dfe4; adult head is gated separately in the shared body.
        vh_head:
            # NO clear-on-consume: the stash stays valid for the WHOLE villager
            # iteration (it's overwritten at the next loop top by stash1/stash2).
            # Clearing it after the first head draw meant a villager drawn a SECOND
            # time in the same iteration (e.g. SWIMMERS, whose head draws via the
            # 0x4093c0 site at 0x438150 AFTER an earlier 0x409410 head draw already
            # consumed the stash) saw an invalid stash and went unmasked. Each head
            # draw independently resolves the same villager's mask now.
            mov edx, dword ptr [0x{VILLAGE_CUR_IDX_VA:X}]        # villager index (kept valid)
            # AGE GATE: this is the CHILD render path (0x409410). Children (age<0x118)
            # mask here. Adults (age>=0x118) render+mask through the ADULT path
            # (0x4093c0) instead -- but a swimming adult ALSO gets a spurious child-path
            # draw here (the in-water reflection), which is the FADED DUPLICATE mask.
            # Skip adults so only their single adult-path mask remains. (Confirmed by
            # in-game capture: the 6 duplicated villagers were all adults drawn by both
            # paths; every child is single-path, every non-swim adult is adult-path only.)
            push eax
            push ecx
            mov eax, dword ptr [0x{MASK_MANAGER_VA:X}]           # gameobj (records base)
            imul ecx, edx, 0x3d8
            add ecx, eax
            cmp dword ptr [ecx + 0x348], 0x118                   # age
            pop ecx
            pop eax
            jae vh_pass                                          # adult -> the faded child-path dup, skip
            mov eax, edx
            shr eax, 1
            movzx eax, byte ptr [eax + 0x{MASK_TABLE_VA:X}]
            test dl, 1
            jz vh_lo
            shr eax, 4
            jmp vh_hm
        vh_lo:
            and eax, 0xf
        vh_hm:
            test eax, eax
            jz vh_pass                            # no mask on this villager
            cmp eax, 5
            ja vh_pass
            dec eax
            mov dword ptr [0x{VILLAGE_MASK_ROW_VA:X}], eax      # mask colour row
            mov eax, dword ptr [0x{VILLAGE_MASK_SPRITE_VA:X}]
            cmp eax, 1
            je vh_pass                            # atlas build previously failed
            test eax, eax
            jnz vh_draw
            # --- JIT build the mask atlas once, guarded (sentinel 1 = failed) ---
            mov eax, dword ptr [0x{VILLAGE_MASK_DLL_FN_VA:X}]
            test eax, eax
            jnz vh_callfn
            push 0x{s['icons_dll']:X}
            call dword ptr [0x457010]             # LoadLibraryA
            test eax, eax
            jz vh_setfail
            push 0x{s['get_mask_sprite']:X}
            push eax
            call dword ptr [0x4570D4]             # GetProcAddress
            test eax, eax
            jz vh_setfail
            mov dword ptr [0x{VILLAGE_MASK_DLL_FN_VA:X}], eax
        vh_callfn:
            call eax                              # Vv1GetMaskSprite() -> sprite
            test eax, eax
            jz vh_setfail
            mov dword ptr [0x{VILLAGE_MASK_SPRITE_VA:X}], eax
            jmp vh_draw
        vh_setfail:
            mov dword ptr [0x{VILLAGE_MASK_SPRITE_VA:X}], 1
            jmp vh_pass
        vh_pass:
            pop edx
            pop eax
            pop ecx
            mov ecx, dword ptr [ecx]              # stock thunk deref
            jmp 0x408af0
        vh_draw:
            mov ecx, dword ptr [esp + 8]          # renderer
            mov ecx, dword ptr [ecx]              # surface = [renderer]
            mov dword ptr [0x{VILLAGE_SURFACE_SAVE_VA:X}], ecx
            mov eax, dword ptr [esp + 4]          # fill arg
            mov dword ptr [0x{VILLAGE_FILL_SAVE_VA:X}], eax
            add esp, 0xc                          # drop the 3 saved regs
            # [esp]=cret [+4]=arg1 ..[+0x1c]=arg7
            # --- HEAD sub-draw: copy the 7 args, call the engine draw ---
            push dword ptr [esp + 0x1c]
            push dword ptr [esp + 0x1c]
            push dword ptr [esp + 0x1c]
            push dword ptr [esp + 0x1c]
            push dword ptr [esp + 0x1c]
            push dword ptr [esp + 0x1c]
            push dword ptr [esp + 0x1c]
            mov ecx, dword ptr [0x{VILLAGE_SURFACE_SAVE_VA:X}]
            mov eax, dword ptr [0x{VILLAGE_FILL_SAVE_VA:X}]
            call 0x408af0
            # --- MASK sub-draw: copy 7 args, swap sprite/row, lift y ---
            push dword ptr [esp + 0x1c]
            push dword ptr [esp + 0x1c]
            push dword ptr [esp + 0x1c]
            push dword ptr [esp + 0x1c]
            push dword ptr [esp + 0x1c]
            push dword ptr [esp + 0x1c]
            push dword ptr [esp + 0x1c]
            mov eax, dword ptr [0x{VILLAGE_MASK_SPRITE_VA:X}]
            mov dword ptr [esp], eax              # arg1 = mask atlas
            mov eax, dword ptr [0x{VILLAGE_MASK_ROW_VA:X}]
            mov dword ptr [esp + 0xc], eax        # arg4 = mask colour row
            # VV5 method = pass the head's own x/y/scale/facing straight through
            # (confirmed 1:1 by VV5). BUT VV5's caveat: zero-offset only seats on
            # VV5 because its head cell IS 65x145 = the mask cell. VV1's head cell
            # is 40x65, so the 65x145 mask at VV1's head-cell corner drifts -- the
            # mask must be RE-SEATED to VV1's head-face. Measured (male/female_
            # heads.png 40x65 vs mask 65x145): VV1 head-face centre ~(21,12),
            # mask face ~(32,60) in-cell -> lift ~48*s, shift left ~12*s. s =
            # arg6*0.01, so lift=(arg6*15)>>5 (~0.47*scale), dx=arg6>>3 (0.125).
            mov eax, dword ptr [esp + 0x14]       # arg6 = head scale
            imul eax, eax, 15
            sar eax, 5
            sub dword ptr [esp + 8], eax          # arg3 = y - lift (re-seat to head-face)
            # NO X term: per-facing X is now BAKED into mask_atlas.png (each facing
            # column shifted so its mask-face-x == that facing's head-face-x), so the
            # mask seats horizontally by construction at every facing and any scale.
            mov ecx, dword ptr [0x{VILLAGE_SURFACE_SAVE_VA:X}]
            mov eax, dword ptr [0x{VILLAGE_FILL_SAVE_VA:X}]
            call 0x408af0
            ret 0x1c
        """,
        village_hook_va,
    )
    patch(
        _vfile, b"\0" * len(village_hook), village_hook,
        "Village all-pose mask Stage 2 hook (0x409410 thunk replacement): for a village head draw of a masked villager, draw the head then re-issue the mask atlas via the engine draw at the head's own x/scale/facing (y lifted) so the mask follows every pose; all other draws pass through unchanged (fail-open)",
    )
    _vfile += len(village_hook); _vva += len(village_hook)
    # splice the shared thunk 0x409410 -> the village hook (replaces the first 5
    # of its 7 bytes; the hook reproduces the mov ecx,[ecx] deref for pass-through)
    patch(
        0x9410, bytes.fromhex("8b09e9d9f6"),
        assemble(f"jmp 0x{village_hook_va:X}", 0x409410),
        "splice the shared scaled-draw thunk 0x409410 into the village all-pose mask hook",
    )

    # === ADULT hook: the SECOND villager render path ========================
    # VV1 renders by age (cmp [rec+0x348],0x118): CHILDREN (age<0x118) go through
    # 0x409410->0x408af0 (handled above); ADULTS (age>=0x118) go through a SEPARATE
    # thunk 0x4093e0 -> 0x408840 with head atlas [gameobj+0x3e008] (4 cols x 1 row,
    # 65x65). The child hook can't see them, so adults render head-without-mask
    # ("ghosts"). This mirror hook covers the adult thunk. 0x408840 takes 5 args
    # (ret 0x14): arg1=sprite, arg2=x, arg3=y, arg4=facing(linear frame, idiv'd
    # to row/col inside), arg5=scale(0.4f). For the mask we set arg1=mask sprite
    # and arg4 = maskrow*mask_cols(8) + facing (row-major pack the engine decodes),
    # leaving x/y/scale identical so the mask rides the adult head. Shared stash +
    # mask table + cached sprite with the child hook. (VV5-decoded, confirmed 1:1.)
    adult_hook_va = _vva
    adult_hook = assemble(
        f"""
            push ecx
            push eax
            push edx
            # [esp]=edx [+4]=fill [+8]=renderer [+0xc]=cret [+0x10]=arg1 [+0x14]=arg2 [+0x18]=arg3 [+0x1c]=arg4 [+0x20]=arg5
            # CALLER-ADDRESS GATE (see village_hook): only mask VILLAGE-render head
            # draws. The adult thunk 0x4093e0 has 47 call sites in 4 clusters; only
            # the one at ~0x43808A is the village adult draw -- the 0x40C/0x41A/0x433B
            # clusters are UI/map/portrait and must NOT be masked. Range excludes them
            # and the Details bighead too.
            mov edx, dword ptr [esp + 0xc]        # caller return address
            cmp edx, 0x437790
            jb ah_pass
            cmp edx, 0x4392D0
            ja ah_pass
            # Exclude the FADED duplicate: 8 swimming adults are drawn twice -- the opaque
            # mask via 0x438150 (0x4093c0) and a faded second draw via the adult thunk
            # 0x4093e0 at 0x43808A (return 0x43808F). In-game capture proved 0x43808A is
            # used by ONLY those 8 (their faded draw); excluding it kills the faded mask
            # while the 0x438150 opaque mask remains. (Confirmed: excluding 0x438150
            # instead left only the faded one -- so 0x43808A is the faded draw.)
            cmp edx, 0x43808F
            je ah_pass
            mov edx, dword ptr [0x{VILLAGE_CUR_IDX_VA:X}]
            cmp edx, 0x100
            jae ah_pass
            mov eax, dword ptr [0x{MASK_MANAGER_VA:X}]
            test eax, eax
            jz ah_pass
            mov edx, dword ptr [esp + 0x10]       # arg1 (sprite)
            cmp edx, dword ptr [eax + 0x3e008]    # adult head atlas (via 0x4093e0)
            je ah_head
            cmp edx, dword ptr [eax + 0x3dff8]    # child head atlas male_heads (via 0x4093c0)
            je ah_head
            cmp edx, dword ptr [eax + 0x3dff4]    # child head atlas female_heads
            jne ah_pass
            # 0x3dff0/0x3dfec are the male/female ACTION sheets, NOT heads -- excluded
            # (see village_hook note): masking them stamped masks onto ground-level
            # action sprites (the "mask on the floor while Exercising" bug).
        ah_head:
            # NO clear-on-consume (see village_hook): keep the stash valid for the
            # whole iteration so swimmers (2nd head draw via 0x4093c0/0x408740) mask.
            mov edx, dword ptr [0x{VILLAGE_CUR_IDX_VA:X}]
            mov eax, edx
            shr eax, 1
            movzx eax, byte ptr [eax + 0x{MASK_TABLE_VA:X}]
            test dl, 1
            jz ah_lo
            shr eax, 4
            jmp ah_hm
        ah_lo:
            and eax, 0xf
        ah_hm:
            test eax, eax
            jz ah_pass
            cmp eax, 5
            ja ah_pass
            dec eax
            mov dword ptr [0x{VILLAGE_MASK_ROW_VA:X}], eax
            mov eax, dword ptr [0x{VILLAGE_MASK_SPRITE_VA:X}]
            cmp eax, 1
            je ah_pass
            test eax, eax
            jnz ah_draw
            mov eax, dword ptr [0x{VILLAGE_MASK_DLL_FN_VA:X}]
            test eax, eax
            jnz ah_callfn
            push 0x{s['icons_dll']:X}
            call dword ptr [0x457010]
            test eax, eax
            jz ah_setfail
            push 0x{s['get_mask_sprite']:X}
            push eax
            call dword ptr [0x4570D4]
            test eax, eax
            jz ah_setfail
            mov dword ptr [0x{VILLAGE_MASK_DLL_FN_VA:X}], eax
        ah_callfn:
            call eax
            test eax, eax
            jz ah_setfail
            mov dword ptr [0x{VILLAGE_MASK_SPRITE_VA:X}], eax
            jmp ah_draw
        ah_setfail:
            mov dword ptr [0x{VILLAGE_MASK_SPRITE_VA:X}], 1
            jmp ah_pass
        ah_pass:
            pop edx
            pop eax
            pop ecx
            mov ecx, dword ptr [ecx]
            jmp dword ptr [0x{VILLAGE_DRAWFN_VA:X}]
        ah_draw:
            mov ecx, dword ptr [esp + 8]
            mov ecx, dword ptr [ecx]
            mov dword ptr [0x{VILLAGE_SURFACE_SAVE_VA:X}], ecx
            mov eax, dword ptr [esp + 4]
            mov dword ptr [0x{VILLAGE_FILL_SAVE_VA:X}], eax
            add esp, 0xc
            # [esp]=cret [+4]=arg1 [+8]=arg2 [+0xc]=arg3 [+0x10]=arg4 [+0x14]=arg5
            push dword ptr [esp + 0x14]
            push dword ptr [esp + 0x14]
            push dword ptr [esp + 0x14]
            push dword ptr [esp + 0x14]
            push dword ptr [esp + 0x14]
            mov ecx, dword ptr [0x{VILLAGE_SURFACE_SAVE_VA:X}]
            mov eax, dword ptr [0x{VILLAGE_FILL_SAVE_VA:X}]
            call dword ptr [0x{VILLAGE_DRAWFN_VA:X}]
            push dword ptr [esp + 0x14]
            push dword ptr [esp + 0x14]
            push dword ptr [esp + 0x14]
            push dword ptr [esp + 0x14]
            push dword ptr [esp + 0x14]
            mov eax, dword ptr [0x{VILLAGE_MASK_SPRITE_VA:X}]
            mov dword ptr [esp], eax              # arg1 = mask atlas
            # SAME re-seat the child path does (mask face sits low in its 145-tall cell
            # ~(32,60); head face ~(20,12); delta (12,48) in-cell), but adults draw at a
            # FIXED scale (0x408740 has no scale arg), so a fixed lift is the correct
            # equivalent: (12,48)*adultScale. Shifts only the mask; it still tracks the
            # head's live x/y (that's the head's own draw position), just seated on the
            # face. Magnitude dialed to the adult on-screen scale.
            # NO X term: per-facing X is baked into mask_atlas.png (see child path), so
            # the mask seats horizontally at every facing with zero draw-time X.
            sub dword ptr [esp + 8], 48           # arg3=y: up 48 (= child scaled-lift at scale 1.0; owner in-game confirmed). Per-color Y also baked into the atlas, so one constant serves all colors.
            # Frame selection differs by DRAW FN behaviour, not by thunk:
            #  * 0x408840 (adult) idiv-DECODES a packed frame into row,col, so we
            #    re-PACK: arg4 = maskrow*mask_cols(8) + facing. (Adult atlas is
            #    4col x 1row so its arg4 is already the bare facing 0..3, hence no
            #    %HEAD_COLS needed here -- confirmed working.)
            #  * 0x408740 (swim/alt child) takes arg4,arg5 as SEPARATE row,col
            #    indices (no idiv -- it hands them straight to 0x409f90 against the
            #    sprite's own cols/rows). So we override ONLY the row (arg4:=mask
            #    colour) and leave arg5 (the head's real facing column) verbatim.
            #    Re-packing it -- what the merged body used to do to both -- shoved
            #    maskrow*8+arg4 into a raw row index and marched the mask through
            #    unrelated cells (the "changes sprite independently" misalignment).
            mov ecx, dword ptr [0x{VILLAGE_DRAWFN_VA:X}]
            cmp ecx, 0x408740
            je msk_sep
            mov eax, dword ptr [0x{VILLAGE_MASK_ROW_VA:X}]
            shl eax, 3                            # maskrow * mask_cols(8)
            add eax, dword ptr [esp + 0xc]        # + facing (original packed arg4)
            mov dword ptr [esp + 0xc], eax        # arg4 = row*8 + facing
            jmp msk_go
        msk_sep:
            mov eax, dword ptr [0x{VILLAGE_MASK_ROW_VA:X}]
            mov dword ptr [esp + 0xc], eax        # arg4 = mask colour ROW; arg5 (facing col) left verbatim
        msk_go:
            mov ecx, dword ptr [0x{VILLAGE_SURFACE_SAVE_VA:X}]
            mov eax, dword ptr [0x{VILLAGE_FILL_SAVE_VA:X}]
            call dword ptr [0x{VILLAGE_DRAWFN_VA:X}]
            ret 0x14
        """,
        adult_hook_va,
    )
    # This body is SHARED by BOTH 5-arg thunks (0x4093e0 adult, 0x4093c0 child-
    # alt/swim). They differ only in the original draw fn (0x408840 vs 0x408740)
    # and which head atlas matches -- and the atlas correlates with the thunk, so
    # gating on all five (adult 0x3e008 + child 0x3dff8/f4/f0/ec) is safe. The
    # draw fn is chosen per-thunk by a 15-byte entry stub that stores it into
    # VILLAGE_DRAWFN_VA before jumping here; the body then draws head + mask via
    # `call [DRAWFN]` and passes through via `jmp [DRAWFN]`. One 346-byte body
    # instead of two -- the duplicate 0x408740 mirror didn't fit anywhere.
    shared_body_va = adult_hook_va
    patch(
        _vfile, b"\0" * len(adult_hook), adult_hook,
        "Village all-pose mask SHARED 5-arg hook body (serves both the adult thunk 0x4093e0->0x408840 and the alternate child/swim thunk 0x4093c0->0x408740): adults (age>=0x118, atlas 0x3e008) and children in the alternate 5-arg pose (swim/sit, atlases 0x3dff8/f4/f0/ec) both render head-without-mask otherwise. Reissues the mask through the per-thunk original draw fn (VILLAGE_DRAWFN_VA) with arg1=mask sprite and arg4=maskrow*8+facing at the head's own x/y/scale.",
    )
    _vfile += len(adult_hook); _vva += len(adult_hook)

    # Two tiny per-thunk entry stubs in the draw-hook gap tail (0x8B0A0): each
    # records its thunk's original draw fn, then jumps the shared body.
    adult_entry_va = THIRD_HOOK_VA
    adult_entry = assemble(
        f"""
            mov dword ptr [0x{VILLAGE_DRAWFN_VA:X}], 0x408840
            jmp 0x{shared_body_va:X}
        """,
        adult_entry_va,
    )
    child_entry_va = THIRD_HOOK_VA + len(adult_entry)
    child_entry = assemble(
        f"""
            mov dword ptr [0x{VILLAGE_DRAWFN_VA:X}], 0x408740
            jmp 0x{shared_body_va:X}
        """,
        child_entry_va,
    )
    entry_blob = adult_entry + child_entry
    assert THIRD_HOOK_FILE_OFFSET + len(entry_blob) <= MASK_RESTORE_STUB_FILE_OFFSET, (
        f"mask entry stubs ({len(entry_blob)} bytes) overflow their .vv1mc slot "
        f"(0x{THIRD_HOOK_FILE_OFFSET:X}..0x{MASK_RESTORE_STUB_FILE_OFFSET:X})"
    )
    patch(
        THIRD_HOOK_FILE_OFFSET, b"\0" * len(entry_blob), entry_blob,
        "Village all-pose mask per-thunk entry stubs (draw-hook gap tail 0x8B0A0): stub A stores the adult draw fn 0x408840, stub B the child-alt draw fn 0x408740, then both jmp the shared 5-arg mask body. Lets one body serve both thunks; the sequential village-cave region has no room for a second 346-byte copy.",
    )
    patch(
        0x93E0, assemble("mov ecx, dword ptr [ecx]\n jmp 0x408840", 0x4093E0)[:5],
        assemble(f"jmp 0x{adult_entry_va:X}", 0x4093E0),
        "splice the adult scaled-draw thunk 0x4093e0 into its mask entry stub (-> shared 5-arg body, draw fn 0x408840)",
    )
    patch(
        0x93C0, assemble("mov ecx, dword ptr [ecx]\n jmp 0x408740", 0x4093C0)[:5],
        assemble(f"jmp 0x{child_entry_va:X}", 0x4093C0),
        "splice the alternate child/swim scaled-draw thunk 0x4093c0 into its mask entry stub (-> shared 5-arg body, draw fn 0x408740)",
    )

    assert _vfile <= MASK_OVERLAY_FILE_OFFSET, (
        f"village mask caves overflow their .vv1mc slot (end={_vfile:#x} > "
        f"MASK_OVERLAY 0x{MASK_OVERLAY_FILE_OFFSET:X})"
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
    save_slot_capture_detour_code = assemble(
        f"""
            jmp {SAVE_SLOT_CAPTURE_VA:#x}
        """,
        SAVE_SLOT_CAPTURE_SPLICE_VA,
    )
    patch(
        SAVE_SLOT_CAPTURE_SPLICE_FILE_OFFSET,
        bytes.fromhex("8B4424048B11"),
        save_slot_capture_detour_code + b"\x90",
        "splice the exact VV1 save builder at 0x402ED0 so both original argument-load instructions are guarded while its numbered slot argument is captured before the native save path formats %s%d.ldw",
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
        FORALL_HELPER_FILE_OFFSET,
        b"\0" * len(forall_helper_code),
        forall_helper_code,
        "resolve and invoke the icons DLL's Change Appearance for All export (tech-menu row 11), which owns its own afford check, conditional 450,000 charge and messaging",
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
        0x248,
        bytes.fromhex("186D0000"),
        bytes.fromhex("A06F0000"),
        "extend .data VirtualSize from 0x6D18 to 0x6FA0 so the loader commits "
        "the BSS bytes (0x48CD18..0x48CFA0) that hold all writable mask state -- "
        "the 128-byte table, surface cache, dest-surface cache, manager pointer, "
        "and the per-frame stash LIST (40 x 12 bytes) -- keeping runtime writes "
        "out of the executable .shr section (W^X); .data stays RW/non-executable. "
        "Deliberately 0x6FA0, NOT 0x7000: extending all the way to .shr's own "
        "start (0x48D000) makes .data's mapped range meet the next section's base "
        "and access-violates the process on launch (live-verified -- 0x7000 "
        "crashes, values below it run); 0x6FA0 leaves a 0x60 gap before .shr and "
        "covers the whole mask scratch region, which ends at 0x48CFA0",
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

    # ---- Append dedicated PE sections for the Heathen-mask feature -------------
    # Owner directive: mask code/data must NOT live in shared caves (the .shr
    # section is shared by Barrel/Cure/Equal-Division/Appearance -- squeezing the
    # mask into its gaps is what collided with CURE_ENTRY). Give the mask its own
    # two appended sections instead, W^X-clean (R-X code, R/W data, never RWX).
    # File+section alignment are both 0x1000 here, so this is straightforward.
    import struct as _st
    _lf = _st.unpack_from("<I", rendered, 0x3C)[0]
    _numsec_off = _lf + 6
    _numsec = _st.unpack_from("<H", rendered, _numsec_off)[0]
    _opt_off = _lf + 0x18
    _sizeofopt = _st.unpack_from("<H", rendered, _lf + 0x14)[0]
    _sectbl_off = _opt_off + _sizeofopt
    _sizeofimage_off = _opt_off + 0x38  # PE32 OPTIONAL_HEADER.SizeOfImage
    _sizeofimage = _st.unpack_from("<I", rendered, _sizeofimage_off)[0]
    _original_numsec_bytes = bytes(rendered[_numsec_off : _numsec_off + 2])
    _original_sizeofimage_bytes = bytes(
        rendered[_sizeofimage_off : _sizeofimage_off + 4]
    )
    _append_header_patches: list[dict[str, str]] = []

    def _append_section(name: bytes, va: int, chars: int) -> None:
        nonlocal _numsec, _sizeofimage
        rva = va - IMAGE_BASE
        raw_ptr = len(rendered)
        size = MASK_SECTION_SIZE
        hdr = (
            name.ljust(8, b"\x00")
            + _st.pack("<I", size)          # VirtualSize
            + _st.pack("<I", rva)           # VirtualAddress
            + _st.pack("<I", size)          # SizeOfRawData
            + _st.pack("<I", raw_ptr)       # PointerToRawData
            + _st.pack("<I", 0)             # PointerToRelocations
            + _st.pack("<I", 0)             # PointerToLinenumbers
            + _st.pack("<H", 0)             # NumberOfRelocations
            + _st.pack("<H", 0)             # NumberOfLinenumbers
            + _st.pack("<I", chars)         # Characteristics
        )
        assert len(hdr) == 0x28
        ent_off = _sectbl_off + _numsec * 0x28
        before = bytes(rendered[ent_off : ent_off + 0x28])
        rendered[ent_off : ent_off + 0x28] = hdr
        _append_header_patches.append(
            {
                "offset": f"0x{ent_off:X}",
                "before": before.hex().upper(),
                "after": hdr.hex().upper(),
                "purpose": f"install the guarded {name.rstrip(bytes([0])).decode('ascii')} section header",
            }
        )
        rendered.extend(b"\x00" * size)     # raw data (zero-filled)
        _numsec += 1
        _sizeofimage = rva + size           # image now ends at this section's end

    _append_section(b".vv1mc", MASK_CODE_SECTION_VA, 0x60000020)  # R-X, CODE
    _append_section(b".vv1md", MASK_DATA_SECTION_VA, 0xC0000040)  # R/W, INIT DATA
    _append_header_patches.insert(
        0,
        {
            "offset": f"0x{_numsec_off:X}",
            "before": _original_numsec_bytes.hex().upper(),
            "after": _st.pack("<H", _numsec).hex().upper(),
            "purpose": "add the owned .vv1mc and .vv1md sections",
        },
    )
    _append_header_patches.insert(
        1,
        {
            "offset": f"0x{_sizeofimage_off:X}",
            "before": _original_sizeofimage_bytes.hex().upper(),
            "after": _st.pack("<I", _sizeofimage).hex().upper(),
            "purpose": "extend SizeOfImage for the owned mask sections",
        },
    )
    _st.pack_into("<H", rendered, _numsec_off, _numsec)
    _st.pack_into("<I", rendered, _sizeofimage_off, _sizeofimage)

    # Apply all patches AFTER the append so mask-code patches (offsets in the
    # zero-filled .vv1mc raw range) land in the new section, not past EOF.
    for item in patches:
        offset = int(item["offset"], 16)
        payload = bytes.fromhex(item["after"])
        rendered[offset : offset + len(payload)] = payload

    OUT_EXE.write_bytes(rendered)
    rendered_json = json.dumps(patches, indent=2) + "\n"
    append_layout = {
        "original_file_size": f"0x{len(original):X}",
        "append_offset": f"0x{len(original):X}",
        "append_length": MASK_SECTION_SIZE * 2,
        "append_bytes": (b"\x00" * (MASK_SECTION_SIZE * 2)).hex().upper(),
        "virtual_address": f"0x{MASK_CODE_SECTION_VA:X}",
        "purpose": "append the owned .vv1mc R-X mask code and .vv1md R/W mask data sections",
        "header_patches": _append_header_patches,
    }
    manifest = {
        "id": "vv1_enable_origins_exclusive_features",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": "vv1",
        "running_preference_id": RUNNING_PREFERENCE_ID,
        "running_preference_evidence": {"source": "exact stock executable embedded preference table", "table_file_offset": "0x7B260", "entry_name": "running"},
        "name": "Enable Origins-Exclusive Features (includes the Heathen Mask mod)",
        "description": "Adds Origins-style Upgrades buttons to the Tech and Villager Details screens. The Tech menu offers Food and Tech Point Doublers for 500,000 tech points each; only scientist tech production and farmer food production are doubled, while Island Events, story/puzzle discoveries (Whale, berries, mushroom, device), one-time milestone-dialog rewards, Duplicate Collectibles, and Golden Child gains remain unchanged. The Village-Wide menu adds Running, Full Mastery, and Make Villagers Young Adults. This patch also contains the Heathen Mask mod: villagers can wear Heathen tribal masks, chosen per-villager via Change Appearance or across the whole village via Change Appearance for All, and rendered both on the Villager Details portrait and in the village view.",
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
        ] + [
            {
                # Portrait ("bighead") mask atlas: the DLL's Vv1DrawPortraitMask
                # builds an engine sprite from Images/mask_atlas.png, so it must
                # ship alongside the per-colour world sheets (m1-m5).
                "source": "assets/origins/mask_atlas.png",
                "destination": "Images/mask_atlas.png",
                "sha256": hashlib.sha256(
                    (ROOT / "assets" / "origins" / "mask_atlas.png").read_bytes()
                ).hexdigest().upper(),
            }
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
        "mask_persistence": {
            "details_mask_y_nudge_px": DETAILS_MASK_Y_NUDGE_PX,
            "details_mask_x_nudge_px": DETAILS_MASK_X_NUDGE_PX,
            "save_builder_entry": "0x402ED0",
            "save_builder_preimage": "8B4424048B11",
            "resume": "0x402ED6",
            "slot_scratch": "0x4911F4",
            "valid_slots": [1, 2, 3, 4, 5],
            "sidecar_pattern": "vv1_masks_<slot>.dat",
            "legacy_migration": False,
            "invalid_or_missing_sidecar": "clear in-memory table",
            "dead_entry_clears": "persisted back to the matching slot sidecar",
            "newborn_reuse_guard": "exact sub_43C350 allocation boundary at 0x43C393 clears the selected record-index nibble before normal/event newborn initialization continues; a patch-owned dirty flag makes Vv1MaskTick persist the clear to the active sidecar and retry on write failure",
            "pickup_held_runtime_status": "static: held villagers update the ordinary record position and re-enter the central village render loops; player-visible held mask behavior remains runtime-unverified",
        },
        "pe_append_transaction": {
            "owner": "vv1_enable_origins_exclusive_features",
            "section_name": ".vv1mc/.vv1md",
            "append_length": MASK_SECTION_SIZE * 2,
            "removal_policy": "restore guarded PE headers and truncate the exact two-page owned tail",
            "layouts": {
                "collection_progression": append_layout,
                "immediate_fixed": append_layout,
            },
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
