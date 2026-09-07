"""Emit the public stock-only VV3 selected-villager Full Mastery feature."""
from __future__ import annotations

import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "candidates"
DOC = ROOT / "docs" / "vv3-individual-full-mastery-candidate.md"
MANIFEST = OUT / "vv3_individual_full_mastery_candidate.json"
MAP = OUT / "vv3_individual_full_mastery_candidate_map.json"
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Secret City.exe"
BASE = OUT / "vv3_origins_full_mastery_base_candidate.json"
VILLAGE_MASTERY = OUT / "vv3_full_mastery_all_candidate.json"
COMPANION = OUT / "VVFP VV3 Safe Upgrades.dll"
FOUNDATION_COMPANION = OUT / "VVFP VV3 Safe Upgrade Foundation.dll"
STATISTICS = ROOT / "data" / "statistics_features.json"

sys.path.insert(0, str(ROOT / ".tools" / "keystone-runtime"))
from keystone import KS_ARCH_X86, KS_MODE_32, Ks  # noqa: E402

STOCK_SHA = "8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503"
PARENTS = {
    "collection_progression": "A36C5EAD61324C11BEE02A4387294ECC878CF70B56AB7D9AEB9A053E6FCAD239",
    "immediate_fixed": "1F9D4B97BC2E5960C7437EACABCE1773AC8979798656235FB6B57033CC80613C",
}
PAGE_RAW, PAGE_RVA, PAGE_VA, PAGE_SIZE = 0xCC000, 0x2E0000, 0x6E0000, 0x1000
HOOK_RAW = 0xA38C3
HOOK_BEFORE = bytes.fromhex("E926010000")
HOOK_AFTER = bytes.fromhex("E938C72300")
DISPATCHER = bytes.fromhex("83FB010F85E539DCFFE8F2000000E9C337DCFF")
SKILLS = (0xEAC, 0xEB0, 0xEB4, 0xEB8, 0xEBC)
SKILL_NAMES = ("Farming", "Building", "Research", "Healing", "Parenting")
PRICE = 100_000

# The current public Origins+village-FM parents end at raw 0xCC000.  The new
# page is the next aligned section and consumes the seventh PE section slot.
PARENT_FILE_SIZE = 0xCC000
SECTION_HEADER_OFFSET = 0x2F0
SECTION_HEADER_BEFORE = bytes(40)
SECTION_HEADER_AFTER = struct.pack(
    "<8sIIIIIIHHI",
    b".vv3im\0\0",
    PAGE_SIZE,
    PAGE_RVA,
    PAGE_SIZE,
    PAGE_RAW,
    0,
    0,
    0,
    0,
    0x60000020,
)
HEADER_PATCHES = [
    {"offset": "0x10E", "before": "0600", "after": "0700", "purpose": "add owned .vv3im section"},
    {"offset": "0x158", "before": "00002E00", "after": "00102E00", "purpose": "extend SizeOfImage for .vv3im"},
    {"offset": "0x2F0", "before": SECTION_HEADER_BEFORE.hex().upper(), "after": SECTION_HEADER_AFTER.hex().upper(), "purpose": "write owned .vv3im section header"},
]
SOURCE_REGION_SHA256 = {
    "manager": (0x428B60, "F420823E509F92909A9012AA8AA66C419D42226AAF2A19D52C7E20217606CB10"),
    "validator": (0x45EE60, "32FD827946A7C5B1BD56280BD2699A35F3888888B129A926B79B0BB0885B46C7"),
    "resolver": (0x45C840, "804C22CD210BABB2045BC44BF8A56CBE1292DC9900BEE807348E80F8A0998250"),
    "skill_writer": (0x455740, "1E35D1B81AA0C7F38AEAB95117CD632C123AD0BFBB279B6F2A7AE6264C003514"),
    "award_evaluator": (0x462500, "28D9A914DE63D0912F1A5BD219462DF3C2B149FBF40844BB195ED2B8F2959B32"),
    "tech_writer": (0x427130, "D3ED48511BAAD72CC1BD0F50D7DE60989B0A79DAD754C477672DCE3F3892DE63"),
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


def verify_source_and_parents() -> tuple[dict[str, bytes], dict[str, str]]:
    """Authenticate every native target and the complete public parent images."""
    stock = STOCK.read_bytes()
    if sha(stock) != STOCK_SHA:
        raise RuntimeError("VV3 stock executable fingerprint mismatch")
    verified_regions: dict[str, str] = {}
    for name, (va, expected) in SOURCE_REGION_SHA256.items():
        region = stock[va - 0x400000 : va - 0x400000 + 0x40]
        actual = sha(region)
        if actual != expected:
            raise RuntimeError(f"VV3 native source region {name} fingerprint mismatch")
        verified_regions[name] = actual
    # Callee-clean ABI guards used by the emitted helper.
    if stock[0x5EE60:0x5EE84].count(bytes.fromhex("C20400")) < 1:
        raise RuntimeError("VV3 validator ret-4 ABI mismatch")
    if stock[0x5C840:0x5C860].count(bytes.fromhex("C20400")) != 1:
        raise RuntimeError("VV3 resolver ret-4 ABI mismatch")
    if stock[0x55740:0x55770].count(bytes.fromhex("C20800")) < 1:
        raise RuntimeError("VV3 skill writer ret-8 ABI mismatch")

    sys.path.insert(0, str(ROOT / "src"))
    import vv_fun_patcher as patcher  # noqa: E402

    build = next(item for item in patcher.load_builds() if item.id == "vv3")
    base = patcher.FunPatch(json.loads(BASE.read_text(encoding="utf-8")))
    village = patcher.FunPatch(json.loads(VILLAGE_MASTERY.read_text(encoding="utf-8")))
    parents: dict[str, bytes] = {}
    for mode, expected in PARENTS.items():
        parent, _ = patcher.render_patched_bytes(
            STOCK,
            build,
            mode,
            _fun_patches_override=[base, village],
        )
        if len(parent) != PARENT_FILE_SIZE or sha(parent) != expected:
            raise RuntimeError(f"VV3 {mode} public parent fingerprint mismatch")
        for item in HEADER_PATCHES:
            offset = int(item["offset"], 0)
            before = bytes.fromhex(item["before"])
            if bytes(parent[offset : offset + len(before)]) != before:
                raise RuntimeError(f"VV3 {mode} append header preimage mismatch")
        if bytes(parent[HOOK_RAW : HOOK_RAW + len(HOOK_BEFORE)]) != HOOK_BEFORE:
            raise RuntimeError(f"VV3 {mode} phase-1 Detail preimage mismatch")
        parents[mode] = bytes(parent)
    return parents, verified_regions


def render_candidate(parent: bytes, page: bytes) -> bytes:
    """Apply the exact child append/hook transaction to one authenticated parent."""
    if len(parent) != PARENT_FILE_SIZE or len(page) != PAGE_SIZE:
        raise RuntimeError("VV3 individual Full Mastery render geometry mismatch")
    work = bytearray(parent)
    for item in HEADER_PATCHES:
        offset = int(item["offset"], 0)
        before = bytes.fromhex(item["before"])
        after = bytes.fromhex(item["after"])
        if bytes(work[offset : offset + len(before)]) != before:
            raise RuntimeError("VV3 individual Full Mastery header guard mismatch")
        work[offset : offset + len(after)] = after
    work.extend(page)
    if bytes(work[HOOK_RAW : HOOK_RAW + len(HOOK_BEFORE)]) != HOOK_BEFORE:
        raise RuntimeError("VV3 individual Full Mastery Detail hook guard mismatch")
    work[HOOK_RAW : HOOK_RAW + len(HOOK_AFTER)] = HOOK_AFTER
    sys.path.insert(0, str(ROOT / "src"))
    import vv_fun_patcher as patcher  # noqa: E402

    checksum_offset, _ = patcher._pe_checksum_layout(work)
    struct.pack_into("<I", work, checksum_offset, 0)
    struct.pack_into("<I", work, checksum_offset, patcher.pe_checksum(work))
    if len(work) != 0xCD000:
        raise RuntimeError("VV3 individual Full Mastery output size mismatch")
    return bytes(work)


def main() -> None:
    page, emitted = build_page()
    parents, verified_regions = verify_source_and_parents()
    companion_hash = sha(COMPANION.read_bytes())
    foundation_hash = sha(FOUNDATION_COMPANION.read_bytes())
    if COMPANION.stat().st_size != 298_496 or FOUNDATION_COMPANION.stat().st_size != 298_496:
        raise RuntimeError("VV3 individual Full Mastery companion size mismatch")
    rendered_outputs: dict[str, dict[str, object]] = {}
    for mode, parent in parents.items():
        candidate = render_candidate(parent, page)
        rendered_outputs[mode] = {
            "parent_sha256": sha(parent),
            "candidate_sha256": sha(candidate),
            "size": len(candidate),
            "checksum": candidate[0x160:0x164].hex().upper(),
        }
    companion = {
        "source": "data/candidates/VVFP VV3 Safe Upgrades.dll",
        "destination": "VVFP VV3 Full Mastery Candidate.dll",
        "sha256": companion_hash,
        "size": COMPANION.stat().st_size,
        "preimage_sha256": foundation_hash,
        "restore_source": "data/candidates/VVFP VV3 Safe Upgrade Foundation.dll",
        "restore_sha256": foundation_hash,
    }
    manifest = {
        "id": "vv3_individual_full_mastery_candidate",
        "game_id": "vv3",
        "name": "Grant Full Mastery to Selected Villager",
        "description": "Stock-only command-1 transaction for the selected current living villager. It raises only below-100 skills through the native writer, postverifies exact 100 values, runs the native evaluator once, and deducts 100,000 tech points once only after final identity, snapshot, and funds reacquisition.",
        "enabled": True,
        "catalog_hidden": False,
        "catalog_enabled": True,
        "runtime_player_status": "pending live player confirmation",
        "certification_status": "public stock-only emitted implementation; independent static re-review and runtime/player confirmation pending",
        "dependencies": ["vv3_full_mastery_all_stage_a_candidate"],
        "supported_modes": ["collection_progression", "immediate_fixed"],
        "unsupported_patch_modes": ["experimental_expanded_256", "experimental_expanded_256_progression"],
        "provenance": {"design_source": "D262/D263 exact-100 native transaction", "implementation_commit": None, "audit_commit": None, "acceptance_commit": None},
        "transaction": {"command": 1, "price": PRICE, "action": "Buy", "repeatable": True, "ownership": None, "remove": False, "confirmation": "Grant Full Mastery to this villager for 100,000 tech points?\r\nPress OK to confirm, or Cancel.", "caption": "Villager Upgrades", "accept": "IDOK only", "accept_result": 1, "cancel_results": [0, 2], "no_deduction_suffix": "No tech points have been deducted."},
        "selection": {"manager_selected_offset": "0x12FC0", "bound": 150, "validator": "ECX=0x59E110; call 0x45EE60", "resolver": "ECX=0x59E110; push index; call 0x45C840; ret 4", "eligibility_before_skills": ["record nonnull", "+0xF10 != 0", "signed +0xE78 > 0"], "population_note": "The selected current living villager is the exact current physical index 0..149 whose active byte is nonzero and signed health is positive."},
        "skills": {"order": list(SKILL_NAMES), "offsets": [f"0x{x:X}" for x in SKILLS], "range": "signed DWORD 0..100", "preferred_job": {"offset": "0xEC0", "access": "snapshot/revalidate only", "writes": False}, "writer": {"address": "0x455740", "abi": "ECX=record+offset; push delta; push skill index; ret 8"}, "evaluator": {"address": "0x462500", "calls": "exactly once after exact-100 postverify"}},
        "base_chain": {"stock_sha256": STOCK_SHA, **{f"{k}_parent_sha256": v for k, v in PARENTS.items()}, "direct_dependency": "vv3_full_mastery_all_stage_a_candidate", "foundation_dll_sha256": foundation_hash, "dll_sha256": companion_hash},
        "companion_files": [companion],
        "patches": [{"offset": "0xA38C3", "before": HOOK_BEFORE.hex().upper(), "after": HOOK_AFTER.hex().upper(), "purpose": "replace the phase-1 reject-all guard with the command-1-only dispatcher"}],
        "pe_append_transaction": {"owner": "vv3_individual_full_mastery_candidate", "section_name": ".vv3im", "append_source": "generated:vv3_individual_full_mastery_page", "append_length": PAGE_SIZE, "section_rva": "0x2E0000", "section_va": "0x6E0000", "section_characteristics": "0x60000020", "header_offset": "0x2F0", "section_count_before": 6, "section_count_after": 7, "size_of_image_before": "0x2E0000", "size_of_image_after": "0x2E1000", "original_file_size": "0xCC000", "append_offset": "0xCC000", "page_sha256": emitted["page_sha256"], "header_patches": HEADER_PATCHES, "parent_hashes": PARENTS, "layouts": {mode: {"original_file_size": "0xCC000", "append_offset": "0xCC000", "append_source": "generated:vv3_individual_full_mastery_page", "append_length": "0x1000", "virtual_address": "0x6E0000", "section_rva": "0x2E0000", "section_name": ".vv3im", "section_characteristics": "0x60000020", "header_patches": HEADER_PATCHES, "page_sha256": emitted["page_sha256"], "purpose": "append guarded VV3 individual Full Mastery .vv3im page"} for mode in ("collection_progression", "immediate_fixed")}},
        "emitted": {"dispatcher_va": "0x6E0000", "dispatcher_hex": DISPATCHER.hex().upper(), "dispatcher_sha256": sha(DISPATCHER), "helper_va": "0x6E0100", **{k: v for k, v in emitted.items() if k != "pointer_map"}},
        "rendered_modes": rendered_outputs,
        "source_verification": {"status": "complete for exact stock SHA and complete public parent images", "region_length": "0x40", "native_region_sha256": verified_regions},
        "failure_policy": {"cancel_noop_recheck_failure": "no writes/no charge; No tech points have been deducted.", "partial_native_failure": "native partial effects may remain; no deduction; rollback is not claimed"},
        "behavior_changes": ["Adds only selected-villager command 1 to the Detail Upgrades dialog and executes the exact-100 native transaction for 100,000 tech points."],
        "explicit_non_changes": ["+0xEC0 is never written or normalized; stock naming/tie behavior remains authoritative, including Master Parent fallback", "legacy Detail commands 0, 2, and 3 remain absent and are rejected before price or mutation", "Tech commands and certified village command 7 bytes remain unchanged", "Expanded modes remain fail-closed before artifact access"],
        "evidence_status": "exact stock-source regions, emitted page, parent composition, resource projection, and final bytes are statically verified; runtime/player confirmation pending",
    }
    # Certify the final public composition with Statistics through the actual
    # production renderer.  Pin the in-memory page identity only for this
    # generator call so first-time regeneration does not depend on old pins.
    sys.path.insert(0, str(ROOT / "src"))
    import vv_fun_patcher as patcher  # noqa: E402

    build = next(item for item in patcher.load_builds() if item.id == "vv3")
    base_patch = patcher.FunPatch(json.loads(BASE.read_text(encoding="utf-8")))
    village_patch = patcher.FunPatch(
        json.loads(VILLAGE_MASTERY.read_text(encoding="utf-8"))
    )
    statistics_raw = next(
        item
        for item in json.loads(STATISTICS.read_text(encoding="utf-8"))["features"]
        if item["id"] == "vv3_write_village_statistics"
    )
    child_patch = patcher.FunPatch(manifest)
    statistics_patch = patcher.FunPatch(statistics_raw)
    old_page_pin = patcher.VV3_INDIVIDUAL_FULL_MASTERY_PAGE_SHA256
    patcher.VV3_INDIVIDUAL_FULL_MASTERY_PAGE_SHA256 = str(emitted["page_sha256"])
    try:
        for mode in PARENTS:
            composed, _ = patcher.render_patched_bytes(
                STOCK,
                build,
                mode,
                _fun_patches_override=[
                    base_patch,
                    village_patch,
                    child_patch,
                    statistics_patch,
                ],
            )
            if len(composed) != 0xCD000:
                raise RuntimeError("VV3 individual+Statistics output size mismatch")
            rendered_outputs[mode]["statistics_candidate_sha256"] = sha(composed)
    finally:
        patcher.VV3_INDIVIDUAL_FULL_MASTERY_PAGE_SHA256 = old_page_pin
    tx_map = {**manifest["transaction"], "native_writer": "0x455740", "native_evaluator": "0x462500 exactly once globally after complete postverify", "preferred_job": "0xEC0 read-only snapshot"}
    mapping = {"candidate_id": manifest["id"], "enabled": True, "catalog_hidden": False, "catalog_enabled": True, "supported_modes": manifest["supported_modes"], "rejected_modes": manifest["unsupported_patch_modes"], "dependencies": manifest["dependencies"], "base_chain": manifest["base_chain"], "companion_files": manifest["companion_files"], "dispatcher": {"raw_offset": "0xA38C3", "before": HOOK_BEFORE.hex().upper(), "after": HOOK_AFTER.hex().upper(), "target": "0x6E0000", "bytes": DISPATCHER.hex().upper(), "abi": "cmp ebx,1; jne 0x4A39EE; call 0x6E0100; jmp 0x4A37D6"}, "section": manifest["pe_append_transaction"], "rendered_modes": rendered_outputs, "emitted": manifest["emitted"], "transaction": tx_map, "skill_order": list(SKILL_NAMES), "skill_offsets": [f"0x{x:X}" for x in SKILLS], "no_preference_write": True, "runtime_status": manifest["runtime_player_status"], "source_verification": manifest["source_verification"], "provenance": manifest["provenance"], "stack_intervals": {"saved_ebx": [-4, -1], "saved_esi": [-8, -5], "saved_edi": [-12, -9], "messagebox": [-16, -13], "manager": [-20, -17], "record": [-24, -21], "selected_index": [-28, -25], "skill_snapshot_0": [-32, -29], "skill_snapshot_1": [-36, -33], "skill_snapshot_2": [-40, -37], "skill_snapshot_3": [-44, -41], "skill_snapshot_4": [-48, -45], "preferred_job": [-52, -49], "active_snapshot": [-56, -53], "health_snapshot": [-60, -57], "changed_mask": [-64, -61]}, "source": {"stock_sha256": STOCK_SHA, "helper_sha256": emitted["helper_sha256"], "page_sha256": emitted["page_sha256"]}}
    OUT.mkdir(exist_ok=True)
    MANIFEST.write_bytes((json.dumps(manifest, indent=2) + "\n").encode("utf-8"))
    MAP.write_bytes((json.dumps(mapping, indent=2) + "\n").encode("utf-8"))
    DOC.write_text("# VV3 Individual Full Mastery\n\nPublic stock-only command-1 child of village Full Mastery. The command dispatcher replaces the phase-1 `E926010000` guard at raw `0xA38C3`, accepts only EBX command 1, calls the helper at `0x6E0100`, and returns to the dialog loop at `0x4A37D6`; every non-1 command exits at `0x4A39EE`. The RX `.vv3im` page is raw `0xCC000`, RVA/VA `0x2E0000`/`0x6E0000`, size `0x1000`, producing a `0xCD000` executable.\n\nThe helper performs dependency preflight, living selected-villager eligibility, a five-skill/+0xEC0/identity snapshot, exact confirmation, identity/snapshot/funds reacquisition, changed-only native writes, exact-100 postverification, one native evaluator, final reacquisition, and one 100,000 deduction. Cancel, no-change, invalid/race, and insufficient-funds paths make no writes and charge nothing. Once native writes begin, a later native/postverify failure may leave partial skill effects, but never deducts tech points; rollback is not claimed. Expanded modes reject before variant, catalog, companion, manifest, or executable source access. Runtime/player confirmation remains pending.\n", encoding="utf-8", newline="")


if __name__ == "__main__":
    main()
