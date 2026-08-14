from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shutil
import stat
import struct
import sys
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from transparency import write_transparency_artifacts

ROOT = Path(__file__).resolve().parents[1]
SOURCE_TEXT_DIGEST_ALGORITHM = "vvfp.source-text.v1"


def canonical_source_text_bytes(payload: bytes) -> bytes:
    """Canonical UTF-8/no-BOM/LF bytes for authenticated tracked source text."""
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise PatcherError("Authenticated source text is not valid UTF-8.") from exc
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def source_text_sha256(payload: bytes) -> str:
    return hashlib.sha256(canonical_source_text_bytes(payload)).hexdigest().upper()
MANIFEST_PATH = ROOT / "data" / "builds.json"
EXPANDED_MANIFEST_PATH = ROOT / "data" / "expanded_256.json"
VV4_EXPANDED_CONTRACT_PATH = ROOT / "data" / "vv4_expanded_256_contract.json"
EXPANDED_STATIC_REPAIR_INTEGRATION_PATH = (
    ROOT / "data" / "expanded_256_static_repair_integration.json"
)
EXPANDED_STATIC_REPAIR_INTEGRATION_SCHEMA_PATH = (
    ROOT / "data" / "schemas" / "expanded_256_static_repair_integration.schema.json"
)
EXPANDED_ATOMIC_WRITER_INTEGRATION_PATH = (
    ROOT / "data" / "expanded_atomic_writer_integration.json"
)
EXPANDED_ATOMIC_WRITER_INTEGRATION_SCHEMA_PATH = (
    ROOT / "data" / "schemas" / "expanded_atomic_writer_integration.schema.json"
)
VV3_EXPANDED_TIME_WARP_CORE_PATH = (
    ROOT / "data" / "vv3_expanded_time_warp_core.json"
)
EXPANDED_STATIC_REPAIR_INTEGRATION_SHA256 = (
    "93AE2305D23F5FCBE1BB1726BC563E5CAF20E85E926AD26D3AB84D9BB3985195"
)
EXPANDED_ATOMIC_WRITER_INTEGRATION_SHA256 = (
    "1B7068D0679CA896706AA201D27726AF612FD167C0406C5D509774E40728F6A6"
)
EXPANDED_MANIFEST_IDENTITIES = {
    "vv3": {
        "source_sha256": "8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503",
        "prototype_sha256": "6EE3361A7AC35F441763647C1E2FC9EC49569DE5EF372BDB41D243D03002D601",
        "patch_count": 1263,
        "patches_sha256": "04B93127BC4D5C6787AB013DE9205813D44947DBC16A370DBC234C06588AC3FB",
    },
    "vv4": {
        "source_sha256": "6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220",
        "prototype_sha256": "3697317341C23B107F8C06F6D4164BC4602BF5CB90DFB56A6B68EB7EA3C43EE1",
        "patch_count": 1771,
        "patches_sha256": "99ABB42FF46A05B92DA96D7EB80F86A8BA5B165CC83795209C652044A683ED71",
    },
    "vv5": {
        "source_sha256": "92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D",
        "prototype_sha256": "1C825CB6AC3C7E1368D3EFD9C81E844A336AB31C7EBA0971674601F25E3E8F0B",
        "patch_count": 1951,
        "patches_sha256": "D0E899B112C106AF136D6D2F91C68C97CF6B431DB6F5457CBD6211852BA01431",
    },
}
VV5_ORIGINS_STOCK_SHA256 = "92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D"
VV5_ORIGINS_RELOCATION_PARTITIONS = {
    "payload_internal_absolute": frozenset(
        {
            "0xDB087", "0xDB147", "0xDB1C3", "0xDB1D2", "0xDB21B", "0xDB22A",
            "0xDB354", "0xDB383", "0xDB399", "0xDB3B4", "0xDB3D5", "0xDB41E",
            "0xDB48E", "0xDB4C4", "0xDB4CB", "0xDB4D2", "0xDB4D8", "0xDB787",
            "0xDB793", "0xDB865", "0xDB88E", "0xDB895", "0xDB89B",
        }
    ),
    "cross_section_rel32": frozenset(
        {
            "0x18910", "0x1EB70", "0x237B1", "0x40A25", "0x4AF13", "0x4BC21", "0x94FBF",
            "0xDB01C", "0xDB021", "0xDB043", "0xDB055", "0xDB06C", "0xDB08E", "0xDB096",
            "0xDB0E1", "0xDB103", "0xDB115", "0xDB12C", "0xDB14E", "0xDB156", "0xDB1A4",
            "0xDB272", "0xDB283", "0xDB292", "0xDB38D", "0xDB3C3", "0xDB3ED", "0xDB415",
            "0xDB437", "0xDB45A", "0xDB462", "0xDB46C", "0xDB7AC", "0xDBA3B", "0xDBB22", "0xDBB27",
        }
    ),
    "external_absolute": frozenset(
        {"0x94B80", "0x94B85", "0x94B94", "0x94ED1", "0x94ED6", "0x94EE5", "0x94FBA"}
    ),
}
VV5_ORIGINS_NATIVE_OVERRIDE_PREIMAGES = {
    "0x1EB70": ("8C3F3900", "F67E3456"),
    "0x237B1": ("4BF23800", "8B742408"),
}
VV4_ORIGINS_RELOCATION_LEDGER_SHA256 = (
    "CEE01F4AEC59CB1CEE0F42E3DDDB3A24615261E628ED0629C1BFAABF421A897D"
)
VV5_ORIGINS_RELOCATION_LEDGER_SHA256 = (
    "7A95D8CCC6477777E9A3AA4C3EFEB30D8AF0D50434C910C1ADE9A645C7DBDDCA"
)
ORIGINS_FEATURE_PATHS = tuple(
    ROOT / "data" / f"vv{game_number}_origins_feature.json"
    for game_number in range(1, 6)
)
ORIGINS_VILLAGE_WIDE_FEATURE_PATHS = tuple(
    ROOT / "data" / f"vv{game_number}_origins_village_wide_upgrades.json"
    for game_number in range(1, 6)
)
VV2_PLAYTEST_DISABLED_FEATURE_ID = "vv2_enable_origins_exclusive_features"
VV2_PLAYTEST_DISABLED_FEATURE_PATH = ROOT / "data" / "vv2_origins_feature.json"
VV3_RUNNING_CANDIDATE_PATHS = {
    "base": ROOT / "data" / "candidates" / "vv3_origins_running_base_candidate.json",
    "running": ROOT / "data" / "candidates" / "vv3_all_villagers_like_running_candidate.json",
    "map": ROOT / "data" / "candidates" / "vv3_running_candidate_map.json",
}
VV3_RUNNING_CERTIFIED_SHA256 = {
    "base": "65F1F5FA72F127986F71A69368E1CC7E013FD0D00B1E6640113B34032ACB9B21",
    "running": "D6AC66D196D4765AB7DC6D719B3180082C15BBF2F267EBF36D614A14B45556A5",
    "map": "63F3A1780A6A4A7300C8A2C1923203AEFA7E85A21B1A92D6E1CE47E9F924B2DC",
}
VV3_FULL_MASTERY_CANDIDATE_PATHS = {
    "base": ROOT / "data" / "candidates" / "vv3_origins_full_mastery_base_candidate.json",
    "feature": ROOT / "data" / "candidates" / "vv3_full_mastery_all_candidate.json",
    "map": ROOT / "data" / "candidates" / "vv3_full_mastery_all_candidate_map.json",
    "dll": ROOT / "data" / "candidates" / "VVFP VV3 Safe Upgrade Foundation.dll",
}
VV3_FULL_MASTERY_CERTIFIED_SHA256 = {
    "base": "71AEE1460B9B39974D42465EE17A81F04B74916623F636ADC83D5F5DE8B5DE3D",
    "feature": "D0FA9145AFECF0EE14A50D04F113E154C497DAC88C7A8AA0660A0FD338DBDF28",
    "map": "1CAADD292CE24941EE2EA39B44E758C4BF764A1E2E761C2259C37DD8A1EF0AC8",
    "dll": "A99584788F1726AF2DFDAE83BC9F42DE82DBD2DBA6E1ECD56222D2BDACB47681",
    "entry": "9685954F75E1DD26103507213FBEADBD9DED2705E62CB37D14080F6EBEC6EB23",
    "slot": "B1499EB3B10B7E4728746711E9F63B88211E4B80CA378742ADC5DC06782DAADA",
    "page": "2DAE85AE4077C23C2C7C39F64B5BA944740F765AC8E24FBB097B0BF28A720DF6",
}
# The current public VV3 route is the complete Origins-style upgrades menu.
# Standalone Full Mastery artifacts remain in the repository only as
# historical evidence and are never admitted to the active catalog.
VV3_FULL_MASTERY_ENABLED = False
VV3_INDIVIDUAL_FULL_MASTERY_CANDIDATE_ID = "vv3_individual_full_mastery_candidate"
VV3_INDIVIDUAL_FULL_MASTERY_CANDIDATE_PATHS = {
    "manifest": ROOT / "data" / "candidates" / "vv3_individual_full_mastery_candidate.json",
    "map": ROOT / "data" / "candidates" / "vv3_individual_full_mastery_candidate_map.json",
}
VV3_INDIVIDUAL_FULL_MASTERY_MANIFEST_SHA256 = "7776B96591750C8171A61F01C533D8C584A0E0436EF39B2293CA8C06D7155ABA"
VV3_INDIVIDUAL_FULL_MASTERY_MAP_SHA256 = "610D8050C539575DCCC2BC71AB2C4C5E33DAE8FAFEFA5F312E2AAE79A4FED484"
VV3_INDIVIDUAL_FULL_MASTERY_PAGE_SHA256 = "9E18B5501456663F7328B23FDFA3E81CE2DA21BE04F1EFD8FCEFAB88EA5C5EBA"
VV3_INDIVIDUAL_FULL_MASTERY_PARENT_SHA256 = {
    "collection_progression": "22456EEE7525066A1125EE7FA92E4EFC71CAACD81056D290EC357226889031A3",
    "immediate_fixed": "1FC6CEFF644928B6EFB4802E8E26D2FE2098AAEA2233D2F00AB59E9113BB9225",
}
VV3_INDIVIDUAL_FULL_MASTERY_OUTPUT_SHA256 = {
    "collection_progression": "41557E64785F68A4D209C863FF6C973D4266F48726F8886A99604052474B8CB1",
    "immediate_fixed": "D824FF8AA33A56C14451B9C27FD7475994DB52CED3B7D0EF77E4A74042DAB8CC",
}
VV3_STOCK_ONLY_UPGRADE_IDS = frozenset(
    {
        "vv3_enable_origins_exclusive_features",
        "vv3_enable_origins_exclusive_features_full_mastery_candidate",
        "vv3_full_mastery_all_stage_a_candidate",
        VV3_INDIVIDUAL_FULL_MASTERY_CANDIDATE_ID,
    }
)
VV3_INDIVIDUAL_RUNNING_CANDIDATE_ID = "vv3_individual_grant_running_candidate"
VV3_INDIVIDUAL_RUNNING_CANDIDATE_PATHS = {
    "manifest": ROOT / "data" / "candidates" / "vv3_individual_grant_running_candidate.json",
    "map": ROOT / "data" / "candidates" / "vv3_individual_grant_running_candidate_map.json",
}
VV3_INDIVIDUAL_RUNNING_MANIFEST_SHA256 = "A3C526AEEFD719B15F6C6CF1422EEF43D342F7B85D55F0C232675B3BE88483E4"
VV3_INDIVIDUAL_RUNNING_MAP_SHA256 = "00C7B9C1DB59E6B36C945551CC40A347C4D302917A6677EE1EDE14F26142F362"
VV3_INDIVIDUAL_RUNNING_SOURCE_COMMIT = "9574f488eefb97bd6320259f301beb87266072f8"
VV3_INDIVIDUAL_RUNNING_IMPLEMENTATION_COMMIT = "a35bee6ed91fb3f105424dca5e3283ce85e01894"
VV3_INDIVIDUAL_RUNNING_ACCEPTANCE_STATUS = (
    "WITHDRAWN; historical Likes-only helper cannot inspect or clear Running Dislikes; revised candidate pending native recertification"
)
VV3_INDIVIDUAL_RUNNING_RENDERED_SHA256 = {
    "collection_progression": "3644A56FE17F843DB67662E4309C3C2B41AE7ADD5FDD60EF2B6789DE2BA15FDC",
    "immediate_fixed": "059230146E8CC36E06E5473AE187D081E337DB90638B227FBA799B9C82B58C1C",
}
VV3_INDIVIDUAL_RUNNING_PINS = {
    "stock": "8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503",
    "collection_pre_running": "6B6FCF33C21B5ED9323F8BBE4C677EF12BA4653E775178DCDF8E77049B2F57A8",
    "immediate_pre_running": "92C5EF70512F57CBD990301E6918DE1BE002823C31CFB4C638D4E0F141BE7514",
    "full_mastery_page": "2DAE85AE4077C23C2C7C39F64B5BA944740F765AC8E24FBB097B0BF28A720DF6",
    "origins_payload": "77BF4DB93204AF1212A6335AF624642068A8B8560F1D78D59E2E07FBF4751F69",
    "hook": "DB0F47AADB04629EB6FD5966547F11CF32A7DC445E8D8641621925B76C816DA1",
    "owned_before": "7B4FC1A8DBE6B6121F16ADA516E2AC27E02964716BACEA5FB7D07CF30595948E",
    "owned_after": "76339C8FFBE0FF92F3F1EB2CC27A4E0600E33DCC936716DA94BBB0BD5D1AB050",
    "helper": "B03DCCF47903326E95A192A8458FD504E80B5D592784072D47525C217202B544",
    "strings": "52CB94EFF2FAC50C91B0C4CDF8D3CC973348F5ECE6BC3BAA0B74307FC1ACDC50",
}
VV3_INDIVIDUAL_RUNNING_HELPER_LENGTH = 0x271
VV3_INDIVIDUAL_RUNNING_STRINGS_LENGTH = 0x2E7
VV3_INDIVIDUAL_RUNNING_OWNED_LENGTH = 0x700
VV3_INDIVIDUAL_RUNNING_STACK_FRAME = {
    "saved_message_box": "-0x10",
    "selected_index": "-0x14",
    "record": "-0x18",
    "first_empty_like": "-0x1C",
    "snapshot": ["-0x20", "-0x24", "-0x28"],
    "local_allocation": "0x1C",
}
VV3_INDIVIDUAL_RUNNING_BLOB_LAYOUT = {
    "helper_offset": "0x0",
    "helper_length": "0x271",
    "strings_offset": "0x400",
    "strings_length": "0x2E7",
    "tail_offset": "0x6E7",
    "tail_length": "0x19",
}
VV3_INDIVIDUAL_RUNNING_FEATURE_OWNED_RANGES = [
    {
        "raw_offset": "0xA38C3",
        "length": 5,
        "purpose": "candidate command-2 detour",
    },
    {
        "raw_offset": "0xCB900",
        "length": 1792,
        "purpose": "candidate-owned .vv3fm helper/string region",
    },
]
VV3_INDIVIDUAL_RUNNING_CHECKSUM_PINS = {
    "collection_progression": {
        "pre": "E9AC0D00",
        "candidate": "93790D00",
    },
    "immediate_fixed": {
        "pre": "E8EE0C00",
        "candidate": "91BB0D00",
    },
}
VV3_INDIVIDUAL_RUNNING_MUTATION_ACCOUNTING_RULE = (
    "The two candidate-owned feature ranges plus raw 0x160..0x163 PE checksum "
    "are the three physical accounting ranges; every other byte is identical "
    "to the certified pre-Running image."
)
VV3_INDIVIDUAL_RUNNING_RESULT_MESSAGES = {
    "no_charge_suffix": "No tech points have been deducted.",
    "distinct": [
        "already_running",
        "no_empty_like",
        "invalid_selection",
        "selection_changed",
        "likes_changed",
        "insufficient_funds",
        "canceled",
        "write_verification_failure",
    ],
    "aliases": {"inactive_or_dead": "invalid_selection"},
    "invalid_selection_text": (
        "No valid living villager is selected.\r\n"
        "No tech points have been deducted."
    ),
    "success": "Running was granted.",
}
VV3_INDIVIDUAL_RUNNING_TRANSACTION_CONTRACT = {
    "command": 2,
    "price": 40_000,
    "action": "Buy",
    "repeatable": True,
    "ownership": None,
    "remove": False,
    "record_bound": 150,
    "stack_frame": VV3_INDIVIDUAL_RUNNING_STACK_FRAME,
    "canonical_blob_layout": VV3_INDIVIDUAL_RUNNING_BLOB_LAYOUT,
    "selection": {
        "manager_getter": "sub_428B60",
        "selected_index_offset": "0x12FC0",
        "validator": "sub_45EE60 with ECX=0x59E110",
        "resolver": "sub_45C840 with ECX=0x59E110",
        "same_index_required_after_confirmation": True,
    },
    "eligibility": ["signed index 0..149", "signed health +0xE78 > 0"],
    "likes": {
        "offsets": ["0xFB4", "0xFB8", "0xFBC"],
        "running": 38,
        "empty": -1,
    },
    "dislikes": {"read": False, "write": False, "storage_never_touched": True},
    "passes": [
        "complete initial three-DWORD Like snapshot/scan",
        "funds >= 40000",
        "OK/Cancel",
        "fresh singleton/index/record",
        "complete second scan and exact snapshot comparison",
        "fresh funds check",
        "verified single first-empty write of 38",
        "one native deduction",
    ],
    "deduction": {
        "receiver": "ECX=0x582644",
        "delta": -40_000,
        "writer": "sub_427130",
        "calls": 1,
    },
    "process_fault_limit": (
        "a process fault remains possible after verified slot write and before "
        "native deduction; no rollback atomicity is claimed"
    ),
}

VV3_FULL_HEAL_CANDIDATE_ID = "vv3_full_heal_cure_all_candidate"
VV3_FULL_HEAL_CANDIDATE_PATHS = {
    "manifest": ROOT / "data" / "candidates" / "vv3_full_heal_cure_all_candidate.json",
    "map": ROOT / "data" / "candidates" / "vv3_full_heal_cure_all_candidate_map.json",
}
VV3_FULL_HEAL_MANIFEST_SHA256 = "3600D697F595B57212B6316C55907C5261D103A0E6A4AD47578B524B5CECB1D0"
VV3_FULL_HEAL_MAP_SHA256 = "BF39F257BB52A9C0EB55D60D8BB03055C5141271123D68264CD44001E85717BB"
VV3_FULL_HEAL_STOCK_SHA256 = "8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503"
VV3_FULL_HEAL_BASE_DLL_PATH = ROOT / "data" / "candidates" / "VVFP VV3 Full Mastery Candidate.dll"
VV3_FULL_HEAL_DLL_PATH = ROOT / "data" / "candidates" / "VVFP VV3 Full Heal Candidate.dll"
VV3_FULL_HEAL_BASE_DLL_SHA256 = "35FB96199E745C7D8054FF6A12851B9E09225E3E41D0CE04012604E74968C0D5"
VV3_FULL_HEAL_DLL_SHA256 = "9F866CB6F92C745CD2AA7009AEC4EB70FA5521EFF0C8F7BABE2058BB4D2F8533"
VV3_FULL_HEAL_DLL_SIZE = 298496
VV3_FULL_HEAL_PRE_CURE_RENDERED_SHA256 = {
    "collection_progression": "3644A56FE17F843DB67662E4309C3C2B41AE7ADD5FDD60EF2B6789DE2BA15FDC",
    "immediate_fixed": "059230146E8CC36E06E5473AE187D081E337DB90638B227FBA799B9C82B58C1C",
}
VV3_FULL_HEAL_HOOK_BEFORE = bytes.fromhex("8B049D543F4A00")
VV3_FULL_HEAL_HOOK_AFTER = bytes.fromhex("E90CCA23009090")
VV3_FULL_HEAL_CAVE_OFFSET = "0xCC000"
VV3_FULL_HEAL_CAVE_OFFSET_INT = 0xCC000
VV3_FULL_HEAL_CAVE_LENGTH = 0x1000
VV3_FULL_HEAL_LEGACY_START = 0x7B664
VV3_FULL_HEAL_LEGACY_END_OFFSET = 0x7B721
VV3_FULL_HEAL_LEGACY_END = "0x7B721"
VV3_FULL_HEAL_CAVE_SHA256 = "E0C7B25F6EEA07D3C0986FA7F7FC919AC63D09DE2518C2B768C856F390DEE738"
VV3_FULL_HEAL_HELPER_SHA256 = "D17F982937FE07B4E4D7EFAC06466ACD05BE0E286673DFA4E19CA8178CC8BDC5"
VV3_FULL_HEAL_HELPER_LENGTH = 0x42B
VV3_FULL_HEAL_STRINGS_OFFSET = 0x800
VV3_FULL_HEAL_STRINGS_LENGTH = 0x4E7
VV3_FULL_HEAL_TAIL_ZERO_LENGTH = 0x319
VV3_FULL_HEAL_COMPOSED_PARENT_HELPER_SHA256 = "CFF1AAA9111728F003621FF662F100940C2F978943F5E69CC64180EA5DE63F7D"
VV3_FULL_HEAL_STOCK_CURE_CAVE_PREIMAGE_SHA256 = "7B4FC1A8DBE6B6121F16ADA516E2AC27E02964716BACEA5FB7D07CF30595948E"
VV3_FULL_HEAL_LEGACY_PRESERVED_RANGE_SHA256 = VV3_FULL_HEAL_COMPOSED_PARENT_HELPER_SHA256
VV3_FULL_HEAL_STOCK_ZERO_PREIMAGE_LEGACY_RANGE_SHA256 = "06EA118EDADD836A02B202C05BC7E47356B57E28C01EDF1DAD6CC4CF90C662E2"
VV3_FULL_HEAL_PROVENANCE = {
    "design_source_commit": "64c1266503c49ba1456f6294683a1f6773eba5d6",
    "implementation_parent_commit": "38510cc21b7cd322a52fbabc936794dfc8601ccc",
    "implementation_commit": "49595a75b65cd0561811593ba19825239ec97dde",
    "metadata_commit": None,
    "audit_source_test_commit": "e2f1a466b61392d161a0df2fbf8da94fc05ee4ca",
    "metadata_status": "enabled/catalog-visible for certified stock modes; D209/C213 independent static GO; runtime/player validation pending",
}
VV3_FULL_HEAL_STATIC_ACCEPTANCE = {
    "commit": None,
    "status": "D209 and C213 independent static GO; runtime/player validation pending",
    "reports": ["D209", "C213"],
    "audit_commit": None,
    "acceptance_commit": None,
}
VV3_FULL_HEAL_IMPLEMENTATION_STATUS = "enabled/catalog-visible for certified stock modes; D209/C213 independent static GO; runtime/player validation pending"
VV3_FULL_HEAL_HELPER_INSTRUCTION_COUNT = 269
VV3_FULL_HEAL_HELPER_EPILOGUE_OFFSET = "0x41F"
VV3_FULL_HEAL_INTERNAL_TARGET_OFFSETS = [
    "0xC2", "0xF8", "0x107", "0x12B", "0x1A0", "0x1E4", "0x1EE",
    "0x222", "0x264", "0x297", "0x2D8", "0x319", "0x328", "0x335",
    "0x3AD", "0x3B9", "0x3C0", "0x3C7", "0x3CE", "0x3D5", "0x3DC",
    "0x3E3", "0x3EA", "0x415", "0x41F",
]
VV3_FULL_HEAL_TRANSACTION = {
    "command": 5,
    "price": 30000,
    "action": "Buy",
    "repeatable": True,
    "ownership": None,
    "remove": False,
}
VV3_FULL_HEAL_MESSAGES = {
    "label": "Full Heal / Cure All",
    "no_charge_suffix": "No tech points have been deducted.",
    "confirm_format": "Full Heal / Cure All will clear sickness from %u eligible villagers and restore %u partial-health villagers for 30,000 tech points?\r\nPress OK to confirm, or Cancel.",
    "success_format": "Full Heal / Cure All completed: %u sickness clears and %u full-health restores were verified.",
    "failure_format": "Full Heal / Cure All failed after %u sickness clears and %u full-health restores were verified.\r\nNo tech points have been deducted.\r\nIf native writes begin and a later write or postverification fails, earlier verified health, sickness, or People Cured effects may remain. No tech points are deducted on that failure, but complete rollback of native side effects is not claimed.",
    "confirm_price": "30,000",
}
VV3_FULL_HEAL_PARTIAL_FAILURE_DISCLOSURE = (
    "If native writes begin and a later write or postverification fails, earlier "
    "verified health, sickness, or People Cured effects may remain. No tech points "
    "are deducted on that failure, but complete rollback of native side effects is "
    "not claimed."
)
VV3_FULL_HEAL_HEALTH_SETTER = {
    "function": "0x462670",
    "ecx": "full_record+0xE6C",
    "push_reason": -1,
    "push_desired": 100,
    "forbidden": "full_record+0xA0",
}
VV3_FULL_HEAL_RESULT_HELPER = {"va": "0x4A3400", "ret": 8, "caller_stack_cleanup": False}
VV3_FULL_HEAL_FORBIDDEN_ROUTES = {
    "legacy_cure_entry": "0x47B664",
    "legacy_text_helper": "0x40D8A0",
    "e94_status_filter": False,
}
VV3_FULL_HEAL_ELIGIBILITY = {
    "proved_predicate": "D182: signed health +0xE78 > 0 after active +0xF10 != 0",
    "active_offset": "0xF10",
    "active_width": "byte",
    "health_offset": "0xE78",
    "non_skeleton": "D182 current active/living predicate; no +0xE94/status filter",
    "record_count": 150,
    "stride": "0x1F8C",
}
VV3_FULL_HEAL_SICKNESS = {
    "offset": "0xE89",
    "clear_value": 0,
    "people_cured_offset": "0x4FC",
    "increment_per_verified_sick_record": True,
    "health_only_does_not_increment": True,
    "manager_acquired_before_clear": True,
    "loop_counter_preserved_across_manager_getter": True,
    "mutation_loop_counter_local": "[ebp-0x30]",
    "mutation_loop_counter_bound": 150,
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
}
VV3_FULL_HEAL_RECORD_ZERO_RESOLVER = {
    "function": "0x45C840",
    "manager_ecx": "0x59E110",
    "index": 0,
    "initial_and_after_confirmation": True,
    "constant_pool_substitute": False,
}
VV3_FULL_HEAL_MESSAGEBOX_RESOLUTION = {
    "load_library_iat": "0x47C124",
    "get_proc_address_iat": "0x47C128",
    "module": "USER32.dll",
    "procedure": "MessageBoxA",
    "formatter_procedure": "wsprintfA",
    "formatter_resolution": "direct imported USER32!wsprintfA at IAT 0x47C3A0",
    "formatter_saved_local": "[ebp-0x14]",
    "format_buffer": "[ebp-0x6E0..ebp-0x4E1]",
    "format_buffer_size": 512,
    "saved_local": "[ebp-0x10]",
    "stdcall_stack_cleanup": "callee",
}
VV3_FULL_HEAL_MUTATION_ACCOUNTING = {
    "physical_ranges": [
        {"offset": "0xA35EF", "length": 7, "purpose": "command-5 hook"},
        {"offset": "0x10E", "length": 2, "purpose": "PE section-count update"},
        {"offset": "0x158", "length": 4, "purpose": "PE SizeOfImage update"},
        {"offset": "0x2F0", "length": 40, "purpose": "candidate-owned .vv3hc section header"},
        {"offset": "0xCC000", "length": 0x1000, "purpose": "candidate-owned .vv3hc RX page"},
        {"offset": "0x160", "length": 4, "purpose": "PE checksum recomputation"},
    ],
    "feature_owned_ranges": ["0xA35EF..0xA35F5", "0x2F0..0x317", "0xCC000..0xCCFFF"],
    "physical_range_count": 6,
    "feature_owned_range_count": 3,
    "every_other_byte_identical": True,
    "rendered_sha256": {
        "collection_progression": "15D58F10FEC11D1E3BE0066A9E7109B08EF3AAD2E8E20E0056E41597277ABEEB",
        "immediate_fixed": "3142012C853615F513E009E4D22AA544C14D72F6ADC960E51E676A8636A571C4",
    },
    "uninstall_sha256": {
        "collection_progression": "3644A56FE17F843DB67662E4309C3C2B41AE7ADD5FDD60EF2B6789DE2BA15FDC",
        "immediate_fixed": "059230146E8CC36E06E5473AE187D081E337DB90638B227FBA799B9C82B58C1C",
    },
    "checksum_offset": "0x160",
    "checksum_transitions": {
        "collection_progression": {"before": "93790D00", "after": "BB270D00"},
        "immediate_fixed": {"before": "91BB0D00", "after": "B9690D00"},
    },
    "section_header": {"name": ".vv3hc", "raw_offset": "0x2F0", "raw_start": "0xCC000", "rva": "0x2E0000", "va": "0x6E0000", "size": "0x1000", "section_count_before": 6, "section_count_after": 7, "size_of_image_before": "0x2E0000", "size_of_image_after": "0x2E1000"},
}
VV3_FULL_HEAL_RENDERED_SHA256 = {
    "collection_progression": "15D58F10FEC11D1E3BE0066A9E7109B08EF3AAD2E8E20E0056E41597277ABEEB",
    "immediate_fixed": "3142012C853615F513E009E4D22AA544C14D72F6ADC960E51E676A8636A571C4",
}
VV3_FULL_HEAL_CHECKSUM_TRANSITIONS = {
    "collection_progression": {"before": "93790D00", "after": "BB270D00"},
    "immediate_fixed": {"before": "91BB0D00", "after": "B9690D00"},
}
VV3_FULL_HEAL_PRE_CANDIDATE_CHECKSUM = {
    "collection_progression": "93790D00",
    "immediate_fixed": "91BB0D00",
}
VV3_FULL_HEAL_NON5_SHIM = bytes.fromhex("8B049D543F4A00E93D32DCFF")


def _strict_manifest_value_equal(actual: Any, expected: Any) -> bool:
    """Compare JSON values without Python's bool/int coercion or key drift."""

    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        if list(actual.keys()) != list(expected.keys()):
            return False
        return all(
            _strict_manifest_value_equal(actual[key], expected[key])
            for key in expected
        )
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            _strict_manifest_value_equal(left, right)
            for left, right in zip(actual, expected, strict=True)
        )
    return actual == expected


VV2_FULL_MASTERY_CANDIDATE_PATHS = {
    "manifest": ROOT / "data" / "candidates" / "vv2_full_mastery_all_candidate.json",
    "map": ROOT / "data" / "candidates" / "vv2_full_mastery_all_candidate_map.json",
    "dll": ROOT / "data" / "candidates" / "VVFP VV2 Full Mastery Candidate.dll",
}
VV2_FULL_MASTERY_MANIFEST_SHA256 = "41CC8B5ADEAF702B1ACC38C832EADEEBF9B7FB23DA23A8A6E6328690F121A53C"
VV2_FULL_MASTERY_MAP_SHA256 = "F93FC7C11D2306A3AA5DCC44EAC26785BC26BD86D46FCFAE51252E6E13FEE8C8"
VV2_FULL_MASTERY_CERTIFIED_SHA256 = {
    "source": "46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677",
    "section": "D84DA1DF60C9AC160312C5AC0943663CA16DA909935A96FA3E1B9D723462B9A1",
    "entry": "505DCF6A0891E640FA73B41A0CBC6868B35FF1C9D5F2A598A6C067004F78A58F",
    "walker": "E67F5F34AEB66A953B5B2A77FD6A5EA00B907D26B61A25A0C132F62C713C98DD",
    "telemetry": "8036B4818E39533B3F5BEBF1EC38A94A71B05EE8BE72FB1EFA0B9AD72789B907",
    "confirmation": "8868C87F2B66AD9D69F1DC7A08A469E5C5C478727955A5E1E4F6DA4EEB306B2C",
    "menu_resolver": "38B1AECEABF47C01B945AB438954C2489C83DDC3E5C573E81321F94C2E360B4F",
    "result_preflight": "C994315AD623EE3E3001193735C435FBC9A721EDB5A0A521E6069421C63D60E5",
    "result_resolver": "B7002D2C62F475914719A8A99B65BEC7580B7026E7FB3A991046CBCC77FB8D0B",
    "dll": "1324EDFB83ABA755AFF6410D71DD668F4860127CD67A952722FDE5DD2FDC92C2",
}
VV2_FULL_MASTERY_STATIC_ACCEPTANCE = {
    "status": "GO",
    "evidence_commit": "13f4341201fa7757d23f77c5c17602bbe7bbf21d",
    "implementation_commit": "895340333d55273e599f2dce5ab0db42cbc6d0ab",
    "runtime_player_status": "pending",
    "allowed_modes": ["collection_progression", "immediate_fixed"],
    "rejected_modes": [
        "experimental_expanded_256",
        "experimental_expanded_256_progression",
    ],
    "source_sha256": VV2_FULL_MASTERY_CERTIFIED_SHA256["source"],
    "section_sha256": VV2_FULL_MASTERY_CERTIFIED_SHA256["section"],
    "entry_sha256": VV2_FULL_MASTERY_CERTIFIED_SHA256["entry"],
    "walker_sha256": VV2_FULL_MASTERY_CERTIFIED_SHA256["walker"],
    "telemetry_sha256": VV2_FULL_MASTERY_CERTIFIED_SHA256["telemetry"],
    "confirmation_sha256": VV2_FULL_MASTERY_CERTIFIED_SHA256["confirmation"],
    "menu_resolver_sha256": VV2_FULL_MASTERY_CERTIFIED_SHA256["menu_resolver"],
    "result_preflight_sha256": VV2_FULL_MASTERY_CERTIFIED_SHA256["result_preflight"],
    "result_resolver_sha256": VV2_FULL_MASTERY_CERTIFIED_SHA256["result_resolver"],
    "dll_sha256": VV2_FULL_MASTERY_CERTIFIED_SHA256["dll"],
    "dll_size": 109056,
    "stock_size": 724992,
    "collection_composition_sha256": "C7C0BEC312B6537B5F1DD692D2C90ED0D0963D6CE3A7F5271AF4A6C680B8ACBC",
    "immediate_composition_sha256": "6AEE09C69C3E7C1AD12284EA5B5A188AF05DA3D87AD6149545CEE65D896E6774",
    "rendered_candidates": {
        "collection_progression": {
            "candidate_sha256": "08F12344A5DE16832E5EFA22270300A1066EB94970359F432CEC723723055194",
            "baseline_sha256": "E87B41564B057598BBCB369BEDC9BB93016CC32F0D223AEE7C877FC6EBC5ADBA",
            "uninstall_target_sha256": "E87B41564B057598BBCB369BEDC9BB93016CC32F0D223AEE7C877FC6EBC5ADBA",
            "size": 733184,
        },
        "immediate_fixed": {
            "candidate_sha256": "21B927806BDB06942F8426BC68E89AB1B10E2E60CEEFC39FEEFDCC125886BE7C",
            "baseline_sha256": "9139A22A85D652878783EAEBCDD6275447B8C8AFA2B344862C25EF6DEBE36560",
            "uninstall_target_sha256": "9139A22A85D652878783EAEBCDD6275447B8C8AFA2B344862C25EF6DEBE36560",
            "size": 733184,
        },
    },
}
VV2_INDIVIDUAL_FULL_MASTERY_CANDIDATE_ID = "vv2_individual_full_mastery_candidate"
VV2_INDIVIDUAL_FULL_MASTERY_CANDIDATE_PATHS = {
    "manifest": ROOT / "data" / "candidates" / "vv2_individual_full_mastery_candidate.json",
    "map": ROOT / "data" / "candidates" / "vv2_individual_full_mastery_candidate_map.json",
}
VV2_INDIVIDUAL_FULL_MASTERY_MANIFEST_SHA256 = "D074D849160948C30BF063F71EF72381F9CD9CA249ADFE5CD18AB8074B6DAAF2"
VV2_INDIVIDUAL_FULL_MASTERY_MAP_SHA256 = "36362D1CE8AE0EE7DAAFBC491D11893302838F0930A22E8BC0C827D80CC77547"
VV2_INDIVIDUAL_FULL_MASTERY_EMITTED_SHA256 = {
    "detail_handler": "00C4EC217FB9A0483C797DBF9FEABAF210A3031DFE07610FBBA0ABBBC6E1EF37",
    "detail_constructor": "288A62BF9829CC5A013F31A2DE169629F9BD802BD61E17C4C8C2CE8A5CFA87F9",
    "helper": "D5403EC7BC9D1659C0A64E90E942B7183E5D2F72285B173F4DFFDA1ADB4A6E28",
    "strings": "6BCA29ACED630E8E82AB7E6D16A4C1D627FA91062390BC73C6C941474549946E",
}
VV2_INDIVIDUAL_FULL_MASTERY_CURRENT_PARENT_SHA256 = {
    "collection_progression": "1EF8F9A9D8C6336706943D37649D897C227408715940EE19CDBB8C6F4AFD63C3",
    "immediate_fixed": "A2F8F9B4DD2454A583096EE653E731235B17B608905E7808CFA15EF027B97042",
}
VV2_INDIVIDUAL_FULL_MASTERY_CURRENT_BASELINE_SHA256 = {
    "collection_progression": "B6A37FF5ECC60358988F222EB952E6710A1B351F175F178DECE74799428CB5E6",
    "immediate_fixed": "71BE2C0563159144C8D410AD11D14FC8F23FD767CB799C7C1763BEE534A8B0E3",
}
VV2_INDIVIDUAL_FULL_MASTERY_OUTPUT_SHA256 = {
    "collection_progression": "D8BEBC6BE0A31863FE88C4394DBB756B713B09B82695F41A928CAE381F63BA18",
    "immediate_fixed": "C6CD6F3E1F068708D9ACFB4FC51B94B5AE2F6C448C1183B34E70B5B97D4B8BE7",
}
VV1_FULL_MASTERY_CANDIDATE_PATHS = {
    "manifest": ROOT / "data" / "candidates" / "vv1_full_mastery_all_candidate.json",
    "map": ROOT / "data" / "candidates" / "vv1_full_mastery_all_candidate_map.json",
    "dll": ROOT / "data" / "candidates" / "VVFP VV1 Full Mastery Candidate.dll",
}
VV1_FULL_MASTERY_CERTIFIED_SHA256 = {
    "section": "F0EFEDF743A375F9A62FC1199809A0F2A5CF05CC749CE5A5DA5EA24BC28EABE7",
    "entry": "DB742B8C696A5D197D4985E49DE636C4E3E584BBC1B7E65132611E2FC4B42A31",
    "walker": "948C1B9E968FB5A8F957E33F6C344A1FF0DC25805BB97DB2D959129A4E2B8C9E",
    "confirmation": "39FBB3CA5B2C32C5566EA918C249D77718F2872AF871511EA23147C48AE6E779",
    "menu_resolver": "66A089D58C80B15DD4BB47DAC3B3ABC1DD5CF8969B9863D90BD084B462496C98",
    "result_resolver": "2945F92280B7A6E59E6F0B91F25A1FBD3C1D49789460D4C4CC094DCE873FA8E8",
    "dll": "4736E5EFB8F680E3B1F124D1920A9390D9F6427260E60743039FA80F8646CCB3",
    "source": "1EC790B927741081D5CE13A48FB76983A4FD4336EA08F89317872643760AF03D",
    "candidate": "C2C6070B11E56BD6B8BD183C9694E88DC6D576758926D18ACEFCD093CCF364B0",
    "active_origins": "5434C71C342B830A5896AFFB610A76C670578760BD33C6145882FA280F6406A3",
    "combined": "9B5CA9671558DE0A8CACB6E62AD98BA6C692522D253374DA74E52984B53FF230",
}
VV1_INDIVIDUAL_FULL_MASTERY_CANDIDATE_ID = "vv1_individual_full_mastery_candidate"
VV1_INDIVIDUAL_FULL_MASTERY_CANDIDATE_PATHS = {
    "manifest": ROOT / "data" / "candidates" / "vv1_individual_full_mastery_candidate.json",
    "map": ROOT / "data" / "candidates" / "vv1_individual_full_mastery_candidate_map.json",
}
VV1_INDIVIDUAL_FULL_MASTERY_MANIFEST_SHA256 = "A84C060B1C582C9CECD1402663341B676D2BABBAB8886D8A82451F55C94F421C"
VV1_INDIVIDUAL_FULL_MASTERY_MAP_SHA256 = "1E8F9519FEA915055D48434F54B3CA9DF7ECE9CC7990DD60831058F702E15B50"
VV1_INDIVIDUAL_FULL_MASTERY_PARENT_ARTIFACT_SHA256 = {
    "manifest": "D36E885F5137DBA453FD419D08D5A59EE7D1AA0402C4A3C28CACA7F1F3C6D76F",
    "map": "87A9BEA67932E153F7113EAA321FD757EAC3C184190297ADF1D0F578C191DCC0",
    "dll": "4736E5EFB8F680E3B1F124D1920A9390D9F6427260E60743039FA80F8646CCB3",
}
VV1_INDIVIDUAL_FULL_MASTERY_EMITTED_SHA256 = {
    "detail_handler": "2D003D26E9E7C6E40FF0AA417C2B4F6D1F5AA4FCC85EB9913AD23DF3520371A5",
    "detail_constructor": "52308A10D29BE194F4909ADDAA448401267689486C7CBDA4E19A577087464027",
    "helper": "B63199E47BAC8AAF725E22C517691D6D49D26DEDD3C039181655B6C05ECA9B94",
    "strings": "2352CCCAACE006D330F300616320BAA3B5A91FF287371E73E72E6B1ED9CC8449",
}
VV1_INDIVIDUAL_FULL_MASTERY_PARENT_SHA256 = {
    "collection_progression": "C2C6070B11E56BD6B8BD183C9694E88DC6D576758926D18ACEFCD093CCF364B0",
    "immediate_fixed": "C2C6070B11E56BD6B8BD183C9694E88DC6D576758926D18ACEFCD093CCF364B0",
}
VV1_INDIVIDUAL_FULL_MASTERY_BASELINE_SHA256 = {
    "collection_progression": "0F54C22C531FCE276EFBF5F0B4418C48B66CE314AA21872A9B2C5D459232EC7A",
    "immediate_fixed": "0F54C22C531FCE276EFBF5F0B4418C48B66CE314AA21872A9B2C5D459232EC7A",
}
VV1_INDIVIDUAL_FULL_MASTERY_OUTPUT_SHA256 = {
    "collection_progression": "B8E08A705680AA098E5989AA045E6F943D19CBFC0C61422E984F2F8FF940DC7A",
    "immediate_fixed": "B8E08A705680AA098E5989AA045E6F943D19CBFC0C61422E984F2F8FF940DC7A",
}
VV1_INDIVIDUAL_FULL_MASTERY_CONFLICTS = {
    "vv1_enable_origins_exclusive_features",
    "vv1_origins_village_wide_upgrades",
    "vv1_full_mastery_origins_composition",
}
VV4_FULL_MASTERY_CANDIDATE_PATHS = {
    "base": ROOT / "data" / "candidates" / "vv4_origins_full_mastery_base_candidate.json",
    "feature": ROOT / "data" / "candidates" / "vv4_full_mastery_all_candidate.json",
    "map": ROOT / "data" / "candidates" / "vv4_full_mastery_all_candidate_map.json",
    "dll": ROOT / "data" / "candidates" / "VVFP VV4 Full Mastery Candidate.dll",
}
VV4_FULL_MASTERY_CERTIFIED_SHA256 = {
    "entry": "CFCDE13267A62C824756748A7B639937AD4F125E733F615C555861338C2702A5",
    "walker": "F8268B904E73B79EE686BE6A4E8FCFA8A54C59E08E8D5CE329900D78DED05155",
    "confirmation": "DCB30F80D0442F289F030CCD2E712A05605469819E4777E3739918A718B55B97",
    "stock_page": "FD72C661B533117BF38D69E7EB855250A93927C831C265226930794C1EFDDB62",
    "expanded_page": "37E43800F7EB3188F367EC6F8DCFA93674F6CA97A8682F6B35038BF0DA7A9BE8",
    "dll": "4E1A83683A875EFE6F67116CDD862927BE1ABCB17DB7AE18143E58E98EAD01E7",
}
VV4_FULL_MASTERY_D19_COMMIT = "8182c235548bc92f304e5571ed61ada3c5abfa4b"
VV4_FULL_MASTERY_D21_COMMIT = "3ba125b2107da4f86f9b70ab5b94206bef7803f5"
VV4_FULL_MASTERY_D19_HASHES = {
    "native_factory": "58E21A9597EB6ABF6949A1E607C3B607FABAF1AE5D280D899A062F5D021ACE21",
    "helper": "C7379FB1AFDDD44F06CF48FAEED14C1701D796F5FC2568E10745337DADE13DB1",
    "tech_constructor": "1D710074D6F5717A420646B2DCEE2BCC351754B4DC0CCFB5A32F586E2E258BDC",
    "detail_constructor": "AC2A88CBD0B7805941EA34261D765F4A727187B35B5443BFB7CDEA8DF43A7E8C",
    "command7_slot": "023CF384A52CB6A6A49511B8B069B952718DC70E771FEE15CAC8A0777FB5F6DE",
    "cure": "2BB7A32344293DCACB4D0359818C6839AC1FBBAEE8F9E3D00DB59C274238D726",
    "dll": "4E1A83683A875EFE6F67116CDD862927BE1ABCB17DB7AE18143E58E98EAD01E7",
}
VV4_FULL_HEAL_CANDIDATE_ID = "vv4_full_heal_cure_all_candidate"
VV4_FULL_HEAL_CANDIDATE_PATHS = {
    "manifest": ROOT / "data" / "candidates" / "vv4_full_heal_cure_all_candidate.json",
    "map": ROOT / "data" / "candidates" / "vv4_full_heal_cure_all_candidate_map.json",
}
VV4_FULL_HEAL_STOCK_SHA256 = "6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220"
VV4_FULL_HEAL_PARENT_PAGE_SHA256 = "FD72C661B533117BF38D69E7EB855250A93927C831C265226930794C1EFDDB62"
VV4_FULL_HEAL_PARENT_DLL_SHA256 = "4E1A83683A875EFE6F67116CDD862927BE1ABCB17DB7AE18143E58E98EAD01E7"
VV4_FULL_HEAL_PARENT_COLLECTION_SHA256 = "D0F90C4666A1E2189044B6F093692E4B56C8F379BC6A4953BBB9B74D997A8092"
VV4_FULL_HEAL_PARENT_IMMEDIATE_SHA256 = "F803918BE5B356F4A3C6D12A5098594E904CDE00C87E1D14901F9CCE5107AECD"
VV4_FULL_HEAL_PARENT_DEPENDENCIES = (
    "vv4_complete_scales_golden_fish",
    "vv4_enable_origins_exclusive_features",
    "vv4_full_mastery_all_stage_a_candidate",
    "vv4_write_village_statistics",
)
VV4_FULL_HEAL_MANIFEST_SHA256 = "02B4F62D2CDE2388E1D7CF159575A5868A754E11E77BFBBE96D49C4EC2E6663D"
VV4_FULL_HEAL_MAP_SHA256 = "8F5C1D529792C3926A40DCF69167CF0F483DBF06C45C1AC0C1F91A32EE8253FC"
VV4_FULL_HEAL_PROTECTED_RANGE_END_INCLUSIVE = True
VV4_FULL_HEAL_ENUMERATION = (
    "resolve every index 0..149 through ECX=0x50E568; push index; "
    "call 0x466040; ret 4; never walk a cached base"
)
VV4_FULL_MASTERY_LEGACY_ASSET_KEYS = frozenset({
    "destination", "path", "png_sha256", "rgba_sha256", "grid",
    "frame_width", "frame_count", "frame_order", "identical_frames",
    "format", "source", "crop_xywh", "crop_rgba_sha256",
})
VV4_FULL_MASTERY_LEGACY_STATIC_ASSET_KEYS = frozenset({
    "destination", "path", "png_sha256", "rgba_sha256", "grid",
    "frame_width", "frame_count", "frame_order", "identical_frames",
    "format", "source", "crop_xywh", "crop_rgba_sha256",
})
VV5_FULL_MASTERY_CANDIDATE_PATHS = {
    "base": ROOT / "data" / "candidates" / "vv5_origins_full_mastery_base_candidate.json",
    "feature": ROOT / "data" / "candidates" / "vv5_full_mastery_all_candidate.json",
    "map": ROOT / "data" / "candidates" / "vv5_full_mastery_all_candidate_map.json",
    "dll": ROOT / "data" / "candidates" / "VVFP VV5 Full Mastery Candidate.dll",
    "cure_dll": ROOT / "data" / "candidates" / "VVFP VV5 Cure Containment Projection.dll",
    "provenance_asset": ROOT / "assets" / "candidates" / "vv5_full_mastery" / "provenance" / "btn_trophies.png",
}
VV5_FULL_MASTERY_ACCEPTANCE_COMMIT = "48955b5f19da5d4279887a4c1b71250a63ac9ade"
VV5_FULL_MASTERY_CERTIFIED_SHA256 = {
    "stock_entry": "3931DE449CDC334B9BD93D0FCF813CC8D44885E7DA430D79C22234F4B3DB1BBB",
    "stock_walker": "7466674FBC225EE898E10086B355509BF6AAB2E2D9024C8E3FCE4D0833CADAB8",
    "stock_confirmation": "234E2D9320A75D6B95DED0A682F13087294AE5E48F126DF30269C6F37653C18F",
    "stock_page": "9B191EE433100638E2C45AD6BC14B65C73C05BFC02DF6553F892F570CD2FC586",
    "dll": "29927CECB448B64944E18E2BA11893DC84C91B39241FBB2549FC2A464E0BE2ED",
    "provenance_asset": "F39E94CBDF24776631D803D1218EFCCDE555081C9C8C644DD073B75EC7DD2095",
}
VV5_FULL_MASTERY_CURE_COMPANION_SHA256 = "A1C55063B548F195B9ECDA492E1799D35EBA5437862353D96BE780D9FCC2E1C8"
VV5_FULL_MASTERY_RENDERED_SHA256 = {
    "collection_progression": "857E22D7C361B802508BF789C3CC486E42E76021F5AA579BB1D16CC6E0D017A0",
    "immediate_fixed": "E93822F752F730ECB751EBAA87021194C992984721B4370FF0015D5FC4BB2E9A",
}
VV5_FULL_MASTERY_CONFIRMATION_SHA256 = {
    "individual_routine": "234E2D9320A75D6B95DED0A682F13087294AE5E48F126DF30269C6F37653C18F",
    "village_routine": "2C392F952854EB485091199AC96AAC0B1C5683B7061D9267650411868926D763",
    "individual_string": "60C9A875AFC93174041B78B3A185B4E1BAE468404F20C3AFC1CF1F127802FD3C",
    "village_string": "56BC07733ED0F93F211BA0D1887502F8A45E03A4187B8C17067F32FF87117D46",
}
VV5_TASK9_PATHS = {
    "manifest": ROOT / "data" / "vv5_task9_native_actions.json",
    "map": ROOT / "data" / "candidates" / "vv5_task9_native_actions_map.json",
    "dll": ROOT / "data" / "candidates" / "VVFP VV5 Task9 Origins Icons.dll",
}
VV5_TASK9_SOURCE_TEXT_SHA256 = {
    "manifest": "A713EA5C89E94A00CB0E25F2851B2D8284416DED9FBE78ACEF8DFF33F76FF3E9",
    "map": "73724CD946B99B94E850EDF13C041E3182752E1689EB1B125733F9FA9A5E7636",
}
VV5_TASK9_DLL_SHA256 = "B402ED8316CD6EB2C43B056848E622DC0924188C81C683F5E2813466AF8045D0"
VV5_TASK9_PAGE_SHA256 = {
    "collection_progression": "ED942C43F5916D474A98D250D0493B3151968770BFB8919A758BA6924096FA9B",
    "immediate_fixed": "ED942C43F5916D474A98D250D0493B3151968770BFB8919A758BA6924096FA9B",
    "experimental_expanded_256": "03948795C056B67195B6528FE3CDA01BDF1DE16537C22C00947B7E68B490F0CB",
    "experimental_expanded_256_progression": "03948795C056B67195B6528FE3CDA01BDF1DE16537C22C00947B7E68B490F0CB",
}
VV5_TASK9_ACTIVE_SOURCE_TEXT_SHA256 = "BEE09E5319A394213AF605CEB60F06ED2CAD1E54397C073176AA52E991013ADD"
VV5_TASK9_TASK8_SOURCE_TEXT_SHA256 = "090ED9CA074F02F9321B2F8E0C470FD0AF18B235231DA94B6D38293360BC9510"
VV5_TASK9_ATOMIC_CORE_COMMIT = "c4e5fe76d1de258d5d4baeac77cbea842b206cd7"
VV5_TASK9_ATOMIC_SOURCE_TEXT_SHA256 = {
    "atomic_generator": "0424B3B56CB4093176A8B429472FCDF04043CBFC22424EBBDE37058EA1A8F72E",
    "atomic_contract": "1B7068D0679CA896706AA201D27726AF612FD167C0406C5D509774E40728F6A6",
}
EXPANDED_TIME_WARP_IDS = {
    "vv3": "vv3_expanded_256_time_warp",
    "vv4": "vv4_expanded_256_time_warp",
    "vv5": "vv5_expanded_256_time_warp",
}
EXPANDED_TIME_WARP_PATHS = {
    "vv3": {
        "manifest": ROOT / "data" / "vv3_expanded_time_warp.json",
        "map": ROOT / "data" / "candidates" / "vv3_expanded_time_warp_map.json",
    },
    "vv4": {
        "manifest": ROOT / "data" / "vv4_expanded_time_warp.json",
        "map": ROOT / "data" / "candidates" / "vv4_expanded_time_warp_map.json",
    },
    "vv5": {
        "manifest": ROOT / "data" / "vv5_expanded_time_warp.json",
        "map": ROOT / "data" / "candidates" / "vv5_expanded_time_warp_map.json",
    },
}
EXPANDED_TIME_WARP_SOURCE_TEXT_SHA256 = {
    "vv3_builder": "58C3586D773D0EF8E30562B54F01A262228C6154C32CCEF0D5FEF44347D72913",
    "builder": "AE645BAEE009D4BFFD7CBECD241B7AF52D39C852C3708D86646879ABF3AF973A",
    "task9_builder": "9298C6A98A56769C0EE50B9CEDA72860A5D3DC606802F4A60F627FD32F099507",
}
EXPANDED_TIME_WARP_ARTIFACT_SHA256 = {
    "vv3": {
        "manifest": "4859537CF25D14076D670CDD60FC0F2A1C939225174EB1A373AB9400991D7E02",
        "map": "BA2443FF8755C20715921354188F2A7A6C18ABF8F307D51045DA382A3AE1418E",
        "core": "6658B41980D5829CC0607AEFBC3AECBE92E0D7ECED2023C9B20C9962CF282356",
    },
    "vv4": {
        "manifest": "FE447BC640FEA16270E85914AD8B732845107ADA99CF45A8056F5870432CEFAC",
        "map": "97A5ED12969DA80A7EF06A950DC4BB2BECC40759E8C9BEAF6EF3B8A7C36D9E4E",
    },
    "vv5": {
        "manifest": "E5C54C6651A10B13B1F6F42A34CA033135EC7C4150C6BB362D9ED95341C81710",
        "map": "470A6EA4B5C65D738477AE310203BC387C6663145C28C1A3757D0AFACC533D29",
    },
}
VV5_TASK9_EXPANDED_HOOK = {
    "offset": "0x415F0",
    "before": "E90B0A3700909090",
    "after": "E90B9A4A00909090",
    "purpose": "post-relocation: bind the Task9 Tech-screen command-13 hook to relocated Expanded .shr without changing C342",
}
VV5_TASK9_CROSS_SECTION_HOOKS = {
    "0x1890F": {"stock_target": "0x7B2180", "expanded_target": "0x8EB180", "expanded_policy": "frozen_c342"},
    "0x1EB6F": {"stock_target": "0x7B2B00", "expanded_target": "0x8EBB00", "expanded_policy": "native_override_preserved"},
    "0x237B0": {"stock_target": "0x7B2A00", "expanded_target": "0x8EBA00", "expanded_policy": "native_override_preserved"},
    "0x40A24": {"stock_target": "0x7B2040", "expanded_target": "0x8EB040", "expanded_policy": "frozen_c342"},
    "0x415F0": {"stock_target": "0x7B2000", "expanded_target": "0x8EB000", "expanded_policy": "task9_post_relocation"},
    "0x4AF12": {"stock_target": "0x7B2100", "expanded_target": "0x8EB100", "expanded_policy": "frozen_c342"},
    "0x4BC20": {"stock_target": "0x7B20C0", "expanded_target": "0x8EB0C0", "expanded_policy": "frozen_c342"},
}
STATISTICS_FEATURES_PATH = ROOT / "data" / "statistics_features.json"
DEFAULT_PATCH_MODE = "collection_progression"
PUBLIC_ORIGINS_VILLAGE_WIDE_PATCH_IDS = tuple(
    f"vv{game_number}_origins_village_wide_upgrades"
    for game_number in range(1, 6)
)
PUBLIC_ORIGINS_VILLAGE_WIDE_PATCH_ID_SET = frozenset(
    PUBLIC_ORIGINS_VILLAGE_WIDE_PATCH_IDS
)
INTERNAL_ORIGINS_BASE_FEATURE_ID_SET = frozenset(
    f"vv{game_number}_enable_origins_exclusive_features"
    for game_number in range(1, 6)
)
# Expanded-256 population modes were removed from the active manifest.  Keep
# their IDs only for validating retained historical evidence records; they are
# not returned by load_patch_modes() and are not accepted by public APIs.
EXPANDED_PATCH_MODES: frozenset[str] = frozenset(
    {
        "experimental_expanded_256",
        "experimental_expanded_256_progression",
    }
)
VV3_EXPANDED_HEALER_ENDPOINT_REPAIR = {
    "offset": "0x5FA46",
    "before": "807B1F00",
    "after": "886C1F00",
    "purpose": (
        "correct the VV3 nearby sick-villager picker endpoint to "
        "record 255 plus the native 0x14 record offset"
    ),
}
VV3_EXPANDED_CAPACITY_CORRECTIONS = (
    {
        "offset": "0x5E8F8",
        "before": "BA0F000000",
        "after": "BA1A000000",
        "purpose": "scan 26 ten-record groups when counting the current population",
    },
    {
        "offset": "0x5EA9C",
        "before": "BF0F000000",
        "after": "BF1A000000",
        "purpose": "scan 26 ten-record groups in the population and gender helper",
    },
    {
        "offset": "0x5D7D6",
        "before": "BA0F000000",
        "after": "BA1A000000",
        "purpose": "scan 26 ten-record groups when resetting all villager records",
    },
    {
        "offset": "0x7B266",
        "before": "93000000",
        "after": "FD000000",
        "purpose": "reserve three free physical slots before a three-child birth",
    },
    {
        "offset": "0x7B286",
        "before": "94000000",
        "after": "FE000000",
        "purpose": "reserve two free physical slots before a two-child birth",
    },
)
VV3_EXPANDED_CHIEF_CANDIDATE_ASSIGNMENT_REPAIR = {
    "offset": "0x5FB9C",
    "before": "94130000",
    "after": "9C0E0000",
    "purpose": (
        "restore the native record-relative 0xE9C displacement used to write "
        "the VV3 Tribal Chief candidate flag at record offset 0xE88"
    ),
}
VV3_EXPANDED_DETAIL_ROSTER_CLASS_SIZE = {
    "offset": "0x27A39",
    "before": "3C030000",
    "after": "E4040000",
}
VV3_EXPANDED_DETAIL_ROSTER_DISPLACEMENT_DELTA = 0x1A8
# Exact reviewed operands in the native VV3 Details-screen class.  The 150
# displacement sites move the original 0x260..0x338 tail behind the expanded
# 256-entry roster.  Keeping the complete table here makes every preimage
# independently guarded instead of applying a broad byte-pattern rewrite.
VV3_EXPANDED_DETAIL_ROSTER_DISPLACEMENTS = (
    (0x6CB03, 0x2BC, 0x464), (0x6CB22, 0x260, 0x408),
    (0x6CB81, 0x26C, 0x414), (0x6CB87, 0x270, 0x418),
    (0x6CB8D, 0x274, 0x41C), (0x6CB93, 0x278, 0x420),
    (0x6CB99, 0x27C, 0x424), (0x6CB9F, 0x280, 0x428),
    (0x6CBA5, 0x284, 0x42C), (0x6CBAB, 0x288, 0x430),
    (0x6CBB1, 0x28C, 0x434), (0x6CBB7, 0x290, 0x438),
    (0x6CBBD, 0x294, 0x43C), (0x6CBC3, 0x298, 0x440),
    (0x6CBC9, 0x29C, 0x444), (0x6CBCF, 0x2A0, 0x448),
    (0x6CBD5, 0x2A4, 0x44C), (0x6CBDB, 0x2A8, 0x450),
    (0x6CBE1, 0x2AC, 0x454), (0x6CBE7, 0x2B0, 0x458),
    (0x6CBED, 0x2B4, 0x45C), (0x6CBF3, 0x2B8, 0x460),
    (0x6CC03, 0x270, 0x418), (0x6CC09, 0x278, 0x420),
    (0x6CC0F, 0x280, 0x428), (0x6CC15, 0x288, 0x430),
    (0x6CC1B, 0x290, 0x438), (0x6CC21, 0x298, 0x440),
    (0x6CC37, 0x2BC, 0x464), (0x6CC41, 0x2C0, 0x468),
    (0x6CC4B, 0x2C4, 0x46C), (0x6CC55, 0x26C, 0x414),
    (0x6CC5F, 0x274, 0x41C), (0x6CC69, 0x27C, 0x424),
    (0x6CC73, 0x284, 0x42C), (0x6CC7D, 0x28C, 0x434),
    (0x6CC87, 0x294, 0x43C), (0x6CC91, 0x2AC, 0x454),
    (0x6CC9B, 0x2B0, 0x458), (0x6CCA1, 0x2B4, 0x45C),
    (0x6CCAB, 0x2B8, 0x460), (0x6CCB1, 0x29C, 0x444),
    (0x6CCB7, 0x2A0, 0x448), (0x6CCBD, 0x2A4, 0x44C),
    (0x6CCC7, 0x2A8, 0x450), (0x6CD16, 0x2D4, 0x47C),
    (0x6CD35, 0x2D4, 0x47C), (0x6CD8E, 0x2D8, 0x480),
    (0x6CDAD, 0x2D8, 0x480), (0x6CDF2, 0x2BC, 0x464),
    (0x6CE05, 0x2C8, 0x470), (0x6CE35, 0x2C8, 0x470),
    (0x6CE41, 0x2C8, 0x470), (0x6CE80, 0x2C4, 0x46C),
    (0x6CE99, 0x2D0, 0x478), (0x6CED4, 0x2C0, 0x468),
    (0x6CEEE, 0x2CC, 0x474), (0x6CF44, 0x2DC, 0x484),
    (0x6CF63, 0x2DC, 0x484), (0x6CFBB, 0x2E0, 0x488),
    (0x6CFDA, 0x2E0, 0x488), (0x6D032, 0x2E4, 0x48C),
    (0x6D051, 0x2E4, 0x48C), (0x6D0B0, 0x2E8, 0x490),
    (0x6D0CF, 0x2E8, 0x490), (0x6D122, 0x2EC, 0x494),
    (0x6D141, 0x2EC, 0x494), (0x6D19A, 0x2F0, 0x498),
    (0x6D1B9, 0x2F0, 0x498), (0x6D212, 0x2F4, 0x49C),
    (0x6D231, 0x2F4, 0x49C), (0x6D28A, 0x2F8, 0x4A0),
    (0x6D2A9, 0x2F8, 0x4A0), (0x6D302, 0x2FC, 0x4A4),
    (0x6D321, 0x2FC, 0x4A4), (0x6D37A, 0x300, 0x4A8),
    (0x6D399, 0x300, 0x4A8), (0x6D3F2, 0x304, 0x4AC),
    (0x6D411, 0x304, 0x4AC), (0x6D464, 0x308, 0x4B0),
    (0x6D483, 0x308, 0x4B0), (0x6D491, 0x308, 0x4B0),
    (0x6D4A0, 0x308, 0x4B0), (0x6D4F6, 0x30C, 0x4B4),
    (0x6D515, 0x30C, 0x4B4), (0x6D568, 0x310, 0x4B8),
    (0x6D587, 0x310, 0x4B8), (0x6D5E0, 0x314, 0x4BC),
    (0x6D5FF, 0x314, 0x4BC), (0x6D652, 0x318, 0x4C0),
    (0x6D671, 0x318, 0x4C0), (0x6D6CA, 0x31C, 0x4C4),
    (0x6D6E9, 0x31C, 0x4C4), (0x6D73C, 0x320, 0x4C8),
    (0x6D75B, 0x320, 0x4C8), (0x6D7B4, 0x324, 0x4CC),
    (0x6D7D3, 0x324, 0x4CC), (0x6D826, 0x328, 0x4D0),
    (0x6D845, 0x328, 0x4D0), (0x6D89E, 0x32C, 0x4D4),
    (0x6D8BD, 0x32C, 0x4D4), (0x6D910, 0x330, 0x4D8),
    (0x6D92F, 0x330, 0x4D8), (0x6D98F, 0x334, 0x4DC),
    (0x6D9AE, 0x334, 0x4DC), (0x6DA01, 0x338, 0x4E0),
    (0x6DA20, 0x338, 0x4E0), (0x6DA33, 0x264, 0x40C),
    (0x6DA39, 0x268, 0x410), (0x6DAEC, 0x310, 0x4B8),
    (0x6DB1C, 0x318, 0x4C0), (0x6DB74, 0x320, 0x4C8),
    (0x6DB8B, 0x328, 0x4D0), (0x6DBA2, 0x330, 0x4D8),
    (0x6DC44, 0x338, 0x4E0), (0x6DC83, 0x334, 0x4DC),
    (0x6DE7E, 0x264, 0x40C), (0x6DEA4, 0x264, 0x40C),
    (0x6DECE, 0x264, 0x40C), (0x6DEFF, 0x2EC, 0x494),
    (0x6E0E8, 0x26C, 0x414), (0x6E0F0, 0x274, 0x41C),
    (0x6E0F8, 0x270, 0x418), (0x6E100, 0x278, 0x420),
    (0x6E117, 0x264, 0x40C), (0x6E12A, 0x27C, 0x424),
    (0x6E132, 0x284, 0x42C), (0x6E13A, 0x280, 0x428),
    (0x6E142, 0x288, 0x430), (0x6E159, 0x264, 0x40C),
    (0x6E16E, 0x28C, 0x434), (0x6E190, 0x264, 0x40C),
    (0x6E1D9, 0x29C, 0x444), (0x6E237, 0x2AC, 0x454),
    (0x6E286, 0x260, 0x408), (0x6E2B1, 0x260, 0x408),
    (0x6E2BB, 0x260, 0x408), (0x6E2FA, 0x264, 0x40C),
    (0x6E362, 0x268, 0x410), (0x6E399, 0x260, 0x408),
    (0x6E3EE, 0x260, 0x408), (0x6E43F, 0x308, 0x4B0),
    (0x6E499, 0x308, 0x4B0), (0x6E50C, 0x308, 0x4B0),
    (0x6E549, 0x2BC, 0x464), (0x6E57B, 0x308, 0x4B0),
    (0x6E5C0, 0x2C4, 0x46C), (0x6E5F6, 0x260, 0x408),
    (0x6E614, 0x2C0, 0x468), (0x6E64D, 0x260, 0x408),
)
VV3_EXPANDED_DETAIL_ORIGINS_REPLAY_DISPLACEMENTS = (
    (0xA3335, 0x264, 0x40C),
    (0xA333B, 0x268, 0x410),
)
VV3_EXPANDED_DETAIL_ORIGINS_FEATURE_IDS = frozenset({
    "vv3_enable_origins_exclusive_features",
    "vv3_enable_origins_exclusive_features_full_mastery_candidate",
    "vv3_enable_origins_exclusive_features_running_candidate",
})
VV3_EXPANDED_FINAL_TIME_WARP_RESULTS = {
    "experimental_expanded_256": {
        "atomic_result": {
            "size": 843776,
            "sha256": "B49CC315AB750D535F3C547BC6E5FC40D63FAE8AEA1ACECE91C1E8D066E9C3E5",
            "checksum": "24160D00",
        },
        "statistics_result": {
            "size": 843776,
            "sha256": "F95E797E9C25081F2FDF6F21063FAD09CCAFF322129423C9C7784D3E09321E15",
            "checksum": "950C0D00",
        },
    },
    "experimental_expanded_256_progression": {
        "atomic_result": {
            "size": 843776,
            "sha256": "78479CDEE2C45123E11CC63AFCC260E336935982774CA923B7CCFD4DF0652F49",
            "checksum": "2E910D00",
        },
        "statistics_result": {
            "size": 843776,
            "sha256": "1CE1E7B794433EA60F99FE31BC5397AD02C2995CDCABFE67D7C901D516B27E77",
            "checksum": "9F870D00",
        },
    },
}
# Kept for compatibility with archival validators; there are no active
# Expanded-256 modes for this flag to enable.
EXPANDED_256_PUBLICATION_ENABLED = False
VV1_ORIGINS_COMPOSITION_ID = "vv1_full_mastery_origins_composition"
VV1_ORIGINS_COMPOSITION_BASE_SHA256 = "5434C71C342B830A5896AFFB610A76C670578760BD33C6145882FA280F6406A3"
VV1_ORIGINS_COMPOSITION_DLL_SHA256 = "2ED1100E7F2EA5B8E522C2DE11F6B00CA8A02B968319C251365E9EFD634BCAF9"


class PatcherError(RuntimeError):
    pass


def _reject_expanded_256_publication(patch_mode: str) -> None:
    """Reject public Expanded-256 publication before any input access."""
    if not EXPANDED_256_PUBLICATION_ENABLED and patch_mode in EXPANDED_PATCH_MODES:
        raise PatcherError(
            "Expanded-256 publication is disabled; use dry-run or static rendering only."
        )


_PUBLIC_PATCH_MODES = {"stock", "collection_progression", "immediate_fixed"}


def _validate_public_patch_mode(patch_mode: str) -> None:
    """Validate a public mode without loading catalogs or touching input paths."""
    if not isinstance(patch_mode, str) or patch_mode not in _PUBLIC_PATCH_MODES:
        raise PatcherError(f"Unknown patch mode: {patch_mode}")


@dataclass(frozen=True)
class Record:
    raw: dict[str, Any]

    def __getattr__(self, name: str) -> Any:
        try:
            return self.raw[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


Build = Record
PatchMode = Record
FunPatch = Record


def _manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8-sig"))


def load_builds() -> list[Build]:
    return [Build(item) for item in _manifest()["games"]]


def load_patch_modes() -> list[PatchMode]:
    return [PatchMode(item) for item in _manifest()["patch_modes"]]


def _certified_vv3_running_records(
    active_base: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    running_candidate = json.loads(
        VV3_RUNNING_CANDIDATE_PATHS["running"].read_text(encoding="utf-8")
    )
    if not running_candidate.get("enabled", True):
        return active_base, None

    records: dict[str, dict[str, Any]] = {}
    for label, path in VV3_RUNNING_CANDIDATE_PATHS.items():
        payload = path.read_bytes()
        digest = source_text_sha256(payload)
        if digest != VV3_RUNNING_CERTIFIED_SHA256[label]:
            raise PatcherError(
                f"Certified VV3 Running {label} artifact hash mismatch: "
                f"expected {VV3_RUNNING_CERTIFIED_SHA256[label]}, got {digest}."
            )
        records[label] = json.loads(payload.decode("utf-8"))

    base = dict(records["base"])
    base.update(
        {
            "id": active_base["id"],
            "name": active_base["name"],
            "enabled": True,
            "certification_status": (
                "Corrected repeatable-action bytes specified by disassembly commit "
                "0095e605b3b488129c0623efd642e9352d8586c0; final emitted-artifact "
                "recertification required before enablement"
            ),
        }
    )
    running = dict(records["running"])
    running.update(
        {
            "id": "vv3_all_villagers_like_running",
            "name": "All Villagers Like Running",
            "enabled": True,
            "dependencies": [active_base["id"]],
            "description": (
                "Give Running preference ID 38 to every eligible active living "
                "VV3 villager with an empty Like slot for 1,000,000 tech points. "
                "Already-like and full-Like records remain unchanged; Running "
                "dislikes are removed only in the same atomic eligible mutation. "
                "This is a repeatable Buy action, never Remove; commands 7 and 8 "
                "remain unavailable."
            ),
            "evidence_status": (
                "corrective byte contract 0095e605b3b488129c0623efd642e9352d8586c0 "
                "implemented as a disabled candidate; final emitted-artifact "
                "recertification and runtime/player confirmation pending"
            ),
        }
    )
    return base, running


def _certified_vv3_full_mastery_records(
    active_base: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    if not VV3_FULL_MASTERY_ENABLED:
        return None

    records: dict[str, dict[str, Any]] = {}
    for label, path in VV3_FULL_MASTERY_CANDIDATE_PATHS.items():
        payload = path.read_bytes()
        digest = hashlib.sha256(payload).hexdigest().upper() if label == "dll" else source_text_sha256(payload)
        expected = VV3_FULL_MASTERY_CERTIFIED_SHA256[label]
        if digest != expected:
            raise PatcherError(
                f"Certified VV3 Full Mastery {label} artifact hash mismatch: "
                f"expected {expected}, got {digest}."
            )
        if label != "dll":
            records[label] = json.loads(payload.decode("utf-8"))

    artifact = records["map"]
    stock = artifact["layouts"]["collection_progression"]
    actual = {
        "entry": stock["slot_map"]["installed"]["entry_sha256"],
        "slot": stock["installed_slot_sha256"],
        "page": stock["installed_page_sha256"],
    }
    for label, actual_digest in actual.items():
        expected = VV3_FULL_MASTERY_CERTIFIED_SHA256[label]
        if actual_digest != expected:
            raise PatcherError(
                f"Certified VV3 Full Mastery {label} artifact hash mismatch: "
                f"expected {expected}, got {actual_digest}."
            )
    if set(artifact["layouts"]) != {"collection_progression", "immediate_fixed"}:
        raise PatcherError(
            "Certified VV3 Full Mastery map unexpectedly contains non-stock layouts."
        )

    base = dict(records["base"])
    base.update(
        {
            "id": active_base["id"],
            "name": active_base["name"],
            "enabled": True,
            "certification_status": (
                "Existing command-7 bytes retain their prior certification; "
                "the command-5/resource containment composition awaits independent review"
            ),
        }
    )
    feature = dict(records["feature"])
    feature.update(
        {
            "id": "vv3_full_mastery_all_stage_a_candidate",
            "name": "Grant Full Mastery to All Villagers",
            "enabled": True,
            "dependencies": [active_base["id"]],
            "certification_status": (
                "Existing command-7 bytes retain their prior certification; "
                "stock modes only; containment composition awaits independent review"
            ),
        }
    )
    return base, feature


def _certified_vv3_individual_running_record(
    active_base: dict[str, Any],
    full_mastery_feature: dict[str, Any],
) -> dict[str, Any] | None:
    """Load the enabled selected-villager record only from pinned metadata."""

    manifest_path = VV3_INDIVIDUAL_RUNNING_CANDIDATE_PATHS["manifest"]
    map_path = VV3_INDIVIDUAL_RUNNING_CANDIDATE_PATHS["map"]
    manifest_bytes = manifest_path.read_bytes()
    manifest_digest = source_text_sha256(manifest_bytes)
    if manifest_digest != VV3_INDIVIDUAL_RUNNING_MANIFEST_SHA256:
        raise PatcherError(
            "VV3 individual Grant Running manifest bytes are not the certified record."
        )
    map_bytes = map_path.read_bytes()
    map_digest = source_text_sha256(map_bytes)
    if map_digest != VV3_INDIVIDUAL_RUNNING_MAP_SHA256:
        raise PatcherError(
            "VV3 individual Grant Running map bytes are not the certified record."
        )
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    artifact_map = json.loads(map_bytes.decode("utf-8"))
    if not manifest.get("enabled", True):
        # The historical candidate is retained only as immutable evidence.  Its
        # Likes-only helper cannot satisfy the current base-game slot
        # contract, so the loader must reject it before catalog/composition.
        revocation = manifest.get("revocation")
        if (
            manifest.get("id") != VV3_INDIVIDUAL_RUNNING_CANDIDATE_ID
            or manifest.get("game_id") != "vv3"
            or manifest.get("catalog_hidden") is not True
            or manifest.get("catalog_enabled") is not False
            or not isinstance(revocation, dict)
            or revocation.get("status") != "withdrawn"
            or revocation.get("superseded_by")
            != "vv3_individual_grant_running_revised_candidate"
            or not isinstance(revocation.get("reason"), str)
            or "Dislikes" not in revocation["reason"]
        ):
            raise PatcherError(
                "VV3 historical Grant Running revocation metadata is not fail-closed."
            )
        if (
            artifact_map.get("candidate_id") != VV3_INDIVIDUAL_RUNNING_CANDIDATE_ID
            or artifact_map.get("candidate_enabled") is not False
            or artifact_map.get("catalog_hidden") is not True
            or artifact_map.get("catalog_enabled") is not False
            or artifact_map.get("acceptance_status", "").startswith("WITHDRAWN") is not True
        ):
            raise PatcherError(
                "VV3 historical Grant Running map revocation metadata is not fail-closed."
            )
        return None
    if (
        manifest.get("id") != VV3_INDIVIDUAL_RUNNING_CANDIDATE_ID
        or manifest.get("game_id") != "vv3"
        or manifest.get("catalog_hidden") is not False
        or manifest.get("catalog_enabled") is not True
        or manifest.get("source_commit") != VV3_INDIVIDUAL_RUNNING_SOURCE_COMMIT
        or manifest.get("implementation_commit")
        != VV3_INDIVIDUAL_RUNNING_IMPLEMENTATION_COMMIT
        or manifest.get("runtime_player_status") != "pending"
        or manifest.get("supported_modes") != [
            "collection_progression",
            "immediate_fixed",
        ]
        or manifest.get("unsupported_patch_modes") != [
            "experimental_expanded_256",
            "experimental_expanded_256_progression",
        ]
        or manifest.get("dependencies") != [
            "vv3_full_mastery_all_stage_a_candidate"
        ]
        or not str(manifest.get("certification_status", "")).startswith(
            "D172 independent static GO;"
        )
    ):
        raise PatcherError(
            "VV3 individual Grant Running manifest enablement is not certified."
        )
    if (
        artifact_map.get("candidate_id") != VV3_INDIVIDUAL_RUNNING_CANDIDATE_ID
        or artifact_map.get("candidate_enabled") is not True
        or artifact_map.get("catalog_hidden") is not False
        or artifact_map.get("catalog_enabled") is not True
        or artifact_map.get("source_commit") != VV3_INDIVIDUAL_RUNNING_SOURCE_COMMIT
        or artifact_map.get("implementation_commit")
        != VV3_INDIVIDUAL_RUNNING_IMPLEMENTATION_COMMIT
        or artifact_map.get("acceptance_status") != VV3_INDIVIDUAL_RUNNING_ACCEPTANCE_STATUS
        or artifact_map.get("allowed_modes") != [
            "collection_progression",
            "immediate_fixed",
        ]
        or artifact_map.get("expanded_fail_closed") is not True
    ):
        raise PatcherError(
            "VV3 individual Grant Running map enablement is not certified."
        )
    rendered = artifact_map.get("rendered")
    if not isinstance(rendered, dict):
        raise PatcherError(
            "VV3 individual Grant Running rendered-mode metadata is missing."
        )
    for mode, expected_sha256 in VV3_INDIVIDUAL_RUNNING_RENDERED_SHA256.items():
        if rendered.get(mode, {}).get("sha256") != expected_sha256:
            raise PatcherError(
                f"VV3 individual Grant Running {mode} rendered identity is not certified."
            )
    for mode in EXPANDED_PATCH_MODES:
        if rendered.get(mode) != {
            "rejected": "VV3 individual Grant Running is stock-mode only; Expanded-256 is fail-closed."
        }:
            raise PatcherError(
                f"VV3 individual Grant Running Expanded mode {mode} is not fail-closed."
            )
    candidate = FunPatch(manifest)
    selected_ids = {
        active_base["id"],
        full_mastery_feature["id"],
        VV3_INDIVIDUAL_RUNNING_CANDIDATE_ID,
    }
    _validate_vv3_individual_running_candidate(
        candidate,
        selected_ids,
        "collection_progression",
    )
    return manifest


def _validate_vv3_individual_full_mastery_candidate() -> dict[str, Any] | None:
    """Validate the public stock-only VV3 selected-villager Full Mastery record."""
    manifest_path = VV3_INDIVIDUAL_FULL_MASTERY_CANDIDATE_PATHS["manifest"]
    map_path = VV3_INDIVIDUAL_FULL_MASTERY_CANDIDATE_PATHS["map"]
    if not manifest_path.is_file() or not map_path.is_file():
        return None
    manifest_bytes = manifest_path.read_bytes()
    map_bytes = map_path.read_bytes()
    if source_text_sha256(manifest_bytes) != VV3_INDIVIDUAL_FULL_MASTERY_MANIFEST_SHA256:
        raise PatcherError("VV3 individual Full Mastery manifest source-text hash mismatch.")
    if source_text_sha256(map_bytes) != VV3_INDIVIDUAL_FULL_MASTERY_MAP_SHA256:
        raise PatcherError("VV3 individual Full Mastery map source-text hash mismatch.")
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    artifact_map = json.loads(map_bytes.decode("utf-8"))
    if (
        manifest.get("id") != VV3_INDIVIDUAL_FULL_MASTERY_CANDIDATE_ID
        or manifest.get("game_id") != "vv3"
        or manifest.get("enabled") is not True
        or manifest.get("catalog_hidden") is not False
        or manifest.get("catalog_enabled") is not True
        or manifest.get("runtime_player_status") != "pending live player confirmation"
        or manifest.get("supported_modes") != ["collection_progression", "immediate_fixed"]
        or set(manifest.get("unsupported_patch_modes", ())) != EXPANDED_PATCH_MODES
        or manifest.get("dependencies") != ["vv3_full_mastery_all_stage_a_candidate"]
    ):
        raise PatcherError("VV3 individual Full Mastery metadata is not public/stock-only.")
    tx_contract = manifest.get("transaction", {})
    if tx_contract.get("accept_result") != 1 or tx_contract.get("cancel_results") != [0, 2]:
        raise PatcherError("VV3 individual Full Mastery MessageBox acceptance must be IDOK=1 only.")
    expected_companion = {
        "source": "data/candidates/VVFP VV3 Safe Upgrades.dll",
        "destination": "VVFP VV3 Full Mastery Candidate.dll",
        "sha256": "5E4DAAC445ABAF654AFB3D36844E6F3DE951C2EBC05E52690C52BD68A263B612",
        "size": 298496,
        "preimage_sha256": "A99584788F1726AF2DFDAE83BC9F42DE82DBD2DBA6E1ECD56222D2BDACB47681",
        "restore_source": "data/candidates/VVFP VV3 Safe Upgrade Foundation.dll",
        "restore_sha256": "A99584788F1726AF2DFDAE83BC9F42DE82DBD2DBA6E1ECD56222D2BDACB47681",
    }
    if manifest.get("companion_files") != [expected_companion]:
        raise PatcherError("VV3 individual Full Mastery companion ownership is not certified.")
    companion_path = ROOT / expected_companion["source"]
    if not companion_path.is_file() or companion_path.stat().st_size != expected_companion["size"] or hashlib.sha256(companion_path.read_bytes()).hexdigest().upper() != expected_companion["sha256"]:
        raise PatcherError("VV3 individual Full Mastery companion source hash mismatch.")
    restore_path = ROOT / expected_companion["restore_source"]
    if not restore_path.is_file() or restore_path.stat().st_size != expected_companion["size"] or hashlib.sha256(restore_path.read_bytes()).hexdigest().upper() != expected_companion["restore_sha256"]:
        raise PatcherError("VV3 individual Full Mastery companion parent hash mismatch.")
    chain = manifest.get("base_chain", {})
    if chain.get("collection_progression_parent_sha256") != VV3_INDIVIDUAL_FULL_MASTERY_PARENT_SHA256["collection_progression"] or chain.get("immediate_fixed_parent_sha256") != VV3_INDIVIDUAL_FULL_MASTERY_PARENT_SHA256["immediate_fixed"]:
        raise PatcherError("VV3 individual Full Mastery parent hashes are not certified.")
    patches = manifest.get("patches")
    if not isinstance(patches, list) or len(patches) != 1 or patches[0].get("offset") != "0xA38C3" or patches[0].get("before") != "E926010000" or patches[0].get("after") != "E938C72300":
        raise PatcherError("VV3 individual Full Mastery command dispatcher guard is not certified.")
    tx = manifest.get("pe_append_transaction", {})
    layouts = tx.get("layouts")
    if tx.get("append_source") != "generated:vv3_individual_full_mastery_page" or tx.get("page_sha256") != VV3_INDIVIDUAL_FULL_MASTERY_PAGE_SHA256 or not isinstance(layouts, dict) or set(layouts) != {"collection_progression", "immediate_fixed"}:
        raise PatcherError("VV3 individual Full Mastery append source/layout metadata is not certified.")
    for mode, layout in layouts.items():
        if not isinstance(layout, dict) or int(layout.get("original_file_size", "-1"), 0) != 0xCC000 or int(layout.get("append_offset", "-1"), 0) != 0xCC000 or layout.get("append_source") != "generated:vv3_individual_full_mastery_page" or int(layout.get("append_length", "-1"), 0) != 0x1000 or layout.get("page_sha256") != VV3_INDIVIDUAL_FULL_MASTERY_PAGE_SHA256 or len(layout.get("header_patches", [])) != 3:
            raise PatcherError(f"VV3 individual Full Mastery {mode} append layout is not certified.")
        rendered = manifest.get("rendered_modes", {}).get(mode, {})
        if rendered.get("candidate_sha256") != VV3_INDIVIDUAL_FULL_MASTERY_OUTPUT_SHA256[mode] or rendered.get("size") != 0xCD000:
            raise PatcherError(f"VV3 individual Full Mastery {mode} rendered identity is not certified.")
        patches = layout.get("header_patches")
        if patches[0].get("offset") != "0x10E" or patches[0].get("before") != "0600" or patches[0].get("after") != "0700" or patches[1].get("offset") != "0x158" or patches[1].get("before") != "00002E00" or patches[1].get("after") != "00102E00" or patches[2].get("offset") != "0x2F0" or len(bytes.fromhex(patches[2].get("before", ""))) != 40 or len(bytes.fromhex(patches[2].get("after", ""))) != 40:
            raise PatcherError("VV3 individual Full Mastery section/header guards are not certified.")
    if artifact_map.get("candidate_id") != VV3_INDIVIDUAL_FULL_MASTERY_CANDIDATE_ID or artifact_map.get("enabled") is not True or artifact_map.get("catalog_hidden") is not False or artifact_map.get("catalog_enabled") is not True or artifact_map.get("rendered_modes") != manifest.get("rendered_modes") or artifact_map.get("dispatcher", {}).get("abi") != "cmp ebx,1; jne 0x4A39EE; call 0x6E0100; jmp 0x4A37D6":
        raise PatcherError("VV3 individual Full Mastery map publication/dispatcher metadata drifted.")
    return manifest


def load_hidden_vv3_individual_full_mastery_candidate() -> FunPatch:
    """Compatibility accessor for the now-public certified VV3 child record."""
    manifest = _validate_vv3_individual_full_mastery_candidate()
    if manifest is None:
        raise PatcherError("VV3 individual Full Mastery candidate metadata is unavailable.")
    return FunPatch(manifest)


def _certified_vv2_full_mastery_record() -> dict[str, Any] | None:
    manifest_bytes = VV2_FULL_MASTERY_CANDIDATE_PATHS["manifest"].read_bytes()
    manifest_digest = source_text_sha256(manifest_bytes)
    if manifest_digest != VV2_FULL_MASTERY_MANIFEST_SHA256:
        raise PatcherError("VV2 Full Mastery manifest bytes are not the certified record.")
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    if not manifest.get("enabled", True):
        return None
    if (
        manifest.get("id") != "vv2_full_mastery_all_stage_a_candidate"
        or manifest.get("catalog_hidden") is not False
        or manifest.get("supported_modes") != VV2_FULL_MASTERY_STATIC_ACCEPTANCE["allowed_modes"]
        or manifest.get("rejected_modes") != VV2_FULL_MASTERY_STATIC_ACCEPTANCE["rejected_modes"]
    ):
        raise PatcherError("VV2 Full Mastery catalog or mode metadata is not certified.")
    if manifest.get("source_commit") != VV2_FULL_MASTERY_STATIC_ACCEPTANCE["implementation_commit"]:
        raise PatcherError("VV2 Full Mastery source commit is not the certified implementation.")
    if manifest.get("implementation_commit") != VV2_FULL_MASTERY_STATIC_ACCEPTANCE["implementation_commit"]:
        raise PatcherError("VV2 Full Mastery implementation commit is not certified.")
    if manifest.get("audit_commit") is not None or manifest.get("acceptance_commit") is not None:
        raise PatcherError("VV2 Full Mastery uses circular legacy provenance fields.")
    static_acceptance = manifest.get("static_acceptance")
    if static_acceptance != VV2_FULL_MASTERY_STATIC_ACCEPTANCE:
        raise PatcherError("VV2 Full Mastery static acceptance evidence is not certified.")
    map_bytes = VV2_FULL_MASTERY_CANDIDATE_PATHS["map"].read_bytes()
    map_digest = source_text_sha256(map_bytes)
    if map_digest != VV2_FULL_MASTERY_MAP_SHA256:
        raise PatcherError("VV2 Full Mastery map bytes are not the certified record.")
    artifact_map = json.loads(map_bytes.decode("utf-8"))
    if artifact_map.get("catalog_enabled") is not True:
        raise PatcherError("VV2 Full Mastery map catalog gate is not enabled.")
    if artifact_map.get("source_commit") != VV2_FULL_MASTERY_STATIC_ACCEPTANCE["implementation_commit"]:
        raise PatcherError("VV2 Full Mastery map source commit is not certified.")
    if artifact_map.get("implementation_commit") != VV2_FULL_MASTERY_STATIC_ACCEPTANCE["implementation_commit"]:
        raise PatcherError("VV2 Full Mastery map implementation commit is not certified.")
    if artifact_map.get("static_acceptance") != VV2_FULL_MASTERY_STATIC_ACCEPTANCE:
        raise PatcherError("VV2 Full Mastery map static acceptance evidence is not certified.")
    for label in (
        "section",
        "entry",
        "walker",
        "telemetry",
        "confirmation",
        "menu_resolver",
        "result_preflight",
        "result_resolver",
    ):
        actual = artifact_map[f"{label}_sha256"]
        expected = VV2_FULL_MASTERY_CERTIFIED_SHA256[label]
        if actual != expected:
            raise PatcherError(
                f"Certified VV2 Full Mastery {label} artifact hash mismatch: "
                f"expected {expected}, got {actual}."
            )
    source = artifact_map.get("source", {})
    if source.get("sha256") != VV2_FULL_MASTERY_CERTIFIED_SHA256["source"] or source.get("size") != 724992:
        raise PatcherError("VV2 Full Mastery stock source fingerprint mismatch.")
    companion = artifact_map.get("companion", {})
    if companion.get("size") != 109056 or companion.get("sha256") != VV2_FULL_MASTERY_CERTIFIED_SHA256["dll"]:
        raise PatcherError("VV2 Full Mastery companion size/hash mismatch.")
    rendered = artifact_map.get("rendered_candidates", {})
    for mode, expected in VV2_FULL_MASTERY_STATIC_ACCEPTANCE["rendered_candidates"].items():
        actual = rendered.get(mode, {})
        if any(actual.get(key) != value for key, value in expected.items()):
            raise PatcherError(f"VV2 Full Mastery {mode} composition identity mismatch.")
    dll_digest = hashlib.sha256(
        VV2_FULL_MASTERY_CANDIDATE_PATHS["dll"].read_bytes()
    ).hexdigest().upper()
    if dll_digest != VV2_FULL_MASTERY_CERTIFIED_SHA256["dll"]:
        raise PatcherError(
            "Certified VV2 Full Mastery DLL hash mismatch: "
            f"expected {VV2_FULL_MASTERY_CERTIFIED_SHA256['dll']}, got {dll_digest}."
        )
    contract = manifest.get("transaction_contract", {})
    if contract.get("command") != 7 or contract.get("price") != 1_000_000:
        raise PatcherError("VV2 Full Mastery Buy contract is not certified.")
    if contract.get("ownership") is not None or "remove" in contract:
        raise PatcherError("VV2 Full Mastery must remain Buy-only with no Remove.")
    return manifest


def _certified_vv2_individual_full_mastery_record() -> dict[str, Any] | None:
    """Validate the public stock-only selected-villager overlay fail closed."""
    manifest_path = VV2_INDIVIDUAL_FULL_MASTERY_CANDIDATE_PATHS["manifest"]
    map_path = VV2_INDIVIDUAL_FULL_MASTERY_CANDIDATE_PATHS["map"]
    manifest_bytes = manifest_path.read_bytes()
    map_bytes = map_path.read_bytes()
    if source_text_sha256(manifest_bytes) != VV2_INDIVIDUAL_FULL_MASTERY_MANIFEST_SHA256:
        raise PatcherError("VV2 selected Full Mastery manifest bytes are not certified.")
    if source_text_sha256(map_bytes) != VV2_INDIVIDUAL_FULL_MASTERY_MAP_SHA256:
        raise PatcherError("VV2 selected Full Mastery map bytes are not certified.")
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    artifact_map = json.loads(map_bytes.decode("utf-8"))
    if not manifest.get("enabled", False):
        return None
    if (
        manifest.get("id") != VV2_INDIVIDUAL_FULL_MASTERY_CANDIDATE_ID
        or manifest.get("game_id") != "vv2"
        or manifest.get("catalog_hidden") is not False
        or manifest.get("catalog_enabled") is not True
        or manifest.get("runtime_player_status") != "pending"
        or manifest.get("dependencies") != ["vv2_full_mastery_all_stage_a_candidate"]
        or manifest.get("companion_files") != []
        or manifest.get("supported_modes") != ["collection_progression", "immediate_fixed"]
        or set(manifest.get("rejected_modes", ())) != EXPANDED_PATCH_MODES
    ):
        raise PatcherError("VV2 selected Full Mastery catalog/mode metadata is invalid.")
    contract = manifest.get("transaction_contract", {})
    if (
        contract.get("detail_event") != 8
        or contract.get("button_id") != 6
        or contract.get("price") != 100_000
        or contract.get("target") != 100
        or contract.get("ownership") is not None
        or contract.get("eligibility_before_skills")
        != ["byte +0x30 != 0", "signed dword +0x52C > 0", "byte +0x558 == 0"]
        or "sub_445430" not in str(contract.get("native_skill_writer"))
        or "sub_44D4C0" not in str(contract.get("native_evaluator"))
        or "sub_426290" not in str(contract.get("native_tech_writer"))
    ):
        raise PatcherError("VV2 selected Full Mastery transaction contract is invalid.")
    parent_chain = manifest.get("parent_chain", {})
    if (
        parent_chain.get("stock_sha256") != VV2_FULL_MASTERY_CERTIFIED_SHA256["source"]
        or parent_chain.get("parent_manifest_source_text_sha256") != VV2_FULL_MASTERY_MANIFEST_SHA256
        or parent_chain.get("parent_map_source_text_sha256") != VV2_FULL_MASTERY_MAP_SHA256
        or parent_chain.get("parent_dll_sha256") != VV2_FULL_MASTERY_CERTIFIED_SHA256["dll"]
        or parent_chain.get("parent_current_rendered_sha256")
        != VV2_INDIVIDUAL_FULL_MASTERY_CURRENT_PARENT_SHA256
        or parent_chain.get("current_baseline_sha256")
        != VV2_INDIVIDUAL_FULL_MASTERY_CURRENT_BASELINE_SHA256
        or parent_chain.get("parent_static_acceptance_sha256")
        != {
            mode: details["candidate_sha256"]
            for mode, details in VV2_FULL_MASTERY_STATIC_ACCEPTANCE["rendered_candidates"].items()
        }
    ):
        raise PatcherError("VV2 selected Full Mastery parent chain is invalid.")
    parent_drift = parent_chain.get("parent_render_drift", {})
    if parent_drift != {
        "classification": "one automatic:safety cave replacement plus the deterministic PE checksum; no parent-owned hook, command-7, section, or DLL byte changed",
        "commit": "f9e5fd90bc998361b58c9c4849800dbd8cda6764",
        "commit_subject": "Fix VV2 event allocation context",
        "owner": "automatic:safety",
        "raw_offset": "0x73D00",
        "current_length": 47,
        "accepted_payload_length": 27,
        "accepted_payload_hex": "51E85A1BFBFF3D00010000597D05E96DB8FDFFB8FFFFFFFFC21400",
        "accepted_zero_tail_length": 20,
        "current_payload_hex": "518B8DA450000085C9741B83B9A4050300007412E8471BFBFF3D00010000597306E95AB8FDFF59B8FFFFFFFFC21400",
        "checksum_raw_offset": "0x148",
        "accepted_checksums": {
            "collection_progression": "0x000B77C9",
            "immediate_fixed": "0x000B62B9",
        },
        "current_checksums": {
            "collection_progression": "0x000BA721",
            "immediate_fixed": "0x000B9211",
        },
        "reconstruction": "replace the 47-byte current cave with the 27-byte accepted payload plus 20 zeros, then recompute the PE checksum; both frozen parent hashes reproduce exactly",
    }:
        raise PatcherError("VV2 selected Full Mastery parent render drift classification is invalid.")
    patches = manifest.get("patches")
    expected_patches = (
        (0x67624, "8B4C242088", "E917CC0400", 5),
        (0x67720, "837C240408", "E9DBCA0400", 5),
        (0xB2200, None, None, 34),
        (0xB2240, None, None, 110),
        (0xB2300, None, None, 1552),
        (0xB2D00, None, None, 762),
    )
    if not isinstance(patches, list) or len(patches) != len(expected_patches):
        raise PatcherError("VV2 selected Full Mastery patch count is invalid.")
    emitted = manifest.get("emitted", {})
    labels = ("detail_handler", "detail_constructor", "helper", "strings")
    for index, (offset, exact_before, exact_after, length) in enumerate(expected_patches):
        patch = patches[index]
        try:
            before = bytes.fromhex(patch["before"])
            after = bytes.fromhex(patch["after"])
        except (KeyError, TypeError, ValueError) as exc:
            raise PatcherError("VV2 selected Full Mastery patch bytes are malformed.") from exc
        if (
            int(patch.get("offset", "-1"), 0) != offset
            or len(before) != length
            or len(after) != length
            or (exact_before is not None and patch.get("before") != exact_before)
            or (exact_after is not None and patch.get("after") != exact_after)
            or (index >= 2 and any(before))
        ):
            raise PatcherError(f"VV2 selected Full Mastery patch 0x{offset:X} is invalid.")
        if index >= 2:
            label = labels[index - 2]
            item = emitted.get(label, {})
            if (
                item.get("raw") != f"0x{offset:X}"
                or item.get("length") != length
                or item.get("sha256") != VV2_INDIVIDUAL_FULL_MASTERY_EMITTED_SHA256[label]
                or hashlib.sha256(after).hexdigest().upper()
                != VV2_INDIVIDUAL_FULL_MASTERY_EMITTED_SHA256[label]
            ):
                raise PatcherError(f"VV2 selected Full Mastery {label} bytes are invalid.")
    rendered_modes = manifest.get("rendered_modes", {})
    for mode in ("collection_progression", "immediate_fixed"):
        rendered = rendered_modes.get(mode, {})
        if (
            rendered.get("current_baseline_sha256")
            != VV2_INDIVIDUAL_FULL_MASTERY_CURRENT_BASELINE_SHA256[mode]
            or rendered.get("uninstall_target_sha256")
            != VV2_INDIVIDUAL_FULL_MASTERY_CURRENT_PARENT_SHA256[mode]
            or rendered.get("parent_uninstall_target_sha256")
            != VV2_INDIVIDUAL_FULL_MASTERY_CURRENT_BASELINE_SHA256[mode]
            or rendered.get("parent_sha256")
            != VV2_INDIVIDUAL_FULL_MASTERY_CURRENT_PARENT_SHA256[mode]
            or rendered.get("candidate_sha256")
            != VV2_INDIVIDUAL_FULL_MASTERY_OUTPUT_SHA256[mode]
            or rendered.get("size") != 733_184
        ):
            raise PatcherError(f"VV2 selected Full Mastery {mode} identity is invalid.")
    if (
        artifact_map.get("candidate_id") != VV2_INDIVIDUAL_FULL_MASTERY_CANDIDATE_ID
        or artifact_map.get("enabled") is not True
        or artifact_map.get("catalog_hidden") is not False
        or artifact_map.get("catalog_enabled") is not True
        or artifact_map.get("dependencies") != ["vv2_full_mastery_all_stage_a_candidate"]
        or artifact_map.get("parent_chain") != parent_chain
        or artifact_map.get("static_evidence") != manifest.get("static_evidence")
        or artifact_map.get("emitted") != emitted
        or artifact_map.get("transaction_contract") != contract
        or artifact_map.get("rendered_modes") != rendered_modes
    ):
        raise PatcherError("VV2 selected Full Mastery map is not bound to the manifest.")
    return manifest


def _certified_vv1_full_mastery_record() -> dict[str, Any] | None:
    manifest = json.loads(
        VV1_FULL_MASTERY_CANDIDATE_PATHS["manifest"].read_text(encoding="utf-8")
    )
    if not manifest.get("enabled", True):
        return None
    if (
        manifest.get("id") != "vv1_full_mastery_all_stage_a_candidate"
        or manifest.get("catalog_hidden") is not False
    ):
        raise PatcherError(
            "VV1 Full Mastery catalog metadata is not explicitly enabled; refusing enablement."
        )
    acceptance = manifest.get("acceptance")
    if not isinstance(acceptance, dict):
        raise PatcherError("VV1 Full Mastery acceptance metadata is missing; refusing enablement.")
    if acceptance.get("source_commit") != "2f22a8b435918bf01b95aa4b9a6e6f4287d0ac94":
        raise PatcherError("VV1 Full Mastery acceptance source commit is not the recertified commit.")
    if acceptance.get("allowed_modes") != ["collection_progression", "immediate_fixed"]:
        raise PatcherError("VV1 Full Mastery acceptance permits a non-stock mode.")
    if acceptance.get("expanded_rejected") is not True:
        raise PatcherError("VV1 Full Mastery Expanded-256 rejection is not certified.")
    if acceptance.get("reviews") != ["C76", "D82", "C83"]:
        raise PatcherError("VV1 Full Mastery independent review set is not certified.")
    if acceptance.get("bundle") != "outputs/vv1-full-mastery-c76-recert":
        raise PatcherError("VV1 Full Mastery recertification bundle is not certified.")
    for key, expected in (
        ("source_sha256", VV1_FULL_MASTERY_CERTIFIED_SHA256["source"]),
        ("companion_sha256", VV1_FULL_MASTERY_CERTIFIED_SHA256["dll"]),
        ("active_origins_base_sha256", VV1_FULL_MASTERY_CERTIFIED_SHA256["active_origins"]),
        ("isolated_candidate_sha256", VV1_FULL_MASTERY_CERTIFIED_SHA256["candidate"]),
        ("combined_origins_full_mastery_sha256", VV1_FULL_MASTERY_CERTIFIED_SHA256["combined"]),
        ("uninstalled_sha256", VV1_FULL_MASTERY_CERTIFIED_SHA256["active_origins"]),
    ):
        if acceptance.get(key) != expected:
            raise PatcherError(f"VV1 Full Mastery acceptance hash {key} is not certified.")
    if acceptance.get("uninstall_equals_active_origins_base") is not True:
        raise PatcherError("VV1 Full Mastery uninstall equality is not certified.")
    artifact_map = json.loads(
        VV1_FULL_MASTERY_CANDIDATE_PATHS["map"].read_text(encoding="utf-8")
    )
    if artifact_map.get("acceptance_commit") != acceptance["source_commit"]:
        raise PatcherError("VV1 Full Mastery map acceptance commit is not certified.")
    if artifact_map.get("catalog_enabled") is not True:
        raise PatcherError("VV1 Full Mastery map catalog gate is not enabled.")
    independent = artifact_map.get("independent_recertification")
    if not isinstance(independent, dict) or independent.get("status") != "GO":
        raise PatcherError("VV1 Full Mastery map independent recertification is not GO.")
    if independent.get("reviews") != acceptance["reviews"] or independent.get("source_commit") != acceptance["source_commit"]:
        raise PatcherError("VV1 Full Mastery map review binding is not certified.")
    if independent.get("bundle") != acceptance["bundle"] or independent.get("expanded_rejected") is not True:
        raise PatcherError("VV1 Full Mastery map mode/bundle gate is not certified.")
    for label in ("section", "entry", "walker", "confirmation", "menu_resolver", "result_resolver"):
        actual = artifact_map.get(f"{label}_sha256")
        expected = VV1_FULL_MASTERY_CERTIFIED_SHA256[label]
        if actual != expected:
            raise PatcherError(
                f"Certified VV1 Full Mastery {label} artifact hash mismatch: "
                f"expected {expected}, got {actual}."
            )
    source = artifact_map.get("source", {})
    if source.get("sha256") != VV1_FULL_MASTERY_CERTIFIED_SHA256["source"]:
        raise PatcherError("VV1 Full Mastery source fingerprint metadata is not certified.")
    if artifact_map.get("allowed_modes") != ["collection_progression", "immediate_fixed"]:
        raise PatcherError("VV1 Full Mastery map permits a non-stock mode.")
    if artifact_map.get("rejected_modes") != [
        "experimental_expanded_256",
        "experimental_expanded_256_progression",
    ]:
        raise PatcherError("VV1 Full Mastery map does not reject both Expanded-256 modes.")
    rendered = artifact_map.get("rendered_candidates", {})
    for mode in ("collection_progression", "immediate_fixed"):
        record = rendered.get(mode, {})
        if record.get("candidate_sha256") != VV1_FULL_MASTERY_CERTIFIED_SHA256["candidate"]:
            raise PatcherError("VV1 Full Mastery rendered candidate hash is not certified.")
        if record.get("uninstall_target_sha256") != record.get("baseline_sha256"):
            raise PatcherError("VV1 Full Mastery uninstall target does not equal its baseline.")
    dll_digest = hashlib.sha256(
        VV1_FULL_MASTERY_CANDIDATE_PATHS["dll"].read_bytes()
    ).hexdigest().upper()
    if dll_digest != VV1_FULL_MASTERY_CERTIFIED_SHA256["dll"]:
        raise PatcherError(
            "Certified VV1 Full Mastery DLL hash mismatch: "
            f"expected {VV1_FULL_MASTERY_CERTIFIED_SHA256['dll']}, got {dll_digest}."
        )
    return manifest


def _certified_vv1_individual_full_mastery_record() -> dict[str, Any] | None:
    """Validate the public stock-only VV1 selected-villager overlay fail closed."""
    manifest_bytes = VV1_INDIVIDUAL_FULL_MASTERY_CANDIDATE_PATHS["manifest"].read_bytes()
    map_bytes = VV1_INDIVIDUAL_FULL_MASTERY_CANDIDATE_PATHS["map"].read_bytes()
    if source_text_sha256(manifest_bytes) != VV1_INDIVIDUAL_FULL_MASTERY_MANIFEST_SHA256:
        raise PatcherError("VV1 selected Full Mastery manifest bytes are not certified.")
    if source_text_sha256(map_bytes) != VV1_INDIVIDUAL_FULL_MASTERY_MAP_SHA256:
        raise PatcherError("VV1 selected Full Mastery map bytes are not certified.")
    if (
        source_text_sha256(VV1_FULL_MASTERY_CANDIDATE_PATHS["manifest"].read_bytes())
        != VV1_INDIVIDUAL_FULL_MASTERY_PARENT_ARTIFACT_SHA256["manifest"]
        or source_text_sha256(VV1_FULL_MASTERY_CANDIDATE_PATHS["map"].read_bytes())
        != VV1_INDIVIDUAL_FULL_MASTERY_PARENT_ARTIFACT_SHA256["map"]
        or hashlib.sha256(VV1_FULL_MASTERY_CANDIDATE_PATHS["dll"].read_bytes()).hexdigest().upper()
        != VV1_INDIVIDUAL_FULL_MASTERY_PARENT_ARTIFACT_SHA256["dll"]
    ):
        raise PatcherError("VV1 selected Full Mastery parent artifacts are not certified.")
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    artifact_map = json.loads(map_bytes.decode("utf-8"))
    if not manifest.get("enabled", False):
        return None
    if (
        manifest.get("id") != VV1_INDIVIDUAL_FULL_MASTERY_CANDIDATE_ID
        or manifest.get("game_id") != "vv1"
        or manifest.get("catalog_hidden") is not False
        or manifest.get("catalog_enabled") is not True
        or manifest.get("runtime_player_status") != "pending"
        or manifest.get("dependencies") != ["vv1_full_mastery_all_stage_a_candidate"]
        or set(manifest.get("conflicts", ())) != VV1_INDIVIDUAL_FULL_MASTERY_CONFLICTS
        or manifest.get("companion_files") != []
        or manifest.get("supported_modes") != ["collection_progression", "immediate_fixed"]
        or set(manifest.get("rejected_modes", ())) != EXPANDED_PATCH_MODES
    ):
        raise PatcherError("VV1 selected Full Mastery catalog/mode metadata is invalid.")
    contract = manifest.get("transaction_contract", {})
    if (
        contract.get("detail_event") != 8
        or contract.get("button_id") != 6
        or contract.get("price") != 100_000
        or contract.get("target") != 100
        or contract.get("ownership") is not None
        or contract.get("eligibility_before_skills")
        != ["byte +0x28 != 0", "signed dword +0x344 > 0", "dword +0x36C != 199"]
        or "sub_437230" not in str(contract.get("native_skill_writer"))
        or "state+0xA2FC" not in str(contract.get("tech_deduction"))
        or "sub_41D120" not in str(contract.get("tech_deduction"))
        or "state+0x9E20" not in str(contract.get("tech_deduction"))
    ):
        raise PatcherError("VV1 selected Full Mastery transaction contract is invalid.")
    parent_chain = manifest.get("parent_chain", {})
    if (
        parent_chain.get("stock_sha256") != VV1_FULL_MASTERY_CERTIFIED_SHA256["source"]
        or parent_chain.get("parent_manifest_source_text_sha256")
        != VV1_INDIVIDUAL_FULL_MASTERY_PARENT_ARTIFACT_SHA256["manifest"]
        or parent_chain.get("parent_map_source_text_sha256")
        != VV1_INDIVIDUAL_FULL_MASTERY_PARENT_ARTIFACT_SHA256["map"]
        or parent_chain.get("parent_dll_sha256")
        != VV1_INDIVIDUAL_FULL_MASTERY_PARENT_ARTIFACT_SHA256["dll"]
        or parent_chain.get("parent_rendered_sha256")
        != VV1_INDIVIDUAL_FULL_MASTERY_PARENT_SHA256
        or parent_chain.get("current_baseline_sha256")
        != VV1_INDIVIDUAL_FULL_MASTERY_BASELINE_SHA256
    ):
        raise PatcherError("VV1 selected Full Mastery parent chain is invalid.")
    patches = manifest.get("patches")
    expected_patches = (
        (0x4A5FA, "8B4C241C5F", "E9C1640400", 5),
        (0x4A700, "8B44240453", "E97B630400", 5),
        (0x8EA80, None, None, 34),
        (0x8EAC0, None, None, 97),
        (0x8EB80, None, None, 1228),
        (0x8F600, None, None, 760),
    )
    if not isinstance(patches, list) or len(patches) != len(expected_patches):
        raise PatcherError("VV1 selected Full Mastery patch count is invalid.")
    emitted = manifest.get("emitted", {})
    labels = ("detail_handler", "detail_constructor", "helper", "strings")
    for index, (offset, exact_before, exact_after, length) in enumerate(expected_patches):
        patch = patches[index]
        try:
            before = bytes.fromhex(patch["before"])
            after = bytes.fromhex(patch["after"])
        except (KeyError, TypeError, ValueError) as exc:
            raise PatcherError("VV1 selected Full Mastery patch bytes are malformed.") from exc
        if (
            int(patch.get("offset", "-1"), 0) != offset
            or len(before) != length
            or len(after) != length
            or (exact_before is not None and patch.get("before") != exact_before)
            or (exact_after is not None and patch.get("after") != exact_after)
            or (index >= 2 and any(before))
        ):
            raise PatcherError(f"VV1 selected Full Mastery patch 0x{offset:X} is invalid.")
        if index >= 2:
            label = labels[index - 2]
            item = emitted.get(label, {})
            if (
                item.get("raw") != f"0x{offset:X}"
                or item.get("length") != length
                or item.get("sha256") != VV1_INDIVIDUAL_FULL_MASTERY_EMITTED_SHA256[label]
                or hashlib.sha256(after).hexdigest().upper()
                != VV1_INDIVIDUAL_FULL_MASTERY_EMITTED_SHA256[label]
            ):
                raise PatcherError(f"VV1 selected Full Mastery {label} bytes are invalid.")
    rendered_modes = manifest.get("rendered_modes", {})
    for mode in ("collection_progression", "immediate_fixed"):
        rendered = rendered_modes.get(mode, {})
        if (
            rendered.get("current_baseline_sha256")
            != VV1_INDIVIDUAL_FULL_MASTERY_BASELINE_SHA256[mode]
            or rendered.get("parent_sha256")
            != VV1_INDIVIDUAL_FULL_MASTERY_PARENT_SHA256[mode]
            or rendered.get("candidate_sha256")
            != VV1_INDIVIDUAL_FULL_MASTERY_OUTPUT_SHA256[mode]
            or rendered.get("uninstall_target_sha256")
            != VV1_INDIVIDUAL_FULL_MASTERY_PARENT_SHA256[mode]
            or rendered.get("parent_uninstall_target_sha256")
            != VV1_INDIVIDUAL_FULL_MASTERY_BASELINE_SHA256[mode]
            or rendered.get("size") != 589_824
        ):
            raise PatcherError(f"VV1 selected Full Mastery {mode} identity is invalid.")
    if (
        artifact_map.get("candidate_id") != VV1_INDIVIDUAL_FULL_MASTERY_CANDIDATE_ID
        or artifact_map.get("enabled") is not True
        or artifact_map.get("catalog_hidden") is not False
        or artifact_map.get("catalog_enabled") is not True
        or artifact_map.get("dependencies") != ["vv1_full_mastery_all_stage_a_candidate"]
        or set(artifact_map.get("conflicts", ())) != VV1_INDIVIDUAL_FULL_MASTERY_CONFLICTS
        or artifact_map.get("parent_chain") != parent_chain
        or artifact_map.get("static_evidence") != manifest.get("static_evidence")
        or artifact_map.get("emitted") != emitted
        or artifact_map.get("transaction_contract") != contract
        or artifact_map.get("rendered_modes") != rendered_modes
    ):
        raise PatcherError("VV1 selected Full Mastery map is not bound to the manifest.")
    return manifest


def _certified_vv4_full_mastery_records(
    active_base: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    base = json.loads(VV4_FULL_MASTERY_CANDIDATE_PATHS["base"].read_text(encoding="utf-8"))
    feature = json.loads(
        VV4_FULL_MASTERY_CANDIDATE_PATHS["feature"].read_text(encoding="utf-8")
    )
    if not base.get("enabled", True) or not feature.get("enabled", True):
        return None
    artifact = json.loads(
        VV4_FULL_MASTERY_CANDIDATE_PATHS["map"].read_text(encoding="utf-8")
    )
    gate = artifact.get("ui_asset_gate")
    if not isinstance(gate, dict):
        raise PatcherError("VV4 Full Mastery UI asset gate is missing; refusing enablement.")
    legacy_gate_keys = sorted(VV4_FULL_MASTERY_LEGACY_ASSET_KEYS.intersection(gate))
    if legacy_gate_keys:
        raise PatcherError(
            "VV4 Full Mastery legacy custom-asset metadata is forbidden: "
            + ", ".join(legacy_gate_keys)
        )
    if gate.get("status") != "independent metadata recertification GO":
        raise PatcherError(
            "VV4 Full Mastery UI asset gate is not independently recertified; "
            "refusing enablement."
        )
    if gate.get("runtime_source") != r"native cached VV4 Images\btn_trophies.png" or gate.get("ordinal") != "0x8C":
        raise PatcherError("VV4 Full Mastery native ordinal asset identity is invalid.")
    if gate.get("custom_runtime_companion") is not None:
        raise PatcherError("VV4 Full Mastery custom runtime asset must be absent.")
    if gate.get("dimensions") != [100, 39] or gate.get("bounds_half_open") != [72, 4, 172, 43]:
        raise PatcherError("VV4 Full Mastery native asset dimensions/bounds are invalid.")
    if gate.get("factory") != "sub_401C20" or gate.get("add_child") != "sub_40C190":
        raise PatcherError("VV4 Full Mastery UI asset factory/ownership gate is invalid.")
    if gate.get("local") != [72, 4]:
        raise PatcherError("VV4 Full Mastery UI asset geometry gate is invalid.")
    if gate.get("events") != {"tech": 13, "detail": 2}:
        raise PatcherError("VV4 Full Mastery UI asset event gate is invalid.")
    runtime_guard = gate.get("runtime_wrapper_contract")
    if not isinstance(runtime_guard, dict):
        raise PatcherError(
            "VV4 Full Mastery runtime wrapper contract is missing; refusing enablement."
        )
    if runtime_guard.get("nonnull_outer_and_inner") != {"attach": True, "tech_slot": "this+0x74"}:
        raise PatcherError("VV4 Full Mastery nonnull ownership contract is invalid.")
    if runtime_guard.get("null_outer") != {"attach": False, "tech_slot": None}:
        raise PatcherError("VV4 Full Mastery null-wrapper contract is invalid.")
    if runtime_guard.get("null_inner") != {
        "attach": False,
        "scalar_destroy_flag": 1,
        "tech_slot": None,
    }:
        raise PatcherError("VV4 Full Mastery incomplete-wrapper cleanup contract is invalid.")
    if runtime_guard.get("runtime_dimension_accessors") != (
        "none; wrapper vtable +0x0C/+0x10 are not image dimensions"
    ):
        raise PatcherError("VV4 Full Mastery runtime dimension accessor calls are forbidden.")
    static_asset = runtime_guard.get("static_asset_contract")
    if isinstance(static_asset, dict):
        legacy_static_keys = sorted(
            VV4_FULL_MASTERY_LEGACY_STATIC_ASSET_KEYS.intersection(static_asset)
        )
        if legacy_static_keys:
            raise PatcherError(
                "VV4 Full Mastery legacy static custom-asset metadata is forbidden: "
                + ", ".join(legacy_static_keys)
            )
    if static_asset != {"ordinal": "0x8C", "asset": "btn_trophies.png", "dimensions": [100, 39], "bounds_half_open": [72, 4, 172, 43], "ownership": "borrowed native cache"}:
        raise PatcherError("VV4 Full Mastery native cached asset contract is invalid.")
    tech_wrapper = gate.get("tech_wrapper")
    if not isinstance(tech_wrapper, dict) or tech_wrapper.get("helper_length") != 34:
        raise PatcherError("VV4 Full Mastery Tech destructor helper length guard is invalid.")
    if tech_wrapper.get("ecx_restore") != "mov ecx, ebx":
        raise PatcherError("VV4 Full Mastery Tech destructor ECX restore guard is invalid.")
    forbidden = set(gate.get("forbidden_helpers", []))
    if forbidden != {"sub_40D8A0"}:
        raise PatcherError("VV4 Full Mastery UI asset helper exclusion gate is incomplete.")
    overlay = artifact.get("candidate_ui_payload", {}).get("text_overlay")
    if overlay != {"text": "Upgrades", "setter": "sub_401600", "style": "sub_401630", "tech_colors": ["0x4BEEE0", "0x4BEEE4", "0x4BEEE8"], "detail_colors": ["0x4BF538", "0x4BF53C", "0x4BF540"]}:
        raise PatcherError("VV4 Full Mastery native text overlay contract is invalid.")
    recertification = artifact.get("independent_recertification")
    if not isinstance(recertification, dict):
        raise PatcherError("VV4 Full Mastery D19 recertification evidence is missing.")
    if (
        recertification.get("status") != "independent payload recertification GO"
        or recertification.get("review") != "D19"
        or recertification.get("commit") != VV4_FULL_MASTERY_D19_COMMIT
        or recertification.get("scope") != "VV4 Full Mastery stock-mode candidate only; Expanded-256 ON HOLD/fail-closed"
    ):
        raise PatcherError("VV4 Full Mastery independent recertification scope/status is invalid.")
    metadata_recertification = artifact.get("metadata_recertification")
    if metadata_recertification != {
        "review": "D21",
        "status": "independent metadata recertification GO",
        "commit": VV4_FULL_MASTERY_D21_COMMIT,
        "scope": "VV4 Full Mastery metadata/validator enablement for stock mode only; Expanded-256 ON HOLD/fail-closed",
    }:
        raise PatcherError("VV4 Full Mastery D21 metadata recertification is invalid.")
    ui_payload = artifact.get("candidate_ui_payload")
    if not isinstance(ui_payload, dict):
        raise PatcherError("VV4 Full Mastery candidate UI payload evidence is missing.")
    ui_hashes: dict[str, Any] = {}
    for label, section_name in (
        ("native_factory", "native_factory"),
        ("helper", "destructor_helper"),
        ("tech_constructor", "tech_constructor"),
        ("detail_constructor", "detail_constructor"),
    ):
        section = ui_payload.get(section_name)
        if not isinstance(section, dict) or not isinstance(section.get("sha256"), str):
            raise PatcherError("VV4 Full Mastery UI constructor/helper hashes are missing.")
        ui_hashes[label] = section["sha256"]
    if any(ui_hashes[label] != VV4_FULL_MASTERY_D19_HASHES[label] for label in ui_hashes):
        raise PatcherError("VV4 Full Mastery D19 UI byte hash is invalid.")
    recert_hashes = recertification.get("hashes")
    if not isinstance(recert_hashes, dict) or any(
        recert_hashes.get(label) != value
        for label, value in ui_hashes.items()
    ):
        raise PatcherError("VV4 Full Mastery recertification does not cover current UI bytes.")
    if not isinstance(artifact.get("acceptance_commit"), str):
        raise PatcherError("VV4 Full Mastery acceptance commit is missing.")
    cure_patch = None
    for item in base.get("patches", []):
        if not isinstance(item, dict):
            continue
        try:
            if int(item.get("offset", "-1"), 0) == 0xCC004:
                cure_patch = item
                break
        except (TypeError, ValueError):
            continue
    try:
        cure_hash = hashlib.sha256(bytes.fromhex(cure_patch["after"])).hexdigest().upper() if isinstance(cure_patch, dict) else ""
    except (KeyError, TypeError, ValueError):
        cure_hash = ""
    if cure_hash != VV4_FULL_MASTERY_D19_HASHES["cure"]:
        raise PatcherError("VV4 Full Mastery Cure payload hash is not the frozen value.")
    if artifact.get("ui_asset_gate", {}).get("scope") != "stock-mode only; Expanded-256 remains ON HOLD/fail-closed":
        raise PatcherError("VV4 Full Mastery UI asset scope is not stock-only fail-closed.")
    containment = artifact.get("cure_containment")
    if not isinstance(containment, dict):
        raise PatcherError("VV4 Full Mastery Cure containment evidence is missing.")
    if containment.get("dispatch", {}).get("command") != 5:
        raise PatcherError("VV4 Full Mastery Cure command-5 containment is invalid.")
    if containment.get("dispatch", {}).get("after_opcode") != "77":
        raise PatcherError("VV4 Full Mastery Cure command-5 no-charge guard is invalid.")
    if containment.get("dispatch", {}).get("forbidden_target_reachable") is not False:
        raise PatcherError("VV4 Full Mastery Cure forbidden target is not fail-closed.")
    if containment.get("public_row", {}).get("selectable") is not False:
        raise PatcherError("VV4 Full Mastery Cure public row is still selectable.")
    if containment.get("payload_sha256") != VV4_FULL_MASTERY_D19_HASHES["cure"]:
        raise PatcherError("VV4 Full Mastery Cure payload was changed.")
    stock = artifact["layouts"]["collection_progression"]
    expanded = artifact["layouts"]["experimental_expanded_256"]
    actual = {
        "entry": stock["slot_map"]["installed"]["entry_sha256"],
        "walker": stock["slot_map"]["installed"]["walker_sha256"],
        "confirmation": stock["slot_map"]["installed"]["confirmation_sha256"],
        "stock_page": stock["installed_page_sha256"],
        "expanded_page": expanded["installed_page_sha256"],
        "dll": hashlib.sha256(
            VV4_FULL_MASTERY_CANDIDATE_PATHS["dll"].read_bytes()
        ).hexdigest().upper(),
    }
    for label, expected in VV4_FULL_MASTERY_CERTIFIED_SHA256.items():
        if actual[label] != expected:
            raise PatcherError(
                f"Certified VV4 Full Mastery {label} artifact hash mismatch: "
                f"expected {expected}, got {actual[label]}."
            )
    if stock.get("legacy_command7_slot_sha256") != VV4_FULL_MASTERY_D19_HASHES["command7_slot"]:
        raise PatcherError("Certified VV4 legacy command-7 slot hash mismatch.")
    base = dict(base)
    base.update(
        {"id": active_base["id"], "name": active_base["name"], "enabled": True}
    )
    feature = dict(feature)
    feature.update(
        {
            "id": "vv4_full_mastery_all_stage_a_candidate",
            "name": "Grant Full Mastery to All Villagers",
            "enabled": True,
            "dependencies": [active_base["id"]],
        }
    )
    return base, feature


def _certified_vv4_full_heal_record(
    active_base: dict[str, Any],
    mastery_feature: dict[str, Any],
) -> dict[str, Any] | None:
    """Validate the disabled VV4 Full Heal contract before future output.

    The candidate is intentionally not part of the public catalog yet.  Once
    its exact stock hook and `.vv4hc` page receive independent recertification,
    this gate is the only place that may admit it into a VV4 composition.
    """

    manifest_path = VV4_FULL_HEAL_CANDIDATE_PATHS["manifest"]
    map_path = VV4_FULL_HEAL_CANDIDATE_PATHS["map"]
    if not manifest_path.is_file() or not map_path.is_file():
        return None
    manifest_bytes = manifest_path.read_bytes()
    map_bytes = map_path.read_bytes()
    try:
        manifest = json.loads(manifest_bytes.decode("utf-8-sig"))
        artifact_map = json.loads(map_bytes.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PatcherError("VV4 Full Heal candidate manifest/map is malformed.") from exc
    disabled_manifest = (
        manifest.get("id") == VV4_FULL_HEAL_CANDIDATE_ID
        and manifest.get("enabled") is False
        and manifest.get("catalog_hidden") is True
        and manifest.get("catalog_enabled") is False
    )
    disabled_map = (
        artifact_map.get("candidate_id") == VV4_FULL_HEAL_CANDIDATE_ID
        and artifact_map.get("candidate_enabled") is False
        and artifact_map.get("catalog_hidden") is True
        and artifact_map.get("catalog_enabled") is False
    )
    if disabled_manifest and disabled_map:
        return None
    if disabled_manifest != disabled_map:
        raise PatcherError("VV4 Full Heal disabled/catalog-hidden records disagree.")
    if source_text_sha256(manifest_bytes) != VV4_FULL_HEAL_MANIFEST_SHA256 or source_text_sha256(map_bytes) != VV4_FULL_HEAL_MAP_SHA256:
        raise PatcherError("VV4 Full Heal enabled candidate manifest/map raw bytes are not pinned.")
    manifest_proof = manifest.get("lineage_proof", {})
    map_proof = artifact_map.get("lineage_proof", {})
    if (manifest_proof.get("protected_range_end_inclusive") is not VV4_FULL_HEAL_PROTECTED_RANGE_END_INCLUSIVE
            or map_proof.get("protected_range_end_inclusive") is not VV4_FULL_HEAL_PROTECTED_RANGE_END_INCLUSIVE):
        raise PatcherError("VV4 Full Heal protected-range endpoint convention is invalid.")
    if any("raw_end_exclusive" not in item
           for proof in (manifest_proof, map_proof)
           for item in proof.get("allowed_diff_ranges", [])):
        raise PatcherError("VV4 Full Heal allowed-difference endpoints must be exclusive.")
    if manifest.get("enabled") is not True or artifact_map.get("candidate_enabled") is not True:
        raise PatcherError("VV4 Full Heal candidate state is neither strictly disabled nor enabled.")
    if manifest.get("catalog_hidden") is not False or manifest.get("catalog_enabled") is not True:
        raise PatcherError("VV4 Full Heal candidate must be explicitly catalog-visible when enabled.")
    if manifest.get("id") != VV4_FULL_HEAL_CANDIDATE_ID or artifact_map.get("candidate_id") != VV4_FULL_HEAL_CANDIDATE_ID:
        raise PatcherError("VV4 Full Heal candidate identity is invalid.")
    expected_vv4_full_heal_dependencies = list(VV4_FULL_HEAL_PARENT_DEPENDENCIES)
    if active_base["id"] != expected_vv4_full_heal_dependencies[1] or mastery_feature["id"] != expected_vv4_full_heal_dependencies[2]:
        raise PatcherError("VV4 Full Heal parent IDs are not the current loader identities.")
    if manifest.get("dependencies") != expected_vv4_full_heal_dependencies:
        raise PatcherError("VV4 Full Heal requires the current VV4 Full Mastery parent chain.")
    if artifact_map.get("dependencies") != expected_vv4_full_heal_dependencies:
        raise PatcherError("VV4 Full Heal map dependency identity is not current.")
    parent_composition = manifest.get("parent_composition", {})
    map_parent_composition = artifact_map.get("parent_composition", {})
    expected_composition = {
        "ids": expected_vv4_full_heal_dependencies,
        "order": expected_vv4_full_heal_dependencies,
        "collection_sha256": VV4_FULL_HEAL_PARENT_COLLECTION_SHA256,
        "immediate_sha256": VV4_FULL_HEAL_PARENT_IMMEDIATE_SHA256,
    }
    if parent_composition != expected_composition or map_parent_composition != expected_composition:
        raise PatcherError("VV4 Full Heal parent composition is not the current complete loader chain.")
    expected_rendered_modes = {
        "collection_progression": {"parent_sha256": VV4_FULL_HEAL_PARENT_COLLECTION_SHA256, "candidate_sha256": VV4_FULL_HEAL_CANDIDATE_EXE_HASHES["collection_progression"], "size": 942080},
        "immediate_fixed": {"parent_sha256": VV4_FULL_HEAL_PARENT_IMMEDIATE_SHA256, "candidate_sha256": VV4_FULL_HEAL_CANDIDATE_EXE_HASHES["immediate_fixed"], "size": 942080},
    }
    if manifest.get("rendered_modes") != expected_rendered_modes or artifact_map.get("rendered_modes") != expected_rendered_modes:
        raise PatcherError("VV4 Full Heal rendered parent/candidate identities are not pinned.")
    if manifest.get("supported_modes") != ["collection_progression", "immediate_fixed"] or set(manifest.get("rejected_modes", ())) != EXPANDED_PATCH_MODES:
        raise PatcherError("VV4 Full Heal mode gate is invalid.")
    if manifest.get("source", {}).get("stock_sha256") != VV4_FULL_HEAL_STOCK_SHA256 or artifact_map.get("source", {}).get("sha256") != VV4_FULL_HEAL_STOCK_SHA256:
        raise PatcherError("VV4 Full Heal stock fingerprint is invalid.")
    if manifest.get("source", {}).get("parent_vv4fm_page_sha256") != VV4_FULL_HEAL_PARENT_PAGE_SHA256:
        raise PatcherError("VV4 Full Heal Full Mastery page parent is invalid.")
    if manifest.get("source", {}).get("parent_dll_sha256") != VV4_FULL_HEAL_PARENT_DLL_SHA256:
        raise PatcherError("VV4 Full Heal companion parent is invalid.")
    transaction = manifest.get("transaction", {})
    if transaction != {
        "command": 5,
        "price": 30000,
        "action": "Buy",
        "repeatable": True,
        "ownership": None,
        "remove": False,
        "physical_bound": 150,
        "enumeration": VV4_FULL_HEAL_ENUMERATION,
        "dry_run_before_warning_or_charge": True,
        "confirmation_counts": ["predicted_sick", "predicted_partial_health"],
        "success_counts": ["actual_sick_cured", "actual_partial_health_restored"],
        "deduction": {"receiver": "0x4D6F88", "push_amount": -30000, "call": "0x41E300", "ret": 4, "calls": 1, "only_after_postverify": True},
        "people_cured": {"receiver": "0x4D6DF0", "increment": 1, "only_after_verified_sickness_clear": True},
    }:
        raise PatcherError("VV4 Full Heal transaction contract is not immutable.")
    if transaction.get("people_cured") != {"receiver": "0x4D6DF0", "increment": 1, "only_after_verified_sickness_clear": True}:
        raise PatcherError("VV4 Full Heal People Cured identity is not immutable.")
    hook = manifest.get("hook", {})
    if (hook.get("owned_ranges") != artifact_map.get("hook", {}).get("ranges")
            or hook.get("hook_length") != 5
            or hook.get("hook_before_parent") != "E941FEFFFF"
            or hook.get("hook_preserved_suffix") != "724C"
            or hook.get("hook_after") != "E9EC792B00"
            or hook.get("shim_bytes") != "83F8050F84F7000000E94784D4FF"
            or hook.get("shim_sha256") != "89A2E84C47D3130915A7830F48EC839C186A8BBABF7584681A83A4770582A370"
            or hook.get("helper_length") != 2053
            or hook.get("helper_sha256") != "F4271D44AB481D1441EA7D8D297AC346FCF0F2840EE9869B90EE1E875A4B403F"
            or hook.get("page_sha256") != "EC7E987845C3081C435CED913CCEE951CC67B0E766FAAB363D313D0B5874A739"
            or hook.get("strings_sha256") != "44CB71162F5F5298E8A6AB309D874EDD20D3B4C20B169DB3D2274F84DCC0717E"
            or hook.get("unknown_until_recertified")):
        raise PatcherError("VV4 Full Heal cannot enable before exact hook/page bytes are certified.")
    if manifest.get("messages", {}).get("label") != "Full Heal / Cure All" or manifest.get("messages", {}).get("failure_suffix") != "No tech points have been deducted.":
        raise PatcherError("VV4 Full Heal message contract is invalid.")
    companion = manifest.get("companion_files", [{}])[0]
    companion_map = artifact_map.get("companion", {})
    if (companion.get("sha256") != "165F327783DFECAB4C42DB28D6F926BCA46397F725F036BFC367BB659384C0AC"
            or companion.get("size") != 298496
            or companion.get("resource_directory_size") != "0x33800"
            or companion.get("source") != "generated:vv4_full_heal_companion"
            or companion.get("preimage_sha256") != VV4_FULL_HEAL_PARENT_DLL_SHA256
            or companion.get("restore_source") != "data/candidates/VVFP VV4 Full Mastery Candidate.dll"
            or companion.get("restore_sha256") != VV4_FULL_HEAL_PARENT_DLL_SHA256
            or companion.get("destination") != "VVFP Origins Icons.dll"
            or companion.get("artwork_resource_id") != 110
            or companion.get("artwork_sha256") != "83552374DFD7AC1AACC57D371C01C26BA1A438ADF34B904609A72165EB73C5A0"
            or companion.get("icon_leaf_sha256") != {
                "46": "68FED72757B4A8A28F69ABFB7A9ED4133647676EAE7665F44BA6D8931929DD23",
                "47": "7B599B3876B44BECA595FCE3ED7DFC984C99E014A057F6ED0BA25CA507F49B73",
                "48": "1D4C17E4E54C623485E9D7D8FE613D6D67F5511521256BBA8572B9EC76D70634",
                "49": "0122D77CF881F79BFD488BE98E917AB76BF2049AE5AF3CC44228AF3A35D70595",
            }
            or companion_map.get("sha256") != companion.get("sha256")
            or companion_map.get("size") != companion.get("size")
            or companion_map.get("parent_sha256") != VV4_FULL_HEAL_PARENT_DLL_SHA256
            or artifact_map.get("companion_resource_directory_size") != "0x33800"):
        raise PatcherError("VV4 Full Heal companion resource transform is not certified.")
    append_tx = manifest.get("pe_append_transaction")
    if not isinstance(append_tx, dict) or append_tx.get("section_name") != ".vv4hc":
        raise PatcherError("VV4 Full Heal append transaction metadata is not certified.")
    for mode_id in ("collection_progression", "immediate_fixed"):
        layout = append_tx.get("layouts", {}).get(mode_id)
        if not isinstance(layout, dict) or layout.get("append_source") != "generated:vv4_full_heal_page" or int(layout.get("original_file_size", "-1"), 0) != 0xE5000 or int(layout.get("append_offset", "-1"), 0) != 0xE5000:
            raise PatcherError("VV4 Full Heal append transaction mode is not certified.")
    ownership = artifact_map.get("ownership", {})
    if ownership.get("exe_hook") != {
        "raw": "0x8960F", "length": 5, "preimage": "E941FEFFFF",
        "candidate": "E9EC792B00", "preserved_suffix": "724C",
        "non_command5_continuation": "0x489455", "command5_continuation": "0x4895D9",
    } or ownership.get("page") != {
        "raw": "0xE5000", "length": 4096,
        "preimage_sha256": "zero-filled 0x1000",
        "candidate_sha256": "EC7E987845C3081C435CED913CCEE951CC67B0E766FAAB363D313D0B5874A739",
    } or ownership.get("companion") != {
        "destination": "VVFP Origins Icons.dll",
        "preimage_sha256": VV4_FULL_HEAL_PARENT_DLL_SHA256,
        "candidate_sha256": companion.get("sha256"),
        "restore_sha256": VV4_FULL_HEAL_PARENT_DLL_SHA256,
    }:
        raise PatcherError("VV4 Full Heal ownership records are not certified.")
    return manifest


def _validate_vv5_individual_running_candidate(
    feature: FunPatch,
    selected_fun_ids: set[str],
    patch_mode: str,
) -> None:
    """Validate the disabled VV5 Like/Dislike overlay before any PE mutation."""
    if patch_mode != "collection_progression":
        raise PatcherError("VV5 revised Running Immediate Fixed is unsupported until its exact parent is authenticated.")
    manifest_bytes = VV5_INDIVIDUAL_RUNNING_CANDIDATE_PATHS["manifest"].read_bytes()
    map_bytes = VV5_INDIVIDUAL_RUNNING_CANDIDATE_PATHS["map"].read_bytes()
    if source_text_sha256(manifest_bytes) != VV5_INDIVIDUAL_RUNNING_MANIFEST_SHA256:
        raise PatcherError("VV5 revised Running manifest source-text hash is not certified.")
    if source_text_sha256(map_bytes) != VV5_INDIVIDUAL_RUNNING_MAP_SHA256:
        raise PatcherError("VV5 revised Running map source-text hash is not certified.")
    raw = feature.raw
    if feature.id != VV5_INDIVIDUAL_RUNNING_CANDIDATE_ID:
        raise PatcherError("VV5 Running validator received an unexpected feature.")
    if raw.get("enabled", True) or not raw.get("catalog_hidden", False) or raw.get("catalog_enabled", True):
        raise PatcherError("VV5 revised Running must remain disabled and catalog-hidden pending recertification.")
    if patch_mode not in VV5_INDIVIDUAL_RUNNING_PARENT_SHA256:
        raise PatcherError("VV5 revised Running rejects Expanded-256 before output.")
    if raw.get("dependencies") != ["vv5_full_mastery_all_stage_a_candidate"]:
        raise PatcherError("VV5 revised Running requires the certified Full Mastery parent identity.")
    tx = raw.get("transaction_contract")
    required_likes = ["record+0x1F5C", "record+0x1F60", "record+0x1F64"]
    required_dislikes = ["record+0x1F68", "record+0x1F6C", "record+0x1F70"]
    if not isinstance(tx, dict) or tx.get("command") != 2 or tx.get("price") != 40000 or tx.get("action") != "Buy" or tx.get("repeatable") is not True or tx.get("ownership") is not None or tx.get("remove") is not False:
        raise PatcherError("VV5 revised Running transaction identity is not exact.")
    if tx.get("likes") != required_likes or tx.get("dislike_slots") != required_dislikes:
        raise PatcherError("VV5 revised Running must bind all six preference slots.")
    if tx.get("forbidden_reads") != ["movement", "speed"] or tx.get("accept_result") != 1 or tx.get("cancel_results") != [0, 2]:
        raise PatcherError("VV5 revised Running result/forbidden-read contract is malformed.")
    append = raw.get("pe_append_transaction")
    layout = append.get("layouts", {}).get(patch_mode) if isinstance(append, dict) else None
    expected_parent = VV5_INDIVIDUAL_RUNNING_PARENT_SHA256[patch_mode]
    if not isinstance(layout, dict) or layout.get("parent_sha256") != expected_parent or layout.get("append_source") != "generated:vv5_individual_running_page" or int(layout.get("original_file_size", "-1"), 0) != 0xF4000 or int(layout.get("append_offset", "-1"), 0) != 0xF4000 or int(layout.get("append_length", "-1")) != 0x2000:
        raise PatcherError("VV5 revised Running append layout is not bound to the certified composed parent.")
    if raw.get("parent_hashes", {}).get(patch_mode) != expected_parent:
        raise PatcherError("VV5 revised Running parent hash is not certified.")
    companion = raw.get("companion")
    if not isinstance(companion, dict) or companion.get("destination") != "VVFP Origins Icons.dll" or companion.get("sha256") != VV5_FULL_MASTERY_CERTIFIED_SHA256["dll"] or companion.get("preimage_sha256") != VV5_FULL_MASTERY_CERTIFIED_SHA256["dll"] or companion.get("restore_sha256") != VV5_FULL_MASTERY_CERTIFIED_SHA256["dll"]:
        raise PatcherError("VV5 revised Running companion identity is not exact.")
    companion_path = ROOT / str(companion.get("source", ""))
    if not companion_path.is_file() or hashlib.sha256(companion_path.read_bytes()).hexdigest().upper() != VV5_FULL_MASTERY_CERTIFIED_SHA256["dll"]:
        raise PatcherError("VV5 revised Running companion source is missing or corrupt.")
    hook = raw.get("patches", [{}])[0]
    if hook.get("offset") != "0xDB766" or hook.get("before") != "E995750100" or hook.get("after") != "E9B5880100":
        raise PatcherError("VV5 revised Running hook guard is not exact.")
    emitted = raw.get("emitted", {})
    if int(emitted.get("helper_length", 0)) <= 0 or int(emitted.get("helper_length", 0)) >= 0x800:
        raise PatcherError("VV5 revised Running helper length is not bounded.")
    import importlib.util
    import sys
    scripts_path = str(ROOT / "scripts")
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)
    builder_path = ROOT / "scripts" / "build_vv5_full_mastery_candidate.py"
    spec = importlib.util.spec_from_file_location("vv5_running_validator_builder", builder_path)
    if spec is None or spec.loader is None:
        raise PatcherError("VV5 revised Running builder is unavailable.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _, slot_map = module.build_slot(module.RUNNING_PAGE_VA, True, True)
    running_page = module.build_page(
        module.RUNNING_PAGE_VA,
        module.build_slot(module.RUNNING_PAGE_VA, True, True)[0],
        module.build_running_dispatcher(module.RUNNING_PAGE_VA),
        slot_map,
        dispatcher_offset=module.RUNNING_DISPATCHER_OFFSET,
    )
    if slot_map.get("running_helper_sha256") != VV5_INDIVIDUAL_RUNNING_HELPER_SHA256 or hashlib.sha256(bytes.fromhex(slot_map["running_helper_bytes"])).hexdigest().upper() != VV5_INDIVIDUAL_RUNNING_HELPER_SHA256:
        raise PatcherError("VV5 revised Running helper identity is not certified.")
    if hashlib.sha256(running_page).hexdigest().upper() != VV5_INDIVIDUAL_RUNNING_PAGE_SHA256 or emitted.get("page_sha256") != VV5_INDIVIDUAL_RUNNING_PAGE_SHA256:
        raise PatcherError("VV5 revised Running page identity is not certified.")
    if emitted.get("rendered_exe_size") != 0xF6000 or emitted.get("rendered_exe_sha256") != {
        "collection_progression": "1E3FD6CE44E906BD8DDD7C937D68AB74671D8F197BC1D767A2B0622F1A0F7907",
    }:
        raise PatcherError("VV5 revised Running rendered output identities are not certified.")


def _certified_vv5_task9_record(active_base: dict[str, Any]) -> dict[str, Any]:
    """Return the one source-generated Task9 owner of the active VV5 actions.

    The historical Full Mastery/Running candidates remain readable evidence,
    but they no longer own the production fallback for these action IDs.
    """
    manifest_bytes = VV5_TASK9_PATHS["manifest"].read_bytes()
    map_bytes = VV5_TASK9_PATHS["map"].read_bytes()
    if source_text_sha256(manifest_bytes) != VV5_TASK9_SOURCE_TEXT_SHA256["manifest"]:
        raise PatcherError("VV5 Task9 manifest source identity mismatch.")
    if source_text_sha256(map_bytes) != VV5_TASK9_SOURCE_TEXT_SHA256["map"]:
        raise PatcherError("VV5 Task9 map source identity mismatch.")
    record = json.loads(manifest_bytes.decode("utf-8"))
    artifact = json.loads(map_bytes.decode("utf-8"))
    if (
        record.get("schema") != "vvfp.vv5_task9_native_actions.v1"
        or record.get("id") != active_base.get("id")
        or record.get("enabled") is not True
        or record.get("catalog_enabled") is not True
        or record.get("catalog_hidden") is not False
        or record.get("supported_modes")
        != [
            "collection_progression",
            "immediate_fixed",
            "experimental_expanded_256",
            "experimental_expanded_256_progression",
        ]
    ):
        raise PatcherError("VV5 Task9 catalog/mode ownership is not fail-closed.")
    active_source = (ROOT / "data" / "vv5_origins_feature.json").read_bytes()
    if source_text_sha256(active_source) != VV5_TASK9_ACTIVE_SOURCE_TEXT_SHA256:
        raise PatcherError("VV5 Task9 pinned active Origins source drifted.")
    if (
        record.get("base_source_text_sha256") != VV5_TASK9_ACTIVE_SOURCE_TEXT_SHA256
        or record.get("task8_overlay_source_text_sha256") != VV5_TASK9_TASK8_SOURCE_TEXT_SHA256
        or source_text_sha256((ROOT / "data/candidates/vv5_post_prototype_overlay.json").read_bytes())
        != VV5_TASK9_TASK8_SOURCE_TEXT_SHA256
    ):
        raise PatcherError("VV5 Task9 Task8/active-base binding mismatch.")
    expected_atomic_core = {
        "commit": VV5_TASK9_ATOMIC_CORE_COMMIT,
        "generator_source_text_sha256": VV5_TASK9_ATOMIC_SOURCE_TEXT_SHA256[
            "atomic_generator"
        ],
        "contract_source_text_sha256": VV5_TASK9_ATOMIC_SOURCE_TEXT_SHA256[
            "atomic_contract"
        ],
    }
    if (
        record.get("atomic_core") != expected_atomic_core
        or artifact.get("atomic_core") != expected_atomic_core
    ):
        raise PatcherError("VV5 Task9 atomic-core commit/source binding mismatch.")
    expected_source_paths = {
        "task9_builder": "scripts/build_vv5_task9_native_actions.py",
        "companion_c": "native/vv5_task9_origins/vv5_task9_origins.c",
        "companion_def": "native/vv5_task9_origins/vv5_task9_origins.def",
        "companion_rc": "native/vv5_task9_origins/vv5_task9_origins.rc",
        "companion_builder": "scripts/build_vv5_task9_origins_dll.ps1",
        "individual_reference": "src/vv5_individual_transactions.py",
        "full_heal_reference": "src/vv5_full_heal.py",
        "active_base": "data/vv5_origins_feature.json",
        "task8_overlay": "data/candidates/vv5_post_prototype_overlay.json",
        "atomic_generator": "src/expanded_atomic_writer.py",
        "atomic_contract": "data/expanded_atomic_writer_integration.json",
    }
    source_bindings = record.get("source_bindings")
    if (
        not isinstance(source_bindings, dict)
        or set(source_bindings) != set(expected_source_paths)
        or artifact.get("source_bindings") != source_bindings
    ):
        raise PatcherError("VV5 Task9 source binding set is not closed.")
    for name, expected_path in expected_source_paths.items():
        binding = source_bindings.get(name)
        if (
            not isinstance(binding, dict)
            or set(binding) != {"path", "source_text_sha256"}
            or binding.get("path") != expected_path
        ):
            raise PatcherError(f"VV5 Task9 {name} source binding is malformed.")
        try:
            bound_source = (ROOT / expected_path).read_bytes()
        except OSError as exc:
            raise PatcherError(f"VV5 Task9 {name} source is unavailable.") from exc
        if source_text_sha256(bound_source) != binding.get("source_text_sha256"):
            raise PatcherError(f"VV5 Task9 {name} source identity mismatch.")
        if (
            name in VV5_TASK9_ATOMIC_SOURCE_TEXT_SHA256
            and binding.get("source_text_sha256")
            != VV5_TASK9_ATOMIC_SOURCE_TEXT_SHA256[name]
        ):
            raise PatcherError(f"VV5 Task9 pinned {name} identity mismatch.")
    active_relocation = active_base.get("expanded_shr_relocations", {}).get("patches")
    task9_relocation = record.get("expanded_shr_relocations", {}).get("patches")
    relocation_digest = hashlib.sha256(
        json.dumps(task9_relocation, sort_keys=True, separators=(",", ":")).encode("ascii")
    ).hexdigest().upper()
    if (
        not isinstance(task9_relocation, list)
        or task9_relocation != active_relocation
        or len(task9_relocation) != 66
        or relocation_digest != VV5_ORIGINS_RELOCATION_LEDGER_SHA256
        or record.get("frozen_c342")
        != {"count": 66, "rows_sha256": VV5_ORIGINS_RELOCATION_LEDGER_SHA256, "unchanged": True}
    ):
        raise PatcherError("VV5 Task9 changed the frozen C342 relocation ledger.")
    active_patches = active_base.get("patches")
    patches = record.get("patches")
    if not isinstance(active_patches, list) or not isinstance(patches, list) or len(patches) != len(active_patches):
        raise PatcherError("VV5 Task9 active-base patch shape mismatch.")
    for before, after in zip(active_patches, patches, strict=True):
        if after.get("offset") != before.get("offset") or after.get("before") != before.get("before"):
            raise PatcherError("VV5 Task9 changed an active-base offset/preimage guard.")
    payload_row = next((item for item in patches if int(item.get("offset", "-1"), 0) == 0xDB000), None)
    if payload_row is None:
        raise PatcherError("VV5 Task9 generated payload row is missing.")
    payload = bytes.fromhex(payload_row.get("after", ""))
    if (
        len(payload) != 0xF60
        or bytes.fromhex("89F96A6A") in payload[0x40:0x180]
        or payload[0x4E:0x59] != bytes.fromhex("97E8EC6F0100E8C7D9C9FF")
        or payload[0x10E:0x119] != bytes.fromhex("97E82C6F0100E807D9C9FF")
        or payload[0x55:0x59] != bytes.fromhex("C7D9C9FF")
        or payload[0x115:0x119] != bytes.fromhex("07D9C9FF")
        or payload[0x40:0xC0].count(bytes.fromhex("6802000000")) != 1
        or payload[0x100:0x180].count(bytes.fromhex("6802000000")) != 1
        or payload[0x40:0xC0].count(bytes.fromhex("6889000000")) != 1
        or payload[0x100:0x180].count(bytes.fromhex("6889000000")) != 1
        or payload[0x2C0:0x2C7] != bytes.fromhex("B800917C00FFE0")
        or payload[0x600:0x607] != bytes.fromhex("B820917C00FFE0")
        or bytes.fromhex("E11C0000") in payload
    ):
        raise PatcherError("VV5 Task9 resource, entry, or withdrawn-gate payload bytes drifted.")
    if any(bytes.fromhex("E11C0000") in bytes.fromhex(item.get("after", "")) for item in patches):
        raise PatcherError("VV5 Task9 patch set retains a withdrawn eligibility read.")
    expected_companion = {
        "source": "data/candidates/VVFP VV5 Task9 Origins Icons.dll",
        "destination": "VVFP Origins Icons.dll",
        "sha256": VV5_TASK9_DLL_SHA256,
        "size": 297472,
    }
    if record.get("companion_files") != [expected_companion]:
        raise PatcherError("VV5 Task9 companion ownership metadata drifted.")
    companion = VV5_TASK9_PATHS["dll"].read_bytes()
    if len(companion) != expected_companion["size"] or hashlib.sha256(companion).hexdigest().upper() != VV5_TASK9_DLL_SHA256:
        raise PatcherError("VV5 Task9 companion identity mismatch.")
    for export in (
        b"BeginOriginsOwner\0",
        b"GetOriginsOwner\0",
        b"EndOriginsOwner\0",
        b"ShowOriginsUpgradeMenuState\0",
        b"ConfirmVV5Task9Action\0",
        b"ShowVV5Task9Result\0",
    ):
        if companion.count(export) != 1:
            raise PatcherError("VV5 Task9 companion export surface drifted.")
    transaction = record.get("pe_append_transaction", {})
    layouts = transaction.get("layouts")
    if transaction.get("section") != ".vv5t9" or not isinstance(layouts, dict) or set(layouts) != set(VV5_TASK9_PAGE_SHA256):
        raise PatcherError("VV5 Task9 append transaction shape drifted.")
    expected_layout = {
        "collection_progression": (0xF2000, 0x7C9000, "0500", "0600", "00903C00", "00103D00", 0x2B8),
        "immediate_fixed": (0xF2000, 0x7C9000, "0500", "0600", "00903C00", "00103D00", 0x2B8),
        "experimental_expanded_256": (0xF4000, 0x904000, "0700", "0800", "00405000", "00C05000", 0x308),
        "experimental_expanded_256_progression": (0xF4000, 0x904000, "0700", "0800", "00405000", "00C05000", 0x308),
    }
    for mode, (append_offset, page_va, count_before, count_after, image_before, image_after, header_offset) in expected_layout.items():
        layout = layouts.get(mode, {})
        page = bytes.fromhex(layout.get("append_bytes", ""))
        headers = layout.get("header_patches", [])
        if (
            int(layout.get("original_file_size", "-1"), 0) != append_offset
            or int(layout.get("append_offset", "-1"), 0) != append_offset
            or layout.get("append_length") != 0x8000
            or int(layout.get("page_virtual_address", "-1"), 0) != page_va
            or len(page) != 0x8000
            or hashlib.sha256(page).hexdigest().upper() != VV5_TASK9_PAGE_SHA256[mode]
            or layout.get("page_sha256") != VV5_TASK9_PAGE_SHA256[mode]
            or len(headers) != 3
            or headers[0].get("before") != count_before
            or headers[0].get("after") != count_after
            or headers[1].get("before") != image_before
            or headers[1].get("after") != image_after
            or int(headers[2].get("offset", "-1"), 0) != header_offset
            or headers[2].get("before") != "00" * 40
        ):
            raise PatcherError(f"VV5 Task9 {mode} append/header guard drifted.")
    nonoverlap = artifact.get("nonoverlap", {})
    if nonoverlap != {
        "task8_dbxxx_range": ["0xDB000", "0xDC000"],
        "task9_stock_append_range": ["0xF2000", "0xFA000"],
        "task9_expanded_append_range": ["0xF4000", "0xFC000"],
        "c342_new_row_count": 0,
        "absolute_entry_stubs_require_c342_relocation": False,
    }:
        raise PatcherError("VV5 Task9 Task8/C342 nonoverlap contract drifted.")
    if artifact.get("resolver_contract") != {
        "record_pointer_resolver": "0x46F950",
        "forbidden_transitive_helpers": ["0x466170", "0x471840"],
        "eligibility_order": [
            "+0x1CD4 != 0",
            "+0x1CE1 == 0",
            "+0x1CEC == 0",
            "+0x1C40 signed > 0",
        ],
    }:
        raise PatcherError("VV5 Task9 direct record-resolver contract drifted.")
    for mode, layout in layouts.items():
        page = bytes.fromhex(layout["append_bytes"])
        page_va = int(layout["page_virtual_address"], 0)
        helper = page[0x40:0x60]
        helper_target = page_va + 0x45 + int.from_bytes(
            helper[1:5], "little", signed=True
        )
        if (
            helper[0] != 0xE8
            or helper_target != 0x44FBB0
            or helper[5:12] != bytes.fromhex("89C15A6A6AFFE2")
        ):
            raise PatcherError(
                f"VV5 Task9 {mode} constructor resource-manager ABI drifted."
            )
        targets: list[int] = []
        for relative in range(len(page) - 4):
            if page[relative] != 0xE8:
                continue
            target = page_va + relative + 5 + int.from_bytes(
                page[relative + 1 : relative + 5], "little", signed=True
            )
            targets.append(target)
        if 0x466170 in targets or 0x471840 in targets or targets.count(0x46F950) != 2:
            raise PatcherError(
                f"VV5 Task9 {mode} retained a forbidden transitive resolver route."
            )
    expected_post_relocation = {
        mode: [VV5_TASK9_EXPANDED_HOOK]
        for mode in (
            "experimental_expanded_256",
            "experimental_expanded_256_progression",
        )
    }
    if record.get("task9_expanded_post_relocation_patches") != expected_post_relocation:
        raise PatcherError("VV5 Task9 Expanded post-relocation hook contract drifted.")
    if artifact.get("expanded_cross_section_hook_audit") != {
        "hook_count": 7,
        "hooks": VV5_TASK9_CROSS_SECTION_HOOKS,
        "frozen_c342_operand_offsets": [
            "0x18910", "0x1EB70", "0x237B1", "0x40A25", "0x4AF13", "0x4BC21"
        ],
        "task9_post_relocation_hook_offset": "0x415F0",
        "task9_post_relocation_operand_offset": "0x415F1",
        "c342_changed": False,
    }:
        raise PatcherError("VV5 Task9 cross-section hook audit drifted.")
    return record


def _certified_vv5_full_mastery_records(
    active_base: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    base = json.loads(VV5_FULL_MASTERY_CANDIDATE_PATHS["base"].read_text(encoding="utf-8"))
    feature = json.loads(
        VV5_FULL_MASTERY_CANDIDATE_PATHS["feature"].read_text(encoding="utf-8")
    )
    if not base.get("enabled", True) or not feature.get("enabled", True):
        return None
    artifact = json.loads(
        VV5_FULL_MASTERY_CANDIDATE_PATHS["map"].read_text(encoding="utf-8")
    )
    if artifact.get("acceptance_commit") != VV5_FULL_MASTERY_ACCEPTANCE_COMMIT:
        raise PatcherError(
            "VV5 Full Mastery acceptance_commit is not the independently certified C99 commit."
        )
    expected_ui = {
        "asset": "native cached Images\\btn_trophies.png",
        "asset_sha256": VV5_FULL_MASTERY_CERTIFIED_SHA256["provenance_asset"],
        "resource_id": "0x6A",
        "native_dimensions": [96, 39],
        "tech": {
            "local_x": 137,
            "local_y": 2,
            "event": 13,
            "factory": "0x401BD0",
            "ownership": "0x40C680",
        },
        "detail": {
            "local_x": 137,
            "local_y": 2,
            "event": 13,
            "factory": "0x401BD0",
            "ownership": "0x40C680",
        },
    }
    expected_map_ui = {
        "asset": "Images\\btn_trophies.png",
        "provenance": "assets/candidates/vv5_full_mastery/provenance/btn_trophies.png",
        "asset_sha256": VV5_FULL_MASTERY_CERTIFIED_SHA256["provenance_asset"],
        "resource_id": "0x6A",
        "native_dimensions": [96, 39],
        "tech": expected_ui["tech"],
        "detail": expected_ui["detail"],
    }

    def exact_tree(actual: Any, expected: Any) -> bool:
        if type(actual) is not type(expected):
            return False
        if isinstance(expected, dict):
            return set(actual) == set(expected) and all(
                exact_tree(actual[key], expected[key]) for key in expected
            )
        if isinstance(expected, list):
            return len(actual) == len(expected) and all(
                exact_tree(value, wanted) for value, wanted in zip(actual, expected, strict=True)
            )
        return actual == expected

    if not exact_tree(artifact.get("ui_geometry_contract"), expected_map_ui):
        raise PatcherError(
            "VV5 Full Mastery candidate map UI contract is not the certified native btn_trophies contract."
        )
    for label, record in (("base", base), ("feature", feature)):
        ui = record.get("ui_geometry_contract")
        if not isinstance(ui, dict) or any(ui.get(key) != value for key, value in expected_ui.items()):
            raise PatcherError(
                f"VV5 Full Mastery {label} UI contract is not the certified native btn_trophies contract."
            )
    provenance_asset = VV5_FULL_MASTERY_CANDIDATE_PATHS["provenance_asset"]
    if not provenance_asset.is_file():
        raise PatcherError(
            "VV5 Full Mastery provenance btn_trophies asset is missing; refusing output."
        )
    provenance_digest = hashlib.sha256(provenance_asset.read_bytes()).hexdigest().upper()
    if provenance_digest != VV5_FULL_MASTERY_CERTIFIED_SHA256["provenance_asset"]:
        raise PatcherError(
            "VV5 Full Mastery provenance btn_trophies asset hash mismatch; refusing output."
        )
    layouts = artifact.get("layouts")
    if not isinstance(layouts, dict) or set(layouts) != set(VV5_FULL_MASTERY_RENDERED_SHA256):
        raise PatcherError(
            "VV5 Full Mastery metadata must expose only the two certified stock-mode layouts."
        )
    rendered = artifact.get("rendered_candidates")
    if not isinstance(rendered, dict):
        raise PatcherError("VV5 Full Mastery rendered-mode gate is missing.")
    if (
        artifact.get("candidate_enabled") is not True
        or artifact.get("catalog_enabled") is not True
        or artifact.get("catalog_hidden") is not False
        or artifact.get("allowed_modes") != ["collection_progression", "immediate_fixed"]
        or artifact.get("expanded_fail_closed") is not True
    ):
        raise PatcherError("VV5 Full Mastery catalog enablement metadata is not C99-certified.")
    for mode in ("collection_progression", "immediate_fixed"):
        if layouts[mode].get("installed_page_sha256") != VV5_FULL_MASTERY_CERTIFIED_SHA256["stock_page"]:
            raise PatcherError(
                f"VV5 Full Mastery {mode} stock page hash is not the certified identity."
            )
    for mode in EXPANDED_PATCH_MODES:
        if rendered.get(mode) != {"rejected": True, "reason": "Expanded-256 fail-closed"}:
            raise PatcherError(
                f"VV5 Full Mastery Expanded-256 mode {mode} is not fail-closed."
            )
    for mode, expected in VV5_FULL_MASTERY_RENDERED_SHA256.items():
        if rendered.get(mode, {}).get("base_plus_mastery_sha256") != expected:
            raise PatcherError(
                f"VV5 Full Mastery {mode} rendered hash is not the certified C99 identity."
            )
    stock = layouts["collection_progression"]
    installed = stock.get("slot_map", {}).get("installed", {})
    actual = {
        "stock_entry": installed.get("entry_sha256"),
        "stock_walker": installed.get("walker_sha256"),
        "stock_confirmation": installed.get("confirmation_sha256"),
        "stock_page": stock.get("installed_page_sha256"),
        "dll": hashlib.sha256(
            VV5_FULL_MASTERY_CANDIDATE_PATHS["dll"].read_bytes()
        ).hexdigest().upper(),
        "provenance_asset": provenance_digest,
    }
    for label, expected in VV5_FULL_MASTERY_CERTIFIED_SHA256.items():
        if actual[label] != expected:
            raise PatcherError(
                f"Certified VV5 Full Mastery {label} artifact hash mismatch: "
                f"expected {expected}, got {actual[label]}."
            )
    expected_companion = {
        "source": "data/candidates/VVFP VV5 Cure Containment Projection.dll",
        "destination": "VVFP Origins Icons.dll",
        "sha256": VV5_FULL_MASTERY_CURE_COMPANION_SHA256,
        "size": 298496,
        "preimage_sha256": VV5_FULL_MASTERY_CERTIFIED_SHA256["dll"],
        "restore_source": "data/candidates/VVFP VV5 Full Mastery Candidate.dll",
        "restore_sha256": VV5_FULL_MASTERY_CERTIFIED_SHA256["dll"],
        "parent": "data/candidates/VVFP VV5 Full Mastery Candidate.dll",
    }
    if base.get("companion_files") != [expected_companion]:
        raise PatcherError("VV5 candidate-owned Cure companion identity is not certified.")
    if artifact.get("companion", {}).get("sha256") != VV5_FULL_MASTERY_CURE_COMPANION_SHA256:
        raise PatcherError("VV5 map does not bind the candidate-owned Cure companion.")
    cure_path = VV5_FULL_MASTERY_CANDIDATE_PATHS["cure_dll"]
    if not cure_path.is_file() or hashlib.sha256(cure_path.read_bytes()).hexdigest().upper() != VV5_FULL_MASTERY_CURE_COMPANION_SHA256:
        raise PatcherError("VV5 candidate-owned Cure companion is missing or corrupt.")
    if installed.get("village_confirmation_sha256") != VV5_FULL_MASTERY_CONFIRMATION_SHA256["village_routine"]:
        raise PatcherError("VV5 Full Mastery village-wide confirmation routine hash is not certified.")
    if installed.get("confirmation_string_sha256") != {
        "individual_confirm": VV5_FULL_MASTERY_CONFIRMATION_SHA256["individual_string"],
        "village_confirm": VV5_FULL_MASTERY_CONFIRMATION_SHA256["village_string"],
    }:
        raise PatcherError("VV5 Full Mastery confirmation string hashes are not certified.")
    if artifact.get("confirmation_contract") != {
        "individual_routine_sha256": VV5_FULL_MASTERY_CONFIRMATION_SHA256["individual_routine"],
        "village_routine_sha256": VV5_FULL_MASTERY_CONFIRMATION_SHA256["village_routine"],
        "individual_string_sha256": VV5_FULL_MASTERY_CONFIRMATION_SHA256["individual_string"],
        "village_string_sha256": VV5_FULL_MASTERY_CONFIRMATION_SHA256["village_string"],
        "individual_price": 100000,
        "village_price": 1000000,
    }:
        raise PatcherError("VV5 Full Mastery confirmation metadata is not C99-certified.")
    base = dict(base)
    base.update(
        {
            "id": active_base["id"],
            "name": "VV5 Origins Full Mastery Extension Base",
            "enabled": True,
            "catalog_hidden": False,
        }
    )
    feature = dict(feature)
    feature.update(
        {
            "id": "vv5_full_mastery_all_stage_a_candidate",
            "name": "Grant Full Mastery to All Villagers",
            "enabled": True,
            "catalog_hidden": False,
            "dependencies": [active_base["id"]],
        }
    )
    return base, feature


def _certified_expanded_time_warp_records() -> list[dict[str, Any]]:
    """Load the three exact Expanded-only Time Warp records fail closed."""

    records: list[dict[str, Any]] = []
    expected_modes = [
        "experimental_expanded_256",
        "experimental_expanded_256_progression",
    ]
    expected_companion = {
        "source": "data/candidates/VVFP VV5 Task9 Origins Icons.dll",
        "destination": "VVFP Origins Icons.dll",
        "sha256": VV5_TASK9_DLL_SHA256,
        "size": 297472,
    }
    shared_bindings = {
        "builder": "scripts/build_expanded_time_warp.py",
        "task9_builder": "scripts/build_vv5_task9_native_actions.py",
        "task9_companion_c": "native/vv5_task9_origins/vv5_task9_origins.c",
        "task9_companion_def": "native/vv5_task9_origins/vv5_task9_origins.def",
        "task9_companion_rc": "native/vv5_task9_origins/vv5_task9_origins.rc",
    }
    vv3_bindings = {
        "builder": "scripts/build_vv3_expanded_time_warp.py",
        "static_candidate": "data/candidates/vv3_full256_serializer_candidate.json",
        "atomic_generator": "src/expanded_atomic_writer.py",
        "task9_companion_c": "native/vv5_task9_origins/vv5_task9_origins.c",
        "task9_companion_def": "native/vv5_task9_origins/vv5_task9_origins.def",
        "task9_companion_rc": "native/vv5_task9_origins/vv5_task9_origins.rc",
    }
    for game_id in ("vv3", "vv4", "vv5"):
        paths = EXPANDED_TIME_WARP_PATHS[game_id]
        try:
            manifest_bytes = paths["manifest"].read_bytes()
            map_bytes = paths["map"].read_bytes()
            record = json.loads(manifest_bytes.decode("utf-8-sig"))
            artifact = json.loads(map_bytes.decode("utf-8-sig"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise PatcherError(
                f"Certified {game_id.upper()} Expanded Time Warp artifacts are unavailable."
            ) from exc
        if (
            source_text_sha256(manifest_bytes)
            != EXPANDED_TIME_WARP_ARTIFACT_SHA256[game_id]["manifest"]
            or source_text_sha256(map_bytes)
            != EXPANDED_TIME_WARP_ARTIFACT_SHA256[game_id]["map"]
        ):
            raise PatcherError(
                f"Certified {game_id.upper()} Expanded Time Warp artifact identity mismatch."
            )
        if (
            record.get("id") != EXPANDED_TIME_WARP_IDS[game_id]
            or record.get("game_id") != game_id
            or record.get("enabled") is not True
            or record.get("catalog_enabled") is not False
            or record.get("catalog_hidden") is not True
            or record.get("experimental_explicit_selection") is not True
            or record.get("supported_modes") != expected_modes
            or record.get("rejected_modes") != [
                "collection_progression",
                "immediate_fixed",
            ]
            or record.get("patches") != []
            or artifact.get("id") != record.get("id")
        ):
            raise PatcherError(
                f"Certified {game_id.upper()} Expanded Time Warp catalog contract drifted."
            )
        expected_bindings = vv3_bindings if game_id == "vv3" else shared_bindings
        bindings = record.get("source_bindings")
        if (
            not isinstance(bindings, dict)
            or set(bindings) != set(expected_bindings)
            or artifact.get("source_bindings") != bindings
        ):
            raise PatcherError(
                f"Certified {game_id.upper()} Expanded Time Warp source binding set drifted."
            )
        for name, expected_path in expected_bindings.items():
            binding = bindings.get(name)
            if (
                not isinstance(binding, dict)
                or binding.get("path") != expected_path
                or set(binding) != {"path", "source_text_sha256"}
            ):
                raise PatcherError(
                    f"Certified {game_id.upper()} Expanded Time Warp {name} binding is malformed."
                )
            try:
                actual = source_text_sha256((ROOT / expected_path).read_bytes())
            except OSError as exc:
                raise PatcherError(
                    f"Certified {game_id.upper()} Expanded Time Warp {name} source is unavailable."
                ) from exc
            if actual != binding.get("source_text_sha256"):
                raise PatcherError(
                    f"Certified {game_id.upper()} Expanded Time Warp {name} source identity mismatch."
                )
            pin_name = "vv3_builder" if game_id == "vv3" and name == "builder" else name
            pinned = EXPANDED_TIME_WARP_SOURCE_TEXT_SHA256.get(pin_name)
            if pinned is not None and actual != pinned:
                raise PatcherError(
                    f"Certified {game_id.upper()} Expanded Time Warp {name} pin drifted."
                )
        overrides = record.get("patch_mode_overrides")
        if not isinstance(overrides, dict) or list(overrides) != expected_modes:
            raise PatcherError(
                f"Certified {game_id.upper()} Expanded Time Warp mode overlays drifted."
            )
        first = overrides[expected_modes[0]]
        if overrides[expected_modes[1]] != first:
            raise PatcherError(
                f"Certified {game_id.upper()} Expanded Time Warp mode bytes diverged."
            )
        if game_id == "vv3":
            try:
                core_bytes = VV3_EXPANDED_TIME_WARP_CORE_PATH.read_bytes()
                core_record = json.loads(core_bytes.decode("utf-8-sig"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise PatcherError(
                    "Certified VV3 Expanded Time Warp core artifact is unavailable."
                ) from exc
            if (
                source_text_sha256(core_bytes)
                != EXPANDED_TIME_WARP_ARTIFACT_SHA256["vv3"]["core"]
                or core_record.get("source_bindings") != bindings
                or artifact.get("core") != core_record
                or record.get("companion_files") != [expected_companion]
                or record.get("dependencies") not in (None, [])
                or record.get("conflicts") != [
                    "vv3_enable_origins_exclusive_features_running_candidate",
                    "vv3_all_villagers_like_running_candidate",
                    "vv3_enable_origins_exclusive_features",
                    "vv3_full_mastery_all_stage_a_candidate",
                ]
                or len(first) != 2
                or first[0].get("offset") != "0x6547D"
                or first[0].get("before") != "8B4C243C5F"
                or first[0].get("after") != "E9FE2B3500"
                or first[1].get("offset") != "0x65640"
                or first[1].get("before") != "6AFF64A100000000"
                or first[1].get("after") != "E9FB293500909090"
                or record.get("pe_append_transaction", {}).get("section_name") != ".vv3tw"
                or artifact.get("layout", {}).get("page_sha256")
                != record.get("pe_append_transaction", {}).get("layouts", {}).get(expected_modes[0], {}).get("page_sha256")
            ):
                raise PatcherError("Certified VV3 Expanded Time Warp emitted bytes drifted.")
        elif game_id == "vv4":
            if (
                record.get("companion_files") != [expected_companion]
                or record.get("dependencies") not in (None, [])
                or record.get("conflicts") != [
                    "vv4_enable_origins_exclusive_features",
                    "vv4_enable_origins_exclusive_features_full_mastery_candidate",
                    "vv4_full_mastery_all_stage_a_candidate",
                ]
                or len(first) != 3
                or first[0].get("offset") != "0x89373"
                or first[0].get("before_fill") != "00"
                or first[0].get("length") != 0xC8D
                or first[1].get("offset") != "0x3E165"
                or first[1].get("before") != "8BC68B4C244C"
                or first[1].get("after") != "E949B2040090"
                or first[2].get("offset") != "0x3E9F0"
                or first[2].get("before") != "578BF9E828F00000"
                or first[2].get("after") != "E97EA90400909090"
                or artifact.get("payload_sha256")
                != hashlib.sha256(bytes.fromhex(first[0].get("after", ""))).hexdigest().upper()
            ):
                raise PatcherError("Certified VV4 Expanded Time Warp emitted bytes drifted.")
        else:
            if (
                record.get("dependencies") != ["vv5_enable_origins_exclusive_features"]
                or record.get("companion_files") not in (None, [])
                or record.get("companion_contract") != expected_companion
                or len(first) != 4
                or [item.get("offset") for item in first]
                != ["0xF4846", "0xF48AB", "0xF5040", "0xFB09A"]
                or first[0].get("before") != "B800070000F70588D351"
                or first[0].get("after") != "B8001E0000E93F000000"
                or first[1].get("before") != "83FB030F82B3000000"
                or first[1].get("after") != "83FB050F828C070000"
                or first[2].get("before_fill") != "00"
                or first[2].get("length") != 0x500
                or artifact.get("layout", {}).get("stock_page_sha256")
                != VV5_TASK9_PAGE_SHA256["collection_progression"]
                or artifact.get("layout", {}).get("expanded_baseline_page_sha256")
                != VV5_TASK9_PAGE_SHA256["experimental_expanded_256"]
            ):
                raise PatcherError("Certified VV5 Expanded Time Warp emitted bytes drifted.")
        records.append(record)
    return records


def _load_fun_patch_records(
    *, include_expanded_time_warp: bool = False
) -> list[FunPatch]:
    items = [
        item
        for item in _manifest().get("fun_patches", [])
        if item.get("enabled", True)
    ]
    for feature_path in ORIGINS_FEATURE_PATHS:
        if feature_path.is_file():
            record = json.loads(feature_path.read_text(encoding="utf-8"))
            if record.get("enabled", True):
                if record.get("id") == "vv3_enable_origins_exclusive_features":
                    # The latest feature-complete VV3 Origins menu owns the
                    # public upgrade actions.  Keep only the base Origins
                    # dependency here; standalone Full Mastery/Running
                    # candidates are historical evidence, not selectable
                    # catalog records.
                    items.append(record)
                elif record.get("id") == "vv4_enable_origins_exclusive_features":
                    # The current VV4 base owns the complete Origins-style
                    # menu.  Standalone Full Mastery and Full Heal candidates
                    # remain historical evidence and are never selectable.
                    items.append(record)
                elif record.get("id") == "vv5_enable_origins_exclusive_features":
                    # Task9 is the sole production owner of the VV5 action
                    # IDs. Historical Full Mastery/Running candidates remain
                    # withdrawn evidence and are never a legacy fallback.
                    items.append(_certified_vv5_task9_record(record))
                else:
                    items.append(record)
    # Full Heal/Cure All is implemented by the current VV3 Origins menu
    # payload, so its old standalone candidate must never be loaded as a
    # duplicate route.
    # The current public catalog owns the complete Origins-style upgrades
    # menu.  The former standalone VV1 Full Mastery candidate is retained as
    # historical evidence only and must not reappear as a selectable patch.
    for feature_path in ORIGINS_VILLAGE_WIDE_FEATURE_PATHS:
        if feature_path.is_file():
            record = json.loads(feature_path.read_text(encoding="utf-8"))
            if record.get("enabled", True):
                items.append(record)
    if STATISTICS_FEATURES_PATH.is_file():
        statistics = json.loads(
            STATISTICS_FEATURES_PATH.read_text(encoding="utf-8")
        )
        items.extend(statistics.get("features", []))
    if include_expanded_time_warp:
        items.extend(_certified_expanded_time_warp_records())
    enriched: list[FunPatch] = []
    for item in items:
        # Keep machine-readable transparency coverage available to the
        # renderer even for older manifests that only supplied a description.
        record = dict(item)
        record.setdefault("behavior_changes", [record.get("description", "")])
        record.setdefault(
            "explicit_non_changes",
            record.get("exclusions", []),
        )
        record.setdefault(
            "evidence_status",
            "static source/manifest verification performed; runtime/player confirmation pending",
        )
        enriched.append(FunPatch(record))
    return enriched


def load_fun_patches(
    *, include_expanded_time_warp: bool = False
) -> list[FunPatch]:
    patches = _load_fun_patch_records(
        include_expanded_time_warp=include_expanded_time_warp
    )
    validate_fun_patch_catalog(patches)
    from transparency import validate_feature_transparency_metadata

    validate_feature_transparency_metadata(patches)
    return patches


def load_public_fun_patches() -> list[FunPatch]:
    """Return every user-selectable current per-game patch.

    The Origins base records remain internal prerequisites.  The public chooser
    exposes the five village-wide menu records alongside the ordinary
    per-game patches, while withdrawn standalone Full Mastery and duplicate
    Origins records remain absent from the catalog.
    """

    catalog = {patch.id: patch for patch in load_fun_patches()}
    missing = [
        patch_id
        for patch_id in PUBLIC_ORIGINS_VILLAGE_WIDE_PATCH_IDS
        if patch_id not in catalog
    ]
    if missing:
        raise PatcherError(
            "Current Origins-style upgrades-menu records are unavailable: "
            + ", ".join(missing)
        )
    return [
        patch
        for patch in load_fun_patches()
        if patch.id not in INTERNAL_ORIGINS_BASE_FEATURE_ID_SET
    ]


def _dependency_ids(patch: FunPatch) -> tuple[str, ...]:
    """Return a normalized, deterministic dependency list for a feature."""
    raw = patch.raw.get("dependencies", ())
    if isinstance(raw, str):
        raw = (raw,)
    if not isinstance(raw, (list, tuple)):
        raise PatcherError(
            f"Invalid dependencies for {patch.id}: expected a list of feature IDs."
        )
    result: list[str] = []
    seen: set[str] = set()
    for dependency in raw:
        if not isinstance(dependency, str) or not dependency.strip():
            raise PatcherError(
                f"Invalid dependency on {patch.id}: feature IDs must be non-empty strings."
            )
        dependency = dependency.strip()
        if dependency not in seen:
            seen.add(dependency)
            result.append(dependency)
    return tuple(result)


def _conflict_ids(patch: FunPatch) -> tuple[str, ...]:
    """Return normalized optional-patch conflict IDs."""
    raw = patch.raw.get("conflicts", ())
    if isinstance(raw, str):
        raw = (raw,)
    if not isinstance(raw, (list, tuple)):
        raise PatcherError(
            f"Invalid conflicts for {patch.id}: expected a list of feature IDs."
        )
    result: list[str] = []
    seen: set[str] = set()
    for conflict in raw:
        if not isinstance(conflict, str) or not conflict.strip():
            raise PatcherError(
                f"Invalid conflict on {patch.id}: feature IDs must be non-empty strings."
            )
        conflict = conflict.strip()
        if conflict == patch.id:
            raise PatcherError(f"Optional patch {patch.id} cannot conflict with itself.")
        if conflict not in seen:
            seen.add(conflict)
            result.append(conflict)
    return tuple(result)


def validate_fun_patch_catalog(
    patches: list[FunPatch] | tuple[FunPatch, ...] | None = None,
) -> None:
    """Validate feature IDs and dependency declarations before any output is written."""
    catalog = _load_fun_patch_records() if patches is None else list(patches)
    by_id: dict[str, FunPatch] = {}
    for patch in catalog:
        if not isinstance(patch.id, str) or not patch.id.strip():
            raise PatcherError("Every optional patch must have a non-empty ID.")
        if patch.id in by_id:
            raise PatcherError(f"Duplicate optional patch ID: {patch.id}")
        by_id[patch.id] = patch
    for patch in catalog:
        transaction = patch.raw.get("pe_append_transaction")
        if transaction is not None:
            if not isinstance(transaction, dict) or not isinstance(
                transaction.get("layouts"), dict
            ):
                raise PatcherError(
                    f"{patch.name} ({patch.id}) has a malformed pe_append_transaction."
                )
            for mode_id, layout in transaction["layouts"].items():
                if not isinstance(mode_id, str) or not isinstance(layout, dict):
                    raise PatcherError(
                        f"{patch.name} ({patch.id}) has a malformed append layout."
                    )
                try:
                    original_size = int(layout["original_file_size"], 0)
                    append_offset = int(layout["append_offset"], 0)
                    append_source = layout.get("append_source")
                    append_bytes = (
                        bytes.fromhex(layout["append_bytes"])
                        if "append_bytes" in layout
                        else b""
                    )
                    header_patches = layout["header_patches"]
                except (KeyError, TypeError, ValueError) as exc:
                    raise PatcherError(
                        f"{patch.name} ({patch.id}) has an invalid {mode_id} append layout."
                    ) from exc
                if (
                    original_size != append_offset
                    or (
                        not append_bytes
                        and append_source
                        not in {
                        "generated:vv4_full_heal_page",
                        "generated:vv3_individual_full_mastery_page",
                        "generated:vv5_individual_running_page",
                        "generated:vv3_expanded_time_warp_page",
                        "generated:vv1_birth_control_page",
                        }
                    )
                    or (append_bytes and len(append_bytes) % 0x1000)
                    or not isinstance(header_patches, list)
                ):
                    raise PatcherError(
                        f"{patch.name} ({patch.id}) has unsafe {mode_id} append geometry."
                    )
                if append_source == "generated:vv3_individual_full_mastery_page" and patch.id != VV3_INDIVIDUAL_FULL_MASTERY_CANDIDATE_ID:
                    raise PatcherError("VV3 individual Full Mastery generated append source is owner-bound.")
                if append_source == "generated:vv5_individual_running_page" and patch.id != VV5_INDIVIDUAL_RUNNING_CANDIDATE_ID:
                    raise PatcherError("VV5 individual Running generated append source is owner-bound.")
                if append_source == "generated:vv3_expanded_time_warp_page" and patch.id != EXPANDED_TIME_WARP_IDS["vv3"]:
                    raise PatcherError("VV3 Expanded Time Warp generated append source is owner-bound.")
                if append_source == "generated:vv1_birth_control_page" and patch.id != "vv1_birth_control":
                    raise PatcherError("VV1 Birth Control generated append source is owner-bound.")
                for item in header_patches:
                    if not isinstance(item, dict):
                        raise PatcherError(
                            f"{patch.name} ({patch.id}) has a non-object append header patch."
                        )
                    before = _patch_bytes(item, "before")
                    after = _patch_bytes(item, "after")
                    if len(before) != len(after) or not item.get("purpose"):
                        raise PatcherError(
                            f"{patch.name} ({patch.id}) has an invalid append header guard."
                        )
        overrides = patch.raw.get("patch_mode_overrides", {})
        if not isinstance(overrides, dict):
            raise PatcherError(
                f"{patch.name} ({patch.id}) patch_mode_overrides must be an object."
            )
        for mode_id, mode_patches in overrides.items():
            if not isinstance(mode_id, str) or not isinstance(mode_patches, list):
                raise PatcherError(
                    f"{patch.name} ({patch.id}) has malformed patch_mode_overrides."
                )
            for mode_patch in mode_patches:
                if not isinstance(mode_patch, dict):
                    raise PatcherError(
                        f"{patch.name} ({patch.id}) has a non-object mode override."
                    )
                try:
                    before = _patch_bytes(mode_patch, "before")
                    after = _patch_bytes(mode_patch, "after")
                except (KeyError, ValueError, TypeError) as exc:
                    raise PatcherError(
                        f"{patch.name} ({patch.id}) has a malformed {mode_id} override."
                    ) from exc
                if len(before) != len(after) or not mode_patch.get("purpose"):
                    raise PatcherError(
                        f"{patch.name} ({patch.id}) has an invalid {mode_id} override length/purpose."
                    )
        for dependency_id in _dependency_ids(patch):
            dependency = by_id.get(dependency_id)
            if dependency is None:
                raise PatcherError(
                    f"{patch.name} ({patch.id}) requires missing prerequisite {dependency_id}."
                )
            if dependency.game_id != patch.game_id:
                raise PatcherError(
                    f"{patch.name} ({patch.id}) cannot depend on {dependency_id}: "
                    "prerequisites must target the same game."
                )
        for conflict_id in _conflict_ids(patch):
            conflict = by_id.get(conflict_id)
            if conflict is None:
                raise PatcherError(
                    f"{patch.name} ({patch.id}) declares missing conflict {conflict_id}."
                )
            if conflict.game_id != patch.game_id:
                raise PatcherError(
                    f"{patch.name} ({patch.id}) cannot conflict with {conflict_id}: "
                    "conflicts must target the same game."
                )
    # A complete DFS catches cycles while retaining a useful feature path.
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(feature_id: str, path: tuple[str, ...] = ()) -> None:
        if feature_id in visiting:
            cycle = " -> ".join((*path, feature_id))
            raise PatcherError(f"Optional patch dependency cycle: {cycle}")
        if feature_id in visited:
            return
        visiting.add(feature_id)
        patch = by_id[feature_id]
        for dependency_id in _dependency_ids(patch):
            visit(dependency_id, (*path, feature_id))
        visiting.remove(feature_id)
        visited.add(feature_id)

    for patch in sorted(catalog, key=lambda item: (item.name.casefold(), item.id)):
        visit(patch.id)


def resolve_fun_patch_ids(
    patch_ids: tuple[str, ...] | list[str],
    *,
    game_id: str | None = None,
    patches: list[FunPatch] | tuple[FunPatch, ...] | None = None,
) -> list[str]:
    """Return explicit selections in dependency-first order.

    The API is intentionally strict: callers must include every prerequisite in
    ``patch_ids``.  The GUI supplies the prerequisites automatically; rejecting
    an incomplete API/CLI selection prevents a partial output from being made.
    """
    catalog = list(load_fun_patches()) if patches is None else list(patches)
    validate_fun_patch_catalog(catalog)
    by_id = {patch.id: patch for patch in catalog}
    requested: list[str] = []
    seen: set[str] = set()
    for patch_id in patch_ids:
        if patch_id in seen:
            continue
        patch = by_id.get(patch_id)
        if patch is None:
            raise PatcherError(f"Unknown optional patch: {patch_id}")
        if game_id is not None and patch.game_id != game_id:
            raise PatcherError(
                f"{patch.name} is only available for {patch.game_id.upper()}."
            )
        seen.add(patch_id)
        requested.append(patch_id)
    requested_set = set(requested)
    # The public Origins-style menu route owns its legacy Origins base as an
    # internal prerequisite.  It is intentionally not a second user-facing
    # checkbox or CLI choice.
    for patch_id in tuple(requested):
        if patch_id not in PUBLIC_ORIGINS_VILLAGE_WIDE_PATCH_ID_SET:
            continue
        for dependency_id in _dependency_ids(by_id[patch_id]):
            if (
                dependency_id in INTERNAL_ORIGINS_BASE_FEATURE_ID_SET
                and dependency_id in by_id
                and dependency_id not in requested_set
            ):
                requested.append(dependency_id)
                requested_set.add(dependency_id)
    for patch_id in requested:
        missing = [
            dependency_id
            for dependency_id in _dependency_ids(by_id[patch_id])
            if dependency_id not in requested_set
        ]
        if missing:
            if (
                patch_id == VV3_INDIVIDUAL_RUNNING_CANDIDATE_ID
                and missing == ["vv3_full_mastery_all_stage_a_candidate"]
            ):
                raise PatcherError(
                    "Grant Running to Selected Villager requires the VV3 Full Mastery "
                    "prerequisite (vv3_full_mastery_all_stage_a_candidate). Select "
                    "the prerequisite before creating output."
                )
            raise PatcherError(
                f"{by_id[patch_id].name} requires prerequisite(s): "
                + ", ".join(missing)
                + ". Select the prerequisite before creating output."
            )
    for patch_id in sorted(requested_set):
        conflicts = sorted(set(_conflict_ids(by_id[patch_id])) & requested_set)
        if conflicts:
            conflict_names = ", ".join(
                f"{by_id[item].name} ({item})" for item in conflicts
            )
            raise PatcherError(
                f"{by_id[patch_id].name} ({patch_id}) conflicts with {conflict_names}."
            )
    ordered: list[str] = []
    emitted: set[str] = set()

    def emit(feature_id: str) -> None:
        if feature_id in emitted:
            return
        patch = by_id[feature_id]
        for dependency_id in _dependency_ids(patch):
            emit(dependency_id)
        emitted.add(feature_id)
        ordered.append(feature_id)

    for feature_id in sorted(
        requested,
        key=lambda item: (by_id[item].name.casefold(), item),
    ):
        emit(feature_id)
    return ordered


def _validate_patch_bounds(
    data: bytes | bytearray,
    offset: int,
    length: int,
    *,
    label: str,
) -> None:
    """Reject malformed file offsets before Python slicing can wrap them."""
    if offset < 0 or length < 0 or offset > len(data) or length > len(data) - offset:
        raise PatcherError(
            f"{label} is outside the input buffer: offset {offset}, "
            f"length {length}, buffer {len(data)}."
        )


def _patch_bytes(patch: dict[str, Any], field: str) -> bytes:
    if field in patch:
        return bytes.fromhex(patch[field])
    if field == "before" and "before_fill" in patch:
        fill = bytes.fromhex(patch["before_fill"])
        length = int(patch["length"])
        if len(fill) != 1:
            raise PatcherError("Internal manifest error: before_fill must be one byte")
        return fill * length
    encoded_field = f"{field}_base64"
    if encoded_field in patch:
        return base64.b64decode(patch[encoded_field], validate=True)
    raise PatcherError(f"Internal manifest error: patch is missing {field}")


def _validate_vv3_individual_running_candidate(
    feature: FunPatch,
    selected_ids: set[str],
    patch_mode: str,
) -> None:
    """Fail closed on every immutable D166 individual-Running contract.

    This validator intentionally runs before any candidate-owned byte is
    applied.  Catalog exposure is separately pinned to the certified stock
    modes, and a direct API/CLI override must not bypass the exact two-range
    and Full-Mastery-chain guards.
    """
    raw = feature.raw
    if patch_mode in EXPANDED_PATCH_MODES:
        raise PatcherError(
            "VV3 individual Grant Running is stock-mode only; Expanded-256 is fail-closed."
        )
    if "vv3_full_mastery_all_stage_a_candidate" not in selected_ids:
        raise PatcherError(
            "VV3 individual Grant Running requires the certified VV3 Full Mastery chain."
        )
    if raw.get("dependencies") != ["vv3_full_mastery_all_stage_a_candidate"]:
        raise PatcherError("VV3 individual Grant Running dependency metadata is not certified.")
    chain = raw.get("base_chain")
    expected_chain = {
        "collection_pre_running_sha256": VV3_INDIVIDUAL_RUNNING_PINS["collection_pre_running"],
        "immediate_pre_running_sha256": VV3_INDIVIDUAL_RUNNING_PINS["immediate_pre_running"],
        "full_mastery_page_sha256": VV3_INDIVIDUAL_RUNNING_PINS["full_mastery_page"],
        "origins_payload_sha256": VV3_INDIVIDUAL_RUNNING_PINS["origins_payload"],
    }
    if not isinstance(chain, dict) or any(chain.get(key) != value for key, value in expected_chain.items()):
        raise PatcherError("VV3 individual Grant Running Full Mastery chain identity is not certified.")
    if "pe_append_transaction" in raw or raw.get("header_patches"):
        raise PatcherError(
            "VV3 individual Grant Running may not append a section or mutate PE headers."
        )
    patches = raw.get("patches")
    if not isinstance(patches, list) or len(patches) != 2:
        raise PatcherError("VV3 individual Grant Running must have exactly two mutation ranges.")
    hook, owned = patches
    if (
        hook.get("offset") != "0xA38C3"
        or _patch_bytes(hook, "before") != bytes.fromhex("83FB027525")
        or _patch_bytes(hook, "after") != bytes.fromhex("E938C02300")
        or hashlib.sha256(_patch_bytes(hook, "after")).hexdigest().upper()
        != VV3_INDIVIDUAL_RUNNING_PINS["hook"]
    ):
        raise PatcherError("VV3 individual Grant Running command-2 mutation is not certified.")
    try:
        owned_before = _patch_bytes(owned, "before")
        owned_after = _patch_bytes(owned, "after")
    except (KeyError, TypeError, ValueError) as exc:
        raise PatcherError("VV3 individual Grant Running owned region is malformed.") from exc
    if (
        owned.get("offset") != "0xCB900"
        or len(owned_before) != VV3_INDIVIDUAL_RUNNING_OWNED_LENGTH
        or len(owned_after) != VV3_INDIVIDUAL_RUNNING_OWNED_LENGTH
        or hashlib.sha256(owned_before).hexdigest().upper()
        != VV3_INDIVIDUAL_RUNNING_PINS["owned_before"]
        or hashlib.sha256(owned_after).hexdigest().upper()
        != VV3_INDIVIDUAL_RUNNING_PINS["owned_after"]
    ):
        raise PatcherError("VV3 individual Grant Running owned .vv3fm range is not certified.")
    if (
        owned.get("helper_length") != VV3_INDIVIDUAL_RUNNING_HELPER_LENGTH
        or owned.get("strings_length") != VV3_INDIVIDUAL_RUNNING_STRINGS_LENGTH
        or owned.get("helper_sha256") != VV3_INDIVIDUAL_RUNNING_PINS["helper"]
        or owned.get("strings_sha256") != VV3_INDIVIDUAL_RUNNING_PINS["strings"]
    ):
        raise PatcherError("VV3 individual Grant Running helper/string pins are not certified.")
    owned_region = raw.get("owned_region")
    transaction = raw.get("transaction_contract")
    if not isinstance(owned_region, dict) or not isinstance(transaction, dict):
        raise PatcherError("VV3 individual Grant Running canonical layout metadata is missing.")
    if owned_region.get("stack_frame") != VV3_INDIVIDUAL_RUNNING_STACK_FRAME:
        raise PatcherError("VV3 individual Grant Running stack-frame locals are not canonical.")
    if owned_region.get("canonical_blob_layout") != VV3_INDIVIDUAL_RUNNING_BLOB_LAYOUT:
        raise PatcherError("VV3 individual Grant Running helper/string layout is not canonical.")
    if transaction.get("stack_frame") != VV3_INDIVIDUAL_RUNNING_STACK_FRAME:
        raise PatcherError("VV3 individual Grant Running transaction stack-frame metadata is not canonical.")
    if transaction.get("canonical_blob_layout") != VV3_INDIVIDUAL_RUNNING_BLOB_LAYOUT:
        raise PatcherError("VV3 individual Grant Running transaction blob layout is not canonical.")
    if not _strict_manifest_value_equal(
        transaction,
        VV3_INDIVIDUAL_RUNNING_TRANSACTION_CONTRACT,
    ):
        raise PatcherError(
            "VV3 individual Grant Running Buy transaction contract is not certified."
        )
    expected_accounting = {
        "feature_owned_range_count": len(VV3_INDIVIDUAL_RUNNING_FEATURE_OWNED_RANGES),
        "feature_owned_ranges": [dict(item) for item in VV3_INDIVIDUAL_RUNNING_FEATURE_OWNED_RANGES],
        "physical_diff_range_count": 3,
        "checksum_range": {
            "raw_offset": "0x160",
            "length": 4,
            "purpose": "deterministic PE checksum recomputation",
            "per_mode": {
                mode: dict(pins)
                for mode, pins in VV3_INDIVIDUAL_RUNNING_CHECKSUM_PINS.items()
            },
        },
        "rule": VV3_INDIVIDUAL_RUNNING_MUTATION_ACCOUNTING_RULE,
    }
    if raw.get("mutation_accounting") != expected_accounting:
        raise PatcherError(
            "VV3 individual Grant Running mutation accounting is not immutable."
        )
    if raw.get("result_messages") != VV3_INDIVIDUAL_RUNNING_RESULT_MESSAGES:
        raise PatcherError(
            "VV3 individual Grant Running result-message metadata is not immutable."
        )
    if b"\xFC\x0F" in owned_after or b"\x94\x0E" in owned_after:
        raise PatcherError("VV3 individual Grant Running may not access Dislikes or +0xE94.")


def _vv3_full_heal_resource_tree(data: bytes) -> tuple[dict[str, Any], dict[tuple[int, int, int], tuple[int, int, bytes]]]:
    """Parse the numeric RT_DIALOG tree without following arbitrary pointers."""
    if data[:2] != b"MZ":
        raise PatcherError("VV3 Full Heal companion is not a PE image.")
    pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe_offset : pe_offset + 4] != b"PE\0\0":
        raise PatcherError("VV3 Full Heal companion PE signature is invalid.")
    section_count = struct.unpack_from("<H", data, pe_offset + 6)[0]
    optional_size = struct.unpack_from("<H", data, pe_offset + 20)[0]
    section_table = pe_offset + 24 + optional_size
    sections: dict[str, tuple[int, int, int, int]] = {}
    for index in range(section_count):
        entry = section_table + index * 40
        name = data[entry : entry + 8].rstrip(b"\0").decode("ascii", errors="strict")
        sections[name] = (
            struct.unpack_from("<I", data, entry + 20)[0],
            struct.unpack_from("<I", data, entry + 16)[0],
            struct.unpack_from("<I", data, entry + 12)[0],
            struct.unpack_from("<I", data, entry + 8)[0],
        )
    if ".rsrc" not in sections:
        raise PatcherError("VV3 Full Heal companion has no .rsrc section.")
    raw_offset, raw_size, rva, virtual_size = sections[".rsrc"]
    if raw_offset != 0x14600 or rva != 0x17000 or virtual_size != 0x33660 or raw_size not in (0x33800, 0x33A00):
        raise PatcherError("VV3 Full Heal companion .rsrc layout is not certified.")
    section = data[raw_offset : raw_offset + raw_size]
    leaves: dict[tuple[int, int, int], tuple[int, int, bytes]] = {}

    def walk(directory: int, path: tuple[int, ...]) -> None:
        named, ids = struct.unpack_from("<HH", section, directory + 12)
        for index in range(named + ids):
            entry = directory + 16 + index * 8
            name, child = struct.unpack_from("<II", section, entry)
            if name & 0x80000000:
                raise PatcherError("VV3 Full Heal resource tree contains a named node.")
            if child & 0x80000000:
                walk(child & 0x7FFFFFFF, path + (name,))
                continue
            data_entry = child & 0x7FFFFFFF
            data_rva, size = struct.unpack_from("<II", section, data_entry)
            data_raw = raw_offset + (data_rva - rva)
            if data_raw < raw_offset or data_raw + size > raw_offset + raw_size:
                raise PatcherError("VV3 Full Heal resource data escapes .rsrc.")
            if len(path) != 2:
                raise PatcherError("VV3 Full Heal resource leaf path is not type/id/language.")
            leaves[(path[0], path[1], name)] = (data_raw, size, data[data_raw : data_raw + size])

    walk(0, ())
    return {"raw_offset": raw_offset, "raw_size": raw_size, "rva": rva, "virtual_size": virtual_size, "section_table": section_table}, leaves


def _vv3_full_heal_dialog_walk(blob: bytes, expected_items: int, expected_end: int) -> list[tuple[int, int]]:
    """Return item title spans for strict DIALOGEX counts/ends."""
    if len(blob) < 26 or struct.unpack_from("<H", blob, 0)[0] != 1 or blob[2:4] != b"\xff\xff":
        raise PatcherError("VV3 Full Heal target is not DIALOGEX.")
    if struct.unpack_from("<H", blob, 16)[0] != expected_items:
        raise PatcherError("VV3 Full Heal DIALOGEX item count is not certified.")

    def skip(cursor: int) -> tuple[int, bytes]:
        first = struct.unpack_from("<H", blob, cursor)[0]
        if first == 0:
            return cursor + 2, blob[cursor : cursor + 2]
        if first == 0xFFFF:
            return cursor + 4, blob[cursor : cursor + 4]
        start = cursor
        cursor += 2
        while struct.unpack_from("<H", blob, cursor)[0] != 0:
            cursor += 2
        return cursor + 2, blob[start : cursor + 2]

    cursor = 26
    for _ in range(3):
        cursor, _ = skip(cursor)
    cursor += 6
    cursor = (cursor + 3) & ~3
    spans: list[tuple[int, int]] = []
    for _ in range(expected_items):
        cursor = (cursor + 3) & ~3
        if cursor + 24 > len(blob):
            raise PatcherError("VV3 Full Heal DIALOGEX item header is truncated.")
        cursor += 24
        cursor, _ = skip(cursor)
        title_start = cursor
        cursor, _ = skip(cursor)
        if cursor + 2 > len(blob):
            raise PatcherError("VV3 Full Heal DIALOGEX creation length is truncated.")
        words = struct.unpack_from("<H", blob, cursor)[0]
        cursor += 2 + words * 2
        cursor = (cursor + 3) & ~3
        spans.append((title_start, cursor))
    if cursor != expected_end:
        raise PatcherError("VV3 Full Heal DIALOGEX exact end is not certified.")
    return spans


def _vv3_full_heal_rsrc_ranges(data: bytes) -> tuple[tuple[int, int], ...]:
    meta, leaves = _vv3_full_heal_resource_tree(data)
    ranges: list[tuple[int, int]] = []
    for resource_id, expected_size in ((201, 0x99C), (203, 0x788)):
        raw, size, blob = leaves[(5, resource_id, 1033)]
        if size != expected_size:
            raise PatcherError("VV3 Full Heal target dialog size is not certified.")
        ranges.append((raw, size))
    return tuple(ranges)


def _validate_vv3_full_heal_companion_transform() -> None:
    base = VV3_FULL_HEAL_BASE_DLL_PATH.read_bytes() if VV3_FULL_HEAL_BASE_DLL_PATH.is_file() else b""
    candidate = VV3_FULL_HEAL_DLL_PATH.read_bytes() if VV3_FULL_HEAL_DLL_PATH.is_file() else b""
    if len(base) != VV3_FULL_HEAL_DLL_SIZE or hashlib.sha256(base).hexdigest().upper() != VV3_FULL_HEAL_BASE_DLL_SHA256:
        raise PatcherError("VV3 Full Heal dependency DLL preimage is not certified.")
    if len(candidate) != VV3_FULL_HEAL_DLL_SIZE or hashlib.sha256(candidate).hexdigest().upper() != VV3_FULL_HEAL_DLL_SHA256:
        raise PatcherError("VV3 Full Heal replacement DLL is not certified.")
    base_meta, base_leaves = _vv3_full_heal_resource_tree(base)
    cand_meta, cand_leaves = _vv3_full_heal_resource_tree(candidate)
    if cand_meta["raw_offset"] != base_meta["raw_offset"] or cand_meta["rva"] != base_meta["rva"] or cand_meta["virtual_size"] != base_meta["virtual_size"] or cand_meta["raw_size"] != 0x33800:
        raise PatcherError("VV3 Full Heal replacement DLL .rsrc repack layout is not certified.")
    if len(candidate) != 298496 or len(base) != 298496:
        raise PatcherError("VV3 Full Heal replacement DLL size transition is not certified.")
    # Every non-resource byte and every section-header byte are immutable;
    # this rejects the malformed Playtest 9 in-place DLL.
    for offset, before in enumerate(base):
        if offset >= len(candidate):
            raise PatcherError("VV3 Full Heal replacement DLL was truncated.")
        if before == candidate[offset]:
            continue
        if 0x14600 <= offset < 0x14600 + 0x33800:
            continue
        raise PatcherError("VV3 Full Heal replacement DLL changed non-resource bytes.")
    for path, (raw, size, blob) in base_leaves.items():
        if path not in cand_leaves:
            raise PatcherError("VV3 Full Heal replacement DLL resource leaf set changed.")
        cand_raw, cand_size, cand_blob = cand_leaves[path]
        if path == (5, 202, 1033):
            _vv3_full_heal_dialog_walk(blob, 21, 0x450)
            _vv3_full_heal_dialog_walk(cand_blob, 21, 0x450)
            if cand_raw != 0x4705C or raw != 0x47058:
                raise PatcherError("VV3 Full Heal resource 202 relocation is not certified.")
            if cand_blob != blob:
                raise PatcherError("VV3 Full Heal resource 202 changed.")
        elif path in ((5, 201, 1033), (5, 203, 1033)):
            expected_items = 46 if path[1] == 201 else 36
            expected_end = 0x99C if path[1] == 201 else 0x788
            _vv3_full_heal_dialog_walk(blob, expected_items, len(blob))
            _vv3_full_heal_dialog_walk(cand_blob, expected_items, expected_end)
            expected_raw = 0x466C0 if path[1] == 201 else 0x474D8
            if cand_raw != expected_raw:
                raise PatcherError("VV3 Full Heal target dialog relocation is not certified.")
            old_label = "Cure all Villagers".encode("utf-16le") + b"\0\0"
            new_label = "Full Heal / Cure All".encode("utf-16le") + b"\0\0"
            if blob.count(old_label) != 1 or cand_blob.count(new_label) != 1 or cand_size != size + 4:
                raise PatcherError("VV3 Full Heal target dialog title delta is not certified.")
        elif cand_blob != blob or cand_size != size:
            raise PatcherError("VV3 Full Heal replacement DLL changed an unrelated resource leaf.")


def _validate_vv3_full_heal_candidate(
    feature: FunPatch,
    selected_ids: set[str],
    patch_mode: str,
) -> None:
    """Validate the disabled VV3 Full Heal candidate before any byte mutation."""

    try:
        manifest_bytes = VV3_FULL_HEAL_CANDIDATE_PATHS["manifest"].read_bytes()
        map_bytes = VV3_FULL_HEAL_CANDIDATE_PATHS["map"].read_bytes()
    except OSError as exc:
        raise PatcherError("VV3 Full Heal candidate metadata is missing.") from exc
    if source_text_sha256(manifest_bytes) != VV3_FULL_HEAL_MANIFEST_SHA256:
        raise PatcherError("VV3 Full Heal candidate manifest bytes are not certified.")
    if source_text_sha256(map_bytes) != VV3_FULL_HEAL_MAP_SHA256:
        raise PatcherError("VV3 Full Heal candidate map bytes are not certified.")
    try:
        canonical_manifest = json.loads(manifest_bytes.decode("utf-8"))
        canonical_map = json.loads(map_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PatcherError("VV3 Full Heal candidate metadata is malformed.") from exc
    if not _strict_manifest_value_equal(canonical_manifest, feature.raw):
        raise PatcherError("VV3 Full Heal candidate object differs from its pinned manifest.")
    if canonical_map.get("candidate_id") != VV3_FULL_HEAL_CANDIDATE_ID:
        raise PatcherError("VV3 Full Heal candidate map identity is not certified.")
    if canonical_map.get("candidate_enabled") is not True or canonical_map.get("catalog_hidden") is not False or canonical_map.get("catalog_enabled") is not True:
        raise PatcherError("VV3 Full Heal candidate map enablement is not certified.")
    if canonical_map.get("allowed_modes") != ["collection_progression", "immediate_fixed"] or canonical_map.get("expanded_fail_closed") is not True:
        raise PatcherError("VV3 Full Heal candidate map mode gate is not certified.")
    if canonical_map.get("audit_commit") is not None or canonical_map.get("acceptance_commit") is not None:
        raise PatcherError("VV3 Full Heal audit/acceptance commit fields must remain null until separately recorded.")
    if canonical_map.get("companion_files") != feature.raw.get("companion_files"):
        raise PatcherError("VV3 Full Heal candidate map companion identity is not certified.")
    for key in (
        "eligibility",
        "transaction",
        "result_helper",
        "health_setter",
        "sickness",
        "record_zero_resolver",
        "messagebox_resolution",
        "messages",
        "resource_transform",
        "partial_failure_limit",
        "rollback_disclosure",
        "mutation_accounting",
        "forbidden_routes",
        "provenance",
        "static_acceptance",
        "implementation_status",
    ):
        if canonical_map.get(key) != feature.raw.get(key):
            raise PatcherError(f"VV3 Full Heal candidate map {key} metadata is not certified.")
    if canonical_map.get("hook") != {
        "raw_offset": "0xA35EF",
        "before": VV3_FULL_HEAL_HOOK_BEFORE.hex().upper(),
        "after": VV3_FULL_HEAL_HOOK_AFTER.hex().upper(),
        "sha256": hashlib.sha256(VV3_FULL_HEAL_HOOK_AFTER).hexdigest().upper(),
    }:
        raise PatcherError("VV3 Full Heal candidate map hook identity is not certified.")
    if canonical_map.get("legacy_preserved_range") != {
        "raw_start": "0x7B664",
        "raw_end": "0x7B721",
        "sha256": VV3_FULL_HEAL_LEGACY_PRESERVED_RANGE_SHA256,
    }:
        raise PatcherError("VV3 Full Heal composed-parent legacy range identity is not certified.")
    if canonical_map.get("stock_zero_preimage_legacy_range") != {
        "raw_start": "0x7B664",
        "raw_end": "0x7B721",
        "sha256": VV3_FULL_HEAL_STOCK_ZERO_PREIMAGE_LEGACY_RANGE_SHA256,
    }:
        raise PatcherError("VV3 Full Heal stock-zero legacy preimage identity is not certified.")
    if patch_mode in EXPANDED_PATCH_MODES:
        raise PatcherError(
            "VV3 Full Heal/Cure All is stock-mode only; Expanded-256 is fail-closed."
        )
    raw = feature.raw
    if raw.get("id") != VV3_FULL_HEAL_CANDIDATE_ID:
        raise PatcherError("VV3 Full Heal candidate identity is not certified.")
    if raw.get("provenance") != VV3_FULL_HEAL_PROVENANCE:
        raise PatcherError("VV3 Full Heal provenance is not stable or is self-referential.")
    if raw.get("static_acceptance") != VV3_FULL_HEAL_STATIC_ACCEPTANCE:
        raise PatcherError("VV3 Full Heal static acceptance evidence is not certified.")
    if raw.get("implementation_status") != VV3_FULL_HEAL_IMPLEMENTATION_STATUS:
        raise PatcherError("VV3 Full Heal implementation status is not truthful or certified.")
    if raw.get("enabled") is not True or raw.get("catalog_hidden") is not False or raw.get("catalog_enabled") is not True:
        raise PatcherError("VV3 Full Heal candidate enablement is not certified.")
    if raw.get("audit_commit") is not None or raw.get("acceptance_commit") is not None:
        raise PatcherError("VV3 Full Heal audit/acceptance commit fields must remain null until separately recorded.")
    if raw.get("dependencies") != [VV3_INDIVIDUAL_RUNNING_CANDIDATE_ID] or not {
        "vv3_enable_origins_exclusive_features",
        "vv3_full_mastery_all_stage_a_candidate",
        VV3_INDIVIDUAL_RUNNING_CANDIDATE_ID,
    }.issubset(selected_ids):
        raise PatcherError("VV3 Full Heal requires the certified Origins + Full Mastery + individual Running chain.")
    chain = raw.get("base_chain")
    if not isinstance(chain, dict) or chain.get("stock_sha256") != VV3_FULL_HEAL_STOCK_SHA256:
        raise PatcherError("VV3 Full Heal stock composition identity is not certified.")
    if (
        chain.get("collection_pre_cure_sha256")
        != "3644A56FE17F843DB67662E4309C3C2B41AE7ADD5FDD60EF2B6789DE2BA15FDC"
        or chain.get("immediate_pre_cure_sha256")
        != "059230146E8CC36E06E5473AE187D081E337DB90638B227FBA799B9C82B58C1C"
    ):
        raise PatcherError("VV3 Full Heal pre-Cure composition fingerprints are not certified.")
    if (
        chain.get("full_mastery_page_sha256") != VV3_FULL_MASTERY_CERTIFIED_SHA256["page"]
        or chain.get("running_region_sha256") != VV3_INDIVIDUAL_RUNNING_PINS["owned_after"]
        or chain.get("running_composed_parent_helper_sha256")
        != VV3_FULL_HEAL_COMPOSED_PARENT_HELPER_SHA256
        or chain.get("stock_cure_cave_preimage_sha256")
        != VV3_FULL_HEAL_STOCK_CURE_CAVE_PREIMAGE_SHA256
        or chain.get("stock_zero_preimage_legacy_range_sha256")
        != VV3_FULL_HEAL_STOCK_ZERO_PREIMAGE_LEGACY_RANGE_SHA256
    ):
        raise PatcherError("VV3 Full Heal dependency-region identities are not certified.")
    companion = raw.get("companion_files")
    expected_companion = {
        "source": "data/candidates/VVFP VV3 Full Heal Candidate.dll",
        "destination": "VVFP VV3 Full Mastery Candidate.dll",
        "size": VV3_FULL_HEAL_DLL_SIZE,
        "sha256": VV3_FULL_HEAL_DLL_SHA256,
        "preimage_sha256": VV3_FULL_HEAL_BASE_DLL_SHA256,
        "restore_source": "data/candidates/VVFP VV3 Full Mastery Candidate.dll",
        "restore_sha256": VV3_FULL_HEAL_BASE_DLL_SHA256,
        "resource_only": True,
        "resource_transform": {
            "type": "RT_DIALOG DIALOGEX structural repack",
            "resource_type": 5,
            "targets": {
                "201": {"items": 46, "old_size": "0x998", "new_size": "0x99C", "raw": "0x466C0", "title_only": True},
                "202": {"items": 21, "size": "0x47C", "old_raw": "0x47058", "new_raw": "0x4705C", "unchanged": True, "exact_dialog_end": "0x450"},
                "203": {"items": 36, "old_size": "0x784", "new_size": "0x788", "raw": "0x474D8", "title_only": True},
            },
            "alignment_gap_consumed": "0x4",
            "section_header_unchanged": True,
            "non_resource_bytes_unchanged": True,
        },
    }
    if companion != [expected_companion]:
        raise PatcherError("VV3 Full Heal companion metadata is not certified.")
    if (
        not VV3_FULL_HEAL_DLL_PATH.is_file()
        or VV3_FULL_HEAL_DLL_PATH.stat().st_size != VV3_FULL_HEAL_DLL_SIZE
        or hashlib.sha256(VV3_FULL_HEAL_DLL_PATH.read_bytes()).hexdigest().upper()
        != VV3_FULL_HEAL_DLL_SHA256
    ):
        raise PatcherError("VV3 Full Heal companion DLL is missing or hash-mismatched.")
    if (
        not VV3_FULL_HEAL_BASE_DLL_PATH.is_file()
        or VV3_FULL_HEAL_BASE_DLL_PATH.stat().st_size != VV3_FULL_HEAL_DLL_SIZE
        or hashlib.sha256(VV3_FULL_HEAL_BASE_DLL_PATH.read_bytes()).hexdigest().upper()
        != VV3_FULL_HEAL_BASE_DLL_SHA256
    ):
        raise PatcherError("VV3 Full Heal certified dependency DLL preimage is missing or hash-mismatched.")
    _validate_vv3_full_heal_companion_transform()
    if raw.get("supported_modes") != ["collection_progression", "immediate_fixed"]:
        raise PatcherError("VV3 Full Heal supported modes are not certified.")
    if set(raw.get("unsupported_patch_modes", ())) != set(EXPANDED_PATCH_MODES):
        raise PatcherError("VV3 Full Heal Expanded-256 rejection metadata is not certified.")
    if raw.get("transaction") != VV3_FULL_HEAL_TRANSACTION:
        raise PatcherError("VV3 Full Heal transaction metadata is not immutable.")
    if raw.get("eligibility") != VV3_FULL_HEAL_ELIGIBILITY:
        raise PatcherError("VV3 Full Heal eligibility metadata is not immutable.")
    if raw.get("sickness") != VV3_FULL_HEAL_SICKNESS:
        raise PatcherError("VV3 Full Heal sickness/stat metadata is not immutable.")
    if raw.get("record_zero_resolver") != VV3_FULL_HEAL_RECORD_ZERO_RESOLVER:
        raise PatcherError("VV3 Full Heal record-zero resolver metadata is not immutable.")
    if raw.get("messagebox_resolution") != VV3_FULL_HEAL_MESSAGEBOX_RESOLUTION:
        raise PatcherError("VV3 Full Heal MessageBoxA resolution metadata is not immutable.")
    if raw.get("mutation_accounting") != VV3_FULL_HEAL_MUTATION_ACCOUNTING:
        raise PatcherError("VV3 Full Heal mutation accounting metadata is not immutable.")
    if raw.get("messages") != VV3_FULL_HEAL_MESSAGES:
        raise PatcherError("VV3 Full Heal result-message metadata is not immutable.")
    if raw.get("partial_failure_limit") != VV3_FULL_HEAL_PARTIAL_FAILURE_DISCLOSURE or raw.get("rollback_disclosure") != VV3_FULL_HEAL_PARTIAL_FAILURE_DISCLOSURE:
        raise PatcherError("VV3 Full Heal rollback disclosure metadata is not immutable.")
    if raw.get("health_setter") != VV3_FULL_HEAL_HEALTH_SETTER:
        raise PatcherError("VV3 Full Heal health-setter ABI metadata is not immutable.")
    if raw.get("result_helper") != VV3_FULL_HEAL_RESULT_HELPER:
        raise PatcherError("VV3 Full Heal result-helper ABI metadata is not immutable.")
    if raw.get("forbidden_routes") != VV3_FULL_HEAL_FORBIDDEN_ROUTES:
        raise PatcherError("VV3 Full Heal forbidden-route metadata is not immutable.")
    patches = raw.get("patches")
    if not isinstance(patches, list) or len(patches) != 1:
        raise PatcherError("VV3 Full Heal must have exactly one command hook plus the guarded .vv3hc append.")
    hook = patches[0]
    if (
        hook.get("offset") != "0xA35EF"
        or _patch_bytes(hook, "before") != VV3_FULL_HEAL_HOOK_BEFORE
        or _patch_bytes(hook, "after") != VV3_FULL_HEAL_HOOK_AFTER
        or hook.get("continuation_non5") != "0x4A35F6"
    ):
        raise PatcherError("VV3 Full Heal command-5 dominance hook is not certified.")
    append_tx = raw.get("pe_append_transaction")
    if not isinstance(append_tx, dict) or append_tx.get("section_name") != ".vv3hc":
        raise PatcherError("VV3 Full Heal .vv3hc append transaction is not certified.")
    layout = append_tx.get("layouts", {}).get(patch_mode)
    if not isinstance(layout, dict) or int(layout.get("append_offset", "-1"), 0) != 0xCC000:
        raise PatcherError("VV3 Full Heal .vv3hc append layout is not certified.")
    after = bytes.fromhex(layout.get("append_bytes", ""))
    if len(after) != VV3_FULL_HEAL_CAVE_LENGTH:
        raise PatcherError("VV3 Full Heal .vv3hc page length is not certified.")
    section = canonical_map.get("section")
    if not isinstance(section, dict) or section.get("name") != ".vv3hc" or section.get("raw_offset") != "0xCC000" or section.get("virtual_address") != "0x6E0000" or section.get("rva") != "0x2E0000":
        raise PatcherError("VV3 Full Heal .vv3hc section identity is not certified.")
    if canonical_map.get("legacy_cave", {}).get("raw_offset") != "0x7B721" or canonical_map.get("legacy_cave", {}).get("length") != 0x700 or canonical_map.get("legacy_cave", {}).get("must_remain_zero") is not True:
        raise PatcherError("VV3 Full Heal legacy Cure cave guard is not certified.")
    layout = section.get("layout")
    if not isinstance(layout, dict) or layout.get("strings_offset") != f"0x{VV3_FULL_HEAL_STRINGS_OFFSET:X}":
        raise PatcherError("VV3 Full Heal helper/string layout is not certified.")
    if layout.get("region_sha256") != VV3_FULL_HEAL_CAVE_SHA256:
        raise PatcherError("VV3 Full Heal owned cave does not match the pinned region identity.")
    if layout.get("region_sha256") != hashlib.sha256(after).hexdigest().upper():
        raise PatcherError("VV3 Full Heal owned cave hash does not match its bytes.")
    if layout.get("helper_length") != VV3_FULL_HEAL_HELPER_LENGTH:
        raise PatcherError("VV3 Full Heal helper length is not certified.")
    if layout.get("strings_length") != VV3_FULL_HEAL_STRINGS_LENGTH:
        raise PatcherError("VV3 Full Heal string length is not certified.")
    if layout.get("tail_zero_length") != VV3_FULL_HEAL_TAIL_ZERO_LENGTH:
        raise PatcherError("VV3 Full Heal cave tail length is not certified.")
    if layout.get("used_length") != VV3_FULL_HEAL_STRINGS_OFFSET + VV3_FULL_HEAL_STRINGS_LENGTH:
        raise PatcherError("VV3 Full Heal helper/string used range is not certified.")
    if layout.get("helper_sha256") != VV3_FULL_HEAL_HELPER_SHA256:
        raise PatcherError("VV3 Full Heal helper identity is not certified.")
    if hashlib.sha256(after[:VV3_FULL_HEAL_HELPER_LENGTH]).hexdigest().upper() != VV3_FULL_HEAL_HELPER_SHA256:
        raise PatcherError("VV3 Full Heal emitted helper slice hash is not certified.")
    if layout.get("instruction_count") != VV3_FULL_HEAL_HELPER_INSTRUCTION_COUNT:
        raise PatcherError("VV3 Full Heal helper instruction count is not certified.")
    if layout.get("epilogue_offset") != VV3_FULL_HEAL_HELPER_EPILOGUE_OFFSET:
        raise PatcherError("VV3 Full Heal helper epilogue boundary is not certified.")
    if layout.get("internal_target_offsets") != VV3_FULL_HEAL_INTERNAL_TARGET_OFFSETS:
        raise PatcherError("VV3 Full Heal internal branch boundaries are not certified.")
    if b"\x68\xA0\x7B\x00\x00" in after or b"\xA0\x7B\x00\x00" in after:
        raise PatcherError("VV3 Full Heal cave may not call the legacy Cure entry.")
    if b"\xD8\x40" in after or b"\x94\x0E" in after:
        raise PatcherError("VV3 Full Heal cave contains a forbidden legacy/UI or +0xE94 route.")
    if b"\x6A\xFF\x6A\x64" not in after:
        raise PatcherError("VV3 Full Heal native setter markers are missing.")
    if after.count(b"\x80\xBF\x10\x0F\x00\x00\x00") != 3:
        raise PatcherError("VV3 Full Heal active predicate must use byte-width checks at all three scans.")
    if b"\x83\xBF\x10\x0F\x00\x00\x00" in after:
        raise PatcherError("VV3 Full Heal active predicate contains a dword-width check.")
    if b"\x8B\x04\xBD\x54\x3F\x4A\x00" in after:
        raise PatcherError("VV3 Full Heal non-command-5 shim may not index through EDI.")
    if b"\x8B\x04\x9D\x54\x3F\x4A\x00" not in after:
        raise PatcherError("VV3 Full Heal non-command-5 shim must preserve the EBX-indexed lookup.")
    if VV3_FULL_HEAL_NON5_SHIM not in after:
        raise PatcherError("VV3 Full Heal non-command-5 shim continuation is not exact.")
    if after.count(b"\xFF\x15\x24\xC1\x47\x00") != 1 or after.count(b"\xFF\x15\x28\xC1\x47\x00") != 1:
        raise PatcherError("VV3 Full Heal MessageBoxA API resolution calls are not exact.")
    if b"\xA1\xA0\xC3\x47\x00\x85\xC0\x0F\x84\x6D\x03\x00\x00\x89\x45\xEC\x90\x90\x90\x90\x90\x90\x90\x90\x90" not in after:
        raise PatcherError("VV3 Full Heal wsprintfA direct-IAT resolution is not exact.")
    if b"\x68\x17\x08\x6E\x00\xFF\x75\xF0\xFF\x15\x28\xC1\x47\x00" in after:
        raise PatcherError("VV3 Full Heal historical second GetProcAddress sequence remains reachable.")
    if after.count(b"\x6A\x00\xB9\x10\xE1\x59\x00") != 3:
        raise PatcherError("VV3 Full Heal must resolve record zero at each required fresh-pool boundary.")
    if b"\xC7\x45\xE8\x24\xE1\x59\x00" in after:
        raise PatcherError("VV3 Full Heal may not substitute the fixed pool constant for record-zero resolution.")
    if after.count(b"\xFF\x80\xFC\x04\x00\x00") != 1:
        raise PatcherError("VV3 Full Heal must increment People Cured once per verified sick record.")
    if after.count(b"\xC7\x45\xD0\x96\x00\x00\x00") != 1 or after.count(b"\xFF\x4D\xD0") != 1:
        raise PatcherError("VV3 Full Heal mutation loop must use the disjoint 150-record local counter.")
    if b"\xE9\x00\x00\x00\x00" in after:
        raise PatcherError("VV3 Full Heal cave contains an unresolved branch relocation.")


def _append_layout(feature: FunPatch, patch_mode: str) -> dict[str, Any] | None:
    transaction = feature.raw.get("pe_append_transaction")
    if transaction is None:
        return None
    if not isinstance(transaction, dict):
        raise PatcherError(
            f"{feature.name} ({feature.id}) pe_append_transaction must be an object."
        )
    layouts = transaction.get("layouts")
    if not isinstance(layouts, dict):
        raise PatcherError(
            f"{feature.name} ({feature.id}) append transaction is missing layouts."
        )
    layout_mode = patch_mode
    if patch_mode == "stock" and feature.id in INTERNAL_ORIGINS_BASE_FEATURE_ID_SET:
        # The current Origins menu prerequisites do not alter population
        # behavior.  Stock mode therefore uses the same append geometry as
        # Collection Progression while leaving the population variant stock.
        layout_mode = "collection_progression"
    layout = layouts.get(layout_mode)
    if not isinstance(layout, dict):
        raise PatcherError(
            f"{feature.name} ({feature.id}) has no append layout for {patch_mode}."
        )
    return layout


def _apply_pe_append_transactions(
    data: bytearray,
    fun_patches: list[FunPatch],
    patch_mode: str,
) -> list[dict[str, str]]:
    """Apply exact guarded PE appends before ordinary feature byte patches."""
    work = bytearray(data)
    applied: list[dict[str, str]] = []
    for feature in fun_patches:
        layout = _append_layout(feature, patch_mode)
        if layout is None:
            continue
        try:
            original_size = int(layout["original_file_size"], 0)
            append_offset = int(layout["append_offset"], 0)
            append_source = layout.get("append_source")
            append_bytes = _resolve_append_bytes(feature, layout)
            header_patches = layout["header_patches"]
        except (KeyError, TypeError, ValueError) as exc:
            raise PatcherError(
                f"{feature.name} ({feature.id}) has a malformed append layout."
            ) from exc
        if original_size != append_offset or len(work) != original_size:
            raise PatcherError(
                f"{feature.name} append guard failed: expected file size "
                f"0x{original_size:X}, found 0x{len(data):X}."
            )
        if not append_bytes or len(append_bytes) % 0x1000:
            raise PatcherError(
                f"{feature.name} append payload must occupy complete 0x1000-byte pages."
            )
        validated_headers: list[tuple[dict[str, Any], int, bytes, bytes]] = []
        for item in header_patches:
            offset = int(item["offset"], 0)
            before = _patch_bytes(item, "before")
            after = _patch_bytes(item, "after")
            if len(before) != len(after):
                raise PatcherError(
                    f"{feature.name} append header changes length at {item['offset']}."
                )
            _validate_patch_bounds(
                work,
                offset,
                len(before),
                label=f"{feature.name} append header at {item['offset']}",
            )
            actual = bytes(work[offset : offset + len(before)])
            if actual != before:
                raise PatcherError(
                    f"{feature.name} append header guard failed at {item['offset']}: "
                    f"expected {before.hex().upper()}, found {actual.hex().upper()}"
                )
            validated_headers.append((item, offset, before, after))
        for item, offset, before, after in validated_headers:
            work[offset : offset + len(after)] = after
            applied.append(
                {
                    "offset": item["offset"],
                    "before": before.hex().upper(),
                    "after": after.hex().upper(),
                    "purpose": item["purpose"],
                    "owner": f"feature:{feature.id}",
                    "virtual_address": None,
                }
            )
        work.extend(append_bytes)
        applied.append(
            {
                "offset": f"0x{append_offset:X}",
                "before": "",
                "after": append_bytes.hex().upper(),
                "purpose": layout["purpose"],
                "owner": f"feature:{feature.id}",
                "virtual_address": layout.get("virtual_address"),
            }
        )
    data[:] = work
    return applied


def _resolve_append_bytes(feature: FunPatch, layout: dict[str, Any]) -> bytes:
    """Resolve an append payload identically for install and removal.

    Generated pages are built in memory from the authoritative builder and are
    hash/size checked before a caller is allowed to mutate executable bytes.
    """
    if "append_bytes" in layout:
        return bytes.fromhex(layout["append_bytes"])
    if layout.get("append_source") == "generated:vv1_birth_control_page":
        if feature.id != "vv1_birth_control":
            raise PatcherError("VV1 Birth Control append source owner mismatch.")
        import importlib.util
        builder_path = ROOT / "scripts" / "build_vv1_birth_control_page.py"
        spec = importlib.util.spec_from_file_location(
            "vv1_birth_control_builder_runtime", builder_path
        )
        if spec is None or spec.loader is None:
            raise PatcherError("VV1 Birth Control page builder is unavailable.")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        append_bytes, details = module.build_page()
        expected = str(layout.get("page_sha256", "")).upper()
        actual = hashlib.sha256(append_bytes).hexdigest().upper()
        if (
            len(append_bytes) != 0x1000
            or not expected
            or actual != expected
            or details.get("page_sha256") != expected
        ):
            raise PatcherError(
                "Generated VV1 Birth Control page identity mismatch: "
                f"expected {expected}, got {actual}."
            )
        return bytes(append_bytes)
    if layout.get("append_source") == "generated:vv3_expanded_time_warp_page":
        if feature.id != EXPANDED_TIME_WARP_IDS["vv3"]:
            raise PatcherError("VV3 Expanded Time Warp append source owner mismatch.")
        import importlib.util
        builder_path = ROOT / "scripts" / "build_vv3_expanded_time_warp.py"
        spec = importlib.util.spec_from_file_location(
            "vv3_expanded_time_warp_builder_runtime", builder_path
        )
        if spec is None or spec.loader is None:
            raise PatcherError("VV3 Expanded Time Warp page builder is unavailable.")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        append_bytes, details = module.build_page()
        expected = str(layout.get("page_sha256", "")).upper()
        actual = hashlib.sha256(append_bytes).hexdigest().upper()
        if (
            len(append_bytes) != 0x1000
            or not expected
            or actual != expected
            or details.get("page_sha256") != expected
        ):
            raise PatcherError(
                "Generated VV3 Expanded Time Warp page identity mismatch: "
                f"expected {expected}, got {actual}."
            )
        return bytes(append_bytes)
    if layout.get("append_source") == "generated:vv3_individual_full_mastery_page":
        if feature.id != VV3_INDIVIDUAL_FULL_MASTERY_CANDIDATE_ID:
            raise PatcherError("VV3 individual Full Mastery append source owner mismatch.")
        import importlib.util
        builder_path = ROOT / "scripts" / "build_vv3_individual_mastery_candidate.py"
        spec = importlib.util.spec_from_file_location("vv3_individual_mastery_builder_runtime", builder_path)
        if spec is None or spec.loader is None:
            raise PatcherError("VV3 individual Full Mastery page builder is unavailable.")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        append_bytes, details = module.build_page()
        expected = str(layout.get("page_sha256", "")).upper()
        actual = hashlib.sha256(append_bytes).hexdigest().upper()
        if len(append_bytes) != 0x1000 or expected != VV3_INDIVIDUAL_FULL_MASTERY_PAGE_SHA256 or actual != expected or details.get("page_sha256") != expected:
            raise PatcherError(f"Generated VV3 individual Full Mastery page identity mismatch: expected {expected}, got {actual}.")
        return bytes(append_bytes)
    if layout.get("append_source") == "generated:vv5_individual_running_page":
        if feature.id != VV5_INDIVIDUAL_RUNNING_CANDIDATE_ID:
            raise PatcherError("VV5 individual Running append source owner mismatch.")
        import importlib.util
        import sys
        builder_path = ROOT / "scripts" / "build_vv5_full_mastery_candidate.py"
        scripts_path = str(ROOT / "scripts")
        if scripts_path not in sys.path:
            sys.path.insert(0, scripts_path)
        spec = importlib.util.spec_from_file_location("vv5_running_builder_runtime", builder_path)
        if spec is None or spec.loader is None:
            raise PatcherError("VV5 individual Running page builder is unavailable.")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        running_slot, running_map = module.build_slot(module.RUNNING_PAGE_VA, True, True)
        running_dispatcher = module.build_running_dispatcher(module.RUNNING_PAGE_VA)
        append_bytes = module.build_page(
            module.RUNNING_PAGE_VA,
            running_slot,
            running_dispatcher,
            running_map,
            dispatcher_offset=module.RUNNING_DISPATCHER_OFFSET,
        )
        expected = str(feature.raw.get("emitted", {}).get("page_sha256", "")).upper()
        actual = hashlib.sha256(append_bytes).hexdigest().upper()
        if len(append_bytes) != 0x2000 or not expected or actual != expected:
            raise PatcherError(
                f"Generated VV5 individual Running page identity mismatch: expected {expected}, got {actual}."
            )
        return bytes(append_bytes)
    if layout.get("append_source") != "generated:vv4_full_heal_page" or feature.id != VV4_FULL_HEAL_CANDIDATE_ID:
        raise PatcherError("Append layout has no supported immutable payload source.")
    import importlib.util
    builder_path = ROOT / "scripts" / "build_vv4_full_heal_candidate.py"
    spec = importlib.util.spec_from_file_location("vv4_full_heal_builder_runtime", builder_path)
    if spec is None or spec.loader is None:
        raise PatcherError("VV4 Full Heal page builder is unavailable.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    append_bytes, _ = module.build_page()
    expected = str(feature.raw.get("hook", {}).get("page_sha256", "")).upper()
    actual = hashlib.sha256(append_bytes).hexdigest().upper()
    if len(append_bytes) != 0x1000 or not expected or actual != expected:
        raise PatcherError(
            f"Generated VV4 Full Heal page identity mismatch: expected {expected}, got {actual}."
        )
    return bytes(append_bytes)


def _prepare_vv3_expanded_origins_automatic_removal(
    work: bytearray,
    feature: FunPatch,
    patch_mode: str,
) -> list[dict[str, str]]:
    """Unwind exact static/atomic dependents before removing their VV3 core.

    The serializer/reader and atomic-writer layers are automatic children of
    the complete withdrawn Origins+Running core.  A base-only render ends at
    its own append page and needs no special handling.  A complete core ends
    with the two exact automatic pages; those pages and their guarded writes
    must be removed first so the base append once again owns the file tail.
    """
    if (
        patch_mode not in EXPANDED_PATCH_MODES
        or feature.id not in VV3_EXPANDED_DETAIL_ORIGINS_FEATURE_IDS
    ):
        return []
    layout = _append_layout(feature, patch_mode)
    if layout is None:
        return []
    base_end = int(layout["append_offset"], 0) + len(
        _resolve_append_bytes(feature, layout)
    )
    if len(work) == base_end:
        return []

    try:
        from expanded_atomic_writer import (
            CONFIGS,
            FORMAT_BYTES,
            build_import_page,
            build_writer_page,
        )
        config = CONFIGS["vv3"]
    except (ImportError, KeyError) as exc:
        raise PatcherError("VV3 Expanded automatic removal is unavailable.") from exc
    expected_final_size = config.import_page_raw + config.append_size
    if len(work) != expected_final_size:
        raise PatcherError(
            f"{feature.name} cannot be removed: appended file length is not owned."
        )

    original_imports = bytes(
        work[config.original_import_raw : config.original_import_raw + 220]
    )
    import_page = build_import_page(config, original_imports)
    if bytes(work[config.import_page_raw:]) != import_page:
        raise PatcherError(
            f"Removal guard failed for {feature.id}: VV3 atomic import page differs."
        )
    writer_page, writer = build_writer_page(config)
    if writer_page[: len(writer)] != writer:
        raise PatcherError("VV3 atomic writer regeneration drifted.")
    atomic_writes: list[tuple[int, bytes, bytes, str]] = [
        (
            config.section_count_raw,
            config.sections_before.to_bytes(2, "little"),
            config.sections_after.to_bytes(2, "little"),
            "remove VV3 atomic section count",
        ),
        (
            config.size_of_image_raw,
            config.size_of_image_before.to_bytes(4, "little"),
            config.size_of_image_after.to_bytes(4, "little"),
            "remove VV3 atomic SizeOfImage extension",
        ),
    ]
    atomic_writes.extend(
        (raw, bytes(40), header, "remove VV3 atomic section header")
        for raw, header in config.section_headers
    )
    atomic_writes.append((
        config.import_directory_raw,
        config.import_directory_before,
        config.import_directory_after,
        "restore the VV3 pre-atomic import directory",
    ))
    atomic_writes.extend(
        (raw, before, after, "restore a VV3 pre-atomic save call")
        for raw, before, after in config.callsites
    )
    atomic_writes.extend((
        (
            config.writer_raw,
            bytes(len(writer)),
            writer,
            "remove the VV3 atomic writer",
        ),
        (
            config.writer_raw + 0xA00,
            bytes(len(FORMAT_BYTES)),
            FORMAT_BYTES,
            "remove the VV3 atomic sibling-path format",
        ),
    ))
    for offset, before, after, _purpose in atomic_writes:
        actual = bytes(work[offset : offset + len(after)])
        if actual != after:
            raise PatcherError(
                f"Removal guard failed for {feature.id} at 0x{offset:X}: "
                f"expected {after.hex().upper()}, found {actual.hex().upper()}"
            )

    integration = _expanded_static_repair_integration()["games"]["vv3"]
    candidate = _expanded_static_repair_candidate(integration)
    static_page = _static_repair_page(candidate, "vv3")
    pe = candidate["pe_guards"]
    section = candidate["section_plan"]
    static_writes: list[tuple[int, bytes, bytes, str]] = [
        (
            int(pe["section_count_raw"], 0),
            bytes.fromhex(pe["section_count_before"]),
            bytes.fromhex(pe["section_count_after"]),
            "remove the VV3 serializer section count",
        ),
        (
            int(pe["size_of_image_raw"], 0),
            bytes.fromhex(pe["size_of_image_before"]),
            bytes.fromhex(pe["size_of_image_after"]),
            "remove the VV3 serializer SizeOfImage extension",
        ),
        (
            int(section["header_raw"], 0),
            bytes.fromhex(section["header_guard"]),
            bytes.fromhex(section["header_bytes"]),
            "remove the VV3 serializer section header",
        ),
    ]
    static_writes.extend(
        (
            int(hook["raw"], 0),
            bytes.fromhex(hook["preimage"]),
            bytes.fromhex(hook["after"]),
            f"restore the VV3 {hook['id']} preimage",
        )
        for hook in candidate["hooks"]
    )

    owner = "automatic:vv3-expanded-dependent-removal"
    records: list[dict[str, str]] = []
    del work[config.import_page_raw:]
    records.append({
        "offset": f"0x{config.import_page_raw:X}",
        "before": import_page.hex().upper(),
        "after": "",
        "purpose": "truncate the owned VV3 atomic import page",
        "owner": owner,
    })
    for offset, before, after, purpose in reversed(atomic_writes):
        work[offset : offset + len(before)] = before
        records.append({
            "offset": f"0x{offset:X}",
            "before": after.hex().upper(),
            "after": before.hex().upper(),
            "purpose": purpose,
            "owner": owner,
        })
    static_raw = int(section["raw_start"], 0)
    if len(work) != static_raw + len(static_page) or bytes(work[static_raw:]) != static_page:
        raise PatcherError(
            f"Removal guard failed for {feature.id}: VV3 serializer page differs."
        )
    for offset, _before, after, _purpose in static_writes:
        actual = bytes(work[offset : offset + len(after)])
        if actual != after:
            raise PatcherError(
                f"Removal guard failed for {feature.id} at 0x{offset:X}: "
                f"expected {after.hex().upper()}, found {actual.hex().upper()}"
            )
    del work[static_raw:]
    records.append({
        "offset": f"0x{static_raw:X}",
        "before": static_page.hex().upper(),
        "after": "",
        "purpose": "truncate the owned VV3 serializer page",
        "owner": owner,
    })
    for offset, before, after, purpose in reversed(static_writes):
        work[offset : offset + len(before)] = before
        records.append({
            "offset": f"0x{offset:X}",
            "before": after.hex().upper(),
            "after": before.hex().upper(),
            "purpose": purpose,
            "owner": owner,
        })
    if len(work) != base_end:
        raise PatcherError("VV3 Expanded dependent removal did not restore the base tail.")
    return records


def _prepare_vv3_expanded_detail_origins_removal(
    work: bytearray,
    feature: FunPatch,
    patch_mode: str,
) -> list[dict[str, str]]:
    """Restore feature-owned constructor operands before Origins removal.

    Expanded rendering moves the two copied constructor stores only after all
    feature payloads have been composed.  Removal must therefore reverse that
    final overlay inside its private transaction before it can authenticate the
    original feature payload.  The feature reversal then restores zero stock
    bytes, so the layout overlay must not be reapplied.
    """
    if (
        patch_mode not in EXPANDED_PATCH_MODES
        or feature.id not in VV3_EXPANDED_DETAIL_ORIGINS_FEATURE_IDS
    ):
        return []
    checked: list[tuple[int, bytes, bytes]] = []
    for offset, before_value, after_value in VV3_EXPANDED_DETAIL_ORIGINS_REPLAY_DISPLACEMENTS:
        before = before_value.to_bytes(4, "little")
        after = after_value.to_bytes(4, "little")
        actual = bytes(work[offset : offset + 4])
        if actual != after:
            raise PatcherError(
                f"Removal guard failed for {feature.id} at 0x{offset:X}: "
                f"expected {after.hex().upper()}, found {actual.hex().upper()}"
            )
        checked.append((offset, after, before))
    records: list[dict[str, str]] = []
    for offset, before, after in checked:
        work[offset : offset + 4] = after
        records.append({
            "offset": f"0x{offset:X}",
            "before": before.hex().upper(),
            "after": after.hex().upper(),
            "purpose": (
                "remove the final VV3 Expanded Details constructor-field overlay "
                f"before removing {feature.id}"
            ),
            "owner": "automatic:vv3-expanded-detail-roster-layout",
        })
    return records


def _remove_feature_bytes(
    data: bytearray,
    feature: FunPatch,
    patch_mode: str,
    output_folder: Path | None = None,
) -> list[dict[str, str]]:
    """Guardedly undo one feature, including its owned append transaction."""
    original_data = bytes(data)
    work = bytearray(original_data)
    removed: list[dict[str, str]] = []
    removed.extend(
        _prepare_vv3_expanded_origins_automatic_removal(
            work, feature, patch_mode
        )
    )
    removed.extend(
        _prepare_vv3_expanded_detail_origins_removal(
            work, feature, patch_mode
        )
    )
    patches = list(feature.patches)
    patches.extend(feature.raw.get("patch_mode_overrides", {}).get(patch_mode, []))
    for patch in reversed(patches):
        offset = int(patch["offset"], 0)
        before = _patch_bytes(patch, "before")
        after = _patch_bytes(patch, "after")
        actual = bytes(work[offset : offset + len(after)])
        if (
            feature.id == "vv5_full_mastery_all_stage_a_candidate"
            and offset == 0xDB766
            and actual == before
        ):
            continue
        if actual != after:
            raise PatcherError(
                f"Removal guard failed for {feature.id} at {patch['offset']}: "
                f"expected {after.hex().upper()}, found {actual.hex().upper()}"
            )
        work[offset : offset + len(before)] = before
        removed.append(
            {
                "offset": patch["offset"],
                "before": after.hex().upper(),
                "after": before.hex().upper(),
                "purpose": f"remove {feature.id}: {patch['purpose']}",
                "owner": f"feature:{feature.id}",
            }
        )
    layout = _append_layout(feature, patch_mode)
    if layout is not None:
        append_offset = int(layout["append_offset"], 0)
        append_bytes = _resolve_append_bytes(feature, layout)
        if len(work) != append_offset + len(append_bytes):
            raise PatcherError(
                f"{feature.name} cannot be removed: appended file length is not owned."
            )
        actual = bytes(work[append_offset:])
        if actual != append_bytes:
            raise PatcherError(
                f"{feature.name} cannot be removed: appended page guard differs."
            )
        del work[append_offset:]
        for item in reversed(layout["header_patches"]):
            offset = int(item["offset"], 0)
            before = _patch_bytes(item, "before")
            after = _patch_bytes(item, "after")
            actual = bytes(work[offset : offset + len(after)])
            if actual != after:
                raise PatcherError(
                    f"{feature.name} removal header guard failed at {item['offset']}."
                )
            work[offset : offset + len(before)] = before
        removed.append(
            {
                "offset": layout["append_offset"],
                "before": append_bytes.hex().upper(),
                "after": "",
                "purpose": f"truncate owned append for {feature.id}",
                "owner": f"feature:{feature.id}",
            }
        )
    checksum_offset, _ = _pe_checksum_layout(work)
    struct.pack_into("<I", work, checksum_offset, 0)
    struct.pack_into("<I", work, checksum_offset, pe_checksum(work))
    if output_folder is not None:
        _remove_companion_files(output_folder, [feature])
    data[:] = work
    return removed


def _remove_feature_with_dependency_guard(
    data: bytearray,
    feature: FunPatch,
    installed_features: list[FunPatch],
    patch_mode: str,
) -> list[dict[str, str]]:
    dependents = [
        item.id
        for item in installed_features
        if item.id != feature.id and feature.id in _dependency_ids(item)
    ]
    if dependents:
        raise PatcherError(
            f"Cannot remove {feature.id} while dependent optional patch(es) remain: "
            + ", ".join(sorted(dependents))
        )
    return _remove_feature_bytes(data, feature, patch_mode)


VV4_FULL_HEAL_CANDIDATE_EXE_HASHES = {
    "collection_progression": "26E82AF29118312978A94225B3D3094511B1765C44185F416F600272A7DB80B9",
    "immediate_fixed": "6220D3B9572809A713C9D6274364844AB486834419FCE4AA9DDDABC3AAED1274",
}
VV5_INDIVIDUAL_RUNNING_CANDIDATE_ID = "vv5_individual_grant_running_candidate"
VV5_INDIVIDUAL_RUNNING_CANDIDATE_PATHS = {
    "manifest": ROOT / "data" / "candidates" / "vv5_individual_running_candidate.json",
    "map": ROOT / "data" / "candidates" / "vv5_individual_running_candidate_map.json",
}
VV5_INDIVIDUAL_RUNNING_PARENT_SHA256 = {
    "collection_progression": "857E22D7C361B802508BF789C3CC486E42E76021F5AA579BB1D16CC6E0D017A0",
}
VV5_INDIVIDUAL_RUNNING_MANIFEST_SHA256 = "7869A3364F598B882E8C29F3A1957C5AF13A4654CF45EE0464DAA34545CB128B"
VV5_INDIVIDUAL_RUNNING_MAP_SHA256 = "3FB4B979A98CC3C5FE76D7BD2D3851E5F918A8436141D4DF8A9C1969B6B11FAF"
VV5_INDIVIDUAL_RUNNING_HELPER_SHA256 = "9692B2C08FEB1F76AA70709C59539B9A76369FE46C5C2E5888A965DA2D562FCC"
VV5_INDIVIDUAL_RUNNING_PAGE_SHA256 = "9DA0E15FA9AB09FF986CC5F132DDB9C7662F77C445634504DDEA9DFAACF1C3F2"


def publish_vv4_full_heal_removal(
    output_folder: Path,
    executable_name: str,
    feature: FunPatch,
    patch_mode: str,
) -> list[dict[str, str]]:
    """Atomically restore the parent EXE and companion DLL together.

    The candidate files are verified before staging, both replacements are
    backed up on the destination volume, and any replace/postverify failure
    restores both originals.  No mixed candidate/parent state is published.
    """
    if feature.id != VV4_FULL_HEAL_CANDIDATE_ID:
        raise PatcherError("VV4 Full Heal removal requires the certified candidate feature.")
    root = Path(output_folder).resolve()
    exe = (root / executable_name).resolve()
    if exe.parent != root or not exe.is_file():
        raise PatcherError("VV4 Full Heal removal executable path is unsafe or missing.")
    companion_item = next(iter(feature.raw.get("companion_files", [])), None)
    if companion_item is None:
        raise PatcherError("VV4 Full Heal companion metadata is missing.")
    dll = root / _safe_companion_destination(companion_item["destination"])
    if not dll.is_file():
        raise PatcherError("VV4 Full Heal removal companion is missing.")
    candidate_exe_hash = VV4_FULL_HEAL_CANDIDATE_EXE_HASHES.get(patch_mode)
    if candidate_exe_hash is None or sha256(exe) != candidate_exe_hash:
        raise PatcherError("VV4 Full Heal removal executable preimage mismatch.")
    candidate_dll_hash = str(companion_item["sha256"]).upper()
    if sha256(dll) != candidate_dll_hash:
        raise PatcherError("VV4 Full Heal removal companion preimage mismatch.")
    work = bytearray(exe.read_bytes())
    removed = _remove_feature_bytes(work, feature, patch_mode, output_folder=None)
    expected_parent_hash = {
        "collection_progression": VV4_FULL_HEAL_PARENT_COLLECTION_SHA256,
        "immediate_fixed": VV4_FULL_HEAL_PARENT_IMMEDIATE_SHA256,
    }.get(patch_mode)
    if expected_parent_hash is None or hashlib.sha256(work).hexdigest().upper() != expected_parent_hash:
        raise PatcherError("VV4 Full Heal removal did not reconstruct the certified parent EXE.")
    restore_source = (ROOT / str(companion_item["restore_source"])).resolve()
    restore_hash = str(companion_item["restore_sha256"]).upper()
    if not restore_source.is_file() or sha256(restore_source) != restore_hash:
        raise PatcherError("VV4 Full Heal parent companion restore source is missing or corrupt.")
    parent = root.parent
    destination_precondition = _capture_tree_snapshot(root)
    stage = parent / f".{root.name}.remove-stage-{uuid.uuid4().hex}"
    if os.path.lexists(stage):
        raise PatcherError("VV4 Full Heal removal staging collision.")
    stage.mkdir()
    staged_exe = stage / executable_name
    staged_dll = stage / dll.name
    backup_exe = stage / f"{executable_name}.backup"
    backup_dll = stage / f"{dll.name}.backup"
    replaced: list[tuple[Path, Path]] = []
    unresolved: list[dict[str, Any]] = []
    try:
        staged_exe.write_bytes(work)
        shutil.copy2(restore_source, staged_dll)
        if sha256(staged_exe) != expected_parent_hash or sha256(staged_dll) != restore_hash:
            raise PatcherError("VV4 Full Heal removal staged verification failed.")
        # Immediate race recheck before either replace.
        if sha256(exe) != candidate_exe_hash or sha256(dll) != candidate_dll_hash:
            raise PatcherError("VV4 Full Heal removal destination changed before replace.")
        shutil.copy2(exe, backup_exe)
        shutil.copy2(dll, backup_dll)
        os.replace(staged_exe, exe)
        replaced.append((exe, backup_exe))
        os.replace(staged_dll, dll)
        replaced.append((dll, backup_dll))
        if sha256(exe) != expected_parent_hash or sha256(dll) != restore_hash:
            raise PatcherError("VV4 Full Heal removal postverify failed.")
        return removed
    except Exception:
        # Restore every destination that may have been replaced, in reverse
        # order, using the verified backups.  If no replace occurred the
        # original files were never touched.
        if (exe, backup_exe) not in replaced and backup_exe.is_file() and sha256(exe) == expected_parent_hash:
            replaced.append((exe, backup_exe))
        if (dll, backup_dll) not in replaced and backup_dll.is_file() and sha256(dll) == restore_hash:
            replaced.append((dll, backup_dll))
        for destination, backup in reversed(replaced):
            expected = candidate_exe_hash if destination == exe else candidate_dll_hash
            try:
                if not backup.is_file() or sha256(backup) != expected:
                    raise PatcherError(f"Removal backup verification failed: {backup}")
                os.replace(backup, destination)
                if not destination.is_file() or sha256(destination) != expected:
                    raise PatcherError(f"Removal restore verification failed: {destination}")
            except Exception as restore_error:
                unresolved.append(
                    {
                        "original_path": str(destination),
                        "original_sha256": expected,
                        "original_size": destination.stat().st_size if destination.is_file() else None,
                        "backup_path": str(backup),
                        "backup_sha256": sha256(backup) if backup.is_file() else None,
                        "backup_size": backup.stat().st_size if backup.is_file() else None,
                        "relative_path": destination.relative_to(root).as_posix(),
                        "error": str(restore_error),
                    }
                )
        if unresolved:
            recovery_dir = parent / f".{root.name}.remove-recovery-{uuid.uuid4().hex}"
            if os.path.lexists(recovery_dir):
                raise PatcherError("VV4 Full Heal removal recovery destination collision.")
            recovery_dir.mkdir()
            retained = recovery_dir / "backups"
            retained.mkdir()
            for item in unresolved:
                backup = Path(item["backup_path"])
                if backup.is_file():
                    os.replace(backup, retained / backup.name)
                    item["backup_path"] = str(retained / backup.name)
                    # The retained original candidate backup is authoritative
                    # for both the original size and hash in recovery records.
                    item["original_size"] = (retained / backup.name).stat().st_size
                    item["backup_size"] = item["original_size"]
                    item["backup_sha256"] = sha256(retained / backup.name)
            retained_stage = recovery_dir / "stage"
            if stage.exists():
                os.replace(stage, retained_stage)
                for item in unresolved:
                    item["stage_path"] = str(retained_stage)
            stage_snapshot = _capture_tree_snapshot(retained_stage) if retained_stage.exists() else None
            restored_snapshot = _capture_tree_snapshot(root)
            restored_entries = {item["relative_path"]: item for item in restored_snapshot["entries"]}
            for item in unresolved:
                rel = item["relative_path"]
                restored_entries[rel] = {
                    "relative_path": rel,
                    "type": "file",
                    "size": item["original_size"],
                    "sha256": item["original_sha256"],
                }
            restored_snapshot["entries"] = sorted(restored_entries.values(), key=lambda entry: entry["relative_path"])
            report_records = [
                {
                    "relative_path": item["relative_path"],
                    "original_path": item["original_path"],
                    "sha256": item["original_sha256"],
                    "size": item["original_size"],
                    "backup_path": item["backup_path"],
                }
                for item in unresolved
            ]
            _write_recovery_report(
                recovery_dir,
                "remove",
                report_records,
                retained,
                destination_root=root,
                destination_snapshot=_capture_tree_snapshot(root),
                restored_snapshot=restored_snapshot,
                destination_precondition=destination_precondition,
                staged_copy_root=retained_stage if retained_stage.exists() else None,
            )
            raise PatcherError(f"VV4 Full Heal removal recovery is unresolved; evidence retained at {recovery_dir}")
        raise
    finally:
        if stage.exists() and not unresolved:
            _cleanup_owned_tree(stage)


def recover_vv4_transaction(recovery_dir: Path) -> None:
    """Replay a strict schema-v3 production recovery report safely."""
    root = Path(recovery_dir).absolute()
    _validate_recovery_root_no_follow(root)
    report = root / "recovery-report.json"
    try:
        report_bytes, _ = _read_recovery_file(report)
    except PatcherError as exc:
        raise PatcherError("Recovery report is missing or unsafe.") from exc
    payload = json.loads(report_bytes.decode("utf-8"))
    _validate_vv4_recovery_payload(payload, root)
    destination = payload["destination"]
    destination_root = Path(destination["root"])
    retry_state = destination["retry_state"]
    retry_snapshot = {"exists": False, "entries": []} if retry_state["kind"] == "absent" else retry_state["snapshot"]
    if not _tree_snapshot_matches(destination_root, retry_snapshot):
        raise PatcherError("Recovery destination changed or contains unknown members.")
    ownership = payload["ownership"]
    backup_area = ownership["original_backup_root"]
    backup_root = root / backup_area["path"] if backup_area["path"] else None
    stage_area = ownership["retained_removal_stage_root"]
    retained_stage = root / stage_area["path"] if stage_area["path"] else None
    if backup_root is not None and not _tree_snapshot_matches(backup_root, backup_area["snapshot"]):
        raise PatcherError("Recovery backups changed or contain unknown members.")
    if retained_stage is not None and not _tree_snapshot_matches(retained_stage, stage_area["snapshot"]):
        raise PatcherError("Recovery retained stage changed or contains unknown members.")
    restored_state = payload["restored_state"]
    restored_snapshot = {"exists": False, "entries": []} if restored_state is None else restored_state
    actions: list[tuple[Path, Path, str, int]] = []
    for item in payload["members"]:
        destination_path = Path(str(item["original_path"]))
        backup = root / str(item["backup_relative_path"])
        expected = str(item["original_sha256"]).upper()
        rel = Path(str(item["relative_path"]))
        try:
            actual_relative = destination_path.absolute().relative_to(destination_root.absolute())
        except ValueError as exc:
            raise PatcherError("Recovery destination escapes its recorded root.") from exc
        if actual_relative.as_posix().casefold() != rel.as_posix().casefold():
            raise PatcherError("Recovery destination path does not match its relative path.")
        data, info = _read_recovery_file(backup)
        if hashlib.sha256(data).hexdigest().upper() != expected or len(data) != int(item["backup_size"]):
            raise PatcherError("Recovery backup is corrupt or size-mismatched.")
        if int(item["original_size"]) != info.st_size:
            raise PatcherError("Recovery original/backup size accounting is inconsistent.")
        actions.append((destination_path, backup, expected, info.st_size))
    replay_stage = root / f".replay-stage-{uuid.uuid4().hex}"
    replay_files: list[tuple[Path, Path, str, int]] = []
    try:
        replay_stage.mkdir()
        for index, (destination_path, backup, expected, size) in enumerate(actions):
            staged = replay_stage / f"member-{index:04d}.bin"
            data, _ = _read_recovery_file(backup)
            with staged.open("xb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            staged_data, staged_info = _read_recovery_file(staged)
            if hashlib.sha256(staged_data).hexdigest().upper() != expected or staged_info.st_size != size:
                raise PatcherError("Replay staging verification failed.")
            replay_files.append((destination_path, staged, expected, size))
        for destination_path, staged, expected, _size in replay_files:
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staged, destination_path)
            data, _ = _read_recovery_file(destination_path)
            if hashlib.sha256(data).hexdigest().upper() != expected:
                raise PatcherError("Recovered destination failed verification.")
        if not _tree_snapshot_matches(destination_root, restored_snapshot):
            raise PatcherError("Recovered destination is not an exact complete tree.")
    except Exception as exc:
        current = _capture_tree_snapshot(destination_root)
        payload["destination"]["failure_diagnostic"] = current
        payload["destination"]["retry_state"] = {"kind": "tree", "snapshot": current} if current.get("exists") else {"kind": "absent"}
        if backup_root is not None:
            payload["ownership"]["original_backup_root"]["snapshot"] = _capture_tree_snapshot(backup_root)
        if replay_stage.exists():
            try:
                _cleanup_owned_tree(replay_stage)
            except (OSError, PatcherError):
                payload["ownership"]["replay_stage_root"] = {"path": replay_stage.relative_to(root).as_posix(), "snapshot": _capture_tree_snapshot(replay_stage)}
        _atomic_write_recovery_json(report, payload)
        raise PatcherError(f"Recovery remains unresolved at {root}") from exc
    else:
        if backup_root is not None:
            _cleanup_owned_tree(backup_root)
        if replay_stage.exists():
            _cleanup_owned_tree(replay_stage)
    if not _tree_snapshot_matches(destination_root, restored_snapshot):
        raise PatcherError("Recovered destination is not an exact complete tree.")
    final_snapshot = _capture_tree_snapshot(root)
    declared_prefixes = [str(area["path"]).rstrip("/") for area in ownership.values() if isinstance(area, dict) and area.get("path")]
    for entry in final_snapshot.get("entries", []):
        rel = str(entry["relative_path"])
        if rel == "recovery-report.json":
            continue
        if not any(rel == prefix or rel.startswith(prefix + "/") for prefix in declared_prefixes):
            raise PatcherError("Recovery contains unknown material; evidence retained.")
    if retained_stage is not None and retained_stage.exists():
        _cleanup_owned_tree(retained_stage)
    report.unlink(missing_ok=True)
    _cleanup_owned_tree(root)


def _fun_patch_support(
    build: Build, fun_patches: list[FunPatch]
) -> list[dict[str, str]]:
    selected_ids = {patch.id for patch in fun_patches}
    patches: list[dict[str, str]] = []
    for support in _manifest().get("fun_patch_support", []):
        if support["game_id"] != build.id:
            continue
        if selected_ids.intersection(support["when_any"]):
            for patch in support["patches"]:
                tagged = dict(patch)
                tagged["_owner"] = "automatic:compatibility"
                patches.append(tagged)
    return patches


def _relocation_ledger_sha256(patches: list[dict[str, Any]]) -> str:
    canonical = json.dumps(
        patches,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest().upper()


def _vv4_expanded_contract() -> dict[str, Any]:
    try:
        contract = json.loads(VV4_EXPANDED_CONTRACT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PatcherError("VV4 Expanded-256 contract is unavailable or invalid.") from exc
    if (
        contract.get("schema_version") != 1
        or contract.get("game_id") != "vv4"
        or contract.get("source_sha256")
        != "6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220"
        or contract.get("publication", {}).get("enabled") is not False
    ):
        raise PatcherError("VV4 Expanded-256 contract identity or fail-closed status is invalid.")
    return contract


def _validate_vv4_expanded_contract(
    game: dict[str, Any],
) -> dict[str, Any]:
    contract = _vv4_expanded_contract()
    if game.get("source_sha256") != contract["source_sha256"]:
        raise PatcherError("VV4 Expanded-256 contract source fingerprint is not bound to the guarded manifest.")
    by_offset = {item.get("offset"): item for item in game.get("patches", [])}
    for expected in contract["current_origins_shr_absolute_operands"]:
        actual = by_offset.get(expected["offset"])
        if not isinstance(actual, dict) or any(
            actual.get(key) != expected[key]
            for key in ("before", "after", "purpose")
        ):
            raise PatcherError(
                f"VV4 current-Origins .shr guard drift at {expected['offset']}."
            )
    compatibility = contract["stock_save_compatibility"]
    for expected in (
        compatibility["loader_hook"],
        compatibility["conversion_cave"],
    ):
        actual = by_offset.get(expected["offset"])
        if not isinstance(actual, dict):
            raise PatcherError(
                f"VV4 stock-save compatibility guard is missing at {expected['offset']}."
            )
        if expected["offset"] == compatibility["loader_hook"]["offset"]:
            if any(actual.get(key) != expected[key] for key in ("before", "after", "purpose")):
                raise PatcherError("VV4 stock-save loader fallback guard drifted.")
        else:
            try:
                cave_before = bytes.fromhex(actual.get("before", ""))
                cave_after = bytes.fromhex(actual.get("after", ""))
            except (TypeError, ValueError) as exc:
                raise PatcherError("VV4 stock-save conversion cave guard is malformed.") from exc
            if (
                actual.get("purpose") != expected["purpose"]
                or len(cave_before) != expected["length"]
                or len(cave_after) != expected["length"]
                or any(bytes.fromhex(sequence) not in cave_after for sequence in expected["required_sequences"])
            ):
                raise PatcherError("VV4 stock-save conversion cave guard drifted.")
    return contract


def _validate_vv4_origins_relocation_contract(
    feature: FunPatch,
    relocation: dict[str, Any],
) -> None:
    if feature.id != "vv4_enable_origins_exclusive_features":
        return
    contract = _vv4_expanded_contract()
    expected_groups = (
        contract["origins_payload_shr_absolute_operands"],
        contract["all_feature_stale_origins_shr_absolute_operands"],
    )
    expected = [item for group in expected_groups for item in group]
    if (
        relocation.get("stock_virtual_address") != "0x728000"
        or relocation.get("expanded_virtual_address") != "0x85A000"
    ):
        raise PatcherError("VV4 Origins payload .shr relocation range is not the certified range.")
    patches = relocation.get("patches")
    if not isinstance(patches, list) or len(patches) != 13:
        raise PatcherError("VV4 current Origins relocation ledger must contain exactly thirteen rows.")
    by_offset = {item.get("offset"): item for item in patches}
    if len(by_offset) != len(patches):
        raise PatcherError("VV4 current Origins relocation ledger contains duplicate offsets.")
    # The eight absolute rows are not the whole ledger.  Keep the four
    # external helper calls and the moved-source call at CC02A under the same
    # exact-build contract: a rel32 row's stock preimage must encode the
    # declared stock source/target, and its expanded target must account for
    # the moved .shr section.  Previously these rows were counted but their
    # arithmetic was not checked, so a malformed rel32 byte could pass the
    # ledger hash gate and still be emitted by the renderer.
    expected_rel32_offsets = {
        "0x896CC",
        "0x89734",
        "0x8973C",
        "0x89746",
        "0xCC02A",
    }
    actual_rel32_offsets = {
        item.get("offset")
        for item in patches
        if isinstance(item, dict) and item.get("kind") == "rel32"
    }
    if actual_rel32_offsets != expected_rel32_offsets:
        raise PatcherError(
            "VV4 current Origins relocation partition drifted: expected exactly "
            "eight absolute and five rel32 rows."
        )
    stock_va = int(relocation["stock_virtual_address"], 0)
    expanded_va = int(relocation["expanded_virtual_address"], 0)
    delta = expanded_va - stock_va
    if delta <= 0:
        raise PatcherError("VV4 current Origins relocation range has a non-positive delta.")
    for offset in sorted(expected_rel32_offsets):
        row = by_offset[offset]
        if not isinstance(row, dict):
            raise PatcherError(f"VV4 rel32 relocation row is malformed at {offset}.")
        try:
            source_stock = int(row["source_virtual_address"], 0)
            target_stock = int(row["target_stock_virtual_address"], 0)
            before = bytes.fromhex(row["before"])
        except (KeyError, TypeError, ValueError) as exc:
            raise PatcherError(f"VV4 rel32 relocation metadata is incomplete at {offset}.") from exc
        if len(before) != 4:
            raise PatcherError(f"VV4 rel32 relocation preimage is not a DWORD at {offset}.")
        target_in_shr = stock_va <= target_stock < stock_va + 0x1000
        expected_target = target_stock + delta if target_in_shr else target_stock
        declared_target = row.get("target_expanded_virtual_address")
        if declared_target is not None:
            try:
                if int(declared_target, 0) != expected_target:
                    raise PatcherError(f"VV4 rel32 moved/unmoved target drifted at {offset}.")
            except (TypeError, ValueError) as exc:
                raise PatcherError(f"VV4 rel32 expanded target is malformed at {offset}.") from exc
        expected_before = (target_stock - (source_stock + 5)).to_bytes(4, "little", signed=True)
        if before != expected_before:
            raise PatcherError(f"VV4 rel32 stock preimage drifted at {offset}.")
    absolute = [
        item for item in patches
        if item.get("kind", "absolute") == "absolute"
    ]
    if len(absolute) != len(expected):
        raise PatcherError("VV4 current Origins payload must contain exactly eight absolute .shr operands.")
    for expected_item in expected:
        actual = by_offset.get(expected_item["offset"])
        if (
            not isinstance(actual, dict)
            or actual.get("kind", "absolute") != "absolute"
            or actual.get("before") != expected_item["before"]
            or actual.get("target_stock_virtual_address") != expected_item["stock_virtual_address"]
            or actual.get("target_expanded_virtual_address") != expected_item["expanded_virtual_address"]
            or (
                "source_virtual_address" in expected_item
                and actual.get("source_virtual_address") != expected_item["source_virtual_address"]
            )
            or (
                "purpose" in expected_item
                and actual.get("purpose") != expected_item["purpose"]
            )
        ):
            raise PatcherError(
                f"VV4 current Origins payload absolute .shr guard drift at {expected_item['offset']}."
            )
    if relocation.get("ledger_sha256") != VV4_ORIGINS_RELOCATION_LEDGER_SHA256:
        raise PatcherError("VV4 current Origins relocation ledger digest drifted.")
    if _relocation_ledger_sha256(patches) != VV4_ORIGINS_RELOCATION_LEDGER_SHA256:
        raise PatcherError("VV4 current Origins relocation row identity drifted.")


def _validate_vv5_origins_relocation_contract(
    feature: FunPatch,
    relocation: dict[str, Any],
) -> None:
    if feature.id != "vv5_enable_origins_exclusive_features":
        return
    if (
        relocation.get("stock_virtual_address") != "0x7B2000"
        or relocation.get("expanded_virtual_address") != "0x8EB000"
    ):
        raise PatcherError("VV5 Origins relocation range is not the certified range.")
    evidence = relocation.get("evidence")
    expected_evidence = {
        "exact_stock_sha256": VV5_ORIGINS_STOCK_SHA256,
        "current_feature_sites": 66,
        "payload_internal_absolute_sites": 23,
        "cross_section_rel32_sites": 36,
        "external_absolute_sites": 7,
        "expanded_mode_native_override_sites": 2,
        "complete_current_feature_relocation_sites": 43,
    }
    if not isinstance(evidence, dict) or any(
        evidence.get(key) != value for key, value in expected_evidence.items()
    ):
        raise PatcherError("VV5 Origins relocation evidence or exact stock hash drifted.")
    patches = relocation.get("patches")
    if not isinstance(patches, list) or len(patches) != 66:
        raise PatcherError("VV5 Origins relocation ledger must contain exactly 66 rows.")
    by_offset: dict[str, dict[str, Any]] = {}
    for patch in patches:
        offset = patch.get("offset") if isinstance(patch, dict) else None
        if not isinstance(offset, str) or offset in by_offset:
            raise PatcherError("VV5 Origins relocation ledger contains duplicate or malformed offsets.")
        by_offset[offset] = patch
    partitions = VV5_ORIGINS_RELOCATION_PARTITIONS
    expected_offsets = set().union(*partitions.values())
    if set(by_offset) != expected_offsets:
        raise PatcherError("VV5 Origins relocation ledger has missing or unexpected rows.")
    stock_va = int(relocation["stock_virtual_address"], 0)
    expanded_va = int(relocation["expanded_virtual_address"], 0)
    delta = expanded_va - stock_va
    if delta <= 0:
        raise PatcherError("VV5 Origins relocation range has a non-positive delta.")
    override_offsets = set(VV5_ORIGINS_NATIVE_OVERRIDE_PREIMAGES)
    actual_override_offsets: set[str] = set()
    for offset, patch in by_offset.items():
        kind = patch.get("kind", "absolute")
        before_hex = patch.get("before")
        try:
            before = bytes.fromhex(before_hex)
        except (TypeError, ValueError) as exc:
            raise PatcherError(f"VV5 Origins relocation preimage is malformed at {offset}.") from exc
        if len(before) != 4:
            raise PatcherError(f"VV5 Origins relocation preimage is not a DWORD at {offset}.")
        if offset in partitions["cross_section_rel32"]:
            if kind != "rel32":
                raise PatcherError(f"VV5 rel32 relocation class drifted at {offset}.")
            try:
                source_expanded = int(patch["source_expanded_virtual_address"], 0)
                target_stock = int(patch["target_stock_virtual_address"], 0)
                target_expanded = int(patch["target_expanded_virtual_address"], 0)
            except (KeyError, TypeError, ValueError) as exc:
                raise PatcherError(f"VV5 rel32 relocation metadata is incomplete at {offset}.") from exc
            source_stock = (
                source_expanded - delta
                if expanded_va <= source_expanded < expanded_va + 0x1000
                else source_expanded
            )
            expected_before = (target_stock - (source_stock + 5)).to_bytes(
                4, "little", signed=True
            )
            if before != expected_before:
                raise PatcherError(f"VV5 rel32 stock preimage drifted at {offset}.")
            target_in_shr = stock_va <= target_stock < stock_va + 0x1000
            expected_target = target_stock + delta if target_in_shr else target_stock
            if target_expanded != expected_target:
                raise PatcherError(f"VV5 rel32 moved/unmoved target drifted at {offset}.")
            if offset in override_offsets:
                expected_before, expected_skip = VV5_ORIGINS_NATIVE_OVERRIDE_PREIMAGES[offset]
                if before_hex != expected_before or patch.get("expanded_skip_before") != expected_skip:
                    raise PatcherError(f"VV5 native override guard drifted at {offset}.")
                actual_override_offsets.add(offset)
            elif patch.get("expanded_skip_before") is not None:
                raise PatcherError(f"VV5 unexpected native override guard at {offset}.")
        elif offset in partitions["payload_internal_absolute"] or offset in partitions["external_absolute"]:
            if kind != "absolute":
                raise PatcherError(f"VV5 absolute relocation class drifted at {offset}.")
            value = int.from_bytes(before, "little")
            if not stock_va <= value < stock_va + 0x1000:
                raise PatcherError(f"VV5 absolute relocation points outside stock .shr at {offset}.")
            if offset in partitions["external_absolute"]:
                if (
                    patch.get("target_stock_virtual_address") != f"0x{value:X}"
                    or patch.get("target_expanded_virtual_address") != f"0x{value + delta:X}"
                ):
                    raise PatcherError(f"VV5 external absolute target drifted at {offset}.")
            elif patch.get("expanded_skip_before") is not None:
                raise PatcherError(f"VV5 unexpected native override guard at {offset}.")
        else:
            raise PatcherError(f"VV5 relocation partition is undefined at {offset}.")
    if actual_override_offsets != override_offsets:
        raise PatcherError("VV5 native override partition is incomplete.")
    if relocation.get("ledger_sha256") != VV5_ORIGINS_RELOCATION_LEDGER_SHA256:
        raise PatcherError("VV5 Origins relocation ledger digest drifted.")
    if _relocation_ledger_sha256(patches) != VV5_ORIGINS_RELOCATION_LEDGER_SHA256:
        raise PatcherError("VV5 Origins relocation row identity drifted.")


def _relocate_expanded_shr_fun_patches(
    build: Build,
    patch_mode: str,
    fun_patches: list[FunPatch],
    data: bytearray,
) -> list[dict[str, str]]:
    """Relocate absolute pointers embedded in fun payloads after .shr moves.

    The experimental VV3-VV5 layout moves the stock ``.shr`` section.  Fun
    patches are applied after the expanded manifest, so payloads installed by
    a fun feature need their own exact-build relocation pass.  This is driven
    by explicit manifest guards; no broad byte-pattern search is performed.
    """
    if patch_mode not in EXPANDED_PATCH_MODES:
        return []

    planned: list[dict[str, Any]] = []
    occupied: dict[int, str] = {}
    for feature in fun_patches:
        relocation = feature.raw.get("expanded_shr_relocations")
        if not relocation:
            continue
        if build.id not in {"vv4", "vv5"}:
            raise PatcherError(
                f"{feature.name} declares an expanded .shr relocation but is not a VV4/VV5 feature."
            )
        expected_identity = EXPANDED_MANIFEST_IDENTITIES[build.id]
        if feature.raw.get("game_id") != build.id:
            raise PatcherError(
                f"{feature.name} expanded .shr relocation game identity does not match {build.id}."
            )
        if build.sha256 != expected_identity["source_sha256"]:
            raise PatcherError(
                f"{feature.name} expanded .shr relocation requires the exact {build.id} stock fingerprint."
            )
        _validate_vv4_origins_relocation_contract(feature, relocation)
        _validate_vv5_origins_relocation_contract(feature, relocation)
        try:
            stock_va = int(relocation["stock_virtual_address"], 0)
            expanded_va = int(relocation["expanded_virtual_address"], 0)
        except (KeyError, TypeError, ValueError) as exc:
            raise PatcherError("Internal expanded .shr relocation range is malformed.") from exc
        delta = expanded_va - stock_va
        if delta <= 0:
            raise PatcherError("Internal expanded .shr relocation has a non-positive delta.")
        for patch in relocation.get("patches", []):
            if not isinstance(patch, dict):
                raise PatcherError("Internal expanded .shr relocation row is malformed.")
            try:
                offset = int(patch["offset"], 0)
                before = bytes.fromhex(patch["before"])
            except (KeyError, TypeError, ValueError) as exc:
                raise PatcherError("Internal expanded .shr relocation row is malformed.") from exc
            if offset < 0 or offset + 4 > len(data):
                raise PatcherError(
                    f"Expanded .shr relocation at {patch.get('offset')} is outside the input buffer."
                )
            if len(before) != 4:
                raise PatcherError(
                    f"Internal expanded .shr relocation at {patch['offset']} is not a DWORD."
                )
            actual = bytes(data[offset : offset + 4])
            relocation_status = None
            if actual != before:
                # VV5's expanded-mode overrides deliberately restore the two
                # stock doubler hooks.  Their relocation rows remain in the
                # complete IDA ledger, but a native preimage is a guarded
                # no-op rather than permission to rewrite an unrelated stock
                # instruction.
                skipped = patch.get("expanded_skip_before")
                if skipped:
                    try:
                        skipped_bytes = bytes.fromhex(skipped)
                    except (TypeError, ValueError) as exc:
                        raise PatcherError(
                            f"Expanded .shr relocation override guard is malformed at {patch['offset']}."
                        ) from exc
                    if len(skipped_bytes) != 4:
                        raise PatcherError(
                            f"Expanded .shr relocation override guard is not a DWORD at {patch['offset']}."
                        )
                    if actual == skipped_bytes:
                        after = actual
                        relocation_status = "native_override_preserved"
                    else:
                        raise PatcherError(
                            f"Expanded .shr relocation guard failed at {patch['offset']}: "
                            f"expected {before.hex().upper()}, found {actual.hex().upper()}"
                        )
                else:
                    raise PatcherError(
                        f"Expanded .shr relocation guard failed at {patch['offset']}: "
                        f"expected {before.hex().upper()}, found {actual.hex().upper()}"
                    )
            else:
                kind = patch.get("kind", "absolute")
                if kind == "absolute":
                    value = int.from_bytes(before, "little")
                    if not stock_va <= value < stock_va + 0x1000:
                        raise PatcherError(
                            f"Expanded .shr relocation at {patch['offset']} points outside stock .shr."
                        )
                    declared_stock = patch.get("target_stock_virtual_address")
                    if declared_stock is not None:
                        try:
                            declared_stock_value = int(declared_stock, 0)
                        except (TypeError, ValueError) as exc:
                            raise PatcherError(
                                f"Expanded .shr relocation at {patch['offset']} has a malformed stock target."
                            ) from exc
                        if declared_stock_value != value:
                            raise PatcherError(
                                f"Expanded .shr relocation at {patch['offset']} has an inconsistent stock target."
                            )
                    after = (value + delta).to_bytes(4, "little")
                    declared_expanded = patch.get("target_expanded_virtual_address")
                    if declared_expanded is not None:
                        try:
                            declared_expanded_value = int(declared_expanded, 0)
                        except (TypeError, ValueError) as exc:
                            raise PatcherError(
                                f"Expanded .shr relocation at {patch['offset']} has a malformed expanded target."
                            ) from exc
                        if declared_expanded_value != value + delta:
                            raise PatcherError(
                                f"Expanded .shr relocation at {patch['offset']} has an inconsistent expanded target."
                            )
                elif kind == "rel32":
                    try:
                        source_value = patch.get("source_expanded_virtual_address")
                        if source_value is None:
                            source_value = patch["source_virtual_address"]
                        source_va = int(source_value, 0)
                        target_stock_va = int(patch["target_stock_virtual_address"], 0)
                    except (KeyError, TypeError, ValueError) as exc:
                        raise PatcherError(
                            f"Internal expanded .shr rel32 relocation at {patch['offset']} is missing source/target metadata."
                        ) from exc
                    source_stock_va = (
                        source_va - delta
                        if expanded_va <= source_va < expanded_va + 0x1000
                        else source_va
                    )
                    expected_before = (target_stock_va - (source_stock_va + 5)).to_bytes(
                        4, "little", signed=True
                    )
                    if actual != expected_before:
                        raise PatcherError(
                            f"Expanded .shr rel32 stock preimage guard failed at {patch['offset']}: "
                            f"expected {expected_before.hex().upper()}, found {actual.hex().upper()}"
                        )
                    # A rel32 operand can itself live inside the moved .shr
                    # payload.  VV4's 0xCC02A row predates the explicit
                    # source_expanded_virtual_address field used by VV5, so
                    # infer the moved source from the certified source range
                    # rather than relocating only its target.
                    if (
                        patch.get("source_expanded_virtual_address") is None
                        and stock_va <= source_va < stock_va + 0x1000
                    ):
                        source_va += delta
                    target_in_shr = stock_va <= target_stock_va < stock_va + 0x1000
                    target_expanded_va = (
                        target_stock_va + delta if target_in_shr else target_stock_va
                    )
                    declared_target = patch.get("target_expanded_virtual_address")
                    if declared_target is not None:
                        try:
                            declared_target_value = int(declared_target, 0)
                        except (TypeError, ValueError) as exc:
                            raise PatcherError(
                                f"Expanded .shr rel32 relocation at {patch['offset']} has a malformed expanded target."
                            ) from exc
                        if declared_target_value != target_expanded_va:
                            raise PatcherError(
                                f"Expanded .shr rel32 relocation at {patch['offset']} has an inconsistent expanded target."
                            )
                    rel32 = target_expanded_va - (source_va + 5)
                    try:
                        after = rel32.to_bytes(4, "little", signed=True)
                    except OverflowError as exc:
                        raise PatcherError(
                            f"Expanded .shr rel32 relocation at {patch['offset']} is out of range."
                        ) from exc
                else:
                    raise PatcherError(
                        f"Internal expanded .shr relocation at {patch['offset']} has unknown kind {kind!r}."
                    )
            for write_offset in range(offset, offset + 4):
                prior_offset = occupied.get(write_offset)
                if prior_offset is not None:
                    raise PatcherError(
                        f"Expanded .shr relocation writes overlap at {patch['offset']} and {prior_offset}."
                    )
            for write_offset in range(offset, offset + 4):
                occupied[write_offset] = patch["offset"]
            planned.append(
                {
                    "feature": feature,
                    "patch": patch,
                    "offset": offset,
                    "before": actual,
                    "after": after,
                    "relocation_status": relocation_status,
                }
            )
    for item in planned:
        offset = item["offset"]
        data[offset : offset + 4] = item["after"]
    applied: list[dict[str, str]] = []
    for item in planned:
        feature = item["feature"]
        patch = item["patch"]
        record = {
            "offset": patch["offset"],
            "before": item["before"].hex().upper(),
            "after": item["after"].hex().upper(),
            "purpose": patch.get(
                "purpose",
                "relocate fun-patch .shr pointer for expanded 256 mode",
            ),
            "owner": f"feature:{feature.id}",
            "virtual_address": _virtual_address_for_offset(bytes(data), item["offset"]),
        }
        if item["relocation_status"] is not None:
            record["relocation_status"] = item["relocation_status"]
        applied.append(record)
    return applied


def _apply_vv5_task9_post_relocation_hook(
    data: bytearray,
    build: Build,
    patch_mode: str,
    fun_patches: list[FunPatch],
) -> list[dict[str, str]]:
    """Bind the one Task9 cross-section hook omitted by frozen C342.

    This exact Task9-owned guard intentionally runs only after the immutable
    66-row relocation pass. It does not add, remove, or reinterpret a C342
    row and is a stock-mode no-op.
    """
    if build.id != "vv5" or patch_mode not in EXPANDED_PATCH_MODES:
        return []
    owners = [
        feature
        for feature in fun_patches
        if feature.id == "vv5_enable_origins_exclusive_features"
        and "task9_expanded_post_relocation_patches" in feature.raw
    ]
    if not owners:
        return []
    if len(owners) != 1:
        raise PatcherError("VV5 Task9 post-relocation hook owner is not unique.")
    rows_by_mode = owners[0].raw.get("task9_expanded_post_relocation_patches")
    if not isinstance(rows_by_mode, dict) or set(rows_by_mode) != EXPANDED_PATCH_MODES:
        raise PatcherError("VV5 Task9 post-relocation hook modes drifted.")
    rows = rows_by_mode.get(patch_mode)
    if rows != [VV5_TASK9_EXPANDED_HOOK]:
        raise PatcherError("VV5 Task9 post-relocation hook row drifted.")
    offset = int(VV5_TASK9_EXPANDED_HOOK["offset"], 0)
    before = bytes.fromhex(VV5_TASK9_EXPANDED_HOOK["before"])
    after = bytes.fromhex(VV5_TASK9_EXPANDED_HOOK["after"])
    actual = bytes(data[offset : offset + len(before)])
    if actual != before:
        raise PatcherError(
            "VV5 Task9 Expanded post-relocation hook guard failed at 0x415F0: "
            f"expected {before.hex().upper()}, found {actual.hex().upper()}"
        )
    data[offset : offset + len(after)] = after
    return [
        {
            "offset": VV5_TASK9_EXPANDED_HOOK["offset"],
            "before": before.hex().upper(),
            "after": after.hex().upper(),
            "purpose": VV5_TASK9_EXPANDED_HOOK["purpose"],
            "owner": "feature:vv5_enable_origins_exclusive_features",
            "virtual_address": _virtual_address_for_offset(bytes(data), offset),
            "relocation_status": "task9_post_relocation_hook",
        }
    ]


def _validate_expanded_manifest_identity(
    build: Build,
    game: dict[str, Any],
) -> None:
    expected = EXPANDED_MANIFEST_IDENTITIES.get(build.id)
    if expected is None:
        raise PatcherError(f"Expanded-256 manifest has no exact identity for {build.id}.")
    if build.sha256 != expected["source_sha256"] or game.get("source_sha256") != expected["source_sha256"]:
        raise PatcherError(
            f"Expanded-256 manifest source fingerprint is not the exact {build.id} build."
        )
    if game.get("prototype_sha256") != expected["prototype_sha256"]:
        raise PatcherError(
            f"Expanded-256 {build.id} prototype fingerprint drifted."
        )
    patches = game.get("patches")
    if not isinstance(patches, list) or game.get("patch_count") != expected["patch_count"]:
        raise PatcherError(
            f"Expanded-256 {build.id} manifest patch count drifted."
        )
    if len(patches) != expected["patch_count"]:
        raise PatcherError(
            f"Expanded-256 {build.id} manifest is incomplete."
        )
    offsets: set[int] = set()
    for patch in patches:
        if not isinstance(patch, dict):
            raise PatcherError(f"Expanded-256 {build.id} manifest row is malformed.")
        offset_text = patch.get("offset")
        try:
            offset = int(offset_text, 0)
            before = bytes.fromhex(str(patch["before"]))
            after = bytes.fromhex(str(patch["after"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise PatcherError(
                f"Expanded-256 {build.id} manifest row is malformed."
            ) from exc
        if not isinstance(offset_text, str) or offset in offsets:
            raise PatcherError(
                f"Expanded-256 {build.id} manifest contains duplicate or malformed offsets."
            )
        if offset < 0 or not before or len(before) != len(after) or offset + len(before) > build.size:
            raise PatcherError(
                f"Expanded-256 {build.id} manifest row bounds or lengths are invalid."
            )
        offsets.add(offset)
    actual_digest = _relocation_ledger_sha256(patches)
    if actual_digest != expected["patches_sha256"]:
        raise PatcherError(
            f"Expanded-256 {build.id} manifest row identity drifted."
        )


def _expanded_patches(build: Build, variant: dict[str, Any]) -> list[dict[str, str]]:
    if not variant.get("expanded_records", False):
        return []
    payload = json.loads(EXPANDED_MANIFEST_PATH.read_text(encoding="utf-8"))
    try:
        game = payload["games"][build.id]
    except KeyError as exc:
        raise PatcherError(
            f"Experimental 256 data is missing for {build.title}."
        ) from exc
    _validate_expanded_manifest_identity(build, game)
    if build.id == "vv4":
        _validate_vv4_expanded_contract(game)
    return game["patches"]


def _safety_patches(build: Build, patch_mode: str) -> list[dict[str, str]]:
    if patch_mode == "stock":
        return []
    if (
        patch_mode
        not in {
            "experimental_expanded_256",
            "experimental_expanded_256_progression",
        }
        or build.id in {"vv1", "vv2"}
    ):
        return build.safety_patches
    patches = []
    for source in build.safety_patches:
        patch = dict(source)
        patch["after"] = patch["after"].replace("96000000", "00010000")
        patch["purpose"] = patch["purpose"].replace("150-slot", "256-slot")
        patches.append(patch)
    return patches


def _apply_vv3_expanded_healer_endpoint_repair(
    data: bytearray,
    build: Build,
    patch_mode: str,
) -> list[dict[str, str]]:
    if build.id != "vv3" or patch_mode not in EXPANDED_PATCH_MODES:
        return []
    patch = VV3_EXPANDED_HEALER_ENDPOINT_REPAIR
    offset = int(patch["offset"], 0)
    before = bytes.fromhex(patch["before"])
    after = bytes.fromhex(patch["after"])
    actual = bytes(data[offset : offset + len(before)])
    if actual != before:
        raise PatcherError(
            "VV3 Expanded healer endpoint repair guard failed at 0x5FA46: "
            f"expected {before.hex().upper()}, found {actual.hex().upper()}"
        )
    data[offset : offset + len(after)] = after
    return [{
        "offset": patch["offset"],
        "before": patch["before"],
        "after": patch["after"],
        "purpose": patch["purpose"],
        "owner": "automatic:vv3-expanded-healer-endpoint",
        "virtual_address": _virtual_address_for_offset(bytes(data), offset),
    }]


def _apply_vv3_expanded_capacity_corrections(
    data: bytearray,
    build: Build,
    patch_mode: str,
) -> list[dict[str, str]]:
    if build.id != "vv3" or patch_mode not in EXPANDED_PATCH_MODES:
        return []
    checked: list[tuple[dict[str, str], int, bytes, bytes]] = []
    for patch in VV3_EXPANDED_CAPACITY_CORRECTIONS:
        offset = int(patch["offset"], 0)
        before = bytes.fromhex(patch["before"])
        after = bytes.fromhex(patch["after"])
        actual = bytes(data[offset : offset + len(before)])
        if actual != before:
            raise PatcherError(
                "VV3 Expanded capacity correction guard failed at "
                f"{patch['offset']}: expected {before.hex().upper()}, "
                f"found {actual.hex().upper()}"
            )
        checked.append((patch, offset, before, after))
    records = []
    for patch, offset, before, after in checked:
        data[offset : offset + len(after)] = after
        records.append({
            "offset": patch["offset"],
            "before": patch["before"],
            "after": patch["after"],
            "purpose": patch["purpose"],
            "owner": "automatic:vv3-expanded-capacity-corrections",
            "virtual_address": _virtual_address_for_offset(bytes(data), offset),
        })
    return records


def _apply_vv3_expanded_chief_candidate_assignment_repair(
    data: bytearray,
    build: Build,
    patch_mode: str,
) -> list[dict[str, str]]:
    """Undo the one invalid manager-relative relocation in the VV3 manifest.

    The immutable prototype manifest widens the surrounding stack frame but
    incorrectly relocates the displacement in ``mov [ecx+esi+disp32], al``.
    That instruction is record-relative: ESI is record minus 0x14 and the
    native 0xE9C displacement therefore writes record+0xE88.  The manifest's
    0x1394 displacement instead writes record+0x1380.  Apply this final,
    guarded overlay only after the Expanded manifest has produced the known
    broken preimage.
    """
    if build.id != "vv3" or patch_mode not in EXPANDED_PATCH_MODES:
        return []
    patch = VV3_EXPANDED_CHIEF_CANDIDATE_ASSIGNMENT_REPAIR
    offset = int(patch["offset"], 0)
    before = bytes.fromhex(patch["before"])
    after = bytes.fromhex(patch["after"])
    actual = bytes(data[offset : offset + len(before)])
    if actual != before:
        raise PatcherError(
            "VV3 Expanded Chief-candidate assignment repair guard failed at "
            f"{patch['offset']}: expected {before.hex().upper()}, "
            f"found {actual.hex().upper()}"
        )
    data[offset : offset + len(after)] = after
    return [{
        "offset": patch["offset"],
        "before": patch["before"],
        "after": patch["after"],
        "purpose": patch["purpose"],
        "owner": "automatic:vv3-expanded-chief-candidate-assignment",
        "virtual_address": _virtual_address_for_offset(bytes(data), offset),
    }]


def _apply_vv3_expanded_detail_roster_layout(
    data: bytearray,
    build: Build,
    patch_mode: str,
    selected_fun_ids: set[str],
) -> list[dict[str, str]]:
    """Move the VV3 Details UI tail behind all 256 roster entries.

    The complete native table is checked before the first byte is changed.  An
    Origins composition can replay two constructor stores after the native
    relocation, so those two copied operands join the same transaction only
    when the selected payload is present.
    """
    if build.id != "vv3" or patch_mode not in EXPANDED_PATCH_MODES:
        return []
    if (
        len(VV3_EXPANDED_DETAIL_ROSTER_DISPLACEMENTS) != 150
        or len({row[0] for row in VV3_EXPANDED_DETAIL_ROSTER_DISPLACEMENTS}) != 150
        or any(
            after - before != VV3_EXPANDED_DETAIL_ROSTER_DISPLACEMENT_DELTA
            for _, before, after in VV3_EXPANDED_DETAIL_ROSTER_DISPLACEMENTS
        )
    ):
        raise PatcherError("VV3 Expanded Details roster displacement table drifted.")

    writes: list[tuple[int, bytes, bytes, str]] = []
    class_size = VV3_EXPANDED_DETAIL_ROSTER_CLASS_SIZE
    writes.append((
        int(class_size["offset"], 0),
        bytes.fromhex(class_size["before"]),
        bytes.fromhex(class_size["after"]),
        "expand the VV3 Details-screen class for 256 roster entries",
    ))
    for offset, before_value, after_value in VV3_EXPANDED_DETAIL_ROSTER_DISPLACEMENTS:
        writes.append((
            offset,
            before_value.to_bytes(4, "little"),
            after_value.to_bytes(4, "little"),
            "move a VV3 Details-screen UI-tail field behind the 256-entry roster",
        ))

    selected_origins = VV3_EXPANDED_DETAIL_ORIGINS_FEATURE_IDS.intersection(
        selected_fun_ids
    )
    replay_state = []
    for offset, before_value, after_value in VV3_EXPANDED_DETAIL_ORIGINS_REPLAY_DISPLACEMENTS:
        before = before_value.to_bytes(4, "little")
        after = after_value.to_bytes(4, "little")
        replay_state.append((offset, before, after, bytes(data[offset : offset + 4])))
    replay_is_present = all(actual == before for _, before, _, actual in replay_state)
    replay_is_absent = all(actual == b"\0\0\0\0" for _, _, _, actual in replay_state)
    if selected_origins:
        if not replay_is_present:
            found = ", ".join(
                f"0x{offset:X}={actual.hex().upper()}"
                for offset, _, _, actual in replay_state
            )
            raise PatcherError(
                "VV3 Expanded Origins Details replay guard failed: " + found
            )
        for offset, before, after, _ in replay_state:
            writes.append((
                offset,
                before,
                after,
                "move an Origins-replayed Details constructor field behind the expanded roster",
            ))
    elif not replay_is_absent:
        found = ", ".join(
            f"0x{offset:X}={actual.hex().upper()}"
            for offset, _, _, actual in replay_state
        )
        raise PatcherError(
            "VV3 Expanded Details found an unowned Origins replay payload: " + found
        )

    # The Details roster loop itself is already widened by the immutable base
    # Expanded manifest.  This final overlay only repairs the surrounding class
    # layout and must never change that loop bound.
    if bytes(data[0x6E2C2:0x6E2C6]) != bytes.fromhex("00010000"):
        raise PatcherError("VV3 Expanded Details roster bound is not 256.")

    for offset, before, _, _ in writes:
        actual = bytes(data[offset : offset + len(before)])
        if actual != before:
            raise PatcherError(
                "VV3 Expanded Details roster layout guard failed at "
                f"0x{offset:X}: expected {before.hex().upper()}, "
                f"found {actual.hex().upper()}"
            )

    owner = "automatic:vv3-expanded-detail-roster-layout"
    records: list[dict[str, str]] = []
    for offset, before, after, purpose in writes:
        data[offset : offset + len(after)] = after
        records.append({
            "offset": f"0x{offset:X}",
            "before": before.hex().upper(),
            "after": after.hex().upper(),
            "purpose": purpose,
            "owner": owner,
            "virtual_address": _virtual_address_for_offset(bytes(data), offset),
        })
    return records


def get_fun_patch(patch_id: str) -> FunPatch:
    for patch in load_fun_patches():
        if patch.id == patch_id:
            return patch
    raise PatcherError(f"Unknown fun patch: {patch_id}")


def _selected_fun_patches(
    build: Build, patch_ids: tuple[str, ...] | list[str]
) -> list[FunPatch]:
    ordered_ids = resolve_fun_patch_ids(patch_ids, game_id=build.id)
    by_id = {
        patch.id: patch
        for patch in load_fun_patches()
    }
    return [by_id[patch_id] for patch_id in ordered_ids]


def _validate_expanded_time_warp_selection(
    build: Build,
    feature: FunPatch,
    selected_ids: set[str],
    patch_mode: str,
) -> None:
    """Keep both reviewed Time Warp records out of every stock composition."""

    expected_id = EXPANDED_TIME_WARP_IDS.get(build.id)
    if expected_id is None or feature.id != expected_id:
        raise PatcherError("Expanded Time Warp feature/game identity mismatch.")
    if patch_mode not in EXPANDED_PATCH_MODES:
        raise PatcherError(
            f"{build.title} Time Warp is available only in experimental Expanded-256; "
            "stock modes are byte-frozen."
        )
    if feature.raw.get("supported_modes") != [
        "experimental_expanded_256",
        "experimental_expanded_256_progression",
    ]:
        raise PatcherError("Expanded Time Warp supported-mode metadata drifted.")
    if build.id == "vv3":
        conflicts = set(feature.raw.get("conflicts", ()))
        selected_conflicts = conflicts & selected_ids
        if selected_conflicts:
            raise PatcherError(
                "VV3 standalone Expanded Time Warp conflicts with the Origins/Running "
                "core: " + ", ".join(sorted(selected_conflicts))
            )
    elif build.id == "vv4":
        conflicts = set(feature.raw.get("conflicts", ()))
        selected_conflicts = conflicts & selected_ids
        if selected_conflicts:
            raise PatcherError(
                "VV4 standalone Expanded Time Warp conflicts with full Origins/Full "
                "Mastery: " + ", ".join(sorted(selected_conflicts))
            )
    elif (
        feature.raw.get("dependencies") != ["vv5_enable_origins_exclusive_features"]
        or "vv5_enable_origins_exclusive_features" not in selected_ids
    ):
        raise PatcherError(
            "VV5 Expanded Time Warp requires the exact Task9 native-actions page."
        )


def _selected_playtest_disabled_fun_patches(
    build: Build,
    feature_ids: tuple[str, ...] | list[str],
    patch_mode: str,
) -> list[FunPatch]:
    """Resolve an explicitly requested Origins feature for a separate stress test.

    This path is deliberately separate from ordinary catalog composition.  It
    is limited to the exact VV2 Origins record or the one game-matched
    Expanded Time Warp record requested for the current stress test. The
    authenticated catalog record remains unchanged; only returned copies
    receive playtest metadata.
    """
    requested = tuple(feature_ids)
    if not requested:
        return []
    time_warp_ids = frozenset(EXPANDED_TIME_WARP_IDS.values())
    if len(requested) == 1 and requested[0] in time_warp_ids:
        expected = EXPANDED_TIME_WARP_IDS.get(build.id)
        if requested[0] != expected:
            raise PatcherError(
                "Expanded Time Warp playtest feature must match the identified source game."
            )
        if patch_mode not in EXPANDED_PATCH_MODES:
            raise PatcherError(
                "Expanded Time Warp playtests require an experimental Expanded-256 mode."
            )
        authenticated = next(
            (
                record
                for record in _certified_expanded_time_warp_records()
                if record.get("id") == expected
            ),
            None,
        )
        if authenticated is None:
            raise PatcherError(
                f"Authenticated {build.id.upper()} Expanded Time Warp record is unavailable."
            )
        enriched = dict(authenticated)
        enriched["playtest_only"] = True
        enriched["playtest_status"] = (
            "runtime/player stress test; not catalog/publication evidence"
        )
        return [FunPatch(enriched)]
    if build.id != "vv2" or requested != (VV2_PLAYTEST_DISABLED_FEATURE_ID,):
        raise PatcherError(
            "Only the VV2 Origins feature or one game-matched Expanded "
            "Time Warp feature may be selected for a playtest."
        )
    try:
        raw = json.loads(VV2_PLAYTEST_DISABLED_FEATURE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PatcherError("VV2 Origins playtest feature manifest is unavailable.") from exc
    if (
        raw.get("id") != VV2_PLAYTEST_DISABLED_FEATURE_ID
        or raw.get("game_id") != "vv2"
        or raw.get("enabled") is not True
        or raw.get("catalog_hidden") is not False
        or raw.get("catalog_enabled") is not True
    ):
        raise PatcherError(
            "VV2 Origins playtest feature must remain enabled and catalog-visible."
        )
    patches = raw.get("patches")
    if not isinstance(patches, list) or not patches:
        raise PatcherError("VV2 Origins playtest feature has no patch rows.")
    for patch in patches:
        if not isinstance(patch, dict) or not patch.get("purpose"):
            raise PatcherError("VV2 Origins playtest feature has malformed patch metadata.")
        before = _patch_bytes(patch, "before")
        after = _patch_bytes(patch, "after")
        if len(before) != len(after):
            raise PatcherError("VV2 Origins playtest feature has mismatched patch lengths.")
    enriched = dict(raw)
    enriched["playtest_only"] = True
    enriched["playtest_status"] = "runtime/player stress test; not catalog/publication evidence"
    return [FunPatch(enriched)]


def _output_name(build: Build, patch_mode: str, fun_patches: list[FunPatch]) -> str:
    get_patch_variant(build, patch_mode)
    suffix = "Modded 256" if patch_mode in EXPANDED_PATCH_MODES else "Modded"
    if any(patch.raw.get("playtest_only") is True for patch in fun_patches):
        suffix += " Playtest"
    return f"{build.title} - {suffix}.exe"


def output_folder_for(
    source: Path,
    build: Build,
    patch_mode: str,
    fun_patches: list[FunPatch],
    output_root: Path | None = None,
) -> Path:
    parent = (
        Path(output_root).expanduser().resolve()
        if output_root is not None
        else source.resolve().parent.parent
    )
    suffix = "Modded 256" if patch_mode in EXPANDED_PATCH_MODES else "Modded"
    if any(patch.raw.get("playtest_only") is True for patch in fun_patches):
        suffix += " Playtest"
    return parent / f"{build.title} - {suffix}"


def _ldw_save_roots(save_root: Path | None = None) -> list[Path]:
    if save_root is not None:
        # An explicit root is authoritative.  Falling through to a user's
        # real Documents/OneDrive roots would make diagnostics and copy tests
        # inspect an unrelated save set.
        return [Path(save_root).expanduser().resolve()]
    candidates: list[Path] = []
    override = os.environ.get("VVFP_LDW_SAVE_ROOT")
    if override:
        candidates.append(Path(override).expanduser())
    for variable in ("OneDrive", "OneDriveConsumer"):
        value = os.environ.get(variable)
        if value:
            candidates.append(Path(value) / "Documents" / "LDW")
    candidates.extend(
        (
            Path.home() / "OneDrive" / "Documents" / "LDW",
            Path.home() / "Documents" / "LDW",
        )
    )
    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = os.path.normcase(str(candidate.resolve()))
        if key not in seen:
            seen.add(key)
            unique.append(candidate.resolve())
    return unique


def vanilla_save_folder_for(
    build: Build, save_root: Path | None = None
) -> Path | None:
    slot_zero = f"{build.title}0.ldw"
    for root in _ldw_save_roots(save_root):
        folder = root / build.title
        if (folder / slot_zero).is_file():
            return folder
    return None


def _save_folder_has_slot_zero(folder: Path, build: Build) -> bool:
    return (folder / f"{build.title}0.ldw").is_file()


def _existing_modded_save_folder_for(
    build: Build, save_root: Path | None = None
) -> Path | None:
    """Find an already-created expanded save folder when stock saves are absent."""
    for root in _ldw_save_roots(save_root):
        folder = root / f"{build.title} - Modded 256"
        if _save_folder_has_slot_zero(folder, build):
            return folder
    return None


def modded_save_folder_for(
    build: Build, patch_mode: str, save_root: Path | None = None
) -> Path | None:
    if patch_mode not in EXPANDED_PATCH_MODES:
        return None
    source = vanilla_save_folder_for(build, save_root)
    if source is not None:
        return source.parent / f"{build.title} - Modded 256"
    return _existing_modded_save_folder_for(build, save_root)


def expanded_save_status(
    build: Build, patch_mode: str, save_root: Path | None = None
) -> dict[str, Any]:
    """Describe which save source is available for an expanded build.

    A slot-zero file is the minimum loader requirement.  This is deliberately
    read-only: it never creates, moves, or rewrites a save folder.
    """
    if patch_mode not in EXPANDED_PATCH_MODES:
        return {"status": "not_requested"}
    vanilla = vanilla_save_folder_for(build, save_root)
    if vanilla is not None:
        return {
            "status": "vanilla_ready",
            "folder": str(vanilla),
            "slot_zero": f"{build.title}0.ldw",
        }
    modded = _existing_modded_save_folder_for(build, save_root)
    if modded is not None:
        return {
            "status": "modded_ready",
            "folder": str(modded),
            "slot_zero": f"{build.title}0.ldw",
        }
    roots = _ldw_save_roots(save_root)
    expected = (
        str(roots[0] / f"{build.title} - Modded 256")
        if roots
        else None
    )
    return {
        "status": "no_valid_save",
        "expected_modded_folder": expected,
        "slot_zero": f"{build.title}0.ldw",
    }


def suggested_modded_save_folder(
    build: Build, patch_mode: str, save_root: Path | None = None
) -> Path | None:
    """Return the save-folder path the expanded executable will use.

    Unlike ``modded_save_folder_for``, this also returns a useful path when no
    vanilla slot-zero file exists yet, so the GUI can tell the player where to
    copy saves after the first launch.
    """
    if patch_mode not in EXPANDED_PATCH_MODES:
        return None
    existing = modded_save_folder_for(build, patch_mode, save_root)
    if existing is not None:
        return existing
    roots = _ldw_save_roots(save_root)
    if not roots:
        return None
    return roots[0] / f"{build.title} - Modded 256"


def copy_vanilla_saves(
    build: Build,
    patch_mode: str,
    *,
    replace_existing: bool = False,
    save_root: Path | None = None,
) -> dict[str, Any]:
    if patch_mode not in EXPANDED_PATCH_MODES:
        return {"status": "not_requested", "copied_files": 0}
    source = vanilla_save_folder_for(build, save_root)
    if source is None:
        return {"status": "vanilla_save_folder_not_found", "copied_files": 0}
    destination = source.parent / f"{build.title} - Modded 256"
    source_files = sorted(
        path
        for path in source.glob(f"{build.title}*.ldw")
        if path.is_file()
    )
    slot_zero_name = f"{build.title}0.ldw"
    if not any(path.name == slot_zero_name for path in source_files):
        raise PatcherError(
            f"Required vanilla slot-zero file is missing: {source / slot_zero_name}"
        )
    existing = (
        sorted(
            path
            for path in destination.glob(f"{build.title}*.ldw")
            if path.is_file()
        )
        if destination.is_dir()
        else []
    )
    if existing and not replace_existing:
        return {
            "status": "existing_modded_saves_preserved",
            "source_folder": str(source),
            "destination_folder": str(destination),
            "copied_files": 0,
            "slot_zero": slot_zero_name,
        }
    destination.mkdir(parents=True, exist_ok=True)
    if replace_existing:
        for path in existing:
            path.unlink()
    copied: list[dict[str, Any]] = []
    for source_path in source_files:
        destination_path = destination / source_path.name
        shutil.copy2(source_path, destination_path)
        source_hash = sha256(source_path)
        if sha256(destination_path) != source_hash:
            raise PatcherError(
                f"Save copy verification failed: {destination_path}"
            )
        copied.append(
            {
                "name": source_path.name,
                "size": source_path.stat().st_size,
                "sha256": source_hash,
            }
        )
    return {
        "status": "vanilla_saves_copied",
        "source_folder": str(source),
        "destination_folder": str(destination),
        "copied_files": len(copied),
        "slot_zero": slot_zero_name,
        "files": copied,
    }


def get_patch_mode(patch_mode: str) -> PatchMode:
    for mode in load_patch_modes():
        if mode.id == patch_mode:
            return mode
    raise PatcherError(f"Unknown patch mode: {patch_mode}")


def get_patch_variant(build: Build, patch_mode: str) -> dict[str, Any]:
    get_patch_mode(patch_mode)
    try:
        return build.variants[patch_mode]
    except KeyError as exc:
        raise PatcherError(f"{build.title} does not define patch mode {patch_mode}") from exc


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def identify(path: Path) -> Build:
    path = path.resolve()
    if not path.is_file():
        raise PatcherError(f"Game executable not found: {path}")
    size = path.stat().st_size
    candidates = [build for build in load_builds() if build.size == size]
    if not candidates:
        raise PatcherError(f"Unsupported executable size: {size:,} bytes")
    digest = sha256(path)
    for build in candidates:
        if digest == build.sha256:
            return build
    raise PatcherError(
        "This executable is not one of the five exact supported stock builds. "
        + f"SHA-256: {digest}"
    )


def _resolve_expected_source(selected: Path, expected: Build) -> Path:
    selected = Path(selected).resolve()
    if selected.is_dir():
        source = selected / expected.input_name
        if not source.is_file():
            raise PatcherError(
                f"{expected.title} folder does not contain {expected.input_name}: {selected}"
            )
        return source.resolve()
    return selected


def validate_all_sources(sources: dict[str, Path]) -> list[tuple[Build, Path]]:
    builds = load_builds()
    missing = [
        build.title
        for build in builds
        if build.id not in sources or not str(sources[build.id]).strip()
    ]
    if missing:
        raise PatcherError(
            "Choose all five original game folders. Missing: " + ", ".join(missing)
        )
    resolved: list[tuple[Build, Path]] = []
    used_paths: set[Path] = set()
    for expected in builds:
        source = _resolve_expected_source(Path(sources[expected.id]), expected)
        actual = identify(source)
        if actual.id != expected.id:
            raise PatcherError(
                f"Wrong game selected for {expected.title}: identified {actual.title}"
            )
        if source in used_paths:
            raise PatcherError(f"The same executable was selected more than once: {source}")
        used_paths.add(source)
        resolved.append((expected, source))
    return resolved


def _pe_checksum_layout(data: bytearray) -> tuple[int, int]:
    if data[:2] != b"MZ":
        raise PatcherError("Input is not a Windows PE executable (missing MZ header).")
    pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe_offset : pe_offset + 4] != b"PE\0\0":
        raise PatcherError("Input is not a Windows PE executable (missing PE header).")
    optional_offset = pe_offset + 24
    magic = struct.unpack_from("<H", data, optional_offset)[0]
    if magic not in (0x10B, 0x20B):
        raise PatcherError(f"Unsupported PE optional-header magic: 0x{magic:04X}")
    return optional_offset + 64, len(data)


def pe_checksum(data: bytearray) -> int:
    checksum_offset, length = _pe_checksum_layout(data)
    struct.pack_into("<I", data, checksum_offset, 0)
    total = 0
    padded = data + (b"\0" if len(data) % 2 else b"")
    for offset in range(0, len(padded), 2):
        total += padded[offset] | (padded[offset + 1] << 8)
        total = (total & 0xFFFF) + (total >> 16)
    total = (total & 0xFFFF) + (total >> 16)
    return ((total & 0xFFFF) + length) & 0xFFFFFFFF


def _virtual_address_for_offset(data: bytes, file_offset: int) -> str | None:
    """Map a raw file offset to a PE VA when the offset is in a section."""
    try:
        pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
        if data[pe_offset : pe_offset + 4] != b"PE\0\0":
            return None
        coff = pe_offset + 4
        section_count = struct.unpack_from("<H", data, coff + 2)[0]
        optional_size = struct.unpack_from("<H", data, coff + 16)[0]
        optional = coff + 20
        magic = struct.unpack_from("<H", data, optional)[0]
        image_base = (
            struct.unpack_from("<I", data, optional + 28)[0]
            if magic == 0x10B
            else struct.unpack_from("<Q", data, optional + 24)[0]
        )
        section_base = optional + optional_size
        for index in range(section_count):
            section = section_base + index * 40
            virtual_address, raw_size, raw_pointer = struct.unpack_from(
                "<III", data, section + 12
            )
            if raw_pointer <= file_offset < raw_pointer + raw_size:
                return f"0x{image_base + virtual_address + file_offset - raw_pointer:X}"
    except (IndexError, struct.error, ValueError):
        return None
    return None


def _vv4_full_heal_overlay_allowed(
    *,
    feature: FunPatch,
    current_owner: str,
    prior_owner: str,
    prior_start: int,
    prior_end: int,
    patch_mode: str,
    offset: int,
    before: bytes,
    composed_sha256: str,
) -> bool:
    """Allow only the certified Full Mastery -> Full Heal hook overlay.

    Every value involved is passed explicitly from the current overlap pair;
    no loop-carried owner or stale preimage is consulted.  The complete
    pre-Running composition hash is checked against the in-memory bytes at the
    moment the overlay is requested, so unrelated later patches do not affect
    this decision while an earlier mutation cannot be hidden.
    """
    if current_owner != f"feature:{VV4_FULL_HEAL_CANDIDATE_ID}":
        return False
    if prior_owner not in {
        "feature:vv4_enable_origins_exclusive_features",
        "feature:vv4_full_mastery_all_stage_a_candidate",
    }:
        return False
    if patch_mode not in {"collection_progression", "immediate_fixed"}:
        return False
    if offset != 0x8960F or not (prior_start <= offset < prior_end):
        return False
    if before != bytes.fromhex("E941FEFFFF"):
        return False
    dependencies = feature.raw.get("dependencies")
    if dependencies != list(VV4_FULL_HEAL_PARENT_DEPENDENCIES):
        return False
    source = feature.raw.get("source", {})
    if source.get("parent_collection_sha256") != VV4_FULL_HEAL_PARENT_COLLECTION_SHA256:
        return False
    if source.get("parent_immediate_sha256") != VV4_FULL_HEAL_PARENT_IMMEDIATE_SHA256:
        return False
    expected = {
        "collection_progression": VV4_FULL_HEAL_PARENT_COLLECTION_SHA256,
        "immediate_fixed": VV4_FULL_HEAL_PARENT_IMMEDIATE_SHA256,
    }[patch_mode]
    return composed_sha256.upper() == expected


def _expanded_static_repair_integration() -> dict[str, Any]:
    """Load the closed, fail-closed contract for real Expanded render repairs."""
    try:
        source = EXPANDED_STATIC_REPAIR_INTEGRATION_PATH.read_bytes()
        if source_text_sha256(source) != EXPANDED_STATIC_REPAIR_INTEGRATION_SHA256:
            raise PatcherError("Expanded static-repair integration source hash mismatch.")
        payload = json.loads(source.decode("utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PatcherError("Expanded static-repair integration contract is unavailable.") from exc
    if set(payload) != {
        "schema", "status", "native_output", "runtime_go", "player_go",
        "publication_ready", "games",
    }:
        raise PatcherError("Expanded static-repair integration contract is not closed.")
    if (
        payload.get("schema") != "vvfp.expanded_256_static_repair_integration.v1"
        or payload.get("status") != "active_in_expanded_render_runtime_stop"
        or payload.get("native_output") is not True
        or payload.get("runtime_go") is not False
        or payload.get("player_go") is not False
        or payload.get("publication_ready") is not False
    ):
        raise PatcherError("Expanded static-repair integration gates are not exact.")
    games = payload.get("games")
    if not isinstance(games, dict) or set(games) != {"vv3", "vv4", "vv5"}:
        raise PatcherError("Expanded static-repair integration game set is not exact.")
    expected_paths = {
        "vv3": "data/candidates/vv3_full256_serializer_candidate.json",
        "vv4": "data/candidates/vv4_full256_serializer_static_candidate.json",
        "vv5": "data/candidates/vv5_post_prototype_overlay.json",
    }
    expected_stages = {
        "vv3": "post_feature_relocation",
        "vv4": "post_manifest",
        "vv5": "post_manifest",
    }
    expected_repair_ids = {
        "vv3": "vv3_full256_serializer_reader_gate",
        "vv4": "vv4_full256_serializer_reader_gate",
        "vv5": "vv5_post_prototype_operand_overlay",
    }
    expected_features = {
        "vv3": [
            "vv3_enable_origins_exclusive_features_running_candidate",
            "vv3_all_villagers_like_running_candidate",
        ],
        "vv4": [],
        "vv5": [],
    }
    for game_id, game in games.items():
        exact_fields = {
            "repair_id", "stage", "candidate_path", "candidate_source_text_sha256",
            "stock_sha256", "manifest_rows_sha256", "required_feature_ids", "modes",
        }
        if game_id == "vv4":
            exact_fields.add("helper_lineage")
        if not isinstance(game, dict) or set(game) != exact_fields:
            raise PatcherError(f"{game_id} static-repair integration record is not closed.")
        if game.get("candidate_path") != expected_paths[game_id]:
            raise PatcherError(f"{game_id} static-repair candidate path is not exact.")
        if game.get("repair_id") != expected_repair_ids[game_id]:
            raise PatcherError(f"{game_id} static-repair ID is not exact.")
        if game.get("stage") != expected_stages[game_id]:
            raise PatcherError(f"{game_id} static-repair stage is not exact.")
        if game.get("required_feature_ids") != expected_features[game_id]:
            raise PatcherError(f"{game_id} static-repair feature binding is not exact.")
        if game.get("stock_sha256") != EXPANDED_MANIFEST_IDENTITIES[game_id]["source_sha256"]:
            raise PatcherError(f"{game_id} static-repair stock binding is stale.")
        if game.get("manifest_rows_sha256") != EXPANDED_MANIFEST_IDENTITIES[game_id]["patches_sha256"]:
            raise PatcherError(f"{game_id} static-repair manifest binding is stale.")
        modes = game.get("modes")
        if not isinstance(modes, dict) or set(modes) != EXPANDED_PATCH_MODES:
            raise PatcherError(f"{game_id} static-repair mode set is not exact.")
        candidate_path = (ROOT / game["candidate_path"]).resolve()
        try:
            candidate_path.relative_to(ROOT.resolve())
        except ValueError as exc:
            raise PatcherError(f"{game_id} static-repair candidate escapes the workspace.") from exc
        try:
            candidate_bytes = candidate_path.read_bytes()
        except OSError as exc:
            raise PatcherError(f"{game_id} static-repair candidate is unavailable.") from exc
        if source_text_sha256(candidate_bytes) != game.get("candidate_source_text_sha256"):
            raise PatcherError(f"{game_id} static-repair candidate source hash mismatch.")
        if game_id == "vv4":
            helper = game.get("helper_lineage")
            if not isinstance(helper, dict) or set(helper) != {
                "id", "raw_start", "raw_end", "stock_sha256",
                "current_parent_sha256", "manifest_row_raw", "manifest_before",
                "manifest_after", "abi_control_flow_unchanged",
            }:
                raise PatcherError("VV4 static-repair helper lineage is not closed.")
            if (
                helper.get("id") != "singleton"
                or helper.get("raw_start") != "0x1FE70"
                or helper.get("raw_end") != "0x1FEEA"
                or helper.get("manifest_row_raw") != "0x1FE9B"
                or helper.get("manifest_before") != "C8710100"
                or helper.get("manifest_after") != "70DD0100"
                or helper.get("abi_control_flow_unchanged") is not True
            ):
                raise PatcherError("VV4 static-repair helper lineage is not exact.")
        for mode_id, mode in modes.items():
            allowed = {
                "parent_size", "parent_sha256", "parent_checksum",
                "result_size", "result_sha256", "result_checksum",
            }
            if game_id in {"vv4", "vv5"}:
                allowed.update({"final_no_fun_sha256", "final_no_fun_checksum"})
            if not isinstance(mode, dict) or set(mode) != allowed:
                raise PatcherError(
                    f"{game_id} {mode_id} static-repair identity record is not closed."
                )
            for key in ("parent_sha256", "result_sha256"):
                value = mode.get(key)
                if not isinstance(value, str) or len(value) != 64:
                    raise PatcherError(f"{game_id} {mode_id} {key} is malformed.")
            for key in ("parent_checksum", "result_checksum"):
                value = mode.get(key)
                if not isinstance(value, str) or len(value) != 8:
                    raise PatcherError(f"{game_id} {mode_id} {key} is malformed.")
    return payload


def _expanded_static_repair_candidate(game: dict[str, Any]) -> dict[str, Any]:
    try:
        return json.loads((ROOT / game["candidate_path"]).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PatcherError("Expanded static-repair candidate cannot be decoded.") from exc


def _canonicalize_pe_checksum(data: bytearray) -> tuple[int, bytes, bytes]:
    checksum_offset, _ = _pe_checksum_layout(data)
    before = bytes(data[checksum_offset : checksum_offset + 4])
    struct.pack_into("<I", data, checksum_offset, 0)
    struct.pack_into("<I", data, checksum_offset, pe_checksum(data))
    return checksum_offset, before, bytes(data[checksum_offset : checksum_offset + 4])


def _static_repair_page(candidate: dict[str, Any], game_id: str) -> bytes:
    if game_id == "vv3":
        section = candidate.get("section_plan", {})
        page_hash = section.get("section_sha256")
    else:
        section = candidate.get("section", {})
        page_hash = section.get("page_sha256")
    raw_start_value = section.get("raw_start", 0)
    raw_size_value = section.get("size", section.get("raw_size", 0))
    raw_start = int(raw_start_value, 0) if isinstance(raw_start_value, str) else int(raw_start_value)
    raw_size = int(raw_size_value, 0) if isinstance(raw_size_value, str) else int(raw_size_value)
    if raw_size != 0x1000:
        raise PatcherError(f"{game_id} static-repair page size is not 0x1000.")
    page = bytearray(raw_size)
    occupied: list[tuple[int, int]] = []
    routines = candidate.get("exact_routines")
    if not isinstance(routines, dict) or set(routines) != {
        "serializer", "deserializer", "serializer_failure_gate"
    }:
        raise PatcherError(f"{game_id} static-repair routine set is not exact.")
    for name, routine in routines.items():
        try:
            raw = int(routine["raw"], 0) if isinstance(routine["raw"], str) else int(routine["raw"])
            blob = bytes.fromhex(routine["bytes"])
            length = int(routine["length"])
        except (KeyError, TypeError, ValueError) as exc:
            raise PatcherError(f"{game_id} {name} routine metadata is malformed.") from exc
        start = raw - raw_start
        end = start + len(blob)
        if len(blob) != length or not (0 <= start < end <= raw_size):
            raise PatcherError(f"{game_id} {name} routine bounds are invalid.")
        if hashlib.sha256(blob).hexdigest().upper() != routine.get("sha256"):
            raise PatcherError(f"{game_id} {name} routine hash mismatch.")
        if any(start < prior_end and prior_start < end for prior_start, prior_end in occupied):
            raise PatcherError(f"{game_id} static-repair routines overlap.")
        occupied.append((start, end))
        page[start:end] = blob
    if hashlib.sha256(page).hexdigest().upper() != page_hash:
        raise PatcherError(f"{game_id} static-repair page hash mismatch.")
    return bytes(page)


def _apply_reviewed_expanded_static_repair(
    data: bytearray,
    build: Build,
    patch_mode: str,
    stage: str,
    selected_fun_ids: set[str],
) -> tuple[list[dict[str, str]], list[tuple[int, int, str]]]:
    """Apply one reviewed repair transaction only at its exact guarded stage."""
    if patch_mode not in EXPANDED_PATCH_MODES or build.id not in {"vv3", "vv4", "vv5"}:
        return [], []
    integration = _expanded_static_repair_integration()
    game = integration["games"][build.id]
    if game["stage"] != stage:
        return [], []
    required = set(game["required_feature_ids"])
    if required and not required.issubset(selected_fun_ids):
        return [], []
    candidate = _expanded_static_repair_candidate(game)
    if build.id == "vv3":
        decision = candidate.get("decision", {})
        if (
            candidate.get("enabled") is not False
            or candidate.get("catalog_visible") is not False
            or candidate.get("native_output") is not False
            or decision.get("runtime_go") is not False
            or decision.get("player_go") is not False
            or decision.get("publication_ready") is not False
        ):
            raise PatcherError("VV3 static-repair candidate gates are not fail-closed.")
    else:
        if (
            candidate.get("enabled") is not False
            or candidate.get("catalog_visible") is not False
            or candidate.get("native_output") is not False
            or candidate.get("runtime_go") is not False
            or candidate.get("player_go") is not False
            or (
                candidate.get(
                    "publication_ready",
                    candidate.get("publication_eligible"),
                )
                is not False
            )
        ):
            raise PatcherError(f"{build.id} static-repair candidate gates are not fail-closed.")
    if build.id == "vv5":
        ledger = candidate.get("bindings", {}).get("c342_relocation_ledger", {})
        if (
            ledger.get("count") != 66
            or ledger.get("rows_sha256") != VV5_ORIGINS_RELOCATION_LEDGER_SHA256
            or ledger.get("source_text_sha256")
            != "6AFF1A8E69234C61CB2D1878C46FA91B0AAA721FC5F29C5B42A678F61BAB8528"
        ):
            raise PatcherError("VV5 static-repair C342 binding mismatch.")
    if build.id == "vv4":
        helper = game["helper_lineage"]
        candidate_helper = candidate.get("d353_helpers", {}).get("singleton", {})
        if candidate_helper.get("sha256") != helper["stock_sha256"]:
            raise PatcherError("VV4 stock singleton helper evidence binding mismatch.")
    mode = game["modes"][patch_mode]
    work = bytearray(data)
    checksum_offset, checksum_before, checksum_parent = _canonicalize_pe_checksum(work)
    parent_sha256 = hashlib.sha256(work).hexdigest().upper()
    if len(work) != mode["parent_size"] or parent_sha256 != mode["parent_sha256"]:
        raise PatcherError(
            f"{build.id} static-repair parent guard failed: expected "
            f"{mode['parent_size']} / {mode['parent_sha256']}, found "
            f"{len(work)} / {parent_sha256}."
        )
    if checksum_parent.hex().upper() != mode["parent_checksum"]:
        raise PatcherError(f"{build.id} static-repair parent checksum mismatch.")
    if build.id == "vv4":
        helper = game["helper_lineage"]
        helper_start = int(helper["raw_start"], 0)
        helper_end = int(helper["raw_end"], 0)
        helper_sha256 = hashlib.sha256(work[helper_start:helper_end]).hexdigest().upper()
        if helper_sha256 != helper["current_parent_sha256"]:
            raise PatcherError("VV4 current-parent singleton helper hash mismatch.")
        row_offset = int(helper["manifest_row_raw"], 0)
        if bytes(work[row_offset : row_offset + 4]).hex().upper() != helper["manifest_after"]:
            raise PatcherError("VV4 current-parent singleton manifest row mismatch.")
    writes: list[tuple[int, bytes, bytes, str]] = []
    append: bytes | None = None
    if build.id == "vv3":
        pe = candidate["pe_guards"]
        section = candidate["section_plan"]
        writes.extend(
            [
                (int(pe["section_count_raw"], 0), bytes.fromhex(pe["section_count_before"]), bytes.fromhex(pe["section_count_after"]), "add reviewed .vv3sv section count"),
                (int(pe["size_of_image_raw"], 0), bytes.fromhex(pe["size_of_image_before"]), bytes.fromhex(pe["size_of_image_after"]), "extend reviewed VV3 SizeOfImage"),
                (int(section["header_raw"], 0), bytes.fromhex(section["header_guard"]), bytes.fromhex(section["header_bytes"]), "add reviewed .vv3sv section header"),
            ]
        )
        for hook in candidate["hooks"]:
            writes.append((int(hook["raw"], 0), bytes.fromhex(hook["preimage"]), bytes.fromhex(hook["after"]), f"route VV3 {hook['id']} through reviewed static repair"))
        append = _static_repair_page(candidate, build.id)
    elif build.id == "vv4":
        pe = candidate["pe_guards"]
        section = candidate["section"]
        writes.extend(
            [
                (int(pe["section_count_offset"]), int(pe["section_count_before"]).to_bytes(2, "little"), int(pe["section_count_after"]).to_bytes(2, "little"), "add reviewed .vv4x section count"),
                (int(pe["size_of_image_offset"]), int(section["old_size_of_image"]).to_bytes(4, "little"), int(section["new_size_of_image"]).to_bytes(4, "little"), "extend reviewed VV4 SizeOfImage"),
                (int(section["header_raw"]), bytes.fromhex(section["header_guard"]), bytes.fromhex(section["final_header_bytes"]), "add reviewed .vv4x section header"),
            ]
        )
        for hook in candidate["hooks"]:
            writes.append((int(hook["raw"]), bytes.fromhex(hook["before"]), bytes.fromhex(hook["after"]), f"route VV4 {hook['name']} through reviewed static repair"))
        append = _static_repair_page(candidate, build.id)
    else:
        overlay = candidate.get("overlay", {})
        rows = overlay.get("rows")
        if not isinstance(rows, list) or len(rows) != 16 or overlay.get("row_count") != 16:
            raise PatcherError("VV5 static-repair overlay row count mismatch.")
        for row in rows:
            before = bytes.fromhex(row["before"])
            after = bytes.fromhex(row["after"])
            if len(before) != len(after) or len(before) != row.get("width"):
                raise PatcherError(f"VV5 static-repair row {row.get('id')} width mismatch.")
            writes.append((int(row["write_raw"], 0), before, after, f"apply reviewed VV5 {row['id']} operand repair"))
    owner = f"automatic:expanded-static-repair:{game['repair_id']}"
    occupied: list[tuple[int, int, str]] = []
    records: list[dict[str, str]] = []
    if checksum_before != checksum_parent:
        records.append(
            {
                "offset": f"0x{checksum_offset:X}",
                "before": checksum_before.hex().upper(),
                "after": checksum_parent.hex().upper(),
                "purpose": f"canonicalize {build.id} static-repair parent checksum",
                "owner": owner,
                "virtual_address": _virtual_address_for_offset(work, checksum_offset),
                "repair_id": game["repair_id"],
                "repair_stage": stage,
                "stage_parent_sha256": parent_sha256,
            }
        )
        occupied.append((checksum_offset, checksum_offset + 4, owner))
    for offset, before, after, purpose in writes:
        if len(before) != len(after):
            raise PatcherError(f"{build.id} static-repair write changes length at 0x{offset:X}.")
        actual = bytes(work[offset : offset + len(before)])
        if actual != before:
            raise PatcherError(
                f"{build.id} static-repair byte guard failed at 0x{offset:X}: "
                f"expected {before.hex().upper()}, found {actual.hex().upper()}."
            )
        work[offset : offset + len(after)] = after
        occupied.append((offset, offset + len(after), owner))
        records.append(
            {
                "offset": f"0x{offset:X}",
                "before": before.hex().upper(),
                "after": after.hex().upper(),
                "purpose": purpose,
                "owner": owner,
                "virtual_address": _virtual_address_for_offset(work, offset),
                "repair_id": game["repair_id"],
                "repair_stage": stage,
                "stage_parent_sha256": parent_sha256,
            }
        )
    if append is not None:
        if len(work) != mode["parent_size"]:
            raise PatcherError(f"{build.id} static-repair append offset is not exact.")
        append_offset = len(work)
        work.extend(append)
        occupied.append((append_offset, append_offset + len(append), owner))
        records.append(
            {
                "offset": f"0x{append_offset:X}",
                "before": "",
                "after": append.hex().upper(),
                "purpose": f"append reviewed {build.id} static serializer/reader page",
                "owner": owner,
                "virtual_address": None,
                "repair_id": game["repair_id"],
                "repair_stage": stage,
                "stage_parent_sha256": parent_sha256,
            }
        )
    result_checksum_offset, result_checksum_before, result_checksum_after = _canonicalize_pe_checksum(work)
    result_sha256 = hashlib.sha256(work).hexdigest().upper()
    if len(work) != mode["result_size"] or result_sha256 != mode["result_sha256"]:
        raise PatcherError(
            f"{build.id} static-repair result guard failed: expected "
            f"{mode['result_size']} / {mode['result_sha256']}, found "
            f"{len(work)} / {result_sha256}."
        )
    if result_checksum_after.hex().upper() != mode["result_checksum"]:
        raise PatcherError(f"{build.id} static-repair result checksum mismatch.")
    if result_checksum_before != result_checksum_after:
        occupied.append((result_checksum_offset, result_checksum_offset + 4, owner))
        records.append(
            {
                "offset": f"0x{result_checksum_offset:X}",
                "before": result_checksum_before.hex().upper(),
                "after": result_checksum_after.hex().upper(),
                "purpose": f"bind {build.id} static-repair result checksum",
                "owner": owner,
                "virtual_address": _virtual_address_for_offset(work, result_checksum_offset),
                "repair_id": game["repair_id"],
                "repair_stage": stage,
                "stage_parent_sha256": parent_sha256,
            }
        )
    for record in records:
        record["stage_result_sha256"] = result_sha256
    data[:] = work
    return records, occupied


def _expanded_static_repair_summary(
    applied: list[dict[str, str]], final_sha256: str
) -> list[dict[str, str]]:
    summaries: dict[str, dict[str, str]] = {}
    for record in applied:
        repair_id = record.get("repair_id")
        if not repair_id:
            continue
        summaries.setdefault(
            repair_id,
            {
                "repair_id": repair_id,
                "stage": record["repair_stage"],
                "stage_parent_sha256": record["stage_parent_sha256"],
                "stage_result_sha256": record["stage_result_sha256"],
                "final_sha256": final_sha256,
                "runtime_go": False,
                "player_go": False,
                "publication_ready": False,
            },
        )
    return list(summaries.values())


def _expanded_atomic_writer_integration() -> dict[str, Any]:
    """Load the closed exact-build contract for real Expanded save writers."""
    try:
        source = EXPANDED_ATOMIC_WRITER_INTEGRATION_PATH.read_bytes()
        if source_text_sha256(source) != EXPANDED_ATOMIC_WRITER_INTEGRATION_SHA256:
            raise PatcherError("Expanded atomic-writer integration source hash mismatch.")
        payload = json.loads(source.decode("utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PatcherError("Expanded atomic-writer integration contract is unavailable.") from exc
    if set(payload) != {
        "schema", "status", "native_output", "runtime_go", "player_go",
        "publication_ready", "generator", "games",
    }:
        raise PatcherError("Expanded atomic-writer integration contract is not closed.")
    if (
        payload.get("schema") != "vvfp.expanded_atomic_writer_integration.v1"
        or payload.get("status") != "active_in_expanded_render_runtime_stop"
        or payload.get("native_output") is not True
        or payload.get("runtime_go") is not False
        or payload.get("player_go") is not False
        or payload.get("publication_ready") is not False
    ):
        raise PatcherError("Expanded atomic-writer integration gates are not exact.")
    generator = payload.get("generator")
    if not isinstance(generator, dict) or set(generator) != {
        "path", "source_text_sha256", "failure_policy", "commit_protocol",
    }:
        raise PatcherError("Expanded atomic-writer generator binding is not closed.")
    if (
        generator.get("path") != "src/expanded_atomic_writer.py"
        or generator.get("failure_policy") != "fatal_nonreturn_on_uncertain_failure"
    ):
        raise PatcherError("Expanded atomic-writer generator binding is not exact.")
    generator_path = ROOT / generator["path"]
    try:
        generator_source = generator_path.read_bytes()
    except OSError as exc:
        raise PatcherError("Expanded atomic-writer generator is unavailable.") from exc
    if source_text_sha256(generator_source) != generator.get("source_text_sha256"):
        raise PatcherError("Expanded atomic-writer generator hash mismatch.")
    games = payload.get("games")
    if not isinstance(games, dict) or set(games) != {"vv3", "vv4", "vv5"}:
        raise PatcherError("Expanded atomic-writer game set is not exact.")
    from expanded_atomic_writer import CONFIGS
    for game_id, game in games.items():
        if not isinstance(game, dict) or set(game) != {
            "writer_va", "writer_raw", "writer_length", "writer_sha256",
            "header_va", "header_size", "header_size_offset", "backup_policy",
            "import_page_sha256", "modes",
        }:
            raise PatcherError(f"{game_id} atomic-writer record is not closed.")
        config = CONFIGS[game_id]
        if (
            game.get("writer_va") != f"0x{config.writer_va:X}"
            or game.get("writer_raw") != f"0x{config.writer_raw:X}"
            or game.get("header_va") != f"0x{config.header_va:X}"
            or game.get("header_size") != config.header_size
            or game.get("header_size_offset") != config.header_size_offset
            or game.get("backup_policy")
            != "manager_slot_plus_0x14_for_positive_slot_else_null"
            or game.get("import_page_sha256") != config.import_page_sha256
        ):
            raise PatcherError(f"{game_id} atomic-writer placement binding is stale.")
        modes = game.get("modes")
        if not isinstance(modes, dict) or set(modes) != EXPANDED_PATCH_MODES:
            raise PatcherError(f"{game_id} atomic-writer mode set is not exact.")
        for mode_id, identity in modes.items():
            if not isinstance(identity, dict) or set(identity) != {
                "parent_size", "parent_sha256", "parent_checksum",
                "result_size", "result_sha256", "result_checksum",
            }:
                raise PatcherError(
                    f"{game_id} {mode_id} atomic-writer identity is not closed."
                )
            for key in ("parent_sha256", "result_sha256"):
                value = identity.get(key)
                if not isinstance(value, str) or len(value) != 64:
                    raise PatcherError(
                        f"{game_id} {mode_id} atomic-writer {key} is malformed."
                    )
            for key in ("parent_checksum", "result_checksum"):
                value = identity.get(key)
                if not isinstance(value, str) or len(value) != 8:
                    raise PatcherError(
                        f"{game_id} {mode_id} atomic-writer {key} is malformed."
                    )
    return payload


def _apply_reviewed_expanded_atomic_writer(
    data: bytearray,
    build: Build,
    patch_mode: str,
    *,
    identity_override: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[tuple[int, int, str]]]:
    """Install the deterministic writer transactionally on an exact parent."""
    if patch_mode not in EXPANDED_PATCH_MODES or build.id not in {"vv3", "vv4", "vv5"}:
        return [], []
    contract = _expanded_atomic_writer_integration()
    game = contract["games"][build.id]
    mode = identity_override or game["modes"][patch_mode]
    work = bytearray(data)
    checksum_offset, checksum_before, checksum_parent = _canonicalize_pe_checksum(work)
    parent_sha256 = hashlib.sha256(work).hexdigest().upper()
    if len(work) != mode["parent_size"] or parent_sha256 != mode["parent_sha256"]:
        raise PatcherError(
            f"{build.id} atomic-writer parent guard failed: expected "
            f"{mode['parent_size']} / {mode['parent_sha256']}, found "
            f"{len(work)} / {parent_sha256}."
        )
    if checksum_parent.hex().upper() != mode["parent_checksum"]:
        raise PatcherError(f"{build.id} atomic-writer parent checksum mismatch.")
    try:
        from expanded_atomic_writer import apply_atomic_writer_bytes
        work, generated, metadata = apply_atomic_writer_bytes(work, build.id)
    except (ImportError, OSError, TypeError, ValueError) as exc:
        raise PatcherError(f"{build.id} atomic-writer generation failed: {exc}") from exc
    if (
        metadata.get("writer_length") != game["writer_length"]
        or metadata.get("writer_sha256") != game["writer_sha256"]
        or metadata.get("import_page_sha256") != game["import_page_sha256"]
        or metadata.get("runtime_go") is not False
        or metadata.get("player_go") is not False
        or metadata.get("publication_ready") is not False
    ):
        raise PatcherError(f"{build.id} atomic-writer emitted metadata mismatch.")
    result_checksum_offset, result_checksum_before, result_checksum_after = _canonicalize_pe_checksum(work)
    result_sha256 = hashlib.sha256(work).hexdigest().upper()
    if len(work) != mode["result_size"] or result_sha256 != mode["result_sha256"]:
        raise PatcherError(
            f"{build.id} atomic-writer result guard failed: expected "
            f"{mode['result_size']} / {mode['result_sha256']}, found "
            f"{len(work)} / {result_sha256}."
        )
    if result_checksum_after.hex().upper() != mode["result_checksum"]:
        raise PatcherError(f"{build.id} atomic-writer result checksum mismatch.")
    owner = f"automatic:expanded-atomic-writer:{build.id}"
    records: list[dict[str, Any]] = []
    occupied: list[tuple[int, int, str]] = []
    if checksum_before != checksum_parent:
        records.append(
            {
                "offset": f"0x{checksum_offset:X}",
                "before": checksum_before.hex().upper(),
                "after": checksum_parent.hex().upper(),
                "purpose": f"canonicalize {build.id} atomic-writer parent checksum",
                "owner": owner,
            }
        )
        occupied.append((checksum_offset, checksum_offset + 4, owner))
    for generated_record in generated:
        record = dict(generated_record)
        offset = int(record["offset"], 0)
        after = bytes.fromhex(record["after"])
        record.update(
            {
                "owner": owner,
                "virtual_address": _virtual_address_for_offset(work, offset),
            }
        )
        records.append(record)
        occupied.append((offset, offset + len(after), owner))
    if result_checksum_before != result_checksum_after:
        records.append(
            {
                "offset": f"0x{result_checksum_offset:X}",
                "before": result_checksum_before.hex().upper(),
                "after": result_checksum_after.hex().upper(),
                "purpose": f"bind {build.id} atomic-writer result checksum",
                "owner": owner,
                "virtual_address": _virtual_address_for_offset(work, result_checksum_offset),
            }
        )
        occupied.append((result_checksum_offset, result_checksum_offset + 4, owner))
    for record in records:
        record.update(
            {
                "atomic_writer_id": f"{build.id}_expanded_atomic_writer",
                "stage_parent_sha256": parent_sha256,
                "stage_result_sha256": result_sha256,
                "writer_sha256": metadata["writer_sha256"],
                "runtime_go": False,
                "player_go": False,
                "publication_ready": False,
            }
        )
    data[:] = work
    return records, occupied


def _expanded_atomic_writer_summary(
    applied: list[dict[str, Any]], final_sha256: str
) -> list[dict[str, Any]]:
    summaries: dict[str, dict[str, Any]] = {}
    for record in applied:
        writer_id = record.get("atomic_writer_id")
        if not writer_id:
            continue
        summaries.setdefault(
            writer_id,
            {
                "atomic_writer_id": writer_id,
                "stage_parent_sha256": record["stage_parent_sha256"],
                "stage_result_sha256": record["stage_result_sha256"],
                "final_sha256": final_sha256,
                "writer_sha256": record["writer_sha256"],
                "failure_policy": "fatal_nonreturn_on_uncertain_failure",
                "runtime_go": False,
                "player_go": False,
                "publication_ready": False,
            },
        )
    return list(summaries.values())


def _vv3_expanded_time_warp_core() -> dict[str, Any]:
    """Load the closed alternate VV3 static+atomic profile."""
    try:
        source = VV3_EXPANDED_TIME_WARP_CORE_PATH.read_bytes()
        expected_hash = EXPANDED_TIME_WARP_ARTIFACT_SHA256["vv3"]["core"]
        if source_text_sha256(source) != expected_hash:
            raise PatcherError("VV3 Time Warp core source identity mismatch.")
        core = json.loads(source.decode("utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PatcherError("VV3 Time Warp core contract is unavailable.") from exc
    if set(core) != {
        "schema", "feature_id", "status", "runtime_go", "player_go",
        "publication_ready", "source_bindings", "page", "static", "atomic", "modes",
    }:
        raise PatcherError("VV3 Time Warp core contract is not closed.")
    if (
        core.get("schema") != "vvfp.vv3_expanded_time_warp_core.v1"
        or core.get("feature_id") != EXPANDED_TIME_WARP_IDS["vv3"]
        or core.get("status")
        != "static implementation awaiting independent Disassembler review"
        or core.get("runtime_go") is not False
        or core.get("player_go") is not False
        or core.get("publication_ready") is not False
    ):
        raise PatcherError("VV3 Time Warp core gates are not exact.")
    page = core.get("page")
    if (
        not isinstance(page, dict)
        or page.get("page_raw") != "0xCB000"
        or page.get("page_rva") != "0x3B8000"
        or page.get("page_va") != "0x7B8000"
        or page.get("page_size") != 0x1000
    ):
        raise PatcherError("VV3 Time Warp page placement drifted.")
    static = core.get("static")
    if static != {
        "page_raw": "0xCC000",
        "page_rva": "0x3B9000",
        "page_va": "0x7B9000",
        "page_sha256": "9F82D59D1436B17ACA69CD637AB40D44DF35323DA46600AAA5FD07315C249B64",
    }:
        raise PatcherError("VV3 Time Warp static-page binding drifted.")
    atomic = core.get("atomic")
    if atomic != {
        "writer_raw": "0xCC400",
        "writer_va": "0x7B9400",
        "writer_sha256": "CEE9E08759B1504C798E4BBE3AD39799358E2A93C8537DBECBE294D53D251154",
        "import_raw": "0xCD000",
        "import_rva": "0x3BA000",
        "import_va": "0x7BA000",
        "import_sha256": "291FA68AE4F320C92226DFE735BD4559CE79BCDC949BECC2F4AFF7D6FC1E2A50",
    }:
        raise PatcherError("VV3 Time Warp atomic-page binding drifted.")
    modes = core.get("modes")
    if not isinstance(modes, dict) or set(modes) != EXPANDED_PATCH_MODES:
        raise PatcherError("VV3 Time Warp core modes are not exact.")
    for mode_id, mode in modes.items():
        if not isinstance(mode, dict) or set(mode) != {
            "expanded_parent", "time_warp_result", "static_result",
            "atomic_result", "statistics_result",
        }:
            raise PatcherError(f"VV3 Time Warp {mode_id} identity chain is not closed.")
        for stage in mode.values():
            if (
                not isinstance(stage, dict)
                or set(stage) != {"size", "sha256", "checksum"}
                or not isinstance(stage.get("size"), int)
                or len(str(stage.get("sha256", ""))) != 64
                or len(str(stage.get("checksum", ""))) != 8
            ):
                raise PatcherError(f"VV3 Time Warp {mode_id} stage identity is malformed.")
    return core


def _apply_reviewed_vv3_time_warp_static_repair(
    data: bytearray,
    build: Build,
    patch_mode: str,
) -> tuple[list[dict[str, Any]], list[tuple[int, int, str]]]:
    """Append the existing certified serializer page on the alternate profile."""
    if build.id != "vv3" or patch_mode not in EXPANDED_PATCH_MODES:
        return [], []
    core = _vv3_expanded_time_warp_core()
    identity = core["modes"][patch_mode]
    work = bytearray(data)
    checksum_raw, checksum_before, checksum_parent = _canonicalize_pe_checksum(work)
    parent = identity["time_warp_result"]
    if (
        len(work) != parent["size"]
        or hashlib.sha256(work).hexdigest().upper() != parent["sha256"]
        or checksum_parent.hex().upper() != parent["checksum"]
    ):
        raise PatcherError("VV3 Time Warp static-repair parent guard failed.")
    integration = _expanded_static_repair_integration()["games"]["vv3"]
    candidate = _expanded_static_repair_candidate(integration)
    page = _static_repair_page(candidate, "vv3")
    section = candidate["section_plan"]
    pe = candidate["pe_guards"]
    writes: list[tuple[int, bytes, bytes, str]] = [
        (int(pe["section_count_raw"], 0), bytes.fromhex(pe["section_count_before"]), bytes.fromhex(pe["section_count_after"]), "add reviewed .vv3sv section count after .vv3tw"),
        (int(pe["size_of_image_raw"], 0), bytes.fromhex(pe["size_of_image_before"]), bytes.fromhex(pe["size_of_image_after"]), "extend reviewed VV3 SizeOfImage through .vv3sv"),
        (int(section["header_raw"], 0), bytes.fromhex(section["header_guard"]), bytes.fromhex(section["header_bytes"]), "add reviewed .vv3sv section header after .vv3tw"),
    ]
    for hook in candidate["hooks"]:
        writes.append((int(hook["raw"], 0), bytes.fromhex(hook["preimage"]), bytes.fromhex(hook["after"]), f"route VV3 {hook['id']} through reviewed static repair"))
    owner = "automatic:expanded-static-repair:vv3_time_warp_profile"
    records: list[dict[str, Any]] = []
    ranges: list[tuple[int, int, str]] = []
    if checksum_before != checksum_parent:
        records.append({"offset": f"0x{checksum_raw:X}", "before": checksum_before.hex().upper(), "after": checksum_parent.hex().upper(), "purpose": "canonicalize VV3 Time Warp static parent checksum", "owner": owner})
        ranges.append((checksum_raw, checksum_raw + 4, owner))
    for raw, before, after, purpose in writes:
        actual = bytes(work[raw : raw + len(before)])
        if actual != before:
            raise PatcherError(f"VV3 Time Warp static-repair preimage mismatch at 0x{raw:X}.")
        work[raw : raw + len(after)] = after
        records.append({"offset": f"0x{raw:X}", "before": before.hex().upper(), "after": after.hex().upper(), "purpose": purpose, "owner": owner})
        ranges.append((raw, raw + len(after), owner))
    append_raw = int(section["raw_start"], 0)
    if len(work) != append_raw:
        raise PatcherError("VV3 Time Warp .vv3sv append boundary drifted.")
    work.extend(page)
    records.append({"offset": f"0x{append_raw:X}", "before": "", "after": page.hex().upper(), "purpose": "append byte-identical reviewed .vv3sv page", "owner": owner, "virtual_address": section["va"]})
    ranges.append((append_raw, append_raw + len(page), owner))
    result_raw, result_before, result_after = _canonicalize_pe_checksum(work)
    result = identity["static_result"]
    if (
        len(work) != result["size"]
        or hashlib.sha256(work).hexdigest().upper() != result["sha256"]
        or result_after.hex().upper() != result["checksum"]
    ):
        raise PatcherError("VV3 Time Warp static-repair result guard failed.")
    if result_before != result_after:
        records.append({"offset": f"0x{result_raw:X}", "before": result_before.hex().upper(), "after": result_after.hex().upper(), "purpose": "bind VV3 Time Warp static result checksum", "owner": owner})
        ranges.append((result_raw, result_raw + 4, owner))
    data[:] = work
    return records, ranges


def _apply_reviewed_vv3_time_warp_atomic_writer(
    data: bytearray,
    build: Build,
    patch_mode: str,
) -> tuple[list[dict[str, Any]], list[tuple[int, int, str]]]:
    core = _vv3_expanded_time_warp_core()
    chain = core["modes"][patch_mode]
    parent = chain["static_result"]
    result = chain["atomic_result"]
    identity = {
        "parent_size": parent["size"],
        "parent_sha256": parent["sha256"],
        "parent_checksum": parent["checksum"],
        "result_size": result["size"],
        "result_sha256": result["sha256"],
        "result_checksum": result["checksum"],
    }
    return _apply_reviewed_expanded_atomic_writer(
        data, build, patch_mode, identity_override=identity
    )


EXPANDED_STATISTICS_FEATURE_IDS = {
    "vv3": "vv3_write_village_statistics",
    "vv4": "vv4_write_village_statistics",
    "vv5": "vv5_write_village_statistics",
}
EXPANDED_VV3_ATOMIC_CORE_IDS = frozenset(
    {
        "vv3_enable_origins_exclusive_features_running_candidate",
        "vv3_all_villagers_like_running_candidate",
    }
)
EXPANDED_VV3_TIME_WARP_CORE_ID = EXPANDED_TIME_WARP_IDS["vv3"]


def _compose_expanded_statistics_after_atomic(
    data: bytes | bytearray,
    build: Build,
    patch_mode: str,
    fun_bytes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Replay the exact Statistics wrapper over the reviewed atomic writer.

    The Statistics feature is the one supported optional owner of the primary
    save callsite also owned by the atomic core.  Its outer detour remains the
    final callsite owner, while the wrapper's one exact inner stock-writer call
    is rebound to the atomic writer.  Every stock and atomic preimage remains
    independently guarded before either composition edit is accepted.
    """
    if patch_mode not in EXPANDED_PATCH_MODES or build.id not in EXPANDED_STATISTICS_FEATURE_IDS:
        return fun_bytes
    feature_id = EXPANDED_STATISTICS_FEATURE_IDS[build.id]
    owner = f"feature:{feature_id}"
    owned = [patch for patch in fun_bytes if patch.get("_owner") == owner]
    if not owned:
        return fun_bytes
    selected_owners = {
        str(patch.get("_owner", "")).removeprefix("feature:")
        for patch in fun_bytes
    }
    if build.id == "vv3":
        old_core = EXPANDED_VV3_ATOMIC_CORE_IDS.issubset(selected_owners)
        time_warp_core = EXPANDED_VV3_TIME_WARP_CORE_ID in selected_owners
        if not old_core and not time_warp_core:
            return fun_bytes
        if old_core and time_warp_core:
            raise PatcherError("VV3 atomic core profiles are mutually exclusive.")
    try:
        from expanded_atomic_writer import CONFIGS
        config = CONFIGS[build.id]
    except (ImportError, KeyError) as exc:
        raise PatcherError(f"{build.id} Statistics/atomic composition is unavailable.") from exc
    callsite_rows = {
        raw: (before, after) for raw, before, after in config.callsites
    }
    outer = [
        patch
        for patch in owned
        if int(patch["offset"], 0) in callsite_rows
    ]
    wrappers = [
        patch
        for patch in owned
        if len(_patch_bytes(patch, "after")) == 0x200
        and _patch_bytes(patch, "before") == bytes(0x200)
    ]
    if len(outer) != 1 or len(wrappers) != 1:
        raise PatcherError(f"{build.id} Statistics/atomic composition shape drifted.")
    outer_raw = int(outer[0]["offset"], 0)
    atomic_before, atomic_after = callsite_rows[outer_raw]
    if _patch_bytes(outer[0], "before") != atomic_before:
        raise PatcherError(f"{build.id} Statistics stock-writer preimage drifted.")
    wrapper_raw = int(wrappers[0]["offset"], 0)
    wrapper_after = bytearray(_patch_bytes(wrappers[0], "after"))
    stock_calls: list[int] = []
    for relative in range(len(wrapper_after) - 4):
        if wrapper_after[relative] != 0xE8:
            continue
        source_va_text = _virtual_address_for_offset(data, wrapper_raw + relative)
        if source_va_text is None:
            raise PatcherError(f"{build.id} Statistics wrapper VA is unmapped.")
        source_va = int(source_va_text, 0)
        target = source_va + 5 + int.from_bytes(
            wrapper_after[relative + 1 : relative + 5], "little", signed=True
        )
        if target == config.stock_writer_va:
            stock_calls.append(relative)
    if len(stock_calls) != 1:
        raise PatcherError(
            f"{build.id} Statistics wrapper stock-writer call count is not one."
        )
    relative = stock_calls[0]
    source_va_text = _virtual_address_for_offset(data, wrapper_raw + relative)
    if source_va_text is None:
        raise PatcherError(f"{build.id} Statistics wrapper VA is unmapped.")
    source_va = int(source_va_text, 0)
    displacement = config.writer_va - (source_va + 5)
    if not -(1 << 31) <= displacement < (1 << 31):
        raise PatcherError(f"{build.id} Statistics/atomic rel32 is out of range.")
    wrapper_after[relative + 1 : relative + 5] = displacement.to_bytes(
        4, "little", signed=True
    )
    composed: list[dict[str, Any]] = []
    for patch in fun_bytes:
        replacement = dict(patch)
        if patch is outer[0]:
            replacement["before"] = atomic_after.hex().upper()
            replacement["purpose"] = (
                str(patch["purpose"])
                + "; replay the exact Statistics outer wrapper after the atomic core"
            )
            replacement["_atomic_statistics_overlay"] = True
        elif patch is wrappers[0]:
            replacement["after"] = bytes(wrapper_after).hex().upper()
            replacement.pop("after_base64", None)
            replacement["purpose"] = (
                str(patch["purpose"])
                + "; route its one guarded inner save through the atomic writer"
            )
            replacement["_atomic_statistics_wrapper"] = True
        composed.append(replacement)
    return composed


def render_patched_bytes(
    source: Path,
    build: Build,
    patch_mode: str = DEFAULT_PATCH_MODE,
    fun_patch_ids: tuple[str, ...] | list[str] = (),
    *,
    _fun_patches_override: list[FunPatch] | None = None,
    playtest_disabled_feature_ids: tuple[str, ...] | list[str] = (),
    playtest_output_root: Path | None = None,
) -> tuple[bytearray, list[dict[str, str]]]:
    # The public/candidate VV3 upgrade surfaces are bound to the stock Detail
    # and Tech layouts.  Reject their IDs before variant, catalog, companion,
    # manifest, or executable source access in both public and override paths.
    requested_ids = set(fun_patch_ids)
    if _fun_patches_override is not None:
        requested_ids.update(patch.id for patch in _fun_patches_override)
    if (
        build.id == "vv3"
        and patch_mode in EXPANDED_PATCH_MODES
        and VV3_STOCK_ONLY_UPGRADE_IDS.intersection(requested_ids)
    ):
        raise PatcherError(
            "VV3 Origins upgrade surfaces support stock modes only; "
            "Expanded-256 remains fail-closed."
        )
    # The VV1 selected-villager transaction is source-bound to the stock
    # Detail/state pool layout. Reject Expanded before variant, catalog,
    # manifest, or source access in this renderer.
    vv1_individual_mastery_selected = (
        VV1_INDIVIDUAL_FULL_MASTERY_CANDIDATE_ID in set(fun_patch_ids)
    )
    if _fun_patches_override is not None:
        vv1_individual_mastery_selected = vv1_individual_mastery_selected or any(
            patch.id == VV1_INDIVIDUAL_FULL_MASTERY_CANDIDATE_ID
            for patch in _fun_patches_override
        )
    if (
        build.id == "vv1"
        and vv1_individual_mastery_selected
        and patch_mode in EXPANDED_PATCH_MODES
    ):
        raise PatcherError(
            "VV1 selected Full Mastery supports stock modes only; "
            "Expanded-256 remains ON HOLD/fail-closed."
        )
    # The VV2 selected-villager transaction is source-bound to the stock
    # 256-record Detail/manager layout.  Reject Expanded before variant,
    # catalog, manifest, or source access in this renderer.
    vv2_individual_mastery_selected = (
        VV2_INDIVIDUAL_FULL_MASTERY_CANDIDATE_ID in set(fun_patch_ids)
    )
    if _fun_patches_override is not None:
        vv2_individual_mastery_selected = vv2_individual_mastery_selected or any(
            patch.id == VV2_INDIVIDUAL_FULL_MASTERY_CANDIDATE_ID
            for patch in _fun_patches_override
        )
    if (
        build.id == "vv2"
        and vv2_individual_mastery_selected
        and patch_mode in EXPANDED_PATCH_MODES
    ):
        raise PatcherError(
            "VV2 selected Full Mastery supports stock modes only; "
            "Expanded-256 remains ON HOLD/fail-closed."
        )
    # VV5 Running is Collection-only.  Keep this guard ahead of variant,
    # catalog, manifest, and source access in the generic production path.
    vv5_running_selected = VV5_INDIVIDUAL_RUNNING_CANDIDATE_ID in set(fun_patch_ids)
    if _fun_patches_override is not None:
        vv5_running_selected = vv5_running_selected or any(
            patch.id == VV5_INDIVIDUAL_RUNNING_CANDIDATE_ID
            for patch in _fun_patches_override
        )
    if build.id == "vv5" and vv5_running_selected and patch_mode != "collection_progression":
        raise PatcherError("VV5 Running supports Collection Progression only.")
    if _fun_patches_override is not None and playtest_disabled_feature_ids:
        raise PatcherError(
            "Playtest-disabled features cannot be combined with an internal patch override."
        )
    if (
        fun_patch_ids
        and playtest_disabled_feature_ids
        and playtest_output_root is None
    ):
        raise PatcherError(
            "Playtest-disabled features cannot be combined with catalog fun patches "
            "without a distinct explicit playtest output root."
        )
    variant = get_patch_variant(build, patch_mode)
    fun_patches = (
        _selected_fun_patches(build, fun_patch_ids)
        if _fun_patches_override is None
        else list(_fun_patches_override)
    )
    if _fun_patches_override is None:
        fun_patches.extend(
            _selected_playtest_disabled_fun_patches(
                build, playtest_disabled_feature_ids, patch_mode
            )
        )
    selected_fun_ids = {patch.id for patch in fun_patches}
    for feature in fun_patches:
        if feature.id == VV1_INDIVIDUAL_FULL_MASTERY_CANDIDATE_ID:
            if build.id != "vv1" or patch_mode not in {
                "collection_progression",
                "immediate_fixed",
            }:
                raise PatcherError("VV1 selected Full Mastery is stock-mode only.")
            if "vv1_full_mastery_all_stage_a_candidate" not in selected_fun_ids:
                raise PatcherError(
                    "VV1 selected Full Mastery requires the village-wide Full Mastery prerequisite."
                )
            selected_conflicts = VV1_INDIVIDUAL_FULL_MASTERY_CONFLICTS & selected_fun_ids
            if selected_conflicts:
                raise PatcherError(
                    "VV1 selected Full Mastery conflicts with legacy Origins owner(s): "
                    + ", ".join(sorted(selected_conflicts))
                )
        if feature.id in EXPANDED_TIME_WARP_IDS.values():
            _validate_expanded_time_warp_selection(
                build,
                feature,
                selected_fun_ids,
                patch_mode,
            )
        if feature.id == VV3_INDIVIDUAL_RUNNING_CANDIDATE_ID:
            _validate_vv3_individual_running_candidate(
                feature,
                selected_fun_ids,
                patch_mode,
            )
        if feature.id == VV3_FULL_HEAL_CANDIDATE_ID:
            _validate_vv3_full_heal_candidate(
                feature,
                selected_fun_ids,
                patch_mode,
            )
        if feature.id == VV5_INDIVIDUAL_RUNNING_CANDIDATE_ID:
            _validate_vv5_individual_running_candidate(
                feature,
                selected_fun_ids,
                patch_mode,
            )
    if (
        _fun_patches_override is None
        and build.id == "vv4"
        and patch_mode in EXPANDED_PATCH_MODES
        and any(
            patch.id
            in {
                "vv4_enable_origins_exclusive_features",
                "vv4_full_mastery_all_stage_a_candidate",
            }
            for patch in fun_patches
        )
    ):
        raise PatcherError(
            "VV4 Full Mastery is certified for stock modes only; "
            "Expanded-256 remains ON HOLD/fail-closed."
        )
    if (
        build.id == "vv5"
        and patch_mode in EXPANDED_PATCH_MODES
        and any(
            patch.id
            in {
                "vv5_enable_origins_exclusive_features_full_mastery_candidate",
                "vv5_full_mastery_all_stage_a_candidate",
                VV5_INDIVIDUAL_RUNNING_CANDIDATE_ID,
            }
            for patch in fun_patches
        )
    ):
        raise PatcherError(
            "VV5 Full Mastery candidates are stock-mode only; Expanded-256 is fail-closed."
        )
    if (
        build.id == "vv1"
        and patch_mode in EXPANDED_PATCH_MODES
        and any(
            patch.id == "vv1_full_mastery_all_stage_a_candidate"
            for patch in fun_patches
        )
    ):
        raise PatcherError(
            "VV1 Full Mastery is certified for stock modes only; "
            "Expanded-256 remains ON HOLD/fail-closed."
        )
    composition = next(
        (patch for patch in fun_patches if patch.id == VV1_ORIGINS_COMPOSITION_ID),
        None,
    )
    if composition is not None:
        if build.id != "vv1" or patch_mode in EXPANDED_PATCH_MODES:
            raise PatcherError(
                "VV1 Origins + Full Mastery composition is stock-only; "
                "Expanded-256 remains ON HOLD/fail-closed."
            )
        origins = next(
            (patch for patch in fun_patches if patch.id == "vv1_enable_origins_exclusive_features"),
            None,
        )
        if origins is None:
            raise PatcherError(
                "VV1 Origins + Full Mastery composition requires the active Origins prerequisite."
            )
        if any(
            patch.id == "vv1_full_mastery_all_stage_a_candidate"
            for patch in fun_patches
        ):
            raise PatcherError(
                "VV1 isolated Full Mastery and Origins composition cannot be selected together."
            )
        required_base = str(
            composition.raw.get("required_base_sha256", "")
        ).upper()
        required_dll = str(
            composition.raw.get("required_origins_dll_sha256", "")
        ).upper()
        if required_base != VV1_ORIGINS_COMPOSITION_BASE_SHA256:
            raise PatcherError("VV1 composition base identity metadata is not the certified value.")
        if required_dll != VV1_ORIGINS_COMPOSITION_DLL_SHA256:
            raise PatcherError("VV1 composition Origins DLL identity metadata is not the certified value.")
        origins_dll = ROOT / "assets" / "origins" / "VVFP Origins Icons.dll"
        if not origins_dll.is_file() or sha256(origins_dll) != VV1_ORIGINS_COMPOSITION_DLL_SHA256:
            raise PatcherError("VV1 composition Origins DLL is missing or hash-mismatched.")
        if sha256(source) != build.sha256:
            raise PatcherError("VV1 composition requires the exact certified stock executable fingerprint.")
        base, _ = render_patched_bytes(
            source,
            build,
            patch_mode,
            _fun_patches_override=[origins],
        )
        if hashlib.sha256(base).hexdigest().upper() != VV1_ORIGINS_COMPOSITION_BASE_SHA256:
            raise PatcherError("VV1 composition active Origins base fingerprint mismatch.")
    _validate_companion_sources(fun_patches)
    data = bytearray(source.read_bytes())
    original_data = bytes(data)
    applied: list[dict[str, str]] = []
    applied_ranges: list[tuple[int, int, str]] = []
    expanded = [dict(patch, _owner="automatic:population") for patch in _expanded_patches(build, variant)]
    safety = [dict(patch, _owner="automatic:safety") for patch in _safety_patches(build, patch_mode)]
    population = [dict(patch, _owner="automatic:population") for patch in variant["patches"]]
    support = _fun_patch_support(build, fun_patches)
    fun_bytes: list[dict[str, Any]] = []
    for feature in fun_patches:
        fun_bytes.extend(
            dict(patch, _owner=f"feature:{feature.id}")
            for patch in feature.patches
        )
        overrides = feature.raw.get("patch_mode_overrides", {})
        if overrides:
            for patch in overrides.get(patch_mode, []):
                fun_bytes.append(dict(patch, _owner=f"feature:{feature.id}"))
    fun_bytes = _compose_expanded_statistics_after_atomic(
        original_data, build, patch_mode, fun_bytes
    )
    vv3_legacy_atomic_core_ids = set(EXPANDED_VV3_ATOMIC_CORE_IDS)
    vv3_legacy_atomic_core = (
        build.id == "vv3"
        and patch_mode in EXPANDED_PATCH_MODES
        and vv3_legacy_atomic_core_ids.issubset(selected_fun_ids)
    )
    vv3_time_warp_atomic_core = (
        build.id == "vv3"
        and patch_mode in EXPANDED_PATCH_MODES
        and EXPANDED_VV3_TIME_WARP_CORE_ID in selected_fun_ids
    )
    if vv3_legacy_atomic_core and vv3_time_warp_atomic_core:
        raise PatcherError("VV3 Origins/Running and Time Warp core profiles are mutually exclusive.")
    vv3_atomic_core = vv3_legacy_atomic_core or vv3_time_warp_atomic_core
    vv3_atomic_core_ids = (
        {EXPANDED_VV3_TIME_WARP_CORE_ID}
        if vv3_time_warp_atomic_core
        else vv3_legacy_atomic_core_ids
    )
    vv3_core_features = (
        [feature for feature in fun_patches if feature.id in vv3_atomic_core_ids]
        if vv3_atomic_core
        else []
    )
    later_fun_features = (
        [feature for feature in fun_patches if feature.id not in vv3_atomic_core_ids]
        if vv3_atomic_core
        else fun_patches
    )
    vv3_core_fun_bytes = (
        [
            patch
            for patch in fun_bytes
            if patch.get("_owner", "").removeprefix("feature:")
            in vv3_atomic_core_ids
        ]
        if vv3_atomic_core
        else []
    )
    later_fun_bytes = (
        [
            patch
            for patch in fun_bytes
            if patch.get("_owner", "").removeprefix("feature:")
            not in vv3_atomic_core_ids
        ]
        if vv3_atomic_core
        else fun_bytes
    )
    candidate_preimage_checked = False
    candidate_preimage_checksum: bytes | None = None
    vv4_composed_parent_sha256: str | None = None
    if any(feature.id == VV4_FULL_HEAL_CANDIDATE_ID for feature in fun_patches):
        vv4_parent_features = [
            feature for feature in fun_patches
            if feature.id != VV4_FULL_HEAL_CANDIDATE_ID
        ]
        vv4_parent_bytes, _ = render_patched_bytes(
            source,
            build,
            patch_mode,
            _fun_patches_override=vv4_parent_features,
        )
        vv4_composed_parent_sha256 = hashlib.sha256(vv4_parent_bytes).hexdigest().upper()
        expected_vv4_parent = {
            "collection_progression": VV4_FULL_HEAL_PARENT_COLLECTION_SHA256,
            "immediate_fixed": VV4_FULL_HEAL_PARENT_IMMEDIATE_SHA256,
        }.get(patch_mode)
        if expected_vv4_parent is None or vv4_composed_parent_sha256 != expected_vv4_parent:
            raise PatcherError("VV4 Full Heal requires the exact complete certified parent composition.")
    if any(feature.id == VV3_FULL_HEAL_CANDIDATE_ID for feature in fun_patches):
        expected_preimage = VV3_FULL_HEAL_PRE_CURE_RENDERED_SHA256.get(patch_mode)
        parent_features = [feature for feature in fun_patches if feature.id != VV3_FULL_HEAL_CANDIDATE_ID]
        parent_bytes, _ = render_patched_bytes(
            source,
            build,
            patch_mode,
            _fun_patches_override=parent_features,
        )
        if build.id != "vv3" or expected_preimage is None or hashlib.sha256(parent_bytes).hexdigest().upper() != expected_preimage:
            raise PatcherError(
                "VV3 Full Heal requires the exact certified Origins + Full Mastery + individual Running composition."
            )
        if hashlib.sha256(parent_bytes[VV3_FULL_HEAL_LEGACY_START:VV3_FULL_HEAL_LEGACY_END_OFFSET]).hexdigest().upper() != VV3_FULL_HEAL_LEGACY_PRESERVED_RANGE_SHA256:
            raise PatcherError("VV3 Full Heal composed-parent legacy range fingerprint mismatch.")
        if hashlib.sha256(original_data[VV3_FULL_HEAL_LEGACY_START:VV3_FULL_HEAL_LEGACY_END_OFFSET]).hexdigest().upper() != VV3_FULL_HEAL_STOCK_ZERO_PREIMAGE_LEGACY_RANGE_SHA256:
            raise PatcherError("VV3 Full Heal stock-zero preimage legacy range fingerprint mismatch.")
        if any(parent_bytes[0x7B721:0x7B721 + 0x700]):
            raise PatcherError("VV3 Full Heal legacy Cure cave must remain zero.")
        candidate_preimage_checked = True
        candidate_preimage_checksum = bytes(parent_bytes[0x160:0x164])
    phases: list[tuple[str, list[dict[str, Any]]]] = [
        ("expanded", expanded),
        ("automatic", [*safety, *population]),
    ]
    if vv3_atomic_core:
        phases.append(("vv3_atomic_core", vv3_core_fun_bytes))
    phases.extend((("support", support), ("optional_fun", later_fun_bytes)))
    for phase_name, phase in phases:
        if phase_name == "automatic":
            repair_records, repair_ranges = _apply_reviewed_expanded_static_repair(
                data,
                build,
                patch_mode,
                "post_manifest",
                selected_fun_ids,
            )
            applied.extend(repair_records)
            applied_ranges.extend(repair_ranges)
        if phase_name == "vv3_atomic_core":
            applied.extend(
                _apply_pe_append_transactions(data, vv3_core_features, patch_mode)
            )
        if phase_name == "support":
            if vv3_atomic_core:
                applied.extend(
                    _relocate_expanded_shr_fun_patches(
                        build, patch_mode, vv3_core_features, data
                    )
                )
                if vv3_time_warp_atomic_core:
                    repair_records, repair_ranges = _apply_reviewed_vv3_time_warp_static_repair(
                        data, build, patch_mode
                    )
                else:
                    repair_records, repair_ranges = _apply_reviewed_expanded_static_repair(
                        data,
                        build,
                        patch_mode,
                        "post_feature_relocation",
                        selected_fun_ids,
                    )
                applied.extend(repair_records)
                applied_ranges.extend(repair_ranges)
                if vv3_time_warp_atomic_core:
                    atomic_records, atomic_ranges = _apply_reviewed_vv3_time_warp_atomic_writer(
                        data, build, patch_mode
                    )
                else:
                    atomic_records, atomic_ranges = _apply_reviewed_expanded_atomic_writer(
                        data, build, patch_mode
                    )
                applied.extend(atomic_records)
                applied_ranges.extend(atomic_ranges)
            elif (
                build.id in {"vv4", "vv5"}
                and patch_mode in EXPANDED_PATCH_MODES
            ):
                atomic_records, atomic_ranges = _apply_reviewed_expanded_atomic_writer(
                    data, build, patch_mode
                )
                applied.extend(atomic_records)
                applied_ranges.extend(atomic_ranges)
        if phase_name == "optional_fun":
            applied.extend(
                _apply_pe_append_transactions(data, later_fun_features, patch_mode)
            )
        for patch in phase:
            offset = int(patch["offset"], 0)
            before = _patch_bytes(patch, "before")
            after = _patch_bytes(patch, "after")
            if len(before) != len(after):
                raise PatcherError(
                    f"Internal manifest error at {patch['offset']}: length changed"
                )
            _validate_patch_bounds(
                data,
                offset,
                len(before),
                label=f"Patch at {patch['offset']}",
            )
            actual = bytes(data[offset : offset + len(before)])
            owner = patch.get("_owner", "automatic")
            if (
                owner == f"feature:{VV3_FULL_HEAL_CANDIDATE_ID}"
                and not candidate_preimage_checked
            ):
                expected_preimage = VV3_FULL_HEAL_PRE_CURE_RENDERED_SHA256.get(patch_mode)
                if build.id != "vv3" or expected_preimage is None or hashlib.sha256(data).hexdigest().upper() != expected_preimage:
                    raise PatcherError(
                        "VV3 Full Heal requires the exact certified Origins + Full Mastery + individual Running composition."
                    )
                if hashlib.sha256(data[VV3_FULL_HEAL_LEGACY_START:VV3_FULL_HEAL_LEGACY_END_OFFSET]).hexdigest().upper() != VV3_FULL_HEAL_LEGACY_PRESERVED_RANGE_SHA256:
                    raise PatcherError("VV3 Full Heal composed-parent legacy range fingerprint mismatch.")
                if hashlib.sha256(original_data[VV3_FULL_HEAL_LEGACY_START:VV3_FULL_HEAL_LEGACY_END_OFFSET]).hexdigest().upper() != VV3_FULL_HEAL_STOCK_ZERO_PREIMAGE_LEGACY_RANGE_SHA256:
                    raise PatcherError("VV3 Full Heal stock-zero legacy preimage fingerprint mismatch.")
                candidate_preimage_checked = True
                candidate_preimage_checksum = bytes(data[0x160:0x164])
            if (
                owner == "feature:vv5_full_mastery_all_stage_a_candidate"
            and offset == 0xDB766
                and actual[:1] == b"\xE9"
            ):
                continue
            end = offset + len(before)
            for prior_start, prior_end, prior_owner in applied_ranges:
                if offset < prior_end and prior_start < end and prior_owner != owner:
                    # The VV1 Origins composition intentionally overlays one
                    # exact post-Origins branch inside the guarded Origins
                    # payload.  It never replaces the shared constructor or
                    # handler hooks; all other cross-owner overlap remains a
                    # hard failure.
                    allowed_vv1_composition_overlay = (
                        owner == f"feature:{VV1_ORIGINS_COMPOSITION_ID}"
                        and prior_owner == "feature:vv1_enable_origins_exclusive_features"
                        and offset == 0x56A88
                        and before == bytes.fromhex("83FB067235")
                    )
                    allowed_vv5_individual_overlay = (
                        owner == "feature:vv5_full_mastery_all_stage_a_candidate"
                        and prior_owner in {
                            "feature:vv5_enable_origins_exclusive_features",
                            "feature:vv5_enable_origins_exclusive_features_full_mastery_candidate",
                        }
                        and offset == 0xDB766
                        and before == bytes.fromhex("83FB027525")
                    )
                    allowed_vv5_running_overlay = (
                        owner == f"feature:{VV5_INDIVIDUAL_RUNNING_CANDIDATE_ID}"
                        and prior_owner in {
                            "feature:vv5_full_mastery_all_stage_a_candidate",
                            "feature:vv5_enable_origins_exclusive_features_full_mastery_candidate",
                        }
                        and offset == 0xDB766
                        and before == bytes.fromhex("E995750100")
                    )
                    allowed_vv3_individual_running_overlay = (
                        owner == "feature:vv3_individual_grant_running_candidate"
                        and prior_owner
                        in {
                            "feature:vv3_enable_origins_exclusive_features",
                            "feature:vv3_enable_origins_exclusive_features_full_mastery_candidate",
                        }
                        and offset == 0xA38C3
                        and before == bytes.fromhex("83FB027525")
                    )
                    allowed_vv3_individual_full_mastery_overlay = (
                        owner
                        == f"feature:{VV3_INDIVIDUAL_FULL_MASTERY_CANDIDATE_ID}"
                        and prior_owner
                        in {
                            "feature:vv3_enable_origins_exclusive_features",
                            "feature:vv3_enable_origins_exclusive_features_full_mastery_candidate",
                        }
                        and offset == 0xA38C3
                        and before == bytes.fromhex("E926010000")
                        and after == bytes.fromhex("E938C72300")
                    )
                    allowed_vv3_full_heal_overlay = (
                        owner == f"feature:{VV3_FULL_HEAL_CANDIDATE_ID}"
                        and prior_owner
                        in {
                            "feature:vv3_enable_origins_exclusive_features",
                            "feature:vv3_enable_origins_exclusive_features_full_mastery_candidate",
                        }
                        and offset == 0xA35EF
                        and before == VV3_FULL_HEAL_HOOK_BEFORE
                    )
                    allowed_vv3_full_heal_cave_overlay = (
                        owner == f"feature:{VV3_FULL_HEAL_CANDIDATE_ID}"
                        and prior_owner
                        in {
                            "feature:vv3_enable_origins_exclusive_features",
                            "feature:vv3_enable_origins_exclusive_features_full_mastery_candidate",
                        }
                        and offset == 0x7B721
                        and before == bytes(VV3_FULL_HEAL_CAVE_LENGTH)
                    )
                    allowed_vv4_full_heal_overlay = _vv4_full_heal_overlay_allowed(
                        feature=feature,
                        current_owner=owner,
                        prior_owner=prior_owner,
                        prior_start=prior_start,
                        prior_end=prior_end,
                        patch_mode=patch_mode,
                        offset=offset,
                        before=before,
                        composed_sha256=vv4_composed_parent_sha256 or "",
                    )
                    allowed_atomic_statistics_overlay = (
                        patch.get("_atomic_statistics_overlay") is True
                        and owner
                        == f"feature:{EXPANDED_STATISTICS_FEATURE_IDS.get(build.id, '')}"
                        and prior_owner
                        == f"automatic:expanded-atomic-writer:{build.id}"
                        and prior_start == offset
                        and prior_end == end
                    )
                    if (
                        allowed_vv1_composition_overlay
                        or allowed_vv5_individual_overlay
                        or allowed_vv5_running_overlay
                        or allowed_vv3_individual_running_overlay
                        or allowed_vv3_individual_full_mastery_overlay
                        or allowed_vv3_full_heal_overlay
                        or allowed_vv3_full_heal_cave_overlay
                        or allowed_vv4_full_heal_overlay
                        or allowed_atomic_statistics_overlay
                    ):
                        continue
                    raise PatcherError(
                        f"Patch overlap between {prior_owner} and {owner} at 0x{offset:X}."
                    )
            if actual != before:
                raise PatcherError(
                    f"Byte guard failed at {patch['offset']}: "
                    f"expected {before.hex().upper()}, found {actual.hex().upper()}"
                )
            data[offset : offset + len(after)] = after
            applied_ranges.append((offset, end, owner))
            applied.append(
                {
                    "offset": patch["offset"],
                    "before": before.hex().upper(),
                    "after": after.hex().upper(),
                    "purpose": patch["purpose"],
                    "owner": patch.get("_owner", "automatic"),
                    "virtual_address": _virtual_address_for_offset(original_data, offset),
                }
            )
    applied.extend(
        _relocate_expanded_shr_fun_patches(
            build, patch_mode, later_fun_features, data
        )
    )
    task9_post_relocation = _apply_vv5_task9_post_relocation_hook(
        data, build, patch_mode, later_fun_features
    )
    applied.extend(task9_post_relocation)
    for record in task9_post_relocation:
        start = int(record["offset"], 0)
        applied_ranges.append((
            start,
            start + len(bytes.fromhex(record["after"])),
            record["owner"],
        ))
    if not vv3_atomic_core:
        repair_records, repair_ranges = _apply_reviewed_expanded_static_repair(
            data,
            build,
            patch_mode,
            "post_feature_relocation",
            selected_fun_ids,
        )
        applied.extend(repair_records)
        applied_ranges.extend(repair_ranges)
    applied.extend(
        _apply_vv3_expanded_healer_endpoint_repair(data, build, patch_mode)
    )
    applied.extend(
        _apply_vv3_expanded_capacity_corrections(data, build, patch_mode)
    )
    applied.extend(
        _apply_vv3_expanded_detail_roster_layout(
            data, build, patch_mode, selected_fun_ids
        )
    )
    applied.extend(
        _apply_vv3_expanded_chief_candidate_assignment_repair(
            data, build, patch_mode
        )
    )
    if applied:
        checksum_offset, _ = _pe_checksum_layout(data)
        checksum = pe_checksum(data)
        struct.pack_into("<I", data, checksum_offset, checksum)
    if vv3_time_warp_atomic_core:
        exact_profile_ids = {
            EXPANDED_VV3_TIME_WARP_CORE_ID,
            EXPANDED_STATISTICS_FEATURE_IDS["vv3"],
        }
        if selected_fun_ids <= exact_profile_ids:
            stage = (
                "statistics_result"
                if EXPANDED_STATISTICS_FEATURE_IDS["vv3"] in selected_fun_ids
                else "atomic_result"
            )
            expected = VV3_EXPANDED_FINAL_TIME_WARP_RESULTS[patch_mode][stage]
            if (
                len(data) != expected["size"]
                or hashlib.sha256(data).hexdigest().upper() != expected["sha256"]
                or bytes(data[checksum_offset : checksum_offset + 4]).hex().upper()
                != expected["checksum"]
            ):
                raise PatcherError(
                    f"VV3 Time Warp {stage} final identity mismatch."
                )
    if any(feature.id == VV3_FULL_HEAL_CANDIDATE_ID for feature in fun_patches):
        expected_rendered = VV3_FULL_HEAL_RENDERED_SHA256.get(patch_mode)
        expected_transition = VV3_FULL_HEAL_CHECKSUM_TRANSITIONS.get(patch_mode)
        if expected_rendered is None or expected_transition is None:
            raise PatcherError("VV3 Full Heal rendered output identity is not certified.")
        if hashlib.sha256(data).hexdigest().upper() != expected_rendered:
            raise PatcherError("VV3 Full Heal rendered output hash is not certified.")
        if candidate_preimage_checksum is None or candidate_preimage_checksum.hex().upper() != VV3_FULL_HEAL_PRE_CANDIDATE_CHECKSUM[patch_mode]:
            raise PatcherError("VV3 Full Heal checksum preimage is not certified.")
        if bytes(data[0x160:0x164]).hex().upper() != expected_transition["after"]:
            raise PatcherError("VV3 Full Heal checksum transition is not certified.")
    return data, applied


def render_vv5_individual_running_parent(
    source: Path | bytes,
    patch_mode: str,
) -> tuple[bytearray, list[dict[str, str]]]:
    """Render the disabled VV5 Running overlay over an authenticated FM parent.

    This deliberately bypasses the public catalog (the candidate is disabled)
    while using the same guarded append resolver and removal identities as the
    production path.  It never accepts stock or Expanded input as a parent.
    """
    if patch_mode != "collection_progression":
        raise PatcherError("VV5 Running supports Collection Progression only.")
    manifest_path = VV5_INDIVIDUAL_RUNNING_CANDIDATE_PATHS["manifest"]
    feature = FunPatch(json.loads(manifest_path.read_text(encoding="utf-8")))
    _validate_vv5_individual_running_candidate(feature, {feature.id}, patch_mode)
    expected = VV5_INDIVIDUAL_RUNNING_PARENT_SHA256[patch_mode]
    source_bytes = bytes(source) if isinstance(source, (bytes, bytearray)) else source.read_bytes()
    if hashlib.sha256(source_bytes).hexdigest().upper() != expected:
        raise PatcherError("VV5 Running requires the exact composed Full Mastery parent bytes.")
    data = bytearray(source_bytes)
    applied = _apply_pe_append_transactions(data, [feature], patch_mode)
    patch = feature.patches[0]
    offset = int(patch["offset"], 0)
    before = _patch_bytes(patch, "before")
    after = _patch_bytes(patch, "after")
    if bytes(data[offset : offset + len(before)]) != before:
        raise PatcherError("VV5 Running composed hook preimage mismatch.")
    data[offset : offset + len(after)] = after
    applied.append({"offset": patch["offset"], "before": before.hex().upper(), "after": after.hex().upper(), "purpose": patch["purpose"], "owner": f"feature:{feature.id}"})
    checksum_offset, _ = _pe_checksum_layout(data)
    struct.pack_into("<I", data, checksum_offset, 0)
    struct.pack_into("<I", data, checksum_offset, pe_checksum(data))
    return data, applied


def remove_vv5_individual_running_parent(
    installed: bytearray,
    patch_mode: str,
) -> list[dict[str, str]]:
    """Remove the VV5 Running overlay and require the exact parent restoration."""
    if patch_mode != "collection_progression":
        raise PatcherError("VV5 Running supports Collection Progression only.")
    feature = FunPatch(json.loads(VV5_INDIVIDUAL_RUNNING_CANDIDATE_PATHS["manifest"].read_text(encoding="utf-8")))
    _validate_vv5_individual_running_candidate(feature, {feature.id}, patch_mode)
    removed = _remove_feature_bytes(installed, feature, patch_mode)
    expected = VV5_INDIVIDUAL_RUNNING_PARENT_SHA256[patch_mode]
    if hashlib.sha256(installed).hexdigest().upper() != expected:
        raise PatcherError("VV5 Running removal did not restore the exact composed parent.")
    return removed


def _result(
    build: Build,
    source: Path,
    patch_mode: str,
    patched: bytearray,
    applied: list[dict[str, str]],
    fun_patches: list[FunPatch],
    output_root: Path | None = None,
) -> dict[str, Any]:
    mode = get_patch_mode(patch_mode)
    variant = get_patch_variant(build, patch_mode)
    villager_slots = variant.get("villager_slots", build.villager_slots)
    absolute_maximum = variant.get("absolute_maximum", build.absolute_maximum)
    output_name = _output_name(build, patch_mode, fun_patches)
    output_folder = output_folder_for(
        source, build, patch_mode, fun_patches, output_root
    )
    result_sha256 = hashlib.sha256(patched).hexdigest().upper()
    if patch_mode == "stock":
        multiple_birth_saturation = (
            "stock multiple-birth behavior is preserved; no population-cap saturation guard is applied"
        )
        island_event_capacity = (
            "stock population-adding Island Event behavior is preserved; no population-cap guard is applied"
        )
    else:
        multiple_birth_saturation = (
            "multiples are reduced only when required to fit the remaining villager slots"
        )
        island_event_capacity = (
            "population-adding Island Events are blocked or reduced only as required to fit the remaining physical villager slots"
        )
    return {
        "game": build.title,
        "source": str(source.resolve()),
        "patch_mode": mode.id,
        "patch_mode_name": mode.name,
        "output_name": output_name,
        "output_folder": str(output_folder),
        "output_path": str(output_folder / output_name),
        "fun_patches": [patch.id for patch in fun_patches],
        "fun_patch_names": [patch.name for patch in fun_patches],
        "playtest_only": any(
            patch.raw.get("playtest_only") is True for patch in fun_patches
        ),
        "playtest_status": next(
            (
                patch.raw.get("playtest_status")
                for patch in fun_patches
                if patch.raw.get("playtest_only") is True
            ),
            None,
        ),
        "absolute_maximum": absolute_maximum,
        "villager_slots": villager_slots,
        "experimental_expanded_records": variant.get("expanded_records", False),
        "save_compatibility": (
            "expanded experimental layout with guarded stock-layout import in the modified executable's separate save folder"
            if variant.get("expanded_records", False)
            else "stock save layout"
        ),
        "population_increase": variant.get("population_increase", True),
        "multiple_birth_saturation": multiple_birth_saturation,
        "island_event_capacity": island_event_capacity,
        "bonuses_affect_maximum": variant["bonuses_affect_maximum"],
        "patches": applied,
        "expanded_static_repairs": _expanded_static_repair_summary(
            applied, result_sha256
        ),
        "expanded_atomic_writers": _expanded_atomic_writer_summary(
            applied, result_sha256
        ),
        "result_sha256": result_sha256,
    }


def _reject_vv5_running_unsupported_mode(
    patch_mode: str, fun_patch_ids: tuple[str, ...] | list[str]
) -> None:
    """Reject VV5 Running before any source/catalog/filesystem work."""
    if patch_mode != "collection_progression" and any(
        str(patch_id) == "vv5_individual_grant_running_candidate"
        for patch_id in fun_patch_ids
    ):
        raise PatcherError(
            "VV5 individual Grant Running supports Collection Progression only; "
            "Immediate and Expanded are fail-closed before input access."
        )


def _validate_playtest_output_request(
    *,
    fun_patch_ids: tuple[str, ...] | list[str],
    playtest_disabled_feature_ids: tuple[str, ...] | list[str],
    output_root: Path | None,
    playtest_output_root: Path | None,
    copy_saves: bool = False,
    replace_modded_saves: bool = False,
    save_root: Path | None = None,
) -> None:
    """Keep mixed catalog/withdrawn selections in a separate save-free root."""
    feature_ids = tuple(playtest_disabled_feature_ids)
    time_warp_ids = frozenset(EXPANDED_TIME_WARP_IDS.values())
    selected_time_warp_ids = tuple(
        feature_id for feature_id in feature_ids if feature_id in time_warp_ids
    )
    if selected_time_warp_ids:
        if len(feature_ids) != 1 or len(selected_time_warp_ids) != 1:
            raise PatcherError(
                "Expanded Time Warp playtests require exactly one hidden Time Warp feature ID."
            )
        if playtest_output_root is None:
            raise PatcherError(
                "Expanded Time Warp playtests require --playtest-output-root."
            )
        if output_root is not None:
            raise PatcherError(
                "Expanded Time Warp playtests cannot use --output-root."
            )
        if not Path(playtest_output_root).expanduser().is_absolute():
            raise PatcherError("--playtest-output-root must be an absolute path.")
    if playtest_output_root is not None:
        if not feature_ids:
            raise PatcherError(
                "--playtest-output-root requires --playtest-disabled-feature."
            )
        if output_root is not None:
            raise PatcherError(
                "--playtest-output-root cannot be combined with --output-root."
            )
        if not Path(playtest_output_root).expanduser().is_absolute():
            raise PatcherError("--playtest-output-root must be an absolute path.")
    elif feature_ids and fun_patch_ids:
        raise PatcherError(
            "Playtest-disabled features cannot be combined with catalog fun patches "
            "without a distinct explicit playtest output root."
        )
    elif feature_ids and output_root is None:
        raise PatcherError("Playtest-disabled features require an explicit output root.")
    if feature_ids and (copy_saves or replace_modded_saves or save_root is not None):
        raise PatcherError(
            "Playtest-disabled features cannot copy or replace saves or use a save root."
        )


def _validate_playtest_feature_channels(
    fun_patch_ids: tuple[str, ...] | list[str],
    playtest_disabled_feature_ids: tuple[str, ...] | list[str],
) -> None:
    """Keep hidden Time Warp IDs out of the ordinary API selection channel."""
    time_warp_ids = frozenset(EXPANDED_TIME_WARP_IDS.values())
    ordinary = set(fun_patch_ids) & time_warp_ids
    hidden = set(playtest_disabled_feature_ids) & time_warp_ids
    overlap = ordinary & hidden
    if overlap:
        raise PatcherError(
            "Expanded Time Warp cannot be selected through both normal and hidden "
            "playtest arguments."
        )
    if ordinary:
        raise PatcherError(
            "Expanded Time Warp is unavailable through normal fun-patch selection; "
            "use exactly one hidden playtest feature argument."
        )


def _validate_single_playtest_patch_mode(
    patch_mode: str,
    *,
    playtest_disabled_feature_ids: tuple[str, ...] | list[str],
    output_root: Path | None,
    playtest_output_root: Path | None,
    copy_saves: bool = False,
    replace_modded_saves: bool = False,
    save_root: Path | None = None,
) -> None:
    """Keep the public gate closed except for one exact Time Warp playtest."""
    if not isinstance(patch_mode, str) or patch_mode not in _PUBLIC_PATCH_MODES:
        raise PatcherError(f"Unknown patch mode: {patch_mode}")


def dry_run(
    source: Path,
    patch_mode: str = DEFAULT_PATCH_MODE,
    fun_patch_ids: tuple[str, ...] | list[str] = (),
    output_root: Path | None = None,
    playtest_disabled_feature_ids: tuple[str, ...] | list[str] = (),
    *,
    playtest_output_root: Path | None = None,
) -> dict[str, Any]:
    _reject_vv5_running_unsupported_mode(patch_mode, fun_patch_ids)
    _validate_playtest_feature_channels(
        fun_patch_ids, playtest_disabled_feature_ids
    )
    _validate_playtest_output_request(
        fun_patch_ids=fun_patch_ids,
        playtest_disabled_feature_ids=playtest_disabled_feature_ids,
        output_root=output_root,
        playtest_output_root=playtest_output_root,
    )
    _validate_single_playtest_patch_mode(
        patch_mode,
        playtest_disabled_feature_ids=playtest_disabled_feature_ids,
        output_root=output_root,
        playtest_output_root=playtest_output_root,
    )
    build = identify(source)
    fun_patches = _selected_fun_patches(build, fun_patch_ids)
    fun_patches.extend(
        _selected_playtest_disabled_fun_patches(
            build, playtest_disabled_feature_ids, patch_mode
        )
    )
    patched, applied = render_patched_bytes(
        source,
        build,
        patch_mode,
        fun_patch_ids,
        playtest_disabled_feature_ids=playtest_disabled_feature_ids,
        playtest_output_root=playtest_output_root,
    )
    return _result(
        build,
        source,
        patch_mode,
        patched,
        applied,
        fun_patches,
        playtest_output_root if playtest_output_root is not None else output_root,
    )


def dry_run_all(
    sources: dict[str, Path],
    patch_mode: str = DEFAULT_PATCH_MODE,
    fun_patch_ids: tuple[str, ...] | list[str] = (),
    output_root: Path | None = None,
) -> list[dict[str, Any]]:
    _validate_public_patch_mode(patch_mode)
    _reject_vv5_running_unsupported_mode(patch_mode, fun_patch_ids)
    validated = validate_all_sources(sources)
    results = []
    for build, source in validated:
        selected_ids = [
            patch_id
            for patch_id in fun_patch_ids
            if get_fun_patch(patch_id).game_id == build.id
        ]
        fun_patches = _selected_fun_patches(build, selected_ids)
        patched, applied = render_patched_bytes(source, build, patch_mode, selected_ids)
        results.append(
            _result(
                build,
                source,
                patch_mode,
                patched,
                applied,
                fun_patches,
                output_root,
            )
        )
    return results


def _log_data(
    build: Build,
    source: Path,
    output: Path,
    patch_mode: str,
    output_hash: str,
    applied: list[dict[str, str]],
    fun_patches: list[FunPatch],
) -> dict[str, Any]:
    mode = get_patch_mode(patch_mode)
    variant = get_patch_variant(build, patch_mode)
    villager_slots = variant.get("villager_slots", build.villager_slots)
    absolute_maximum = variant.get("absolute_maximum", build.absolute_maximum)
    if patch_mode == "stock":
        multiple_birth_saturation = (
            "stock multiple-birth behavior is preserved; no population-cap saturation guard is applied"
        )
        island_event_capacity = (
            "stock population-adding Island Event behavior is preserved; no population-cap guard is applied"
        )
    else:
        multiple_birth_saturation = (
            "multiples are reduced only when required to fit the remaining villager slots"
        )
        island_event_capacity = (
            "population-adding Island Events are blocked or reduced only as required to fit the remaining physical villager slots"
        )
    return {
        "patcher": "Virtual Villagers Fun Patcher",
        "patch": mode.name,
        "patch_mode": mode.id,
        "patch_mode_name": mode.name,
        "fun_patches": [patch.id for patch in fun_patches],
        "fun_patch_names": [patch.name for patch in fun_patches],
        "playtest_only": any(
            patch.raw.get("playtest_only") is True for patch in fun_patches
        ),
        "playtest_status": next(
            (
                patch.raw.get("playtest_status")
                for patch in fun_patches
                if patch.raw.get("playtest_only") is True
            ),
            None,
        ),
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "game": build.title,
        "absolute_maximum": absolute_maximum,
        "villager_slots": villager_slots,
        "experimental_expanded_records": variant.get("expanded_records", False),
        "save_compatibility": (
            "expanded experimental layout with guarded stock-layout import in the modified executable's separate save folder"
            if variant.get("expanded_records", False)
            else "stock save layout"
        ),
        "population_increase": variant.get("population_increase", True),
        "multiple_birth_saturation": multiple_birth_saturation,
        "island_event_capacity": island_event_capacity,
        "bonuses_affect_maximum": variant["bonuses_affect_maximum"],
        "source_path": str(source.resolve()),
        "source_sha256": build.sha256,
        "output_path": str(output),
        "output_sha256": output_hash,
        "expanded_static_repairs": _expanded_static_repair_summary(
            applied, output_hash
        ),
        "expanded_atomic_writers": _expanded_atomic_writer_summary(
            applied, output_hash
        ),
        "patches": applied,
    }


def _copy_game_folder_direct(
    source_folder: Path,
    destination: Path,
    overwrite: bool,
    output_root: Path | None = None,
) -> None:
    source_resolved = source_folder.resolve()
    destination_resolved = destination.resolve()
    expected_parent = (
        Path(output_root).expanduser().resolve()
        if output_root is not None
        else source_resolved.parent
    )
    if destination_resolved.parent != expected_parent:
        raise PatcherError(
            "Internal safety check failed: output is outside the selected output folder"
        )
    if destination_resolved == source_resolved:
        raise PatcherError(
            "Internal safety check failed: output would replace the original folder"
        )
    try:
        expected_parent.relative_to(source_resolved)
    except ValueError:
        pass
    else:
        raise PatcherError(
            "Internal safety check failed: output folder cannot be inside the original game folder"
        )
    existed = destination.exists()
    if existed and not overwrite:
        raise PatcherError(f"Modified game folder already exists: {destination}")
    try:
        expected_parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            source_folder,
            destination,
            copy_function=shutil.copy2,
            dirs_exist_ok=overwrite,
        )
        for source_path in source_folder.rglob("*"):
            if not source_path.is_file():
                continue
            copied_path = destination / source_path.relative_to(source_folder)
            if (
                not copied_path.is_file()
                or copied_path.stat().st_size != source_path.stat().st_size
                or sha256(copied_path) != sha256(source_path)
            ):
                raise PatcherError(
                    "Verification failed while copying the complete game folder: "
                    f"{source_folder}"
                )
    except Exception:
        if not existed and destination.exists():
            shutil.rmtree(destination, ignore_errors=True)
        raise


def _copy_companion_files(
    output_folder: Path, fun_patches: list[FunPatch]
) -> list[dict[str, str]]:
    copied: list[dict[str, str]] = []
    root = ROOT.resolve()
    for feature in fun_patches:
        for item in feature.raw.get("companion_files", []):
            source, generated_temp = _vv4_generated_companion_path(item)
            try:
                source.relative_to(root)
            except ValueError as exc:
                if generated_temp is None:
                    raise PatcherError(
                        f"Companion file escapes the patcher folder: {source}"
                    ) from exc
            try:
                destination_name = _safe_companion_destination(item["destination"])
                if not source.is_file():
                    raise PatcherError(f"Required companion file is missing: {source}")
                expected_hash = item["sha256"].upper()
                preimage_hash = str(item.get("preimage_sha256", "")).upper() or None
                if preimage_hash:
                    destination = output_folder / destination_name
                    if not destination.is_file() or sha256(destination) != preimage_hash:
                        raise PatcherError(
                            f"Companion replacement preimage mismatch: {destination}"
                        )
                if sha256(source) != expected_hash:
                    raise PatcherError(f"Companion file hash mismatch: {source.name}")
                destination = output_folder / destination_name
                _atomic_companion_replace(
                    source,
                    destination,
                    source_hash=expected_hash,
                    preimage_hash=preimage_hash,
                    feature_id=feature.id,
                )
                copied.append(
                    {
                        "feature": feature.id,
                        "path": str(destination),
                        "sha256": expected_hash,
                        **({"preimage_sha256": preimage_hash, "restore_sha256": str(item["restore_sha256"]).upper()} if preimage_hash else {}),
                    }
                )
            finally:
                if generated_temp is not None:
                    generated_temp.cleanup()
    return copied


def _companion_relative_destination(path: Path, output_folder: Path) -> tuple[Path, str]:
    """Return a normalized full relative destination and its comparison key.

    Companion records may be absolute while a tree is staged.  Verification
    must retain directory identity (``a/X.dll`` and ``b/X.dll`` are distinct)
    and only collapse repeated writes to the same normalized destination.
    """
    root = Path(output_folder).resolve()
    candidate = Path(path)
    try:
        relative = Path(os.path.relpath(str(candidate), str(root)))
    except (OSError, ValueError) as exc:
        raise PatcherError(f"Companion destination cannot be normalized: {path}") from exc
    if relative.is_absolute() or ".." in relative.parts:
        raise PatcherError(f"Companion destination escapes output folder: {path}")
    normalized = Path(*[part for part in relative.parts if part not in ("", ".")])
    if not normalized.parts:
        raise PatcherError(f"Companion destination is empty: {path}")
    return normalized, normalized.as_posix().casefold()


def _verify_final_companion_records(
    output_folder: Path, records: list[dict[str, str]]
) -> None:
    """Verify only the final writer for each complete relative destination.

    Intermediate records are still validated while staging.  At publication,
    repeated records for one destination are intentionally reduced to the last
    writer; records in different directories remain independent.
    """
    final: dict[str, tuple[Path, dict[str, str]]] = {}
    for item in records:
        relative, key = _companion_relative_destination(Path(item["path"]), output_folder)
        final[key] = (relative, item)
    for relative, item in final.values():
        destination = Path(output_folder) / relative
        expected = str(item["sha256"]).upper()
        if not destination.is_file() or sha256(destination) != expected:
            raise PatcherError(
                f"Post-publish companion verification failed: {relative.as_posix()}"
            )
        if "size" in item and destination.stat().st_size != int(item["size"]):
            raise PatcherError(
                f"Post-publish companion size verification failed: {relative.as_posix()}"
            )


def _capture_tree_records(root: Path) -> list[dict[str, Any]]:
    snapshot = _capture_tree_snapshot(root)
    return [
        {
            "relative_path": item["relative_path"],
            "original_path": str(Path(root) / item["relative_path"]),
            "sha256": item["sha256"],
            "size": item["size"],
        }
        for item in snapshot.get("entries", [])
        if item.get("type") == "file"
    ]


def _tree_records_match(root: Path, records: list[dict[str, Any]]) -> bool:
    if not records and not os.path.lexists(root):
        return True
    if not records and os.path.lexists(root):
        try:
            snapshot = _capture_tree_snapshot(root)
        except PatcherError:
            return False
        return not snapshot.get("entries")
    try:
        snapshot = _capture_tree_snapshot(root)
    except PatcherError:
        return False
    expected = {str(item["relative_path"]): item for item in records}
    actual = {
        str(item["relative_path"]): item
        for item in snapshot.get("entries", [])
        if item.get("type") == "file"
    }
    if set(actual) != set(expected):
        return False
    return all(
        str(item.get("sha256", "")).upper() == str(expected[rel]["sha256"]).upper()
        and int(item.get("size", -1)) == int(expected[rel]["size"])
        for rel, item in actual.items()
    )


def _read_recovery_file(path: Path) -> tuple[bytes, os.stat_result]:
    """Read one owned recovery file with no-follow identity checks."""
    path = Path(path)
    try:
        before = os.lstat(path)
    except OSError as exc:
        raise PatcherError(f"Recovery file cannot be inspected: {path}") from exc
    attrs = int(getattr(before, "st_file_attributes", 0))
    junction = False
    if hasattr(path, "is_junction"):
        try:
            junction = bool(path.is_junction())
        except OSError:
            junction = True
    if attrs & 0x400 or stat.S_ISLNK(before.st_mode) or junction or not stat.S_ISREG(before.st_mode):
        raise PatcherError(f"Recovery file is not a regular non-reparse file: {path}")
    flags = os.O_RDONLY | int(getattr(os, "O_BINARY", 0)) | int(getattr(os, "O_NOFOLLOW", 0))
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise PatcherError(f"Recovery file cannot be opened without following links: {path}") from exc
    try:
        opened = os.fstat(fd)
        if (before.st_dev, before.st_ino, before.st_size) != (opened.st_dev, opened.st_ino, opened.st_size):
            raise PatcherError(f"Recovery file changed before hashing: {path}")
        with os.fdopen(fd, "rb", closefd=True) as handle:
            fd = -1
            data = handle.read()
            after_open = os.fstat(handle.fileno())
        if (before.st_dev, before.st_ino, before.st_size) != (
            after_open.st_dev, after_open.st_ino, after_open.st_size
        ) or len(data) != before.st_size:
            raise PatcherError(f"Recovery file changed while hashing: {path}")
    finally:
        if fd != -1:
            os.close(fd)
    try:
        after = os.lstat(path)
    except OSError as exc:
        raise PatcherError(f"Recovery file disappeared after hashing: {path}") from exc
    if (before.st_dev, before.st_ino, before.st_size) != (after.st_dev, after.st_ino, after.st_size):
        raise PatcherError(f"Recovery file changed after hashing: {path}")
    return data, before


def _capture_tree_snapshot(root: Path) -> dict[str, Any]:
    """Capture a complete tree with explicit no-follow enumeration."""
    root = Path(root)
    if not os.path.lexists(root):
        return {"exists": False, "entries": []}

    def reject_entry(path: Path, info: os.stat_result) -> None:
        attrs = int(getattr(info, "st_file_attributes", 0))
        junction = False
        if hasattr(path, "is_junction"):
            try:
                junction = bool(path.is_junction())
            except OSError:
                junction = True
        if attrs & 0x400 or stat.S_ISLNK(info.st_mode) or junction:
            raise PatcherError(f"Reparse/symlink entry rejected: {path}")

    try:
        root_info = os.lstat(root)
    except OSError as exc:
        raise PatcherError(f"Cannot inspect snapshot root: {root}") from exc
    reject_entry(root, root_info)
    if not stat.S_ISDIR(root_info.st_mode):
        raise PatcherError(f"Destination snapshot root is not a directory: {root}")

    entries: list[dict[str, Any]] = []
    seen: set[str] = set()

    def walk(directory: Path, relative_parent: str = "") -> None:
        try:
            before_directory = os.lstat(directory)
        except OSError as exc:
            raise PatcherError(f"Cannot inspect snapshot directory: {directory}") from exc
        reject_entry(directory, before_directory)
        if not stat.S_ISDIR(before_directory.st_mode):
            raise PatcherError(f"Snapshot directory changed type: {directory}")
        try:
            with os.scandir(directory) as scan:
                children = sorted(list(scan), key=lambda item: (item.name.casefold(), item.name))
                for entry in children:
                    rel = f"{relative_parent}/{entry.name}" if relative_parent else entry.name
                    normalized = Path(rel).as_posix().casefold()
                    if not normalized or normalized in seen or Path(rel).is_absolute() or ".." in Path(rel).parts:
                        raise PatcherError(f"Unsafe or colliding snapshot path: {rel}")
                    seen.add(normalized)
                    try:
                        # DirEntry.stat on Windows may expose zero file
                        # identity fields; lstat is the authoritative no-follow
                        # identity used for the before/after race check.
                        before = os.lstat(entry.path)
                    except OSError as exc:
                        raise PatcherError(f"Cannot inspect snapshot entry: {entry.path}") from exc
                    reject_entry(Path(entry.path), before)
                    if stat.S_ISDIR(before.st_mode):
                        entries.append({"relative_path": rel.replace("\\", "/"), "type": "dir"})
                        walk(Path(entry.path), rel)
                    elif stat.S_ISREG(before.st_mode):
                        flags = os.O_RDONLY | int(getattr(os, "O_BINARY", 0)) | int(getattr(os, "O_NOFOLLOW", 0))
                        try:
                            fd = os.open(entry.path, flags)
                        except OSError as exc:
                            raise PatcherError(f"Cannot open snapshot file without following links: {entry.path}") from exc
                        try:
                            opened = os.fstat(fd)
                            if (before.st_dev, before.st_ino, before.st_size) != (
                                opened.st_dev, opened.st_ino, opened.st_size
                            ) or not stat.S_ISREG(opened.st_mode):
                                raise PatcherError(f"Snapshot file identity changed before hashing: {entry.path}")
                            with os.fdopen(fd, "rb", closefd=True) as handle:
                                fd = -1
                                data = handle.read()
                                after_open = os.fstat(handle.fileno())
                            if (before.st_dev, before.st_ino, before.st_size) != (
                                after_open.st_dev, after_open.st_ino, after_open.st_size
                            ) or not stat.S_ISREG(after_open.st_mode):
                                raise PatcherError(f"Snapshot file identity changed while hashing: {entry.path}")
                        finally:
                            if fd != -1:
                                os.close(fd)
                        try:
                            after = os.lstat(entry.path)
                        except OSError as exc:
                            raise PatcherError(f"Snapshot entry disappeared: {entry.path}") from exc
                        reject_entry(Path(entry.path), after)
                        if (before.st_dev, before.st_ino, before.st_size) != (
                            after.st_dev, after.st_ino, after.st_size
                        ) or len(data) != before.st_size:
                            raise PatcherError(f"Snapshot entry changed during hashing: {entry.path}")
                        entries.append(
                            {
                                "relative_path": rel.replace("\\", "/"),
                                "type": "file",
                                "size": len(data),
                                "sha256": hashlib.sha256(data).hexdigest().upper(),
                            }
                        )
                    else:
                        raise PatcherError(f"Unsupported snapshot entry type: {entry.path}")
            after_directory = os.lstat(directory)
            reject_entry(directory, after_directory)
            if (before_directory.st_dev, before_directory.st_ino, before_directory.st_mode) != (
                after_directory.st_dev, after_directory.st_ino, after_directory.st_mode
            ):
                raise PatcherError(f"Snapshot directory identity changed during enumeration: {directory}")
        except OSError as exc:
            raise PatcherError(f"Cannot enumerate snapshot directory: {directory}") from exc

    walk(root)
    return {"exists": True, "entries": entries}


_PLAYTEST_SAVE_SUFFIXES = {".ldw", ".sav", ".save", ".savegame"}
_PLAYTEST_SAVE_PARTS = {"save", "saves", "savegames", "savedgames"}


def _validate_time_warp_playtest_source_tree(source_folder: Path) -> None:
    """Reject save-like or reparse content before hidden playtest staging."""
    snapshot = _capture_tree_snapshot(source_folder)
    if not snapshot.get("exists"):
        raise PatcherError("Expanded Time Warp playtest source folder is unavailable.")
    for entry in snapshot.get("entries", []):
        relative = str(entry.get("relative_path", ""))
        path = Path(relative)
        parts = {part.casefold() for part in path.parts}
        if (
            parts & _PLAYTEST_SAVE_PARTS
            or (
                entry.get("type") == "file"
                and path.suffix.casefold() in _PLAYTEST_SAVE_SUFFIXES
            )
        ):
            raise PatcherError(
                f"Expanded Time Warp playtest source contains save-like content: {relative}"
            )


def _tree_snapshot_matches(root: Path, snapshot: dict[str, Any]) -> bool:
    try:
        actual = _capture_tree_snapshot(root)
    except PatcherError:
        return False
    expected = {str(item["relative_path"]): item for item in snapshot.get("entries", [])}
    got = {str(item["relative_path"]): item for item in actual.get("entries", [])}
    if bool(actual.get("exists")) != bool(snapshot.get("exists")) or set(expected) != set(got):
        return False
    for rel, item in expected.items():
        current = got[rel]
        if item.get("type") != current.get("type"):
            return False
        if item.get("type") == "file" and (
            int(item.get("size", -1)) != int(current.get("size", -2))
            or str(item.get("sha256", "")).upper() != str(current.get("sha256", "")).upper()
        ):
            return False
    return True


def _cleanup_owned_tree(root: Path) -> None:
    """Remove an inventory-owned tree bottom-up without following links."""
    root = Path(root)
    if not os.path.lexists(root):
        return

    def reject(path: Path, info: os.stat_result) -> None:
        attrs = int(getattr(info, "st_file_attributes", 0))
        junction = bool(path.is_junction()) if hasattr(path, "is_junction") else False
        if attrs & 0x400 or stat.S_ISLNK(info.st_mode) or junction:
            raise PatcherError(f"Owned cleanup encountered reparse/symlink: {path}")

    root_info = os.lstat(root)
    reject(root, root_info)
    if not stat.S_ISDIR(root_info.st_mode):
        raise PatcherError(f"Owned cleanup root is not a directory: {root}")

    def remove_dir(directory: Path) -> None:
        before_dir = os.lstat(directory)
        reject(directory, before_dir)
        if not stat.S_ISDIR(before_dir.st_mode):
            raise PatcherError(f"Owned cleanup directory changed type: {directory}")
        with os.scandir(directory) as scan:
            children = sorted(list(scan), key=lambda item: (item.name.casefold(), item.name))
        for entry in children:
            path = Path(entry.path)
            before = os.lstat(path)
            reject(path, before)
            if stat.S_ISDIR(before.st_mode):
                remove_dir(path)
                after = os.lstat(path)
                reject(path, after)
                if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
                    raise PatcherError(f"Owned cleanup directory identity changed: {path}")
                path.rmdir()
            elif stat.S_ISREG(before.st_mode):
                after = os.lstat(path)
                reject(path, after)
                if (before.st_dev, before.st_ino, before.st_size) != (after.st_dev, after.st_ino, after.st_size):
                    raise PatcherError(f"Owned cleanup file changed: {path}")
                path.unlink()
            else:
                raise PatcherError(f"Owned cleanup encountered unsupported type: {path}")
        after_dir = os.lstat(directory)
        reject(directory, after_dir)
        if (before_dir.st_dev, before_dir.st_ino) != (after_dir.st_dev, after_dir.st_ino):
            raise PatcherError(f"Owned cleanup root identity changed: {directory}")

    remove_dir(root)
    root.rmdir()


def _write_recovery_report(
    recovery_dir: Path,
    operation: str,
    records: list[dict[str, Any]],
    backup_root: Path | None,
    *,
    destination_root: Path | None = None,
    destination_snapshot: dict[str, Any] | None = None,
    restored_snapshot: dict[str, Any] | None = None,
    destination_precondition: dict[str, Any] | None = None,
    staged_copy_root: Path | None = None,
    failed_publication_root: Path | None = None,
) -> Path:
    recovery_dir.mkdir(parents=True, exist_ok=True)
    if destination_root is None or destination_precondition is None or destination_snapshot is None:
        raise PatcherError("Strict recovery report requires destination state snapshots.")
    if operation not in {"install", "remove"}:
        raise PatcherError("Unsupported recovery report operation.")
    # The v3 operation names are deliberately distinct from the old generic
    # install/remove aliases.  The operation is derived from the immutable
    # pre-mutation destination state, never from a failure-time tree.
    if operation == "remove":
        report_operation = "removal"
    elif destination_precondition.get("exists"):
        report_operation = "install_existing"
    else:
        report_operation = "install_new"

    def relative_owned(path: Path | None) -> str | None:
        if path is None or not os.path.lexists(path):
            return None
        try:
            return Path(path).absolute().relative_to(recovery_dir.absolute()).as_posix()
        except ValueError as exc:
            raise PatcherError("Recovery report attempted to record an old or foreign sibling path.") from exc

    def owned_snapshot(path: Path | None) -> dict[str, Any] | None:
        return _capture_tree_snapshot(path) if path is not None and os.path.lexists(path) else None

    members: list[dict[str, Any]] = []
    for item in records:
        rel = str(item["relative_path"])
        backup_path = (
            Path(str(item["backup_path"]))
            if item.get("backup_path")
            else ((backup_root / rel) if backup_root is not None else None)
        )
        if backup_path is not None and not os.path.lexists(backup_path):
            raise PatcherError("Recovery report backup member is missing at final retained location.")
        backup_data = _read_recovery_file(backup_path)[0] if backup_path is not None else None
        members.append(
            {
                "original_path": item.get("original_path"),
                "original_sha256": item.get("sha256"),
                "original_size": item.get("size"),
                "backup_relative_path": (
                    relative_owned(backup_path) if backup_path is not None else None
                ),
                "backup_sha256": (
                    hashlib.sha256(backup_data).hexdigest().upper() if backup_data is not None else None
                ),
                "backup_size": len(backup_data) if backup_data is not None else None,
                "relative_path": rel,
            }
        )
    report = recovery_dir / "recovery-report.json"
    backup_rel = relative_owned(backup_root)
    failed_rel = relative_owned(failed_publication_root)
    stage_rel = relative_owned(staged_copy_root)
    ownership = {
        "recovery_root": ".",
        "report_path": "recovery-report.json",
        "original_backup_root": {"path": backup_rel, "snapshot": owned_snapshot(backup_root)},
        "failed_publication_root": {"path": failed_rel, "snapshot": owned_snapshot(failed_publication_root)},
        "retained_removal_stage_root": {"path": stage_rel, "snapshot": owned_snapshot(staged_copy_root)},
        "replay_stage_root": {"path": None, "snapshot": {"exists": False, "entries": []}},
    }
    owned_files: list[str] = []
    for root_path in (backup_root, failed_publication_root, staged_copy_root):
        if root_path is not None and os.path.lexists(root_path):
            snap = _capture_tree_snapshot(root_path)
            owned_files.extend(
                f"{Path(relative_owned(root_path) or '.').as_posix().rstrip('./')}/{item['relative_path']}".strip("/")
                for item in snap.get("entries", [])
            )
    ownership["owned_files"] = sorted(set(owned_files))
    initial_state = (
        {"kind": "tree", "snapshot": destination_precondition}
        if destination_precondition.get("exists")
        else {"kind": "absent"}
    )
    retry_state = (
        {"kind": "tree", "snapshot": destination_snapshot}
        if destination_snapshot.get("exists")
        else {"kind": "absent"}
    )
    payload: dict[str, Any] = {
        "schema_version": 3,
        "operation": report_operation,
        "destination": {
            "root": str(destination_root),
            "initial_state": initial_state,
            "retry_state": retry_state,
            "failure_diagnostic": destination_snapshot,
        },
        "ownership": ownership,
        "members": members,
        "restored_state": restored_snapshot,
    }
    _atomic_write_recovery_json(report, payload)
    # Re-open and validate the exact emitted schema before returning it.
    report_bytes, _ = _read_recovery_file(report)
    _validate_vv4_recovery_payload(json.loads(report_bytes.decode("utf-8")), recovery_dir)
    return report


def _atomic_write_recovery_json(path: Path, payload: dict[str, Any]) -> None:
    """Write recovery evidence atomically without following untrusted paths."""
    path = Path(path)
    staged_report = path.parent / f".{path.name}-{uuid.uuid4().hex}.tmp"
    data = (json.dumps(payload, indent=2) + "\n").encode("utf-8")
    with staged_report.open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(staged_report, path)


def _validate_vv4_recovery_payload(payload: dict[str, Any], recovery_root: Path) -> None:
    """Strictly validate the v3 production recovery schema before replay."""
    if not isinstance(payload, dict):
        raise PatcherError("Recovery report is not an object.")
    required = {"schema_version", "operation", "destination", "ownership", "members", "restored_state"}
    if set(payload) != required or payload.get("schema_version") != 3:
        raise PatcherError("Recovery report schema is unsupported or ambiguous.")
    operation = payload.get("operation")
    if operation not in {"install_new", "install_existing", "removal"}:
        raise PatcherError("Recovery operation is unsupported.")
    destination = payload["destination"]
    if not isinstance(destination, dict) or set(destination) != {"root", "initial_state", "retry_state", "failure_diagnostic"}:
        raise PatcherError("Recovery destination contract is incomplete.")
    if not isinstance(destination["root"], str) or not destination["root"]:
        raise PatcherError("Recovery destination root is invalid.")

    def validate_state(value: Any, *, allow_absent: bool = True) -> None:
        if not isinstance(value, dict) or "kind" not in value:
            raise PatcherError("Recovery destination state is malformed.")
        kind = value["kind"]
        if kind == "absent":
            if set(value) != {"kind"}:
                raise PatcherError("Absent recovery destination state has extra fields.")
            if not allow_absent:
                raise PatcherError("Recovery destination state cannot be absent.")
        elif kind == "tree":
            if set(value) != {"kind", "snapshot"}:
                raise PatcherError("Tree recovery destination state has extra fields.")
            snap = value.get("snapshot")
            if not isinstance(snap, dict) or set(snap) != {"exists", "entries"} or not snap.get("exists"):
                raise PatcherError("Recovery tree state is malformed.")
        else:
            raise PatcherError("Recovery destination state kind is unsupported.")

    validate_state(destination["initial_state"])
    validate_state(destination["retry_state"])
    failure = destination["failure_diagnostic"]
    if not isinstance(failure, dict) or set(failure) != {"exists", "entries"}:
        raise PatcherError("Recovery failure diagnostic snapshot is malformed.")
    restored = payload["restored_state"]
    if restored is not None and (not isinstance(restored, dict) or set(restored) != {"exists", "entries"}):
        raise PatcherError("Recovery restored-state snapshot is malformed.")
    initial = destination["initial_state"]
    if operation == "install_new" and initial.get("kind") != "absent":
        raise PatcherError("install_new requires an immutable absent destination precondition.")
    if operation != "install_new" and initial.get("kind") != "tree":
        raise PatcherError("This recovery operation requires an immutable owned tree precondition.")

    ownership = payload["ownership"]
    ownership_keys = {
        "recovery_root", "report_path", "original_backup_root", "failed_publication_root",
        "retained_removal_stage_root", "replay_stage_root", "owned_files",
    }
    if not isinstance(ownership, dict) or set(ownership) != ownership_keys:
        raise PatcherError("Recovery ownership inventory is incomplete.")
    if ownership["recovery_root"] != "." or ownership["report_path"] != "recovery-report.json":
        raise PatcherError("Recovery ownership root/report relationship is invalid.")
    if not isinstance(ownership["owned_files"], list) or any(not isinstance(x, str) for x in ownership["owned_files"]):
        raise PatcherError("Recovery owned-file inventory is malformed.")

    def validate_owned_area(area: Any) -> None:
        if not isinstance(area, dict) or set(area) != {"path", "snapshot"}:
            raise PatcherError("Recovery owned-area inventory is malformed.")
        path = area["path"]
        snap = area["snapshot"]
        if path is None:
            if snap is not None and snap != {"exists": False, "entries": []}:
                raise PatcherError("Absent recovery owned area has a snapshot.")
            return
        rel = Path(str(path))
        if rel.is_absolute() or ".." in rel.parts or rel.as_posix().casefold() in {"", "."}:
            raise PatcherError("Recovery owned-area path is unsafe.")
        if not isinstance(snap, dict) or set(snap) != {"exists", "entries"} or not snap.get("exists"):
            raise PatcherError("Recovery owned-area snapshot is missing.")
        if not _tree_snapshot_matches(recovery_root / rel, snap):
            raise PatcherError("Recovery owned-area snapshot does not match disk.")

    for key in ("original_backup_root", "failed_publication_root", "retained_removal_stage_root", "replay_stage_root"):
        validate_owned_area(ownership[key])

    members = payload["members"]
    if not isinstance(members, list) or not members:
        raise PatcherError("Recovery report has no recoverable members.")
    member_keys = {"original_path", "original_sha256", "original_size", "backup_relative_path", "backup_sha256", "backup_size", "relative_path"}
    backup_area = ownership["original_backup_root"]["path"]
    seen: set[str] = set()
    for item in members:
        if not isinstance(item, dict) or set(item) != member_keys:
            raise PatcherError("Recovery member schema is malformed.")
        rel = Path(str(item["relative_path"]))
        key = rel.as_posix().casefold()
        if not key or key in seen or rel.is_absolute() or ".." in rel.parts:
            raise PatcherError("Recovery member path is unsafe or duplicated.")
        seen.add(key)
        backup_rel = item["backup_relative_path"]
        if backup_area is None or not isinstance(backup_rel, str):
            raise PatcherError("Recovery member has no owned backup path.")
        expected_backup = (Path(str(backup_area)) / Path(backup_rel).relative_to(Path(str(backup_area)))).as_posix()
        if expected_backup.casefold() not in {str(x).casefold() for x in ownership["owned_files"]}:
            raise PatcherError("Recovery member backup is absent from the ownership inventory.")
        if not isinstance(item["original_sha256"], str) or len(item["original_sha256"]) != 64:
            raise PatcherError("Recovery member hash is malformed.")

    # The root inventory may contain only declared owned areas plus the report;
    # any other descendant is foreign material and must remain untouched.
    root_snapshot = _capture_tree_snapshot(recovery_root)
    declared_prefixes = [
        str(area["path"]).rstrip("/")
        for area in ownership.values()
        if isinstance(area, dict) and "path" in area and area.get("path")
    ]
    for entry in root_snapshot.get("entries", []):
        rel = str(entry["relative_path"])
        if rel == "recovery-report.json":
            continue
        if not any(rel == prefix or rel.startswith(prefix + "/") for prefix in declared_prefixes):
            raise PatcherError("Recovery root contains unknown material.")


def _validate_recovery_root_no_follow(root: Path) -> None:
    """Validate the caller-supplied recovery root before opening its report."""
    try:
        info = os.lstat(root)
    except OSError as exc:
        raise PatcherError("Recovery root is missing or inaccessible.") from exc
    attrs = int(getattr(info, "st_file_attributes", 0))
    if attrs & 0x400 or stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise PatcherError("Recovery root is a reparse/symlink or wrong type.")
    if os.name == "nt":
        try:
            import ctypes
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            create = kernel32.CreateFileW
            create.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
            create.restype = ctypes.c_void_p
            close = kernel32.CloseHandle
            close.argtypes = [ctypes.c_void_p]
            handle = create(str(root), 0x80000000, 0x00000007, None, 3, 0x02000000 | 0x00200000, None)
            if handle in (None, ctypes.c_void_p(-1).value):
                raise PatcherError("Windows no-follow recovery root handle could not be opened.")
            try:
                get_attrs = kernel32.GetFileAttributesW
                get_attrs.argtypes = [ctypes.c_wchar_p]
                get_attrs.restype = ctypes.c_uint32
                win_attrs = int(get_attrs(str(root)))
                if win_attrs == 0xFFFFFFFF or win_attrs & 0x400:
                    raise PatcherError("Windows recovery root is reparse or inaccessible.")
            finally:
                close(handle)
        except PatcherError:
            raise
        except Exception as exc:
            raise PatcherError("Windows no-follow recovery root validation failed.") from exc


def _companion_hash_matches(path: Path, expected_hash: str) -> bool:
    return path.is_file() and sha256(path) == expected_hash.upper()


def _stage_companion_file(source: Path, destination_parent: Path, expected_hash: str) -> Path:
    """Copy and fsync one verified sibling stage file on the destination volume."""
    destination_parent.mkdir(parents=True, exist_ok=True)
    fd, raw_stage = tempfile.mkstemp(
        prefix=f".{source.name}.", suffix=".vvfp-stage", dir=str(destination_parent)
    )
    stage = Path(raw_stage)
    try:
        os.close(fd)
        shutil.copy2(source, stage)
        with stage.open("r+b") as handle:
            os.fsync(handle.fileno())
        if not _companion_hash_matches(stage, expected_hash):
            raise PatcherError(
                f"Companion staged verification failed: {stage}"
            )
        return stage
    except Exception:
        try:
            stage.unlink()
        except OSError:
            pass
        raise


def _vv4_generated_companion_path(item: dict[str, Any]) -> tuple[Path, tempfile.TemporaryDirectory | None]:
    """Materialize the VV4 candidate companion from the pinned builder only."""
    if item.get("source") != "generated:vv4_full_heal_companion":
        source = (ROOT / str(item["source"])).resolve()
        return source, None
    import importlib.util
    builder_path = ROOT / "scripts" / "build_vv4_full_heal_candidate.py"
    spec = importlib.util.spec_from_file_location("vv4_full_heal_builder_companion", builder_path)
    if spec is None or spec.loader is None:
        raise PatcherError("VV4 Full Heal companion builder is unavailable.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    base_path = ROOT / str(item["restore_source"])
    if not base_path.is_file() or sha256(base_path) != str(item["preimage_sha256"]).upper():
        raise PatcherError("VV4 Full Heal companion parent preimage is missing or corrupt.")
    candidate, digest = module.build_resource_only_companion(base_path.read_bytes())
    if digest != str(item["sha256"]).upper() or len(candidate) != int(item["size"]):
        raise PatcherError("VV4 Full Heal emitted companion identity is not pinned.")
    temp = tempfile.TemporaryDirectory(prefix="vv4-full-heal-companion-")
    path = Path(temp.name) / "VVFP Origins Icons.dll"
    path.write_bytes(candidate)
    return path, temp


def _atomic_companion_replace(
    source: Path,
    destination: Path,
    *,
    source_hash: str,
    preimage_hash: str | None,
    feature_id: str,
) -> None:
    """Atomically install/restore a companion while preserving a verified backup."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_hash = source_hash.upper()
    preimage_hash = preimage_hash.upper() if preimage_hash else None
    destination_exists = destination.exists()
    before_hash: str | None = None
    if preimage_hash:
        if not _companion_hash_matches(destination, preimage_hash):
            raise PatcherError(
                f"Companion replacement preimage mismatch: {destination}"
            )
        before_hash = preimage_hash
    elif destination_exists:
        if not destination.is_file():
            raise PatcherError(f"Companion destination is not a file: {destination}")
        before_hash = sha256(destination)

    stage: Path | None = None
    backup: Path | None = None
    replace_attempted = False
    replace_completed = False
    preserve_recovery = False
    try:
        stage = _stage_companion_file(source, destination.parent, source_hash)
        if destination_exists:
            backup = _stage_companion_file(destination, destination.parent, before_hash or sha256(destination))
        # Recheck immediately before the no-overwrite replace; a race must not
        # overwrite a foreign destination or consume the verified backup.
        if preimage_hash:
            if not _companion_hash_matches(destination, preimage_hash):
                raise PatcherError(
                    f"Companion replacement preimage changed before replace: {destination}"
                )
        elif destination_exists and not _companion_hash_matches(destination, before_hash or ""):
            raise PatcherError(
                f"Companion destination changed before replace: {destination}"
            )
        replace_attempted = True
        os.replace(stage, destination)
        stage = None
        replace_completed = True
        if not _companion_hash_matches(destination, source_hash):
            raise PatcherError(
                f"Companion post-replace verification failed: {destination}"
            )
        if backup is not None:
            backup.unlink()
            backup = None
    except Exception as exc:
        # If replacement happened (including an injected exception after the
        # replace), restore only from the already-verified sibling backup.
        replaced = replace_completed or (
            replace_attempted
            and destination.is_file()
            and sha256(destination) == source_hash
        )
        if replaced and backup is not None:
            try:
                os.replace(backup, destination)
                backup = None
                if before_hash is None or not destination.is_file() or sha256(destination) != before_hash:
                    raise PatcherError(
                        f"Companion rollback verification failed: {destination}"
                    )
            except Exception as rollback_exc:
                preserve_recovery = True
                raise PatcherError(
                    f"Companion replace failed and rollback is preserved for recovery at {backup}: {rollback_exc}"
                ) from exc
        elif (
            not destination_exists
            and (replace_completed or (destination.is_file() and sha256(destination) == source_hash))
        ):
            # No preimage existed; remove only our verified replacement.
            destination.unlink()
        raise
    finally:
        if stage is not None:
            try:
                stage.unlink()
            except OSError:
                pass
        if backup is not None and not preserve_recovery:
            try:
                backup.unlink()
            except OSError:
                pass


def _safe_companion_destination(destination: str) -> Path:
    """Allow owned subpaths while rejecting absolute/traversal destinations."""
    if not isinstance(destination, str) or not destination.strip():
        raise PatcherError("Companion destination must be a non-empty relative path")
    normalized = destination.replace("\\", "/")
    candidate = Path(normalized)
    if candidate.is_absolute() or any(part in {"", ".", ".."} for part in candidate.parts):
        raise PatcherError(f"Companion destination is unsafe: {destination}")
    return Path(*candidate.parts)


def _validate_companion_sources(fun_patches: list[FunPatch]) -> None:
    """Fail before any executable bytes are changed if a companion is absent/corrupt."""
    root = ROOT.resolve()
    for feature in fun_patches:
        for item in feature.raw.get("companion_files", []):
            expected_hash = str(item["sha256"]).upper()
            source, generated_temp = _vv4_generated_companion_path(item)
            try:
                if generated_temp is None:
                    try:
                        source.relative_to(root)
                    except ValueError as exc:
                        raise PatcherError(
                            f"Companion file escapes the patcher folder: {source}"
                        ) from exc
                if not source.is_file():
                    raise PatcherError(f"Required companion file is missing: {source}")
                actual_hash = sha256(source)
                if actual_hash != expected_hash:
                    raise PatcherError(
                        f"Companion file hash mismatch: {source.name}; "
                        f"expected {expected_hash}, got {actual_hash}"
                    )
                if item.get("source") == "generated:vv4_full_heal_companion":
                    if item.get("preimage_sha256") != item.get("restore_sha256"):
                        raise PatcherError("VV4 Full Heal companion restore identity is not exact.")
                    restore_source = (ROOT / str(item.get("restore_source", ""))).resolve()
                    if not restore_source.is_file() or sha256(restore_source) != str(item.get("restore_sha256", "")).upper():
                        raise PatcherError("VV4 Full Heal companion restore source is missing or corrupt.")
            finally:
                if generated_temp is not None:
                    generated_temp.cleanup()
            _safe_companion_destination(item["destination"])


def _remove_companion_files(
    output_folder: Path, fun_patches: list[FunPatch]
) -> list[dict[str, str]]:
    """Remove or restore exact companion bytes, refusing corruption/path escape."""
    removed: list[dict[str, str]] = []
    root = output_folder.resolve()
    pending: list[tuple[FunPatch, Path, str]] = []
    pending_restore: dict[Path, tuple[FunPatch, Path, str, str]] = {}
    for feature in reversed(fun_patches):
        for item in reversed(feature.raw.get("companion_files", [])):
            destination_name = _safe_companion_destination(item["destination"])
            destination = (root / destination_name).resolve()
            try:
                destination.relative_to(root)
            except ValueError as exc:
                raise PatcherError(f"Companion destination escapes output folder: {destination}") from exc
            if not destination.is_file():
                raise PatcherError(f"Companion removal guard failed; missing: {destination}")
            expected_hash = str(item["sha256"]).upper()
            actual_hash = sha256(destination)
            restore_hash = str(item.get("restore_sha256", "")).upper() or None
            if restore_hash:
                if actual_hash != expected_hash:
                    raise PatcherError(
                        f"Companion removal guard failed for {destination}: "
                        f"expected {expected_hash}, got {actual_hash}"
                    )
                restore_source = (ROOT / item["restore_source"]).resolve()
                try:
                    restore_source.relative_to(ROOT.resolve())
                except ValueError as exc:
                    raise PatcherError("Companion restore source escapes the patcher folder") from exc
                if not restore_source.is_file() or sha256(restore_source) != restore_hash:
                    raise PatcherError("Companion restore preimage is missing or corrupt")
                pending_restore[destination] = (feature, restore_source, restore_hash, expected_hash)
                continue
            if destination in pending_restore:
                # The dependent Full Heal entry owns the replacement and will
                # restore this shared dependency DLL before ordinary removal.
                continue
            if actual_hash != expected_hash:
                raise PatcherError(
                    f"Companion removal guard failed for {destination}: "
                    f"expected {expected_hash}, got {actual_hash}"
                )
            pending.append((feature, destination, expected_hash))
    for destination, (feature, restore_source, restore_hash, expected_hash) in pending_restore.items():
        _atomic_companion_replace(
            restore_source,
            destination,
            source_hash=restore_hash,
            preimage_hash=expected_hash,
            feature_id=feature.id,
        )
        removed.append(
            {
                "feature": feature.id,
                "path": str(destination),
                "sha256": restore_hash,
                "action": "restore",
            }
        )
    for feature, destination, expected_hash in pending:
        destination.unlink()
        parent = destination.parent
        while parent != root and parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent
        removed.append(
            {
                "feature": feature.id,
                "path": str(destination),
                "sha256": expected_hash,
            }
        )
    return removed


def apply_patch(
    source: Path,
    patch_mode: str = DEFAULT_PATCH_MODE,
    overwrite: bool = False,
    fun_patch_ids: tuple[str, ...] | list[str] = (),
    output_root: Path | None = None,
    copy_saves: bool = False,
    replace_modded_saves: bool = False,
    save_root: Path | None = None,
    playtest_disabled_feature_ids: tuple[str, ...] | list[str] = (),
    *,
    playtest_output_root: Path | None = None,
) -> tuple[Path, Path]:
    _reject_vv5_running_unsupported_mode(patch_mode, fun_patch_ids)
    _validate_playtest_feature_channels(
        fun_patch_ids, playtest_disabled_feature_ids
    )
    _validate_playtest_output_request(
        fun_patch_ids=fun_patch_ids,
        playtest_disabled_feature_ids=playtest_disabled_feature_ids,
        output_root=output_root,
        playtest_output_root=playtest_output_root,
        copy_saves=copy_saves,
        replace_modded_saves=replace_modded_saves,
        save_root=save_root,
    )
    _validate_single_playtest_patch_mode(
        patch_mode,
        playtest_disabled_feature_ids=playtest_disabled_feature_ids,
        output_root=output_root,
        playtest_output_root=playtest_output_root,
        copy_saves=copy_saves,
        replace_modded_saves=replace_modded_saves,
        save_root=save_root,
    )
    source = source.resolve()
    build = identify(source)
    fun_patches = _selected_fun_patches(build, fun_patch_ids)
    fun_patches.extend(
        _selected_playtest_disabled_fun_patches(
            build, playtest_disabled_feature_ids, patch_mode
        )
    )
    if any(
        patch.id in EXPANDED_TIME_WARP_IDS.values()
        and patch.raw.get("playtest_only") is True
        for patch in fun_patches
    ):
        _validate_time_warp_playtest_source_tree(source.parent)
    selected_output_root = (
        playtest_output_root if playtest_output_root is not None else output_root
    )
    output_name = _output_name(build, patch_mode, fun_patches)
    output_folder = output_folder_for(
        source, build, patch_mode, fun_patches, selected_output_root
    )
    output = output_folder / output_name
    if output_folder.exists() and not overwrite:
        raise PatcherError(f"Modified game folder already exists: {output_folder}")
    destination_precondition = _capture_tree_snapshot(output_folder)
    patched, applied = render_patched_bytes(
        source,
        build,
        patch_mode,
        fun_patch_ids,
        playtest_disabled_feature_ids=playtest_disabled_feature_ids,
        playtest_output_root=playtest_output_root,
    )
    output_parent = output_folder.parent
    if os.path.lexists(output_folder) and not overwrite:
        raise PatcherError(f"Modified game folder already exists: {output_folder}")
    staging_folder = output_parent / f".{output_folder.name}.staging-{uuid.uuid4().hex}"
    if os.path.lexists(staging_folder):
        raise PatcherError(f"Staging destination already exists: {staging_folder}")
    _copy_game_folder_direct(source.parent, staging_folder, False, selected_output_root)
    staged_output = staging_folder / output_name
    companions: list[dict[str, str]] = []
    log_path = staged_output.with_suffix(".patch-log.json")
    backup_folder: Path | None = None
    published = False
    original_records: list[dict[str, Any]] = []
    recovery_dir: Path | None = None
    failed_publish: Path | None = None
    try:
        companions = _copy_companion_files(staging_folder, fun_patches)
        converted: list[dict[str, str]] = []
        for item in companions:
            relative, _ = _companion_relative_destination(Path(item["path"]), staging_folder)
            converted.append({**item, "path": str(output_folder / relative)})
        companions = converted
        with staged_output.open("wb") as handle:
            handle.write(patched)
            handle.flush()
            os.fsync(handle.fileno())
        if staged_output.stat().st_size != len(patched):
            raise PatcherError("Verification failed: patched file size mismatch")
        output_hash = sha256(staged_output)
        expected_hash = hashlib.sha256(patched).hexdigest().upper()
        if output_hash != expected_hash:
            raise PatcherError("Verification failed: output hash mismatch")
        log_data = _log_data(
            build, source, staged_output, patch_mode, output_hash, applied, fun_patches
        )
        log_data["companion_files"] = companions
        save_copy: dict[str, Any] | None = None
        if copy_saves:
            save_copy = copy_vanilla_saves(
                build,
                patch_mode,
                replace_existing=replace_modded_saves,
                save_root=save_root,
            )
        write_transparency_artifacts(
            base_log=log_data,
            source=source,
            output=staged_output,
            source_folder=source.parent,
            output_folder=staging_folder,
            fun_patches=fun_patches,
            companions=companions,
            applied=applied,
            save_copy=save_copy,
            root=ROOT,
            json_path=log_path,
        )
        # Publish the complete EXE+DLL tree only after every staged product is
        # verified.  A prior destination is moved to a sibling backup and is
        # restored byte-for-byte on any rename/postverify failure.
        if os.path.lexists(output_folder):
            if not overwrite:
                raise PatcherError(f"Modified game folder appeared before publish: {output_folder}")
            # Preserve user-created files in an overwrite transaction while
            # still replacing the certified EXE/DLL pair as one tree.
            original_records = _capture_tree_records(output_folder)
            for prior in output_folder.rglob("*"):
                if not prior.is_file():
                    continue
                relative = prior.relative_to(output_folder)
                target = staging_folder / relative
                if target.exists():
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(prior, target)
            backup_folder = output_parent / f".{output_folder.name}.backup-{uuid.uuid4().hex}"
            if os.path.lexists(backup_folder):
                raise PatcherError(f"Backup destination already exists: {backup_folder}")
            os.rename(output_folder, backup_folder)
        if os.path.lexists(output_folder):
            raise PatcherError(f"Modified game folder appeared during publish: {output_folder}")
        os.rename(staging_folder, output_folder)
        published = True
        output = output_folder / output_name
        log_path = output.with_suffix(".patch-log.json")
        # The log is rendered before publication while the tree still has its
        # staging name.  Normalize the emitted output identity after the
        # atomic rename so consumers never observe a transient staging path.
        if log_path.is_file():
            published_log = json.loads(log_path.read_text(encoding="utf-8"))
            published_log["output_path"] = str(output)
            log_path.write_text(
                json.dumps(published_log, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        if not output.is_file() or sha256(output) != expected_hash:
            raise PatcherError("Post-publish executable verification failed")
        _verify_final_companion_records(output_folder, companions)
        if backup_folder is not None:
            if not _tree_records_match(backup_folder, original_records):
                raise PatcherError("Install backup verification failed before cleanup")
            _cleanup_owned_tree(backup_folder)
            backup_folder = None
    except Exception:
        restore_ok = True
        if published and output_folder.exists():
            failed_publish = output_parent / f".{output_folder.name}.failed-{uuid.uuid4().hex}"
            try:
                os.rename(output_folder, failed_publish)
                if failed_publish.exists():
                    # Keep the failed publication available until the prior
                    # tree is proven restored; it becomes recovery evidence if
                    # restoration cannot be completed.
                    pass
            except OSError:
                restore_ok = False
        elif staging_folder.exists():
            try:
                _cleanup_owned_tree(staging_folder)
            except OSError:
                restore_ok = False
        if backup_folder is not None and backup_folder.exists() and not output_folder.exists():
            try:
                os.rename(backup_folder, output_folder)
                if not _tree_records_match(output_folder, original_records):
                    restore_ok = False
                else:
                    _cleanup_owned_tree(output_folder.parent / backup_folder.name)
                    backup_folder = None
            except OSError:
                restore_ok = False
        if not restore_ok or (backup_folder is not None and backup_folder.exists()):
            recovery_dir = output_parent / f".{output_folder.name}.recovery-{uuid.uuid4().hex}"
            if os.path.lexists(recovery_dir):
                raise PatcherError("Recovery destination collision; original evidence retained")
            recovery_dir.mkdir()
            retained_backup = recovery_dir / "backup"
            if backup_folder is not None and backup_folder.exists():
                os.rename(backup_folder, retained_backup)
                backup_folder = None
            if failed_publish is not None and failed_publish.exists():
                os.rename(failed_publish, recovery_dir / "failed-publication")
                retained_failed_publish = recovery_dir / "failed-publication"
            else:
                retained_failed_publish = None
            _write_recovery_report(
                recovery_dir,
                "install",
                original_records,
                retained_backup if retained_backup.exists() else None,
                destination_root=output_folder,
                destination_snapshot=_capture_tree_snapshot(output_folder),
                restored_snapshot=_capture_tree_snapshot(retained_backup) if retained_backup.exists() else None,
                destination_precondition=destination_precondition,
                staged_copy_root=None,
                failed_publication_root=retained_failed_publish,
            )
            raise PatcherError(f"Install recovery is unresolved; evidence retained at {recovery_dir}")
        if failed_publish is not None and failed_publish.exists():
            _cleanup_owned_tree(failed_publish)
        raise
    finally:
        if staging_folder.exists():
            _cleanup_owned_tree(staging_folder)
    return output, log_path


def apply_all(
    sources: dict[str, Path],
    patch_mode: str = DEFAULT_PATCH_MODE,
    overwrite: bool = False,
    fun_patch_ids: tuple[str, ...] | list[str] = (),
    output_root: Path | None = None,
    copy_saves: bool = False,
    replace_modded_saves: bool = False,
    save_root: Path | None = None,
) -> list[tuple[Path, Path]]:
    _validate_public_patch_mode(patch_mode)
    _reject_vv5_running_unsupported_mode(patch_mode, fun_patch_ids)
    validated = validate_all_sources(sources)
    plans: list[
        tuple[Build, Path, bytearray, list[dict[str, str]], Path, Path]
    ] = []
    selected_by_game: dict[str, list[FunPatch]] = {}
    requested_by_game: dict[str, list[str]] = {}
    for patch_id in fun_patch_ids:
        patch = get_fun_patch(patch_id)
        requested_by_game.setdefault(patch.game_id, []).append(patch_id)
    for build in load_builds():
        requested = requested_by_game.get(build.id, [])
        if not requested:
            continue
        resolved_ids = resolve_fun_patch_ids(requested, game_id=build.id)
        by_id = {patch.id: patch for patch in load_fun_patches()}
        selected_by_game[build.id] = [by_id[item] for item in resolved_ids]
    for build, source in validated:
        fun_patches = selected_by_game.get(build.id, [])
        selected_ids = [patch.id for patch in fun_patches]
        patched, applied = render_patched_bytes(source, build, patch_mode, selected_ids)
        output_folder = output_folder_for(
            source, build, patch_mode, fun_patches, output_root
        )
        plans.append(
            (
                build,
                source,
                patched,
                applied,
                output_folder,
                output_folder / _output_name(build, patch_mode, fun_patches),
            )
        )
    existing = [folder for _, _, _, _, folder, _ in plans if folder.exists()]
    if existing and not overwrite:
        raise PatcherError(
            "Bulk modified game folder already exists; no files were written:\n"
            + "\n".join(str(path) for path in existing)
        )
    # All paths are preflighted above before any write.  Delegate each actual
    # publication to the same destination-local atomic transaction used by a
    # single patch; this prevents the bulk path from bypassing companion and
    # recovery verification.
    results: list[tuple[Path, Path]] = []
    for build, source, _patched, _applied, _output_folder, _output in plans:
        selected_ids = [patch.id for patch in selected_by_game.get(build.id, [])]
        results.append(
            apply_patch(
                source,
                patch_mode=patch_mode,
                overwrite=overwrite,
                fun_patch_ids=selected_ids,
                output_root=output_root,
                copy_saves=copy_saves,
                replace_modded_saves=replace_modded_saves,
                save_root=save_root,
            )
        )
    return results


def _add_patch_mode_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--patch-mode",
        choices=[mode.id for mode in load_patch_modes()],
        default=DEFAULT_PATCH_MODE,
    )


def _add_fun_patch_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--fun-patch",
        action="append",
        choices=[patch.id for patch in load_public_fun_patches()],
        default=[],
        help="optional game-specific patch; may be supplied more than once",
    )


def _add_playtest_feature_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--playtest-disabled-feature",
        action="append",
        choices=[
            VV2_PLAYTEST_DISABLED_FEATURE_ID,
        ],
        default=[],
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--playtest-output-root",
        type=Path,
        default=None,
        help=argparse.SUPPRESS,
    )


def _add_output_root_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help=(
            "parent folder for short '(Game name) - Modded' outputs; "
            "defaults to the original game's parent folder"
        ),
    )


def _add_all_source_args(parser: argparse.ArgumentParser) -> None:
    for build in load_builds():
        parser.add_argument(
            f"--{build.id}",
            required=True,
            type=Path,
            help=f"folder containing {build.input_name}, or the EXE itself",
        )


def _all_sources_from_args(args: argparse.Namespace) -> dict[str, Path]:
    return {build.id: getattr(args, build.id) for build in load_builds()}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="Virtual Villagers Fun Patcher", allow_abbrev=False
    )
    sub = parser.add_subparsers(dest="command", required=True)

    identify_cmd = sub.add_parser(
        "identify", help="identify an exact supported stock EXE", allow_abbrev=False
    )
    identify_cmd.add_argument("exe", type=Path)

    dry_cmd = sub.add_parser(
        "dry-run", help="verify and preview without writing output", allow_abbrev=False
    )
    dry_cmd.add_argument("exe", type=Path)
    _add_patch_mode_arg(dry_cmd)
    _add_fun_patch_args(dry_cmd)
    _add_playtest_feature_arg(dry_cmd)
    _add_output_root_arg(dry_cmd)

    apply_cmd = sub.add_parser(
        "apply", help="create one modified copy", allow_abbrev=False
    )
    apply_cmd.add_argument("exe", type=Path)
    apply_cmd.add_argument("--overwrite", action="store_true")
    _add_patch_mode_arg(apply_cmd)
    _add_fun_patch_args(apply_cmd)
    _add_playtest_feature_arg(apply_cmd)
    _add_output_root_arg(apply_cmd)

    dry_all_cmd = sub.add_parser(
        "dry-run-all",
        help="verify all five games without writing output",
        allow_abbrev=False,
    )
    _add_all_source_args(dry_all_cmd)
    _add_patch_mode_arg(dry_all_cmd)
    _add_fun_patch_args(dry_all_cmd)
    _add_output_root_arg(dry_all_cmd)

    apply_all_cmd = sub.add_parser(
        "apply-all", help="create all five modified copies together", allow_abbrev=False
    )
    apply_all_cmd.add_argument("--overwrite", action="store_true")
    _add_all_source_args(apply_all_cmd)
    _add_patch_mode_arg(apply_all_cmd)
    _add_fun_patch_args(apply_all_cmd)
    _add_output_root_arg(apply_all_cmd)
    return parser


def _preparse_publication_mode(argv: list[str] | None = None) -> None:
    """Reject public mode errors before the catalog-backed argparse parser."""
    tokens = list(sys.argv[1:] if argv is None else argv)
    if not tokens or tokens[0] not in {
        "dry-run", "apply", "dry-run-all", "apply-all"
    }:
        return
    patch_mode = DEFAULT_PATCH_MODE
    for index, token in enumerate(tokens[1:], start=1):
        if token == "--patch-mode" and index + 1 < len(tokens):
            patch_mode = tokens[index + 1]
        elif token.startswith("--patch-mode="):
            patch_mode = token.split("=", 1)[1]
    if patch_mode in EXPANDED_PATCH_MODES and tokens[0] in {"dry-run", "apply"}:
        feature_ids: list[str] = []
        playtest_roots: list[str] = []
        for index, token in enumerate(tokens[1:], start=1):
            if token == "--playtest-disabled-feature" and index + 1 < len(tokens):
                feature_ids.append(tokens[index + 1])
            elif token.startswith("--playtest-disabled-feature="):
                feature_ids.append(token.split("=", 1)[1])
            elif token == "--playtest-output-root" and index + 1 < len(tokens):
                playtest_roots.append(tokens[index + 1])
            elif token.startswith("--playtest-output-root="):
                playtest_roots.append(token.split("=", 1)[1])
        forbidden = {
            "--output-root",
            "--copy-vanilla-saves",
            "--replace-modded-saves",
            "--save-root",
        }
        has_forbidden = any(
            token in forbidden
            or any(token.startswith(option + "=") for option in forbidden)
            for token in tokens[1:]
        )
        if (
            len(feature_ids) == 1
            and feature_ids[0] in frozenset(EXPANDED_TIME_WARP_IDS.values())
            and len(playtest_roots) == 1
            and Path(playtest_roots[0]).expanduser().is_absolute()
            and not has_forbidden
        ):
            return
    _validate_public_patch_mode(patch_mode)


def main() -> int:
    try:
        _preparse_publication_mode()
        args = _parser().parse_args()
        if args.command == "identify":
            print(json.dumps(identify(args.exe).raw, indent=2))
        elif args.command == "dry-run":
            print(
                json.dumps(
                    dry_run(
                        args.exe,
                        args.patch_mode,
                        args.fun_patch,
                        output_root=args.output_root,
                        playtest_disabled_feature_ids=args.playtest_disabled_feature,
                        playtest_output_root=args.playtest_output_root,
                    ),
                    indent=2,
                )
            )
        elif args.command == "apply":
            output, log = apply_patch(
                args.exe,
                args.patch_mode,
                args.overwrite,
                args.fun_patch,
                output_root=args.output_root,
                playtest_disabled_feature_ids=args.playtest_disabled_feature,
                playtest_output_root=args.playtest_output_root,
            )
            print(f"Created: {output}")
            print(f"Log: {log}")
        elif args.command == "dry-run-all":
            print(
                json.dumps(
                    dry_run_all(
                        _all_sources_from_args(args),
                        args.patch_mode,
                        args.fun_patch,
                        output_root=args.output_root,
                    ),
                    indent=2,
                )
            )
        else:
            _validate_public_patch_mode(args.patch_mode)
            results = apply_all(
                _all_sources_from_args(args),
                args.patch_mode,
                args.overwrite,
                args.fun_patch,
                output_root=args.output_root,
            )
            for output, log in results:
                print(f"Created: {output}")
                print(f"Log: {log}")
        return 0
    except PatcherError as exc:
        print(f"Error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
