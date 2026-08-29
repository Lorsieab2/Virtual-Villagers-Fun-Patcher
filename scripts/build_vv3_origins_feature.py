"""Assemble the exact-build VV3 Origins-exclusive feature patch."""

from __future__ import annotations

import hashlib
import json
import struct
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STOCK = (
    ROOT
    / "research"
    / "stock-executables"
    / "Virtual Villagers - The Secret City.exe"
)
OUT_DIR = ROOT / "research" / "vv3-origins"
OUT_EXE = OUT_DIR / "Virtual Villagers - The Secret City - Origins Research.exe"
OUT_JSON = OUT_DIR / "vv3-origins-feature-patches.json"
MANIFEST_JSON = ROOT / "data" / "vv3_origins_feature.json"
COMPANION = ROOT / "data" / "candidates" / "VVFP VV3 Safe Upgrades.dll"
CANONICAL_COMPANION = ROOT / "data" / "candidates" / "VVFP VV3 Full Mastery Candidate.dll"

sys.path.insert(0, str(ROOT / ".tools" / "keystone"))
sys.path.insert(0, str(ROOT / ".tools" / "keystone-runtime"))
from keystone import KS_ARCH_X86, KS_MODE_32, Ks  # noqa: E402


IMAGE_BASE = 0x400000
PAYLOAD_FILE_OFFSET = 0xA3180
PAYLOAD_VA = IMAGE_BASE + PAYLOAD_FILE_OFFSET
PAYLOAD_SIZE = 0xE80
STRINGS_OFFSET = 0xC00
STRINGS_VA = PAYLOAD_VA + STRINGS_OFFSET
HEAL_CAVE_FILE_OFFSET = 0x7B664
HEAL_CAVE_VA = IMAGE_BASE + HEAL_CAVE_FILE_OFFSET
# Placed after the Cure/village-wide cave (HEAL_CAVE now runs to ~0x7B7F7 after
# the singular/plural Cure result), still in the free .text padding before the
# village-wide signature at 0x7B820.  The Island Event food/tech reward hooks
# jump here by NATIVE_*_TAIL_VA, so the move is self-consistent.
NATIVE_FOOD_TAIL_FILE_OFFSET = 0x7B800
NATIVE_FOOD_TAIL_VA = IMAGE_BASE + NATIVE_FOOD_TAIL_FILE_OFFSET
NATIVE_TECH_TAIL_FILE_OFFSET = 0x7B810
NATIVE_TECH_TAIL_VA = IMAGE_BASE + NATIVE_TECH_TAIL_FILE_OFFSET
VILLAGE_WIDE_SIGNATURE_VA = IMAGE_BASE + 0x7B820
VILLAGE_WIDE_ENTRY_VA = IMAGE_BASE + 0x7B840
# Keep the village-wide dependency check inside the owned A3180 payload.  The
# legacy Cure reserve begins at 0x7B664 and is now large enough for the native
# health-setter transaction, so the old 0x7B7A0 zero cave is no longer safe.
VILLAGE_PREFLIGHT_FILE_OFFSET = PAYLOAD_FILE_OFFSET + 0xB80
VILLAGE_PREFLIGHT_VA = IMAGE_BASE + VILLAGE_PREFLIGHT_FILE_OFFSET
# Change Appearance action cave: 704 bytes of zero .text padding that begin
# immediately after the optional village-wide payload (0x7B820..0x7BD40).
CHANGE_APPEARANCE_FILE_OFFSET = 0x7BD40
CHANGE_APPEARANCE_VA = IMAGE_BASE + CHANGE_APPEARANCE_FILE_OFFSET

# ---- Appended PE sections for the mask feature (docs/head-mask-rendering.md Part 7) ----
# The mask trampolines and the DLL fn-pointer slots used to live in BORROWED GAPS: the
# trampolines in the .text tail slack (.text VirtualSize ends at 0x47B254, so 0x47B260+ sat in
# the unmapped-by-vsize remainder of the raw section) and the slots in the .data slack (.data
# VirtualSize ends at 0x6C7518, so 0x6C7A00+ sat past it).  Both are code caves: two patches
# wanting the same gap silently corrupt each other.  Part 7 requires appending our OWN sections
# instead, W^X-separated -- one R-X for code, one R/W for data, never R/W/X.
#
# Geometry (stock VV3, verified): file size 0xCB000, SectionAlignment/FileAlignment 0x1000,
# 5 sections ending at VA 0x6DED40 / raw 0xCB000, SizeOfImage 0x2DF000.  The section table
# starts at 0x200 with the next free 40-byte header slot at 0x2C8, and the first raw data is at
# 0x1000, so there is room for two more headers.  Appending at the stock EOF also satisfies the
# patcher's pe_append_transaction rule that append_offset == original_file_size.
#
# Co-selection is impossible with the only other VV3 append (.vv3tw, expanded Time Warp): its
# layouts exist only for the experimental_expanded_256* modes, and builds.json's selectable
# patch_mode ids are exactly stock / collection_progression / immediate_fixed.  So this append
# can own the stock EOF with no offset coupling.
SECTION_CODE_NAME = b".vv3mc"             # R-X: mask trampolines
SECTION_CODE_VA = 0x006DF000
SECTION_CODE_RAW = 0x000CB000             # == stock file size
SECTION_CODE_SIZE = 0x1000
SECTION_CODE_CHARS = 0x60000020           # CODE | EXECUTE | READ   (no WRITE: W^X)
SECTION_DATA_NAME = b".vv3md"             # R/W: DLL fn-pointer slots + flags + active save
SECTION_DATA_VA = 0x006E0000
SECTION_DATA_RAW = 0x000CC000
SECTION_DATA_SIZE = 0x1000
SECTION_DATA_CHARS = 0xC0000040           # INITIALIZED_DATA | READ | WRITE (no EXECUTE)
PE_NUMSECTIONS_OFF = 0x10E                # e_lfanew(0x108) + 6
PE_SIZEOFIMAGE_OFF = 0x158                # e_lfanew + 24 + 56
PE_NEW_SECHDR_OFF = 0x2C8                 # first free section-header slot
NEW_SIZE_OF_IMAGE = 0x2E1000              # through both appended sections

# The stock save-builder starts with these two instructions.  The mask sidecar
# must follow the save currently being written, not one process-global file, so
# the exact entry is detoured to a small .vv3mc trampoline.  The trampoline
# preserves both stock instructions and records [esp+4] in the patch-owned
# .vv3md word consumed by the companion DLL.
SAVE_SLOT_CAPTURE_FN = 0x00403290
SAVE_SLOT_CAPTURE_LEN = 6
SAVE_SLOT_CAPTURE_CAVE_VA = SECTION_CODE_VA + 0x100
SAVE_SLOT_CAPTURE_RETURN_VA = SAVE_SLOT_CAPTURE_FN + SAVE_SLOT_CAPTURE_LEN
SAVE_SLOT_CAPTURE_BEFORE = bytes.fromhex("8B4424048B11")
SAVE_SLOT_PTR = SECTION_DATA_VA + 0x44
# The companion publishes this one-argument boundary function in .vv3md.  The
# detail and village-wide Running writers call it before/after their exact
# preference mutations so the existing raw-preference identity can be refreshed
# without weakening slot-reuse or slot-shift protection.
RUNNING_BOUNDARYFN_PTR = SECTION_DATA_VA + 0x48
RUNNING_BOUNDARY_BEFORE_CAVE_VA = SECTION_CODE_VA + 0x180
RUNNING_BOUNDARY_AFTER_CAVE_VA = SECTION_CODE_VA + 0x1C0
RUNNING_VILLAGE_WRAPPER_CAVE_VA = SECTION_CODE_VA + 0x220


# Heathen-mask render cave (DLL-draw method).  The .text/.rdata cave padding is
# fully reserved by the composed fun-patches, so the cave lives INSIDE the always-
# present Origins payload, in the free gap between detail_menu (ends +0xAD4) and
# village_preflight (+0xB80) -- emitted with put(), whose occupied-check guards a
# payload-layout collision.  The cave draws the villager head normally, then calls
# the companion DLL's VV3DrawMaskOnHead(record, sprite_obj, &args) once.  The DLL
# owns everything mask-related -- the fingerprint-guarded mask table (the record
# byte +0xED0 could NOT be used: the sim zeroes it every frame), the dedicated
# atlas Images/heathen_masks.png loaded via the game's own loader, the (mask-1)
# row, and the tunable y-lift -- and draws the mask cell ON TOP via the game's draw
# fn.  Keeping the draw in the DLL keeps this cave tiny (no atlas/lift asm) and all
# the mask logic in readable, tunable C.  A missing DLL/export/atlas degrades to
# "no mask", never a crash.  Writes NO villager state.  NOTE: this call site only
# covers the villager head-draw paths that route through 0x456B24; if some
# villagers don't render, switch the hook to the child draw thunk 0x409FB0.
MASK_CAVE_VA = PAYLOAD_VA + 0xAD8
MASK_HOOK_VA = 0x456B24
MASK_HOOK_LEN = 0x456B2F - 0x456B24  # 11 bytes replaced (head-draw call site)
MASK_DRAW_FN = 0x409FB0
MASK_SPRITE_OBJ_OFF = 0x1F7C
# Cached pointer to the companion DLL's VV3DrawMaskOnHead export.  Lives in the
# mapped, zero-filled, writable, otherwise-unreferenced page tail of .data
# (VirtualSize ends 0x6C7518; the page rounds up to 0x6C8000), so .text/.rdata
# stay read-only and nothing else uses it.  The mask store, atlas load, and the
# tunable lift all live in the DLL now, so the exe cave just draws the head and
# calls this once -- keeping the cave tiny and the mask logic in readable C.
MASK_DRAWFN_PTR = SECTION_DATA_VA + 0x00

# ---- Village / world Heathen-mask hook (INTERCEPT the head draw) ----
# VV3's village view is a DEFERRED command-queue renderer; the per-villager handler
# sub_4605F0 draws the head via `sub_42E570(mgr, headSprite, x, y, scale, flag)` at
# the SOLE call site 0x460A60.  Rather than reconstruct the villager draw (fragile:
# anchor/scale/facing all differ), we REDIRECT that head-draw call to a cave that
# (1) re-issues the identical head draw, then (2) calls the DLL's
# VV3WorldMaskDrawAt(record, &args), which draws the mask ON TOP through the SAME
# manager 0x58F6F8 at the head's EXACT x/y/scale (so position + scale + alpha come
# free).  At 0x460A60 esi = the villager record and the 5 head-draw args are on the
# stack; the cave passes both.  DLL publishes its ptr to WORLD_DRAWFN_PTR in DllMain
# (no per-frame LoadLibrary).  A null ptr / mask=0 / no atlas just draws the plain
# head (never a crash); writes NO villager state.
WORLD_MASK_CAVE_VA = PAYLOAD_VA + 0xB48   # free gap after MASK_CAVE, before preflight
WORLD_MASK_CALLSITE_VA = 0x460A60         # sub_4605F0's sole `call sub_42E570` (head)
WORLD_HEAD_DRAW_VA = 0x42E570             # the head draw we re-issue then STASH
WORLD_DRAWFN_PTR = SECTION_DATA_VA + 0x04               # DLL publishes VV3WorldMaskDrawAt (stash) here
# Z-ORDER FIX: the mask must draw AFTER the front-hair (sub_42E4B0), else the hair paints
# over it (owner's "behind the head/hair" symptom).  The hair call @0x460A89 is GUARDED by
# record+0xF11 (has-hair): bald villagers `je 0x460A8E`, so detouring the hair call alone
# would drop their masks.  0x460A8E is the CONVERGENCE both paths reach (post-hair for
# haired, hair-skipped for bald) -> the one universal, per-villager last-layer spot.
# Z-ORDER (final): WRAP the per-villager handler's CALL SITE instead of hooking inside it.
# sub_4605F0 (the case-8 villager handler) draws head->hair->overlays->action->props; any
# in-function hook draws too early (covered by later layers) AND risks stealing a jump
# target (0x460A8E stole 0x460A92, branched from 0x4609D8/0x4609E6 -> children/special
# villagers corrupted).  Its SOLE call site 0x42E3F5 (`call 0x4605F0`, a 5-byte E8 that is
# never a branch target -- verified 0 xrefs into its bytes) is the clean wrap point: run
# the whole handler, THEN draw the mask = guaranteed LAST layer, correct inter-villager
# z-order, no stolen bytes.  Handler is `ret 4` (1 arg = villager INDEX; record = base +
# index*0x1F8C).  The head-site cave still STASHES the exact head x/y/scale during the
# handler; the wrapper then draws from that stash on top.
WORLD_MASK_WRAPPER_CAVE_VA = SECTION_CODE_VA + 0x000   # appended R-X section
WORLD_HANDLER_CALLSITE_VA = 0x0042E3F5    # sole `call 0x4605F0` in the world dispatch
WORLD_HANDLER_FN = 0x004605F0             # the per-villager handler we wrap (ret 4)
WORLD_INDEXFN_PTR = SECTION_DATA_VA + 0x08              # DLL publishes VV3WorldMaskDraw here
# The stock calls at 0x434357 and 0x4344B3 are deliberately not patch points.  Exact
# disassembly identifies both as draws inside one three-style timed UI/effect object: the
# selector is 0..2, entries are 24 bytes, and elapsed time is compared with 0x12C/0x7080.
# No villager record or held/cursor identity reaches either call.  Keep the bytes stock until
# a player trace proves the separate grab and held-render boundaries.
# ACTION-POSE mask: VV3 draws sit/lie/swim/fish/work as a FULL-BODY sprite (head baked in) via
# the action overlay sub_45F7E0, so the base head-draw stash misses the pose head (owner's
# "fishing villager's mask at the hip").  Wrap the overlay's call site 0x460B48 (inside the
# per-villager handler): re-push its 3 args (record=esi, x, y), run the original overlay, then
# call VV3ActionMaskDraw(record, x, y) to seat the mask on the pose sprite's head.  sub_45F7E0
# is `ret 0xc` (3 args), ecx=this (preserved from before the stolen call); the wrap's `ret 0xc`
# keeps the net stack effect identical.
WORLD_ACTION_CALLSITE_VA = 0x00460B48     # `call 0x45F7E0` in sub_4605F0 (action overlay)
WORLD_ACTION_FN = 0x0045F7E0              # the action-overlay draw (ret 0xc; arg1=record)
WORLD_ACTION_WRAP_CAVE_VA = SECTION_CODE_VA + 0x0C0 # appended R-X section
WORLD_ACTIONFN_PTR = SECTION_DATA_VA + 0x30             # DLL publishes VV3ActionMaskDraw here

# Complete/Reset all Collections action caves live in a free executable-.rdata
# padding run at 0x9EE99..0x9EFA2 (the 0x24C section patch marks all of .rdata
# executable).  The crowded .text tail (0x7B254..0x7B664) is fully consumed by
# the other composed VV3 fun-patches' caves, so this .rdata run -- verified free
# in both patch modes -- is used instead.  Each cave fills or clears the native
# collectible count array at 0x58F428+0x10 and broadcasts the goal events.
COLLECTIONS_COMPLETE_FILE_OFFSET = 0x9EEA0
COLLECTIONS_COMPLETE_VA = IMAGE_BASE + COLLECTIONS_COMPLETE_FILE_OFFSET
COLLECTIONS_RESET_FILE_OFFSET = 0x9EF30
COLLECTIONS_RESET_VA = IMAGE_BASE + COLLECTIONS_RESET_FILE_OFFSET

# Deferred barrel-event hook.  Firing the "Another One of Those Barrels" event
# synchronously from the (paused, modal) Tech menu flashes its popup and never
# spawns, so do_barrel instead sets a pending flag (the unused game byte
# 0x4B3C75) and this hook -- spliced into the island-event handler at 0x468727,
# which runs every frame during normal gameplay -- fires the full event once the
# menu has closed, so it reads and behaves like a real island event.
BARREL_HOOK_FILE_OFFSET = 0x7B3B1
BARREL_HOOK_VA = IMAGE_BASE + BARREL_HOOK_FILE_OFFSET
BARREL_PENDING_FLAG_VA = 0x4B3C75
BARREL_HANDLER_SPLICE_VA = 0x468727
# Barrel present routine (in the free .text padding just past the hook).  Drives
# the game's own island-event presenter, forced to the barrel, so the full
# "Another One of Those Barrels" popup shows and the native 3-child spawn runs on
# confirm -- exactly like the random event.  The event objects live in an array
# at 0x4B3C78 (indices 1..0x39, barrel at slot 0x39 = 0x4B3D5C); the presenter
# 0x419B30 (this = the manager from 0x419AC0, arg = the island scene) picks a
# random *eligible* slot and shows it via 0x4192F0.  We save the array, point
# every slot at the barrel object so any selection path resolves to it, invoke
# the native pair, then restore the array (the popup keeps a direct pointer to
# the barrel singleton, which we never move).
BARREL_PRESENT_FILE_OFFSET = 0x7B3E0
BARREL_PRESENT_VA = IMAGE_BASE + BARREL_PRESENT_FILE_OFFSET
BARREL_EVENT_ARRAY_VA = 0x4B3C78          # &event_objects[0]
BARREL_EVENT_SLOT1_VA = BARREL_EVENT_ARRAY_VA + 4   # &event_objects[1]
BARREL_EVENT_OBJECT_VA = 0x4B3D5C          # event_objects[0x39] = barrel singleton
BARREL_EVENT_SLOT_COUNT = 0x39             # slots 1..0x39 inclusive (57)
BARREL_SELECT_MANAGER_VA = 0x419AC0        # lazy manager getter (returns eax)
BARREL_PRESENT_EVENT_VA = 0x419B30         # present(this=mgr, scene); ret 4
# 0x419B30 records the presented event's index in the parallel "seen" byte array
# at 0x4B3C3C + index (0x4B3C3C..0x4B3C77 for indices 0..0x39).  Because we point
# every object slot at the barrel, its random pick marks some *other* index as
# seen, which would consume an unrelated one-shot island event.  So we save and
# restore that seen array around the present too -- one contiguous dword block
# from 0x4B3C3C up through the object slots -- undoing the spurious mark (and the
# barrel's own pending flag at 0x4B3C75, already cleared by the hook, rides along
# unchanged).  Restore starts at BARREL_SAVE_LOW_VA; save descends from the
# barrel singleton; BARREL_SAVE_COUNT dwords cover the seen array plus slots
# 1..0x39.
BARREL_SAVE_LOW_VA = 0x4B3C3C
BARREL_SAVE_COUNT = (BARREL_EVENT_OBJECT_VA - BARREL_SAVE_LOW_VA) // 4 + 1  # 0x49
# Barrel capacity preflight, in the payload block's free code tail (the whole
# .text padding is contended by other fun-patches, but this .rdata payload page
# is executable via the 0x24C section-flags patch).  It just LoadLibrary/
# GetProcAddress-probes the companion DLL and calls PrepareBarrelBabies, which
# does the mode-aware "can the village hold three more?" computation (reading the
# live per-mode base-population byte the patcher sets at 0x45FEE3).  Keeping the
# logic in the DLL avoids growing the nearly-full payload and stays correct
# across the patcher's population modes.  Returns eax != 0 when the barrel may
# fire; fails open (eax = 1) if the DLL cannot be probed.
BARREL_PREFLIGHT_DLL_VA = PAYLOAD_VA + 0xBB6
# Read-only strings for the cure and Change Appearance caves, placed in the
# free .text padding after the Change Appearance cave (0x7BD40) and before the
# .rdata boundary (0x7C000).
EXTRA_STRINGS_FILE_OFFSET = 0x7BDE0  # after the (grown) Change Appearance cave,
                                     # which now writes the mask byte +0xED0
                                     # (code=148B ends 0x7BDD4; strings=515B fit to 0x7C000)
EXTRA_STRINGS_VA = IMAGE_BASE + EXTRA_STRINGS_FILE_OFFSET
RUNNING_PREFERENCE_ID = 38  # exact-build preference-table evidence: 0x97488
DETAIL_BUTTON_PTR = PAYLOAD_VA + 0xBF0
DETAIL_BUTTON_ID = 6
# VV3's stock Tech handler receives message 8.  IDs through 14 are stock
# routes, so command 15 is the first free/custom button event for Origins.
# Keep these values named and shared by the constructor and handler so a
# future edit cannot silently make the visible control unreachable.
TECH_BUTTON_MESSAGE = 8
TECH_BUTTON_EVENT = 15


def assemble(source: str, address: int) -> bytes:
    encoding, _ = Ks(KS_ARCH_X86, KS_MODE_32).asm(source, address)
    return bytes(encoding)


def rel32_jump(source_va: int, target_va: int, size: int = 5) -> bytes:
    payload = b"\xE9" + int(target_va - source_va - 5).to_bytes(
        4, "little", signed=True
    )
    if size < 5:
        raise ValueError("relative jump requires at least five bytes")
    return payload + b"\x90" * (size - 5)


def add_c_string(blob: bytearray, labels: dict[str, int], name: str, value: str) -> None:
    labels[name] = STRINGS_VA + len(blob)
    blob.extend(value.encode("ascii") + b"\0")


def main() -> None:
    original = STOCK.read_bytes()
    expected_sha256 = (
        "8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503"
    )
    actual_sha256 = hashlib.sha256(original).hexdigest().upper()
    if actual_sha256 != expected_sha256:
        raise RuntimeError(
            f"stock SHA-256 mismatch: expected {expected_sha256}, got {actual_sha256}"
        )
    if not COMPANION.is_file():
        raise RuntimeError(f"missing companion DLL: {COMPANION}")
    if not CANONICAL_COMPANION.is_file():
        raise RuntimeError(f"missing canonical companion DLL: {CANONICAL_COMPANION}")
    if COMPANION.read_bytes() != CANONICAL_COMPANION.read_bytes():
        raise RuntimeError(
            "VV3 deployed companion is stale; rebuild the canonical Full Mastery "
            "DLL before building Origins"
        )
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    strings = bytearray()
    s: dict[str, int] = {}
    for name, value in (
        ("button_label", "Upgrades"),
        ("tech_title", "Origins Upgrades"),
        ("detail_title", "Villager Upgrades"),
        ("mastery_failed", "Full Mastery could not be completed."),
        ("not_enough", "Not enough tech points."),
        ("paused", "Time Warp is unavailable while the game is paused."),
        (
            "time_warp_done",
            "Time Warp completed.",
        ),
        (
            "youth_already",
            "This villager is already full of youth. "
            "No tech points have been deducted.",
        ),
        ("villager_one", "villager"),
        ("villager_many", "villagers"),
        ("icons_dll", "VVFP Origins Icons.dll"),
        ("show_dialog_export", "ShowOriginsUpgradeMenuState"),
        ("show_result_export", "ShowOriginsVillageWideResult"),
        ("prepare_export", "PrepareOriginsVillageWide"),
        ("prepare_barrel_export", "PrepareBarrelBabies"),
        ("result_export", "ShowOriginsUpgradeResult"),
        ("edl_export", "EqualDivisionOfLabor"),
        (
            "village_no_change",
            "No changes were needed. No tech points have been deducted.",
        ),
        ("user32_dll", "USER32.dll"),
        ("message_box_export", "MessageBoxA"),
        ("wsprintf_export", "wsprintfA"),
    ):
        add_c_string(strings, s, name, value)

    while len(strings) % 4:
        strings.append(0)
    s["tech_costs"] = STRINGS_VA + len(strings)
    for value in (50000, 30000, 75000, 500000, 500000, 30000):
        strings.extend(value.to_bytes(4, "little"))
    s["detail_costs"] = STRINGS_VA + len(strings)
    # Indices 0..4: Grant Youth, Grant Full Mastery, Grant Running, Set Age to
    # 18, Change Appearance.
    for value in (50000, 100000, 40000, 50000, 5000):
        strings.extend(value.to_bytes(4, "little"))
    if len(strings) > PAYLOAD_SIZE - STRINGS_OFFSET:
        raise RuntimeError(
            f"string/data block is too large: {len(strings):#x}/"
            f"{PAYLOAD_SIZE - STRINGS_OFFSET:#x}"
        )

    # Strings referenced only by the separate 0x7B664 cure cave and 0x7BD40
    # Change Appearance cave live in the free .text padding after the Change
    # Appearance cave, so the 0xA3180 payload string block stays within budget.
    extra_strings = bytearray()
    for name, value in (
        ("appearance_export", "ShowVV3AppearanceChooser"),
        ("drawmask_export", "VV3DrawMaskOnHead"),
        (
            "cure_message",
            "Cured sickness from %u %s.\n\n"
            "Restored %u %s to full health.",
        ),
        (
            "cure_nothing",
            "Everyone is at full health already. No villagers are sick. "
            "No tech points have been deducted.",
        ),
        (
            "collections_completed",
            "Marked all 48 collectibles as found and triggered 5 collection goals.",
        ),
        (
            "collections_reset",
            "Cleared all 48 collectibles.",
        ),
        ("detail_youth_done", "Grant Youth completed."),
        ("detail_mastery_done", "Grant Full Mastery completed."),
        ("detail_running_done", "Grant Running completed."),
        ("detail_age_done", "Set Age to 18 completed."),
        (
            "detail_mastery_already",
            "This villager is already fully mastered. "
            "No tech points have been deducted.",
        ),
        (
            "detail_age_already",
            "No changes were needed. "
            "No tech points have been deducted.",
        ),
    ):
        s[name] = EXTRA_STRINGS_VA + len(extra_strings)
        extra_strings.extend(value.encode("ascii") + b"\0")
    if len(extra_strings) > 0x7C000 - EXTRA_STRINGS_FILE_OFFSET:
        raise RuntimeError("extra .text string block overflows the free padding")

    tech_handler = PAYLOAD_VA + 0x000
    tech_constructor = PAYLOAD_VA + 0x040
    detail_handler = PAYLOAD_VA + 0x100
    detail_constructor = PAYLOAD_VA + 0x140
    show_dialog = PAYLOAD_VA + 0x220
    show_message = PAYLOAD_VA + 0x280
    get_detail_record = PAYLOAD_VA + 0x2E0
    tech_menu = PAYLOAD_VA + 0x340
    detail_menu = PAYLOAD_VA + 0x650
    tech_increment = PAYLOAD_VA + 0xA20
    food_increment = PAYLOAD_VA + 0xAA0

    code = bytearray(b"\0" * STRINGS_OFFSET)
    occupied = bytearray(b"\0" * STRINGS_OFFSET)

    def put(va: int, source: str) -> None:
        payload = assemble(source, va)
        start = va - PAYLOAD_VA
        end = start + len(payload)
        if start < 0 or end > len(code):
            raise RuntimeError(
                f"code at {va:#x} ({len(payload):#x} bytes) exceeds code block"
            )
        if any(occupied[start:end]):
            raise RuntimeError(f"code overlap at {va:#x}, size {len(payload):#x}")
        code[start:end] = payload
        occupied[start:end] = b"\1" * len(payload)

    put(
        tech_handler,
        f"""
            cmp dword ptr [esp + 4], {TECH_BUTTON_MESSAGE}
            jne original_handler
            cmp dword ptr [esp + 8], {TECH_BUTTON_EVENT}
            jne original_handler
            call 0x{tech_menu:X}
            xor eax, eax
            ret 8
        original_handler:
            push -1
            mov eax, dword ptr fs:[0]
            jmp 0x465648
        """,
    )

    put(
        tech_constructor,
        f"""
            push 0x14
            call 0x46EC93
            add esp, 4
            test eax, eax
            je constructor_done
            mov edi, eax
            call 0x42E9D0
            mov ecx, eax
            push 3
            call 0x42E8A0
            push 0
            push esi
            push 563
            push 138
            push eax
            push {TECH_BUTTON_EVENT}
            mov ecx, edi
            call 0x4019F0
            mov edi, eax
            push 0
            push 0xFF555555
            push 0xFF555555
            push 0xFF000000
            push 0x{s['button_label']:X}
            mov ecx, edi
            call 0x401620
            push edi
            mov ecx, esi
            call 0x40C1F0
        constructor_done:
            mov ecx, dword ptr [esp + 0x3C]
            pop edi
            mov eax, esi
            pop esi
            pop ebp
            pop ebx
            mov dword ptr fs:[0], ecx
            add esp, 0x38
            ret
        """,
    )

    put(
        detail_handler,
        f"""
            cmp dword ptr [esp + 4], 8
            jne original_handler
            cmp dword ptr [esp + 8], {DETAIL_BUTTON_ID}
            jne original_handler
            call 0x{detail_menu:X}
            xor eax, eax
            ret 8
        original_handler:
            mov eax, dword ptr [esp + 4]
            sub esp, 0x14
            jmp 0x46E537
        """,
    )

    put(
        detail_constructor,
        f"""
            push 0x14
            call 0x46EC93
            add esp, 4
            test eax, eax
            je no_button
            mov edi, eax
            call 0x42E9D0
            mov ecx, eax
            push 3
            call 0x42E8A0
            push 0
            push esi
            push 563
            push 138
            push eax
            push {DETAIL_BUTTON_ID}
            mov ecx, edi
            call 0x4019F0
            mov edi, eax
            mov dword ptr [0x{DETAIL_BUTTON_PTR:X}], edi
            push 0
            push 0xFF555555
            push 0xFF555555
            push 0xFF000000
            push 0x{s['button_label']:X}
            mov ecx, edi
            call 0x401620
            push edi
            mov ecx, esi
            call 0x40C1F0
            jmp constructor_done
        no_button:
            mov dword ptr [0x{DETAIL_BUTTON_PTR:X}], 0
        constructor_done:
            mov ecx, dword ptr [esp + 0x20]
            pop edi
            mov dword ptr [esi + 0x264], ebx
            mov dword ptr [esi + 0x268], ebx
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
        show_dialog,
        f"""
            push ebx
            push esi
            push 0x{s['icons_dll']:X}
            call dword ptr [0x47C124]
            test eax, eax
            je unavailable
            push 0x{s['show_dialog_export']:X}
            push eax
            call dword ptr [0x47C128]
            test eax, eax
            je unavailable
            cmp dword ptr [0x{VILLAGE_WIDE_SIGNATURE_VA:X}], 0x50465656
            jne no_village_wide
            # When the optional village-wide payload is installed, mark the
            # dialog VILLAGE_WIDE (0x20000).  The companion resolves that to
            # the nine-row Tech dialog (201) with row_count 9, so Cure (5),
            # All Villagers Like Running (6), Grant Full Mastery to All (7),
            # and All Villagers are 18 (8) all render as live Buy controls.
            # The former 0xA01C0 selected the eight-row Full-Mastery-only
            # dialog (203) -- which has no Running or Age-18 rows -- and set
            # the rows 6-8 "done" bits, so those upgrades were hidden or shown
            # greyed/disabled rather than purchasable.
            or dword ptr [esp + 0x10], 0x20000
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

    put(
        show_message,
        f"""
            push ebx
            push esi
            mov ebx, dword ptr [esp + 0x0C]
            mov esi, dword ptr [esp + 0x10]
            push 0x{s['user32_dll']:X}
            call dword ptr [0x47C124]
            test eax, eax
            je message_done
            push 0x{s['message_box_export']:X}
            push eax
            call dword ptr [0x47C128]
            test eax, eax
            je message_done
            push 0x50000
            push ebx
            push esi
            push 0
            call eax
        message_done:
            pop esi
            pop ebx
            ret 8
        """,
    )

    put(
        get_detail_record,
        """
            push ebx
            call 0x428B60
            xor ecx, ecx
            cmp dword ptr [0x42883A], 0x100
            jne selected_offset_ready
            mov ecx, 0x7598
        selected_offset_ready:
            mov ebx, dword ptr [eax + ecx + 0x12FC0]
            push ebx
            mov ecx, 0x59E110
            call 0x45EE60
            test al, al
            je invalid
            push ebx
            mov ecx, 0x59E110
            call 0x45C840
            pop ebx
            ret
        invalid:
            xor eax, eax
            pop ebx
            ret
        """,
    )

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
            test dword ptr [0x5824D0], 1
            jz tech_not_owned
            or eax, 8
        tech_not_owned:
            test dword ptr [0x5824D0], 2
            jz food_not_owned
            or eax, 16
        food_not_owned:
            # Tech/Food Doublers must be purchasable when unowned: show the
            # default "Buy" control (owned rows still resolve to "Remove" via
            # the eax bit-3/bit-4 done flags above).  The former
            # `or eax, 0x1800` set the row 3/4 "Unavailable" flags
            # unconditionally, which blocked both doublers from ever being
            # bought.
            push eax
            push 0
            call 0x{show_dialog:X}
            cmp eax, -1
            je menu_done
            mov ebx, eax

            cmp ebx, 9
            je do_complete_collections
            cmp ebx, 10
            je do_reset_collections
            cmp ebx, 11
            je do_equal_division_incl
            cmp ebx, 12
            je do_equal_division_no
            cmp ebx, 13
            je do_change_appearance_for_all

            cmp ebx, 3
            jb preflight
            cmp ebx, 5
            jae preflight
            cmp ebx, 4
            je maybe_remove_food
            test dword ptr [0x5824D0], 1
            jz preflight
            and dword ptr [0x5824D0], 0xFFFFFFFE
            mov eax, 4
            jmp show_result
        maybe_remove_food:
            test dword ptr [0x5824D0], 2
            jz preflight
            and dword ptr [0x5824D0], 0xFFFFFFFD
            mov eax, 5
            jmp show_result

        preflight:
            call 0x428B60
            mov edi, eax
            xor ebp, ebp
            cmp dword ptr [0x42883A], 0x100
            jne manager_offset_ready
            mov ebp, 0x7598
        manager_offset_ready:
            cmp ebx, 0
            jne maybe_barrel
            cmp dword ptr [edi + ebp + 0x12F20], 999
            jne charge
            mov eax, 0x{s['paused']:X}
            jmp show_status
        maybe_barrel:
            cmp ebx, 2
            jne charge
            # The barrel spawns three children, so refuse (nothing has been
            # charged yet) unless the village can hold all three under its real,
            # mode-aware maximum.  The DLL export PrepareBarrelBabies does the
            # computation (current + 3 <= max, reading the live per-mode base
            # population the patcher sets at 0x45FEE3); the cave just probes and
            # calls it, returning nonzero when the barrel may fire.
            call 0x{BARREL_PREFLIGHT_DLL_VA:X}
            test eax, eax
            jnz charge
            mov eax, 6
            jmp show_result

        charge:
            cmp ebx, 6
            jb legacy_charge
            cmp ebx, 8
            ja menu_loop
            call 0x{VILLAGE_PREFLIGHT_VA:X}
            test eax, eax
            jz menu_loop
            cmp dword ptr [0x582644], 1000000
            jb insufficient
            sub dword ptr [0x582644], 1000000
            jmp do_village_wide
        legacy_charge:
            mov eax, dword ptr [0x{s['tech_costs']:X} + ebx*4]
            cmp dword ptr [0x582644], eax
            jb insufficient
            sub dword ptr [0x582644], eax
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
            jmp menu_done

        do_cure:
            call 0x{HEAL_CAVE_VA:X}
            jmp menu_done

        do_village_wide:
            call 0x{HEAL_CAVE_VA:X}
            jmp menu_done

        do_time_warp:
            # Advance a constant three displayed villager years regardless of
            # the running game speed.  The village applies the injected clock
            # shift at a rate proportional to the current speed, so a constant
            # villager-time advance needs an elapsed-clock shift of
            # 129600 / speed seconds (two real hours per displayed year at
            # normal speed; 43,200s at half speed 3, 21,600s at normal 6,
            # 12,960s at double 10).  The former `imul speed, 3600` was
            # proportional -- correct only at normal speed, under-advancing at
            # half speed and over-advancing at double speed.  The pause guard
            # above already refused speed 999 before charging, and VV3 only
            # ever assigns speed codes 3/6/10, so the idiv cannot divide by
            # zero or overflow.
            mov ecx, dword ptr [edi + ebp + 0x12F20]
            mov eax, 129600
            cdq
            idiv ecx
            sub dword ptr [0x4A4210], eax
            mov eax, 0x{s['time_warp_done']:X}
            jmp show_status

        do_island_event:
            mov dword ptr [edi + ebp + 0x12EF4], 0
            mov eax, 1
            jmp show_result

        do_barrel:
            # Defer the "Another One of Those Barrels" island event.  Firing it
            # from this paused, modal menu flashes the popup and never spawns, so
            # just mark it pending; the island-event handler hook spliced at
            # 0x{BARREL_HANDLER_SPLICE_VA:X} fires the full event next frame once
            # the menu closes, so it reads and behaves like a real island event.
            # Confirm the purchase now with the "Barrel of Babies completed."
            # result box (the cued event itself follows a moment into gameplay).
            mov byte ptr [0x{BARREL_PENDING_FLAG_VA:X}], 1
            mov eax, 7
            jmp show_result

        do_complete_collections:
            # No-change guard: if every collectible id 52..99 is already found
            # (non-zero in the native count array at 0x58F438 + id*4), refuse
            # without charging and show result code 8.  Otherwise complete.
            mov ecx, 52
        cc_already_loop:
            cmp dword ptr [ecx*4 + 0x58F438], 0
            je do_complete_collections_go
            inc ecx
            cmp ecx, 100
            jl cc_already_loop
            mov eax, 8
            jmp show_result
        do_complete_collections_go:
            call 0x{COLLECTIONS_COMPLETE_VA:X}
            jmp menu_done

        do_reset_collections:
            # No-change guard: if every collectible id 52..99 is already cleared
            # (zero), refuse without charging and show result code 9.  Otherwise
            # reset.
            mov ecx, 52
        rc_already_loop:
            cmp dword ptr [ecx*4 + 0x58F438], 0
            jne do_reset_collections_go
            inc ecx
            cmp ecx, 100
            jl rc_already_loop
            mov eax, 9
            jmp show_result
        do_reset_collections_go:
            call 0x{COLLECTIONS_RESET_VA:X}
            jmp menu_done

        do_tech_doubler:
            or dword ptr [0x5824D0], 1
            mov eax, 2
            jmp show_result
        do_food_doubler:
            or dword ptr [0x5824D0], 2
            mov eax, 3
            jmp show_result
        insufficient:
            mov eax, 0x{s['not_enough']:X}
            jmp show_status
        show_status:
            push eax
            push 0x{s['tech_title']:X}
            call 0x{show_message:X}
            jmp menu_done
        show_result:
            # eax = result code; hand it to the DLL export ShowOriginsUpgradeResult,
            # which owns the exact OFFICIAL-sheet wording for the Tech one-shots and
            # the Barrel guard.  Fails silently (still closes the menu) if the DLL
            # or export cannot be resolved.
            push eax
            push 0x{s['icons_dll']:X}
            call dword ptr [0x47C124]
            test eax, eax
            je show_result_done
            push 0x{s['result_export']:X}
            push eax
            call dword ptr [0x47C128]
            test eax, eax
            je show_result_done
            push dword ptr [esp]
            call eax
        show_result_done:
            pop eax
            jmp menu_done
        do_equal_division_incl:
            push 1
            jmp do_equal_division
        do_equal_division_no:
            push 0
        do_equal_division:
            # ebx 11/12: the DLL export EqualDivisionOfLabor owns the whole
            # transaction (funds check, the 1,000,000 deduct from the tech pool
            # 0x582644, the round-robin +0xEC0 job-preference assignment, and the
            # OFFICIAL-sheet result box), so the near-full payload only routes the
            # already-confirmed button to it.  includeParenting = 1 (row 11) or 0
            # (row 12); fail-open (just close the menu) if the DLL/export is
            # unresolved, leaving the pushed argument to be discarded.
            push 0x{s['icons_dll']:X}
            call dword ptr [0x47C124]
            test eax, eax
            je do_equal_division_pop
            push 0x{s['edl_export']:X}
            push eax
            call dword ptr [0x47C128]
            test eax, eax
            je do_equal_division_pop
            call eax
            jmp menu_done
        do_equal_division_pop:
            add esp, 4
            jmp menu_done
        do_change_appearance_for_all:
            # ebx==13: the DLL export ShowVV3AppearanceForAll owns the whole
            # transaction -- the dialog, the 450,000 charge from the tech pool
            # 0x582644, applying head/body/mask to every villager, and the sidecar.
            # VV3's fixed record/tech addresses mean the export needs no argument.
            push 0x{s['icons_dll']:X}
            call dword ptr [0x47C124]
            test eax, eax
            je menu_done
            push 100
            push eax
            call dword ptr [0x47C128]
            test eax, eax
            je menu_done
            call eax
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
            call 0x{get_detail_record:X}
            test eax, eax
            je detail_done
            mov edx, eax
            xor edi, edi
            cmp dword ptr [edx + 0xDC4], 100
            ja youth_not_done
            or edi, 1
        youth_not_done:
            cmp dword ptr [edx + 0xEAC], 100
            jne mastery_not_done
            cmp dword ptr [edx + 0xEB0], 100
            jne mastery_not_done
            cmp dword ptr [edx + 0xEB4], 100
            jne mastery_not_done
            cmp dword ptr [edx + 0xEB8], 100
            jne mastery_not_done
            cmp dword ptr [edx + 0xEBC], 100
            jne mastery_not_done
            or edi, 2
        mastery_not_done:
            xor ebp, ebp
            lea eax, [edx + 0xFB4]
            mov ecx, 3
        running_like_scan:
            cmp dword ptr [eax], {RUNNING_PREFERENCE_ID}
            je running_like_found
            cmp dword ptr [eax], -1
            jne running_like_next
            or ebp, 1
        running_like_next:
            add eax, 4
            dec ecx
            jne running_like_scan
            test ebp, 1
            jnz running_state_done
            or edi, 0x400
            jmp running_state_done
        running_like_found:
            or ebp, 2
        running_state_done:
            lea eax, [edx + 0xFC0]
            mov ecx, 3
        running_dislike_scan:
            cmp dword ptr [eax], {RUNNING_PREFERENCE_ID}
            jne running_dislike_next
            or ebp, 4
        running_dislike_next:
            add eax, 4
            dec ecx
            jne running_dislike_scan
            test ebp, 2
            jz running_no_like
            # An existing Running Like is already complete.  Do not expose
            # a second purchase merely because a stale Running Dislike also
            # exists; the transaction is a no-op in that state.
            or edi, 4
            jmp running_check_done
        running_no_like:
            test ebp, 1
            jnz running_check_done
            or edi, 0x400
        running_check_done:
            cmp dword ptr [edx + 0xDC4], 360
            jne age_not_done
            or edi, 8
        age_not_done:
            push edi
            push 1
            call 0x{show_dialog:X}
            cmp eax, -1
            je detail_done
            mov ebx, eax

            call 0x{get_detail_record:X}
            test eax, eax
            je detail_done
            mov edx, eax
            cmp ebx, 2
            jne detail_charge
            lea eax, [edx + 0xFB4]
            mov ecx, 3
        running_preflight:
            cmp dword ptr [eax], {RUNNING_PREFERENCE_ID}
            je running_already
            cmp dword ptr [eax], -1
            je detail_charge
            add eax, 4
            dec ecx
            jne running_preflight
            # Likes are full and none is Running.  If the villager has a Running
            # dislike, clear it (free, no charge) and report case 2; otherwise it
            # is a true no-op (case 3).  Nothing has been charged yet.
            lea eax, [edx + 0xFC0]
            mov ecx, 3
        running_full_dislike:
            cmp dword ptr [eax], {RUNNING_PREFERENCE_ID}
            je running_full_removed
            add eax, 4
            dec ecx
            jne running_full_dislike
            mov eax, 22
            jmp show_detail_result
        running_full_removed:
            # This is the free, full-Likes edge case: the owned route mutates
            # only the Running Dislike, so it needs the same identity boundary
            # as the charged Like insertion below.
            call 0x{RUNNING_BOUNDARY_BEFORE_CAVE_VA:X}
            mov dword ptr [eax], -1
            call 0x{RUNNING_BOUNDARY_AFTER_CAVE_VA:X}
            mov eax, 21
            jmp show_detail_result

        running_already:
            mov eax, 20
            jmp show_detail_result

        detail_charge:
            mov eax, dword ptr [0x{s['detail_costs']:X} + ebx*4]
            cmp dword ptr [0x582644], eax
            jb detail_insufficient
            # Change Appearance charges only when the chooser actually changes
            # the head or body, so verify funds here but defer the deduction to
            # the appearance cave; every other detail upgrade deducts now.
            cmp ebx, 4
            je do_change_appearance
            sub dword ptr [0x582644], eax
            cmp ebx, 0
            je detail_youth
            cmp ebx, 1
            je detail_mastery
            cmp ebx, 2
            je detail_running
            cmp dword ptr [edx + 0xDC4], 360
            je detail_age_nochange
            mov eax, 360
            jmp detail_set_age
        detail_age_nochange:
            mov ecx, dword ptr [0x{s['detail_costs']:X} + ebx*4]
            add dword ptr [0x582644], ecx
            mov eax, 0x{s['detail_age_already']:X}
            jmp detail_status

        do_change_appearance:
            # detail_charge verified funds but did NOT deduct; the appearance
            # cave opens the chooser and charges 5,000 only if the head or body
            # actually changed (the DLL handles the genetics warning and the
            # "unchanged" message).  Then close the Villager Upgrades menu so the
            # detail-screen update loop regains control.
            call 0x{CHANGE_APPEARANCE_VA:X}
            jmp detail_done

        detail_youth:
            # No-change guard: a villager already at the minimum age (100 units
            # = 5 years) is "full of youth" -- Grant Youth would change nothing,
            # so refund the charge and report it.
            cmp dword ptr [edx + 0xDC4], 100
            jg detail_youth_apply
            mov ecx, dword ptr [0x{s['detail_costs']:X} + ebx*4]
            add dword ptr [0x582644], ecx
            mov eax, 0x{s['youth_already']:X}
            jmp detail_status
        detail_youth_apply:
            mov eax, dword ptr [edx + 0xDC4]
            sub eax, 700
            cmp eax, 100
            jge detail_set_age
            mov eax, 100
        detail_set_age:
            mov ecx, eax
            sub ecx, dword ptr [edx + 0xDC4]
            mov dword ptr [edx + 0xDC4], eax
            add dword ptr [edx + 0xE74], ecx
            cmp dword ptr [edx + 0xE8C], 0
            je detail_age_result
            add dword ptr [edx + 0xE8C], ecx
        detail_age_result:
            cmp ebx, 3
            je detail_age_show
            mov eax, 0x{s['detail_youth_done']:X}
            jmp detail_status
        detail_age_show:
            mov eax, 0x{s['detail_age_done']:X}
            jmp detail_status

        detail_mastery:
            mov esi, edx
            xor edi, edi
            mov eax, dword ptr [esi + 0xEAC]
            cmp eax, 100
            je detail_mastery_skill_1
            mov ecx, 100
            sub ecx, eax
            push ecx
            push 0
            lea ecx, [esi + 0xEAC]
            call 0x455740
            inc edi
        detail_mastery_skill_1:
            mov eax, dword ptr [esi + 0xEB0]
            cmp eax, 100
            je detail_mastery_skill_2
            mov ecx, 100
            sub ecx, eax
            push ecx
            push 1
            lea ecx, [esi + 0xEAC]
            call 0x455740
            inc edi
        detail_mastery_skill_2:
            mov eax, dword ptr [esi + 0xEB4]
            cmp eax, 100
            je detail_mastery_skill_3
            mov ecx, 100
            sub ecx, eax
            push ecx
            push 2
            lea ecx, [esi + 0xEAC]
            call 0x455740
            inc edi
        detail_mastery_skill_3:
            mov eax, dword ptr [esi + 0xEB8]
            cmp eax, 100
            je detail_mastery_skill_4
            mov ecx, 100
            sub ecx, eax
            push ecx
            push 3
            lea ecx, [esi + 0xEAC]
            call 0x455740
            inc edi
        detail_mastery_skill_4:
            mov eax, dword ptr [esi + 0xEBC]
            cmp eax, 100
            je detail_mastery_verify
            mov ecx, 100
            sub ecx, eax
            push ecx
            push 4
            lea ecx, [esi + 0xEAC]
            call 0x455740
            inc edi
        detail_mastery_verify:
            cmp dword ptr [esi + 0xEAC], 100
            jne detail_mastery_failed
            cmp dword ptr [esi + 0xEB0], 100
            jne detail_mastery_failed
            cmp dword ptr [esi + 0xEB4], 100
            jne detail_mastery_failed
            cmp dword ptr [esi + 0xEB8], 100
            jne detail_mastery_failed
            cmp dword ptr [esi + 0xEBC], 100
            jne detail_mastery_failed
            test edi, edi
            jz detail_mastery_nochange
            push esi
            call 0x462500
            mov eax, 0x{s['detail_mastery_done']:X}
            jmp detail_status
        detail_mastery_nochange:
            mov ecx, dword ptr [0x{s['detail_costs']:X} + ebx*4]
            add dword ptr [0x582644], ecx
            mov eax, 0x{s['detail_mastery_already']:X}
            jmp detail_status
        detail_mastery_failed:
            mov eax, 0x{s['mastery_failed']:X}
            jmp detail_status

        detail_running:
            lea ecx, [edx + 0xFB4]
            mov eax, 3
        running_find_like:
            cmp dword ptr [ecx], {RUNNING_PREFERENCE_ID}
            je running_already
            cmp dword ptr [ecx], -1
            je running_store_like
            add ecx, 4
            dec eax
            jne running_find_like
            # Unreachable: running_preflight only charges (and reaches here) when
            # a free Like slot exists.  Close the menu defensively.
            jmp detail_done
        running_store_like:
            call 0x{RUNNING_BOUNDARY_BEFORE_CAVE_VA:X}
            mov dword ptr [ecx], {RUNNING_PREFERENCE_ID}
        running_remove_dislikes:
            lea ecx, [edx + 0xFC0]
            mov eax, 3
        running_dislike_loop:
            cmp dword ptr [ecx], {RUNNING_PREFERENCE_ID}
            jne running_next_dislike
            mov dword ptr [ecx], -1
        running_next_dislike:
            add ecx, 4
            dec eax
            jne running_dislike_loop
            call 0x{RUNNING_BOUNDARY_AFTER_CAVE_VA:X}
            mov eax, 0x{s['detail_running_done']:X}
            jmp detail_status
        detail_insufficient:
            mov eax, 0x{s['not_enough']:X}
        detail_status:
            push eax
            push 0x{s['detail_title']:X}
            call 0x{show_message:X}
            jmp detail_loop
        show_detail_result:
            # eax = result code (20..22); the DLL export ShowOriginsUpgradeResult
            # owns the exact "Villager Upgrades" no-change wording for Grant
            # Running.  Fails silently (returns to the menu loop) if unresolved.
            push eax
            push 0x{s['icons_dll']:X}
            call dword ptr [0x47C124]
            test eax, eax
            je show_detail_result_done
            push 0x{s['result_export']:X}
            push eax
            call dword ptr [0x47C128]
            test eax, eax
            je show_detail_result_done
            push dword ptr [esp]
            call eax
        show_detail_result_done:
            pop eax
            jmp detail_loop
        detail_done:
            pop ebp
            pop edi
            pop esi
            pop ebx
            ret
        """,
    )

    put(
        tech_increment,
        """
            mov eax, dword ptr [esp + 4]
            test eax, eax
            jle apply
            cmp dword ptr [esp], 0x42DF79
            je apply
            cmp dword ptr [esp], 0x458DB0
            jb check_owned
            cmp dword ptr [esp], 0x45943F
            jb apply
        check_owned:
            test dword ptr [0x5824D0], 1
            jz apply
            shl dword ptr [esp + 4], 1
        apply:
            mov eax, dword ptr [esp + 4]
            mov edx, dword ptr [ecx]
            jmp 0x427136
        """,
    )

    put(
        food_increment,
        """
            mov eax, dword ptr [esp + 4]
            test eax, eax
            jle apply
            cmp dword ptr [esp], 0x458DB0
            jb check_owned
            cmp dword ptr [esp], 0x45943F
            jb apply
        check_owned:
            test dword ptr [0x5824D0], 2
            jz apply
            shl dword ptr [esp + 4], 1
        apply:
            mov eax, dword ptr [esp + 4]
            push esi
            jmp 0x4263F5
        """,
    )

    # Barrel capacity preflight: probe the companion DLL and call
    # PrepareBarrelBabies, which returns 1 when the village can hold three more
    # villagers under its live, mode-aware maximum and 0 otherwise.  LoadLibraryA
    # is [0x47C124], GetProcAddress is [0x47C128] (same imports the village-wide
    # path uses).  If the DLL/export cannot be resolved, fail open so the barrel
    # still works (the native 150-slot safety guard on 0x415320 remains).
    put(
        BARREL_PREFLIGHT_DLL_VA,
        f"""
            push 0x{s['icons_dll']:X}
            call dword ptr [0x47C124]
            test eax, eax
            je bp_allow
            push 0x{s['prepare_barrel_export']:X}
            push eax
            call dword ptr [0x47C128]
            test eax, eax
            je bp_allow
            call eax
            ret
        bp_allow:
            mov eax, 1
            ret
        """,
    )

    patches: list[dict[str, str]] = []

    def patch(offset: int, before: bytes, after: bytes, purpose: str) -> None:
        actual = original[offset : offset + len(before)]
        if actual != before:
            raise RuntimeError(
                f"guard mismatch at {offset:#x}: expected {before.hex()}, "
                f"got {actual.hex()}"
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

    # ---- Appended-section pages (docs/head-mask-rendering.md Part 7) ----
    # The mask trampolines live in an appended R-X section rather than a borrowed gap, so
    # nothing of ours sits in the .text tail slack.  These pages are concatenated onto the stock
    # EOF; the section headers mapping them are emitted as ordinary header patches below.
    append_code = bytearray(SECTION_CODE_SIZE)     # .vv3mc  R-X
    append_data = bytearray(SECTION_DATA_SIZE)     # .vv3md  R/W (zero-init; DllMain fills it)
    cave_slots: list[tuple[int, int, str]] = []

    def put_cave(page_off: int, code: bytes, purpose: str) -> None:
        """Place a trampoline in the appended R-X page at a fixed 0x40-byte slot."""
        if page_off + len(code) > SECTION_CODE_SIZE:
            raise RuntimeError("appended code page overflow")
        for prev_off, prev_len, prev_purpose in cave_slots:
            if page_off < prev_off + prev_len and prev_off < page_off + len(code):
                raise RuntimeError(
                    f"cave overlap at +0x{page_off:X} ({purpose}) "
                    f"with +0x{prev_off:X} ({prev_purpose})"
                )
        append_code[page_off : page_off + len(code)] = code
        cave_slots.append((page_off, len(code), purpose))

    def section_header(name: bytes, vsize: int, va: int, raw_size: int,
                       raw_ptr: int, chars: int) -> bytes:
        hdr = bytearray(40)
        hdr[0 : len(name)] = name
        struct.pack_into("<I", hdr, 8, vsize)
        struct.pack_into("<I", hdr, 12, va - IMAGE_BASE)   # VirtualAddress is an RVA
        struct.pack_into("<I", hdr, 16, raw_size)
        struct.pack_into("<I", hdr, 20, raw_ptr)
        struct.pack_into("<I", hdr, 36, chars)
        return bytes(hdr)

    cure_code = assemble(
        f"""
            cmp ebx, 5
            je cure_all
            cmp ebx, 6
            jae village_wide
            or dword ptr [0x5824D0], 2
            ret
        village_wide:
            # ebx = command (6 running / 7 mastery / 8 age).  Count the affected
            # villagers in the DLL first (PrepareOriginsVillageWide): if nothing
            # would change, refund the 1,000,000 charge and say so; otherwise
            # apply the native change and show the counted result.  ebp holds the
            # DLL module (0 if it could not load) across the single apply block,
            # which VILLAGE_WIDE_ENTRY leaves untouched.
            push ebx
            push ebp
            push ecx
            push edx
            push esi
            push edi
            push 0x{s['icons_dll']:X}
            call dword ptr [0x47C124]
            mov ebp, eax
            test eax, eax
            je village_apply
            push 0x{s['prepare_export']:X}
            push ebp
            call dword ptr [0x47C128]
            test eax, eax
            je village_apply
            push ebx
            call eax
            test eax, eax
            jnz village_apply
            add dword ptr [0x582644], 1000000
            jmp village_result
        village_apply:
            mov eax, ebx
            mov ecx, 0x59E124
            mov edx, dword ptr [0x42883A]
            # Keep this original five-byte call in the certified payload
            # footprint.  The .vv3mc wrapper brackets only command 6 with the
            # mask-fingerprint boundary, while commands 7/8 tail-jump directly
            # into the untouched native entry.
            call 0x{RUNNING_VILLAGE_WRAPPER_CAVE_VA:X}
        village_result:
            test ebp, ebp
            je village_wide_done
            push 0x{s['show_result_export']:X}
            push ebp
            call dword ptr [0x47C128]
            test eax, eax
            je village_wide_done
            push ebx
            call eax
        village_wide_done:
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
            xor ebx, ebx
            mov ecx, 0x59E110
            call 0x428B60
            test eax, eax
            je cure_after_loop
            mov edi, eax
            mov edx, 0x59E124
            mov ecx, dword ptr [0x42883A]
        cure_loop:
            mov esi, edx
            cmp byte ptr [esi + 0xF10], 0
            je cure_next
            cmp dword ptr [esi + 0xE78], 0
            jle cure_next
            cmp dword ptr [esi + 0xE78], 80
            jge cure_health_done
            push ecx
            push ebp
            lea eax, [esi + 0xE6C]
            mov ecx, eax
            push -1
            push 100
            call 0x462670
            pop ebp
            pop ecx
            cmp dword ptr [esi + 0xE78], 100
            jne cure_next
            inc ebx
        cure_health_done:
            cmp byte ptr [esi + 0xE89], 0
            je cure_next
            mov byte ptr [esi + 0xE89], 0
            inc dword ptr [edi + 0x4FC]
            inc ebp
        cure_next:
            mov edx, esi
            add edx, 0x1F8C
            dec ecx
            jne cure_loop
        cure_after_loop:
            # ebp = villagers whose sickness was cleared, ebx = villagers
            # restored to full health.  If neither happened, refund the cure
            # cost and report that nothing was needed.
            mov eax, ebp
            or eax, ebx
            jnz cure_success
            add dword ptr [0x582644], 30000
            push 0x{s['cure_nothing']:X}
            push 0x{s['tech_title']:X}
            call 0x{show_message:X}
            jmp cure_ret
        cure_success:
            # wsprintfA(buffer, "Cured sickness from %u %s.\\n\\nRestored %u %s
            # to full health.", ebp, word(ebp), ebx, word(ebx)) then show it,
            # with correct singular/plural for each count.
            sub esp, 0x80
            push 0x{s['user32_dll']:X}
            call dword ptr [0x47C124]
            test eax, eax
            je cure_free
            push 0x{s['wsprintf_export']:X}
            push eax
            call dword ptr [0x47C128]
            test eax, eax
            je cure_free
            mov edx, eax
            mov esi, 0x{s['villager_many']:X}
            cmp ebp, 1
            jne cure_word1_done
            mov esi, 0x{s['villager_one']:X}
        cure_word1_done:
            mov edi, 0x{s['villager_many']:X}
            cmp ebx, 1
            jne cure_word2_done
            mov edi, 0x{s['villager_one']:X}
        cure_word2_done:
            push edi
            push ebx
            push esi
            push ebp
            push 0x{s['cure_message']:X}
            lea eax, [esp + 0x14]
            push eax
            call edx
            add esp, 0x18
            lea eax, [esp]
            push eax
            push 0x{s['tech_title']:X}
            call 0x{show_message:X}
        cure_free:
            add esp, 0x80
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
    # Availability check for the village-wide upgrades.  Only verify the
    # village-wide component's signature (magic + version); the previous version
    # also LoadLibrary/GetProcAddress-probed the result DLL here, which corrupted
    # the return path and crashed every village-wide purchase (Running, Full
    # Mastery, All Villagers are 18) with a ret-to-garbage.  The signature alone
    # proves the component is installed, and village_wide re-resolves the result
    # export with its own null guard, so the probe was redundant.
    preflight_source = f"""
            cmp dword ptr [0x{VILLAGE_WIDE_SIGNATURE_VA:X}], 0x50465656
            jne preflight_invalid
            cmp dword ptr [0x{VILLAGE_WIDE_SIGNATURE_VA + 4:X}], 0x0055574F
            jne preflight_invalid
            cmp dword ptr [0x{VILLAGE_WIDE_SIGNATURE_VA + 8:X}], 0x00200001
            jne preflight_invalid
            cmp dword ptr [0x{VILLAGE_WIDE_SIGNATURE_VA + 0x10:X}], 3
            jne preflight_invalid
            mov eax, 1
            ret
        preflight_invalid:
            xor eax, eax
            ret
        """
    preflight_code = assemble(
        preflight_source,
        VILLAGE_PREFLIGHT_VA,
    )
    put(VILLAGE_PREFLIGHT_VA, preflight_source)

    native_food_tail = assemble(
        """
            mov eax, dword ptr [esp + 4]
            push esi
            jmp 0x4263F5
        """,
        NATIVE_FOOD_TAIL_VA,
    )
    native_tech_tail = assemble(
        """
            mov eax, dword ptr [esp + 4]
            mov edx, dword ptr [ecx]
            jmp 0x427136
        """,
        NATIVE_TECH_TAIL_VA,
    )

    # Change Appearance action cave.  Opens the companion DLL's custom
    # head+body chooser (ShowVV3AppearanceChooser) for the selected villager.
    # The DLL returns 1 only when the head or body actually changed and (for a
    # head change) the genetics warning was confirmed; it shows the "unchanged"
    # and warning boxes itself.  On that 1, this cave deducts the 5,000-tech
    # charge (detail_charge only verified funds) and writes the chosen head
    # (+0xDF0) and body (+0xDF4).  Cancel / unchanged / declined-warning return 0
    # here: no charge, no write.  edx = the validated selected record on entry;
    # head/body are staged in two stack locals passed by pointer.
    # The cosmetic MASK is NOT a record field (VV3's record +0xED0 is zeroed by
    # the sim every frame).  The chooser is passed the record POINTER as arg5 and
    # reads/commits the mask through the DLL-owned table (VV3_Get/SetMaskForRecord,
    # keyed by slot index, fingerprint-guarded).  This cave never touches +0xED0 --
    # the record and save are never written by the mask.  head(+0xDF0)/body(+0xDF4)
    # are still written (paid appearance changes).
    change_appearance_code = assemble(
        f"""
            push ebx
            push esi
            mov esi, edx
            sub esp, 8
            mov eax, dword ptr [esi + 0xDF0]
            mov dword ptr [esp], eax
            mov eax, dword ptr [esi + 0xDF4]
            mov dword ptr [esp + 4], eax
            push 0x{s['icons_dll']:X}
            call dword ptr [0x47C124]
            test eax, eax
            je ca_done
            push 0x{s['appearance_export']:X}
            push eax
            call dword ptr [0x47C128]
            test eax, eax
            je ca_done
            mov ebx, eax
            push esi
            lea eax, [esp + 8]
            push eax
            lea eax, [esp + 8]
            push eax
            push dword ptr [esi + 0xDC4]
            push dword ptr [esi + 0xDC8]
            call ebx
            test eax, eax
            je ca_done
            sub dword ptr [0x582644], 5000
            mov eax, dword ptr [esp]
            mov dword ptr [esi + 0xDF0], eax
            mov eax, dword ptr [esp + 4]
            mov dword ptr [esi + 0xDF4], eax
        ca_done:
            add esp, 8
            pop esi
            pop ebx
            ret
        """,
        CHANGE_APPEARANCE_VA,
    )

    # Heathen-mask render hook cave (DLL-draw method).  Draw the head (via copies
    # of the 7 stack args, so the originals survive), then call the DLL's
    # VV3DrawMaskOnHead(record=esi, sprite_obj=[esi+0x1F7C], args=&originals) once.
    # The DLL looks up the villager's mask (its own fingerprint-guarded table),
    # loads the atlas, and draws the mask cell on top with the tunable lift.  The
    # export pointer is resolved once (LoadLibrary/GetProcAddress) and cached in
    # MASK_DRAWFN_PTR.  Any failure (no DLL/export/mask) draws nothing.  No state.
    put(
        MASK_CAVE_VA,
        f"""
            push dword ptr [esp + 0x18]
            push dword ptr [esp + 0x18]
            push dword ptr [esp + 0x18]
            push dword ptr [esp + 0x18]
            push dword ptr [esp + 0x18]
            push dword ptr [esp + 0x18]
            push dword ptr [esp + 0x18]
            mov ecx, dword ptr [esi + 0x{MASK_SPRITE_OBJ_OFF:X}]
            call 0x{MASK_DRAW_FN:X}
            mov eax, dword ptr [0x{MASK_DRAWFN_PTR:X}]
            test eax, eax
            jnz mask_have
            push 0x{s['icons_dll']:X}
            call dword ptr [0x47C124]
            test eax, eax
            je mask_done
            push 0x{s['drawmask_export']:X}
            push eax
            call dword ptr [0x47C128]
            test eax, eax
            je mask_done
            mov dword ptr [0x{MASK_DRAWFN_PTR:X}], eax
        mask_have:
            mov edx, esp
            push edx
            push dword ptr [esi + 0x{MASK_SPRITE_OBJ_OFF:X}]
            push esi
            call eax
        mask_done:
            add esp, 0x1C
            jmp 0x{0x456B2F:X}
        """,
    )
    mask_hook_code = assemble(
        f"jmp 0x{MASK_CAVE_VA:X}", MASK_HOOK_VA
    ) + b"\x90" * (MASK_HOOK_LEN - 5)

    # Head-site STASH cave: at 0x460A60 the game does `call 0x42E570` (the head draw) with
    # esi=record and the 5 head-draw args on the stack ([esp+4]=headSprite,+8=x,+0xC=y,
    # +0x10=scale,+0x14=flag).  Redirect that call here: re-issue the identical head draw
    # with a COPY of the 5 args (sub_42E570 is ret 0x14 so it cleans the copies, leaving the
    # originals), then hand the DLL VV3WorldMaskDrawAt(record,&origArgs) to STASH the head's
    # EXACT animated x/y/scale for this pass.  It draws NOTHING (drawing here lands under the
    # front-hair); the wrapper draws last, on top, reusing this stash.  Null ptr -> plain
    # head.  esi + callee-saved regs survive both calls.
    put(
        WORLD_MASK_CAVE_VA,
        f"""
            push dword ptr [esp + 0x14]
            push dword ptr [esp + 0x14]
            push dword ptr [esp + 0x14]
            push dword ptr [esp + 0x14]
            push dword ptr [esp + 0x14]
            mov ecx, 0x58F6F8
            call 0x{WORLD_HEAD_DRAW_VA:X}
            mov eax, dword ptr [0x{WORLD_DRAWFN_PTR:X}]
            test eax, eax
            je world_stash_done
            lea edx, [esp + 4]
            push edx
            push esi
            call eax
        world_stash_done:
            ret 0x14
        """,
    )
    world_mask_head_redirect = assemble(
        f"call 0x{WORLD_MASK_CAVE_VA:X}", WORLD_MASK_CALLSITE_VA
    )

    # Village/world mask WRAPPER: replace the per-villager handler's SOLE call site
    # (0x42E3F5: `call 0x4605F0`) with `call <wrapper>`.  The wrapper runs the ENTIRE
    # handler (head, hair, all overlays, action, props), THEN draws the mask -> guaranteed
    # LAST layer (fixes "behind the hair") with correct inter-villager z-order, and no
    # stolen jump target (a call site is never a branch target).
    #   Handler is `ret 4`, arg = villager INDEX (record = base + index*0x1F8C), ecx = base.
    #   At entry: [esp]=return(0x42E3FA), [esp+4]=index, ecx=0x59E110.
    #   We RE-PUSH the index for the inner call (its own extra return address would otherwise
    #   shift the handler's [esp+0x48] arg read by one slot -> garbage record).  After the
    #   handler returns (its ret 4 cleans the re-push), we call VV3WorldMaskDraw(index),
    #   which consumes the head-site stash and blits the mask on top.  The
    #   DLL fn is __stdcall @4 (cleans its own arg).  Finally ret 4 cleans the original
    #   index -> identical net stack effect to the original `call 0x4605F0`.  ecx is left
    #   untouched before the inner call so 0x59E110 reaches the handler as `this`.
    # AUTO-LOAD: masks must appear on the first village frame, WITHOUT the player opening the
    # Upgrades menu (which is how the DLL used to get pulled in -> "nothing changed" if never
    # opened).  On the first call of this per-villager wrapper, LoadLibraryA the companion DLL
    # once (gated by the byte at 0x6C7A34, zero-init .data next to the published fn slots); its
    # DllMain then publishes the fn pointers so the very same frame's wrapper draws masks, and the
    # sidecar restore happens lazily on the first VV3_GetMaskForRecord.  LoadLibrary from normal
    # game code (NOT DllMain) is safe; the load is synchronous so the pointer is live immediately.
    world_mask_wrapper_cave = assemble(
        f"""
            cmp byte ptr [0x{SECTION_DATA_VA + 0x34:X}], 0
            jne world_wrap_loaded
            mov byte ptr [0x{SECTION_DATA_VA + 0x34:X}], 1
            push 0x{s['icons_dll']:X}
            call dword ptr [0x47C124]
        world_wrap_loaded:
            push dword ptr [esp + 4]
            call 0x{WORLD_HANDLER_FN:X}
            mov eax, dword ptr [0x{WORLD_INDEXFN_PTR:X}]
            test eax, eax
            je world_wrap_done
            push dword ptr [esp + 4]
            call eax
        world_wrap_done:
            ret 4
        """,
        WORLD_MASK_WRAPPER_CAVE_VA,
    )
    world_mask_wrapper_redirect = assemble(
        f"call 0x{WORLD_MASK_WRAPPER_CAVE_VA:X}", WORLD_HANDLER_CALLSITE_VA
    )

    # No cursor/held wrapper is emitted here.  The stock calls at 0x434357 and 0x4344B3
    # belong to the timed UI/effect object documented above, not to a villager renderer.
    # No held/effect cave is assembled.
    # ACTION-POSE wrapper: wrap the action overlay's `call 0x45F7E0` at 0x460B48.  At entry the 3
    # args are on the stack ([esp+4]=record, [esp+8]=x, [esp+0xC]=y) and ecx=this.  Re-push them,
    # run the original overlay (its `ret 0xc` cleans the re-push), then call
    # VV3ActionMaskDraw(record, x, y) reading the ORIGINAL args so the mask seats on the pose
    # sprite's head.  Null ptr -> plain pose.  `ret 0xc` cleans the original 3 args -> identical
    # net stack effect to the original `call 0x45F7E0`.  ecx is not clobbered before the inner
    # call, so `this` reaches the overlay.
    world_action_wrap_cave = assemble(
        f"""
            push dword ptr [esp + 0xC]
            push dword ptr [esp + 0xC]
            push dword ptr [esp + 0xC]
            call 0x{WORLD_ACTION_FN:X}
            mov eax, dword ptr [0x{WORLD_ACTIONFN_PTR:X}]
            test eax, eax
            je action_wrap_done
            push dword ptr [esp + 0xC]
            push dword ptr [esp + 0xC]
            push dword ptr [esp + 0xC]
            call eax
        action_wrap_done:
            ret 0xC
        """,
        WORLD_ACTION_WRAP_CAVE_VA,
    )
    world_action_wrap_redirect = assemble(
        f"call 0x{WORLD_ACTION_WRAP_CAVE_VA:X}", WORLD_ACTION_CALLSITE_VA
    )

    # Running-boundary helpers live in the patch-owned executable section so the
    # crowded Origins payload only needs four five-byte calls.  They preserve the
    # caller's volatile registers and fail open when the companion has not yet
    # published its fixed .vv3md function pointer.
    running_boundary_before_cave = assemble(
        f"""
            push eax
            push ecx
            push edx
            mov eax, dword ptr [0x{RUNNING_BOUNDARYFN_PTR:X}]
            test eax, eax
            je running_boundary_before_missing
            push 0
            call eax
            jmp running_boundary_before_done
        running_boundary_before_missing:
        running_boundary_before_done:
            pop edx
            pop ecx
            pop eax
            ret
        """,
        RUNNING_BOUNDARY_BEFORE_CAVE_VA,
    )
    running_boundary_after_cave = assemble(
        f"""
            push eax
            push ecx
            push edx
            mov eax, dword ptr [0x{RUNNING_BOUNDARYFN_PTR:X}]
            test eax, eax
            je running_boundary_after_missing
            push 1
            call eax
            jmp running_boundary_after_done
        running_boundary_after_missing:
        running_boundary_after_done:
            pop edx
            pop ecx
            pop eax
            ret
        """,
        RUNNING_BOUNDARY_AFTER_CAVE_VA,
    )
    running_village_wrapper_cave = assemble(
        f"""
            cmp ebx, 6
            jne running_village_native
            call 0x{RUNNING_BOUNDARY_BEFORE_CAVE_VA:X}
            call 0x{VILLAGE_WIDE_ENTRY_VA:X}
            call 0x{RUNNING_BOUNDARY_AFTER_CAVE_VA:X}
            ret
        running_village_native:
            jmp 0x{VILLAGE_WIDE_ENTRY_VA:X}
        """,
        RUNNING_VILLAGE_WRAPPER_CAVE_VA,
    )

    # Save-slot capture: the stock save-builder entry begins with
    # `mov eax,[esp+4]; mov edx,[ecx]`.  Preserve those exact instructions,
    # publish the positive slot argument into .vv3md, and jump back to the
    # untouched prologue.  The companion owns the slot switch/sidecar policy;
    # this trampoline only observes the stock save-builder argument.
    save_slot_capture_cave = assemble(
        f"""
            mov eax, dword ptr [esp + 4]
            mov dword ptr [0x{SAVE_SLOT_PTR:X}], eax
            mov edx, dword ptr [ecx]
            jmp 0x{SAVE_SLOT_CAPTURE_RETURN_VA:X}
        """,
        SAVE_SLOT_CAPTURE_CAVE_VA,
    )
    save_slot_capture_redirect = rel32_jump(
        SAVE_SLOT_CAPTURE_FN,
        SAVE_SLOT_CAPTURE_CAVE_VA,
        SAVE_SLOT_CAPTURE_LEN,
    )

    # Complete all Collections: mark collectible ids 52..99 found in the native
    # count array [0x58F428 + 0x10 + id*4], then broadcast the collectible
    # refresh (0x293) and the four collection-complete goal events plus the
    # all-complete master event (0x2D0..0x2D4) on the event manager 0x594C40 via
    # the stock notifier 0x436E60 (which self-gates against re-firing).
    collections_complete_code = assemble(
        f"""
            cmp dword ptr [0x582644], 1000000
            jb cc_insufficient
            sub dword ptr [0x582644], 1000000
            mov esi, 52
        cc_loop:
            cmp dword ptr [esi*4 + 0x58F438], 0
            jne cc_next
            mov dword ptr [esi*4 + 0x58F438], 1
        cc_next:
            inc esi
            cmp esi, 100
            jl cc_loop
            push 0
            push 0
            push 0x293
            mov ecx, 0x594C40
            call 0x436E60
            mov esi, 0x2D0
        cc_goal:
            push 0
            push 0
            push esi
            mov ecx, 0x594C40
            call 0x436E60
            inc esi
            cmp esi, 0x2D5
            jl cc_goal
            push 0x{s['collections_completed']:X}
            push 0x{s['tech_title']:X}
            call 0x{show_message:X}
            ret
        cc_insufficient:
            push 0x{s['not_enough']:X}
            push 0x{s['tech_title']:X}
            call 0x{show_message:X}
            ret
        """,
        COLLECTIONS_COMPLETE_VA,
    )

    # Reset all Collections: zero collectible ids 52..99 in the native count
    # array, re-arm the collection-complete goals, and broadcast a refresh
    # (0x293) so the Collections screen redraws.  Each goal event 0x2D0..0x2D4
    # self-gates on the byte at 0x594C40 + (event-0x279)*0x20 (the notifier skips
    # an already-delivered event), so clearing those five gate bytes lets a later
    # Complete fire the goals again.  0x2D0's gate is at 0x594C40 + 0x57*0x20 =
    # 0x595720; 0x2D1..0x2D4 follow at +0x20.
    collections_reset_code = assemble(
        f"""
            cmp dword ptr [0x582644], 1000000
            jb rc_insufficient
            sub dword ptr [0x582644], 1000000
            mov esi, 52
        rc_loop:
            mov dword ptr [esi*4 + 0x58F438], 0
            inc esi
            cmp esi, 100
            jl rc_loop
            mov esi, 0x595720
            mov edx, 5
        rc_rearm:
            mov byte ptr [esi], 0
            add esi, 0x20
            dec edx
            jnz rc_rearm
            push 0
            push 0
            push 0x293
            mov ecx, 0x594C40
            call 0x436E60
            push 0x{s['collections_reset']:X}
            push 0x{s['tech_title']:X}
            call 0x{show_message:X}
            ret
        rc_insufficient:
            push 0x{s['not_enough']:X}
            push 0x{s['tech_title']:X}
            call 0x{show_message:X}
            ret
        """,
        COLLECTIONS_RESET_VA,
    )

    # Deferred barrel-event hook, spliced into the island-event handler at
    # 0x468727 (runs every frame during village gameplay).  When do_barrel has
    # set the pending flag, present the real "Another One of Those Barrels"
    # island event -- popup and all -- via barrel_present_code below, then clear
    # the flag and run the two spliced-out instructions before returning.  esi is
    # the island scene throughout the handler, so [esi+0x10] is the manager the
    # spliced code needs, and esi itself is the scene the presenter wants.
    barrel_hook_code = assemble(
        f"""
            cmp byte ptr [0x{BARREL_PENDING_FLAG_VA:X}], 0
            je bh_original
            mov byte ptr [0x{BARREL_PENDING_FLAG_VA:X}], 0
            call 0x{BARREL_PRESENT_VA:X}
        bh_original:
            mov ecx, dword ptr [esi + 0x10]
            call 0x403330
            jmp 0x{BARREL_HANDLER_SPLICE_VA + 8:X}
        """,
        BARREL_HOOK_VA,
    )
    # Present the barrel event through the game's own island-event presenter,
    # forced to the barrel.  Called from the hook with esi = the island scene.
    # Save the event-object array, point every slot 1..0x39 at the barrel object
    # (so the presenter's random pick and its population-based fallbacks all
    # resolve to the barrel), run the native select + present pair, then restore
    # the array.  The presented popup keeps a direct pointer to the barrel
    # singleton (0x4B3D5C, which we never move), so restoring the slots is safe,
    # and the 3-child spawn runs from the game's own outcome when the player
    # dismisses the popup.  The 57 saved pointers are held on the stack, so no
    # data cave is needed.
    barrel_present_code = assemble(
        f"""
            pushad
            mov ebp, esi
            mov esi, 0x{BARREL_EVENT_OBJECT_VA:X}
            mov ecx, 0x{BARREL_SAVE_COUNT:X}
        bp_save:
            push dword ptr [esi]
            sub esi, 4
            loop bp_save
            mov eax, dword ptr [0x{BARREL_EVENT_OBJECT_VA:X}]
            mov edi, 0x{BARREL_EVENT_SLOT1_VA:X}
            mov ecx, 0x{BARREL_EVENT_SLOT_COUNT:X}
            rep stosd
            push ebp
            call 0x{BARREL_SELECT_MANAGER_VA:X}
            mov ecx, eax
            call 0x{BARREL_PRESENT_EVENT_VA:X}
            mov edi, 0x{BARREL_SAVE_LOW_VA:X}
            mov ecx, 0x{BARREL_SAVE_COUNT:X}
        bp_restore:
            pop eax
            stosd
            loop bp_restore
            popad
            ret
        """,
        BARREL_PRESENT_VA,
    )
    barrel_splice_before = assemble(
        "mov ecx, dword ptr [esi + 0x10]\n call 0x403330",
        BARREL_HANDLER_SPLICE_VA,
    )
    barrel_splice_after = assemble(
        f"jmp 0x{BARREL_HOOK_VA:X}", BARREL_HANDLER_SPLICE_VA
    ) + b"\x90\x90\x90"

    payload = code + strings
    if len(payload) > PAYLOAD_SIZE:
        raise RuntimeError(f"payload too large: {len(payload):#x}/{PAYLOAD_SIZE:#x}")

    patch(
        HEAL_CAVE_FILE_OFFSET,
        b"\0" * len(cure_code),
        cure_code,
        "restore health below 80 to 100, clear sickness, and increment People Cured",
    )
    patch(
        NATIVE_FOOD_TAIL_FILE_OFFSET,
        b"\0" * len(native_food_tail),
        native_food_tail,
        "keep Island Event food rewards on the native food path",
    )
    patch(
        NATIVE_TECH_TAIL_FILE_OFFSET,
        b"\0" * len(native_tech_tail),
        native_tech_tail,
        "keep Island Event tech rewards on the native tech path",
    )
    patch(
        CHANGE_APPEARANCE_FILE_OFFSET,
        b"\0" * len(change_appearance_code),
        change_appearance_code,
        "open the custom head/body appearance chooser for the selected villager",
    )
    # (The mask render cave itself is emitted into the payload via put() above,
    # so it rides the payload patch -- no standalone .text cave patch here.)
    patch(
        MASK_HOOK_VA - IMAGE_BASE,
        original[MASK_HOOK_VA - IMAGE_BASE : MASK_HOOK_VA - IMAGE_BASE + MASK_HOOK_LEN],
        mask_hook_code,
        "redirect the villager head-draw through the Heathen-mask cave",
    )
    patch(
        WORLD_MASK_CALLSITE_VA - IMAGE_BASE,
        original[WORLD_MASK_CALLSITE_VA - IMAGE_BASE : WORLD_MASK_CALLSITE_VA - IMAGE_BASE + 5],
        world_mask_head_redirect,
        "redirect the head draw through the stash cave (capture exact head x/y/scale)",
    )
    put_cave(0x000, world_mask_wrapper_cave, "world-mask wrapper: run the whole villager handler, then draw the mask on top")
    patch(
        WORLD_HANDLER_CALLSITE_VA - IMAGE_BASE,
        original[WORLD_HANDLER_CALLSITE_VA - IMAGE_BASE : WORLD_HANDLER_CALLSITE_VA - IMAGE_BASE + 5],
        world_mask_wrapper_redirect,
        "wrap the per-villager handler call so the mask draws as the last layer",
    )
    put_cave(
        0x100,
        save_slot_capture_cave,
        "capture the exact positive save slot for per-save mask sidecars",
    )
    patch(
        SAVE_SLOT_CAPTURE_FN - IMAGE_BASE,
        SAVE_SLOT_CAPTURE_BEFORE,
        save_slot_capture_redirect,
        "capture save-builder [esp+4] into the patch-owned VV3 mask slot word",
    )
    # 0x434357 / 0x4344B3 ARE NOT VILLAGER DRAWS -- these two hooks are REMOVED, not disabled.
    # Proven from the binary, not assumed:
    #   * the head-atlas holder [+0x127C1C] is read at EXACTLY ONE site in the whole exe
    #     (0x460A54, feeding the head draw at 0x460A60);
    #   * 0x42E570 is a GENERIC scaled-sprite draw whose sprite is an ARGUMENT -- at 0x434357
    #     that argument comes from [esi+ecx*4+0x7C] with ecx from [ebp+0x10] in 0..2, a
    #     3-entry sprite table, never a head atlas;
    #   * the function containing both sites never references the record stride 0x1F8C;
    #   * it iterates 24-byte array entries, compares elapsed time against 0x12C and 0x7080,
    #     and its 3 anchors are the fixed screen positions (110,160)/(114,212)/(75,176)
    #     written once behind an init latch at 0x5947D0.
    # It is a timed UI/effect renderer.  Patching its call sites made the mask paint onto that
    # effect, so the correct fix is to leave those bytes STOCK.
    put_cave(0x0C0, world_action_wrap_cave, "action-overlay wrapper: run the pose overlay, then seat the mask on the pose head")
    put_cave(0x180, running_boundary_before_cave, "snapshot VV3 Running mask fingerprints before owned preference writes")
    put_cave(0x1C0, running_boundary_after_cave, "refresh VV3 Running mask fingerprints after owned preference writes")
    put_cave(0x220, running_village_wrapper_cave, "wrap the native village-wide Running writer with the mask-fingerprint boundary")
    patch(
        WORLD_ACTION_CALLSITE_VA - IMAGE_BASE,
        original[WORLD_ACTION_CALLSITE_VA - IMAGE_BASE : WORLD_ACTION_CALLSITE_VA - IMAGE_BASE + 5],
        world_action_wrap_redirect,
        "wrap the action-overlay call so pose villagers get their mask on the pose head",
    )
    # (No head-atlas row-count bump: the separate-atlas method draws the mask from
    # its own Images/heathen_masks.png, so the head atlases are left untouched.)
    patch(
        COLLECTIONS_COMPLETE_FILE_OFFSET,
        b"\0" * len(collections_complete_code),
        collections_complete_code,
        "fill every collectible and fire the collection-complete goal events",
    )
    patch(
        COLLECTIONS_RESET_FILE_OFFSET,
        b"\0" * len(collections_reset_code),
        collections_reset_code,
        "clear every collectible and refresh the Collections screen",
    )
    patch(
        BARREL_HOOK_FILE_OFFSET,
        b"\0" * len(barrel_hook_code),
        barrel_hook_code,
        "deferred barrel-event hook: fire the pending barrel event in-frame",
    )
    patch(
        BARREL_PRESENT_FILE_OFFSET,
        b"\0" * len(barrel_present_code),
        barrel_present_code,
        "present the barrel as a native island event (popup + 3-child spawn)",
    )
    patch(
        BARREL_HANDLER_SPLICE_VA - IMAGE_BASE,
        barrel_splice_before,
        barrel_splice_after,
        "splice the deferred barrel-event firing into the island-event handler",
    )
    patch(
        EXTRA_STRINGS_FILE_OFFSET,
        b"\0" * len(extra_strings),
        bytes(extra_strings),
        "cure and Change Appearance cave strings",
    )
    for offset in (0x415EF1, 0x416983, 0x416BAB, 0x417A3A):
        patch(
            offset - IMAGE_BASE,
            original[offset - IMAGE_BASE : offset - IMAGE_BASE + 5],
            rel32_jump(offset, NATIVE_FOOD_TAIL_VA),
            "bypass the Food Doubler for an Island Event tail-jump",
        )
    for offset in (0x415D44, 0x41673E, 0x418452):
        patch(
            offset - IMAGE_BASE,
            original[offset - IMAGE_BASE : offset - IMAGE_BASE + 5],
            rel32_jump(offset, NATIVE_TECH_TAIL_VA),
            "bypass the Tech Doubler for an Island Event tail-jump",
        )
    patch(
        0x24C,
        bytes.fromhex("40000040"),
        bytes.fromhex("400000E0"),
        "make the mapped padding executable and writable for the Origins payload state "
        "(e.g. DETAIL_BUTTON_PTR at PAYLOAD_VA+0xBF0).  NOTE: this W+X is NOT what "
        "Malwarebytes flags -- the AV heuristic 2069 fires on the exe-name-fix stub's "
        "GetModuleFileNameA basename-spoofing, so stock-named playtest builds must be "
        "deployed WITHOUT the name-fix (it is redundant when the exe keeps the stock name)",
    )
    patch(
        0x263F0,
        bytes.fromhex("8B44240456"),
        rel32_jump(0x4263F0, food_increment),
        "double eligible positive food-source deltas",
    )
    patch(
        0x27130,
        bytes.fromhex("8B4424048B11"),
        rel32_jump(0x427130, tech_increment, 6),
        "double eligible positive earned tech deltas",
    )
    patch(
        0x6547D,
        bytes.fromhex("8B4C243C5F"),
        rel32_jump(0x46547D, tech_constructor),
        "append the stock-styled Origins Upgrades button to the Tech screen",
    )
    patch(
        0x65640,
        bytes.fromhex("6AFF64A100000000"),
        rel32_jump(0x465640, tech_handler, 8),
        "route only Tech message 8 / free command-15 event through the guarded Origins handler",
    )
    patch(
        0x6DA2C,
        bytes.fromhex("8B4C24205F"),
        rel32_jump(0x46DA2C, detail_constructor),
        "append the stock-styled Upgrades button to Villager Detail",
    )
    patch(
        0x6E530,
        bytes.fromhex("8B44240483EC14"),
        rel32_jump(0x46E530, detail_handler, 7),
        "route the exact added Detail button through the guarded villager-upgrade handler",
    )
    patch(
        PAYLOAD_FILE_OFFSET,
        b"\0" * len(payload),
        bytes(payload),
        "install the VV3 Origins Tech and Villager upgrade menus and mechanics",
    )

    # ---- Header patches that map the two appended sections (Part 7) ----
    # Emitted last so they sit after every in-file edit.  Each is an ordinary guarded
    # offset/before/after patch, so the shipping patcher applies them like any other.
    patch(
        PE_NUMSECTIONS_OFF,
        original[PE_NUMSECTIONS_OFF : PE_NUMSECTIONS_OFF + 2],
        struct.pack("<H", 7),
        "NumberOfSections 5 -> 7 (add the .vv3mc R-X and .vv3md R/W mask sections)",
    )
    patch(
        PE_SIZEOFIMAGE_OFF,
        original[PE_SIZEOFIMAGE_OFF : PE_SIZEOFIMAGE_OFF + 4],
        struct.pack("<I", NEW_SIZE_OF_IMAGE),
        "extend SizeOfImage through the appended mask sections",
    )
    patch(
        PE_NEW_SECHDR_OFF,
        original[PE_NEW_SECHDR_OFF : PE_NEW_SECHDR_OFF + 80],
        section_header(SECTION_CODE_NAME, SECTION_CODE_SIZE, SECTION_CODE_VA,
                       SECTION_CODE_SIZE, SECTION_CODE_RAW, SECTION_CODE_CHARS)
        + section_header(SECTION_DATA_NAME, SECTION_DATA_SIZE, SECTION_DATA_VA,
                         SECTION_DATA_SIZE, SECTION_DATA_RAW, SECTION_DATA_CHARS),
        "install the .vv3mc (R-X, mask trampolines) and .vv3md (R/W, DLL fn-ptr/active-save slots) headers",
    )

    rendered = bytearray(original)
    for item in patches:
        offset = int(item["offset"], 16)
        replacement = bytes.fromhex(item["after"])
        rendered[offset : offset + len(replacement)] = replacement
    # Append the two mapped pages at the stock EOF (pe_append_transaction requires
    # append_offset == original_file_size, which SECTION_CODE_RAW equals by construction).
    if len(rendered) != SECTION_CODE_RAW:
        raise RuntimeError(
            f"append offset mismatch: file is {len(rendered):#x}, expected {SECTION_CODE_RAW:#x}"
        )
    rendered += append_code
    if len(rendered) != SECTION_DATA_RAW:
        raise RuntimeError("data page append offset mismatch")
    rendered += append_data
    OUT_EXE.write_bytes(rendered)
    OUT_JSON.write_text(json.dumps(patches, indent=2) + "\n", encoding="utf-8")

    companion_hash = hashlib.sha256(COMPANION.read_bytes()).hexdigest().upper()
    manifest = {
        "id": "vv3_enable_origins_exclusive_features",
        "game_id": "vv3",
        "running_preference_id": RUNNING_PREFERENCE_ID,
        "running_preference_evidence": {"source": "exact stock executable embedded preference table", "table_file_offset": "0x97488", "entry_name": "running"},
        "name": "Enable Origins-Exclusive Features",
        "description": "Adds Origins-style Upgrades buttons to the Tech and Villager Details screens. The Tech menu offers Food and Tech Point Doublers for 500,000 tech points each; eligible positive gains are doubled, while Island Events and Duplicate Collectibles remain unchanged. The Village-Wide menu adds Running, Full Mastery, and Make Villagers Young Adults.",
        "output_tag": "Origins Exclusive Features",
        "companion_files": [
            {
                "source": "data/candidates/VVFP VV3 Safe Upgrades.dll",
                "destination": "VVFP Origins Icons.dll",
                "sha256": companion_hash,
            }
        ],
        "doubler_evidence": {
            "positive_tech_writer": "0x427130",
            "positive_food_writer": "0x4263F0",
            "collection_adjustment": {
                "dispatcher": "sub_42DEB0",
                "tech_writer": "0x42DF79",
                "food_writer": "0x42E079",
                "tech_awards": {
                    "100": "IDs 52-55, 64-67, 76-79, 88-91",
                    "250": "IDs 56-59, 68-71, 80-83, 92-95",
                    "1500": "IDs 60-63, 72-75, 84-87, 96-99",
                },
                "caller_status": "IDA has no resolved caller to sub_42DEB0; computed/indirect reachability remains unresolved",
            },
            "duplicate_collectibles": {
                "dispatcher": "sub_42DEB0",
                "tech_return": "0x42DF79",
                "behavior": "an already-completed collectible routes to the tech writer",
            },
            "island_event_producers": {
                "dispatcher": "0x458DB0-0x45943F",
                "inventory": "complete positive/zero/negative/bypass inventory including tail calls; mixed-source writers have no source tag",
                "final_delta": "sub_458DB0 emits base and bonus components through separate tech-writer calls; no single final-delta boundary is proved",
            },
            "writer_inventory": {"food": {"rows": 33, "calls": 29, "e9_tails": 4}, "tech": {"rows": 16, "calls": 13, "e9_tails": 3}},
            "tail_sites": {"food": ["0x415EF1", "0x416983", "0x416BAB", "0x417A3A"], "tech": ["0x415D44", "0x41673E", "0x418452"]},
            "tail_bypass_sites": {
                "food": ["0x415EF1", "0x416983", "0x416BAB", "0x417A3A"],
                "tech": ["0x415D44", "0x41673E", "0x418452"],
            },
            "hook_status": "GO: positive writer wrappers double eligible positive deltas once; duplicate collectibles and audited Island Event calls remain native; runtime/player confirmation pending",
        },
        "doubler_composition_contract": {
            "stacking": [
                "positive earned tech deltas only",
                "positive food-source deltas only",
            ],
            "exclusions": ["Island Event tech-point gain", "Duplicate Collectibles tech-point gain"],
            "food_mastery_status": "confirmed absent in the exact-build writer, strings, and bounded caller corpus",
            "status": "GO: positive writer wrappers double eligible positive deltas once; duplicate collectibles and audited Island Event calls remain native; runtime/player confirmation pending",
        },
        "doubler_purchase_status": {
            "new_purchase": "available at 500,000 tech points for each doubler",
            "existing_owned": "removable at zero cost with zero refund",
            "repurchase": "available again at 500,000 tech points after removal",
        },
        "patches": patches,
    }
    MANIFEST_JSON.write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    used = max(index for index, value in enumerate(code) if value) + 1
    print(f"code bytes used: {used:#x}/{STRINGS_OFFSET:#x}")
    print(f"string bytes used: {len(strings):#x}/{PAYLOAD_SIZE - STRINGS_OFFSET:#x}")
    print(f"companion SHA-256: {companion_hash}")
    print(OUT_JSON)
    print(MANIFEST_JSON)
    print(OUT_EXE)


if __name__ == "__main__":
    main()
