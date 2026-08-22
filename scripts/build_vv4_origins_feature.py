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

# --- Heathen-mask cosmetic overlay (append-rows) -----------------------------
# The 5 VV5 masks are appended to each head atlas as rows 30..34 (shipped as the
# companion asset swap below); the head-atlas row-count fields are bumped 30->35
# so the game can address those rows; and one render-hook cave re-draws head-
# atlas row (29 + [esi+0x1BC4]) on top of the villager's head at BOTH render
# twins, gated on the unused per-villager byte +0x1BC4 (0=none, 1..5=mask). esi
# = villager record is callee-saved across the native draw, so it is still the
# record after the head has been drawn. No villager fields are written; mask=0
# is byte-for-byte the stock head draw. The cave lives in the free tail of the
# .shr page the origins feature already expands to 0x1000 and marks RWX.
MASK_DRAW_VA = 0x409A70                    # FUN_00409a70 (stdcall, ret 0x1c)
MASK_CALL_SITES = (0x45F702, 0x45F9CA)     # walking-world twin + panel-portrait twin
MASK_CAVE_VA = 0x728D80
MASK_CAVE_FILE_OFFSET = 0xCCD80
# 7 dword scratch slots: saved ecx, the 5 forwarded draw args, and the dynamic
# return address (so the single cave serves every call site).
(MASK_S_ECX, MASK_S_A0, MASK_S_A1, MASK_S_A2, MASK_S_A4, MASK_S_A5,
 MASK_S_RET) = (0x728D60, 0x728D64, 0x728D68, 0x728D6C, 0x728D70, 0x728D74,
                0x728D78)
MASK_BYTE_OFFSET = 0x1BC4
MASK_ROW_FIELDS = {0xC3C24: (30, 35), 0xC3B94: (30, 35)}  # male / female heads
MASK_HEAD_ATLASES = ("male_heads00.png", "male_heads10.png",
                     "female_heads00.png", "female_heads10.png")

# Detail-portrait (big) head draw -- FUN_0043cdf0 @0x43D040. There EBP =
# record+0x1B98 (head field = [EBP+0x20], body = [EBP+0x24]), so the mask byte
# record+0x1BC4 reads as [EBP+0x2C]. The draw ABI (FUN_00409a70, 7 args, arg3 =
# atlas row) is identical to the twins, so a second cave -- same body, EBP gate
# instead of ESI -- hooks it. Its head atlas is masked and row-count-bumped too
# (rows 30..34, cell 60x100, mask scaled to match) so row 29+mask is valid
# whichever head sheet the portrait pulls.
BIGMASK_CALL_SITE = 0x43D040
BIGMASK_CAVE_VA = 0x728E30
BIGMASK_CAVE_FILE_OFFSET = 0xCCE30
(BIG_S_ECX, BIG_S_A0, BIG_S_A1, BIG_S_A2, BIG_S_A4, BIG_S_A5,
 BIG_S_RET) = (0x728E10, 0x728E14, 0x728E18, 0x728E1C, 0x728E20, 0x728E24,
               0x728E28)
BIGMASK_EBP_OFFSET = 0x2C
BIGHEAD_ROW_FIELD = (0xC3CB4, (30, 35))       # bigheads row count 30 -> 35
BIGHEAD_ATLASES = ("BigHeads00.png", "BigHeads10.png")

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


def mask_cave_bytes(cave_va: int, scratch: tuple, gate: str) -> bytes:
    """A Heathen-mask render-hook cave.

    It saves the head-draw call's ecx and its stdcall args, replaces the return
    address with ``post_head`` and tail-jumps into the native draw so the head
    is painted normally; on return ``gate`` loads the per-villager mask byte
    into eax and jumps to ``mask_done`` when it is zero, otherwise the cave
    re-draws head-atlas row ``29 + byte`` with the SAME position and facing, then
    returns to the site's real caller via the saved address. Two call sites in
    the same twin can share one cave (it returns via the saved address); the
    detail portrait uses its own cave only because its mask byte lives at a
    different register+offset (EBP vs ESI). The two-pass assemble resolves the
    absolute ``post_head`` immediate (its length is value-independent, so the
    prologue length is stable)."""
    s_ecx, s_a0, s_a1, s_a2, s_a4, s_a5, s_ret = scratch

    def src(post_head: int) -> str:
        return f"""
            mov [{s_ecx}], ecx
            mov eax, [esp+4]
            mov [{s_a0}], eax
            mov eax, [esp+8]
            mov [{s_a1}], eax
            mov eax, [esp+0xC]
            mov [{s_a2}], eax
            mov eax, [esp+0x14]
            mov [{s_a4}], eax
            mov eax, [esp+0x18]
            mov [{s_a5}], eax
            mov eax, [esp]
            mov [{s_ret}], eax
            mov dword ptr [esp], {post_head}
            jmp {MASK_DRAW_VA}
        post_head:
            {gate}
            add eax, 29
            push 0
            push dword ptr [{s_a5}]
            push dword ptr [{s_a4}]
            push eax
            push dword ptr [{s_a2}]
            push dword ptr [{s_a1}]
            push dword ptr [{s_a0}]
            mov ecx, dword ptr [{s_ecx}]
            call {MASK_DRAW_VA}
        mask_done:
            jmp dword ptr [{s_ret}]
        """
    prologue = src(0).split("post_head:")[0]
    post_head = cave_va + len(assemble(prologue, cave_va))
    return assemble(src(post_head), cave_va)


def add_c_string(blob: bytearray, labels: dict[str, int], name: str, value: str) -> None:
    labels[name] = STRINGS_VA + len(blob)
    blob.extend(value.encode("ascii") + b"\0")


def mask_atlas_companion(name: str) -> dict[str, str]:
    """Companion entry that swaps one head atlas for its masked (rows 30..34
    appended) version in the copied game's Images folder, and can restore the
    bundled stock atlas on removal. Hashes are read from the pinned repo assets
    so the manifest stays in lockstep with the committed bytes."""
    masked = ROOT / "assets/vv4_masks/atlases" / name
    base = ROOT / "assets/vv4_masks/base" / name
    base_sha = hashlib.sha256(base.read_bytes()).hexdigest().upper()
    return {
        "source": f"assets/vv4_masks/atlases/{name}",
        "destination": f"Images/{name}",
        "sha256": hashlib.sha256(masked.read_bytes()).hexdigest().upper(),
        "preimage_sha256": base_sha,
        "restore_source": f"assets/vv4_masks/base/{name}",
        "restore_sha256": base_sha,
    }


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
    mask_cave = mask_cave_bytes(
        MASK_CAVE_VA,
        (MASK_S_ECX, MASK_S_A0, MASK_S_A1, MASK_S_A2, MASK_S_A4, MASK_S_A5, MASK_S_RET),
        f"movzx eax, byte ptr [esi + {MASK_BYTE_OFFSET}]\n test eax, eax\n jz mask_done")
    patch(MASK_CAVE_FILE_OFFSET, b"\0" * len(mask_cave), mask_cave,
          "Heathen mask: world/panel render-hook cave -- draw the head normally, then (when +0x1BC4 is 1..5) re-draw head-atlas row 29+byte on top; no villager fields written")
    for site in MASK_CALL_SITES:
        patch(site - IMAGE_BASE,
              rel32_call(site, MASK_DRAW_VA), rel32_call(site, MASK_CAVE_VA),
              f"Heathen mask: route the head-draw call at {site:#x} through the mask cave")
    for offset, (old, new) in MASK_ROW_FIELDS.items():
        patch(offset, bytes([old]), bytes([new]),
              f"Heathen mask: bump head-atlas row count {old}->{new} at {offset:#x} so rows 30..34 (the masks) are addressable")
    # Detail-portrait (big) head draw: its own cave (EBP gate) + row-count bump.
    big_cave = mask_cave_bytes(
        BIGMASK_CAVE_VA,
        (BIG_S_ECX, BIG_S_A0, BIG_S_A1, BIG_S_A2, BIG_S_A4, BIG_S_A5, BIG_S_RET),
        f"movzx eax, byte ptr [ebp + {BIGMASK_EBP_OFFSET}]\n test eax, eax\n jz mask_done")
    patch(BIGMASK_CAVE_FILE_OFFSET, b"\0" * len(big_cave), big_cave,
          "Heathen mask: detail-portrait render-hook cave (mask byte at [ebp+0x2C]); same draw, re-draws head-atlas row 29+byte on the big head")
    patch(BIGMASK_CALL_SITE - IMAGE_BASE,
          rel32_call(BIGMASK_CALL_SITE, MASK_DRAW_VA),
          rel32_call(BIGMASK_CALL_SITE, BIGMASK_CAVE_VA),
          f"Heathen mask: route the detail-portrait head-draw call at {BIGMASK_CALL_SITE:#x} through the detail mask cave")
    _big_off, (_big_old, _big_new) = BIGHEAD_ROW_FIELD
    patch(_big_off, bytes([_big_old]), bytes([_big_new]),
          f"Heathen mask: bump bigheads row count {_big_old}->{_big_new} at {_big_off:#x}")
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
        "name": "Enable Origins-Exclusive Features",
        "description": "Adds Origins-style Upgrades buttons to the Tech and Villager Details screens. The Tech menu offers Time Warp, Island Event, Barrel of Babies, Food and Tech Point Doublers for 500,000 tech points each (eligible positive gains are doubled after native Food Mastery, while Island Events and Duplicate Collectibles remain unchanged), Full Heal/Cure All, Complete and Reset All Collections, and Equal Division of Labor with and without Parenting. The Village-Wide menu adds Running, Full Mastery, and Make Villagers Young Adults. The Villager Details menu grants Youth, Full Mastery, Running, Set Age to 18, and Change Appearance.",
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
            # Heathen-mask head atlases (rows 30..34 appended). The row-count
            # bump to 35 above makes the modded exe REQUIRE the taller atlas, so
            # these ship with the feature; rows 0..29 are byte-identical to
            # stock, so mask=(None) villagers look exactly as before. The
            # bigheads pair (masks scaled to the larger detail-portrait cell)
            # ships for the same reason -- its row count is bumped too.
            *(mask_atlas_companion(name)
              for name in (*MASK_HEAD_ATLASES, *BIGHEAD_ATLASES)),
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
