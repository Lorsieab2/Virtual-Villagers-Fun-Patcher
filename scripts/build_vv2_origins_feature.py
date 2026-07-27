"""Assemble the exact-build VV2 Origins-exclusive feature patch."""

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
    / "Virtual Villagers - The Lost Children.exe"
)
OUT_DIR = ROOT / "research" / "vv2-origins"
OUT_EXE = OUT_DIR / "Virtual Villagers - The Lost Children - Origins Research.exe"
OUT_JSON = OUT_DIR / "vv2-origins-feature-patches.json"
MANIFEST_JSON = ROOT / "data" / "vv2_origins_feature.json"

sys.path.insert(0, str(ROOT / ".tools" / "keystone"))
sys.path.insert(0, str(ROOT / ".tools" / "keystone-runtime"))
from keystone import KS_ARCH_X86, KS_MODE_32, Ks  # noqa: E402


IMAGE_BASE = 0x400000
PAYLOAD_FILE_OFFSET = 0x943A8
PAYLOAD_VA = IMAGE_BASE + PAYLOAD_FILE_OFFSET
PAYLOAD_SIZE = 0xC58
STRINGS_OFFSET = 0xA00
STRINGS_VA = PAYLOAD_VA + STRINGS_OFFSET
HEAL_CAVE_FILE_OFFSET = 0x9A004
CURE_ENTRY_FILE_OFFSET = 0x9A530
CURE_ENTRY_VA = IMAGE_BASE + CURE_ENTRY_FILE_OFFSET
HEAL_CAVE_VA = CURE_ENTRY_VA
VILLAGE_WIDE_SIGNATURE_VA = IMAGE_BASE + 0x9A180
VILLAGE_WIDE_ENTRY_VA = IMAGE_BASE + 0x9A1A0
VILLAGE_PREFLIGHT_FILE_OFFSET = 0x9A009
VILLAGE_PREFLIGHT_VA = IMAGE_BASE + VILLAGE_PREFLIGHT_FILE_OFFSET
RUNNING_PREFERENCE_ID = 38  # exact-build preference-table evidence: 0x8B808

# Exact caller-return addresses proven by the VV2 stock executable audit.  The
# wrappers compare the immediate caller return address so Island Event and Gong
# outcomes remain byte-for-byte native while ordinary positive awards can still
# use the save-scoped doubler.
TECH_DOUBLER_EXCLUDED_RETURNS = (
    0x4205AC,
    0x434351,
    0x44EA32,
    0x44ED52,
    0x44F202,
)
FOOD_DOUBLER_EXCLUDED_RETURNS = (
    0x420AE9,
    0x433FC6,
    0x44E9C3,
    0x44EDB9,
    0x44F0D9,
)


def caller_blacklist_asm(addresses: tuple[int, ...]) -> str:
    return "\n".join(
        f"cmp dword ptr [esp + 4], 0x{address:X}\n            je apply"
        for address in addresses
    )


def assemble(source: str, address: int) -> bytes:
    encoding, _ = Ks(KS_ARCH_X86, KS_MODE_32).asm(source, address)
    return bytes(encoding)


def rel32_jump(source_va: int, target_va: int) -> bytes:
    return b"\xE9" + int(target_va - source_va - 5).to_bytes(
        4, "little", signed=True
    )


def add_c_string(blob: bytearray, labels: dict[str, int], name: str, value: str) -> None:
    labels[name] = STRINGS_VA + len(blob)
    blob.extend(value.encode("ascii") + b"\0")


def main() -> None:
    original = STOCK.read_bytes()
    expected_sha256 = (
        "46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677"
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
    tech_constructor = PAYLOAD_VA + 0x030
    detail_handler = PAYLOAD_VA + 0x0C0
    detail_constructor = PAYLOAD_VA + 0x0F0
    show_dialog = PAYLOAD_VA + 0x180
    show_message = PAYLOAD_VA + 0x1D0
    tech_menu = PAYLOAD_VA + 0x240
    detail_menu = PAYLOAD_VA + 0x500
    tech_increment = PAYLOAD_VA + 0x800
    food_increment = PAYLOAD_VA + 0x880
    event_dispatch = PAYLOAD_VA + 0x940

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
            cmp dword ptr [esp + 8], 2
            jne original_handler
            call 0x{tech_menu:X}
            xor eax, eax
            ret 8
        original_handler:
            cmp dword ptr [esp + 4], 8
            jmp 0x4437C5
        """,
    )

    put(
        tech_constructor,
        f"""
            push 0x14
            call 0x467F83
            add esp, 4
            test eax, eax
            je constructor_done
            push 0
            push esi
            push 563
            push 138
            push 0x4763E8
            push 2
            mov ecx, eax
            call 0x4019D0
            mov edi, eax
            push 0
            push 0xFF555555
            push 0xFF555555
            push 0xFF000000
            push 0x{s['button_label']:X}
            mov ecx, edi
            call 0x4015D0
            push edi
            mov ecx, esi
            call 0x40B560
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
        detail_handler,
        f"""
            cmp dword ptr [esp + 4], 8
            jne original_handler
            cmp dword ptr [esp + 8], 6
            jne original_handler
            call 0x{detail_menu:X}
            xor eax, eax
            ret 8
        original_handler:
            cmp dword ptr [esp + 4], 8
            jmp 0x467725
        """,
    )

    put(
        detail_constructor,
        f"""
            push 0x14
            call 0x467F83
            add esp, 4
            test eax, eax
            je constructor_done
            push 0
            push esi
            push 563
            push 120
            push 0x4763E8
            push 6
            mov ecx, eax
            call 0x4019D0
            mov edi, eax
            push 0
            push 0xFF555555
            push 0xFF555555
            push 0xFF000000
            push 0x{s['button_label']:X}
            mov ecx, edi
            call 0x4015D0
            push edi
            mov ecx, esi
            call 0x40B560
        constructor_done:
            mov ecx, dword ptr [esp + 0x20]
            mov byte ptr [esi + 0x26], bl
            mov byte ptr [esi + 0x27], bl
            pop edi
            mov byte ptr [esi + 0x25], 1
            mov eax, esi
            pop esi
            pop ebx
            mov dword ptr fs:[0], ecx
            add esp, 0x20
            ret
        """,
    )

    put(
        show_dialog,
        f"""
            push ebx
            push esi
            push 0x{s['icons_dll']:X}
            call dword ptr [0x474010]
            test eax, eax
            je unavailable
            push 0x{s['show_dialog_export']:X}
            push eax
            call dword ptr [0x4740D4]
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
            call dword ptr [0x474010]
            test eax, eax
            je message_done
            push 0x{s['message_box_export']:X}
            push eax
            call dword ptr [0x4740D4]
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
        tech_menu,
        f"""
            push ebx
            push esi
            push edi
            push ebp
            mov esi, ecx
        menu_loop:
            mov edi, dword ptr [esi + 0x0C]
            xor eax, eax
            test dword ptr [edi + 0x2EAE8], 1
            jz tech_not_owned
            or eax, 8
        tech_not_owned:
            test dword ptr [edi + 0x2EAE8], 2
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
            test dword ptr [edi + 0x2EAE8], 1
            jz preflight
            and dword ptr [edi + 0x2EAE8], 0xFFFFFFFE
            mov eax, 0x{s['removed']:X}
            jmp show_status
        maybe_remove_food:
            test dword ptr [edi + 0x2EAE8], 2
            jz preflight
            and dword ptr [edi + 0x2EAE8], 0xFFFFFFFD
            mov eax, 0x{s['removed']:X}
            jmp show_status

        preflight:
            cmp ebx, 0
            jne maybe_barrel
            cmp dword ptr [edi + 0x2EB08], 999
            jne charge
            mov eax, 0x{s['paused']:X}
            jmp show_status
        maybe_barrel:
            cmp ebx, 2
            jne charge
            mov ecx, edi
            call 0x425860
            cmp eax, 253
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
            cmp dword ptr [edi + 0x2EADC], 1000000
            jb insufficient
            sub dword ptr [edi + 0x2EADC], 1000000
            jmp do_village_wide
        legacy_charge:
            mov eax, dword ptr [0x{s['tech_costs']:X} + ebx*4]
            cmp dword ptr [edi + 0x2EADC], eax
            jb insufficient
            sub dword ptr [edi + 0x2EADC], eax
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
            mov eax, dword ptr [edi + 0x2EB08]
            cmp eax, 3
            je time_apply
            cmp eax, 10
            je time_apply
            mov eax, 6
        time_apply:
            imul eax, eax, 3600
            sub dword ptr [0x4950F0], eax
            jmp success

        do_island_event:
            mov dword ptr [edi + 0x2EAE0], 0
            jmp success

        do_barrel:
            sub esp, 0x50D8
            mov ebp, esp
            push 0x7F4B1A2C
            push 2
            mov ecx, ebp
            call 0x4348E0
            push 0
            push esi
            mov ecx, ebp
            call 0x401AD0
            mov ecx, ebp
            call 0x433190
            add esp, 0x50D8
            jmp success

        do_tech_doubler:
            or dword ptr [edi + 0x2EAE8], 1
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
            mov eax, dword ptr [esi + 0x0C]
            mov ecx, dword ptr [eax + 0x304F0]
            cmp ecx, 0x100
            jae detail_done
            imul ecx, ecx, 0xE48C
            mov edx, dword ptr [esi + 0x10]
            add edx, ecx
            cmp byte ptr [edx + 0x30], 0
            je detail_done
            xor edi, edi
            cmp dword ptr [edx + 0x530], 100
            ja youth_not_done
            or edi, 1
        youth_not_done:
            cmp dword ptr [edx + 0x7E4], 90
            jl mastery_not_done
            cmp dword ptr [edx + 0x7E8], 90
            jl mastery_not_done
            cmp dword ptr [edx + 0x7EC], 90
            jl mastery_not_done
            cmp dword ptr [edx + 0x7F0], 90
            jl mastery_not_done
            cmp dword ptr [edx + 0x7F4], 90
            jl mastery_not_done
            or edi, 2
        mastery_not_done:
            xor ebp, ebp
            lea eax, [edx + 0x5F0]
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
            lea eax, [edx + 0x6E8]
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
            cmp dword ptr [edx + 0x530], 360
            jne age_not_done
            or edi, 8
        age_not_done:
            push edi
            push 1
            call 0x{show_dialog:X}
            cmp eax, -1
            je detail_done
            mov ebx, eax

            mov edi, dword ptr [esi + 0x0C]
            mov ecx, dword ptr [edi + 0x304F0]
            cmp ecx, 0x100
            jae detail_done
            imul ecx, ecx, 0xE48C
            mov edx, dword ptr [esi + 0x10]
            add edx, ecx
            cmp ebx, 2
            jne detail_charge
            lea eax, [edx + 0x5F0]
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
            cmp dword ptr [edi + 0x2EADC], eax
            jb detail_insufficient
            sub dword ptr [edi + 0x2EADC], eax
            cmp ebx, 0
            je detail_youth
            cmp ebx, 1
            je detail_mastery
            cmp ebx, 2
            je detail_running
            mov dword ptr [edx + 0x530], 360
            mov dword ptr [edx + 0x534], 360
            cmp dword ptr [edx + 0x540], 0
            je detail_success
            mov dword ptr [edx + 0x540], 318
            jmp detail_success

        detail_youth:
            mov eax, dword ptr [edx + 0x530]
            sub eax, 700
            cmp eax, 100
            jge youth_ready
            mov eax, 100
        youth_ready:
            mov dword ptr [edx + 0x530], eax
            cmp dword ptr [edx + 0x540], 0
            je youth_not_pregnant
            lea ecx, [eax - 1]
            mov dword ptr [edx + 0x534], ecx
            sub eax, 42
            mov dword ptr [edx + 0x540], eax
            jmp detail_success
        youth_not_pregnant:
            mov dword ptr [edx + 0x534], eax
            jmp detail_success

        detail_mastery:
            mov dword ptr [edx + 0x7E4], 90
            mov dword ptr [edx + 0x7E8], 90
            mov dword ptr [edx + 0x7EC], 90
            mov dword ptr [edx + 0x7F0], 90
            mov dword ptr [edx + 0x7F4], 90
            jmp detail_success

        detail_running:
            lea ecx, [edx + 0x5F0]
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
            lea ecx, [edx + 0x6E8]
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
        f"""
            push ebx
            mov ebx, ecx
            mov eax, dword ptr [esp + 8]
            test eax, eax
            jle apply
            {caller_blacklist_asm(TECH_DOUBLER_EXCLUDED_RETURNS)}
            test dword ptr [ebx + 0x2EAE8], 1
            jz apply
            shl dword ptr [esp + 8], 1
        apply:
            mov eax, dword ptr [esp + 8]
            add dword ptr [ebx + 0x2EADC], eax
            add dword ptr [ebx + 0x2E4FC], eax
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
            jle apply
            {caller_blacklist_asm(FOOD_DOUBLER_EXCLUDED_RETURNS)}
            test dword ptr [ebx + 0x2EAE8], 2
            jz apply
            shl dword ptr [esp + 8], 1
        apply:
            mov eax, dword ptr [esp + 8]
            add dword ptr [ebx + 0x2EAA4], eax
            add dword ptr [ebx + 0x2E504], eax
            pop ebx
            ret 4
        """,
    )

    put(
        event_dispatch,
        """
            cmp dword ptr [esp + 8], 0x7F4B1A2C
            jne original
            push 10
            push 21
            call 0x433600
            ret 8
        original:
            sub esp, 8
            mov eax, dword ptr [esp + 0x0C]
            jmp 0x434577
        """,
    )

    payload = code + strings
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
            or dword ptr [edi + 0x2EAE8], 2
            ret
        village_wide:
            push ebx
            push ebp
            push ecx
            push edx
            push esi
            push edi
            mov eax, ebx
            mov ecx, dword ptr [esi + 0x10]
            mov edx, 256
            call 0x{VILLAGE_WIDE_ENTRY_VA:X}
            mov ebp, eax
            mov edi, edx
            mov esi, ecx
            push 0x{s['show_result_export']:X}
            push 0x{s['icons_dll']:X}
            call dword ptr [0x474010]
            test eax, eax
            je village_result_done
            push 0x{s['show_result_export']:X}
            push eax
            call dword ptr [0x4740D4]
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
            mov edx, dword ptr [esi + 0x10]
            mov ecx, 256
        cure_loop:
            cmp byte ptr [edx + 0x30], 0
            je cure_next
            cmp dword ptr [edx + 0x52C], 0
            jle cure_next
            cmp dword ptr [edx + 0x53C], 0
            je cure_next
            mov dword ptr [edx + 0x53C], 0
            inc dword ptr [edi + 0x2E508]
            inc eax
        cure_next:
            add edx, 0xE48C
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
            call dword ptr [0x474010]
            test eax, eax
            je preflight_invalid
            push 0x{s['show_result_export']:X}
            push eax
            call dword ptr [0x4740D4]
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
        b"\0" * 5,
        rel32_jump(IMAGE_BASE + HEAL_CAVE_FILE_OFFSET, CURE_ENTRY_VA),
        "redirect the shared VV2 Cure/village-wide dispatch stub to its certified helper after the optional Origins reserve",
    )
    patch(
        CURE_ENTRY_FILE_OFFSET,
        b"\0" * len(cure_code),
        cure_code,
        "cure active VV2 villagers without changing health and increment People Cured",
    )
    patch(
        VILLAGE_PREFLIGHT_FILE_OFFSET,
        b"\0" * len(preflight_code),
        preflight_code,
        "validate the complete optional Origins header and result-export dependency before any village-wide charge",
    )

    patch(
        0x234,
        bytes.fromhex("40000040"),
        bytes.fromhex("40000060"),
        "make the mapped read-only padding executable for the Origins payload",
    )
    patch(
        0x26290,
        bytes.fromhex("8B44240401"),
        rel32_jump(0x426290, tech_increment),
        "double positive non-Island-Event tech awards when the current save owns the doubler",
    )
    patch(
        0x262B0,
        bytes.fromhex("8B44240401"),
        rel32_jump(0x4262B0, food_increment),
        "double positive non-Island-Event food awards when the current save owns the doubler",
    )
    patch(
        0x34570,
        bytes.fromhex("83EC088B44"),
        rel32_jump(0x434570, event_dispatch),
        "route the marked request to the native three-child Barrel of Babies result",
    )
    patch(
        0x435EF,
        bytes.fromhex("8B4C24205F"),
        rel32_jump(0x4435EF, tech_constructor),
        "append the stock-styled Origins Upgrades button to the Tech screen",
    )
    patch(
        0x437C0,
        bytes.fromhex("837C240408"),
        rel32_jump(0x4437C0, tech_handler),
        "route Tech-screen messages through the guarded Origins Upgrades handler",
    )
    patch(
        0x67624,
        bytes.fromhex("8B4C242088"),
        rel32_jump(0x467624, detail_constructor),
        "append the stock-styled Upgrades button to Villager Detail",
    )
    patch(
        0x67720,
        bytes.fromhex("837C240408"),
        rel32_jump(0x467720, detail_handler),
        "route Detail-screen messages through the guarded villager-upgrade handler",
    )
    patch(
        PAYLOAD_FILE_OFFSET,
        b"\0" * len(payload),
        bytes(payload),
        "install the VV2 Origins Tech and Villager upgrade menus and mechanics",
    )

    rendered = bytearray(original)
    for item in patches:
        offset = int(item["offset"], 16)
        replacement = bytes.fromhex(item["after"])
        rendered[offset : offset + len(replacement)] = replacement
    OUT_EXE.write_bytes(rendered)
    OUT_JSON.write_text(json.dumps(patches, indent=2) + "\n", encoding="utf-8")

    manifest = {
        "id": "vv2_enable_origins_exclusive_features",
        "game_id": "vv2",
        "running_preference_id": RUNNING_PREFERENCE_ID,
        "running_preference_evidence": {"source": "exact stock executable embedded preference table", "table_file_offset": "0x8B808", "entry_name": "running"},
        "name": "Enable Origins-Exclusive Features",
        "description": (
            "Inspired by the Virtual Villagers 1 mobile port where these exclusive "
            "Origins upgrades originated, this selected-upgrades port adds the icon-based "
            "Origins Upgrades screen with a Time Warp that "
            "advances exactly three displayed villager years, Island "
            "Event, the native Barrel of Babies event with a three-space reserved-"
            "population guard, and removable 500,000-tech-point Tech Point and Food "
            "Point Doublers, plus Cure all Villagers for 30,000 tech points. Cure all "
            "Villagers clears sickness from eligible active living records without changing "
            "health and increments People Cured once per sickness cleared, then displays the "
            "exact result `Cured X villagers`. Doubler ownership is confined to the current save. "
            "The certified composition applies after native collectible adjustments; Food Mastery "
            "presence is still being verified for this build. Island Event and Gong of Wonder outcomes remain native, including "
            "zero/negative and side-effect paths. The exact-build static provenance audit covers every "
            "positive Island Event and Gong food/tech writer callsite, including "
            "direct resource writes that bypass the wrappers. Runtime/player "
            "confirmation remains pending. Adds Villager Upgrades for "
            "Grant Youth, Grant Full Mastery, Grant Running, and Set Age to 18. "
            "Grant Running uses an available normal Likes slot, removes Running from "
            "the displayed villager's Dislikes, refuses without charging when all "
            "normal Like slots are occupied, and changes no movement-speed value, "
            "predicate, or other vanilla speed logic."
        ),
        "output_tag": "Origins Exclusive Features",
        "companion_files": [
            {
                "source": "assets/origins/VVFP Origins Icons.dll",
                "destination": "VVFP Origins Icons.dll",
                "sha256": hashlib.sha256(
                    (ROOT / "assets" / "origins" / "VVFP Origins Icons.dll").read_bytes()
                ).hexdigest().upper(),
            }
        ],
        "doubler_evidence": {
            "build": {
                "filename": "Virtual Villagers - The Lost Children.exe",
                "size": 724992,
                "sha256": "46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677",
            },
            "positive_tech_writer": "0x426290",
            "positive_food_writer": "0x4262B0",
            "collection_adjustment": "No separate global collection multiplier exists in either final writer; every eligible caller passes the final native signed delta, so the wrapper doubles that positive delta after all caller-side collection arithmetic.",
            "island_event_handlers": {
                "two_choice_handler": {
                    "function": "0x4204B0",
                    "tech_returns": ["0x4205AC"],
                    "food_returns": ["0x420AE9"],
                    "direct_resource_paths": ["direct +3000 tech result and deductions/caps bypass the positive writers"],
                },
                "single_result_dispatcher": {
                    "function": "0x433600",
                    "tech_returns": ["0x434351"],
                    "food_returns": ["0x433FC6"],
                    "direct_resource_paths": ["losses, caps, halves, resets, and unrelated resources bypass positive writers"],
                },
            },
            "gong_of_wonder": {
                "function": "0x44E8A0",
                "registered_action": 164,
                "invoked_by": "0x461B10",
                "tech_returns": ["0x44EA32", "0x44ED52", "0x44F202"],
                "food_returns": ["0x44E9C3", "0x44EDB9", "0x44F0D9"],
                "direct_resource_paths": ["negative tech and reset/zero outcomes bypass positive writers"],
            },
            "tech_blacklist_returns": [
                "0x4205AC", "0x434351", "0x44EA32", "0x44ED52", "0x44F202"
            ],
            "food_blacklist_returns": [
                "0x420AE9", "0x433FC6", "0x44E9C3", "0x44EDB9", "0x44F0D9"
            ],
            "direct_call_inventory": {
                "tech": [
                    "0x4205A7/0x4205AC", "0x43434C/0x434351", "0x4385E1/0x4385E6",
                    "0x438741/0x438746", "0x4388A1/0x4388A6", "0x438A9B/0x438AA0",
                    "0x438C7B/0x438C80", "0x438E5B/0x438E60", "0x44EA2D/0x44EA32",
                    "0x44ED4D/0x44ED52", "0x44F1FD/0x44F202", "0x46345C/0x463461",
                    "0x463468/0x46346D", "0x463474/0x463479", "0x463737/0x46373C",
                    "0x4637C0/0x4637C5", "0x463809/0x46380E"
                ],
                "food": [
                    "0x420AE4/0x420AE9", "0x433FC1/0x433FC6", "0x438293/0x438298",
                    "0x438371/0x438376", "0x438445/0x43844A", "0x44E9BE/0x44E9C3",
                    "0x44EDB4/0x44EDB9", "0x44F0D4/0x44F0D9", "0x463198/0x46319D",
                    "0x463259/0x46325E", "0x463312/0x463317", "0x463364/0x463369",
                    "0x4633CD/0x4633D2"
                ],
                "e9_tail_jumps_to_writers": 0,
            },
            "hook_status": "GO: exact-build static provenance proof complete for all positive Island Event and Gong writer callsites; runtime/player confirmation pending",
        },
        "doubler_composition_contract": {
            "stacking": [
                "every exact-build collectible/collection effect that increases tech-point gain",
                "native Food Mastery technology adjustment",
            ],
            "exclusions": ["Island Event outcomes", "Gong of Wonder outcomes"],
            "food_mastery_status": "pending exact-build verification; no cross-game assumption",
            "status": "GO: exact-build static provenance covers the certified positive writer paths; runtime/player confirmation pending",
        },
        "patches": patches,
    }
    MANIFEST_JSON.write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    used = max(index for index, value in enumerate(code) if value) + 1
    print(f"code bytes used: {used:#x}/{STRINGS_OFFSET:#x}")
    print(f"string bytes used: {len(strings):#x}/{PAYLOAD_SIZE - STRINGS_OFFSET:#x}")
    print(OUT_JSON)
    print(MANIFEST_JSON)
    print(OUT_EXE)


if __name__ == "__main__":
    main()
