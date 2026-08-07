import importlib.util,json,tempfile,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("builder",ROOT/"scripts"/"build_vv3_full256_serializer_candidate.py")
B=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(B)

class Full256StaticCandidateTests(unittest.TestCase):
    def setUp(self):self.value=B.build()
    def test_checked_in_model_is_deterministic(self):self.assertEqual(B.canonical_bytes(self.value),B.OUTPUT.read_bytes().replace(b"\r\n",b"\n"))
    def test_disabled_everywhere(self):
        self.assertFalse(self.value["enabled"]);self.assertFalse(self.value["catalog_visible"]);self.assertFalse(self.value["native_output"]);self.assertEqual("STOP",self.value["decision"]["status"])
    def test_exact_parents(self):self.assertEqual(B.PARENTS,tuple((x["mode"],x["sha256"]) for x in self.value["parents"]))
    def test_parent_layout(self):self.assertTrue(all(x["size"]=="0xCC000" and x["sections"]==6 and x["size_of_image"]=="0x3B9000" for x in self.value["parents"]))
    def test_results_unknown(self):self.assertTrue(all(x["result_sha256"] is None and x["pe_checksum"] is None for x in self.value["parents"]))
    def test_section_plan_exact_rx(self):
        s=self.value["section_plan"];self.assertEqual((".vv3sv","0x2F0","0xCC000","0xCD000","0x3B9000","0x7B9000","RX"),(s["name"],s["header_raw"],s["raw_start"],s["raw_end"],s["rva"],s["va"],s["characteristics"]))
    def test_section_bytes_absent(self):
        s=self.value["section_plan"];self.assertIsNone(s["header_bytes"]);self.assertIsNone(s["section_bytes"]);self.assertIsNone(s["final_bytes"])
    def test_hooks_exact_but_not_emitted(self):
        self.assertEqual([("0x27D57","E824720300","E8A4123900","0x7B9000"),("0x28A4C","E80F3E0300","E8AF073900","0x7B9200")],[(x["raw"],x["preimage"],x["expected"],x["target"]) for x in self.value["hooks"]]);self.assertTrue(all(x["emitted"] is None for x in self.value["hooks"]))
    def test_hook_roles_bind_stock_functions_callsites_and_targets(self):
        self.assertEqual(
            [("serializer","0x45EF80","0x27D57","0x427D57","0x7B9000"),("deserializer","0x45C860","0x28A4C","0x428A4C","0x7B9200")],
            [(x["id"],x["stock_function"],x["raw"],x["va"],x["target"]) for x in self.value["hooks"]],
        )
    def test_serializer_and_deserializer_roles_cannot_swap(self):
        hooks={x["id"]:x for x in self.value["hooks"]}
        self.assertEqual(("0x45EF80","0x27D57","0x7B9000"),tuple(hooks["serializer"][k] for k in ("stock_function","raw","target")))
        self.assertEqual(("0x45C860","0x28A4C","0x7B9200"),tuple(hooks["deserializer"][k] for k in ("stock_function","raw","target")))
    def test_abis_exact(self):self.assertEqual(B.ABIS,tuple((x["id"],x["start"],x["end"],x["sha256"],x["contract"]) for x in self.value["abis"]))
    def test_compact_base_uses_singleton(self):self.assertIn("0x428B60",self.value["wrapper_model"]["compact_base"]);self.assertIn("0x786C",self.value["wrapper_model"]["compact_base"])
    def test_padding_forbidden(self):self.assertEqual("256..259 forbidden",self.value["wrapper_model"]["padding"])
    def test_conditional_terminator(self):self.assertIn("terminator only when count<256",self.value["wrapper_model"]["serializer"])
    def test_reader_hard_bound(self):self.assertIn("read no more than 256 compact records",self.value["wrapper_model"]["deserializer"])
    def test_wrapper_bytes_absent(self):self.assertIsNone(self.value["wrapper_model"]["wrapper_bytes"]);self.assertIsNone(self.value["wrapper_model"]["wrapper_sha256"])
    def test_caller_blocker(self):
        g=self.value["caller_failure_gate"];self.assertTrue(g["load_caller_tests_al"]);self.assertFalse(g["save_caller_tests_al"]);self.assertFalse(g["recoverable_failure"]);self.assertIsNone(g["save_caller_after"])
    def test_d354_writer_plan_exact_and_disabled(self):
        w=self.value["atomic_writer_plan"];self.assertEqual(("0x403530","0x7B9400","0xCC400"),(w["stock_writer"],w["wrapper_va"],w["wrapper_raw"]));self.assertFalse(w["enabled"]);self.assertFalse(w["native_output"])
    def test_d354_calls_are_expectations_not_emission(self):
        rows=self.value["atomic_writer_plan"]["callsites"];self.assertEqual([("0x27C7D","E87E173900"),("0x27C92","E869173900"),("0x27D6C","E88F163900"),("0x27D81","E87A163900")],[(x["raw"],x["expected"]) for x in rows]);self.assertTrue(all(x["preimage"] is None and x["emitted"] is None for x in rows))
    def test_d354_resolver_and_wrapper_blocked(self):
        w=self.value["atomic_writer_plan"];self.assertIsNone(w["dynamic_api_resolver_bytes"]);self.assertIsNone(w["wrapper_bytes"]);self.assertIsNone(w["wrapper_sha256"]);self.assertIsNone(w["import_changes"]);self.assertIn("D355",w["blocker"])
    def test_atomic_contract_has_no_numeric_slot_or_replace_existing(self):
        tx=self.value["atomic_writer_plan"]["transaction"];self.assertIn("sibling temporary path without numeric save slot",tx);self.assertIn("existing final uses ReplaceFileA flags 0",tx);self.assertIn("absent final uses MoveFileExA WRITE_THROUGH without replace-existing",tx)
    def test_uninstall_restores_hooks_before_truncate(self):
        order=self.value["uninstall_ledger"]["order"];self.assertLess(order.index("restore and verify both hook preimages"),order.index("truncate only candidate-owned 0xCC000..0xCD000"))
    def test_check_rejects_stale_model(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"x.json";p.write_text("{}",encoding="utf-8")
            with self.assertRaises(SystemExit):B.main(["--check","--output",str(p)])
    def test_builder_has_no_native_input_or_emission(self):
        source=(ROOT/"scripts"/"build_vv3_full256_serializer_candidate.py").read_text(encoding="utf-8")
        for token in ("pefile","lief","keystone","capstone","stock-executables","subprocess"):
            self.assertNotIn(token,source.lower())
    def test_json_parses(self):json.loads(B.OUTPUT.read_text(encoding="utf-8"))

if __name__=="__main__":unittest.main()
