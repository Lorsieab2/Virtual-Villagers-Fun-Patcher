"""A villager's sex changed (native/shared/sex_change.h): "VVFP Last Names.dll" keeps their own last-name rule.

A villager's own rule is kept in the village's Last Names record as a line
    villager<TAB><name><TAB><head><TAB><body><TAB><M or F><TAB><rule>
keyed by the sex too.  On a change the DLL's VvfpVillagerSexChanged rewrites that line's M / F to the new sex at
once (every other byte of the record kept), and at a birth a parent -- recorded in the father's or the mother's
place at conception, so possibly of the other sex now -- whose line has the other sex still has their own rule,
only when the slot's "Sex Changes" log names them (never a guess).

The shipped source runs in native/vvfp_last_names/last_names_harness.c section 15 (built and run by
tests/test_last_names_own_rules.py, which counts and requires every check); here: the section names those checks, the
birth asks by the parent's place, and the DLL exports VvfpVillagerSexChanged.
"""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DLL = ROOT / "assets" / "last_names" / "VVFP Last Names.dll"
HARNESS = ROOT / "native" / "vvfp_last_names" / "last_names_harness.c"
SOURCE = ROOT / "native" / "vvfp_last_names" / "vvfp_last_names.c"


class LastNamesSexChange(unittest.TestCase):
    def test_the_dll_exports_it(self):
        try:
            import pefile
        except ImportError:  # pragma: no cover - environment dependent
            self.skipTest("pefile is not installed")
        pe = pefile.PE(str(DLL), fast_load=True)
        pe.parse_data_directories([pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_EXPORT"]])
        self.assertIn(b"VvfpVillagerSexChanged", {e.name for e in pe.DIRECTORY_ENTRY_EXPORT.symbols})

    def test_the_harness_proves_it(self):
        text = HARNESS.read_text(encoding="latin-1")
        section = text.split('printf("15. A sex change', 1)[1].split("== %d check(s)", 1)[0]
        for proven in ("only that line's sex is rewritten, every other byte kept",
                       "without the log, a father's line of the other sex is never his",
                       "with the log naming them, the recorded father's own rule (mother) still applies",
                       "a name the log does not name: the village's rule"):
            self.assertIn(proven, section)

    def test_a_parent_is_found_by_the_place_not_the_sex_now(self):
        source = SOURCE.read_text(encoding="latin-1")
        self.assertIn("use = decide(parent_rule(father, father_head, father_body, 'M', slot),", source)
        self.assertIn("parent_rule(mother, mother_head, mother_body, 'F', slot), rule[0]);", source)


if __name__ == "__main__":
    unittest.main()
