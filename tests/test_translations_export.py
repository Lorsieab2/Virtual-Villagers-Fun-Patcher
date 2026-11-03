"""Exporting several translation files at once never lets one overwrite another."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import vv_translations as vt  # noqa: E402


class ExportManyTests(unittest.TestCase):
    def test_same_named_files_get_distinct_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "installed").mkdir()
            (root / "shipped").mkdir()
            ana, bob = root / "installed" / "fr.tsv", root / "shipped" / "fr.tsv"
            ana.write_text("Ana", encoding="utf-8")
            bob.write_text("Bob", encoding="utf-8")
            other = root / "shipped" / "de.tsv"
            other.write_text("Otto", encoding="utf-8")
            out = root / "out"
            out.mkdir()
            done, problems = vt.export_many([ana, bob, other], out)
            self.assertEqual(problems, [])
            self.assertEqual([p.name for p in done], ["fr.tsv", "fr (2).tsv", "de.tsv"])
            self.assertEqual((out / "fr.tsv").read_text(encoding="utf-8"), "Ana")
            self.assertEqual((out / "fr (2).tsv").read_text(encoding="utf-8"), "Bob")
            self.assertEqual((out / "de.tsv").read_text(encoding="utf-8"), "Otto")

    def test_case_only_differences_count_as_the_same_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a, b = root / "a" / "FR.tsv", root / "b" / "fr.tsv"
            a.parent.mkdir()
            b.parent.mkdir()
            a.write_text("A", encoding="utf-8")
            b.write_text("B", encoding="utf-8")
            out = root / "out"
            out.mkdir()
            done, problems = vt.export_many([a, b], out)
            self.assertEqual(problems, [])
            self.assertEqual(len({p.name.casefold() for p in done}), 2)


if __name__ == "__main__":
    unittest.main()
