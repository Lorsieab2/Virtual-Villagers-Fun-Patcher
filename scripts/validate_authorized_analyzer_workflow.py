"""Validate the disabled, source-bound analyzer workflow without emitting native data."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / "data" / "authorized_analyzer_workflow.json"
EXPECTED = {
    "vv3": (415, "1B348AC2FA05E1D723F92AFBBB2E98507F624F7EDBC39B237D8C2B722955A1E6", "Virtual Villagers - The Secret City.exe", 831488, "8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503"),
    "vv4": (556, "DDA63528390D271F356E1A359AD991DB6A759E118F1EAD8F58813FD00103E155", "Virtual Villagers - The Tree of Life.exe", 929792, "6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220"),
    "vv5": (639, "9B9773905E5DA8D7A5B67FB8FD58E70093870429C60853C0023F5FFFEF3BF977", "Virtual Villagers - New Believers.exe", 991232, "92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D"),
}
MANIFEST_SHA = "A53C6D01B0AD58124EFDA7F2C2C8FC6ABC537DE5104C46F3C29F4C43B9305F42"
QUERY_PLAN_SHA = "FED6AE17FAB8FB173DD56AC20FA6FED7C80BE62EE9D53202FE705BDCC1B55087"
COLLECTIBLES_PLAN_SHA = "D5D2DB8B63B4BF5FE7E05AF677EAFF74907C8D9E0D1ECB66C676616AAE06E98E"
GAME_BINDING_KEYS = {
    "folder", "file_count", "dll_count", "inventory_sha256", "executable",
    "query_plan", "collectibles_plan", "export",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def validate(document: dict) -> None:
    assert document["status"] == "STOP"
    workflow = document["workflow"]
    assert workflow == {"read_only": True, "dry_run": True, "launches_performed": 0, "saves_accessed": 0, "exports_written": 0, "native_output": False, "publication_ready": False, "runtime_go": False, "player_go": False}
    recon = document["vv2_manifest_reconciliation"]
    assert recon["status"] == "STOP_MISSING_DEDICATED_MANIFEST"
    assert recon["available_manifest"]["query_count"] == 48
    assert sha256(ROOT / recon["available_manifest"]["path"]) == MANIFEST_SHA
    assert recon["dedicated_manifest"] == {"expected_query_count": 50, "path": None, "sha256": None, "query_ids": None}
    assert recon["unresolved_query_count"] == 2 and recon["unresolved_query_ids"] is None and recon["invented_rows"] == []
    for game, (count, inventory_sha, exe_name, exe_size, exe_sha) in EXPECTED.items():
        binding = document["game_bindings"][game]
        assert set(binding) == GAME_BINDING_KEYS, f"{game} binding contains an unnamespaced digest or unknown field"
        folder = ROOT / binding["folder"]
        assert folder.is_dir()
        files = [p for p in folder.rglob("*") if p.is_file()]
        assert len(files) == count and sum(p.suffix.lower() == ".dll" for p in files) == 7
        exe = folder / binding["executable"]["path"]
        assert exe.stat().st_size == exe_size and sha256(exe) == exe_sha
        assert binding["inventory_sha256"] == inventory_sha
        assert binding["query_plan"]["sha256"] == QUERY_PLAN_SHA and binding["query_plan"]["query_count"] == 10
        assert binding["collectibles_plan"]["sha256"] == COLLECTIBLES_PLAN_SHA and binding["collectibles_plan"]["query_count"] == 10
        assert binding["export"] == {"status": "PENDING_AUTHORIZED_MACHINE_SESSION", "artifact_path": None, "artifact_sha256": None, "resolved_rows": 0}
    assert document["gates"] == {"enabled": False, "catalog_enabled": False, "catalog_hidden": True, "native_output": False, "runtime_go": False, "player_go": False, "publication_ready": False}


def main() -> int:
    validate(json.loads(WORKFLOW.read_text(encoding="utf-8")))
    print("STOP: authorized analyzer workflow is source-bound for inventory/plan dry-run only; VV2 has 48 available queries versus unresolved dedicated 50-query manifest; VV3-VV5 exports remain pending authorized machine sessions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
