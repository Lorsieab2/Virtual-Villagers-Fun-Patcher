import copy,json,tempfile,unittest
from pathlib import Path
from scripts.validate_x45_expanded256_reference_audit import AUDIT,ROOT,validate
class AuditTests(unittest.TestCase):
 def setUp(self): self.d=json.loads(AUDIT.read_text(encoding="utf-8"))
 def bad(self,fn):
  d=copy.deepcopy(self.d); fn(d)
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/"a.json"; p.write_text(json.dumps(d),encoding="utf-8")
   with self.assertRaises(ValueError): validate(p,ROOT)
 def test_valid_stop(self): self.assertEqual(validate()["status"],"audit_stop")
 def test_publication_rejected(self): self.bad(lambda d:d["publication"].update(enabled=True))
 def test_ledger_mutation_rejected(self): self.bad(lambda d:d.update(ledger_changes_allowed=True))
 def test_vv4_pin_rejected(self): self.bad(lambda d:d["games"]["vv4"]["ledger"].update(count=12))
 def test_vv5_pin_rejected(self): self.bad(lambda d:d["games"]["vv5"]["ledger"].update(canonical_json_sha256="0"*64))
 def test_vv5_integration_pin_is_distinct(self): self.assertNotEqual(self.d["games"]["vv5"]["ledger"]["current_digest"],self.d["games"]["vv5"]["ledger"]["integration_digest"])
 def test_stale_classification_rejected(self): self.bad(lambda d:d["legacy_stale_references"][0].update(classification="safe"))
 def test_runtime_gate_rejected(self): self.bad(lambda d:d["gates"].update(runtime_receipts="observed_go"))
 def test_rel32_policy_rejected(self): self.bad(lambda d:d["games"]["vv5"]["rel32_policy"].update(external_targets_must_not_move=False))
 def test_empty_evidence_rejected(self): self.bad(lambda d:d["evidence"].append({"synthetic":True}))
if __name__=="__main__": unittest.main()
