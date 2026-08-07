"""Assemble the exact-build VV5 Origins-exclusive feature patch."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research/stock-executables/Virtual Villagers - New Believers.exe"
OUT_DIR = ROOT / "research/vv5-origins"
OUT_EXE = OUT_DIR / "Virtual Villagers - New Believers - Origins Research.exe"
OUT_JSON = OUT_DIR / "vv5-origins-feature-patches.json"
MANIFEST_JSON = ROOT / "data/vv5_origins_feature.json"
COMPANION = ROOT / "assets/origins/VVFP Origins Icons.dll"
VV5_PROVENANCE_DIR = ROOT / "assets/candidates/vv5_full_mastery/provenance"
VV5_PROVENANCE = {
    "VV5Mockup.jpg": "4EF2DFC0DAE6C733C452CCB4BEA4023C0E2601EEF2396A1A38D75A4DCD57B00F",
    "VV5Mockup2.jpg": "104B1BE5873B1660EE4BC2E02A886C6EBB99B06CB6F0D723D20638C2B0949144",
}

sys.path.insert(0, str(ROOT / ".tools/keystone"))
sys.path.insert(0, str(ROOT / ".tools/keystone-runtime"))
from keystone import KS_ARCH_X86, KS_MODE_32, Ks  # noqa: E402

IMAGE_BASE = 0x400000
PAYLOAD_FILE_OFFSET = 0xDB000
PAYLOAD_VA = 0x7B2000
EXPANDED_PAYLOAD_VA = 0x8EB000
PAYLOAD_SIZE = 0x1000
STRINGS_OFFSET = 0xD00
STRINGS_VA = PAYLOAD_VA + STRINGS_OFFSET
HEAL_CAVE_FILE_OFFSET = 0x94B32
CURE_ENTRY_FILE_OFFSET = 0x94EA0
CURE_ENTRY_VA = IMAGE_BASE + CURE_ENTRY_FILE_OFFSET
HEAL_CAVE_VA = CURE_ENTRY_VA
VILLAGE_WIDE_SIGNATURE_VA = IMAGE_BASE + 0x94C20
VILLAGE_WIDE_ENTRY_VA = IMAGE_BASE + 0x94C40
VILLAGE_PREFLIGHT_FILE_OFFSET = 0x94B37
VILLAGE_PREFLIGHT_VA = IMAGE_BASE + VILLAGE_PREFLIGHT_FILE_OFFSET
RUNNING_PREFERENCE_ID = 38  # exact-build preference-table evidence: 0xAEF60
TECH_BUTTON_EVENT = 13
DETAIL_BUTTON_EVENT = 13  # native VV5 Detail constructor/handler event
DETAIL_NATIVE_HANDLER_VA = 0x44B560

# This is the reviewed VV5 all-current-feature relocation ledger exported from
# IDA Pro 9.4.  The operand heads, source/target VAs, and stock preimages are
# committed evidence; a raw payload byte sweep is deliberately not used to
# discover or certify relocation sites.
VV5_IDA_PAYLOAD_ABSOLUTE_RELOCATIONS = [
    ("0xDB087", "002D7B00"),
    ("0xDB147", "002D7B00"),
    ("0xDB1C3", "BD2E7B00"),
    ("0xDB1D2", "D42E7B00"),
    ("0xDB21B", "0D2F7B00"),
    ("0xDB22A", "182F7B00"),
    ("0xDB354", "372D7B00"),
    ("0xDB383", "372D7B00"),
    ("0xDB399", "3F2E7B00"),
    ("0xDB3B4", "9D2D7B00"),
    ("0xDB3D5", "082E7B00"),
    ("0xDB41E", "382F7B00"),
    ("0xDB48E", "D02D7B00"),
    ("0xDB4C4", "2C2D7B00"),
    ("0xDB4CB", "402D7B00"),
    ("0xDB4D2", "582D7B00"),
    ("0xDB4D8", "092D7B00"),
    ("0xDB787", "842E7B00"),
    ("0xDB793", "502F7B00"),
    ("0xDB865", "842E7B00"),
    ("0xDB88E", "2C2D7B00"),
    ("0xDB895", "402D7B00"),
    ("0xDB89B", "1A2D7B00"),
]

VV5_IDA_CROSS_SECTION_REL32_RELOCATIONS = [
    # Unmoved .text -> moved .shr branches.  The two doubler rows are
    # preserved by the expanded-mode native-hook overrides when encountered.
    ("0x18910", "6C983900", "0x41890F", "0x7B2180", None),
    ("0x1EB70", "8C3F3900", "0x41EB6F", "0x7B2B00", "F67E3456"),
    ("0x237B1", "4BF23800", "0x4237B0", "0x7B2A00", "8B742408"),
    ("0x40A25", "17163700", "0x440A24", "0x7B2040", None),
    ("0x4AF13", "E9713600", "0x44AF12", "0x7B2100", None),
    ("0x4BC21", "9B643600", "0x44BC20", "0x7B20C0", None),
    ("0x94FBF", "4DD23100", "0x494FBE", "0x7B2210", None),
    # Moved .shr -> unmoved .text calls, returns, and jumps.  The source VA
    # is the expanded instruction VA because the source instruction moves.
    ("0xDB01C", "20EDC9FF", "0x8EB01B", "0x450D40", None),
    ("0xDB021", "D3F5C8FF", "0x8EB020", "0x4415F8", None),
    ("0xDB043", "959BCCFF", "0x8EB042", "0x47BBDC", None),
    ("0xDB055", "C7D9C9FF", "0x8EB054", "0x44FA20", None),
    ("0xDB06C", "60FBC4FF", "0x8EB06B", "0x401BD0", None),
    ("0xDB08E", "3EF5C4FF", "0x8EB08D", "0x4015D0", None),
    ("0xDB096", "E6A5C5FF", "0x8EB095", "0x40C680", None),
    ("0xDB0E1", "439BC9FF", "0x8EB0E0", "0x44BC28", None),
    ("0xDB103", "D59ACCFF", "0x8EB102", "0x47BBDC", None),
    ("0xDB115", "07D9C9FF", "0x8EB114", "0x44FA20", None),
    ("0xDB12C", "A0FAC4FF", "0x8EB12B", "0x401BD0", None),
    ("0xDB14E", "7EF4C4FF", "0x8EB14D", "0x4015D0", None),
    ("0xDB156", "26A5C5FF", "0x8EB155", "0x40C680", None),
    ("0xDB1A4", "7267C6FF", "0x8EB1A3", "0x41891A", None),
    ("0xDB272", "DA36C7FF", "0x8EB271", "0x425950", None),
    ("0xDB283", "B9F5CBFF", "0x8EB282", "0x471840", None),
    ("0xDB292", "BAD6CBFF", "0x8EB291", "0x46F950", None),
    ("0xDB38D", "BF35C7FF", "0x8EB38C", "0x425950", None),
    ("0xDB3C3", "F920CEFF", "0x8EB3C2", "0x4944C0", None),
    ("0xDB3ED", "4627CEFF", "0x8EB3EC", "0x494B37", None),
    ("0xDB415", "9713C7FF", "0x8EB414", "0x4237B0", None),
    ("0xDB437", "7513C7FF", "0x8EB436", "0x4237B0", None),
    ("0xDB45A", "422ACEFF", "0x8EB459", "0x494EA0", None),
    ("0xDB462", "3A2ACEFF", "0x8EB461", "0x494EA0", None),
    ("0xDB46C", "302ACEFF", "0x8EB46B", "0x494EA0", None),
    ("0xDB7AC", "0010C7FF", "0x8EB7AB", "0x4237B0", None),
    ("0xDBA56", "5D0DC7FF", "0x8EBA55", "0x4237B7", None),
    ("0xDBB22", "4EC0C6FF", "0x8EBB21", "0x41EB74", None),
    ("0xDBB27", "7CC0C6FF", "0x8EBB26", "0x41EBA7", None),
]

VV5_IDA_EXTERNAL_ABSOLUTE_RELOCATIONS = [
    ("0x94B80", "F02E7B00", "ShowOriginsVillageWideResult"),
    ("0x94B85", "BD2E7B00", "VVFP Origins Icons.dll"),
    ("0x94B94", "F02E7B00", "ShowOriginsVillageWideResult"),
    ("0x94ED1", "F02E7B00", "ShowOriginsVillageWideResult"),
    ("0x94ED6", "BD2E7B00", "VVFP Origins Icons.dll"),
    ("0x94EE5", "F02E7B00", "ShowOriginsVillageWideResult"),
    ("0x94FBA", "092D7B00", "Origins Upgrades"),
]

# D37 VV5 selector repair.  The hook remains the existing seven-byte detour;
# only the owned body is corrected so both marker branches call the native
# selector and return after the complete stock call instruction.
BARREL_SELECTOR_HOOK_FILE_OFFSET = 0x1890F
BARREL_SELECTOR_HOOK_VA = IMAGE_BASE + BARREL_SELECTOR_HOOK_FILE_OFFSET
BARREL_SELECTOR_BODY_FILE_OFFSET = PAYLOAD_FILE_OFFSET + 0x180
BARREL_SELECTOR_BODY_VA = PAYLOAD_VA + 0x180
BARREL_SELECTOR_HOOK_STOCK = bytes.fromhex("8B7484146A64E8")
BARREL_SELECTOR_HOOK_REPAIRED = bytes.fromhex("E96C9839009090")
BARREL_SELECTOR_BODY_STOCK = b"\0" * 0x28
BARREL_SELECTOR_BODY_REPAIRED = bytes.fromhex(
    "8B748414F70588D3510004000000740C832588D35100FBBE1E000000"
    "6A64E8BD14C5FFE97267C6FF"
)
BARREL_SELECTOR_BODY_SHA256 = hashlib.sha256(BARREL_SELECTOR_BODY_REPAIRED).hexdigest().upper()


def assemble(source: str, address: int) -> bytes:
    encoded, _ = Ks(KS_ARCH_X86, KS_MODE_32).asm(source, address)
    return bytes(encoded)


def rel32_jump(source_va: int, target_va: int, size: int = 5) -> bytes:
    result = b"\xE9" + int(target_va - source_va - 5).to_bytes(
        4, "little", signed=True
    )
    return result + b"\x90" * (size - 5)


def add_c_string(
    blob: bytearray, labels: dict[str, int], name: str, value: str
) -> None:
    labels[name] = STRINGS_VA + len(blob)
    blob.extend(value.encode("ascii") + b"\0")


def main() -> None:
    original = STOCK.read_bytes()
    expected = "92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D"
    actual = hashlib.sha256(original).hexdigest().upper()
    if actual != expected:
        raise RuntimeError(f"stock SHA-256 mismatch: expected {expected}, got {actual}")
    if not COMPANION.is_file():
        raise RuntimeError(f"missing companion DLL: {COMPANION}")
    for name, expected_hash in VV5_PROVENANCE.items():
        provenance_path = VV5_PROVENANCE_DIR / name
        if not provenance_path.is_file():
            raise RuntimeError(f"missing VV5 provenance reference: {provenance_path}")
        actual_hash = hashlib.sha256(provenance_path.read_bytes()).hexdigest().upper()
        if actual_hash != expected_hash:
            raise RuntimeError(
                f"VV5 provenance hash mismatch for {name}: expected {expected_hash}, got {actual_hash}"
            )
    if any(original[PAYLOAD_FILE_OFFSET : PAYLOAD_FILE_OFFSET + PAYLOAD_SIZE]):
        raise RuntimeError("VV5 Origins .shr payload region is not stock zero padding")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    strings = bytearray()
    s: dict[str, int] = {}
    for name, value in (
        ("button", "Upgrades"),
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
        ("time_done", "Time Warp advanced every villager by 3 displayed years."),
        ("capacity", "The village population is already at maximum capacity."),
        ("vv5_unsafe_native", "Unavailable: this VV5 native path is not verified safe for Heathens."),
        ("running_unavailable", "Running cannot be added because all Like slots are full."),
        ("icons_dll", "VVFP Origins Icons.dll"),
        ("dialog_export", "ShowOriginsUpgradeMenuState"),
        ("show_result_export", "ShowOriginsVillageWideResult"),
        ("user32", "USER32.dll"),
        ("message_box", "MessageBoxA"),
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
        raise RuntimeError("VV5 Origins strings exceed payload allowance")

    entry = {
        "tech_handler": PAYLOAD_VA + 0x000,
        "tech_ctor": PAYLOAD_VA + 0x040,
        "detail_handler": PAYLOAD_VA + 0x0C0,
        "detail_ctor": PAYLOAD_VA + 0x100,
        "barrel_selector": PAYLOAD_VA + 0x180,
        "show_dialog": PAYLOAD_VA + 0x1C0,
        "show_message": PAYLOAD_VA + 0x210,
        "get_record": PAYLOAD_VA + 0x270,
        "tech_menu": PAYLOAD_VA + 0x2C0,
        "detail_menu": PAYLOAD_VA + 0x600,
        "tech_increment": PAYLOAD_VA + 0xA00,
        "food_increment": PAYLOAD_VA + 0xB00,
    }
    code = bytearray(STRINGS_OFFSET)
    occupied = bytearray(STRINGS_OFFSET)

    def put(name: str, source: str) -> None:
        va = entry[name]
        payload = assemble(source, va)
        start = va - PAYLOAD_VA
        end = start + len(payload)
        if start < 0 or end > len(code):
            raise RuntimeError(f"{name} exceeds VV5 Origins code block")
        if any(occupied[start:end]):
            raise RuntimeError(f"{name} overlaps another payload routine")
        code[start:end] = payload
        occupied[start:end] = b"\1" * len(payload)

    put(
        "tech_handler",
        f"""
            cmp dword ptr [esp + 4], 8
            jne original
            cmp dword ptr [esp + 8], {TECH_BUTTON_EVENT}
            jne original
            call 0x{entry['tech_menu']:X}
            xor eax, eax
            ret 8
        original:
            push edi
            mov edi, ecx
            call 0x450D40
            jmp 0x4415F8
        """,
    )
    put(
        "tech_ctor",
        f"""
            push 0x14
            call 0x47BBDC
            add esp, 4
            test eax, eax
            je done
            mov edi, eax
            mov ecx, edi
            push 72
            call 0x44FA20
            push 0
            push esi
            push 722
            push 180
            push eax
            push {TECH_BUTTON_EVENT}
            mov ecx, edi
            call 0x401BD0
            mov edi, eax
            push 0
            push dword ptr [0x4CD2A8]
            push dword ptr [0x4CD2A4]
            push dword ptr [0x4CD2A0]
            push 0x{s['button']:X}
            mov ecx, edi
            call 0x4015D0
            push edi
            mov ecx, esi
            call 0x40C680
        done:
            mov eax, esi
            mov ecx, dword ptr [esp + 0x4C]
            mov dword ptr fs:[0], ecx
            pop ecx
            pop edi
            pop esi
            pop ebp
            pop ebx
            add esp, 0x44
            ret
        """,
    )
    put(
        "detail_handler",
        f"""
            cmp dword ptr [esp + 4], 8
            jne original
            cmp dword ptr [esp + 8], {DETAIL_BUTTON_EVENT}
            jne original
            call 0x{entry['detail_menu']:X}
            xor eax, eax
            ret 8
        original:
            sub esp, 0x18
            mov eax, dword ptr [0x4D97A8]
            jmp 0x44BC28
        """,
    )
    put(
        "detail_ctor",
        f"""
            push 0x14
            call 0x47BBDC
            add esp, 4
            test eax, eax
            je no_button
            mov edi, eax
            mov ecx, edi
            push 72
            call 0x44FA20
            push 0
            push esi
            push 700
            push 180
            push eax
            push {DETAIL_BUTTON_EVENT}
            mov ecx, edi
            call 0x401BD0
            mov edi, eax
            push 0
            push dword ptr [0x4CD2A8]
            push dword ptr [0x4CD2A4]
            push dword ptr [0x4CD2A0]
            push 0x{s['button']:X}
            mov ecx, edi
            call 0x4015D0
            push edi
            mov ecx, esi
            call 0x40C680
            jmp done
        no_button:
        done:
            mov eax, esi
            mov ecx, dword ptr [esp + 0x24]
            mov dword ptr fs:[0], ecx
            pop ecx
            pop edi
            pop esi
            pop ebp
            pop ebx
            add esp, 0x1C
            ret
        """,
    )
    put(
        "barrel_selector",
        """
            mov esi, dword ptr [esp + eax*4 + 0x14]
            test dword ptr [0x51D388], 4
            jz done
            and dword ptr [0x51D388], 0xFFFFFFFB
            mov esi, 30
        done:
            push 100
            call 0x403660
            jmp 0x41891A
        """,
    )
    put(
        "show_dialog",
        f"""
            push ebx
            push esi
            push 0x{s['icons_dll']:X}
            call dword ptr [0x4951E0]
            test eax, eax
            je unavailable
            push 0x{s['dialog_export']:X}
            push eax
            call dword ptr [0x4951DC]
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
        "show_message",
        f"""
            push ebx
            push esi
            mov ebx, dword ptr [esp + 0x0C]
            mov esi, dword ptr [esp + 0x10]
            push 0x{s['user32']:X}
            call dword ptr [0x4951E0]
            test eax, eax
            je done
            push 0x{s['message_box']:X}
            push eax
            call dword ptr [0x4951DC]
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
        "get_record",
        """
            push ebx
            call 0x425950
            mov ebx, dword ptr [eax + 0x17E24]
            push ebx
            mov ecx, 0x554148
            call 0x471840
            test al, al
            je invalid
            push ebx
            mov ecx, 0x554148
            call 0x46F950
            pop ebx
            ret
        invalid:
            xor eax, eax
            pop ebx
            ret
        """,
    )
    put(
        "tech_menu",
        f"""
            push ebx
            push esi
            push edi
            push ebp
            mov esi, ecx
        menu:
            xor eax, eax
            test dword ptr [0x51D388], 1
            jnz tech_owned
            cmp dword ptr [0x41F1E6], 0x96
            je tech_clear
            or eax, 0x0800
            jmp tech_clear
        tech_owned:
            or eax, 8
        tech_clear:
            test dword ptr [0x51D388], 2
            jnz food_owned
            cmp dword ptr [0x41F1E6], 0x96
            je food_clear
            or eax, 0x1000
            jmp food_clear
        food_owned:
            or eax, 16
        food_clear:
            push eax
            push 0
            call 0x{entry['show_dialog']:X}
            cmp eax, -1
            je done
            mov ebx, eax
            cmp ebx, 3
            jb preflight
            cmp ebx, 5
            jae preflight
            cmp ebx, 4
            je remove_food
            test dword ptr [0x51D388], 1
            jnz tech_owned_remove
            cmp dword ptr [0x41F1E6], 0x96
            jne doubler_unavailable
            jmp preflight
        tech_owned_remove:
            and dword ptr [0x51D388], 0xFFFFFFFE
            mov eax, 0x{s['removed']:X}
            jmp status
        remove_food:
            test dword ptr [0x51D388], 2
            jnz food_owned_remove
            cmp dword ptr [0x41F1E6], 0x96
            jne doubler_unavailable
            jmp preflight
        food_owned_remove:
            and dword ptr [0x51D388], 0xFFFFFFFD
            mov eax, 0x{s['removed']:X}
            jmp status
        preflight:
            call 0x425950
            mov edi, eax
            cmp ebx, 2
            ja native_safe_row
            mov eax, 0x{s['vv5_unsafe_native']:X}
            jmp status
        native_safe_row:
            cmp ebx, 0
            jne barrel_check
            cmp dword ptr [edi + 0x17D7C], 999
            jne charge
            mov eax, 0x{s['paused']:X}
            jmp status
        barrel_check:
            cmp ebx, 2
            jne charge
            call 0x4944C0
            mov ecx, dword ptr [0x41F1E6]
            sub ecx, 3
            cmp eax, ecx
            jbe charge
            mov eax, 0x{s['capacity']:X}
            jmp status
        charge:
            cmp ebx, 6
            jb legacy_charge
            cmp ebx, 8
            ja menu
            call 0x{VILLAGE_PREFLIGHT_VA:X}
            test eax, eax
            jz menu
            cmp dword ptr [0x51D5F8], 1000000
            jb insufficient
            mov eax, -1000000
            push eax
            mov ecx, 0x51D5F8
            call 0x4237B0
            jmp do_village_wide
        legacy_charge:
            mov eax, dword ptr [0x{s['tech_costs']:X} + ebx*4]
            cmp dword ptr [0x51D5F8], eax
            jb insufficient
            neg eax
            push eax
            mov ecx, 0x51D5F8
            call 0x4237B0
            cmp ebx, 0
            je time_warp
            cmp ebx, 1
            je island_event
            cmp ebx, 2
            je barrel
            cmp ebx, 3
            je tech_doubler
            cmp ebx, 4
            je food_doubler
            cmp ebx, 5
            je cure
            call 0x{HEAL_CAVE_VA:X}
            nop
            jmp success


        cure:
            call 0x{HEAL_CAVE_VA:X}
            jmp menu
        do_village_wide:
            call 0x{HEAL_CAVE_VA:X}
            jmp success
        time_warp:
            mov ecx, dword ptr [edi + 0x17D7C]
            mov eax, 129600
            cdq
            idiv ecx
            sub dword ptr [0x4C6250], eax
            sbb dword ptr [0x4C6254], 0
            mov eax, 0x{s['time_done']:X}
            jmp status
        island_event:
            mov dword ptr [edi + 0x17D3C], 0
            jmp success
        barrel:
            or dword ptr [0x51D388], 4
            mov dword ptr [edi + 0x17D3C], 0
            jmp success
        tech_doubler:
            or dword ptr [0x51D388], 1
            jmp success
        food_doubler:
            or dword ptr [0x51D388], 2
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
            call 0x{entry['show_message']:X}
            jmp menu
        done:
            pop ebp
            pop edi
            pop esi
            pop ebx
            ret
        """,
    )
    put(
        "detail_menu",
        f"""
            push ebx
            push esi
            push edi
            push ebp
            mov esi, ecx
        menu:
            call 0x{entry['get_record']:X}
            test eax, eax
            je done
            mov edx, eax
            cmp byte ptr [edx + 0x1CD4], 0
            je done
            cmp byte ptr [edx + 0x1CE1], 0
            jne done
            cmp dword ptr [edx + 0x1C40], 0
            jle done
            cmp byte ptr [edx + 0x1CEC], 0
            jne done
            xor edi, edi
            cmp dword ptr [edx + 7052], 100
            ja youth_open
            or edi, 1
        youth_open:
            cmp dword ptr [edx + 7260], 0x42B40000
            jb mastery_open
            cmp dword ptr [edx + 7264], 0x42B40000
            jb mastery_open
            cmp dword ptr [edx + 7268], 0x42B40000
            jb mastery_open
            cmp dword ptr [edx + 7272], 0x42B40000
            jb mastery_open
            cmp dword ptr [edx + 7276], 0x42B40000
            jb mastery_open
            cmp dword ptr [edx + 7280], 0x42B40000
            jb mastery_open
            or edi, 2
        mastery_open:
            xor ebp, ebp
            lea eax, [edx + 8028]
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
            jnz dislikes
            or edi, 0x400
            jmp dislikes
        like_found:
            or ebp, 2
        dislikes:
            lea eax, [edx + 8040]
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
            cmp dword ptr [edx + 7052], 360
            jne show
            or edi, 8
        show:
            push edi
            push 1
            call 0x{entry['show_dialog']:X}
            cmp eax, -1
            je done
            mov ebx, eax
            call 0x{entry['get_record']:X}
            test eax, eax
            je done
            mov edx, eax
            cmp byte ptr [edx + 0x1CD4], 0
            je done
            cmp byte ptr [edx + 0x1CE1], 0
            jne done
            cmp dword ptr [edx + 0x1C40], 0
            jle done
            cmp byte ptr [edx + 0x1CEC], 0
            jne done
            cmp ebx, 2
            jne detail_charge
            lea eax, [edx + 8028]
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
            cmp dword ptr [0x51D5F8], eax
            jb detail_insufficient
            neg eax
            push eax
            mov ecx, 0x51D5F8
            call 0x4237B0
            cmp ebx, 0
            je youth
            cmp ebx, 1
            je mastery
            cmp ebx, 2
            je running
            mov eax, 360
            jmp set_age
        youth:
            mov eax, dword ptr [edx + 7052]
            sub eax, 700
            cmp eax, 100
            jge set_age
            mov eax, 100
        set_age:
            mov ecx, eax
            sub ecx, dword ptr [edx + 7052]
            mov dword ptr [edx + 7052], eax
            add dword ptr [edx + 7228], ecx
            cmp dword ptr [edx + 7244], 0
            je detail_success
            add dword ptr [edx + 7244], ecx
            jmp detail_success
        mastery:
            mov dword ptr [edx + 7260], 0x42B40000
            mov dword ptr [edx + 7264], 0x42B40000
            mov dword ptr [edx + 7268], 0x42B40000
            mov dword ptr [edx + 7272], 0x42B40000
            mov dword ptr [edx + 7276], 0x42B40000
            mov dword ptr [edx + 7280], 0x42B40000
            jmp detail_success
        running:
            lea ecx, [edx + 8028]
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
            lea ecx, [edx + 8040]
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
            call 0x{entry['show_message']:X}
            jmp menu
        done:
            pop ebp
            pop edi
            pop esi
            pop ebx
            ret
        """,
    )
    tech_wrapper_expected = bytes.fromhex(
        "8B44240485C07E46F70588D3510001000000743A"
        "813C24BE474100742D813C24DD4741007424813C24F9474100741B"
        "813C244DDE46007412813C247CDE46007409813C24A5DE46007504"
        "D1642404568B7424080131E95D0DC7FF"
    )
    put(
        "tech_increment",
        f"""
            mov eax, dword ptr [esp + 4]
            test eax, eax
            jle native
            test dword ptr [0x51D388], 1
            jz native
            cmp dword ptr [esp], 0x4147BE
            je matched
            cmp dword ptr [esp], 0x4147DD
            je matched
            cmp dword ptr [esp], 0x4147F9
            je matched
            cmp dword ptr [esp], 0x46DE4D
            je matched
            cmp dword ptr [esp], 0x46DE7C
            je matched
            cmp dword ptr [esp], 0x46DEA5
            jne native
        matched:
            shl dword ptr [esp + 4], 1
        native:
            push esi
            mov esi, dword ptr [esp + 8]
            add dword ptr [ecx], esi
            jmp 0x4237B7
        """,
    )
    tech_wrapper = bytes(code[entry["tech_increment"] - PAYLOAD_VA : entry["tech_increment"] - PAYLOAD_VA + len(tech_wrapper_expected)])
    if tech_wrapper != tech_wrapper_expected:
        raise RuntimeError(
            "VV5 Tech Doubler wrapper bytes drifted from the exact stock whitelist"
        )
    put(
        "food_increment",
        f"""
            test esi, esi
            jle native
            test dword ptr [0x51D388], 2
            jz native
            cmp dword ptr [esp + 8], 0x414970
            jne native
            add esi, esi
        native:
            test esi, esi
            jle nonpositive
            push esi
            jmp 0x41EB74
        nonpositive:
            jmp 0x41EBA7
        """,
    )

    payload = code + strings
    expanded_shr_relocations: list[dict[str, str]] = []
    for offset, before in VV5_IDA_PAYLOAD_ABSOLUTE_RELOCATIONS:
        expanded_shr_relocations.append(
            {
                "offset": offset,
                "before": before,
                "kind": "absolute",
                "purpose": "relocate IDA-decoded VV5 Origins payload-internal .shr absolute pointer for expanded 256 mode",
            }
        )
    for offset, before, source_va, target_va, skip_before in VV5_IDA_CROSS_SECTION_REL32_RELOCATIONS:
        target_stock_va = int(target_va, 0)
        target_expanded_va = (
            target_stock_va + (EXPANDED_PAYLOAD_VA - PAYLOAD_VA)
            if PAYLOAD_VA <= target_stock_va < PAYLOAD_VA + PAYLOAD_SIZE
            else target_stock_va
        )
        entry = {
            "offset": offset,
            "before": before,
            "kind": "rel32",
            "source_virtual_address": source_va,
            "source_expanded_virtual_address": source_va,
            "target_stock_virtual_address": target_va,
            "target_expanded_virtual_address": f"0x{target_expanded_va:X}",
            "purpose": "relocate IDA-decoded VV5 current-feature cross-section rel32 operand for expanded 256 mode",
        }
        if skip_before:
            entry["expanded_skip_before"] = skip_before
            entry["purpose"] += "; preserve the exact expanded native-hook override"
        expanded_shr_relocations.append(entry)
    for offset, before, referenced_value in VV5_IDA_EXTERNAL_ABSOLUTE_RELOCATIONS:
        expanded_shr_relocations.append(
            {
                "offset": offset,
                "before": before,
                "kind": "absolute",
                "source_virtual_address": f"0x{int.from_bytes(bytes.fromhex(before), 'little'):X}",
                "target_stock_virtual_address": f"0x{int.from_bytes(bytes.fromhex(before), 'little'):X}",
                "target_expanded_virtual_address": f"0x{int.from_bytes(bytes.fromhex(before), 'little') + (EXPANDED_PAYLOAD_VA - PAYLOAD_VA):X}",
                "purpose": f"relocate IDA-decoded VV5 Origins external .shr absolute operand ({referenced_value}) for expanded 256 mode",
            }
        )
    patches: list[dict[str, str | int]] = []

    def patch(offset: int, before: bytes, after: bytes, purpose: str) -> None:
        actual_bytes = original[offset : offset + len(before)]
        if actual_bytes != before:
            raise RuntimeError(
                f"guard mismatch at {offset:#x}: expected {before.hex()}, "
                f"got {actual_bytes.hex()}"
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
            or dword ptr [0x51D388], 2
            ret
        village_wide:
            push ebx
            push ebp
            push ecx
            push edx
            push esi
            push edi
            mov eax, ebx
            mov ecx, 0x554190
            mov edx, dword ptr [0x41F1E6]
            call 0x{VILLAGE_WIDE_ENTRY_VA:X}
            mov ebp, eax
            mov edi, edx
            mov esi, ecx
            push 0x{s['show_result_export']:X}
            push 0x{s['icons_dll']:X}
            call dword ptr [0x4951E0]
            test eax, eax
            je village_result_done
            push 0x{s['show_result_export']:X}
            push eax
            call dword ptr [0x4951DC]
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
            mov edx, 0x554190
            mov ecx, dword ptr [0x41F1E6]
        cure_loop:
            cmp byte ptr [edx + 0x1CD4], 0
            je cure_next
            cmp byte ptr [edx + 0x1CE1], 0
            jne cure_next
            cmp dword ptr [edx + 0x1C40], 0
            jle cure_next
            cmp byte ptr [edx + 0x1CEC], 0
            jne cure_next
            cmp byte ptr [edx + 0x1C48], 0
            je cure_next
            mov byte ptr [edx + 0x1C48], 0
            inc dword ptr [0x55490C]
            inc eax
        cure_next:
            add edx, 0x2F44
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
            call 0x{entry['show_message']:X}
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
            call dword ptr [0x4951E0]
            test eax, eax
            je preflight_invalid
            push 0x{s['show_result_export']:X}
            push eax
            call dword ptr [0x4951DC]
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
        "redirect the shared VV5 Cure/village-wide dispatch stub to its certified helper after the optional Origins reserve",
    )
    patch(
        CURE_ENTRY_FILE_OFFSET,
        b"\0" * len(cure_code),
        cure_code,
        "retain the byte-identical withdrawn Cure payload behind the EB5F containment gate; command 5 is unavailable and unreachable, and no Cure behavior is available",
    )
    patch(
        VILLAGE_PREFLIGHT_FILE_OFFSET,
        b"\0" * len(preflight_code),
        preflight_code,
        "validate the complete optional Origins header and result-export dependency before any village-wide charge",
    )

    patch(0x28C, bytes.fromhex("400000D0"), bytes.fromhex("400000F0"),
          "make the stock shared payload section executable")
    patch(BARREL_SELECTOR_HOOK_FILE_OFFSET, BARREL_SELECTOR_HOOK_STOCK,
          BARREL_SELECTOR_HOOK_REPAIRED,
          "consume the one-shot purchase marker and force native event index 30")
    stock_food_hook = bytes.fromhex("85F67E3456")
    detoured_food_hook = rel32_jump(0x41EB6F, entry["food_increment"])
    stock_tech_hook = bytes.fromhex("568B742408")
    detoured_tech_hook = rel32_jump(0x4237B0, entry["tech_increment"])
    patch(0x1EB6F, stock_food_hook,
          detoured_food_hook,
          "double positive non-Island-Event food after stock mastery adjustments")
    patch(0x237B0, stock_tech_hook,
          detoured_tech_hook,
          "double six exact positive-whitelist tech awards for the current save")
    patch(0x40A24, bytes.fromhex("8BC68B4C244C"),
          rel32_jump(0x440A24, entry["tech_ctor"], 6),
          "append the stock-styled Upgrades control to the Tech screen")
    patch(0x415F0, bytes.fromhex("578BF9E848F70000"),
          rel32_jump(0x4415F0, entry["tech_handler"], 8),
          "route Tech-screen control 13 through the Origins menu")
    patch(0x4AF12, bytes.fromhex("8BC68B4C2424"),
          rel32_jump(0x44AF12, entry["detail_ctor"], 6),
          "append the stock-styled Upgrades control to Villager Detail")
    patch(0x4BC20, bytes.fromhex("83EC18A1A8974D00"),
          rel32_jump(0x44BC20, entry["detail_handler"], 8),
          "route the added Detail control through the villager-upgrade menu")
    if bytes(payload[0x180:0x1A8]) != BARREL_SELECTOR_BODY_REPAIRED:
        raise RuntimeError(
            "D37 VV5 selector body assembly drifted from the exact repaired bytes: "
            + bytes(payload[0x180:0x1A8]).hex().upper()
        )
    patch(PAYLOAD_FILE_OFFSET, b"\0" * len(payload), bytes(payload),
          "install the VV5 Origins menus and mechanics in the unused .shr section")

    patch_mode_overrides = {
        "experimental_expanded_256": [
            {
                "offset": "0x237B0",
                "before": detoured_tech_hook.hex().upper(),
                "after": stock_tech_hook.hex().upper(),
                "purpose": "restore the exact stock VV5 tech-writer bytes in expanded mode; no expanded Tech Doubler detour is emitted",
            },
            {
                "offset": "0x1EB6F",
                "before": detoured_food_hook.hex().upper(),
                "after": stock_food_hook.hex().upper(),
                "purpose": "restore the exact stock VV5 food-writer bytes in expanded mode; no expanded Food Doubler detour is emitted",
            }
        ],
        "experimental_expanded_256_progression": [
            {
                "offset": "0x237B0",
                "before": detoured_tech_hook.hex().upper(),
                "after": stock_tech_hook.hex().upper(),
                "purpose": "restore the exact stock VV5 tech-writer bytes in expanded mode; no expanded Tech Doubler detour is emitted",
            },
            {
                "offset": "0x1EB6F",
                "before": detoured_food_hook.hex().upper(),
                "after": stock_food_hook.hex().upper(),
                "purpose": "restore the exact stock VV5 food-writer bytes in expanded mode; no expanded Food Doubler detour is emitted",
            }
        ],
    }

    rendered = bytearray(original)
    for item in patches:
        offset = int(str(item["offset"]), 16)
        replacement = bytes.fromhex(str(item["after"]))
        rendered[offset : offset + len(replacement)] = replacement
    for relocation in expanded_shr_relocations:
        offset = int(relocation["offset"], 0)
        expected_before = bytes.fromhex(relocation["before"])
        actual = bytes(rendered[offset : offset + len(expected_before)])
        if actual != expected_before:
            raise RuntimeError(
                "IDA relocation ledger guard drift at "
                f"{relocation['offset']}: expected {expected_before.hex().upper()}, "
                f"got {actual.hex().upper()}"
            )
    OUT_EXE.write_bytes(rendered)
    OUT_JSON.write_text(json.dumps(patches, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "id": "vv5_enable_origins_exclusive_features",
        "game_id": "vv5",
        "running_preference_id": RUNNING_PREFERENCE_ID,
        "running_preference_evidence": {"source": "exact stock executable embedded preference table", "table_file_offset": "0xAEF60", "entry_name": "running"},
        "name": "Enable Origins-Exclusive Features",
        "description": (
            "Inspired by the Virtual Villagers 1 mobile port where these exclusive "
            "Origins upgrades originated, this selected-upgrades port adds icon-based "
            "Origins Upgrades. The native Time Warp (the stock route advances exactly 3 "
            "displayed villager years), Island Event, and Barrel of Babies "
            "rows are retained but disabled until their Heathen-safe target paths are "
            "proved; selecting one reports that it is unavailable. The stock-layout Tech "
            "Point and Food Point Doublers are available for their configured 500,000-tech-point "
            "purchases; each existing owned doubler remains removable at zero cost with zero "
            "refund, and each removed doubler can be repurchased at the full configured price "
            "in stock layout. Expanded-256 keeps both new purchases unavailable while preserving "
            "owned Remove. The legacy Cure row and command 5 are withdrawn, unavailable, "
            "bypassed by the EB5F containment gate, unreachable, and not part of this candidate; "
            "Full Heal/Cure All repair remains pending. "
            "Villager Upgrades include Grant Youth (floor age 5), six-skill Full "
            "Mastery, Set Age to 18, and the historical Grant Running label. Grant "
            "Running is STOP/hidden contract evidence only; the legacy preference "
            "helper is not native ABI proof and no selectable or runtime-ready "
            "Running action is exposed. VV5 Food Mastery is technology ID 4: the upgrade from level 1 to 2 costs 3,000 tech points and the upgrade from level 2 to 3 costs 40,000 tech points; central food writer 0x41EB40 applies positive A as A, A+floor(A/2), or 2A before food storage, statistics, and other downstream channels; zero and negative inputs bypass mastery. Ordinary collection return 0x414970 is eligible: base 6/35 becomes 6/35, 9/52, or 12/70 by mastery level. The Food Point Doubler runs after mastery and doubles the final positive eligible delta once. Island Event, startup, consumption, and unknown callers remain native. The stock Tech wrapper at 0x4237B0 is the exact six-return positive whitelist to .shr 0x7B2A00; 0x419EA3 clothing refunds remain native. The stock Food wrapper is the exact positive whitelist at 0x41EB6F to .shr 0x7B2B00. Expanded-256 restores both native five-byte hooks and keeps new doubler purchases unavailable pending complete rel32 relocation proof."
        ),
        "output_tag": "Origins Exclusive Features",
        "companion_files": [
            {
                "source": "assets/origins/VVFP Origins Icons.dll",
                "destination": "VVFP Origins Icons.dll",
                "sha256": hashlib.sha256(COMPANION.read_bytes()).hexdigest().upper(),
            }
        ],
        "doubler_evidence": {
            "build": {
                "filename": STOCK.name,
                "size": 991232,
                "sha256": "92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D",
            },
            "positive_tech_writer": "0x4237B0",
            "tech_positive_returns": ["0x4147BE", "0x4147DD", "0x4147F9", "0x46DE4D", "0x46DE7C", "0x46DEA5"],
            "tech_excluded_refund_return": "0x419EA3",
            "tech_exclusions": [
                "all 16 Island Event outcomes",
                "all eight writer tail paths",
                "technology purchase/spending/deduction paths",
                "zero and negative deltas",
                "unknown caller returns",
            ],
            "positive_food_writer": "0x41EB40 before storage/statistics channels",
            "food_mastery": {
                "technology_id": 4,
                "levels": {"1": "A", "2": "A+floor(A/2)", "3": "2A"},
                "costs": {"level_1_to_2": 3000, "level_2_to_3": 40000},
                "zero_negative_inputs": "bypass mastery",
                "collection_return": "0x414970",
                "collection_base_to_native": {"6": [6, 9, 12], "35": [35, 52, 70]},
            },
            "collection_adjustment": "Ordinary collection return 0x414970 supplies base 6/35; native Food Mastery produces 6/35, 9/52, or 12/70 after the level 1 to 2 (3,000 tech points) and level 2 to 3 (40,000 tech points) upgrades. The Food Point Doubler must follow this transform and double the final positive eligible delta once.",
            "island_event_producers": ["Island Event, startup, consumption, and unknown callers remain native; unknown callers cannot match return 0x414970"],
            "tech_writer_hook": {
                "virtual_address": "0x4237B0",
                "file_offset": "0x237B0",
                "before": "568B742408",
                "after": "E94BF23800",
                "wrapper_virtual_address": "0x7B2A00",
                "wrapper_file_offset": "0xDBA00",
                "wrapper_bytes": "8B44240485C07E46F70588D3510001000000743A813C24BE474100742D813C24DD4741007424813C24F9474100741B813C244DDE46007412813C247CDE46007409813C24A5DE46007504D1642404568B7424080131E95D0DC7FF",
                "ownership_address": "0x51D388",
                "ownership_mask": "0x1",
                "eligible_returns": ["0x4147BE", "0x4147DD", "0x4147F9", "0x46DE4D", "0x46DE7C", "0x46DEA5"],
                "excluded_refund_return": "0x419EA3",
                "branch_destinations": ["0x7B2A4A", "0x7B2A4E", "0x4237B7"]
            },
            "stock_hook": {
                "virtual_address": "0x41EB6F",
                "file_offset": "0x1EB6F",
                "before": "85F67E3456",
                "after": "E98C3F3900",
                "wrapper_virtual_address": "0x7B2B00",
                "wrapper_file_offset": "0xDBB00",
                "wrapper_bytes": "85F67E18F70588D3510002000000740C817C240870494100750201F685F67E0656E94EC0C6FFE97CC0C6FF",
                "ownership_address": "0x51D388",
                "ownership_mask": "0x2",
                "eligible_return": "0x414970",
                "branch_destinations": ["0x41EB74", "0x41EBA7"]
            },
            "hook_status": "stock-layout implemented: exact Tech six-return and Food positive-whitelist wrappers; expanded-256 restores both exact stock hooks and remains native for doubler runtime.",
        },
        "doubler_composition_contract": {
            "stacking": [
                "every exact-build collectible/collection effect that increases tech-point gain",
                "native Food Mastery technology adjustment",
            ],
            "exclusions": ["Island Event outcomes"],
            "food_mastery_status": "confirmed in exact-build disassembly; technology ID 4 and separate level 1 to 2 / level 2 to 3 native transforms documented",
            "status": "stock-layout implemented: Tech and Food Doublers run after their native adjustments; expanded-256 keeps both native writers and disables only new doubler purchases.",
        },
        "doubler_purchase_status": {
            "status": "stock-layout Tech and Food Doubler purchase/remove/repurchase implemented; expanded-256 new purchases are marker-gated unavailable",
            "new_purchase": "Tech and Food available in stock layout at 500,000 tech points after their exact positive-whitelist wrappers; both unavailable in expanded-256",
            "existing_owned": "removable at zero cost with zero refund",
            "repurchase": "full-price repurchase after zero-cost/no-refund removal in stock layout for both doublers; expanded-256 remains unavailable for new purchases",
        },
        "native_event_safety": {
            "disabled_rows": ["Time Warp", "Island Event", "Barrel of Babies"],
            "reason": "VV5 native time/event paths are not yet proven to avoid current Heathen record targeting.",
            "evidence_status": "STOP; no charge or native call is made for these rows",
        },
        "provenance": {"vv5_mockups": VV5_PROVENANCE},
        "patches": patches,
        "selector_repair": {
            "status": "candidate-only; base and individual Full Mastery records remain disabled",
            "stock_fingerprint": {
                "filename": "Virtual Villagers - New Believers.exe",
                "size": len(original),
                "sha256": expected,
            },
            "hook": {
                "file_offset": f"0x{BARREL_SELECTOR_HOOK_FILE_OFFSET:X}",
                "virtual_address": f"0x{BARREL_SELECTOR_HOOK_VA:X}",
                "before": BARREL_SELECTOR_HOOK_STOCK.hex().upper(),
                "after": BARREL_SELECTOR_HOOK_REPAIRED.hex().upper(),
                "uninstall_after": BARREL_SELECTOR_HOOK_STOCK.hex().upper(),
                "length": len(BARREL_SELECTOR_HOOK_STOCK),
            },
            "body": {
                "file_offset": f"0x{BARREL_SELECTOR_BODY_FILE_OFFSET:X}",
                "virtual_address": f"0x{BARREL_SELECTOR_BODY_VA:X}",
                "before": BARREL_SELECTOR_BODY_STOCK.hex().upper(),
                "after": BARREL_SELECTOR_BODY_REPAIRED.hex().upper(),
                "uninstall_after": BARREL_SELECTOR_BODY_STOCK.hex().upper(),
                "length": len(BARREL_SELECTOR_BODY_REPAIRED),
                "sha256": BARREL_SELECTOR_BODY_SHA256,
            },
            "native_call_virtual_address": "0x403660",
            "continuation_virtual_address": "0x41891A",
            "forbidden_branch_targets": ["0x418916", "0x418917", "0x418918", "0x418919"],
            "shr_guard": {
                "name": ".shr",
                "raw_range": "0xDB000..0xDBFFF",
                "virtual_address": "0x7B2000",
                "stock_characteristics": "0xD0000040",
                "candidate_characteristics": "0xF0000040",
                "header_patch": {"file_offset": "0x28C", "before": "400000D0", "after": "400000F0"},
                "payload_zero_preimage_required": True,
            },
            "atomic_install_uninstall": True,
        },
        "patch_mode_overrides": patch_mode_overrides,
        "expanded_shr_relocations": {
            "stock_virtual_address": f"0x{PAYLOAD_VA:X}",
            "expanded_virtual_address": f"0x{EXPANDED_PAYLOAD_VA:X}",
            "evidence": {
                "method": "IDA Pro 9.4 decoded instruction heads and operands; raw byte patterns are discovery-only and are not relocation proof",
                "exact_stock_sha256": expected,
                "disassembly_commit": "8dfccbd1b31e55f5168bb1c5ff23890bb98d9fdb",
                "current_feature_sites": len(expanded_shr_relocations),
                "payload_internal_absolute_sites": len(VV5_IDA_PAYLOAD_ABSOLUTE_RELOCATIONS),
                "cross_section_rel32_sites": len(VV5_IDA_CROSS_SECTION_REL32_RELOCATIONS),
                "external_absolute_sites": len(VV5_IDA_EXTERNAL_ABSOLUTE_RELOCATIONS),
                "expanded_mode_native_override_sites": sum(
                    item[4] is not None for item in VV5_IDA_CROSS_SECTION_REL32_RELOCATIONS
                ),
                "complete_current_feature_relocation_sites": (
                    len(VV5_IDA_CROSS_SECTION_REL32_RELOCATIONS)
                    + len(VV5_IDA_EXTERNAL_ABSOLUTE_RELOCATIONS)
                ),
            },
            "patches": expanded_shr_relocations,
        },
    }
    MANIFEST_JSON.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    used = max(i for i, value in enumerate(code) if value) + 1
    print(f"code bytes used: {used:#x}/{STRINGS_OFFSET:#x}")
    print(f"string bytes used: {len(strings):#x}/{PAYLOAD_SIZE - STRINGS_OFFSET:#x}")
    print(OUT_EXE)
    print(MANIFEST_JSON)


if __name__ == "__main__":
    main()
