"""Build the disabled VV1 Origins + Full Mastery composition artifact."""

from __future__ import annotations

import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - A New Home.exe"
ORIGINS_DLL = ROOT / "assets" / "origins" / "VVFP Origins Icons.dll"
CANDIDATE_DLL = ROOT / "data" / "candidates" / "VVFP VV1 Full Mastery Candidate.dll"
MANIFEST_OUT = ROOT / "data" / "candidates" / "vv1_full_mastery_origins_composition.json"
MAP_OUT = ROOT / "data" / "candidates" / "vv1_full_mastery_origins_composition_map.json"
DOC_OUT = ROOT / "docs" / "vv1-full-mastery-origins-composition.md"
OUTPUT_ROOT = ROOT / "outputs" / "vv1-full-mastery-c74-recert"

sys.path.insert(0, str(ROOT / ".tools" / "keystone"))
sys.path.insert(0, str(ROOT / ".tools" / "keystone-runtime"))
sys.path.insert(0, str(ROOT / "src"))
from keystone import KS_ARCH_X86, KS_MODE_32, Ks  # noqa: E402

from build_vv1_full_mastery_candidate import (  # noqa: E402
    BOUND,
    MODES,
    SECTION_SIZE,
    SECTION_VA,
    STRIDE,
    build_section,
    sha,
)
from vv_fun_patcher import FunPatch, PatcherError, load_builds, render_patched_bytes  # noqa: E402


COMPOSITION_ID = "vv1_full_mastery_origins_composition"
ORIGINS_ID = "vv1_enable_origins_exclusive_features"
REQUIRED_BASE_SHA256 = "5434C71C342B830A5896AFFB610A76C670578760BD33C6145882FA280F6406A3"
REQUIRED_ORIGINS_DLL_SHA256 = "2ED1100E7F2EA5B8E522C2DE11F6B00CA8A02B968319C251365E9EFD634BCAF9"
REQUIRED_CANDIDATE_DLL_SHA256 = "4736E5EFB8F680E3B1F124D1920A9390D9F6427260E60743039FA80F8646CCB3"
HOOK_OFFSET = 0x56A88
HOOK_VA = 0x456A88
HOOK_BEFORE = bytes.fromhex("83FB067235")
HOOK_AFTER = bytes.fromhex("E973950300")
DIRECT_ENTRY_OFFSET = 0x100
DIRECT_ENTRY_VA = SECTION_VA + DIRECT_ENTRY_OFFSET
WALKER_OFFSET = 0x380
CONFIRM_OFFSET = 0x580
RESULT_OFFSET = 0x6C0
STRINGS_OFFSET = 0x900
SHIM_BYTES = bytes.fromhex(
    "83FB07750C89F1E8F4000000E9B469FCFF83FB060F82A86AFCFFE96E6AFCFF"
)


def asm(source: str, address: int) -> bytes:
    encoding, _ = Ks(KS_ARCH_X86, KS_MODE_32).asm(source, address)
    return bytes(encoding)


def _put(blob: bytearray, offset: int, payload: bytes, label: str) -> None:
    end = offset + len(payload)
    if end > len(blob) or any(blob[offset:end]):
        raise RuntimeError(f"{label} does not fit the zero-owned composition space")
    blob[offset:end] = payload


def _pe_layout(data: bytes) -> dict[str, int]:
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    coff = pe + 4
    optional_size = struct.unpack_from("<H", data, coff + 16)[0]
    optional = coff + 20
    sections = struct.unpack_from("<H", data, coff + 2)[0]
    return {
        "section_count_offset": coff + 2,
        "size_of_image_offset": optional + 56,
        "section_header_offset": optional + optional_size + sections * 40,
    }


def _direct_transaction() -> bytes:
    """The certified transaction body without the candidate menu call."""
    return asm(
        f"""
            push ebp
            mov ebp, esp
            push ebx
            push esi
            mov esi, ecx
            push edi
            sub esp, 4
            push 0x490911
            call dword ptr [0x457010]
            test eax, eax
            jz done
            push 0x49094C
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
            call 0x490380
            add esp, 12
            cmp edx, 1
            je invalid
            test eax, eax
            jz no_change
            mov edi, dword ptr [esi + 0x0C]
            test edi, edi
            jz invalid
            lea edx, [edi + 0xA2FC]
            cmp dword ptr [edx], 1000000
            jb insufficient
            call 0x490580
            cmp eax, 1
            jne done
            mov edi, dword ptr [esi + 0x0C]
            test edi, edi
            jz invalid
            mov edx, dword ptr [edi + 0xADE8]
            test edx, edx
            jz invalid
            lea edx, [edi + 0xA2FC]
            cmp dword ptr [edx], 1000000
            jb insufficient
            mov edx, dword ptr [edi + 0xADE8]
            test edx, edx
            jz invalid
            push 0
            push {BOUND}
            push edx
            call 0x490380
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
            call 0x490380
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
            cmp dword ptr [edx], 1000000
            jb insufficient
            sub dword ptr [edx], 1000000
            push dword ptr [ebp - 16]
            push ebx
            push 1
            call 0x4906C0
            jmp done
        no_change:
            push dword ptr [ebp - 16]
            push 0
            push 0
            call 0x4906C0
            jmp done
        insufficient:
            push dword ptr [ebp - 16]
            push 0
            push 2
            call 0x4906C0
            jmp done
        invalid:
            push dword ptr [ebp - 16]
            push 0
            push 3
            call 0x4906C0
            jmp done
        post_verify_failure:
            push dword ptr [ebp - 16]
            push 0
            push 4
            call 0x4906C0
        done:
            add esp, 4
            pop edi
            pop esi
            pop ebx
            mov esp, ebp
            pop ebp
            ret
        """,
        DIRECT_ENTRY_VA,
    )


def composition_section() -> tuple[bytes, dict[str, str]]:
    # Reuse only the certified walker/confirmation/result helpers from the
    # isolated candidate section.  The composition section intentionally has
    # no candidate constructor, handler, menu resolver, or menu transaction.
    base, _ = build_section()
    section = bytearray(SECTION_SIZE)
    shim = SHIM_BYTES
    _put(section, WALKER_OFFSET, base[WALKER_OFFSET:CONFIRM_OFFSET], "composition walker")
    _put(section, CONFIRM_OFFSET, base[CONFIRM_OFFSET:0x640], "composition confirmation helper")
    _put(section, RESULT_OFFSET, base[RESULT_OFFSET:0x740], "composition result helper")
    required_strings = {
        0x911: b"VVFP VV1 Full Mastery Candidate.dll\0",
        0x94C: b"ShowVV1FullMasteryResult\0",
        0x965: b"user32.dll\0",
        0x970: b"MessageBoxA\0",
        0x97C: b"Grant Full Mastery to all villagers for 1,000,000 tech points?\r\nPress OK to confirm, or Cancel.\0",
        0x9DC: b"Origins Upgrades\0",
        0x9ED: b"Full Mastery could not be verified after native writes.\r\nNo tech points have been deducted.\0",
    }
    for offset, value in required_strings.items():
        _put(section, offset, value, f"composition string 0x{offset:X}")
    direct = _direct_transaction()
    _put(section, 0, shim, "composition command-7 shim")
    _put(section, DIRECT_ENTRY_OFFSET, direct, "direct transaction entry")
    return bytes(section), {
        "shim_sha256": sha(shim),
        "direct_entry_sha256": sha(direct),
        "section_sha256": sha(bytes(section)),
        "shim_bytes": shim.hex().upper(),
        "direct_entry_bytes": direct.hex().upper(),
    }


def build_manifest_and_map() -> tuple[dict[str, object], dict[str, object]]:
    original = STOCK.read_bytes()
    section, evidence = composition_section()
    pe = _pe_layout(original)
    header_before = original[pe["section_header_offset"] : pe["section_header_offset"] + 40]
    header_after = bytearray(header_before)
    header_after[:8] = b".vv1fm\0\0"
    struct.pack_into("<IIII", header_after, 8, SECTION_SIZE, 0x90000, SECTION_SIZE, 0x8E000)
    struct.pack_into("<I", header_after, 36, 0x60000020)
    layout = {
        "original_file_size": "0x8E000",
        "append_offset": "0x8E000",
        "append_length": SECTION_SIZE,
        "append_bytes": section.hex().upper(),
        "virtual_address": "0x490000",
        "purpose": "append the disabled Origins composition .vv1fm RX section",
        "header_patches": [
            {"offset": f"0x{pe['section_count_offset']:X}", "before": "0500", "after": "0600", "purpose": "add the guarded composition .vv1fm section"},
            {"offset": f"0x{pe['size_of_image_offset']:X}", "before": struct.pack("<I", 0x90000).hex().upper(), "after": struct.pack("<I", 0x92000).hex().upper(), "purpose": "extend SizeOfImage for composition"},
            {"offset": f"0x{pe['section_header_offset']:X}", "before": header_before.hex().upper(), "after": bytes(header_after).hex().upper(), "purpose": "install guarded composition .vv1fm RX section header"},
        ],
    }
    manifest: dict[str, object] = {
        "id": COMPOSITION_ID,
        "game_id": "vv1",
        "name": "VV1 Origins + Full Mastery composition",
        "enabled": False,
        "catalog_hidden": True,
        "certification_status": "disabled pending independent composition recertification",
        "description": "Disabled stock-only composition. Reuses Origins Tech row ID1007/command 7 and detours only the certified post-menu command branch; isolated Full Mastery remains separately supported and collision-fail-closed.",
        "dependencies": [ORIGINS_ID],
        "required_base_sha256": REQUIRED_BASE_SHA256,
        "required_origins_dll_sha256": REQUIRED_ORIGINS_DLL_SHA256,
        "companion_files": [{"source": "data/candidates/VVFP VV1 Full Mastery Candidate.dll", "destination": "VVFP VV1 Full Mastery Candidate.dll", "sha256": REQUIRED_CANDIDATE_DLL_SHA256}],
        "patches": [{"offset": "0x56A88", "before": HOOK_BEFORE.hex().upper(), "after": HOOK_AFTER.hex().upper(), "purpose": "route only Origins command 7 to the direct Full Mastery transaction while preserving original command branches"}],
        "pe_append_transaction": {"owner": COMPOSITION_ID, "append_length": SECTION_SIZE, "removal_policy": "restore exact active Origins base and truncate only the owned .vv1fm tail", "layouts": {mode: layout for mode in MODES}},
        "composition_contract": {
            "origins_control": "Tech dialog resource 201 row ID1007 returns command 7",
            "shim": "command 7 sets ECX=ESI, calls the direct transaction entry, then jumps to Origins menu loop 0x4569C5",
            "legacy_branches": {"commands_0_to_5": "0x456AC2", "commands_6_and_8": "0x456A8D"},
            "no_extra_control": True,
            "isolated_candidate": "remains disabled/hidden and ordinary cross-owner composition remains collision-fail-closed",
        },
    }
    artifact: dict[str, object] = {
        "source": {"size": len(original), "sha256": sha(original)},
        "required_active_origins_sha256": REQUIRED_BASE_SHA256,
        "required_origins_dll_sha256": REQUIRED_ORIGINS_DLL_SHA256,
        "required_candidate_dll_sha256": REQUIRED_CANDIDATE_DLL_SHA256,
        "hook": {"file_offset": "0x56A88", "virtual_address": "0x456A88", "before": HOOK_BEFORE.hex().upper(), "after": HOOK_AFTER.hex().upper()},
        "shim": {"virtual_address": "0x490000", **evidence},
        "direct_entry": {"virtual_address": f"0x{DIRECT_ENTRY_VA:X}", "menu_call": False, "walker": "0x490380", "confirmation": "0x490580", "result": "0x4906C0", "pool_transport": "state=[Tech+0x0C], pool=[state+0xADE8]", "bound": 256, "stride": f"0x{STRIDE:X}"},
        "origins_routing": {"tech_resource": 201, "row_id": 1007, "command": 7, "menu_loop": "0x4569C5", "legacy_low": "0x456AC2", "legacy_high": "0x456A8D"},
        "layouts": {mode: layout for mode in MODES},
        "composition_uninstall": "remove hook and owned append/header changes; resulting bytes must equal the active Origins base SHA exactly",
        "candidate_enabled": False,
        "expanded_rejected": True,
    }
    return manifest, artifact


def main() -> None:
    requested = tuple(sys.argv[1:]) or MODES
    if any(mode not in MODES for mode in requested):
        raise PatcherError("VV1 Origins composition is stock-only; Expanded-256 is rejected before output.")
    manifest, artifact = build_manifest_and_map()
    build = next(item for item in load_builds() if item.id == "vv1")
    origins_record = FunPatch(json.loads((ROOT / "data" / "vv1_origins_feature.json").read_text(encoding="utf-8")))
    composition = FunPatch(manifest)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    rendered: dict[str, object] = {}
    for mode in requested:
        base, _ = render_patched_bytes(STOCK, build, mode, _fun_patches_override=[origins_record])
        if sha(base) != REQUIRED_BASE_SHA256:
            raise PatcherError(f"active Origins base identity mismatch: {sha(base)}")
        combined, applied = render_patched_bytes(STOCK, build, mode, _fun_patches_override=[origins_record, composition])
        combined_path = OUTPUT_ROOT / mode / "Virtual Villagers - A New Home - Origins Full Mastery.exe"
        combined_path.parent.mkdir(parents=True, exist_ok=True)
        combined_path.write_bytes(combined)
        removed = bytearray(combined)
        from vv_fun_patcher import _remove_feature_bytes
        _remove_feature_bytes(removed, composition, mode)
        if sha(removed) != REQUIRED_BASE_SHA256:
            raise PatcherError("composition uninstall did not restore active Origins base")
        (OUTPUT_ROOT / mode / "active-origins-base.exe").write_bytes(base)
        (OUTPUT_ROOT / mode / "uninstalled-active-origins.exe").write_bytes(removed)
        rendered[mode] = {"base_sha256": sha(base), "combined_sha256": sha(combined), "uninstall_sha256": sha(removed), "applied": applied}
    artifact["rendered"] = rendered
    MANIFEST_OUT.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    MAP_OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    (OUTPUT_ROOT / "composition-proof.json").write_text(
        json.dumps(
            {
                "active_base_sha256": REQUIRED_BASE_SHA256,
                "modes": {
                    mode: {
                        "combined_sha256": values["combined_sha256"],
                        "active_base_sha256": values["base_sha256"],
                        "uninstalled_sha256": values["uninstall_sha256"],
                        "uninstall_equals_active_base": values["uninstall_sha256"] == values["base_sha256"] == REQUIRED_BASE_SHA256,
                    }
                    for mode, values in rendered.items()
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    DOC_OUT.write_text(
        "# VV1 Origins + Full Mastery composition (disabled)\n\n"
        "This stock-only composition remains disabled and catalog-hidden pending independent recertification. "
        "It requires the exact active Origins base and Origins DLL hashes recorded in the map, reuses Tech row ID1007/command 7, "
        "and detours only file `0x56A88` / VA `0x456A88`. Command 7 sets `ECX=ESI`, calls a direct transaction entry without opening another menu, "
        "then returns to the Origins menu loop at `0x4569C5`. Commands 0-5 and 6/8 reconstruct the original branches at `0x456AC2` and `0x456A8D`. "
        "The direct entry is exactly VA `0x490100`; the section contains one walker and exactly three direct walker calls, with no isolated constructor, handler, menu resolver, or duplicate menu path. "
        "Removal is guarded and must reproduce the active Origins base byte-for-byte. Expanded-256 is rejected before output.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
