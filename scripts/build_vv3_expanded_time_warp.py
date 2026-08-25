"""Build the reviewed VV3 Expanded-256-only Time Warp core profile."""

from __future__ import annotations

import base64
import hashlib
import json
import struct
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SELF = ROOT / "scripts/build_vv3_expanded_time_warp.py"
MANIFEST_OUT = ROOT / "data/vv3_expanded_time_warp.json"
MAP_OUT = ROOT / "data/candidates/vv3_expanded_time_warp_map.json"
CORE_OUT = ROOT / "data/vv3_expanded_time_warp_core.json"
COMPANION = ROOT / "data/candidates/VVFP VV5 Task9 Origins Icons.dll"
STATIC_CANDIDATE = ROOT / "data/candidates/vv3_full256_serializer_candidate.json"
ATOMIC_GENERATOR = ROOT / "src/expanded_atomic_writer.py"

COMPANION_SHA256 = "E8487A8A6328D04EFFEDED580ADFC6CA5E0E6DF6CFAF3B3AEAFCD3811991B348"
COMPANION_SIZE = 1753088
STOCK_SHA256 = "8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503"
STATIC_PAGE_SHA256 = "9F82D59D1436B17ACA69CD637AB40D44DF35323DA46600AAA5FD07315C249B64"
ATOMIC_WRITER_SHA256 = "CEE9E08759B1504C798E4BBE3AD39799358E2A93C8537DBECBE294D53D251154"
ATOMIC_IMPORT_SHA256 = "291FA68AE4F320C92226DFE735BD4559CE79BCDC949BECC2F4AFF7D6FC1E2A50"
FEATURE_ID = "vv3_expanded_256_time_warp"
MODES = (
    "experimental_expanded_256",
    "experimental_expanded_256_progression",
)

PAGE_RAW = 0xCB000
PAGE_RVA = 0x3B8000
PAGE_VA = 0x7B8000
PAGE_SIZE = 0x1000
HANDLER = PAGE_VA + 0x40
CONSTRUCTOR = PAGE_VA + 0x80
SHOW_MENU = PAGE_VA + 0x180
SHOW_MESSAGE = PAGE_VA + 0x200
TRANSACTION = PAGE_VA + 0x300
STRINGS_OFFSET = 0xC00

HEADER = bytes.fromhex(
    "2E767633747700000010000000803B000010000000B00C0000000000000000000000000020000060"
)

sys.path.insert(0, str(ROOT / ".tools/keystone-runtime"))
sys.path.insert(1, str(ROOT / ".tools/keystone"))
sys.path.insert(2, str(ROOT / "src"))
from keystone import KS_ARCH_X86, KS_MODE_32, Ks  # noqa: E402
import vv_fun_patcher as patcher  # noqa: E402
from expanded_atomic_writer import CONFIGS, apply_atomic_writer_bytes  # noqa: E402


def asm(source: str, address: int) -> bytes:
    encoded, _ = Ks(KS_ARCH_X86, KS_MODE_32).asm(source, address)
    return bytes(encoded)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def source_text_sha(path: Path) -> str:
    return patcher.source_text_sha256(path.read_bytes())


def companion() -> dict[str, object]:
    data = COMPANION.read_bytes()
    if len(data) != COMPANION_SIZE or sha(data) != COMPANION_SHA256:
        raise RuntimeError("Task9 companion identity mismatch")
    return {
        "source": "data/candidates/VVFP VV5 Task9 Origins Icons.dll",
        "destination": "VVFP Origins Icons.dll",
        "sha256": COMPANION_SHA256,
        "size": COMPANION_SIZE,
    }


def build_page() -> tuple[bytes, dict[str, object]]:
    page = bytearray(PAGE_SIZE)
    occupied = bytearray(PAGE_SIZE)
    labels: dict[str, int] = {}
    cursor = STRINGS_OFFSET
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
        labels[name] = PAGE_VA + cursor
        page[cursor : cursor + len(encoded)] = encoded
        occupied[cursor : cursor + len(encoded)] = b"\1" * len(encoded)
        cursor += len(encoded)
    if cursor > PAGE_SIZE:
        raise RuntimeError("VV3 Time Warp strings exceed the isolated page")

    routines: dict[str, dict[str, object]] = {}

    def put(name: str, offset: int, source: str, limit: int) -> bytes:
        encoded = asm(source, PAGE_VA + offset)
        if len(encoded) > limit:
            raise RuntimeError(
                f"VV3 Time Warp {name} exceeds reserve: {len(encoded):#x}/{limit:#x}"
            )
        if any(occupied[offset : offset + limit]):
            raise RuntimeError(f"VV3 Time Warp {name} overlaps another region")
        page[offset : offset + len(encoded)] = encoded
        occupied[offset : offset + len(encoded)] = b"\1" * len(encoded)
        routines[name] = {
            "offset": f"0x{offset:X}",
            "va": f"0x{PAGE_VA + offset:X}",
            "length": len(encoded),
            "sha256": sha(encoded),
        }
        return encoded

    put(
        "handler",
        0x40,
        f"""
            cmp dword ptr [esp+4], 8
            jne original
            cmp dword ptr [esp+8], 15
            jne original
            call 0x{TRANSACTION:X}
            xor eax, eax
            ret 8
        original:
            push -1
            mov eax, dword ptr fs:[0]
            jmp 0x465648
        """,
        0x40,
    )
    put(
        "constructor",
        0x80,
        f"""
            push 0x14
            call 0x46EC93
            add esp, 4
            test eax, eax
            je constructor_done
            mov edi, eax
            call 0x42E9D0
            mov ecx, eax
            push 3
            call 0x42E8A0
            push 0
            push esi
            push 563
            push 138
            push eax
            push 15
            mov ecx, edi
            call 0x4019F0
            mov edi, eax
            push 0
            push 0xFF555555
            push 0xFF555555
            push 0xFF000000
            push 0x{labels['button']:X}
            mov ecx, edi
            call 0x401620
            push edi
            mov ecx, esi
            call 0x40C1F0
        constructor_done:
            mov ecx, dword ptr [esp+0x3C]
            pop edi
            mov eax, esi
            pop esi
            pop ebp
            pop ebx
            mov dword ptr fs:[0], ecx
            add esp, 0x38
            ret
        """,
        0x100,
    )
    put(
        "show_menu",
        0x180,
        f"""
            push ebx
            push esi
            push 0x{labels['dll']:X}
            call dword ptr [0x47C124]
            test eax, eax
            jz unavailable
            push 0x{labels['menu']:X}
            push eax
            call dword ptr [0x47C128]
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
        0x80,
    )
    put(
        "show_message",
        0x200,
        f"""
            push ebx
            push esi
            push edi
            mov esi, dword ptr [esp+0x10]
            mov edi, dword ptr [esp+0x14]
            push 0x{labels['dll']:X}
            call dword ptr [0x47C124]
            test eax, eax
            jz done
            push 0x{labels['get']:X}
            push eax
            call dword ptr [0x47C128]
            test eax, eax
            jz done
            call eax
            test eax, eax
            jz done
            xchg ebx, eax
            push 0x{labels['user32']:X}
            call dword ptr [0x47C124]
            test eax, eax
            jz done
            push 0x{labels['messagebox']:X}
            push eax
            call dword ptr [0x47C128]
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
        0x100,
    )
    put(
        "transaction",
        0x300,
        f"""
            push ebp
            push ebx
            push esi
            push edi
            sub esp, 0x50
            mov esi, esp
            mov dword ptr [esi], 0
            mov dword ptr [esi+4], 0
            push 0x{labels['dll']:X}
            call dword ptr [0x47C124]
            test eax, eax
            jz cleanup
            mov ebx, eax
            push 0x{labels['end']:X}
            push ebx
            call dword ptr [0x47C128]
            test eax, eax
            jz cleanup
            mov dword ptr [esi], eax
            push 0x{labels['begin']:X}
            push ebx
            call dword ptr [0x47C128]
            test eax, eax
            jz cleanup
            mov dword ptr [esi+4], 1
            call eax
            test eax, eax
            jz cleanup
            push 0x3E00
            call 0x{SHOW_MENU:X}
            cmp eax, -1
            je cleanup
            test eax, eax
            jne unavailable
            call 0x428B60
            test eax, eax
            jz unavailable
            mov edi, eax
            xor ebp, ebp
            cmp dword ptr [0x42883A], 0x100
            jne initial_offset_ready
            mov ebp, 0x7598
        initial_offset_ready:
            mov dword ptr [esi+8], ebp
            mov eax, dword ptr [edi+ebp+0x12F20]
            cmp eax, 999
            je paused
            cmp eax, 3
            je initial_speed_ready
            cmp eax, 10
            je initial_speed_ready
            mov eax, 6
        initial_speed_ready:
            mov dword ptr [esi+0xC], eax
            mov dword ptr [esi+0x10], edi
            mov eax, dword ptr [0x582644]
            mov dword ptr [esi+0x14], eax
            cmp eax, 50000
            jb insufficient
            mov eax, dword ptr [0x4A4210]
            mov dword ptr [esi+0x18], eax
            mov eax, dword ptr [0x4A4214]
            mov dword ptr [esi+0x1C], eax
            push 1
            push 0x{labels['warning']:X}
            call 0x{SHOW_MESSAGE:X}
            cmp eax, 1
            jne cancelled
            call 0x428B60
            cmp eax, dword ptr [esi+0x10]
            jne recheck
            mov edi, eax
            xor ebp, ebp
            cmp dword ptr [0x42883A], 0x100
            jne fresh_offset_ready
            mov ebp, 0x7598
        fresh_offset_ready:
            cmp ebp, dword ptr [esi+8]
            jne recheck
            mov eax, dword ptr [edi+ebp+0x12F20]
            cmp eax, 999
            je recheck
            cmp eax, 3
            je fresh_speed_ready
            cmp eax, 10
            je fresh_speed_ready
            mov eax, 6
        fresh_speed_ready:
            cmp eax, dword ptr [esi+0xC]
            jne recheck
            mov eax, dword ptr [0x582644]
            cmp eax, dword ptr [esi+0x14]
            jne recheck
            cmp eax, 50000
            jb insufficient
            mov eax, dword ptr [0x4A4210]
            cmp eax, dword ptr [esi+0x18]
            jne recheck
            mov eax, dword ptr [0x4A4214]
            cmp eax, dword ptr [esi+0x1C]
            jne recheck
            sub dword ptr [0x582644], 50000
            mov eax, dword ptr [esi+0x14]
            sub eax, 50000
            mov dword ptr [esi+0x20], eax
            cmp dword ptr [0x582644], eax
            jne charge_unknown
            mov eax, dword ptr [esi+0xC]
            imul eax, eax, 3600
            mov dword ptr [esi+0x24], eax
            mov ecx, dword ptr [esi+0x18]
            mov edx, dword ptr [esi+0x1C]
            sub ecx, eax
            sbb edx, 0
            mov dword ptr [esi+0x28], ecx
            mov dword ptr [esi+0x2C], edx
            sub dword ptr [0x4A4210], eax
            sbb dword ptr [0x4A4214], 0
            cmp dword ptr [0x4A4210], ecx
            jne clock_unknown
            cmp dword ptr [0x4A4214], edx
            jne clock_unknown
            push 0x40
            push 0x{labels['success']:X}
            call 0x{SHOW_MESSAGE:X}
            jmp cleanup
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
            push 0x30
            push eax
            call 0x{SHOW_MESSAGE:X}
        cleanup:
            cmp dword ptr [esi+4], 0
            je done
            call dword ptr [esi]
        done:
            add esp, 0x50
            pop edi
            pop esi
            pop ebx
            pop ebp
            ret
        """,
        STRINGS_OFFSET - 0x300,
    )
    return bytes(page), {
        "page_raw": f"0x{PAGE_RAW:X}",
        "page_rva": f"0x{PAGE_RVA:X}",
        "page_va": f"0x{PAGE_VA:X}",
        "page_size": PAGE_SIZE,
        "page_sha256": sha(bytes(page)),
        "routines": routines,
        "strings_offset": f"0x{STRINGS_OFFSET:X}",
        "strings_length": cursor - STRINGS_OFFSET,
        "strings_sha256": sha(bytes(page[STRINGS_OFFSET:cursor])),
        "strings": {key: f"0x{value:X}" for key, value in labels.items()},
    }


def canonicalize(data: bytearray) -> tuple[str, str]:
    checksum_raw, _ = patcher._pe_checksum_layout(data)
    struct.pack_into("<I", data, checksum_raw, 0)
    struct.pack_into("<I", data, checksum_raw, patcher.pe_checksum(data))
    return sha(bytes(data)), bytes(data[checksum_raw : checksum_raw + 4]).hex().upper()


def apply_rows(data: bytearray, rows: list[dict[str, object]]) -> None:
    for row in rows:
        raw = int(str(row["offset"]), 0)
        before = patcher._patch_bytes(row, "before")
        after = patcher._patch_bytes(row, "after")
        if bytes(data[raw : raw + len(before)]) != before:
            raise RuntimeError(f"row preimage mismatch at {raw:#x}")
        data[raw : raw + len(after)] = after


def expanded_parent(mode: str) -> bytearray:
    build = next(item for item in patcher.load_builds() if item.id == "vv3")
    source = ROOT / "research/stock-executables" / build.input_name
    original = source.read_bytes()
    if sha(original) != STOCK_SHA256:
        raise RuntimeError("VV3 stock identity mismatch")
    variant = patcher.get_patch_variant(build, mode)
    data = bytearray(original)
    apply_rows(data, patcher._expanded_patches(build, variant))
    apply_rows(data, patcher._safety_patches(build, mode))
    apply_rows(data, variant["patches"])
    canonicalize(data)
    if len(data) != PAGE_RAW:
        raise RuntimeError("VV3 Expanded parent size drift")
    return data


def install_time_warp(parent: bytearray, page: bytes) -> bytearray:
    data = bytearray(parent)
    header_rows = [
        {"offset": "0x10E", "before": "0500", "after": "0600"},
        {"offset": "0x158", "before": "00803B00", "after": "00903B00"},
        {"offset": "0x2C8", "before": "00" * 40, "after": HEADER.hex()},
    ]
    apply_rows(data, header_rows)
    data.extend(page)
    apply_rows(
        data,
        [
            {"offset": "0x6547D", "before": "8B4C243C5F", "after": "E9FE2B3500"},
            {"offset": "0x65640", "before": "6AFF64A100000000", "after": "E9FB293500909090"},
        ],
    )
    canonicalize(data)
    return data


def install_static(parent: bytearray) -> bytearray:
    candidate = json.loads(STATIC_CANDIDATE.read_text(encoding="utf-8"))
    data = bytearray(parent)
    pe = candidate["pe_guards"]
    section = candidate["section_plan"]
    rows: list[dict[str, object]] = [
        {"offset": pe["section_count_raw"], "before": pe["section_count_before"], "after": pe["section_count_after"]},
        {"offset": pe["size_of_image_raw"], "before": pe["size_of_image_before"], "after": pe["size_of_image_after"]},
        {"offset": section["header_raw"], "before": section["header_guard"], "after": section["header_bytes"]},
    ]
    rows.extend(
        {"offset": row["raw"], "before": row["preimage"], "after": row["after"]}
        for row in candidate["hooks"]
    )
    apply_rows(data, rows)
    page = patcher._static_repair_page(candidate, "vv3")
    if sha(page) != STATIC_PAGE_SHA256:
        raise RuntimeError("VV3 static page identity drift")
    data.extend(page)
    canonicalize(data)
    return data


def install_atomic(parent: bytearray) -> tuple[bytearray, dict[str, object]]:
    data, _, metadata = apply_atomic_writer_bytes(bytearray(parent), "vv3")
    canonicalize(data)
    if metadata.get("writer_sha256") != ATOMIC_WRITER_SHA256:
        raise RuntimeError("VV3 atomic writer identity drift")
    if metadata.get("import_page_sha256") != ATOMIC_IMPORT_SHA256:
        raise RuntimeError("VV3 atomic import identity drift")
    return data, metadata


def install_statistics(parent: bytearray) -> bytearray:
    statistics = json.loads((ROOT / "data/statistics_features.json").read_text(encoding="utf-8"))
    record = next(item for item in statistics["features"] if item["id"] == "vv3_write_village_statistics")
    data = bytearray(parent)
    rows = []
    for row in record["patches"]:
        item = dict(row)
        item["_owner"] = "feature:vv3_write_village_statistics"
        rows.append(item)
    rows.append(
        {
            "offset": "0xCB000",
            "before_fill": "00",
            "length": 1,
            "after": "00",
            "_owner": f"feature:{FEATURE_ID}",
        }
    )
    build = next(item for item in patcher.load_builds() if item.id == "vv3")
    composed = patcher._compose_expanded_statistics_after_atomic(
        data, build, MODES[0], rows
    )
    composed = [row for row in composed if row.get("_owner") == "feature:vv3_write_village_statistics"]
    apply_rows(data, composed)
    canonicalize(data)
    return data


def source_bindings() -> dict[str, dict[str, str]]:
    paths = {
        "builder": "scripts/build_vv3_expanded_time_warp.py",
        "static_candidate": "data/candidates/vv3_full256_serializer_candidate.json",
        "atomic_generator": "src/expanded_atomic_writer.py",
        "task9_companion_c": "native/vv5_task9_origins/vv5_task9_origins.c",
        "task9_companion_def": "native/vv5_task9_origins/vv5_task9_origins.def",
        "task9_companion_rc": "native/vv5_task9_origins/vv5_task9_origins.rc",
    }
    return {
        name: {"path": path, "source_text_sha256": source_text_sha(ROOT / path)}
        for name, path in paths.items()
    }


def main() -> None:
    page, layout = build_page()
    bindings = source_bindings()
    identities: dict[str, dict[str, object]] = {}
    for mode in MODES:
        base = expanded_parent(mode)
        base_sha, base_checksum = canonicalize(base)
        time_warp = install_time_warp(base, page)
        time_warp_sha, time_warp_checksum = canonicalize(time_warp)
        static = install_static(time_warp)
        static_sha, static_checksum = canonicalize(static)
        atomic, atomic_metadata = install_atomic(static)
        atomic_sha, atomic_checksum = canonicalize(atomic)
        statistics = install_statistics(atomic)
        statistics_sha, statistics_checksum = canonicalize(statistics)
        identities[mode] = {
            "expanded_parent": {"size": len(base), "sha256": base_sha, "checksum": base_checksum},
            "time_warp_result": {"size": len(time_warp), "sha256": time_warp_sha, "checksum": time_warp_checksum},
            "static_result": {"size": len(static), "sha256": static_sha, "checksum": static_checksum},
            "atomic_result": {"size": len(atomic), "sha256": atomic_sha, "checksum": atomic_checksum},
            "statistics_result": {"size": len(statistics), "sha256": statistics_sha, "checksum": statistics_checksum},
        }
        if atomic_metadata.get("writer_sha256") != ATOMIC_WRITER_SHA256:
            raise RuntimeError("VV3 atomic writer metadata mismatch")

    transaction = {
        "owner": FEATURE_ID,
        "section_name": ".vv3tw",
        "append_length": PAGE_SIZE,
        "removal_policy": "automatic .vv3i and .vv3sv pages must be removed first, then the exact Time Warp page is restored and truncated",
        "layouts": {
            mode: {
                "original_file_size": "0xCB000",
                "append_offset": "0xCB000",
                "append_source": "generated:vv3_expanded_time_warp_page",
                "page_sha256": layout["page_sha256"],
                "virtual_address": "0x7B8000",
                "purpose": "append the isolated reviewed VV3 Expanded Time Warp page",
                "header_patches": [
                    {"offset": "0x10E", "before": "0500", "after": "0600", "purpose": "add the .vv3tw section"},
                    {"offset": "0x158", "before": "00803B00", "after": "00903B00", "purpose": "extend SizeOfImage through .vv3tw"},
                    {"offset": "0x2C8", "before": "00" * 40, "after": HEADER.hex().upper(), "purpose": "install the exact RX .vv3tw section header"},
                ],
            }
            for mode in MODES
        },
    }
    hooks = [
        {"offset": "0x6547D", "before": "8B4C243C5F", "after": "E9FE2B3500", "purpose": "route the Tech constructor through isolated Expanded Time Warp"},
        {"offset": "0x65640", "before": "6AFF64A100000000", "after": "E9FB293500909090", "purpose": "route only Tech message 8 / event 15 through isolated Expanded Time Warp"},
    ]
    manifest = {
        "id": FEATURE_ID,
        "game_id": "vv3",
        "name": "Enable Time Warp (Expanded-256)",
        "description": "Adds only the reviewed Time Warp purchase to VV3 experimental Expanded-256 without installing the Origins or Running mechanics.",
        "output_tag": "Expanded Time Warp",
        "enabled": True,
        "catalog_enabled": False,
        "catalog_hidden": True,
        "experimental_explicit_selection": True,
        "supported_modes": list(MODES),
        "rejected_modes": ["collection_progression", "immediate_fixed"],
        "conflicts": [
            "vv3_enable_origins_exclusive_features_running_candidate",
            "vv3_all_villagers_like_running_candidate",
            "vv3_enable_origins_exclusive_features",
            "vv3_full_mastery_all_stage_a_candidate",
        ],
        "companion_files": [companion()],
        "patches": [],
        "patch_mode_overrides": {mode: hooks for mode in MODES},
        "pe_append_transaction": transaction,
        "source_bindings": bindings,
        "native_contract": {
            "dialog_state": "0x3E00; row 0 enabled and rows 1..5 unavailable",
            "owner": "BeginOriginsOwner/GetOriginsOwner/EndOriginsOwner captured same-process window; every dialog uses that owner",
            "confirmation": "exact permanent-change warning; IDOK only",
            "manager": "0x428B60 nonnull",
            "expanded_offset": "EBP=0x7598 iff dword [0x42883A] == 0x100, otherwise EBP=0",
            "speed": "[EDI+EBP+0x12F20]; paused=999; 3 and 10 accepted, all other values normalize to 6",
            "delta": "normalized speed * 3600",
            "clock": "0x4A4210/0x4A4214 sub/sbb and exact readback",
            "funds": "0x582644 direct one exact -50000 mutation and exact readback before clock mutation",
        },
        "behavior_changes": ["Enables only Time Warp in VV3 experimental Expanded-256 for 50,000 tech points."],
        "explicit_non_changes": ["Stock modes, Origins, Running, villager records, .rdata execute permissions, and the old A3180 payload are unchanged."],
        "evidence_status": "static implementation awaiting independent Disassembler review; runtime/player confirmation pending",
        "runtime_player_status": "pending",
    }
    core = {
        "schema": "vvfp.vv3_expanded_time_warp_core.v1",
        "feature_id": FEATURE_ID,
        "status": "static implementation awaiting independent Disassembler review",
        "runtime_go": False,
        "player_go": False,
        "publication_ready": False,
        "source_bindings": bindings,
        "page": layout,
        "static": {
            "page_raw": "0xCC000",
            "page_rva": "0x3B9000",
            "page_va": "0x7B9000",
            "page_sha256": STATIC_PAGE_SHA256,
        },
        "atomic": {
            "writer_raw": "0xCC400",
            "writer_va": "0x7B9400",
            "writer_sha256": ATOMIC_WRITER_SHA256,
            "import_raw": "0xCD000",
            "import_rva": "0x3BA000",
            "import_va": "0x7BA000",
            "import_sha256": ATOMIC_IMPORT_SHA256,
        },
        "modes": identities,
    }
    artifact = {
        "id": FEATURE_ID,
        "status": "static implementation awaiting independent Disassembler review; runtime/player pending",
        "source_bindings": bindings,
        "companion": companion(),
        "section_header_raw": "0x2C8",
        "section_header": HEADER.hex().upper(),
        "layout": layout,
        "hooks": hooks,
        "core": core,
        "forbidden_mutations": ["stock modes", "old A3180 .rdata payload", "Origins mechanics", "Running mechanics", ".shr", "existing Origins/Running static or atomic bindings"],
    }
    outputs = {
        MANIFEST_OUT: json.dumps(manifest, indent=2) + "\n",
        MAP_OUT: json.dumps(artifact, indent=2) + "\n",
        CORE_OUT: json.dumps(core, indent=2) + "\n",
    }
    check = "--check" in sys.argv[1:]
    unexpected = [arg for arg in sys.argv[1:] if arg != "--check"]
    if unexpected:
        raise RuntimeError(f"unknown arguments: {unexpected}")
    for path, rendered in outputs.items():
        if check:
            if not path.is_file() or path.read_text(encoding="utf-8") != rendered:
                raise RuntimeError(f"generated artifact is stale: {path.relative_to(ROOT)}")
        else:
            path.write_text(rendered, encoding="utf-8")
    print(f"VV3 Time Warp page {len(page)} bytes {layout['page_sha256']}")
    for mode, identity in identities.items():
        print(f"{mode}: {identity['atomic_result']['sha256']} / Statistics {identity['statistics_result']['sha256']}")


if __name__ == "__main__":
    main()
