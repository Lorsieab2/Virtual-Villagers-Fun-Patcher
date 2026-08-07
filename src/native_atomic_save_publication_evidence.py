"""Disabled fail-closed VV3-VV5 native atomic-save evidence gate."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Mapping

GAMES = ("vv3", "vv4", "vv5")
EXPECTED_STOCK = {
    "vv3": ("Virtual Villagers - The Secret City.exe", 831488, "8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503"),
    "vv4": ("Virtual Villagers - The Tree of Life.exe", 929792, "6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220"),
    "vv5": ("Virtual Villagers - New Believers.exe", 991232, "92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D"),
}
REQUIREMENTS = (
    "exact_native_abis", "sibling_temp_write", "checked_header_body_flush_close",
    "reopen_exact_validation", "atomic_replace_preserves_prior_final", "directory_durability",
    "slot0_current_backup_results", "fatal_nonreturn_after_late_load_mutation",
    "record_bounds_tail_padding", "fault_injection_runtime_player_receipts",
)
NATIVE_KEYS = ("header_writer", "body_writer", "slot_result_handler", "late_load_failure_handler")
SHAPE_KEYS = ("header_size", "body_size", "final_size", "record_count", "record_size", "tail_size", "padding_policy")
DEFECT_KEYS = ("direct_wb_truncation", "ignored_rotation_result", "ignored_close_result")
HASH = re.compile(r"^[0-9A-F]{64}$")

@dataclass(frozen=True)
class Result:
    structural: bool
    evidence_complete: bool
    publication_allowed: bool
    errors: tuple[str, ...]

def _receipt_ok(item: Any, game: str, kind: str, errors: list[str]) -> bool:
    if not isinstance(item, Mapping):
        errors.append(f"{game} {kind} receipt must be an object")
        return False
    required = {"id", "source_sha256", "full_folder_manifest_sha256", "synthetic", "stale", "observed", "faults"}
    if set(item) != required:
        errors.append(f"{game} {kind} receipt has wrong shape")
        return False
    if item["synthetic"] is not False or item["stale"] is not False or item["observed"] is not True:
        errors.append(f"{game} {kind} receipt is synthetic, stale, or unobserved")
    if item["source_sha256"] != EXPECTED_STOCK[game][2] or not HASH.fullmatch(str(item["full_folder_manifest_sha256"])):
        errors.append(f"{game} {kind} receipt fingerprint mismatch")
    faults = item["faults"]
    if not isinstance(faults, list) or len(faults) != len(set(map(str, faults))) or not faults:
        errors.append(f"{game} {kind} receipt lacks unique fault-injection coverage")
    return True

def validate(data: Mapping[str, Any]) -> Result:
    errors: list[str] = []
    flags = ("enabled", "native_emission", "runtime_certified", "player_certified", "publication")
    if data.get("schema") != "vvfp.native_atomic_save_publication_evidence" or data.get("schema_version") != 1:
        errors.append("schema identity/version mismatch")
    if data.get("feature") != "native_atomic_save_publication": errors.append("feature mismatch")
    for flag in flags:
        if data.get(flag) is not False: errors.append(f"{flag} must remain false")
    if data.get("nonqualifying_proofs") != ["stock_backup_rotation", "serializer_arithmetic_only"]:
        errors.append("nonqualifying proof rejection set mismatch")
    games = data.get("games")
    if not isinstance(games, Mapping) or set(games) != set(GAMES):
        return Result(False, False, False, tuple(errors + ["games must be exactly vv3-vv5"]))
    complete = True
    for game in GAMES:
        row = games[game]
        if not isinstance(row, Mapping): errors.append(f"{game} row must be an object"); complete = False; continue
        stock = row.get("stock", {})
        name, size, sha = EXPECTED_STOCK[game]
        if (stock.get("exe_name"), stock.get("size"), stock.get("imagebase"), stock.get("sha256")) != (name, size, 0x400000, sha):
            errors.append(f"{game} stock fingerprint mismatch")
        for key in ("full_folder_sha256", "full_folder_manifest_sha256"):
            if not HASH.fullmatch(str(stock.get(key, ""))): errors.append(f"{game} {key} missing"); complete = False
        if not isinstance(stock.get("full_folder_file_count"), int) or stock.get("full_folder_file_count", 0) <= 0:
            errors.append(f"{game} full-folder count missing"); complete = False
        native, shape, defects = row.get("native", {}), row.get("file_shape", {}), row.get("stock_defects", {})
        for key in NATIVE_KEYS:
            value = native.get(key)
            if not isinstance(value, Mapping) or not {"va", "file_offset", "bytes", "calling_convention", "registers", "cleanup", "callers", "xrefs"}.issubset(value):
                errors.append(f"{game} exact {key} ABI missing"); complete = False
        for key in SHAPE_KEYS:
            if shape.get(key) is None: errors.append(f"{game} exact {key} missing"); complete = False
        for key in DEFECT_KEYS:
            if defects.get(key) is not True: errors.append(f"{game} stock defect {key} unproved"); complete = False
        if tuple(row.get("requirements", ())) != REQUIREMENTS:
            errors.append(f"{game} requirement set/order mismatch"); complete = False
        evidence = row.get("evidence")
        if not isinstance(evidence, list) or len(evidence) != len(REQUIREMENTS):
            errors.append(f"{game} requires one evidence row per gate"); complete = False
        else:
            ids = [item.get("requirement") for item in evidence if isinstance(item, Mapping)]
            if tuple(ids) != REQUIREMENTS or len(ids) != len(set(ids)): errors.append(f"{game} evidence rows missing, duplicate, or reordered"); complete = False
            for item in evidence:
                if not isinstance(item, Mapping) or item.get("verified") is not True or item.get("synthetic") is not False or item.get("stale") is not False:
                    errors.append(f"{game} evidence row is incomplete/synthetic/stale"); complete = False; continue
                proof_class = item.get("proof_class")
                if proof_class in ("stock_backup_rotation", "serializer_arithmetic_only"):
                    errors.append(f"{game} nonqualifying {proof_class} used as proof"); complete = False
        runtime, player = row.get("runtime_receipts"), row.get("player_receipts")
        if not isinstance(runtime, list) or not runtime: errors.append(f"{game} runtime receipts missing"); complete = False
        else:
            for item in runtime: _receipt_ok(item, game, "runtime", errors)
        if not isinstance(player, list) or not player: errors.append(f"{game} player receipts missing"); complete = False
        else:
            for item in player: _receipt_ok(item, game, "player", errors)
    structural = not any("schema" in e or "games must" in e or "fingerprint mismatch" in e or "must remain false" in e for e in errors)
    return Result(structural, complete and not errors, False, tuple(errors))

def load(path: Path) -> Mapping[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))

def validate_file(path: Path) -> Result:
    try: return validate(load(path))
    except (OSError, json.JSONDecodeError) as exc: return Result(False, False, False, (str(exc),))
