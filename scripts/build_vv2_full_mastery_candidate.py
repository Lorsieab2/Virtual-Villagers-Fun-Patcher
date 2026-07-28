"""Generate the disabled VV2 command-7 Full Mastery Stage-A candidate."""

from __future__ import annotations

import hashlib
import json
import struct
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Lost Children.exe"
OUT_DIR = ROOT / "data" / "candidates"
MANIFEST_OUT = OUT_DIR / "vv2_full_mastery_all_candidate.json"
MAP_OUT = OUT_DIR / "vv2_full_mastery_all_candidate_map.json"
DOC_OUT = ROOT / "docs" / "vv2-full-mastery-stage-a-candidate.md"
COMPANION = OUT_DIR / "VVFP VV2 Full Mastery Candidate.dll"

sys.path.insert(0, str(ROOT / ".tools" / "keystone"))
sys.path.insert(0, str(ROOT / ".tools" / "keystone-runtime"))
sys.path.insert(0, str(ROOT / "src"))
from keystone import KS_ARCH_X86, KS_MODE_32, Ks  # noqa: E402


IMAGE_BASE = 0x400000
APPEND_OFFSET = 0xB1000
SECTION_RVA = 0xB3000
SECTION_VA = IMAGE_BASE + SECTION_RVA
SECTION_SIZE = 0x2000
OLD_SIZE_OF_IMAGE = 0xB3000
NEW_SIZE_OF_IMAGE = 0xB5000
TECH_HANDLER_OFFSET = 0x000
TECH_CONSTRUCTOR_OFFSET = 0x040
ENTRY_OFFSET = 0x100
WALKER_OFFSET = 0x380
TELEMETRY_OFFSET = 0x520
CONFIRM_OFFSET = 0x680
SHOW_MENU_OFFSET = 0x740
SHOW_RESULT_OFFSET = 0x7C0
STRINGS_OFFSET = 0x900
PRICE = 1_000_000
BOUND = 256
STRIDE = 0xE48C

MODES = (
    "collection_progression",
    "immediate_fixed",
    "experimental_expanded_256",
    "experimental_expanded_256_progression",
)


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
        ("candidate_dll", b"VVFP VV2 Full Mastery Candidate.dll"),
        ("menu_export", b"ShowVV2FullMasteryMenu"),
        ("result_export", b"ShowVV2FullMasteryResult"),
        ("user32", b"user32.dll"),
        ("message_box", b"MessageBoxA"),
        (
            "warning",
            b"This upgrade makes permanent changes to your village. Are you sure "
            b"you want to purchase it? Press OK to confirm, or Cancel.",
        ),
        ("caption", b"Origins Upgrades"),
    ):
        strings[key], cursor = _add_string(section, cursor, value)

    handler_va = SECTION_VA + TECH_HANDLER_OFFSET
    constructor_va = SECTION_VA + TECH_CONSTRUCTOR_OFFSET
    entry_va = SECTION_VA + ENTRY_OFFSET
    walker_va = SECTION_VA + WALKER_OFFSET
    telemetry_va = SECTION_VA + TELEMETRY_OFFSET
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
            jmp 0x4437C5
        """,
        handler_va,
    )
    _put(section, TECH_HANDLER_OFFSET, handler, "tech handler")

    constructor = asm(
        f"""
            push 0x14
            call 0x467F83
            add esp, 4
            test eax, eax
            je done
            push 0
            push esi
            push 563
            push 138
            push 0x4763E8
            push 2
            mov ecx, eax
            call 0x4019D0
            mov edi, eax
            push 0
            push 0xFF555555
            push 0xFF555555
            push 0xFF000000
            push 0x{strings['button']:X}
            mov ecx, edi
            call 0x4015D0
            push edi
            mov ecx, esi
            call 0x40B560
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

    # ESI is the stock Tech-screen object. The 0x100-byte local snapshot uses
    # 0=unchanged, 1=changed+unmarked-before, 2=changed+already-marked.
    entry = asm(
        f"""
            push ebp
            mov ebp, esp
            push ebx
            push esi
            mov esi, ecx
            push edi
            sub esp, 0x124
            call 0x{show_menu_va:X}
            cmp eax, 7
            jne done
            mov ebx, eax
            mov edi, dword ptr [esi + 0x0C]
            lea edx, [edi + 0x2EADC]
            cmp dword ptr [edx], {PRICE}
            jb insufficient
            lea eax, [ebp - 0x124]
            push eax
            push 0
            push {BOUND}
            push dword ptr [esi + 0x10]
            call 0x{walker_va:X}
            add esp, 16
            test eax, eax
            jz no_change
            call 0x{confirm_va:X}
            cmp eax, 1
            jne done
            mov edi, dword ptr [esi + 0x0C]
            lea edx, [edi + 0x2EADC]
            cmp dword ptr [edx], {PRICE}
            jb insufficient
            lea eax, [ebp - 0x124]
            push eax
            push 0
            push {BOUND}
            push dword ptr [esi + 0x10]
            call 0x{walker_va:X}
            add esp, 16
            test eax, eax
            jz no_change
            mov edi, dword ptr [esi + 0x0C]
            lea edx, [edi + 0x2EADC]
            sub dword ptr [edx], {PRICE}
            mov dword ptr [ebp - 0x18], eax
            mov eax, dword ptr [esi + 0x10]
            mov dword ptr [ebp - 0x1C], eax
            lea edi, [ebp - 0x124]
            xor eax, eax
            mov ecx, 64
            rep stosd
            lea eax, [ebp - 0x124]
            push eax
            push 1
            push {BOUND}
            push dword ptr [esi + 0x10]
            call 0x{walker_va:X}
            add esp, 16
            mov dword ptr [ebp - 0x18], eax
            call 0x44D4C0
            lea eax, [ebp - 0x124]
            push eax
            push {BOUND}
            push dword ptr [ebp - 0x1C]
            call 0x{telemetry_va:X}
            add esp, 12
            push edx
            push ecx
            push dword ptr [ebp - 0x18]
            push 1
            call 0x{show_result_va:X}
            jmp done
        no_change:
            push 0
            push 0
            push 0
            push 0
            call 0x{show_result_va:X}
            jmp done
        insufficient:
            push 0
            push 0
            push 0
            push 2
            call 0x{show_result_va:X}
        done:
            add esp, 0x124
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

    # cdecl walker(base, bound, mode, snapshot); EAX=changed count.
    walker = asm(
        f"""
            push ebp
            mov ebp, esp
            push ebx
            push esi
            push edi
            mov esi, dword ptr [ebp + 8]
            mov ecx, dword ptr [ebp + 12]
            mov edx, dword ptr [ebp + 16]
            mov edi, dword ptr [ebp + 20]
            xor eax, eax
            xor ebx, ebx
        next:
            cmp ebx, ecx
            jae walk_done
            cmp byte ptr [esi + 0x30], 0
            je advance
            cmp dword ptr [esi + 0x52C], 0
            jle advance
            cmp byte ptr [esi + 0x558], 0
            jne advance
            cmp dword ptr [esi + 0x7E4], 100
            jne changed
            cmp dword ptr [esi + 0x7E8], 100
            jne changed
            cmp dword ptr [esi + 0x7EC], 100
            jne changed
            cmp dword ptr [esi + 0x7F0], 100
            jne changed
            cmp dword ptr [esi + 0x7F4], 100
            je advance
        changed:
            inc eax
            test edx, edx
            jz advance
            mov byte ptr [edi + ebx], 1
            cmp byte ptr [esi + 0x7FC], 0
            je stores
            mov byte ptr [edi + ebx], 2
        stores:
            cmp dword ptr [esi + 0x7E4], 100
            je s2
            mov dword ptr [esi + 0x7E4], 100
        s2:
            cmp dword ptr [esi + 0x7E8], 100
            je s3
            mov dword ptr [esi + 0x7E8], 100
        s3:
            cmp dword ptr [esi + 0x7EC], 100
            je s4
            mov dword ptr [esi + 0x7EC], 100
        s4:
            cmp dword ptr [esi + 0x7F0], 100
            je s5
            mov dword ptr [esi + 0x7F0], 100
        s5:
            cmp dword ptr [esi + 0x7F4], 100
            je advance
            mov dword ptr [esi + 0x7F4], 100
        advance:
            add esi, {STRIDE}
            inc ebx
            jmp next
        walk_done:
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

    # cdecl telemetry(base,bound,snapshot); ECX=new markers, EDX=unmarked.
    telemetry = asm(
        f"""
            push ebp
            mov ebp, esp
            push ebx
            push esi
            push edi
            mov esi, dword ptr [ebp + 8]
            mov edi, dword ptr [ebp + 16]
            mov ebx, dword ptr [ebp + 12]
            xor eax, eax
            xor ecx, ecx
            xor edx, edx
        tnext:
            cmp eax, ebx
            jae tdone
            cmp byte ptr [edi + eax], 0
            je tadvance
            cmp byte ptr [esi + 0x7FC], 0
            jne marked
            xor ebp, ebp
            cmp dword ptr [esi + 0x7E4], 88
            jl c2
            inc ebp
        c2:
            cmp dword ptr [esi + 0x7E8], 88
            jl c3
            inc ebp
        c3:
            cmp dword ptr [esi + 0x7EC], 88
            jl c4
            inc ebp
        c4:
            cmp dword ptr [esi + 0x7F0], 88
            jl c5
            inc ebp
        c5:
            cmp dword ptr [esi + 0x7F4], 88
            jl check_three
            inc ebp
        check_three:
            cmp ebp, 3
            jb tadvance
            inc edx
            jmp tadvance
        marked:
            cmp byte ptr [edi + eax], 1
            jne tadvance
            inc ecx
        tadvance:
            add esi, {STRIDE}
            inc eax
            jmp tnext
        tdone:
            pop edi
            pop esi
            pop ebx
            pop ebp
            ret
        """,
        telemetry_va,
    )
    _put(section, TELEMETRY_OFFSET, telemetry, "telemetry walker")

    confirm = asm(
        f"""
            push ebp
            mov ebp, esp
            push ebx
            push esi
            push edi
            push 0x{strings['user32']:X}
            call dword ptr [0x474010]
            test eax, eax
            jz cancel
            push 0x{strings['message_box']:X}
            push eax
            call dword ptr [0x4740D4]
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
            call dword ptr [0x474010]
            test eax, eax
            jz unavailable
            push 0x{strings['menu_export']:X}
            push eax
            call dword ptr [0x4740D4]
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

    # stdcall show_result(status, changed, new_markers, unmarked), ret 16.
    show_result = asm(
        f"""
            push ebx
            push esi
            push 0x{strings['candidate_dll']:X}
            call dword ptr [0x474010]
            test eax, eax
            jz result_done
            push 0x{strings['result_export']:X}
            push eax
            call dword ptr [0x4740D4]
            test eax, eax
            jz result_done
            push dword ptr [esp + 0x18]
            push dword ptr [esp + 0x18]
            push dword ptr [esp + 0x18]
            push dword ptr [esp + 0x18]
            call eax
        result_done:
            pop esi
            pop ebx
            ret 16
        """,
        show_result_va,
    )
    _put(section, SHOW_RESULT_OFFSET, show_result, "result resolver")

    metadata = {
        "section_sha256": sha(section),
        "entry_sha256": sha(entry),
        "walker_sha256": sha(walker),
        "telemetry_sha256": sha(telemetry),
        "confirmation_sha256": sha(confirm),
        "menu_resolver_sha256": sha(show_menu),
        "result_resolver_sha256": sha(show_result),
        "offsets": {
            "handler": f"0x{TECH_HANDLER_OFFSET:X}",
            "constructor": f"0x{TECH_CONSTRUCTOR_OFFSET:X}",
            "entry": f"0x{ENTRY_OFFSET:X}",
            "walker": f"0x{WALKER_OFFSET:X}",
            "telemetry": f"0x{TELEMETRY_OFFSET:X}",
            "confirmation": f"0x{CONFIRM_OFFSET:X}",
            "menu_resolver": f"0x{SHOW_MENU_OFFSET:X}",
            "result_resolver": f"0x{SHOW_RESULT_OFFSET:X}",
            "strings": f"0x{STRINGS_OFFSET:X}",
        },
        "strings": {key: f"0x{value:X}" for key, value in strings.items()},
        "absolute_references": [
            "0x474010 LoadLibraryA IAT",
            "0x4740D4 GetProcAddress IAT",
            "0x44D4C0 native Elder evaluator",
            "0x467F83 stock allocation helper",
            "0x4019D0 stock button constructor",
            "0x4015D0 stock button styling",
            "0x40B560 stock child attachment",
        ],
        "rel32_references": [
            "handler -> entry",
            "handler -> stock continuation 0x4437C5",
            "constructor -> 0x467F83/0x4019D0/0x4015D0/0x40B560",
            "entry -> menu/walker/confirmation/0x44D4C0/telemetry/result",
        ],
        "iat_references": ["0x474010 LoadLibraryA", "0x4740D4 GetProcAddress"],
        "base_relocations": [],
    }
    return bytes(section), metadata


def build() -> tuple[dict[str, object], dict[str, object]]:
    original = STOCK.read_bytes()
    if len(original) != 724_992:
        raise RuntimeError("VV2 stock size mismatch")
    expected_sha = "46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677"
    if sha(original) != expected_sha:
        raise RuntimeError("VV2 stock SHA-256 mismatch")
    if not COMPANION.is_file():
        raise RuntimeError("build the disabled candidate companion DLL first")

    pe = _pe_layout(original)
    if pe["section_count"] != 5:
        raise RuntimeError("unexpected stock section count")
    if len(original) != APPEND_OFFSET:
        raise RuntimeError("unexpected stock file end")
    if struct.unpack_from("<I", original, pe["size_of_image_offset"])[0] != OLD_SIZE_OF_IMAGE:
        raise RuntimeError("unexpected stock SizeOfImage")
    if original[0x6FE49:0x6FE49 + 11] != bytes.fromhex("6838104900FF1510404700"):
        raise RuntimeError("LoadLibraryA IAT anchor guard mismatch")
    if original[0x6FE5E:0x6FE5E + 14] != bytes.fromhex("8B35D4404700682C10490057FFD6"):
        raise RuntimeError("GetProcAddress IAT anchor guard mismatch")

    section, artifact = build_section()
    header = (
        b".vv2fm\0\0"
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

    constructor_after = rel32_jump(0x4435EF, SECTION_VA + TECH_CONSTRUCTOR_OFFSET)
    handler_after = rel32_jump(0x4437C0, SECTION_VA + TECH_HANDLER_OFFSET)
    manifest: dict[str, object] = {
        "id": "vv2_full_mastery_all_stage_a_candidate",
        "game_id": "vv2",
        "name": "Grant Full Mastery to All Villagers",
        "enabled": False,
        "certification_status": "HARD WITHDRAWN after live Buy crash at walker+0x1E from invalid ESI; disabled pending exact repair and recertification",
        "description": (
            "Withdrawn command-7-only candidate. Live Buy crashed at walker+0x1E "
            "because ESI was invalid before the permanent-change warning. Commands "
            "6/8, ownership, Remove, old .shr transport, Gong, and Island Event "
            "paths remain absent."
        ),
        "dependencies": [],
        "companion_files": [
            {
                "source": "data/candidates/VVFP VV2 Full Mastery Candidate.dll",
                "destination": "VVFP VV2 Full Mastery Candidate.dll",
                "sha256": sha(COMPANION.read_bytes()),
            }
        ],
        "patches": [
            {
                "offset": "0x435EF",
                "before": "8B4C24205F",
                "after": constructor_after.hex().upper(),
                "purpose": "append the isolated command-7 Origins Upgrades button",
            },
            {
                "offset": "0x437C0",
                "before": "837C240408",
                "after": handler_after.hex().upper(),
                "purpose": "route only the isolated command-7 button",
            },
        ],
        "pe_append_transaction": {
            "owner": "vv2_full_mastery_all_stage_a_candidate",
            "append_length": SECTION_SIZE,
            "removal_policy": "restore both exact hooks, guarded header fields, and exact appended tail before truncation",
            "layouts": {},
        },
        "transaction_contract": {
            "command": 7,
            "price": PRICE,
            "ownership": None,
            "record_bound": BOUND,
            "eligibility": ["byte +0x30 != 0", "signed dword +0x52C > 0", "byte +0x558 == 0"],
            "skills": ["+0x7E4", "+0x7E8", "+0x7EC", "+0x7F0", "+0x7F4"],
            "target": 100,
            "native_evaluator": "sub_44D4C0 exactly once after commit",
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
            "purpose": "append the disabled command-7-only .vv2fm RX section",
            "header_patches": [
                {
                    "offset": f"0x{pe['section_count_offset']:X}",
                    "before": "0500",
                    "after": "0600",
                    "purpose": "add the disabled candidate .vv2fm section",
                },
                {
                    "offset": f"0x{pe['size_of_image_offset']:X}",
                    "before": struct.pack("<I", OLD_SIZE_OF_IMAGE).hex().upper(),
                    "after": struct.pack("<I", NEW_SIZE_OF_IMAGE).hex().upper(),
                    "purpose": "extend SizeOfImage for .vv2fm",
                },
                {
                    "offset": f"0x{pe['section_header_offset']:X}",
                    "before": header_before.hex().upper(),
                    "after": header.hex().upper(),
                    "purpose": "install guarded .vv2fm RX section header",
                },
            ],
        }

    artifact.update(
        {
            "acceptance_commit": "93d69a7826d3c7260ea18e1467597e7580ddbae9",
            "audit_commit": "b5183ca0564de3dca84590254cf275f6ce4db255",
            "source": {"size": len(original), "sha256": expected_sha},
            "companion": {
                "path": "data/candidates/VVFP VV2 Full Mastery Candidate.dll",
                "size": COMPANION.stat().st_size,
                "sha256": sha(COMPANION.read_bytes()),
                "exports": export_map(COMPANION.read_bytes()),
            },
            "section": {
                "name": ".vv2fm",
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
                    "offset": "0x435EF",
                    "before": "8B4C24205F",
                    "after": constructor_after.hex().upper(),
                },
                "handler": {
                    "offset": "0x437C0",
                    "before": "837C240408",
                    "after": handler_after.hex().upper(),
                },
            },
            "confirmation": {
                "abi": "no arguments; preserves EBP/EBX/ESI/EDI; EAX=1 only explicit IDOK",
                "load_library_iat": "0x474010",
                "get_proc_address_iat": "0x4740D4",
                "return_matrix": {"0": 0, "1": 1, "2": 0, "arbitrary_non_1": 0},
            },
            "command_abi": {
                "entry": "stock thiscall Tech-screen receiver arrives in ECX; entry saves old ESI, transports ECX to ESI, and restores old ESI on exit; menu result command is kept in EBX; bound is an independent stack argument",
                "walker": "cdecl(base,bound,mode,snapshot); EAX changed; preserves EBX/ESI/EDI/EBP",
                "telemetry": "cdecl(base,bound,snapshot); ECX new markers; EDX changed-but-unmarked",
                "result": "stdcall(status,changed,new_markers,changed_but_unmarked); ret 16",
            },
            "modes": list(MODES),
        }
    )
    return manifest, artifact


def main() -> None:
    manifest, artifact = build()
    from vv_fun_patcher import FunPatch, load_builds, load_fun_patches, render_patched_bytes

    build_record = next(item for item in load_builds() if item.id == "vv2")
    candidate = FunPatch(manifest)
    others = [
        item
        for item in load_fun_patches()
        if item.game_id == "vv2" and item.id != manifest["id"]
    ]
    rendered: dict[str, object] = {}
    for mode in MODES:
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
        rendered[mode]["all_current_vv2_sha256"] = sha(all_image)
        rendered[mode]["all_current_vv2_owners"] = sorted(
            {item["owner"] for item in all_applied}
        )
        rendered[mode]["collision_status"] = "PASS"
        rendered[mode]["uninstall_target_sha256"] = sha(baseline)
    artifact["rendered_candidates"] = rendered
    MANIFEST_OUT.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    MAP_OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    DOC_OUT.write_text(
        "# VV2 Full Mastery withdrawn candidate\n\n"
        "This artifact is generated from disassembly acceptance contract "
        "`93d69a7826d3c7260ea18e1467597e7580ddbae9` and confirmation ABI "
        "`b5183ca0564de3dca84590254cf275f6ce4db255`. It remains "
        "**HARD WITHDRAWN and catalog-hidden** after live Buy crashed at "
        "walker+0x1E with invalid ESI before the warning.\n\n"
        f"- Section SHA-256: `{artifact['section_sha256']}`\n"
        f"- Companion SHA-256: `{artifact['companion']['sha256']}`\n"
        f"- Entry SHA-256: `{artifact['entry_sha256']}`\n"
        f"- Walker SHA-256: `{artifact['walker_sha256']}`\n"
        f"- Confirmation SHA-256: `{artifact['confirmation_sha256']}`\n\n"
        "The candidate appends `.vv2fm`; it never uses or changes `.shr`. It "
        "adds command 7 only, with commands 6/8, ownership, Remove, Gong, and "
        "Island Event interception absent. The raw manifest and complete map "
        "are under `data/candidates/`.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
