"""Generate the enabled VV3 selected-villager Grant Running candidate.

The candidate is deliberately separate from the withdrawn command-6
village-wide Running records.  It composes on the already-certified VV3 Full
Mastery chain and owns only the zero ``.vv3fm`` slot at raw ``0xCB900``.  The
generator is intentionally strict: D166's canonical helper,
string, and owned-region identities are immutable pins, not values that this script may
silently replace with a different assembly.
"""

from __future__ import annotations

import hashlib
import json
import struct
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Secret City.exe"
FULL_MASTERY_BASE = ROOT / "data" / "candidates" / "vv3_origins_full_mastery_base_candidate.json"
FULL_MASTERY_FEATURE = ROOT / "data" / "candidates" / "vv3_full_mastery_all_candidate.json"
FULL_MASTERY_MAP = ROOT / "data" / "candidates" / "vv3_full_mastery_all_candidate_map.json"
OUT_DIR = ROOT / "data" / "candidates"
MANIFEST_OUT = OUT_DIR / "vv3_individual_grant_running_candidate.json"
MAP_OUT = OUT_DIR / "vv3_individual_grant_running_candidate_map.json"
DOC_OUT = ROOT / "docs" / "vv3-individual-running-stage-a-candidate.md"

IMAGE_BASE = 0x400000
COMMAND2_OFFSET = 0xA38C3
COMMAND2_VA = 0x4A38C3
COMMAND2_BEFORE = bytes.fromhex("83FB027525")
NON_COMMAND2_VA = 0x4A38ED
DETAIL_LOOP_VA = 0x4A37D6
PAGE_OFFSET = 0xCB000
PAGE_VA = 0x6DF000
OWNED_OFFSET = 0xCB900
OWNED_VA = 0x6DF900
OWNED_LENGTH = 0x700
PAGE_SIZE = 0x1000
HELPER_OFFSET = 0x900
HELPER_VA = OWNED_VA
STRINGS_OFFSET = 0xD00
STRINGS_VA = 0x6DFD00
PE_CHECKSUM_OFFSET = 0x160
PE_CHECKSUM_LENGTH = 4
PRICE = 40_000
RUNNING_ID = 38
STOCK_SHA256 = "8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503"
SOURCE_BASE_COMMIT = "9574f488eefb97bd6320259f301beb87266072f8"
IMPLEMENTATION_COMMIT = "a35bee6ed91fb3f105424dca5e3283ce85e01894"
PRE_RUNNING_SHA256 = {
    "collection_progression": "6B6FCF33C21B5ED9323F8BBE4C677EF12BA4653E775178DCDF8E77049B2F57A8",
    "immediate_fixed": "92C5EF70512F57CBD990301E6918DE1BE002823C31CFB4C638D4E0F141BE7514",
}
EXPECTED_PE_CHECKSUMS = {
    "collection_progression": {
        "pre": "E9AC0D00",
        "candidate": "93790D00",
    },
    "immediate_fixed": {
        "pre": "E8EE0C00",
        "candidate": "91BB0D00",
    },
}
FEATURE_OWNED_RANGES = (
    {
        "raw_offset": "0xA38C3",
        "length": 5,
        "purpose": "candidate command-2 detour",
    },
    {
        "raw_offset": "0xCB900",
        "length": OWNED_LENGTH,
        "purpose": "candidate-owned .vv3fm helper/string region",
    },
)
FULL_MASTERY_PAGE_SHA256 = "2DAE85AE4077C23C2C7C39F64B5BA944740F765AC8E24FBB097B0BF28A720DF6"
ORIGINS_PAYLOAD_SHA256 = "77BF4DB93204AF1212A6335AF624642068A8B8560F1D78D59E2E07FBF4751F69"
OWNED_ZERO_SHA256 = "7B4FC1A8DBE6B6121F16ADA516E2AC27E02964716BACEA5FB7D07CF30595948E"
EXPECTED_HELPER_LENGTH = 0x271
EXPECTED_HELPER_SHA256 = "B03DCCF47903326E95A192A8458FD504E80B5D592784072D47525C217202B544"
EXPECTED_STRINGS_LENGTH = 0x2E7
EXPECTED_STRINGS_SHA256 = "52CB94EFF2FAC50C91B0C4CDF8D3CC973348F5ECE6BC3BAA0B74307FC1ACDC50"
EXPECTED_REGION_SHA256 = "76339C8FFBE0FF92F3F1EB2CC27A4E0600E33DCC936716DA94BBB0BD5D1AB050"
EXPECTED_HOOK_SHA256 = "DB0F47AADB04629EB6FD5966547F11CF32A7DC445E8D8641621925B76C816DA1"
EXPANDED_MODES = (
    "experimental_expanded_256",
    "experimental_expanded_256_progression",
)
STOCK_MODES = {
    "collection_progression": {
        "page_rva": 0x2DF000,
        "page_va": 0x6DF000,
        "old_size_of_image": 0x2DF000,
        "new_size_of_image": 0x2E0000,
    },
    "immediate_fixed": {
        "page_rva": 0x2DF000,
        "page_va": 0x6DF000,
        "old_size_of_image": 0x2DF000,
        "new_size_of_image": 0x2E0000,
    },
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _rel32_jump(source_va: int, target_va: int) -> bytes:
    return b"\xE9" + int(target_va - source_va - 5).to_bytes(4, "little", signed=True)


def _accounted_physical_ranges(
    before: bytes | bytearray,
    after: bytes | bytearray,
    mode: str,
) -> list[dict[str, object]]:
    """Return the three logical physical ranges changed by rendering.

    The owned 0x700-byte slot is one candidate range even when some of its
    trailing bytes remain zero.  The renderer's PE checksum is the only
    deterministic non-feature range; every byte outside these three ranges
    must remain identical.
    """
    if len(before) != len(after):
        raise RuntimeError("rendered candidate size changed during checksum accounting")
    checksum = EXPECTED_PE_CHECKSUMS[mode]
    expected_ranges = [
        {
            "raw_offset": f"0x{PE_CHECKSUM_OFFSET:X}",
            "length": PE_CHECKSUM_LENGTH,
            "owner": "renderer:pe_checksum",
            "before": checksum["pre"],
            "after": checksum["candidate"],
        },
        {
            "raw_offset": "0xA38C3",
            "length": 5,
            "owner": "candidate:command2_detour",
            "before": "83FB027525",
            "after": "E938C02300",
        },
        {
            "raw_offset": "0xCB900",
            "length": OWNED_LENGTH,
            "owner": "candidate:owned_vv3fm_region",
            "before_sha256": OWNED_ZERO_SHA256,
            "after_sha256": EXPECTED_REGION_SHA256,
        },
    ]
    accounted = bytearray(len(before))
    for item in expected_ranges:
        offset = int(str(item["raw_offset"]), 0)
        length = int(item["length"])
        if offset < 0 or offset + length > len(before):
            raise RuntimeError("checksum accounting range is outside the rendered image")
        accounted[offset : offset + length] = b"\x01" * length
    outside_diffs = [
        offset for offset, (left, right) in enumerate(zip(before, after))
        if left != right and not accounted[offset]
    ]
    if outside_diffs:
        raise RuntimeError(
            "rendered candidate changed bytes outside checksum and two feature ranges: "
            + ",".join(f"0x{item:X}" for item in outside_diffs[:8])
        )
    if before[PE_CHECKSUM_OFFSET : PE_CHECKSUM_OFFSET + PE_CHECKSUM_LENGTH].hex().upper() != checksum["pre"]:
        raise RuntimeError(f"{mode} pre-render PE checksum pin mismatch")
    if after[PE_CHECKSUM_OFFSET : PE_CHECKSUM_OFFSET + PE_CHECKSUM_LENGTH].hex().upper() != checksum["candidate"]:
        raise RuntimeError(f"{mode} candidate PE checksum pin mismatch")
    return expected_ranges


CANONICAL_HELPER_HEX = "83FB020F85E43FDCFF5589E553565783EC1C6800FD6D00FF1524C1470085C00F8440020000680BFD6D0050FF1528C1470085C00F842C0200008945F0E81F92D4FF85C00F84EE0100008B88C02F0100894DEC85C90F88DD01000081F9960000000F83D101000051B910E15900E8EFF4D7FF84C00F84BE010000FF75ECB910E15900E8BACED7FF85C00F84A901000083B8780E0000000F8E9C0100008945E88B88B40F0000894DE08B88B80F0000894DDC8B88BC0F0000894DD8C745E4000000008DB8B40F0000B903000000833F260F8455010000833FFF7509837DE4007503897DE483C7044975E3837DE4000F843E010000813D44265800409C00000F824A0100006A016817FD6D006829FD6D006A00FF55F083F8010F8537010000E83F91D4FF85C00F84150100008B88C02F01003B4DEC0F850601000085C90F88FE00000081F9960000000F83F200000051B910E15900E809F4D7FF84C00F84DF000000FF75ECB910E15900E8D4CDD7FF85C00F84CA00000083B8780E0000000F8EBD0000008945E88B88B40F00003B4DE00F85B20000008B88B80F00003B4DDC0F85A30000008B88BC0F00003B4DD80F8594000000C745E4000000008DB8B40F0000B903000000833F26747D833FFF7509837DE4007503897DE483C7044975E7837DE4007463813D44265800409C0000725E8B7DE4833FFF754FC70726000000833F26751668C063FFFFB944265800E82076D4FFBA81FD6D00EB41833F267506C707FFFFFFFFBAA4FF6D00EB2FBA96FD6D00EB28BADFFD6D00EB21BA29FE6D00EB1ABA73FE6D00EB13BAD4FE6D00EB0CBA28FF6D00EB05BA64FF6D006A006817FD6D00526A00FF55F083C41C5F5E5B5DE9653CDCFF"
CANONICAL_STRINGS_HEX = (
    "5553455233322E646C6C004D657373616765426F78410056696C6C61676572205570677261646573004772616E742052756E6E696E6720746F207468"
    "69732076696C6C6167657220666F722034302C303030207465636820706F696E74733F0D0A5072657373204F4B20746F20636F6E6669726D2C206F72"
    "2043616E63656C2E0052756E6E696E6720776173206772616E7465642E00546869732076696C6C6167657220616C7265616479206C696B6573205275"
    "6E6E696E672E0D0A4E6F207465636820706F696E74732068617665206265656E2064656475637465642E00546869732076696C6C6167657220686173"
    "206E6F20656D707479204C696B6520736C6F742E0D0A4E6F207465636820706F696E74732068617665206265656E2064656475637465642E004E6F20"
    "76616C6964206C6976696E672076696C6C616765722069732073656C65637465642E0D0A4E6F207465636820706F696E74732068617665206265656E"
    "2064656475637465642E005468652073656C656374696F6E206F722076696C6C61676572207374617465206368616E67656420647572696E6720636F"
    "6E6669726D6174696F6E2E0D0A4E6F207465636820706F696E74732068617665206265656E2064656475637465642E005468652076696C6C61676572"
    "204C696B6573206368616E67656420647572696E6720636F6E6669726D6174696F6E2E0D0A4E6F207465636820706F696E7473206861766520626565"
    "6E2064656475637465642E004E6F7420656E6F756768207465636820706F696E74732E0D0A4E6F207465636820706F696E7473206861766520626565"
    "6E2064656475637465642E004772616E742052756E6E696E67207761732063616E63656C65642E0D0A4E6F207465636820706F696E74732068617665"
    "206265656E2064656475637465642E0052756E6E696E6720636F756C64206E6F742062652076657269666965642E0D0A4E6F207465636820706F696E"
    "74732068617665206265656E2064656475637465642E00"
)


def _canonical_strings() -> tuple[dict[str, int], bytes]:
    blob = bytes.fromhex(CANONICAL_STRINGS_HEX)
    if len(blob) != EXPECTED_STRINGS_LENGTH or sha(blob) != EXPECTED_STRINGS_SHA256:
        raise RuntimeError("D166 canonical strings blob is malformed")
    names = (
        "user32",
        "message_box",
        "caption",
        "warning",
        "success",
        "already",
        "no_empty",
        "invalid",
        "selection_changed",
        "likes_changed",
        "insufficient",
        "cancel",
        "write_failure",
    )
    addresses: dict[str, int] = {}
    offset = 0
    for name in names:
        end = blob.find(b"\0", offset)
        if end < 0:
            raise RuntimeError(f"D166 canonical string {name} is unterminated")
        addresses[name] = STRINGS_VA + offset
        offset = end + 1
    if offset != len(blob):
        raise RuntimeError("D166 canonical strings contain unexpected trailing bytes")
    return addresses, blob


def _strings() -> tuple[dict[str, int], bytes]:
    return _canonical_strings()


def _build_helper() -> tuple[bytes, dict[str, int], bytes]:
    """Return the immutable D166 helper and natural string table."""
    helper = bytes.fromhex(CANONICAL_HELPER_HEX)
    strings, string_blob = _canonical_strings()
    if len(helper) != EXPECTED_HELPER_LENGTH or sha(helper) != EXPECTED_HELPER_SHA256:
        raise RuntimeError("D166 canonical helper blob is malformed")
    if len(helper) > STRINGS_OFFSET - HELPER_OFFSET:
        raise RuntimeError("D166 helper overlaps the canonical string start")
    return helper, strings, string_blob


def _build_owned_region() -> tuple[bytes, dict[str, object]]:
    """Build only the existing 0x700-byte zero slot at raw 0xCB900."""
    helper, strings, string_blob = _build_helper()
    if len(string_blob) > OWNED_LENGTH - (STRINGS_OFFSET - HELPER_OFFSET):
        raise RuntimeError(
            "VV3 individual Running strings exceed the owned .vv3fm slot: "
            f"0x{len(string_blob):X} > 0x{OWNED_LENGTH - (STRINGS_OFFSET - HELPER_OFFSET):X}"
        )
    region = bytearray(OWNED_LENGTH)
    region[: len(helper)] = helper
    string_start = STRINGS_OFFSET - HELPER_OFFSET
    region[string_start : string_start + len(string_blob)] = string_blob
    return bytes(region), {
        "raw_offset": f"0x{OWNED_OFFSET:X}",
        "virtual_address": f"0x{OWNED_VA:X}",
        "length": OWNED_LENGTH,
        "helper_length": len(helper),
        "helper_sha256": sha(helper),
        "strings_offset": f"0x{PAGE_OFFSET + STRINGS_OFFSET:X}",
        "strings_virtual_address": f"0x{STRINGS_VA:X}",
        "strings_length": len(string_blob),
        "strings_sha256": sha(string_blob),
        "strings": {key: f"0x{value:X}" for key, value in strings.items()},
        "stack_frame": {
            "saved_message_box": "-0x10",
            "selected_index": "-0x14",
            "record": "-0x18",
            "first_empty_like": "-0x1C",
            "snapshot": ["-0x20", "-0x24", "-0x28"],
            "local_allocation": "0x1C",
        },
        "canonical_blob_layout": {
            "helper_offset": "0x0",
            "helper_length": "0x271",
            "strings_offset": "0x400",
            "strings_length": "0x2E7",
            "tail_offset": "0x6E7",
            "tail_length": "0x19",
        },
        "tail_offset": f"0x{OWNED_OFFSET + (STRINGS_OFFSET - HELPER_OFFSET) + len(string_blob):X}",
        "tail_length": OWNED_LENGTH - (STRINGS_OFFSET - HELPER_OFFSET) - len(string_blob),
        "helper_region_sha256": sha(bytes(region[: STRINGS_OFFSET - HELPER_OFFSET])),
        "no_dislike_offsets": [],
    }


def _render_map(
    candidate: dict[str, object],
    owned_region: bytes,
    region_map: dict[str, object],
) -> dict[str, object]:
    sys.path.insert(0, str(ROOT / "src"))
    from vv_fun_patcher import (
        FunPatch,
        PatcherError,
        _certified_vv3_full_mastery_records,
        _pe_checksum_layout,
        load_builds,
        render_patched_bytes,
    )

    build = next(item for item in load_builds() if item.id == "vv3")
    active_origins = json.loads(
        (ROOT / "data" / "vv3_origins_feature.json").read_text(encoding="utf-8")
    )
    certified = _certified_vv3_full_mastery_records(active_origins)
    if certified is None:
        raise RuntimeError("certified VV3 Full Mastery chain is unavailable")
    certified_base, certified_feature = certified
    full_base = FunPatch(certified_base)
    full_feature = FunPatch(certified_feature)
    feature = FunPatch(candidate)
    renders: dict[str, object] = {}
    for mode in STOCK_MODES:
        pre_running, _ = render_patched_bytes(
            STOCK,
            build,
            mode,
            _fun_patches_override=[full_base, full_feature],
        )
        pre_sha = sha(bytes(pre_running))
        if pre_sha != PRE_RUNNING_SHA256[mode]:
            raise RuntimeError(
                f"certified Full Mastery pre-Running {mode} mismatch: "
                f"expected {PRE_RUNNING_SHA256[mode]}, got {pre_sha}"
            )
        rendered, applied = render_patched_bytes(
            STOCK,
            build,
            mode,
            _fun_patches_override=[full_base, full_feature, feature],
        )
        checksum_offset, _ = _pe_checksum_layout(rendered)
        if checksum_offset != PE_CHECKSUM_OFFSET:
            raise RuntimeError(f"{mode} PE checksum offset changed: 0x{checksum_offset:X}")
        physical_ranges = _accounted_physical_ranges(pre_running, rendered, mode)
        renders[mode] = {
            "sha256": sha(bytes(rendered)),
            "size": len(rendered),
            "pre_running_sha256": pre_sha,
            "pre_pe_checksum": f"0x{struct.unpack_from('<I', pre_running, checksum_offset)[0]:08X}",
            "pe_checksum": f"0x{struct.unpack_from('<I', rendered, checksum_offset)[0]:08X}",
            "physical_diff_ranges": physical_ranges,
            "feature_owned_ranges": [dict(item) for item in FEATURE_OWNED_RANGES],
            "physical_diff_range_count": len(physical_ranges),
            "feature_owned_range_count": len(FEATURE_OWNED_RANGES),
            "all_other_bytes_identical": True,
            "owners": sorted({item["owner"] for item in applied}),
        }
    for mode in EXPANDED_MODES:
        try:
            render_patched_bytes(
                STOCK,
                build,
                mode,
                _fun_patches_override=[full_base, full_feature, feature],
            )
        except PatcherError as exc:
            renders[mode] = {"rejected": str(exc)}
        else:
            raise RuntimeError(f"Expanded mode unexpectedly accepted: {mode}")
    return renders


def main() -> None:
    stock = STOCK.read_bytes()
    if len(stock) != 831_488 or sha(stock) != STOCK_SHA256:
        raise RuntimeError("VV3 stock fixture fingerprint mismatch")
    for path, expected in (
        (FULL_MASTERY_BASE, "657D2D4F01550A121127053878E2777AB719CF00300A2AD69016296A4758B989"),
        (FULL_MASTERY_FEATURE, "844A3CB7996793F51D741409C9EFAF675E07ED92122BCD2F91750766D7357783"),
        (FULL_MASTERY_MAP, "018586F36A9B242D11C6A245DC5E2C2A8C5BA0A5E20B398DC00AFB3E86CCDAF7"),
    ):
        actual = sha(path.read_bytes())
        if actual != expected:
            raise RuntimeError(f"certified Full Mastery input mismatch for {path.name}: {actual}")
    full_map = json.loads(FULL_MASTERY_MAP.read_text(encoding="utf-8"))
    if full_map.get("base_stock_payload_sha256") != ORIGINS_PAYLOAD_SHA256:
        raise RuntimeError("certified Origins payload identity is not the D166 value")
    for mode in STOCK_MODES:
        if full_map["layouts"][mode]["installed_page_sha256"] != FULL_MASTERY_PAGE_SHA256:
            raise RuntimeError(f"Full Mastery page identity mismatch for {mode}")

    owned_region, region_map = _build_owned_region()
    hook_after = _rel32_jump(COMMAND2_VA, HELPER_VA)
    if hook_after != bytes.fromhex("E938C02300"):
        raise RuntimeError(f"command-2 detour mismatch: {hook_after.hex().upper()}")
    if sha(hook_after) != EXPECTED_HOOK_SHA256:
        raise RuntimeError(f"D166 hook hash mismatch: {sha(hook_after)}")
    helper_len = int(region_map["helper_length"])
    strings_len = int(region_map["strings_length"])
    if helper_len != EXPECTED_HELPER_LENGTH:
        raise RuntimeError(f"D166 helper length mismatch: expected 0x271, got 0x{helper_len:X}")
    if region_map["helper_sha256"] != EXPECTED_HELPER_SHA256:
        raise RuntimeError(f"D166 helper hash mismatch: {region_map['helper_sha256']}")
    if strings_len != EXPECTED_STRINGS_LENGTH:
        raise RuntimeError(f"D166 string length mismatch: expected 0x2E7, got 0x{strings_len:X}")
    if region_map["strings_sha256"] != EXPECTED_STRINGS_SHA256:
        raise RuntimeError(f"D166 string hash mismatch: {region_map['strings_sha256']}")
    if sha(owned_region) != EXPECTED_REGION_SHA256:
        raise RuntimeError(f"D166 owned-region hash mismatch: {sha(owned_region)}")
    if sha(bytes(OWNED_LENGTH)) != OWNED_ZERO_SHA256:
        raise RuntimeError("D166 zero preimage hash mismatch")

    candidate = {
        "id": "vv3_individual_grant_running_candidate",
        "game_id": "vv3",
        "name": "Grant Running to Selected Villager",
        "enabled": True,
        "catalog_hidden": False,
        "catalog_enabled": True,
        "certification_status": (
            "D172 independent static GO; stock Collection Progression and "
            "Immediate Fixed catalog-enabled; runtime/player validation pending; "
            "Expanded-256 fail-closed"
        ),
        "source_commit": SOURCE_BASE_COMMIT,
        "implementation_commit": IMPLEMENTATION_COMMIT,
        "runtime_player_status": "pending",
        "supported_modes": ["collection_progression", "immediate_fixed"],
        "dependencies": ["vv3_full_mastery_all_stage_a_candidate"],
        "base_chain": {
            "collection_pre_running_sha256": PRE_RUNNING_SHA256["collection_progression"],
            "immediate_pre_running_sha256": PRE_RUNNING_SHA256["immediate_fixed"],
            "full_mastery_page_sha256": FULL_MASTERY_PAGE_SHA256,
            "origins_payload_sha256": ORIGINS_PAYLOAD_SHA256,
            "full_mastery_base": FULL_MASTERY_BASE.name,
            "full_mastery_feature": FULL_MASTERY_FEATURE.name,
        },
        "description": (
            "Enabled/catalog-visible stock Collection Progression/Immediate Fixed-only "
            "selected-villager Grant Running candidate composed after the certified "
            "VV3 Full Mastery chain. The withdrawn village-wide command-6 Running "
            "candidate is not reused or modified; runtime/player validation remains pending."
        ),
        "behavior_changes": [
            "Command-2 selected-villager Grant Running is an exact 40,000-tech-point Buy action, repeatable=true, ownership=null, remove=false.",
        ],
        "explicit_non_changes": [
            "The GUI dependency closure selects the certified VV3 Full Mastery prerequisite; direct API/CLI selections containing only this ID fail closed and do not auto-expand.",
            "The withdrawn village-wide command-6 Running candidate remains absent and is not reused or modified.",
        ],
        "mutation_accounting": {
            "feature_owned_range_count": len(FEATURE_OWNED_RANGES),
            "feature_owned_ranges": [dict(item) for item in FEATURE_OWNED_RANGES],
            "physical_diff_range_count": 3,
            "checksum_range": {
                "raw_offset": f"0x{PE_CHECKSUM_OFFSET:X}",
                "length": PE_CHECKSUM_LENGTH,
                "purpose": "deterministic PE checksum recomputation",
                "per_mode": EXPECTED_PE_CHECKSUMS,
            },
            "rule": (
                "The two candidate-owned feature ranges plus raw 0x160..0x163 "
                "PE checksum are the three physical accounting ranges; every "
                "other byte is identical to the certified pre-Running image."
            ),
        },
        "companion_files": [],
        "patches": [
            {
                "offset": f"0x{COMMAND2_OFFSET:X}",
                "before": COMMAND2_BEFORE.hex().upper(),
                "after": hook_after.hex().upper(),
                "purpose": "detour only command 2 before legacy price lookup/charge to the selected-villager helper",
            },
            {
                "offset": f"0x{OWNED_OFFSET:X}",
                "before_fill": "00",
                "length": OWNED_LENGTH,
                "after": owned_region.hex().upper(),
                "helper_length": EXPECTED_HELPER_LENGTH,
                "helper_sha256": EXPECTED_HELPER_SHA256,
                "strings_length": EXPECTED_STRINGS_LENGTH,
                "strings_sha256": EXPECTED_STRINGS_SHA256,
                "purpose": "install exactly the candidate-owned D166 canonical helper/strings in the existing .vv3fm zero slot",
            },
        ],
        "unsupported_patch_modes": list(EXPANDED_MODES),
        "owned_region": {
            **region_map,
            "preimage_sha256": OWNED_ZERO_SHA256,
            "after_sha256": EXPECTED_REGION_SHA256,
            "tail_zero_length": 0x19,
        },
        "transaction_contract": {
            "command": 2,
            "price": PRICE,
            "action": "Buy",
            "repeatable": True,
            "ownership": None,
            "remove": False,
            "record_bound": 150,
            "stack_frame": region_map["stack_frame"],
            "canonical_blob_layout": region_map["canonical_blob_layout"],
            "selection": {
                "manager_getter": "sub_428B60",
                "selected_index_offset": "0x12FC0",
                "validator": "sub_45EE60 with ECX=0x59E110",
                "resolver": "sub_45C840 with ECX=0x59E110",
                "same_index_required_after_confirmation": True,
            },
            "eligibility": ["signed index 0..149", "signed health +0xE78 > 0"],
            "likes": {"offsets": ["0xFB4", "0xFB8", "0xFBC"], "running": RUNNING_ID, "empty": -1},
            "dislikes": {"read": False, "write": False, "storage_never_touched": True},
            "passes": ["complete initial three-DWORD Like snapshot/scan", "funds >= 40000", "OK/Cancel", "fresh singleton/index/record", "complete second scan and exact snapshot comparison", "fresh funds check", "verified single first-empty write of 38", "one native deduction"],
            "deduction": {"receiver": "ECX=0x582644", "delta": -PRICE, "writer": "sub_427130", "calls": 1},
            "process_fault_limit": "a process fault remains possible after verified slot write and before native deduction; no rollback atomicity is claimed",
        },
        "result_messages": {
            "no_charge_suffix": "No tech points have been deducted.",
            "distinct": ["already_running", "no_empty_like", "invalid_selection", "selection_changed", "likes_changed", "insufficient_funds", "canceled", "write_verification_failure"],
            "aliases": {"inactive_or_dead": "invalid_selection"},
            "invalid_selection_text": "No valid living villager is selected.\r\nNo tech points have been deducted.",
            "success": "Running was granted.",
        },
    }
    MANIFEST_OUT.write_text(json.dumps(candidate, indent=2) + "\n", encoding="utf-8")
    renders = _render_map(candidate, owned_region, region_map)
    artifact = {
        "candidate_id": candidate["id"],
        "candidate_enabled": True,
        "catalog_hidden": False,
        "catalog_enabled": True,
        "source_commit": SOURCE_BASE_COMMIT,
        "implementation_commit": IMPLEMENTATION_COMMIT,
        "acceptance_status": "D172 independent static GO; runtime/player validation pending",
        "allowed_modes": ["collection_progression", "immediate_fixed"],
        "expanded_fail_closed": True,
        "source": {"size": len(stock), "sha256": STOCK_SHA256},
        "base_chain": candidate["base_chain"],
        "manifest_sha256": sha(MANIFEST_OUT.read_bytes()),
        "feature_owned_ranges": [
            {
                "file_offset": f"0x{COMMAND2_OFFSET:X}",
                "virtual_address": f"0x{COMMAND2_VA:X}",
                "length": len(hook_after),
                "before": COMMAND2_BEFORE.hex().upper(),
                "after": hook_after.hex().upper(),
                "sha256": EXPECTED_HOOK_SHA256,
            },
            {
                "file_offset": f"0x{OWNED_OFFSET:X}",
                "virtual_address": f"0x{OWNED_VA:X}",
                "length": OWNED_LENGTH,
                "before_sha256": OWNED_ZERO_SHA256,
                "after_sha256": EXPECTED_REGION_SHA256,
                "helper_sha256": EXPECTED_HELPER_SHA256,
                "strings_sha256": EXPECTED_STRINGS_SHA256,
            },
        ],
        "physical_diff_ranges": {
            mode: renders[mode]["physical_diff_ranges"] for mode in STOCK_MODES
        },
        "mutation_accounting": candidate["mutation_accounting"],
        "protected_regions": (
            "every byte outside raw 0x160..0x163, 0xA38C3..0xA38C7, and "
            "0xCB900..0xCBFFF is byte-identical to the certified pre-Running image"
        ),
        "protected_calls": {"manager_getter": "0x428B60", "validator": "0x45EE60", "resolver": "0x45C840", "deduction": "0x427130"},
        "no_dislike_or_e94_access": True,
        "stack_frame": region_map["stack_frame"],
        "canonical_blob_layout": region_map["canonical_blob_layout"],
        "semantic_guards": {
            "command_gate_before_api": True,
            "message_box_pointer": "[ebp-0x10]",
            "selected_index_local": "[ebp-0x14]",
            "record_local": "[ebp-0x18]",
            "first_empty_like_local": "[ebp-0x1C]",
            "snapshot_locals": ["[ebp-0x20]", "[ebp-0x24]", "[ebp-0x28]"],
            "likes_only_offsets": ["0xFB4", "0xFB8", "0xFBC"],
            "forbidden_offsets": ["0xFC0", "0xFC4", "0xFC8", "0xE94"],
            "native_deduction_calls": 1,
        },
        "composition": {"full_mastery_chain": "required and verified before candidate patch", "withdrawn_village_wide_running": "not a dependency and not reused"},
        "rendered": renders,
    }
    MAP_OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    DOC_OUT.write_text(
        "# VV3 individual Grant Running - enabled static candidate\n\n"
        "This candidate is enabled and catalog-visible only for stock Collection "
        "Progression and Immediate Fixed. It composes after the certified VV3 Full "
        "Mastery chain; runtime/player validation remains pending, and it does not "
        "reuse or modify the withdrawn village-wide command-6 Running candidate.\n\n"
        f"- Stock SHA-256: `{STOCK_SHA256}`; source baseline: `{SOURCE_BASE_COMMIT}`.\n"
        f"- Certified pre-Running identities: Collection `{PRE_RUNNING_SHA256['collection_progression']}`, "
        f"Immediate `{PRE_RUNNING_SHA256['immediate_fixed']}`; Full Mastery `.vv3fm` page `{FULL_MASTERY_PAGE_SHA256}`.\n"
        f"- Hook: file/VA `0x{COMMAND2_OFFSET:X}`/`0x{COMMAND2_VA:X}`, `{COMMAND2_BEFORE.hex().upper()}` â†’ `{hook_after.hex().upper()}`; "
        f"non-command-2 continues at `0x{NON_COMMAND2_VA:X}` and every result returns to `0x{DETAIL_LOOP_VA:X}`.\n"
        f"- Owned slot: raw/VA `0x{OWNED_OFFSET:X}`/`0x{OWNED_VA:X}`, length `0x{OWNED_LENGTH:X}`, "
        f"helper `0x{region_map['helper_length']:X}` bytes `{region_map['helper_sha256']}`, strings at `0x{STRINGS_VA:X}` `{region_map['strings_length']:#x}` bytes `{region_map['strings_sha256']}`.\n"
        "- Buy contract: command 2, price 40,000, action `Buy`, repeatable `true`, ownership `null`, remove `false`. "
        "The GUI dependency closure selects Full Mastery; direct API/CLI requests containing only this ID fail closed.\n"
        "- Transaction: selected physical index 0..149, signed health +0xE78 > 0, complete three-DWORD Likes-only dry run and snapshot, >=40,000 funds check, exact OK/Cancel warning, fresh same-index reacquisition, complete final snapshot comparison, first exact -1 Like write of 38, readback, then one `ECX=0x582644`, push -40,000, `sub_427130` deduction. Dislikes and +0xE94 are never accessed.\n"
        "- Every no-charge result is reason-specific and includes `No tech points have been deducted.` A process fault remains possible between verified write and deduction; rollback atomicity is not claimed.\n"
        "- Only stock modes are supported. The two Expanded-256 modes, malformed/corrupt inputs, wrong chain, nonzero owned slot, and uninstall mismatches fail closed. Independent emitted-byte and runtime/player recertification remains pending.\n",
        encoding="utf-8",
    )
    # Rewrite the generated document from the same canonical values after the
    # legacy block above; this keeps the on-disk artifact free of stale claims
    # while the source diff remains limited to this candidate generator.
    DOC_OUT.write_text(
        "# VV3 individual Grant Running - enabled static candidate\n\n"
        "This stock-only candidate is enabled and catalog-visible only for Collection "
        "Progression and Immediate Fixed after D172 independent static GO. Runtime/player "
        "validation remains pending. It composes only after the "
        "certified VV3 Full Mastery chain and does not reuse or modify the withdrawn "
        "village-wide command-6 Running candidate.\n\n"
        f"- Stock SHA-256: `{STOCK_SHA256}`; source baseline: `{SOURCE_BASE_COMMIT}`.\n"
        f"- Certified pre-Running identities: Collection `{PRE_RUNNING_SHA256['collection_progression']}`, "
        f"Immediate `{PRE_RUNNING_SHA256['immediate_fixed']}`; Full Mastery `.vv3fm` page `{FULL_MASTERY_PAGE_SHA256}`; "
        f"Origins payload `{ORIGINS_PAYLOAD_SHA256}`.\n"
        f"- Hook: raw/file and VA `0x{COMMAND2_OFFSET:X}`/`0x{COMMAND2_VA:X}`, `{COMMAND2_BEFORE.hex().upper()}` -> `{hook_after.hex().upper()}` "
        f"(SHA-256 `{EXPECTED_HOOK_SHA256}`); command 2 is gated before any API call, non-command-2 continues at `0x{NON_COMMAND2_VA:X}`, "
        f"and result paths return to `0x{DETAIL_LOOP_VA:X}`.\n"
        "- Physical accounting has exactly three ranges: candidate-owned `0xA38C3..0xA38C7` and `0xCB900..0xCBFFF`, plus deterministic "
        "PE checksum recomputation at raw `0x160..0x163`. Collection is `E9AC0D00` -> `93790D00`; Immediate is `E8EE0C00` -> `91BB0D00`; "
        "every other byte is identical to the certified pre-Running image.\n"
        f"- Existing owned `.vv3fm` slot: raw/VA `0x{OWNED_OFFSET:X}`/`0x{OWNED_VA:X}`, length `0x{OWNED_LENGTH:X}`, "
        f"helper `0x{region_map['helper_length']:X}` bytes (SHA-256 `{region_map['helper_sha256']}`), "
        f"strings at VA `0x{STRINGS_VA:X}` length `0x{region_map['strings_length']:X}` (SHA-256 `{region_map['strings_sha256']}`), "
        "with a natural string table and a 0x19-byte zero tail.\n"
        "- Canonical stack frame: `sub esp,0x1C`; MessageBoxA pointer `[ebp-0x10]`, selected physical index `[ebp-0x14]`, "
        "record `[ebp-0x18]`, first empty Like `[ebp-0x1C]`, and the three Like snapshots `[ebp-0x20]`, "
        "`[ebp-0x24]`, `[ebp-0x28]`; these locals do not overlap saved registers or one another.\n"
        "- Buy contract: command 2, price 40,000, action `Buy`, repeatable `true`, ownership `null`, remove `false`. "
        "The GUI dependency closure selects the certified VV3 Full Mastery prerequisite; direct API/CLI requests containing only this ID fail closed.\n"
        "- Transaction: validate a selected physical index 0..149 through the native validator/resolver, require signed health "
        "+0xE78 > 0, and scan only Likes +0xFB4/+0xFB8/+0xFBC. A complete initial three-DWORD scan preserves every existing Running "
        "slot and records the first exact -1 slot; only then is the >=40,000 funds check and exact OK/Cancel confirmation shown. "
        "After OK, reacquire the singleton, selection, record, eligibility, Likes, and funds; require an exact snapshot match, write 38 "
        "only to the first still-empty slot, read it back, then perform one native `ECX=0x582644`, push -40,000, `sub_427130` deduction.\n"
        "- Distinct reason-aware no-charge results cover already Running, no empty Like, selection/state change, "
        "Likes changed, insufficient funds, cancellation, and write verification failure. Every no-charge result includes `No tech points have been deducted.` "
        "Inactive/dead acquisition failures share the invalid-selection text `No valid living villager is selected.\\r\\nNo tech points have been deducted.` "
        "The success result is exactly `Running was granted.` Dislikes (+0xFC0 onward) and +0xE94 are never read or written. A process fault remains possible between verified slot write and "
        "native deduction; rollback atomicity is not claimed.\n"
        "- Only stock Collection Progression and Immediate Fixed are supported. Expanded-256, malformed/corrupt inputs, wrong Full Mastery "
        "chain, nonzero owned slot, and uninstall mismatches fail closed before output or mutation.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
