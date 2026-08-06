"""Emit the disabled VV3 selected-villager Full Mastery candidate.

The candidate is deliberately not registered in the public catalog.  It emits
the complete command-1 transaction into a separately owned RX page so that
the bytes can be independently disassembled and reviewed before enablement.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "candidates"
DOC = ROOT / "docs" / "vv3-individual-full-mastery-candidate.md"
MANIFEST = OUT / "vv3_individual_full_mastery_candidate.json"
MAP = OUT / "vv3_individual_full_mastery_candidate_map.json"

sys.path.insert(0, str(ROOT / ".tools" / "keystone-runtime"))
from keystone import KS_ARCH_X86, KS_MODE_32, Ks  # noqa: E402

STOCK_SHA = "8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503"
PARENTS = {
    "collection_progression": "8DD1CE07C885DDA3DD038D0B2F5C4F019D8C5BAC5DCA29F9799CE0C7909D2CEA",
    "immediate_fixed": "78758FD0003842AEFAC092A47874329C9C103F9AD46483E6ECA71291EFD3E382",
}
PAGE_RAW, PAGE_RVA, PAGE_VA, PAGE_SIZE = 0xCE000, 0x2E2000, 0x6E2000, 0x1000
HOOK_RAW = 0xA38C3
HOOK_BEFORE = bytes.fromhex("E938C02300")
HOOK_AFTER = bytes.fromhex("E938E72300")
DISPATCHER = bytes.fromhex("83FB010F84F700000083FB020F84EED8FFFFE9D618DCFF")
SKILLS = (0xEAC, 0xEB0, 0xEB4, 0xEB8, 0xEBC)
SKILL_NAMES = ("Farming", "Building", "Research", "Healing", "Parenting")
PRICE = 100_000

# The certified Fullscreen Collection/Immediate parents are already complete
# 0xCE000-byte images (the .vv3fs section occupies raw 0xCD000).  The new
# individual-Mastery page is therefore the next aligned section at raw
# 0xCE000/RVA 0x2E2000.  These header edits are derived from those parents and
# are guarded byte-for-byte by the production resolver.
PARENT_FILE_SIZE = 0xCE000
SECTION_HEADER_OFFSET = 0x340
SECTION_HEADER_BEFORE = bytes(40)
SECTION_HEADER_AFTER = bytes.fromhex(
    "2E767633696D00000010000000202E000010000000E00C0000000000000000000000000020000060"
)
HEADER_PATCHES = [
    {"offset": "0x10E", "before": "0800", "after": "0900", "purpose": "add owned .vv3im section"},
    {"offset": "0x158", "before": "00202E00", "after": "00302E00", "purpose": "extend SizeOfImage for .vv3im"},
    {"offset": "0x340", "before": SECTION_HEADER_BEFORE.hex().upper(), "after": SECTION_HEADER_AFTER.hex().upper(), "purpose": "write owned .vv3im section header"},
]
RENDERED_OUTPUTS = {
    "collection_progression": {"parent_sha256": PARENTS["collection_progression"], "candidate_sha256": "BFFA0B5F54CD084138EABD68D3EA67F834CEFE915F7DB0000F81639F34BF90F1", "size": 0xCF000, "checksum": "9D3A0D00"},
    "immediate_fixed": {"parent_sha256": PARENTS["immediate_fixed"], "candidate_sha256": "6550141AFFAEF3F7965E89F1B32A3F4CB929E8E217778C5BBCB512AAC499E59C", "size": 0xCF000, "checksum": "9B7C0D00"},
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def asm(source: str, address: int) -> bytes:
    encoded, _ = Ks(KS_ARCH_X86, KS_MODE_32).asm(source, address)
    return bytes(encoded)


def _strings(base: int) -> tuple[bytes, dict[str, int]]:
    values = {
        "user32": b"USER32.dll\0",
        "messagebox": b"MessageBoxA\0",
        "caption": b"Villager Upgrades\0",
        "prompt": b"Grant Full Mastery to this villager for 100,000 tech points?\r\nPress OK to confirm, or Cancel.\0",
        "success": b"Full Mastery was granted.\0",
        "noop": b"This villager is already fully mastered.\r\nNo tech points have been deducted.\0",
        "cancel": b"Full Mastery was canceled.\r\nNo tech points have been deducted.\0",
        "invalid": b"No valid living villager is selected.\r\nNo tech points have been deducted.\0",
        "insufficient": b"Not enough tech points.\r\nNo tech points have been deducted.\0",
        "race": b"The selected villager changed during confirmation.\r\nNo tech points have been deducted.\0",
        "failure": b"Full Mastery could not be completed; native changes may remain.\r\nNo tech points have been deducted.\0",
        "dependency": b"Full Mastery dependencies are unavailable.\r\nNo tech points have been deducted.\0",
    }
    blob = bytearray()
    pointers: dict[str, int] = {}
    for key, value in values.items():
        pointers[key] = base + len(blob)
        blob.extend(value)
    return bytes(blob), pointers


def build_helper(strings: dict[str, int]) -> bytes:
    """Assemble the complete dry-run/confirm/recheck/native transaction."""
    va = PAGE_VA + 0x100
    lines = [
        "push ebp", "mov ebp, esp", "push ebx", "push esi", "push edi", "sub esp, 0x50",
        # MessageBoxA dependency preflight occurs before any record field read.
        "mov dword ptr [ebp-0x10], 0", f"push 0x{strings['user32']:X}", "call dword ptr [0x47C124]", "test eax, eax", "jz dependency",
        f"push 0x{strings['messagebox']:X}", "push eax", "call dword ptr [0x47C128]", "test eax, eax", "jz dependency",
        "mov dword ptr [ebp-0x10], eax",
        # Selected physical index from the manager singleton, hard bound <150.
        "call 0x428B60", "test eax, eax", "jz invalid", "mov edx, dword ptr [eax+0x12FC0]",
        "cmp edx, 0x96", "jae invalid", "mov dword ptr [ebp-0x1C], edx",
        "mov ecx, 0x59E110", "push edx", "call 0x45EE60", "test eax, eax", "jz invalid",
        "mov ecx, 0x59E110", "push dword ptr [ebp-0x1C]", "call 0x45C840", "test eax, eax", "jz invalid",
        "mov dword ptr [ebp-0x18], eax", "mov esi, eax",
        # Eligibility precedes every skill/preference read.
        "cmp byte ptr [esi+0xF10], 0", "je invalid", "cmp dword ptr [esi+0xE78], 0", "jle invalid",
        "movzx eax, byte ptr [esi+0xF10]", "mov dword ptr [ebp-0x38], eax", "mov eax, dword ptr [esi+0xE78]", "mov dword ptr [ebp-0x3C], eax",
        "mov dword ptr [ebp-0x40], 0",
    ]
    for i, off in enumerate(SKILLS):
        slot = 0x20 + i * 4
        lines += [
            f"mov eax, dword ptr [esi+0x{off:X}]", f"mov dword ptr [ebp-0x{slot:X}], eax",
            f"cmp dword ptr [ebp-0x{slot:X}], 0", "jl invalid",
            f"cmp dword ptr [ebp-0x{slot:X}], 100", "jg invalid",
            f"cmp dword ptr [ebp-0x{slot:X}], 100", f"je skill_{i}_unchanged",
            f"or dword ptr [ebp-0x40], {1 << i}", f"skill_{i}_unchanged:",
        ]
    lines += [
        "mov eax, dword ptr [esi+0xEC0]", "mov dword ptr [ebp-0x34], eax",
        "cmp dword ptr [ebp-0x40], 0", "je noop",
        "cmp dword ptr [0x582644], 100000", "jb insufficient",
        # IDOK is exactly 1; MessageBoxA is stdcall and cleans its arguments.
        "push 1", f"push 0x{strings['caption']:X}", f"push 0x{strings['prompt']:X}", "push 0", "call dword ptr [ebp-0x10]",
        "cmp eax, 1", "jne cancel",
        # Reacquire selected index and record and compare the complete snapshot.
        "call 0x428B60", "test eax, eax", "jz race", "mov edx, dword ptr [eax+0x12FC0]",
        "cmp edx, dword ptr [ebp-0x1C]", "jne race", "mov ecx, 0x59E110", "push edx", "call 0x45EE60", "test eax, eax", "jz race",
        "mov ecx, 0x59E110", "push dword ptr [ebp-0x1C]", "call 0x45C840", "test eax, eax", "jz race",
        "cmp eax, dword ptr [ebp-0x18]", "jne race", "mov esi, eax",
        "cmp byte ptr [esi+0xF10], 0", "je race", "cmp dword ptr [esi+0xE78], 0", "jle race", "movzx eax, byte ptr [esi+0xF10]", "cmp eax, dword ptr [ebp-0x38]", "jne race", "mov eax, dword ptr [esi+0xE78]", "cmp eax, dword ptr [ebp-0x3C]", "jne race",
    ]
    for i, off in enumerate(SKILLS):
        slot = 0x20 + i * 4
        lines += [f"mov eax, dword ptr [esi+0x{off:X}]", f"cmp eax, dword ptr [ebp-0x{slot:X}]", "jne race"]
    lines += ["mov eax, dword ptr [esi+0xEC0]", "cmp eax, dword ptr [ebp-0x34]", "jne race", "cmp dword ptr [0x582644], 100000", "jb insufficient"]
    for i, off in enumerate(SKILLS):
        lines += [f"mov esi, dword ptr [ebp-0x18]", f"mov eax, dword ptr [esi+0x{off:X}]", "cmp eax, 100", f"je write_{i}_done", "mov ebx, 100", "sub ebx, eax", f"push ebx", f"push {i}", "lea ecx, [esi+0xEAC]", "call 0x455740", f"write_{i}_done:"]
    lines += [
        "mov esi, dword ptr [ebp-0x18]",
    ]
    for off in SKILLS:
        lines += [f"cmp dword ptr [esi+0x{off:X}], 100", "jne failure"]
    lines += [
        "push esi", "call 0x462500",
        # Fresh final reacquisition, exact-100 and preference preservation.
        "call 0x428B60", "test eax, eax", "jz failure", "mov edx, dword ptr [eax+0x12FC0]", "cmp edx, dword ptr [ebp-0x1C]", "jne failure",
        "mov ecx, 0x59E110", "push edx", "call 0x45C840", "test eax, eax", "jz failure", "cmp eax, dword ptr [ebp-0x18]", "jne failure", "mov esi, eax",
        "cmp byte ptr [esi+0xF10], 0", "je failure", "cmp dword ptr [esi+0xE78], 0", "jle failure", "movzx eax, byte ptr [esi+0xF10]", "cmp eax, dword ptr [ebp-0x38]", "jne failure", "mov eax, dword ptr [esi+0xE78]", "cmp eax, dword ptr [ebp-0x3C]", "jne failure",
    ]
    for off in SKILLS:
        lines += [f"cmp dword ptr [esi+0x{off:X}], 100", "jne failure"]
    lines += ["mov eax, dword ptr [esi+0xEC0]", "cmp eax, dword ptr [ebp-0x34]", "jne failure", "cmp dword ptr [0x582644], 100000", "jb failure", "mov ecx, 0x582644", "push -100000", "call 0x427130", f"mov edx, 0x{strings['success']:X}", "jmp show"]
    lines += [
        "noop:", f"mov edx, 0x{strings['noop']:X}", "jmp show", "cancel:", f"mov edx, 0x{strings['cancel']:X}", "jmp show", "invalid:", f"mov edx, 0x{strings['invalid']:X}", "jmp show", "insufficient:", f"mov edx, 0x{strings['insufficient']:X}", "jmp show", "race:", f"mov edx, 0x{strings['race']:X}", "jmp show", "failure:", f"mov edx, 0x{strings['failure']:X}", "jmp show", "dependency:", "cmp dword ptr [ebp-0x10], 0", "je done", f"mov edx, 0x{strings['dependency']:X}", "jmp show",
        "show:", "push 0", f"push 0x{strings['caption']:X}", "push edx", "push 0", "call dword ptr [ebp-0x10]", "done:", "add esp, 0x50", "pop edi", "pop esi", "pop ebx", "mov esp, ebp", "pop ebp", "ret",
    ]
    return asm("\n".join(lines), va)


def build_page() -> tuple[bytes, dict[str, object]]:
    strings, ptrs = _strings(PAGE_VA + 0x800)
    helper = build_helper(ptrs)
    if len(helper) > 0x700 or 0x800 + len(strings) > PAGE_SIZE:
        raise RuntimeError("VV3 individual page layout overflow")
    page = bytearray(PAGE_SIZE)
    page[: len(DISPATCHER)] = DISPATCHER
    page[0x100 : 0x100 + len(helper)] = helper
    page[0x800 : 0x800 + len(strings)] = strings
    return bytes(page), {"helper_length": len(helper), "helper_sha256": sha(helper), "strings_length": len(strings), "strings_sha256": sha(strings), "strings_hex": strings.hex().upper(), "page_sha256": sha(page), "pointer_map": ptrs}


def main() -> None:
    page, emitted = build_page()
    manifest = {
        "id": "vv3_individual_full_mastery_candidate", "game_id": "vv3", "name": "Grant Full Mastery to Selected Villager", "enabled": False, "catalog_hidden": True, "catalog_enabled": False, "runtime_player_status": "pending", "certification_status": "disabled emitted candidate; independent runtime and loader recertification pending", "dependencies": ["vv3_individual_grant_running_candidate"], "supported_modes": ["collection_progression", "immediate_fixed"], "unsupported_patch_modes": ["experimental_expanded_256", "experimental_expanded_256_progression"], "provenance": {"design_source": "D262/D263", "implementation_commit": None, "audit_commit": None, "acceptance_commit": None},
        "transaction": {"command": 1, "price": PRICE, "action": "Buy", "repeatable": True, "ownership": None, "remove": False, "confirmation": "Grant Full Mastery to this villager for 100,000 tech points?\r\nPress OK to confirm, or Cancel.", "caption": "Villager Upgrades", "accept": "IDOK only", "accept_result": 1, "cancel_results": [0, 2], "no_deduction_suffix": "No tech points have been deducted."},
        "selection": {"manager_selected_offset": "0x12FC0", "bound": 150, "validator": "ECX=0x59E110; call 0x45EE60", "resolver": "ECX=0x59E110; push index; call 0x45C840; ret 4", "eligibility_before_skills": ["record nonnull", "+0xF10 != 0", "signed +0xE78 > 0"], "population_note": "VV3 has no independently proved Heathen/skeleton discriminator in this route; the supported predicate is active nonzero plus signed positive health, and the candidate remains disabled pending independent lifecycle proof."},
        "skills": {"order": list(SKILL_NAMES), "offsets": [f"0x{x:X}" for x in SKILLS], "range": "signed DWORD 0..100", "preferred_job": {"offset": "0xEC0", "access": "snapshot/revalidate only", "writes": False}, "writer": {"address": "0x455740", "abi": "ECX=record+offset; push delta; push skill index; ret 8"}, "evaluator": {"address": "0x462500", "calls": "exactly once after exact-100 postverify"}},
        "base_chain": {"stock_sha256": STOCK_SHA, **{f"{k}_parent_sha256": v for k, v in PARENTS.items()}, "dll_sha256": "9F866CB6F92C745CD2AA7009AEC4EB70FA5521EFF0C8F7BABE2058BB4D2F8533", "running_command2": "0x6DF900"},
        "companion_files": [{"source": "data/candidates/VVFP VV3 Full Heal Candidate.dll", "destination": "VVFP Origins Icons.dll", "sha256": "9F866CB6F92C745CD2AA7009AEC4EB70FA5521EFF0C8F7BABE2058BB4D2F8533", "size": 298496, "preimage_sha256": "9F866CB6F92C745CD2AA7009AEC4EB70FA5521EFF0C8F7BABE2058BB4D2F8533", "restore_source": "data/candidates/VVFP VV3 Full Heal Candidate.dll", "restore_sha256": "9F866CB6F92C745CD2AA7009AEC4EB70FA5521EFF0C8F7BABE2058BB4D2F8533"}],
        "patches": [{"offset": "0xA38C3", "before": HOOK_BEFORE.hex().upper(), "after": HOOK_AFTER.hex().upper(), "purpose": "guarded command-1 dispatcher composition"}],
        "pe_append_transaction": {"owner": "vv3_individual_full_mastery_candidate", "section_name": ".vv3im", "append_source": "generated:vv3_individual_full_mastery_page", "append_length": PAGE_SIZE, "section_rva": "0x2E2000", "section_va": "0x6E2000", "section_characteristics": "0x60000020", "header_offset": "0x340", "section_count_before": 8, "section_count_after": 9, "size_of_image_before": "0x2E2000", "size_of_image_after": "0x2E3000", "original_file_size": "0xCE000", "append_offset": "0xCE000", "page_sha256": emitted["page_sha256"], "header_patches": HEADER_PATCHES, "parent_hashes": PARENTS, "layouts": {mode: {"original_file_size": "0xCE000", "append_offset": "0xCE000", "append_source": "generated:vv3_individual_full_mastery_page", "append_length": "0x1000", "virtual_address": "0x6E2000", "section_rva": "0x2E2000", "section_name": ".vv3im", "section_characteristics": "0x60000020", "header_patches": HEADER_PATCHES, "page_sha256": emitted["page_sha256"], "purpose": "append guarded VV3 individual Full Mastery .vv3im page"} for mode in ("collection_progression", "immediate_fixed")}},
        "emitted": {"dispatcher_va": "0x6E2000", "dispatcher_hex": DISPATCHER.hex().upper(), "dispatcher_sha256": sha(DISPATCHER), "helper_va": "0x6E2100", **{k: v for k, v in emitted.items() if k != "pointer_map"}},
        "rendered_modes": RENDERED_OUTPUTS,
        "failure_policy": {"cancel_noop_recheck_failure": "no writes/no charge; No tech points have been deducted.", "partial_native_failure": "native partial effects may remain; no deduction; rollback is not claimed"},
        "explicit_non_changes": ["+0xEC0 is never written or normalized; stock naming/tie behavior remains authoritative, including Master Parent fallback", "command 2 remains Grant Running at 0x6DF900", "Full Heal/fullscreen/DLL/Expanded and existing certified bytes remain unchanged"],
    }
    tx_map = {**manifest["transaction"], "native_writer": "0x455740", "native_evaluator": "0x462500 exactly once globally after complete postverify", "preferred_job": "0xEC0 read-only snapshot"}
    mapping = {"candidate_id": manifest["id"], "enabled": False, "catalog_hidden": True, "catalog_enabled": False, "supported_modes": manifest["supported_modes"], "rejected_modes": manifest["unsupported_patch_modes"], "dependencies": manifest["dependencies"], "base_chain": manifest["base_chain"], "companion_files": manifest["companion_files"], "dispatcher": {"raw_offset": "0xA38C3", "before": HOOK_BEFORE.hex().upper(), "after": HOOK_AFTER.hex().upper(), "target": "0x6E2000", "bytes": DISPATCHER.hex().upper()}, "section": manifest["pe_append_transaction"], "rendered_modes": RENDERED_OUTPUTS, "emitted": manifest["emitted"], "transaction": tx_map, "skill_order": list(SKILL_NAMES), "skill_offsets": [f"0x{x:X}" for x in SKILLS], "no_preference_write": True, "runtime_status": "pending", "provenance": manifest["provenance"], "stack_intervals": {"saved_ebx": [-4, -1], "saved_esi": [-8, -5], "saved_edi": [-12, -9], "messagebox": [-16, -13], "manager": [-20, -17], "record": [-24, -21], "selected_index": [-28, -25], "skill_snapshot_0": [-32, -29], "skill_snapshot_1": [-36, -33], "skill_snapshot_2": [-40, -37], "skill_snapshot_3": [-44, -41], "skill_snapshot_4": [-48, -45], "preferred_job": [-52, -49], "active_snapshot": [-56, -53], "health_snapshot": [-60, -57], "changed_mask": [-64, -61]}, "source": {"stock_sha256": STOCK_SHA, "helper_sha256": emitted["helper_sha256"], "page_sha256": emitted["page_sha256"]}}
    OUT.mkdir(exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    MAP.write_text(json.dumps(mapping, indent=2) + "\n", encoding="utf-8")
    DOC.write_text("# VV3 Individual Full Mastery Candidate\n\nDisabled/catalog-hidden emitted `.vv3im` candidate for Collection Progression and Immediate Fixed only; runtime/player validation and loader enablement remain pending. The command-1 dispatcher at raw `0xA38C3` uses the exact composed preimage `E938C02300` and routes command 1 to `0x6E2100`, command 2 to `0x6DF900`, and other commands to `0x4A38ED`. The page is raw `0xCE000`, RVA/VA `0x2E2000`/`0x6E2000`, size `0x1000`, RX.\n\nThe supported VV3 lifecycle predicate is record non-null, active byte `+0xF10` nonzero, and signed health `+0xE78` positive, checked before any skill or preference read. VV3 has no independently proved Heathen/skeleton discriminator in this route; that limitation is explicit and keeps this candidate disabled pending lifecycle recertification.\n\nThe helper performs dependency preflight, eligibility before skill reads, a complete five-skill/+0xEC0/eligibility snapshot, confirmation, exact reacquisition, changed-only native writes, exact-100 postverify, one evaluator, final reacquisition, and one 100,000 deduction. MessageBoxA accepts only EAX==1 (IDOK); EAX==2, close, or any other result is cancel/no-charge. If MessageBoxA itself cannot resolve, the helper silently fails closed; a dependency result is displayed only through a verified MessageBoxA pointer. It never writes or normalizes +0xEC0, and preserves stock naming/tie behavior including the no-preference Master Parent fallback. Expanded modes reject before output.\n", encoding="utf-8")


if __name__ == "__main__":
    main()
