"""Generate the certified VV5 command-7 Full Mastery feature."""

from __future__ import annotations

import hashlib
import json
import struct
import sys
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - New Believers.exe"
ACTIVE_BASE = ROOT / "data" / "vv5_origins_feature.json"
OUT_DIR = ROOT / "data" / "candidates"
BASE_OUT = OUT_DIR / "vv5_origins_full_mastery_base_candidate.json"
FEATURE_OUT = OUT_DIR / "vv5_full_mastery_all_candidate.json"
MAP_OUT = OUT_DIR / "vv5_full_mastery_all_candidate_map.json"
DOC_OUT = ROOT / "docs" / "vv5-full-mastery-stage-a-candidate.md"
COMPANION = OUT_DIR / "VVFP VV5 Full Mastery Candidate.dll"
PROVENANCE_ASSET = ROOT / "assets" / "candidates" / "vv5_full_mastery" / "provenance" / "btn_trophies.png"
PROVENANCE_ASSET_SHA256 = "F39E94CBDF24776631D803D1218EFCCDE555081C9C8C644DD073B75EC7DD2095"

sys.path.insert(0, str(ROOT / ".tools" / "keystone"))
sys.path.insert(0, str(ROOT / ".tools" / "keystone-runtime"))
from keystone import KS_ARCH_X86, KS_MODE_32, Ks  # noqa: E402
from runtime_freeze import isolated_runtime_freeze  # noqa: E402


IMAGE_BASE = 0x400000
PAYLOAD_OFFSET = 0xDB000
PAYLOAD_VA = 0x7B2000
PAYLOAD_SIZE = 0x1000
SHOW_DIALOG_OFFSET = 0x1C0
SHOW_DIALOG_SIZE = 0x50
TECH_MENU_OFFSET = 0x2C0
TECH_MENU_SIZE = 0x340
CURE_OFFSET = 0x94EA0
VILLAGE_PREFLIGHT_OFFSET = 0x94B37
APPEND_OFFSET = 0xF2000
PAGE_SIZE = 0x2000
SLOT_OFFSET = 0x100
SLOT_SIZE = 0x1000
SLOT_ENTRY_OFFSET = 0x20
WALKER_OFFSET = 0x400
CONFIRM_OFFSET = 0x800
# Keep the independently certified individual confirmation at 0x800.  The
# village-wide command gets its own bounded routine in the remaining zero cave
# before the individual transaction at 0xC00.
VILLAGE_CONFIRM_OFFSET = 0x850
INDIVIDUAL_OFFSET = 0xC00
STRINGS_OFFSET = 0x1200
PRICE = 1_000_000
INDIVIDUAL_PRICE = 100_000
STRIDE = 0x2F44

LAYOUTS = {
    "collection_progression": {
        "page_rva": 0x3C9000,
        "page_va": 0x7C9000,
        "bound": 150,
        "old_size_of_image": 0x3C9000,
        "new_size_of_image": 0x3CB000,
    },
    "immediate_fixed": {
        "page_rva": 0x3C9000,
        "page_va": 0x7C9000,
        "bound": 150,
        "old_size_of_image": 0x3C9000,
        "new_size_of_image": 0x3CB000,
    },
}

EXPANDED_MODES = (
    "experimental_expanded_256",
    "experimental_expanded_256_progression",
)


def asm(source: str, address: int) -> bytes:
    encoding, _ = Ks(KS_ARCH_X86, KS_MODE_32).asm(source, address)
    return bytes(encoding)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def canonical_sha(value: object) -> str:
    return sha(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii"))


def export_map(data: bytes) -> dict[str, dict[str, int]]:
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    coff = pe + 4
    sections = struct.unpack_from("<H", data, coff + 2)[0]
    optional_size = struct.unpack_from("<H", data, coff + 16)[0]
    optional = coff + 20
    section_table = optional + optional_size
    export_rva = struct.unpack_from("<I", data, optional + 96)[0]

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
        ordinal_index = struct.unpack_from("<H", data, raw(ordinals_rva) + index * 2)[0]
        if ordinal_index >= function_count:
            raise RuntimeError("export ordinal index out of range")
        function_rva = struct.unpack_from(
            "<I", data, raw(functions_rva) + ordinal_index * 4
        )[0]
        result[name] = {"ordinal": ordinal_base + ordinal_index, "rva": function_rva}
    return result


def _put(blob: bytearray, offset: int, size: int, payload: bytes, label: str) -> None:
    if len(payload) > size:
        raise RuntimeError(f"{label} exceeds reserved size: {len(payload):#x}/{size:#x}")
    if any(blob[offset : offset + size]):
        raise RuntimeError(f"{label} overlaps nonzero bytes")
    blob[offset : offset + size] = payload + b"\0" * (size - len(payload))


def _add_string(blob: bytearray, cursor: int, value: bytes, page_va: int) -> tuple[int, int]:
    if not value.endswith(b"\0"):
        value += b"\0"
    end = cursor + len(value)
    if end > SLOT_SIZE:
        raise RuntimeError("slot strings exceed reserved space")
    blob[cursor:end] = value
    return page_va + SLOT_OFFSET + cursor, end


def build_individual_helper(page_va: int, strings: dict[str, int]) -> bytes:
    """Candidate-only command-1 transaction; native writer, no raw stores."""
    va = page_va + SLOT_OFFSET + INDIVIDUAL_OFFSET
    return asm(f"""
        cmp ebx, 1
        je individual_body
        cmp ebx, 2
        je 0x7B276B
        jmp 0x7B2790
    individual_body:
        push ebp
        mov ebp, esp
        push ebx
        push esi
        push edi
        sub esp, 0x20
        mov dword ptr [ebp-0x10], esi
        call 0x425950
        test eax, eax
        jz bad
        mov eax, dword ptr [eax+0x17E24]
        cmp eax, 0x96
        jae bad
        mov dword ptr [ebp-0x14], eax
        mov ecx, 0x554148
        push eax
        call 0x471840
        test eax, eax
        jz bad
        mov ecx, 0x554148
        push dword ptr [ebp-0x14]
        call 0x46F950
        test eax, eax
        jz bad
        mov dword ptr [ebp-0x18], eax
        mov esi, eax
        cmp byte ptr [esi+0x1CD4], 0
        je bad
        cmp dword ptr [esi+0x1C40], 0
        jle bad
        cmp byte ptr [esi+0x1CE1], 0
        jne bad
        cmp byte ptr [esi+0x1CEC], 0
        jne bad
        xor edi, edi
        xor ebx, ebx
    dry1:
        cmp edi, 6
        jae dry1_done
        mov eax, dword ptr [esi+edi*4+0x1C5C]
        mov edx, eax
        and edx, 0x7FFFFFFF
        jz dry1_next
        test eax, 0x80000000
        jne bad
        cmp edx, 0x42C80000
        ja bad
    dry1_next:
        cmp edx, 0x42C80000
        jae dry1_count
        inc ebx
    dry1_count:
        inc edi
        jmp dry1
    dry1_done:
        test ebx, ebx
        jz no_change
        cmp dword ptr [0x51D5F8], {INDIVIDUAL_PRICE}
        jb insufficient
        call 0x{page_va + SLOT_OFFSET + CONFIRM_OFFSET:X}
        test eax, eax
        jz cancel
        call 0x425950
        test eax, eax
        jz recheck
        mov eax, dword ptr [eax+0x17E24]
        cmp eax, dword ptr [ebp-0x14]
        jne recheck
        mov ecx, 0x554148
        push eax
        call 0x471840
        test eax, eax
        jz recheck
        mov ecx, 0x554148
        push dword ptr [ebp-0x14]
        call 0x46F950
        test eax, eax
        jz recheck
        mov dword ptr [ebp-0x18], eax
        mov esi, eax
        cmp byte ptr [esi+0x1CD4], 0
        je recheck
        cmp dword ptr [esi+0x1C40], 0
        jle recheck
        cmp byte ptr [esi+0x1CE1], 0
        jne recheck
        cmp byte ptr [esi+0x1CEC], 0
        jne recheck
        xor edi, edi
        xor ebx, ebx
    dry2:
        cmp edi, 6
        jae dry2_done
        mov eax, dword ptr [esi+edi*4+0x1C5C]
        mov edx, eax
        and edx, 0x7FFFFFFF
        jz dry2_next
        test eax, 0x80000000
        jne recheck
        cmp edx, 0x42C80000
        ja recheck
    dry2_next:
        cmp edx, 0x42C80000
        jae dry2_count
        inc ebx
    dry2_count:
        inc edi
        jmp dry2
    dry2_done:
        test ebx, ebx
        jz recheck
        cmp dword ptr [0x51D5F8], {INDIVIDUAL_PRICE}
        jb insufficient
        xor edi, edi
    write_loop:
        cmp edi, 6
        jae verify
        mov eax, dword ptr [esi+edi*4+0x1C5C]
        cmp eax, 0x42C80000
        je write_next
        push 0x42C80000
        fld dword ptr [esp]
        fsub dword ptr [esi+edi*4+0x1C5C]
        fstp dword ptr [esp]
        push edi
        lea ecx, [esi+0x1C5C]
        call 0x475730
    write_next:
        inc edi
        jmp write_loop
    verify:
        xor edi, edi
    verify_loop:
        cmp edi, 6
        jae commit
        cmp dword ptr [esi+edi*4+0x1C5C], 0x42C80000
        jne postverify
        inc edi
        jmp verify_loop
    commit:
        push -{INDIVIDUAL_PRICE}
        mov ecx, 0x51D5F8
        call 0x4237B0
        push 0x{strings['individual_success']:X}
        push 0x{strings['caption']:X}
        call 0x7B2210
        jmp done
    no_change:
        push 0x{strings['individual_no_change']:X}
        push 0x{strings['caption']:X}
        call 0x7B2210
        jmp done
    insufficient:
        push 0x{strings['individual_insufficient']:X}
        push 0x{strings['caption']:X}
        call 0x7B2210
        jmp done
    cancel:
        push 0x{strings['individual_cancel']:X}
        push 0x{strings['caption']:X}
        call 0x7B2210
        jmp done
    recheck:
        push 0x{strings['individual_recheck']:X}
        push 0x{strings['caption']:X}
        call 0x7B2210
        jmp done
    postverify:
        push 0x{strings['individual_postverify']:X}
        push 0x{strings['caption']:X}
        call 0x7B2210
        jmp done
    bad:
        push 0x{strings['individual_invalid']:X}
        push 0x{strings['caption']:X}
        call 0x7B2210
    done:
        mov esi, dword ptr [ebp-0x10]
        add esp, 0x20
        pop edi
        pop esi
        pop ebx
        pop ebp
        jmp 0x7B2606
    """, va)


def build_confirmation(
    routine_va: int,
    user32_va: int,
    message_box_va: int,
    caption_va: int,
    message_va: int,
) -> bytes:
    """Emit the fixed stdcall MessageBoxA wrapper for one confirmation text."""
    return asm(
        f"""
            push ebp
            mov ebp, esp
            push ebx
            push esi
            push edi
            push 0x{user32_va:X}
            call dword ptr [0x4951E0]
            test eax, eax
            jz cancel
            push 0x{message_box_va:X}
            push eax
            call dword ptr [0x4951DC]
            test eax, eax
            jz cancel
            push 1
            push 0x{caption_va:X}
            push 0x{message_va:X}
            push 0
            call eax
            cmp eax, 1
            sete al
            movzx eax, al
            jmp confirm_done
        cancel:
            xor eax, eax
        confirm_done:
            pop edi
            pop esi
            pop ebx
            mov esp, ebp
            pop ebp
            ret
        """,
        routine_va,
    )


def build_slot(page_va: int, installed: bool) -> tuple[bytes, dict[str, object]]:
    slot = bytearray(SLOT_SIZE)
    slot[0:8] = b"VVFMSLT\0"
    slot[8:12] = (1).to_bytes(4, "little")
    slot[12:16] = int(installed).to_bytes(4, "little")
    slot[16:20] = SLOT_ENTRY_OFFSET.to_bytes(4, "little")
    slot[20:24] = SLOT_SIZE.to_bytes(4, "little")
    entry_va = page_va + SLOT_OFFSET + SLOT_ENTRY_OFFSET
    if not installed:
        body = asm("mov eax, -1; xor edx, edx; ret", entry_va)
        slot[SLOT_ENTRY_OFFSET : SLOT_ENTRY_OFFSET + len(body)] = body
        return bytes(slot), {
            "entry_offset": SLOT_ENTRY_OFFSET,
            "entry_length": len(body),
            "entry_sha256": sha(body),
        }

    cursor = STRINGS_OFFSET
    strings: dict[str, int] = {}
    for key, value in (
        ("dll", b"VVFP Origins Icons.dll"),
        ("result", b"ShowVV5FullMasteryResult"),
        ("user32", b"user32.dll"),
        ("message_box", b"MessageBoxA"),
        (
            "warning",
            b"This upgrade makes permanent changes to your village. Are you sure "
            b"you want to purchase it? Press OK to confirm, or Cancel.",
        ),
        ("caption", b"Origins Upgrades"),
        ("individual_no_change", b"This villager is already fully mastered.\r\nNo tech points have been deducted."),
        ("individual_invalid", b"Full Mastery cannot be applied because the selected villager has an out-of-range skill.\r\nNo tech points have been deducted."),
        ("individual_insufficient", b"You do not have enough tech points.\r\nNo tech points have been deducted."),
        ("individual_cancel", b"Full Mastery was canceled.\r\nNo tech points have been deducted."),
        ("individual_recheck", b"The selected villager changed or no longer passed the final checks.\r\nNo tech points have been deducted."),
        ("individual_postverify", b"Full Mastery could not be verified.\r\nNo tech points have been deducted."),
        ("individual_confirm", b"Grant Full Mastery to this villager for 100,000 tech points?\r\nPress OK to confirm, or Cancel."),
        ("individual_success", b"Full Mastery has been granted to the selected villager."),
        (
            "village_confirm",
            b"Grant Full Mastery to all eligible villagers for 1,000,000 tech points?\r\n"
            b"Press OK to confirm, or Cancel.",
        ),
    ):
        if not value.endswith(b"\0"):
            value += b"\0"
        strings[key] = page_va + cursor
        cursor += len(value)
        if cursor > PAGE_SIZE:
            raise RuntimeError("page strings exceed reserved space")

    walker_va = page_va + SLOT_OFFSET + WALKER_OFFSET
    confirm_va = page_va + SLOT_OFFSET + CONFIRM_OFFSET
    village_confirm_va = page_va + SLOT_OFFSET + VILLAGE_CONFIRM_OFFSET
    entry = asm(
        f"""
            push ebp
            mov ebp, esp
            push ebx
            push esi
            push edi
            sub esp, 0x10
            mov dword ptr [ebp - 16], edx
            push 0x{strings['dll']:X}
            call dword ptr [0x4951E0]
            test eax, eax
            jz done
            push 0x{strings['result']:X}
            push eax
            call dword ptr [0x4951DC]
            test eax, eax
            jz done
            mov dword ptr [ebp - 20], eax
            cmp dword ptr [0x51D5F8], {PRICE}
            jb insufficient
            push 0
            push dword ptr [ebp - 16]
            push 0x554190
            call 0x{walker_va:X}
            add esp, 12
            cmp edx, 1
            je invalid
            test eax, eax
            jz no_change
            call 0x{village_confirm_va:X}
            cmp eax, 1
            jne done
            cmp dword ptr [0x51D5F8], {PRICE}
            jb insufficient
            push 0
            push dword ptr [ebp - 16]
            push 0x554190
            call 0x{walker_va:X}
            add esp, 12
            cmp edx, 1
            je invalid
            test eax, eax
            jz no_change
            push -1000000
            mov ecx, 0x51D5F8
            call 0x4237B0
            push 1
            push dword ptr [ebp - 16]
            push 0x554190
            call 0x{walker_va:X}
            add esp, 12
            mov dword ptr [ebp - 24], eax
            push dword ptr [ebp - 24]
            push 1
            call dword ptr [ebp - 20]
            jmp done
        no_change:
            push 0
            push 0
            call dword ptr [ebp - 20]
            jmp done
        insufficient:
            push 0
            push 2
            call dword ptr [ebp - 20]
            jmp done
        invalid:
            push 0
            push 3
            call dword ptr [ebp - 20]
        done:
            add esp, 0x10
            pop edi
            pop esi
            pop ebx
            mov esp, ebp
            pop ebp
            ret
        """,
        entry_va,
    )

    walker = asm(
        f"""
            push ebp
            mov ebp, esp
            push ebx
            push esi
            push edi
            mov esi, dword ptr [ebp + 8]
            xor ebx, ebx
            push dword ptr [ebp + 16]
            push 0
        next:
            cmp ebx, dword ptr [ebp + 12]
            jae walk_done
            cmp byte ptr [esi + 0x1CD4], 0
            je advance
            cmp dword ptr [esi + 0x1C40], 0
            jle advance
            cmp byte ptr [esi + 0x1CEC], 0
            jne advance
            mov edi, 6
            lea edx, [esi + 0x1C5C]
        validate:
            mov eax, dword ptr [edx]
            mov ecx, eax
            and ecx, 0x7FFFFFFF
            jz valid_value
            test eax, 0x80000000
            jne invalid
            cmp ecx, 0x42C80000
            ja invalid
        valid_value:
            add edx, 4
            dec edi
            jne validate
            mov edi, 6
            lea edx, [esi + 0x1C5C]
        change_scan:
            cmp dword ptr [edx], 0x42C80000
            jb changed
            add edx, 4
            dec edi
            jne change_scan
            jmp advance
        changed:
            inc dword ptr [esp]
            cmp dword ptr [esp + 4], 0
            je advance
            xor edi, edi
        skill_loop:
            mov eax, dword ptr [esi + edi*4 + 0x1C5C]
            cmp eax, 0x42C80000
            je skill_next
            push 0x42C80000
            fld dword ptr [esp]
            fsub dword ptr [esi + edi*4 + 0x1C5C]
            fstp dword ptr [esp]
            push edi
            lea ecx, [esi + 0x1C5C]
            call 0x475730
        skill_next:
            inc edi
            cmp edi, 6
            jb skill_loop
        advance:
            add esi, {STRIDE}
            inc ebx
            jmp next
        invalid:
            add esp, 8
            xor eax, eax
            mov edx, 1
            jmp walker_exit
        walk_done:
            mov eax, dword ptr [esp]
            add esp, 8
            xor edx, edx
        walker_exit:
            pop edi
            pop esi
            pop ebx
            mov esp, ebp
            pop ebp
            ret
        """,
        walker_va,
    )

    confirm = build_confirmation(
        confirm_va,
        strings["user32"],
        strings["message_box"],
        strings["caption"],
        strings["individual_confirm"],
    )
    village_confirm = build_confirmation(
        village_confirm_va,
        strings["user32"],
        strings["message_box"],
        strings["caption"],
        strings["village_confirm"],
    )
    individual = build_individual_helper(page_va, strings)
    _put(slot, SLOT_ENTRY_OFFSET, WALKER_OFFSET - SLOT_ENTRY_OFFSET, entry, "entry")
    _put(slot, WALKER_OFFSET, CONFIRM_OFFSET - WALKER_OFFSET, walker, "walker")
    _put(
        slot,
        CONFIRM_OFFSET,
        VILLAGE_CONFIRM_OFFSET - CONFIRM_OFFSET,
        confirm,
        "individual confirmation",
    )
    _put(
        slot,
        VILLAGE_CONFIRM_OFFSET,
        INDIVIDUAL_OFFSET - VILLAGE_CONFIRM_OFFSET,
        village_confirm,
        "village-wide confirmation",
    )
    _put(slot, INDIVIDUAL_OFFSET, SLOT_SIZE - INDIVIDUAL_OFFSET, individual, "individual transaction")
    return bytes(slot), {
        "entry_offset": SLOT_ENTRY_OFFSET,
        "entry_length": len(entry),
        "entry_sha256": sha(entry),
        "walker_offset": WALKER_OFFSET,
        "walker_length": len(walker),
        "walker_sha256": sha(walker),
        "confirmation_offset": CONFIRM_OFFSET,
        "confirmation_length": len(confirm),
        "confirmation_sha256": sha(confirm),
        "village_confirmation_offset": VILLAGE_CONFIRM_OFFSET,
        "village_confirmation_length": len(village_confirm),
        "village_confirmation_sha256": sha(village_confirm),
        "confirmation_string_sha256": {
            "individual_confirm": sha(
                b"Grant Full Mastery to this villager for 100,000 tech points?\r\n"
                b"Press OK to confirm, or Cancel.\0"
            ),
            "village_confirm": sha(
                b"Grant Full Mastery to all eligible villagers for 1,000,000 tech points?\r\n"
                b"Press OK to confirm, or Cancel.\0"
            ),
        },
        "individual_offset": INDIVIDUAL_OFFSET,
        "individual_length": len(individual),
        "individual_sha256": sha(individual),
        "strings": {key: f"0x{value:X}" for key, value in strings.items()},
    }


def build_dispatcher(page_va: int, bound: int) -> bytes:
    slot_va = page_va + SLOT_OFFSET
    entry_va = slot_va + SLOT_ENTRY_OFFSET
    return asm(
        f"""
            push ebp
            push ebx
            push esi
            push edi
            cmp dword ptr [0x{page_va:X}], 0x354D4656
            jne unavailable
            cmp dword ptr [0x{page_va + 8:X}], 1
            jne unavailable
            cmp dword ptr [0x{slot_va:X}], 0x4D465656
            jne unavailable
            cmp dword ptr [0x{slot_va + 8:X}], 1
            jne unavailable
            cmp dword ptr [0x{slot_va + 12:X}], 1
            jne unavailable
            mov edx, {bound}
            call 0x{entry_va:X}
            jmp done
        unavailable:
            mov eax, -1
        done:
            pop edi
            pop esi
            pop ebx
            pop ebp
            ret
        """,
        page_va + 0x40,
    )


def build_page(page_va: int, slot: bytes, dispatcher: bytes) -> bytes:
    page = bytearray(PAGE_SIZE)
    page[0:8] = b"VFM5PG\0\0"
    page[8:12] = (1).to_bytes(4, "little")
    page[12:16] = PAGE_SIZE.to_bytes(4, "little")
    page[16:20] = SLOT_OFFSET.to_bytes(4, "little")
    page[20:24] = SLOT_SIZE.to_bytes(4, "little")
    page[24:28] = (SLOT_OFFSET + SLOT_ENTRY_OFFSET).to_bytes(4, "little")
    page[28:32] = page_va.to_bytes(4, "little")
    if 0x40 + len(dispatcher) > SLOT_OFFSET:
        raise RuntimeError("base dispatcher overlaps command-7 slot")
    page[0x40 : 0x40 + len(dispatcher)] = dispatcher
    page[SLOT_OFFSET : SLOT_OFFSET + SLOT_SIZE] = slot
    cursor = STRINGS_OFFSET
    for value in (
        b"VVFP Origins Icons.dll\0",
        b"ShowVV5FullMasteryResult\0",
        b"user32.dll\0",
        b"MessageBoxA\0",
        b"This upgrade makes permanent changes to your village. Are you sure "
        b"you want to purchase it? Press OK to confirm, or Cancel.\0",
        b"Origins Upgrades\0",
        b"This villager is already fully mastered.\r\nNo tech points have been deducted.\0",
        b"Full Mastery cannot be applied because the selected villager has an out-of-range skill.\r\nNo tech points have been deducted.\0",
        b"You do not have enough tech points.\r\nNo tech points have been deducted.\0",
        b"Full Mastery was canceled.\r\nNo tech points have been deducted.\0",
        b"The selected villager changed or no longer passed the final checks.\r\nNo tech points have been deducted.\0",
        b"Full Mastery could not be verified.\r\nNo tech points have been deducted.\0",
        b"Grant Full Mastery to this villager for 100,000 tech points?\r\nPress OK to confirm, or Cancel.\0",
        b"Full Mastery has been granted to the selected villager.\0",
        b"Grant Full Mastery to all eligible villagers for 1,000,000 tech points?\r\n"
        b"Press OK to confirm, or Cancel.\0",
    ):
        page[cursor : cursor + len(value)] = value
        cursor += len(value)
    return bytes(page)


def section_header(rva: int) -> bytes:
    return (
        b".vv5fm\0\0"
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
        "append_length": PAGE_SIZE,
        "append_bytes": page.hex().upper(),
        "virtual_address": f"0x{layout['page_va']:X}",
        "purpose": "append the certified base-owned VV5 command-7 extension page",
        "header_patches": [
            {
                "offset": "0xFE",
                "before": "0500",
                "after": "0600",
                "purpose": "add the base-owned .vv5fm section",
            },
            {
                "offset": "0x148",
                "before": layout["old_size_of_image"].to_bytes(4, "little").hex().upper(),
                "after": layout["new_size_of_image"].to_bytes(4, "little").hex().upper(),
                "purpose": "extend SizeOfImage for .vv5fm",
            },
            {
                "offset": "0x2B8",
                "before": "00" * 40,
                "after": section_header(layout["page_rva"]).hex().upper(),
                "purpose": "install the guarded .vv5fm RX section header",
            },
        ],
    }


def build_base_payload(active_payload: bytes, page_va: int) -> bytes:
    payload = bytearray(active_payload)
    # D79's native top-left contract uses cached btn_trophies (resource 0x6A,
    # 96x39) for both controls. Constructor arguments are pushed y then x.
    constructors = {
        "Tech": (0x40, 0xC0, bytes.fromhex("68D2020000")),
        "Detail": (0x100, 0x180, bytes.fromhex("68BC020000")),
    }
    for label, (start, end, old_y) in constructors.items():
        ctor = bytearray(payload[start:end])
        replacements = (
            (bytes.fromhex("6A48"), bytes.fromhex("6A6A")),
            (old_y, bytes.fromhex("6802000000")),
            (bytes.fromhex("68B4000000"), bytes.fromhex("6889000000")),
        )
        for before, after in replacements:
            if ctor.count(before) != 1:
                raise RuntimeError(
                    f"VV5 {label} Upgrades geometry guard mismatch: "
                    f"{before.hex().upper()}"
                )
            ctor = ctor.replace(before, after)
        if ctor.count(bytes.fromhex("6A6A")) != 1 or ctor.count(bytes.fromhex("6889000000")) != 1:
            raise RuntimeError(f"VV5 {label} native top-left geometry postcondition failed")
        payload[start:end] = ctor
    dll_offset = payload.find(b"VVFP Origins Icons.dll\0")
    menu_offset = payload.find(b"ShowOriginsUpgradeMenuState\0")
    if dll_offset < 0 or menu_offset < 0:
        raise RuntimeError("base companion strings missing")
    dll_va = PAYLOAD_VA + dll_offset
    menu_va = PAYLOAD_VA + menu_offset
    slot_va = page_va + SLOT_OFFSET
    page_dispatcher_va = page_va + 0x40
    show_dialog = asm(
        f"""
            push 0x{dll_va:X}
            call dword ptr [0x4951E0]
            test eax, eax
            je unavailable
            push 0x{menu_va:X}
            push eax
            call dword ptr [0x4951DC]
            test eax, eax
            je unavailable
            cmp dword ptr [0x{slot_va + 12:X}], 1
            jne no_mastery
            or dword ptr [esp + 8], 0x80000
        no_mastery:
            push dword ptr [esp + 8]
            push dword ptr [esp + 8]
            call eax
            ret 8
        unavailable:
            mov eax, -1
            ret 8
        """,
        PAYLOAD_VA + SHOW_DIALOG_OFFSET,
    )
    tech_menu = bytearray(payload[TECH_MENU_OFFSET : TECH_MENU_OFFSET + TECH_MENU_SIZE])
    village_start = tech_menu.find(bytes.fromhex("83FB0672"))
    legacy_start = tech_menu.find(bytes.fromhex("8B049D"))
    if village_start != 0x11E or legacy_start != 0x15B:
        raise RuntimeError("base command block does not match certified layout")
    menu_loop_va = PAYLOAD_VA + TECH_MENU_OFFSET + 6
    legacy_va = PAYLOAD_VA + TECH_MENU_OFFSET + legacy_start
    replacement = asm(
        f"""
            cmp ebx, 6
            jb 0x{legacy_va:X}
            cmp ebx, 7
            jne 0x{menu_loop_va:X}
            mov ecx, esi
            call 0x{page_dispatcher_va:X}
            jmp 0x{menu_loop_va:X}
        """,
        PAYLOAD_VA + TECH_MENU_OFFSET + village_start,
    )
    if len(replacement) > legacy_start - village_start:
        raise RuntimeError("command-7-only dispatch does not fit base block")
    tech_menu[village_start:legacy_start] = replacement + b"\x90" * (
        legacy_start - village_start - len(replacement)
    )
    if len(show_dialog) > SHOW_DIALOG_SIZE:
        raise RuntimeError(
            f"show dialog exceeds reserved base payload block: {len(show_dialog):#x}"
        )
    payload[SHOW_DIALOG_OFFSET : SHOW_DIALOG_OFFSET + SHOW_DIALOG_SIZE] = (
        show_dialog + b"\0" * (SHOW_DIALOG_SIZE - len(show_dialog))
    )
    payload[TECH_MENU_OFFSET : TECH_MENU_OFFSET + TECH_MENU_SIZE] = tech_menu
    return bytes(payload)


def main() -> None:
    stock = STOCK.read_bytes()
    expected_sha = "92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D"
    if len(stock) != 991_232 or sha(stock) != expected_sha:
        raise RuntimeError("VV5 stock fixture fingerprint mismatch")
    if not COMPANION.is_file():
        raise RuntimeError("build the certified companion DLL first")
    if not PROVENANCE_ASSET.is_file() or sha(PROVENANCE_ASSET.read_bytes()) != PROVENANCE_ASSET_SHA256:
        raise RuntimeError("VV5 btn_trophies provenance asset fingerprint mismatch")

    active = json.loads(ACTIVE_BASE.read_text(encoding="utf-8"))
    payload_patch = next(
        item for item in active["patches"] if int(item["offset"], 0) == PAYLOAD_OFFSET
    )
    active_payload = bytes.fromhex(payload_patch["after"]).ljust(PAYLOAD_SIZE, b"\0")
    noop_slots: dict[str, bytes] = {}
    installed_slots: dict[str, bytes] = {}
    slot_maps: dict[str, object] = {}
    dispatchers: dict[str, bytes] = {}
    pages: dict[str, bytes] = {}
    installed_pages: dict[str, bytes] = {}
    for mode, layout in LAYOUTS.items():
        noop, noop_map = build_slot(layout["page_va"], False)
        installed, installed_map = build_slot(layout["page_va"], True)
        dispatcher = build_dispatcher(layout["page_va"], layout["bound"])
        noop_slots[mode] = noop
        installed_slots[mode] = installed
        dispatchers[mode] = dispatcher
        pages[mode] = build_page(layout["page_va"], noop, dispatcher)
        installed_pages[mode] = build_page(layout["page_va"], installed, dispatcher)
        slot_maps[mode] = {"noop": noop_map, "installed": installed_map}

    stock_payload = build_base_payload(
        active_payload, LAYOUTS["collection_progression"]["page_va"]
    )
    base = deepcopy(active)
    base["id"] = "vv5_enable_origins_exclusive_features_full_mastery_candidate"
    base["name"] = (
        "VV5 Origins Full Mastery Extension Base"
        if bool(json.loads(FEATURE_OUT.read_text(encoding="utf-8")).get("enabled", False))
        else "DISABLED Candidate: VV5 Origins Full Mastery Extension Base"
    )
    base["enabled"] = True
    base["catalog_hidden"] = not bool(
        json.loads(FEATURE_OUT.read_text(encoding="utf-8")).get("enabled", False)
    )
    base["certification_status"] = (
        "C99 independently certified; stock Collection Progression and Immediate Fixed "
        "catalog-enabled; Expanded-256 ON HOLD/fail-closed"
        if not base["catalog_hidden"]
        else "disabled Stage-A candidate awaiting independent emitted-byte certification"
    )
    base["dependencies"] = []
    base["expanded_shr_relocations"]["patches"] = []
    base["companion_files"] = [
        {
            "source": "data/candidates/VVFP VV5 Full Mastery Candidate.dll",
            "destination": "VVFP Origins Icons.dll",
            "sha256": sha(COMPANION.read_bytes()),
        }
    ]
    base["patches"] = [
        item
        for item in base["patches"]
        if int(item["offset"], 0) != VILLAGE_PREFLIGHT_OFFSET
    ]
    cure_item = next(item for item in base["patches"] if int(item["offset"], 0) == CURE_OFFSET)
    cure_bytes = bytes.fromhex(cure_item["after"])
    cure_start = cure_bytes.find(bytes.fromhex("53555152565731C0"))
    if cure_start < 0:
        raise RuntimeError("base Cure-only signature missing")
    cure_jump = asm(
        f"jmp 0x{IMAGE_BASE + CURE_OFFSET + cure_start:X}",
        IMAGE_BASE + CURE_OFFSET,
    )
    cure_item["after"] = (
        cure_jump + b"\x90" * (cure_start - len(cure_jump)) + cure_bytes[cure_start:]
    ).hex().upper()
    cure_item["purpose"] = (
        "retain the byte-identical withdrawn Cure payload behind the EB5F containment "
        "gate; command 5 is unavailable and unreachable"
    )
    payload_item = next(
        item for item in base["patches"] if int(item["offset"], 0) == PAYLOAD_OFFSET
    )
    payload_item["before"] = (b"\0" * PAYLOAD_SIZE).hex().upper()
    payload_item["after"] = stock_payload.hex().upper()
    payload_item["purpose"] = (
        "install the base Origins core with a guarded command-7 no-op extension slot"
    )
    base["ui_geometry_contract"] = {
        "asset": "native cached Images\\btn_trophies.png",
        "asset_sha256": PROVENANCE_ASSET_SHA256,
        "resource_id": "0x6A",
        "native_dimensions": [96, 39],
        "tech": {"local_x": 137, "local_y": 2, "event": 13, "factory": "0x401BD0", "ownership": "0x40C680"},
        "detail": {"local_x": 137, "local_y": 2, "event": 13, "factory": "0x401BD0", "ownership": "0x40C680"},
        "status": (
            "independent metadata recertification GO; stock modes only; Expanded-256 ON HOLD/fail-closed"
            if not base["catalog_hidden"]
            else "disabled pending independent emitted-byte recertification"
        ),
    }
    base["patch_mode_overrides"] = {}
    base["pe_append_transaction"] = {
        "owner": base["id"],
        "section_name": ".vv5fm",
        "append_length": PAGE_SIZE,
        "slot_offset": f"0x{SLOT_OFFSET:X}",
        "slot_length": f"0x{SLOT_SIZE:X}",
        "removal_policy": (
            "dependent slot must equal exact no-op bytes before guarded base restore/truncate"
        ),
        "layouts": {
            mode: append_layout(layout, pages[mode])
            for mode, layout in LAYOUTS.items()
        },
    }

    stock_noop = noop_slots["collection_progression"]
    stock_installed = installed_slots["collection_progression"]
    route_offset = PAYLOAD_OFFSET + 0x766
    route_before = bytes.fromhex("83FB027525")
    route_after = asm(
        f"jmp 0x{LAYOUTS['collection_progression']['page_va'] + SLOT_OFFSET + INDIVIDUAL_OFFSET:X}",
        PAYLOAD_VA + 0x766,
    )
    existing_feature = (
        json.loads(FEATURE_OUT.read_text(encoding="utf-8"))
        if FEATURE_OUT.is_file()
        else {}
    )
    feature_enabled = bool(existing_feature.get("enabled", False))
    feature = {
        "id": "vv5_full_mastery_all_stage_a_candidate",
        "game_id": "vv5",
        "name": (
            "Grant Full Mastery to All Villagers"
            if feature_enabled
            else "DISABLED Candidate: Grant Full Mastery to All Villagers"
        ),
        "catalog_hidden": not feature_enabled,
        "enabled": feature_enabled,
        "certification_status": (
            existing_feature.get("certification_status")
            if feature_enabled
            else (
                "disabled candidate awaiting independent recertification of the VV5 "
                "native btn_trophies resource and exact-100 individual transaction"
            )
        ),
        "dependencies": [base["id"]],
        "description": (
            "Command-7 village-wide and guarded command-1 selected-Believer Full Mastery "
            "candidate using native six-skill Float32 writer sub_475730; commands 6/8 are absent."
        ),
        "companion_files": [],
        "patches": [
            {
                "offset": f"0x{APPEND_OFFSET + SLOT_OFFSET:X}",
                "before": stock_noop.hex().upper(),
                "after": stock_installed.hex().upper(),
                "purpose": "replace only the guarded base-owned no-op slot with command 7",
            },
            {
                "offset": f"0x{route_offset:X}",
                "before": route_before.hex().upper(),
                "after": route_after.hex().upper(),
                "purpose": "intercept command 1 before legacy charge; preserve command 2 preflight and other legacy routes",
            }
        ],
        "patch_mode_overrides": {},
        "transaction_contract": {
            "command": 7,
            "price": PRICE,
            "ownership": None,
            "record_bounds": {"stock": 150},
            "eligibility": [
                "byte +0x1CD4 != 0",
                "signed dword +0x1C40 > 0",
                "byte +0x1CEC == 0 before skill reads",
            ],
            "skills": [
                "+0x1C5C",
                "+0x1C60",
                "+0x1C64",
                "+0x1C68",
                "+0x1C6C",
                "+0x1C70",
            ],
            "target": 100,
            "native_writer": "sub_475730 once for each below-100 Float32 skill",
            "native_evaluator": None,
            "individual_transaction": {
                "route_offset": f"0x{route_offset:X}",
                "route_before": route_before.hex().upper(),
                "price": INDIVIDUAL_PRICE,
                "route_target": "EBX=1 helper; EBX=2 native Running preflight; all others legacy path",
                "target": "selected current active/living non-skeleton Believer",
                "finite_float_range": [0.0, 100.0],
                "native_writer": "0x475730 delta=100-current, once per changed skill",
                "reacquire_same_index": True,
                "postverify": "all six exact 100.0f before 0x4237B0 deduction",
                "no_deduction_text": "No tech points have been deducted.",
            },
        },
        "ui_geometry_contract": {
            "asset": "native cached Images\\btn_trophies.png",
            "asset_sha256": "F39E94CBDF24776631D803D1218EFCCDE555081C9C8C644DD073B75EC7DD2095",
            "resource_id": "0x6A",
            "native_dimensions": [96, 39],
            "tech": {"local_x": 137, "local_y": 2, "event": 13, "factory": "0x401BD0", "ownership": "0x40C680"},
            "detail": {"local_x": 137, "local_y": 2, "event": 13, "factory": "0x401BD0", "ownership": "0x40C680"},
            "status": (
                "independent metadata recertification GO; stock modes only; Expanded-256 ON HOLD/fail-closed"
                if feature_enabled
                else "disabled pending independent emitted-byte recertification"
            ),
        },
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    BASE_OUT.write_text(json.dumps(base, indent=2) + "\n", encoding="utf-8")
    FEATURE_OUT.write_text(json.dumps(feature, indent=2) + "\n", encoding="utf-8")

    sys.path.insert(0, str(ROOT / "src"))
    from vv_fun_patcher import FunPatch, _pe_checksum_layout, load_builds, render_patched_bytes  # noqa: PLC0415

    # Build the VV5 compatibility set from VV5-owned manifests only.  The
    # general catalog loader validates every game's certified map and would
    # couple an isolated VV5 regeneration to unrelated VV3 drift.
    build_manifest = json.loads((ROOT / "data" / "builds.json").read_text(encoding="utf-8"))
    isolated_records = [
        item
        for item in build_manifest.get("fun_patches", [])
        if item.get("game_id") == "vv5" and item.get("enabled", True)
    ]
    for path in (
        ROOT / "data" / "vv5_origins_feature.json",
        ROOT / "data" / "vv5_origins_village_wide_upgrades.json",
    ):
        if path.is_file():
            record = json.loads(path.read_text(encoding="utf-8"))
            if record.get("enabled", True):
                isolated_records.append(record)
    statistics = ROOT / "data" / "statistics_features.json"
    if statistics.is_file():
        isolated_records.extend(
            item
            for item in json.loads(statistics.read_text(encoding="utf-8")).get("features", [])
            if item.get("game_id") == "vv5" and item.get("enabled", True)
        )
    compatible = [
        FunPatch(item)
        for item in isolated_records
        if item.get("id")
        not in {
            "vv5_enable_origins_exclusive_features",
            "vv5_full_mastery_all_stage_a_candidate",
        }
    ]

    build = next(item for item in load_builds() if item.id == "vv5")
    renders: dict[str, object] = {}
    for mode in LAYOUTS:
        baseline, _ = render_patched_bytes(STOCK, build, mode)
        base_render, _ = render_patched_bytes(
            STOCK, build, mode, _fun_patches_override=[FunPatch(base)]
        )
        feature_render, applied = render_patched_bytes(
            STOCK, build, mode, _fun_patches_override=[FunPatch(base), FunPatch(feature)]
        )
        all_render, all_applied = render_patched_bytes(
            STOCK,
            build,
            mode,
            _fun_patches_override=[FunPatch(base), FunPatch(feature), *compatible],
        )
        checksum_offset, _ = _pe_checksum_layout(feature_render)
        renders[mode] = {
            "baseline_sha256": sha(bytes(baseline)),
            "base_only_sha256": sha(bytes(base_render)),
            "base_plus_mastery_sha256": sha(bytes(feature_render)),
            "all_current_compatible_sha256": sha(bytes(all_render)),
            "size": len(feature_render),
            "pe_checksum": f"0x{struct.unpack_from('<I', feature_render, checksum_offset)[0]:08X}",
            "owners": sorted({item["owner"] for item in applied}),
            "all_current_owners": sorted({item["owner"] for item in all_applied}),
        }

    artifact = {
        "acceptance_commit": "48955b5f19da5d4279887a4c1b71250a63ac9ade",
        "candidate_enabled": feature_enabled,
        "catalog_enabled": feature_enabled,
        "catalog_hidden": not feature_enabled,
        "certification_status": (
            "C99 independently certified; stock Collection Progression and Immediate Fixed catalog-enabled; Expanded-256 ON HOLD/fail-closed"
            if feature_enabled
            else "disabled candidate awaiting independent emitted-byte certification"
        ),
        "allowed_modes": ["collection_progression", "immediate_fixed"],
        "expanded_fail_closed": True,
        "source": {"size": len(stock), "sha256": expected_sha},
        "ui_geometry_contract": {
            "asset": "Images\\btn_trophies.png",
            "provenance": "assets/candidates/vv5_full_mastery/provenance/btn_trophies.png",
            "asset_sha256": "F39E94CBDF24776631D803D1218EFCCDE555081C9C8C644DD073B75EC7DD2095",
            "resource_id": "0x6A",
            "native_dimensions": [96, 39],
            "tech": {"local_x": 137, "local_y": 2, "event": 13, "factory": "0x401BD0", "ownership": "0x40C680"},
            "detail": {"local_x": 137, "local_y": 2, "event": 13, "factory": "0x401BD0", "ownership": "0x40C680"},
        },
        "base_manifest_sha256": sha(BASE_OUT.read_bytes()),
        "feature_manifest_sha256": sha(FEATURE_OUT.read_bytes()),
        "base_stock_payload_sha256": sha(stock_payload),
        "companion": {
            "path": "data/candidates/VVFP VV5 Full Mastery Candidate.dll",
            "size": COMPANION.stat().st_size,
            "sha256": sha(COMPANION.read_bytes()),
            "exports": export_map(COMPANION.read_bytes()),
            "required_result": "ShowVV5FullMasteryResult stdcall(status,changed), ret 8",
        },
        "slot_layout": {
            "offset": f"0x{SLOT_OFFSET:X}",
            "length": f"0x{SLOT_SIZE:X}",
            "entry_offset": f"0x{SLOT_ENTRY_OFFSET:X}",
            "walker_offset": f"0x{WALKER_OFFSET:X}",
            "confirmation_offset": f"0x{CONFIRM_OFFSET:X}",
            "village_confirmation_offset": f"0x{VILLAGE_CONFIRM_OFFSET:X}",
        },
        "confirmation_contract": {
            "individual_routine_sha256": "234E2D9320A75D6B95DED0A682F13087294AE5E48F126DF30269C6F37653C18F",
            "village_routine_sha256": "2C392F952854EB485091199AC96AAC0B1C5683B7061D9267650411868926D763",
            "individual_string_sha256": "60C9A875AFC93174041B78B3A185B4E1BAE468404F20C3AFC1CF1F127802FD3C",
            "village_string_sha256": "56BC07733ED0F93F211BA0D1887502F8A45E03A4187B8C17067F32FF87117D46",
            "individual_price": 100000,
            "village_price": 1000000,
        },
        "layouts": {
            mode: {
                **layout,
                "noop_slot_sha256": sha(noop_slots[mode]),
                "installed_slot_sha256": sha(installed_slots[mode]),
                "dispatcher_sha256": sha(dispatchers[mode]),
                "base_page_sha256": sha(pages[mode]),
                "installed_page_sha256": sha(installed_pages[mode]),
                "slot_map": slot_maps[mode],
            }
            for mode, layout in LAYOUTS.items()
        },
        "references": {
            "absolute": [
                "0x51D5F8 unsigned Technology Points",
                "0x4951E0 LoadLibraryA IAT",
                "0x4951DC GetProcAddress IAT",
                "0x475730 native six-skill Float32 writer",
                "0x4237B0 native Technology Points writer",
                "0x554190 fixed current-village record base",
            ],
            "rel32": [
                "base Tech menu -> mode-specific page dispatcher",
                "dispatcher -> mode-specific slot entry",
                "entry -> walker/village confirmation",
                "individual helper -> individual confirmation",
                "walker -> 0x475730",
            ],
            "base_relocations": [],
        },
        "runtime_freeze": isolated_runtime_freeze(
            game_id="vv5", map_path=MAP_OUT, data_root=ROOT / "data"
        ),
        "rendered_candidates": {
            **renders,
            **{
                mode: {"rejected": True, "reason": "Expanded-256 fail-closed"}
                for mode in EXPANDED_MODES
            },
        },
    }
    MAP_OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    DOC_OUT.write_text(
        (
            "# VV5 Full Mastery certified playtest feature\n\n"
            if feature_enabled
            else "# VV5 Full Mastery native top-left geometry corrective candidate\n\n"
        )
        + "Generated from acceptance contract "
        "`48955b5f19da5d4279887a4c1b71250a63ac9ade`. "
        + (
            "C99 independently certified the emitted bytes and C101 enables this "
            "candidate only for stock Collection Progression and Immediate Fixed. "
            "Expanded-256 remains fail-closed; Cure command 5 remains withdrawn and "
            "unreachable.\n\n"
            if feature_enabled
            else "The corrected constructor and Full Mastery paths passed the M2 live "
            "test, but the Upgrades controls require the proven native top-left layout. "
            "This disabled candidate uses cached `Images\\btn_trophies.png`, resource "
            "0x6A (96x39), at local (137,2) for both Tech and Detail, with event 13, "
            "sub_401BD0, and existing 0x40C680 ownership. It remains catalog-hidden "
            "pending independent emitted-byte recertification.\n\n"
        )
        + f"- Companion SHA-256: `{artifact['companion']['sha256']}`\n"
        f"- Physical provenance asset `assets/candidates/vv5_full_mastery/provenance/btn_trophies.png` SHA-256: `{PROVENANCE_ASSET_SHA256}`\n"
        f"- Stock installed slot SHA-256: `{artifact['layouts']['collection_progression']['installed_slot_sha256']}`\n"
        f"- Stock installed `.vv5fm` page SHA-256: `{artifact['layouts']['collection_progression']['installed_page_sha256']}` (required in both stock modes).\n"
        f"- Collection Progression render SHA-256: `{renders['collection_progression']['base_plus_mastery_sha256']}`\n"
        f"- Immediate Fixed render SHA-256: `{renders['immediate_fixed']['base_plus_mastery_sha256']}`\n"
        "- Expanded-256 render: rejected before artifact output (fail-closed).\n\n"
        "The loader requires the exact acceptance commit above before any output is\n"
        "created. It also requires the physical provenance asset hash and the complete\n"
        "native UI contract: resource `0x6A`, dimensions `96x39`, Tech and Detail local\n"
        "position `(137,2)`, event `13`, factory `0x401BD0`, and ownership `0x40C680`.\n\n"
        "The feature exposes command 7 only inside its certified base dependency. "
        "The candidate-only Detail command-1 route performs complete selected-current "
        "Believer dry-run/reacquisition/funds checks, calls native writer 0x475730 "
        "with 100-current deltas, verifies six exact 100.0f values, then deducts "
        "once through 0x4237B0; failures use 'No tech points have been deducted.'. "
        "Commands 6/8, village-wide Running/Age bytes, direct skill stores, ownership, "
        "Remove, and save-format changes are absent. The command shim routes EBX=1 to "
        "the individual helper, EBX=2 to the native Running preflight, and all other "
        "values to the legacy path. The individual confirmation uses the exact "
        "100,000-point confirmation string, and recheck reports a changed villager or "
        "failed final checks with no deduction. Expanded-256 remains on hold and is "
        "rejected before output. The village-wide command-7 route uses a separate "
        "confirmation routine and the exact 1,000,000-point text; the individual "
        "confirmation routine and string remain distinct.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
