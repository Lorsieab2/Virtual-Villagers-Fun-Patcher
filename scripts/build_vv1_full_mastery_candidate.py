"""Generate the disabled VV1 command-7 Full Mastery Stage-A candidate."""

from __future__ import annotations

import hashlib
import json
import struct
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - A New Home.exe"
OUT_DIR = ROOT / "data" / "candidates"
MANIFEST_OUT = OUT_DIR / "vv1_full_mastery_all_candidate.json"
MAP_OUT = OUT_DIR / "vv1_full_mastery_all_candidate_map.json"
DOC_OUT = ROOT / "docs" / "vv1-full-mastery-stage-a-candidate.md"
COMPANION = OUT_DIR / "VVFP VV1 Full Mastery Candidate.dll"

sys.path.insert(0, str(ROOT / ".tools" / "keystone"))
sys.path.insert(0, str(ROOT / ".tools" / "keystone-runtime"))
sys.path.insert(0, str(ROOT / "src"))
from keystone import KS_ARCH_X86, KS_MODE_32, Ks  # noqa: E402


IMAGE_BASE = 0x400000
APPEND_OFFSET = 0x8E000
SECTION_RVA = 0x90000
SECTION_VA = IMAGE_BASE + SECTION_RVA
SECTION_SIZE = 0x2000
OLD_SIZE_OF_IMAGE = 0x90000
NEW_SIZE_OF_IMAGE = 0x92000
TECH_HANDLER_OFFSET = 0x000
TECH_CONSTRUCTOR_OFFSET = 0x040
ENTRY_OFFSET = 0x100
WALKER_OFFSET = 0x380
CONFIRM_OFFSET = 0x580
SHOW_MENU_OFFSET = 0x640
SHOW_RESULT_OFFSET = 0x6C0
STRINGS_OFFSET = 0x900
PRICE = 1_000_000
BOUND = 256
STRIDE = 0x3D8

MODES = (
    "collection_progression",
    "immediate_fixed",
)
REJECTED_MODES = (
    "experimental_expanded_256",
    "experimental_expanded_256_progression",
)


def require_supported_mode(mode: str) -> None:
    if mode in REJECTED_MODES:
        raise RuntimeError(
            f"VV1 Full Mastery candidate rejects Expanded-256 mode before output: {mode}"
        )
    if mode not in MODES:
        raise RuntimeError(f"unsupported VV1 Full Mastery candidate mode: {mode}")


def asm(source: str, address: int) -> bytes:
    encoding, _ = Ks(KS_ARCH_X86, KS_MODE_32).asm(source, address)
    return bytes(encoding)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def rel32_jump(source_va: int, target_va: int) -> bytes:
    return b"\xE9" + struct.pack("<i", target_va - (source_va + 5))


def export_map(data: bytes) -> dict[str, dict[str, int]]:
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    coff = pe + 4
    section_count = struct.unpack_from("<H", data, coff + 2)[0]
    optional_size = struct.unpack_from("<H", data, coff + 16)[0]
    optional = coff + 20
    table = optional + optional_size
    export_rva = struct.unpack_from("<I", data, optional + 96)[0]

    def raw(rva: int) -> int:
        for index in range(section_count):
            entry = table + index * 40
            virtual_size, section_rva, raw_size, raw_offset = struct.unpack_from(
                "<IIII", data, entry + 8
            )
            if section_rva <= rva < section_rva + max(virtual_size, raw_size):
                return raw_offset + rva - section_rva
        raise RuntimeError(f"unmapped DLL RVA 0x{rva:X}")

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
            raise RuntimeError("DLL export ordinal is out of range")
        function_rva = struct.unpack_from(
            "<I", data, raw(functions_rva) + ordinal_index * 4
        )[0]
        result[name] = {
            "ordinal": ordinal_base + ordinal_index,
            "rva": function_rva,
        }
    return result


def _put(blob: bytearray, offset: int, payload: bytes, label: str) -> None:
    end = offset + len(payload)
    if end > len(blob):
        raise RuntimeError(f"{label} exceeds section")
    if any(blob[offset:end]):
        raise RuntimeError(f"{label} overlaps another artifact")
    blob[offset:end] = payload


def _add_string(blob: bytearray, cursor: int, value: bytes) -> tuple[int, int]:
    if not value.endswith(b"\0"):
        value += b"\0"
    end = cursor + len(value)
    if end > len(blob):
        raise RuntimeError("candidate string block exceeds section")
    blob[cursor:end] = value
    return SECTION_VA + cursor, end


def _pe_layout(image: bytes) -> dict[str, int]:
    pe = struct.unpack_from("<I", image, 0x3C)[0]
    coff = pe + 4
    optional_size = struct.unpack_from("<H", image, coff + 16)[0]
    optional = coff + 20
    sections = struct.unpack_from("<H", image, coff + 2)[0]
    return {
        "pe": pe,
        "section_count_offset": coff + 2,
        "optional": optional,
        "size_of_image_offset": optional + 56,
        "checksum_offset": optional + 64,
        "section_header_offset": optional + optional_size + sections * 40,
        "section_count": sections,
    }


def build_section() -> tuple[bytes, dict[str, object]]:
    section = bytearray(SECTION_SIZE)
    cursor = STRINGS_OFFSET
    strings: dict[str, int] = {}
    for key, value in (
        ("button", b"Origins Upgrades"),
        ("candidate_dll", b"VVFP VV1 Full Mastery Candidate.dll"),
        ("menu_export", b"ShowVV1FullMasteryMenu"),
        ("result_export", b"ShowVV1FullMasteryResult"),
        ("user32", b"user32.dll"),
        ("message_box", b"MessageBoxA"),
        (
            "warning",
            b"Grant Full Mastery to all villagers for 1,000,000 tech points?\r\n"
            b"Press OK to confirm, or Cancel.",
        ),
        ("caption", b"Origins Upgrades"),
        (
            "post_verify_failure",
            b"Full Mastery could not be verified after native writes.\r\n"
            b"No tech points have been deducted.",
        ),
    ):
        strings[key], cursor = _add_string(section, cursor, value)

    handler_va = SECTION_VA + TECH_HANDLER_OFFSET
    constructor_va = SECTION_VA + TECH_CONSTRUCTOR_OFFSET
    entry_va = SECTION_VA + ENTRY_OFFSET
    walker_va = SECTION_VA + WALKER_OFFSET
    confirm_va = SECTION_VA + CONFIRM_OFFSET
    show_menu_va = SECTION_VA + SHOW_MENU_OFFSET
    show_result_va = SECTION_VA + SHOW_RESULT_OFFSET

    handler = asm(
        f"""
            cmp dword ptr [esp + 4], 8
            jne original
            cmp dword ptr [esp + 8], 2
            jne original
            call 0x{entry_va:X}
            xor eax, eax
            ret 8
        original:
            cmp dword ptr [esp + 4], 8
            jmp 0x435AB5
        """,
        handler_va,
    )
    _put(section, TECH_HANDLER_OFFSET, handler, "tech handler")

    constructor = asm(
        f"""
            push 0x14
            call 0x44AF03
            add esp, 4
            test eax, eax
            je done
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
            push 0x{strings['button']:X}
            mov ecx, edi
            call 0x4015B0
            push edi
            mov ecx, esi
            call 0x40AB80
        done:
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
        constructor_va,
    )
    _put(section, TECH_CONSTRUCTOR_OFFSET, constructor, "tech constructor")

    # The handler is thiscall. Save the caller's nonvolatile ESI, transport ECX
    # into ESI, and use the native writer for every individual skill change.
    entry = asm(
        f"""
            push ebp
            mov ebp, esp
            push ebx
            push esi
            mov esi, ecx
            push edi
            sub esp, 4
            call 0x{show_menu_va:X}
            cmp eax, 7
            jne done
            push 0x{strings['candidate_dll']:X}
            call dword ptr [0x457010]
            test eax, eax
            jz done
            push 0x{strings['result_export']:X}
            push eax
            call dword ptr [0x4570D4]
            test eax, eax
            jz done
            mov dword ptr [ebp - 16], eax
            mov edi, dword ptr [esi + 0x0C]
            test edi, edi
            jz invalid
            mov edx, dword ptr [edi + 0xADE8]
            test edx, edx
            jz invalid
            push 0
            push {BOUND}
            push edx
            call 0x{walker_va:X}
            add esp, 12
            cmp edx, 1
            je invalid
            test eax, eax
            jz no_change
            mov edi, dword ptr [esi + 0x0C]
            test edi, edi
            jz invalid
            lea edx, [edi + 0xA2FC]
            cmp dword ptr [edx], {PRICE}
            jb insufficient
            call 0x{confirm_va:X}
            cmp eax, 1
            jne done
            mov edi, dword ptr [esi + 0x0C]
            test edi, edi
            jz invalid
            mov edx, dword ptr [edi + 0xADE8]
            test edx, edx
            jz invalid
            lea edx, [edi + 0xA2FC]
            cmp dword ptr [edx], {PRICE}
            jb insufficient
            mov edx, dword ptr [edi + 0xADE8]
            test edx, edx
            jz invalid
            push 0
            push {BOUND}
            push edx
            call 0x{walker_va:X}
            add esp, 12
            cmp edx, 1
            je invalid
            test eax, eax
            jz no_change
            mov edi, dword ptr [esi + 0x0C]
            test edi, edi
            jz invalid
            mov edx, dword ptr [edi + 0xADE8]
            test edx, edx
            jz invalid
            push 1
            push {BOUND}
            push edx
            call 0x{walker_va:X}
            add esp, 12
            mov ebx, eax
            cmp edx, 1
            je invalid
            cmp edx, 2
            je post_verify_failure
            mov edi, dword ptr [esi + 0x0C]
            test edi, edi
            jz post_verify_failure
            lea edx, [edi + 0xA2FC]
            cmp dword ptr [edx], {PRICE}
            jb insufficient
            sub dword ptr [edx], {PRICE}
            push dword ptr [ebp - 16]
            push ebx
            push 1
            call 0x{show_result_va:X}
            jmp done
        no_change:
            push dword ptr [ebp - 16]
            push 0
            push 0
            call 0x{show_result_va:X}
            jmp done
        insufficient:
            push dword ptr [ebp - 16]
            push 0
            push 2
            call 0x{show_result_va:X}
            jmp done
        invalid:
            push dword ptr [ebp - 16]
            push 0
            push 3
            call 0x{show_result_va:X}
            jmp done
        post_verify_failure:
            push dword ptr [ebp - 16]
            push 0
            push 4
            call 0x{show_result_va:X}
        done:
            add esp, 4
            pop edi
            pop esi
            pop ebx
            mov esp, ebp
            pop ebp
            ret
        """,
        entry_va,
    )
    _put(section, ENTRY_OFFSET, entry, "transaction entry")

    # cdecl walker(pool, bound, mode); EAX=changed count, EDX=1 on invalid
    # eligible data, EDX=2 when mode-1's complete second read-only pass finds
    # any eligible record that is not exactly 100 in all five skills. Mode 0
    # is read-only; mode 1 writes during the first pass and then reacquires
    # the pool for a complete second pass. There is no mode 2 entry path.
    walker = asm(
        f"""
            push ebp
            mov ebp, esp
            push ebx
            push esi
            push edi
            mov esi, dword ptr [ebp + 8]
            mov edx, dword ptr [ebp + 16]
            xor ebx, ebx
            push edx
            push 0
        next:
            cmp ebx, dword ptr [ebp + 12]
            jae walk_done
            cmp byte ptr [esi + 0x28], 0
            je first_advance
            cmp dword ptr [esi + 0x344], 0
            jle first_advance
            cmp dword ptr [esi + 0x36C], 199
            je first_advance
            mov edi, 5
            lea edx, [esi + 0x3BC]
        validate:
            cmp dword ptr [edx], 0
            jl invalid
            cmp dword ptr [edx], 100
            jg invalid
            add edx, 4
            dec edi
            jne validate
            cmp dword ptr [esi + 0x3BC], 100
            jl changed
            cmp dword ptr [esi + 0x3C0], 100
            jl changed
            cmp dword ptr [esi + 0x3C4], 100
            jl changed
            cmp dword ptr [esi + 0x3C8], 100
            jl changed
            cmp dword ptr [esi + 0x3CC], 100
            jge first_advance
        changed:
            inc dword ptr [esp]
            cmp dword ptr [esp + 4], 0
            jz first_advance
            cmp dword ptr [esi + 0x3BC], 100
            je s2
            mov edi, 100
            sub edi, dword ptr [esi + 0x3BC]
            push edi
            push 2
            push ebx
            mov ecx, dword ptr [ebp + 8]
            call 0x437230
        s2:
            cmp dword ptr [esi + 0x3C0], 100
            je s3
            mov edi, 100
            sub edi, dword ptr [esi + 0x3C0]
            push edi
            push 4
            push ebx
            mov ecx, dword ptr [ebp + 8]
            call 0x437230
        s3:
            cmp dword ptr [esi + 0x3C4], 100
            je s4
            mov edi, 100
            sub edi, dword ptr [esi + 0x3C4]
            push edi
            push 1
            push ebx
            mov ecx, dword ptr [ebp + 8]
            call 0x437230
        s4:
            cmp dword ptr [esi + 0x3C8], 100
            je s5
            mov edi, 100
            sub edi, dword ptr [esi + 0x3C8]
            push edi
            push 5
            push ebx
            mov ecx, dword ptr [ebp + 8]
            call 0x437230
        s5:
            cmp dword ptr [esi + 0x3CC], 100
            je first_advance
            mov edi, 100
            sub edi, dword ptr [esi + 0x3CC]
            push edi
            push 3
            push ebx
            mov ecx, dword ptr [ebp + 8]
            call 0x437230
        first_advance:
            add esi, {STRIDE}
            inc ebx
            jmp next
        invalid:
            add esp, 8
            xor eax, eax
            mov edx, 1
            jmp walker_exit
        verify_failed:
            add esp, 8
            xor eax, eax
            mov edx, 2
            jmp walker_exit
        walk_done:
            cmp dword ptr [esp + 4], 0
            je walk_success
            mov esi, dword ptr [ebp + 8]
            xor ebx, ebx
        verify_next:
            cmp ebx, dword ptr [ebp + 12]
            jae walk_success
            cmp byte ptr [esi + 0x28], 0
            je verify_advance
            cmp dword ptr [esi + 0x344], 0
            jle verify_advance
            cmp dword ptr [esi + 0x36C], 199
            je verify_advance
            mov edi, 5
            lea edx, [esi + 0x3BC]
        verify_values:
            cmp dword ptr [edx], 0
            jl verify_failed
            cmp dword ptr [edx], 100
            jg verify_failed
            add edx, 4
            dec edi
            jne verify_values
            cmp dword ptr [esi + 0x3BC], 100
            jne verify_failed
            cmp dword ptr [esi + 0x3C0], 100
            jne verify_failed
            cmp dword ptr [esi + 0x3C4], 100
            jne verify_failed
            cmp dword ptr [esi + 0x3C8], 100
            jne verify_failed
            cmp dword ptr [esi + 0x3CC], 100
            jne verify_failed
        verify_advance:
            add esi, {STRIDE}
            inc ebx
            jmp verify_next
        walk_success:
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
    _put(section, WALKER_OFFSET, walker, "mastery walker")

    confirm = asm(
        f"""
            push ebp
            mov ebp, esp
            push ebx
            push esi
            push edi
            push 0x{strings['user32']:X}
            call dword ptr [0x457010]
            test eax, eax
            jz cancel
            push 0x{strings['message_box']:X}
            push eax
            call dword ptr [0x4570D4]
            test eax, eax
            jz cancel
            push 1
            push 0x{strings['caption']:X}
            push 0x{strings['warning']:X}
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
        confirm_va,
    )
    _put(section, CONFIRM_OFFSET, confirm, "confirmation helper")

    show_menu = asm(
        f"""
            push ebx
            push esi
            push 0x{strings['candidate_dll']:X}
            call dword ptr [0x457010]
            test eax, eax
            jz unavailable
            push 0x{strings['menu_export']:X}
            push eax
            call dword ptr [0x4570D4]
            test eax, eax
            jz unavailable
            call eax
            pop esi
            pop ebx
            ret
        unavailable:
            mov eax, -1
            pop esi
            pop ebx
            ret
        """,
        show_menu_va,
    )
    _put(section, SHOW_MENU_OFFSET, show_menu, "menu resolver")

    # stdcall show_result(status, changed, retained_export), ret 12. The
    # export pointer is resolved and validated before any charge or write.
    show_result = asm(
        f"""
            mov eax, dword ptr [esp + 12]
            test eax, eax
            jz result_done
            push dword ptr [esp + 8]
            push dword ptr [esp + 8]
            call eax
        result_done:
            ret 12
        """,
        show_result_va,
    )
    _put(section, SHOW_RESULT_OFFSET, show_result, "result resolver")

    metadata = {
        "section_sha256": sha(section),
        "entry_sha256": sha(entry),
        "walker_sha256": sha(walker),
        "confirmation_sha256": sha(confirm),
        "menu_resolver_sha256": sha(show_menu),
        "result_resolver_sha256": sha(show_result),
        "offsets": {
            "handler": f"0x{TECH_HANDLER_OFFSET:X}",
            "constructor": f"0x{TECH_CONSTRUCTOR_OFFSET:X}",
            "entry": f"0x{ENTRY_OFFSET:X}",
            "walker": f"0x{WALKER_OFFSET:X}",
            "confirmation": f"0x{CONFIRM_OFFSET:X}",
            "menu_resolver": f"0x{SHOW_MENU_OFFSET:X}",
            "result_resolver": f"0x{SHOW_RESULT_OFFSET:X}",
            "strings": f"0x{STRINGS_OFFSET:X}",
        },
        "strings": {key: f"0x{value:X}" for key, value in strings.items()},
        "absolute_references": [
            "0x457010 LoadLibraryA IAT",
            "0x4570D4 GetProcAddress IAT",
            "0x437230 native skill writer",
            "0x44AF03 stock allocation helper",
            "0x4019B0 stock button constructor",
            "0x4015B0 stock button styling",
            "0x40AB80 stock child attachment",
        ],
        "rel32_references": [
            "handler -> entry",
            "handler -> stock continuation 0x435AB5",
            "constructor -> 0x44AF03/0x4019B0/0x4015B0/0x40AB80",
            "entry -> menu/walker/confirmation/result",
            "walker -> native skill writer 0x437230",
        ],
        "iat_references": ["0x457010 LoadLibraryA", "0x4570D4 GetProcAddress"],
        "pool_transport": {
            "state": "[Tech+0x0C]",
            "pool": "[state+0xADE8]",
            "null_guard": "state and pool are rejected before every walk",
            "bound": BOUND,
            "stride": f"0x{STRIDE:X}",
        },
        "post_verify_pass": {
            "mode": 1,
            "scope": "complete second read-only pass over all 256 records after the entire native-write pass",
            "reacquire": "reload [EBP+8] and reset physical index to zero",
            "eligibility": "same occupied/health/special guards as the first pass",
            "value_validation": "same five-skill range checks, then every eligible skill must equal exact Float32 100",
            "failure": "EDX=2 on any invalid or non-100 eligible record; EDX=0 only after the full pass",
        },
        "rollback_limit": (
            "Native skill writes are not rolled back if the process is interrupted "
            "or post-write verification fails; no deduction is made on failure."
        ),
        "composition_audit": {
            "base_identity": "active Origins/Cure feature vv1_enable_origins_exclusive_features",
            "combined_identity": "active Origins/Cure bytes plus the candidate .vv1fm append and guarded Full Mastery hook bytes",
            "uninstall_identity": "remove only the candidate .vv1fm append/header/hooks and restore the active Origins/Cure bytes",
            "proof": "combined uninstall must equal the active Origins/Cure base byte-for-byte",
            "shared_hook_policy": "ordinary catalog composition remains collision-fail-closed; the recertification bundle uses an explicit guarded audit composition only",
            "bundle_output": "outputs/vv1-full-mastery-c71-recert",
            "identity_files": [
                "active-origins-cure-base/Virtual Villagers - A New Home - Active Origins.exe",
                "combined-origins-cure-full-mastery/Virtual Villagers - A New Home - Full Mastery.exe",
                "uninstalled-full-mastery/Virtual Villagers - A New Home - Active Origins.exe",
                "composition-proof.json",
            ],
            "candidate_enabled": False,
        },
        "base_relocations": [],
    }
    return bytes(section), metadata


def build() -> tuple[dict[str, object], dict[str, object]]:
    original = STOCK.read_bytes()
    if len(original) != 581_632:
        raise RuntimeError("VV1 stock size mismatch")
    expected_sha = "1EC790B927741081D5CE13A48FB76983A4FD4336EA08F89317872643760AF03D"
    if sha(original) != expected_sha:
        raise RuntimeError("VV1 stock SHA-256 mismatch")
    if not COMPANION.is_file():
        raise RuntimeError("build the disabled candidate companion DLL first")

    pe = _pe_layout(original)
    if pe["section_count"] != 5:
        raise RuntimeError("unexpected stock section count")
    if len(original) != APPEND_OFFSET:
        raise RuntimeError("unexpected stock file end")
    if struct.unpack_from("<I", original, pe["size_of_image_offset"])[0] != OLD_SIZE_OF_IMAGE:
        raise RuntimeError("unexpected stock SizeOfImage")
    if original[0x52DC9:0x52DC9 + 11] != bytes.fromhex("68082E4800FF1510704500"):
        raise RuntimeError("LoadLibraryA IAT anchor guard mismatch")
    if original[0x52DDE:0x52DDE + 14] != bytes.fromhex("8B35D470450068FC2D480057FFD6"):
        raise RuntimeError("GetProcAddress IAT anchor guard mismatch")

    section, artifact = build_section()
    header = (
        b".vv1fm\0\0"
        + struct.pack(
            "<IIIIIIHHI",
            SECTION_SIZE,
            SECTION_RVA,
            SECTION_SIZE,
            APPEND_OFFSET,
            0,
            0,
            0,
            0,
            0x60000020,
        )
    )
    if len(header) != 40:
        raise RuntimeError("section header length mismatch")
    header_before = original[pe["section_header_offset"]:pe["section_header_offset"] + 40]
    if header_before != b"\0" * 40:
        raise RuntimeError("new section header slot is not empty")

    constructor_after = rel32_jump(0x4358DC, SECTION_VA + TECH_CONSTRUCTOR_OFFSET)
    handler_after = rel32_jump(0x435AB0, SECTION_VA + TECH_HANDLER_OFFSET)
    manifest: dict[str, object] = {
        "id": "vv1_full_mastery_all_stage_a_candidate",
        "game_id": "vv1",
        "name": "Grant Full Mastery to All Villagers",
        "enabled": False,
        "certification_status": "disabled Stage-A emitted candidate awaiting independent Sol byte certification",
        "description": (
            "Uncertified disabled command-7-only Stage-A candidate. Commands 6/8, "
            "ownership, Remove, Golden Child, and Island Event paths are absent."
        ),
        "dependencies": [],
        "companion_files": [
            {
                "source": "data/candidates/VVFP VV1 Full Mastery Candidate.dll",
                "destination": "VVFP VV1 Full Mastery Candidate.dll",
                "sha256": sha(COMPANION.read_bytes()),
            }
        ],
        "patches": [
            {
                "offset": "0x358DC",
                "before": "8B4C24205F",
                "after": constructor_after.hex().upper(),
                "purpose": "append the isolated command-7 Origins Upgrades button",
            },
            {
                "offset": "0x35AB0",
                "before": "837C240408",
                "after": handler_after.hex().upper(),
                "purpose": "route only the isolated command-7 button",
            },
        ],
        "pe_append_transaction": {
            "owner": "vv1_full_mastery_all_stage_a_candidate",
            "append_length": SECTION_SIZE,
            "removal_policy": "restore both exact hooks, guarded header fields, and exact appended tail before truncation",
            "layouts": {},
        },
        "transaction_contract": {
            "command": 7,
            "price": PRICE,
            "ownership": None,
            "record_bound": BOUND,
            "eligibility": ["byte +0x28 != 0", "signed dword +0x344 > 0", "dword +0x36C != 199"],
            "skills": ["+0x3BC Parenting/code2", "+0x3C0 Building/code4", "+0x3C4 Farming/code1", "+0x3C8 Healing/code5", "+0x3CC Research/code3"],
            "target": 100,
            "native_writer": "sub_437230 once for each valid below-100 skill",
            "pool_transport": "state=[Tech+0x0C], pool=[state+0xADE8]; null is fail-closed",
            "post_verify": "mode 1 reacquires [EBP+8] and performs a complete second read-only pass over all 256 records after native writes; identical eligibility/range validation and exact Float32 100 for every eligible skill are required before deduction",
            "rollback_limit": "partial native writes may remain after interruption or failed post-verification; no charge is made",
        },
        "composition_audit": {
            "base_identity": "active Origins/Cure feature vv1_enable_origins_exclusive_features",
            "combined_identity": "active Origins/Cure bytes plus the candidate .vv1fm append and guarded Full Mastery hook bytes",
            "uninstall_identity": "remove only the candidate .vv1fm append/header/hooks and restore the active Origins/Cure bytes",
            "proof": "combined uninstall must equal the active Origins/Cure base byte-for-byte",
            "shared_hook_policy": "ordinary catalog composition remains collision-fail-closed; the recertification bundle uses an explicit guarded audit composition only",
            "bundle_output": "outputs/vv1-full-mastery-c71-recert",
            "identity_files": [
                "active-origins-cure-base/Virtual Villagers - A New Home - Active Origins.exe",
                "combined-origins-cure-full-mastery/Virtual Villagers - A New Home - Full Mastery.exe",
                "uninstalled-full-mastery/Virtual Villagers - A New Home - Active Origins.exe",
                "composition-proof.json",
            ],
            "candidate_enabled": False,
        },
    }
    layouts = manifest["pe_append_transaction"]["layouts"]  # type: ignore[index]
    for mode in MODES:
        layouts[mode] = {  # type: ignore[index]
            "original_file_size": f"0x{APPEND_OFFSET:X}",
            "append_offset": f"0x{APPEND_OFFSET:X}",
            "append_length": SECTION_SIZE,
            "append_bytes": section.hex().upper(),
            "virtual_address": f"0x{SECTION_VA:X}",
            "purpose": "append the disabled command-7-only .vv1fm RX section",
            "header_patches": [
                {
                    "offset": f"0x{pe['section_count_offset']:X}",
                    "before": "0500",
                    "after": "0600",
                    "purpose": "add the disabled candidate .vv1fm section",
                },
                {
                    "offset": f"0x{pe['size_of_image_offset']:X}",
                    "before": struct.pack("<I", OLD_SIZE_OF_IMAGE).hex().upper(),
                    "after": struct.pack("<I", NEW_SIZE_OF_IMAGE).hex().upper(),
                    "purpose": "extend SizeOfImage for .vv1fm",
                },
                {
                    "offset": f"0x{pe['section_header_offset']:X}",
                    "before": header_before.hex().upper(),
                    "after": header.hex().upper(),
                    "purpose": "install guarded .vv1fm RX section header",
                },
            ],
        }

    artifact.update(
        {
            "acceptance_commit": "1b3e4565d4168457c00404a12ed30cfb777c86e9",
            "semantic_commit": "b328c1b1c76f68ade762ec139ee6c2e08ce54a96",
            "correction_audit_commit": "284b8cad9e876e53eefdd5ec909d25dfd336b398",
            "source": {"size": len(original), "sha256": expected_sha},
            "companion": {
                "path": "data/candidates/VVFP VV1 Full Mastery Candidate.dll",
                "size": COMPANION.stat().st_size,
                "sha256": sha(COMPANION.read_bytes()),
                "exports": export_map(COMPANION.read_bytes()),
            },
            "section": {
                "name": ".vv1fm",
                "raw_offset": f"0x{APPEND_OFFSET:X}",
                "rva": f"0x{SECTION_RVA:X}",
                "va": f"0x{SECTION_VA:X}",
                "virtual_size": f"0x{SECTION_SIZE:X}",
                "raw_size": f"0x{SECTION_SIZE:X}",
                "characteristics": "0x60000020 executable/readable/non-writable",
                "old_size_of_image": f"0x{OLD_SIZE_OF_IMAGE:X}",
                "new_size_of_image": f"0x{NEW_SIZE_OF_IMAGE:X}",
                "old_file_length": f"0x{APPEND_OFFSET:X}",
                "new_file_length": f"0x{APPEND_OFFSET + SECTION_SIZE:X}",
            },
            "hooks": {
                "constructor": {
                    "offset": "0x358DC",
                    "before": "8B4C24205F",
                    "after": constructor_after.hex().upper(),
                },
                "handler": {
                    "offset": "0x35AB0",
                    "before": "837C240408",
                    "after": handler_after.hex().upper(),
                },
            },
            "confirmation": {
                "abi": "no arguments; preserves EBP/EBX/ESI/EDI; EAX=1 only explicit IDOK",
                "load_library_iat": "0x457010",
                "get_proc_address_iat": "0x4570D4",
                "return_matrix": {"0": 0, "1": 1, "2": 0, "arbitrary_non_1": 0},
            },
            "command_abi": {
                "entry": "stock thiscall Tech-screen receiver arrives in ECX; entry saves old ESI, transports ECX to ESI, and restores old ESI on exit",
                "walker": "cdecl(pool,bound,mode); mode0 dry-run, mode1 native commit followed by a complete second 256-record read-only exact-100 pass; EAX changed, EDX 1=first-pass invalid/2=second-pass mismatch; no fourth entry walk; preserves EBX/ESI/EDI/EBP",
                "result": "stdcall(status,changed,retained_export); ret 12; retained export itself is stdcall(status,changed), ret 8",
            },
            "modes": list(MODES),
            "allowed_modes": list(MODES),
            "rejected_modes": list(REJECTED_MODES),
        }
    )
    return manifest, artifact


def main() -> None:
    requested_modes = tuple(sys.argv[1:]) or MODES
    for mode in requested_modes:
        require_supported_mode(mode)
    manifest, artifact = build()
    from vv_fun_patcher import FunPatch, load_builds, load_fun_patches, render_patched_bytes

    build_record = next(item for item in load_builds() if item.id == "vv1")
    candidate = FunPatch(manifest)
    others = [
        item
        for item in load_fun_patches()
        if item.game_id == "vv1"
        and item.id not in {manifest["id"], "vv1_enable_origins_exclusive_features"}
    ]
    rendered: dict[str, object] = {}
    for mode in requested_modes:
        baseline, _ = render_patched_bytes(STOCK, build_record, mode)
        image, applied = render_patched_bytes(
            STOCK,
            build_record,
            mode,
            _fun_patches_override=[candidate],
        )
        rendered[mode] = {
            "baseline_sha256": sha(baseline),
            "candidate_sha256": sha(image),
            "size": len(image),
            "pe_checksum": f"0x{struct.unpack_from('<I', image, _pe_layout(image)['checksum_offset'])[0]:08X}",
            "owners": sorted({item["owner"] for item in applied}),
        }
        all_image, all_applied = render_patched_bytes(
            STOCK,
            build_record,
            mode,
            _fun_patches_override=[candidate, *others],
        )
        rendered[mode]["all_current_vv1_sha256"] = sha(all_image)
        rendered[mode]["all_current_vv1_owners"] = sorted(
            {item["owner"] for item in all_applied}
        )
        rendered[mode]["collision_status"] = "PASS"
        rendered[mode]["uninstall_target_sha256"] = sha(baseline)
    artifact["rendered_candidates"] = rendered
    MANIFEST_OUT.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    MAP_OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    DOC_OUT.write_text(
        "# VV1 Full Mastery disabled Stage-A candidate\n\n"
        "This catalog-hidden artifact is generated from disassembly acceptance "
        "contract `1b3e4565d4168457c00404a12ed30cfb777c86e9` and applies the "
        "pre-resolved-result correction from certification report "
        "`284b8cad9e876e53eefdd5ec909d25dfd336b398`. It remains "
        "**disabled pending independent Sol emitted-byte certification**.\n\n"
        f"- Section SHA-256: `{artifact['section_sha256']}`\n"
        f"- Companion SHA-256: `{artifact['companion']['sha256']}`\n"
        f"- Entry SHA-256: `{artifact['entry_sha256']}`\n"
        f"- Walker SHA-256: `{artifact['walker_sha256']}`\n"
        f"- Confirmation SHA-256: `{artifact['confirmation_sha256']}`\n\n"
        "The candidate appends `.vv1fm`; it does not reuse the overlapping old "
        "Origins payload. It "
        "adds command 7 only, with commands 6/8, ownership, Remove, Gong, and "
        "Island Event interception absent. The result export is resolved and "
        "validated before any charge or native writer call, then retained through "
        "commit. The physical pool is reacquired from `state=[Tech+0x0C]` and "
        "`pool=[state+0xADE8]` with null fail-closed guards, preserving 256 "
        "records at stride `0x3D8`. A complete mode-0 dry run and no-change test "
        "precede the unsigned funds check and explicit 1,000,000-point confirmation. "
        "Mode 1 performs the complete native write pass, then reacquires the pool "
        "and performs a second read-only pass over all 256 records with identical "
        "eligibility/range checks and exact-100 requirements before the single "
        "deduction; there is no mode-2 entry walk. A "
        "process interruption or failed verification cannot safely roll back "
        "partial native writes, so no charge is made. Collection Progression and "
        "Immediate Fixed are the only allowed modes; Expanded-256 is rejected "
        "before output creation. The ignored C71 recertification bundle emits the "
        "active Origins/Cure base, combined Origins/Cure plus Full Mastery audit "
        "identity, Full Mastery uninstall identity, and a proof manifest whose "
        "uninstall hash equals the active base hash. The raw manifest and "
        "complete map are under `data/candidates/`.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
