"""Build the disabled VV3 Full Heal/Cure All candidate.

The candidate is deliberately separate from the withdrawn command-6 payload and
from the selected-villager Running slot.  It is emitted only as a source-owned
manifest/map pair; the public catalog remains unchanged until independent
recertification.
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
HOOK_AFTER = bytes.fromhex("E92D81FDFF9090")
CAVE_OFFSET = 0x7B721
CAVE_VA = 0x47B721
CAVE_LENGTH = 0x700
STRING_OFFSET = 0x300
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
SOURCE_COMMIT = "64c1266503c49ba1456f6294683a1f6773eba5d6"
IMPLEMENTATION_STATUS = "candidate implementation; D182 static predicate evidence incorporated; independent lifecycle recertification pending"
RENDERED_SHA256 = {
    "collection_progression": "FC145FDB6A5E448B0BB670D0C81E44EB8915DAB6D3EAA2E3F93334D5E6E3F9CB",
    "immediate_fixed": "69213F2C3CB2E30B385E008D26E0CFB7F381B6F09016A6DDC51F8BCE61F5183A",
}

sys.path.insert(0, str(ROOT / ".tools" / "keystone-runtime"))
from keystone import KS_ARCH_X86, KS_MODE_32, Ks  # noqa: E402


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def assemble(source: str, address: int) -> bytes:
    encoding, _ = Ks(KS_ARCH_X86, KS_MODE_32).asm(source, address)
    return bytes(encoding)


def rel32(source_va: int, target_va: int) -> bytes:
    return b"\xE9" + int(target_va - source_va - 5).to_bytes(4, "little", signed=True)


def _strings() -> tuple[dict[str, int], bytes]:
    values = (
        ("user32", "USER32.dll"),
        ("messagebox", "MessageBoxA"),
        ("caption", "Origins Upgrades"),
        ("confirm", "Cure all eligible villagers for 30,000 tech points?\r\nPress OK to confirm, or Cancel."),
        ("no_change", "All eligible villagers are already healthy and free of sickness.\r\nNo tech points have been deducted."),
        ("invalid", "No valid living non-skeleton villagers are available.\r\nNo tech points have been deducted."),
        ("insufficient", "Not enough tech points.\r\nNo tech points have been deducted."),
        ("canceled", "Cure All was canceled.\r\nNo tech points have been deducted."),
        ("changed", "Villager state changed during confirmation.\r\nNo tech points have been deducted."),
        ("write_failure", "Cure verification failed; some native changes may already have occurred.\r\nNo tech points have been deducted."),
        ("success", "Full Heal was granted to all eligible villagers."),
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
    # manager -14, pool -18, initial changed/sick counts -1C/-20,
    # recheck count -24, and 150 pairs of health/sickness snapshots occupy
    # -4E0..-31.  No +0xE94 or unrelated status field is read.
    source = f"""
        cmp ebx, 5
        jne non_five
        push ebp
        mov ebp, esp
        push ebx
        push esi
        push edi
        sub esp, 0x4D4
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
        call {MANAGER_GETTER:#x}
        test eax, eax
        je invalid_failure
        mov dword ptr [ebp-0x14], eax
        push 0
        mov ecx, {MANAGER_SINGLETON:#x}
        call 0x45C840
        test eax, eax
        je invalid_failure
        mov dword ptr [ebp-0x18], eax
        mov dword ptr [ebp-0x1C], 0
        mov dword ptr [ebp-0x20], 0
        mov dword ptr [ebp-0x24], 0
        lea edi, [ebp-0x4E0]
        xor eax, eax
        mov ecx, 300
        rep stosd
        mov edi, dword ptr [ebp-0x18]
        xor esi, esi
        mov ecx, {POOL_COUNT}
    initial_scan:
        cmp byte ptr [edi+{ACTIVE_OFFSET:#x}], 0
        je initial_next
        cmp dword ptr [edi+{HEALTH_OFFSET:#x}], 0
        jle initial_next
        inc dword ptr [ebp-0x24]
        mov eax, dword ptr [edi+{HEALTH_OFFSET:#x}]
        lea edx, [ebp-0x4E0]
        mov dword ptr [edx+esi*8], eax
        movzx eax, byte ptr [edi+{SICK_OFFSET:#x}]
        mov dword ptr [edx+esi*8+4], eax
        cmp dword ptr [edx+esi*8], 100
        jne initial_need
        cmp dword ptr [edx+esi*8+4], 0
        je initial_next
    initial_need:
        inc dword ptr [ebp-0x1C]
        cmp dword ptr [edx+esi*8+4], 0
        je initial_next
        inc dword ptr [ebp-0x20]
    initial_next:
        inc esi
        add edi, {POOL_STRIDE:#x}
        dec ecx
        jnz initial_scan
        cmp dword ptr [ebp-0x24], 0
        je invalid_failure
        cmp dword ptr [ebp-0x1C], 0
        je no_change
        cmp dword ptr [{TECH_BALANCE:#x}], {PRICE}
        jb insufficient
        push 1
        push {strings['caption']:#x}
        push {strings['confirm']:#x}
        push 0
        call dword ptr [ebp-0x10]
        cmp eax, 1
        jne canceled
        call {MANAGER_GETTER:#x}
        test eax, eax
        je changed_state
        mov dword ptr [ebp-0x14], eax
        push 0
        mov ecx, {MANAGER_SINGLETON:#x}
        call 0x45C840
        test eax, eax
        je changed_state
        mov dword ptr [ebp-0x18], eax
        mov edi, dword ptr [ebp-0x18]
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
        mov edi, dword ptr [ebp-0x18]
        xor esi, esi
        mov ecx, {POOL_COUNT}
    mutation_scan:
        lea edx, [ebp-0x4E0]
        cmp dword ptr [edx+esi*8], 0
        je mutation_next
        cmp dword ptr [edi+{HEALTH_OFFSET:#x}], 100
        je health_done
        lea eax, [edi+{FULL_RECORD_HEALTH_ARG:#x}]
        mov ecx, eax
        push -1
        push 100
        call {HEALTH_SETTER:#x}
        cmp dword ptr [edi+{HEALTH_OFFSET:#x}], 100
        jne write_failure
    health_done:
        cmp byte ptr [edi+{SICK_OFFSET:#x}], 0
        je mutation_next
        mov byte ptr [edi+{SICK_OFFSET:#x}], 0
        cmp byte ptr [edi+{SICK_OFFSET:#x}], 0
        jne write_failure
        call {MANAGER_GETTER:#x}
        test eax, eax
        je write_failure
        inc dword ptr [eax+0x4FC]
    mutation_next:
        inc esi
        add edi, {POOL_STRIDE:#x}
        dec ecx
        jnz mutation_scan
        call {MANAGER_GETTER:#x}
        test eax, eax
        je write_failure
        mov dword ptr [ebp-0x14], eax
        push 0
        mov ecx, {MANAGER_SINGLETON:#x}
        call 0x45C840
        test eax, eax
        je write_failure
        mov dword ptr [ebp-0x18], eax
    postverify:
        mov edi, dword ptr [ebp-0x18]
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
        cmp dword ptr [edi+{HEALTH_OFFSET:#x}], 100
        jne write_failure
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
        mov dword ptr [ebp-0x14], eax
        cmp dword ptr [{TECH_BALANCE:#x}], {PRICE}
        jb write_failure
        mov ecx, {TECH_BALANCE:#x}
        push -{PRICE}
        call {TECH_DEDUCTION:#x}
        push {strings['success']:#x}
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
    canceled:
        push {strings['canceled']:#x}
        jmp show_no_charge
    changed_state:
        push {strings['changed']:#x}
        jmp show_no_charge
    write_failure:
        push {strings['write_failure']:#x}
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


def build_region() -> tuple[bytes, dict[str, object]]:
    strings, blob = _strings()
    helper = _helper(strings)
    if len(helper) > 0x500 or len(helper) + len(blob) > CAVE_LENGTH:
        raise RuntimeError(f"VV3 Cure helper exceeds bounded cave: {len(helper):#x}")
    region = bytearray(CAVE_LENGTH)
    region[: len(helper)] = helper
    region[STRING_OFFSET : STRING_OFFSET + len(blob)] = blob
    return bytes(region), {
        "helper_length": len(helper),
        "helper_sha256": sha(helper),
        "strings_offset": f"0x{STRING_OFFSET:X}",
        "strings_length": len(blob),
        "strings_sha256": sha(blob),
        "region_sha256": sha(region),
        "used_length": STRING_OFFSET + len(blob),
        "tail_zero_length": CAVE_LENGTH - (STRING_OFFSET + len(blob)),
    }


def main() -> None:
    stock = STOCK.read_bytes()
    if sha(stock) != STOCK_SHA256:
        raise RuntimeError("VV3 stock fingerprint mismatch")
    if bytes.fromhex(HOOK_AFTER.hex()) != rel32(HOOK_VA, CAVE_VA) + b"\x90\x90":
        raise RuntimeError("VV3 Cure hook rel32 mismatch")
    region, layout = build_region()
    if any(stock[CAVE_OFFSET : CAVE_OFFSET + CAVE_LENGTH]):
        raise RuntimeError("VV3 Cure cave is not zero in stock preimage")
    base = json.loads(BASE_MANIFEST.read_text(encoding="utf-8"))
    manifest = {
        "id": "vv3_full_heal_cure_all_candidate",
        "game_id": "vv3",
        "name": "Full Heal / Cure All (candidate)",
        "enabled": False,
        "catalog_hidden": True,
        "catalog_enabled": False,
        "dependencies": ["vv3_individual_grant_running_candidate"],
        "supported_modes": ["collection_progression", "immediate_fixed"],
        "unsupported_patch_modes": ["experimental_expanded_256", "experimental_expanded_256_progression"],
        "source_commit": SOURCE_COMMIT,
        "implementation_status": IMPLEMENTATION_STATUS,
        "runtime_player_status": "pending",
        "price": PRICE,
        "transaction": {"command": 5, "price": PRICE, "action": "Buy", "repeatable": True, "ownership": None, "remove": False},
        "base_chain": {
            "stock_sha256": STOCK_SHA256,
            "collection_pre_cure_sha256": "3644A56FE17F843DB67662E4309C3C2B41AE7ADD5FDD60EF2B6789DE2BA15FDC",
            "immediate_pre_cure_sha256": "059230146E8CC36E06E5473AE187D081E337DB90638B227FBA799B9C82B58C1C",
            "full_mastery_page_sha256": "2DAE85AE4077C23C2C7C39F64B5BA944740F765AC8E24FBB097B0BF28A720DF6",
            "running_region_sha256": "76339C8FFBE0FF92F3F1EB2CC27A4E0600E33DCC936716DA94BBB0BD5D1AB050",
            "full_mastery_running_dependency": "vv3_individual_grant_running_candidate",
            "composition": "Origins + Full Mastery + individual Grant Running",
        },
        "companion_files": [
            {
                "source": "data/candidates/VVFP VV3 Full Mastery Candidate.dll",
                "destination": "VVFP VV3 Full Mastery Candidate.dll",
                "size": 298496,
                "sha256": "35FB96199E745C7D8054FF6A12851B9E09225E3E41D0CE04012604E74968C0D5",
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
            "saved_local": "[ebp-0x10]",
            "stdcall_stack_cleanup": "callee",
        },
        "result_helper": {"va": "0x4A3400", "ret": 8, "caller_stack_cleanup": False},
        "messages": {"no_charge_suffix": "No tech points have been deducted.", "success": "Full Heal was granted to all eligible villagers.", "confirm_price": "30,000"},
        "partial_failure_limit": "Native writes may have occurred before postverification failure; no deduction is made and rollback is not claimed.",
        "forbidden_routes": {"legacy_cure_entry": "0x47B664", "legacy_text_helper": "0x40D8A0", "e94_status_filter": False},
        "patches": [
            {"offset": "0xA35EF", "before": HOOK_BEFORE.hex().upper(), "after": HOOK_AFTER.hex().upper(), "purpose": "command-5 dominance before legacy price lookup/precharge", "continuation_non5": "0x4A35F6"},
            {"offset": f"0x{CAVE_OFFSET:X}", "before_fill": "00", "length": CAVE_LENGTH, "after": region.hex().upper(), "purpose": "candidate-owned RX .text Full Heal helper and strings", "virtual_address": f"0x{CAVE_VA:X}", "legacy_preserved": [f"0x{LEGACY_CURE_START:X}", f"0x{LEGACY_CURE_END:X}"], "layout": layout},
        ],
        "atomicity": {"install_remove": "hook and bounded cave are paired; exact composition, guard, cave, and uninstall preimages required", "expanded_fail_closed": True},
        "mutation_accounting": {
            "physical_ranges": [
                {"offset": "0xA35EF", "length": 7, "purpose": "command-5 hook"},
                {"offset": "0x7B721", "length": CAVE_LENGTH, "purpose": "candidate-owned cave"},
                {"offset": "0x160", "length": 4, "purpose": "PE checksum recomputation"},
            ],
            "feature_owned_ranges": ["0xA35EF..0xA35F5", f"0x{CAVE_OFFSET:X}..0x{CAVE_OFFSET + CAVE_LENGTH - 1:X}"],
            "physical_range_count": 3,
            "feature_owned_range_count": 2,
            "every_other_byte_identical": True,
            "rendered_sha256": RENDERED_SHA256,
            "uninstall_sha256": {
                "collection_progression": "3644A56FE17F843DB67662E4309C3C2B41AE7ADD5FDD60EF2B6789DE2BA15FDC",
                "immediate_fixed": "059230146E8CC36E06E5473AE187D081E337DB90638B227FBA799B9C82B58C1C",
            },
            "checksum_offset": "0x160",
            "checksum_transitions": {
                "collection_progression": {"before": "93790D00", "after": "22ED0C00"},
                "immediate_fixed": {"before": "91BB0D00", "after": "202F0D00"},
            },
        },
    }
    manifest["base_manifest_sha256"] = sha(BASE_MANIFEST.read_bytes())
    artifact_map = {
        "candidate_id": manifest["id"],
        "candidate_enabled": False,
        "catalog_hidden": True,
        "catalog_enabled": False,
        "source_commit": SOURCE_COMMIT,
        "implementation_status": IMPLEMENTATION_STATUS,
        "allowed_modes": manifest["supported_modes"],
        "expanded_fail_closed": True,
        "hook": {"raw_offset": "0xA35EF", "before": HOOK_BEFORE.hex().upper(), "after": HOOK_AFTER.hex().upper(), "sha256": sha(HOOK_AFTER)},
        "cave": {"raw_offset": f"0x{CAVE_OFFSET:X}", "virtual_address": f"0x{CAVE_VA:X}", "length": CAVE_LENGTH, "before_sha256": sha(bytes(CAVE_LENGTH)), "after_sha256": sha(region), "layout": layout},
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
        "mutation_accounting": manifest["mutation_accounting"],
        "forbidden_routes": manifest["forbidden_routes"],
        "legacy_preserved_range": {"raw_start": f"0x{LEGACY_CURE_START:X}", "raw_end": f"0x{LEGACY_CURE_END:X}", "sha256": sha(stock[LEGACY_CURE_START:LEGACY_CURE_END])},
        "rendered": {mode: {"pending": "candidate disabled; render only after independent lifecycle recertification"} for mode in manifest["supported_modes"]},
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_OUT.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    MAP_OUT.write_text(json.dumps(artifact_map, indent=2) + "\n", encoding="utf-8")
    DOC_OUT.write_text(
        "# VV3 Full Heal / Cure All candidate (disabled)\n\n"
        "This stock-only candidate is catalog-hidden and disabled pending independent lifecycle recertification. "
        "It composes only after the certified VV3 Origins + Full Mastery + individual Grant Running chain in "
        "Collection Progression or Immediate Fixed. Expanded-256 is rejected before output.\n\n"
        f"The command-5 detour is `{HOOK_BEFORE.hex().upper()}` -> `{HOOK_AFTER.hex().upper()}` at raw `0x{HOOK_OFFSET:X}`. "
        f"The owned cave is raw `0x{CAVE_OFFSET:X}` / VA `0x{CAVE_VA:X}` for `0x{CAVE_LENGTH:X}` bytes; legacy Cure bytes "
        f"`0x{LEGACY_CURE_START:X}..0x{LEGACY_CURE_END:X}` remain byte-identical.\n\n"
        "The transaction scans exactly 150 records in physical order, resolves record zero through 0x45C840 with ECX=0x59E110 before the dry run and again after confirmation, and resolves USER32.dll/MessageBoxA before any dialog. It performs a complete dry run, confirms at 30,000 tech points, reacquires and rechecks the full state, uses native health setter 0x462670 with ECX=record+0xE6C and pushes -1/100, clears sickness at +0xE89, and increments fresh manager People Cured +0x4FC once per verified sick record (health-only records do not increment). It postverifies and deducts once through 0x427130. The hook and cave are two feature-owned ranges; the only third physical diff is the PE checksum at raw 0x160..0x163. Every no-charge route ends with `No tech points have been deducted.` Native writes may remain after a postverify failure; rollback is not claimed.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
