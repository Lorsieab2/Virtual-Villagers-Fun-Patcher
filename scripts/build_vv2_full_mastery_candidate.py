"""Generate the disabled VV2 command-7 Full Mastery Stage-A candidate."""

from __future__ import annotations

import hashlib
import argparse
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
AUDIT_OUT = ROOT / "outputs" / "vv2-c138-native-audit"
IMPLEMENTATION_COMMIT = "895340333d55273e599f2dce5ab0db42cbc6d0ab"
AUDIT_STATUS = "pending independent recertification"

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
TELEMETRY_OFFSET = 0x800
CONFIRM_OFFSET = 0xA00
SHOW_MENU_OFFSET = 0xB00
SHOW_RESULT_OFFSET = 0xC00
RESULT_PREFLIGHT_OFFSET = 0xD00
STRINGS_OFFSET = 0x1000
PRICE = 1_000_000
BOUND = 256
STRIDE = 0xE48C
SNAPSHOT_LOW = -0x124
SNAPSHOT_HIGH = -0x25
ENTRY_SCALAR_LOCALS = {
    "result_pointer": -0x10,
    "changed_but_unmarked": -0x14,
    "changed_count": -0x18,
    "manager": -0x1C,
    "state": -0x20,
    "new_elder_count": -0x24,
}
ENTRY_SAVED_SLOTS = {"ebx": -0x04, "esi": -0x08, "edi": -0x0C}


def _assert_entry_scalar_layout() -> None:
    """Reject any scalar local overlapping the snapshot or saved registers."""
    def span(offset: int) -> tuple[int, int]:
        return offset, offset + 3

    snapshot = (SNAPSHOT_LOW, SNAPSHOT_HIGH)
    saved = [span(offset) for offset in ENTRY_SAVED_SLOTS.values()]
    seen: list[tuple[str, tuple[int, int]]] = []
    for name, offset in ENTRY_SCALAR_LOCALS.items():
        current = span(offset)
        if current[0] >= snapshot[0] and current[1] <= snapshot[1]:
            raise ValueError(f"entry scalar {name} overlaps snapshot interval")
        if current[0] <= snapshot[1] and current[1] >= snapshot[0]:
            raise ValueError(f"entry scalar {name} partially overlaps snapshot interval")
        if any(current[0] <= slot[1] and current[1] >= slot[0] for slot in saved):
            raise ValueError(f"entry scalar {name} overlaps saved-register slots")
        for prior_name, prior in seen:
            if current[0] <= prior[1] and current[1] >= prior[0]:
                raise ValueError(f"entry scalar {name} overlaps {prior_name}")
        seen.append((name, current))

MODES = (
    "collection_progression",
    "immediate_fixed",
)
REJECTED_MODES = (
    "experimental_expanded_256",
    "experimental_expanded_256_progression",
)


def resolve_output_paths(output_root: Path | None) -> dict[str, Path]:
    """Resolve every generated destination under one root, or default tracked paths."""
    if output_root is None:
        return {
            "manifest": MANIFEST_OUT,
            "map": MAP_OUT,
            "doc": DOC_OUT,
            "audit_dir": AUDIT_OUT,
            "audit_manifest": AUDIT_OUT / "artifact-manifest.json",
            "audit_source_map": AUDIT_OUT / "source-map.json",
        }

    root = output_root.expanduser().resolve(strict=False)
    tracked_root = ROOT.resolve()
    outputs_root = (ROOT / "outputs").resolve()
    forbidden_tracked = tuple(
        (ROOT / name).resolve()
        for name in ("assets", "data", "docs", "native", "research", "scripts", "src")
    )
    if root == tracked_root or root in tracked_root.parents:
        raise ValueError("output root cannot be the repository or one of its parents")
    inside_outputs = root == outputs_root or outputs_root in root.parents
    if tracked_root in root.parents and not inside_outputs:
        raise ValueError("output root cannot escape into a mixed repository path")
    if any(root == forbidden or forbidden in root.parents for forbidden in forbidden_tracked):
        raise ValueError("output root cannot be inside tracked source/configuration paths")
    if root.exists() and not root.is_dir():
        raise ValueError("output root exists but is not a directory")
    if not root.parent.exists() or not root.parent.is_dir():
        raise ValueError("output root parent directory is missing")

    paths = {
        "manifest": root / "data" / "candidates" / MANIFEST_OUT.name,
        "map": root / "data" / "candidates" / MAP_OUT.name,
        "doc": root / "docs" / DOC_OUT.name,
        "audit_dir": root / "audit",
        "audit_manifest": root / "audit" / "artifact-manifest.json",
        "audit_source_map": root / "audit" / "source-map.json",
    }
    for path in paths.values():
        resolved = path.resolve(strict=False)
        if resolved != root and root not in resolved.parents:
            raise ValueError("resolved output path escapes output root")
    return paths


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
    _assert_entry_scalar_layout()
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
    result_preflight_va = SECTION_VA + RESULT_PREFLIGHT_OFFSET

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

    # The stock manager getter is the sole pool transport.  Its result owns
    # the 256 records at +0x52C (stride 0xE48C) and the tech-point state at
    # +0xE574D4.  The local snapshot is telemetry only; skill writes go
    # exclusively through sub_445430.
    entry = asm(
        f"""
            push ebp
            mov ebp, esp
            push ebx
            push esi
            push edi
            sub esp, 0x124
            lea edi, [ebp - 0x124]
            xor eax, eax
            mov ecx, 64
            rep stosd
            call 0x{show_menu_va:X}
            cmp eax, 7
            jne done
            call 0x{result_preflight_va:X}
            test eax, eax
            jz no_result
            mov dword ptr [ebp - 0x10], eax
            call 0x44F4E0
            test eax, eax
            jz unavailable
            mov dword ptr [ebp - 0x1C], eax
            mov edx, dword ptr [eax + 0xE574D4]
            test edx, edx
            jz unavailable
            mov dword ptr [ebp - 0x20], edx
            lea eax, [ebp - 0x124]
            push eax
            push 0
            push {BOUND}
            push dword ptr [ebp - 0x1C]
            call 0x{walker_va:X}
            add esp, 16
            mov dword ptr [ebp - 0x18], eax
            test eax, eax
            js invalid
            test eax, eax
            jz no_change
            mov edx, dword ptr [ebp - 0x20]
            cmp dword ptr [edx + 0x2EADC], {PRICE}
            jb insufficient
            call 0x{confirm_va:X}
            cmp eax, 1
            jne canceled
            call 0x44F4E0
            test eax, eax
            jz recheck_failed
            mov dword ptr [ebp - 0x1C], eax
            mov edx, dword ptr [eax + 0xE574D4]
            test edx, edx
            jz recheck_failed
            mov dword ptr [ebp - 0x20], edx
            lea eax, [ebp - 0x124]
            push eax
            push 0
            push {BOUND}
            push dword ptr [ebp - 0x1C]
            call 0x{walker_va:X}
            add esp, 16
            test eax, eax
            js invalid
            test eax, eax
            jz recheck_failed
            mov edx, dword ptr [ebp - 0x20]
            cmp dword ptr [edx + 0x2EADC], {PRICE}
            jb insufficient
            lea eax, [ebp - 0x124]
            push eax
            push 1
            push {BOUND}
            push dword ptr [ebp - 0x1C]
            call 0x{walker_va:X}
            add esp, 16
            mov dword ptr [ebp - 0x18], eax
            test eax, eax
            js recheck_failed
            test eax, eax
            jz recheck_failed
            call 0x44F4E0
            test eax, eax
            jz recheck_failed
            mov dword ptr [ebp - 0x1C], eax
            mov edx, dword ptr [eax + 0xE574D4]
            test edx, edx
            jz recheck_failed
            mov dword ptr [ebp - 0x20], edx
            lea eax, [ebp - 0x124]
            push 0
            push 2
            push {BOUND}
            push dword ptr [ebp - 0x1C]
            call 0x{walker_va:X}
            add esp, 16
            test eax, eax
            jz recheck_failed
            mov ecx, dword ptr [ebp - 0x1C]
            call 0x44F4E0
            test eax, eax
            jz recheck_failed
            mov dword ptr [ebp - 0x1C], eax
            mov edx, dword ptr [eax + 0xE574D4]
            test edx, edx
            jz recheck_failed
            mov dword ptr [ebp - 0x20], edx
            mov ecx, dword ptr [ebp - 0x1C]
            call 0x44D4C0
            call 0x44F4E0
            test eax, eax
            jz recheck_failed
            mov dword ptr [ebp - 0x1C], eax
            mov edx, dword ptr [eax + 0xE574D4]
            test edx, edx
            jz recheck_failed
            mov dword ptr [ebp - 0x20], edx
            lea eax, [ebp - 0x124]
            push eax
            push {BOUND}
            mov eax, dword ptr [ebp - 0x1C]
            add eax, 0x52C
            push eax
            call 0x{telemetry_va:X}
            add esp, 12
            mov dword ptr [ebp - 0x24], ecx
            mov dword ptr [ebp - 0x14], edx
            mov edx, dword ptr [ebp - 0x20]
            cmp dword ptr [edx + 0x2EADC], {PRICE}
            jb insufficient
            mov ecx, edx
            push -{PRICE}
            call 0x426290
            push dword ptr [ebp - 0x14]
            push dword ptr [ebp - 0x24]
            push dword ptr [ebp - 0x18]
            push 1
            call dword ptr [ebp - 0x10]
            jmp done
        recheck_failed:
            push 0
            push 0
            push 0
            push 3
            call dword ptr [ebp - 0x10]
            jmp done
        no_change:
            push 0
            push 0
            push 0
            push 0
            call dword ptr [ebp - 0x10]
            jmp done
        insufficient:
            push 0
            push 0
            push 0
            push 2
            call dword ptr [ebp - 0x10]
            jmp done
        canceled:
            push 0
            push 0
            push 0
            push 4
            call dword ptr [ebp - 0x10]
            jmp done
        unavailable:
            push 0
            push 0
            push 0
            push 3
            call dword ptr [ebp - 0x10]
            jmp done
        invalid:
            push 0
            push 0
            push 0
            push 3
            call dword ptr [ebp - 0x10]
            jmp done
        no_result:
            jmp done
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

    # cdecl walker(manager, bound, mode, snapshot); EAX=changed count.
    # mode 0 is a complete read-only dry run, mode 1 performs changed-only
    # native writer calls, and mode 2 is the complete exact-100 postverify.
    walker = asm(
        f"""
            push ebp
            mov ebp, esp
            push ebx
            push esi
            push edi
            sub esp, 0x0C
            mov esi, dword ptr [ebp + 8]
            add esi, 0x52C
            mov ecx, dword ptr [ebp + 12]
            mov edx, dword ptr [ebp + 16]
            mov edi, dword ptr [ebp + 20]
            mov dword ptr [ebp - 0x10], edx
            mov dword ptr [ebp - 0x14], ecx
            mov dword ptr [ebp - 0x18], 0
            xor eax, eax
            xor ebx, ebx
        next:
            mov edx, dword ptr [ebp - 0x10]
            mov ecx, dword ptr [ebp - 0x14]
            cmp ebx, ecx
            jae walk_done
            cmp byte ptr [esi + 0x30], 0
            je advance
            cmp dword ptr [esi + 0x52C], 0
            jle advance
            cmp byte ptr [esi + 0x558], 0
            jne advance
            cmp edx, 2
            je postverify
            cmp dword ptr [esi + 0x7E4], 0
            jl invalid_data
            cmp dword ptr [esi + 0x7E4], 100
            jg invalid_data
            cmp dword ptr [esi + 0x7E8], 0
            jl invalid_data
            cmp dword ptr [esi + 0x7E8], 100
            jg invalid_data
            cmp dword ptr [esi + 0x7EC], 0
            jl invalid_data
            cmp dword ptr [esi + 0x7EC], 100
            jg invalid_data
            cmp dword ptr [esi + 0x7F0], 0
            jl invalid_data
            cmp dword ptr [esi + 0x7F0], 100
            jg invalid_data
            cmp dword ptr [esi + 0x7F4], 0
            jl invalid_data
            cmp dword ptr [esi + 0x7F4], 100
            jg invalid_data
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
            mov dword ptr [ebp - 0x18], eax
            test edx, edx
            jz advance
            cmp byte ptr [esi + 0x7FC], 0
            jne originally_marked
            mov byte ptr [edi + ebx], 1
            jmp snapshot_done
        originally_marked:
            mov byte ptr [edi + ebx], 2
        snapshot_done:
            cmp dword ptr [esi + 0x7E4], 100
            je s2
            mov ecx, 100
            sub ecx, dword ptr [esi + 0x7E4]
            push ecx
            push 3
            push ebx
            mov ecx, dword ptr [ebp + 8]
            add ecx, 0x52C
            call 0x445430
        s2:
            cmp dword ptr [esi + 0x7E8], 100
            je s3
            mov ecx, 100
            sub ecx, dword ptr [esi + 0x7E8]
            push ecx
            push 2
            push ebx
            mov ecx, dword ptr [ebp + 8]
            add ecx, 0x52C
            call 0x445430
        s3:
            cmp dword ptr [esi + 0x7EC], 100
            je s4
            mov ecx, 100
            sub ecx, dword ptr [esi + 0x7EC]
            push ecx
            push 1
            push ebx
            mov ecx, dword ptr [ebp + 8]
            add ecx, 0x52C
            call 0x445430
        s4:
            cmp dword ptr [esi + 0x7F0], 100
            je s5
            mov ecx, 100
            sub ecx, dword ptr [esi + 0x7F0]
            push ecx
            push 5
            push ebx
            mov ecx, dword ptr [ebp + 8]
            add ecx, 0x52C
            call 0x445430
        s5:
            cmp dword ptr [esi + 0x7F4], 100
            je advance
            mov ecx, 100
            sub ecx, dword ptr [esi + 0x7F4]
            push ecx
            push 4
            push ebx
            mov ecx, dword ptr [ebp + 8]
            add ecx, 0x52C
            call 0x445430
            mov eax, dword ptr [ebp - 0x18]
            jmp advance
        postverify:
            cmp dword ptr [esi + 0x7E4], 100
            jne verify_failed
            cmp dword ptr [esi + 0x7E8], 100
            jne verify_failed
            cmp dword ptr [esi + 0x7EC], 100
            jne verify_failed
            cmp dword ptr [esi + 0x7F0], 100
            jne verify_failed
            cmp dword ptr [esi + 0x7F4], 100
            jne verify_failed
            inc eax
            jmp advance
        verify_failed:
            xor eax, eax
            jmp walk_done
        invalid_data:
            mov eax, -1
            jmp walk_done
        advance:
            cmp dword ptr [ebp - 0x10], 1
            jne next_record
            mov eax, dword ptr [ebp - 0x18]
        next_record:
            add esi, {STRIDE}
            inc ebx
            jmp next
        walk_done:
            add esp, 0x0C
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

    result_preflight = asm(
        f"""
            push ebx
            push esi
            push 0x{strings['candidate_dll']:X}
            call dword ptr [0x474010]
            test eax, eax
            jz result_unavailable
            push 0x{strings['result_export']:X}
            push eax
            call dword ptr [0x4740D4]
            test eax, eax
            jz result_unavailable
            mov esi, eax
            mov eax, esi
            pop esi
            pop ebx
            ret
        result_unavailable:
            xor eax, eax
            pop esi
            pop ebx
            ret
        """,
        result_preflight_va,
    )
    _put(section, RESULT_PREFLIGHT_OFFSET, result_preflight, "result export preflight")

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
        "result_preflight_sha256": sha(result_preflight),
        "result_resolver_sha256": sha(show_result),
        "offsets": {
            "handler": f"0x{TECH_HANDLER_OFFSET:X}",
            "constructor": f"0x{TECH_CONSTRUCTOR_OFFSET:X}",
            "entry": f"0x{ENTRY_OFFSET:X}",
            "walker": f"0x{WALKER_OFFSET:X}",
            "telemetry": f"0x{TELEMETRY_OFFSET:X}",
            "confirmation": f"0x{CONFIRM_OFFSET:X}",
            "menu_resolver": f"0x{SHOW_MENU_OFFSET:X}",
            "result_preflight": f"0x{RESULT_PREFLIGHT_OFFSET:X}",
            "result_resolver": f"0x{SHOW_RESULT_OFFSET:X}",
            "strings": f"0x{STRINGS_OFFSET:X}",
        },
        "constructor_pointer": {
            "instruction_va": f"0x{constructor_va + 0x3C:X}",
            "target_va": f"0x{strings['button']:X}",
            "target_text": "Origins Upgrades",
            "guard": "constructor button pointer must resolve inside emitted string block",
        },
        "strings": {key: f"0x{value:X}" for key, value in strings.items()},
        "absolute_references": [
            "0x474010 LoadLibraryA IAT",
            "0x4740D4 GetProcAddress IAT",
            "0x44F4E0 native manager getter (no args, EAX manager)",
            "0x445430 native changed-only skill writer (thiscall, ret 0xC)",
            "0x44D4C0 native Elder evaluator (thiscall, exactly once)",
            "0x426290 native tech-point writer (thiscall, ret 4, exactly once)",
            "0x467F83 stock allocation helper",
            "0x4019D0 stock button constructor",
            "0x4015D0 stock button styling",
            "0x40B560 stock child attachment",
        ],
        "rel32_references": [
            "handler -> entry",
            "handler -> stock continuation 0x4437C5",
            "constructor -> 0x467F83/0x4019D0/0x4015D0/0x40B560",
            "entry -> 0x44F4E0/walker/confirmation/0x44D4C0/0x426290/telemetry/result-preflight/result",
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
        "catalog_hidden": True,
        "certification_status": "PENDING INDEPENDENT RECERTIFICATION after native manager/pool transport repair; disabled and catalog-hidden",
        "source_commit": IMPLEMENTATION_COMMIT,
        "implementation_commit": IMPLEMENTATION_COMMIT,
        "acceptance_commit": None,
        "audit_commit": None,
        "audit_status": AUDIT_STATUS,
        "description": (
            "Disabled command-7-only stock candidate. The repaired transaction uses "
            "the native manager getter, changed-only native skill writer, native "
            "Elder evaluator, and native tech-point writer; no raw skill stores, "
            "precharge, .shr transport, Gong, or Island Event paths are emitted. "
            "It remains hidden pending independent recertification."
        ),
        "dependencies": [],
        "supported_modes": list(MODES),
        "rejected_modes": list(REJECTED_MODES),
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
            "purpose": "append the disabled command-7 Origins Upgrades button",
            },
            {
                "offset": "0x437C0",
                "before": "837C240408",
                "after": handler_after.hex().upper(),
            "purpose": "route only the command-7 button",
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
            "skills": {
                "farming": "+0x7E4 -> native skill 3",
                "building": "+0x7E8 -> native skill 2",
                "research": "+0x7EC -> native skill 1",
                "healing": "+0x7F0 -> native skill 5",
                "parenting": "+0x7F4 -> native skill 4",
            },
            "target": 100,
            "native_manager_getter": "sub_44F4E0 no arguments; EAX manager; fresh calls at initial, post-confirmation, post-write, pre-evaluator, and post-evaluator boundaries",
            "native_skill_writer": "sub_445430 thiscall ECX=manager+0x52C; push delta, skill id, physical index; callee ret 0xC",
            "native_evaluator": "sub_44D4C0 thiscall ECX=manager exactly once globally",
            "native_tech_writer": "sub_426290 thiscall ECX=state; push signed -1000000; callee ret 4 exactly once after evaluator",
            "rollback_limit": "native writer partial changes are not rolled back on postverify failure; failure is no-charge and reported",
            "transaction_order": [
                "complete 256-record read-only dry run",
                "no-change result before funds/confirmation",
                "unsigned funds check",
                "explicit confirmation",
                "fresh manager and complete read-only recheck",
                "changed-only sub_445430 writes",
                "complete exact-100 postverify",
                "fresh manager/state acquisition before evaluator",
                "sub_44D4C0 exactly once",
                "fresh manager/state acquisition after evaluator",
                "fresh telemetry after evaluator",
                "fresh unsigned funds >= 1000000 recheck",
                "sub_426290 exactly once",
            ],
            "walker_locals": {
                "mode": "[ebp-0x10]",
                "bound": "[ebp-0x14]",
                "changed_count": "[ebp-0x18]",
                "snapshot": "entry [ebp-0x124..-0x24], zeroed 256 bytes before mutation",
            },
            "result_preflight": "both menu and result exports are resolved before confirmation/mutation",
            "result_pointer_local": "[ebp-0x10], outside the 256-byte snapshot; every post-preflight result uses the saved stdcall pointer",
            "entry_snapshot_interval": "[ebp-0x124..ebp-0x25] inclusive (256 bytes)",
            "entry_scalar_locals": {
                "result_pointer": "[ebp-0x10]",
                "changed_but_unmarked": "[ebp-0x14]",
                "changed_count": "[ebp-0x18]",
                "manager": "[ebp-0x1C]",
                "state": "[ebp-0x20]",
                "new_elder_count": "[ebp-0x24]",
            },
            "entry_saved_register_slots": {
                "ebx": "[ebp-0x04]",
                "esi": "[ebp-0x08]",
                "edi": "[ebp-0x0C]",
            },
            "fresh_manager_boundaries": [
                "initial dry-run",
                "post-confirmation recheck",
                "post-write pre-postverify",
                "postverify pre-evaluator",
                "post-evaluator telemetry/funds/deduction",
            ],
            "final_funds_recheck": "fresh post-evaluator state [state+0x2EADC] >= 1000000 dominates sub_426290",
            "result_statuses": {
                "0": "no eligible changes; no charge",
                "2": "insufficient funds; no charge",
                "3": "validation or pointer failure; no charge",
                "4": "Full Mastery was canceled; No tech points have been deducted.",
            },
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
            "source_commit": IMPLEMENTATION_COMMIT,
            "implementation_commit": IMPLEMENTATION_COMMIT,
            "acceptance_commit": None,
            "audit_commit": None,
            "audit_status": AUDIT_STATUS,
            "catalog_enabled": False,
            "certification_status": "PENDING INDEPENDENT RECERTIFICATION; disabled/catalog-hidden",
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
                "entry": "handler retains command-7 menu routing; entry calls sub_44F4E0 for manager and never transports the Tech receiver as a pool base",
                "manager_getter": "sub_44F4E0 takes no arguments and returns manager in EAX; records begin at manager+0x52C",
                "walker": "cdecl(manager,bound,mode,snapshot); bound 256; mode0 dry-run, mode1 native writes, mode2 exact100 postverify; preserves EBX/ESI/EDI/EBP",
                "telemetry": "cdecl(base,bound,snapshot); ECX new markers; EDX changed-but-unmarked",
                "skill_writer": "sub_445430 thiscall ECX=manager+0x52C; stack delta, skill id, physical index; ret 0xC",
                "evaluator": "sub_44D4C0 thiscall ECX=manager exactly once",
                "tech_writer": "sub_426290 thiscall ECX=state; stack signed -1000000; ret 4 exactly once after evaluator",
                "result": "stdcall(status,changed,new_markers,changed_but_unmarked); ret 16",
            },
            "modes": list(MODES),
            "allowed_modes": list(MODES),
            "rejected_modes": list(REJECTED_MODES),
        }
    )
    return manifest, artifact


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-root",
        type=Path,
        help="redirect all generated metadata/audit files beneath this directory",
    )
    parser.add_argument(
        "--emit-executables",
        action="store_true",
        help="also emit Collection Progression and Immediate Fixed candidate EXEs under the audit directory",
    )
    args = parser.parse_args(argv)
    manifest, artifact = build()
    paths = resolve_output_paths(args.output_root)
    from vv_fun_patcher import FunPatch, load_builds, load_fun_patches, render_patched_bytes

    build_record = next(item for item in load_builds() if item.id == "vv2")
    candidate = FunPatch(manifest)
    others = [
        item
        for item in load_fun_patches()
        if item.game_id == "vv2" and item.id != manifest["id"]
    ]
    rendered: dict[str, object] = {}
    emitted_images: dict[str, bytes] = {}
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
        emitted_images[mode] = image
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
    audit_manifest = {
        "candidate_id": manifest["id"],
        "source_commit": artifact["source_commit"],
        "implementation_commit": artifact["implementation_commit"],
        "acceptance_commit": artifact["acceptance_commit"],
        "audit_commit": artifact["audit_commit"],
        "audit_status": artifact["audit_status"],
        "implementation_status": "committed",
        "enabled": manifest["enabled"],
        "catalog_hidden": manifest["catalog_hidden"],
        "allowed_modes": list(MODES),
        "rejected_modes": list(REJECTED_MODES),
        "rendered": {
            mode: {
                "path": f"{mode}.exe",
                "sha256": details["candidate_sha256"],
                "size": details["size"],
                "deterministic_second_sha256": details["candidate_sha256"],
                "uninstall_stock_sha256": details["uninstall_target_sha256"],
                "owners": details["owners"],
            }
            for mode, details in rendered.items()
        },
        "companion": manifest["companion_files"],
    }
    doc = (
        "# VV2 Full Mastery repaired candidate (pending recertification)\n\n"
        "This disabled, catalog-hidden stock-only candidate is generated from the "
        "C138 D133/D134 local-layout repair. It remains unavailable pending independent "
        "recertification; no player package is produced by this task.\n\n"
        f"- Section SHA-256: `{artifact['section_sha256']}`\n"
        f"- Companion SHA-256: `{artifact['companion']['sha256']}`\n"
        f"- Entry SHA-256: `{artifact['entry_sha256']}`\n"
        f"- Walker SHA-256: `{artifact['walker_sha256']}`\n"
        f"- Confirmation SHA-256: `{artifact['confirmation_sha256']}`\n\n"
        f"Provenance is bound to implementation commit `{IMPLEMENTATION_COMMIT}` (source and implementation). "
        "Acceptance and audit commits are explicitly null; independent recertification remains pending and no audit identity is claimed.\n\n"
        "The candidate appends `.vv2fm`; it never uses or changes `.shr`. It "
        "adds command 7 only, with commands 6/8, ownership, Remove, Gong, and "
        "Island Event interception absent. The five native skill IDs are "
        "Farming=3, Building=2, Research=1, Healing=5, and Parenting=4; the "
        "walker uses real stack locals, preserves EBX/ESI/EDI, and keeps the "
        "256-record bound stable across every native call. A zeroed snapshot "
        "records 0 unchanged, 1 newly changed from unmarked, and 2 newly changed "
        "from marked. Both menu and result exports are preflighted before any "
        "confirmation or mutation. The result pointer is saved at `[ebp-0x10]` "
        "and changed-but-unmarked telemetry at `[ebp-0x14]`, both disjoint from "
        "the `[ebp-0x124..ebp-0x25]` snapshot and saved-register slots; every "
        "post-preflight result uses that pointer without another "
        "resolver. The transaction performs a complete 256-record dry run before "
        "funds/confirmation, reacquires manager/state at five pointer-sensitive "
        "boundaries, post-verifies exact 100, calls sub_44D4C0 once, reacquires "
        "again, refreshes telemetry, performs a fresh unsigned funds check, then "
        "calls sub_426290 once for the single deduction. Cancel reports `Full "
        "Mastery was canceled.` followed by `No tech points have been deducted.` "
        "and every other failure is no-charge. "
        "Expanded-256 modes are rejected before output. The raw manifest and "
        "complete map are under `data/candidates/`. If a native writer succeeds "
        "and a later postverify fails, the candidate reports no-charge failure "
        "without an unproved rollback of already-applied native changes.\n"
    )
    output_files = [
        paths["manifest"],
        paths["map"],
        paths["doc"],
        paths["audit_manifest"],
        paths["audit_source_map"],
    ]
    if args.emit_executables:
        output_files.extend(paths["audit_dir"] / f"{mode}.exe" for mode in MODES)
    for output in output_files:
        output.parent.mkdir(parents=True, exist_ok=True)
    paths["manifest"].write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    paths["map"].write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    paths["doc"].write_text(doc, encoding="utf-8")
    paths["audit_manifest"].write_text(json.dumps(audit_manifest, indent=2) + "\n", encoding="utf-8")
    paths["audit_source_map"].write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    if args.emit_executables:
        for mode, image in emitted_images.items():
            (paths["audit_dir"] / f"{mode}.exe").write_bytes(image)


if __name__ == "__main__":
    main()
