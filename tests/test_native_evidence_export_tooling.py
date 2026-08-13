from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import native_evidence_export as tool

class NativeEvidenceExportToolingTests(unittest.TestCase):
    def _folder(self, root: Path):
        folder=root/"copied-vv3"; folder.mkdir(); payload=b"MZ"+bytes(range(64)); exe=folder/"fixture.exe"; exe.write_bytes(payload); (folder/"asset.dat").write_bytes(b"asset"); return folder,payload

    def test_inventory_is_stable_sorted_and_self_contained(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); folder,payload=self._folder(root)
            with patch.dict(tool.GAMES,{"vv3":("fixture.exe",len(payload),tool.sha(payload))},clear=False): inv=tool.inventory_folder(root,folder,"vv3")
            self.assertEqual(inv["file_count"],2); self.assertEqual([x["path"] for x in inv["files"]],["asset.dat","fixture.exe"])
            self.assertEqual(inv["inventory_sha256"],tool.sha(tool.canonical_json({k:v for k,v in inv.items() if k!="inventory_sha256"})))

    def test_outside_empty_wrong_fingerprint_and_link_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); empty=root/"empty"; empty.mkdir()
            with self.assertRaises(tool.EvidenceError): tool.inventory_folder(root,root,"vv3")
            with self.assertRaises(tool.EvidenceError): tool.inventory_folder(root,empty,"vv3")
            folder,_=self._folder(root)
            with self.assertRaises(tool.EvidenceError): tool.inventory_folder(root,folder,"vv3")
            try:
                (folder/"linked").symlink_to(folder/"asset.dat")
            except OSError: return
            with patch.dict(tool.GAMES,{"vv3":("fixture.exe",66,tool.sha((folder/"fixture.exe").read_bytes()))},clear=False):
                with self.assertRaises(tool.EvidenceError): tool.inventory_folder(root,folder,"vv3")

    def test_plan_is_dry_and_complete(self):
        ids=[q["id"] for q in tool.dry_run_plan({"game":"vv3","inventory_sha256":"A"*64})["queries"]]
        self.assertEqual(len(ids),10); self.assertEqual(len(ids),len(set(ids)))
        self.assertEqual(tool.dry_run_plan({"game":"vv3","inventory_sha256":"A"*64})["writes"],[])

    def _valid_export(self, inv, exe):
        queries=json.loads(tool.QUERY_PATH.read_text())["queries"]; rows=[]
        for q in queries:
            rows.append({"query_id":q["id"],"status":"resolved","function_start_ea":"0x401000","function_end_ea":"0x401002","file_offset":"0x0","raw_bytes":exe[:2].hex().upper(),"instructions":[{"ea":"0x401000","text":"dec eax"}],"callers":[],"xrefs":[],"registers":{"inputs":["ecx"],"outputs":["eax"]},"stack_cleanup":"callee ret 4","call_convention":"__thiscall"})
        data={"schema":"vvfp.authenticated-native-export.v1","generated_by":"ida_python","synthetic":False,"manual":False,"game":"vv3","inventory_sha256":inv["inventory_sha256"],"functions":rows}; data["artifact_sha256"]=tool.sha(tool.canonical_json(data)); return data

    def test_valid_export_and_adversarial_partial_synthetic_manual_stale_bytes(self):
        inv={"game":"vv3","inventory_sha256":"A"*64}; exe=b"MZpayload"; good=self._valid_export(inv,exe)
        self.assertEqual(tool.validate_export(good,inv,exe),[])
        cases=[]
        for key in ("synthetic","manual"):
            item=copy.deepcopy(good); item[key]=True; cases.append(item)
        item=copy.deepcopy(good); item["functions"].pop(); cases.append(item)
        item=copy.deepcopy(good); item["functions"][0]["raw_bytes"]="FFFF"; cases.append(item)
        item=copy.deepcopy(good); item["functions"][0]["registers"]={}; cases.append(item)
        item=copy.deepcopy(good); item["inventory_sha256"]="B"*64; cases.append(item)
        for item in cases:
            item["artifact_sha256"]=tool.sha(tool.canonical_json({k:v for k,v in item.items() if k!="artifact_sha256"}))
            self.assertTrue(tool.validate_export(item,inv,exe))
        fixture=json.loads((ROOT/"tests/fixtures/native_evidence_export/adversarial_cases.json").read_text())
        self.assertEqual(len(fixture["rejected_cases"]),len(cases))

    def test_clean_archive_and_windows_checkout_query_manifest_match(self):
        blob=subprocess.run(["git","show","HEAD:data/native_evidence_queries.json"],cwd=ROOT,capture_output=True)
        if blob.returncode == 0:
            sys.path.insert(0,str(ROOT/"src")); from vv_fun_patcher import source_text_sha256
            self.assertEqual(source_text_sha256(blob.stdout),source_text_sha256(tool.QUERY_PATH.read_bytes()))

if __name__ == "__main__": unittest.main()
