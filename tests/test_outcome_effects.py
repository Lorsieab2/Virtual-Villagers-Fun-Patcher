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
        for nid in oe.table()[f]:
            doc["nodes"][nid].pop("effects", None)
        self.assertTrue(oe.missing(doc, p))
        again = oe.apply(json.loads(json.dumps(doc)), p)
        self.assertEqual(oe.missing(again, p), [])
        self.assertEqual(oe.apply(json.loads(json.dumps(again)), p), again)   # idempotent

    def test_text_is_never_changed(self):
        for f in oe.table():
            p = oe.COLLECTION_DIR / f
            doc = json.loads(p.read_text(encoding="utf-8"))
            before = {k: {x: y for x, y in n.items() if x != "effects"} for k, n in doc["nodes"].items()}
            after = oe.apply(json.loads(json.dumps(doc)), p)
            self.assertEqual(before, {k: {x: y for x, y in n.items() if x != "effects"} for k, n in after["nodes"].items()})

    def test_listed_files_pass_collection_check(self):
        rows = cc.manifest_rows()
        for f in oe.table():
            rep = cc.check_file(oe.COLLECTION_DIR / f, rows)
            self.assertTrue(rep.ok, (f, rep.problems))


if __name__ == "__main__":
    unittest.main()
