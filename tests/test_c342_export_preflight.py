import json,tempfile,unittest
from pathlib import Path
from scripts.validate_c342_export_preflight import CONTRACT,ROOT,PreflightError,validate
class PreflightTests(unittest.TestCase):
 def test_missing_inputs_stop(self):
  with self.assertRaises(PreflightError): validate()
 def test_missing_folder_stop(self):
  with tempfile.TemporaryDirectory() as td:
   with self.assertRaises(PreflightError): validate(Path(td),Path(td)/"vv4",Path(td)/"vv5",None,None)
 def test_contract_is_disabled(self):
  d=json.loads(CONTRACT.read_text(encoding="utf-8")); self.assertTrue(d["status"].startswith("preflight_stop")); self.assertFalse(any(d["gates"][k] for k in ("enabled","catalog","native_output","runtime_go","player_go","publication"))); self.assertEqual(d["gates"]["evidence"],[])
 def test_exact_rebind_pins(self):
  d=json.loads(CONTRACT.read_text(encoding="utf-8")); self.assertEqual(d["c342_rebind"]["vv4"]["ledger_count"],13); self.assertEqual(d["c342_rebind"]["vv5"]["ledger_count"],66); self.assertNotEqual(d["c342_rebind"]["vv5"]["ledger_sha256"],"A5DF4E109D32E2BC9FDE36E2BA3139230B6E6CD89DE4C3FF784846F4CE803740")
if __name__=="__main__": unittest.main()
