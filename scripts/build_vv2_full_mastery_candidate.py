"""Generate the statically enabled, stock-only VV2 command-7 Full Mastery candidate."""

from __future__ import annotations

import hashlib
import argparse
import json
import os
import stat
import struct
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Lost Children.exe"
OUT_DIR = ROOT / "data" / "candidates"
MANIFEST_OUT = OUT_DIR / "vv2_full_mastery_all_candidate.json"
MAP_OUT = OUT_DIR / "vv2_full_mastery_all_candidate_map.json"
DOC_OUT = ROOT / "docs" / "vv2-full-mastery-stage-a-candidate.md"
COMPANION = OUT_DIR / "VVFP VV2 Full Mastery Candidate.dll"
AUDIT_OUT = ROOT / "outputs" / "vv2-c138-native-audit"
COMPANION_SIZE = 109056
COMPANION_SHA256 = "1324EDFB83ABA755AFF6410D71DD668F4860127CD67A952722FDE5DD2FDC92C2"
IMPLEMENTATION_COMMIT = "895340333d55273e599f2dce5ab0db42cbc6d0ab"
STATIC_ACCEPTANCE_COMMIT = "13f4341201fa7757d23f77c5c17602bbe7bbf21d"
AUDIT_STATUS = "static emitted-byte GO; runtime/player confirmation pending"

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
EVALUATOR_TRUTH = "native sub_44D4C0 runs exactly once globally after complete exact-100 postverification"
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
STATIC_ACCEPTANCE = {
    "status": "GO",
    "evidence_commit": STATIC_ACCEPTANCE_COMMIT,
    "implementation_commit": IMPLEMENTATION_COMMIT,
    "runtime_player_status": "pending",
    "source_sha256": "46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677",
    "section_sha256": "D84DA1DF60C9AC160312C5AC0943663CA16DA909935A96FA3E1B9D723462B9A1",
    "entry_sha256": "505DCF6A0891E640FA73B41A0CBC6868B35FF1C9D5F2A598A6C067004F78A58F",
    "walker_sha256": "E67F5F34AEB66A953B5B2A77FD6A5EA00B907D26B61A25A0C132F62C713C98DD",
    "telemetry_sha256": "8036B4818E39533B3F5BEBF1EC38A94A71B05EE8BE72FB1EFA0B9AD72789B907",
    "confirmation_sha256": "8868C87F2B66AD9D69F1DC7A08A469E5C5C478727955A5E1E4F6DA4EEB306B2C",
    "menu_resolver_sha256": "38B1AECEABF47C01B945AB438954C2489C83DDC3E5C573E81321F94C2E360B4F",
    "result_preflight_sha256": "C994315AD623EE3E3001193735C435FBC9A721EDB5A0A521E6069421C63D60E5",
    "result_resolver_sha256": "B7002D2C62F475914719A8A99B65BEC7580B7026E7FB3A991046CBCC77FB8D0B",
    "dll_sha256": COMPANION_SHA256,
    "dll_size": COMPANION_SIZE,
    "stock_size": 724992,
    "collection_composition_sha256": "C7C0BEC312B6537B5F1DD692D2C90ED0D0963D6CE3A7F5271AF4A6C680B8ACBC",
    "immediate_composition_sha256": "6AEE09C69C3E7C1AD12284EA5B5A188AF05DA3D87AD6149545CEE65D896E6774",
    "allowed_modes": list(MODES),
    "rejected_modes": list(REJECTED_MODES),
}


def resolve_output_paths(output_root: Path | None) -> dict[str, object]:
    """Resolve every generated destination under one fresh outputs child."""
    if output_root is None:
        return {
            "manifest": MANIFEST_OUT,
            "map": MAP_OUT,
            "doc": DOC_OUT,
            "audit_dir": AUDIT_OUT,
            "audit_manifest": AUDIT_OUT / "artifact-manifest.json",
            "audit_source_map": AUDIT_OUT / "source-map.json",
            "isolated": False,
            "root": None,
        }

    requested = Path(output_root).expanduser()
    if os.path.lexists(os.fspath(requested)):
        raise ValueError("output root lexical destination already exists")
    if ".." in requested.parts:
        raise ValueError("output root cannot contain traversal components")
    lexical_root = Path(os.path.abspath(os.fspath(requested)))
    lexical_outputs = Path(os.path.abspath(os.fspath(ROOT / "outputs")))
    outputs_info = os.lstat(lexical_outputs)
    outputs_attributes = int(getattr(outputs_info, "st_file_attributes", 0))
    if stat.S_ISLNK(outputs_info.st_mode) or outputs_attributes & 0x400:
        raise ValueError("repository outputs directory is a reparse point")
    try:
        lexical_relative = lexical_root.relative_to(lexical_outputs)
    except ValueError as exc:
        raise ValueError("output root must be a child of the repository outputs directory") from exc
    if not lexical_relative.parts:
        raise ValueError("output root must be a strict child of the repository outputs directory")
    lexical_parent = lexical_root.parent
    try:
        parent_relative = lexical_parent.relative_to(lexical_outputs)
    except ValueError as exc:
        raise ValueError("output root parent escapes the repository outputs directory") from exc
    cursor = lexical_outputs
    for component in parent_relative.parts:
        cursor = cursor / component
        if os.path.lexists(os.fspath(cursor)):
            info = os.lstat(cursor)
            attributes = int(getattr(info, "st_file_attributes", 0))
            if stat.S_ISLNK(info.st_mode) or attributes & 0x400:
                raise ValueError("output root traverses a symlink/reparse point")
            if not stat.S_ISDIR(info.st_mode):
                raise ValueError("output root parent is not a directory")
    if not os.path.lexists(os.fspath(lexical_parent)) or not lexical_parent.is_dir():
        raise ValueError("output root parent directory is missing")
    root = lexical_root.resolve(strict=False)
    outputs_root = lexical_outputs.resolve(strict=False)
    if root == outputs_root or outputs_root not in root.parents:
        raise ValueError("resolved output root escapes the repository outputs directory")
    if root.exists():
        raise ValueError("output root already exists; choose a fresh destination")

    paths = {
        "manifest": root / "data" / "candidates" / MANIFEST_OUT.name,
        "map": root / "data" / "candidates" / MAP_OUT.name,
        "doc": root / "docs" / DOC_OUT.name,
        "audit_dir": root / "audit",
        "audit_manifest": root / "audit" / "artifact-manifest.json",
        "audit_source_map": root / "audit" / "source-map.json",
    }
    for path in paths.values():
        if not isinstance(path, Path):
            continue
        resolved = path.resolve(strict=False)
        if resolved != root and root not in resolved.parents:
            raise ValueError("resolved output path escapes output root")
    paths["isolated"] = True
    paths["root"] = root
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
            f"{EVALUATOR_TRUTH} at 0x44D4C0 (thiscall ECX=manager)",
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
        raise RuntimeError("build the enabled static-candidate companion DLL first")
    companion_bytes = COMPANION.read_bytes()
    if len(companion_bytes) != COMPANION_SIZE:
        raise RuntimeError("VV2 companion DLL size mismatch")
    if sha(companion_bytes) != COMPANION_SHA256:
        raise RuntimeError("VV2 companion DLL SHA-256 mismatch")

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
        "enabled": True,
        "catalog_hidden": False,
        "certification_status": "STATIC EMITTED-BYTE GO; catalog-visible for stock modes; runtime/player confirmation pending",
        "source_commit": IMPLEMENTATION_COMMIT,
        "implementation_commit": IMPLEMENTATION_COMMIT,
        "acceptance_commit": None,
        "audit_commit": None,
        "audit_status": AUDIT_STATUS,
        "static_acceptance": dict(STATIC_ACCEPTANCE),
        "description": (
            "Enabled command-7-only stock candidate for stock Collection Progression "
            "and Immediate Fixed modes. Runtime/player confirmation remains pending. "
            "The repaired transaction uses "
            "the native manager getter, changed-only native skill writer, native "
            "Elder evaluator, and native tech-point writer; no raw skill stores, "
            "precharge, .shr transport, Gong, or Island Event paths are emitted. "
            "Expanded-256 modes are rejected before output."
        ),
        "dependencies": [],
        "supported_modes": list(MODES),
        "rejected_modes": list(REJECTED_MODES),
        "companion_files": [
            {
                "source": "data/candidates/VVFP VV2 Full Mastery Candidate.dll",
                "destination": "VVFP VV2 Full Mastery Candidate.dll",
                "sha256": sha(companion_bytes),
            }
        ],
        "patches": [
            {
                "offset": "0x435EF",
                "before": "8B4C24205F",
                "after": constructor_after.hex().upper(),
            "purpose": "append the enabled command-7 static-candidate Origins Upgrades button",
            },
            {
                "offset": "0x437C0",
                "before": "837C240408",
                "after": handler_after.hex().upper(),
            "purpose": "route only the enabled command-7 static-candidate button",
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
            "native_evaluator": f"{EVALUATOR_TRUTH}; thiscall ECX=manager",
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
                EVALUATOR_TRUTH,
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
            "purpose": "append the enabled command-7-only .vv2fm RX static-candidate section",
            "header_patches": [
                {
                    "offset": f"0x{pe['section_count_offset']:X}",
                    "before": "0500",
                    "after": "0600",
                    "purpose": "add the enabled static-candidate .vv2fm section",
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
                    "purpose": "install the enabled static-candidate .vv2fm RX section header",
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
            "static_acceptance": dict(STATIC_ACCEPTANCE),
            "catalog_enabled": True,
            "certification_status": "STATIC EMITTED-BYTE GO; catalog-visible for stock modes; runtime/player confirmation pending",
            "source": {"size": len(original), "sha256": expected_sha},
            "companion": {
                "path": "data/candidates/VVFP VV2 Full Mastery Candidate.dll",
                "size": len(companion_bytes),
                "sha256": sha(companion_bytes),
                "exports": export_map(companion_bytes),
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
                "evaluator": f"{EVALUATOR_TRUTH}; thiscall ECX=manager",
                "tech_writer": "sub_426290 thiscall ECX=state; stack signed -1000000; ret 4 exactly once after evaluator",
                "result": "stdcall(status,changed,new_markers,changed_but_unmarked); ret 16",
            },
            "modes": list(MODES),
            "allowed_modes": list(MODES),
            "rejected_modes": list(REJECTED_MODES),
        }
    )
    return manifest, artifact


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2) + "\n").encode("utf-8")


def _validate_generated_bundle(
    bundle: dict[str, bytes],
    manifest: dict[str, object],
    artifact: dict[str, object],
    audit_manifest: dict[str, object],
    emitted_images: dict[str, bytes],
) -> None:
    required = {
        "data/candidates/vv2_full_mastery_all_candidate.json",
        "data/candidates/vv2_full_mastery_all_candidate_map.json",
        "docs/vv2-full-mastery-stage-a-candidate.md",
        "audit/artifact-manifest.json",
        "audit/source-map.json",
    }
    expected = set(required)
    expected.update(f"audit/{mode}.exe" for mode in emitted_images)
    if set(bundle) != expected:
        raise ValueError("generated product set is incomplete or contains unexpected paths")
    parsed_manifest = json.loads(bundle[next(path for path in bundle if path.endswith("_candidate.json"))])
    parsed_map = json.loads(bundle[next(path for path in bundle if path.endswith("_candidate_map.json"))])
    parsed_audit = json.loads(bundle["audit/artifact-manifest.json"])
    parsed_source_map = json.loads(bundle["audit/source-map.json"])
    if parsed_manifest != manifest or parsed_map != artifact or parsed_source_map != artifact:
        raise ValueError("in-memory generated metadata does not match source records")
    if parsed_audit != audit_manifest:
        raise ValueError("in-memory audit manifest does not match source record")
    for record in (parsed_manifest, parsed_map, parsed_audit, parsed_source_map):
        if record.get("source_commit") != IMPLEMENTATION_COMMIT:
            raise ValueError("generated provenance source commit mismatch")
        if record.get("implementation_commit") != IMPLEMENTATION_COMMIT:
            raise ValueError("generated provenance implementation commit mismatch")
        if record.get("audit_commit") is not None or record.get("acceptance_commit") is not None:
            raise ValueError("generated provenance must not use circular legacy audit/acceptance fields")
        static = record.get("static_acceptance")
        if not isinstance(static, dict) or static.get("status") != "GO":
            raise ValueError("static acceptance evidence is missing")
        if static.get("evidence_commit") != STATIC_ACCEPTANCE_COMMIT:
            raise ValueError("static acceptance evidence commit mismatch")
        if static.get("implementation_commit") != IMPLEMENTATION_COMMIT:
            raise ValueError("static acceptance implementation binding mismatch")
        if static.get("runtime_player_status") != "pending":
            raise ValueError("runtime/player status must remain pending")
        if static.get("allowed_modes") != list(MODES) or static.get("rejected_modes") != list(REJECTED_MODES):
            raise ValueError("static acceptance mode contract mismatch")
    if not parsed_manifest.get("enabled") or parsed_manifest.get("catalog_hidden"):
        raise ValueError("candidate must remain enabled and catalog-visible")
    if not parsed_map.get("catalog_enabled"):
        raise ValueError("candidate map catalog gate is not enabled")
    if parsed_manifest.get("supported_modes") != list(MODES):
        raise ValueError("supported mode contract mismatch")
    if not bundle["docs/vv2-full-mastery-stage-a-candidate.md"].decode("utf-8").strip():
        raise ValueError("generated documentation is empty")
    for mode, image in emitted_images.items():
        emitted = bundle[f"audit/{mode}.exe"]
        if emitted != image or sha(emitted) != artifact["rendered_candidates"][mode]["candidate_sha256"]:  # type: ignore[index]
            raise ValueError(f"rendered {mode} does not match its in-memory identity")


def _lstat_entry(path: Path, expected_hash: str | None = None) -> dict[str, object]:
    info = os.lstat(path)
    attributes = int(getattr(info, "st_file_attributes", 0))
    if stat.S_ISLNK(info.st_mode) or attributes & 0x400:
        entry_type = "reparse"
    elif stat.S_ISREG(info.st_mode):
        entry_type = "file"
    elif stat.S_ISDIR(info.st_mode):
        entry_type = "directory"
    else:
        entry_type = "other"
    entry: dict[str, object] = {
        "type": entry_type,
        "identity": (int(info.st_dev), int(info.st_ino)),
        "attributes": attributes,
        "mode": stat.S_IMODE(info.st_mode),
        "nlink": int(info.st_nlink),
    }
    if expected_hash is not None:
        entry["expected_hash"] = expected_hash
    return entry


def _enumerate_lstat_tree(root: Path) -> dict[str, dict[str, object]] | None:
    try:
        entries = {"": _lstat_entry(root)}
        pending = [root]
        while pending:
            directory = pending.pop()
            directory_entry = entries[directory.relative_to(root).as_posix() if directory != root else ""]
            if directory_entry["type"] != "directory":
                return None
            with os.scandir(directory) as children:
                for child in children:
                    child_path = Path(child.path)
                    relative = child_path.relative_to(root).as_posix()
                    entry = _lstat_entry(child_path)
                    entries[relative] = entry
                    if entry["type"] == "reparse":
                        return None
                    if entry["type"] == "directory":
                        pending.append(child_path)
        return entries
    except (OSError, ValueError):
        return None


def _inventory_matches(root: Path, inventory: dict[str, dict[str, object]]) -> bool:
    actual = _enumerate_lstat_tree(root)
    if actual is None or set(actual) != set(inventory):
        return False
    for relative, expected in inventory.items():
        current = actual[relative]
        for field in ("type", "identity", "attributes", "mode"):
            if current.get(field) != expected.get(field):
                return False
        if expected["type"] == "file":
            if current.get("nlink") != expected.get("nlink") or int(current.get("nlink", 0)) != 1:
                return False
            path = root / relative
            try:
                before = _lstat_entry(path)
                digest = sha(path.read_bytes())
                after = _lstat_entry(path)
            except (OSError, ValueError):
                return False
            if before != after or before["identity"] != expected["identity"]:
                return False
            if digest != expected.get("expected_hash"):
                return False
    return True


def _entry_matches(path: Path, expected: dict[str, object]) -> bool:
    try:
        current = _lstat_entry(path)
        for field in ("type", "identity", "attributes", "mode"):
            if current.get(field) != expected.get(field):
                return False
        return expected["type"] != "file" or (
            current.get("nlink") == expected.get("nlink") and current.get("nlink") == 1
        )
    except (OSError, ValueError):
        return False


def _cleanup_owned_tree(
    root: Path,
    inventory: dict[str, dict[str, object]],
    parent: Path,
    name: str,
) -> bool:
    if root.name != name or root.parent.resolve(strict=False) != parent:
        return False
    if not _inventory_matches(root, inventory):
        return False
    files = sorted(
        (relative for relative, entry in inventory.items() if entry["type"] == "file"),
        key=lambda value: (value.count("/"), value),
        reverse=True,
    )
    directories = sorted(
        (relative for relative, entry in inventory.items() if entry["type"] == "directory" and relative),
        key=lambda value: (value.count("/"), value),
        reverse=True,
    )
    directories.append("")
    try:
        for relative in files:
            path = root / relative
            expected = inventory[relative]
            if not _entry_matches(path, expected):
                return False
            path.unlink()
            if os.path.lexists(path):
                return False
        for relative in directories:
            path = root / relative if relative else root
            if not _entry_matches(path, inventory[relative]) or inventory[relative]["type"] != "directory":
                return False
            path.rmdir()
            if os.path.lexists(path):
                return False
        return True
    except (OSError, ValueError):
        return False


def write_output_bundle(
    final_root: Path,
    bundle: dict[str, bytes],
    *,
    replace_func=None,
    write_func=None,
) -> None:
    """Atomically publish a validated isolated bundle beneath outputs."""
    requested = Path(final_root).expanduser()
    if os.path.lexists(os.fspath(requested)):
        raise ValueError("output root lexical destination already exists")
    if ".." in requested.parts:
        raise ValueError("output root cannot contain traversal components")
    final_root = requested.resolve(strict=False)
    outputs_root = (ROOT / "outputs").resolve()
    if final_root == outputs_root or outputs_root not in final_root.parents:
        raise ValueError("output root must be a strict child of outputs")
    if final_root.exists():
        raise ValueError("output root already exists")
    if not final_root.parent.exists() or not final_root.parent.is_dir():
        raise ValueError("output root parent is missing")
    parent_identity = _lstat_entry(final_root.parent)
    if parent_identity["type"] != "directory":
        raise ValueError("output root parent is not an ordinary directory")
    cursor = outputs_root
    for component in final_root.relative_to(outputs_root).parts[:-1]:
        cursor = cursor / component
        if cursor.exists():
            attributes = getattr(cursor.stat(), "st_file_attributes", 0)
            if stat.S_ISLNK(cursor.stat().st_mode) or attributes & 0x400:
                raise ValueError("output root traverses a symlink/reparse point")
    rename = replace_func or os.rename
    writer = write_func or (lambda path, data: path.write_bytes(data))
    stage_path: Path | None = None
    stage_parent: Path | None = None
    stage_name: str | None = None
    inventory: dict[str, dict[str, object]] = {}

    try:
        if not _entry_matches(final_root.parent, parent_identity):
            raise RuntimeError("output root parent changed before staging")
        stage_path = Path(tempfile.mkdtemp(prefix=f".{final_root.name}.staging-", dir=str(final_root.parent)))
        stage_parent = final_root.parent.resolve(strict=False)
        stage_name = stage_path.name
        inventory[""] = _lstat_entry(stage_path)
        if inventory[""]["type"] != "directory":
            raise RuntimeError("owned staging directory identity could not be established")
        for relative, data in bundle.items():
            destination = stage_path / relative
            relative_path = destination.relative_to(stage_path)
            for parent_relative in reversed(relative_path.parents):
                parent_text = parent_relative.as_posix()
                if parent_text == ".":
                    continue
                parent_path = stage_path / parent_relative
                if parent_text in inventory:
                    if not _entry_matches(parent_path, inventory[parent_text]):
                        raise ValueError("staging directory identity changed")
                    continue
                if os.path.lexists(parent_path):
                    raise ValueError("unexpected pre-existing staging entry")
                parent_path.mkdir()
                inventory[parent_text] = _lstat_entry(parent_path)
                if inventory[parent_text]["type"] != "directory":
                    raise ValueError("staging parent is not a directory")
            try:
                writer(destination, data)
            except Exception:
                raise
            if not os.path.lexists(destination):
                raise ValueError(f"staged product was not created: {relative}")
            entry = _lstat_entry(destination, sha(data))
            if entry["type"] != "file" or entry["nlink"] != 1:
                raise ValueError("staged product is not an ordinary owned file")
            inventory[relative_path.as_posix()] = entry
        if not _inventory_matches(stage_path, inventory):
            raise ValueError("staged product inventory mismatch")
        for relative, expected in bundle.items():
            actual_path = stage_path / relative
            if not actual_path.is_file() or actual_path.read_bytes() != expected:
                raise ValueError(f"staged product mismatch: {relative}")
            if sha(actual_path.read_bytes()) != sha(expected):
                raise ValueError(f"staged product hash mismatch: {relative}")
            if relative.endswith(".json"):
                json.loads(actual_path.read_text(encoding="utf-8"))
        if not _inventory_matches(stage_path, inventory):
            raise RuntimeError("staging directory changed before rename")
        if not _entry_matches(final_root.parent, parent_identity):
            raise RuntimeError("output root parent changed before rename")
        if os.path.lexists(os.fspath(requested)) or os.path.lexists(os.fspath(final_root)):
            raise FileExistsError("output destination appeared before atomic rename")
        rename(stage_path, final_root)
        if stage_path.exists():
            raise RuntimeError("atomic rename did not transfer the owned staging directory")
        stage_path = None
    finally:
        if stage_path is not None and stage_parent is not None and stage_name is not None:
            _cleanup_owned_tree(stage_path, inventory, stage_parent, stage_name)


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
    paths = resolve_output_paths(args.output_root)
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
    static_rendered = {
        mode: {
            "candidate_sha256": details["candidate_sha256"],
            "baseline_sha256": details["baseline_sha256"],
            "uninstall_target_sha256": details["uninstall_target_sha256"],
            "size": details["size"],
        }
        for mode, details in rendered.items()
    }
    manifest["static_acceptance"]["rendered_candidates"] = static_rendered
    artifact["static_acceptance"] = json.loads(json.dumps(manifest["static_acceptance"]))
    audit_manifest = {
        "candidate_id": manifest["id"],
        "source_commit": artifact["source_commit"],
        "implementation_commit": artifact["implementation_commit"],
        "acceptance_commit": artifact["acceptance_commit"],
        "audit_commit": artifact["audit_commit"],
        "audit_status": artifact["audit_status"],
        "static_acceptance": json.loads(json.dumps(manifest["static_acceptance"])),
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
        "# VV2 Full Mastery repaired candidate (static certification GO)\n\n"
        "This enabled, catalog-visible stock-only candidate is generated from the "
        "C138 D133/D134 local-layout repair and is available only in Collection "
        "Progression and Immediate Fixed modes. Runtime/player confirmation remains "
        "pending; no player package is produced by this task.\n\n"
        f"- Section SHA-256: `{artifact['section_sha256']}`\n"
        f"- Companion SHA-256: `{artifact['companion']['sha256']}`\n"
        f"- Entry SHA-256: `{artifact['entry_sha256']}`\n"
        f"- Walker SHA-256: `{artifact['walker_sha256']}`\n"
        f"- Confirmation SHA-256: `{artifact['confirmation_sha256']}`\n\n"
        f"Binary provenance is bound to implementation commit `{IMPLEMENTATION_COMMIT}` (source and implementation). "
        f"Static acceptance is an independent GO recorded by `{STATIC_ACCEPTANCE_COMMIT}`; runtime/player confirmation remains pending.\n\n"
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
        "boundaries, post-verifies exact 100, then native sub_44D4C0 runs exactly "
        "once globally after complete exact-100 postverification. It reacquires "
        "again, refreshes telemetry, performs a fresh unsigned funds check, then "
        "calls sub_426290 once for the single deduction. Cancel reports `Full "
        "Mastery was canceled.` followed by `No tech points have been deducted.` "
        "and every other failure is no-charge. "
        "Expanded-256 modes are rejected before output. The raw manifest and "
        "complete map are under `data/candidates/`. If a native writer succeeds "
        "and a later postverify fails, the candidate reports no-charge failure "
        "without an unproved rollback of already-applied native changes.\n"
    )
    bundle = {
        "data/candidates/vv2_full_mastery_all_candidate.json": _json_bytes(manifest),
        "data/candidates/vv2_full_mastery_all_candidate_map.json": _json_bytes(artifact),
        "docs/vv2-full-mastery-stage-a-candidate.md": doc.encode("utf-8"),
        "audit/artifact-manifest.json": _json_bytes(audit_manifest),
        "audit/source-map.json": _json_bytes(artifact),
    }
    if args.emit_executables:
        bundle.update({f"audit/{mode}.exe": image for mode, image in emitted_images.items()})
    _validate_generated_bundle(bundle, manifest, artifact, audit_manifest, emitted_images if args.emit_executables else {})
    if paths["isolated"]:
        write_output_bundle(paths["root"], bundle)  # type: ignore[arg-type]
        return
    direct_files = {
        paths["manifest"]: bundle["data/candidates/vv2_full_mastery_all_candidate.json"],
        paths["map"]: bundle["data/candidates/vv2_full_mastery_all_candidate_map.json"],
        paths["doc"]: bundle["docs/vv2-full-mastery-stage-a-candidate.md"],
        paths["audit_manifest"]: bundle["audit/artifact-manifest.json"],
        paths["audit_source_map"]: bundle["audit/source-map.json"],
    }
    if args.emit_executables:
        direct_files.update({paths["audit_dir"] / f"{mode}.exe": image for mode, image in emitted_images.items()})
    for output, data in direct_files.items():
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(data)


if __name__ == "__main__":
    main()
