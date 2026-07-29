from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shutil
import struct
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from transparency import write_transparency_artifacts

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "data" / "builds.json"
EXPANDED_MANIFEST_PATH = ROOT / "data" / "expanded_256.json"
ORIGINS_FEATURE_PATHS = tuple(
    ROOT / "data" / f"vv{game_number}_origins_feature.json"
    for game_number in range(1, 6)
)
ORIGINS_VILLAGE_WIDE_FEATURE_PATHS = tuple(
    ROOT / "data" / f"vv{game_number}_origins_village_wide_upgrades.json"
    for game_number in range(1, 6)
)
VV3_RUNNING_CANDIDATE_PATHS = {
    "base": ROOT / "data" / "candidates" / "vv3_origins_running_base_candidate.json",
    "running": ROOT / "data" / "candidates" / "vv3_all_villagers_like_running_candidate.json",
    "map": ROOT / "data" / "candidates" / "vv3_running_candidate_map.json",
}
VV3_RUNNING_CERTIFIED_SHA256 = {
    "base": "10D1516956AD7FF71A569869B4D03255C4FEB9A168A2B4084D3D091BE723D270",
    "running": "512FDBE807314B3371DCF10D7417EE42C8A104A1F87FB4165E04FCFBE6D9F49E",
    "map": "F7ECE7A55747EDC17EFC257206AF4F63408AF516FA08DFD14BA5E5003431636A",
}
VV3_FULL_MASTERY_CANDIDATE_PATHS = {
    "base": ROOT / "data" / "candidates" / "vv3_origins_full_mastery_base_candidate.json",
    "feature": ROOT / "data" / "candidates" / "vv3_full_mastery_all_candidate.json",
    "map": ROOT / "data" / "candidates" / "vv3_full_mastery_all_candidate_map.json",
    "dll": ROOT / "data" / "candidates" / "VVFP VV3 Full Mastery Candidate.dll",
}
VV3_FULL_MASTERY_CERTIFIED_SHA256 = {
    "base": "657D2D4F01550A121127053878E2777AB719CF00300A2AD69016296A4758B989",
    "feature": "844A3CB7996793F51D741409C9EFAF675E07ED92122BCD2F91750766D7357783",
    "map": "A8075640C3FC7230965E9645285254C5AF0C6E14C7E0437CBDDA9DF6B1E1B818",
    "dll": "35FB96199E745C7D8054FF6A12851B9E09225E3E41D0CE04012604E74968C0D5",
    "entry": "9685954F75E1DD26103507213FBEADBD9DED2705E62CB37D14080F6EBEC6EB23",
    "slot": "B1499EB3B10B7E4728746711E9F63B88211E4B80CA378742ADC5DC06782DAADA",
    "page": "2DAE85AE4077C23C2C7C39F64B5BA944740F765AC8E24FBB097B0BF28A720DF6",
}
VV3_FULL_MASTERY_ENABLED = True
VV2_FULL_MASTERY_CANDIDATE_PATHS = {
    "manifest": ROOT / "data" / "candidates" / "vv2_full_mastery_all_candidate.json",
    "map": ROOT / "data" / "candidates" / "vv2_full_mastery_all_candidate_map.json",
    "dll": ROOT / "data" / "candidates" / "VVFP VV2 Full Mastery Candidate.dll",
}
VV2_FULL_MASTERY_CERTIFIED_SHA256 = {
    "section": "0D0DD6DBEA7236807D15ED7047F08E7B8CC8B9AB098051C29A49C1AFDC31C61A",
    "entry": "68EB76203CA0AC65F3A608AEA8466B881BEFF536E8E88C64BAD7C8148C2A3D99",
    "walker": "7B01459A15542151B07D8A716731646A165C190C064B7BCB6CEB67EB1E1FAC94",
    "telemetry": "8036B4818E39533B3F5BEBF1EC38A94A71B05EE8BE72FB1EFA0B9AD72789B907",
    "confirmation": "07011CB557B6FCF7560AACB750D41851895C6856D851A567A4B952128E6B6258",
    "dll": "BDEAC1B39925834A7CD8DF7CD2C13BA7D7CBDF6E27760DAED6525092FF092699",
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
    "stock_page": "19BD89A04B1476F0CC996112906A02DD25A9ECD149B696A4C1EDA4A4CE713124",
    "expanded_page": "468A995FE91E2C6FE4E7812A65D77F68B22C6DBC9C3C9F696A4233C8EEDBC480",
    "dll": "9AC4E365BE55D32AB889E7B7472A1EDA8749B1EB259EA02BA35AB97BE666AF22",
}
VV5_FULL_MASTERY_CANDIDATE_PATHS = {
    "base": ROOT / "data" / "candidates" / "vv5_origins_full_mastery_base_candidate.json",
    "feature": ROOT / "data" / "candidates" / "vv5_full_mastery_all_candidate.json",
    "map": ROOT / "data" / "candidates" / "vv5_full_mastery_all_candidate_map.json",
    "dll": ROOT / "data" / "candidates" / "VVFP VV5 Full Mastery Candidate.dll",
}
VV5_FULL_MASTERY_CERTIFIED_SHA256 = {
    "stock_entry": "5BCB2527C5C7350779F98C9ECAC7CA9C2B2E2247DDA7D553085DA6FFD5CC8DEA",
    "stock_walker": "7466674FBC225EE898E10086B355509BF6AAB2E2D9024C8E3FCE4D0833CADAB8",
    "stock_confirmation": "E4B72DE00646AF4779C533165ECE95F727725E36925F841797F1B0F21A3CCEE5",
    "expanded_entry": "B7AAF750DC64DBED77D6D64BB83C50F631AAC5F109C9635F92FB88478D35FE5F",
    "expanded_walker": "35DFE0E67EF7B356ED6D3CB7E558FBFAF6F3364000818F4FC2D84599B902419F",
    "expanded_confirmation": "BFD577602BBF2E3AC581B92B8E1C99A221EB84504B2CB574A27ADA147ECB27BD",
    "stock_page": "DD473180CDCFE752706347739EF81008BA5072C2D5C802D41752D2964DF84FEE",
    "expanded_page": "877BB11B9906B4D259557C2A313E46C3FCA80A2A667DD9CE1BBE49BA59D7BDD4",
    "dll": "BD80B1B0692FE3C0F2293A73CFF707C18198AECA8922355DB2E9EB169E112608",
}
STATISTICS_FEATURES_PATH = ROOT / "data" / "statistics_features.json"
DEFAULT_PATCH_MODE = "collection_progression"
EXPANDED_PATCH_MODES = {
    "experimental_expanded_256",
    "experimental_expanded_256_progression",
}


class PatcherError(RuntimeError):
    pass


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
        digest = hashlib.sha256(payload).hexdigest().upper()
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
        digest = hashlib.sha256(payload).hexdigest().upper()
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
                "FINAL CERTIFIED GO under disassembly commit "
                "1e6ad7fd610d2fe9d80416fb218366ccd7d0656b"
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
                "FINAL CERTIFIED GO under disassembly commit "
                "1e6ad7fd610d2fe9d80416fb218366ccd7d0656b; stock modes only"
            ),
        }
    )
    return base, feature


def _certified_vv2_full_mastery_record() -> dict[str, Any] | None:
    manifest = json.loads(
        VV2_FULL_MASTERY_CANDIDATE_PATHS["manifest"].read_text(encoding="utf-8")
    )
    if not manifest.get("enabled", True):
        return None
    artifact_map = json.loads(
        VV2_FULL_MASTERY_CANDIDATE_PATHS["map"].read_text(encoding="utf-8")
    )
    for label in ("section", "entry", "walker", "telemetry", "confirmation"):
        actual = artifact_map[f"{label}_sha256"]
        expected = VV2_FULL_MASTERY_CERTIFIED_SHA256[label]
        if actual != expected:
            raise PatcherError(
                f"Certified VV2 Full Mastery {label} artifact hash mismatch: "
                f"expected {expected}, got {actual}."
            )
    dll_digest = hashlib.sha256(
        VV2_FULL_MASTERY_CANDIDATE_PATHS["dll"].read_bytes()
    ).hexdigest().upper()
    if dll_digest != VV2_FULL_MASTERY_CERTIFIED_SHA256["dll"]:
        raise PatcherError(
            "Certified VV2 Full Mastery DLL hash mismatch: "
            f"expected {VV2_FULL_MASTERY_CERTIFIED_SHA256['dll']}, got {dll_digest}."
        )
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
    if gate.get("status") != "independent recertification GO":
        raise PatcherError(
            "VV4 Full Mastery UI asset gate is not independently recertified; "
            "refusing enablement."
        )
    if gate.get("destination") != r"Images\btn_upgrades_297x35.png":
        raise PatcherError("VV4 Full Mastery UI asset destination is not the approved direct path.")
    if gate.get("dimensions") != [297, 35] or gate.get("frame_width") != 99:
        raise PatcherError("VV4 Full Mastery UI asset dimensions are not the approved 297x35 strip.")
    if gate.get("factory") != "sub_401C20" or gate.get("add_child") != "sub_40C190":
        raise PatcherError("VV4 Full Mastery UI asset factory/ownership gate is invalid.")
    if gate.get("grid") != [3, 1] or gate.get("local") != [72, 4]:
        raise PatcherError("VV4 Full Mastery UI asset geometry gate is invalid.")
    if gate.get("events") != {"tech": 13, "detail": 2}:
        raise PatcherError("VV4 Full Mastery UI asset event gate is invalid.")
    runtime_guard = gate.get("runtime_dimension_guard")
    if not isinstance(runtime_guard, dict):
        raise PatcherError(
            "VV4 Full Mastery runtime dimension guard is missing; refusing enablement."
        )
    if runtime_guard.get("required_frame_dimensions") != [99, 35]:
        raise PatcherError(
            "VV4 Full Mastery runtime frame dimension guard is not 99x35."
        )
    if runtime_guard.get("static_strip_dimensions") != [297, 35]:
        raise PatcherError(
            "VV4 Full Mastery static strip dimension guard is invalid."
        )
    if runtime_guard.get("static_grid") != [3, 1]:
        raise PatcherError("VV4 Full Mastery static grid guard is invalid.")
    accessors = runtime_guard.get("accessors")
    if accessors != {
        "width": {"wrapper_vtable_offset": "0x0C", "va": "0x401470"},
        "height": {"wrapper_vtable_offset": "0x10", "va": "0x4014B0"},
    }:
        raise PatcherError("VV4 Full Mastery native dimension accessor guard is invalid.")
    reject = runtime_guard.get("reject")
    if reject != {"scalar_destructor_flag": 1, "attach": False, "tech_slot": None}:
        raise PatcherError("VV4 Full Mastery runtime reject guard is invalid.")
    tech_wrapper = gate.get("tech_wrapper")
    if not isinstance(tech_wrapper, dict) or tech_wrapper.get("helper_length") != 34:
        raise PatcherError("VV4 Full Mastery Tech destructor helper length guard is invalid.")
    if tech_wrapper.get("ecx_restore") != "mov ecx, ebx":
        raise PatcherError("VV4 Full Mastery Tech destructor ECX restore guard is invalid.")
    forbidden = set(gate.get("forbidden_helpers", []))
    if {"sub_40D8A0", "sub_401140", "sub_401600"} - forbidden:
        raise PatcherError("VV4 Full Mastery UI asset helper exclusion gate is incomplete.")
    png_hash = gate.get("png_sha256")
    if not isinstance(png_hash, str) or len(png_hash) != 64:
        raise PatcherError("VV4 Full Mastery UI asset hash gate is missing.")
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
    stock = artifact["layouts"]["collection_progression"]
    expanded = artifact["layouts"]["experimental_expanded_256"]
    actual = {
        "stock_entry": stock["slot_map"]["installed"]["entry_sha256"],
        "stock_walker": stock["slot_map"]["installed"]["walker_sha256"],
        "stock_confirmation": stock["slot_map"]["installed"]["confirmation_sha256"],
        "expanded_entry": expanded["slot_map"]["installed"]["entry_sha256"],
        "expanded_walker": expanded["slot_map"]["installed"]["walker_sha256"],
        "expanded_confirmation": expanded["slot_map"]["installed"]["confirmation_sha256"],
        "stock_page": stock["installed_page_sha256"],
        "expanded_page": expanded["installed_page_sha256"],
        "dll": hashlib.sha256(
            VV5_FULL_MASTERY_CANDIDATE_PATHS["dll"].read_bytes()
        ).hexdigest().upper(),
    }
    for label, expected in VV5_FULL_MASTERY_CERTIFIED_SHA256.items():
        if actual[label] != expected:
            raise PatcherError(
                f"Certified VV5 Full Mastery {label} artifact hash mismatch: "
                f"expected {expected}, got {actual[label]}."
            )
    base = dict(base)
    base.update(
        {"id": active_base["id"], "name": active_base["name"], "enabled": True}
    )
    feature = dict(feature)
    feature.update(
        {
            "id": "vv5_full_mastery_all_stage_a_candidate",
            "name": "Grant Full Mastery to All Villagers",
            "enabled": True,
            "dependencies": [active_base["id"]],
        }
    )
    return base, feature


def _load_fun_patch_records() -> list[FunPatch]:
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
                    certified_base, running = _certified_vv3_running_records(record)
                    mastery = _certified_vv3_full_mastery_records(certified_base)
                    if mastery is None:
                        items.append(certified_base)
                    elif running is not None:
                        raise PatcherError(
                            "VV3 Running and Full Mastery cannot own the same "
                            "base Origins extension simultaneously."
                        )
                    else:
                        items.extend(mastery)
                    if running is not None and mastery is None:
                        items.append(running)
                elif record.get("id") == "vv4_enable_origins_exclusive_features":
                    mastery = _certified_vv4_full_mastery_records(record)
                    if mastery is None:
                        items.append(record)
                    else:
                        items.extend(mastery)
                elif record.get("id") == "vv5_enable_origins_exclusive_features":
                    mastery = _certified_vv5_full_mastery_records(record)
                    if mastery is None:
                        items.append(record)
                    else:
                        items.extend(mastery)
                else:
                    items.append(record)
    for feature_path in ORIGINS_VILLAGE_WIDE_FEATURE_PATHS:
        if feature_path.is_file():
            record = json.loads(feature_path.read_text(encoding="utf-8"))
            if record.get("enabled", True):
                items.append(record)
    vv2_full_mastery = _certified_vv2_full_mastery_record()
    if vv2_full_mastery is not None:
        items.append(vv2_full_mastery)
    if STATISTICS_FEATURES_PATH.is_file():
        statistics = json.loads(
            STATISTICS_FEATURES_PATH.read_text(encoding="utf-8")
        )
        items.extend(statistics.get("features", []))
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


def load_fun_patches() -> list[FunPatch]:
    patches = _load_fun_patch_records()
    validate_fun_patch_catalog(patches)
    from transparency import validate_feature_transparency_metadata

    validate_feature_transparency_metadata(patches)
    return patches


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
                    append_bytes = bytes.fromhex(layout["append_bytes"])
                    header_patches = layout["header_patches"]
                except (KeyError, TypeError, ValueError) as exc:
                    raise PatcherError(
                        f"{patch.name} ({patch.id}) has an invalid {mode_id} append layout."
                    ) from exc
                if (
                    original_size != append_offset
                    or not append_bytes
                    or len(append_bytes) % 0x1000
                    or not isinstance(header_patches, list)
                ):
                    raise PatcherError(
                        f"{patch.name} ({patch.id}) has unsafe {mode_id} append geometry."
                    )
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
    for patch_id in requested:
        missing = [
            dependency_id
            for dependency_id in _dependency_ids(by_id[patch_id])
            if dependency_id not in requested_set
        ]
        if missing:
            raise PatcherError(
                f"{by_id[patch_id].name} requires prerequisite(s): "
                + ", ".join(missing)
                + ". Select the prerequisite before creating output."
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
    layout = layouts.get(patch_mode)
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
    applied: list[dict[str, str]] = []
    for feature in fun_patches:
        layout = _append_layout(feature, patch_mode)
        if layout is None:
            continue
        try:
            original_size = int(layout["original_file_size"], 0)
            append_offset = int(layout["append_offset"], 0)
            append_bytes = bytes.fromhex(layout["append_bytes"])
            header_patches = layout["header_patches"]
        except (KeyError, TypeError, ValueError) as exc:
            raise PatcherError(
                f"{feature.name} ({feature.id}) has a malformed append layout."
            ) from exc
        if original_size != append_offset or len(data) != original_size:
            raise PatcherError(
                f"{feature.name} append guard failed: expected file size "
                f"0x{original_size:X}, found 0x{len(data):X}."
            )
        if not append_bytes or len(append_bytes) % 0x1000:
            raise PatcherError(
                f"{feature.name} append payload must occupy complete 0x1000-byte pages."
            )
        for item in header_patches:
            offset = int(item["offset"], 0)
            before = _patch_bytes(item, "before")
            after = _patch_bytes(item, "after")
            if len(before) != len(after):
                raise PatcherError(
                    f"{feature.name} append header changes length at {item['offset']}."
                )
            actual = bytes(data[offset : offset + len(before)])
            if actual != before:
                raise PatcherError(
                    f"{feature.name} append header guard failed at {item['offset']}: "
                    f"expected {before.hex().upper()}, found {actual.hex().upper()}"
                )
            data[offset : offset + len(after)] = after
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
        data.extend(append_bytes)
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
    return applied


def _remove_feature_bytes(
    data: bytearray,
    feature: FunPatch,
    patch_mode: str,
    output_folder: Path | None = None,
) -> list[dict[str, str]]:
    """Guardedly undo one feature, including its owned append transaction."""
    original_data = bytes(data)
    removed: list[dict[str, str]] = []
    patches = list(feature.patches)
    patches.extend(feature.raw.get("patch_mode_overrides", {}).get(patch_mode, []))
    for patch in reversed(patches):
        offset = int(patch["offset"], 0)
        before = _patch_bytes(patch, "before")
        after = _patch_bytes(patch, "after")
        actual = bytes(data[offset : offset + len(after)])
        if actual != after:
            raise PatcherError(
                f"Removal guard failed for {feature.id} at {patch['offset']}: "
                f"expected {after.hex().upper()}, found {actual.hex().upper()}"
            )
        data[offset : offset + len(before)] = before
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
        append_bytes = bytes.fromhex(layout["append_bytes"])
        if len(data) != append_offset + len(append_bytes):
            raise PatcherError(
                f"{feature.name} cannot be removed: appended file length is not owned."
            )
        actual = bytes(data[append_offset:])
        if actual != append_bytes:
            raise PatcherError(
                f"{feature.name} cannot be removed: appended page guard differs."
            )
        del data[append_offset:]
        for item in reversed(layout["header_patches"]):
            offset = int(item["offset"], 0)
            before = _patch_bytes(item, "before")
            after = _patch_bytes(item, "after")
            actual = bytes(data[offset : offset + len(after)])
            if actual != after:
                raise PatcherError(
                    f"{feature.name} removal header guard failed at {item['offset']}."
                )
            data[offset : offset + len(before)] = before
        removed.append(
            {
                "offset": layout["append_offset"],
                "before": append_bytes.hex().upper(),
                "after": "",
                "purpose": f"truncate owned append for {feature.id}",
                "owner": f"feature:{feature.id}",
            }
        )
    checksum_offset, _ = _pe_checksum_layout(data)
    struct.pack_into("<I", data, checksum_offset, 0)
    struct.pack_into("<I", data, checksum_offset, pe_checksum(data))
    if output_folder is not None:
        try:
            _remove_companion_files(output_folder, [feature])
        except Exception:
            data[:] = original_data
            raise
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

    applied: list[dict[str, str]] = []
    for feature in fun_patches:
        relocation = feature.raw.get("expanded_shr_relocations")
        if not relocation:
            continue
        if build.id not in {"vv4", "vv5"}:
            raise PatcherError(
                f"{feature.name} declares an expanded .shr relocation but is not a VV4/VV5 feature."
            )
        stock_va = int(relocation["stock_virtual_address"], 0)
        expanded_va = int(relocation["expanded_virtual_address"], 0)
        delta = expanded_va - stock_va
        if delta <= 0:
            raise PatcherError("Internal expanded .shr relocation has a non-positive delta.")
        for patch in relocation.get("patches", []):
            offset = int(patch["offset"], 0)
            before = bytes.fromhex(patch["before"])
            if len(before) != 4:
                raise PatcherError(
                    f"Internal expanded .shr relocation at {patch['offset']} is not a DWORD."
                )
            actual = bytes(data[offset : offset + 4])
            if actual != before:
                raise PatcherError(
                    f"Expanded .shr relocation guard failed at {patch['offset']}: "
                    f"expected {before.hex().upper()}, found {actual.hex().upper()}"
                )
            kind = patch.get("kind", "absolute")
            if kind == "absolute":
                value = int.from_bytes(before, "little")
                if not stock_va <= value < stock_va + 0x1000:
                    raise PatcherError(
                        f"Expanded .shr relocation at {patch['offset']} points outside stock .shr."
                    )
                after = (value + delta).to_bytes(4, "little")
            elif kind == "rel32":
                try:
                    source_va = int(patch["source_virtual_address"], 0)
                    target_stock_va = int(patch["target_stock_virtual_address"], 0)
                except (KeyError, TypeError, ValueError) as exc:
                    raise PatcherError(
                        f"Internal expanded .shr rel32 relocation at {patch['offset']} is missing source/target metadata."
                    ) from exc
                if not stock_va <= target_stock_va < stock_va + 0x1000:
                    raise PatcherError(
                        f"Expanded .shr rel32 relocation at {patch['offset']} points outside stock .shr."
                    )
                target_expanded_va = target_stock_va + delta
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
            data[offset : offset + 4] = after
            applied.append(
                {
                    "offset": patch["offset"],
                    "before": before.hex().upper(),
                    "after": after.hex().upper(),
                    "purpose": patch.get(
                        "purpose",
                        "relocate fun-patch .shr pointer for expanded 256 mode",
                    ),
                    "owner": f"feature:{feature.id}",
                    "virtual_address": _virtual_address_for_offset(bytes(data), offset),
                }
            )
    return applied


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
    if game["source_sha256"] != build.sha256:
        raise PatcherError(
            f"Experimental 256 data does not match {build.title}'s supported build."
        )
    return game["patches"]


def _safety_patches(build: Build, patch_mode: str) -> list[dict[str, str]]:
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


def get_fun_patch(patch_id: str) -> FunPatch:
    for patch in load_fun_patches():
        if patch.id == patch_id:
            return patch
    raise PatcherError(f"Unknown fun patch: {patch_id}")


def _selected_fun_patches(
    build: Build, patch_ids: tuple[str, ...] | list[str]
) -> list[FunPatch]:
    ordered_ids = resolve_fun_patch_ids(patch_ids, game_id=build.id)
    by_id = {patch.id: patch for patch in load_fun_patches()}
    return [by_id[patch_id] for patch_id in ordered_ids]


def _output_name(build: Build, patch_mode: str, fun_patches: list[FunPatch]) -> str:
    get_patch_variant(build, patch_mode)
    suffix = "Modded 256" if patch_mode in EXPANDED_PATCH_MODES else "Modded"
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


def render_patched_bytes(
    source: Path,
    build: Build,
    patch_mode: str = DEFAULT_PATCH_MODE,
    fun_patch_ids: tuple[str, ...] | list[str] = (),
    *,
    _fun_patches_override: list[FunPatch] | None = None,
) -> tuple[bytearray, list[dict[str, str]]]:
    variant = get_patch_variant(build, patch_mode)
    fun_patches = (
        _selected_fun_patches(build, fun_patch_ids)
        if _fun_patches_override is None
        else list(_fun_patches_override)
    )
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
    for phase_index, phase in enumerate(
        ([*expanded, *safety, *population, *support], fun_bytes)
    ):
        if phase_index == 1:
            applied.extend(
                _apply_pe_append_transactions(data, fun_patches, patch_mode)
            )
        for patch in phase:
            offset = int(patch["offset"], 0)
            before = _patch_bytes(patch, "before")
            after = _patch_bytes(patch, "after")
            if len(before) != len(after):
                raise PatcherError(
                    f"Internal manifest error at {patch['offset']}: length changed"
                )
            actual = bytes(data[offset : offset + len(before)])
            owner = patch.get("_owner", "automatic")
            end = offset + len(before)
            for prior_start, prior_end, prior_owner in applied_ranges:
                if offset < prior_end and prior_start < end and prior_owner != owner:
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
            build, patch_mode, fun_patches, data
        )
    )
    checksum_offset, _ = _pe_checksum_layout(data)
    checksum = pe_checksum(data)
    struct.pack_into("<I", data, checksum_offset, checksum)
    return data, applied


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
        "absolute_maximum": absolute_maximum,
        "villager_slots": villager_slots,
        "experimental_expanded_records": variant.get("expanded_records", False),
        "save_compatibility": (
            "expanded experimental layout with guarded stock-layout import in the modified executable's separate save folder"
            if variant.get("expanded_records", False)
            else "stock save layout"
        ),
        "multiple_birth_saturation": "multiples are reduced only when required to fit the remaining villager slots",
        "island_event_capacity": "population-adding Island Events are blocked or reduced only as required to fit the remaining physical villager slots",
        "bonuses_affect_maximum": variant["bonuses_affect_maximum"],
        "patches": applied,
        "result_sha256": hashlib.sha256(patched).hexdigest().upper(),
    }


def dry_run(
    source: Path,
    patch_mode: str = DEFAULT_PATCH_MODE,
    fun_patch_ids: tuple[str, ...] | list[str] = (),
    output_root: Path | None = None,
) -> dict[str, Any]:
    build = identify(source)
    fun_patches = _selected_fun_patches(build, fun_patch_ids)
    patched, applied = render_patched_bytes(source, build, patch_mode, fun_patch_ids)
    return _result(
        build, source, patch_mode, patched, applied, fun_patches, output_root
    )


def dry_run_all(
    sources: dict[str, Path],
    patch_mode: str = DEFAULT_PATCH_MODE,
    fun_patch_ids: tuple[str, ...] | list[str] = (),
    output_root: Path | None = None,
) -> list[dict[str, Any]]:
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
    return {
        "patcher": "Virtual Villagers Fun Patcher",
        "patch": mode.name,
        "patch_mode": mode.id,
        "patch_mode_name": mode.name,
        "fun_patches": [patch.id for patch in fun_patches],
        "fun_patch_names": [patch.name for patch in fun_patches],
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
        "multiple_birth_saturation": "multiples are reduced only when required to fit the remaining villager slots",
        "island_event_capacity": "population-adding Island Events are blocked or reduced only as required to fit the remaining physical villager slots",
        "bonuses_affect_maximum": variant["bonuses_affect_maximum"],
        "source_path": str(source.resolve()),
        "source_sha256": build.sha256,
        "output_path": str(output),
        "output_sha256": output_hash,
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
            source = (ROOT / item["source"]).resolve()
            try:
                source.relative_to(root)
            except ValueError as exc:
                raise PatcherError(
                    f"Companion file escapes the patcher folder: {source}"
                ) from exc
            destination_name = _safe_companion_destination(item["destination"])
            if not source.is_file():
                raise PatcherError(f"Required companion file is missing: {source}")
            expected_hash = item["sha256"].upper()
            if sha256(source) != expected_hash:
                raise PatcherError(f"Companion file hash mismatch: {source.name}")
            destination = output_folder / destination_name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            if sha256(destination) != expected_hash:
                raise PatcherError(
                    f"Companion file copy verification failed: {destination}"
                )
            copied.append(
                {
                    "feature": feature.id,
                    "path": str(destination),
                    "sha256": expected_hash,
                }
            )
    return copied


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
            source = (ROOT / item["source"]).resolve()
            try:
                source.relative_to(root)
            except ValueError as exc:
                raise PatcherError(
                    f"Companion file escapes the patcher folder: {source}"
                ) from exc
            if not source.is_file():
                raise PatcherError(f"Required companion file is missing: {source}")
            expected_hash = str(item["sha256"]).upper()
            actual_hash = sha256(source)
            if actual_hash != expected_hash:
                raise PatcherError(
                    f"Companion file hash mismatch: {source.name}; "
                    f"expected {expected_hash}, got {actual_hash}"
                )
            _safe_companion_destination(item["destination"])


def _remove_companion_files(
    output_folder: Path, fun_patches: list[FunPatch]
) -> list[dict[str, str]]:
    """Remove only exact companion bytes, refusing corruption or path escape."""
    removed: list[dict[str, str]] = []
    root = output_folder.resolve()
    pending: list[tuple[FunPatch, Path, str]] = []
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
            if actual_hash != expected_hash:
                raise PatcherError(
                    f"Companion removal guard failed for {destination}: "
                    f"expected {expected_hash}, got {actual_hash}"
                )
            pending.append((feature, destination, expected_hash))
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
) -> tuple[Path, Path]:
    source = source.resolve()
    build = identify(source)
    fun_patches = _selected_fun_patches(build, fun_patch_ids)
    output_name = _output_name(build, patch_mode, fun_patches)
    output_folder = output_folder_for(
        source, build, patch_mode, fun_patches, output_root
    )
    output = output_folder / output_name
    if output_folder.exists() and not overwrite:
        raise PatcherError(f"Modified game folder already exists: {output_folder}")
    patched, applied = render_patched_bytes(source, build, patch_mode, fun_patch_ids)
    output_folder_existed = output_folder.exists()
    _copy_game_folder_direct(source.parent, output_folder, overwrite, output_root)
    try:
        companions = _copy_companion_files(output_folder, fun_patches)
    except Exception:
        if not output_folder_existed:
            shutil.rmtree(output_folder, ignore_errors=True)
        raise
    log_path = output.with_suffix(".patch-log.json")
    try:
        with output.open("wb") as handle:
            handle.write(patched)
            handle.flush()
            os.fsync(handle.fileno())
        if output.stat().st_size != len(patched):
            raise PatcherError("Verification failed: patched file size mismatch")
        output_hash = sha256(output)
        expected_hash = hashlib.sha256(patched).hexdigest().upper()
        if output_hash != expected_hash:
            raise PatcherError("Verification failed: output hash mismatch")
        log_data = _log_data(
            build, source, output, patch_mode, output_hash, applied, fun_patches
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
            output=output,
            source_folder=source.parent,
            output_folder=output_folder,
            fun_patches=fun_patches,
            companions=companions,
            applied=applied,
            save_copy=save_copy,
            root=ROOT,
            json_path=log_path,
        )
    except Exception:
        # Do not leave an executable or a report that looks successful when
        # transparency generation fails.  A pre-existing overwrite target is
        # left in place because it cannot be safely reconstructed here.
        if not output_folder_existed:
            shutil.rmtree(output_folder, ignore_errors=True)
        else:
            output.unlink(missing_ok=True)
            log_path.unlink(missing_ok=True)
            (output.parent / "VVFP Transparency Log.txt").unlink(missing_ok=True)
        raise
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
    results: list[tuple[Path, Path]] = []
    completed_outputs: list[tuple[Path, bool, Path, Path]] = []
    for build, source, patched, applied, output_folder, output in plans:
        output_folder_existed = output_folder.exists()
        _copy_game_folder_direct(source.parent, output_folder, overwrite, output_root)
        companions = _copy_companion_files(
            output_folder, selected_by_game.get(build.id, [])
        )
        with output.open("wb") as handle:
            handle.write(patched)
            handle.flush()
            os.fsync(handle.fileno())
        if output.stat().st_size != source.stat().st_size:
            raise PatcherError(f"Bulk verification failed: {build.title} size changed")
        output_hash = sha256(output)
        expected_hash = hashlib.sha256(patched).hexdigest().upper()
        if output_hash != expected_hash:
            raise PatcherError(f"Bulk verification failed: {build.title} hash mismatch")
        log_path = output.with_suffix(".patch-log.json")
        log_data = _log_data(
            build,
            source,
            output,
            patch_mode,
            output_hash,
            applied,
            selected_by_game.get(build.id, []),
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
        try:
            write_transparency_artifacts(
                base_log=log_data,
                source=source,
                output=output,
                source_folder=source.parent,
                output_folder=output_folder,
                fun_patches=selected_by_game.get(build.id, []),
                companions=companions,
                applied=applied,
                save_copy=save_copy,
                root=ROOT,
                json_path=log_path,
            )
        except Exception:
            if not output_folder_existed:
                shutil.rmtree(output_folder, ignore_errors=True)
            else:
                output.unlink(missing_ok=True)
                log_path.unlink(missing_ok=True)
                (output.parent / "VVFP Transparency Log.txt").unlink(missing_ok=True)
            for completed_folder, completed_existed, completed_output, completed_log in completed_outputs:
                if not completed_existed:
                    shutil.rmtree(completed_folder, ignore_errors=True)
                else:
                    completed_output.unlink(missing_ok=True)
                    completed_log.unlink(missing_ok=True)
                    (completed_folder / "VVFP Transparency Log.txt").unlink(missing_ok=True)
            raise
        completed_outputs.append((output_folder, output_folder_existed, output, log_path))
        results.append((output, log_path))
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
        choices=[patch.id for patch in load_fun_patches()],
        default=[],
        help="optional game-specific patch; may be supplied more than once",
    )


def _add_output_root_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help=(
            "parent folder for short '(Game name) - Modded' or "
            "'(Game name) - Modded 256' outputs; "
            "defaults to the original game's parent folder"
        ),
    )


def _add_save_copy_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--copy-vanilla-saves",
        action="store_true",
        help=(
            "copy the exact vanilla numbered saves and required slot-zero file "
            "into the separate Modded 256 save folder"
        ),
    )
    parser.add_argument(
        "--replace-modded-saves",
        action="store_true",
        help=(
            "replace existing Modded 256 .ldw files with verified vanilla "
            "copies; requires --copy-vanilla-saves"
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
    parser = argparse.ArgumentParser(prog="Virtual Villagers Fun Patcher")
    sub = parser.add_subparsers(dest="command", required=True)

    identify_cmd = sub.add_parser("identify", help="identify an exact supported stock EXE")
    identify_cmd.add_argument("exe", type=Path)

    dry_cmd = sub.add_parser("dry-run", help="verify and preview without writing output")
    dry_cmd.add_argument("exe", type=Path)
    _add_patch_mode_arg(dry_cmd)
    _add_fun_patch_args(dry_cmd)
    _add_output_root_arg(dry_cmd)

    apply_cmd = sub.add_parser("apply", help="create one modified copy")
    apply_cmd.add_argument("exe", type=Path)
    apply_cmd.add_argument("--overwrite", action="store_true")
    _add_patch_mode_arg(apply_cmd)
    _add_fun_patch_args(apply_cmd)
    _add_output_root_arg(apply_cmd)
    _add_save_copy_args(apply_cmd)

    dry_all_cmd = sub.add_parser(
        "dry-run-all", help="verify all five games without writing output"
    )
    _add_all_source_args(dry_all_cmd)
    _add_patch_mode_arg(dry_all_cmd)
    _add_fun_patch_args(dry_all_cmd)
    _add_output_root_arg(dry_all_cmd)

    apply_all_cmd = sub.add_parser(
        "apply-all", help="create all five modified copies together"
    )
    apply_all_cmd.add_argument("--overwrite", action="store_true")
    _add_all_source_args(apply_all_cmd)
    _add_patch_mode_arg(apply_all_cmd)
    _add_fun_patch_args(apply_all_cmd)
    _add_output_root_arg(apply_all_cmd)
    _add_save_copy_args(apply_all_cmd)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if (
            getattr(args, "replace_modded_saves", False)
            and not getattr(args, "copy_vanilla_saves", False)
        ):
            raise PatcherError(
                "--replace-modded-saves requires --copy-vanilla-saves"
            )
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
                copy_saves=args.copy_vanilla_saves,
                replace_modded_saves=args.replace_modded_saves,
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
            results = apply_all(
                _all_sources_from_args(args),
                args.patch_mode,
                args.overwrite,
                args.fun_patch,
                output_root=args.output_root,
                copy_saves=args.copy_vanilla_saves,
                replace_modded_saves=args.replace_modded_saves,
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
