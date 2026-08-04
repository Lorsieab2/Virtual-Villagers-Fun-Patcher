"""Build the VV3 Full Heal/Cure All candidate metadata.

The candidate is deliberately separate from the withdrawn command-6 payload and
from the selected-villager Running slot.  It is emitted as a source-owned
manifest/map pair for the certified stock modes after independent static GO;
runtime/player validation remains pending.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Secret City.exe"
BASE_MANIFEST = ROOT / "data" / "candidates" / "vv3_individual_grant_running_candidate.json"
OUT_DIR = ROOT / "data" / "candidates"
MANIFEST_OUT = OUT_DIR / "vv3_full_heal_cure_all_candidate.json"
MAP_OUT = OUT_DIR / "vv3_full_heal_cure_all_candidate_map.json"
DOC_OUT = ROOT / "docs" / "vv3-full-heal-candidate.md"

# The runtime image is the already-certified Origins + Full Mastery + individual
# Running composition.  The new hook is applied after those features.
HOOK_OFFSET = 0xA35EF
HOOK_VA = 0x4A35EF
HOOK_BEFORE = bytes.fromhex("8B049D543F4A00")
HOOK_AFTER = bytes.fromhex("E90CCA23009090")
# The legacy Cure cave is deliberately left untouched.  The revised candidate
# owns a separately guarded RX page appended after the certified parent chain.
OLD_CAVE_OFFSET = 0x7B721
OLD_CAVE_LENGTH = 0x700
APPEND_OFFSET = 0xCC000
SECTION_RVA = 0x2E0000
SECTION_VA = 0x6E0000
SECTION_HEADER_OFFSET = 0x2F0
SECTION_PAGE_SIZE = 0x1000
CAVE_OFFSET = APPEND_OFFSET
CAVE_VA = SECTION_VA
CAVE_LENGTH = SECTION_PAGE_SIZE
# Keep code and strings disjoint inside the dedicated page.
STRING_OFFSET = 0x800
LEGACY_CURE_START = 0x7B664
LEGACY_CURE_END = 0x7B721
NON5_CONTINUATION = 0x4A35F6
RESULT_HELPER = 0x4A3400
DETAIL_LOOP = 0x4A34C6
MANAGER_GETTER = 0x428B60
HEALTH_SETTER = 0x462670
TECH_DEDUCTION = 0x427130
MESSAGEBOX_IAT = 0x47C124
GETPROC_IAT = 0x47C128
MANAGER_SINGLETON = 0x59E110
TECH_BALANCE = 0x582644
POOL_COUNT = 150
POOL_STRIDE = 0x1F8C
ACTIVE_OFFSET = 0xF10
HEALTH_OFFSET = 0xE78
FULL_RECORD_HEALTH_ARG = 0xE6C
SICK_OFFSET = 0xE89
PE_CHECKSUM_OFFSET = 0x160
PRICE = 30_000
STOCK_SHA256 = "8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503"
# Authenticated package-base accounting.  Packaging records these values in
# the patch/transparency log without changing the candidate executable.
PACKAGE_SOURCE_ZIP_SHA256 = "B616282E0C21A9A8D509CE64C129EF6F24B4F50EAC538632DFBBC8C374662048"
PACKAGE_SOURCE_ZIP_ENTRIES = 419
PACKAGE_SOURCE_RUNTIME_MEMBERS = 417
PACKAGE_SOURCE_OUTER_EVIDENCE_FILES = 2
PACKAGE_SOURCE_RETAINED_STOCK_FILES = 412
PACKAGE_SOURCE_PAYLOAD_RECORDS = 417
PACKAGE_CURRENT_FILE_COUNT = 7
PARTIAL_FAILURE_DISCLOSURE = (
    "If native writes begin and a later write or postverification fails, earlier "
    "verified health, sickness, or People Cured effects may remain. No tech points "
    "are deducted on that failure, but complete rollback of native side effects is "
    "not claimed."
)
COMPOSED_PARENT_HELPER_SHA256 = "CFF1AAA9111728F003621FF662F100940C2F978943F5E69CC64180EA5DE63F7D"
STOCK_CURE_CAVE_PREIMAGE_SHA256 = "7B4FC1A8DBE6B6121F16ADA516E2AC27E02964716BACEA5FB7D07CF30595948E"
LEGACY_PRESERVED_RANGE_SHA256 = COMPOSED_PARENT_HELPER_SHA256
STOCK_ZERO_PREIMAGE_LEGACY_RANGE_SHA256 = "06EA118EDADD836A02B202C05BC7E47356B57E28C01EDF1DAD6CC4CF90C662E2"
SOURCE_COMMIT = "64c1266503c49ba1456f6294683a1f6773eba5d6"
IMPLEMENTATION_PARENT_COMMIT = "38510cc21b7cd322a52fbabc936794dfc8601ccc"
IMPLEMENTATION_COMMIT = "49595a75b65cd0561811593ba19825239ec97dde"
IMPLEMENTATION_STATUS = "enabled/catalog-visible for certified stock modes; D209/C213 independent static GO; runtime/player validation pending"
PROVENANCE = {
    "design_source_commit": SOURCE_COMMIT,
    "implementation_parent_commit": IMPLEMENTATION_PARENT_COMMIT,
    "implementation_commit": IMPLEMENTATION_COMMIT,
    "metadata_commit": None,
    "audit_source_test_commit": "e2f1a466b61392d161a0df2fbf8da94fc05ee4ca",
    "metadata_status": "enabled/catalog-visible for certified stock modes; D209/C213 independent static GO; runtime/player validation pending",
}
RENDERED_SHA256 = {
    "collection_progression": "B095FAFCC53B66B8FE7C852DAF488B8921EA4FBD3247FD293E1BBDCA369BF173",
    "immediate_fixed": "CFE508B213C566E8A81302556946AAA500F701B25E8F0BE620D3C6A8844C2B61",
}
STATIC_ACCEPTANCE = {
    "commit": None,
    "status": "D209 and C213 independent static GO; runtime/player validation pending",
    "reports": ["D209", "C213"],
    "audit_commit": None,
    "acceptance_commit": None,
}

BASE_DLL_PATH = OUT_DIR / "VVFP VV3 Full Mastery Candidate.dll"
FULL_HEAL_DLL_PATH = OUT_DIR / "VVFP VV3 Full Heal Candidate.dll"
BASE_DLL_SHA256 = "35FB96199E745C7D8054FF6A12851B9E09225E3E41D0CE04012604E74968C0D5"
FULL_HEAL_DLL_SHA256 = "A1C58D5DD34252C532C288F87210363FE4C85E355E76946276954F907FAA88FC"
FULL_HEAL_DLL_SIZE = 298496

sys.path.insert(0, str(ROOT / ".tools" / "keystone-runtime"))
from keystone import KS_ARCH_X86, KS_MODE_32, Ks  # noqa: E402
sys.path.insert(0, str(ROOT / ".tools" / "capstone"))
from capstone import CS_ARCH_X86, CS_MODE_32, CS_GRP_CALL, CS_GRP_JUMP, Cs  # noqa: E402
from capstone.x86_const import X86_OP_IMM  # noqa: E402


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def build_resource_only_companion(base: bytes) -> bytes:
    """Derive the Full Heal companion from the certified Full Mastery DLL.

    The transformation is deliberately length-preserving: only the two exact
    RT_DIALOG leaf label strings are replaced, consuming the documented four
    zero padding bytes that follow each stock string.  PE headers, section
    tables, every non-.rsrc byte, every other resource leaf, and all exports
    therefore remain byte-identical.
    """
    if len(base) != FULL_HEAL_DLL_SIZE or sha(base) != BASE_DLL_SHA256:
        raise RuntimeError("VV3 Full Heal companion base DLL fingerprint mismatch")
    old = "Cure all Villagers".encode("utf-16le") + b"\0\0"
    new = "Full Heal / Cure All".encode("utf-16le") + b"\0\0"
    if len(new) != len(old) + 4 or base.count(old) != 2:
        raise RuntimeError("VV3 Full Heal companion resource preimage is not exact")
    result = bytearray(base)
    cursor = 0
    positions: list[int] = []
    while True:
        position = base.find(old, cursor)
        if position < 0:
            break
        # The four bytes immediately following the stock NUL are required
        # padding; no resource directory or leaf-size rewrite is permitted.
        if base[position + len(old) : position + len(new)] != b"\0" * 4:
            raise RuntimeError("VV3 Full Heal resource label lacks certified padding")
        result[position : position + len(new)] = new
        positions.append(position)
        cursor = position + len(old)
    if positions != [0x46C60, 0x47A78]:
        raise RuntimeError(f"VV3 Full Heal resource leaf offsets changed: {positions!r}")
    transformed = bytes(result)
    if sha(transformed) != FULL_HEAL_DLL_SHA256:
        raise RuntimeError("VV3 Full Heal companion transformation hash mismatch")
    return transformed


def assemble(source: str, address: int) -> bytes:
    encoding, _ = Ks(KS_ARCH_X86, KS_MODE_32).asm(source, address)
    return bytes(encoding)


def rel32(source_va: int, target_va: int) -> bytes:
    return b"\xE9" + int(target_va - source_va - 5).to_bytes(4, "little", signed=True)


def _strings() -> tuple[dict[str, int], bytes]:
    values = (
        ("user32", "USER32.dll"),
        ("messagebox", "MessageBoxA"),
        ("wsprintf", "wsprintfA"),
        ("caption", "Origins Upgrades"),
        ("confirm_format", "Full Heal / Cure All will clear sickness from %u eligible villagers and restore %u partial-health villagers for 30,000 tech points?\r\nPress OK to confirm, or Cancel."),
        ("no_change", "All eligible villagers are already healthy and free of sickness.\r\nNo tech points have been deducted."),
        ("invalid", "No valid living non-skeleton villagers are available.\r\nNo tech points have been deducted."),
        ("insufficient", "Not enough tech points before confirmation.\r\nNo tech points have been deducted."),
        ("initial_insufficient", "Not enough tech points after confirmation recheck.\r\nNo tech points have been deducted."),
        ("canceled", "Cure All was canceled.\r\nNo tech points have been deducted."),
        ("changed", "Villager state changed during confirmation.\r\nNo tech points have been deducted."),
        ("write_failure_format", "Full Heal / Cure All failed after %u sickness clears and %u full-health restores were verified.\r\nNo tech points have been deducted.\r\n" + PARTIAL_FAILURE_DISCLOSURE),
        ("success_format", "Full Heal / Cure All completed: %u sickness clears and %u full-health restores were verified."),
        ("dependency", "Cure dependencies are unavailable.\r\nNo tech points have been deducted."),
    )
    blob = bytearray()
    labels: dict[str, int] = {}
    for name, text in values:
        labels[name] = CAVE_VA + STRING_OFFSET + len(blob)
        blob.extend(text.encode("ascii") + b"\0")
    return labels, bytes(blob)


def _helper(strings: dict[str, int]) -> bytes:
    # Stack contract: saved EBX/ESI/EDI are -4/-8/-C, MessageBoxA -10,
    # wsprintfA -14, manager -18, pool -1C, predicted A/B -20/-24,
    # verified A/B -28/-2C, eligible/mutation locals -30/-34, and 150
    # pairs of health/sickness snapshots occupy -4E0..-31.  A dedicated
    # 512-byte format buffer occupies -6E0..-4E1.  No +0xE94 or unrelated
    # status field is read.
    source = f"""
        cmp ebx, 5
        jne non_five
        push ebp
        mov ebp, esp
        push ebx
        push esi
        push edi
        sub esp, 0x6D4
        push {strings['user32']:#x}
        call dword ptr [{MESSAGEBOX_IAT:#x}]
        test eax, eax
        je dependency_failure
        push {strings['messagebox']:#x}
        push eax
        call dword ptr [{GETPROC_IAT:#x}]
        test eax, eax
        je dependency_failure
        mov dword ptr [ebp-0x10], eax
        push {strings['wsprintf']:#x}
        push dword ptr [ebp-0x10]
        call dword ptr [{GETPROC_IAT:#x}]
        test eax, eax
        je dependency_failure
        mov dword ptr [ebp-0x14], eax
        call {MANAGER_GETTER:#x}
        test eax, eax
        je invalid_failure
        mov dword ptr [ebp-0x18], eax
        push 0
        mov ecx, {MANAGER_SINGLETON:#x}
        call 0x45C840
        test eax, eax
        je invalid_failure
        mov dword ptr [ebp-0x1C], eax
        mov dword ptr [ebp-0x20], 0
        mov dword ptr [ebp-0x24], 0
        mov dword ptr [ebp-0x20], 0
        mov dword ptr [ebp-0x28], 0
        mov dword ptr [ebp-0x2C], 0
        mov dword ptr [ebp-0x30], 0
        lea edi, [ebp-0x4E0]
        xor eax, eax
        mov ecx, 300
        rep stosd
        mov edi, dword ptr [ebp-0x1C]
        xor esi, esi
        mov ecx, {POOL_COUNT}
    initial_scan:
        cmp byte ptr [edi+{ACTIVE_OFFSET:#x}], 0
        je initial_next
        cmp dword ptr [edi+{HEALTH_OFFSET:#x}], 0
        jle initial_next
        inc dword ptr [ebp-0x30]
        mov eax, dword ptr [edi+{HEALTH_OFFSET:#x}]
        lea edx, [ebp-0x4E0]
        mov dword ptr [edx+esi*8], eax
        movzx eax, byte ptr [edi+{SICK_OFFSET:#x}]
        mov dword ptr [edx+esi*8+4], eax
        test eax, eax
        je initial_partial
        inc dword ptr [ebp-0x20]
    initial_partial:
        cmp dword ptr [edx+esi*8], 1
        jl initial_next
        cmp dword ptr [edx+esi*8], 99
        jg initial_next
        inc dword ptr [ebp-0x24]
    initial_next:
        inc esi
        add edi, {POOL_STRIDE:#x}
        dec ecx
        jnz initial_scan
        cmp dword ptr [ebp-0x30], 0
        je invalid_failure
        cmp dword ptr [ebp-0x20], 0
        jne have_changes
        cmp dword ptr [ebp-0x24], 0
        je no_change
    have_changes:
        cmp dword ptr [{TECH_BALANCE:#x}], {PRICE}
        jb insufficient
        lea eax, [ebp-0x6E0]
        push dword ptr [ebp-0x24]
        push dword ptr [ebp-0x20]
        push {strings['confirm_format']:#x}
        push eax
        call dword ptr [ebp-0x14]
        add esp, 0x10
        lea eax, [ebp-0x6E0]
        push 1
        push {strings['caption']:#x}
        push eax
        push 0
        call dword ptr [ebp-0x10]
        cmp eax, 1
        jne canceled
        call {MANAGER_GETTER:#x}
        test eax, eax
        je changed_state
        mov dword ptr [ebp-0x18], eax
        push 0
        mov ecx, {MANAGER_SINGLETON:#x}
        call 0x45C840
        test eax, eax
        je changed_state
        mov dword ptr [ebp-0x1C], eax
        mov edi, dword ptr [ebp-0x1C]
        xor esi, esi
        mov ecx, {POOL_COUNT}
    recheck_scan:
        lea edx, [ebp-0x4E0]
        cmp byte ptr [edi+{ACTIVE_OFFSET:#x}], 0
        je recheck_ineligible
        cmp dword ptr [edi+{HEALTH_OFFSET:#x}], 0
        jle recheck_ineligible
        cmp dword ptr [edx+esi*8], 0
        je changed_state
        mov eax, dword ptr [edi+{HEALTH_OFFSET:#x}]
        cmp eax, dword ptr [edx+esi*8]
        jne changed_state
        movzx eax, byte ptr [edi+{SICK_OFFSET:#x}]
        cmp eax, dword ptr [edx+esi*8+4]
        jne changed_state
        jmp recheck_next
    recheck_ineligible:
        cmp dword ptr [edx+esi*8], 0
        jne changed_state
    recheck_next:
        inc esi
        add edi, {POOL_STRIDE:#x}
        dec ecx
        jnz recheck_scan
        # After the complete fresh state recheck and immediately before the
        # first possible native write, re-read funds.  Failure here is a
        # distinct no-charge route and cannot occur after mutation begins.
        cmp dword ptr [{TECH_BALANCE:#x}], {PRICE}
        jb initial_insufficient
        mov dword ptr [ebp-0x28], 0
        mov dword ptr [ebp-0x2C], 0
        mov edi, dword ptr [ebp-0x1C]
        xor esi, esi
        mov dword ptr [ebp-0x30], {POOL_COUNT}
    mutation_scan:
        lea edx, [ebp-0x4E0]
        cmp dword ptr [edx+esi*8], 0
        je mutation_next
        # Only snapshotted partial-health records may be health-written.  A
        # snapshot at 100 or above is preserved byte-for-byte and never reaches
        # the native setter; sickness clearing remains independently eligible.
        cmp dword ptr [edx+esi*8], 1
        jl mutation_next
        cmp dword ptr [edx+esi*8], 99
        jg health_done
        cmp dword ptr [edi+{HEALTH_OFFSET:#x}], 100
        je health_done
        lea eax, [edi+{FULL_RECORD_HEALTH_ARG:#x}]
        mov ecx, eax
        push -1
        push 100
        call {HEALTH_SETTER:#x}
        cmp dword ptr [edi+{HEALTH_OFFSET:#x}], 100
        jne write_failure
        inc dword ptr [ebp-0x2C]
        health_done:
            cmp byte ptr [edi+{SICK_OFFSET:#x}], 0
            je mutation_next
        # Acquire the fresh manager before touching sickness.  The mutation
        # loop counter lives in a disjoint local because both this getter and
        # the native setter are allowed to consume ECX.  A null manager
        # therefore causes no sickness write.
        call {MANAGER_GETTER:#x}
        test eax, eax
        je write_failure
        mov byte ptr [edi+{SICK_OFFSET:#x}], 0
        cmp byte ptr [edi+{SICK_OFFSET:#x}], 0
        jne write_failure
        inc dword ptr [eax+0x4FC]
        inc dword ptr [ebp-0x28]
    mutation_next:
        inc esi
        add edi, {POOL_STRIDE:#x}
        dec dword ptr [ebp-0x30]
        jnz mutation_scan
        call {MANAGER_GETTER:#x}
        test eax, eax
        je write_failure
        mov dword ptr [ebp-0x18], eax
        push 0
        mov ecx, {MANAGER_SINGLETON:#x}
        call 0x45C840
        test eax, eax
        je write_failure
        mov dword ptr [ebp-0x1C], eax
    postverify:
        mov edi, dword ptr [ebp-0x1C]
        xor esi, esi
        mov ecx, {POOL_COUNT}
    postverify_scan:
        lea edx, [ebp-0x4E0]
        cmp dword ptr [edx+esi*8], 0
        je postverify_next
        cmp byte ptr [edi+{ACTIVE_OFFSET:#x}], 0
        je write_failure
        cmp dword ptr [edi+{HEALTH_OFFSET:#x}], 0
        jle write_failure
        cmp dword ptr [edx+esi*8], 1
        jl postverify_next
        cmp dword ptr [edx+esi*8], 99
        jg postverify_preserved
        cmp dword ptr [edi+{HEALTH_OFFSET:#x}], 100
        jne write_failure
        jmp postverify_sick
    postverify_preserved:
        mov eax, dword ptr [edi+{HEALTH_OFFSET:#x}]
        cmp eax, dword ptr [edx+esi*8]
        jne write_failure
    postverify_sick:
        cmp byte ptr [edi+{SICK_OFFSET:#x}], 0
        jne write_failure
    postverify_next:
        inc esi
        add edi, {POOL_STRIDE:#x}
        dec ecx
        jnz postverify_scan
        call {MANAGER_GETTER:#x}
        test eax, eax
        je write_failure
        mov dword ptr [ebp-0x18], eax
        mov eax, dword ptr [ebp-0x28]
        cmp eax, dword ptr [ebp-0x20]
        jne write_failure
        mov eax, dword ptr [ebp-0x2C]
        cmp eax, dword ptr [ebp-0x24]
        jne write_failure
        cmp dword ptr [{TECH_BALANCE:#x}], {PRICE}
        jb write_failure
        mov ecx, {TECH_BALANCE:#x}
        push -{PRICE}
        call {TECH_DEDUCTION:#x}
        lea eax, [ebp-0x6E0]
        push dword ptr [ebp-0x2C]
        push dword ptr [ebp-0x28]
        push {strings['success_format']:#x}
        push eax
        call dword ptr [ebp-0x14]
        add esp, 0x10
        lea eax, [ebp-0x6E0]
        push eax
        push {strings['caption']:#x}
        call {RESULT_HELPER:#x}
        jmp finish
    non_five:
        mov eax, dword ptr [ebx*4+0x4A3F54]
        jmp {NON5_CONTINUATION:#x}
    dependency_failure:
        push {strings['dependency']:#x}
        jmp show_no_charge
    invalid_failure:
        push {strings['invalid']:#x}
        jmp show_no_charge
    no_change:
        push {strings['no_change']:#x}
        jmp show_no_charge
    insufficient:
        push {strings['insufficient']:#x}
        jmp show_no_charge
    initial_insufficient:
        push {strings['initial_insufficient']:#x}
        jmp show_no_charge
    canceled:
        push {strings['canceled']:#x}
        jmp show_no_charge
    changed_state:
        push {strings['changed']:#x}
        jmp show_no_charge
    write_failure:
    counted_failure:
        lea eax, [ebp-0x6E0]
        push dword ptr [ebp-0x2C]
        push dword ptr [ebp-0x28]
        push {strings['write_failure_format']:#x}
        push eax
        call dword ptr [ebp-0x14]
        add esp, 0x10
        lea eax, [ebp-0x6E0]
        push eax
        push {strings['caption']:#x}
        call {RESULT_HELPER:#x}
        jmp finish
    show_no_charge:
        push {strings['caption']:#x}
        call {RESULT_HELPER:#x}
    finish:
        lea esp, [ebp-0x0C]
        pop edi
        pop esi
        pop ebx
        pop ebp
        jmp {DETAIL_LOOP:#x}
    """
    return assemble(source, CAVE_VA)


def _verify_helper_targets(helper: bytes) -> dict[str, object]:
    """Disassemble the assembled helper and reject code/string control-flow overlap."""

    if len(helper) >= STRING_OFFSET:
        raise RuntimeError(
            f"VV3 Cure helper overlaps strings: helper={len(helper):#x}, strings={STRING_OFFSET:#x}"
        )
    disassembler = Cs(CS_ARCH_X86, CS_MODE_32)
    disassembler.detail = True
    instructions = list(disassembler.disasm(helper, CAVE_VA))
    if not instructions or sum(item.size for item in instructions) != len(helper):
        raise RuntimeError("VV3 Cure helper did not disassemble completely.")
    starts = {item.address for item in instructions}
    internal_targets: set[int] = set()
    string_start = CAVE_VA + STRING_OFFSET
    cave_end = CAVE_VA + CAVE_LENGTH
    for item in instructions:
        if item.address + item.size > string_start:
            raise RuntimeError("VV3 Cure helper instruction crosses into strings.")
        if not (item.group(CS_GRP_JUMP) or item.group(CS_GRP_CALL)):
            continue
        if not item.operands or item.operands[0].type != X86_OP_IMM:
            continue
        target = item.operands[0].imm
        if CAVE_VA <= target < cave_end:
            if target >= string_start:
                raise RuntimeError("VV3 Cure branch/call targets strings or tail.")
            if target not in starts:
                raise RuntimeError(
                    f"VV3 Cure branch/call target is not an instruction boundary: {target:#x}"
                )
            internal_targets.add(target - CAVE_VA)
    epilogue = helper.rfind(b"\x8D\x65\xF4")
    if epilogue < 0 or epilogue >= STRING_OFFSET:
        raise RuntimeError("VV3 Cure epilogue is missing or outside the code range.")
    return {
        "instruction_count": len(instructions),
        "internal_target_offsets": [f"0x{offset:X}" for offset in sorted(internal_targets)],
        "epilogue_offset": f"0x{epilogue:X}",
    }


def build_region() -> tuple[bytes, dict[str, object]]:
    strings, blob = _strings()
    helper = _helper(strings)
    control_flow = _verify_helper_targets(helper)
    if len(helper) > STRING_OFFSET or STRING_OFFSET + len(blob) > CAVE_LENGTH:
        raise RuntimeError(f"VV3 Cure helper exceeds bounded cave: {len(helper):#x}")
    region = bytearray(CAVE_LENGTH)
    region[: len(helper)] = helper
    region[STRING_OFFSET : STRING_OFFSET + len(blob)] = blob
    if sha(bytes(region[: len(helper)])) != sha(helper):
        raise RuntimeError("VV3 Cure helper slice hash differs after layout.")
    return bytes(region), {
        "helper_length": len(helper),
        "helper_sha256": sha(helper),
        "strings_offset": f"0x{STRING_OFFSET:X}",
        "strings_length": len(blob),
        "strings_sha256": sha(blob),
        "region_sha256": sha(region),
        "used_length": STRING_OFFSET + len(blob),
        "tail_zero_length": CAVE_LENGTH - (STRING_OFFSET + len(blob)),
        **control_flow,
    }


def section_header() -> bytes:
    return (
        b".vv3hc\0\0"
        + SECTION_PAGE_SIZE.to_bytes(4, "little")
        + SECTION_RVA.to_bytes(4, "little")
        + SECTION_PAGE_SIZE.to_bytes(4, "little")
        + APPEND_OFFSET.to_bytes(4, "little")
        + b"\0" * 12
        + (0x60000020).to_bytes(4, "little")
    )


def append_layout(region: bytes) -> dict[str, object]:
    if len(region) != SECTION_PAGE_SIZE:
        raise RuntimeError("VV3 Full Heal .vv3hc page must be exactly 0x1000 bytes.")
    return {
        "original_file_size": f"0x{APPEND_OFFSET:X}",
        "append_offset": f"0x{APPEND_OFFSET:X}",
        "append_length": SECTION_PAGE_SIZE,
        "append_bytes": region.hex().upper(),
        "virtual_address": f"0x{SECTION_VA:X}",
        "section_name": ".vv3hc",
        "section_rva": f"0x{SECTION_RVA:X}",
        "section_characteristics": "0x60000020",
        "purpose": "append the guarded VV3 Full Heal / Cure All .vv3hc RX page",
        "header_patches": [
            {"offset": "0x10E", "before": "0600", "after": "0700", "purpose": "add the candidate .vv3hc section"},
            {"offset": "0x158", "before": "00002E00", "after": "00102E00", "purpose": "extend SizeOfImage for .vv3hc"},
            {"offset": f"0x{SECTION_HEADER_OFFSET:X}", "before": "00" * 40, "after": section_header().hex().upper(), "purpose": "install the guarded .vv3hc RX section header"},
        ],
    }


def main() -> None:
    stock = STOCK.read_bytes()
    if sha(stock) != STOCK_SHA256:
        raise RuntimeError("VV3 stock fingerprint mismatch")
    if HOOK_AFTER != rel32(HOOK_VA, SECTION_VA) + b"\x90\x90":
        raise RuntimeError("VV3 Cure hook rel32 mismatch")
    region, layout = build_region()
    if any(stock[OLD_CAVE_OFFSET : OLD_CAVE_OFFSET + OLD_CAVE_LENGTH]):
        raise RuntimeError("VV3 legacy Cure cave is not zero in stock preimage")
    append = append_layout(region)
    transformed_dll = build_resource_only_companion(BASE_DLL_PATH.read_bytes())
    FULL_HEAL_DLL_PATH.write_bytes(transformed_dll)
    base = json.loads(BASE_MANIFEST.read_text(encoding="utf-8"))
    manifest = {
        "id": "vv3_full_heal_cure_all_candidate",
        "game_id": "vv3",
        "name": "Full Heal / Cure All",
        "enabled": True,
        "catalog_hidden": False,
        "catalog_enabled": True,
        "audit_commit": None,
        "acceptance_commit": None,
        "dependencies": ["vv3_individual_grant_running_candidate"],
        "supported_modes": ["collection_progression", "immediate_fixed"],
        "unsupported_patch_modes": ["experimental_expanded_256", "experimental_expanded_256_progression"],
        "provenance": PROVENANCE,
        "static_acceptance": STATIC_ACCEPTANCE,
        "implementation_status": IMPLEMENTATION_STATUS,
        "runtime_player_status": "pending",
        "description": "Enabled/catalog-visible VV3 Full Heal / Cure All command-5 Buy candidate for certified Collection Progression and Immediate Fixed compositions after Origins + Full Mastery + individual Grant Running; static evidence is GO from D209/C213 and runtime/player validation remains pending.",
        "behavior_changes": [
            "Command 5 performs the certified Full Heal / Cure All transaction at 30,000 tech points.",
        ],
        "explicit_non_changes": [
            "Expanded-256 and unknown builds remain fail-closed; the withdrawn village-wide Running route is absent.",
            "The candidate is stock-mode only and does not add Remove or ownership behavior.",
        ],
        "evidence_status": "implementation generated at 49595a75b65cd0561811593ba19825239ec97dde; source/test state audited at e2f1a466b61392d161a0df2fbf8da94fc05ee4ca; independent static GO reports D209/C213; runtime/player validation pending",
        "price": PRICE,
        "transaction": {"command": 5, "price": PRICE, "action": "Buy", "repeatable": True, "ownership": None, "remove": False},
        "base_chain": {
            "stock_sha256": STOCK_SHA256,
            "collection_pre_cure_sha256": "3644A56FE17F843DB67662E4309C3C2B41AE7ADD5FDD60EF2B6789DE2BA15FDC",
            "immediate_pre_cure_sha256": "059230146E8CC36E06E5473AE187D081E337DB90638B227FBA799B9C82B58C1C",
            "full_mastery_page_sha256": "2DAE85AE4077C23C2C7C39F64B5BA944740F765AC8E24FBB097B0BF28A720DF6",
            "running_region_sha256": "76339C8FFBE0FF92F3F1EB2CC27A4E0600E33DCC936716DA94BBB0BD5D1AB050",
            "running_composed_parent_helper_sha256": COMPOSED_PARENT_HELPER_SHA256,
            "stock_cure_cave_preimage_sha256": STOCK_CURE_CAVE_PREIMAGE_SHA256,
            "stock_zero_preimage_legacy_range_sha256": STOCK_ZERO_PREIMAGE_LEGACY_RANGE_SHA256,
            "full_mastery_running_dependency": "vv3_individual_grant_running_candidate",
            "composition": "Origins + Full Mastery + individual Grant Running",
        },
        "companion_files": [
            {
                "source": "data/candidates/VVFP VV3 Full Heal Candidate.dll",
                "destination": "VVFP VV3 Full Mastery Candidate.dll",
                "size": FULL_HEAL_DLL_SIZE,
                "sha256": FULL_HEAL_DLL_SHA256,
                "preimage_sha256": BASE_DLL_SHA256,
                "restore_source": "data/candidates/VVFP VV3 Full Mastery Candidate.dll",
                "restore_sha256": BASE_DLL_SHA256,
                "resource_only": True,
            }
        ],
        "eligibility": {
            "proved_predicate": "D182: signed health +0xE78 > 0 after active +0xF10 != 0",
            "active_offset": "0xF10",
            "active_width": "byte",
            "health_offset": "0xE78",
            "non_skeleton": "D182 current active/living predicate; no +0xE94/status filter",
            "record_count": POOL_COUNT,
            "stride": f"0x{POOL_STRIDE:X}",
        },
        "health_setter": {"function": "0x462670", "ecx": "full_record+0xE6C", "push_reason": -1, "push_desired": 100, "forbidden": "full_record+0xA0"},
        "sickness": {
            "offset": "0xE89",
            "clear_value": 0,
            "people_cured_offset": "0x4FC",
            "increment_per_verified_sick_record": True,
            "health_only_does_not_increment": True,
            "manager_acquired_before_clear": True,
            "loop_counter_preserved_across_manager_getter": True,
            "mutation_loop_counter_local": "[ebp-0x30]",
            "mutation_loop_counter_bound": POOL_COUNT,
            "manager_null_means_no_sickness_write": True,
            "predicted_count_a": "sickness != 0",
            "predicted_count_b": "health >= 1 && health <= 99",
            "verified_count_a": "verified sickness clears",
            "verified_count_b": "verified health restores",
            "overlap_counted_in_both": True,
            "health_write_snapshot_range": "1..99 only",
            "health_ge_100_preserved": True,
            "actual_counts_must_equal_predicted_before_deduction": True,
            "reason_routes": ["dependency", "initial_insufficient", "cancel", "recheck", "postwrite_partial"],
        },
        "record_zero_resolver": {
            "function": "0x45C840",
            "manager_ecx": "0x59E110",
            "index": 0,
            "initial_and_after_confirmation": True,
            "constant_pool_substitute": False,
        },
        "messagebox_resolution": {
            "load_library_iat": "0x47C124",
            "get_proc_address_iat": "0x47C128",
            "module": "USER32.dll",
            "procedure": "MessageBoxA",
            "formatter_procedure": "wsprintfA",
            "formatter_saved_local": "[ebp-0x14]",
            "format_buffer": "[ebp-0x6E0..ebp-0x4E1]",
            "format_buffer_size": 512,
            "saved_local": "[ebp-0x10]",
            "stdcall_stack_cleanup": "callee",
        },
        "result_helper": {"va": "0x4A3400", "ret": 8, "caller_stack_cleanup": False},
        "messages": {
            "label": "Full Heal / Cure All",
            "no_charge_suffix": "No tech points have been deducted.",
            "confirm_format": "Full Heal / Cure All will clear sickness from %u eligible villagers and restore %u partial-health villagers for 30,000 tech points?\r\nPress OK to confirm, or Cancel.",
            "success_format": "Full Heal / Cure All completed: %u sickness clears and %u full-health restores were verified.",
            "failure_format": "Full Heal / Cure All failed after %u sickness clears and %u full-health restores were verified.\r\nNo tech points have been deducted.\r\n" + PARTIAL_FAILURE_DISCLOSURE,
            "confirm_price": "30,000",
        },
        "partial_failure_limit": PARTIAL_FAILURE_DISCLOSURE,
        "rollback_disclosure": PARTIAL_FAILURE_DISCLOSURE,
        "forbidden_routes": {"legacy_cure_entry": "0x47B664", "legacy_text_helper": "0x40D8A0", "e94_status_filter": False},
        "patches": [
            {"offset": "0xA35EF", "before": HOOK_BEFORE.hex().upper(), "after": HOOK_AFTER.hex().upper(), "purpose": "command-5 dominance before legacy price lookup/precharge", "continuation_non5": "0x4A35F6"},
        ],
        "pe_append_transaction": {"owner": "vv3_full_heal_cure_all_candidate", "section_name": ".vv3hc", "append_length": SECTION_PAGE_SIZE, "layouts": {"collection_progression": append, "immediate_fixed": append}, "removal_policy": "restore exact parent headers, hook, and truncate only the owned .vv3hc page"},
        "legacy_cave_guard": {"raw_offset": f"0x{OLD_CAVE_OFFSET:X}", "length": OLD_CAVE_LENGTH, "before_sha256": sha(bytes(OLD_CAVE_LENGTH)), "must_remain_zero": True},
        "atomicity": {"install_remove": "hook and bounded cave are paired; exact composition, guard, cave, and uninstall preimages required", "expanded_fail_closed": True},
        "mutation_accounting": {
            "physical_ranges": [
                {"offset": "0xA35EF", "length": 7, "purpose": "command-5 hook"},
                {"offset": "0x10E", "length": 2, "purpose": "PE section-count update"},
                {"offset": "0x158", "length": 4, "purpose": "PE SizeOfImage update"},
                {"offset": "0x2F0", "length": 40, "purpose": "candidate-owned .vv3hc section header"},
                {"offset": "0xCC000", "length": SECTION_PAGE_SIZE, "purpose": "candidate-owned .vv3hc RX page"},
                {"offset": "0x160", "length": 4, "purpose": "PE checksum recomputation"},
            ],
            "feature_owned_ranges": ["0xA35EF..0xA35F5", "0x2F0..0x317", "0xCC000..0xCCFFF"],
            "physical_range_count": 6,
            "feature_owned_range_count": 3,
            "every_other_byte_identical": True,
            "rendered_sha256": RENDERED_SHA256,
            "uninstall_sha256": {
                "collection_progression": "3644A56FE17F843DB67662E4309C3C2B41AE7ADD5FDD60EF2B6789DE2BA15FDC",
                "immediate_fixed": "059230146E8CC36E06E5473AE187D081E337DB90638B227FBA799B9C82B58C1C",
            },
            "checksum_offset": "0x160",
            "checksum_transitions": {
                "collection_progression": {"before": "93790D00", "after": "F3260D00"},
                "immediate_fixed": {"before": "91BB0D00", "after": "F1680D00"},
            },
            "section_header": {"name": ".vv3hc", "raw_offset": "0x2F0", "raw_start": "0xCC000", "rva": "0x2E0000", "va": "0x6E0000", "size": "0x1000", "section_count_before": 6, "section_count_after": 7, "size_of_image_before": "0x2E0000", "size_of_image_after": "0x2E1000"},
        },
    }
    manifest["base_manifest_sha256"] = sha(BASE_MANIFEST.read_bytes())
    artifact_map = {
        "candidate_id": manifest["id"],
        "candidate_enabled": True,
        "catalog_hidden": False,
        "catalog_enabled": True,
        "audit_commit": None,
        "acceptance_commit": None,
        "provenance": PROVENANCE,
        "static_acceptance": STATIC_ACCEPTANCE,
        "implementation_status": IMPLEMENTATION_STATUS,
        "allowed_modes": manifest["supported_modes"],
        "expanded_fail_closed": True,
        "hook": {"raw_offset": "0xA35EF", "before": HOOK_BEFORE.hex().upper(), "after": HOOK_AFTER.hex().upper(), "sha256": sha(HOOK_AFTER)},
        "section": {"name": ".vv3hc", "raw_offset": f"0x{APPEND_OFFSET:X}", "virtual_address": f"0x{SECTION_VA:X}", "rva": f"0x{SECTION_RVA:X}", "length": SECTION_PAGE_SIZE, "before_sha256": sha(bytes(SECTION_PAGE_SIZE)), "after_sha256": sha(region), "layout": layout, "append": append},
        "legacy_cave": {"raw_offset": f"0x{OLD_CAVE_OFFSET:X}", "length": OLD_CAVE_LENGTH, "before_sha256": sha(bytes(OLD_CAVE_LENGTH)), "must_remain_zero": True},
        "composition": manifest["base_chain"],
        "companion_files": manifest["companion_files"],
        "eligibility": manifest["eligibility"],
        "transaction": manifest["transaction"],
        "result_helper": manifest["result_helper"],
        "health_setter": manifest["health_setter"],
        "sickness": manifest["sickness"],
        "record_zero_resolver": manifest["record_zero_resolver"],
        "messagebox_resolution": manifest["messagebox_resolution"],
        "messages": manifest["messages"],
        "partial_failure_limit": manifest["partial_failure_limit"],
        "rollback_disclosure": PARTIAL_FAILURE_DISCLOSURE,
        "mutation_accounting": manifest["mutation_accounting"],
        "forbidden_routes": manifest["forbidden_routes"],
        "legacy_preserved_range": {"raw_start": f"0x{LEGACY_CURE_START:X}", "raw_end": f"0x{LEGACY_CURE_END:X}", "sha256": LEGACY_PRESERVED_RANGE_SHA256},
        "stock_zero_preimage_legacy_range": {"raw_start": f"0x{LEGACY_CURE_START:X}", "raw_end": f"0x{LEGACY_CURE_END:X}", "sha256": STOCK_ZERO_PREIMAGE_LEGACY_RANGE_SHA256},
        "rendered": {mode: {"sha256": RENDERED_SHA256[mode], "runtime_player_status": "pending"} for mode in manifest["supported_modes"]},
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_OUT.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    MAP_OUT.write_text(json.dumps(artifact_map, indent=2) + "\n", encoding="utf-8")
    DOC_OUT.write_text(
        "# VV3 Full Heal / Cure All (enabled static candidate; runtime pending)\n\n"
        "This stock-only candidate is enabled and catalog-visible only for certified Collection Progression and Immediate Fixed. Its implementation is bound to commit `49595a75b65cd0561811593ba19825239ec97dde` with parent `38510cc21b7cd322a52fbabc936794dfc8601ccc`; independent static GO is recorded by D209/C213, while runtime/player validation remains pending. "
        "It composes only after the certified VV3 Origins + Full Mastery + individual Grant Running chain in "
        "Collection Progression or Immediate Fixed. Expanded-256 is rejected before output.\n\n"
        f"Provenance is non-circular: design/source lineage `{SOURCE_COMMIT}`, implementation parent `{IMPLEMENTATION_PARENT_COMMIT}`, current implementation `{IMPLEMENTATION_COMMIT}`, and metadata commit is intentionally null until a later audit. The legacy preserved range `0x{LEGACY_CURE_START:X}..0x{LEGACY_CURE_END:X}` is `{LEGACY_PRESERVED_RANGE_SHA256}` in both composed parents; the stock-zero preimage is separately `{STOCK_ZERO_PREIMAGE_LEGACY_RANGE_SHA256}`.\n\n"
        f"The command-5 detour is `{HOOK_BEFORE.hex().upper()}` -> `{HOOK_AFTER.hex().upper()}` at raw `0x{HOOK_OFFSET:X}`. The dedicated `.vv3hc` RX page is raw `0x{APPEND_OFFSET:X}` / VA `0x{SECTION_VA:X}` with a guarded header at `0x{SECTION_HEADER_OFFSET:X}`; the old Cure cave remains zero and legacy bytes `0x{LEGACY_CURE_START:X}..0x{LEGACY_CURE_END:X}` remain byte-identical.\n\n"
        f"The transaction scans exactly 150 records in physical order. Dry-run Count A is sick eligible villagers, Count B is eligible health 1..99 villagers, and overlap is counted in both. Confirmation formats both predicted counts and the 30,000 cost into a dedicated 512-byte buffer; success and failure format verified sickness clears and verified health restores. It resolves record zero through 0x45C840 with ECX=0x59E110 before the dry run and again after confirmation, resolves USER32.dll/MessageBoxA/wsprintfA before any dialog, uses native health setter 0x462670 with ECX=record+0xE6C and pushes -1/100, acquires a fresh manager before clearing sickness at +0xE89, and increments fresh manager People Cured +0x4FC only after each verified sick clear. It postverifies and deducts once through 0x427130. Every no-charge route ends with `No tech points have been deducted.` {PARTIAL_FAILURE_DISCLOSURE}\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
