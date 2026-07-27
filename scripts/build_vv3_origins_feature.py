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
COMPANION = ROOT / "assets" / "origins" / "VVFP Origins Icons.dll"

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
VILLAGE_WIDE_SIGNATURE_VA = IMAGE_BASE + 0x7B820
VILLAGE_WIDE_ENTRY_VA = IMAGE_BASE + 0x7B840
VILLAGE_PREFLIGHT_FILE_OFFSET = 0x7B7A0
VILLAGE_PREFLIGHT_VA = IMAGE_BASE + VILLAGE_PREFLIGHT_FILE_OFFSET
RUNNING_PREFERENCE_ID = 38  # exact-build preference-table evidence: 0x97488
DETAIL_BUTTON_PTR = PAYLOAD_VA + 0xBF0
DETAIL_BUTTON_ID = 6


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
        ("cure_all", "Cure all Villagers"),
    ):
        add_c_string(strings, s, name, value)

    while len(strings) % 4:
        strings.append(0)
    s["tech_costs"] = STRINGS_VA + len(strings)
    for value in (50000, 30000, 75000, 500000, 500000, 30000):
        strings.extend(value.to_bytes(4, "little"))
    s["detail_costs"] = STRINGS_VA + len(strings)
    for value in (50000, 100000, 40000, 50000):
        strings.extend(value.to_bytes(4, "little"))
    if len(strings) > PAYLOAD_SIZE - STRINGS_OFFSET:
        raise RuntimeError(
            f"string/data block is too large: {len(strings):#x}/"
            f"{PAYLOAD_SIZE - STRINGS_OFFSET:#x}"
        )

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
            cmp dword ptr [esp + 4], 8
            jne original_handler
            cmp dword ptr [esp + 8], 15
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
            push 15
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
            cmp ebx, 5
            je do_cure
            call 0x{HEAL_CAVE_VA:X}
            nop
            jmp success

        do_cure:
            call 0x{HEAL_CAVE_VA:X}
            jmp menu_loop

        do_village_wide:
            call 0x{HEAL_CAVE_VA:X}
            jmp success

        do_time_warp:
            mov eax, dword ptr [edi + ebp + 0x12F20]
            cmp eax, 3
            je time_apply
            cmp eax, 10
            je time_apply
            mov eax, 6
        time_apply:
            imul eax, eax, 3600
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

        do_tech_doubler:
            or dword ptr [0x5824D0], 1
        success:
            mov eax, 0x{s['purchased']:X}
            jmp show_status
        insufficient:
            mov eax, 0x{s['not_enough']:X}
        show_status:
            push eax
            push 0x{s['tech_title']:X}
            call 0x{show_message:X}
            jmp menu_loop
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
            cmp dword ptr [edx + 0xEAC], 90
            jl mastery_not_done
            cmp dword ptr [edx + 0xEB0], 90
            jl mastery_not_done
            cmp dword ptr [edx + 0xEB4], 90
            jl mastery_not_done
            cmp dword ptr [edx + 0xEB8], 90
            jl mastery_not_done
            cmp dword ptr [edx + 0xEBC], 90
            jl mastery_not_done
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
            test ebp, 4
            jnz running_check_done
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
            je detail_charge
            cmp dword ptr [eax], -1
            je detail_charge
            add eax, 4
            dec ecx
            jne running_preflight
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
            mov eax, 360
            jmp detail_set_age

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
            mov dword ptr [edx + 0xEAC], 90
            mov dword ptr [edx + 0xEB0], 90
            mov dword ptr [edx + 0xEB4], 90
            mov dword ptr [edx + 0xEB8], 90
            mov dword ptr [edx + 0xEBC], 90
            jmp detail_success

        detail_running:
            lea ecx, [edx + 0xFB4]
            mov eax, 3
        running_find_like:
            cmp dword ptr [ecx], {RUNNING_PREFERENCE_ID}
            je running_remove_dislikes
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

    payload = code + strings
    if len(payload) > PAYLOAD_SIZE:
        raise RuntimeError(f"payload too large: {len(payload):#x}/{PAYLOAD_SIZE:#x}")

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
            push 0x{s['show_result_export']:X}
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
            xor eax, eax
            mov edx, 0x59E124
            mov ecx, dword ptr [0x42883A]
        cure_loop:
            cmp byte ptr [edx + 0xF10], 0
            je cure_next
            cmp dword ptr [edx + 0xE78], 0
            jle cure_next
            cmp byte ptr [edx + 0xE89], 0
            je cure_next
            mov byte ptr [edx + 0xE89], 0
            inc dword ptr [edi + 0x4FC]
            inc eax
        cure_next:
            add edx, 0x1F8C
            dec ecx
            jne cure_loop
            mov ebp, eax
            sub esp, 40
            mov dword ptr [esp], 0x65727543
            mov word ptr [esp + 4], 0x2064
            lea edi, [esp + 6]
            test ebp, ebp
            jnz cure_digits
            mov byte ptr [edi], 0x30
            inc edi
            jmp cure_suffix
        cure_digits:
            lea esi, [esp + 30]
            mov eax, ebp
            mov ebx, 10
            xor ecx, ecx
        cure_digit_loop:
            xor edx, edx
            div ebx
            add dl, 0x30
            dec esi
            mov byte ptr [esi], dl
            inc ecx
            test eax, eax
            jne cure_digit_loop
        cure_copy_loop:
            mov dl, byte ptr [esi]
            mov byte ptr [edi], dl
            inc esi
            inc edi
            dec ecx
            jne cure_copy_loop
        cure_suffix:
            mov byte ptr [edi], 0x20
            mov dword ptr [edi + 1], 0x6C6C6976
            mov dword ptr [edi + 5], 0x72656761
            mov word ptr [edi + 9], 0x0073
            lea eax, [esp]
            push eax
            push 0x{s['tech_title']:X}
            call 0x{show_message:X}
            add esp, 8
            add esp, 40
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
            push 0x{s['show_result_export']:X}
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
        """,
        VILLAGE_PREFLIGHT_VA,
    )
    patch(
        HEAL_CAVE_FILE_OFFSET,
        b"\0" * len(cure_code),
        cure_code,
        "cure active VV3 villagers without changing health and increment People Cured",
    )
    patch(
        VILLAGE_PREFLIGHT_FILE_OFFSET,
        b"\0" * len(preflight_code),
        preflight_code,
        "validate the complete optional Origins header and result-export dependency before any village-wide charge",
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
        "double positive non-Island-Event food awards when this save owns the doubler",
    )
    patch(
        0x27130,
        bytes.fromhex("8B4424048B11"),
        rel32_jump(0x427130, tech_increment, 6),
        "double positive non-Island-Event tech awards when this save owns the doubler",
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
        "route Tech-screen command 15 through the guarded Origins handler",
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
        "description": (
            "Inspired by the Virtual Villagers 1 mobile port where these exclusive "
            "Origins upgrades originated, this selected-upgrades port adds the icon-based "
            "Origins Upgrades screen with Time Warp, Island "
            "Event, the native Another One of Those Barrels event with a dynamic "
            "three-space 150/256-record guard, and removable 500,000-tech-point "
            "Tech Point and Food Point Doublers, plus Cure all Villagers for 30,000 "
            "tech points. Cure all Villagers clears sickness from eligible active living "
            "records without changing health and increments People Cured once per sickness "
            "cleared, then displays the exact result `Cured X villagers`. Time Warp advances every villager "
            "by exactly 3 displayed years at every active game speed; the required "
            "wall-clock shift is 3 hours at half speed, 6 hours at normal speed, "
            "and 10 hours at double speed. Doubler ownership is confined to the "
            "current save, and Island Event awards are not multiplied. Adds "
            "Villager Upgrades for Grant Youth, Grant Full Mastery, Grant Running, "
            "and Set Age to 18. Grant Running only uses an available normal Likes "
            "slot on the displayed villager and removes Running from that villager's "
            "Dislikes; it refuses without charging when all normal Like slots are "
            "occupied and does not alter any movement behavior or speed value."
        ),
        "output_tag": "Origins Exclusive Features",
        "companion_files": [
            {
                "source": "assets/origins/VVFP Origins Icons.dll",
                "destination": "VVFP Origins Icons.dll",
                "sha256": companion_hash,
            }
        ],
        "doubler_evidence": {
            "positive_tech_writer": "0x427130",
            "positive_food_writer": "0x4263F0",
            "collection_adjustment": "not independently recorded; no exact callsite claim",
            "island_event_producers": ["dispatcher 0x458DB0-0x45943F"],
            "hook_status": "pending exact all-path provenance audit",
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
