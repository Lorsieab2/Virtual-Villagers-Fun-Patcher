import copy, json, tempfile, unittest
from pathlib import Path
from scripts.validate_vv4_full256_serializer_evidence import DATA, ROOT, validate

class ContractTests(unittest.TestCase):
    def setUp(self): self.doc=json.loads(DATA.read_text(encoding="utf-8"))
    def check_bad(self, mutate):
        d=copy.deepcopy(self.doc); mutate(d)
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"c.json"; p.write_text(json.dumps(d),encoding="utf-8")
            with self.assertRaises(ValueError): validate(p,ROOT)
    def test_checked_in_contract(self): self.assertTrue(validate())
    def test_publication_rejected(self): self.check_bad(lambda d:d["publication"].update(enabled=True))
    def test_wrong_geometry_rejected(self): self.check_bad(lambda d:d["geometry"].update(expanded_file=122059))
    def test_terminator_row_rejected(self): self.check_bad(lambda d:d["stock_functions"]["serializer"]["rows"][21].__setitem__(1,"90"))
    def test_reader_unknown_row_removed_rejected(self): self.check_bad(lambda d:d["stock_functions"]["deserializer"].update(unresolved_exact_rows=[]))
    def test_one_immediate_overclaim_rejected(self): self.check_bad(lambda d:d["current_candidate"].update(status="complete"))
    def test_nonnull_hook_rejected(self): self.check_bad(lambda d:d["replacement"].update(serializer_hook_target="0x1234"))
    def test_atomic_gate_claim_rejected(self): self.check_bad(lambda d:d["atomic_writer"]["completed"].append("sibling_temp"))
    def test_synthetic_receipt_rejected(self): self.check_bad(lambda d:d["runtime_fault_matrix"]["receipts"].append({"synthetic":True}))
    def test_ledger_count_rejected(self): self.check_bad(lambda d:d["bindings"]["vv4_relocation_ledger"].update(count=12))
    def test_c342_digest_rejected(self): self.check_bad(lambda d:d["bindings"]["c342_vv5_relocation_ledger"].update(digest="00"*32))

if __name__=="__main__": unittest.main()
