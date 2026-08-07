import copy, hashlib, importlib.util, json, os, tempfile, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("abi",ROOT/"scripts"/"validate_vv3_save_serializer_abi_gate.py")
ABI=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(ABI)

class SaveSerializerAbiGateTests(unittest.TestCase):
    def setUp(self): self.contract=ABI.load(ABI.CONTRACT)
    def test_contract_is_valid_stop(self):
        r=ABI.validate_contract(self.contract); self.assertTrue(r["contract_valid"]); self.assertEqual("STOP",r["status"]); self.assertFalse(r["publication_ready"])
    def test_exact_rows(self): self.assertEqual(ABI.ROW_IDS,tuple(x["id"] for x in self.contract["native_rows"]))
    def test_exact_addresses(self): self.assertEqual(ABI.ROW_EAS,tuple(x["ea"] for x in self.contract["native_rows"]))
    def test_all_rows_empty(self): self.assertTrue(all(x["expected"] is None and x["evidence_refs"]==[] for x in self.contract["native_rows"]))
    def test_gap_matrix_complete(self): self.assertEqual(ABI.GAPS,tuple(x["id"] for x in self.contract["gap_matrix"]))
    def test_all_gaps_absent(self): self.assertTrue(all(x["status"]=="evidence_absent" for x in self.contract["gap_matrix"]))
    def test_exact_fingerprints(self): self.assertEqual(ABI.SOURCE,self.contract["bindings"]["source_sha256"]); self.assertEqual(ABI.PROTOTYPE,self.contract["bindings"]["prototype_sha256"])
    def test_stored_index_digest_bound(self): self.assertEqual(ABI.STORED,self.contract["bindings"]["stored_index_gate_sha256"])
    def test_dependency_hash_is_line_ending_stable(self):
        raw=(ROOT/"data"/"vv3_expanded_256_folder_inventory.schema.json").read_bytes()
        self.assertEqual(hashlib.sha256(raw.replace(b"\r\n",b"\n")).hexdigest().upper(),self.contract["bindings"]["folder_inventory_schema_sha256"])
    def test_decision_all_false(self): self.assertEqual({"publication_ready":False,"runtime_go":False,"player_go":False,"native_emission_permitted":False,"status":"STOP"},self.contract["decision"])
    def test_digest_tamper_rejected(self):
        d=copy.deepcopy(self.contract); d["enabled"]=True
        with self.assertRaises(ABI.GateError): ABI.validate_contract(d)
    def test_populated_native_row_rejected(self):
        d=copy.deepcopy(self.contract); d["native_rows"][0]["expected"]={}
        with self.assertRaises(ABI.GateError): ABI.validate_contract(d)
    def test_reordered_rows_rejected(self):
        d=copy.deepcopy(self.contract); d["native_rows"][0],d["native_rows"][1]=d["native_rows"][1],d["native_rows"][0]
        with self.assertRaises(ABI.GateError): ABI.validate_contract(d)
    def test_duplicate_json_key_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"x.json"; p.write_text('{"a":1,"a":2}',encoding="utf-8")
            with self.assertRaises(ABI.GateError): ABI.load(p)
    def test_noncanonical_candidate_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"x.json"; p.write_text('{"a": 1}',encoding="utf-8")
            with self.assertRaises(ABI.GateError): ABI.load(p,True)
    def test_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(ABI.GateError): ABI.safe_file(Path(t),"../x",1,"0"*64)
    def test_absolute_path_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(ABI.GateError): ABI.safe_file(Path(t),"C:/x",1,"0"*64)
    def test_hash_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); (root/"x").write_bytes(b"x")
            with self.assertRaises(ABI.GateError): ABI.safe_file(root,"x",1,"0"*64)
    def test_size_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); (root/"x").write_bytes(b"x")
            with self.assertRaises(ABI.GateError): ABI.safe_file(root,"x",2,hashlib.sha256(b"x").hexdigest().upper())
    def test_symlink_rejected_or_explicitly_unsupported(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); target=root/"target"; link=root/"link"; target.write_bytes(b"x")
            try: os.symlink(target,link)
            except OSError as exc: self.skipTest(f"symlink creation unsupported/privilege denied: {exc}")
            with self.assertRaises(ABI.GateError): ABI.safe_file(root,"link",1,hashlib.sha256(b"x").hexdigest().upper())
    def test_structural_candidate_never_go(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"bad.json"; p.write_bytes(ABI.canonical({"schema":"wrong"}))
            r=ABI.validate_candidate(p,Path(t)); self.assertFalse(r["gate_ready"]); self.assertFalse(r["runtime_go"]); self.assertFalse(r["player_go"]); self.assertFalse(r["publication_ready"])
    def test_schema_files_parse(self):
        for name in ("vv3_expanded_256_save_serializer_abi_gate.schema.json","vv3_expanded_256_save_serializer_abi_evidence.schema.json"):
            json.loads((ROOT/"data"/name).read_text(encoding="utf-8"))
    def test_no_forbidden_runtime_operations(self):
        source=(ROOT/"scripts"/"validate_vv3_save_serializer_abi_gate.py").read_text(encoding="utf-8")
        for token in ("subprocess","Popen(","Savegame","CreateProcess","native emission"):
            self.assertNotIn(token,source)

if __name__=="__main__": unittest.main()
