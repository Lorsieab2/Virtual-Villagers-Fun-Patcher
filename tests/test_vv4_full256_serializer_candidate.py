import copy,json,subprocess,sys,tempfile,unittest
from pathlib import Path
from scripts.build_vv4_full256_serializer_candidate import MODEL,ROOT,rel32,validate

class CandidateTests(unittest.TestCase):
 def setUp(self): self.d=json.loads(MODEL.read_text(encoding="utf-8"))
 def bad(self,fn):
  d=copy.deepcopy(self.d); fn(d)
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/"m.json"; p.write_text(json.dumps(d),encoding="utf-8")
   with self.assertRaises(ValueError): validate(p)
 def test_model(self): self.assertEqual(validate()["status"],"blocked_static_model")
 def test_exact_jumps(self): self.assertEqual(rel32(0x4660A0,0x871000),"E95BAF4000"); self.assertEqual(rel32(0x466110,0x871100),"E9EBAF4000")
 def test_enable_rejected(self): self.bad(lambda d:d.update(enabled=True))
 def test_native_output_rejected(self): self.bad(lambda d:d.update(native_output=True))
 def test_composed_parent_rejected(self): self.bad(lambda d:d["parent"].update(sha256="0"*64))
 def test_section_overlap_rejected(self): self.bad(lambda d:d["section"].update(raw_start=0xE2FFF))
 def test_header_claim_rejected(self): self.bad(lambda d:d["section"].update(header_guard="00"*40))
 def test_hook_preimage_rejected(self): self.bad(lambda d:d["hooks"][0].update(before="90"*5))
 def test_hook_target_rejected(self): self.bad(lambda d:d["hooks"][1].update(target=0x871101))
 def test_d353_helper_hash_rejected(self): self.bad(lambda d:d["d353_helpers"]["decode"].update(sha256="0"*64))
 def test_instruction_model_truncation_rejected(self): self.bad(lambda d:d["wrapper_model"]["serializer"].update(instruction_model=[]))
 def test_register_contract_rejected(self): self.bad(lambda d:d["wrapper_model"]["serializer"].update(preserves=["EBX"]))
 def test_tail_semantics_rejected(self): self.bad(lambda d:d["wrapper_model"]["deserializer"].update(full_256_unterminated="read tail"))
 def test_final_bytes_rejected(self): self.bad(lambda d:d["final"].update(serializer_bytes="90"))
 def test_checksum_claim_rejected(self): self.bad(lambda d:d["uninstall"].update(checksum_after=1))
 def test_writer_guard_rejected(self): self.bad(lambda d:d["writer_model"]["entry"].update(before="90"*6))
 def test_writer_target_placeholder_rejected(self): self.bad(lambda d:d["writer_model"]["entry"].update(target=0x871200))
 def test_writer_resolver_placeholder_rejected(self): self.bad(lambda d:d["writer_model"].update(resolver_bytes="90"))
 def test_replace_existing_weakening_rejected(self): self.bad(lambda d:d["writer_model"]["atomic_contract"].update(final_absent="MoveFileExA replace existing"))
 def test_nonfatal_writer_failure_rejected(self): self.bad(lambda d:d["writer_model"]["atomic_contract"].update(failure_policy="return false and continue"))
 def test_cli_requires_dry_run(self):
  r=subprocess.run([sys.executable,str(ROOT/"scripts/build_vv4_full256_serializer_candidate.py")],capture_output=True,text=True); self.assertNotEqual(r.returncode,0)
 def test_cli_dry_run(self):
  r=subprocess.run([sys.executable,str(ROOT/"scripts/build_vv4_full256_serializer_candidate.py"),"--dry-run"],capture_output=True,text=True); self.assertEqual(r.returncode,0); self.assertIn("STOP",r.stdout)

if __name__=="__main__": unittest.main()
