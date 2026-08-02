"""Generate the certified VV3 Running base-core and slot artifacts.

The command-6 feature is enabled only after independent byte certification.
Commands 7 and 8 remain absent.
"""

from __future__ import annotations

import hashlib
import json
import struct
import sys
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Secret City.exe"
ACTIVE_BASE = ROOT / "data" / "vv3_origins_feature.json"
OUT_DIR = ROOT / "data" / "candidates"
BASE_OUT = OUT_DIR / "vv3_origins_running_base_candidate.json"
RUNNING_OUT = OUT_DIR / "vv3_all_villagers_like_running_candidate.json"
MAP_OUT = OUT_DIR / "vv3_running_candidate_map.json"
DOC_OUT = ROOT / "docs" / "vv3-running-stage-a-candidate.md"
COMPANION = ROOT / "assets" / "origins" / "VVFP Origins Icons.dll"

sys.path.insert(0, str(ROOT / ".tools" / "keystone"))
sys.path.insert(0, str(ROOT / ".tools" / "keystone-runtime"))
from keystone import KS_ARCH_X86, KS_MODE_32, Ks  # noqa: E402
from runtime_freeze import isolated_runtime_freeze  # noqa: E402


IMAGE_BASE = 0x400000
PAYLOAD_OFFSET = 0xA3180
PAYLOAD_VA = 0x4A3180
PAYLOAD_SIZE = 0xE80
SHOW_DIALOG_OFFSET = 0x220
SHOW_DIALOG_SIZE = 0x60
TECH_MENU_OFFSET = 0x340
TECH_MENU_SIZE = 0x310
CURE_OFFSET = 0x7B664
APPEND_OFFSET = 0xCB000
PAGE_SIZE = 0x1000
SLOT_OFFSET = 0x100
SLOT_SIZE = 0x700
SLOT_ENTRY_OFFSET = 0x20
RUNNING_ID = 38
CONFIRMATION_OFFSET = 0x800
NO_CHANGE_OFFSET = 0x880
CONFIRMATION_HELPER_OFFSET = 0x900
CONFIRMATION_TEXT = (
    b"This upgrade makes permanent changes to your village. Are you sure you "
    b"want to purchase it? Press OK to confirm, or Cancel.\0"
)
NO_CHANGE_TEXT = (
    b"Everyone already likes running.\r\n"
    b"No tech points have been deducted.\0"
)

LAYOUTS = {
    "collection_progression": {
        "page_rva": 0x2DF000,
        "page_va": 0x6DF000,
        "old_size_of_image": 0x2DF000,
        "new_size_of_image": 0x2E0000,
    },
    "immediate_fixed": {
        "page_rva": 0x2DF000,
        "page_va": 0x6DF000,
        "old_size_of_image": 0x2DF000,
        "new_size_of_image": 0x2E0000,
    },
    "experimental_expanded_256": {
        "page_rva": 0x3B8000,
        "page_va": 0x7B8000,
        "old_size_of_image": 0x3B8000,
        "new_size_of_image": 0x3B9000,
    },
    "experimental_expanded_256_progression": {
        "page_rva": 0x3B8000,
        "page_va": 0x7B8000,
        "old_size_of_image": 0x3B8000,
        "new_size_of_image": 0x3B9000,
    },
}


def asm(source: str, address: int) -> bytes:
    encoding, _ = Ks(KS_ARCH_X86, KS_MODE_32).asm(source, address)
    return bytes(encoding)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def canonical_sha(value: object) -> str:
    return sha(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("ascii")
    )


def delta_ranges(before: bytes, after: bytes, base_offset: int) -> list[dict[str, object]]:
    if len(before) != len(after):
        raise RuntimeError("delta range inputs must be equal length")
    result: list[dict[str, object]] = []
    cursor = 0
    while cursor < len(before):
        if before[cursor] == after[cursor]:
            cursor += 1
            continue
        start = cursor
        while cursor < len(before) and before[cursor] != after[cursor]:
            cursor += 1
        result.append(
            {
                "offset": f"0x{base_offset + start:X}",
                "length": cursor - start,
                "before": before[start:cursor].hex().upper(),
                "after": after[start:cursor].hex().upper(),
            }
        )
    return result


def export_map(data: bytes) -> dict[str, dict[str, int]]:
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    coff = pe + 4
    sections = struct.unpack_from("<H", data, coff + 2)[0]
    optional_size = struct.unpack_from("<H", data, coff + 16)[0]
    optional = coff + 20
    export_rva = struct.unpack_from("<I", data, optional + 96)[0]
    section_table = optional + optional_size

    def raw(rva: int) -> int:
        for index in range(sections):
            entry = section_table + index * 40
            virtual_size, section_rva, raw_size, raw_offset = struct.unpack_from(
                "<IIII", data, entry + 8
            )
            if section_rva <= rva < section_rva + max(virtual_size, raw_size):
                return raw_offset + rva - section_rva
        raise RuntimeError(f"unmapped RVA 0x{rva:X}")

    directory = raw(export_rva)
    ordinal_base, function_count, name_count = struct.unpack_from(
        "<III", data, directory + 16
    )
    functions_rva, names_rva, ordinals_rva = struct.unpack_from(
        "<III", data, directory + 28
    )
    result: dict[str, dict[str, int]] = {}
    for index in range(name_count):
        name_rva = struct.unpack_from("<I", data, raw(names_rva) + index * 4)[0]
        cursor = raw(name_rva)
        end = data.index(0, cursor)
        name = data[cursor:end].decode("ascii")
        ordinal_index = struct.unpack_from(
            "<H", data, raw(ordinals_rva) + index * 2
        )[0]
        if ordinal_index >= function_count:
            raise RuntimeError("export ordinal index is out of range")
        function_rva = struct.unpack_from(
            "<I", data, raw(functions_rva) + ordinal_index * 4
        )[0]
        result[name] = {
            "ordinal": ordinal_base + ordinal_index,
            "rva": function_rva,
        }
    return result


def _put(blob: bytearray, offset: int, size: int, payload: bytes, label: str) -> None:
    if len(payload) > size:
        raise RuntimeError(f"{label} is too large: {len(payload):#x}/{size:#x}")
    blob[offset : offset + size] = payload + b"\0" * (size - len(payload))


def build_slot(installed: bool) -> tuple[bytes, dict[str, int | str]]:
    slot = bytearray(SLOT_SIZE)
    slot[0:8] = b"VVRNSLT\0"
    slot[8:12] = (1).to_bytes(4, "little")
    slot[12:16] = int(installed).to_bytes(4, "little")
    slot[16:20] = SLOT_ENTRY_OFFSET.to_bytes(4, "little")
    slot[20:24] = SLOT_SIZE.to_bytes(4, "little")
    entry_va = SLOT_ENTRY_OFFSET
    if not installed:
        body = asm(
            """
                mov eax, -1
                xor edx, edx
                xor ecx, ecx
                ret
            """,
            entry_va,
        )
        slot[SLOT_ENTRY_OFFSET : SLOT_ENTRY_OFFSET + len(body)] = body
        return bytes(slot), {
            "entry_offset": SLOT_ENTRY_OFFSET,
            "entry_length": len(body),
            "entry_sha256": sha(body),
        }

    walk_offset = 0x240
    body = bytes.fromhex(
        "5553565783EC20894C241089542414897C241883F8060F85DF000000"
        "C7042400000000C744240400000000C744240800000000C744240C00000000"
        "8D3C248B4C24108B54241431C0E8D3010000833C24000F848F000000"
        "E88407000085C00F8490000000"
        "C7042400000000C744240400000000C744240800000000C744240C00000000"
        "8D3C248B4C24108B54241431C0E88B010000833C2400744B"
        "813D4426580040420F007246812D4426580040420F00"
        "8B7C2418C70700000000C7470400000000C7470800000000C7470C00000000"
        "8B4C24108B542414B801000000E83E01000031C0EB1A"
        "B802000000EB13B803000000EB0CB8FFFFFFFFEB05B8FFFFFFFF"
        "83C4205F5E5B5DC3"
    )
    walker = asm(
        f"""
            push ebp
            push ebx
            push esi
            push edi
            sub esp, 8
            mov dword ptr [esp], eax
            mov dword ptr [esp + 4], edi
            mov esi, ecx
            mov ebp, edx
        record_loop:
            test ebp, ebp
            jz walk_done
            cmp byte ptr [esi + 0xF10], 0
            je next_record
            cmp dword ptr [esi + 0xE78], 0
            jle next_record
            xor ebx, ebx
            lea ecx, [esi + 0xFB4]
            mov edx, 3
        like_loop:
            cmp dword ptr [ecx], {RUNNING_ID}
            je already_like
            cmp dword ptr [ecx], -1
            jne like_next
            test ebx, ebx
            jne like_next
            mov ebx, ecx
        like_next:
            add ecx, 4
            dec edx
            jne like_loop
            test ebx, ebx
            jz full_like
            xor eax, eax
            lea ecx, [esi + 0xFC0]
            mov edx, 3
        dislike_loop:
            cmp dword ptr [ecx], {RUNNING_ID}
            jne dislike_next
            mov eax, 1
            cmp dword ptr [esp], 0
            je dislike_next
            mov dword ptr [ecx], -1
        dislike_next:
            add ecx, 4
            dec edx
            jne dislike_loop
            test eax, eax
            jz no_removed
            mov edi, dword ptr [esp + 4]
            inc dword ptr [edi + 12]
        no_removed:
            mov edi, dword ptr [esp + 4]
            inc dword ptr [edi]
            cmp dword ptr [esp], 0
            je next_record
            mov dword ptr [ebx], {RUNNING_ID}
            jmp next_record
        already_like:
            mov edi, dword ptr [esp + 4]
            inc dword ptr [edi + 4]
            jmp next_record
        full_like:
            mov edi, dword ptr [esp + 4]
            inc dword ptr [edi + 8]
        next_record:
            add esi, 0x1F8C
            dec ebp
            jmp record_loop
        walk_done:
            add esp, 8
            pop edi
            pop esi
            pop ebx
            pop ebp
            ret
        """,
        walk_offset,
    )
    if SLOT_ENTRY_OFFSET + len(body) > walk_offset:
        raise RuntimeError("transaction overlaps walker")
    slot[SLOT_ENTRY_OFFSET : SLOT_ENTRY_OFFSET + len(body)] = body
    slot[walk_offset : walk_offset + len(walker)] = walker
    return bytes(slot), {
        "entry_offset": SLOT_ENTRY_OFFSET,
        "entry_length": len(body),
        "entry_sha256": sha(body),
        "walker_offset": walk_offset,
        "walker_length": len(walker),
        "walker_sha256": sha(walker),
    }


def build_dispatcher(page_va: int, result_export_va: int) -> bytes:
    if result_export_va != 0x4A3F80:
        raise RuntimeError("unexpected @20 export-name VA")
    if page_va == 0x6DF000:
        payload = (
            "55535657813D00F16D005656524E0F859C000000833D0CF16D00010F858F000000"
            "83EC1089E631C0890689460489460889460C89F7B924E159008B153A884200B806000000"
            "E89600000089C383FB00740C83FB02743783FB037443EB50"
            "68D83E4A00FF1524C1470085C0744168803F4A0050FF1528C1470085C07431"
            "FF760CFF7608FF7604FF366A06FFD0EB20"
            "6880F86D0068893D4A00E82443DCFFEB0F"
            "68C03D4A0068893D4A00E81343DCFF83C4105F5E5B5DC3"
        )
    elif page_va == 0x7B8000:
        payload = (
            "55535657813D00817B005656524E0F859C000000833D0C817B00010F858F000000"
            "83EC1089E631C0890689460489460889460C89F7B924E159008B153A884200B806000000"
            "E89600000089C383FB00740C83FB02743783FB037443EB50"
            "68D83E4A00FF1524C1470085C0744168803F4A0050FF1528C1470085C07431"
            "FF760CFF7608FF7604FF366A06FFD0EB20"
            "6880887B0068893D4A00E824B3CEFFEB0F"
            "68C03D4A0068893D4A00E813B3CEFF83C4105F5E5B5DC3"
        )
    else:
        raise RuntimeError(f"unsupported VV3 Running page VA 0x{page_va:X}")
    return bytes.fromhex(payload)


def build_confirmation_helper(page_va: int) -> bytes:
    if page_va == 0x6DF000:
        payload = (
            "535668283F4A00FF1524C1470085C0742B68333F4A0050FF1528C1470085C0741B"
            "6A3168893D4A006800F86D006A00FFD083F8010F94C00FB6C0EB0231C05E5BC3"
        )
    elif page_va == 0x7B8000:
        payload = (
            "535668283F4A00FF1524C1470085C0742B68333F4A0050FF1528C1470085C0741B"
            "6A3168893D4A006800887B006A00FFD083F8010F94C00FB6C0EB0231C05E5BC3"
        )
    else:
        raise RuntimeError(f"unsupported VV3 Running page VA 0x{page_va:X}")
    return bytes.fromhex(payload)


def build_page(page_va: int, slot: bytes, dispatcher: bytes) -> bytes:
    page = bytearray(PAGE_SIZE)
    page[0:8] = b"VVRUNPG\0"
    page[8:12] = (1).to_bytes(4, "little")
    page[12:16] = PAGE_SIZE.to_bytes(4, "little")
    page[16:20] = SLOT_OFFSET.to_bytes(4, "little")
    page[20:24] = SLOT_SIZE.to_bytes(4, "little")
    page[24:28] = (SLOT_OFFSET + SLOT_ENTRY_OFFSET).to_bytes(4, "little")
    page[28:32] = page_va.to_bytes(4, "little")
    if 0x40 + len(dispatcher) > SLOT_OFFSET:
        raise RuntimeError("base dispatcher overlaps extension slot")
    page[0x40 : 0x40 + len(dispatcher)] = dispatcher
    page[SLOT_OFFSET : SLOT_OFFSET + SLOT_SIZE] = slot
    page[
        CONFIRMATION_OFFSET : CONFIRMATION_OFFSET + len(CONFIRMATION_TEXT)
    ] = CONFIRMATION_TEXT
    page[NO_CHANGE_OFFSET : NO_CHANGE_OFFSET + len(NO_CHANGE_TEXT)] = NO_CHANGE_TEXT
    helper = build_confirmation_helper(page_va)
    page[
        CONFIRMATION_HELPER_OFFSET : CONFIRMATION_HELPER_OFFSET + len(helper)
    ] = helper
    return bytes(page)


def section_header(rva: int) -> bytes:
    return (
        b".vvrun\0\0"
        + PAGE_SIZE.to_bytes(4, "little")
        + rva.to_bytes(4, "little")
        + PAGE_SIZE.to_bytes(4, "little")
        + APPEND_OFFSET.to_bytes(4, "little")
        + b"\0" * 12
        + (0x60000020).to_bytes(4, "little")
    )


def append_layout(layout: dict[str, int], page: bytes) -> dict[str, object]:
    return {
        "original_file_size": f"0x{APPEND_OFFSET:X}",
        "append_offset": f"0x{APPEND_OFFSET:X}",
        "append_bytes": page.hex().upper(),
        "virtual_address": f"0x{layout['page_va']:X}",
        "purpose": "append the base-owned certified VV3 Running extension page",
        "header_patches": [
            {
                "offset": "0x10E",
                "before": "0500",
                "after": "0600",
                "purpose": "add the base-owned .vvrun section",
            },
            {
                "offset": "0x158",
                "before": layout["old_size_of_image"].to_bytes(4, "little").hex().upper(),
                "after": layout["new_size_of_image"].to_bytes(4, "little").hex().upper(),
                "purpose": "extend SizeOfImage for the base-owned .vvrun page",
            },
            {
                "offset": "0x2C8",
                "before": "00" * 40,
                "after": section_header(layout["page_rva"]).hex().upper(),
                "purpose": "install the guarded .vvrun section header",
            },
        ],
    }


def build_base_payload(active_payload: bytes, page_va: int, result_export_va: int) -> bytes:
    payload = bytearray(active_payload)
    slot_header_va = page_va + SLOT_OFFSET
    page_dispatcher_va = page_va + 0x40
    show_dialog = asm(
        f"""
            push ebx
            push esi
            push 0x4A3ED8
            call dword ptr [0x47C124]
            test eax, eax
            je unavailable
            push 0x4A3EEF
            push eax
            call dword ptr [0x47C128]
            test eax, eax
            je unavailable
            cmp dword ptr [0x{slot_header_va:X}], 0x4E525656
            jne no_running
            cmp dword ptr [0x{slot_header_va + 12:X}], 1
            jne no_running
            or dword ptr [esp + 0x10], 0x40000
        no_running:
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
        PAYLOAD_VA + SHOW_DIALOG_OFFSET,
    )
    tech_menu = bytearray(payload[TECH_MENU_OFFSET : TECH_MENU_OFFSET + TECH_MENU_SIZE])
    village_start = tech_menu.find(bytes.fromhex("83FB0672"))
    legacy_start = tech_menu.find(bytes.fromhex("8B049D"))
    if village_start != 0xF8 or legacy_start != 0x12F:
        raise RuntimeError("current tech-menu command block does not match certified layout")
    menu_loop_va = PAYLOAD_VA + TECH_MENU_OFFSET + 6
    legacy_va = PAYLOAD_VA + TECH_MENU_OFFSET + legacy_start
    replacement = asm(
        f"""
            cmp ebx, 6
            jb 0x{legacy_va:X}
            jne 0x{menu_loop_va:X}
            call 0x{page_dispatcher_va:X}
            jmp 0x{menu_loop_va:X}
        """,
        PAYLOAD_VA + TECH_MENU_OFFSET + village_start,
    )
    if len(replacement) > legacy_start - village_start:
        raise RuntimeError("command-6-only dispatch does not fit the certified block")
    tech_menu[village_start:legacy_start] = replacement + b"\x90" * (
        legacy_start - village_start - len(replacement)
    )
    _put(payload, SHOW_DIALOG_OFFSET, SHOW_DIALOG_SIZE, show_dialog, "candidate show_dialog")
    _put(payload, TECH_MENU_OFFSET, TECH_MENU_SIZE, bytes(tech_menu), "candidate tech_menu")
    return bytes(payload)


def main() -> None:
    stock = STOCK.read_bytes()
    if len(stock) != APPEND_OFFSET or sha(stock) != (
        "8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503"
    ):
        raise RuntimeError("VV3 stock fixture fingerprint mismatch")
    active = json.loads(ACTIVE_BASE.read_text(encoding="utf-8"))
    payload_patch = next(
        item for item in active["patches"] if int(item["offset"], 0) == PAYLOAD_OFFSET
    )
    active_payload = bytes.fromhex(payload_patch["after"]).ljust(PAYLOAD_SIZE, b"\0")
    result_string = b"ShowOriginsVillageWideResult@20\0"
    string_offset = 0xE00
    if any(active_payload[string_offset : string_offset + len(result_string)]):
        raise RuntimeError("candidate export string slot is not zero")
    active_payload = bytearray(active_payload)
    active_payload[string_offset : string_offset + len(result_string)] = result_string
    result_export_va = PAYLOAD_VA + string_offset

    noop_slot, noop_map = build_slot(False)
    running_slot, running_map = build_slot(True)
    dispatchers = {
        mode: build_dispatcher(layout["page_va"], result_export_va)
        for mode, layout in LAYOUTS.items()
    }
    candidate = deepcopy(active)
    candidate["id"] = "vv3_enable_origins_exclusive_features_running_candidate"
    candidate["name"] = "DISABLED Candidate: VV3 Origins Running Extension Base"
    candidate["enabled"] = False
    candidate["certification_status"] = (
        "Stage C corrected; not catalog-visible; awaiting Sol byte recertification"
    )
    candidate["dependencies"] = []
    candidate["patches"] = [
        item for item in candidate["patches"] if int(item["offset"], 0) != 0x7B7A0
    ]
    cure_item = next(
        item for item in candidate["patches"] if int(item["offset"], 0) == CURE_OFFSET
    )
    current_cure = bytes.fromhex(cure_item["after"])
    cure_start = current_cure.find(bytes.fromhex("53555152565731C0"))
    if cure_start < 0:
        raise RuntimeError("candidate cure-only body signature not found")
    cure_item["after"] = (
        current_cure[cure_start:] + b"\0" * cure_start
    ).hex().upper()
    cure_item["purpose"] = (
        "preserve Cure all Villagers without the forbidden commands 6/7/8 router"
    )
    payload_item = next(
        item for item in candidate["patches"] if int(item["offset"], 0) == PAYLOAD_OFFSET
    )
    stock_payload = build_base_payload(
        bytes(active_payload), LAYOUTS["collection_progression"]["page_va"], result_export_va
    )
    expanded_payload = build_base_payload(
        bytes(active_payload), LAYOUTS["experimental_expanded_256"]["page_va"], result_export_va
    )
    payload_item["before"] = (b"\0" * PAYLOAD_SIZE).hex().upper()
    payload_item["after"] = stock_payload.hex().upper()
    payload_item["purpose"] = "install the certified VV3 Origins base with a command-6-only extension dispatcher"
    candidate["patch_mode_overrides"] = {
        mode: [
            {
                "offset": f"0x{PAYLOAD_OFFSET:X}",
                "before": stock_payload.hex().upper(),
                "after": expanded_payload.hex().upper(),
                "purpose": "retarget only the base-owned Running slot references for expanded-256",
            }
        ]
        for mode in (
            "experimental_expanded_256",
            "experimental_expanded_256_progression",
        )
    }
    candidate["pe_append_transaction"] = {
        "owner": candidate["id"],
        "section_name": ".vvrun",
        "append_length": PAGE_SIZE,
        "slot_offset": f"0x{SLOT_OFFSET:X}",
        "slot_length": f"0x{SLOT_SIZE:X}",
        "removal_policy": "Running slot must equal the base no-op bytes before base restore/truncate",
        "layouts": {
            mode: append_layout(
                layout, build_page(layout["page_va"], noop_slot, dispatcher)
            )
            for mode, layout in LAYOUTS.items()
            for dispatcher in (dispatchers[mode],)
        },
    }

    running = {
        "id": "vv3_all_villagers_like_running_candidate",
        "game_id": "vv3",
        "name": "DISABLED Candidate: All Villagers Like Running",
        "enabled": False,
        "dependencies": [candidate["id"]],
        "description": "Stage C corrected command-6-only candidate; not selectable pending Sol byte recertification.",
        "behavior_changes": ["Candidate-only guarded replacement of the base-owned no-op slot."],
        "explicit_non_changes": [
            "Commands 7 and 8 are absent.",
            "Uninstall restores the no-op slot and does not reverse preference edits.",
            "Running is a repeatable Buy action and never reads, sets, or clears save ownership bit 0x4.",
            "Vanilla save layout is unchanged.",
        ],
        "evidence_status": "generated Stage C corrected candidate; Sol byte recertification pending",
        "companion_files": [],
        "patches": [
            {
                "offset": f"0x{APPEND_OFFSET + SLOT_OFFSET:X}",
                "before": noop_slot.hex().upper(),
                "after": running_slot.hex().upper(),
                "purpose": "replace only the guarded base-owned no-op slot with command 6",
            }
        ],
    }
    artifact_map = {
        "disassembly_handoffs": [
            "d78db872efe04f98bd19b45c9e098bb5a25d53b8",
            "b9c7a22eb1d7cceae25160ce4d360621e7485625",
            "f73625582adae714473068c272b90af91a57d945",
            "0095e605b3b488129c0623efd642e9352d8586c0",
        ],
        "active_base_payload_sha256": sha(bytes.fromhex(payload_patch["before"]))
        if bytes.fromhex(payload_patch["before"]).strip(b"\0")
        else sha(bytes.fromhex(payload_patch["after"])),
        "candidate_stock_payload_sha256": sha(stock_payload),
        "candidate_expanded_payload_sha256": sha(expanded_payload),
        "noop_slot_sha256": sha(noop_slot),
        "running_slot_sha256": sha(running_slot),
        "noop": noop_map,
        "running": running_map,
        "page_layouts": {
            mode: {
                **layout,
                "page_sha256": sha(
                    build_page(layout["page_va"], noop_slot, dispatcher)
                ),
                "running_page_sha256": sha(
                    build_page(layout["page_va"], running_slot, dispatcher)
                ),
                "dispatcher_sha256": sha(dispatchers[mode]),
            }
            for mode, layout in LAYOUTS.items()
            for dispatcher in (dispatchers[mode],)
        },
        "slot_abi": {
            "input": "EAX=6, ECX=first record, EDX=physical bound, EDI=pointer to four DWORD counters",
            "counter_order": ["granted", "already_like", "full_like", "removed_dislike"],
            "return_status": {
                "0": "committed",
                "1": "forbidden and never produced",
                "2": "no change",
                "3": "insufficient",
                "-1": "invalid or confirmation declined/unavailable",
            },
            "preserved": ["EBX", "ESI", "EDI", "EBP", "ESP"],
        },
        "dispatcher": {
            "offset": 0x40,
            "length": len(dispatchers["collection_progression"]),
            "stock_sha256": sha(dispatchers["collection_progression"]),
            "expanded_sha256": sha(dispatchers["experimental_expanded_256"]),
            "role": "base-owned command-6-only bridge; resolves @20 and reports four counters",
        },
        "stage_c_corrections": {
            "status": "HARD WITHDRAWN after intermittent Run2 status-2 crash; runtime fault capture required",
            "result_arguments": "stable ESI counter base pushes removed_dislike, full_like, already_like, granted, then command 6",
            "dispatcher_nonvolatile_registers": ["EBP", "EBX", "ESI", "EDI"],
            "transaction_passes": [
                "read-only dry run",
                "confirmation",
                "read-only final dry recheck",
                "single commit",
            ],
            "charge_order": (
                "first dry granted check; exact warning; final dry granted "
                "recheck; unsigned balance recheck; one deduction; one commit"
            ),
            "confirmation": {
                "text": CONFIRMATION_TEXT[:-1].decode("ascii"),
                "offset": CONFIRMATION_OFFSET,
                "sha256": sha(CONFIRMATION_TEXT),
                "helper_offset": CONFIRMATION_HELPER_OFFSET,
            },
            "no_change": {
                "text": NO_CHANGE_TEXT[:-1].decode("ascii"),
                "offset": NO_CHANGE_OFFSET,
                "sha256": sha(NO_CHANGE_TEXT),
            },
            "forbidden": [
                "stack-relative counter aliasing after ESP movement",
                "unbalanced dispatcher EBX or EDI clobber",
                "record mutation before charge",
                "post-commit no-change branch",
                "status 1",
                "any read, set, or clear of 0x5824D0 bit 0x4",
                "a Running Remove UI or preference reversal",
            ],
        },
        "companion": {
            "size": COMPANION.stat().st_size,
            "sha256": sha(COMPANION.read_bytes()),
            "exports": export_map(COMPANION.read_bytes()),
            "required_export": "ShowOriginsVillageWideResult@20",
            "calling_convention": "stdcall, five 32-bit arguments, callee ret 20",
            "result_buffer_bytes": 256,
        },
        "active_runtime_projection": isolated_runtime_freeze(
            game_id="vv3",
            map_path=MAP_OUT,
            data_root=ROOT / "data",
            section="active_runtime_projection",
        ),
        "payload_delta_ranges": {
            "stock": delta_ranges(bytes(active_payload), stock_payload, PAYLOAD_OFFSET),
            "expanded": delta_ranges(
                bytes(active_payload), expanded_payload, PAYLOAD_OFFSET
            ),
        },
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    BASE_OUT.write_text(json.dumps(candidate, indent=2) + "\n", encoding="utf-8")
    RUNNING_OUT.write_text(json.dumps(running, indent=2) + "\n", encoding="utf-8")
    sys.path.insert(0, str(ROOT / "src"))
    from vv_fun_patcher import (  # noqa: PLC0415
        FunPatch,
        _pe_checksum_layout,
        load_builds,
        render_patched_bytes,
    )

    build = next(item for item in load_builds() if item.id == "vv3")
    render_map: dict[str, object] = {}
    for mode in LAYOUTS:
        base_rendered, _ = render_patched_bytes(
            STOCK,
            build,
            mode,
            _fun_patches_override=[FunPatch(candidate)],
        )
        running_rendered, applied = render_patched_bytes(
            STOCK,
            build,
            mode,
            _fun_patches_override=[FunPatch(candidate), FunPatch(running)],
        )
        checksum_offset, _ = _pe_checksum_layout(running_rendered)
        render_map[mode] = {
            "base_only_sha256": sha(bytes(base_rendered)),
            "base_plus_running_sha256": sha(bytes(running_rendered)),
            "base_plus_running_size": len(running_rendered),
            "pe_checksum": f"0x{struct.unpack_from('<I', running_rendered, checksum_offset)[0]:08X}",
            "owned_edit_count": len(applied),
        }
    artifact_map["rendered_candidates"] = render_map
    MAP_OUT.write_text(json.dumps(artifact_map, indent=2) + "\n", encoding="utf-8")
    stock_render = render_map["collection_progression"]
    expanded_render = render_map["experimental_expanded_256"]
    DOC_OUT.write_text(
        f"""# VV3 Running corrected certified artifact

This generated artifact is HARD WITHDRAWN and catalog-hidden after the
intermittent Run2 status-2 crash. Runtime fault capture remains required;
commands 7 and 8 remain absent.

Evidence inputs are disassembly commits
`d78db872efe04f98bd19b45c9e098bb5a25d53b8` and
`b9c7a22eb1d7cceae25160ce4d360621e7485625`. Stage C corrects the three
defects certified by Sol at
`f73625582adae714473068c272b90af91a57d945`: the @20 counter arguments now
use a stable base, the dispatcher preserves every nonvolatile register it
uses, and exact repair contract
`0095e605b3b488129c0623efd642e9352d8586c0` replaces the revoked owned-state
transaction. Gameplay validation remains pending.
Player-confirmed Like 38 /
Dislike -1 save-and-reload persistence is supporting runtime evidence, not PE
integration proof.

## Deterministic layout

- Base-owned section: `.vvrun`, raw `0xCB000`, length `0x1000`.
- Stock RVA/VA: `0x2DF000` / `0x6DF000`; expanded RVA/VA:
  `0x3B8000` / `0x7B8000`.
- Base dispatcher: page `+0x40`, stock SHA-256
  `{artifact_map['dispatcher']['stock_sha256']}`, expanded SHA-256
  `{artifact_map['dispatcher']['expanded_sha256']}`.
- Guarded extension slot: page `+0x100`, file `0xCB100`, length `0x700`;
  entry `+0x20`, walker `+0x240`.
- No-op slot SHA-256: `{artifact_map['noop_slot_sha256']}`.
- Running slot SHA-256: `{artifact_map['running_slot_sha256']}`.
- Stock base payload SHA-256:
  `{artifact_map['candidate_stock_payload_sha256']}`.
- Expanded base payload SHA-256:
  `{artifact_map['candidate_expanded_payload_sha256']}`.
- Companion DLL SHA-256: `{artifact_map['companion']['sha256']}`;
  `ShowOriginsVillageWideResult@20` is ordinal
  `{artifact_map['companion']['exports']['ShowOriginsVillageWideResult@20']['ordinal']}`,
  RVA `0x{artifact_map['companion']['exports']['ShowOriginsVillageWideResult@20']['rva']:X}`,
  stdcall five arguments with a 256-byte result buffer.

Stock base+Running render SHA-256 is
`{stock_render['base_plus_running_sha256']}` with PE checksum
`{stock_render['pe_checksum']}`. Expanded base+Running render SHA-256 is
`{expanded_render['base_plus_running_sha256']}` with PE checksum
`{expanded_render['pe_checksum']}`.

The machine-readable complete map, payload deltas, page hashes, per-mode
checksums, ABI, and export map are in
`data/candidates/vv3_running_candidate_map.json`.

## Closed transaction and record contract

The candidate uses only active `+0xF10 != 0` and signed health
`+0xE78 > 0`; dormant `+0xE94` is not read. It scans exactly three Likes
`+0xFB4..+0xFBC` and three Dislikes `+0xFC0..+0xFC8`, with sentinel `-1`
and independently confirmed Running ID 38. Already-like records are skipped
without mutation. Otherwise the first empty Like is preflighted before any
Running dislike is removed; full Likes cause no mutation. All Running
dislikes are cleared, unrelated slots and order are preserved, and 38 is
written to the first empty Like.

Running is a repeatable Buy action and has no ownership or Remove state. A
read-only dry run happens first. Zero grants show exactly
`Everyone already likes running.\\r\\nNo tech points have been deducted.`
without warning, charge, or writes. Positive grants show the exact universal
permanent-change OK/Cancel warning. Cancel, close, or import failure is inert.
OK repeats the identical read-only dry run, then performs the final unsigned
1,000,000-point balance recheck, one deduction, and one mutating commit.
Command 6 never reads, sets, or clears `0x5824D0 & 0x4`; stale bit 4 is
ignored. Commands 7 and 8 are absent.

The four exact result lines are:

1. `Granted Running to %u villagers`
2. `Skipped over %u villagers. Reason: already likes running`
3. `Skipped over %u villagers. Reason: all like slots are occupied`
4. `Removed running dislike from %u villagers`

Persistent means serialized and restored, not immutable. This candidate must
preserve unrelated fields at its transaction and save roundtrip and must not
intercept native future writers. Native events and other game mechanics may
legitimately change persisted fields later.

## Ownership and uninstall

Base Origins remains the sole owner of hooks `0x6547D` and `0x65640`, the
section header, appended page, and checksum. Running replaces only the exact
guarded slot. Running patch uninstall restores the no-op slot without truncating or
reversing preferences. Base removal is dependency-blocked while Running is
installed; afterward it guards its bytes, restores the stock headers and
hooks, truncates exactly `0x1000`, and recomputes the checksum.
""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
