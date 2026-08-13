"""Deterministic x86 atomic-save writer for reviewed Expanded-256 builds.

The emitted routine replaces only the four stock save-writer call sites in
each supported exact build.  It writes a same-directory unique sibling,
verifies that sibling by handle identity and complete content, and commits it
with ReplaceFileA or MoveFileExA.  Any uncertain outcome terminates the
process; the routine never returns a false status to an unchecked caller.

This module only constructs bytes.  The patcher's guarded integration owns PE
parent/result identities and remains responsible for publication gates.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FORMAT_BYTES = b"%s.vvfp.%08X.%08X.%08X.tmp\0"
IMPORT_NAMES = (
    (0x100, "ReplaceFileA"),
    (0x110, "MoveFileExA"),
    (0x11E, "GetFileInformationByHandle"),
    (0x13C, "GetFileSizeEx"),
    (0x14C, "SetFileInformationByHandle"),
)


@dataclass(frozen=True)
class AtomicWriterConfig:
    game_id: str
    writer_va: int
    writer_raw: int
    format_va: int
    import_page_va: int
    import_page_raw: int
    import_page_rva: int
    import_descriptor: bytes
    import_page_sha256: str
    original_import_raw: int
    original_import_sha256: str
    import_directory_raw: int
    import_directory_before: bytes
    import_directory_after: bytes
    header_va: int
    header_size: int
    header_size_offset: int
    full_body_size: int
    stock_writer_va: int
    section_count_raw: int
    size_of_image_raw: int
    sections_before: int
    sections_after: int
    size_of_image_before: int
    size_of_image_after: int
    section_headers: tuple[tuple[int, bytes], ...]
    append_size: int
    callsites: tuple[tuple[int, bytes, bytes], ...]
    iat: dict[str, int]


COMMON_IMPORTS_VV3 = {
    "CreateFileA": 0x47C144, "WriteFile": 0x47C164,
    "FlushFileBuffers": 0x47C0A4, "CloseHandle": 0x47C148,
    "ReadFile": 0x47C14C, "GetFileAttributesA": 0x47C158,
    "GetLastError": 0x47C168, "GetCurrentProcessId": 0x47C0FC,
    "GetTickCount": 0x47C0F8, "InterlockedIncrement": 0x47C19C,
    "lstrlenA": 0x47C1A8, "wsprintfA": 0x47C3A0,
    "InterlockedCompareExchange": 0x47C114, "InterlockedExchange": 0x47C170,
    "TerminateProcess": 0x47C070, "ExitProcess": 0x47C078,
}
COMMON_IMPORTS_VV45 = {
    "CreateFileA": 0x48A140, "WriteFile": 0x48A160,
    "FlushFileBuffers": 0x48A0F8, "CloseHandle": 0x48A144,
    "ReadFile": 0x48A148, "GetFileAttributesA": 0x48A154,
    "GetLastError": 0x48A164, "GetCurrentProcessId": 0x48A054,
    "GetTickCount": 0x48A058, "InterlockedIncrement": 0x48A190,
    "lstrlenA": 0x48A198, "wsprintfA": 0x48A310,
    "InterlockedCompareExchange": 0x48A204, "InterlockedExchange": 0x48A0C8,
    "TerminateProcess": 0x48A078, "ExitProcess": 0x48A0BC,
}
COMMON_IMPORTS_VV5 = {key: value + 0xB000 for key, value in COMMON_IMPORTS_VV45.items()}


def _imports(common: dict[str, int], base: int) -> dict[str, int]:
    return {
        **common,
        "ReplaceFileA": base + 0x184,
        "MoveFileExA": base + 0x188,
        "GetFileInformationByHandle": base + 0x18C,
        "GetFileSizeEx": base + 0x190,
        "SetFileInformationByHandle": base + 0x194,
        "lock": base + 0x200,
        "counter": base + 0x204,
    }


CONFIGS = {
    "vv3": AtomicWriterConfig(
        "vv3", 0x7B9400, 0xCC400, 0x7B9E00,
        0x7BA000, 0xCD000, 0x3BA000,
        bytes.fromhex("6CA13B000000000000000000F0A03B0084A13B00"),
        "291FA68AE4F320C92226DFE735BD4559CE79BCDC949BECC2F4AFF7D6FC1E2A50",
        0xA19D0, "33D405AA872A3C8779C9E396743FBFE673BD3ADF513FB2E09EDC3BAC20CC3F65",
        0x188, bytes.fromhex("D0190A00DC000000"), bytes.fromhex("00A03B00F0000000"),
        0x4A420C, 0x0C, 0x08, 0x1A4B4, 0x403530, 0x10E, 0x158, 7, 8, 0x3BA000, 0x3BB000,
        ((0x318, bytes.fromhex("2E767633690000000010000000A03B000010000000D00C00000000000000000000000000400000C0")),),
        0x1000,
        (
            (0x27C7D, bytes.fromhex("E8AEB8FDFF"), bytes.fromhex("E87E173900")),
            (0x27C92, bytes.fromhex("E899B8FDFF"), bytes.fromhex("E869173900")),
            (0x27D6C, bytes.fromhex("E8BFB7FDFF"), bytes.fromhex("E88F163900")),
            (0x27D81, bytes.fromhex("E8AAB7FDFF"), bytes.fromhex("E87A163900")),
        ),
        _imports(COMMON_IMPORTS_VV3, 0x7BA000),
    ),
    "vv4": AtomicWriterConfig(
        "vv4", 0x871200, 0xE3200, 0x871C00,
        0x872000, 0xE4000, 0x472000,
        bytes.fromhex("6C2147000000000000000000F020470084214700"),
        "6635B445C7ED82230AEF02BA0DD012268582B61BE31E976C6C72864AE933ADAD",
        0xB5BDC, "4B2748952F5DB3972D4990FFBE5A159754A553316B8EB6557B55D4AB938F668C",
        0x180, bytes.fromhex("DC5B0B00DC000000"), bytes.fromhex("00204700F0000000"),
        0x4B8228, 0x18, 0x10, 0x1DCB4, 0x4039B0, 0x106, 0x150, 6, 7, 0x472000, 0x473000,
        ((0x2E8, bytes.fromhex("2E7676346900000000100000002047000010000000400E00000000000000000000000000400000C0")),),
        0x1000,
        (
            (0x1F04D, bytes.fromhex("E85E49FEFF"), bytes.fromhex("E8AE214500")),
            (0x1F060, bytes.fromhex("E84B49FEFF"), bytes.fromhex("E89B214500")),
            (0x1F13A, bytes.fromhex("E87148FEFF"), bytes.fromhex("E8C1204500")),
            (0x1F14F, bytes.fromhex("E85C48FEFF"), bytes.fromhex("E8AC204500")),
        ),
        _imports(COMMON_IMPORTS_VV45, 0x872000),
    ),
    "vv5": AtomicWriterConfig(
        "vv5", 0x902000, 0xF2000, 0x902A00,
        0x903000, 0xF3000, 0x503000,
        bytes.fromhex("6C3150000000000000000000F030500084315000"),
        "47D78D31AF0AD9CF212232CEA5624C4BC698F3CC1F641BB91E548D26DD6201E4",
        0xC3E24, "50FCCE42F4C7EFF1F716C08F64FDAFF91682A9F7B94E36F62753D17E1720A9D3",
        0x178, bytes.fromhex("243E0C00DC000000"), bytes.fromhex("00305000F0000000"),
        0x4C6248, 0x18, 0x10, 0x1F168, 0x403940, 0x0FE, 0x148, 5, 7, 0x502000, 0x504000,
        (
            (0x2B8, bytes.fromhex("2E7676356177000000100000002050000010000000200F0000000000000000000000000020000060")),
            (0x2E0, bytes.fromhex("2E7676356900000000100000003050000010000000300F00000000000000000000000000400000C0")),
        ),
        0x2000,
        (
            (0x2450D, bytes.fromhex("E82EF4FDFF"), bytes.fromhex("E8EEDA4D00")),
            (0x24520, bytes.fromhex("E81BF4FDFF"), bytes.fromhex("E8DBDA4D00")),
            (0x245FA, bytes.fromhex("E841F3FDFF"), bytes.fromhex("E801DA4D00")),
            (0x2460F, bytes.fromhex("E82CF3FDFF"), bytes.fromhex("E8ECD94D00")),
        ),
        _imports(COMMON_IMPORTS_VV5, 0x903000),
    ),
}


def _keystone():
    try:
        from keystone import KS_ARCH_X86, KS_MODE_32, Ks
        return KS_ARCH_X86, KS_MODE_32, Ks
    except (ImportError, OSError):
        runtime = ROOT / ".tools" / "keystone-runtime"
        if runtime.is_dir():
            sys.path.insert(0, str(runtime))
        from keystone import KS_ARCH_X86, KS_MODE_32, Ks
        return KS_ARCH_X86, KS_MODE_32, Ks


def build_import_page(config: AtomicWriterConfig, original_import_block: bytes) -> bytes:
    if len(original_import_block) != 220:
        raise ValueError("atomic writer original import block must be exactly 220 bytes")
    if hashlib.sha256(original_import_block).hexdigest().upper() != config.original_import_sha256:
        raise ValueError("atomic writer original import descriptor hash mismatch")
    if any(original_import_block[200:]):
        raise ValueError("atomic writer original import descriptor terminator is not zero")
    page = bytearray(0x1000)
    page[:200] = original_import_block[:200]
    page[0xC8:0xDC] = config.import_descriptor
    page[0xF0:0xFD] = b"KERNEL32.dll\0"
    for offset, name in IMPORT_NAMES:
        encoded = name.encode("ascii") + b"\0"
        page[offset:offset + 2] = b"\0\0"
        page[offset + 2:offset + 2 + len(encoded)] = encoded
    for index, (offset, _) in enumerate(IMPORT_NAMES):
        value = config.import_page_rva + offset
        page[0x16C + index * 4:0x170 + index * 4] = value.to_bytes(4, "little")
        page[0x184 + index * 4:0x188 + index * 4] = value.to_bytes(4, "little")
    if hashlib.sha256(page).hexdigest().upper() != config.import_page_sha256:
        raise ValueError("atomic writer import page hash mismatch")
    return bytes(page)


def assembly_source(config: AtomicWriterConfig) -> str:
    i = config.iat
    return f"""
        push ebp
        mov ebp, esp
        push ebx
        push esi
        push edi
        sub esp, 0x840
        mov dword ptr [ebp-0x10], ecx
        mov eax, dword ptr [ebp+8]
        mov dword ptr [ebp-0x18], eax
        mov eax, dword ptr [ebp+0xC]
        mov dword ptr [ebp-0x1C], eax
        mov eax, dword ptr [ebp+0x10]
        mov dword ptr [ebp-0x20], eax
        mov dword ptr [ebp-0x2C], -1
        mov dword ptr [ebp-0x30], -1
        mov dword ptr [ebp-0x34], 0
        test ecx, ecx
        jz fatal
        cmp dword ptr [ebp-0x18], 0
        je fatal
        mov eax, dword ptr [ebp-0x1C]
        cmp eax, 0x88
        je size_settings
        cmp eax, 0x{config.full_body_size:X}
        jne fatal
        cmp dword ptr [ebp-0x20], 0
        jle fatal
        jmp size_ok
    size_settings:
        cmp dword ptr [ebp-0x20], 0
        jne fatal
    size_ok:
        push 0
        push 1
        push 0x{i['lock']:X}
        call dword ptr [0x{i['InterlockedCompareExchange']:X}]
        test eax, eax
        jne fatal
        mov dword ptr [ebp-0x24], 0
        mov eax, dword ptr [ebp-0x20]
        test eax, eax
        jz resolve_final_path
        add eax, 0x14
        jc fatal
        mov ecx, dword ptr [ebp-0x10]
        mov edx, dword ptr [ecx]
        push eax
        call dword ptr [edx+0x0C]
        test eax, eax
        jz fatal
        mov dword ptr [ebp-0x5C], eax
        push eax
        call dword ptr [0x{i['lstrlenA']:X}]
        test eax, eax
        jle fatal
        cmp eax, 223
        ja fatal
        inc eax
        mov ecx, eax
        mov esi, dword ptr [ebp-0x5C]
        lea edi, [ebp-0x730]
        rep movsb
        lea eax, [ebp-0x730]
        mov dword ptr [ebp-0x24], eax
    resolve_final_path:
        mov ecx, dword ptr [ebp-0x10]
        mov eax, dword ptr [ecx]
        push dword ptr [ebp-0x20]
        call dword ptr [eax+0x0C]
        test eax, eax
        jz fatal
        mov dword ptr [ebp-0x14], eax
        push eax
        call dword ptr [0x{i['lstrlenA']:X}]
        test eax, eax
        jle fatal
        cmp eax, 223
        ja fatal
        inc eax
        mov ecx, eax
        mov esi, dword ptr [ebp-0x14]
        lea edi, [ebp-0x830]
        rep movsb
        lea eax, [ebp-0x830]
        mov dword ptr [ebp-0x14], eax
        mov esi, 0x{config.header_va:X}
        lea edi, [ebp-0x80]
        mov ecx, 0x{config.header_size // 4:X}
        rep movsd dword ptr es:[edi], dword ptr [esi]
        mov eax, dword ptr [ebp-0x1C]
        mov dword ptr [ebp-0x{0x80-config.header_size_offset:X}], eax
        add eax, 0x{config.header_size:X}
        jc fatal
        mov dword ptr [ebp-0x28], eax
        call dword ptr [0x{i['GetCurrentProcessId']:X}]
        mov dword ptr [ebp-0x40], eax
        mov dword ptr [ebp-0x58], 32
    create_retry:
        call dword ptr [0x{i['GetTickCount']:X}]
        mov dword ptr [ebp-0x44], eax
        push 0x{i['counter']:X}
        call dword ptr [0x{i['InterlockedIncrement']:X}]
        mov dword ptr [ebp-0x3C], eax
        push eax
        push dword ptr [ebp-0x44]
        push dword ptr [ebp-0x40]
        push dword ptr [ebp-0x14]
        push 0x{config.format_va:X}
        lea eax, [ebp-0x628]
        push eax
        call dword ptr [0x{i['wsprintfA']:X}]
        add esp, 24
        test eax, eax
        jle fatal
        cmp eax, 259
        ja fatal
        push 0
        push 0x80000080
        push 1
        push 0
        push 0
        push 0xC0010000
        lea eax, [ebp-0x628]
        push eax
        call dword ptr [0x{i['CreateFileA']:X}]
        cmp eax, -1
        jne created
        call dword ptr [0x{i['GetLastError']:X}]
        cmp eax, 80
        je retry_name
        cmp eax, 183
        jne fatal
    retry_name:
        dec dword ptr [ebp-0x58]
        jnz create_retry
        jmp fatal
    created:
        mov dword ptr [ebp-0x2C], eax
        push 0x{config.header_size:X}
        lea ecx, [ebp-0x80]
        push ecx
        push eax
        call write_all
        push dword ptr [ebp-0x1C]
        push dword ptr [ebp-0x18]
        push dword ptr [ebp-0x2C]
        call write_all
        push dword ptr [ebp-0x2C]
        call dword ptr [0x{i['FlushFileBuffers']:X}]
        test eax, eax
        jz fatal
        lea eax, [ebp-0xC0]
        push eax
        push dword ptr [ebp-0x2C]
        call dword ptr [0x{i['GetFileInformationByHandle']:X}]
        test eax, eax
        jz fatal
        test dword ptr [ebp-0xC0], 0x410
        jnz fatal
        push dword ptr [ebp-0x2C]
        call dword ptr [0x{i['CloseHandle']:X}]
        test eax, eax
        jz fatal
        mov dword ptr [ebp-0x2C], -1
        push 0
        push 0x00200080
        push 3
        push 0
        push 0
        push 0x80010000
        lea eax, [ebp-0x628]
        push eax
        call dword ptr [0x{i['CreateFileA']:X}]
        cmp eax, -1
        je fatal
        mov dword ptr [ebp-0x30], eax
        lea ecx, [ebp-0x100]
        push ecx
        push eax
        call dword ptr [0x{i['GetFileInformationByHandle']:X}]
        test eax, eax
        jz fatal
        test dword ptr [ebp-0x100], 0x410
        jnz fatal
        mov eax, dword ptr [ebp-0xE4]
        cmp eax, dword ptr [ebp-0xA4]
        jne fatal
        mov eax, dword ptr [ebp-0xD4]
        cmp eax, dword ptr [ebp-0x94]
        jne fatal
        mov eax, dword ptr [ebp-0xD0]
        cmp eax, dword ptr [ebp-0x90]
        jne fatal
        mov dword ptr [ebp-0x34], 1
        lea eax, [ebp-0x108]
        push eax
        push dword ptr [ebp-0x30]
        call dword ptr [0x{i['GetFileSizeEx']:X}]
        test eax, eax
        jz fatal
        cmp dword ptr [ebp-0x104], 0
        jne fatal
        mov eax, dword ptr [ebp-0x108]
        cmp eax, dword ptr [ebp-0x28]
        jne fatal
        push 0x{config.header_size:X}
        lea eax, [ebp-0x520]
        push eax
        push dword ptr [ebp-0x30]
        call read_exact
        lea esi, [ebp-0x520]
        lea edi, [ebp-0x80]
        mov ecx, 0x{config.header_size:X}
        repe cmpsb
        jne fatal
        mov eax, dword ptr [ebp-0x18]
        mov dword ptr [ebp-0x50], eax
        mov eax, dword ptr [ebp-0x1C]
        mov dword ptr [ebp-0x4C], eax
    verify_body:
        cmp dword ptr [ebp-0x4C], 0
        je verified_body
        mov eax, dword ptr [ebp-0x4C]
        cmp eax, 0x400
        jbe verify_chunk_ready
        mov eax, 0x400
    verify_chunk_ready:
        mov dword ptr [ebp-0x48], eax
        push eax
        lea ecx, [ebp-0x520]
        push ecx
        push dword ptr [ebp-0x30]
        call read_exact
        lea esi, [ebp-0x520]
        mov edi, dword ptr [ebp-0x50]
        mov ecx, dword ptr [ebp-0x48]
        repe cmpsb
        jne fatal
        mov eax, dword ptr [ebp-0x48]
        add dword ptr [ebp-0x50], eax
        sub dword ptr [ebp-0x4C], eax
        jmp verify_body
    verified_body:
        push dword ptr [ebp-0x30]
        call dword ptr [0x{i['CloseHandle']:X}]
        test eax, eax
        jz fatal
        mov dword ptr [ebp-0x30], -1
        push dword ptr [ebp-0x14]
        call dword ptr [0x{i['GetFileAttributesA']:X}]
        cmp eax, -1
        je final_absent_check
        test eax, 0x410
        jnz fatal
        push 0
        push 0
        push 0
        push dword ptr [ebp-0x24]
        lea eax, [ebp-0x628]
        push eax
        push dword ptr [ebp-0x14]
        call dword ptr [0x{i['ReplaceFileA']:X}]
        test eax, eax
        jz fatal
        jmp committed
    final_absent_check:
        call dword ptr [0x{i['GetLastError']:X}]
        cmp eax, 2
        je final_absent
        cmp eax, 3
        jne fatal
    final_absent:
        push 8
        push dword ptr [ebp-0x14]
        lea eax, [ebp-0x628]
        push eax
        call dword ptr [0x{i['MoveFileExA']:X}]
        test eax, eax
        jz fatal
    committed:
        mov dword ptr [ebp-0x34], 0
        push 0
        push 0x{i['lock']:X}
        call dword ptr [0x{i['InterlockedExchange']:X}]
        mov al, 1
        lea esp, [ebp-0x0C]
        pop edi
        pop esi
        pop ebx
        pop ebp
        ret 0x0C

    write_all:
        push ebx
        push esi
        push edi
        mov ebx, dword ptr [esp+0x10]
        mov esi, dword ptr [esp+0x14]
        mov edi, dword ptr [esp+0x18]
    write_loop:
        test edi, edi
        jz write_done
        push 0
        lea eax, [ebp-0x38]
        push eax
        push edi
        push esi
        push ebx
        call dword ptr [0x{i['WriteFile']:X}]
        test eax, eax
        jz fatal
        mov eax, dword ptr [ebp-0x38]
        test eax, eax
        jz fatal
        cmp eax, edi
        ja fatal
        add esi, eax
        sub edi, eax
        jmp write_loop
    write_done:
        pop edi
        pop esi
        pop ebx
        ret 0x0C

    read_exact:
        push ebx
        push esi
        push edi
        mov ebx, dword ptr [esp+0x10]
        mov esi, dword ptr [esp+0x14]
        mov edi, dword ptr [esp+0x18]
    read_loop:
        test edi, edi
        jz read_done
        push 0
        lea eax, [ebp-0x38]
        push eax
        push edi
        push esi
        push ebx
        call dword ptr [0x{i['ReadFile']:X}]
        test eax, eax
        jz fatal
        mov eax, dword ptr [ebp-0x38]
        test eax, eax
        jz fatal
        cmp eax, edi
        ja fatal
        add esi, eax
        sub edi, eax
        jmp read_loop
    read_done:
        pop edi
        pop esi
        pop ebx
        ret 0x0C

    fatal:
        mov eax, dword ptr [ebp-0x2C]
        cmp eax, -1
        je fatal_verify_handle
        push eax
        call dword ptr [0x{i['CloseHandle']:X}]
        mov dword ptr [ebp-0x2C], -1
    fatal_verify_handle:
        mov eax, dword ptr [ebp-0x30]
        cmp eax, -1
        je fatal_reopen
        cmp dword ptr [ebp-0x34], 1
        jne fatal_close_verify
        push 1
        lea ecx, [ebp-0x734]
        mov byte ptr [ecx], 1
        push ecx
        push 4
        push eax
        call dword ptr [0x{i['SetFileInformationByHandle']:X}]
    fatal_close_verify:
        push dword ptr [ebp-0x30]
        call dword ptr [0x{i['CloseHandle']:X}]
        mov dword ptr [ebp-0x30], -1
        jmp fatal_terminate
    fatal_reopen:
        cmp dword ptr [ebp-0x34], 1
        jne fatal_terminate
        push 0
        push 0x00200080
        push 3
        push 0
        push 0
        push 0x00010080
        lea eax, [ebp-0x628]
        push eax
        call dword ptr [0x{i['CreateFileA']:X}]
        cmp eax, -1
        je fatal_terminate
        mov dword ptr [ebp-0x30], eax
        lea ecx, [ebp-0x100]
        push ecx
        push eax
        call dword ptr [0x{i['GetFileInformationByHandle']:X}]
        test eax, eax
        jz fatal_close_verify
        test dword ptr [ebp-0x100], 0x410
        jnz fatal_close_verify
        mov eax, dword ptr [ebp-0xE4]
        cmp eax, dword ptr [ebp-0xA4]
        jne fatal_close_verify
        mov eax, dword ptr [ebp-0xD4]
        cmp eax, dword ptr [ebp-0x94]
        jne fatal_close_verify
        mov eax, dword ptr [ebp-0xD0]
        cmp eax, dword ptr [ebp-0x90]
        jne fatal_close_verify
        mov byte ptr [ebp-0x734], 1
        push 1
        lea ecx, [ebp-0x734]
        push ecx
        push 4
        push dword ptr [ebp-0x30]
        call dword ptr [0x{i['SetFileInformationByHandle']:X}]
        jmp fatal_close_verify
    fatal_terminate:
        push 0xE0010256
        push -1
        call dword ptr [0x{i['TerminateProcess']:X}]
        push 0xE0010256
        call dword ptr [0x{i['ExitProcess']:X}]
    fatal_spin:
        int3
        jmp fatal_spin
    """


def assemble_writer(config: AtomicWriterConfig) -> bytes:
    arch, mode, ks_class = _keystone()
    encoded, _ = ks_class(arch, mode).asm(assembly_source(config), config.writer_va)
    blob = bytes(encoded)
    if len(blob) > 0xA00:
        raise ValueError("atomic writer exceeds its reviewed RX code range")
    return blob


def build_writer_page(config: AtomicWriterConfig) -> tuple[bytes, bytes]:
    blob = assemble_writer(config)
    page = bytearray(0x1000)
    page[:len(blob)] = blob
    page[0xA00:0xA00 + len(FORMAT_BYTES)] = FORMAT_BYTES
    return bytes(page), blob


def apply_atomic_writer_bytes(
    source: bytes | bytearray,
    game_id: str,
) -> tuple[bytearray, list[dict[str, object]], dict[str, object]]:
    """Apply the exact guarded writer/PE/import transaction in memory."""
    if game_id not in CONFIGS:
        raise ValueError("atomic writer game is not supported")
    config = CONFIGS[game_id]
    work = bytearray(source)
    expected_parent_size = config.writer_raw if game_id == "vv5" else config.import_page_raw
    if len(work) != expected_parent_size:
        raise ValueError("atomic writer parent size mismatch")
    if bytes(work[config.section_count_raw:config.section_count_raw + 2]) != config.sections_before.to_bytes(2, "little"):
        raise ValueError("atomic writer parent section count mismatch")
    if bytes(work[config.size_of_image_raw:config.size_of_image_raw + 4]) != config.size_of_image_before.to_bytes(4, "little"):
        raise ValueError("atomic writer parent SizeOfImage mismatch")
    if bytes(work[config.import_directory_raw:config.import_directory_raw + 8]) != config.import_directory_before:
        raise ValueError("atomic writer import directory preimage mismatch")
    original_imports = bytes(
        work[config.original_import_raw:config.original_import_raw + 220]
    )
    import_page = build_import_page(config, original_imports)
    writer_page, writer = build_writer_page(config)
    records: list[dict[str, object]] = []

    def write(offset: int, before: bytes, after: bytes, purpose: str) -> None:
        if len(before) != len(after):
            raise ValueError("atomic writer guarded write changes length")
        actual = bytes(work[offset:offset + len(before)])
        if actual != before:
            raise ValueError(
                f"atomic writer byte guard failed at 0x{offset:X}: "
                f"expected {before.hex().upper()}, found {actual.hex().upper()}"
            )
        work[offset:offset + len(after)] = after
        records.append(
            {
                "offset": f"0x{offset:X}",
                "before": before.hex().upper(),
                "after": after.hex().upper(),
                "purpose": purpose,
            }
        )

    write(
        config.section_count_raw,
        config.sections_before.to_bytes(2, "little"),
        config.sections_after.to_bytes(2, "little"),
        f"add reviewed {game_id} atomic writer sections",
    )
    write(
        config.size_of_image_raw,
        config.size_of_image_before.to_bytes(4, "little"),
        config.size_of_image_after.to_bytes(4, "little"),
        f"extend {game_id} image for atomic writer",
    )
    for raw, header in config.section_headers:
        write(raw, bytes(40), header, f"add {game_id} atomic writer section header")
    write(
        config.import_directory_raw,
        config.import_directory_before,
        config.import_directory_after,
        f"route {game_id} imports through guarded duplicate KERNEL32 descriptor",
    )
    for raw, before, after in config.callsites:
        write(raw, before, after, f"route {game_id} stock save call through atomic writer")

    if game_id == "vv5":
        work.extend(writer_page)
        records.append(
            {
                "offset": f"0x{config.writer_raw:X}", "before": "",
                "after": writer_page.hex().upper(),
                "purpose": "append guarded VV5 atomic writer RX page",
            }
        )
    else:
        writer_raw_end = config.writer_raw + 0xA00 + len(FORMAT_BYTES)
        if any(work[config.writer_raw:writer_raw_end]):
            raise ValueError("atomic writer existing RX cave is not zero")
        write(
            config.writer_raw,
            bytes(len(writer)),
            writer,
            f"install {game_id} parameterized atomic writer",
        )
        write(
            config.writer_raw + 0xA00,
            bytes(len(FORMAT_BYTES)),
            FORMAT_BYTES,
            f"install {game_id} sibling temporary format",
        )
    if len(work) != config.import_page_raw:
        raise ValueError("atomic writer import page append offset mismatch")
    work.extend(import_page)
    records.append(
        {
            "offset": f"0x{config.import_page_raw:X}", "before": "",
            "after": import_page.hex().upper(),
            "purpose": f"append guarded {game_id} atomic import/IAT page",
        }
    )
    if len(work) != expected_parent_size + config.append_size:
        raise ValueError("atomic writer final file size mismatch")
    metadata = {
        "writer_va": f"0x{config.writer_va:X}",
        "writer_raw": f"0x{config.writer_raw:X}",
        "writer_length": len(writer),
        "writer_sha256": hashlib.sha256(writer).hexdigest().upper(),
        "import_page_sha256": hashlib.sha256(import_page).hexdigest().upper(),
        "callsite_count": len(config.callsites),
        "failure_policy": "fatal_nonreturn_on_uncertain_failure",
        "runtime_go": False,
        "player_go": False,
        "publication_ready": False,
    }
    return work, records, metadata


def fault_model(*, final_exists: bool, fail_at: str | None = None) -> dict[str, object]:
    """Pure model for fail-closed transaction tests; it performs no I/O."""
    prior = b"old" if final_exists else None
    temp = b"new"
    verified = False
    committed = False
    stages = (
        "create", "write_header", "write_body", "flush", "close_write",
        "reopen_nofollow", "identity", "size", "readback", "close_verify",
        "commit",
    )
    for stage in stages:
        if fail_at == stage:
            if verified:
                temp = None
            commit_uncertain = stage == "commit"
            return {
                "fatal": True, "prior_final": prior,
                "final": None if commit_uncertain else prior,
                "final_known": not commit_uncertain,
                "temp": temp, "verified": verified, "committed": False,
            }
        if stage == "identity":
            verified = True
        if stage == "commit":
            committed = True
    return {
        "fatal": False, "prior_final": prior, "final": b"new",
        "final_known": True,
        "temp": None, "verified": verified, "committed": committed,
    }
