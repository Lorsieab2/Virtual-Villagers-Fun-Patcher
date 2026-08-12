"""Build the active VV5 Task9 owner-safe native action extension.

This generator treats ``data/vv5_origins_feature.json`` as an immutable input.
It clones its exact patch/relocation ledger, replaces only the active menu entry
paths and guarded constructor geometry, and appends one generated RX section.
"""

from __future__ import annotations

import hashlib
import json
import struct
import sys
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research/stock-executables/Virtual Villagers - New Believers.exe"
ACTIVE = ROOT / "data/vv5_origins_feature.json"
COMPANION = ROOT / "data/candidates/VVFP VV5 Task9 Origins Icons.dll"
OUT = ROOT / "data/vv5_task9_native_actions.json"
MAP_OUT = ROOT / "data/candidates/vv5_task9_native_actions_map.json"
SOURCE_PATHS = {
    "task9_builder": "scripts/build_vv5_task9_native_actions.py",
    "companion_c": "native/vv5_task9_origins/vv5_task9_origins.c",
    "companion_def": "native/vv5_task9_origins/vv5_task9_origins.def",
    "companion_rc": "native/vv5_task9_origins/vv5_task9_origins.rc",
    "companion_builder": "scripts/build_vv5_task9_origins_dll.ps1",
    "individual_reference": "src/vv5_individual_transactions.py",
    "full_heal_reference": "src/vv5_full_heal.py",
    "active_base": "data/vv5_origins_feature.json",
    "task8_overlay": "data/candidates/vv5_post_prototype_overlay.json",
    "atomic_generator": "src/expanded_atomic_writer.py",
    "atomic_contract": "data/expanded_atomic_writer_integration.json",
}
ATOMIC_CORE_COMMIT = "c4e5fe76d1de258d5d4baeac77cbea842b206cd7"
ATOMIC_SOURCE_TEXT_SHA256 = {
    "atomic_generator": "0424B3B56CB4093176A8B429472FCDF04043CBFC22424EBBDE37058EA1A8F72E",
    "atomic_contract": "1B7068D0679CA896706AA201D27726AF612FD167C0406C5D509774E40728F6A6",
}

STOCK_SHA256 = "92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D"
ACTIVE_SHA256 = "F9643E2B7D115B6ECDDD4D8AD4BFFC73F2FF6937995E40E991041B6AF6463D44"
ACTIVE_SOURCE_TEXT_SHA256 = "6AFF1A8E69234C61CB2D1878C46FA91B0AAA721FC5F29C5B42A678F61BAB8528"
C342_COUNT = 66
C342_ROWS_SHA256 = "14E460773ADC065E053FA30921ED01D33A5F36AD49DC754CCD69127EA02C01B7"
TASK8_SOURCE_TEXT_SHA256 = "090ED9CA074F02F9321B2F8E0C470FD0AF18B235231DA94B6D38293360BC9510"

sys.path.insert(0, str(ROOT / ".tools/keystone-runtime"))
sys.path.insert(1, str(ROOT / ".tools/keystone"))
from keystone import KS_ARCH_X86, KS_MODE_32, Ks  # noqa: E402


IMAGE_BASE = 0x400000
PAYLOAD_OFFSET = 0xDB000
PAYLOAD_VA = 0x7B2000
EXPANDED_PAYLOAD_VA = 0x8EB000
PAGE_SIZE = 0x8000
STRIDE = 0x2F44
BOUND = 150
TASK9_EXPANDED_HOOK = {
    "offset": "0x415F0",
    "before": "E90B0A3700909090",
    "after": "E90B9A4A00909090",
    "purpose": "post-relocation: bind the Task9 Tech-screen command-13 hook to relocated Expanded .shr without changing C342",
}
TASK9_CROSS_SECTION_HOOKS = {
    "0x1890F": {"stock_target": "0x7B2180", "expanded_target": "0x8EB180", "expanded_policy": "frozen_c342"},
    "0x1EB6F": {"stock_target": "0x7B2B00", "expanded_target": "0x8EBB00", "expanded_policy": "native_override_preserved"},
    "0x237B0": {"stock_target": "0x7B2A00", "expanded_target": "0x8EBA00", "expanded_policy": "native_override_preserved"},
    "0x40A24": {"stock_target": "0x7B2040", "expanded_target": "0x8EB040", "expanded_policy": "frozen_c342"},
    "0x415F0": {"stock_target": "0x7B2000", "expanded_target": "0x8EB000", "expanded_policy": "task9_post_relocation"},
    "0x4AF12": {"stock_target": "0x7B2100", "expanded_target": "0x8EB100", "expanded_policy": "frozen_c342"},
    "0x4BC20": {"stock_target": "0x7B20C0", "expanded_target": "0x8EB0C0", "expanded_policy": "frozen_c342"},
}

LAYOUTS = {
    "collection_progression": {
        "append_offset": 0xF2000,
        "page_rva": 0x3C9000,
        "page_va": 0x7C9000,
        "section_count_offset": 0xFE,
        "section_count_before": 5,
        "size_of_image_offset": 0x148,
        "size_of_image_before": 0x3C9000,
        "section_header_offset": 0x2B8,
    },
    "immediate_fixed": {
        "append_offset": 0xF2000,
        "page_rva": 0x3C9000,
        "page_va": 0x7C9000,
        "section_count_offset": 0xFE,
        "section_count_before": 5,
        "size_of_image_offset": 0x148,
        "size_of_image_before": 0x3C9000,
        "section_header_offset": 0x2B8,
    },
    "experimental_expanded_256": {
        "append_offset": 0xF4000,
        "page_rva": 0x504000,
        "page_va": 0x904000,
        "section_count_offset": 0xFE,
        "section_count_before": 7,
        "size_of_image_offset": 0x148,
        "size_of_image_before": 0x504000,
        "section_header_offset": 0x308,
    },
    "experimental_expanded_256_progression": {
        "append_offset": 0xF4000,
        "page_rva": 0x504000,
        "page_va": 0x904000,
        "section_count_offset": 0xFE,
        "section_count_before": 7,
        "size_of_image_offset": 0x148,
        "size_of_image_before": 0x504000,
        "section_header_offset": 0x308,
    },
}

OFF = {
    "constructor_resource": 0x40,
    "tech_entry": 0x100,
    "detail_entry": 0x120,
    "modal_common": 0x140,
    "resolve_current": 0x580,
    "resolve_index": 0x5C0,
    "eligible": 0x620,
    "show_menu": 0x670,
    "confirm": 0x6D0,
    "status": 0x740,
    "resolve_manager": 0x7A0,
    "tech_menu": 0x840,
    "detail_menu": 0xB40,
    "age": 0xD40,
    "time_warp": 0x1040,
    "mastery": 0x1540,
    "running": 0x2240,
    "heal": 0x3400,
    "strings": 0x7000,
}

SIZES = {
    "constructor_resource": 0x20,
    "tech_entry": 0x20,
    "detail_entry": 0x20,
    "modal_common": 0x440,
    "resolve_current": 0x40,
    "resolve_index": 0x60,
    "eligible": 0x40,
    "show_menu": 0x60,
    "confirm": 0x70,
    "status": 0x50,
    "resolve_manager": 0xA0,
    "tech_menu": 0x300,
    "detail_menu": 0x200,
    "age": 0x300,
    "time_warp": 0x500,
    "mastery": 0xD00,
    "running": 0x11C0,
    "heal": 0x3C00,
}


def asm(source: str, address: int) -> bytes:
    encoded, _ = Ks(KS_ARCH_X86, KS_MODE_32).asm(source, address)
    return bytes(encoded)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def canonical_sha(value: object) -> str:
    return sha(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii"))


def source_text_sha(data: bytes) -> str:
    text = data.decode("utf-8-sig").replace("\r\n", "\n")
    if not text.endswith("\n"):
        text += "\n"
    return sha(text.encode("utf-8"))


def source_bindings() -> dict[str, dict[str, str]]:
    bindings = {
        name: {
            "path": path,
            "source_text_sha256": source_text_sha((ROOT / path).read_bytes()),
        }
        for name, path in SOURCE_PATHS.items()
    }
    for name, expected in ATOMIC_SOURCE_TEXT_SHA256.items():
        if bindings[name]["source_text_sha256"] != expected:
            raise RuntimeError(f"pinned {name} source drift")
    return bindings


def section_header(rva: int, raw: int) -> bytes:
    return (
        b".vv5t9\0\0"
        + PAGE_SIZE.to_bytes(4, "little")
        + rva.to_bytes(4, "little")
        + PAGE_SIZE.to_bytes(4, "little")
        + raw.to_bytes(4, "little")
        + b"\0" * 12
        + (0x60000020).to_bytes(4, "little")
    )


def build_strings(page: bytearray, page_va: int) -> dict[str, int]:
    values = (
        ("dll", b"VVFP Origins Icons.dll\0"),
        ("begin", b"BeginOriginsOwner\0"),
        ("end", b"EndOriginsOwner\0"),
        ("menu", b"ShowOriginsUpgradeMenuState\0"),
        ("confirm_export", b"ConfirmVV5Task9Action\0"),
        ("status_export", b"ShowVV5Task9Result\0"),
        ("sdl", b"SDL2.dll\0"),
        ("flags", b"SDL_GetWindowFlags\0"),
    )
    cursor = OFF["strings"]
    result: dict[str, int] = {}
    for name, value in values:
        result[name] = page_va + cursor
        page[cursor : cursor + len(value)] = value
        cursor += len(value)
    if cursor > PAGE_SIZE:
        raise RuntimeError("Task9 strings overflow")
    return result


def put(page: bytearray, page_va: int, name: str, source: str) -> bytes:
    payload = asm(source, page_va + OFF[name])
    if len(payload) > SIZES[name]:
        raise RuntimeError(f"{name} exceeds reserve: {len(payload):#x}/{SIZES[name]:#x}")
    start = OFF[name]
    if any(page[start : start + SIZES[name]]):
        raise RuntimeError(f"{name} overlaps generated data")
    page[start : start + len(payload)] = payload
    return payload


def build_modal(page: bytearray, page_va: int, s: dict[str, int]) -> dict[str, bytes]:
    tech = put(page, page_va, "tech_entry", f"mov eax, 0x{page_va + OFF['tech_menu']:X}; jmp 0x{page_va + OFF['modal_common']:X}")
    detail = put(page, page_va, "detail_entry", f"mov eax, 0x{page_va + OFF['detail_menu']:X}; jmp 0x{page_va + OFF['modal_common']:X}")
    common = put(
        page,
        page_va,
        "modal_common",
        f"""
            push ebp
            mov ebp, esp
            push ebx
            push esi
            push edi
            sub esp, 0x40
            mov dword ptr [ebp-0x10], eax
            mov dword ptr [ebp-0x14], ecx
            mov dword ptr [ebp-0x2C], -1
            mov dword ptr [ebp-0x30], 0
            mov dword ptr [ebp-0x34], 0
            mov dword ptr [ebp-0x38], 0
            test ecx, ecx
            jz done
            push 0x{s['dll']:X}
            call dword ptr [0x4951E0]
            test eax, eax
            jz done
            mov dword ptr [ebp-0x3C], eax
            push 0x{s['end']:X}
            push eax
            call dword ptr [0x4951DC]
            test eax, eax
            jz done
            mov dword ptr [ebp-0x34], eax
            push 0x{s['begin']:X}
            push dword ptr [ebp-0x3C]
            call dword ptr [0x4951DC]
            test eax, eax
            jz done
            mov dword ptr [ebp-0x38], 1
            call eax
            test eax, eax
            jz cleanup
            call reacquire
            test eax, eax
            jz cleanup
            mov dword ptr [ebp-0x18], esi
            mov dword ptr [ebp-0x1C], edi
            mov dword ptr [ebp-0x20], eax
            movzx ebx, byte ptr [edi+0x1E]
            mov dword ptr [ebp-0x24], ebx
            push 0x{s['sdl']:X}
            call dword ptr [0x4951D8]
            test eax, eax
            jz cleanup
            push 0x{s['flags']:X}
            push eax
            call dword ptr [0x4951DC]
            test eax, eax
            jz cleanup
            mov dword ptr [ebp-0x28], eax
            push dword ptr [ebp-0x20]
            call eax
            add esp, 4
            and eax, 0x1001
            cmp eax, 0
            je windowed
            cmp eax, 0x1001
            jne cleanup
            cmp dword ptr [ebp-0x24], 0
            jne cleanup
            mov ecx, esi
            call 0x40A270
            mov dword ptr [ebp-0x30], 1
            call reacquire
            cmp esi, dword ptr [ebp-0x18]
            jne invoke_failed
            cmp edi, dword ptr [ebp-0x1C]
            jne invoke_failed
            cmp eax, dword ptr [ebp-0x20]
            jne invoke_failed
            cmp byte ptr [edi+0x1E], 1
            jne invoke_failed
            push dword ptr [ebp-0x20]
            call dword ptr [ebp-0x28]
            add esp, 4
            and eax, 0x1001
            test eax, eax
            jne invoke_failed
            jmp invoke
        windowed:
            cmp dword ptr [ebp-0x24], 1
            jne cleanup
        invoke:
            mov ecx, dword ptr [ebp-0x14]
            call dword ptr [ebp-0x10]
            mov dword ptr [ebp-0x2C], eax
            jmp cleanup
        invoke_failed:
            mov dword ptr [ebp-0x2C], -1
        cleanup:
            cmp dword ptr [ebp-0x30], 0
            je end_owner
            call reacquire
            cmp esi, dword ptr [ebp-0x18]
            jne restore_failed
            cmp edi, dword ptr [ebp-0x1C]
            jne restore_failed
            cmp eax, dword ptr [ebp-0x20]
            jne restore_failed
            mov ecx, esi
            call 0x40A280
            call 0x4080C0
            test eax, eax
            jz restore_failed
            call reacquire
            cmp esi, dword ptr [ebp-0x18]
            jne restore_failed
            cmp edi, dword ptr [ebp-0x1C]
            jne restore_failed
            cmp eax, dword ptr [ebp-0x20]
            jne restore_failed
            push dword ptr [ebp-0x20]
            call dword ptr [ebp-0x28]
            add esp, 4
            and eax, 0x1001
            cmp byte ptr [edi+0x1E], 0
            jne restore_failed
            cmp eax, 0x1001
            je end_owner
        restore_failed:
            mov dword ptr [ebp-0x2C], -1
        end_owner:
            cmp dword ptr [ebp-0x38], 0
            je done
            call dword ptr [ebp-0x34]
        done:
            mov eax, dword ptr [ebp-0x2C]
            add esp, 0x40
            pop edi
            pop esi
            pop ebx
            pop ebp
            ret
        reacquire:
            mov esi, dword ptr [0x4DB0E8]
            test esi, esi
            jz reacquire_fail
            mov edi, dword ptr [esi]
            test edi, edi
            jz reacquire_fail
            mov eax, dword ptr [edi+0x38]
            test eax, eax
            jz reacquire_fail
            ret
        reacquire_fail:
            xor eax, eax
            ret
        """,
    )
    return {"tech_entry": tech, "detail_entry": detail, "modal_common": common}


def build_helpers(page: bytearray, page_va: int, s: dict[str, int]) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    result["constructor_resource"] = put(page, page_va, "constructor_resource", """
        call 0x44FBB0
        mov ecx, eax
        pop edx
        push 0x6A
        jmp edx
    """)
    result["resolve_current"] = put(page, page_va, "resolve_current", f"""
        push ebx
        call 0x425950
        test eax, eax
        jz invalid
        mov ebx, dword ptr [eax+0x17E24]
        cmp ebx, {BOUND}
        jae invalid
        push ebx
        call 0x{page_va + OFF['resolve_index']:X}
        mov edx, ebx
        pop ebx
        ret
    invalid:
        xor eax, eax
        xor edx, edx
        pop ebx
        ret
    """)
    result["resolve_index"] = put(page, page_va, "resolve_index", f"""
        push ebp
        mov ebp, esp
        push ebx
        mov ebx, dword ptr [ebp+8]
        cmp ebx, {BOUND}
        jae invalid
        push ebx
        mov ecx, 0x554148
        call 0x46F950
        test eax, eax
        jz invalid
        cmp byte ptr [eax+0x1CD4], 0
        je invalid
        cmp byte ptr [eax+0x1CE1], 0
        jne invalid
        cmp dword ptr [eax+0x1C40], 0
        jle invalid
        cmp byte ptr [eax+0x1CEC], 0
        jne invalid
        mov edx, ebx
        pop ebx
        pop ebp
        ret 4
    invalid:
        xor eax, eax
        xor edx, edx
        pop ebx
        pop ebp
        ret 4
    """)
    result["resolve_manager"] = put(page, page_va, "resolve_manager", """
        test eax, eax
        jz invalid
        mov ebx, dword ptr [eax+0x17E24]
        cmp ebx, 150
        jae invalid
        push ebx
        mov ecx, 0x554148
        call 0x46F950
        test eax, eax
        jz invalid
        cmp byte ptr [eax+0x1CD4], 0
        je invalid
        cmp byte ptr [eax+0x1CE1], 0
        jne invalid
        cmp dword ptr [eax+0x1C40], 0
        jle invalid
        cmp byte ptr [eax+0x1CEC], 0
        jne invalid
        pop ebx
        ret
    invalid:
        xor eax, eax
        pop ebx
        ret
    """)
    result["eligible"] = put(page, page_va, "eligible", """
        mov edx, dword ptr [esp+4]
        xor eax, eax
        test edx, edx
        jz done
        cmp byte ptr [edx+0x1CD4], 0
        je done
        cmp byte ptr [edx+0x1CE1], 0
        jne done
        cmp dword ptr [edx+0x1C40], 0
        jle done
        cmp byte ptr [edx+0x1CEC], 0
        jne done
        inc eax
    done:
        ret 4
    """)
    for name, export, argc in (
        ("show_menu", "menu", 2),
        ("confirm", "confirm_export", 3),
        ("status", "status_export", 4),
    ):
        pushes = "\n".join(
            f"push dword ptr [ebp+{8 + index * 4:#x}]"
            for index in range(argc - 1, -1, -1)
        )
        result[name] = put(page, page_va, name, f"""
            push ebp
            mov ebp, esp
            push ebx
            push 0x{s['dll']:X}
            call dword ptr [0x4951E0]
            test eax, eax
            jz unavailable
            push 0x{s[export]:X}
            push eax
            call dword ptr [0x4951DC]
            test eax, eax
            jz unavailable
            {pushes}
            call eax
            jmp done
        unavailable:
            mov eax, -1
        done:
            pop ebx
            pop ebp
            ret {argc * 4}
        """)
    return result


def status_call(page_va: int, action: str, status: int, a: str = "0", b: str = "0") -> str:
    return f"push {b}; push {a}; push {status}; push {action}; call 0x{page_va + OFF['status']:X}"


def build_menus(page: bytearray, page_va: int) -> dict[str, bytes]:
    tech = put(page, page_va, "tech_menu", f"""
        push ebp
        mov ebp, esp
        push ebx
        push esi
        push edi
    menu:
        mov eax, 0x700
        test dword ptr [0x51D388], 1
        jz tech_not_owned
        or eax, 8
        jmp food_state
    tech_not_owned:
        cmp dword ptr [0x41F1E6], 0x96
        je food_state
        or eax, 0x800
    food_state:
        test dword ptr [0x51D388], 2
        jz food_not_owned
        or eax, 16
        jmp show
    food_not_owned:
        cmp dword ptr [0x41F1E6], 0x96
        je show
        or eax, 0x1000
    show:
        push eax
        push 0
        call 0x{page_va + OFF['show_menu']:X}
        cmp eax, -1
        je done
        mov ebx, eax
        cmp ebx, 5
        ja done
        cmp ebx, 3
        jb unavailable
        cmp ebx, 5
        je heal
        mov edi, 1
        cmp ebx, 3
        je have_mask
        mov edi, 2
    have_mask:
        test dword ptr [0x51D388], edi
        jz purchase
        mov eax, edi
        not eax
        and dword ptr [0x51D388], eax
        test dword ptr [0x51D388], edi
        jnz retained
        {status_call(page_va, 'ebx', 11)}
        jmp menu
    purchase:
        cmp dword ptr [0x41F1E6], 0x96
        jne unavailable
        mov esi, dword ptr [0x51D5F8]
        cmp esi, 500000
        jb insufficient
        or dword ptr [0x51D388], edi
        test dword ptr [0x51D388], edi
        jz retained
        cmp dword ptr [0x51D5F8], esi
        jne retained
        push -500000
        mov ecx, 0x51D5F8
        call 0x4237B0
        mov eax, esi
        sub eax, 500000
        cmp dword ptr [0x51D5F8], eax
        jne charge_unknown
        {status_call(page_va, 'ebx', 12)}
        jmp menu
    heal:
        call 0x{page_va + OFF['heal']:X}
        jmp menu
    unavailable:
        {status_call(page_va, 'ebx', 10)}
        jmp menu
    insufficient:
        {status_call(page_va, 'ebx', 3)}
        jmp menu
    retained:
        {status_call(page_va, 'ebx', 6)}
        jmp menu
    charge_unknown:
        {status_call(page_va, 'ebx', 7)}
        jmp menu
    done:
        pop edi
        pop esi
        pop ebx
        pop ebp
        ret
    """)
    detail = put(page, page_va, "detail_menu", f"""
        push ebp
        mov ebp, esp
        push ebx
        push esi
        push edi
    menu:
        push 0
        push 1
        call 0x{page_va + OFF['show_menu']:X}
        cmp eax, -1
        je done
        mov ebx, eax
        cmp ebx, 3
        ja done
        cmp ebx, 0
        je age
        cmp ebx, 1
        je mastery
        cmp ebx, 2
        je running
        mov eax, 3
    age:
        call 0x{page_va + OFF['age']:X}
        jmp menu
    mastery:
        call 0x{page_va + OFF['mastery']:X}
        jmp menu
    running:
        call 0x{page_va + OFF['running']:X}
        jmp menu
    done:
        pop edi
        pop esi
        pop ebx
        pop ebp
        ret
    """)
    return {"tech_menu": tech, "detail_menu": detail}


def build_age(page: bytearray, page_va: int) -> bytes:
    return put(page, page_va, "age", f"""
        push ebp
        mov ebp, esp
        push ebx
        push esi
        push edi
        sub esp, 0x50
        mov dword ptr [ebp-0x10], eax
        call 0x{page_va + OFF['resolve_current']:X}
        test eax, eax
        jz invalid
        mov dword ptr [ebp-0x18], eax
        mov dword ptr [ebp-0x14], edx
        push eax
        call 0x{page_va + OFF['eligible']:X}
        test eax, eax
        jz invalid
        mov esi, dword ptr [ebp-0x18]
        mov eax, dword ptr [esi+0x1B8C]
        mov dword ptr [ebp-0x1C], eax
        mov eax, dword ptr [esi+0x1C3C]
        mov dword ptr [ebp-0x20], eax
        mov eax, dword ptr [esi+0x1C4C]
        mov dword ptr [ebp-0x24], eax
        mov eax, dword ptr [0x51D5F8]
        mov dword ptr [ebp-0x28], eax
        cmp dword ptr [ebp-0x10], 3
        je age18
        mov eax, dword ptr [ebp-0x1C]
        sub eax, 700
        jo invalid
        cmp eax, 100
        jge target_ready
        mov eax, 100
        jmp target_ready
    age18:
        mov eax, 360
    target_ready:
        mov dword ptr [ebp-0x2C], eax
        sub eax, dword ptr [ebp-0x1C]
        jo invalid
        mov dword ptr [ebp-0x30], eax
        test eax, eax
        jz no_change
        cmp dword ptr [ebp-0x28], 50000
        jb insufficient
        push 0
        push 0
        push dword ptr [ebp-0x10]
        call 0x{page_va + OFF['confirm']:X}
        cmp eax, 1
        jne cancelled
        push dword ptr [ebp-0x14]
        call 0x{page_va + OFF['resolve_index']:X}
        test eax, eax
        jz recheck
        cmp eax, dword ptr [ebp-0x18]
        jne recheck
        mov esi, eax
        push eax
        call 0x{page_va + OFF['eligible']:X}
        test eax, eax
        jz recheck
        mov eax, dword ptr [esi+0x1B8C]
        cmp eax, dword ptr [ebp-0x1C]
        jne recheck
        mov eax, dword ptr [esi+0x1C3C]
        cmp eax, dword ptr [ebp-0x20]
        jne recheck
        mov eax, dword ptr [esi+0x1C4C]
        cmp eax, dword ptr [ebp-0x24]
        jne recheck
        mov eax, dword ptr [0x51D5F8]
        cmp eax, dword ptr [ebp-0x28]
        jne recheck
        cmp eax, 50000
        jb insufficient
        mov eax, dword ptr [ebp-0x20]
        add eax, dword ptr [ebp-0x30]
        jo recheck
        mov dword ptr [ebp-0x34], eax
        mov eax, dword ptr [ebp-0x24]
        test eax, eax
        jz timer_ready
        add eax, dword ptr [ebp-0x30]
        jo recheck
    timer_ready:
        mov dword ptr [ebp-0x38], eax
        push dword ptr [ebp-0x30]
        lea ecx, [esi+0x1B8C]
        call 0x46F7F0
        mov eax, dword ptr [esi+0x1B8C]
        cmp eax, dword ptr [ebp-0x2C]
        jne retained
        mov eax, dword ptr [ebp-0x34]
        mov dword ptr [esi+0x1C3C], eax
        cmp dword ptr [esi+0x1C3C], eax
        jne retained
        cmp dword ptr [ebp-0x24], 0
        je postverify
        mov eax, dword ptr [ebp-0x38]
        mov dword ptr [esi+0x1C4C], eax
        cmp dword ptr [esi+0x1C4C], eax
        jne retained
    postverify:
        push dword ptr [ebp-0x14]
        call 0x{page_va + OFF['resolve_index']:X}
        cmp eax, dword ptr [ebp-0x18]
        jne retained
        mov esi, eax
        push eax
        call 0x{page_va + OFF['eligible']:X}
        test eax, eax
        jz retained
        mov eax, dword ptr [esi+0x1B8C]
        cmp eax, dword ptr [ebp-0x2C]
        jne retained
        mov eax, dword ptr [esi+0x1C3C]
        cmp eax, dword ptr [ebp-0x34]
        jne retained
        mov eax, dword ptr [esi+0x1C4C]
        cmp eax, dword ptr [ebp-0x38]
        jne retained
        mov eax, dword ptr [0x51D5F8]
        cmp eax, dword ptr [ebp-0x28]
        jne retained
        push -50000
        mov ecx, 0x51D5F8
        call 0x4237B0
        mov eax, dword ptr [ebp-0x28]
        sub eax, 50000
        cmp dword ptr [0x51D5F8], eax
        jne charge_unknown
        {status_call(page_va, 'dword ptr [ebp-0x10]', 0)}
        jmp done
    invalid:
        {status_call(page_va, 'dword ptr [ebp-0x10]', 2)}
        jmp done
    no_change:
        {status_call(page_va, 'dword ptr [ebp-0x10]', 1)}
        jmp done
    insufficient:
        {status_call(page_va, 'dword ptr [ebp-0x10]', 3)}
        jmp done
    cancelled:
        {status_call(page_va, 'dword ptr [ebp-0x10]', 4)}
        jmp done
    recheck:
        {status_call(page_va, 'dword ptr [ebp-0x10]', 5)}
        jmp done
    retained:
        {status_call(page_va, 'dword ptr [ebp-0x10]', 6)}
        jmp done
    charge_unknown:
        {status_call(page_va, 'dword ptr [ebp-0x10]', 7)}
    done:
        add esp, 0x50
        pop edi
        pop esi
        pop ebx
        pop ebp
        ret
    """)


def build_mastery(page: bytearray, page_va: int) -> bytes:
    return put(page, page_va, "mastery", f"""
        push ebp
        mov ebp, esp
        push ebx
        push esi
        push edi
        sub esp, 0x60
        mov dword ptr [ebp-0x20], 0
        call 0x{page_va + OFF['resolve_current']:X}
        test eax, eax
        jz invalid
        mov dword ptr [ebp-0x14], eax
        mov dword ptr [ebp-0x10], edx
        push eax
        call 0x{page_va + OFF['eligible']:X}
        test eax, eax
        jz invalid
        mov esi, dword ptr [ebp-0x14]
        xor edi, edi
        xor ebx, ebx
    snapshot:
        mov eax, dword ptr [esi+edi*4+0x1C5C]
        mov dword ptr [ebp+edi*4-0x40], eax
        mov edx, eax
        and edx, 0x7FFFFFFF
        cmp edx, 0x7F800000
        jae invalid_skill
        test edx, edx
        jz finite
        test eax, 0x80000000
        jne invalid_skill
    finite:
        cmp edx, 0x42C80000
        ja invalid_skill
        cmp eax, 0x42C80000
        je snapshot_next
        inc ebx
    snapshot_next:
        inc edi
        cmp edi, 6
        jb snapshot
        test ebx, ebx
        jz no_change
        mov eax, dword ptr [0x51D5F8]
        mov dword ptr [ebp-0x18], eax
        cmp eax, 100000
        jb insufficient
        push 0
        push 0
        push 1
        call 0x{page_va + OFF['confirm']:X}
        cmp eax, 1
        jne cancelled
        push dword ptr [ebp-0x10]
        call 0x{page_va + OFF['resolve_index']:X}
        cmp eax, dword ptr [ebp-0x14]
        jne recheck
        mov esi, eax
        push eax
        call 0x{page_va + OFF['eligible']:X}
        test eax, eax
        jz recheck
        xor edi, edi
    initial_compare:
        mov eax, dword ptr [esi+edi*4+0x1C5C]
        cmp eax, dword ptr [ebp+edi*4-0x40]
        jne recheck
        inc edi
        cmp edi, 6
        jb initial_compare
        mov eax, dword ptr [0x51D5F8]
        cmp eax, dword ptr [ebp-0x18]
        jne recheck
        cmp eax, 100000
        jb insufficient
        xor edi, edi
    writer_loop:
        push dword ptr [ebp-0x10]
        call 0x{page_va + OFF['resolve_index']:X}
        cmp eax, dword ptr [ebp-0x14]
        jne write_failure
        mov esi, eax
        push eax
        call 0x{page_va + OFF['eligible']:X}
        test eax, eax
        jz write_failure
        xor ecx, ecx
    evolving_compare:
        mov eax, dword ptr [esi+ecx*4+0x1C5C]
        cmp ecx, edi
        jb expect_mastered
        cmp eax, dword ptr [ebp+ecx*4-0x40]
        jne write_failure
        jmp evolving_next
    expect_mastered:
        cmp eax, 0x42C80000
        jne write_failure
    evolving_next:
        inc ecx
        cmp ecx, 6
        jb evolving_compare
        mov eax, dword ptr [0x51D5F8]
        cmp eax, dword ptr [ebp-0x18]
        jne write_failure
        cmp dword ptr [esi+edi*4+0x1C5C], 0x42C80000
        je writer_next
        mov dword ptr [ebp-0x20], 1
        push 0x42C80000
        fld dword ptr [esp]
        fsub dword ptr [esi+edi*4+0x1C5C]
        fstp dword ptr [esp]
        push edi
        lea ecx, [esi+0x1C5C]
        call 0x475730
        cmp dword ptr [esi+edi*4+0x1C5C], 0x42C80000
        jne retained
    writer_next:
        inc edi
        cmp edi, 6
        jb writer_loop
        push dword ptr [ebp-0x10]
        call 0x{page_va + OFF['resolve_index']:X}
        cmp eax, dword ptr [ebp-0x14]
        jne retained
        mov esi, eax
        push eax
        call 0x{page_va + OFF['eligible']:X}
        test eax, eax
        jz retained
        xor edi, edi
    final_verify:
        cmp dword ptr [esi+edi*4+0x1C5C], 0x42C80000
        jne retained
        inc edi
        cmp edi, 6
        jb final_verify
        mov eax, dword ptr [0x51D5F8]
        cmp eax, dword ptr [ebp-0x18]
        jne retained
        push -100000
        mov ecx, 0x51D5F8
        call 0x4237B0
        mov eax, dword ptr [ebp-0x18]
        sub eax, 100000
        cmp dword ptr [0x51D5F8], eax
        jne charge_unknown
        {status_call(page_va, '1', 0)}
        jmp done
    write_failure:
        cmp dword ptr [ebp-0x20], 0
        jne retained
        jmp recheck
    invalid:
        {status_call(page_va, '1', 2)}
        jmp done
    invalid_skill:
        {status_call(page_va, '1', 9)}
        jmp done
    no_change:
        {status_call(page_va, '1', 1)}
        jmp done
    insufficient:
        {status_call(page_va, '1', 3)}
        jmp done
    cancelled:
        {status_call(page_va, '1', 4)}
        jmp done
    recheck:
        {status_call(page_va, '1', 5)}
        jmp done
    retained:
        {status_call(page_va, '1', 6)}
        jmp done
    charge_unknown:
        {status_call(page_va, '1', 7)}
    done:
        add esp, 0x60
        pop edi
        pop esi
        pop ebx
        pop ebp
        ret
    """)


def build_running(page: bytearray, page_va: int) -> bytes:
    return put(page, page_va, "running", f"""
        push ebp
        mov ebp, esp
        push ebx
        push esi
        push edi
        sub esp, 0x70
        mov dword ptr [ebp-0x1C], -1
        mov dword ptr [ebp-0x44], 0
        mov dword ptr [ebp-0x48], 0
        call 0x{page_va + OFF['resolve_current']:X}
        test eax, eax
        jz invalid
        mov dword ptr [ebp-0x14], eax
        mov dword ptr [ebp-0x10], edx
        push eax
        call 0x{page_va + OFF['eligible']:X}
        test eax, eax
        jz invalid
        mov esi, dword ptr [ebp-0x14]
        xor edi, edi
    snapshot_likes:
        mov eax, dword ptr [esi+edi*4+0x1F5C]
        mov dword ptr [ebp+edi*4-0x30], eax
        inc edi
        cmp edi, 3
        jb snapshot_likes
        xor edi, edi
    snapshot_dislikes:
        mov eax, dword ptr [esi+edi*4+0x1F68]
        mov dword ptr [ebp+edi*4-0x40], eax
        inc edi
        cmp edi, 3
        jb snapshot_dislikes
        mov eax, dword ptr [0x51D5F8]
        mov dword ptr [ebp-0x18], eax
        push 38
        lea ecx, [esi+0x1F5C]
        call 0x464F90
        test al, al
        jnz no_change
        xor edi, edi
    find_empty:
        cmp dword ptr [ebp+edi*4-0x30], -1
        je found_empty
        inc edi
        cmp edi, 3
        jb find_empty
        jmp no_slot
    found_empty:
        mov dword ptr [ebp-0x1C], edi
        cmp dword ptr [ebp-0x18], 40000
        jb insufficient
        push 0
        push 0
        push 2
        call 0x{page_va + OFF['confirm']:X}
        cmp eax, 1
        jne cancelled
        call running_reacquire_exact
        test eax, eax
        jz recheck
        push 38
        lea ecx, [esi+0x1F5C]
        call 0x464AD0
        mov dword ptr [ebp-0x48], 1
        xor edi, edi
    verify_insert_likes:
        mov eax, dword ptr [ebp+edi*4-0x30]
        cmp edi, dword ptr [ebp-0x1C]
        jne verify_insert_like
        mov eax, 38
    verify_insert_like:
        cmp dword ptr [esi+edi*4+0x1F5C], eax
        jne rollback
        inc edi
        cmp edi, 3
        jb verify_insert_likes
        xor edi, edi
    verify_insert_dislikes:
        mov eax, dword ptr [ebp+edi*4-0x40]
        cmp dword ptr [esi+edi*4+0x1F68], eax
        jne rollback
        inc edi
        cmp edi, 3
        jb verify_insert_dislikes
        xor edi, edi
    removal_loop:
        cmp dword ptr [ebp+edi*4-0x40], 38
        jne removal_next
        push edi
        call running_reacquire_evolving
        pop edi
        test eax, eax
        jz rollback
        push 38
        lea ecx, [esi+0x1F68]
        call 0x4649E0
        mov eax, 2
        mov ecx, edi
        shl eax, cl
        or dword ptr [ebp-0x48], eax
        cmp dword ptr [esi+edi*4+0x1F68], -1
        jne rollback
    removal_next:
        inc edi
        cmp edi, 3
        jb removal_loop
        call running_reacquire_evolving
        test eax, eax
        jz rollback
        mov eax, dword ptr [0x51D5F8]
        cmp eax, dword ptr [ebp-0x18]
        jne rollback
        push -40000
        mov ecx, 0x51D5F8
        call 0x4237B0
        mov eax, dword ptr [ebp-0x18]
        sub eax, 40000
        cmp dword ptr [0x51D5F8], eax
        jne charge_unknown
        {status_call(page_va, '2', 0)}
        jmp done
    running_reacquire_exact:
        push dword ptr [ebp-0x10]
        call 0x{page_va + OFF['resolve_index']:X}
        cmp eax, dword ptr [ebp-0x14]
        jne running_exact_fail
        mov esi, eax
        push eax
        call 0x{page_va + OFF['eligible']:X}
        test eax, eax
        jz running_exact_fail
        xor ecx, ecx
    running_exact_likes:
        mov eax, dword ptr [ebp+ecx*4-0x30]
        cmp dword ptr [esi+ecx*4+0x1F5C], eax
        jne running_exact_fail
        inc ecx
        cmp ecx, 3
        jb running_exact_likes
        xor ecx, ecx
    running_exact_dislikes:
        mov eax, dword ptr [ebp+ecx*4-0x40]
        cmp dword ptr [esi+ecx*4+0x1F68], eax
        jne running_exact_fail
        inc ecx
        cmp ecx, 3
        jb running_exact_dislikes
        mov eax, dword ptr [0x51D5F8]
        cmp eax, dword ptr [ebp-0x18]
        jne running_exact_fail
        mov eax, 1
        ret
    running_exact_fail:
        xor eax, eax
        ret
    running_reacquire_evolving:
        push dword ptr [ebp-0x10]
        call 0x{page_va + OFF['resolve_index']:X}
        cmp eax, dword ptr [ebp-0x14]
        jne running_evolving_fail
        mov esi, eax
        push eax
        call 0x{page_va + OFF['eligible']:X}
        test eax, eax
        jz running_evolving_fail
        xor ecx, ecx
    evolving_likes:
        mov eax, dword ptr [ebp+ecx*4-0x30]
        cmp ecx, dword ptr [ebp-0x1C]
        jne evolving_like_compare
        mov eax, 38
    evolving_like_compare:
        cmp dword ptr [esi+ecx*4+0x1F5C], eax
        jne running_evolving_fail
        inc ecx
        cmp ecx, 3
        jb evolving_likes
        xor ecx, ecx
    evolving_dislikes:
        mov eax, dword ptr [ebp+ecx*4-0x40]
        mov edx, 2
        shl edx, cl
        test dword ptr [ebp-0x48], edx
        jz evolving_dislike_compare
        mov eax, -1
    evolving_dislike_compare:
        cmp dword ptr [esi+ecx*4+0x1F68], eax
        jne running_evolving_fail
        inc ecx
        cmp ecx, 3
        jb evolving_dislikes
        mov eax, dword ptr [0x51D5F8]
        cmp eax, dword ptr [ebp-0x18]
        jne running_evolving_fail
        mov eax, 1
        ret
    running_evolving_fail:
        xor eax, eax
        ret
    rollback:
        mov edi, 2
    rollback_dislikes:
        mov eax, 2
        mov ecx, edi
        shl eax, cl
        test dword ptr [ebp-0x48], eax
        jz rollback_dislike_next
        push edi
        call running_reacquire_evolving
        pop edi
        test eax, eax
        jz rollback_dislike_next
        cmp dword ptr [esi+edi*4+0x1F68], -1
        jne rollback_dislike_next
        mov dword ptr [esi+edi*4+0x1F68], 38
        cmp dword ptr [esi+edi*4+0x1F68], 38
        jne rollback_dislike_next
        mov eax, 2
        mov ecx, edi
        shl eax, cl
        not eax
        and dword ptr [ebp-0x48], eax
    rollback_dislike_next:
        dec edi
        jns rollback_dislikes
        test dword ptr [ebp-0x48], 1
        jz retained
        call running_reacquire_evolving
        test eax, eax
        jz retained
        mov edi, dword ptr [ebp-0x1C]
        cmp dword ptr [esi+edi*4+0x1F5C], 38
        jne retained
        mov dword ptr [esi+edi*4+0x1F5C], -1
        cmp dword ptr [esi+edi*4+0x1F5C], -1
        jne retained
        and dword ptr [ebp-0x48], 0xFFFFFFFE
        jmp retained
    invalid:
        {status_call(page_va, '2', 2)}
        jmp done
    no_change:
        {status_call(page_va, '2', 1)}
        jmp done
    no_slot:
        {status_call(page_va, '2', 8)}
        jmp done
    insufficient:
        {status_call(page_va, '2', 3)}
        jmp done
    cancelled:
        {status_call(page_va, '2', 4)}
        jmp done
    recheck:
        {status_call(page_va, '2', 5)}
        jmp done
    retained:
        {status_call(page_va, '2', 6)}
        jmp done
    charge_unknown:
        {status_call(page_va, '2', 7)}
    done:
        add esp, 0x70
        pop edi
        pop esi
        pop ebx
        pop ebp
        ret
    """)


def build_heal(page: bytearray, page_va: int) -> bytes:
    return put(page, page_va, "heal", f"""
        push ebp
        mov ebp, esp
        push ebx
        push esi
        push edi
        sub esp, 0x1000
        mov dword ptr [ebp-0x18], 0
        mov dword ptr [ebp-0x1C], 0
        mov dword ptr [ebp-0x20], 0
        mov dword ptr [ebp-0x24], 0
        mov eax, dword ptr [0x51D5F8]
        mov dword ptr [ebp-0x10], eax
        mov eax, dword ptr [0x51D368]
        mov dword ptr [ebp-0x14], eax
        mov esi, 0x554190
        lea edi, [ebp-0xF00]
        mov ebx, {BOUND}
    dry_loop:
        movzx eax, byte ptr [esi+0x1CD4]
        mov dword ptr [edi], eax
        movzx eax, byte ptr [esi+0x1CE1]
        mov dword ptr [edi+20], eax
        cmp dword ptr [edi], 0
        je dry_next
        cmp dword ptr [edi+20], 0
        jne dry_next
        movzx eax, byte ptr [esi+0x1CEC]
        mov dword ptr [edi+8], eax
        mov eax, dword ptr [esi+0x1C40]
        mov dword ptr [edi+4], eax
        movzx eax, byte ptr [esi+0x1C48]
        mov dword ptr [edi+12], eax
        mov eax, dword ptr [esi+0x1CFC]
        mov dword ptr [edi+16], eax
        cmp dword ptr [edi+4], 0
        jle dry_next
        cmp dword ptr [edi+8], 0
        jne dry_next
        cmp dword ptr [edi+12], 0
        je dry_health
        cmp dword ptr [edi+16], 12
        je unsupported
        inc dword ptr [ebp-0x18]
    dry_health:
        cmp dword ptr [edi+4], 80
        jae dry_next
        inc dword ptr [ebp-0x1C]
    dry_next:
        add esi, {STRIDE}
        add edi, 24
        dec ebx
        jne dry_loop
        mov eax, dword ptr [ebp-0x18]
        or eax, dword ptr [ebp-0x1C]
        jz no_change
        cmp dword ptr [ebp-0x10], 30000
        jb insufficient
        push dword ptr [ebp-0x1C]
        push dword ptr [ebp-0x18]
        push 4
        call 0x{page_va + OFF['confirm']:X}
        cmp eax, 1
        jne cancelled
        mov eax, dword ptr [0x51D5F8]
        cmp eax, dword ptr [ebp-0x10]
        jne recheck
        mov eax, dword ptr [0x51D368]
        cmp eax, dword ptr [ebp-0x14]
        jne recheck
        mov esi, 0x554190
        lea edi, [ebp-0xF00]
        mov ebx, {BOUND}
    fresh_loop:
        cmp dword ptr [edi], 0
        je fresh_next
        cmp dword ptr [edi+20], 0
        jne fresh_next
        movzx eax, byte ptr [esi+0x1CD4]
        cmp eax, dword ptr [edi]
        jne recheck
        movzx eax, byte ptr [esi+0x1CE1]
        cmp eax, dword ptr [edi+20]
        jne recheck
        movzx eax, byte ptr [esi+0x1CEC]
        cmp eax, dword ptr [edi+8]
        jne recheck
        mov eax, dword ptr [esi+0x1C40]
        cmp eax, dword ptr [edi+4]
        jne recheck
        movzx eax, byte ptr [esi+0x1C48]
        cmp eax, dword ptr [edi+12]
        jne recheck
        mov eax, dword ptr [esi+0x1CFC]
        cmp eax, dword ptr [edi+16]
        jne recheck
    fresh_next:
        add esi, {STRIDE}
        add edi, 24
        dec ebx
        jne fresh_loop
        mov esi, 0x554190
        lea edi, [ebp-0xF00]
        mov ebx, {BOUND}
    write_loop:
        cmp dword ptr [edi], 0
        je write_next
        cmp dword ptr [edi+20], 0
        jne write_next
        cmp dword ptr [edi+4], 0
        jle write_next
        cmp dword ptr [edi+8], 0
        jne write_next
        cmp dword ptr [edi+4], 80
        jae sickness_write
        call heal_record_guard
        test eax, eax
        jz retained
        mov dword ptr [ebp-0x20], 1
        push -1
        push 100
        lea ecx, [esi+0x1C34]
        call 0x4758B0
        cmp dword ptr [esi+0x1C40], 100
        jne retained
    sickness_write:
        cmp dword ptr [edi+12], 0
        je write_next
        call heal_record_guard_evolving
        test eax, eax
        jz retained
        mov dword ptr [ebp-0x20], 1
        mov byte ptr [esi+0x1C48], 0
        cmp byte ptr [esi+0x1C48], 0
        jne retained
        inc dword ptr [0x51D368]
        inc dword ptr [ebp-0x24]
        mov eax, dword ptr [ebp-0x14]
        add eax, dword ptr [ebp-0x24]
        cmp dword ptr [0x51D368], eax
        jne retained
        push 1
        push 52
        mov ecx, 0x4DB358
        call 0x413450
        push 1
        push 53
        mov ecx, 0x4DB358
        call 0x413450
        push 1
        push 54
        mov ecx, 0x4DB358
        call 0x413450
        jmp write_next
    write_next:
        add esi, {STRIDE}
        add edi, 24
        dec ebx
        jne write_loop
        mov esi, 0x554190
        lea edi, [ebp-0xF00]
        mov ebx, {BOUND}
    post_loop:
        movzx eax, byte ptr [esi+0x1CD4]
        cmp eax, dword ptr [edi]
        jne retained
        movzx eax, byte ptr [esi+0x1CE1]
        cmp eax, dword ptr [edi+20]
        jne retained
        cmp dword ptr [edi+20], 0
        jne post_next
        cmp dword ptr [edi], 0
        je post_next
        movzx eax, byte ptr [esi+0x1CEC]
        cmp eax, dword ptr [edi+8]
        jne retained
        mov eax, dword ptr [esi+0x1CFC]
        cmp eax, dword ptr [edi+16]
        jne retained
        cmp dword ptr [edi], 0
        je post_ineligible
        cmp dword ptr [edi+4], 0
        jle post_ineligible
        cmp dword ptr [edi+8], 0
        jne post_ineligible
        cmp dword ptr [edi+4], 80
        jae post_health_unchanged
        cmp dword ptr [esi+0x1C40], 100
        jne retained
        jmp post_health_done
    post_health_unchanged:
        mov eax, dword ptr [esi+0x1C40]
        cmp eax, dword ptr [edi+4]
        jne retained
    post_health_done:
        cmp byte ptr [esi+0x1C48], 0
        jne retained
        jmp post_next
    post_ineligible:
        mov eax, dword ptr [esi+0x1C40]
        cmp eax, dword ptr [edi+4]
        jne retained
        movzx eax, byte ptr [esi+0x1C48]
        cmp eax, dword ptr [edi+12]
        jne retained
    post_next:
        add esi, {STRIDE}
        add edi, 24
        dec ebx
        jne post_loop
        mov eax, dword ptr [ebp-0x14]
        add eax, dword ptr [ebp-0x18]
        cmp dword ptr [0x51D368], eax
        jne retained
        mov eax, dword ptr [0x51D5F8]
        cmp eax, dword ptr [ebp-0x10]
        jne retained
        push -30000
        mov ecx, 0x51D5F8
        call 0x4237B0
        mov eax, dword ptr [ebp-0x10]
        sub eax, 30000
        cmp dword ptr [0x51D5F8], eax
        jne charge_unknown
        {status_call(page_va, '4', 0, 'dword ptr [ebp-0x18]', 'dword ptr [ebp-0x1C]')}
        jmp done
    heal_record_guard:
        movzx eax, byte ptr [esi+0x1CD4]
        cmp eax, dword ptr [edi]
        jne heal_guard_fail
        movzx eax, byte ptr [esi+0x1CE1]
        cmp eax, dword ptr [edi+20]
        jne heal_guard_fail
        mov eax, dword ptr [esi+0x1C40]
        cmp eax, dword ptr [edi+4]
        jne heal_guard_fail
        jmp heal_guard_common
    heal_record_guard_evolving:
        movzx eax, byte ptr [esi+0x1CD4]
        cmp eax, dword ptr [edi]
        jne heal_guard_fail
        movzx eax, byte ptr [esi+0x1CE1]
        cmp eax, dword ptr [edi+20]
        jne heal_guard_fail
        mov eax, dword ptr [edi+4]
        cmp eax, 80
        jae heal_guard_health_original
        mov eax, 100
    heal_guard_health_original:
        cmp dword ptr [esi+0x1C40], eax
        jne heal_guard_fail
    heal_guard_common:
        movzx eax, byte ptr [esi+0x1CEC]
        cmp eax, dword ptr [edi+8]
        jne heal_guard_fail
        movzx eax, byte ptr [esi+0x1CE1]
        cmp eax, dword ptr [edi+20]
        jne heal_guard_fail
        movzx eax, byte ptr [esi+0x1C48]
        cmp eax, dword ptr [edi+12]
        jne heal_guard_fail
        mov eax, dword ptr [esi+0x1CFC]
        cmp eax, dword ptr [edi+16]
        jne heal_guard_fail
        mov eax, dword ptr [0x51D5F8]
        cmp eax, dword ptr [ebp-0x10]
        jne heal_guard_fail
        mov eax, dword ptr [ebp-0x14]
        add eax, dword ptr [ebp-0x24]
        cmp dword ptr [0x51D368], eax
        jne heal_guard_fail
        mov eax, 1
        ret
    heal_guard_fail:
        xor eax, eax
        ret
    unsupported:
        {status_call(page_va, '4', 13)}
        jmp done
    no_change:
        {status_call(page_va, '4', 1)}
        jmp done
    insufficient:
        {status_call(page_va, '4', 3)}
        jmp done
    cancelled:
        {status_call(page_va, '4', 4)}
        jmp done
    recheck:
        {status_call(page_va, '4', 5)}
        jmp done
    retained:
        cmp dword ptr [ebp-0x20], 0
        jne retained_status
        {status_call(page_va, '4', 5)}
        jmp done
    retained_status:
        {status_call(page_va, '4', 6, 'dword ptr [ebp-0x24]', '0')}
        jmp done
    charge_unknown:
        {status_call(page_va, '4', 7, 'dword ptr [ebp-0x18]', 'dword ptr [ebp-0x1C]')}
    done:
        add esp, 0x1000
        pop edi
        pop esi
        pop ebx
        pop ebp
        ret
    """)


def build_page(page_va: int) -> tuple[bytes, dict[str, object]]:
    page = bytearray(PAGE_SIZE)
    page[0:8] = b"VVT9PG\0\0"
    page[8:12] = (1).to_bytes(4, "little")
    page[12:16] = PAGE_SIZE.to_bytes(4, "little")
    page[16:20] = BOUND.to_bytes(4, "little")
    page[20:24] = STRIDE.to_bytes(4, "little")
    page[24:28] = page_va.to_bytes(4, "little")
    strings = build_strings(page, page_va)
    routines: dict[str, bytes] = {}
    routines.update(build_modal(page, page_va, strings))
    routines.update(build_helpers(page, page_va, strings))
    routines.update(build_menus(page, page_va))
    routines["age"] = build_age(page, page_va)
    routines["mastery"] = build_mastery(page, page_va)
    routines["running"] = build_running(page, page_va)
    routines["heal"] = build_heal(page, page_va)
    result = {
        "page_sha256": sha(bytes(page)),
        "routine_sha256": {name: sha(value) for name, value in routines.items()},
        "routine_length": {name: len(value) for name, value in routines.items()},
        "entry_virtual_addresses": {
            name: f"0x{page_va + OFF[name]:X}"
            for name in ("tech_entry", "detail_entry", "age", "mastery", "running", "heal")
        },
        "string_virtual_addresses": {name: f"0x{value:X}" for name, value in strings.items()},
    }
    return bytes(page), result


def patch_payload(active: dict[str, object], stock_page_va: int) -> tuple[bytes, dict[str, object]]:
    payload_patch = next(
        item for item in active["patches"] if int(str(item["offset"]), 0) == PAYLOAD_OFFSET
    )
    active_payload = bytes.fromhex(str(payload_patch["after"]))
    patch_length = len(active_payload)
    payload = bytearray(active_payload.ljust(0x1000, b"\0"))
    if len(payload) != 0x1000:
        raise RuntimeError("active VV5 payload length drift")
    geometry: dict[str, dict[str, str]] = {}
    for label, start, end, old_y in (
        ("tech", 0x40, 0xC0, bytes.fromhex("68D2020000")),
        ("detail", 0x100, 0x180, bytes.fromhex("68BC020000")),
    ):
        ctor = bytearray(payload[start:end])
        for before, after in (
            (bytes.fromhex("6A48"), bytes.fromhex("6A6A")),
            (old_y, bytes.fromhex("6802000000")),
            (bytes.fromhex("68B4000000"), bytes.fromhex("6889000000")),
        ):
            if ctor.count(before) != 1:
                raise RuntimeError(f"{label} geometry preimage drift: {before.hex().upper()}")
            ctor = ctor.replace(before, after)
        receiver = ctor.find(bytes.fromhex("89C789F96A6AE8"))
        if receiver < 0:
            raise RuntimeError(f"{label} constructor allocation/resource ABI drift")
        native_lookup = bytes(ctor[receiver + 6 : receiver + 11])
        if len(native_lookup) != 5 or native_lookup[0] != 0xE8:
            raise RuntimeError(f"{label} native resource lookup call drift")
        bridge = asm(
            f"xchg eax, edi; call 0x{stock_page_va + OFF['constructor_resource']:X}",
            PAYLOAD_VA + start + receiver,
        )
        if len(bridge) != 6:
            raise RuntimeError(f"{label} constructor resource bridge length drift")
        ctor[receiver : receiver + 11] = bridge + native_lookup
        payload[start:end] = ctor
        geometry[label] = {
            "allocation_bridge_bytes": (bridge + native_lookup).hex().upper(),
            "allocation_bridge_operand_offset": f"0x{PAYLOAD_OFFSET + start + receiver + 2:X}",
            "resource_manager": "0x44FBB0",
            "resource_lookup": "0x44FA20",
            "resource_lookup_receiver": "EAX returned by 0x44FBB0 copied to ECX",
            "control_constructor_receiver": "EDI allocation preserved by xchg EAX,EDI before constructor_resource helper",
            "resource_id": "0x6A",
            "dimensions": "96x39",
            "local_x": "137",
            "local_y": "2",
        }
    old_guard = bytes(payload[0x270:0x2C0])
    resolver_transfer = asm(
        f"push 0x{stock_page_va + OFF['resolve_manager']:X}; ret",
        PAYLOAD_VA + 0x276,
    )
    if len(resolver_transfer) != 6:
        raise RuntimeError("safe resolver transfer length drift")
    payload[0x276:0x27C] = resolver_transfer
    tech_stub = asm(f"mov eax, 0x{stock_page_va + OFF['tech_entry']:X}; jmp eax", PAYLOAD_VA + 0x2C0)
    detail_stub = asm(f"mov eax, 0x{stock_page_va + OFF['detail_entry']:X}; jmp eax", PAYLOAD_VA + 0x600)
    if len(tech_stub) != 7 or len(detail_stub) != 7:
        raise RuntimeError("Task9 absolute menu stub length drift")
    payload[0x2C0:0x2C7] = tech_stub
    payload[0x600:0x607] = detail_stub
    forbidden = bytes.fromhex("E11C0000")
    forbidden_count = payload.count(forbidden)
    payload = bytearray(bytes(payload).replace(forbidden, bytes.fromhex("EC1C0000")))
    if forbidden in payload:
        raise RuntimeError("withdrawn legacy eligibility read remains")
    return bytes(payload[:patch_length]), {
        "geometry": geometry,
        "safe_resolver_before_sha256": sha(old_guard),
        "safe_resolver_transfer_bytes": resolver_transfer.hex().upper(),
        "safe_resolver_transfer_sha256": sha(resolver_transfer),
        "tech_entry_stub": tech_stub.hex().upper(),
        "detail_entry_stub": detail_stub.hex().upper(),
        "withdrawn_legacy_eligibility_immediates_rebound_to_faction": forbidden_count,
    }


def append_layout(layout: dict[str, int], page: bytes) -> dict[str, object]:
    new_size = layout["size_of_image_before"] + PAGE_SIZE
    header = section_header(layout["page_rva"], layout["append_offset"])
    return {
        "original_file_size": f"0x{layout['append_offset']:X}",
        "append_offset": f"0x{layout['append_offset']:X}",
        "append_length": PAGE_SIZE,
        "append_bytes": page.hex().upper(),
        "append_source": "generated:vv5_task9_native_actions_page",
        "page_virtual_address": f"0x{layout['page_va']:X}",
        "page_sha256": sha(page),
        "purpose": "append the guarded VV5 Task9 native action and owner-safe UI page",
        "header_patches": [
            {
                "offset": f"0x{layout['section_count_offset']:X}",
                "before": layout["section_count_before"].to_bytes(2, "little").hex().upper(),
                "after": (layout["section_count_before"] + 1).to_bytes(2, "little").hex().upper(),
                "purpose": "add the generated Task9 RX section",
            },
            {
                "offset": f"0x{layout['size_of_image_offset']:X}",
                "before": layout["size_of_image_before"].to_bytes(4, "little").hex().upper(),
                "after": new_size.to_bytes(4, "little").hex().upper(),
                "purpose": "extend SizeOfImage for Task9",
            },
            {
                "offset": f"0x{layout['section_header_offset']:X}",
                "before": "00" * 40,
                "after": header.hex().upper(),
                "purpose": "install the guarded .vv5t9 section header",
            },
        ],
    }


def main() -> None:
    stock = STOCK.read_bytes()
    if len(stock) != 991232 or sha(stock) != STOCK_SHA256:
        raise RuntimeError("VV5 stock identity drift")
    active_bytes = ACTIVE.read_bytes()
    if sha(active_bytes) != ACTIVE_SHA256 or source_text_sha(active_bytes) != ACTIVE_SOURCE_TEXT_SHA256:
        raise RuntimeError("pinned active VV5 Origins source drift")
    active = json.loads(active_bytes.decode("utf-8"))
    relocations = active["expanded_shr_relocations"]["patches"]
    if len(relocations) != C342_COUNT or canonical_sha(relocations) != C342_ROWS_SHA256:
        raise RuntimeError("frozen C342 66-row ledger drift")
    companion = COMPANION.read_bytes()
    bindings = source_bindings()
    pages: dict[str, bytes] = {}
    page_maps: dict[str, object] = {}
    for mode, layout in LAYOUTS.items():
        page, page_map = build_page(layout["page_va"])
        pages[mode] = page
        page_maps[mode] = page_map
    payload, payload_map = patch_payload(active, LAYOUTS["collection_progression"]["page_va"])
    result = deepcopy(active)
    result.update({
        "schema": "vvfp.vv5_task9_native_actions.v1",
        "id": "vv5_enable_origins_exclusive_features",
        "name": "Enable Origins-Exclusive Features (Task9 native actions)",
        "description": "Enables the VV5 Origins-style Tech and Villager Upgrades menus. The native action page provides Full Mastery, Grant Running, Set Age to 18, and Full Heal / Cure All for active living Believers only; records with the VV5 Heathen mask/status byte set are skipped before any action-specific read or write. Time Warp, Island Event, and Barrel of Babies remain unavailable until their native target paths are proven Heathen-safe.",
        "enabled": True,
        "catalog_hidden": False,
        "catalog_enabled": True,
        "supported_modes": list(LAYOUTS),
        "runtime_player_status": "pending",
        "base_source_text_sha256": ACTIVE_SOURCE_TEXT_SHA256,
        "base_file_sha256": ACTIVE_SHA256,
        "task8_overlay_source_text_sha256": TASK8_SOURCE_TEXT_SHA256,
        "atomic_core": {
            "commit": ATOMIC_CORE_COMMIT,
            "generator_source_text_sha256": ATOMIC_SOURCE_TEXT_SHA256["atomic_generator"],
            "contract_source_text_sha256": ATOMIC_SOURCE_TEXT_SHA256["atomic_contract"],
        },
        "source_bindings": bindings,
        "frozen_c342": {"count": C342_COUNT, "rows_sha256": C342_ROWS_SHA256, "unchanged": True},
        "task9_contract": {
            "owner": "BeginOriginsOwner/GetOriginsOwner/EndOriginsOwner; same-process HWND only; capture before fullscreen leave; no foreground fallback; centralized restore then End",
            "sequence": "complete dry-run -> IDOK -> fresh identity/snapshot/funds -> mutation -> postverify -> one native charge -> exact balance readback",
            "selection": "resolver 0x425950 null-guarded before +0x17E24; unsigned command 0..3 before resolver or price access",
            "eligibility": "active +0x1CD4, Heathen mask/status +0x1CE1 == 0, signed living health +0x1C40 > 0, current-Believer faction +0x1CEC == 0",
            "eligibility_schema": "both the VV5 Heathen mask/status byte and current faction must identify an active living Believer; masked records are rejected before action-specific reads or writes",
            "actions": {
                "youth": {"price": 50000, "target": "max(raw_age-700,100)", "writer": "0x46F7F0 ECX=record+0x1B8C signed delta", "companions": ["+0x1C3C same delta", "+0x1C4C same delta only when nonzero"]},
                "age18": {"price": 50000, "target": 360, "writer": "0x46F7F0 ECX=record+0x1B8C signed delta", "companions": ["+0x1C3C same delta", "+0x1C4C same delta only when nonzero"]},
                "full_mastery": {"price": 100000, "fields": ["0x1C5C", "0x1C60", "0x1C64", "0x1C68", "0x1C6C", "0x1C70"], "writer": "0x475730 ECX=record+0x1C5C push Float32 delta then push index", "target_bits": "0x42C80000"},
                "running": {"price": 40000, "preference_id": 38, "likes": ["0x1F5C", "0x1F60", "0x1F64"], "dislikes": ["0x1F68", "0x1F6C", "0x1F70"], "native": {"membership": "0x464F90", "insertion": "0x464AD0", "first_removal": "0x4649E0"}},
                "full_heal": {"price": 30000, "health_rule": "only health < 80 is raised to exactly 100; health 80-100 is preserved", "health_writer": "0x4758B0 ECX=record+0x1C34 push -1 then push 100", "sickness": "+0x1C48 byte", "masked_heathen_policy": "skip before sickness/type reads; includes the sick Heathen puzzle record", "unsupported_type": "+0x1CFC == 12 when sick on an otherwise eligible Believer", "people_cured": "0x51D368", "statistic_writer": "0x413450 ECX=0x4DB358 IDs 52/53/54 amount 1"},
            },
        },
        "companion_files": [{
            "source": "data/candidates/VVFP VV5 Task9 Origins Icons.dll",
            "destination": "VVFP Origins Icons.dll",
            "sha256": sha(companion),
            "size": len(companion),
        }],
        "pe_append_transaction": {
            "section": ".vv5t9",
            "append_source": "generated:vv5_task9_native_actions_page",
            "layouts": {mode: append_layout(LAYOUTS[mode], pages[mode]) for mode in LAYOUTS},
        },
        "task9_expanded_post_relocation_patches": {
            mode: [deepcopy(TASK9_EXPANDED_HOOK)]
            for mode in (
                "experimental_expanded_256",
                "experimental_expanded_256_progression",
            )
        },
    })
    for item in result["patches"]:
        after = bytes.fromhex(str(item["after"]))
        if int(str(item["offset"]), 0) == PAYLOAD_OFFSET:
            item["after"] = payload.hex().upper()
            item["purpose"] = "install pinned VV5 Origins payload with Task9 geometry, safe resolver, and absolute native-action entries"
        elif bytes.fromhex("E11C0000") in after:
            item["after"] = after.replace(bytes.fromhex("E11C0000"), bytes.fromhex("EC1C0000")).hex().upper()
            item["purpose"] = str(item["purpose"]) + "; remove the withdrawn synthetic eligibility read"
    expanded_overrides = [
        {
            "offset": f"0x{PAYLOAD_OFFSET + 0x2C1:X}",
            "before": (LAYOUTS["collection_progression"]["page_va"] + OFF["tech_entry"]).to_bytes(4, "little").hex().upper(),
            "after": (LAYOUTS["experimental_expanded_256"]["page_va"] + OFF["tech_entry"]).to_bytes(4, "little").hex().upper(),
            "purpose": "bind relocated .shr Tech entry to the fixed Expanded Task9 page",
        },
        {
            "offset": f"0x{PAYLOAD_OFFSET + 0x601:X}",
            "before": (LAYOUTS["collection_progression"]["page_va"] + OFF["detail_entry"]).to_bytes(4, "little").hex().upper(),
            "after": (LAYOUTS["experimental_expanded_256"]["page_va"] + OFF["detail_entry"]).to_bytes(4, "little").hex().upper(),
            "purpose": "bind relocated .shr Detail entry to the fixed Expanded Task9 page",
        },
        {
            "offset": f"0x{PAYLOAD_OFFSET + 0x277:X}",
            "before": (LAYOUTS["collection_progression"]["page_va"] + OFF["resolve_manager"]).to_bytes(4, "little").hex().upper(),
            "after": (LAYOUTS["experimental_expanded_256"]["page_va"] + OFF["resolve_manager"]).to_bytes(4, "little").hex().upper(),
            "purpose": "bind the preserved legacy resolver entry to its Expanded null-guard continuation without changing any C342 row",
        },
    ]
    for label in ("tech", "detail"):
        operand_offset = int(payload_map["geometry"][label]["allocation_bridge_operand_offset"], 0)
        stock_opcode_va = PAYLOAD_VA + (operand_offset - PAYLOAD_OFFSET) - 1
        expanded_opcode_va = EXPANDED_PAYLOAD_VA + (operand_offset - PAYLOAD_OFFSET) - 1
        stock_target = LAYOUTS["collection_progression"]["page_va"] + OFF["constructor_resource"]
        expanded_target = LAYOUTS["experimental_expanded_256"]["page_va"] + OFF["constructor_resource"]
        expanded_overrides.append({
            "offset": f"0x{operand_offset:X}",
            "before": (stock_target - (stock_opcode_va + 5)).to_bytes(4, "little", signed=True).hex().upper(),
            "after": (expanded_target - (expanded_opcode_va + 5)).to_bytes(4, "little", signed=True).hex().upper(),
            "purpose": f"bind the relocated .shr {label} constructor resource-manager bridge to the Expanded Task9 page",
        })
    for mode in ("experimental_expanded_256", "experimental_expanded_256_progression"):
        result["patch_mode_overrides"].setdefault(mode, []).extend(deepcopy(expanded_overrides))
    if any(bytes.fromhex("E11C0000") in bytes.fromhex(str(item["after"])) for item in result["patches"]):
        raise RuntimeError("Task9 emitted patch set retains a withdrawn eligibility read")
    map_record = {
        "schema": "vvfp.vv5_task9_native_actions_map.v1",
        "source": {"size": len(stock), "sha256": sha(stock)},
        "active_base": {"size": len(active_bytes), "file_sha256": sha(active_bytes), "source_text_sha256": source_text_sha(active_bytes)},
        "task8_overlay_source_text_sha256": TASK8_SOURCE_TEXT_SHA256,
        "atomic_core": {
            "commit": ATOMIC_CORE_COMMIT,
            "generator_source_text_sha256": ATOMIC_SOURCE_TEXT_SHA256["atomic_generator"],
            "contract_source_text_sha256": ATOMIC_SOURCE_TEXT_SHA256["atomic_contract"],
        },
        "source_bindings": bindings,
        "c342": {"count": len(relocations), "rows_sha256": canonical_sha(relocations), "unchanged": True},
        "companion": {"size": len(companion), "sha256": sha(companion)},
        "payload": {"sha256": sha(payload), **payload_map},
        "layouts": {mode: page_maps[mode] | {"append_offset": f"0x{LAYOUTS[mode]['append_offset']:X}", "page_virtual_address": f"0x{LAYOUTS[mode]['page_va']:X}"} for mode in LAYOUTS},
        "nonoverlap": {
            "task8_dbxxx_range": ["0xDB000", "0xDC000"],
            "task9_stock_append_range": ["0xF2000", "0xFA000"],
            "task9_expanded_append_range": ["0xF4000", "0xFC000"],
            "c342_new_row_count": 0,
            "absolute_entry_stubs_require_c342_relocation": False,
        },
        "resolver_contract": {
            "record_pointer_resolver": "0x46F950",
            "forbidden_transitive_helpers": ["0x466170", "0x471840"],
            "eligibility_order": ["+0x1CD4 != 0", "+0x1CE1 == 0", "+0x1C40 signed > 0", "+0x1CEC == 0"],
        },
        "expanded_cross_section_hook_audit": {
            "hook_count": len(TASK9_CROSS_SECTION_HOOKS),
            "hooks": TASK9_CROSS_SECTION_HOOKS,
            "frozen_c342_operand_offsets": [
                "0x18910", "0x1EB70", "0x237B1", "0x40A25", "0x4AF13", "0x4BC21"
            ],
            "task9_post_relocation_hook_offset": "0x415F0",
            "task9_post_relocation_operand_offset": "0x415F1",
            "c342_changed": False,
        },
    }
    result["task9_map_canonical_sha256"] = canonical_sha(map_record)
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    MAP_OUT.write_text(json.dumps(map_record, indent=2) + "\n", encoding="utf-8")
    print(f"manifest {OUT} {sha(OUT.read_bytes())}")
    print(f"map {MAP_OUT} {sha(MAP_OUT.read_bytes())}")
    for mode in LAYOUTS:
        print(f"{mode} page {sha(pages[mode])}")


if __name__ == "__main__":
    main()
