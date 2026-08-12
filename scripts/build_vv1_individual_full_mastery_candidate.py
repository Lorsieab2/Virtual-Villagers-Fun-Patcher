"""Generate the public stock-only VV1 selected-villager Full Mastery overlay."""

from __future__ import annotations

import hashlib
import json
import struct
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - A New Home.exe"
OUT = ROOT / "data" / "candidates"
MANIFEST = OUT / "vv1_individual_full_mastery_candidate.json"
MAP = OUT / "vv1_individual_full_mastery_candidate_map.json"
DOC = ROOT / "docs" / "vv1-individual-full-mastery-candidate.md"
PARENT_MANIFEST = OUT / "vv1_full_mastery_all_candidate.json"
PARENT_MAP = OUT / "vv1_full_mastery_all_candidate_map.json"
PARENT_DLL = OUT / "VVFP VV1 Full Mastery Candidate.dll"

sys.path.insert(0, str(ROOT / ".tools" / "keystone"))
sys.path.insert(0, str(ROOT / ".tools" / "keystone-runtime"))
sys.path.insert(0, str(ROOT / "src"))
from keystone import KS_ARCH_X86, KS_MODE_32, Ks  # noqa: E402


FEATURE_ID = "vv1_individual_full_mastery_candidate"
PARENT_ID = "vv1_full_mastery_all_stage_a_candidate"
MODES = ("collection_progression", "immediate_fixed")
REJECTED_MODES = ("experimental_expanded_256", "experimental_expanded_256_progression")
CONFLICTS = (
    "vv1_enable_origins_exclusive_features",
    "vv1_origins_village_wide_upgrades",
    "vv1_full_mastery_origins_composition",
)
STOCK_SHA256 = "1EC790B927741081D5CE13A48FB76983A4FD4336EA08F89317872643760AF03D"
PARENT_MANIFEST_SHA256 = "D36E885F5137DBA453FD419D08D5A59EE7D1AA0402C4A3C28CACA7F1F3C6D76F"
PARENT_MAP_SHA256 = "87A9BEA67932E153F7113EAA321FD757EAC3C184190297ADF1D0F578C191DCC0"
PARENT_DLL_SHA256 = "4736E5EFB8F680E3B1F124D1920A9390D9F6427260E60743039FA80F8646CCB3"
CURRENT_BASELINE_SHA256 = {mode: "0F54C22C531FCE276EFBF5F0B4418C48B66CE314AA21872A9B2C5D459232EC7A" for mode in MODES}
PARENT_RENDERED_SHA256 = {mode: "C2C6070B11E56BD6B8BD183C9694E88DC6D576758926D18ACEFCD093CCF364B0" for mode in MODES}

IMAGE_BASE = 0x400000
SECTION_RAW = 0x8E000
SECTION_VA = 0x490000
DETAIL_HANDLER_RAW = 0x8EA80
DETAIL_HANDLER_VA = 0x490A80
DETAIL_CONSTRUCTOR_RAW = 0x8EAC0
DETAIL_CONSTRUCTOR_VA = 0x490AC0
HELPER_RAW = 0x8EB80
HELPER_VA = 0x490B80
STRINGS_RAW = 0x8F600
STRINGS_VA = 0x491600
DETAIL_CONSTRUCTOR_HOOK_RAW = 0x4A5FA
DETAIL_CONSTRUCTOR_HOOK_VA = 0x44A5FA
DETAIL_HANDLER_HOOK_RAW = 0x4A700
DETAIL_HANDLER_HOOK_VA = 0x44A700
DETAIL_CONSTRUCTOR_BEFORE = bytes.fromhex("8B4C241C5F")
DETAIL_HANDLER_BEFORE = bytes.fromhex("8B44240453")
PARENT_BUTTON_VA = 0x490900

PRICE = 100_000
BOUND = 256
STRIDE = 0x3D8
SKILLS = (
    ("Parenting", 0x3BC, 2),
    ("Building", 0x3C0, 4),
    ("Farming", 0x3C4, 1),
    ("Healing", 0x3C8, 5),
    ("Research", 0x3CC, 3),
)


def canonical_source_text(payload: bytes) -> bytes:
    return payload.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def source_text_sha256(payload: bytes) -> str:
    return hashlib.sha256(canonical_source_text(payload)).hexdigest().upper()


def sha(payload: bytes | bytearray) -> str:
    return hashlib.sha256(payload).hexdigest().upper()


def asm(source: str, address: int) -> bytes:
    encoded, _ = Ks(KS_ARCH_X86, KS_MODE_32).asm(source, address)
    return bytes(encoded)


def rel32_jump(source_va: int, target_va: int) -> bytes:
    return b"\xE9" + struct.pack("<i", target_va - (source_va + 5))


def build_strings() -> tuple[bytes, dict[str, int]]:
    values = {
        "user32": b"USER32.dll\0",
        "messagebox": b"MessageBoxA\0",
        "caption": b"Villager Upgrades\0",
        "prompt": b"Grant Full Mastery to this villager for 100,000 tech points?\r\nPress OK to confirm, or Cancel.\0",
        "success": b"Full Mastery was granted to the selected villager.\0",
        "noop": b"This villager is already fully mastered.\r\nNo tech points have been deducted.\0",
        "cancel": b"Full Mastery was canceled.\r\nNo tech points have been deducted.\0",
        "invalid": b"No valid living non-Golden-Child villager is selected.\r\nNo tech points have been deducted.\0",
        "insufficient": b"Not enough tech points.\r\nNo tech points have been deducted.\0",
        "race": b"The selected villager or account changed during confirmation.\r\nNo tech points have been deducted.\0",
        "failure": b"Full Mastery could not be completed; native skill changes may remain.\r\nNo tech points have been deducted.\0",
        "dependency": b"Full Mastery dependencies are unavailable.\r\nNo tech points have been deducted.\0",
    }
    blob = bytearray()
    pointers: dict[str, int] = {}
    for key, value in values.items():
        pointers[key] = STRINGS_VA + len(blob)
        blob.extend(value)
    if len(blob) > 0xA00:
        raise RuntimeError("VV1 selected Full Mastery strings exceed their assigned parent space")
    return bytes(blob), pointers


def build_detail_handler() -> bytes:
    return asm(
        f"""
            cmp dword ptr [esp + 4], 8
            jne original
            cmp dword ptr [esp + 8], 6
            jne original
            call 0x{HELPER_VA:X}
            xor eax, eax
            ret 8
        original:
            mov eax, dword ptr [esp + 4]
            push ebx
            jmp 0x44A705
        """,
        DETAIL_HANDLER_VA,
    )


def build_detail_constructor() -> bytes:
    return asm(
        f"""
            push 0x14
            call 0x44AF03
            add esp, 4
            test eax, eax
            je done
            push 0
            push esi
            push 563
            push 120
            push 0x459340
            push 6
            mov ecx, eax
            call 0x4019B0
            mov edi, eax
            push 0
            push 0xFF555555
            push 0xFF555555
            push 0xFF000000
            push 0x{PARENT_BUTTON_VA:X}
            mov ecx, edi
            call 0x4015B0
            push edi
            mov ecx, esi
            call 0x40AB80
        done:
            mov ecx, dword ptr [esp + 0x1C]
            pop edi
            mov eax, esi
            pop esi
            pop ebx
            mov dword ptr fs:[0], ecx
            add esp, 0x1C
            ret
        """,
        DETAIL_CONSTRUCTOR_VA,
    )


def build_helper(strings: dict[str, int]) -> bytes:
    """Assemble the source-bound dry-run, native writes, and one direct charge."""
    lines = [
        "push ebp", "mov ebp, esp", "push ebx", "push esi", "push edi", "sub esp, 0x60",
        "mov dword ptr [ebp-0x10], 0", "mov dword ptr [ebp-0x14], ecx",
        f"push 0x{strings['user32']:X}", "call dword ptr [0x457010]", "test eax, eax", "jz dependency",
        f"push 0x{strings['messagebox']:X}", "push eax", "call dword ptr [0x4570D4]", "test eax, eax", "jz dependency",
        "mov dword ptr [ebp-0x10], eax",
        # Initial source-bound selected record acquisition.
        "mov ebx, dword ptr [ebp-0x14]", "test ebx, ebx", "jz invalid",
        "mov esi, dword ptr [ebx+0x0C]", "test esi, esi", "jz invalid", "mov dword ptr [ebp-0x18], esi",
        "mov eax, dword ptr [esi+0xAD34]", f"cmp eax, {BOUND}", "jae invalid", "mov dword ptr [ebp-0x1C], eax",
        "mov edi, dword ptr [ebx+0x10]", "test edi, edi", "jz invalid", "mov dword ptr [ebp-0x20], edi",
        "cmp edi, dword ptr [esi+0xADE8]", "jne invalid",
        "mov eax, dword ptr [ebp-0x1C]", f"imul eax, eax, 0x{STRIDE:X}", "add eax, edi", "mov dword ptr [ebp-0x24], eax", "mov esi, eax",
        # Eligibility precedes every skill/preference read.
        "cmp byte ptr [esi+0x28], 0", "je invalid", "cmp dword ptr [esi+0x344], 0", "jle invalid", "cmp dword ptr [esi+0x36C], 199", "je invalid",
        "movzx eax, byte ptr [esi+0x28]", "mov dword ptr [ebp-0x2C], eax",
        "mov eax, dword ptr [esi+0x344]", "mov dword ptr [ebp-0x30], eax",
        "mov eax, dword ptr [esi+0x36C]", "mov dword ptr [ebp-0x34], eax",
        "mov eax, dword ptr [esi+0x3D0]", "mov dword ptr [ebp-0x38], eax",
        "mov dword ptr [ebp-0x50], 0",
    ]
    for index, (_name, offset, _skill_id) in enumerate(SKILLS):
        slot = 0x3C + index * 4
        lines += [
            f"mov eax, dword ptr [esi+0x{offset:X}]", f"mov dword ptr [ebp-0x{slot:X}], eax",
            "cmp eax, 0", "jl invalid", "cmp eax, 100", "jg invalid", "cmp eax, 100", f"je unchanged_{index}",
            f"or dword ptr [ebp-0x50], {1 << index}", f"unchanged_{index}:",
        ]
    lines += [
        "cmp dword ptr [ebp-0x50], 0", "je noop",
        "mov esi, dword ptr [ebp-0x18]", "mov eax, dword ptr [esi+0xA2FC]", "mov dword ptr [ebp-0x28], eax",
        f"cmp eax, {PRICE}", "jb insufficient",
        "push 1", f"push 0x{strings['caption']:X}", f"push 0x{strings['prompt']:X}", "push 0", "call dword ptr [ebp-0x10]",
        "cmp eax, 1", "jne cancel",
        # Full exact reacquisition before the first write.
        "mov ebx, dword ptr [ebp-0x14]", "mov esi, dword ptr [ebx+0x0C]", "cmp esi, dword ptr [ebp-0x18]", "jne race",
        "mov eax, dword ptr [esi+0xAD34]", "cmp eax, dword ptr [ebp-0x1C]", "jne race",
        "mov edi, dword ptr [ebx+0x10]", "cmp edi, dword ptr [ebp-0x20]", "jne race", "cmp edi, dword ptr [esi+0xADE8]", "jne race",
        "mov eax, dword ptr [ebp-0x1C]", f"imul eax, eax, 0x{STRIDE:X}", "add eax, edi", "cmp eax, dword ptr [ebp-0x24]", "jne race", "mov esi, eax",
        "cmp byte ptr [esi+0x28], 0", "je race", "cmp dword ptr [esi+0x344], 0", "jle race", "cmp dword ptr [esi+0x36C], 199", "je race",
        "movzx eax, byte ptr [esi+0x28]", "cmp eax, dword ptr [ebp-0x2C]", "jne race",
        "mov eax, dword ptr [esi+0x344]", "cmp eax, dword ptr [ebp-0x30]", "jne race",
        "mov eax, dword ptr [esi+0x36C]", "cmp eax, dword ptr [ebp-0x34]", "jne race",
        "mov eax, dword ptr [esi+0x3D0]", "cmp eax, dword ptr [ebp-0x38]", "jne race",
    ]
    for index, (_name, offset, _skill_id) in enumerate(SKILLS):
        slot = 0x3C + index * 4
        lines += [f"mov eax, dword ptr [esi+0x{offset:X}]", f"cmp eax, dword ptr [ebp-0x{slot:X}]", "jne race"]
    lines += [
        "mov esi, dword ptr [ebp-0x18]", "mov eax, dword ptr [esi+0xA2FC]", "cmp eax, dword ptr [ebp-0x28]", "jne race",
    ]
    for index, (_name, offset, skill_id) in enumerate(SKILLS):
        lines += [
            "mov esi, dword ptr [ebp-0x24]", f"mov eax, dword ptr [esi+0x{offset:X}]", "cmp eax, 100", f"je write_{index}_done",
            "mov ebx, 100", "sub ebx, eax", "push ebx", f"push {skill_id}", "push dword ptr [ebp-0x1C]",
            "mov ecx, dword ptr [ebp-0x20]", "call 0x437230", f"write_{index}_done:",
        ]
    lines += [
        # Full postwrite reacquisition and verification. Native effects are not rolled back.
        "mov ebx, dword ptr [ebp-0x14]", "mov esi, dword ptr [ebx+0x0C]", "cmp esi, dword ptr [ebp-0x18]", "jne failure",
        "mov eax, dword ptr [esi+0xAD34]", "cmp eax, dword ptr [ebp-0x1C]", "jne failure",
        "mov edi, dword ptr [ebx+0x10]", "cmp edi, dword ptr [ebp-0x20]", "jne failure", "cmp edi, dword ptr [esi+0xADE8]", "jne failure",
        "mov eax, dword ptr [ebp-0x1C]", f"imul eax, eax, 0x{STRIDE:X}", "add eax, edi", "cmp eax, dword ptr [ebp-0x24]", "jne failure", "mov edi, eax",
        "cmp byte ptr [edi+0x28], 0", "je failure", "cmp dword ptr [edi+0x344], 0", "jle failure", "cmp dword ptr [edi+0x36C], 199", "je failure",
        "movzx eax, byte ptr [edi+0x28]", "cmp eax, dword ptr [ebp-0x2C]", "jne failure",
        "mov eax, dword ptr [edi+0x344]", "cmp eax, dword ptr [ebp-0x30]", "jne failure",
        "mov eax, dword ptr [edi+0x36C]", "cmp eax, dword ptr [ebp-0x34]", "jne failure",
        "mov eax, dword ptr [edi+0x3D0]", "cmp eax, dword ptr [ebp-0x38]", "jne failure",
    ]
    for _name, offset, _skill_id in SKILLS:
        lines += [f"cmp dword ptr [edi+0x{offset:X}], 100", "jne failure"]
    lines += [
        "mov esi, dword ptr [ebp-0x18]", f"cmp dword ptr [esi+0xA2FC], {PRICE}", "jb failure",
        f"sub dword ptr [esi+0xA2FC], {PRICE}",
        f"mov edx, 0x{strings['success']:X}", "jmp show",
        "noop:", f"mov edx, 0x{strings['noop']:X}", "jmp show",
        "cancel:", f"mov edx, 0x{strings['cancel']:X}", "jmp show",
        "invalid:", f"mov edx, 0x{strings['invalid']:X}", "jmp show",
        "insufficient:", f"mov edx, 0x{strings['insufficient']:X}", "jmp show",
        "race:", f"mov edx, 0x{strings['race']:X}", "jmp show",
        "failure:", f"mov edx, 0x{strings['failure']:X}", "jmp show",
        "dependency:", "cmp dword ptr [ebp-0x10], 0", "je done", f"mov edx, 0x{strings['dependency']:X}", "jmp show",
        "show:", "push 0", f"push 0x{strings['caption']:X}", "push edx", "push 0", "call dword ptr [ebp-0x10]",
        "done:", "add esp, 0x60", "pop edi", "pop esi", "pop ebx", "mov esp, ebp", "pop ebp", "ret",
    ]
    helper = asm("\n".join(lines), HELPER_VA)
    if len(helper) > STRINGS_RAW - HELPER_RAW:
        raise RuntimeError("VV1 selected Full Mastery helper exceeds its assigned parent space")
    return helper


def _patch(offset: int, before: bytes, after: bytes, purpose: str) -> dict[str, object]:
    if len(before) != len(after):
        raise RuntimeError(f"length-changing patch at 0x{offset:X}")
    return {"offset": f"0x{offset:X}", "before": before.hex().upper(), "after": after.hex().upper(), "purpose": purpose}


def _validate_parent() -> dict[str, object]:
    checks = (
        (PARENT_MANIFEST, PARENT_MANIFEST_SHA256, True),
        (PARENT_MAP, PARENT_MAP_SHA256, True),
        (PARENT_DLL, PARENT_DLL_SHA256, False),
        (STOCK, STOCK_SHA256, False),
        (OUT / "vv1_individual_grant_running_binding.json", "B36F3A4B6988F69EC50C43DE75E99A48DDB8503359BF7DB33252AAEBE7BA2C54", False),
    )
    for path, expected, text_hash in checks:
        actual = source_text_sha256(path.read_bytes()) if text_hash else sha(path.read_bytes())
        if actual != expected:
            raise RuntimeError(f"VV1 selected Full Mastery dependency hash mismatch: {path}")
    parent = json.loads(PARENT_MANIFEST.read_text(encoding="utf-8"))
    if parent.get("id") != PARENT_ID or not parent.get("enabled"):
        raise RuntimeError("VV1 Full Mastery parent is not the exact enabled prerequisite")
    for mode in MODES:
        page = bytes.fromhex(parent["pe_append_transaction"]["layouts"][mode]["append_bytes"])
        if len(page) != 0x2000 or any(page[0xA80:]):
            raise RuntimeError(f"VV1 parent {mode} does not retain the selected overlay zero preimage")
    return parent


def build_manifest() -> tuple[dict[str, object], dict[str, object]]:
    parent = _validate_parent()
    strings, pointers = build_strings()
    handler = build_detail_handler()
    constructor = build_detail_constructor()
    helper = build_helper(pointers)
    if len(handler) > DETAIL_CONSTRUCTOR_RAW - DETAIL_HANDLER_RAW:
        raise RuntimeError("VV1 Detail handler overlaps its constructor")
    if len(constructor) > HELPER_RAW - DETAIL_CONSTRUCTOR_RAW:
        raise RuntimeError("VV1 Detail constructor overlaps the transaction")

    patches = [
        _patch(DETAIL_CONSTRUCTOR_HOOK_RAW, DETAIL_CONSTRUCTOR_BEFORE, rel32_jump(DETAIL_CONSTRUCTOR_HOOK_VA, DETAIL_CONSTRUCTOR_VA), "append the stock-styled selected-villager Upgrades button at X=120/Y=563"),
        _patch(DETAIL_HANDLER_HOOK_RAW, DETAIL_HANDLER_BEFORE, rel32_jump(DETAIL_HANDLER_HOOK_VA, DETAIL_HANDLER_VA), "route only Detail event 8/button 6 to selected-villager Full Mastery"),
        _patch(DETAIL_HANDLER_RAW, bytes(len(handler)), handler, "install the collision-guarded Detail handler"),
        _patch(DETAIL_CONSTRUCTOR_RAW, bytes(len(constructor)), constructor, "install the X=120/Y=563 Detail button constructor"),
        _patch(HELPER_RAW, bytes(len(helper)), helper, "install the complete selected-villager native transaction"),
        _patch(STRINGS_RAW, bytes(len(strings)), strings, "install selected-villager confirmation and result text"),
    ]
    emitted = {
        "detail_handler": {"raw": f"0x{DETAIL_HANDLER_RAW:X}", "va": f"0x{DETAIL_HANDLER_VA:X}", "length": len(handler), "sha256": sha(handler)},
        "detail_constructor": {"raw": f"0x{DETAIL_CONSTRUCTOR_RAW:X}", "va": f"0x{DETAIL_CONSTRUCTOR_VA:X}", "length": len(constructor), "sha256": sha(constructor)},
        "helper": {"raw": f"0x{HELPER_RAW:X}", "va": f"0x{HELPER_VA:X}", "length": len(helper), "sha256": sha(helper)},
        "strings": {"raw": f"0x{STRINGS_RAW:X}", "va": f"0x{STRINGS_VA:X}", "length": len(strings), "sha256": sha(strings)},
    }
    contract = {
        "detail_event": 8,
        "button_id": 6,
        "price": PRICE,
        "target": 100,
        "action": "Buy",
        "repeatable": True,
        "ownership": None,
        "confirmation": "IDOK (1) only; Cancel, close, or any other return is no-change/no-charge",
        "selection": {
            "state": "[detail+0x0C]",
            "selected_index": "[state+0xAD34] unsigned < 256",
            "detail_record_pool": "[detail+0x10]",
            "state_record_pool": "[state+0xADE8]",
            "identity_guard": "same Detail owner, state, selected index, matching Detail/state pool, and derived record pointer; complete eligibility, five-skill, preference, and funds snapshot before writes",
        },
        "eligibility_before_skills": ["byte +0x28 != 0", "signed dword +0x344 > 0", "dword +0x36C != 199"],
        "skills": {name.lower(): f"+0x{offset:X} -> native skill {skill_id}" for name, offset, skill_id in SKILLS},
        "preference": "+0x3D0 is snapshotted and must remain unchanged; never written or normalized",
        "native_skill_writer": "sub_437230 thiscall ECX=matching record pool; push delta, skill id, physical selected index; ret 0x0C; changed skills only",
        "tech_deduction": "direct sub of exactly 100000 from fresh state+0xA2FC once after final unsigned funds recheck; positive award writer sub_41D120 and lifetime field state+0x9E20 are never called or touched",
        "transaction_order": [
            "MessageBox dependency preflight",
            "complete read-only selected-villager dry run",
            "no-change before funds and confirmation",
            "unsigned initial funds check",
            "explicit IDOK-only confirmation",
            "full identity, eligibility, skills, preference, and exact funds snapshot reacquisition",
            "five changed-only native skill writes",
            "full identity and eligibility reacquisition, exact-100 postverification, and unchanged preference verification",
            "fresh unsigned funds >= 100000 recheck",
            "one direct 100000 deduction from fresh state+0xA2FC",
        ],
        "rollback_limit": "native skill changes are not rolled back after a post-write failure; all such failures are no-charge and explicitly report that native changes may remain",
    }
    manifest: dict[str, object] = {
        "id": FEATURE_ID,
        "game_id": "vv1",
        "name": "Grant Full Mastery to Selected Villager",
        "enabled": True,
        "catalog_hidden": False,
        "catalog_enabled": True,
        "runtime_player_status": "pending",
        "certification_status": "implemented and statically verified; runtime/player confirmation pending",
        "dependencies": [PARENT_ID],
        "conflicts": list(CONFLICTS),
        "companion_files": [],
        "supported_modes": list(MODES),
        "rejected_modes": list(REJECTED_MODES),
        "description": "Adds a stock-styled Villager Detail action that grants exact Full Mastery to the selected living non-Golden-Child villager for 100,000 tech points through VV1's native changed-only skill writer. Stock Collection Progression and Immediate Fixed only.",
        "behavior_changes": [
            "Detail event 8/button 6 opens an explicit 100,000-tech-point Full Mastery confirmation for the selected eligible villager.",
            "Changed skills are raised to exactly 100 through native sub_437230 and completely postverified before one charge.",
        ],
        "explicit_non_changes": [
            "The prerequisite village-wide command-7 Tech hooks, implementation, price, and companion DLL remain unchanged.",
            "No legacy Origins owner is enabled or reused; those records explicitly conflict.",
            "Preference +0x3D0, positive award writer sub_41D120, and lifetime field state+0x9E20 are never written.",
            "Expanded-256 modes remain rejected before variant, catalog, manifest, or source access.",
        ],
        "evidence_status": "source/static emitted-byte verification; runtime/player confirmation pending",
        "static_evidence": {
            "selected_binding": {"path": "data/candidates/vv1_individual_grant_running_binding.json", "sha256": "B36F3A4B6988F69EC50C43DE75E99A48DDB8503359BF7DB33252AAEBE7BA2C54", "facts": "selected Detail path, unsigned 256 bound, state+ADE8 pool binding, active/living gates, and source-bound reacquisition contract"},
            "native_parent_map": {"path": "data/candidates/vv1_full_mastery_all_candidate_map.json", "source_text_sha256": PARENT_MAP_SHA256, "facts": "sub_437230 native skill writer; exact skills, IDs, eligibility, pool, Golden Child, and preference semantics"},
            "detail_alignment": {"source_path": "scripts/build_vv1_origins_feature.py", "sha256": "46AF8FB718726A2FB0F6433D1BBDD04C60F6885E19D4B05AD84E37519A43E8FF", "placement": "X=120/Y=563"},
            "player_runtime": "pending; no gameplay claim",
        },
        "parent_chain": {
            "stock_sha256": STOCK_SHA256,
            "parent_manifest_source_text_sha256": PARENT_MANIFEST_SHA256,
            "parent_map_source_text_sha256": PARENT_MAP_SHA256,
            "parent_dll_sha256": PARENT_DLL_SHA256,
            "parent_rendered_sha256": PARENT_RENDERED_SHA256,
            "current_baseline_sha256": CURRENT_BASELINE_SHA256,
            "parent_section_raw": f"0x{SECTION_RAW:X}",
            "parent_section_va": f"0x{SECTION_VA:X}",
            "owned_zero_preimage": "parent .vv1fm +0xA80..+0x1FFF",
        },
        "patches": patches,
        "transaction_contract": contract,
        "emitted": emitted,
    }

    import vv_fun_patcher as patcher  # noqa: E402

    build = next(item for item in patcher.load_builds() if item.id == "vv1")
    parent_feature = patcher.FunPatch(parent)
    child_feature = patcher.FunPatch(manifest)
    rendered_modes: dict[str, object] = {}
    for mode in MODES:
        baseline, _ = patcher.render_patched_bytes(STOCK, build, mode)
        if sha(baseline) != CURRENT_BASELINE_SHA256[mode]:
            raise RuntimeError(f"VV1 {mode} current baseline hash mismatch")
        parent_bytes, _ = patcher.render_patched_bytes(STOCK, build, mode, _fun_patches_override=[parent_feature])
        if sha(parent_bytes) != PARENT_RENDERED_SHA256[mode]:
            raise RuntimeError(f"VV1 {mode} parent render hash mismatch")
        if any(parent_bytes[DETAIL_HANDLER_RAW:SECTION_RAW + 0x2000]):
            raise RuntimeError(f"VV1 {mode} parent child-space preimage is not zero")
        candidate, _ = patcher.render_patched_bytes(STOCK, build, mode, _fun_patches_override=[parent_feature, child_feature])
        if candidate[0x358DC:0x358E1] != parent_bytes[0x358DC:0x358E1] or candidate[0x35AB0:0x35AB5] != parent_bytes[0x35AB0:0x35AB5]:
            raise RuntimeError(f"VV1 {mode} parent Tech hooks drifted")
        if candidate[SECTION_RAW:DETAIL_HANDLER_RAW] != parent_bytes[SECTION_RAW:DETAIL_HANDLER_RAW]:
            raise RuntimeError(f"VV1 {mode} parent command-7 region drifted")
        child_removed = bytearray(candidate)
        patcher._remove_feature_bytes(child_removed, child_feature, mode)
        if child_removed != parent_bytes:
            raise RuntimeError(f"VV1 {mode} child uninstall does not restore exact parent")
        parent_removed = bytearray(parent_bytes)
        patcher._remove_feature_bytes(parent_removed, parent_feature, mode)
        if parent_removed != baseline:
            raise RuntimeError(f"VV1 {mode} parent uninstall does not restore exact baseline")
        rendered_modes[mode] = {
            "current_baseline_sha256": sha(baseline),
            "parent_sha256": sha(parent_bytes),
            "candidate_sha256": sha(candidate),
            "uninstall_target_sha256": sha(parent_bytes),
            "parent_uninstall_target_sha256": sha(baseline),
            "size": len(candidate),
        }
    manifest["rendered_modes"] = rendered_modes
    mapping = {
        "candidate_id": FEATURE_ID,
        "enabled": True,
        "catalog_hidden": False,
        "catalog_enabled": True,
        "runtime_player_status": "pending",
        "supported_modes": list(MODES),
        "rejected_modes": list(REJECTED_MODES),
        "dependencies": [PARENT_ID],
        "conflicts": list(CONFLICTS),
        "parent_chain": manifest["parent_chain"],
        "static_evidence": manifest["static_evidence"],
        "detail_hooks": {
            "constructor": {"raw": f"0x{DETAIL_CONSTRUCTOR_HOOK_RAW:X}", "before": DETAIL_CONSTRUCTOR_BEFORE.hex().upper(), "after": patches[0]["after"], "target": f"0x{DETAIL_CONSTRUCTOR_VA:X}"},
            "handler": {"raw": f"0x{DETAIL_HANDLER_HOOK_RAW:X}", "before": DETAIL_HANDLER_BEFORE.hex().upper(), "after": patches[1]["after"], "target": f"0x{DETAIL_HANDLER_VA:X}"},
        },
        "emitted": emitted,
        "transaction_contract": contract,
        "rendered_modes": rendered_modes,
        "preserved_parent": {
            "tech_constructor_hook_raw": "0x358DC",
            "tech_handler_hook_raw": "0x35AB0",
            "command7_and_parent_section_range": "0x8E000..0x8EA7F",
            "parent_dll_sha256": PARENT_DLL_SHA256,
        },
    }
    return manifest, mapping


def main() -> None:
    manifest, mapping = build_manifest()
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    MAP.write_text(json.dumps(mapping, indent=2) + "\n", encoding="utf-8")
    DOC.write_text(
        "# VV1 Individual Full Mastery Candidate\n\n"
        "This public stock-only overlay adds one `Upgrades` button to Villager Detail at X=120/Y=563. Detail event 8/button 6 routes only to selected-villager Full Mastery for 100,000 tech points. It depends directly on `vv1_full_mastery_all_stage_a_candidate` and conflicts with every legacy VV1 Origins owner. Runtime/player confirmation remains pending.\n\n"
        "The child owns only the stock Detail hooks at raw `0x4A5FA` and `0x4A700`, plus the assigned zero-preimage ranges beginning at raw `0x8EA80` in the parent `.vv1fm` section. The prerequisite Tech hooks, village-wide command-7 implementation through raw `0x8EA7F`, and companion DLL remain byte-identical. Both stock modes are rendered and hash-pinned; Expanded-256 rejects before variant, catalog, manifest, or source access.\n\n"
        "The selected index is `[state+0xAD34]` with unsigned bound 256. `[detail+0x10]` must equal `[state+0xADE8]`; the Detail owner, state, selected index, pool, derived record pointer, eligibility, five skills, preference `+0x3D0`, and funds are snapshotted and fully rechecked before writes. Eligibility is active `+0x28 != 0`, signed health `+0x344 > 0`, and non-Golden Child `+0x36C != 199`, checked before skill or preference reads.\n\n"
        "Changed skills target exactly 100 through native `sub_437230` with ECX equal to the matching record pool and the proved index/skill/delta ABI. Complete exact-100 and unchanged-preference postverification precede a fresh unsigned funds check and one direct subtraction of 100,000 from fresh `state+0xA2FC`. Positive award writer `sub_41D120` is never called, and lifetime field `state+0x9E20` is never touched. Pre-write failures are no-change/no-charge. Native writes are not rolled back after a post-write failure; those paths explicitly report that native changes may remain and make no charge.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
