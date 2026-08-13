"""Generate the public stock-only VV2 selected-villager Full Mastery overlay.

The overlay depends on the certified village-wide VV2 candidate.  It reuses
only zero-filled bytes in that candidate's existing ``.vv2fm`` section and
adds the two independently guarded stock Villager Detail hooks.  The parent
Tech hooks, command-7 transaction, appended bytes, and companion DLL are not
rewritten by this generator.
"""

from __future__ import annotations

import hashlib
import json
import struct
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Lost Children.exe"
OUT = ROOT / "data" / "candidates"
MANIFEST = OUT / "vv2_individual_full_mastery_candidate.json"
MAP = OUT / "vv2_individual_full_mastery_candidate_map.json"
DOC = ROOT / "docs" / "vv2-individual-full-mastery-candidate.md"
PARENT_MANIFEST = OUT / "vv2_full_mastery_all_candidate.json"
PARENT_MAP = OUT / "vv2_full_mastery_all_candidate_map.json"
PARENT_DLL = OUT / "VVFP VV2 Full Mastery Candidate.dll"

sys.path.insert(0, str(ROOT / ".tools" / "keystone"))
sys.path.insert(0, str(ROOT / ".tools" / "keystone-runtime"))
sys.path.insert(0, str(ROOT / "src"))
from keystone import KS_ARCH_X86, KS_MODE_32, Ks  # noqa: E402


FEATURE_ID = "vv2_individual_full_mastery_candidate"
PARENT_ID = "vv2_full_mastery_all_stage_a_candidate"
MODES = ("collection_progression", "immediate_fixed")
REJECTED_MODES = (
    "experimental_expanded_256",
    "experimental_expanded_256_progression",
)
STOCK_SHA256 = "46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677"
PARENT_MANIFEST_SHA256 = "41CC8B5ADEAF702B1ACC38C832EADEEBF9B7FB23DA23A8A6E6328690F121A53C"
PARENT_MAP_SHA256 = "F93FC7C11D2306A3AA5DCC44EAC26785BC26BD86D46FCFAE51252E6E13FEE8C8"
PARENT_DLL_SHA256 = "1324EDFB83ABA755AFF6410D71DD668F4860127CD67A952722FDE5DD2FDC92C2"
PARENT_STATIC_ACCEPTANCE_SHA256 = {
    "collection_progression": "08F12344A5DE16832E5EFA22270300A1066EB94970359F432CEC723723055194",
    "immediate_fixed": "21B927806BDB06942F8426BC68E89AB1B10E2E60CEEFC39FEEFDCC125886BE7C",
}
PARENT_CURRENT_RENDERED_SHA256 = {
    "collection_progression": "1EF8F9A9D8C6336706943D37649D897C227408715940EE19CDBB8C6F4AFD63C3",
    "immediate_fixed": "A2F8F9B4DD2454A583096EE653E731235B17B608905E7808CFA15EF027B97042",
}
CURRENT_BASELINE_SHA256 = {
    "collection_progression": "B6A37FF5ECC60358988F222EB952E6710A1B351F175F178DECE74799428CB5E6",
    "immediate_fixed": "71BE2C0563159144C8D410AD11D14FC8F23FD767CB799C7C1763BEE534A8B0E3",
}
PARENT_STATIC_CHECKSUM = {
    "collection_progression": "0x000B77C9",
    "immediate_fixed": "0x000B62B9",
}
PARENT_CURRENT_CHECKSUM = {
    "collection_progression": "0x000BA721",
    "immediate_fixed": "0x000B9211",
}
DRIFT_COMMIT = "f9e5fd90bc998361b58c9c4849800dbd8cda6764"
DRIFT_RAW = 0x73D00
DRIFT_ACCEPTED = bytes.fromhex(
    "51E85A1BFBFF3D00010000597D05E96DB8FDFFB8FFFFFFFFC21400"
)
DRIFT_CURRENT = bytes.fromhex(
    "518B8DA450000085C9741B83B9A4050300007412E8471BFBFF"
    "3D00010000597306E95AB8FDFF59B8FFFFFFFFC21400"
)

IMAGE_BASE = 0x400000
SECTION_RAW = 0xB1000
SECTION_VA = 0x4B3000
DETAIL_HANDLER_RAW = 0xB2200
DETAIL_HANDLER_VA = 0x4B4200
DETAIL_CONSTRUCTOR_RAW = 0xB2240
DETAIL_CONSTRUCTOR_VA = 0x4B4240
HELPER_RAW = 0xB2300
HELPER_VA = 0x4B4300
STRINGS_RAW = 0xB2D00
STRINGS_VA = 0x4B4D00
DETAIL_CONSTRUCTOR_HOOK_RAW = 0x67624
DETAIL_CONSTRUCTOR_HOOK_VA = 0x467624
DETAIL_HANDLER_HOOK_RAW = 0x67720
DETAIL_HANDLER_HOOK_VA = 0x467720
DETAIL_CONSTRUCTOR_BEFORE = bytes.fromhex("8B4C242088")
DETAIL_HANDLER_BEFORE = bytes.fromhex("837C240408")

PRICE = 100_000
BOUND = 256
STRIDE = 0xE48C
SKILLS = (
    ("Farming", 0x7E4, 3),
    ("Building", 0x7E8, 2),
    ("Research", 0x7EC, 1),
    ("Healing", 0x7F0, 5),
    ("Parenting", 0x7F4, 4),
)


def canonical_source_text(payload: bytes) -> bytes:
    text = payload.decode("utf-8-sig")
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def source_text_sha256(payload: bytes) -> str:
    return hashlib.sha256(canonical_source_text(payload)).hexdigest().upper()


def sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest().upper()


def asm(source: str, address: int) -> bytes:
    encoded, _ = Ks(KS_ARCH_X86, KS_MODE_32).asm(source, address)
    return bytes(encoded)


def rel32_jump(source_va: int, target_va: int) -> bytes:
    return b"\xE9" + struct.pack("<i", target_va - (source_va + 5))


def build_strings() -> tuple[bytes, dict[str, int]]:
    values = {
        "button": b"Upgrades\0",
        "user32": b"USER32.dll\0",
        "messagebox": b"MessageBoxA\0",
        "caption": b"Villager Upgrades\0",
        "prompt": (
            b"Grant Full Mastery to this villager for 100,000 tech points?\r\n"
            b"Press OK to confirm, or Cancel.\0"
        ),
        "success": b"Full Mastery was granted to the selected villager.\0",
        "noop": (
            b"This villager is already fully mastered.\r\n"
            b"No tech points have been deducted.\0"
        ),
        "cancel": (
            b"Full Mastery was canceled.\r\n"
            b"No tech points have been deducted.\0"
        ),
        "invalid": (
            b"No valid living non-totem villager is selected.\r\n"
            b"No tech points have been deducted.\0"
        ),
        "insufficient": (
            b"Not enough tech points.\r\n"
            b"No tech points have been deducted.\0"
        ),
        "race": (
            b"The selected villager or account changed during confirmation.\r\n"
            b"No tech points have been deducted.\0"
        ),
        "failure": (
            b"Full Mastery could not be completed; native skill changes may remain.\r\n"
            b"No tech points have been deducted.\0"
        ),
        "dependency": (
            b"Full Mastery dependencies are unavailable.\r\n"
            b"No tech points have been deducted.\0"
        ),
    }
    blob = bytearray()
    pointers: dict[str, int] = {}
    for key, value in values.items():
        pointers[key] = STRINGS_VA + len(blob)
        blob.extend(value)
    if len(blob) > 0x300:
        raise RuntimeError("VV2 selected Full Mastery string block exceeds reserved space")
    return bytes(blob), pointers


def build_detail_handler() -> bytes:
    return asm(
        f"""
            cmp dword ptr [esp + 4], 8
            jne original_handler
            cmp dword ptr [esp + 8], 6
            jne original_handler
            call 0x{HELPER_VA:X}
            xor eax, eax
            ret 8
        original_handler:
            cmp dword ptr [esp + 4], 8
            jmp 0x467725
        """,
        DETAIL_HANDLER_VA,
    )


def build_detail_constructor(button_pointer: int) -> bytes:
    return asm(
        f"""
            push 0x14
            call 0x467F83
            add esp, 4
            test eax, eax
            je constructor_done
            push 0
            push esi
            push 563
            push 140
            push 0x4763E8
            push 6
            mov ecx, eax
            call 0x4019D0
            mov edi, eax
            push 0
            push 0xFF555555
            push 0xFF555555
            push 0xFF000000
            push 0x{button_pointer:X}
            mov ecx, edi
            call 0x4015D0
            push edi
            mov ecx, esi
            call 0x40B560
        constructor_done:
            mov ecx, dword ptr [esp + 0x20]
            mov byte ptr [esi + 0x26], bl
            mov byte ptr [esi + 0x27], bl
            pop edi
            mov byte ptr [esi + 0x25], 1
            mov eax, esi
            pop esi
            pop ebx
            mov dword ptr fs:[0], ecx
            add esp, 0x20
            ret
        """,
        DETAIL_CONSTRUCTOR_VA,
    )


def build_helper(strings: dict[str, int]) -> bytes:
    """Assemble the selected-villager dry-run/native transaction."""
    lines = [
        "push ebp", "mov ebp, esp", "push ebx", "push esi", "push edi", "sub esp, 0x60",
        # Keep the Detail owner and resolve MessageBoxA before any record read.
        "mov dword ptr [ebp-0x10], 0", "mov dword ptr [ebp-0x14], ecx",
        f"push 0x{strings['user32']:X}", "call dword ptr [0x474010]", "test eax, eax", "jz dependency",
        f"push 0x{strings['messagebox']:X}", "push eax", "call dword ptr [0x4740D4]", "test eax, eax", "jz dependency",
        "mov dword ptr [ebp-0x10], eax",
        # Initial exact Detail/state/index/pool/manager/record acquisition.
        "mov ebx, dword ptr [ebp-0x14]", "test ebx, ebx", "jz invalid",
        "mov esi, dword ptr [ebx+0x0C]", "test esi, esi", "jz invalid", "mov dword ptr [ebp-0x18], esi",
        "mov eax, dword ptr [esi+0x304F0]", f"cmp eax, {BOUND}", "jae invalid", "mov dword ptr [ebp-0x1C], eax",
        "mov edi, dword ptr [ebx+0x10]", "test edi, edi", "jz invalid", "mov dword ptr [ebp-0x20], edi",
        "call 0x44F4E0", "test eax, eax", "jz invalid", "mov dword ptr [ebp-0x24], eax",
        "lea edx, [eax+0x52C]", "cmp edx, edi", "jne invalid",
        "mov eax, dword ptr [ebp-0x1C]", f"imul eax, eax, 0x{STRIDE:X}", "add eax, edi", "mov dword ptr [ebp-0x28], eax", "mov esi, eax",
        # Eligibility is checked before skill reads.
        "cmp byte ptr [esi+0x30], 0", "je invalid", "cmp dword ptr [esi+0x52C], 0", "jle invalid", "cmp byte ptr [esi+0x558], 0", "jne invalid",
        "movzx eax, byte ptr [esi+0x30]", "mov dword ptr [ebp-0x30], eax",
        "mov eax, dword ptr [esi+0x52C]", "mov dword ptr [ebp-0x34], eax",
        "movzx eax, byte ptr [esi+0x558]", "mov dword ptr [ebp-0x38], eax",
        "mov eax, dword ptr [esi+0x7F8]", "mov dword ptr [ebp-0x3C], eax",
        "mov dword ptr [ebp-0x54], 0",
    ]
    for index, (_name, offset, _skill_id) in enumerate(SKILLS):
        slot = 0x40 + index * 4
        lines += [
            f"mov eax, dword ptr [esi+0x{offset:X}]", f"mov dword ptr [ebp-0x{slot:X}], eax",
            f"cmp dword ptr [ebp-0x{slot:X}], 0", "jl invalid",
            f"cmp dword ptr [ebp-0x{slot:X}], 100", "jg invalid",
            f"cmp dword ptr [ebp-0x{slot:X}], 100", f"je skill_{index}_unchanged",
            f"or dword ptr [ebp-0x54], {1 << index}", f"skill_{index}_unchanged:",
        ]
    lines += [
        # No-change exits before either funds or confirmation.
        "cmp dword ptr [ebp-0x54], 0", "je noop",
        "mov esi, dword ptr [ebp-0x18]", "mov eax, dword ptr [esi+0x2EADC]", "mov dword ptr [ebp-0x2C], eax",
        f"cmp eax, {PRICE}", "jb insufficient",
        "push 1", f"push 0x{strings['caption']:X}", f"push 0x{strings['prompt']:X}", "push 0", "call dword ptr [ebp-0x10]",
        "cmp eax, 1", "jne cancel",
        # Reacquire and require the same state, selection, pool, manager, record,
        # transaction-relevant record snapshot, and exact funds value.
        "mov ebx, dword ptr [ebp-0x14]", "mov esi, dword ptr [ebx+0x0C]", "cmp esi, dword ptr [ebp-0x18]", "jne race",
        "mov eax, dword ptr [esi+0x304F0]", "cmp eax, dword ptr [ebp-0x1C]", "jne race",
        "mov edi, dword ptr [ebx+0x10]", "cmp edi, dword ptr [ebp-0x20]", "jne race",
        "call 0x44F4E0", "cmp eax, dword ptr [ebp-0x24]", "jne race",
        "lea edx, [eax+0x52C]", "cmp edx, edi", "jne race",
        "mov eax, dword ptr [ebp-0x1C]", f"imul eax, eax, 0x{STRIDE:X}", "add eax, edi", "cmp eax, dword ptr [ebp-0x28]", "jne race", "mov esi, eax",
        "cmp byte ptr [esi+0x30], 0", "je race", "cmp dword ptr [esi+0x52C], 0", "jle race", "cmp byte ptr [esi+0x558], 0", "jne race",
        "movzx eax, byte ptr [esi+0x30]", "cmp eax, dword ptr [ebp-0x30]", "jne race",
        "mov eax, dword ptr [esi+0x52C]", "cmp eax, dword ptr [ebp-0x34]", "jne race",
        "movzx eax, byte ptr [esi+0x558]", "cmp eax, dword ptr [ebp-0x38]", "jne race",
        "mov eax, dword ptr [esi+0x7F8]", "cmp eax, dword ptr [ebp-0x3C]", "jne race",
    ]
    for index, (_name, offset, _skill_id) in enumerate(SKILLS):
        slot = 0x40 + index * 4
        lines += [f"mov eax, dword ptr [esi+0x{offset:X}]", f"cmp eax, dword ptr [ebp-0x{slot:X}]", "jne race"]
    lines += [
        "mov esi, dword ptr [ebp-0x18]", "mov eax, dword ptr [esi+0x2EADC]", "cmp eax, dword ptr [ebp-0x2C]", "jne race",
    ]
    for index, (_name, offset, skill_id) in enumerate(SKILLS):
        lines += [
            "mov esi, dword ptr [ebp-0x28]", f"mov eax, dword ptr [esi+0x{offset:X}]", "cmp eax, 100", f"je write_{index}_done",
            "mov ebx, 100", "sub ebx, eax", "push ebx", f"push {skill_id}", "push dword ptr [ebp-0x1C]",
            "mov ecx, dword ptr [ebp-0x24]", "add ecx, 0x52C", "call 0x445430", f"write_{index}_done:",
        ]
    lines += [
        # Complete pre-evaluator reacquisition and exact-100 postverification.
        "mov ebx, dword ptr [ebp-0x14]", "mov esi, dword ptr [ebx+0x0C]", "cmp esi, dword ptr [ebp-0x18]", "jne failure",
        "mov eax, dword ptr [esi+0x304F0]", "cmp eax, dword ptr [ebp-0x1C]", "jne failure",
        "mov edi, dword ptr [ebx+0x10]", "cmp edi, dword ptr [ebp-0x20]", "jne failure",
        "call 0x44F4E0", "cmp eax, dword ptr [ebp-0x24]", "jne failure",
        "lea edx, [eax+0x52C]", "cmp edx, edi", "jne failure",
        "mov eax, dword ptr [ebp-0x1C]", f"imul eax, eax, 0x{STRIDE:X}", "add eax, edi", "cmp eax, dword ptr [ebp-0x28]", "jne failure", "mov esi, eax",
        "cmp byte ptr [esi+0x30], 0", "je failure", "cmp dword ptr [esi+0x52C], 0", "jle failure", "cmp byte ptr [esi+0x558], 0", "jne failure",
        "movzx eax, byte ptr [esi+0x30]", "cmp eax, dword ptr [ebp-0x30]", "jne failure",
        "mov eax, dword ptr [esi+0x52C]", "cmp eax, dword ptr [ebp-0x34]", "jne failure",
        "mov eax, dword ptr [esi+0x7F8]", "cmp eax, dword ptr [ebp-0x3C]", "jne failure",
    ]
    for _name, offset, _skill_id in SKILLS:
        lines += [f"cmp dword ptr [esi+0x{offset:X}], 100", "jne failure"]
    lines += [
        "mov esi, dword ptr [ebp-0x18]", "mov eax, dword ptr [esi+0x2EADC]", "cmp eax, dword ptr [ebp-0x2C]", "jne failure",
        # The native evaluator is semantically required for Elder/totem effects.
        "mov ecx, dword ptr [ebp-0x24]", "call 0x44D4C0",
        # Final fresh identity/account/funds acquisition.  Totem byte is not
        # required to remain zero because the evaluator may promote the target.
        "mov ebx, dword ptr [ebp-0x14]", "mov esi, dword ptr [ebx+0x0C]", "cmp esi, dword ptr [ebp-0x18]", "jne failure",
        "mov eax, dword ptr [esi+0x304F0]", "cmp eax, dword ptr [ebp-0x1C]", "jne failure",
        "mov edi, dword ptr [ebx+0x10]", "cmp edi, dword ptr [ebp-0x20]", "jne failure",
        "call 0x44F4E0", "cmp eax, dword ptr [ebp-0x24]", "jne failure",
        "lea edx, [eax+0x52C]", "cmp edx, edi", "jne failure",
        "mov eax, dword ptr [ebp-0x1C]", f"imul eax, eax, 0x{STRIDE:X}", "add eax, edi", "cmp eax, dword ptr [ebp-0x28]", "jne failure", "mov esi, eax",
        "cmp byte ptr [esi+0x30], 0", "je failure", "cmp dword ptr [esi+0x52C], 0", "jle failure",
        "movzx eax, byte ptr [esi+0x30]", "cmp eax, dword ptr [ebp-0x30]", "jne failure",
        "mov eax, dword ptr [esi+0x52C]", "cmp eax, dword ptr [ebp-0x34]", "jne failure",
        "mov eax, dword ptr [esi+0x7F8]", "cmp eax, dword ptr [ebp-0x3C]", "jne failure",
    ]
    for _name, offset, _skill_id in SKILLS:
        lines += [f"cmp dword ptr [esi+0x{offset:X}], 100", "jne failure"]
    lines += [
        "mov esi, dword ptr [ebp-0x18]", f"cmp dword ptr [esi+0x2EADC], {PRICE}", "jb failure",
        "mov ecx, esi", f"push -{PRICE}", "call 0x426290",
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
        raise RuntimeError("VV2 selected Full Mastery helper exceeds reserved space")
    return helper


def _patch(offset: int, before: bytes, after: bytes, purpose: str) -> dict[str, object]:
    if len(before) != len(after):
        raise RuntimeError(f"length-changing patch at 0x{offset:X}")
    return {
        "offset": f"0x{offset:X}",
        "before": before.hex().upper(),
        "after": after.hex().upper(),
        "purpose": purpose,
    }


def _validate_parent() -> dict[str, object]:
    parent_bytes = PARENT_MANIFEST.read_bytes()
    map_bytes = PARENT_MAP.read_bytes()
    if source_text_sha256(parent_bytes) != PARENT_MANIFEST_SHA256:
        raise RuntimeError("VV2 Full Mastery parent manifest hash mismatch")
    if source_text_sha256(map_bytes) != PARENT_MAP_SHA256:
        raise RuntimeError("VV2 Full Mastery parent map hash mismatch")
    if sha(PARENT_DLL.read_bytes()) != PARENT_DLL_SHA256:
        raise RuntimeError("VV2 Full Mastery parent DLL hash mismatch")
    if sha(STOCK.read_bytes()) != STOCK_SHA256:
        raise RuntimeError("VV2 stock executable hash mismatch")
    evidence_files = {
        ROOT / "research" / "ida-batch" / "vv2-coconut.json": "A070824C5A67FFD0C4D40ECE1EB03FA693CEAA284A0675DEE5C9230E9C8254AF",
        OUT / "vv2_individual_grant_running_binding.json": "FC8165A0A04BD6094477B1DBD86785A2F5733637861E12A371BA7DFDE1EB2C09",
        ROOT / "scripts" / "build_vv2_origins_feature.py": "FA0FB729A7906694F339D6B64E68571723A14BE32129CEBCAB1707F490F31CD6",
    }
    for path, expected in evidence_files.items():
        if sha(path.read_bytes()) != expected:
            raise RuntimeError(f"VV2 selected Full Mastery evidence hash mismatch: {path}")
    parent = json.loads(parent_bytes.decode("utf-8"))
    if parent.get("id") != PARENT_ID or not parent.get("enabled"):
        raise RuntimeError("VV2 Full Mastery parent is not the exact enabled prerequisite")
    for mode in MODES:
        append_bytes = bytes.fromhex(
            parent["pe_append_transaction"]["layouts"][mode]["append_bytes"]
        )
        if len(append_bytes) != 0x2000 or any(append_bytes[0x1200:]):
            raise RuntimeError(f"VV2 parent {mode} does not retain the selected overlay zero preimage")
    return parent


def build_manifest() -> tuple[dict[str, object], dict[str, object]]:
    parent = _validate_parent()
    strings, pointers = build_strings()
    handler = build_detail_handler()
    constructor = build_detail_constructor(pointers["button"])
    helper = build_helper(pointers)
    if len(handler) > DETAIL_CONSTRUCTOR_RAW - DETAIL_HANDLER_RAW:
        raise RuntimeError("Detail handler overlaps constructor")
    if len(constructor) > HELPER_RAW - DETAIL_CONSTRUCTOR_RAW:
        raise RuntimeError("Detail constructor overlaps helper")

    patches = [
        _patch(
            DETAIL_CONSTRUCTOR_HOOK_RAW,
            DETAIL_CONSTRUCTOR_BEFORE,
            rel32_jump(DETAIL_CONSTRUCTOR_HOOK_VA, DETAIL_CONSTRUCTOR_VA),
            "append the stock-styled selected-villager Upgrades button at X=140/Y=563",
        ),
        _patch(
            DETAIL_HANDLER_HOOK_RAW,
            DETAIL_HANDLER_BEFORE,
            rel32_jump(DETAIL_HANDLER_HOOK_VA, DETAIL_HANDLER_VA),
            "route only Detail event 8/button 6 to selected-villager Full Mastery",
        ),
        _patch(DETAIL_HANDLER_RAW, bytes(len(handler)), handler, "install the collision-guarded Detail handler"),
        _patch(DETAIL_CONSTRUCTOR_RAW, bytes(len(constructor)), constructor, "install the X=140/Y=563 Detail button constructor"),
        _patch(HELPER_RAW, bytes(len(helper)), helper, "install the complete selected-villager native transaction"),
        _patch(STRINGS_RAW, bytes(len(strings)), strings, "install selected-villager labels, confirmation, and results"),
    ]
    emitted = {
        "detail_handler": {"raw": f"0x{DETAIL_HANDLER_RAW:X}", "va": f"0x{DETAIL_HANDLER_VA:X}", "length": len(handler), "sha256": sha(handler)},
        "detail_constructor": {"raw": f"0x{DETAIL_CONSTRUCTOR_RAW:X}", "va": f"0x{DETAIL_CONSTRUCTOR_VA:X}", "length": len(constructor), "sha256": sha(constructor)},
        "helper": {"raw": f"0x{HELPER_RAW:X}", "va": f"0x{HELPER_VA:X}", "length": len(helper), "sha256": sha(helper)},
        "strings": {"raw": f"0x{STRINGS_RAW:X}", "va": f"0x{STRINGS_VA:X}", "length": len(strings), "sha256": sha(strings)},
    }
    manifest: dict[str, object] = {
        "id": FEATURE_ID,
        "game_id": "vv2",
        "name": "Grant Full Mastery to Selected Villager",
        "enabled": True,
        "catalog_hidden": False,
        "catalog_enabled": True,
        "runtime_player_status": "pending",
        "certification_status": "implemented and statically verified; runtime/player confirmation pending",
        "dependencies": [PARENT_ID],
        "companion_files": [],
        "supported_modes": list(MODES),
        "rejected_modes": list(REJECTED_MODES),
        "description": "Adds one stock-styled Villager Detail action for the currently selected living non-totem villager. It grants exact Full Mastery for 100,000 tech points through VV2's native manager, changed-only skill writer, Elder evaluator, and tech writer. Stock Collection Progression and Immediate Fixed only.",
        "behavior_changes": [
            "Detail event 8/button 6 opens an explicit 100,000-tech-point Full Mastery confirmation for the current selected eligible villager.",
            "Changed skills are raised to exactly 100 by native deltas; the native Elder evaluator runs once only after complete exact-100 postverification.",
        ],
        "explicit_non_changes": [
            "The prerequisite village-wide command-7 bytes, Tech hooks, price, behavior, rendered identities, and companion DLL remain unchanged when this feature is not selected.",
            "VV2 Barrel code and X=140/Y=563 Detail alignment are unchanged.",
            "No Origins-exclusive feature is enabled or required.",
            "Expanded-256 modes remain rejected before output.",
        ],
        "evidence_status": "source/static emitted-byte verification; runtime/player confirmation pending",
        "static_evidence": {
            "stock_detail_ida": {
                "path": "research/ida-batch/vv2-coconut.json",
                "sha256": "A070824C5A67FFD0C4D40ECE1EB03FA693CEAA284A0675DEE5C9230E9C8254AF",
                "function": "sub_467720",
                "facts": "stock Detail reads state at this+0x0C, selected physical index at state+197872 (0x304F0), record pool at this+0x10, and stride 58508 (0xE48C)",
            },
            "selected_binding": {
                "path": "data/candidates/vv2_individual_grant_running_binding.json",
                "sha256": "FC8165A0A04BD6094477B1DBD86785A2F5733637861E12A371BA7DFDE1EB2C09",
                "facts": "existing selected Detail path, 256 bound, active/living eligibility, and exact selection/account reacquisition requirement",
            },
            "native_parent_map": {
                "path": "data/candidates/vv2_full_mastery_all_candidate_map.json",
                "source_text_sha256": PARENT_MAP_SHA256,
                "facts": "sub_44F4E0 manager and manager+0x52C record pool, sub_445430 skill writer, sub_44D4C0 evaluator, sub_426290 tech writer",
            },
            "detail_alignment": {
                "source_path": "scripts/build_vv2_origins_feature.py",
                "sha256": "FA0FB729A7906694F339D6B64E68571723A14BE32129CEBCAB1707F490F31CD6",
                "commits": ["17fdb89", "c968b6a"],
                "placement": "X=140/Y=563",
            },
            "player_runtime": "pending; no gameplay claim",
        },
        "parent_chain": {
            "stock_sha256": STOCK_SHA256,
            "parent_manifest_source_text_sha256": PARENT_MANIFEST_SHA256,
            "parent_map_source_text_sha256": PARENT_MAP_SHA256,
            "parent_dll_sha256": PARENT_DLL_SHA256,
            "parent_static_acceptance_sha256": PARENT_STATIC_ACCEPTANCE_SHA256,
            "parent_current_rendered_sha256": PARENT_CURRENT_RENDERED_SHA256,
            "parent_section_raw": f"0x{SECTION_RAW:X}",
            "parent_section_va": f"0x{SECTION_VA:X}",
            "owned_zero_preimage": "parent .vv2fm +0x1200..+0x1FFF",
            "current_baseline_sha256": CURRENT_BASELINE_SHA256,
            "parent_render_drift": {
                "classification": "one automatic:safety cave replacement plus the deterministic PE checksum; no parent-owned hook, command-7, section, or DLL byte changed",
                "commit": DRIFT_COMMIT,
                "commit_subject": "Fix VV2 event allocation context",
                "owner": "automatic:safety",
                "raw_offset": f"0x{DRIFT_RAW:X}",
                "current_length": len(DRIFT_CURRENT),
                "accepted_payload_length": len(DRIFT_ACCEPTED),
                "accepted_payload_hex": DRIFT_ACCEPTED.hex().upper(),
                "accepted_zero_tail_length": len(DRIFT_CURRENT) - len(DRIFT_ACCEPTED),
                "current_payload_hex": DRIFT_CURRENT.hex().upper(),
                "checksum_raw_offset": "0x148",
                "accepted_checksums": PARENT_STATIC_CHECKSUM,
                "current_checksums": PARENT_CURRENT_CHECKSUM,
                "reconstruction": "replace the 47-byte current cave with the 27-byte accepted payload plus 20 zeros, then recompute the PE checksum; both frozen parent hashes reproduce exactly",
            },
        },
        "patches": patches,
        "transaction_contract": {
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
                "selected_index": "[state+0x304F0] unsigned < 256",
                "detail_record_pool": "[detail+0x10]",
                "manager_record_pool": "sub_44F4E0 return + 0x52C",
                "identity_guard": "same Detail owner, state, selected index, detail pool, manager, and derived record pointer; complete active/health/totem/skills/job snapshot before writes",
            },
            "eligibility_before_skills": [
                "byte +0x30 != 0",
                "signed dword +0x52C > 0",
                "byte +0x558 == 0",
            ],
            "skills": {name.lower(): f"+0x{offset:X} -> native skill {skill_id}" for name, offset, skill_id in SKILLS},
            "native_manager_getter": "sub_44F4E0 no arguments; exact manager/pool/record identity re-acquired at every boundary",
            "native_skill_writer": "sub_445430 thiscall ECX=manager+0x52C; push delta, skill id, physical selected index; changed skills only",
            "native_evaluator": "sub_44D4C0 thiscall ECX=manager; exactly once after complete exact-100 postverify; semantically required for native Elder/totem effects",
            "native_tech_writer": "sub_426290 thiscall ECX=fresh state; push signed -100000; exactly once after final funds recheck",
            "transaction_order": [
                "MessageBox dependency preflight",
                "complete read-only selected-villager dry run",
                "no-change before funds and confirmation",
                "unsigned initial funds check",
                "explicit IDOK-only confirmation",
                "same selection/identity/manager/account/exact funds and complete snapshot reacquisition",
                "changed-only native skill writes",
                "complete exact-100 pre-evaluator postverify",
                "one native Elder evaluator",
                "fresh same selection/identity/manager/account reacquisition and exact-100 postverify",
                "fresh unsigned funds >= 100000 recheck",
                "one native -100000 deduction",
            ],
            "rollback_limit": "native skill/evaluator changes are not rolled back after a post-write failure; all such failures are no-charge and explicitly reported",
        },
        "emitted": emitted,
    }

    # Authenticate the complete prerequisite render before recording the child
    # composition identity.  No executable is written.
    import vv_fun_patcher as patcher  # noqa: E402

    build = next(item for item in patcher.load_builds() if item.id == "vv2")
    parent_feature = patcher.FunPatch(parent)
    child_feature = patcher.FunPatch(manifest)
    rendered_modes: dict[str, object] = {}
    for mode in MODES:
        baseline, _ = patcher.render_patched_bytes(STOCK, build, mode)
        if sha(baseline) != CURRENT_BASELINE_SHA256[mode]:
            raise RuntimeError(f"VV2 {mode} current baseline hash mismatch")
        parent_bytes, _ = patcher.render_patched_bytes(
            STOCK, build, mode, _fun_patches_override=[parent_feature]
        )
        parent_digest = sha(parent_bytes)
        if parent_digest != PARENT_CURRENT_RENDERED_SHA256[mode]:
            raise RuntimeError(f"VV2 {mode} parent rendered hash mismatch")
        if bytes(parent_bytes[DRIFT_RAW:DRIFT_RAW + len(DRIFT_CURRENT)]) != DRIFT_CURRENT:
            raise RuntimeError(f"VV2 {mode} current automatic:safety cave drift is not exact")
        checksum_offset, _ = patcher._pe_checksum_layout(parent_bytes)
        if checksum_offset != 0x148 or f"0x{int.from_bytes(parent_bytes[checksum_offset:checksum_offset+4], 'little'):08X}" != PARENT_CURRENT_CHECKSUM[mode]:
            raise RuntimeError(f"VV2 {mode} current parent checksum is not exact")
        reconstructed = bytearray(parent_bytes)
        reconstructed[DRIFT_RAW:DRIFT_RAW + len(DRIFT_CURRENT)] = (
            DRIFT_ACCEPTED + bytes(len(DRIFT_CURRENT) - len(DRIFT_ACCEPTED))
        )
        reconstructed[checksum_offset:checksum_offset + 4] = bytes(4)
        reconstructed[checksum_offset:checksum_offset + 4] = patcher.pe_checksum(
            reconstructed
        ).to_bytes(4, "little")
        if sha(reconstructed) != PARENT_STATIC_ACCEPTANCE_SHA256[mode]:
            raise RuntimeError(f"VV2 {mode} frozen parent identity was not exactly reconstructed")
        if f"0x{int.from_bytes(reconstructed[checksum_offset:checksum_offset+4], 'little'):08X}" != PARENT_STATIC_CHECKSUM[mode]:
            raise RuntimeError(f"VV2 {mode} frozen parent checksum was not exactly reconstructed")
        parent_uninstall = bytearray(parent_bytes)
        patcher._remove_feature_bytes(parent_uninstall, parent_feature, mode)
        if parent_uninstall != baseline:
            raise RuntimeError(f"VV2 {mode} current parent uninstall does not restore the current baseline")
        candidate, _ = patcher.render_patched_bytes(
            STOCK, build, mode, _fun_patches_override=[parent_feature, child_feature]
        )
        # The parent Tech hooks and command-7 body remain exact in composition.
        if candidate[0x435EF:0x435F4] != parent_bytes[0x435EF:0x435F4]:
            raise RuntimeError(f"VV2 {mode} Tech constructor hook drifted")
        if candidate[0x437C0:0x437C5] != parent_bytes[0x437C0:0x437C5]:
            raise RuntimeError(f"VV2 {mode} Tech handler hook drifted")
        if candidate[SECTION_RAW:SECTION_RAW+0x1200] != parent_bytes[SECTION_RAW:SECTION_RAW+0x1200]:
            raise RuntimeError(f"VV2 {mode} command-7 parent region drifted")
        child_uninstall = bytearray(candidate)
        patcher._remove_feature_bytes(child_uninstall, child_feature, mode)
        if child_uninstall != parent_bytes:
            raise RuntimeError(f"VV2 {mode} child uninstall does not restore the current parent")
        rendered_modes[mode] = {
            "current_baseline_sha256": sha(baseline),
            "parent_sha256": parent_digest,
            "candidate_sha256": sha(candidate),
            "uninstall_target_sha256": parent_digest,
            "parent_uninstall_target_sha256": sha(baseline),
            "size": len(candidate),
        }
    manifest["rendered_modes"] = rendered_modes

    mapping: dict[str, object] = {
        "candidate_id": FEATURE_ID,
        "enabled": True,
        "catalog_hidden": False,
        "catalog_enabled": True,
        "runtime_player_status": "pending",
        "supported_modes": list(MODES),
        "rejected_modes": list(REJECTED_MODES),
        "dependencies": [PARENT_ID],
        "parent_chain": manifest["parent_chain"],
        "static_evidence": manifest["static_evidence"],
        "detail_hooks": {
            "constructor": {"raw": f"0x{DETAIL_CONSTRUCTOR_HOOK_RAW:X}", "before": DETAIL_CONSTRUCTOR_BEFORE.hex().upper(), "after": patches[0]["after"], "target": f"0x{DETAIL_CONSTRUCTOR_VA:X}"},
            "handler": {"raw": f"0x{DETAIL_HANDLER_HOOK_RAW:X}", "before": DETAIL_HANDLER_BEFORE.hex().upper(), "after": patches[1]["after"], "target": f"0x{DETAIL_HANDLER_VA:X}"},
        },
        "emitted": emitted,
        "transaction_contract": manifest["transaction_contract"],
        "rendered_modes": rendered_modes,
        "preserved_parent": {
            "tech_constructor_hook_raw": "0x435EF",
            "tech_handler_hook_raw": "0x437C0",
            "command7_and_parent_section_range": "0xB1000..0xB21FF",
            "parent_dll_sha256": PARENT_DLL_SHA256,
        },
    }
    return manifest, mapping


def main() -> None:
    manifest, mapping = build_manifest()
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    MAP.write_text(json.dumps(mapping, indent=2) + "\n", encoding="utf-8")
    DOC.write_text(
        "# VV2 Individual Full Mastery Candidate\n\n"
        "This public, stock-only feature adds one `Upgrades` button to Villager Detail at the already-proved X=140/Y=563 placement. Detail event 8/button 6 is collision-guarded and routes only to `Grant Full Mastery to Selected Villager`. It depends on `vv2_full_mastery_all_stage_a_candidate`; it does not enable or reuse `vv2_enable_origins_exclusive_features`. Runtime/player confirmation remains pending.\n\n"
        "The overlay owns the stock Detail hooks at raw `0x67624` and `0x67720`, plus zero-preimage regions beginning at raw `0xB2200` in the prerequisite `.vv2fm` section. The prerequisite Tech hooks, command-7 body/range `0xB1000..0xB21FF`, companion DLL, Barrel code, and alignment are unchanged. Both stock modes are rendered and hash-pinned; Expanded-256 modes reject before output.\n\n"
        "The prerequisite's older frozen whole-image hashes (`08F123...` Collection and `21B927...` Immediate) differ from current HEAD's public parent renders (`1EF8F9...` and `A2F8F9...`) for one classified reason: commit `f9e5fd90bc998361b58c9c4849800dbd8cda6764` replaced the `automatic:safety` event-allocation cave at raw `0x73D00` (27 accepted bytes plus 20 zeros became 47 current bytes), which also changes the deterministic PE checksum at raw `0x148`. Replacing only that 47-byte range with the accepted payload/zero tail and recomputing the checksum exactly reproduces both frozen hashes. No parent-owned Tech hook, command-7, `.vv2fm`, or DLL byte accounts for the drift. Current parent installation and removal remain guarded: current public parent renders uninstall exactly to current stock-mode baselines, and this child uninstalls exactly to the current public parent in both modes.\n\n"
        "The selected index is `[state+0x304F0]` with unsigned bound 256. `[detail+0x10]` must exactly equal the freshly acquired manager's record pool at `manager+0x52C`; the derived record pointer, Detail owner, state, index, pool, and manager must all remain identical through confirmation and every transaction boundary. Eligibility is active `+0x30 != 0`, signed health `+0x52C > 0`, and non-totem `+0x558 == 0`, always checked before skill reads. The exact current active/health/totem/five-skill/job snapshot and funds value are revalidated before any write. No immutable per-record villager identifier has been proved for this build, so identity is deliberately defined by that exact source-bound pointer/index/snapshot chain.\n\n"
        "All five skills target exactly 100 through changed-only calls to native `sub_445430`. Complete exact-100 postverification precedes one call to native evaluator `sub_44D4C0`, which is semantically required for stock Elder/totem effects. A fresh final identity/account acquisition, exact-100 verification, and unsigned funds check precede one native `sub_426290` deduction of 100,000. Already mastered, invalid, insufficient, canceled, or pre-write race paths make no changes and charge nothing. Native changes are not rolled back after a post-write failure; those paths report that native skill changes may remain and do not charge.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
