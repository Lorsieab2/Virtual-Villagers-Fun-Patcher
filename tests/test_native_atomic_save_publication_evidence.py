from __future__ import annotations
import copy, json, sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from native_atomic_save_publication_evidence import EXPECTED_STOCK, REQUIREMENTS, validate

class AtomicSaveEvidenceTests(unittest.TestCase):
    def setUp(self): self.data=json.loads((ROOT/"data/native_atomic_save_publication_evidence.json").read_text(encoding="utf-8"))
    def test_checked_in_contract_is_structural_stop(self):
        r=validate(self.data); self.assertTrue(r.structural); self.assertFalse(r.evidence_complete); self.assertFalse(r.publication_allowed)
    def test_exact_stock_pins(self):
        for game,(name,size,sha) in EXPECTED_STOCK.items(): self.assertEqual((self.data["games"][game]["stock"]["exe_name"],self.data["games"][game]["stock"]["size"],self.data["games"][game]["stock"]["sha256"]),(name,size,sha))
    def test_all_publication_flags_fail_closed(self):
        for flag in ("enabled","native_emission","runtime_certified","player_certified","publication"):
            bad=copy.deepcopy(self.data); bad[flag]=True; self.assertIn(f"{flag} must remain false",validate(bad).errors)
    def test_rejects_backup_rotation_and_serializer_arithmetic(self):
        for proof in ("stock_backup_rotation","serializer_arithmetic_only"):
            bad=copy.deepcopy(self.data); row={"requirement": REQUIREMENTS[0],"verified":True,"synthetic":False,"stale":False,"proof_class":proof}; bad["games"]["vv3"]["evidence"]=[row]*len(REQUIREMENTS); self.assertTrue(any("nonqualifying" in e or "duplicate" in e for e in validate(bad).errors))
    def test_rejects_synthetic_duplicate_missing_and_stale(self):
        bad=copy.deepcopy(self.data); bad["games"]["vv4"]["evidence"]=[{"requirement":r,"verified":True,"synthetic":r==REQUIREMENTS[0],"stale":r==REQUIREMENTS[1],"proof_class":"native_observation"} for r in REQUIREMENTS]; self.assertTrue(any("synthetic/stale" in e for e in validate(bad).errors)); bad["games"]["vv4"]["evidence"].pop(); self.assertTrue(any("one evidence row" in e for e in validate(bad).errors))
    def test_wrong_fingerprint_and_unknown_abi_rejected(self):
        bad=copy.deepcopy(self.data); bad["games"]["vv5"]["stock"]["sha256"]="0"*64; bad["games"]["vv5"]["native"]["header_writer"]={}; r=validate(bad); self.assertIn("vv5 stock fingerprint mismatch",r.errors); self.assertIn("vv5 exact header_writer ABI missing",r.errors)
    def test_catalog_loader_has_no_atomic_save_feature(self):
        text=(ROOT/"src/vv_fun_patcher.py").read_text(encoding="utf-8"); self.assertNotIn("native_atomic_save_publication",text)
    def test_no_native_output_or_save_access(self):
        for rel in ("src/native_atomic_save_publication_evidence.py","scripts/validate_native_atomic_save_publication_evidence.py"):
            text=(ROOT/rel).read_text(encoding="utf-8");
            for token in ("open(\"wb\"","open('wb'","os.replace","shutil.copy","Savegame"):
                self.assertNotIn(token,text)
if __name__=="__main__": unittest.main()
