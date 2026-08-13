"""Strictly disabled VV1/VV2 fullscreen owner-transition evidence gate."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "data/candidates/vv1_vv2_fullscreen_owner_transition_evidence_gate.json"
SCHEMA_PATH = ROOT / "data/candidates/vv1_vv2_fullscreen_owner_transition_evidence.schema.json"
ORACLE_PATH = "data/candidates/vv1_vv2_fullscreen_safe_candidate.json"
ORACLE_SHA256 = "7BB3DC74824B71B52E9C868D8A1C68EB9BC5AFE3708530E8B2F8BBC7C308EBD2"
DESTINATION_DLL = "VVFP Origins Icons.dll"
ROUTES = ("tech", "detail", "isolated_full_mastery", "future_full_heal", "modal_result")
MODES = ("windowed", "fullscreen")
RESULTS = ("cancel", "no_op", "success", "failure", "foreground_change", "restore_failure")
HEX64 = re.compile(r"^[0-9A-F]{64}$")
FORBIDDEN = ("todo", "tbd", "unknown", "synthetic", "invented", "placeholder", "not recorded", "address unavailable")
STOCK = {
    "vv1": {"filename": "Virtual Villagers - A New Home.exe", "size": 581632, "sha256": "1EC790B927741081D5CE13A48FB76983A4FD4336EA08F89317872643760AF03D"},
    "vv2": {"filename": "Virtual Villagers - The Lost Children.exe", "size": 724992, "sha256": "46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677"},
}
ROOT_KEYS = {"schema_version", "game_id", "status", "enabled", "catalog_enabled", "catalog_hidden", "publication", "player_ready", "runtime_certified", "native_output", "evidence_origin", "stock", "folder_inventory", "oracle", "routes", "window_types", "owner", "placement", "sdl_flags", "transition", "identity", "return_preservation", "restore", "cleanup", "ownership", "receipts"}

class EvidenceGateError(ValueError):
    pass

def _fail(path: str, message: str) -> None:
    raise EvidenceGateError(f"{path}: {message}")

def _obj(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping): _fail(path, "must be an object")
    return value

def _exact(value: Mapping[str, Any], keys: set[str], path: str) -> None:
    missing, extra = keys-set(value), set(value)-keys
    if missing: _fail(path, "missing keys: " + ", ".join(sorted(missing)))
    if extra: _fail(path, "unknown keys: " + ", ".join(sorted(extra)))

def _hex(value: Any, path: str) -> str:
    if not isinstance(value, str) or not HEX64.fullmatch(value): _fail(path, "must be 64 uppercase hexadecimal characters")
    return value

def _required(obj: Mapping[str, Any], path: str, keys: tuple[str, ...]) -> None:
    for key in keys:
        if key not in obj: _fail(f"{path}.{key}", "missing required evidence")

def _no_placeholders(value: Any, path: str = "candidate") -> None:
    if isinstance(value, str):
        for token in FORBIDDEN:
            if token in value.casefold(): _fail(path, f"contains forbidden token {token!r}")
    elif isinstance(value, Mapping):
        for key, child in value.items(): _no_placeholders(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value): _no_placeholders(child, f"{path}[{index}]")

def load_contract(path: Path = CONTRACT_PATH) -> Mapping[str, Any]:
    raw = _obj(json.loads(path.read_text(encoding="utf-8")), "contract")
    for key, expected in {"status":"STOP", "enabled":False, "catalog_enabled":False, "catalog_hidden":True, "publication":False, "player_ready":False, "runtime_certified":False, "native_output":False, "oracle_enablement_allowed":False}.items():
        if raw.get(key) != expected or type(raw.get(key)) is not type(expected): _fail(f"contract.{key}", f"must be {expected!r}")
    if raw.get("public_choices") != [] or raw.get("evidence_records") != []: _fail("contract", "tracked evidence and public choices must remain empty")
    oracle = _obj(raw.get("oracle"), "contract.oracle")
    if oracle != {"path":ORACLE_PATH, "sha256":ORACLE_SHA256, "status":"disabled-static-oracle-only", "static_evidence":True, "runtime_evidence":False, "enablement_evidence":False, "bytes_accepted_for_enablement":False}: _fail("contract.oracle", "oracle must remain disabled static evidence only")
    if raw.get("required_routes") != list(ROUTES) or raw.get("required_modes") != list(MODES) or raw.get("required_results") != list(RESULTS): _fail("contract", "route/mode/result matrix drifted")
    return raw

def load_schema(path: Path = SCHEMA_PATH) -> Mapping[str, Any]:
    return _obj(json.loads(path.read_text(encoding="utf-8")), "schema")

def validate_candidate_evidence(candidate: Mapping[str, Any]) -> None:
    c = _obj(candidate, "candidate"); _exact(c, ROOT_KEYS, "candidate"); _no_placeholders(c)
    for key, expected in {"schema_version":1, "status":"STOP", "enabled":False, "catalog_enabled":False, "catalog_hidden":True, "publication":False, "player_ready":False, "runtime_certified":False, "native_output":False, "evidence_origin":"repository-owned-native-and-runtime-evidence"}.items():
        if c[key] != expected or type(c[key]) is not type(expected): _fail(f"candidate.{key}", f"must be {expected!r}")
    game = c["game_id"]
    if game not in STOCK or dict(_obj(c["stock"], "candidate.stock")) != STOCK[game]: _fail("candidate.stock", "must match exact supported stock executable")
    inv = _obj(c["folder_inventory"], "candidate.folder_inventory"); _required(inv, "candidate.folder_inventory", ("scope", "complete", "all_dlls", "archive_sha256", "dll_inventory_sha256", "dlls"))
    if inv["scope"] != "full-game-folder" or inv["complete"] is not True or inv["all_dlls"] is not True: _fail("candidate.folder_inventory", "must be a complete full-folder/all-DLL inventory")
    _hex(inv["archive_sha256"], "candidate.folder_inventory.archive_sha256"); _hex(inv["dll_inventory_sha256"], "candidate.folder_inventory.dll_inventory_sha256")
    if not isinstance(inv["dlls"], list) or not inv["dlls"]: _fail("candidate.folder_inventory.dlls", "must be non-empty")
    seen=set()
    for i, dll in enumerate(inv["dlls"]):
        d=_obj(dll, f"candidate.folder_inventory.dlls[{i}]"); _exact(d,{"path","size","sha256"},f"candidate.folder_inventory.dlls[{i}]")
        if not isinstance(d["path"],str) or not d["path"].lower().endswith(".dll") or d["path"] in seen: _fail(f"candidate.folder_inventory.dlls[{i}].path","must be a unique relative DLL path")
        seen.add(d["path"])
        if type(d["size"]) is not int or d["size"] <= 0: _fail(f"candidate.folder_inventory.dlls[{i}].size","must be positive")
        _hex(d["sha256"],f"candidate.folder_inventory.dlls[{i}].sha256")
    oracle=_obj(c["oracle"],"candidate.oracle")
    expected_oracle={"path":ORACLE_PATH,"sha256":ORACLE_SHA256,"static_evidence":True,"runtime_evidence":False,"enablement_evidence":False,"bytes_accepted_for_enablement":False}
    if dict(oracle)!=expected_oracle: _fail("candidate.oracle","current bytes are static-only and rejected for enablement")
    if c["routes"] != list(ROUTES): _fail("candidate.routes","must cover every modal route exactly once")
    wt=_obj(c["window_types"],"candidate.window_types"); _required(wt,"candidate.window_types",("sdl_window_type","hwnd_type","distinct","cast_forbidden","native_handle_route"))
    if wt["sdl_window_type"]!="SDL_Window*" or wt["hwnd_type"]!="HWND" or wt["distinct"] is not True or wt["cast_forbidden"] is not True: _fail("candidate.window_types","SDL_Window* and HWND must be distinct and never cast")
    owner=_obj(c["owner"],"candidate.owner"); _required(owner,"candidate.owner",("capture_before_leave","non_null","is_window_abi","same_process_abi","same_process","dialogbox_owner_reused","messagebox_owner_reused","foreground_reacquire_forbidden"))
    for k in ("capture_before_leave","non_null","same_process","dialogbox_owner_reused","messagebox_owner_reused","foreground_reacquire_forbidden"):
        if owner[k] is not True: _fail(f"candidate.owner.{k}","must be true")
    placement=_obj(c["placement"],"candidate.placement"); _required(placement,"candidate.placement",("monitor_from_window_abi","get_monitor_info_abi","owner_monitor_work_area","center_arithmetic","clamp_all_edges"))
    if placement["owner_monitor_work_area"] is not True or placement["clamp_all_edges"] is not True: _fail("candidate.placement","must center and clamp in owner monitor work area")
    flags=_obj(c["sdl_flags"],"candidate.sdl_flags"); _required(flags,"candidate.sdl_flags",("symbol","calling_convention","argument","return_type","caller_cleanup_bytes","mask","unsupported_bits_rejected"))
    if (flags["symbol"],flags["calling_convention"],flags["argument"],flags["return_type"],flags["caller_cleanup_bytes"],flags["mask"],flags["unsupported_bits_rejected"]) != ("SDL_GetWindowFlags","cdecl","SDL_Window*","Uint32",4,"0x1001",True): _fail("candidate.sdl_flags","exact SDL flags ABI/mask required")
    transition=_obj(c["transition"],"candidate.transition"); _required(transition,"candidate.transition",("leave_address","enter_address","calling_convention","receiver","argument","callee_cleanup_bytes","state_byte_address","state_byte_semantics","leave_success_predicate"))
    if transition["receiver"]!="ECX=engine" or transition["argument"]!="push bool" or transition["callee_cleanup_bytes"]!=4: _fail("candidate.transition","native receiver/argument/ret 4 contract required")
    identity=_obj(c["identity"],"candidate.identity"); _required(identity,"candidate.identity",("objects","after_leave","before_restore","after_restore","stale_pointer_rejected","equality_rules"))
    if identity["objects"] != ["singleton","outer","engine","SDL_Window*","HWND"] or not all(identity[k] is True for k in ("after_leave","before_restore","after_restore","stale_pointer_rejected")): _fail("candidate.identity","fresh identity is required at all transition boundaries")
    ret=_obj(c["return_preservation"],"candidate.return_preservation"); _required(ret,"candidate.return_preservation",("target_address","return_abi","registers","stack","original_result_preserved"))
    if ret["original_result_preserved"] is not True: _fail("candidate.return_preservation","original target result must be preserved")
    restore=_obj(c["restore"],"candidate.restore"); _required(restore,"candidate.restore",("zero_if_leave_failed","exactly_one_after_successful_leave","all_exit_paths","duplicate_rejected","failure_reported"))
    if not all(restore[k] is True for k in restore): _fail("candidate.restore","restore cardinality/failure contract incomplete")
    cleanup=_obj(c["cleanup"],"candidate.cleanup"); _required(cleanup,"candidate.cleanup",("storage","pod_fields","initialized","destructor","process_detach","restore_if_outstanding","nested_modal_rejected","cleanup_order"))
    if cleanup["storage"] not in ("TLS","POD") or not all(cleanup[k] is True for k in ("initialized","restore_if_outstanding","nested_modal_rejected")): _fail("candidate.cleanup","TLS/POD lifecycle proof incomplete")
    ownership=_obj(c["ownership"],"candidate.ownership"); _required(ownership,"candidate.ownership",("destination_dll","parent_sha256","candidate_sha256","hook_ranges","cave_ranges","append_page_owner","install_order","uninstall_order","full_mastery_removed_before_origins_truncation","collision_fail_closed"))
    if ownership["destination_dll"] != DESTINATION_DLL or ownership["append_page_owner"] != "Origins" or ownership["full_mastery_removed_before_origins_truncation"] is not True or ownership["collision_fail_closed"] is not True: _fail("candidate.ownership","exact destination and reverse ownership order required")
    _hex(ownership["parent_sha256"],"candidate.ownership.parent_sha256"); _hex(ownership["candidate_sha256"],"candidate.ownership.candidate_sha256")
    receipts=c["receipts"]
    expected={(route,mode,result) for route in ROUTES for mode in MODES for result in RESULTS}
    if not isinstance(receipts,list) or len(receipts)!=len(expected): _fail("candidate.receipts",f"must contain exactly {len(expected)} receipts")
    actual=set()
    required_receipt=("route","mode","result","stock_sha256","folder_sha256","dll_inventory_sha256","owner_hwnd","owner_pid","game_pid","owner_valid","identity_before","identity_after_leave","identity_before_restore","identity_after_restore","leave_succeeded","leave_count","restore_count","restore_succeeded","dialog_owner","message_owner","original_return","state_byte_before","state_byte_after","final_window_flags","mutation","charge","failure_disclosure")
    for i, receipt in enumerate(receipts):
        r=_obj(receipt,f"candidate.receipts[{i}]"); _required(r,f"candidate.receipts[{i}]",required_receipt)
        key=(r["route"],r["mode"],r["result"])
        if key in actual: _fail(f"candidate.receipts[{i}]","duplicate matrix entry")
        actual.add(key)
        if r["owner_valid"] is not True or r["owner_pid"]!=r["game_pid"] or r["dialog_owner"]!=r["owner_hwnd"] or r["message_owner"]!=r["owner_hwnd"]: _fail(f"candidate.receipts[{i}]","owner validation/reuse failed")
        expected_leave = r["mode"] == "fullscreen"
        if r["leave_succeeded"] is not expected_leave or r["leave_count"] != int(expected_leave) or r["restore_count"] != int(expected_leave): _fail(f"candidate.receipts[{i}]","successful leave requires exactly one restore; no leave requires zero restores")
        expected_restore = expected_leave and r["result"] != "restore_failure"
        if r["restore_succeeded"] is not expected_restore: _fail(f"candidate.receipts[{i}]","restore outcome does not match mode/result")
        if r["result"]=="restore_failure" and not r["failure_disclosure"]: _fail(f"candidate.receipts[{i}]","restore failure must be disclosed")
    if actual != expected: _fail("candidate.receipts","matrix is incomplete or contains unsupported entries")

def assert_enablement_blocked(*_args: Any, **_kwargs: Any) -> None:
    raise EvidenceGateError("enablement is unavailable: tracked evidence is empty and oracle bytes are explicitly rejected")

def validate_clean_archive(root: Path) -> None:
    required = [CONTRACT_PATH.relative_to(ROOT), SCHEMA_PATH.relative_to(ROOT), Path("src/vv_fullscreen_owner_transition_evidence_gate.py"), Path("tests/test_vv1_vv2_fullscreen_owner_transition_evidence_gate.py"), Path("docs/vv1-vv2-fullscreen-owner-transition-evidence-gate.md")]
    for rel in required:
        if not (root/rel).is_file(): _fail("archive", f"missing {rel.as_posix()}")
    forbidden={".exe",".dll",".bin",".zip",".7z",".page"}
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.casefold() in forbidden: _fail("archive",f"native/package artifact forbidden: {path.relative_to(root).as_posix()}")
    raw=json.loads((root/CONTRACT_PATH.relative_to(ROOT)).read_text(encoding="utf-8"))
    if raw.get("evidence_records") != [] or raw.get("native_output") is not False: _fail("archive.contract","must remain empty and native-output false")
