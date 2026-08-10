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
RUNNING_OUT = OUT_DIR / "vv5_individual_running_candidate.json"
RUNNING_MAP_OUT = OUT_DIR / "vv5_individual_running_candidate_map.json"
RUNNING_DOC_OUT = ROOT / "docs" / "vv5-individual-running-candidate.md"
DOC_OUT = ROOT / "docs" / "vv5-full-mastery-stage-a-candidate.md"
COMPANION = OUT_DIR / "VVFP VV5 Full Mastery Candidate.dll"
CURE_PROJECTION = OUT_DIR / "VVFP VV5 Cure Containment Projection.dll"
COMPANION_PARENT_SHA256 = "29927CECB448B64944E18E2BA11893DC84C91B39241FBB2549FC2A464E0BE2ED"
CURE_PROJECTION_SHA256 = "A1C55063B548F195B9ECDA492E1799D35EBA5437862353D96BE780D9FCC2E1C8"
ACTIVE_BASE_SHA256 = "F9643E2B7D115B6ECDDD4D8AD4BFFC73F2FF6937995E40E991041B6AF6463D44"
ACTIVE_BASE_SIZE = 53747
PROVENANCE_ASSET = ROOT / "assets" / "candidates" / "vv5_full_mastery" / "provenance" / "btn_trophies.png"
PROVENANCE_ASSET_SHA256 = "F39E94CBDF24776631D803D1218EFCCDE555081C9C8C644DD073B75EC7DD2095"

# The repository contains an older namespace-only Keystone wheel alongside the
# pinned runtime wheel.  Put the runtime first so the bundled native binding is
# the one imported under the approved test protocol (the legacy directory is
# retained only as a fallback for older developer environments).
sys.path.insert(0, str(ROOT / ".tools" / "keystone-runtime"))
sys.path.insert(1, str(ROOT / ".tools" / "keystone"))
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
# The two stock call sites are five-byte rel32 calls.  They share one
# candidate-owned wrapper: the Tech entry at 0x7B2B40 loads its target and
# jumps to the common body at 0x7B2B4C; the Detail entry at 0x7B2B47 loads its
# target and falls through to that same body.  The bounded region is an
# existing zero gap in the certified VV5 .shr payload.
FULLSCREEN_TECH_OFFSET = 0xB40
FULLSCREEN_DETAIL_OFFSET = 0xB47
FULLSCREEN_COMMON_OFFSET = 0xB4C
FULLSCREEN_STRING_OFFSET = 0xA5A
FULLSCREEN_STRING = b"SDL2.dll\0SDL_GetWindowFlags\0"
SDL_GET_WINDOW_FLAGS_IAT = 0x4951DC
SDL_GET_MODULE_HANDLE_IAT = 0x4951D8
NATIVE_FULLSCREEN_LEAVE_VA = 0x40A270
NATIVE_FULLSCREEN_ENTER_VA = 0x40A280
NATIVE_FULLSCREEN_GETTER_VA = 0x4080C0
NATIVE_FULLSCREEN_OUTER_GLOBAL_VA = 0x4DB0E8
NATIVE_FULLSCREEN_TRANSITION_VA = 0x404700
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
# Running is appended to the certified Full Mastery page.  Keep the entire
# Full Mastery slot/string region byte-identical and place Running after it.
RUNNING_CONFIRM_OFFSET = 0x15D4
RUNNING_OFFSET = 0x1620
RUNNING_STRINGS_OFFSET = 0x1D80
RUNNING_PAGE_SIZE = PAGE_SIZE
# Individual Grant Running is an isolated extension layered over the
# already-composed Full Mastery parent.  Keep it out of the certified
# .vv5fm page so the enabled feature's bytes remain byte-identical.
RUNNING_APPEND_OFFSET = 0xF4000
RUNNING_PAGE_RVA = 0x3CB000
RUNNING_PAGE_VA = 0x7CB000
RUNNING_DISPATCHER_OFFSET = 0x20
RUNNING_PARENT_HOOK_BEFORE = "E995750100"
RUNNING_HOOK_AFTER = "E9B5880100"
RUNNING_PARENT_HOOK_OFFSET = 0xDB766
PRICE = 1_000_000
INDIVIDUAL_PRICE = 100_000
STRIDE = 0x2F44

RUNNING_STRING_VALUES = (
    ("running_confirm", b"Grant Running to this villager for 40,000 tech points?\r\nPress OK to confirm, or Cancel.\0"),
    ("running_success", b"Running was granted.\0"),
    ("running_already", b"This villager already likes Running.\r\nNo tech points have been deducted.\0"),
    ("running_no_slot", b"This villager has no empty Like slot.\r\nNo tech points have been deducted.\0"),
    ("running_cancel", b"Grant Running was canceled.\r\nNo tech points have been deducted.\0"),
    ("running_recheck", b"The selected villager changed during confirmation.\r\nNo tech points have been deducted.\0"),
    ("running_write_failed", b"Running could not be verified; a native change may remain.\r\nNo tech points have been deducted.\0"),
    ("running_invalid", b"No valid living villager is selected.\r\nNo tech points have been deducted.\0"),
    ("running_insufficient", b"Not enough tech points.\r\nNo tech points have been deducted.\0"),
)


def running_strings_blob() -> bytes:
    """Return the one canonical NUL-terminated VV5 Running string blob."""
    return b"".join(value for _, value in RUNNING_STRING_VALUES)

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


def build_fullscreen_wrapper(common_va: int, sdl_string_va: int) -> bytes:
    """Build the native-state-synchronised VV5 modal wrapper.

    Entry stubs place the selected menu target in EAX and enter this common
    body.  The body receives the original screen object in ECX, preserves all
    non-volatiles, resolves only SDL_GetWindowFlags through the existing
    GetModuleHandleA/GetProcAddress IATs, and brackets the complete blocking
    Origins interaction with the game's native leave/enter transitions.  The
    menu exports are plain-return functions taking ECX only; this wrapper is
    therefore also a plain ``ret`` and never consumes handler arguments.
    """
    return asm(
        f"""
            push ebp
            mov ebp, esp
            push ebx
            push esi
            push edi
            sub esp, 0x30
            mov dword ptr [ebp-0x10], eax
            mov dword ptr [ebp-0x14], ecx
            test ecx, ecx
            jz fail
            mov byte ptr [ebp-0x30], 0
            call reacquire
            test eax, eax
            jz fail
            mov dword ptr [ebp-0x18], esi
            mov dword ptr [ebp-0x1C], edi
            mov dword ptr [ebp-0x20], eax
            movzx ebx, byte ptr [edi+0x1E]
            mov dword ptr [ebp-0x24], ebx
            push 0x{sdl_string_va:X}
            call dword ptr [0x{SDL_GET_MODULE_HANDLE_IAT:X}]
            test eax, eax
            jz fail
            push 0x{sdl_string_va + len(b"SDL2.dll") + 1:X}
            push eax
            call dword ptr [0x{SDL_GET_WINDOW_FLAGS_IAT:X}]
            test eax, eax
            jz fail
            mov dword ptr [ebp-0x28], eax
            push dword ptr [ebp-0x20]
            call dword ptr [ebp-0x28]
            add esp, 4
            mov edx, eax
            and edx, 0x1001
            cmp edx, 0
            je windowed
            cmp edx, 0x1001
            je fullscreen
            jmp fail
        windowed:
            cmp dword ptr [ebp-0x24], 1
            jne fail
            jmp invoke_menu
        fullscreen:
            cmp dword ptr [ebp-0x24], 0
            jne fail
            mov ecx, esi
            call 0x{NATIVE_FULLSCREEN_LEAVE_VA:X}
            mov dword ptr [ebp-0x30], 1
            call reacquire
            cmp esi, dword ptr [ebp-0x18]
            jne post_leave_failed
            cmp edi, dword ptr [ebp-0x1C]
            jne post_leave_failed
            cmp eax, dword ptr [ebp-0x20]
            jne post_leave_failed
            cmp byte ptr [edi+0x1E], 1
            jne post_leave_failed
            push dword ptr [ebp-0x20]
            call dword ptr [ebp-0x28]
            add esp, 4
            mov edx, eax
            and edx, 0x1001
            cmp edx, 0
            jne post_leave_failed
            jmp invoke_menu
        invoke_menu:
            mov ecx, dword ptr [ebp-0x14]
            call dword ptr [ebp-0x10]
            mov dword ptr [ebp-0x2C], eax
            cmp dword ptr [ebp-0x30], 0
            je windowed_done
        restore_start:
            call reacquire
            cmp esi, dword ptr [ebp-0x18]
            jne restore_failed
            cmp edi, dword ptr [ebp-0x1C]
            jne restore_failed
            cmp eax, dword ptr [ebp-0x20]
            jne restore_failed
            mov ecx, esi
            call 0x{NATIVE_FULLSCREEN_ENTER_VA:X}
            call 0x{NATIVE_FULLSCREEN_GETTER_VA:X}
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
            mov edx, eax
            and edx, 0x1001
            cmp byte ptr [edi+0x1E], 0
            je restored_fullscreen
            cmp byte ptr [edi+0x1E], 1
            jne restore_failed
            cmp edx, 0
            jne restore_failed
            xor eax, eax
            jmp done
        restored_fullscreen:
            cmp edx, 0x1001
            jne restore_failed
            mov eax, dword ptr [ebp-0x2C]
            jmp done
        windowed_done:
            mov eax, dword ptr [ebp-0x2C]
            jmp done
        reacquire:
            mov esi, dword ptr [0x{NATIVE_FULLSCREEN_OUTER_GLOBAL_VA:X}]
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
        post_leave_failed:
            xor eax, eax
            mov dword ptr [ebp-0x2C], eax
            jmp restore_start
        restore_failed:
            xor eax, eax
            jmp done
        fail:
            xor eax, eax
        done:
            add esp, 0x30
            pop edi
            pop esi
            pop ebx
            pop ebp
            ret
        """,
        common_va,
    )


def build_fullscreen_entry(entry_va: int, target_va: int, common_va: int, jump: bool) -> bytes:
    """Build the compact target-selection stubs at the D249 offsets."""
    source = f"mov eax, 0x{target_va:X}"
    if jump:
        source += f"; jmp 0x{common_va:X}"
    return asm(source, entry_va)


def _vv5_skip_resource_var(blob: bytes, cursor: int) -> int:
    if cursor + 2 > len(blob):
        raise RuntimeError("VV5 dialog variable is truncated")
    first = int.from_bytes(blob[cursor : cursor + 2], "little")
    if first == 0:
        return cursor + 2
    if first == 0xFFFF:
        if cursor + 4 > len(blob):
            raise RuntimeError("VV5 dialog ordinal is truncated")
        return cursor + 4
    cursor += 2
    while cursor + 2 <= len(blob):
        if blob[cursor : cursor + 2] == b"\0\0":
            return cursor + 2
        cursor += 2
    raise RuntimeError("VV5 dialog UTF-16 value is unterminated")


def _vv5_dialog_item_spans(blob: bytes, expected_count: int) -> list[tuple[int, int, str | None]]:
    """Strictly parse one VV5 DIALOGEX leaf and return item spans/titles."""
    if len(blob) < 26 or blob[0:2] != b"\x01\0" or blob[2:4] != b"\xff\xff":
        raise RuntimeError("VV5 target is not DIALOGEX")
    count = int.from_bytes(blob[16:18], "little")
    if count != expected_count:
        raise RuntimeError(f"VV5 DIALOGEX count {count} != {expected_count}")
    cursor = 26
    cursor = _vv5_skip_resource_var(blob, cursor)  # menu
    cursor = _vv5_skip_resource_var(blob, cursor)  # class
    cursor = _vv5_skip_resource_var(blob, cursor)  # caption
    if cursor + 6 > len(blob):
        raise RuntimeError("VV5 DIALOGEX font tuple is truncated")
    cursor += 6
    cursor = _vv5_skip_resource_var(blob, cursor)  # typeface
    spans: list[tuple[int, int, str | None]] = []
    for _ in range(count):
        cursor = (cursor + 3) & ~3
        start = cursor
        if cursor + 24 > len(blob):
            raise RuntimeError("VV5 DIALOGEX item header is truncated")
        cursor += 24
        cursor = _vv5_skip_resource_var(blob, cursor)  # class
        title_start = cursor
        title_end = _vv5_skip_resource_var(blob, cursor)
        raw_title = blob[title_start:title_end]
        title = None
        if raw_title[:2] not in (b"\0\0", b"\xff\xff"):
            title = raw_title[:-2].decode("utf-16le")
        if title_end + 2 > len(blob):
            raise RuntimeError("VV5 DIALOGEX creation length is truncated")
        extra_words = int.from_bytes(blob[title_end : title_end + 2], "little")
        cursor = title_end + 2 + extra_words * 2
        end = (cursor + 3) & ~3
        if end > len(blob):
            raise RuntimeError("VV5 DIALOGEX item data is truncated")
        spans.append((start, end, title))
        cursor = end
    if cursor > len(blob):
        raise RuntimeError("VV5 DIALOGEX end escapes resource leaf")
    return spans


def strip_vv5_cure_rows(base: bytes) -> bytes:
    """Structurally remove the five-item legacy Cure row from dialogs 201/203.

    The leaf allocation is retained and zero-padded after the compacted item
    list so no unrelated resource, PE section, export, or non-resource byte is
    moved. Dialog 202 is parsed and asserted byte-identical. This function is
    intentionally separate from the frozen C99 companion; callers must hash
    and recertify its returned bytes before installing them.
    """
    if len(base) != 298496:
        raise RuntimeError("VV5 companion size preimage mismatch")
    output = bytearray(base)
    leaves = ((0x466C0, 0x47070, 46), (0x47070, 0x474F0, 21), (0x474F0, 0x47C88, 36))
    original_202 = bytes(base[0x47070:0x474F0])
    for raw, end, count in leaves:
        blob = bytes(base[raw:end])
        spans = _vv5_dialog_item_spans(blob, count)
        if count == 21:
            if bytes(output[raw:end]) != original_202:
                raise RuntimeError("VV5 dialog 202 changed unexpectedly")
            continue
        cure = [index for index, (_, _, title) in enumerate(spans) if title == "Cure all Villagers"]
        if cure != [27]:
            raise RuntimeError("VV5 Cure row structure is not the certified five-item row")
        compact = blob[: spans[25][0]] + blob[spans[30][0] :]
        if len(compact) > len(blob):
            raise RuntimeError("VV5 Cure row compaction overflow")
        compact += b"\0" * (len(blob) - len(compact))
        compact = bytearray(compact)
        compact[16:18] = (count - 5).to_bytes(2, "little")
        after = _vv5_dialog_item_spans(bytes(compact), count - 5)
        if any(title == "Cure all Villagers" for _, _, title in after):
            raise RuntimeError("VV5 Cure row remains after structural removal")
        output[raw:end] = compact
    return bytes(output)


def build_cure_projection() -> bytes:
    """Return the deterministic resource-only Cure containment projection.

    The certified C99 companion remains the immutable Full Mastery parent. The
    projection is a separate candidate-evidence binary used only to prove the
    structural 201/203 row removal and 202 byte identity; it is never treated
    as the parent DLL and never replaces the frozen C99 companion in-place.
    """
    parent = COMPANION.read_bytes()
    if len(parent) != 298496 or sha(parent) != COMPANION_PARENT_SHA256:
        raise RuntimeError("VV5 C99 companion parent is missing or hash-mismatched")
    projection = strip_vv5_cure_rows(parent)
    if len(projection) != len(parent):
        raise RuntimeError("VV5 Cure projection changed companion size")
    if sha(projection) != CURE_PROJECTION_SHA256:
        raise RuntimeError("VV5 Cure projection hash is not the deterministic candidate identity")
    return projection


def build_individual_helper(page_va: int, strings: dict[str, int], running_va: int | None = None) -> bytes:
    """Candidate-only command-1 transaction; native writer, no raw stores."""
    va = page_va + SLOT_OFFSET + INDIVIDUAL_OFFSET
    running_target = running_va if running_va is not None else 0x7B276B
    return asm(f"""
        cmp ebx, 1
        je individual_body
        cmp ebx, 2
        je 0x{running_target:X}
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


def build_running_helper(page_va: int, strings: dict[str, int]) -> bytes:
    """Emit the revised Like/Dislike-safe command-2 transaction."""
    va = page_va + RUNNING_OFFSET
    return asm(f"""
        push ebp
        mov ebp, esp
        push ebx
        push esi
        push edi
        # Locals: saved ESI -10, index -14, record -18, first empty -1C,
        # Like snapshots -28/-24/-20, Dislike snapshots -34/-30/-2C,
        # has_like -38, has_dislike -3C, MessageBox/result preflight -40.
        sub esp, 0x48
        mov dword ptr [ebp-0x10], esi
        mov dword ptr [ebp-0x1C], -1
        mov dword ptr [ebp-0x38], 0
        mov dword ptr [ebp-0x3C], 0
        mov dword ptr [ebp-0x40], 0
        # Mutation mask: bit 0 = inserted Like; bits 1..3 = cleared Dislikes.
        mov dword ptr [ebp-0x44], 0
        push 0x{strings['user32']:X}
        call dword ptr [0x4951E0]
        test eax, eax
        jz done
        push 0x{strings['message_box']:X}
        push eax
        call dword ptr [0x4951DC]
        test eax, eax
        jz done
        mov dword ptr [ebp-0x40], eax
        call 0x425950
        test eax, eax
        jz fail
        mov eax, dword ptr [eax+0x17E24]
        cmp eax, 0x96
        jae fail
        mov dword ptr [ebp-0x14], eax
        mov ecx, 0x554148
        push eax
        call 0x471840
        test eax, eax
        jz fail
        mov ecx, 0x554148
        push dword ptr [ebp-0x14]
        call 0x46F950
        test eax, eax
        jz fail
        mov dword ptr [ebp-0x18], eax
        mov esi, eax
        cmp byte ptr [esi+0x1CD4], 0
        je fail
        cmp dword ptr [esi+0x1C40], 0
        jle fail
        cmp byte ptr [esi+0x1CE1], 0
        jne fail
        cmp byte ptr [esi+0x1CEC], 0
        jne fail
        xor edi, edi
    like_scan:
        cmp edi, 3
        jae dislike_scan_start
        mov eax, dword ptr [esi+edi*4+0x1F5C]
        mov dword ptr [ebp+edi*4-0x28], eax
        cmp eax, 38
        jne like_not_running
        mov dword ptr [ebp-0x38], 1
    like_not_running:
        cmp eax, -1
        jne like_next
        cmp dword ptr [ebp-0x1C], -1
        jne like_next
        mov dword ptr [ebp-0x1C], edi
    like_next:
        inc edi
        jmp like_scan
    dislike_scan_start:
        xor edi, edi
    dislike_scan:
        cmp edi, 3
        jae scanned
        mov eax, dword ptr [esi+edi*4+0x1F68]
        mov dword ptr [ebp+edi*4-0x34], eax
        cmp eax, 38
        jne dislike_next
        mov dword ptr [ebp-0x3C], 1
    dislike_next:
        inc edi
        jmp dislike_scan
    scanned:
        cmp dword ptr [ebp-0x38], 1
        je has_running_like
        cmp dword ptr [ebp-0x1C], -1
        je no_slot
        jmp needs_confirmation
    has_running_like:
        cmp dword ptr [ebp-0x3C], 1
        jne no_change
    needs_confirmation:
        cmp dword ptr [0x51D5F8], 40000
        jb funds
        call 0x{page_va + RUNNING_CONFIRM_OFFSET:X}
        test eax, eax
        jz cancel
        call 0x425950
        test eax, eax
        jz stale
        mov eax, dword ptr [eax+0x17E24]
        cmp eax, dword ptr [ebp-0x14]
        jne stale
        mov ecx, 0x554148
        push eax
        call 0x471840
        test eax, eax
        jz stale
        mov ecx, 0x554148
        push dword ptr [ebp-0x14]
        call 0x46F950
        test eax, eax
        jz stale
        cmp eax, dword ptr [ebp-0x18]
        jne stale
        mov esi, eax
        cmp byte ptr [esi+0x1CD4], 0
        je stale
        cmp dword ptr [esi+0x1C40], 0
        jle stale
        cmp byte ptr [esi+0x1CE1], 0
        jne stale
        cmp byte ptr [esi+0x1CEC], 0
        jne stale
        mov eax, dword ptr [esi+0x1F5C]
        cmp eax, dword ptr [ebp-0x28]
        jne stale
        mov eax, dword ptr [esi+0x1F60]
        cmp eax, dword ptr [ebp-0x24]
        jne stale
        mov eax, dword ptr [esi+0x1F64]
        cmp eax, dword ptr [ebp-0x20]
        jne stale
        mov eax, dword ptr [esi+0x1F68]
        cmp eax, dword ptr [ebp-0x34]
        jne stale
        mov eax, dword ptr [esi+0x1F6C]
        cmp eax, dword ptr [ebp-0x30]
        jne stale
        mov eax, dword ptr [esi+0x1F70]
        cmp eax, dword ptr [ebp-0x2C]
        jne stale
        cmp dword ptr [0x51D5F8], 40000
        jb funds
        cmp dword ptr [ebp-0x38], 1
        je clear_dislikes
        mov edi, dword ptr [ebp-0x1C]
        # Reacquire identity/eligibility immediately before the Like store.
        call 0x425950
        test eax, eax
        jz write_failed
        mov eax, dword ptr [eax+0x17E24]
        cmp eax, dword ptr [ebp-0x14]
        jne write_failed
        mov ecx, 0x554148
        push eax
        call 0x471840
        test eax, eax
        jz write_failed
        mov ecx, 0x554148
        push dword ptr [ebp-0x14]
        call 0x46F950
        test eax, eax
        jz write_failed
        cmp eax, dword ptr [ebp-0x18]
        jne write_failed
        mov esi, eax
        cmp byte ptr [esi+0x1CD4], 0
        je write_failed
        cmp dword ptr [esi+0x1C40], 0
        jle write_failed
        cmp byte ptr [esi+0x1CE1], 0
        jne write_failed
        cmp byte ptr [esi+0x1CEC], 0
        jne write_failed
        cmp dword ptr [esi+edi*4+0x1F5C], -1
        jne stale
        mov dword ptr [esi+edi*4+0x1F5C], 38
        or dword ptr [ebp-0x44], 1
        cmp dword ptr [esi+edi*4+0x1F5C], 38
        jne write_failed
    clear_dislikes:
        xor edi, edi
    clear_dislike_loop:
        cmp edi, 3
        jae commit_running
        # Reacquire identity/eligibility before every Dislike mutation.
        call 0x425950
        test eax, eax
        jz write_failed
        mov eax, dword ptr [eax+0x17E24]
        cmp eax, dword ptr [ebp-0x14]
        jne write_failed
        mov ecx, 0x554148
        push eax
        call 0x471840
        test eax, eax
        jz write_failed
        mov ecx, 0x554148
        push dword ptr [ebp-0x14]
        call 0x46F950
        test eax, eax
        jz write_failed
        cmp eax, dword ptr [ebp-0x18]
        jne write_failed
        mov esi, eax
        cmp byte ptr [esi+0x1CD4], 0
        je write_failed
        cmp dword ptr [esi+0x1C40], 0
        jle write_failed
        cmp byte ptr [esi+0x1CE1], 0
        jne write_failed
        cmp byte ptr [esi+0x1CEC], 0
        jne write_failed
        cmp dword ptr [esi+edi*4+0x1F68], 38
        jne clear_dislike_next
        # Claim ownership before the native store/readback so a failed
        # readback still leaves a precise candidate-written bit for guarded
        # rollback.  Dislike slot i maps to bit i+1 (bits 1..3).
        mov eax, 1
        mov ecx, edi
        inc ecx
        shl eax, cl
        or dword ptr [ebp-0x44], eax
        mov dword ptr [esi+edi*4+0x1F68], -1
        cmp dword ptr [esi+edi*4+0x1F68], -1
        jne write_failed
    clear_dislike_next:
        inc edi
        jmp clear_dislike_loop
    commit_running:
        # Complete post-write identity/eligibility and six-slot verification
        # gates the sole native deduction.  A failure reports partial native
        # effects and never charges.
        call 0x425950
        test eax, eax
        jz write_failed_result
        mov eax, dword ptr [eax+0x17E24]
        cmp eax, dword ptr [ebp-0x14]
        jne write_failed_result
        mov ecx, 0x554148
        push eax
        call 0x46F950
        test eax, eax
        jz write_failed_result
        cmp eax, dword ptr [ebp-0x18]
        jne write_failed_result
        mov esi, eax
        cmp byte ptr [esi+0x1CD4], 0
        je write_failed_result
        cmp dword ptr [esi+0x1C40], 0
        jle write_failed_result
        cmp byte ptr [esi+0x1CE1], 0
        jne write_failed_result
        cmp byte ptr [esi+0x1CEC], 0
        jne write_failed_result
        cmp dword ptr [ebp-0x38], 1
        je postverify_like_preserved
        mov edi, dword ptr [ebp-0x1C]
        cmp dword ptr [esi+edi*4+0x1F5C], 38
        jne write_failed_result
        cmp edi, 0
        je postverify_like_1
        mov eax, dword ptr [esi+0x1F5C]
        cmp eax, dword ptr [ebp-0x28]
        jne write_failed_result
    postverify_like_1:
        cmp edi, 1
        je postverify_like_2
        mov eax, dword ptr [esi+0x1F60]
        cmp eax, dword ptr [ebp-0x24]
        jne write_failed_result
    postverify_like_2:
        cmp edi, 2
        je postverify_dislikes
        mov eax, dword ptr [esi+0x1F64]
        cmp eax, dword ptr [ebp-0x20]
        jne write_failed_result
        jmp postverify_dislikes
    postverify_like_preserved:
        mov eax, dword ptr [esi+0x1F5C]
        cmp eax, dword ptr [ebp-0x28]
        jne write_failed_result
        mov eax, dword ptr [esi+0x1F60]
        cmp eax, dword ptr [ebp-0x24]
        jne write_failed_result
        mov eax, dword ptr [esi+0x1F64]
        cmp eax, dword ptr [ebp-0x20]
    postverify_dislikes:
        jne write_failed_result
        xor edi, edi
    postverify_dislike_loop:
        cmp edi, 3
        jae postverify_funds
        mov eax, dword ptr [ebp+edi*4-0x34]
        cmp eax, 38
        jne postverify_dislike_unchanged
        cmp dword ptr [esi+edi*4+0x1F68], -1
        jne write_failed_result
        jmp postverify_dislike_next
    postverify_dislike_unchanged:
        cmp dword ptr [esi+edi*4+0x1F68], eax
        jne write_failed_result
    postverify_dislike_next:
        inc edi
        jmp postverify_dislike_loop
    postverify_funds:
        cmp dword ptr [0x51D5F8], 40000
        jb funds
        push -40000
        mov ecx, 0x51D5F8
        call 0x4237B0
        push 0x{strings['running_success']:X}
        push 0x{strings['caption']:X}
        call 0x7B2210
        jmp done
    no_change:
        push 0x{strings['running_already']:X}
        jmp result
    no_slot:
        push 0x{strings['running_no_slot']:X}
        jmp result
    funds:
        push 0x{strings['running_insufficient']:X}
        jmp result
    cancel:
        push 0x{strings['running_cancel']:X}
        jmp result
    stale:
        push 0x{strings['running_recheck']:X}
        jmp result
    write_failed:
        # Restore only candidate-written values after identity and predicate recheck.
        call 0x425950
        test eax, eax
        jz write_failed_result
        mov eax, dword ptr [eax+0x17E24]
        cmp eax, dword ptr [ebp-0x14]
        jne write_failed_result
        mov ecx, 0x554148
        push eax
        call 0x46F950
        test eax, eax
        jz write_failed_result
        cmp eax, dword ptr [ebp-0x18]
        jne write_failed_result
        mov esi, eax
        cmp byte ptr [esi+0x1CD4], 0
        je write_failed_result
        cmp dword ptr [esi+0x1C40], 0
        jle write_failed_result
        cmp byte ptr [esi+0x1CE1], 0
        jne write_failed_result
        cmp byte ptr [esi+0x1CEC], 0
        jne write_failed_result
        test dword ptr [ebp-0x44], 1
        jz rollback_dislikes
        mov edi, dword ptr [ebp-0x1C]
        # Reacquire and revalidate before rolling back the inserted Like.
        call 0x425950
        test eax, eax
        jz write_failed_result
        mov eax, dword ptr [eax+0x17E24]
        cmp eax, dword ptr [ebp-0x14]
        jne write_failed_result
        mov ecx, 0x554148
        push eax
        call 0x471840
        test eax, eax
        jz write_failed_result
        mov ecx, 0x554148
        push dword ptr [ebp-0x14]
        call 0x46F950
        test eax, eax
        jz write_failed_result
        cmp eax, dword ptr [ebp-0x18]
        jne write_failed_result
        mov esi, eax
        cmp byte ptr [esi+0x1CD4], 0
        je write_failed_result
        cmp dword ptr [esi+0x1C40], 0
        jle write_failed_result
        cmp byte ptr [esi+0x1CE1], 0
        jne write_failed_result
        cmp byte ptr [esi+0x1CEC], 0
        jne write_failed_result
        cmp dword ptr [esi+edi*4+0x1F5C], 38
        jne write_failed_result
        mov dword ptr [esi+edi*4+0x1F5C], -1
        cmp dword ptr [esi+edi*4+0x1F5C], -1
        jne write_failed_result
        and dword ptr [ebp-0x44], 0xFFFFFFFE
    rollback_dislikes:
        xor edi, edi
    rollback_dislike_loop:
        cmp edi, 3
        jae write_failed_result
        mov eax, 1
        mov ecx, edi
        inc ecx
        shl eax, cl
        test dword ptr [ebp-0x44], eax
        jz rollback_dislike_next
        cmp dword ptr [ebp+edi*4-0x34], 38
        jne rollback_dislike_next
        # Reacquire and revalidate before each Dislike restoration.
        call 0x425950
        test eax, eax
        jz write_failed_result
        mov eax, dword ptr [eax+0x17E24]
        cmp eax, dword ptr [ebp-0x14]
        jne write_failed_result
        mov ecx, 0x554148
        push eax
        call 0x471840
        test eax, eax
        jz write_failed_result
        mov ecx, 0x554148
        push dword ptr [ebp-0x14]
        call 0x46F950
        test eax, eax
        jz write_failed_result
        cmp eax, dword ptr [ebp-0x18]
        jne write_failed_result
        mov esi, eax
        cmp byte ptr [esi+0x1CD4], 0
        je write_failed_result
        cmp dword ptr [esi+0x1C40], 0
        jle write_failed_result
        cmp byte ptr [esi+0x1CE1], 0
        jne write_failed_result
        cmp byte ptr [esi+0x1CEC], 0
        jne write_failed_result
        cmp dword ptr [esi+edi*4+0x1F68], -1
        jne write_failed_result
        mov dword ptr [esi+edi*4+0x1F68], 38
        cmp dword ptr [esi+edi*4+0x1F68], 38
        jne write_failed_result
        mov eax, 1
        mov ecx, edi
        inc ecx
        shl eax, cl
        xor dword ptr [ebp-0x44], eax
    rollback_dislike_next:
        inc edi
        jmp rollback_dislike_loop
    write_failed_result:
        push 0x{strings['running_write_failed']:X}
        jmp result
    fail:
        push 0x{strings['running_invalid']:X}
    result:
        push 0x{strings['caption']:X}
        call 0x7B2210
    done:
        mov esi, dword ptr [ebp-0x10]
        add esp, 0x48
        pop edi
        pop esi
        pop ebx
        pop ebp
        ret
    """, va)


def build_slot(page_va: int, installed: bool, include_running: bool = False) -> tuple[bytes, dict[str, object]]:
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

    if include_running:
        _running_cursor = RUNNING_STRINGS_OFFSET
        for _key, _value in RUNNING_STRING_VALUES:
            strings[_key] = page_va + _running_cursor
            _running_cursor += len(_value)

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
    individual = build_individual_helper(page_va, strings, page_va + RUNNING_OFFSET if include_running else None)
    running_confirm = b""
    if include_running:
        running_confirm = build_confirmation(
            page_va + RUNNING_CONFIRM_OFFSET,
            strings["user32"],
            strings["message_box"],
            strings["caption"],
            strings["running_confirm"],
        )
    running_helper = build_running_helper(page_va, strings) if include_running else b""
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
    result = {
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
    if include_running:
        result.update({
            "running_offset": RUNNING_OFFSET,
            "running_confirm_offset": RUNNING_CONFIRM_OFFSET,
            "running_helper_length": len(running_helper),
            "running_helper_sha256": sha(running_helper),
            "running_helper_bytes": running_helper.hex().upper(),
            "running_confirm_bytes": running_confirm.hex().upper(),
            "running_stack_frame_size": 0x48,
            "running_stack_locals": {
                "saved_esi": [-0x10, -0x0D],
                "selected_index": [-0x14, -0x11],
                "record_identity": [-0x18, -0x15],
                "first_empty_slot": [-0x1C, -0x19],
                "likes_snapshot_0": [-0x28, -0x25],
                "likes_snapshot_1": [-0x24, -0x21],
                "likes_snapshot_2": [-0x20, -0x1D],
                "dislikes_snapshot_0": [-0x34, -0x31],
                "dislikes_snapshot_1": [-0x30, -0x2D],
                "dislikes_snapshot_2": [-0x2C, -0x29],
                "has_running_like": [-0x38, -0x35],
                "has_running_dislike": [-0x3C, -0x39],
                "message_box_pointer": [-0x40, -0x3D],
                "mutation_mask": [-0x44, -0x41],
            },
            "running_saved_register_intervals": {
                "saved_ebx": [-0x04, -0x01],
                "saved_esi": [-0x08, -0x05],
                "saved_edi": [-0x0C, -0x09],
            },
            "running_snapshot_initialization": "all three Like and all three Dislike DWORDs are stored before confirmation in disjoint slots; first-empty initializes to -1 and record identity is stored separately",
            "running_rollback": "after any failed write/readback, reacquire the same index and record pointer before each slot restore, verify active/living/status/faction and the exact candidate-written value, restore every inserted Like and every cleared Running Dislike independently, and verify each restore; if any guard fails, disclose retained per-slot effects and never claim full rollback; never deduct; no independent skeleton discriminator is claimed",
            "running_strings_offset": RUNNING_STRINGS_OFFSET,
            "running_strings_blob": running_strings_blob().hex().upper(),
            "running_string_pointers": {
                key: f"0x{page_va + RUNNING_STRINGS_OFFSET + sum(len(item) for _, item in RUNNING_STRING_VALUES[:index]):X}"
                for index, (key, item) in enumerate(RUNNING_STRING_VALUES)
            },
        })
    return bytes(slot), result


def build_dispatcher(page_va: int, bound: int, dispatcher_offset: int = 0x40) -> bytes:
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
        page_va + dispatcher_offset,
    )


def build_running_dispatcher(page_va: int) -> bytes:
    """Route the composed command-1/2 hook without touching legacy commands."""
    return asm(
        f"""
            cmp ebx, 1
            je 0x7C9D00
            cmp ebx, 2
            je 0x{page_va + RUNNING_OFFSET:X}
            jmp 0x7B2790
        """,
        page_va + RUNNING_DISPATCHER_OFFSET,
    )


def build_page(
    page_va: int,
    slot: bytes,
    dispatcher: bytes,
    slot_map: dict[str, object] | None = None,
    dispatcher_offset: int = 0x40,
) -> bytes:
    page = bytearray(PAGE_SIZE)
    page[0:8] = b"VFM5PG\0\0"
    page[8:12] = (1).to_bytes(4, "little")
    page[12:16] = PAGE_SIZE.to_bytes(4, "little")
    page[16:20] = SLOT_OFFSET.to_bytes(4, "little")
    page[20:24] = SLOT_SIZE.to_bytes(4, "little")
    page[24:28] = (SLOT_OFFSET + SLOT_ENTRY_OFFSET).to_bytes(4, "little")
    page[28:32] = page_va.to_bytes(4, "little")
    if dispatcher_offset + len(dispatcher) > SLOT_OFFSET:
        raise RuntimeError("base dispatcher overlaps command-7 slot")
    page[dispatcher_offset : dispatcher_offset + len(dispatcher)] = dispatcher
    page[SLOT_OFFSET : SLOT_OFFSET + SLOT_SIZE] = slot
    if slot_map and slot_map.get("running_helper_bytes"):
        helper = bytes.fromhex(str(slot_map["running_helper_bytes"]))
        confirm = bytes.fromhex(str(slot_map["running_confirm_bytes"]))
        if RUNNING_CONFIRM_OFFSET < PAGE_SIZE and RUNNING_CONFIRM_OFFSET + len(confirm) > RUNNING_STRINGS_OFFSET:
            raise RuntimeError("VV5 Running confirmation overlaps strings")
        if RUNNING_CONFIRM_OFFSET < PAGE_SIZE and RUNNING_CONFIRM_OFFSET + len(confirm) > RUNNING_OFFSET:
            raise RuntimeError("VV5 Running confirmation overlaps helper")
        if RUNNING_OFFSET + len(helper) > RUNNING_STRINGS_OFFSET:
            raise RuntimeError("VV5 Running helper overlaps strings")
        page[RUNNING_OFFSET : RUNNING_OFFSET + len(helper)] = helper
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
    if slot_map and slot_map.get("running_helper_bytes"):
        intervals = {
            "dispatcher": (dispatcher_offset, dispatcher_offset + len(dispatcher)),
            "slot": (0x100, 0x1100),
            "full_mastery_strings": (STRINGS_OFFSET, cursor),
            "running_helper": (RUNNING_OFFSET, RUNNING_OFFSET + len(helper)),
            "running_strings": (RUNNING_STRINGS_OFFSET, RUNNING_STRINGS_OFFSET + len(running_strings_blob())),
        }
        if RUNNING_CONFIRM_OFFSET < PAGE_SIZE:
            intervals["running_confirm"] = (RUNNING_CONFIRM_OFFSET, RUNNING_CONFIRM_OFFSET + len(confirm))
        for name, (start, end) in intervals.items():
            if start < 0 or end > PAGE_SIZE:
                raise RuntimeError(f"VV5 Running {name} escapes page")
            for other, (ostart, oend) in intervals.items():
                if name != other and start < oend and ostart < end:
                    raise RuntimeError(f"VV5 Running interval overlap: {name}/{other}")
    running_strings = (
        bytes.fromhex(str(slot_map["running_strings_blob"]))
        if slot_map and slot_map.get("running_strings_blob")
        else running_strings_blob()
    )
    if slot_map and slot_map.get("running_helper_bytes") and RUNNING_STRINGS_OFFSET + len(running_strings) > len(page):
        raise RuntimeError("VV5 Running strings exceed page")
    if slot_map and slot_map.get("running_helper_bytes") and RUNNING_CONFIRM_OFFSET < PAGE_SIZE:
        page[RUNNING_CONFIRM_OFFSET : RUNNING_CONFIRM_OFFSET + len(confirm)] = confirm
    if slot_map and slot_map.get("running_helper_bytes"):
        page[RUNNING_STRINGS_OFFSET : RUNNING_STRINGS_OFFSET + len(running_strings)] = running_strings
    return bytes(page)


def build_running_page(base_page: bytes, confirm: bytes) -> bytes:
    """Extend the certified Full Mastery page with an isolated confirm tail."""
    if len(base_page) != PAGE_SIZE or RUNNING_CONFIRM_OFFSET + len(confirm) > RUNNING_PAGE_SIZE:
        raise RuntimeError("VV5 Running extended page layout is invalid")
    page = bytearray(RUNNING_PAGE_SIZE)
    page[:PAGE_SIZE] = base_page
    page[RUNNING_CONFIRM_OFFSET : RUNNING_CONFIRM_OFFSET + len(confirm)] = confirm
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


def running_section_header(rva: int, raw_offset: int = RUNNING_APPEND_OFFSET) -> bytes:
    """Build the exact RX .vv5run section record at the derived append boundary."""
    return (
        b".vv5run\0"
        + RUNNING_PAGE_SIZE.to_bytes(4, "little")
        + rva.to_bytes(4, "little")
        + RUNNING_PAGE_SIZE.to_bytes(4, "little")
        + raw_offset.to_bytes(4, "little")
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

    # The stock constructors already call the correct menu entry points at
    # 0x7B200E (Tech -> 0x7B22C0) and 0x7B20CE (Detail -> 0x7B2600). Replace
    # only those five-byte call instructions with calls into the one common
    # native-state wrapper. The compact Tech/Detail stubs at 0x7B2B40 and
    # 0x7B2B47 select the target and share the body at 0x7B2B4C.
    sdl_string_va = PAYLOAD_VA + FULLSCREEN_STRING_OFFSET
    tech_wrapper_va = PAYLOAD_VA + FULLSCREEN_TECH_OFFSET
    detail_wrapper_va = PAYLOAD_VA + FULLSCREEN_DETAIL_OFFSET
    common_wrapper_va = PAYLOAD_VA + FULLSCREEN_COMMON_OFFSET
    tech_wrapper = build_fullscreen_entry(tech_wrapper_va, 0x7B22C0, common_wrapper_va, True)
    detail_wrapper = build_fullscreen_entry(detail_wrapper_va, 0x7B2600, common_wrapper_va, False)
    common_wrapper = build_fullscreen_wrapper(common_wrapper_va, sdl_string_va)
    for label, offset, wrapper, expected in (
        ("Tech", 0x0E, tech_wrapper, bytes.fromhex("E8AD020000")),
        ("Detail", 0xCE, detail_wrapper, bytes.fromhex("E82D050000")),
    ):
        if payload[offset : offset + 5] != expected:
            raise RuntimeError(f"VV5 {label} menu call guard mismatch")
        if any(payload[offset + 5 : offset + 5]):
            raise RuntimeError(f"VV5 {label} call boundary is not five bytes")
        call = asm(f"call 0x{(tech_wrapper_va if label == 'Tech' else detail_wrapper_va):X}", PAYLOAD_VA + offset)
        if len(call) != 5:
            raise RuntimeError(f"VV5 {label} wrapper call is not rel32")
        payload[offset : offset + 5] = call
        cave_offset = FULLSCREEN_TECH_OFFSET if label == "Tech" else FULLSCREEN_DETAIL_OFFSET
        if any(payload[cave_offset : cave_offset + len(wrapper)]):
            raise RuntimeError(f"VV5 {label} fullscreen wrapper cave is not zero")
        payload[cave_offset : cave_offset + len(wrapper)] = wrapper
    if payload[FULLSCREEN_COMMON_OFFSET : FULLSCREEN_COMMON_OFFSET + len(common_wrapper)] != b"\0" * len(common_wrapper):
        raise RuntimeError("VV5 common fullscreen wrapper cave is not zero")
    payload[FULLSCREEN_COMMON_OFFSET : FULLSCREEN_COMMON_OFFSET + len(common_wrapper)] = common_wrapper
    if payload[FULLSCREEN_STRING_OFFSET : FULLSCREEN_STRING_OFFSET + len(FULLSCREEN_STRING)] != b"\0" * len(FULLSCREEN_STRING):
        raise RuntimeError("VV5 SDL2 wrapper string cave is not zero")
    payload[FULLSCREEN_STRING_OFFSET : FULLSCREEN_STRING_OFFSET + len(FULLSCREEN_STRING)] = FULLSCREEN_STRING
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
            cmp ebx, 5
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
    active_bytes = ACTIVE_BASE.read_bytes()
    if len(active_bytes) != ACTIVE_BASE_SIZE or sha(active_bytes) != ACTIVE_BASE_SHA256:
        raise RuntimeError("VV5 active Origins base is not the exact pinned input")
    active = json.loads(active_bytes.decode("utf-8"))
    cure_projection = build_cure_projection()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    CURE_PROJECTION.write_bytes(cure_projection)
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
        pages[mode] = build_page(layout["page_va"], noop, dispatcher, noop_map)
        installed_pages[mode] = build_page(layout["page_va"], installed, dispatcher, installed_map)
        slot_maps[mode] = {"noop": noop_map, "installed": installed_map}

    # Keep the new command-2 candidate isolated from the certified Full
    # Mastery feature page.  Its bytes and metadata are emitted as a separate
    # disabled projection until independent recertification.
    running_slot, running_map = build_slot(RUNNING_PAGE_VA, True, True)
    running_dispatcher = build_running_dispatcher(RUNNING_PAGE_VA)
    running_base_page = build_page(
        RUNNING_PAGE_VA,
        running_slot,
        running_dispatcher,
        running_map,
        dispatcher_offset=RUNNING_DISPATCHER_OFFSET,
    )
    running_page = build_running_page(
        running_base_page,
        bytes.fromhex(str(running_map["running_confirm_bytes"])),
    )
    running_section = running_section_header(RUNNING_PAGE_RVA)
    running_layouts = {
        mode: {
            "parent_sha256": parent_sha,
            "original_file_size": "0xF4000",
            "append_offset": "0xF4000",
            "append_length": RUNNING_PAGE_SIZE,
            "append_source": "generated:vv5_individual_running_page",
            "rva": "0x3CB000",
            "va": "0x7CB000",
            "section_header_offset": "0x2E0",
            "section_header_before": (b"\0" * 40).hex().upper(),
            "section_header_after": running_section.hex().upper(),
            "header_patches": [
                {"offset": "0xFE", "before": "0600", "after": "0700", "purpose": "add candidate-owned .vv5run section"},
                {"offset": "0x148", "before": "00B03C00", "after": "00D03C00", "purpose": "extend SizeOfImage for .vv5run"},
                {"offset": "0x2E0", "before": (b"\0" * 40).hex().upper(), "after": running_section.hex().upper(), "purpose": "install guarded RX .vv5run section header"},
            ],
            "hook_before": RUNNING_PARENT_HOOK_BEFORE,
            "hook_after": RUNNING_HOOK_AFTER,
            "purpose": "append the candidate-owned VV5 command-2 .vv5run RX page",
        }
        for mode, parent_sha in {
            "collection_progression": "857E22D7C361B802508BF789C3CC486E42E76021F5AA579BB1D16CC6E0D017A0",
        }.items()
    }
    running_candidate = {
        "id": "vv5_individual_grant_running_candidate",
        "game_id": "vv5",
        "name": "DISABLED Candidate: Grant Running to Selected Villager",
        "enabled": False,
        "catalog_hidden": True,
        "catalog_enabled": False,
        "runtime_status": "pending",
        "certification_status": "disabled candidate; independent emitted-byte and runtime recertification pending",
        "allowed_modes": ["collection_progression"],
        "unsupported_patch_modes": ["experimental_expanded_256", "experimental_expanded_256_progression"],
        "expanded_fail_closed": True,
        "dependencies": ["vv5_full_mastery_all_stage_a_candidate"],
        "companion": {
            "source": "data/candidates/VVFP VV5 Full Mastery Candidate.dll",
            "destination": "VVFP Origins Icons.dll",
            "sha256": COMPANION_PARENT_SHA256,
            "preimage_sha256": COMPANION_PARENT_SHA256,
            "restore_sha256": COMPANION_PARENT_SHA256,
            "atomic_install_remove": True,
        },
        "patches": [{
            "offset": f"0x{RUNNING_PARENT_HOOK_OFFSET:X}",
            "before": RUNNING_PARENT_HOOK_BEFORE,
            "after": RUNNING_HOOK_AFTER,
            "purpose": "guarded composed-parent dispatcher: EBX=1 remains 0x7C9D00, EBX=2 enters Running, all other commands continue 0x7B2790",
        }],
        "parent_hashes": {
            "collection_progression": "857E22D7C361B802508BF789C3CC486E42E76021F5AA579BB1D16CC6E0D017A0",
        },
        "pe_append_transaction": {
            "status": "disabled real production candidate; loader/install/remove recertification pending",
            "section": ".vv5run",
            "append_source": "generated:vv5_individual_running_page",
            "append_offset": f"0x{RUNNING_APPEND_OFFSET:X}",
            "rva": f"0x{RUNNING_PAGE_RVA:X}",
            "va": f"0x{RUNNING_PAGE_VA:X}",
            "append_length": RUNNING_PAGE_SIZE,
            "section_characteristics": "RX",
            "dispatcher_offset": f"0x{RUNNING_DISPATCHER_OFFSET:X}",
            "dispatcher_va": f"0x{RUNNING_PAGE_VA + RUNNING_DISPATCHER_OFFSET:X}",
            "hook_preimage": RUNNING_PARENT_HOOK_BEFORE,
            "hook_after": RUNNING_HOOK_AFTER,
            "hook_owner": "vv5_individual_grant_running_candidate",
            "uninstall": "restore exact composed parent hook and truncate only candidate-owned .vv5run append",
            "layouts": running_layouts,
        },
        "transaction_contract": {
            "command": 2, "price": 40000, "action": "Buy", "repeatable": True,
            "ownership": None, "remove": False,
            "selected_index": "sub_425950()+0x17E24 signed 0..149",
            "eligibility": ["byte record+0x1CD4 != 0 (active)", "signed dword record+0x1C40 > 0 (living)", "byte record+0x1CE1 == 0 (Heathen-active/status guard)", "byte record+0x1CEC == 0 (current-Believer faction); no independent skeleton discriminator is claimed"],
            "likes": ["record+0x1F5C", "record+0x1F60", "record+0x1F64"],
            "running_value": 38, "empty_value": -1,
            "dry_run": "scan all three Likes and all three Dislikes before confirmation; preserve Like duplicates; first physical -1 Like only; clear every Running Dislike",
            "reacquire": "same selected index, record identity, eligibility, and exact six-slot snapshot before write",
            "record_identity": "initial and confirmed resolver pointers must match exactly; no cached physical-base walking",
            "funds_checks": ["complete dry-run before confirmation", "immediately before write"],
            "rollback": "on failed write/readback, reacquire the same index and record identity before every direct store, require the supported active/living/status/faction predicate and exact candidate-written values, restore the inserted Like and every cleared Running Dislike independently and verify; if any restore is unsafe, report retained per-slot effects rather than claiming full rollback; no charge; no independent skeleton discriminator is claimed",
            "deduction": "ECX=0x51D5F8; push -40000; call 0x4237B0 exactly once",
            "dislike_slots": ["record+0x1F68", "record+0x1F6C", "record+0x1F70"],
            "allowed_writes": ["first physical empty Like = 38", "every Dislike = 38 -> -1"],
            "forbidden_reads": ["movement", "speed"],
            "accept_result": 1,
            "cancel_results": [0, 2],
            "confirmation": "Grant Running to this villager for 40,000 tech points?\\r\\nPress OK to confirm, or Cancel.",
            "no_deduction": "No tech points have been deducted.",
            "result_messages": {
                "already_running": "This villager already likes Running.\\r\\nNo tech points have been deducted.",
                "no_empty_like": "This villager has no empty Like slot.\\r\\nNo tech points have been deducted.",
                "invalid_selection": "No valid living villager is selected.\\r\\nNo tech points have been deducted.",
                "canceled": "Grant Running was canceled.\\r\\nNo tech points have been deducted.",
                "recheck": "The selected villager changed during confirmation.\\r\\nNo tech points have been deducted.",
                "write_failure": "Running could not be verified.\\r\\nNo tech points have been deducted.",
                "success": "Running was granted.",
            },
        },
        "emitted": {
            "page_sha256": sha(running_page),
            "page_rva": f"0x{RUNNING_PAGE_RVA:X}",
            "page_va": f"0x{RUNNING_PAGE_VA:X}",
            "append_offset": f"0x{RUNNING_APPEND_OFFSET:X}",
            "dispatcher_va": f"0x{RUNNING_PAGE_VA + RUNNING_DISPATCHER_OFFSET:X}",
            "dispatcher_sha256": sha(running_dispatcher),
            "dispatcher_bytes": running_dispatcher.hex().upper(),
            "helper_sha256": running_map["running_helper_sha256"],
            "helper_length": running_map["running_helper_length"],
            "rendered_exe_size": 0xF6000,
            "rendered_exe_sha256": {
                "collection_progression": "1E3FD6CE44E906BD8DDD7C937D68AB74671D8F197BC1D767A2B0622F1A0F7907",
            },
        },
        "provenance": {"implementation_parent": "f1256fca68f2711974e93057e599f2642c77a2a4", "implementation_commit": None, "audit_commit": None, "acceptance_commit": None},
    }
    RUNNING_OUT.write_text(json.dumps(running_candidate, indent=2) + "\n", encoding="utf-8")
    RUNNING_MAP_OUT.write_text(json.dumps({"candidate": running_candidate, "slot": running_map}, indent=2) + "\n", encoding="utf-8")
    RUNNING_DOC_OUT.write_text(
        "# VV5 individual Grant Running candidate\n\n"
        "This candidate is disabled and catalog-hidden pending independent emitted-byte and runtime recertification. "
        "It is restricted to Collection Progression; Immediate Fixed is unsupported until its exact parent is authenticated, and Expanded-256 rejects before output.\n\n"
        "The transaction is command 2, Buy-only, 40,000 tech points. It performs a complete selected-villager dry run, "
        "scans and snapshots Likes +0x1F5C/+0x1F60/+0x1F64 and Dislikes +0x1F68/+0x1F6C/+0x1F70, preserves duplicate Likes, "
        "writes Running only to the first exact -1 Like when needed, and clears every Running Dislike only when Running is or can be ensured as a Like. "
        "No empty Like means no writes/no charge even when Running is a Dislike. It reacquires and rechecks before mutation, verifies all six slots after writes, then performs one native deduction. Movement and speed are untouched.\n\n"
        "The disabled production candidate owns .vv5run at raw 0xF4000 / RVA 0x3CB000 / VA 0x7CB000 (RX, 0x2000 bytes); "
        "its dispatcher is VA 0x7CB020 and replaces the composed-parent hook E995750100 with E9B5880100. "
        "EBX=1 remains the certified Full Mastery helper at 0x7C9D00, EBX=2 is Running, and all other commands continue at 0x7B2790.\n\n"
        "Every cancel, no-change, recheck, dependency, and failure result includes `No tech points have been deducted.` IDOK is exactly 1; Cancel/close/other results are rejected. "
        "Eligibility is the certified active/living/status-valid current-Believer predicate: +0x1CD4 active, signed +0x1C40 > 0, +0x1CE1 Heathen-active/status guard clear, and +0x1CEC current-Believer faction clear. No independent skeleton discriminator is claimed, so runtime certification remains pending. The existing enabled VV5 Full Mastery bytes remain unchanged; this overlay is not catalog-visible. Direct native preference stores remain a separate enablement gate and native partial effects are disclosed truthfully.\n",
        encoding="utf-8",
    )

    stock_payload = build_base_payload(
        active_payload, LAYOUTS["collection_progression"]["page_va"]
    )
    base = deepcopy(active)
    base["id"] = "vv5_enable_origins_exclusive_features_full_mastery_candidate"
    base["name"] = "DISABLED Candidate: VV5 Origins Full Mastery Extension Base"
    base["enabled"] = False
    base["catalog_hidden"] = True
    base["certification_status"] = (
        "disabled C253 candidate; native 0x404700 fullscreen state chain is statically "
        "proven and independent emitted-byte recertification is pending; Expanded-256 fail-closed"
    )
    base["active_base"] = {
        "path": "data/vv5_origins_feature.json",
        "size": ACTIVE_BASE_SIZE,
        "sha256": ACTIVE_BASE_SHA256,
    }
    base["dependencies"] = []
    base["expanded_shr_relocations"]["patches"] = []
    base["companion_files"] = [
        {
            "source": "data/candidates/VVFP VV5 Cure Containment Projection.dll",
            "destination": "VVFP Origins Icons.dll",
            "sha256": CURE_PROJECTION_SHA256,
            "size": len(cure_projection),
            "preimage_sha256": COMPANION_PARENT_SHA256,
            "restore_source": "data/candidates/VVFP VV5 Full Mastery Candidate.dll",
            "restore_sha256": COMPANION_PARENT_SHA256,
            "parent": "data/candidates/VVFP VV5 Full Mastery Candidate.dll",
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
        "retain the legacy Cure payload byte-identically for provenance while the "
        "candidate command-5 router returns to the menu and the candidate DLL "
        "structurally removes the public Cure row"
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
    base["fullscreen_dialog_contract"] = {
        "status": (
            "disabled candidate-only native engine state-synchronised bracket; pending independent emitted-byte recertification"
        ),
        "tech_call": {"offset": "0xDB00E", "before": "E8AD020000", "target": "0x7B22C0", "wrapper": f"0x{PAYLOAD_VA + FULLSCREEN_TECH_OFFSET:X}"},
        "detail_call": {"offset": "0xDB0CE", "before": "E82D050000", "target": "0x7B2600", "wrapper": f"0x{PAYLOAD_VA + FULLSCREEN_DETAIL_OFFSET:X}"},
        "common_wrapper": f"0x{PAYLOAD_VA + FULLSCREEN_COMMON_OFFSET:X}",
        "sdl": {
            "module": "SDL2.dll",
            "get_module_handle_iat": "0x4951D8",
            "get_proc_address_iat": "0x4951DC",
            "get_window_flags_symbol": "SDL_GetWindowFlags",
            "fullscreen_flags": "0x1001",
            "calls": 3,
            "abi": "push SDL_Window*; indirect call; add esp,4 for each invocation",
        },
        "native_transition_returns": "ignored; only freshly reacquired engine state and masked flags decide success",
        "restore": "successful leave sets a local left flag; every modal exit attempts one fresh singleton/outer/engine/window restoration and post-verifies flags/state",
        "failure": (
            "missing dependency, singleton mismatch, unexpected flags, failed native leave, "
            "or failed native restore returns safely without entering/charging the modal menu"
        ),
        "native_engine_getter_va": "0x4080C0",
        "native_engine_leave_va": "0x40A270",
        "native_engine_enter_va": "0x40A280",
        "native_engine_transition_va": "0x404700",
        "native_engine_state_chain": "getter -> outer [0x4DB0E8] -> engine [outer] -> window +0x38, state +0x1E",
        "native_engine_transition_proof": "stock exact-build chain statically proven; candidate remains disabled/catalog-hidden pending emitted recertification",
    }
    base["cure_containment"] = {
        "command": 5,
        "router_guard": {"comparison": "EBX < 5", "legacy_target": "0x7B2461", "menu_loop": "0x7B22C0"},
        "resource_transform": "structurally remove the five-item legacy Cure row from RT_DIALOG 201 and 203; 202 byte-identical",
        "parent_dll_sha256": COMPANION_PARENT_SHA256,
        "candidate_companion_sha256": CURE_PROJECTION_SHA256,
        "restore_source": "data/candidates/VVFP VV5 Full Mastery Candidate.dll",
        "restore_sha256": COMPANION_PARENT_SHA256,
        "atomic_install_remove": True,
        "asset_policy": {
            "destination": "Images\\btn_trophies.png",
            "sha256": PROVENANCE_ASSET_SHA256,
            "operation": "preserve-and-verify-stock-asset",
            "note": "The native cached PNG is never replaced or deleted; EXE/DLL atomic publication verifies it byte-for-byte.",
        },
        "projection": {
            "path": "data/candidates/VVFP VV5 Cure Containment Projection.dll",
            "size": len(cure_projection),
            "sha256": CURE_PROJECTION_SHA256,
        },
        "status": "candidate-only; requires independent emitted DLL recertification before enablement",
    }
    base["pe_append_transaction"] = {
        "owner": base["id"],
        "section_name": ".vv5fm",
            "append_length": RUNNING_PAGE_SIZE,
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
    # Never re-enable the dependent C99 candidate while its base parent remains
    # disabled by the unresolved D248 native-transition gate. Rendering still
    # produces the stock-mode bytes and hashes as static evidence, but the
    # dependent metadata must follow the parent fail-closed.
    feature_enabled = base.get("enabled") is True
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
            "C260 static enablement for Collection Progression and Immediate Fixed; "
            "runtime/player validation pending; Expanded-256 remains fail-closed"
            if feature_enabled
            else (
                "disabled candidate; base parent is disabled pending independent "
                "emitted-byte and native-transition recertification"
            )
        ),
        "dependencies": [base["id"]],
        "description": (
        "Command-7 village-wide and guarded command-1 selected-Believer Full Mastery "
        "candidate using native six-skill Float32 writer sub_475730; commands 5/6/8 "
        "are fail-closed and the legacy Cure row is structurally removed from the "
        "candidate DLL."
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
                "target": "selected current active/living status-valid current-Believer; no independent skeleton discriminator is claimed",
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
            else (
                "disabled candidate; base parent is disabled pending independent "
                "emitted-byte and native-transition recertification"
            )
        ),
        "allowed_modes": ["collection_progression", "immediate_fixed"],
        "expanded_fail_closed": True,
        "source": {"size": len(stock), "sha256": expected_sha},
        "active_base": base["active_base"],
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
        "fullscreen_dialog_contract": base["fullscreen_dialog_contract"],
        "cure_containment": base["cure_containment"],
        "asset_policy": base["cure_containment"]["asset_policy"],
        "companion": {
            "path": "data/candidates/VVFP VV5 Cure Containment Projection.dll",
            "size": len(cure_projection),
            "sha256": CURE_PROJECTION_SHA256,
            "parent_sha256": COMPANION_PARENT_SHA256,
            "preimage_sha256": COMPANION_PARENT_SHA256,
            "restore_source": "data/candidates/VVFP VV5 Full Mastery Candidate.dll",
            "restore_sha256": COMPANION_PARENT_SHA256,
            "exports": export_map(cure_projection),
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
                "0x4951D8 GetModuleHandleA IAT",
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
            "Expanded-256 remains fail-closed; legacy Cure command 5 is routed to a "
            "safe menu return and its public row is removed by the candidate-owned "
            "resource transform.\n\n"
            if feature_enabled
            else "The corrected constructor and Full Mastery paths remain static evidence, "
            "but this dependent feature is disabled and catalog-hidden while its base "
            "parent remains disabled pending independent emitted-byte and native-transition "
            "recertification. The candidate uses cached `Images\\btn_trophies.png`, resource "
            "0x6A (96x39), at local (137,2) for both Tech and Detail, with event 13, "
            "sub_401BD0, and existing 0x40C680 ownership.\n\n"
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
        "position `(137,2)`, event `13`, factory `0x401BD0`, and ownership `0x40C680`.\n"
        "The candidate map `ui_geometry_contract` must reproduce this contract exactly\n"
        "(including asset/provenance paths and hashes) before either stock-mode output\n"
        "is created; missing, mistyped, or extra fields fail closed.\n\n"
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
        "confirmation routine and string remain distinct.\n"
        "Each Tech and Detail modal call is wrapped by one guarded native-state "
        "transition. Compact entries at VA 0x7B2B40 and 0x7B2B47 select the menu "
        "target and share VA 0x7B2B4C. The wrapper resolves only SDL_GetWindowFlags "
        "through the existing GetModuleHandleA/GetProcAddress IATs, validates flags "
        "0 or 0x1001 against the native engine state, calls native leave 0x40A270 and "
        "enter 0x40A280 through the 0x4080C0 singleton chain, and fail-closes on "
        "identity, dependency, or restore failure.\n"
        "The candidate-owned DLL transform removes the five-item legacy Cure row from "
        "dialogs 201 and 203 while preserving dialog 202 and all non-resource bytes.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
