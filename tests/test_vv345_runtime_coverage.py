from __future__ import annotations
import copy,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"src"))
from vv345_runtime_coverage import CATALOG,INDICES,MODES,SAVE_SCENARIOS,SCENARIOS,validate
class RuntimeCoverageTests(unittest.TestCase):
 def setUp(self):self.data=json.loads((ROOT/"data/vv345_runtime_coverage_matrix.json").read_text(encoding="utf-8"))
 def test_checked_in_matrix_is_structural_stop(self):
  r=validate(self.data,ROOT);self.assertTrue(r.structural,r.errors);self.assertFalse(r.complete);self.assertFalse(r.publication)
 def test_exact_catalog_inventory(self):
  self.assertEqual(sum(map(len,CATALOG.values())),16)
  for g,ids in CATALOG.items():self.assertEqual(tuple(self.data["catalog_visible"][g]),ids)
 def test_exact_modes_and_boundaries(self):
  for g in CATALOG:self.assertEqual(tuple(self.data["expanded_modes"][g]),MODES)
  self.assertEqual(tuple(self.data["late_record_indices"]),INDICES)
 def test_every_patch_requires_windowed_fullscreen_and_outcomes(self):
  self.assertEqual(tuple(self.data["required_scenarios"]),SCENARIOS);self.assertIn("uninstall",SCENARIOS);self.assertIn("crash_hang_monitoring",SCENARIOS)
 def test_every_expanded_mode_requires_save_lifecycle(self):self.assertEqual(tuple(self.data["save_scenarios"]),SAVE_SCENARIOS)
 def test_rejects_missing_duplicate_and_stale_catalog(self):
  for mutation in ("missing","duplicate","stale"):
   bad=copy.deepcopy(self.data)
   if mutation=="missing":bad["catalog_visible"]["vv3"].pop()
   elif mutation=="duplicate":bad["catalog_visible"]["vv4"].append(bad["catalog_visible"]["vv4"][0])
   else:bad["source_commit"]="0"*40
   self.assertTrue(validate(bad,ROOT).errors)
 def test_rejects_enabled_or_receipts_in_checked_in_contract(self):
  bad=copy.deepcopy(self.data);bad["flags"]["publication"]=True;self.assertIn("all flags must remain false",validate(bad,ROOT).errors)
  bad=copy.deepcopy(self.data);bad["receipts"]=[{}];self.assertIn("checked-in receipts must be empty",validate(bad,ROOT).errors)
 def test_existing_evidence_paths_are_exact_c348_relative_bindings(self):
  paths=self.data["existing_evidence"]
  self.assertEqual(paths["fullscreen"],"data/fullscreen_owner_transition_evidence.json")
  self.assertEqual(paths["expanded_vv4_vv5"],"data/expanded_256_runtime_evidence.json")
  self.assertTrue(all(isinstance(p,str) and not Path(p).is_absolute() and ".." not in Path(p).parts for p in paths.values()))
if __name__=="__main__":unittest.main()
