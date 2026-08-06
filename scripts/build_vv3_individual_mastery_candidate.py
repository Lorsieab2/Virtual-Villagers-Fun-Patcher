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
        f"push 0x{strings['user32']:X}", "call dword ptr [0x47C124]", "test eax, eax", "jz dependency",
        f"push 0x{strings['messagebox']:X}", "push eax", "call dword ptr [0x47C128]", "test eax, eax", "jz dependency",
        "mov dword ptr [ebp-0x10], eax",
        # Selected physical index from the manager singleton, hard bound <150.
        "call 0x428B60", "test eax, eax", "jz invalid", "mov edx, dword ptr [eax+0x12FC0]",
        "cmp edx, 0x96", "jae invalid", "mov dword ptr [ebp-0x1C], edx",
        "mov ecx, 0x59E110", "push edx", "call 0x45EE60", "add esp, 4", "test eax, eax", "jz invalid",
        "mov ecx, 0x59E110", "push dword ptr [ebp-0x1C]", "call 0x45C840", "add esp, 4", "test eax, eax", "jz invalid",
        "mov dword ptr [ebp-0x18], eax", "mov esi, eax",
        # Eligibility precedes every skill/preference read.
        "cmp byte ptr [esi+0xF10], 0", "je invalid", "cmp dword ptr [esi+0xE78], 0", "jle invalid",
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
        # IDOK is exactly 2; MessageBoxA is stdcall and cleans its arguments.
        "push 1", f"push 0x{strings['caption']:X}", f"push 0x{strings['prompt']:X}", "push 0", "call dword ptr [ebp-0x10]",
        "cmp eax, 2", "jne cancel",
        # Reacquire selected index and record and compare the complete snapshot.
        "call 0x428B60", "test eax, eax", "jz race", "mov edx, dword ptr [eax+0x12FC0]",
        "cmp edx, dword ptr [ebp-0x1C]", "jne race", "mov ecx, 0x59E110", "push edx", "call 0x45EE60", "add esp, 4", "test eax, eax", "jz race",
        "mov ecx, 0x59E110", "push dword ptr [ebp-0x1C]", "call 0x45C840", "add esp, 4", "test eax, eax", "jz race",
        "cmp eax, dword ptr [ebp-0x18]", "jne race", "mov esi, eax",
        "cmp byte ptr [esi+0xF10], 0", "je race", "cmp dword ptr [esi+0xE78], 0", "jle race",
    ]
    for i, off in enumerate(SKILLS):
        slot = 0x20 + i * 4
        lines += [f"mov eax, dword ptr [esi+0x{off:X}]", f"cmp eax, dword ptr [ebp-0x{slot:X}]", "jne race"]
    lines += ["mov eax, dword ptr [esi+0xEC0]", "cmp eax, dword ptr [ebp-0x34]", "jne race", "cmp dword ptr [0x582644], 100000", "jb insufficient"]
    for i, off in enumerate(SKILLS):
        lines += [f"mov esi, dword ptr [ebp-0x18]", f"mov eax, dword ptr [esi+0x{off:X}]", "cmp eax, 100", f"je write_{i}_done", "mov ebx, 100", "sub ebx, eax", f"push ebx", f"push {i}", f"lea ecx, [esi+0x{off:X}]", "call 0x455740", f"write_{i}_done:"]
    lines += [
        "mov esi, dword ptr [ebp-0x18]",
    ]
    for off in SKILLS:
        lines += [f"cmp dword ptr [esi+0x{off:X}], 100", "jne failure"]
    lines += [
        "mov ecx, esi", "call 0x462500",
        # Fresh final reacquisition, exact-100 and preference preservation.
        "call 0x428B60", "test eax, eax", "jz failure", "mov edx, dword ptr [eax+0x12FC0]", "cmp edx, dword ptr [ebp-0x1C]", "jne failure",
        "mov ecx, 0x59E110", "push edx", "call 0x45C840", "add esp, 4", "test eax, eax", "jz failure", "cmp eax, dword ptr [ebp-0x18]", "jne failure", "mov esi, eax",
        "cmp byte ptr [esi+0xF10], 0", "je failure", "cmp dword ptr [esi+0xE78], 0", "jle failure",
    ]
    for off in SKILLS:
        lines += [f"cmp dword ptr [esi+0x{off:X}], 100", "jne failure"]
    lines += ["mov eax, dword ptr [esi+0xEC0]", "cmp eax, dword ptr [ebp-0x34]", "jne failure", "cmp dword ptr [0x582644], 100000", "jb failure", "mov ecx, 0x582644", "push -100000", "call 0x427130", f"mov edx, 0x{strings['success']:X}", "jmp show"]
    lines += [
        "noop:", f"mov edx, 0x{strings['noop']:X}", "jmp show", "cancel:", f"mov edx, 0x{strings['cancel']:X}", "jmp show", "invalid:", f"mov edx, 0x{strings['invalid']:X}", "jmp show", "insufficient:", f"mov edx, 0x{strings['insufficient']:X}", "jmp show", "race:", f"mov edx, 0x{strings['race']:X}", "jmp show", "failure:", f"mov edx, 0x{strings['failure']:X}", "jmp show", "dependency:", "jmp done",
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
        "transaction": {"command": 1, "price": PRICE, "action": "Buy", "repeatable": True, "ownership": None, "remove": False, "confirmation": "Grant Full Mastery to this villager for 100,000 tech points?\r\nPress OK to confirm, or Cancel.", "caption": "Villager Upgrades", "accept": "IDOK only", "no_deduction_suffix": "No tech points have been deducted."},
        "selection": {"manager_selected_offset": "0x12FC0", "bound": 150, "validator": "ECX=0x59E110; call 0x45EE60", "resolver": "ECX=0x59E110; push index; call 0x45C840; ret 4", "eligibility_before_skills": ["record nonnull", "+0xF10 != 0", "signed +0xE78 > 0"]},
        "skills": {"order": list(SKILL_NAMES), "offsets": [f"0x{x:X}" for x in SKILLS], "range": "signed DWORD 0..100", "preferred_job": {"offset": "0xEC0", "access": "snapshot/revalidate only", "writes": False}, "writer": {"address": "0x455740", "abi": "ECX=record+offset; push delta; push skill index; ret 8"}, "evaluator": {"address": "0x462500", "calls": "exactly once after exact-100 postverify"}},
        "base_chain": {"stock_sha256": STOCK_SHA, **{f"{k}_parent_sha256": v for k, v in PARENTS.items()}, "dll_sha256": "9F866CB6F92C745CD2AA7009AEC4EB70FA5521EFF0C8F7BABE2058BB4D2F8533", "running_command2": "0x6DF900"},
        "patches": [{"offset": "0xA38C3", "before": HOOK_BEFORE.hex().upper(), "after": HOOK_AFTER.hex().upper(), "purpose": "guarded command-1 dispatcher composition"}],
        "pe_append_transaction": {"owner": "vv3_individual_full_mastery_candidate", "section_name": ".vv3im", "append_offset": "0xCE000", "append_length": PAGE_SIZE, "section_rva": "0x2E2000", "section_va": "0x6E2000", "section_characteristics": "0x60000020", "header_offset": "0x318", "section_count_before": 7, "section_count_after": 8, "size_of_image_before": "0x2E1000", "size_of_image_after": "0x2E2000", "page_sha256": emitted["page_sha256"], "page_hex": page.hex().upper()},
        "emitted": {"dispatcher_va": "0x6E2000", "dispatcher_hex": DISPATCHER.hex().upper(), "dispatcher_sha256": sha(DISPATCHER), "helper_va": "0x6E2100", **{k: v for k, v in emitted.items() if k != "pointer_map"}},
        "failure_policy": {"cancel_noop_recheck_failure": "no writes/no charge; No tech points have been deducted.", "partial_native_failure": "native partial effects may remain; no deduction; rollback is not claimed"},
        "explicit_non_changes": ["+0xEC0 is never written or normalized; stock naming/tie behavior remains authoritative, including Master Parent fallback", "command 2 remains Grant Running at 0x6DF900", "Full Heal/fullscreen/DLL/Expanded and existing certified bytes remain unchanged"],
    }
    tx_map = {**manifest["transaction"], "native_writer": "0x455740", "native_evaluator": "0x462500 exactly once globally after complete postverify", "preferred_job": "0xEC0 read-only snapshot"}
    mapping = {"candidate_id": manifest["id"], "enabled": False, "catalog_hidden": True, "catalog_enabled": False, "supported_modes": manifest["supported_modes"], "rejected_modes": manifest["unsupported_patch_modes"], "dependencies": manifest["dependencies"], "base_chain": manifest["base_chain"], "dispatcher": {"raw_offset": "0xA38C3", "before": HOOK_BEFORE.hex().upper(), "after": HOOK_AFTER.hex().upper(), "target": "0x6E2000", "bytes": DISPATCHER.hex().upper()}, "section": manifest["pe_append_transaction"], "emitted": manifest["emitted"], "transaction": tx_map, "skill_order": list(SKILL_NAMES), "skill_offsets": [f"0x{x:X}" for x in SKILLS], "no_preference_write": True, "runtime_status": "pending", "provenance": manifest["provenance"], "stack_intervals": {"saved_ebx": [-4, -1], "saved_esi": [-8, -5], "saved_edi": [-12, -9], "messagebox": [-16, -13], "manager": [-20, -17], "record": [-24, -21], "selected_index": [-28, -25], "skill_snapshot_0": [-32, -29], "skill_snapshot_1": [-36, -33], "skill_snapshot_2": [-40, -37], "skill_snapshot_3": [-44, -41], "skill_snapshot_4": [-48, -45], "preferred_job": [-52, -49], "changed_mask": [-64, -61]}, "source": {"stock_sha256": STOCK_SHA, "helper_sha256": emitted["helper_sha256"], "page_sha256": emitted["page_sha256"]}}
    OUT.mkdir(exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    MAP.write_text(json.dumps(mapping, indent=2) + "\n", encoding="utf-8")
    DOC.write_text("# VV3 Individual Full Mastery Candidate\n\nDisabled/catalog-hidden emitted `.vv3im` candidate for Collection Progression and Immediate Fixed only; runtime/player validation and loader enablement remain pending. The command-1 dispatcher at raw `0xA38C3` uses the exact composed preimage `E938C02300` and routes command 1 to `0x6E2100`, command 2 to `0x6DF900`, and other commands to `0x4A38ED`. The page is raw `0xCE000`, RVA/VA `0x2E2000`/`0x6E2000`, size `0x1000`, RX.\n\nThe helper performs dependency preflight, eligibility before skill reads, a complete five-skill/+0xEC0 snapshot, confirmation, exact reacquisition, changed-only native writes, exact-100 postverify, one evaluator, final reacquisition, and one 100,000 deduction. It never writes or normalizes +0xEC0, and preserves stock naming/tie behavior including the no-preference Master Parent fallback. Expanded modes reject before output.\n", encoding="utf-8")


if __name__ == "__main__":
    main()
