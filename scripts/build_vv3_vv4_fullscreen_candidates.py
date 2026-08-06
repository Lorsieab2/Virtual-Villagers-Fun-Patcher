"""Emit disabled, exact-parent fullscreen-safe VV3/VV4 candidate evidence.

This builder only creates source-owned manifest/map evidence.  It never changes
the public catalog and rejects any parent, hook, section, or mode mismatch.
"""
from __future__ import annotations

import hashlib
import json
import struct
import sys
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "candidates"

sys.path.insert(0, str(ROOT / ".tools" / "keystone-runtime"))
sys.path.insert(0, str(ROOT / ".tools" / "capstone"))
from keystone import KS_ARCH_X86, KS_MODE_32, Ks  # noqa: E402
from capstone import CS_ARCH_X86, CS_MODE_32, Cs  # noqa: E402


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def json_bytes(value: object) -> bytes:
    """Return the repository's deterministic UTF-8/CRLF JSON representation."""
    return (json.dumps(value, indent=2) + "\n").replace("\n", "\r\n").encode("utf-8")


def asm(source: str, address: int) -> bytes:
    ks = Ks(KS_ARCH_X86, KS_MODE_32)
    encoded, _ = ks.asm(source, addr=address)
    return bytes(encoded)


def rel32(call_va: int, target_va: int) -> bytes:
    return (target_va - (call_va + 5)).to_bytes(4, "little", signed=True)


def pe_checksum(data: bytearray) -> None:
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    checksum = pe + 24 + 64
    original = struct.unpack_from("<I", data, checksum)[0]
    struct.pack_into("<I", data, checksum, 0)
    total = 0
    for off in range(0, len(data), 2):
        word = data[off] | ((data[off + 1] if off + 1 < len(data) else 0) << 8)
        total = (total + word) & 0xFFFFFFFF
        total = (total & 0xFFFF) + (total >> 16)
    total = (total & 0xFFFF) + (total >> 16)
    total = (total + len(data)) & 0xFFFFFFFF
    struct.pack_into("<I", data, checksum, total)
    if original == total:
        return


CONFIG = {
    "vv3": {
        "stock": ROOT / "research/stock-executables/Virtual Villagers - The Secret City.exe",
        "parents": {
            "collection_progression": "15D58F10FEC11D1E3BE0066A9E7109B08EF3AAD2E8E20E0056E41597277ABEEB",
            "immediate_fixed": "3142012C853615F513E009E4D22AA544C14D72F6ADC960E51E676A8636A571C4",
        },
        "parent_ids": [
            "vv3_enable_origins_exclusive_features",
            "vv3_full_mastery_all_stage_a_candidate",
            "vv3_individual_grant_running_candidate",
            "vv3_full_heal_cure_all_candidate",
        ],
        "getter": 0x408940,
        "outer_global": 0x4B34A8,
        "leave": 0x40A430,
        "enter": 0x40A450,
        "module_iat": 0x47C074,
        "proc_iat": 0x47C128,
        "tech": (0x4A318E, bytes.fromhex("E82D030000")),
        "detail": (0x4A328E, bytes.fromhex("E83D050000")),
        "header": 0x318,
        "append_raw": 0xCD000,
        "section_rva": 0x2E1000,
        "section_va": 0x6E1000,
        "section_name": b".vv3fs\0\0",
        "section_count_before": 7,
        "image_before": 0x2E1000,
        "image_after": 0x2E2000,
        "parent_size": 0xCD000,
        "dll": "9F866CB6F92C745CD2AA7009AEC4EB70FA5521EFF0C8F7BABE2058BB4D2F8533",
        "dll_path": ROOT / "data/candidates/VVFP VV3 Full Heal Candidate.dll",
        "dll_size": 298496,
    },
    "vv4": {
        "stock": ROOT / "research/stock-executables/Virtual Villagers - The Tree of Life.exe",
        "parents": {
            "collection_progression": "0E26D7B6FEF660194297BA017419D6E9F4D70F01A80265830C8461341B9334E9",
            "immediate_fixed": "043DA03EDEE4CDA82269F0584178E84D90D7DAC54ABD80873A3F59E3B4957388",
        },
        "parent_ids": [
            "vv4_enable_origins_exclusive_features",
            "vv4_full_mastery_all_stage_a_candidate",
        ],
        "getter": 0x408130,
        "outer_global": None,
        "leave": 0x409FA0,
        "enter": 0x409FB0,
        "module_iat": 0x48A1D8,
        "proc_iat": 0x48A1DC,
        "tech": (0x489381, bytes.fromhex("E84D020000")),
        "detail": (0x4895B6, bytes.fromhex("E8B8020000")),
        "header": 0x2E8,
        "append_raw": 0xE5000,
        "section_rva": 0x341000,
        "section_va": 0x741000,
        "section_name": b".vv4fs\0\0",
        "section_count_before": 6,
        "image_before": 0x341000,
        "image_after": 0x342000,
        "parent_size": 0xE5000,
        "dll": "4E1A83683A875EFE6F67116CDD862927BE1ABCB17DB7AE18143E58E98EAD01E7",
        "dll_path": ROOT / "data/candidates/VVFP VV4 Full Mastery Candidate.dll",
        "dll_size": 282624,
    },
}


def _target(call_va: int, before: bytes) -> int:
    return call_va + 5 + int.from_bytes(before[1:5], "little", signed=True)


def _build_wrapper_legacy(cfg: dict[str, object], page_va: int, string_va: int, target_va: int) -> tuple[bytes, dict[str, object]]:
    # The wrapper is a plain-return call replacement.  It uses the game's
    # proven singleton transport, leaves/enters native fullscreen, and checks
    # only the SDL fullscreen bits so unrelated SDL flags are accepted.
    outer_load = (
        f"mov esi, dword ptr [0x{cfg['outer_global']:X}]"
        if cfg["outer_global"] is not None
        else "mov esi, eax"
    )
    source = f"""
        push ebp
        mov ebp, esp
        push ebx
        push esi
        push edi
        sub esp, 0x20
        mov dword ptr [ebp-0x10], ecx
        mov dword ptr [ebp-0x14], 0
        call 0x{cfg['getter']:X}
        test eax, eax
        jz fail
        {outer_load}
        test esi, esi
        jz fail
        mov edi, dword ptr [esi]
        test edi, edi
        jz fail
        mov eax, dword ptr [edi+0x38]
        test eax, eax
        jz fail
        mov dword ptr [ebp-0x18], eax
        movzx ebx, byte ptr [edi+0x1E]
        mov dword ptr [ebp-0x1C], ebx
        push 0x{string_va:X}
        call dword ptr [0x{cfg['module_iat']:X}]
        test eax, eax
        jz fail
        push 0x{string_va + len(b'SDL2.dll\\0'):X}
        push eax
        call dword ptr [0x{cfg['proc_iat']:X}]
        test eax, eax
        jz fail
        mov dword ptr [ebp-0x20], eax
        push dword ptr [ebp-0x18]
        call eax
        add esp, 4
        mov edx, eax
        and edx, 0x1001
        cmp edx, 0
        je windowed
        cmp edx, 0x1001
        je fullscreen
        jmp fail
    windowed:
        cmp dword ptr [ebp-0x1C], 1
        jne fail
        mov ecx, dword ptr [ebp-0x10]
        call 0x{target_va:X}
        jmp done
    fullscreen:
        cmp dword ptr [ebp-0x1C], 0
        jne fail
        mov ecx, esi
        call 0x{cfg['leave']:X}
        call 0x{cfg['getter']:X}
        {outer_load}
        cmp esi, dword ptr [ebp-0x18]
        jne fail
        mov edi, dword ptr [esi]
        test edi, edi
        jz fail
        cmp byte ptr [edi+0x1E], 1
        jne fail
        mov ecx, dword ptr [ebp-0x10]
        call 0x{target_va:X}
        mov dword ptr [ebp-0x14], eax
        call 0x{cfg['getter']:X}
        {outer_load}
        cmp esi, dword ptr [ebp-0x18]
        jne fail_after_leave
        mov edi, dword ptr [esi]
        test edi, edi
        jz fail_after_leave
        mov ecx, esi
        call 0x{cfg['enter']:X}
        call 0x{cfg['getter']:X}
        {outer_load}
        cmp esi, dword ptr [ebp-0x18]
        jne fail_after_leave
        mov edi, dword ptr [esi]
        test edi, edi
        jz fail_after_leave
        cmp byte ptr [edi+0x1E], 0
        jne fail_after_leave
        push dword ptr [ebp-0x18]
        call dword ptr [ebp-0x20]
        add esp, 4
        mov edx, eax
        and edx, 0x1001
        cmp edx, 0x1001
        jne fail_after_leave
        mov eax, dword ptr [ebp-0x14]
        jmp done
    fail_after_leave:
        xor eax, eax
        jmp done
    fail:
        xor eax, eax
    done:
        add esp, 0x20
        pop edi
        pop esi
        pop ebx
        pop ebp
        ret
    """
    body = asm(source, page_va + 0x100)
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    ins = list(md.disasm(body, page_va + 0x100))
    if not ins or sum(i.size for i in ins) != len(body):
        raise RuntimeError("fullscreen wrapper did not disassemble continuously")
    if any(i.mnemonic == "ret" and i.op_str for i in ins):
        raise RuntimeError("fullscreen wrapper consumed handler arguments")
    return body, {
        "helper_length": len(body),
        "helper_sha256": sha(body),
        "instruction_count": len(ins),
        "target": f"0x{target_va:X}",
        "flags_mask": "0x1001",
        "api_abi": "GetModuleHandleA/GetProcAddress stdcall with no caller cleanup; SDL_GetWindowFlags cdecl add esp,4",
        "state_chain": "getter -> configured outer -> engine[outer] -> window +0x38/state +0x1E",
        "failure": "leave/restore/identity/flag failure returns safely without entering the modal route or charging",
    }


def build_wrapper(
    cfg: dict[str, object],
    helper_va: int,
    string_va: int,
    target_va: int,
) -> tuple[bytes, dict[str, object]]:
    """Assemble one helper at its final VA with typed state locals."""
    reacquire_outer = (
        f"mov esi, dword ptr [0x{cfg['outer_global']:X}]"
        if cfg["outer_global"] is not None
        else "mov esi, eax"
    )
    source = f"""
        push ebp
        mov ebp, esp
        push ebx
        push esi
        push edi
        sub esp, 0x2C
        mov dword ptr [ebp-0x10], ecx
        xor eax, eax
        mov dword ptr [ebp-0x28], eax
        mov dword ptr [ebp-0x2C], eax
        call reacquire
        test eax, eax
        jz fail
        mov dword ptr [ebp-0x14], esi
        mov dword ptr [ebp-0x18], edi
        mov dword ptr [ebp-0x1C], eax
        movzx ebx, byte ptr [edi+0x1E]
        mov dword ptr [ebp-0x20], ebx
        push 0x{string_va:X}
        call dword ptr [0x{cfg['module_iat']:X}]
        test eax, eax
        jz fail
        push 0x{string_va + len(b'SDL2.dll\0'):X}
        push eax
        call dword ptr [0x{cfg['proc_iat']:X}]
        test eax, eax
        jz fail
        mov dword ptr [ebp-0x24], eax
        push dword ptr [ebp-0x1C]
        call dword ptr [ebp-0x24]
        add esp, 4
        mov edx, eax
        and edx, 0x1001
        cmp edx, 0
        je windowed
        cmp edx, 0x1001
        je fullscreen
        jmp fail
    windowed:
        cmp dword ptr [ebp-0x20], 1
        jne fail
        mov ecx, dword ptr [ebp-0x10]
        call 0x{target_va:X}
        jmp done
    fullscreen:
        cmp dword ptr [ebp-0x20], 0
        jne fail
        mov ecx, dword ptr [ebp-0x14]
        call 0x{cfg['leave']:X}
        mov dword ptr [ebp-0x2C], 1
        call reacquire
        cmp esi, dword ptr [ebp-0x14]
        jne post_leave_failed
        cmp edi, dword ptr [ebp-0x18]
        jne post_leave_failed
        cmp eax, dword ptr [ebp-0x1C]
        jne post_leave_failed
        cmp byte ptr [edi+0x1E], 1
        jne post_leave_failed
        push dword ptr [ebp-0x1C]
        call dword ptr [ebp-0x24]
        add esp, 4
        mov edx, eax
        and edx, 0x1001
        cmp edx, 0
        jne post_leave_failed
        mov ecx, dword ptr [ebp-0x10]
        call 0x{target_va:X}
        mov dword ptr [ebp-0x28], eax
        cmp dword ptr [ebp-0x2C], 0
        je done
    restore_start:
        call reacquire
        test eax, eax
        jz restore_failed
        cmp esi, dword ptr [ebp-0x14]
        jne restore_failed
        cmp edi, dword ptr [ebp-0x18]
        jne restore_failed
        cmp eax, dword ptr [ebp-0x1C]
        jne restore_failed
        mov ecx, dword ptr [ebp-0x14]
        call 0x{cfg['enter']:X}
        call reacquire
        test eax, eax
        jz restore_failed
        cmp esi, dword ptr [ebp-0x14]
        jne restore_failed
        cmp edi, dword ptr [ebp-0x18]
        jne restore_failed
        cmp eax, dword ptr [ebp-0x1C]
        jne restore_failed
        cmp byte ptr [edi+0x1E], 0
        jne restore_failed
        push dword ptr [ebp-0x1C]
        call dword ptr [ebp-0x24]
        add esp, 4
        mov edx, eax
        and edx, 0x1001
        cmp edx, 0x1001
        jne restore_failed
        mov eax, dword ptr [ebp-0x28]
        jmp done
    post_leave_failed:
        xor eax, eax
        mov dword ptr [ebp-0x28], eax
        jmp restore_start
    reacquire:
        call 0x{cfg['getter']:X}
        test eax, eax
        jz reacquire_failed
        {reacquire_outer}
        test esi, esi
        jz reacquire_failed
        mov edi, dword ptr [esi]
        test edi, edi
        jz reacquire_failed
        mov eax, dword ptr [edi+0x38]
        test eax, eax
        jz reacquire_failed
        ret
    reacquire_failed:
        xor eax, eax
        ret
    restore_failed:
        xor eax, eax
        jmp done
    fail:
        xor eax, eax
    done:
        add esp, 0x2C
        pop edi
        pop esi
        pop ebx
        pop ebp
        ret
    """
    body = asm(source, helper_va)
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    ins = list(md.disasm(body, helper_va))
    if not ins or sum(i.size for i in ins) != len(body):
        raise RuntimeError("fullscreen helper did not disassemble continuously")
    if any(i.mnemonic == "ret" and i.op_str for i in ins):
        raise RuntimeError("fullscreen helper consumed handler arguments")
    boundaries = {i.address for i in ins}
    for i in ins:
        if i.mnemonic in {"call", "jmp", "je", "jne", "jz", "jnz"} and i.op_str.startswith("0x"):
            target = int(i.op_str, 16)
            if helper_va <= target < helper_va + len(body) and target not in boundaries:
                raise RuntimeError("fullscreen helper branches into a non-instruction boundary")
    return body, {
        "assembled_va": f"0x{helper_va:X}",
        "helper_length": len(body),
        "helper_sha256": sha(body),
        "instruction_count": len(ins),
        "target": f"0x{target_va:X}",
        "flags_mask": "0x1001",
        "api_abi": "GetModuleHandleA/GetProcAddress stdcall with no caller cleanup; SDL_GetWindowFlags push SDL_Window*; indirect call; add esp,4",
        "state_chain": "getter -> typed outer -> typed engine -> typed SDL_Window +0x38/state +0x1E",
        "failure": "leave/restore/identity/flag failure returns safely without entering the modal route or charging; every post-leave exit attempts one fresh restoration",
    }


def section_header(cfg: dict[str, object]) -> bytes:
    return (
        cfg["section_name"]
        + (0x1000).to_bytes(4, "little")
        + int(cfg["section_rva"]).to_bytes(4, "little")
        + (0x1000).to_bytes(4, "little")
        + int(cfg["append_raw"]).to_bytes(4, "little")
        + b"\0" * 12
        + (0x60000020).to_bytes(4, "little")
    )


def emit_game(game: str, cfg: dict[str, object], output_root: Path = OUT, emit_binaries: bool = False) -> dict[str, object]:
    stock = cfg["stock"].read_bytes()
    dll_path = cfg["dll_path"]
    if not dll_path.is_file() or dll_path.stat().st_size != cfg["dll_size"]:
        raise RuntimeError(f"{game} companion DLL input is missing or has the wrong size")
    if sha(dll_path.read_bytes()) != cfg["dll"]:
        raise RuntimeError(f"{game} companion DLL input hash mismatch")
    parents = cfg["parents"]
    if len(stock) > cfg["parent_size"]:
        raise RuntimeError(f"{game} stock exceeds parent append boundary")
    # Parent bytes are rendered by the production loader and pinned before any
    # fullscreen mutation is accepted.
    sys.path.insert(0, str(ROOT / "src"))
    from vv_fun_patcher import identify, load_fun_patches, render_patched_bytes
    build = identify(cfg["stock"])
    records = load_fun_patches()
    ids = cfg["parent_ids"]
    parents_bytes: dict[str, bytes] = {}
    for mode, expected in parents.items():
        rendered, _ = render_patched_bytes(cfg["stock"], build, mode, ids)
        rendered = bytes(rendered)
        if len(rendered) != cfg["parent_size"] or sha(rendered) != expected:
            raise RuntimeError(f"{game} {mode} certified parent mismatch")
        parents_bytes[mode] = rendered
    page_va = int(cfg["section_va"])
    string_offset = 0xE00
    strings = b"SDL2.dll\0SDL_GetWindowFlags\0"
    tech_helper, tech_meta = build_wrapper(
        cfg, page_va + 0x100, page_va + string_offset, _target(*cfg["tech"])
    )
    detail_helper, detail_meta = build_wrapper(
        cfg, page_va + 0x400, page_va + string_offset, _target(*cfg["detail"])
    )
    if len(tech_helper) > 0x400 or len(detail_helper) > string_offset or string_offset + len(strings) > 0x1000:
        raise RuntimeError("fullscreen helper/string layout exceeds page")
    page = bytearray(0x1000)
    page[0x100:0x100 + len(tech_helper)] = tech_helper
    page[0x400:0x400 + len(detail_helper)] = detail_helper
    page[string_offset:string_offset + len(strings)] = strings
    page_meta = {"tech": tech_meta, "detail": detail_meta, "strings_offset": f"0x{string_offset:X}", "strings_sha256": sha(strings), "page_sha256": sha(bytes(page))}
    modes: dict[str, object] = {}
    candidate_bytes: dict[str, bytes] = {}
    for mode, parent in parents_bytes.items():
        data = bytearray(parent)
        for key in ("tech", "detail"):
            off_va, before = cfg[key]
            off = off_va - 0x400000
            if data[off:off + 5] != before:
                raise RuntimeError(f"{game} {key} hook guard mismatch")
            wrapper_va = page_va + (0x100 if key == "tech" else 0x400)
            call_va = off_va
            data[off:off + 5] = b"\xE8" + rel32(call_va, wrapper_va)
        if len(data) != cfg["append_raw"]:
            raise RuntimeError(f"{game} parent size does not equal fullscreen append raw")
        pe = struct.unpack_from("<I", data, 0x3C)[0]
        if struct.unpack_from("<H", data, pe + 6)[0] != cfg["section_count_before"]:
            raise RuntimeError(f"{game} section count guard mismatch")
        if struct.unpack_from("<I", data, pe + 0x50)[0] != cfg["image_before"]:
            raise RuntimeError(f"{game} SizeOfImage guard mismatch")
        if any(data[cfg["header"]:cfg["header"] + 40]):
            raise RuntimeError(f"{game} fullscreen section header area is not zero")
        struct.pack_into("<H", data, pe + 6, cfg["section_count_before"] + 1)
        struct.pack_into("<I", data, pe + 0x50, cfg["image_after"])
        data[cfg["header"]:cfg["header"] + 40] = section_header(cfg)
        data.extend(page)
        pe_checksum(data)
        candidate_bytes[mode] = bytes(data)
        modes[mode] = {"parent_sha256": sha(parent), "candidate_sha256": sha(bytes(data)), "size": len(data)}
    stem = f"vv{game[-1]}_fullscreen_safe_candidate"
    contract = {
        "stock": str(cfg["stock"].relative_to(ROOT)),
        "getter": hex(cfg["getter"]),
        "outer_global": None if cfg["outer_global"] is None else hex(cfg["outer_global"]),
        "leave": hex(cfg["leave"]),
        "enter": hex(cfg["enter"]),
        "get_module_handle_iat": hex(cfg["module_iat"]),
        "get_proc_address_iat": hex(cfg["proc_iat"]),
        "tech": {"va": hex(cfg["tech"][0]), "raw": hex(cfg["tech"][0] - 0x400000), "before": cfg["tech"][1].hex().upper(), "after": (b"\xE8" + rel32(cfg["tech"][0], page_va + 0x100)).hex().upper(), "target": hex(_target(*cfg["tech"]))},
        "detail": {"va": hex(cfg["detail"][0]), "raw": hex(cfg["detail"][0] - 0x400000), "before": cfg["detail"][1].hex().upper(), "after": (b"\xE8" + rel32(cfg["detail"][0], page_va + 0x400)).hex().upper(), "target": hex(_target(*cfg["detail"]))},
        "section_header": {"offset": hex(cfg["header"]), "bytes": section_header(cfg).hex().upper()},
        "page_raw": hex(cfg["append_raw"]),
        "section_rva": hex(cfg["section_rva"]),
        "section_va": hex(cfg["section_va"]),
        "page": page_meta,
        "flags_mask": "0x1001",
        "plain_return": True,
    }
    manifest = {
        "id": stem,
        "game_id": game,
        "name": f"DISABLED {game.upper()} Fullscreen-Safe Origins Dialog Wrapper",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "supported_modes": ["collection_progression", "immediate_fixed"],
        "rejected_modes": ["experimental_expanded_256", "experimental_expanded_256_progression"],
        "runtime_player_status": "pending",
        "certification_status": "static candidate enabled for Collection/Immediate; runtime/player validation pending",
        "parent_hashes": parents,
        "companion_dll_sha256": cfg["dll"],
        "companion_install": {
            "required": False,
            "reason": "fullscreen-only wrapper; certified companion/resource bytes are not replaced",
            "input": str(dll_path.relative_to(ROOT)),
            "size": cfg["dll_size"],
            "sha256_if_present": cfg["dll"],
        },
        "fullscreen_contract": contract,
        "rendered_modes": modes,
        "uninstall": "restore exact parent bytes, section count/image/header/checksum, and five-byte hook guards",
    }
    artifact_map = {"candidate_id": stem, "enabled": True, "catalog_hidden": False, "catalog_enabled": True, "parents": parents, "page": page_meta, "rendered_modes": modes, "rejected_modes": manifest["rejected_modes"], "dll_sha256": cfg["dll"], "companion_install": manifest["companion_install"], "feature_ranges": [hex(cfg["tech"][0] - 0x400000), hex(cfg["detail"][0] - 0x400000), f"{hex(cfg['header'])}..{hex(cfg['header'] + 40)}", f"{hex(cfg['append_raw'])}..{hex(cfg['append_raw'] + 0x1000)}"]}
    output_root.mkdir(parents=True, exist_ok=True)
    manifest_bytes = json_bytes(manifest)
    map_bytes = json_bytes(artifact_map)
    (output_root / f"{stem}.json").write_bytes(manifest_bytes)
    (output_root / f"{stem}_map.json").write_bytes(map_bytes)
    if emit_binaries:
        (output_root / f"{stem}_fullscreen_page.bin").write_bytes(bytes(page))
        for mode, candidate in candidate_bytes.items():
            (output_root / f"{stem}_{mode}.exe").write_bytes(candidate)
    return {"manifest": sha(manifest_bytes), "map": sha(map_bytes), "page": page_meta, "modes": modes}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=OUT,
                        help="directory for generated candidate evidence (default: tracked data/candidates)")
    parser.add_argument("--emit-binaries", action="store_true",
                        help="also write ignored candidate EXE/page projections under --output-root")
    args = parser.parse_args()
    result = {game: emit_game(game, cfg, args.output_root, args.emit_binaries) for game, cfg in CONFIG.items()}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
