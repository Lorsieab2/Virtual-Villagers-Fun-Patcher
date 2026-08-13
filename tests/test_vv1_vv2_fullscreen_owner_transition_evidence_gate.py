import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
import vv_fullscreen_owner_transition_evidence_gate as gate

H="A"*64

def candidate():
    receipts=[]
    for route in gate.ROUTES:
        for mode in gate.MODES:
            for result in gate.RESULTS:
                left=mode=="fullscreen"
                receipts.append({"route":route,"mode":mode,"result":result,"stock_sha256":gate.STOCK["vv1"]["sha256"],"folder_sha256":H,"dll_inventory_sha256":H,"owner_hwnd":"0x00123456","owner_pid":42,"game_pid":42,"owner_valid":True,"identity_before":"a","identity_after_leave":"b","identity_before_restore":"c","identity_after_restore":"d","leave_succeeded":left,"leave_count":int(left),"restore_count":int(left),"restore_succeeded":left and result!="restore_failure","dialog_owner":"0x00123456","message_owner":"0x00123456","original_return":"preserved","state_byte_before":1,"state_byte_after":1,"final_window_flags":"0x00001001","mutation":result=="success","charge":result=="success","failure_disclosure":result in ("failure","restore_failure")})
    return {"schema_version":1,"game_id":"vv1","status":"STOP","enabled":False,"catalog_enabled":False,"catalog_hidden":True,"publication":False,"player_ready":False,"runtime_certified":False,"native_output":False,"evidence_origin":"repository-owned-native-and-runtime-evidence","stock":dict(gate.STOCK["vv1"]),"folder_inventory":{"scope":"full-game-folder","complete":True,"all_dlls":True,"archive_sha256":H,"dll_inventory_sha256":H,"dlls":[{"path":"SDL2.dll","size":1,"sha256":H}]},"oracle":{"path":gate.ORACLE_PATH,"sha256":gate.ORACLE_SHA256,"static_evidence":True,"runtime_evidence":False,"enablement_evidence":False,"bytes_accepted_for_enablement":False},"routes":list(gate.ROUTES),"window_types":{"sdl_window_type":"SDL_Window*","hwnd_type":"HWND","distinct":True,"cast_forbidden":True,"native_handle_route":"proved ABI"},"owner":{"capture_before_leave":True,"non_null":True,"is_window_abi":"IsWindow(HWND)->BOOL","same_process_abi":"GetWindowThreadProcessId(HWND,LPDWORD)","same_process":True,"dialogbox_owner_reused":True,"messagebox_owner_reused":True,"foreground_reacquire_forbidden":True},"placement":{"monitor_from_window_abi":"MonitorFromWindow(HWND,DWORD)","get_monitor_info_abi":"GetMonitorInfoA(HMONITOR,LPMONITORINFO)","owner_monitor_work_area":True,"center_arithmetic":"proved integer arithmetic","clamp_all_edges":True},"sdl_flags":{"symbol":"SDL_GetWindowFlags","calling_convention":"cdecl","argument":"SDL_Window*","return_type":"Uint32","caller_cleanup_bytes":4,"mask":"0x1001","unsupported_bits_rejected":True},"transition":{"leave_address":"0x00401000","enter_address":"0x00401100","calling_convention":"thiscall-like","receiver":"ECX=engine","argument":"push bool","callee_cleanup_bytes":4,"state_byte_address":"0x00402000","state_byte_semantics":"proved","leave_success_predicate":"proved"},"identity":{"objects":["singleton","outer","engine","SDL_Window*","HWND"],"after_leave":True,"before_restore":True,"after_restore":True,"stale_pointer_rejected":True,"equality_rules":"proved"},"return_preservation":{"target_address":"0x00403000","return_abi":"EAX","registers":"proved","stack":"proved","original_result_preserved":True},"restore":{"zero_if_leave_failed":True,"exactly_one_after_successful_leave":True,"all_exit_paths":True,"duplicate_rejected":True,"failure_reported":True},"cleanup":{"storage":"TLS","pod_fields":"proved","initialized":True,"destructor":"proved","process_detach":"proved","restore_if_outstanding":True,"nested_modal_rejected":True,"cleanup_order":"proved"},"ownership":{"destination_dll":gate.DESTINATION_DLL,"parent_sha256":H,"candidate_sha256":H,"hook_ranges":["0x1-0x2"],"cave_ranges":["0x3-0x4"],"append_page_owner":"Origins","install_order":["Origins","Full Mastery","modal wrapper"],"uninstall_order":["modal wrapper","Full Mastery","Origins"],"full_mastery_removed_before_origins_truncation":True,"collision_fail_closed":True},"receipts":receipts}

class GateTests(unittest.TestCase):
    def test_tracked_contract_is_empty_disabled_and_oracle_rejected(self):
        c=gate.load_contract(); self.assertEqual(c["evidence_records"],[]); self.assertFalse(c["publication"]); self.assertFalse(c["native_output"])
        with self.assertRaises(gate.EvidenceGateError): gate.assert_enablement_blocked(c)

    def test_schema_is_fail_closed(self):
        s=gate.load_schema(); self.assertFalse(s["additionalProperties"]); self.assertEqual(s["properties"]["enabled"]["const"],False)

    def test_structurally_complete_record_still_cannot_enable(self):
        c=candidate(); gate.validate_candidate_evidence(c)
        with self.assertRaises(gate.EvidenceGateError): gate.assert_enablement_blocked(c)

    def test_adversarial_mutations_fail(self):
        mutations=[]
        def add(fn):
            c=candidate(); fn(c); mutations.append(c)
        add(lambda c:c.__setitem__("enabled",True)); add(lambda c:c.__setitem__("publication",True)); add(lambda c:c["oracle"].__setitem__("enablement_evidence",True)); add(lambda c:c["window_types"].__setitem__("hwnd_type","SDL_Window*")); add(lambda c:c["owner"].__setitem__("same_process",False)); add(lambda c:c["sdl_flags"].__setitem__("mask","0x1")); add(lambda c:c["transition"].__setitem__("callee_cleanup_bytes",0)); add(lambda c:c["identity"].__setitem__("after_restore",False)); add(lambda c:c["return_preservation"].__setitem__("original_result_preserved",False)); add(lambda c:c["restore"].__setitem__("exactly_one_after_successful_leave",False)); add(lambda c:c["ownership"].__setitem__("destination_dll","guess.dll")); add(lambda c:c["receipts"].pop()); add(lambda c:c["receipts"][0].__setitem__("restore_count",1)); add(lambda c:c["folder_inventory"].__setitem__("archive_sha256","synthetic"))
        for c in mutations:
            with self.assertRaises(gate.EvidenceGateError): gate.validate_candidate_evidence(c)

    def test_clean_archive_and_native_artifact_rejection(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)
            for rel in [gate.CONTRACT_PATH.relative_to(ROOT),gate.SCHEMA_PATH.relative_to(ROOT),Path("src/vv_fullscreen_owner_transition_evidence_gate.py"),Path("tests/test_vv1_vv2_fullscreen_owner_transition_evidence_gate.py"),Path("docs/vv1-vv2-fullscreen-owner-transition-evidence-gate.md")]:
                (out/rel).parent.mkdir(parents=True,exist_ok=True); shutil.copy2(ROOT/rel,out/rel)
            gate.validate_clean_archive(out)
            (out/"forbidden.dll").write_bytes(b"MZ")
            with self.assertRaises(gate.EvidenceGateError): gate.validate_clean_archive(out)

if __name__=="__main__": unittest.main()
