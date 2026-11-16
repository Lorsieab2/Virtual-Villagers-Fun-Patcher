"""A villager's sex changed (native/shared/sex_change.h): "VVFP VV1 Parentage.dll" keeps their parents (A New Home).

The companion keeps each record's occupant (name, sex, family scalar, looks) and follows them from look to look and
load to load by that identity, so a sex change read as somebody else would take the villager for a departure and a
newcomer and drop their parents.  Its VvfpVillagerSexChanged carries the roster's sex at once and writes the file;
at a load the slot's "Sex Changes" log carries an entry written before (or after) a save it does not match; and a
parent recorded in the father's or the mother's place is found though their sex changed (vv1_only_looks_in) --
only when the log names them.

native/vv1_parentage/vv1_parentage_sidecar_harness.c compiles the companion's own source and runs these on real
files (tests/test_vv1_parentage_sidecar.py builds it); here: every sex-change case is run and passes, and the DLL
exports VvfpVillagerSexChanged.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

import test_vv1_parentage_sidecar as sidecar  # noqa: E402

DLL = ROOT / "assets" / "parentage" / "VVFP VV1 Parentage.dll"
CASES = (
    "the change is carried",
    "in play the parents stay theirs",
    "written at once, a reload with the new sex finds them",
    "without the word the parents are not hers (the control)",
    "without the log, a save older than the change does not find them",
    "with the slot's log naming them, it does",
    "a namesake is never guessed",
    "without the log a father is never taken for a woman of his name",
    "with the log the recorded father is found, whatever his sex now",
)


class Vv1ParentageSexChange(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sidecar.Vv1ParentageSidecarHarnessTests.setUpClass()
        cls.out = sidecar.Vv1ParentageSidecarHarnessTests.result.stdout

    @classmethod
    def tearDownClass(cls):
        sidecar.Vv1ParentageSidecarHarnessTests.tearDownClass()

    def test_every_case_passes(self):
        self.assertIn("0 failure(s)", self.out, self.out[-3000:])
        for case in CASES:
            self.assertIn("PASS sex change: " + case, self.out)

    def test_the_dll_exports_it(self):
        try:
            import pefile
        except ImportError:  # pragma: no cover - environment dependent
            self.skipTest("pefile is not installed")
        pe = pefile.PE(str(DLL), fast_load=True)
        pe.parse_data_directories([pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_EXPORT"]])
        self.assertIn(b"VvfpVillagerSexChanged", {e.name for e in pe.DIRECTORY_ENTRY_EXPORT.symbols})


if __name__ == "__main__":
    unittest.main()
