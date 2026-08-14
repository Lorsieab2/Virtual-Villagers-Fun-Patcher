"""Assemble the exact-build VV3 Origins-exclusive feature patch."""

from __future__ import annotations

import hashlib
import json
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
NATIVE_FOOD_TAIL_FILE_OFFSET = 0x7B7C0
NATIVE_FOOD_TAIL_VA = IMAGE_BASE + NATIVE_FOOD_TAIL_FILE_OFFSET
NATIVE_TECH_TAIL_FILE_OFFSET = 0x7B7D0
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
# Read-only strings for the cure and Change Appearance caves, placed in the
# free .text padding after the Change Appearance cave (0x7BD40) and before the
# .rdata boundary (0x7C000).
EXTRA_STRINGS_FILE_OFFSET = 0x7BDC0
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
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    strings = bytearray()
    s: dict[str, int] = {}
    for name, value in (
        ("button_label", "Upgrades"),
        ("tech_title", "Origins Upgrades"),
        ("detail_title", "Villager Upgrades"),
        ("purchased", "Purchased."),
        ("mastery_failed", "Full Mastery could not be completed."),
        ("removed", "Removed."),
        ("not_enough", "Not enough tech points."),
        ("paused", "Time Warp is unavailable while the game is paused."),
        (
            "time_warp_done",
            "Time Warp advanced every villager by 3 displayed years.",
        ),
        (
            "population_capacity",
            "The village population is already at maximum capacity.",
        ),
        ("running_unavailable", "Running cannot be added."),
        ("icons_dll", "VVFP Origins Icons.dll"),
        ("show_dialog_export", "ShowOriginsUpgradeMenuState"),
        ("show_result_export", "ShowOriginsVillageWideResult"),
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
        (
            "cure_message",
            "Cured sickness from %u villagers.\n"
            "Restored %u villagers to full health.",
        ),
        (
            "cure_nothing",
            "Everyone is at full health already. No villagers are sick. "
            "No tech points have been deducted.",
        ),
        (
            "collections_completed",
            "All four collections are now complete.",
        ),
        (
            "collections_reset",
            "All collections have been reset to empty.",
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
            push 0
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

            cmp ebx, 3
            jb preflight
            cmp ebx, 5
            jae preflight
            cmp ebx, 4
            je maybe_remove_food
            test dword ptr [0x5824D0], 1
            jz preflight
            and dword ptr [0x5824D0], 0xFFFFFFFE
            mov eax, 0x{s['removed']:X}
            jmp show_status
        maybe_remove_food:
            test dword ptr [0x5824D0], 2
            jz preflight
            and dword ptr [0x5824D0], 0xFFFFFFFD
            mov eax, 0x{s['removed']:X}
            jmp show_status

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
            mov ecx, 0x59E110
            call 0x45E8F0
            mov ecx, 147
            cmp dword ptr [0x42883A], 0x100
            jne barrel_limit_ready
            mov ecx, 253
        barrel_limit_ready:
            cmp eax, ecx
            jbe charge
            mov eax, 0x{s['population_capacity']:X}
            jmp show_status

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
            jmp success

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
            jmp success

        do_barrel:
            call 0x419AC0
            mov eax, dword ptr [0x4B3D5C]
            test eax, eax
            je success
            sub esp, 0x868
            lea ebp, [esp + 0xF0]
            push eax
            lea ecx, [ebp + 4]
            call 0x4192F0
            cmp byte ptr [ebp + 0x4C], 0
            je barrel_cleanup
            push 0
            push esi
            call 0x401AF0
            mov byte ptr [0x4B3C75], 1
        barrel_cleanup:
            mov ecx, ebp
            call 0x418460
            add esp, 0x868
            jmp success

        do_complete_collections:
            call 0x{COLLECTIONS_COMPLETE_VA:X}
            jmp menu_done

        do_reset_collections:
            call 0x{COLLECTIONS_RESET_VA:X}
            jmp menu_done

        do_tech_doubler:
            or dword ptr [0x5824D0], 1
            jmp success
        do_food_doubler:
            or dword ptr [0x5824D0], 2
        success:
            mov eax, 0x{s['purchased']:X}
            jmp show_status
        insufficient:
            mov eax, 0x{s['not_enough']:X}
            jmp show_status
        show_status:
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
            mov eax, 0x{s['running_unavailable']:X}
            jmp detail_status

        running_already:
            mov eax, 0x{s['running_unavailable']:X}
            jmp detail_status

        detail_charge:
            mov eax, dword ptr [0x{s['detail_costs']:X} + ebx*4]
            cmp dword ptr [0x582644], eax
            jb detail_insufficient
            sub dword ptr [0x582644], eax
            cmp ebx, 0
            je detail_youth
            cmp ebx, 1
            je detail_mastery
            cmp ebx, 2
            je detail_running
            cmp ebx, 4
            je do_change_appearance
            mov eax, 360
            jmp detail_set_age

        do_change_appearance:
            # The 5,000-tech charge was already applied by detail_charge above.
            # Queue the appearance chooser for the selected villager, then close
            # the Villager Upgrades menu (detail_done) so the detail-screen
            # update loop regains control and opens the native chooser.
            call 0x{CHANGE_APPEARANCE_VA:X}
            jmp detail_done

        detail_youth:
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
            je detail_success
            add dword ptr [edx + 0xE8C], ecx
            jmp detail_success

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
            jz detail_success
            push esi
            call 0x462500
            jmp detail_success
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
            mov eax, 0x{s['running_unavailable']:X}
            jmp detail_status
        running_store_like:
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

    cure_code = assemble(
        f"""
            cmp ebx, 5
            je cure_all
            cmp ebx, 6
            jae village_wide
            or dword ptr [0x5824D0], 2
            ret
        village_wide:
            push ebx
            push ebp
            push ecx
            push edx
            push esi
            push edi
            mov eax, ebx
            mov ecx, 0x59E124
            mov edx, dword ptr [0x42883A]
            call 0x{VILLAGE_WIDE_ENTRY_VA:X}
            mov ebp, eax
            mov edi, edx
            mov esi, ecx
            mov eax, 0x{s['show_result_export']:X}
            push 0x{s['icons_dll']:X}
            call dword ptr [0x47C124]
            test eax, eax
            je village_result_done
            push 0x{s['show_result_export']:X}
            push eax
            call dword ptr [0x47C128]
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
            # wsprintfA(buffer, "Cured sickness from %u villagers.\\nRestored
            # %u villagers to full health.", ebp, ebx) then show it.
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
            push ebx
            push ebp
            push 0x{s['cure_message']:X}
            lea eax, [esp + 0xC]
            push eax
            call edx
            add esp, 0x10
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
    preflight_source = f"""
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
            call dword ptr [0x47C124]
            test eax, eax
            je preflight_invalid
            push 0x{s['show_result_export']:X}
            push eax
            call dword ptr [0x47C128]
            test eax, eax
            je preflight_invalid
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
    # head+body chooser (ShowVV3AppearanceChooser) for the selected villager
    # and, on OK, writes the chosen head (+0xDF0) and body (+0xDF4).  The DLL
    # only previews the extracted atlas strips and returns the chosen indices;
    # this cave owns the record writes.  edx = the validated selected record on
    # entry; head/body are staged in two stack locals passed by pointer.  The
    # 5,000-tech charge was applied by detail_charge above; Cancel/close leaves
    # the record unchanged.
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
            lea ecx, [esp + 4]
            lea edx, [esp]
            push ecx
            push edx
            push dword ptr [esi + 0xDC4]
            push dword ptr [esi + 0xDC8]
            call eax
            test eax, eax
            je ca_done
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
    # array and broadcast a refresh (0x293) so the Collections screen redraws.
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
        "make the mapped padding executable and writable for the Origins payload state",
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

    rendered = bytearray(original)
    for item in patches:
        offset = int(item["offset"], 16)
        replacement = bytes.fromhex(item["after"])
        rendered[offset : offset + len(replacement)] = replacement
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
