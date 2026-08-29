"""Build the reviewed VV4/VV5 Expanded-256 Time Warp overlays.

The VV4 implementation occupies the stock executable's existing zero RX cave.
The VV5 implementation overlays only the reserved Task9 Expanded page.  Stock
mode records contain no mutation rows and are rejected by the runtime gate.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SELF = ROOT / "scripts/build_expanded_time_warp.py"
TASK9_BUILDER = ROOT / "scripts/build_vv5_task9_native_actions.py"
COMPANION = ROOT / "data/candidates/VVFP VV5 Task9 Origins Icons.dll"
VV4_OUT = ROOT / "data/vv4_expanded_time_warp.json"
VV4_MAP_OUT = ROOT / "data/candidates/vv4_expanded_time_warp_map.json"
VV5_OUT = ROOT / "data/vv5_expanded_time_warp.json"
VV5_MAP_OUT = ROOT / "data/candidates/vv5_expanded_time_warp_map.json"

COMPANION_SHA256 = "08C068D7F0E98BA1AE85AE0046709877B703B2A3EA3B9E1C76BC5CDAAFDDEC8C"
COMPANION_SIZE = 1753088
EXPANDED_MODES = (
    "experimental_expanded_256",
    "experimental_expanded_256_progression",
)
VV4_STOCK_SPEED_OFFSET = 0x17110
VV4_EXPANDED_SPEED_OFFSET = 0x1DCB8
VV4_SPEED_OFFSET_BY_MODE = {
    "collection_progression": VV4_STOCK_SPEED_OFFSET,
    "immediate_fixed": VV4_STOCK_SPEED_OFFSET,
    **{mode: VV4_EXPANDED_SPEED_OFFSET for mode in EXPANDED_MODES},
}

sys.path.insert(0, str(ROOT / ".tools/keystone-runtime"))
sys.path.insert(1, str(ROOT / ".tools/keystone"))
from keystone import KS_ARCH_X86, KS_MODE_32, Ks  # noqa: E402


def asm(source: str, address: int) -> bytes:
    encoded, _ = Ks(KS_ARCH_X86, KS_MODE_32).asm(source, address)
    return bytes(encoded)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def source_text_sha(path: Path) -> str:
    text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    if not text.endswith("\n"):
        text += "\n"
    return sha(text.encode("utf-8"))


def rel32_jump(source_va: int, target_va: int) -> bytes:
    return b"\xE9" + int(target_va - source_va - 5).to_bytes(
        4, "little", signed=True
    )


def companion() -> dict[str, object]:
    if COMPANION.stat().st_size != COMPANION_SIZE or sha(COMPANION.read_bytes()) != COMPANION_SHA256:
        raise RuntimeError("Task9 companion identity mismatch")
    return {
        "source": "data/candidates/VVFP VV5 Task9 Origins Icons.dll",
        "destination": "VVFP Origins Icons.dll",
        "sha256": COMPANION_SHA256,
        "size": COMPANION_SIZE,
    }


def add_string(
    payload: bytearray,
    labels: dict[str, int],
    base_va: int,
    cursor: int,
    name: str,
    value: str,
) -> int:
    encoded = value.encode("ascii") + b"\0"
    labels[name] = base_va + cursor
    payload[cursor : cursor + len(encoded)] = encoded
    return cursor + len(encoded)


def build_vv4_payload(
    mode: str = EXPANDED_MODES[0],
) -> tuple[bytes, dict[str, object]]:
    if mode not in EXPANDED_MODES:
        raise ValueError(f"VV4 Expanded Time Warp does not support mode {mode!r}")
    speed_offset = VV4_SPEED_OFFSET_BY_MODE[mode]
    base_va = 0x489373
    size = 0xC8D
    strings_offset = 0xA00
    payload = bytearray(size)
    labels: dict[str, int] = {}
    cursor = strings_offset
    for name, value in (
        ("button", "Upgrades"),
        ("dll", "VVFP Origins Icons.dll"),
        ("begin", "BeginOriginsOwner"),
        ("get", "GetOriginsOwner"),
        ("end", "EndOriginsOwner"),
        ("menu", "ShowOriginsUpgradeMenuState"),
        ("user32", "USER32.dll"),
        ("messagebox", "MessageBoxA"),
        ("title", "Origins Upgrades"),
        (
            "warning",
            "This upgrade makes permanent changes to your village. Are you sure you want to continue?",
        ),
        (
            "paused",
            "Time Warp is unavailable while the game is paused.\r\nNo tech points have been deducted.",
        ),
        ("insufficient", "Not enough tech points.\r\nNo tech points have been deducted."),
        ("stopped", "Time Warp stopped.\r\nNo tech points have been deducted."),
        ("success", "Time Warp completed."),
        (
            "charge_unknown",
            "The Time Warp charge outcome is unknown; the village clock was not changed.",
        ),
        (
            "clock_unknown",
            "The charge succeeded, but the Time Warp clock update could not be verified.",
        ),
    ):
        cursor = add_string(payload, labels, base_va, cursor, name, value)
    if cursor > size:
        raise RuntimeError("VV4 Time Warp strings exceed the reviewed cave")

    occupied = bytearray(size)
    occupied[strings_offset:cursor] = b"\1" * (cursor - strings_offset)

    def put(offset: int, source: str, limit: int) -> bytes:
        encoded = asm(source, base_va + offset)
        if len(encoded) > limit:
            raise RuntimeError(
                f"VV4 Time Warp routine at +0x{offset:X} exceeds reserve: {len(encoded):#x}/{limit:#x}"
            )
        if any(occupied[offset : offset + limit]):
            raise RuntimeError(f"VV4 Time Warp routine overlap at +0x{offset:X}")
        payload[offset : offset + len(encoded)] = encoded
        occupied[offset : offset + len(encoded)] = b"\1" * len(encoded)
        return encoded

    handler = put(
        0x000,
        f"""
            cmp dword ptr [esp+4], 8
            jne original
            cmp dword ptr [esp+8], 13
            jne original
            call 0x{base_va + 0x260:X}
            xor eax, eax
            ret 8
        original:
            push edi
            mov edi, ecx
            call 0x44DA20
            jmp 0x43E9F8
        """,
        0x40,
    )
    constructor = put(
        0x040,
        f"""
            push 0x14
            call 0x470C5C
            add esp, 4
            test eax, eax
            je done
            push 0x3F800000
            push 0
            push 13
            push 0x{labels['button']:X}
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
            mov ecx, dword ptr [esp+0x4C]
            jmp 0x43E16B
        """,
        0x170,
    )
    show_menu = put(
        0x1B0,
        f"""
            push ebx
            push esi
            push 0x{labels['dll']:X}
            call dword ptr [0x48A1E0]
            test eax, eax
            jz unavailable
            push 0x{labels['menu']:X}
            push eax
            call dword ptr [0x48A1DC]
            test eax, eax
            jz unavailable
            push dword ptr [esp+0xC]
            push 0
            call eax
            jmp done
        unavailable:
            mov eax, -1
        done:
            pop esi
            pop ebx
            ret 4
        """,
        0x50,
    )
    show_message = put(
        0x200,
        f"""
            push ebx
            push esi
            push edi
            mov esi, dword ptr [esp+0x10]
            mov edi, dword ptr [esp+0x14]
            push 0x{labels['dll']:X}
            call dword ptr [0x48A1E0]
            test eax, eax
            jz done
            push 0x{labels['get']:X}
            push eax
            call dword ptr [0x48A1DC]
            test eax, eax
            jz done
            call eax
            test eax, eax
            jz done
            xchg ebx, eax
            push 0x{labels['user32']:X}
            call dword ptr [0x48A1E0]
            test eax, eax
            jz done
            push 0x{labels['messagebox']:X}
            push eax
            call dword ptr [0x48A1DC]
            test eax, eax
            jz done
            push edi
            push 0x{labels['title']:X}
            push esi
            push ebx
            call eax
        done:
            pop edi
            pop esi
            pop ebx
            ret 8
        """,
        0x60,
    )
    transaction = put(
        0x260,
        f"""
            push ebp
            mov ebp, esp
            push ebx
            push esi
            push edi
            sub esp, 0x40
            mov dword ptr [ebp-0x10], 0
            mov dword ptr [ebp-0x14], 0
            push 0x{labels['dll']:X}
            call dword ptr [0x48A1E0]
            test eax, eax
            jz cleanup
            mov esi, eax
            push 0x{labels['end']:X}
            push esi
            call dword ptr [0x48A1DC]
            test eax, eax
            jz cleanup
            mov dword ptr [ebp-0x10], eax
            push 0x{labels['begin']:X}
            push esi
            call dword ptr [0x48A1DC]
            test eax, eax
            jz cleanup
            mov dword ptr [ebp-0x14], 1
            call eax
            test eax, eax
            jz cleanup
            push 0x3E00
            call 0x{base_va + 0x1B0:X}
            cmp eax, -1
            je cleanup
            test eax, eax
            jne unavailable
            call 0x41FE70
            test eax, eax
            jz unavailable
            mov dword ptr [ebp-0x18], eax
            mov eax, dword ptr [eax+0x{speed_offset:X}]
            cmp eax, 999
            je paused
            cmp eax, 3
            je speed_ready
            cmp eax, 10
            je speed_ready
            mov eax, 6
        speed_ready:
            mov dword ptr [ebp-0x1C], eax
            mov eax, dword ptr [0x4D6F88]
            mov dword ptr [ebp-0x20], eax
            cmp eax, 50000
            jb insufficient
            mov eax, dword ptr [0x4B8230]
            mov dword ptr [ebp-0x24], eax
            mov eax, dword ptr [0x4B8234]
            mov dword ptr [ebp-0x28], eax
            push 1
            push 0x{labels['warning']:X}
            call 0x{base_va + 0x200:X}
            cmp eax, 1
            jne cancelled
            call 0x41FE70
            cmp eax, dword ptr [ebp-0x18]
            jne recheck
            mov eax, dword ptr [eax+0x{speed_offset:X}]
            cmp eax, 999
            je recheck
            cmp eax, 3
            je fresh_speed
            cmp eax, 10
            je fresh_speed
            mov eax, 6
        fresh_speed:
            cmp eax, dword ptr [ebp-0x1C]
            jne recheck
            mov eax, dword ptr [0x4D6F88]
            cmp eax, dword ptr [ebp-0x20]
            jne recheck
            cmp eax, 50000
            jb insufficient
            mov eax, dword ptr [0x4B8230]
            cmp eax, dword ptr [ebp-0x24]
            jne recheck
            mov eax, dword ptr [0x4B8234]
            cmp eax, dword ptr [ebp-0x28]
            jne recheck
            push -50000
            mov ecx, 0x4D6F88
            call 0x41E300
            mov eax, dword ptr [ebp-0x20]
            sub eax, 50000
            cmp dword ptr [0x4D6F88], eax
            jne charge_unknown
            mov eax, dword ptr [ebp-0x1C]
            imul eax, eax, 3600
            mov dword ptr [ebp-0x2C], eax
            mov ecx, dword ptr [ebp-0x24]
            mov edx, dword ptr [ebp-0x28]
            sub ecx, eax
            sbb edx, 0
            mov dword ptr [ebp-0x30], ecx
            mov dword ptr [ebp-0x34], edx
            sub dword ptr [0x4B8230], eax
            sbb dword ptr [0x4B8234], 0
            cmp dword ptr [0x4B8230], ecx
            jne clock_unknown
            cmp dword ptr [0x4B8234], edx
            jne clock_unknown
            push 0x40
            push 0x{labels['success']:X}
            call 0x{base_va + 0x200:X}
            jmp cleanup
        paused:
            push 0x30
            push 0x{labels['paused']:X}
            call 0x{base_va + 0x200:X}
            jmp cleanup
        insufficient:
            push 0x30
            push 0x{labels['insufficient']:X}
            call 0x{base_va + 0x200:X}
            jmp cleanup
        cancelled:
            push 0x30
            push 0x{labels['stopped']:X}
            call 0x{base_va + 0x200:X}
            jmp cleanup
        recheck:
            push 0x30
            push 0x{labels['stopped']:X}
            call 0x{base_va + 0x200:X}
            jmp cleanup
        unavailable:
            push 0x30
            push 0x{labels['stopped']:X}
            call 0x{base_va + 0x200:X}
            jmp cleanup
        charge_unknown:
            push 0x30
            push 0x{labels['charge_unknown']:X}
            call 0x{base_va + 0x200:X}
            jmp cleanup
        clock_unknown:
            push 0x30
            push 0x{labels['clock_unknown']:X}
            call 0x{base_va + 0x200:X}
        cleanup:
            cmp dword ptr [ebp-0x14], 0
            je done
            call dword ptr [ebp-0x10]
        done:
            add esp, 0x40
            pop edi
            pop esi
            pop ebx
            pop ebp
            ret
        """,
        strings_offset - 0x260,
    )
    return bytes(payload), {
        "handler_length": len(handler),
        "constructor_length": len(constructor),
        "show_menu_length": len(show_menu),
        "show_message_length": len(show_message),
        "transaction_length": len(transaction),
        "handler_sha256": sha(handler),
        "constructor_sha256": sha(constructor),
        "show_menu_sha256": sha(show_menu),
        "show_message_sha256": sha(show_message),
        "transaction_sha256": sha(transaction),
        "strings_used": cursor - strings_offset,
        "strings": {key: f"0x{value:X}" for key, value in labels.items()},
    }


def load_task9_builder():
    spec = importlib.util.spec_from_file_location("vv5_task9_builder_tw", TASK9_BUILDER)
    if spec is None or spec.loader is None:
        raise RuntimeError("Task9 builder is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_vv5_overlay() -> tuple[list[dict[str, object]], dict[str, object]]:
    task9 = load_task9_builder()
    if task9.OFF.get("time_warp") != 0x1040 or task9.SIZES.get("time_warp") != 0x500:
        raise RuntimeError("Task9 Time Warp reserve drift")
    if task9.OFF.get("age") != 0xD40 or task9.SIZES.get("age") != 0x300:
        raise RuntimeError("Task9 age reserve drift")
    page_va = 0x904000
    base_page, base_map = task9.build_page(page_va)
    if sha(base_page) != "88AEDF7FAE96AA725744EC00E63C9F5262AC73D0E29DFF9ABB2EDCF5BACD9457":
        raise RuntimeError("Task9 Expanded baseline page drift")
    stock_page, stock_map = task9.build_page(0x7C9000)
    if sha(stock_page) != "1783D690F2BA4743708265BF4DA15AA17C36672F826BBB13679163300AB44DAD":
        raise RuntimeError("Task9 stock page drift")

    strings_start = task9.OFF["strings"]
    last_nonzero = max(
        index for index in range(strings_start, len(base_page)) if base_page[index] != 0
    )
    string_offset = last_nonzero + 2
    string_blob = bytearray()
    labels: dict[str, int] = {}
    for name, value in (
        ("get", "GetOriginsOwner"),
        ("user32", "USER32.dll"),
        ("messagebox", "MessageBoxA"),
        ("title", "Origins Upgrades"),
        (
            "warning",
            "This upgrade makes permanent changes to your village. Are you sure you want to continue?",
        ),
        (
            "paused",
            "Time Warp is unavailable while the game is paused.\r\nNo tech points have been deducted.",
        ),
        ("insufficient", "Not enough tech points.\r\nNo tech points have been deducted."),
        ("cancelled", "Time Warp was canceled.\r\nNo tech points have been deducted."),
        (
            "recheck",
            "The game speed, village clock, or tech-point balance changed during confirmation.\r\nNo tech points have been deducted.",
        ),
        ("unavailable", "Time Warp is unavailable.\r\nNo tech points have been deducted."),
        ("success", "Time Warp completed."),
        (
            "charge_unknown",
            "The final tech-point balance did not match the exact 50,000-point deduction. The charge outcome is unknown; the village clock was not changed.",
        ),
        (
            "clock_unknown",
            "The 50,000-point deduction was verified, but the village clock update could not be verified.",
        ),
    ):
        encoded = value.encode("ascii") + b"\0"
        labels[name] = page_va + string_offset + len(string_blob)
        string_blob.extend(encoded)
    if string_offset < strings_start or string_offset + len(string_blob) > task9.PAGE_SIZE:
        raise RuntimeError("VV5 Time Warp strings exceed the Task9 string reserve")
    if any(base_page[string_offset : string_offset + len(string_blob)]):
        raise RuntimeError("VV5 Time Warp string preimage is not zero")
    dll_va = int(base_map["string_virtual_addresses"]["dll"], 0)
    routine_va = page_va + task9.OFF["time_warp"]
    routine = asm(
        f"""
            test ebx, ebx
            jne 0x904967
            push ebp
            mov ebp, esp
            push ebx
            push esi
            push edi
            sub esp, 0x50
            mov dword ptr [ebp-0x10], 0
            mov dword ptr [ebp-0x14], 0
            push 0x{dll_va:X}
            call dword ptr [0x4951E0]
            test eax, eax
            jz unavailable
            push 0x{labels['get']:X}
            push eax
            call dword ptr [0x4951DC]
            test eax, eax
            jz unavailable
            mov dword ptr [ebp-0x10], eax
            push 0x{labels['user32']:X}
            call dword ptr [0x4951E0]
            test eax, eax
            jz unavailable
            push 0x{labels['messagebox']:X}
            push eax
            call dword ptr [0x4951DC]
            test eax, eax
            jz unavailable
            mov dword ptr [ebp-0x14], eax
            call 0x425950
            test eax, eax
            jz unavailable
            mov edi, eax
            mov eax, dword ptr [edi+0x17D7C]
            test eax, eax
            jle unavailable
            cmp eax, 999
            je paused
            mov dword ptr [ebp-0x1C], eax
            mov dword ptr [ebp-0x18], edi
            mov eax, dword ptr [0x51D5F8]
            mov dword ptr [ebp-0x20], eax
            cmp eax, 50000
            jb insufficient
            mov eax, dword ptr [0x4C6250]
            mov dword ptr [ebp-0x24], eax
            mov eax, dword ptr [0x4C6254]
            mov dword ptr [ebp-0x28], eax
            mov eax, 0x{labels['warning']:X}
            mov edx, 1
            call show_message
            cmp eax, 1
            jne cancelled
            call 0x425950
            cmp eax, dword ptr [ebp-0x18]
            jne recheck
            mov edi, eax
            mov eax, dword ptr [edi+0x17D7C]
            test eax, eax
            jle recheck
            cmp eax, 999
            je recheck
            cmp eax, dword ptr [ebp-0x1C]
            jne recheck
            mov eax, dword ptr [0x51D5F8]
            cmp eax, dword ptr [ebp-0x20]
            jne recheck
            cmp eax, 50000
            jb insufficient
            mov eax, dword ptr [0x4C6250]
            cmp eax, dword ptr [ebp-0x24]
            jne recheck
            mov eax, dword ptr [0x4C6254]
            cmp eax, dword ptr [ebp-0x28]
            jne recheck
            push -50000
            mov ecx, 0x51D5F8
            call 0x4237B0
            mov eax, dword ptr [ebp-0x20]
            sub eax, 50000
            mov dword ptr [ebp-0x2C], eax
            cmp dword ptr [0x51D5F8], eax
            jne charge_unknown
            mov eax, 129600
            xor edx, edx
            div dword ptr [ebp-0x1C]
            mov dword ptr [ebp-0x30], eax
            mov ecx, dword ptr [ebp-0x24]
            mov edx, dword ptr [ebp-0x28]
            sub ecx, eax
            sbb edx, 0
            mov dword ptr [ebp-0x34], ecx
            mov dword ptr [ebp-0x38], edx
            sub dword ptr [0x4C6250], eax
            sbb dword ptr [0x4C6254], 0
            cmp dword ptr [0x4C6250], ecx
            jne clock_unknown
            cmp dword ptr [0x4C6254], edx
            jne clock_unknown
            mov eax, 0x{labels['success']:X}
            mov edx, 0x40
            call show_message
            jmp done
        paused:
            mov eax, 0x{labels['paused']:X}
            jmp warning_status
        insufficient:
            mov eax, 0x{labels['insufficient']:X}
            jmp warning_status
        cancelled:
            mov eax, 0x{labels['cancelled']:X}
            jmp warning_status
        recheck:
            mov eax, 0x{labels['recheck']:X}
            jmp warning_status
        unavailable:
            mov eax, 0x{labels['unavailable']:X}
            jmp warning_status
        charge_unknown:
            mov eax, 0x{labels['charge_unknown']:X}
            jmp warning_status
        clock_unknown:
            mov eax, 0x{labels['clock_unknown']:X}
        warning_status:
            mov edx, 0x30
            call show_message
        done:
            add esp, 0x50
            pop edi
            pop esi
            pop ebx
            pop ebp
            jmp 0x904846
        show_message:
            mov dword ptr [ebp-0x3C], eax
            mov dword ptr [ebp-0x40], edx
            cmp dword ptr [ebp-0x10], 0
            je message_unavailable
            cmp dword ptr [ebp-0x14], 0
            je message_unavailable
            call dword ptr [ebp-0x10]
            test eax, eax
            jz message_unavailable
            push dword ptr [ebp-0x40]
            push 0x{labels['title']:X}
            push dword ptr [ebp-0x3C]
            push eax
            call dword ptr [ebp-0x14]
            ret
        message_unavailable:
            xor eax, eax
            ret
        """,
        routine_va,
    )
    if len(routine) > task9.SIZES["time_warp"]:
        raise RuntimeError(
            f"VV5 Time Warp dispatcher exceeds reserve: {len(routine):#x}/{task9.SIZES['time_warp']:#x}"
        )
    routine_block = routine.ljust(task9.SIZES["time_warp"], b"\0")
    if any(base_page[task9.OFF["time_warp"] : task9.OFF["time_warp"] + len(routine_block)]):
        raise RuntimeError("VV5 Time Warp routine preimage is not zero")
    if base_page[0x846:0x850] != bytes.fromhex("B800070000F70588D351"):
        raise RuntimeError("VV5 Task9 menu-state preimage drift")
    if base_page[0x8AB:0x8B4] != bytes.fromhex("83FB030F82B3000000"):
        raise RuntimeError("VV5 Task9 command-router operand preimage drift")
    patches = [
        {
            "offset": "0xF4846",
            "before": "B800070000F70588D351",
            "after": "B8001E0000E93F000000",
            "purpose": "set fixed dialog state 0x1E00 and bypass dynamic row 3/4 state while preserving row 5 Full Heal",
        },
        {
            "offset": "0xF48AB",
            "before": "83FB030F82B3000000",
            "after": "83FB050F828C070000",
            "purpose": "route commands 0..4 through the dispatcher so only command 0 runs Time Warp and commands 1..4 are unavailable",
        },
        {
            "offset": "0xF5040",
            "before_fill": "00",
            "length": len(routine_block),
            "after": routine_block.hex().upper(),
            "purpose": "install reviewed command-0 Time Warp dispatcher in the reserved Task9 page",
        },
        {
            "offset": f"0x{0xF4000 + string_offset:X}",
            "before_fill": "00",
            "length": len(string_blob),
            "after": bytes(string_blob).hex().upper(),
            "purpose": "install owner-safe Time Warp confirmation and result strings in the Task9 string reserve",
        },
    ]
    rendered = bytearray(base_page)
    rendered[0x846:0x850] = bytes.fromhex("B8001E0000E93F000000")
    rendered[0x8AB:0x8B4] = bytes.fromhex("83FB050F828C070000")
    rendered[task9.OFF["time_warp"] : task9.OFF["time_warp"] + len(routine_block)] = routine_block
    rendered[string_offset : string_offset + len(string_blob)] = string_blob
    return patches, {
        "stock_page_sha256": sha(stock_page),
        "expanded_baseline_page_sha256": sha(base_page),
        "expanded_time_warp_page_sha256": sha(bytes(rendered)),
        "age_length": stock_map["routine_length"]["age"],
        "age_sha256_stock": stock_map["routine_sha256"]["age"],
        "age_sha256_expanded": base_map["routine_sha256"]["age"],
        "dispatcher_length": len(routine),
        "dispatcher_sha256": sha(routine),
        "dispatcher_block_sha256": sha(routine_block),
        "dispatcher_va": "0x905040",
        "unavailable_target": "0x904967",
        "menu_target": "0x904846",
        "strings_offset": f"0x{string_offset:X}",
        "strings_file_offset": f"0x{0xF4000 + string_offset:X}",
        "strings_length": len(string_blob),
        "strings_sha256": sha(bytes(string_blob)),
        "strings": {key: f"0x{value:X}" for key, value in labels.items()},
    }


def feature_common(game_id: str, feature_id: str, name: str) -> dict[str, object]:
    return {
        "id": feature_id,
        "game_id": game_id,
        "name": name,
        "description": (
            "Adds the reviewed Time Warp purchase only to experimental Expanded-256. "
            "The action advances the village clock by exactly three displayed villager years "
            "for 50,000 tech points, after an owner-safe permanent-change confirmation."
        ),
        "output_tag": "Expanded Time Warp",
        "enabled": True,
        "catalog_enabled": False,
        "catalog_hidden": True,
        "experimental_explicit_selection": True,
        "supported_modes": list(EXPANDED_MODES),
        "rejected_modes": ["collection_progression", "immediate_fixed"],
        "patches": [],
        "behavior_changes": [
            "Enables Time Warp in experimental Expanded-256 for 50,000 tech points.",
            "Time Warp subtracts an exact speed-scaled three-year delta from the village clock after one verified deduction.",
        ],
        "explicit_non_changes": [
            "Stock patch modes and stock executable bytes are unchanged.",
            "No villager record, faction, Believer gate, save schema, import, section, or relocation ledger is changed.",
        ],
        "evidence_status": "independent static Disassembler GO; runtime/player confirmation pending",
        "runtime_player_status": "pending",
    }


def main() -> None:
    vv4_payloads = {
        mode: build_vv4_payload(mode)[0] for mode in EXPANDED_MODES
    }
    vv4_payload, vv4_map = build_vv4_payload(EXPANDED_MODES[0])
    vv5_patches, vv5_map = build_vv5_overlay()
    bindings = {
        "builder": {
            "path": "scripts/build_expanded_time_warp.py",
            "source_text_sha256": source_text_sha(SELF),
        },
        "task9_builder": {
            "path": "scripts/build_vv5_task9_native_actions.py",
            "source_text_sha256": source_text_sha(TASK9_BUILDER),
        },
        "task9_companion_c": {
            "path": "native/vv5_task9_origins/vv5_task9_origins.c",
            "source_text_sha256": source_text_sha(ROOT / "native/vv5_task9_origins/vv5_task9_origins.c"),
        },
        "task9_companion_def": {
            "path": "native/vv5_task9_origins/vv5_task9_origins.def",
            "source_text_sha256": source_text_sha(ROOT / "native/vv5_task9_origins/vv5_task9_origins.def"),
        },
        "task9_companion_rc": {
            "path": "native/vv5_task9_origins/vv5_task9_origins.rc",
            "source_text_sha256": source_text_sha(ROOT / "native/vv5_task9_origins/vv5_task9_origins.rc"),
        },
    }

    vv4 = feature_common("vv4", "vv4_expanded_256_time_warp", "Enable Time Warp (Expanded-256)")
    vv4.update(
        {
            "conflicts": [
                "vv4_enable_origins_exclusive_features",
                "vv4_enable_origins_exclusive_features_full_mastery_candidate",
                "vv4_full_mastery_all_stage_a_candidate",
            ],
            "companion_files": [companion()],
            "patch_mode_overrides": {
                mode: [
                    {
                        "offset": "0x89373",
                        "before_fill": "00",
                        "length": len(vv4_payloads[mode]),
                        "after": vv4_payloads[mode].hex().upper(),
                        "purpose": "install standalone Time Warp handler, constructor, owner-safe UI helpers, transaction, and strings in the reviewed zero RX cave",
                    },
                    {
                        "offset": "0x3E165",
                        "before": "8BC68B4C244C",
                        "after": "E949B2040090",
                        "purpose": "route the Tech-screen constructor through the standalone Time Warp constructor",
                    },
                    {
                        "offset": "0x3E9F0",
                        "before": "578BF9E828F00000",
                        "after": "E97EA90400909090",
                        "purpose": "route Tech command 13 through the standalone Time Warp handler",
                    },
                ]
                for mode in EXPANDED_MODES
            },
            "source_bindings": bindings,
            "native_contract": {
                "dialog_state": "0x3E00; row 0 enabled and rows 1..5 unavailable",
                "permanent_warning": "This upgrade makes permanent changes to your village. Are you sure you want to continue?",
                "confirmation": "MessageBoxA IDOK only through captured same-process Task9 companion owner",
                "manager": "0x41FE70",
                "speed": "Expanded modes read [manager+0x1DCB8]; paused=999; 3 and 10 accepted, all other values normalize to 6",
                "stock_speed_reference": "[manager+0x17110] remains stock-only; stock modes are byte-frozen and rejected by this feature",
                "delta": "normalized speed * 3600",
                "clock": "0x4B8230/0x4B8234 sub/sbb and exact readback",
                "funds": "0x4D6F88; one -50000 call to 0x41E300 and exact readback before clock mutation",
            },
        }
    )
    vv5 = feature_common("vv5", "vv5_expanded_256_time_warp", "Enable Time Warp (Expanded-256)")
    vv5.update(
        {
            "dependencies": ["vv5_enable_origins_exclusive_features"],
            "companion_contract": companion(),
            "patch_mode_overrides": {mode: vv5_patches for mode in EXPANDED_MODES},
            "source_bindings": bindings,
            "native_contract": {
                "dialog_state": "fixed 0x1E00; row 0 enabled, rows 1..4 unavailable, existing row 5 Full Heal preserved; dynamic row 3/4 state is bypassed",
                "permanent_warning": "This upgrade makes permanent changes to your village. Are you sure you want to continue?",
                "confirmation": "MessageBoxA IDOK only through the captured same-process Task9 companion owner",
                "manager": "0x425950 nonnull",
                "speed": "[manager+0x17D7C] signed positive and not 999",
                "delta": "129600 / exact positive speed",
                "clock": "0x4C6250/0x4C6254 sub/sbb and exact readback",
                "funds": "0x51D5F8; one -50000 call to 0x4237B0 and exact readback before clock mutation",
                "dispatcher": "EBX!=0 -> 0x904967 unavailable; EBX==0 -> Time Warp -> 0x904846 menu",
            },
        }
    )

    VV4_OUT.write_text(json.dumps(vv4, indent=2) + "\n", encoding="utf-8")
    VV5_OUT.write_text(json.dumps(vv5, indent=2) + "\n", encoding="utf-8")
    vv4_map_out = {
        "id": vv4["id"],
        "status": "independent static Disassembler GO; runtime/player pending",
        "source_bindings": bindings,
        "companion": companion(),
        "payload_file_offset": "0x89373",
        "payload_va": "0x489373",
        "payload_size": len(vv4_payload),
        "payload_sha256": sha(vv4_payload),
        "payload_sha256_by_mode": {
            mode: sha(payload) for mode, payload in vv4_payloads.items()
        },
        "speed_offset_by_mode": {
            mode: f"0x{VV4_SPEED_OFFSET_BY_MODE[mode]:X}" for mode in EXPANDED_MODES
        },
        "layout": vv4_map,
        "hooks": vv4["patch_mode_overrides"][EXPANDED_MODES[0]][1:],
        "forbidden_mutations": ["PE sections", "imports", ".shr", "13-row ledger", "stock modes", "VV3"],
        "stock_no_mutation_sha256": {
            "collection_progression": "132516F4A5F7D2E9B539B14300207AEA5872FDCC0D34F13768435D9F4B6F76D4",
            "immediate_fixed": "EB0CDD4F7F5E41F7A03734D51F9417A126C3BE9D214B484A848DB688545CF5FB",
        },
        "expanded_rendered_sha256": {
            "experimental_expanded_256": "13109DFD12B9458CCBFB92F9D5122A29C2A9CE63DEE256AFB9C0355CE8AA7B7C",
            "experimental_expanded_256_progression": "91889DCD1D94EB0E4FCE5988FFECCF464FCF989F286CA50343E70ABB07DC1DDD",
        },
    }
    vv5_map_out = {
        "id": vv5["id"],
        "status": "independent static Disassembler GO; runtime/player pending",
        "source_bindings": bindings,
        "companion": companion(),
        "dependency": "vv5_enable_origins_exclusive_features",
        "page_raw": "0xF4000",
        "page_rva": "0x504000",
        "page_va": "0x904000",
        "layout": vv5_map,
        "patches": vv5_patches,
        "forbidden_mutations": ["stock Task9 page", "Task9 hooks", "PE sections", "imports", "companion bytes", "C342 ledger", "VV3"],
        "stock_no_mutation_sha256": {
            "collection_progression": "3540FA10994826A37205C6BF4F0CDC244B9E2AC5D99A5BFE54AF72B4B948D29A",
            "immediate_fixed": "08B81AFB590A0F7171CECECD66DD0A149115A4A383E8C5AA157343A7A242B7FF",
        },
        "expanded_rendered_sha256": {
            "experimental_expanded_256": "65D81A31B9BA44AFA8E69E0A0B787ED680DFB0FC832B66FA8D11C899D2B80A5D",
            "experimental_expanded_256_progression": "B6AD620FA4B1D339B18130BA737EDC17CB0C40E326D0D461AA43166B79ABAA88",
        },
    }
    VV4_MAP_OUT.write_text(json.dumps(vv4_map_out, indent=2) + "\n", encoding="utf-8")
    VV5_MAP_OUT.write_text(json.dumps(vv5_map_out, indent=2) + "\n", encoding="utf-8")
    print(f"VV4 payload {len(vv4_payload)} bytes {sha(vv4_payload)}")
    print(f"VV5 dispatcher {vv5_map['dispatcher_length']} bytes {vv5_map['dispatcher_sha256']}")
    print(f"VV5 page {vv5_map['expanded_time_warp_page_sha256']}")


if __name__ == "__main__":
    main()
