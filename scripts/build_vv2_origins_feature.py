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
# The Origins payload occupies the final 0xC58 bytes of .rdata.  Its raw
# offset and RVA are equal, but the stock .rdata VirtualSize stops exactly at
# this payload start; the PE-header patches below extend that mapped range and
# mark it executable.
PAYLOAD_VA = IMAGE_BASE + PAYLOAD_FILE_OFFSET
PAYLOAD_SIZE = 0xC58
STRINGS_OFFSET = 0x9E0
STRINGS_VA = PAYLOAD_VA + STRINGS_OFFSET
# .shr is stored at raw 0x9A000 but is mapped at RVA 0x9C000.  Never derive a
# runtime VA by adding IMAGE_BASE to a raw file offset: that was the cause of
# the Tech-screen preflight access violation at raw 0x9A009.
SHR_FILE_OFFSET = 0x9A000
SHR_RVA = 0x9C000
HEAL_CAVE_FILE_OFFSET = 0x9A004
CURE_PREFLIGHT_FILE_OFFSET = 0x9A300
CURE_PREFLIGHT_VA = IMAGE_BASE + SHR_RVA + (
    CURE_PREFLIGHT_FILE_OFFSET - SHR_FILE_OFFSET
)
DETAIL_PREFLIGHT_FILE_OFFSET = 0x9A380
DETAIL_PREFLIGHT_VA = IMAGE_BASE + SHR_RVA + (
    DETAIL_PREFLIGHT_FILE_OFFSET - SHR_FILE_OFFSET
)
CURE_ENTRY_FILE_OFFSET = 0x9A530
CURE_ENTRY_VA = IMAGE_BASE + SHR_RVA + (CURE_ENTRY_FILE_OFFSET - SHR_FILE_OFFSET)
HEAL_CAVE_VA = CURE_ENTRY_VA
# The optional village-wide payload follows the base VV2 Origins helpers in
# the .shr reserve at raw 0x9A800.  Its runtime address must use the mapped
# .shr RVA, not IMAGE_BASE + raw file offset.
VILLAGE_WIDE_SIGNATURE_VA = IMAGE_BASE + SHR_RVA + 0x800
VILLAGE_WIDE_ENTRY_VA = IMAGE_BASE + SHR_RVA + 0x820
VILLAGE_PREFLIGHT_FILE_OFFSET = 0x9A009
VILLAGE_PREFLIGHT_VA = IMAGE_BASE + SHR_RVA + (VILLAGE_PREFLIGHT_FILE_OFFSET - SHR_FILE_OFFSET)
BARREL_PENDING_FILE_OFFSET = 0x9A700
BARREL_PENDING_VA = IMAGE_BASE + SHR_RVA + (BARREL_PENDING_FILE_OFFSET - SHR_FILE_OFFSET)
BARREL_CLOSE_HELPER_FILE_OFFSET = 0x9A710
BARREL_CLOSE_HELPER_VA = IMAGE_BASE + SHR_RVA + (
    BARREL_CLOSE_HELPER_FILE_OFFSET - SHR_FILE_OFFSET
)
BARREL_CLOSE_HELPER_CODE = bytes.fromhex(
    "8B4E146A4BE8F628FAFF6A0089F1E8CDF0F6FF8B460C"
    "C7807004030001000000803D00C74900017507C60500C7490002"
    "E9B570FAFF"
)
BARREL_MAIN_HELPER_FILE_OFFSET = 0x9A780
BARREL_MAIN_HELPER_VA = IMAGE_BASE + SHR_RVA + (
    BARREL_MAIN_HELPER_FILE_OFFSET - SHR_FILE_OFFSET
)
BARREL_MAIN_HELPER_CODE = bytes.fromhex(
    "803D00C74900027536C60500C749000081ECD8500000682C1A4B7F"
    "6A028D4C2408E83A81F9FF6A00568D4C2408E81E53F6FF89E1E8"
    "D769F9FF81C4D850000089F9E83A6AF6FFE92A22F9FF"
)
RUNNING_PREFERENCE_ID = 38  # exact-build preference-table evidence: 0x8B808

# Exact caller-return addresses proven by the VV2 stock executable audit.  The
# wrappers compare the immediate caller return address so Island Event, Gong,
# and duplicate-collectible tech awards remain byte-for-byte native while
# ordinary positive awards can still use the save-scoped doubler.
TECH_DOUBLER_EXCLUDED_RETURNS = (
    0x4205AC,
    0x434351,
    0x44EA32,
    0x44ED52,
    0x44F202,
    0x463461,
    0x46346D,
    0x463479,
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
        ("mastery_failed", "Full Mastery could not be completed."),
        ("paused", "Time Warp is unavailable while the game is paused."),
        (
            "population_capacity",
            "The village population is already close to its max. No tech points have been deducted.",
        ),
        (
            "permanent_warning",
            "This upgrade makes permanent changes to your village. Are you sure you want to continue?",
        ),
        ("running_unavailable", "Running cannot be added."),
        ("running_granted", "All villagers like running."),
        (
            "running_no_change",
            "No changes were needed. No tech points have been deducted.",
        ),
        ("icons_dll", "VVFP VV2 Origins Icons.dll"),
        ("show_dialog_export", "ShowOriginsUpgradeMenuState"),
        ("show_result_export", "ShowOriginsVillageWideResult"),
        ("user32_dll", "USER32.dll"),
        ("message_box_export", "MessageBoxA"),
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
    s["vv2_skill_codes"] = STRINGS_VA + len(strings)
    for value in (2, 5, 1, 3, 4):
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
    confirm_dialog = PAYLOAD_VA + 0x210
    # Keep a full gap after the confirmation helper (0x210..0x251).
    tech_menu = PAYLOAD_VA + 0x260
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
            push 140
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
            or dword ptr [esp + 0x10], 0xA01C0
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
        confirm_dialog,
        f"""
            push ebx
            push esi
            push 0x{s['user32_dll']:X}
            call dword ptr [0x474010]
            test eax, eax
            je confirm_done
            push 0x{s['message_box_export']:X}
            push eax
            call dword ptr [0x4740D4]
            test eax, eax
            je confirm_done
            push 1
            push 0x{s['tech_title']:X}
            push 0x{s['permanent_warning']:X}
            push 0
            call eax
            cmp eax, 1
            sete al
            movzx eax, al
            jmp confirm_return
        confirm_done:
            xor eax, eax
        confirm_return:
            pop esi
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

            cmp ebx, 0
            je confirm_tech_purchase
            cmp ebx, 1
            je confirm_tech_purchase
            cmp ebx, 2
            je confirm_tech_purchase
            cmp ebx, 3
            je confirm_tech_purchase
            cmp ebx, 4
            je confirm_tech_purchase
            cmp ebx, 5
            je confirm_tech_purchase
            cmp ebx, 6
            jne tech_purchase_ready
        confirm_tech_purchase:
            call 0x{confirm_dialog:X}
            test eax, eax
            jz menu_loop
        tech_purchase_ready:
            # The menu/confirmation helpers may use EDI internally.  The
            # stock handler reacquires its village object from [ESI+0x0C]
            # before each native read/write; do the same before any command
            # reaches the capacity, charge, or removal paths.
            mov edi, dword ptr [esi + 0x0C]

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
            jmp barrel_capacity_preflight

        charge:
            cmp ebx, 6
            jb legacy_charge
            cmp ebx, 8
            ja unsupported_village_command
            call 0x{VILLAGE_PREFLIGHT_VA:X}
            cmp eax, 2
            je village_no_change
            cmp eax, 1
            jne menu_loop
            cmp dword ptr [edi + 0x2EADC], 1000000
            jb insufficient
            sub dword ptr [edi + 0x2EADC], 1000000
            jmp do_village_wide
        village_no_change:
            mov eax, 0x{s['running_no_change']:X}
            jmp show_status
        unsupported_village_command:
            mov eax, 0x{s['running_unavailable']:X}
            jmp show_status
        legacy_charge:
            cmp ebx, 5
            jne legacy_charge_ready
            call 0x{CURE_PREFLIGHT_VA:X}
            test eax, eax
            jnz legacy_charge_ready
            mov eax, 0x{s['running_no_change']:X}
            jmp show_status
        legacy_charge_ready:
            mov eax, dword ptr [0x{s['tech_costs']:X} + ebx*4]
            cmp ebx, 2
            je barrel_capacity_preflight
            cmp dword ptr [edi + 0x2EADC], eax
            jb insufficient
            sub dword ptr [edi + 0x2EADC], eax
            cmp ebx, 0
            je do_time_warp
            cmp ebx, 1
            je do_island_event
            cmp ebx, 2
            je barrel_capacity_preflight
            cmp ebx, 3
            je do_tech_doubler
            cmp ebx, 4
            je do_food_doubler
            cmp ebx, 5
            je do_cure
            call 0x{HEAL_CAVE_VA:X}
            nop
            jmp success

        barrel_capacity_preflight:
            cmp byte ptr [0x{BARREL_PENDING_VA:X}], 0
            jne menu_done
            sub esp, 0x50D8
            mov ebp, esp
            # The Tech menu's EDI is already the VV2 state object loaded from
            # [ESI+0x0C], matching stock state-local callers of sub_425860.
            # Its first dereference is [ECX+0x305A4], so reject an
            # uninitialized record-pool chain before calling the helper.
            mov ecx, edi
            test ecx, ecx
            jz barrel_capacity_unavailable
            cmp dword ptr [ecx + 0x305A4], 0
            jz barrel_capacity_unavailable
            call 0x425860
            cmp eax, 254
            jae barrel_capacity_low
            mov eax, dword ptr [0x{s['tech_costs']:X} + ebx*4]
            cmp dword ptr [edi + 0x2EADC], eax
            jb barrel_insufficient
            sub dword ptr [edi + 0x2EADC], eax
            add esp, 0x50D8
            mov eax, 0x{s['purchased']:X}
            push eax
            push 0x{s['tech_title']:X}
            call 0x{show_message:X}
            mov byte ptr [0x{BARREL_PENDING_VA:X}], 1
            jmp menu_done
        barrel_capacity_low:
            add esp, 0x50D8
            mov eax, 0x{s['population_capacity']:X}
            jmp show_status
        barrel_insufficient:
            add esp, 0x50D8
            mov eax, 0x{s['not_enough']:X}
            jmp show_status
        barrel_capacity_unavailable:
            add esp, 0x50D8
            mov eax, 0x{s['population_capacity']:X}
            jmp show_status

        do_cure:
            call 0x{HEAL_CAVE_VA:X}
            jmp menu_done

        do_village_wide:
            call 0x{HEAL_CAVE_VA:X}
            jmp menu_done

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

        do_tech_doubler:
            or dword ptr [edi + 0x2EAE8], 1
            jmp success
        do_food_doubler:
            or dword ptr [edi + 0x2EAE8], 2
        success:
            mov eax, 0x{s['purchased']:X}
            jmp show_status
        insufficient:
            mov eax, 0x{s['not_enough']:X}
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
            cmp dword ptr [edx + 0x7E4], 100
            jne mastery_not_done
            cmp dword ptr [edx + 0x7E8], 100
            jne mastery_not_done
            cmp dword ptr [edx + 0x7EC], 100
            jne mastery_not_done
            cmp dword ptr [edx + 0x7F0], 100
            jne mastery_not_done
            cmp dword ptr [edx + 0x7F4], 100
            jne mastery_not_done
            or edi, 2
        mastery_not_done:
            xor ebp, ebp
            lea eax, [edx + 0x5F0]
            mov ecx, 62
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
            mov ecx, 62
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

            cmp ebx, 3
            ja detail_purchase_ready
            call 0x{confirm_dialog:X}
            test eax, eax
            jz detail_loop
        detail_purchase_ready:

            mov edi, dword ptr [esi + 0x0C]
            mov ecx, dword ptr [edi + 0x304F0]
            cmp ecx, 0x100
            jae detail_done
            imul ecx, ecx, 0xE48C
            mov edx, dword ptr [esi + 0x10]
            add edx, ecx
            cmp byte ptr [edx + 0x30], 0
            je detail_done
            call 0x{DETAIL_PREFLIGHT_VA:X}
            test eax, eax
            jnz detail_charge
            mov eax, 0x{s['running_no_change']:X}
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
            mov ebx, edx
            mov eax, dword ptr [esi + 0x10]
            call 0x44F4E0
            test eax, eax
            jz detail_mastery_failed
            mov ebp, eax
            lea ecx, [ebp + 0x52C]
            cmp ecx, dword ptr [esi + 0x10]
            jne detail_mastery_failed
            mov esi, ebx
            xor ebx, ebx
        detail_mastery_loop:
            cmp dword ptr [esi + ebx*4 + 0x7E4], 100
            je detail_mastery_next
            mov eax, 100
            sub eax, dword ptr [esi + ebx*4 + 0x7E4]
            push eax
            mov eax, dword ptr [0x{s['vv2_skill_codes']:X} + ebx*4]
            push eax
            push dword ptr [edi + 0x304F0]
            lea ecx, [ebp + 0x52C]
            call 0x445430
        detail_mastery_next:
            inc ebx
            cmp ebx, 5
            jb detail_mastery_loop
            cmp dword ptr [esi + 0x7E4], 100
            jne detail_mastery_failed
            cmp dword ptr [esi + 0x7E8], 100
            jne detail_mastery_failed
            cmp dword ptr [esi + 0x7EC], 100
            jne detail_mastery_failed
            cmp dword ptr [esi + 0x7F0], 100
            jne detail_mastery_failed
            cmp dword ptr [esi + 0x7F4], 100
            jne detail_mastery_failed
            jmp detail_success
        detail_mastery_failed:
            mov eax, 0x{s['mastery_failed']:X}
            jmp detail_status

        detail_running:
            xor ebp, ebp
            xor edi, edi
            lea ecx, [edx + 0x5F0]
            mov eax, 62
        running_find_like:
            cmp dword ptr [ecx], {RUNNING_PREFERENCE_ID}
            jne running_check_empty
            or ebp, 1
        running_check_empty:
            cmp dword ptr [ecx], -1
            jne running_next_like
            test edi, edi
            jnz running_next_like
            mov edi, ecx
        running_next_like:
            add ecx, 4
            dec eax
            jne running_find_like
            test ebp, 1
            jnz detail_success
            test edi, edi
            jz detail_success
            mov dword ptr [edi], {RUNNING_PREFERENCE_ID}
        running_remove_dislikes:
            lea ecx, [edx + 0x6E8]
            mov eax, 62
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
            jb unsupported_village
            cmp ebx, 8
            ja unsupported_village
            jmp running_village
        unsupported_village:
            mov eax, 0x{s['running_unavailable']:X}
            push eax
            push 0x{s['tech_title']:X}
            call 0x{show_message:X}
            ret
        running_village:
            push ebx
            push ebp
            push ecx
            push edx
            push esi
            push edi
            mov eax, ebx
            call 0x44F4E0
            test eax, eax
            je village_wide_done
            lea ecx, [eax + 0x52C]
            mov eax, ebx
            mov edx, 256
            call 0x{VILLAGE_WIDE_ENTRY_VA:X}
            mov ebp, eax
            mov edi, edx
            mov esi, ecx
            cmp ebx, 6
            jne village_wide_status
            mov eax, 0x{s['show_result_export']:X}
            push 0x{s['icons_dll']:X}
            call dword ptr [0x474010]
            test eax, eax
            je village_wide_status
            push 0x{s['show_result_export']:X}
            push eax
            call dword ptr [0x4740D4]
            test eax, eax
            je village_wide_status
            push esi
            push edi
            push ebp
            push ebx
            call eax
            jmp village_wide_done
        village_wide_status:
            mov eax, 0x{s['purchased']:X}
            push eax
            push 0x{s['tech_title']:X}
            call 0x{show_message:X}
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
            xor eax, eax
            call 0x44F4E0
            test eax, eax
            je cure_format
            lea edx, [eax + 0x52C]
            xor eax, eax
            mov ecx, 256
        cure_loop:
            cmp byte ptr [edx + 0x30], 0
            je cure_next
            cmp dword ptr [edx + 0x52C], 0
            jle cure_next
            cmp byte ptr [edx + 0x558], 0
            jne cure_next
            xor ebx, ebx
            cmp dword ptr [edx + 0x52C], 100
            jge cure_health_done
            mov dword ptr [edx + 0x52C], 100
            mov ebx, 1
        cure_health_done:
            cmp dword ptr [edx + 0x53C], 0
            je cure_changed_check
            mov dword ptr [edx + 0x53C], 0
            inc dword ptr [edi + 0x2E508]
            mov ebx, 1
        cure_changed_check:
            test ebx, ebx
            jz cure_next
            inc eax
        cure_next:
            add edx, 0xE48C
            dec ecx
            jne cure_loop
        cure_format:
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
            mov eax, 0x{s['show_result_export']:X}
            push 0x{s['icons_dll']:X}
            call dword ptr [0x474010]
            test eax, eax
            je preflight_invalid
            push 0x{s['show_result_export']:X}
            push eax
            call dword ptr [0x4740D4]
            test eax, eax
            je preflight_invalid
            call 0x44F4E0
            test eax, eax
            je preflight_invalid
            lea edx, [eax + 0x52C]
            push ebx
            push ebp
            push ecx
            push edx
            push edi
            cmp ebx, 7
            je preflight_mastery
            cmp ebx, 8
            je preflight_age
            mov ecx, 256
        preflight_record:
            cmp byte ptr [edx + 0x30], 0
            je preflight_next_record
            cmp dword ptr [edx + 0x52C], 0
            jle preflight_next_record
            cmp byte ptr [edx + 0x558], 0
            jne preflight_next_record
            xor ebp, ebp
            lea edi, [edx + 0x5F0]
            mov ebx, 62
        preflight_likes:
            cmp dword ptr [edi], {RUNNING_PREFERENCE_ID}
            jne preflight_like_empty
            or ebp, 1
        preflight_like_empty:
            cmp dword ptr [edi], -1
            jne preflight_like_next
            or ebp, 2
        preflight_like_next:
            add edi, 4
            dec ebx
            jne preflight_likes
            lea edi, [edx + 0x6E8]
            mov ebx, 62
            test ebp, 1
            jnz preflight_dislike_scan
            test ebp, 2
            jz preflight_next_record
        preflight_dislike_scan:
            cmp dword ptr [edi], {RUNNING_PREFERENCE_ID}
            je preflight_change
            add edi, 4
            dec ebx
            jne preflight_dislike_scan
            test ebp, 1
            jnz preflight_next_record
            test ebp, 2
            jnz preflight_change
        preflight_mastery:
            mov ecx, 256
        preflight_mastery_record:
            cmp byte ptr [edx + 0x30], 0
            je preflight_mastery_next
            cmp dword ptr [edx + 0x52C], 0
            jle preflight_mastery_next
            cmp byte ptr [edx + 0x558], 0
            jne preflight_mastery_next
            cmp dword ptr [edx + 0x7E4], 100
            jne preflight_change
            cmp dword ptr [edx + 0x7E8], 100
            jne preflight_change
            cmp dword ptr [edx + 0x7EC], 100
            jne preflight_change
            cmp dword ptr [edx + 0x7F0], 100
            jne preflight_change
            cmp dword ptr [edx + 0x7F4], 100
            jne preflight_change
        preflight_mastery_next:
            add edx, 0xE48C
            dec ecx
            jne preflight_mastery_record
            jmp preflight_no_change
        preflight_age:
            mov ecx, 256
        preflight_age_record:
            cmp byte ptr [edx + 0x30], 0
            je preflight_age_next
            cmp dword ptr [edx + 0x52C], 0
            jle preflight_age_next
            cmp byte ptr [edx + 0x558], 0
            jne preflight_age_next
            cmp dword ptr [edx + 0x530], 360
            jne preflight_change
        preflight_age_next:
            add edx, 0xE48C
            dec ecx
            jne preflight_age_record
            jmp preflight_no_change
        preflight_next_record:
            add edx, 0xE48C
            dec ecx
            jne preflight_record
        preflight_no_change:
            pop edi
            pop edx
            pop ecx
            pop ebp
            pop ebx
            mov eax, 2
            ret
        preflight_change:
            pop edi
            pop edx
            pop ecx
            pop ebp
            pop ebx
            mov eax, 1
            ret
        preflight_invalid:
            xor eax, eax
            ret
        """,
        VILLAGE_PREFLIGHT_VA,
    )
    cure_preflight_code = assemble(
        """
            push ecx
            push edx
            call 0x44F4E0
            test eax, eax
            je cure_preflight_no_change
            lea edx, [eax + 0x52C]
            mov ecx, 256
        cure_preflight_record:
            cmp byte ptr [edx + 0x30], 0
            je cure_preflight_next
            cmp dword ptr [edx + 0x52C], 0
            jle cure_preflight_next
            cmp byte ptr [edx + 0x558], 0
            jne cure_preflight_next
            cmp dword ptr [edx + 0x52C], 100
            jl cure_preflight_change
            cmp dword ptr [edx + 0x53C], 0
            jne cure_preflight_change
        cure_preflight_next:
            add edx, 0xE48C
            dec ecx
            jne cure_preflight_record
        cure_preflight_no_change:
            pop edx
            pop ecx
            xor eax, eax
            ret
        cure_preflight_change:
            pop edx
            pop ecx
            mov eax, 1
            ret
        """,
        CURE_PREFLIGHT_VA,
    )
    detail_preflight_code = assemble(
        f"""
            push ecx
            push edx
            push edi
            push ebp
            cmp ebx, 0
            je detail_preflight_youth
            cmp ebx, 1
            je detail_preflight_mastery
            cmp ebx, 2
            je detail_preflight_running
            cmp ebx, 3
            je detail_preflight_age
            jmp detail_preflight_no_change

        detail_preflight_youth:
            mov ecx, dword ptr [edx + 0x530]
            mov eax, ecx
            sub eax, 700
            cmp eax, 100
            jge detail_preflight_youth_target
            mov eax, 100
        detail_preflight_youth_target:
            cmp ecx, eax
            jne detail_preflight_change
            cmp dword ptr [edx + 0x540], 0
            jne detail_preflight_youth_pregnant
            cmp dword ptr [edx + 0x534], eax
            jne detail_preflight_change
            jmp detail_preflight_no_change
        detail_preflight_youth_pregnant:
            lea ecx, [eax - 1]
            cmp dword ptr [edx + 0x534], ecx
            jne detail_preflight_change
            sub eax, 42
            cmp dword ptr [edx + 0x540], eax
            jne detail_preflight_change
            jmp detail_preflight_no_change

        detail_preflight_mastery:
            cmp dword ptr [edx + 0x52C], 0
            jle detail_preflight_no_change
            cmp byte ptr [edx + 0x558], 0
            jne detail_preflight_no_change
            cmp dword ptr [edx + 0x7E4], 100
            jne detail_preflight_change
            cmp dword ptr [edx + 0x7E8], 100
            jne detail_preflight_change
            cmp dword ptr [edx + 0x7EC], 100
            jne detail_preflight_change
            cmp dword ptr [edx + 0x7F0], 100
            jne detail_preflight_change
            cmp dword ptr [edx + 0x7F4], 100
            jne detail_preflight_change
            jmp detail_preflight_no_change

        detail_preflight_running:
            xor ebp, ebp
            lea edi, [edx + 0x5F0]
            mov ecx, 62
        detail_preflight_likes:
            cmp dword ptr [edi], {RUNNING_PREFERENCE_ID}
            jne detail_preflight_like_empty
            or ebp, 1
        detail_preflight_like_empty:
            cmp dword ptr [edi], -1
            jne detail_preflight_like_next
            or ebp, 2
        detail_preflight_like_next:
            add edi, 4
            dec ecx
            jne detail_preflight_likes
            test ebp, 1
            jnz detail_preflight_no_change
            test ebp, 2
            jz detail_preflight_no_change
            lea edi, [edx + 0x6E8]
            mov ecx, 62
        detail_preflight_dislike_scan:
            cmp dword ptr [edi], {RUNNING_PREFERENCE_ID}
            je detail_preflight_change
            add edi, 4
            dec ecx
            jne detail_preflight_dislike_scan
            jmp detail_preflight_change

        detail_preflight_age:
            cmp dword ptr [edx + 0x530], 360
            jne detail_preflight_change
            cmp dword ptr [edx + 0x534], 360
            jne detail_preflight_change
            mov eax, dword ptr [edx + 0x540]
            test eax, eax
            je detail_preflight_no_change
            cmp eax, 318
            jne detail_preflight_change
        detail_preflight_no_change:
            pop ebp
            pop edi
            pop edx
            pop ecx
            xor eax, eax
            ret
        detail_preflight_change:
            pop ebp
            pop edi
            pop edx
            pop ecx
            mov eax, 1
            ret
        """,
        DETAIL_PREFLIGHT_VA,
    )
    patch(
        HEAL_CAVE_FILE_OFFSET,
        b"\0" * 5,
        rel32_jump(
            IMAGE_BASE + SHR_RVA + (HEAL_CAVE_FILE_OFFSET - SHR_FILE_OFFSET),
            CURE_ENTRY_VA,
        ),
        "redirect the shared VV2 Cure/village-wide dispatch stub to its certified helper after the optional Origins reserve",
    )
    patch(
        CURE_ENTRY_FILE_OFFSET,
        b"\0" * len(cure_code),
        cure_code,
        "restore active living VV2 villagers below 80 health to 100, clear sickness, and increment People Cured when sickness is removed",
    )
    patch(
        VILLAGE_PREFLIGHT_FILE_OFFSET,
        b"\0" * len(preflight_code),
        preflight_code,
        "validate the optional Origins dependency and dry-scan all 256 living records and all 62 Like and Dislike slots before any village-wide Running charge",
    )
    patch(
        CURE_PREFLIGHT_FILE_OFFSET,
        b"\0" * len(cure_preflight_code),
        cure_preflight_code,
        "dry-scan all 256 active living records for low health or sickness before any Cure charge",
    )
    patch(
        DETAIL_PREFLIGHT_FILE_OFFSET,
        b"\0" * len(detail_preflight_code),
        detail_preflight_code,
        "recheck the selected active record and exact target state before any Villager Detail charge",
    )
    patch(
        BARREL_PENDING_FILE_OFFSET,
        b"\0",
        b"\0",
        "reserve the process-local one-shot VV2 Barrel event token",
    )
    patch(
        BARREL_CLOSE_HELPER_FILE_OFFSET,
        b"\0" * len(BARREL_CLOSE_HELPER_CODE),
        BARREL_CLOSE_HELPER_CODE,
        "advance the purchased Barrel token only after the stock Technologies screen closes",
    )
    patch(
        BARREL_MAIN_HELPER_FILE_OFFSET,
        b"\0" * len(BARREL_MAIN_HELPER_CODE),
        BARREL_MAIN_HELPER_CODE,
        "consume the closed-screen Barrel token with the stock main-village modal owner",
    )

    patch(
        0x218,
        bytes.fromhex("A8030200"),
        bytes.fromhex("00100200"),
        "extend the mapped .rdata VirtualSize to cover the Origins payload at its raw end",
    )
    patch(
        0x234,
        bytes.fromhex("40000040"),
        bytes.fromhex("20000060"),
        "make the mapped .rdata Origins payload executable code",
    )
    patch(
        0x268,
        bytes.fromhex("04000000"),
        bytes.fromhex("00100000"),
        "extend the mapped .shr VirtualSize to cover the preflight and Cure helpers",
    )
    patch(
        0x284,
        bytes.fromhex("400000D0"),
        bytes.fromhex("600000F0"),
        "make the mapped .shr preflight and Cure helpers executable code",
    )
    patch(
        0x26290,
        bytes.fromhex("8B44240401"),
        rel32_jump(0x426290, tech_increment),
        "double eligible positive earned tech deltas",
    )
    patch(
        0x262B0,
        bytes.fromhex("8B44240401"),
        rel32_jump(0x4262B0, food_increment),
        "double eligible positive food-source deltas",
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
        0x437DA,
        bytes.fromhex("8B4E146A4B"),
        rel32_jump(0x4437DA, BARREL_CLOSE_HELPER_VA),
        "advance a purchased Barrel only after the stock Technologies screen closes",
    )
    patch(
        0x2E9F0,
        bytes.fromhex("E80B48FDFF"),
        rel32_jump(0x42E9F0, BARREL_MAIN_HELPER_VA),
        "present the pending native Barrel event from the stock main-village update owner",
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
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": "vv2",
        "running_preference_id": RUNNING_PREFERENCE_ID,
        "running_preference_evidence": {"source": "exact stock executable embedded preference table", "table_file_offset": "0x8B808", "entry_name": "running"},
        "name": "Enable Origins-Exclusive Features",
        "description": "Adds Origins-style Upgrades buttons to the Tech and Villager Details screens. The Tech menu offers Food and Tech Point Doublers for 500,000 tech points each; eligible positive gains are doubled, while Island Events, Duplicate Collectibles, and Gong of Wonder tech gains remain unchanged. The Village-Wide menu adds Running, Full Mastery, and Make Villagers Young Adults.",
        "output_tag": "Origins Exclusive Features",
        "companion_files": [
            {
                "source": "assets/origins/VVFP VV2 Origins Icons.dll",
                "destination": "VVFP VV2 Origins Icons.dll",
                "sha256": hashlib.sha256(
                    (ROOT / "assets" / "origins" / "VVFP VV2 Origins Icons.dll").read_bytes()
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
            "duplicate_collectibles": {
                "function": "0x463426",
                "tech_returns": ["0x463461", "0x46346D", "0x463479"],
                "behavior": "an already-completed collectible routes to the tech writer",
            },
            "tech_blacklist_returns": [
                "0x4205AC", "0x434351", "0x44EA32", "0x44ED52", "0x44F202",
                "0x463461", "0x46346D", "0x463479"
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
            "hook_status": "GO: exact-build static provenance proof covers the positive writer callsites and excludes Island Event, Gong, and duplicate-collectible tech awards; runtime/player confirmation pending",
        },
        "doubler_composition_contract": {
            "stacking": [
                "positive earned tech deltas only",
                "positive food-source deltas only",
            ],
            "exclusions": [
                "Island Event tech-point gain",
                "Gong of Wonder tech-point gain",
                "Duplicate Collectibles tech-point gain",
            ],
            "food_mastery_status": "confirmed absent in exact-build audit: enumerated technology definitions, resource strings, direct writer calls, and food-source call chains; Farming gates/unlocks sources only; Herb Mastery is unrelated",
            "status": "GO: exact-build static provenance covers the certified positive delta boundaries; native writers still perform storage/statistics updates for the doubled amount; runtime/player confirmation pending",
        },
        "doubler_purchase_status": {
            "status": "Tech and Food Doublers are available at 500,000 tech points; owned upgrades can be removed for no refund and bought again.",
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
    print(OUT_JSON)
    print(MANIFEST_JSON)
    print(OUT_EXE)


if __name__ == "__main__":
    main()
