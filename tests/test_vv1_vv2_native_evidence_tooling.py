import copy, hashlib, importlib.util, json, shutil, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import vv_native_evidence_inventory as inv
import vv_native_evidence_validate as val

H="A"*64
def good(manifest,inventory):
    binding={"executable_sha256":H,"folder_inventory_sha256":inventory["inventory_sha256"],"manifest_sha256":val.canonical_hash(manifest),"exporter_sha256":H,"analyzer_name":"IDA Pro","analyzer_version":"9.1"}
    raw=b"\x90\xC3"
    fn={"query_id":"funds_getter","topic":"funds","status":"resolved","function_name":"sub_401000","start_ea":"0x401000","end_ea":"0x401002","start_file_offset":512,"end_file_offset":514,"raw_bytes_sha256":hashlib.sha256(raw).hexdigest().upper(),"raw_bytes_hex":raw.hex().upper(),"instructions":[{"ea":"0x401000","file_offset":512,"raw_bytes":"90","mnemonic":"nop","operands":""}],"callers":[],"callees":[],"xrefs":[],"register_contract":"EAX return","stack_cleanup":"caller","return_contract":"EAX","side_effects":"none","source_binding":binding}
    e={"schema_version":1,"producer":"ida-python","automated_export":True,"manual_edits":False,"complete":True,"game_id":"vv1","source_binding":binding,"functions":[fn]}; e["artifact_sha256"]=val.canonical_hash(e); return e

class Tests(unittest.TestCase):
    def test_manifest_covers_every_authorized_query_family(self):
        m=json.loads((ROOT/"data/native_evidence/vv1_vv2_native_query_manifest.json").read_text())
        self.assertEqual(set(m["required_topics"]),{"selected_world_resolver","funds","age_and_statistics","preferences","confirmation","full_heal","fullscreen","persistence"})
        self.assertEqual(m["games"],["vv1","vv2"]); self.assertFalse(m["manual_exports_allowed"]); self.assertFalse(m["partial_exports_allowed"])

    def test_inventory_is_stable_complete_and_no_follow(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as td:
            root=Path(td)/"game"; root.mkdir(); (root/"game.exe").write_bytes(b"MZ"); (root/"SDL2.dll").write_bytes(b"dll")
            a=inv.inventory(root); b=inv.inventory(root); self.assertEqual(a,b); self.assertTrue(a["complete"]); self.assertEqual(a["dll_count"],1)

    def test_outside_workspace_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError): inv.inventory(Path(td))

    def test_dry_run_has_no_exports(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as td:
            root=Path(td)/"game"; root.mkdir(); (root/"game.exe").write_bytes(b"MZ"); (root/"SDL2.dll").write_bytes(b"dll")
            p=inv.plan("vv1",root,ROOT/"data/native_evidence/vv1_vv2_native_query_manifest.json"); self.assertTrue(p["dry_run"]); self.assertEqual(p["file_count"],2); self.assertEqual(p["dll_count"],1); self.assertEqual(p["launches_performed"],0); self.assertEqual(p["exports_written"],0)

    def test_valid_and_adversarial_exports(self):
        manifest=json.loads((ROOT/"tests/fixtures/native_evidence/minimal_manifest.json").read_text()); inventory={"inventory_sha256":H,"files":[{"path":"game.exe","size":2,"sha256":H}]}; base=good(manifest,inventory); self.assertTrue(val.validate(base,manifest,inventory))
        mutations=[]
        for mutate in (lambda e:e.__setitem__("complete",False),lambda e:e.__setitem__("manual_edits",True),lambda e:e["functions"].clear(),lambda e:e["functions"][0].__setitem__("function_name","synthetic"),lambda e:e["functions"][0].__setitem__("raw_bytes_hex","CC"),lambda e:e["source_binding"].__setitem__("folder_inventory_sha256","B"*64)):
            e=copy.deepcopy(base); mutate(e); e["artifact_sha256"]=val.canonical_hash({k:v for k,v in e.items() if k!="artifact_sha256"}); mutations.append(e)
        for e in mutations:
            with self.assertRaises(val.EvidenceError): val.validate(e,manifest,inventory)

    def test_templates_are_guarded_and_archive_is_scripts_only(self):
        gh=(ROOT/"scripts/ghidra_vv_native_evidence_export.py").read_text(); ida=(ROOT/"scripts/ida_vv_native_evidence_export.py").read_text(); self.assertIn("separately authorized",gh); self.assertIn("separately authorized",ida)
        allowed={".py",".json",".md"}
        rels=[Path("scripts/vv_native_evidence_inventory.py"),Path("scripts/vv_native_evidence_validate.py"),Path("scripts/ida_vv_native_evidence_export.py"),Path("scripts/ghidra_vv_native_evidence_export.py"),Path("data/native_evidence/vv1_vv2_native_query_manifest.json"),Path("docs/vv1-vv2-authenticated-native-export-tooling.md"),Path("tests/fixtures/native_evidence/minimal_manifest.json"),Path("tests/test_vv1_vv2_native_evidence_tooling.py")]
        with tempfile.TemporaryDirectory() as td:
            archive=Path(td)
            for rel in rels:
                (archive/rel).parent.mkdir(parents=True,exist_ok=True); shutil.copy2(ROOT/rel,archive/rel)
            files=[p for p in archive.rglob("*") if p.is_file()]
            self.assertEqual({p.relative_to(archive) for p in files},set(rels)); self.assertTrue(all(p.suffix in allowed for p in files))
if __name__=="__main__": unittest.main()
