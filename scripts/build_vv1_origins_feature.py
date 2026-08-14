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
# report_mastery_counts, which write these -- this is the VV1-only opt-in
# side of that shared, cross-game generator). There is no free register
# left at either running_va's or mastery_va's return point to carry these
# counts back through directly, so they are read from fixed memory here
# instead, after the call returns.
RUNNING_GRANTED_VA = VILLAGE_WIDE_ENTRY_VA + 0x30
MASTERY_GRANTED_VA = VILLAGE_WIDE_ENTRY_VA + 0x38
MASTERY_ALREADY_VA = VILLAGE_WIDE_ENTRY_VA + 0x3C
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
RUNNING_PREFERENCE_ID = 38  # exact-build preference-table evidence: 0x7B260
VV1_NATIVE_SKILL_WRITER_VA = 0x437230
VV1_SKILL_FIELDS = (
    (0x3BC, 2),  # Parenting
    (0x3C0, 4),  # Building
    (0x3C4, 1),  # Farming
    (0x3C8, 5),  # Healing
    (0x3CC, 3),  # Research
)


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
    add_c_string(strings, s, "purchase_complete", "Purchased.")
    add_c_string(strings, s, "removed", "Removed.")
    add_c_string(strings, s, "not_enough", "Not enough tech points.")
    add_c_string(
        strings,
        s,
        "event_queued",
        "Island Event queued.",
    )
    add_c_string(strings, s, "barrel_villagers", "Gained 3 children.")
    add_c_string(
        strings,
        s,
        "population_capacity",
        "The village population is already at maximum capacity.",
    )
    add_c_string(strings, s, "already_owned", "This doubler is already owned.")
    add_c_string(
        strings,
        s,
        "show_icon_dialog_state",
        "ShowOriginsUpgradeMenuState",
    )
    add_c_string(strings, s, "running_unavailable", "Running cannot be added.")
    add_c_string(strings, s, "icons_dll", "VVFP VV1 Origins Icons.dll")
    add_c_string(strings, s, "show_icon_dialog_legacy", "ShowOriginsUpgradeMenu")
    add_c_string(strings, s, "show_result_export", "ShowOriginsVillageWideResult")
    add_c_string(strings, s, "show_mastery_result_export", "ShowOriginsMasteryResult")
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
    tech_costs = [50000, 30000, 75000, 500000, 500000, 30000]
    detail_costs = [50000, 100000, 40000, 50000]
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

            call 0x{CONFIRM_HELPER_VA:X}
            test eax, eax
            je menu_done

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
            cmp eax, 253
            ja population_capacity
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
            cmp ebx, 5
            je cure_gated
            cmp ebx, 6
            jb legacy_charge
            cmp ebx, 8
            ja menu_loop
            call 0x{VILLAGE_PREFLIGHT_VA:X}
            test eax, eax
            jz menu_loop
            cmp dword ptr [edi + 0xA2FC], 1000000
            jb insufficient
            sub dword ptr [edi + 0xA2FC], 1000000
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
            mov eax, 0x{s['event_queued']:X}
            jmp show_and_done

        do_barrel:
            mov byte ptr [0x{BARREL_PENDING_VA:X}], 1
            mov dword ptr [0x{BARREL_DELAY_COUNTER_VA:X}], 0
            mov eax, 0x{s['purchase_complete']:X}
            push 0
            push 0x{s['title']:X}
            push eax
            call 0x452DB6
            add esp, 0x0C
            jmp menu_done

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
            mov eax, 0x{s['removed']:X}
            jmp show_and_done

        success:
            mov eax, 0x{s['purchase_complete']:X}
            jmp show_and_done
        insufficient:
            mov eax, 0x{s['not_enough']:X}
            jmp show_and_done
        population_capacity:
            mov eax, 0x{s['population_capacity']:X}
        show_and_done:
            push 0
            push 0x{s['title']:X}
            push eax
            call 0x452DB6
            add esp, 0x0C
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
            cmp ebx, 2
            jne detail_charge
            lea eax, [edx + 0x398]
            mov ecx, 4
        running_preflight:
            cmp dword ptr [eax], {RUNNING_PREFERENCE_ID}
            je detail_charge
            cmp dword ptr [eax], -1
            je detail_charge
            add eax, 4
            dec ecx
            jne running_preflight
            jmp detail_running_unavailable
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
            jmp detail_running_unavailable
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
            mov eax, 0x{s['purchase_complete']:X}
            jmp detail_show
        detail_insufficient:
            mov eax, 0x{s['not_enough']:X}
            jmp detail_show
        detail_running_unavailable:
            mov eax, 0x{s['running_unavailable']:X}
        detail_show:
            push 0
            push 0x{s['detail_title']:X}
            push eax
            call 0x452DB6
            add esp, 0x0C
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
            mov ebp, eax
            mov edi, edx
            mov esi, ecx
            cmp ebx, 7
            je village_mastery_result
            mov eax, 0x{s['show_result_export']:X}
            push 0x{s['icons_dll']:X}
            call dword ptr [0x457010]
            test eax, eax
            je village_result_done
            push 0x{s['show_result_export']:X}
            push eax
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
            push 0x{s['icons_dll']:X}
            call dword ptr [0x457010]
            test eax, eax
            je village_result_done
            push 0x{s['show_mastery_result_export']:X}
            push eax
            call dword ptr [0x4570D4]
            test eax, eax
            je village_result_done
            mov ecx, dword ptr [0x{MASTERY_ALREADY_VA:X}]
            push ecx
            mov ecx, dword ptr [0x{MASTERY_GRANTED_VA:X}]
            push ecx
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
            test eax, eax
            je 0x{DETAIL_LOOP_VA:X}
            mov eax, 0x{s['purchase_complete']:X}
            push 0
            push 0x{s['detail_title']:X}
            push eax
            call 0x452DB6
            add esp, 0x0C
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
            test eax, eax
            je appearance_fail
            sub dword ptr [edi + 0xA2FC], 5000
            mov eax, 1
            ret
        appearance_insufficient:
            mov eax, 0x{s['not_enough']:X}
            push 0
            push 0x{s['detail_title']:X}
            push eax
            call 0x452DB6
            add esp, 0x0C
        appearance_fail:
            xor eax, eax
            ret
        """,
        APPEARANCE_HELPER_VA,
    )
    confirm_helper_code = assemble(
        f"""
            push 0x{s['icons_dll']:X}
            call dword ptr [0x457010]
            test eax, eax
            je confirm_fail
            push 0x{s['confirm_export']:X}
            push eax
            call dword ptr [0x4570D4]
            test eax, eax
            je confirm_fail
            call eax
            ret
        confirm_fail:
            xor eax, eax
            ret
        """,
        CONFIRM_HELPER_VA,
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
