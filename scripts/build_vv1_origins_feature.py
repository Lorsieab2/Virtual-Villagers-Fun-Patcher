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
    add_c_string(strings, s, "button_label", "Upgrades")
    add_c_string(strings, s, "detail_button_label", "Upgrades")
    add_c_string(strings, s, "title", "Origins Upgrades")
    add_c_string(strings, s, "detail_title", "Villager Upgrades")
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
        ("name_youth", "Grant Youth"),
        ("name_mastery", "Grant Full Mastery"),
        ("name_running", "Grant Running"),
        ("name_age_18", "Set Age to 18"),
        ("name_tech_doubler", "Tech Point Doubler"),
        ("name_food_doubler", "Food Point Doubler"),
    ):
        add_c_string(strings, s, name, text)
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
    add_c_string(strings, s, "save_failed", "Could not save the doubler.")
    add_c_string(strings, s, "running_unavailable", "Running cannot be added.")
    add_c_string(strings, s, "icons_dll", "VVFP Origins Icons.dll")
    add_c_string(strings, s, "show_icon_dialog", "ShowOriginsUpgradeMenu")

    tech_names = [
        s["name_time_warp"],
        s["name_island_event"],
        s["name_barrel"],
        s["name_tech_doubler"],
        s["name_food_doubler"],
    ]
    tech_costs = [50000, 30000, 75000, 500000, 500000]
    detail_names = [
        s["name_youth"],
        s["name_mastery"],
        s["name_running"],
        s["name_age_18"],
    ]
    detail_costs = [50000, 100000, 40000, 50000]
    while len(strings) % 4:
        strings.append(0)
    s["tech_name_table"] = STRINGS_VA + len(strings)
    for value in tech_names:
        strings.extend(value.to_bytes(4, "little"))
    s["tech_cost_table"] = STRINGS_VA + len(strings)
    for value in tech_costs:
        strings.extend(value.to_bytes(4, "little"))
    s["detail_name_table"] = STRINGS_VA + len(strings)
    for value in detail_names:
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
    show_dialog = CODE_VA + 0x2E0
    tech_increment = CODE_VA + 0x360
    food_increment = CODE_VA + 0x3B0
    sparkle_hook = CODE_VA + 0x3F0
    event_dispatch_hook = CODE_VA + 0x450
    detail_handler_hook = CODE_VA + 0x490
    detail_constructor_hook = CODE_VA + 0x4C0
    detail_menu = CODE_VA + 0x521

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
            or edi, 1
        tech_not_owned_for_menu:
            mov eax, dword ptr [esi + 0x0C]
            cmp dword ptr [eax + 0xAD4C], 0
            je food_not_owned_for_menu
            or edi, 2
        food_not_owned_for_menu:
            push edi
            push 0
            call 0x{show_dialog:X}
            cmp eax, -1
            je menu_done
            mov ebx, eax

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
            cmp ebx, 3
            jb charge
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
            push 0x50F0
            call 0x44AF03
            add esp, 4
            test eax, eax
            je barrel_allocation_failed
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
            call 0x42A6A0
            mov eax, 0x{s['purchase_complete']:X}
            jmp show_and_done
        barrel_allocation_failed:
            mov eax, 0x{s['save_failed']:X}
            jmp show_and_done

        do_tech_doubler:
            mov dword ptr [edi + 0xAD48], 1
            jmp success
        do_food_doubler:
            mov dword ptr [edi + 0xAD4C], 1
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
            jmp menu_loop

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
            push 0x{s['show_icon_dialog']:X}
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
        sparkle_hook,
        """
            call 0x41AFA0
            pushad
            push 50
            call 0x402F10
            add esp, 4
            cmp eax, 2
            jae sparkle_done
            mov ebp, dword ptr [esi + 0x10]
            cmp dword ptr [ebp + 0xAD48], 0
            je sparkle_food
            mov ecx, dword ptr [esi + 8]
            test ecx, ecx
            je sparkle_food
            push 1
            push 0x53E
            push 0x443
            push 4
            call 0x41AFA0
        sparkle_food:
            cmp dword ptr [ebp + 0xAD4C], 0
            je sparkle_done
            mov ecx, dword ptr [esi + 8]
            test ecx, ecx
            je sparkle_done
            push 1
            push 0x462
            push 0x47A
            push 4
            call 0x41AFA0
        sparkle_done:
            popad
            ret
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

            mov edi, dword ptr [esi + 0x0C]
            mov ecx, dword ptr [edi + 0xAD34]
            imul ecx, ecx, 0x3D8
            mov edx, dword ptr [esi + 0x10]
            add edx, ecx
            cmp ebx, 2
            jne detail_charge
            lea eax, [edx + 0x398]
            mov ecx, 3
        running_preflight:
            cmp dword ptr [eax], 38
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
            mov eax, 3
        running_find_like_slot:
            cmp dword ptr [ecx], 38
            je running_remove_dislikes
            cmp dword ptr [ecx], -1
            je running_store_like
            add ecx, 4
            dec eax
            jne running_find_like_slot
            jmp detail_running_unavailable
        running_store_like:
            mov dword ptr [ecx], 38
        running_remove_dislikes:
            lea ecx, [edx + 0x3A8]
            mov eax, 3
        running_dislike_loop:
            cmp dword ptr [ecx], 38
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
            mov dword ptr [edx + 0x3BC], 90
            mov dword ptr [edx + 0x3C0], 90
            mov dword ptr [edx + 0x3C4], 90
            mov dword ptr [edx + 0x3C8], 90
            mov dword ptr [edx + 0x3CC], 90
            cmp dword ptr [edx + 0x3D0], 0
            jne detail_success
            mov dword ptr [edx + 0x3D0], 1
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
        "double positive non-Island-Event tech-point awards after the current save owns the Tech Point Doubler; the research table also sparkles while it is active",
    )
    patch(
        0x1D140,
        original[0x1D140 : 0x1D145],
        rel32_jump(0x41D140, food_increment),
        "double positive non-Island-Event food awards after the current save owns the Food Point Doubler; the food bin also sparkles while it is active",
    )
    patch(
        0x23D85,
        bytes.fromhex("E81672FFFF"),
        rel32_jump(0x423D85, sparkle_hook),
        "retain the stock world sparkle call and add occasional save-scoped sparkles at the tech chest and food bin while their doublers are active",
    )
    patch(
        0x3CD22,
        bytes.fromhex("6A2653E8B6A5FFFF84C0740E"),
        b"\xEB\x0A" + b"\x90" * 10,
        "require the stock Running Like trait instead of treating no Running Dislike as Running",
    )
    patch(
        0x28470,
        bytes.fromhex("8B44240483F801"),
        rel32_jump(0x428470, event_dispatch_hook) + b"\x90\x90",
        "route the marked Barrel of Babies request through the native event result path",
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
        "game_id": "vv1",
        "name": "Enable Origins-Exclusive Features",
        "description": (
            "Adds an icon-based Upgrades screen containing Time Warp, Island Event, the "
            "native Barrel of Babies event with a three-space capacity guard, "
            "and removable 500,000-tech-point Tech Point Doubler and Food Point Doubler. "
            "The doublers do not multiply Island Event tech or food awards. They double other positive awards; each description also notes that its matching storage object sparkles while active, and the effect is stored in the current save rather than a global INI. Adds "
            "an icon-based Villager Upgrades screen containing Grant Youth, Grant Full "
            "Mastery, Grant Running, and Set Age to 18 for the displayed villager. Grant "
            "Full Mastery preserves a checked job preference and chooses Farming when "
            "none is checked so VV1 does not show the incomplete title Master. Grant Running adds running to an "
            "available Likes slot on the displayed villager, removes running from that "
            "villager's Dislikes slots, and refuses without charging when no Like slot is "
            "available; it does not alter movement speed, movement initialization, or any "
            "custom running flag."
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
