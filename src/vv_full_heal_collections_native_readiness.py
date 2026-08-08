"""Fail-closed readiness checks for future VV1/VV2 native Full Heal/collections exports."""
from __future__ import annotations
import json
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "data/native_evidence/vv1_vv2_full_heal_collections_query_manifest.json"
EXPECTED_GAMES = ("vv1", "vv2")
EXPECTED_STOCK = {
    "vv1": {"filename":"Virtual Villagers - A New Home.exe","size":581632,"sha256":"1EC790B927741081D5CE13A48FB76983A4FD4336EA08F89317872643760AF03D"},
    "vv2": {"filename":"Virtual Villagers - The Lost Children.exe","size":724992,"sha256":"46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677"},
}
EXPECTED_TOPICS = {
    "full_heal": {"health_getter","health_to_100_setter","health_setter_abi","health_side_effects","sickness_getter","sickness_clear_route","people_cured_field","people_cured_increment","eligibility_enumerator","physical_record_order","postverify"},
    "complete_collections": {"collection_table_base","collection_table_layout","collection_count_getter","collection_completion_predicate","collection_completion_setter","collection_setter_side_effects","collection_dispatch_route","notification_route","trophy_route","statistics_route","save_loader_field","save_serializer_field","transaction_confirmation","selected_world_identity_reacquisition","funds_getter","native_deduction","postverify"},
    "shared": {"world_singleton","manager_pool_identity","fresh_record_resolver","record_count_and_stride","dialog_or_messagebox_abi","idok_guard","cancel_no_mutation","fullscreen_owner_hwnd","fullscreen_leave_enter","fullscreen_restore_cleanup"},
}

class ReadinessError(ValueError):
    pass

def validate_manifest(manifest: dict) -> None:
    if manifest.get("schema_version") != 1 or manifest.get("id") != "vv1_vv2_full_heal_collections_native_readiness":
        raise ReadinessError("manifest identity/schema is not exact")
    if manifest.get("status") != "STOP" or any(manifest.get(k) is not False for k in ("enabled","publication_allowed","native_output")):
        raise ReadinessError("readiness manifest must remain disabled, unpublished, and native-output false")
    if tuple(manifest.get("games", [])) != EXPECTED_GAMES:
        raise ReadinessError("only VV1 and VV2 are in scope")
    if manifest.get("stock_executables") != EXPECTED_STOCK:
        raise ReadinessError("stock executable fingerprints drifted")
    folder = manifest.get("folder_requirements", {})
    if folder.get("scope") != "complete-game-folder" or folder.get("no_follow_inventory_required") is not True:
        raise ReadinessError("complete no-follow folder inventory is required")
    if folder.get("inventory_sha256") is not None or folder.get("dll_inventory_sha256") is not None or folder.get("known_dlls") != []:
        raise ReadinessError("unknown folder/DLL evidence must remain null/empty until authenticated")
    topics = manifest.get("required_topics", {})
    for topic, expected in EXPECTED_TOPICS.items():
        if set(topics.get(topic, [])) != expected:
            raise ReadinessError(f"missing or altered native query topic: {topic}")
    if manifest.get("manual_exports_allowed") is not False or manifest.get("partial_exports_allowed") is not False:
        raise ReadinessError("manual and partial exports are forbidden")
    legacy = manifest.get("legacy_cure_policy", {})
    if legacy != {"label":"Cure all Villagers","status":"legacy-sickness-only","full_heal":False,"catalog_enabled":False,"native_output":False}:
        raise ReadinessError("legacy Cure must remain explicit and non-Full-Heal")
    if manifest.get("evidence_records") != []:
        raise ReadinessError("no native evidence records may be tracked by the disabled gate")

def validate_file(path: str | Path = MANIFEST_PATH) -> None:
    validate_manifest(json.loads(Path(path).read_text(encoding="utf-8")))

def reject_candidate_export(export: object) -> None:
    """Reject any future export until it is separately authenticated and complete."""
    if export not in (None, {}):
        raise ReadinessError("native export is not accepted by this empty readiness gate; use authenticated export validation")

def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the disabled VV1/VV2 Full Heal/collections readiness manifest.")
    parser.add_argument("manifest", nargs="?", type=Path, default=MANIFEST_PATH)
    args = parser.parse_args()
    validate_file(args.manifest)
    print("VALID: disabled VV1/VV2 Full Heal/collections readiness manifest; evidence remains empty")

if __name__ == "__main__":
    main()
