from __future__ import annotations
import copy, importlib.util, json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
CONTRACT=ROOT/"data"/"expanded_256_save_serializer_abi_evidence.json"
DOC=ROOT/"docs"/"expanded-256-save-serializer-abi-evidence.md"
SPEC=importlib.util.spec_from_file_location("save_abi",ROOT/"scripts"/"validate_expanded_save_serializer_abi_evidence.py")
MODULE=importlib.util.module_from_spec(SPEC); assert SPEC.loader; SPEC.loader.exec_module(MODULE)
class SaveSerializerAbiEvidenceTests(unittest.TestCase):
 def setUp(self): self.contract=json.loads(CONTRACT.read_text(encoding="utf-8"))
 def recanon(self,d): d["integrity"]["canonical_sha256"]=MODULE.contract_sha(d)
 def fails(self,fn,msg):
  d=copy.deepcopy(self.contract); fn(d); self.recanon(d)
  with self.assertRaisesRegex(MODULE.SaveSerializerEvidenceError,msg): MODULE.validate_contract(d,ROOT)
 def row(self,req="loader_abi",synthetic=False):
  return {"row_id":"vv4-loader-1","requirement":req,"function_name":"sub_exact","function_ea":"0x401000","instruction_ea":"0x401010","file_offset":"0x1010","preimage":"8B442404","calling_convention":"cdecl","return_semantics":"zero failure, nonzero success","failure_semantics":"returns before manager mutation","xrefs":["0x402000"],"artifact":{"path":"data/vv4_origins_feature.json","sha256":"A38F98973EB83F91D60FCA5C2A1BD28444622CEAC5434C295FB7E73D3A1BCB71","evidence_class":"authenticated_native_artifact"},"runtime_receipt_refs":["runtime"],"player_receipt_refs":["player"],"synthetic":synthetic}
 def complete(self,d,row=None):
  e=d["games"]["vv4"]["evidence_matrix"][1]; row=row or self.row(); e.update(status="observed_complete",expected_row_count=1,native_rows=[row],runtime_receipt_refs=["runtime"],player_receipt_refs=["player"],missing_evidence=[]); e["row_ledger_sha256"]=MODULE.sha(e["native_rows"])
 def test_canonical_empty_stop(self):
  r=MODULE.validate_contract(self.contract,ROOT); self.assertFalse(r["publication_eligible"]); self.assertEqual((r["games"]["vv4"]["requirements_complete"],r["games"]["vv5"]["requirements_complete"]),(0,0))
 def test_publication_and_native_emission_disabled(self):
  self.fails(lambda d:d["publication"].__setitem__("enabled",True),"publication"); self.fails(lambda d:d["policy"].__setitem__("native_emission",True),"native emission")
 def test_required_schema_fields_and_closed_key_sets(self):
  required = ("schema_version", "contract_id", "status", "integrity", "publication", "policy", "bindings", "required_requirements", "games")
  for field in required:
   with self.subTest(field=field):
    d=copy.deepcopy(self.contract); d.pop(field)
    if "integrity" in d: self.recanon(d)
    with self.assertRaisesRegex(MODULE.SaveSerializerEvidenceError, "contract keys"):
     MODULE.validate_contract(d,ROOT)
  self.fails(lambda d:d["games"].__setitem__("vv6",copy.deepcopy(d["games"]["vv4"])),"games keys")
  self.fails(lambda d:d["games"]["vv4"].__setitem__("extra",None),"game keys")
  self.fails(lambda d:d["policy"].__setitem__("extra",None),"policy keys")
 def test_fingerprints_exact(self):
  self.fails(lambda d:d["games"]["vv4"]["stock_fingerprint"].__setitem__("sha256","0"*64),"stock fingerprint"); self.fails(lambda d:d["games"]["vv5"]["expanded_fingerprints"]["experimental_expanded_256"].__setitem__("size",1),"expanded fingerprints")
 def test_relocations_exact(self):
  self.fails(lambda d:d["games"]["vv4"]["relocation_ledger"].__setitem__("count",12),"relocation ledger"); self.fails(lambda d:d["games"]["vv5"]["relocation_ledger"].__setitem__("file_sha256","0"*64),"relocation artifact")
 def test_contract_and_harness_bindings_exact(self):
  self.assertEqual(self.contract["bindings"]["runtime_contract"], {"path":"data/expanded_256_runtime_evidence.json","file_sha256":"5A3BAEB25B958460243DD0E91DE94667CB304F22282EA721A2CE43B758C03F85","canonical_sha256":"54A0B95547ED52DBA6A7144E6610C5CB25097AADD5629697F2608FD5B447266A"})
  self.assertEqual(self.contract["bindings"]["stored_index_contract"], {"path":"data/expanded_256_stored_index_evidence.json","file_sha256":"02C0957E2A6ED5F702955821F68CE7A8A751C4C807FE5C34665DCA6FF00E786A","canonical_sha256":"EFE728FCBBD55E28B1D410E72D5BE701B4514951DCD261F0AE0474AC7B511274"})
  for k in ("stored_index_contract","runtime_contract","runtime_harness"):
   with self.subTest(k=k): self.fails(lambda d,key=k:d["bindings"][key].__setitem__("file_sha256","0"*64),"binding is stale")
 def test_schema_is_strict_and_digest_bound(self):
  schema=json.loads((ROOT/"data"/"schemas"/"expanded_256_save_serializer_abi_evidence.schema.json").read_text(encoding="utf-8"))
  self.assertFalse(schema["additionalProperties"])
  self.assertFalse(schema["$defs"]["game"]["additionalProperties"])
  self.assertFalse(schema["$defs"]["requirement"]["additionalProperties"])
  self.assertEqual(schema["properties"]["required_requirements"]["minItems"],14)
  self.assertEqual(MODULE.file_sha(ROOT/self.contract["bindings"]["schema"]["path"]),self.contract["bindings"]["schema"]["file_sha256"])
 def test_missing_duplicate_reordered_requirements(self):
  self.fails(lambda d:d["games"]["vv4"]["evidence_matrix"].pop(),"missing, duplicate, or reordered")
  self.fails(lambda d:d["games"]["vv5"]["evidence_matrix"].__setitem__(1,copy.deepcopy(d["games"]["vv5"]["evidence_matrix"][0])),"missing, duplicate, or reordered")
  self.fails(lambda d:d["games"]["vv4"]["evidence_matrix"].reverse(),"missing, duplicate, or reordered")
 def test_partial_application_rejected(self):
  self.fails(lambda d:d["games"]["vv4"]["evidence_matrix"][0]["native_rows"].append(self.row("save_layout_sizes")),"nonqualifying rows must remain empty")
 def test_exact_row_count_and_digest(self):
  def count(d): self.complete(d); d["games"]["vv4"]["evidence_matrix"][1]["expected_row_count"]=2
  self.fails(count,"row count is incomplete")
  def digest(d): self.complete(d); d["games"]["vv4"]["evidence_matrix"][1]["row_ledger_sha256"]="0"*64
  self.fails(digest,"ledger digest is stale")
 def test_synthetic_and_manual_injection(self):
  self.fails(lambda d:self.complete(d,self.row(synthetic=True)),"synthetic evidence")
  def injected(d): r=self.row(); r["manual_observation"]=True; self.complete(d,r)
  self.fails(injected,"fields are incomplete or injected")
 def test_static_description_not_authenticated(self):
  def mutate(d): r=self.row(); r["artifact"]["evidence_class"]="static_description"; self.complete(d,r)
  self.fails(mutate,"unauthenticated or stale")
 def test_exact_abi_fields_and_xrefs_required(self):
  for f in ("function_ea","file_offset","preimage","calling_convention","return_semantics","failure_semantics","xrefs"):
   def mutate(d,field=f): r=self.row(); r[field]=[] if field=="xrefs" else ""; self.complete(d,r)
   with self.subTest(f=f): self.fails(mutate,"exact native evidence is incomplete")
 def test_runtime_and_player_receipts_required(self):
  def runtime(d): self.complete(d); d["games"]["vv4"]["evidence_matrix"][1]["runtime_receipt_refs"]=[]
  self.fails(runtime,"authenticated receipts are missing")
  def player(d): self.complete(d); d["games"]["vv4"]["evidence_matrix"][1]["player_receipt_refs"]=[]
  self.fails(player,"authenticated receipts are missing")
 def test_folder_and_layout_required(self):
  self.fails(lambda d:self.complete(d),"complete-folder receipt is absent")
  def layout(d): self.complete(d); d["games"]["vv4"]["complete_folder"]={"status":"observed_complete","inventory_sha256":"A"*64,"authenticated":True}
  self.fails(layout,"exact save layouts are absent")
 def test_docs_preserve_stop(self):
  t=" ".join(DOC.read_text(encoding="utf-8").split())
  for p in ("fourteen required evidence classes","13-row VV4","66-row VV5","checked-in evidence matrix is empty","No game was launched","no save was accessed","publication remains false"): self.assertIn(p,t)
if __name__=="__main__": unittest.main()
