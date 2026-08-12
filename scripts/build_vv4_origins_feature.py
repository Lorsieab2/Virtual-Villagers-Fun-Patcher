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
CURE_ENTRY_FILE_OFFSET = HEAL_CAVE_FILE_OFFSET
CURE_ENTRY_VA = HEAL_CAVE_VA
EXPANDED_HEAL_CAVE_VA = 0x85A004
SHR_STOCK_VA = 0x728000
SHR_EXPANDED_VA = 0x85A000
VILLAGE_WIDE_SIGNATURE_VA = 0x728220
VILLAGE_WIDE_ENTRY_VA = 0x728240
VILLAGE_PREFLIGHT_FILE_OFFSET = 0xCC180
VILLAGE_PREFLIGHT_VA = 0x728180
EXPANDED_VILLAGE_WIDE_ENTRY_VA = 0x85A240
EXPANDED_VILLAGE_PREFLIGHT_VA = 0x85A180
RUNNING_PREFERENCE_ID = 38  # exact-build preference-table evidence: 0xA0CD8
VV4_MASTER_VALUE = 0x42C80000  # Float32 100.0
VV4_NATIVE_SKILL_WRITER_VA = 0x46AD80
VV4_DETAIL_HANDLER_RELOC_OFFSET = 0x235
VV4_RESULT_HELPER_OFFSET = 0x960
VV4_RESULT_HELPER_VA = PAYLOAD_VA + VV4_RESULT_HELPER_OFFSET
VV4_RESULT_HELPER_BYTES = bytes.fromhex(
    "53568B5C240C8B74241068E39E4800FF15E0A1480085C0741868EE9E480050"
    "FF15DCA1480085C074086A0053566A00FFD05E5BC20800"
)

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
        (
            "doubler_unavailable",
            "Unavailable: exact-build doubler behavior is not yet fully verified.",
        ),
        ("paused", "Time Warp is unavailable while the game is paused."),
        ("capacity", "The village population is already at maximum capacity."),
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
    tech_increment = PAYLOAD_VA + 0x850
    food_increment = PAYLOAD_VA + 0x900

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
        """
            test dword ptr [0x4D6E10], 0x80000000
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
            call dword ptr [0x48A1E0]
            test eax, eax
            je done
            push 0x{s['message_box_export']:X}
            push eax
            call dword ptr [0x48A1DC]
            test eax, eax
            je done
            push 0
            push ebx
            push esi
            push 0
            call eax
        done:
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
            xor eax, eax
            test dword ptr [0x4D6E10], 1
            jz tech_not_owned
            or eax, 8
        tech_not_owned:
            test dword ptr [0x4D6E10], 2
            jz food_not_owned
            or eax, 16
        food_not_owned:
            or eax, 0x1800
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
            jz doubler_unavailable
            and dword ptr [0x4D6E10], 0xFFFFFFFE
            mov eax, 0x{s['removed']:X}
            jmp status
        maybe_remove_food:
            test dword ptr [0x4D6E10], 2
            jz doubler_unavailable
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
            mov ebp, dword ptr [0x467499]
            xor edi, edi
            mov edx, 0x50E5AC
        count_records:
            cmp byte ptr [edx + 0x1CC4], 0
            je record_free
            inc edi
        record_free:
            add edx, 0x2E3C
            dec ebp
            jne count_records
            mov eax, dword ptr [0x467499]
            sub eax, 3
            cmp edi, eax
            jbe charge
            mov eax, 0x{s['capacity']:X}
            jmp status
        charge:
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
            or dword ptr [0x4D6E10], 0x80000000
            push 25
            push esi
            call 0x418190
            and dword ptr [0x4D6E10], 0x7FFFFFFF
            jmp success
        do_tech_doubler:
            or dword ptr [0x4D6E10], 1
        success:
            mov eax, 0x{s['purchased']:X}
            jmp status
        insufficient:
            mov eax, 0x{s['not_enough']:X}
            jmp status
        doubler_unavailable:
            mov eax, 0x{s['doubler_unavailable']:X}
        status:
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
            jne show
            or edi, 8
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
            lea ecx, [edx + 0x1E60]
            mov eax, 3
        find_like:
            cmp dword ptr [ecx], {RUNNING_PREFERENCE_ID}
            je remove_dislikes
            cmp dword ptr [ecx], -1
            je store_like
            add ecx, 4
            dec eax
            jne find_like
            mov eax, 0x{s['running_unavailable']:X}
            jmp detail_status
        store_like:
            mov dword ptr [ecx], {RUNNING_PREFERENCE_ID}
        remove_dislikes:
            lea ecx, [edx + 0x1E6C]
            mov eax, 3
        remove_loop:
            cmp dword ptr [ecx], {RUNNING_PREFERENCE_ID}
            jne remove_next
            mov dword ptr [ecx], -1
        remove_next:
            add ecx, 4
            dec eax
            jne remove_loop
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
        0x414477,
        0x414493,
        0x4144AF,
        0x414A2D,
        0x4156FD,
        0x415874,
        0x415A86,
        0x415B4B,
        0x415D91,
        0x41673A,
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
    food_exclusions = (0x41494E, 0x415213)
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
    if any(payload[VV4_RESULT_HELPER_OFFSET : VV4_RESULT_HELPER_OFFSET + len(VV4_RESULT_HELPER_BYTES)]):
        raise RuntimeError("VV4 result-helper cave is not zero")
    payload[VV4_RESULT_HELPER_OFFSET : VV4_RESULT_HELPER_OFFSET + len(VV4_RESULT_HELPER_BYTES)] = VV4_RESULT_HELPER_BYTES
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
        "sha256": hashlib.sha256(VV4_RESULT_HELPER_BYTES).hexdigest().upper(),
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
            push 0x{s['show_result_export']:X}
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
            cmp dword ptr [esi + 0x1C40], 80
            jge cure_health_done
            # Native VV4 health setter: ECX=record+0x1C34, push -1 and
            # target 100, callee ret 8.  Save the walker state because this
            # is a native call, not an inline field assignment.
            push ecx
            push ebp
            lea eax, [esi + 0x1C34]
            mov ecx, eax
            push -1
            push 100
            call 0x46AF00
            pop ebp
            pop ecx
            cmp dword ptr [esi + 0x1C40], 100
            jne cure_next
            inc ebp
        cure_health_done:
            cmp byte ptr [esi + 0x1C48], 0
            je cure_next
            mov byte ptr [esi + 0x1C48], 0
            inc dword ptr [0x4D6DF0]
            inc ebp
        cure_next:
            mov edx, esi
            add edx, 0x2E3C
            dec ecx
            jne cure_loop
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
            call dword ptr [0x48A1E0]
            test eax, eax
            je preflight_invalid
            push 0x{s['show_result_export']:X}
            push eax
            call dword ptr [0x48A1DC]
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
        "restore health below 80 to 100 through the native setter, clear sickness, and update People Cured",
    )
    patch(
        VILLAGE_PREFLIGHT_FILE_OFFSET,
        b"\0" * len(preflight_code),
        preflight_code,
        "validate the complete optional Origins header and result-export dependency before any village-wide charge",
    )

    patch(0x244, bytes.fromhex("40000040"), bytes.fromhex("40000060"),
          "make the mapped .text cave executable for the Origins payload")
    patch(0x14D50, bytes.fromhex("B968E55000"), rel32_jump(0x414D50, barrel_eligibility),
          "temporarily admit the explicitly purchased native Barrel of Babies event")
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
        "description": "Adds Origins-style upgrade buttons to the Tech and Villager Details screens. The Village-Wide menu adds Running, Full Mastery, and Make Villagers Young Adults.",
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
                "source": "assets/origins/VVFP Origins Icons.dll",
                "destination": "VVFP Origins Icons.dll",
                "sha256": hashlib.sha256(
                    (ROOT / "assets/origins/VVFP Origins Icons.dll").read_bytes()
                ).hexdigest().upper(),
            }
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
                "tech_returns": ["0x414477", "0x414493", "0x4144AF"],
                "behavior": "an already-completed collectible routes to the tech writer",
            },
            "island_event_positive_sites": {
                "tech": ["0x414A28", "0x4156F8", "0x415862", "0x415A81", "0x415B46", "0x415D8C", "0x416722", "0x464E58", "0x464E82", "0x464EAB"],
                "food": ["0x414949", "0x41520E", "0x4643E6", "0x464433", "0x464492", "0x46450B", "0x464573", "0x4645B0", "0x4645FB"],
            },
            "hook_status": "STOP: duplicate-collectible and Island Event direct returns are excluded, but no safe post-Food-Mastery hook has been implemented; return-address-only exclusion is invalid for the listed E9 tails",
        },
        "doubler_composition_contract": {
            "stacking": [
                "positive earned tech deltas only",
                "positive food-source deltas only",
            ],
            "exclusions": ["Island Event tech-point gain", "Duplicate Collectibles tech-point gain"],
            "food_mastery_status": "confirmed in exact-build disassembly; native transform documented in doubler evidence",
            "status": "STOP: direct duplicate-collectible exclusion is encoded, but no safe post-Food-Mastery hook/section and incomplete dynamic/computed Island Event provenance remain",
        },
        "doubler_purchase_status": {
            "new_purchase": "temporarily unavailable pending exact-build provenance verification",
            "existing_owned": "removable at zero cost with zero refund",
            "repurchase": "temporarily disabled pending exact-build provenance verification",
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
