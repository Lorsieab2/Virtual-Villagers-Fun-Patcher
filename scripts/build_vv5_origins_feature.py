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

sys.path.insert(0, str(ROOT / ".tools/keystone"))
from keystone import KS_ARCH_X86, KS_MODE_32, Ks  # noqa: E402

IMAGE_BASE = 0x400000
PAYLOAD_FILE_OFFSET = 0xDB000
PAYLOAD_VA = 0x7B2000
EXPANDED_PAYLOAD_VA = 0x8EB000
PAYLOAD_SIZE = 0x1000
STRINGS_OFFSET = 0xD00
STRINGS_VA = PAYLOAD_VA + STRINGS_OFFSET


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
        ("paused", "Time Warp is unavailable while the game is paused."),
        ("time_done", "Time Warp advanced every villager by 3 displayed years."),
        ("capacity", "The village population is already at maximum capacity."),
        ("running_unavailable", "Running cannot be added because all Like slots are full."),
        ("icons_dll", "VVFP Origins Icons.dll"),
        ("dialog_export", "ShowOriginsUpgradeMenuState"),
        ("user32", "USER32.dll"),
        ("message_box", "MessageBoxA"),
    ):
        add_c_string(strings, s, name, value)
    while len(strings) % 4:
        strings.append(0)
    s["tech_costs"] = STRINGS_VA + len(strings)
    for value in (50000, 30000, 75000, 500000, 500000):
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
            cmp dword ptr [esp + 8], 13
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
            push 72
            call 0x44FA20
            push 0
            push esi
            push 722
            push 180
            push eax
            push 13
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
            cmp dword ptr [esp + 8], 13
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
            push 72
            call 0x44FA20
            push 0
            push esi
            push 700
            push 180
            push eax
            push 13
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
            mov esi, dword ptr [esp + eax*4 + 0x96C]
            test dword ptr [0x51D388], 4
            jz done
            and dword ptr [0x51D388], 0xFFFFFFFB
            mov esi, 30
        done:
            jmp 0x418916
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
            jz tech_clear
            or eax, 8
        tech_clear:
            test dword ptr [0x51D388], 2
            jz food_clear
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
            cmp ebx, 4
            je remove_food
            test dword ptr [0x51D388], 1
            jz preflight
            and dword ptr [0x51D388], 0xFFFFFFFE
            mov eax, 0x{s['removed']:X}
            jmp status
        remove_food:
            test dword ptr [0x51D388], 2
            jz preflight
            and dword ptr [0x51D388], 0xFFFFFFFD
            mov eax, 0x{s['removed']:X}
            jmp status
        preflight:
            call 0x425950
            mov edi, eax
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
            or dword ptr [0x51D388], 2
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
        success:
            mov eax, 0x{s['purchased']:X}
            jmp status
        insufficient:
            mov eax, 0x{s['not_enough']:X}
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
            cmp dword ptr [eax], 38
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
            cmp dword ptr [eax], 38
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
            cmp ebx, 2
            jne detail_charge
            lea eax, [edx + 8028]
            mov ecx, 3
        running_preflight:
            cmp dword ptr [eax], 38
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
            cmp dword ptr [ecx], 38
            je remove_dislikes
            cmp dword ptr [ecx], -1
            je store_like
            add ecx, 4
            dec eax
            jne find_like
            mov eax, 0x{s['running_unavailable']:X}
            jmp detail_status
        store_like:
            mov dword ptr [ecx], 38
        remove_dislikes:
            lea ecx, [edx + 8040]
            mov eax, 3
        remove_loop:
            cmp dword ptr [ecx], 38
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
    tech_exclusions = (0x414D0D, 0x416569, 0x416657, 0x418757, 0x41876C)
    tech_checks = "\n".join(
        f"cmp dword ptr [esp], 0x{x:X}\nje apply" for x in tech_exclusions
    )
    put(
        "tech_increment",
        f"""
            mov eax, dword ptr [esp + 4]
            test eax, eax
            jle apply
            test dword ptr [0x51D388], 1
            jz apply
            {tech_checks}
            shl dword ptr [esp + 4], 1
        apply:
            push esi
            mov esi, dword ptr [esp + 8]
            add dword ptr [ecx], esi
            jmp 0x4237B7
        """,
    )
    food_exclusions = (0x414C2E, 0x41511E, 0x416D01, 0x418757, 0x41876C)
    food_checks = "\n".join(
        f"cmp dword ptr [esp + 8], 0x{x:X}\nje apply" for x in food_exclusions
    )
    put(
        "food_increment",
        f"""
            test esi, esi
            jle apply
            test dword ptr [0x51D388], 2
            jz apply
            {food_checks}
            add esi, esi
        apply:
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
    for payload_offset in range(len(payload) - 3):
        value = int.from_bytes(payload[payload_offset : payload_offset + 4], "little")
        if PAYLOAD_VA <= value < PAYLOAD_VA + PAYLOAD_SIZE:
            expanded_shr_relocations.append(
                {
                    "offset": f"0x{PAYLOAD_FILE_OFFSET + payload_offset:X}",
                    "before": payload[payload_offset : payload_offset + 4].hex().upper(),
                    "purpose": "relocate VV5 Origins .shr absolute pointer for expanded 256 mode",
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

    patch(0x28C, bytes.fromhex("400000D0"), bytes.fromhex("400000F0"),
          "make the stock shared payload section executable")
    patch(0x1890F, bytes.fromhex("8B7484146A64E8"),
          rel32_jump(0x41890F, entry["barrel_selector"], 7),
          "consume the one-shot purchase marker and force native event index 30")
    patch(0x1EB6F, bytes.fromhex("85F67E3456"),
          rel32_jump(0x41EB6F, entry["food_increment"]),
          "double positive non-Island-Event food after stock mastery adjustments")
    patch(0x237B0, bytes.fromhex("568B742408"),
          rel32_jump(0x4237B0, entry["tech_increment"]),
          "double positive non-Island-Event tech awards for the current save")
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
    patch(PAYLOAD_FILE_OFFSET, b"\0" * len(payload), bytes(payload),
          "install the VV5 Origins menus and mechanics in the unused .shr section")

    rendered = bytearray(original)
    for item in patches:
        offset = int(str(item["offset"]), 16)
        replacement = bytes.fromhex(str(item["after"]))
        rendered[offset : offset + len(replacement)] = replacement
    OUT_EXE.write_bytes(rendered)
    OUT_JSON.write_text(json.dumps(patches, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "id": "vv5_enable_origins_exclusive_features",
        "game_id": "vv5",
        "name": "Enable Origins-Exclusive Features",
        "description": (
            "Adds icon-based Origins Upgrades. Time Warp advances exactly 3 "
            "displayed villager years at half, normal, or double speed. Island "
            "Event uses the stock scheduler. Barrel of Babies forces the literal "
            "native event and requires three free occupied-or-reserved physical "
            "slots in both 150- and 256-record games. Adds removable, save-scoped "
            "Tech Point and Food Point Doublers that exclude Island Event awards. "
            "Villager Upgrades include Grant Youth (floor age 5), six-skill Full "
            "Mastery, Set Age to 18, and Grant Running. Grant Running only adds "
            "trait 38 to a free normal Like slot and removes trait 38 from "
            "Dislikes; it never changes movement or speed logic."
        ),
        "output_tag": "Origins Exclusive Features",
        "companion_files": [
            {
                "source": "assets/origins/VVFP Origins Icons.dll",
                "destination": "VVFP Origins Icons.dll",
                "sha256": hashlib.sha256(COMPANION.read_bytes()).hexdigest().upper(),
            }
        ],
        "patches": patches,
        "expanded_shr_relocations": {
            "stock_virtual_address": f"0x{PAYLOAD_VA:X}",
            "expanded_virtual_address": f"0x{EXPANDED_PAYLOAD_VA:X}",
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
