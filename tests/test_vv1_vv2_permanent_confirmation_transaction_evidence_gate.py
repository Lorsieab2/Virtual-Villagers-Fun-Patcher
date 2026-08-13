import copy, shutil, sys, tempfile, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
import vv_permanent_confirmation_transaction_evidence_gate as gate
H="A"*64

def candidate():
    return {
        "schema_version":1,"game_id":"vv1","route_id":"selected_grant_youth","command":0,"price":50000,"action":"Buy","remove":False,
        "status":"STOP","enabled":False,"catalog_enabled":False,"catalog_hidden":True,"publication":False,"player_ready":False,"runtime_certified":False,"native_output":False,"source":"repository-owned-automated-evidence",
        "stock":dict(gate.STOCK["vv1"]),"folder_inventory":{"complete":True,"no_follow":True,"inventory_sha256":H,"dlls":[{"path":"SDL2.dll","size":1,"sha256":H}]},
        "dry_run":{"complete":True,"exact_eligibility":"proved predicate","world_id":"w","selected_index":1,"record_id":"r","account_id":"a","funds":100000,"predicted_count":1,"no_op_before_confirmation":True},
        "confirmation":{"owner_valid_same_process":True,"owner_reused":True,"accepted_result":"IDOK","all_other_results_cancel":True,"prompt_binds_target_cost_prediction":True},
        "reacquisition":{"fresh_world":True,"fresh_selection":True,"fresh_record":True,"fresh_account":True,"fresh_funds":True,"identities_equal":True,"prestate_equal":True},
        "native_mutation":{"setter_abi":"0x401000 thiscall ret4","side_effects":"proved notification","direct_store":False,"legacy_route":False,"readback":True},
        "postverify":{"complete":True,"before_deduction":True,"verified_count":1},
        "deduction":{"native_abi":"0x402000 thiscall ret4","call_count":1,"after_postverify":True,"funds_readback":True,"precharge":False},
        "charge_certainty":"charged_once","fullscreen":{"owner_contract_sha256":H,"leave_succeeded":True,"restore_count":1,"result_owner_reused":True,"cleanup":True},
        "wording":{"count_phrase":"1 villager was changed.","result":"Updated 1 villager.","charge_sentence":"50,000 tech points were deducted.","partial_disclosure":"Native changes may remain; complete rollback is not claimed."},
        "ownership":{"ranges":"proved","install_order":"proved","uninstall_order":"proved"},"receipts":[{"mode":"windowed","result":"success"}],
    }

class Tests(unittest.TestCase):
    def test_contract_disabled_empty_exact_routes_prices_and_unknowns_null(self):
        c=gate.load_contract(); self.assertEqual(tuple(r["id"] for r in c["routes"]),gate.ROUTES); self.assertEqual(c["evidence_records"],[]); self.assertTrue(all(v is None for v in c["unknown_evidence"].values()))
        self.assertEqual([(r["command"],r["price"]) for r in c["routes"]],[gate.ROUTE_FACTS[x] for x in gate.ROUTES])
        self.assertNotIn(c["id"],(ROOT/"src/vv_fun_patcher.py").read_text(encoding="utf-8"))
    def test_structural_candidate_valid_but_enablement_always_blocked(self):
        c=candidate(); self.assertTrue(gate.validate_candidate(c))
        with self.assertRaises(gate.EvidenceError): gate.assert_enablement_blocked(c)
    def test_adversarial_transaction_mutations_fail(self):
        mutations=[]
        def add(fn): c=candidate(); fn(c); mutations.append(c)
        add(lambda c:c.__setitem__("enabled",True)); add(lambda c:c.__setitem__("route_id","Tech Point Doubler")); add(lambda c:c.__setitem__("price",1)); add(lambda c:c.__setitem__("action","Remove")); add(lambda c:c["confirmation"].__setitem__("accepted_result","IDCANCEL")); add(lambda c:c["reacquisition"].__setitem__("fresh_account",False)); add(lambda c:c["native_mutation"].__setitem__("direct_store",True)); add(lambda c:c["native_mutation"].__setitem__("legacy_route",True)); add(lambda c:c["deduction"].__setitem__("precharge",True)); add(lambda c:c["postverify"].__setitem__("before_deduction",False)); add(lambda c:c["deduction"].__setitem__("call_count",2)); add(lambda c:c["fullscreen"].__setitem__("restore_count",0)); add(lambda c:c["wording"].__setitem__("count_phrase","1 villager(s) changed")); add(lambda c:c["native_mutation"].__setitem__("setter_abi","synthetic"))
        for c in mutations:
            with self.assertRaises(gate.EvidenceError): gate.validate_candidate(c)
    def test_unknown_charge_rejects_no_charge_claim(self):
        c=candidate(); c["charge_certainty"]="unknown"; c["deduction"]["call_count"]=0; c["wording"]["charge_sentence"]=gate.NO_CHARGE
        with self.assertRaises(gate.EvidenceError): gate.validate_candidate(c)
    def test_natural_zero_one_many(self):
        for count,text in ((0,"No villagers were changed."),(1,"1 villager was changed."),(2,"2 villagers were changed.")):
            c=candidate(); c["postverify"]["verified_count"]=count; c["wording"]["count_phrase"]=text; gate.validate_candidate(c)
    def test_clean_archive_rejects_native_artifact(self):
        rels=[gate.CONTRACT.relative_to(ROOT),gate.SCHEMA.relative_to(ROOT),Path("src/vv_permanent_confirmation_transaction_evidence_gate.py"),Path("tests/test_vv1_vv2_permanent_confirmation_transaction_evidence_gate.py"),Path("docs/vv1-vv2-permanent-confirmation-transaction-evidence-gate.md")]
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)
            for rel in rels: (out/rel).parent.mkdir(parents=True,exist_ok=True); shutil.copy2(ROOT/rel,out/rel)
            gate.validate_clean_archive(out); (out/"bad.dll").write_bytes(b"MZ")
            with self.assertRaises(gate.EvidenceError): gate.validate_clean_archive(out)
if __name__=="__main__": unittest.main()
