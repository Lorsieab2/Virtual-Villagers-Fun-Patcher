"""Assemble the exact-build VV1 Origins-exclusive feature patch.

This is a developer helper. It emits guarded manifest edits and a patched
research executable; the user-facing patcher consumes the emitted edits.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - A New Home.exe"
OUT_DIR = ROOT / "research" / "vv1-origins-apk"
OUT_EXE = OUT_DIR / "Virtual Villagers - A New Home - Origins Feature Research.exe"
OUT_JSON = OUT_DIR / "vv1-origins-feature-patches.json"

sys.path.insert(0, str(ROOT / ".tools" / "keystone"))
from keystone import KS_ARCH_X86, KS_MODE_32, Ks  # noqa: E402


IMAGE_BASE = 0x400000
CODE_FILE_OFFSET = 0x56900
CODE_VA = IMAGE_BASE + CODE_FILE_OFFSET
STRINGS_FILE_OFFSET = 0x85D30
STRINGS_VA = IMAGE_BASE + STRINGS_FILE_OFFSET


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
    add_c_string(strings, s, "button_asset", "main_wide_button2.png")
    add_c_string(strings, s, "button_label", "Origins Upgrades")
    add_c_string(strings, s, "title", "Origins Upgrades")
    add_c_string(
        strings,
        s,
        "menu_format",
        "%s\n%i tech\n\nYes: Buy  No: Next  Cancel: Close",
    )
    for name, text in (
        ("name_time_warp", "Time Warp"),
        ("name_island_event", "Island Event"),
        ("name_barrel", "Barrel of Babies"),
        ("name_max_pop", "Bump Max Population"),
        ("name_youth", "Grant Youth"),
        ("name_mastery", "Grant Full Mastery"),
        ("name_running", "Grant Running"),
        ("name_tech_doubler", "Tech Point Doubler"),
        ("name_food_doubler", "Food Point Doubler"),
    ):
        add_c_string(strings, s, name, text)
    add_c_string(strings, s, "purchase_complete", "Purchased.")
    add_c_string(strings, s, "not_enough", "Not enough tech points.")
    add_c_string(strings, s, "select_villager", "Select a living villager first.")
    add_c_string(
        strings,
        s,
        "hard_cap",
        "VV1 already uses the 256-villager maximum.",
    )
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
    add_c_string(strings, s, "save_failed", "Could not save the doubler.")
    add_c_string(strings, s, "ini_section", "OriginsExclusiveFeatures")
    add_c_string(strings, s, "ini_tech", "TechPointDoubler")
    add_c_string(strings, s, "ini_food", "FoodPointDoubler")
    add_c_string(strings, s, "ini_one", "1")
    add_c_string(strings, s, "ini_file", "Origins Exclusive Features.ini")
    add_c_string(strings, s, "kernel32", "kernel32.dll")
    add_c_string(strings, s, "write_profile", "WritePrivateProfileStringA")

    names = [
        s["name_time_warp"],
        s["name_island_event"],
        s["name_barrel"],
        s["name_max_pop"],
        s["name_youth"],
        s["name_mastery"],
        s["name_running"],
        s["name_tech_doubler"],
        s["name_food_doubler"],
    ]
    costs = [50000, 30000, 75000, 250000, 50000, 100000, 40000, 500000, 500000]
    while len(strings) % 4:
        strings.append(0)
    s["name_table"] = STRINGS_VA + len(strings)
    for value in names:
        strings.extend(value.to_bytes(4, "little"))
    s["cost_table"] = STRINGS_VA + len(strings)
    for value in costs:
        strings.extend(value.to_bytes(4, "little"))
    if len(strings) > 0x2D0:
        raise RuntimeError(f"string/data block is too large: {len(strings)} bytes")

    # Fixed entry points inside the one guarded executable cave.
    handler_hook = CODE_VA
    constructor_hook = CODE_VA + 0x30
    menu = CODE_VA + 0xC0
    write_setting = CODE_VA + 0x3D0
    tech_increment = CODE_VA + 0x430
    food_increment = CODE_VA + 0x480
    running_hook = CODE_VA + 0x4D0

    code = bytearray(b"\x00" * 0x700)

    def put(va: int, source: str) -> None:
        payload = assemble(source, va)
        start = va - CODE_VA
        end = start + len(payload)
        if end > len(code):
            raise RuntimeError(f"code at {va:#x} exceeds cave")
        if any(code[start:end]):
            raise RuntimeError(f"code overlap at {va:#x} (payload {len(payload):#x} bytes)")
        code[start:end] = payload

    put(
        handler_hook,
        f"""
            cmp dword ptr [esp + 4], 8
            jne original_handler
            mov eax, dword ptr [esp + 8]
            test eax, eax
            je original_handler
            cmp dword ptr [eax + 4], 2
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
            push 0x{s['button_asset']:X}
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
            sub esp, 0x100
            mov esi, ecx
            xor ebx, ebx
        menu_loop:
            mov eax, dword ptr [0x{s['cost_table']:X} + ebx*4]
            mov edx, dword ptr [0x{s['name_table']:X} + ebx*4]
            lea edi, [esp]
            push eax
            push edx
            push 0x{s['menu_format']:X}
            push edi
            call dword ptr [0x457200]
            add esp, 0x10
            push 3
            push 0x{s['title']:X}
            push edi
            call 0x452DB6
            add esp, 0x0C
            cmp eax, 7
            je next_item
            cmp eax, 6
            jne menu_done

            cmp ebx, 3
            je hard_cap

            mov edi, dword ptr [esi + 0x0C]
            cmp ebx, 4
            jb pre_resource_item
            cmp ebx, 6
            jbe require_villager
            jmp check_owned

        require_villager:
            mov eax, dword ptr [edi + 0xAD34]
            cmp eax, 0x100
            jae no_villager
            imul eax, eax, 0x3D8
            mov edx, dword ptr [edi + 0xADE8]
            add edx, eax
            cmp byte ptr [edx + 0x28], 0
            je no_villager
            jmp charge

        pre_resource_item:
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
            cmp ebx, 7
            jb charge
            mov eax, 0x{s['ini_food']:X}
            cmp ebx, 8
            je read_owned
            mov eax, 0x{s['ini_tech']:X}
        read_owned:
            push 0x{s['ini_file']:X}
            push 0
            push eax
            push 0x{s['ini_section']:X}
            call dword ptr [0x457118]
            test eax, eax
            jne owned

        charge:
            mov eax, dword ptr [0x{s['cost_table']:X} + ebx*4]
            cmp dword ptr [edi + 0xA2FC], eax
            jb insufficient
            sub dword ptr [edi + 0xA2FC], eax

            cmp ebx, 0
            je do_time_warp
            cmp ebx, 1
            je do_island_event
            cmp ebx, 2
            je do_barrel
            cmp ebx, 4
            je do_youth
            cmp ebx, 5
            je do_mastery
            cmp ebx, 6
            je do_running
            cmp ebx, 7
            je do_tech_doubler
            jmp do_food_doubler

        do_time_warp:
            mov eax, 21600
            mov ecx, dword ptr [edi + 0xA318]
            cmp ecx, 3
            jne time_not_three
            mov eax, 10800
        time_not_three:
            cmp ecx, 12
            jne time_apply
            mov eax, 43200
        time_apply:
            sub dword ptr [0x4860F0], eax
            jmp success

        do_island_event:
            mov dword ptr [edi + 0xA300], 0
            mov eax, 0x{s['event_queued']:X}
            jmp show_and_done

        do_barrel:
            xor eax, eax
        barrel_loop:
            cmp eax, 3
            jae barrel_done
            push eax
            mov ecx, dword ptr [edi + 0xADE8]
            call 0x43A1A0
            test al, al
            pop eax
            je barrel_done
            push eax
            push 20
            call 0x402F10
            add esp, 4
            add eax, 70
            push eax
            push 0
            push 0
            push 0
            push -1
            mov ecx, dword ptr [edi + 0xADE8]
            call 0x43C350
            pop eax
            inc eax
            jmp barrel_loop
        barrel_done:
            mov eax, 0x{s['barrel_villagers']:X}
            jmp show_and_done

        do_youth:
            mov eax, dword ptr [edx + 0x348]
            sub eax, 700
            cmp eax, 100
            jge youth_age_ready
            mov eax, 100
        youth_age_ready:
            mov dword ptr [edx + 0x348], eax
            cmp dword ptr [edx + 0x358], 0
            je youth_not_pregnant
            lea ecx, [eax - 1]
            mov dword ptr [edx + 0x34C], ecx
            sub eax, 42
            mov dword ptr [edx + 0x358], eax
            jmp success
        youth_not_pregnant:
            mov dword ptr [edx + 0x34C], eax
            jmp success

        do_mastery:
            mov dword ptr [edx + 0x3BC], 90
            mov dword ptr [edx + 0x3C0], 90
            mov dword ptr [edx + 0x3C4], 90
            mov dword ptr [edx + 0x3C8], 90
            mov dword ptr [edx + 0x3CC], 90
            jmp success

        do_running:
            mov dword ptr [edx + 0x3D4], 10101010
            mov dword ptr [edx + 0x58], 300
            jmp success

        do_tech_doubler:
            mov eax, 0x{s['ini_tech']:X}
            jmp save_doubler
        do_food_doubler:
            mov eax, 0x{s['ini_food']:X}
        save_doubler:
            call 0x{write_setting:X}
            test eax, eax
            jne success
            mov eax, dword ptr [0x{s['cost_table']:X} + ebx*4]
            add dword ptr [edi + 0xA2FC], eax
            mov eax, 0x{s['save_failed']:X}
            jmp show_and_done

        success:
            mov eax, 0x{s['purchase_complete']:X}
            jmp show_and_done
        insufficient:
            mov eax, 0x{s['not_enough']:X}
            jmp show_and_done
        no_villager:
            mov eax, 0x{s['select_villager']:X}
            jmp show_and_done
        owned:
            mov eax, 0x{s['already_owned']:X}
            jmp show_and_done
        hard_cap:
            mov eax, 0x{s['hard_cap']:X}
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

        next_item:
            inc ebx
            cmp ebx, 9
            jb menu_loop
            xor ebx, ebx
            jmp menu_loop

        menu_done:
            add esp, 0x100
            pop edi
            pop esi
            pop ebx
            ret
        """,
    )

    put(
        write_setting,
        f"""
            push ebx
            mov ebx, eax
            push 0x{s['kernel32']:X}
            call dword ptr [0x4570D0]
            test eax, eax
            je write_failed
            push 0x{s['write_profile']:X}
            push eax
            call dword ptr [0x4570D4]
            test eax, eax
            je write_failed
            push 0x{s['ini_file']:X}
            push 0x{s['ini_one']:X}
            push ebx
            push 0x{s['ini_section']:X}
            call eax
            pop ebx
            ret
        write_failed:
            xor eax, eax
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
            jle tech_apply
            push 0x{s['ini_file']:X}
            push 0
            push 0x{s['ini_tech']:X}
            push 0x{s['ini_section']:X}
            call dword ptr [0x457118]
            test eax, eax
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
            push 0x{s['ini_file']:X}
            push 0
            push 0x{s['ini_food']:X}
            push 0x{s['ini_section']:X}
            call dword ptr [0x457118]
            test eax, eax
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
        running_hook,
        """
            cmp dword ptr [esi + 0x3D4], 10101010
            jne no_running_upgrade
            mov dword ptr [esi + 0x58], 300
        no_running_upgrade:
            mov dword ptr [esi + 0x20], 1
            jmp 0x43CD19
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
        0x1D120,
        original[0x1D120 : 0x1D125],
        rel32_jump(0x41D120, tech_increment),
        "double only positive tech-point awards after the persistent Tech Point Doubler is owned",
    )
    patch(
        0x1D140,
        original[0x1D140 : 0x1D145],
        rel32_jump(0x41D140, food_increment),
        "double only positive food awards after the persistent Food Point Doubler is owned",
    )
    patch(
        0x3CD12,
        bytes.fromhex("C7462001000000"),
        rel32_jump(0x43CD12, running_hook) + b"\x90\x90",
        "honor the saved Grant Running flag without consuming a villager like/dislike slot",
    )
    patch(
        CODE_FILE_OFFSET,
        b"\x00" * len(code),
        bytes(code),
        "install the guarded Origins-exclusive Tech-screen menu and upgrade implementations",
    )
    patch(
        STRINGS_FILE_OFFSET,
        b"\x00" * len(strings),
        bytes(strings),
        "install Origins upgrade labels, descriptions, costs, and persistent doubler keys",
    )

    rendered = bytearray(original)
    for item in patches:
        offset = int(item["offset"], 16)
        payload = bytes.fromhex(item["after"])
        rendered[offset : offset + len(payload)] = payload
    OUT_EXE.write_bytes(rendered)
    OUT_JSON.write_text(json.dumps(patches, indent=2) + "\n", encoding="utf-8")
    print(f"code bytes used: {max(i for i, value in enumerate(code) if value) + 1:#x}/0x700")
    print(f"string bytes used: {len(strings):#x}/0x2d0")
    print(OUT_JSON)
    print(OUT_EXE)


if __name__ == "__main__":
    main()
