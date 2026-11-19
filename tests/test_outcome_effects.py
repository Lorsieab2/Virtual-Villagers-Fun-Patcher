"""The owner's text-implied outcome effects (scripts/outcome_effects.py): every list parses, every active line is in
its event file, and collection_check fails a file that lacks one."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import collection_check as cc  # noqa: E402
import outcome_effects as oe  # noqa: E402


class OutcomeEffectsTest(unittest.TestCase):
    def test_every_list_parses(self):
        files = sorted(oe.LISTS.glob("*.txt")) + sorted((oe.LISTS / "pending").glob("*.txt"))
        self.assertTrue(files)
        for p in files:
            for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                row = oe.parse_line(line, f"{p.name}:{i}")
                if row:
                    self.assertTrue(row["quote"].startswith('"') and row["quote"].endswith('"'), (p.name, i))

    def test_active_lines_are_in_their_files(self):
        table = oe.table()
        self.assertTrue(table)
        for f in table:
            p = oe.COLLECTION_DIR / f
            self.assertTrue(p.exists(), f)
            doc = json.loads(p.read_text(encoding="utf-8"))
            self.assertEqual(oe.missing(doc, p), [], f)

    def test_check_fails_without_the_effect(self):
        f = next(iter(sorted(oe.table())))
        p = oe.COLLECTION_DIR / f
        doc = json.loads(p.read_text(encoding="utf-8"))
        for nid in oe.table()[f]:          # back to the page as it was before this pass
            doc["nodes"][nid] = doc["nodes"].pop(oe.text_id(nid))
            doc["nodes"].pop(oe.fx_id(nid))
        self.assertTrue(oe.missing(doc, p))
        again = oe.apply(json.loads(json.dumps(doc)), p)
        self.assertEqual(oe.missing(again, p), [])
        self.assertEqual(oe.apply(json.loads(json.dumps(again)), p), again)   # idempotent
        for nid in oe.table()[f]:          # the 50%: an even split to two copies of the same page
            head, fx, plain = (again["nodes"][k] for k in (nid, oe.fx_id(nid), oe.text_id(nid)))
            self.assertEqual(head["type"], "branch")
            self.assertEqual([c["next"] for c in head["children"]], [oe.fx_id(nid), oe.text_id(nid)])
            self.assertEqual({k: v for k, v in fx.items() if k not in ("effects", "auto_text")},
                             {k: v for k, v in plain.items() if k not in ("effects", "auto_text")})

    def test_text_is_never_changed(self):
        for f in oe.table():
            p = oe.COLLECTION_DIR / f
            doc = json.loads(p.read_text(encoding="utf-8"))
            before = {k: {x: y for x, y in n.items() if x != "effects"} for k, n in doc["nodes"].items()}
            after = oe.apply(json.loads(json.dumps(doc)), p)
            self.assertEqual(before, {k: {x: y for x, y in n.items() if x != "effects"} for k, n in after["nodes"].items()})

    def test_death_and_leaving_wording(self):
        page = {"text": "A fall on the rocks.", "effects": [{"do": "kill", "role": "a", "cause": "unknown"}]}
        self.assertEqual(oe.wording(page, page["effects"][0]), "injuries")
        page = {"text": "She sets out to live with her cousins.", "effects": [{"do": "vanish", "role": "a"}]}
        self.assertEqual(oe.wording(page, page["effects"][0]), "leaves")
        page = {"text": "They set off alone and go missing.", "effects": [{"do": "vanish", "role": "a"}]}
        self.assertIsNone(oe.wording(page, page["effects"][0]))
        done = oe.finish({"nodes": {"p": dict(page, effects=[dict(page["effects"][0])])}})
        self.assertTrue(done["nodes"]["p"]["auto_text"])

    def test_the_line_flag_compiles_and_reads_back(self):
        sys.path.insert(0, str(ROOT / "src"))
        import vv_cie_graph as cg
        for do, line, key in (("kill", "injuries", "<R> suffers fatal injuries."),
                              ("vanish", "leaves", "<R> leaves the village.")):
            e = {"do": do, "role": "subject", "line": line}
            if do == "kill":
                e["cause"] = "unknown"
            g = {"format": "vvfp-cie-graph", "version": 6, "title": "T", "games": [3], "roles": {"subject": {"kind": "villager"}},
                 "start": "p", "nodes": {"p": {"text": "x.", "auto_text": True, "effects": [e]}}}
            lg = cg.load(g, True)
            back = cg.decompile_graph(cg.compile_graph(lg))
            self.assertEqual(back["nodes"]["p"]["effects"][0].get("line"), line)
            self.assertEqual(cg.AUTO_LINES[f"{do}_{line}"], key)
            self.assertEqual(cg.auto_line_options(lg["nodes"]["p"]["effects"][0], 3),
                             [key.replace("<R>", "(subject.Name)")])

    def test_listed_files_pass_collection_check(self):
        # A spread sample (collection_check itself, and test_event_collection_files, check every file).
        rows = cc.manifest_rows()
        listed = sorted(oe.table())
        for f in listed[::max(1, len(listed) // 25)]:
            rep = cc.check_file(oe.COLLECTION_DIR / f, rows)
            self.assertTrue(rep.ok, (f, rep.problems))


if __name__ == "__main__":
    unittest.main()
