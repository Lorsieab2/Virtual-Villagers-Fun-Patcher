r"""A runtime harness must look where its exporter actually writes.

Both harnesses load the shipped DLL, drive an export, and read back the file
it wrote. That makes them the only evidence in this project that comes from
running the code rather than reading it -- and it also makes them silently
useless the moment the exporter's output path moves, because a harness that
cannot find the file reports exactly what a DLL writing nothing reports.

That is not hypothetical. When the logs moved into `VVFP Logs\<kind>\`
subfolders, the parentage harness was left addressing the save folder itself.
All 37 of its checks failed. It stayed that way across a release because the
harnesses need a 32-bit MSVC toolchain with hardcoded SDK paths and so do not
run in CI -- nothing was watching.

These guards need no toolchain. They compare the folder literal each harness
builds against the one its exporter builds, so the two cannot drift apart
again without a red test here.

They deliberately do NOT check the DLL's behaviour -- that is the harnesses'
own job, and they pass. This checks only that the harnesses are still pointed
at the right place to see it.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARENTAGE = ROOT / "native/parentage_export/parentage_export.c"
PARENTAGE_HARNESS = ROOT / "native/parentage_export/parentage_export_harness.c"
POPULATION = ROOT / "native/population_export/population_export.c"
POPULATION_HARNESS = ROOT / "native/population_export/population_export_harness.c"


def subfolders(source: str) -> set[str]:
    r"""Every `VVFP Logs\<kind>` literal a file names, narrow or wide."""
    return set(re.findall(r'VVFP Logs\\\\([A-Za-z ]+)', source))


class HarnessesFollowTheirExportersTests(unittest.TestCase):
    def test_the_parentage_harness_reads_the_parentage_folder(self):
        exporter = subfolders(PARENTAGE.read_text(encoding="utf-8"))
        harness = subfolders(PARENTAGE_HARNESS.read_text(encoding="utf-8"))
        self.assertTrue(
            exporter, "the exporter names no VVFP Logs subfolder at all")
        self.assertTrue(
            harness,
            "the harness names no VVFP Logs subfolder, so it is reading the "
            "save folder itself and will find nothing the exporter wrote")
        self.assertTrue(
            harness <= exporter,
            "the harness reads %s but the exporter writes %s"
            % (sorted(harness), sorted(exporter)))

    def test_the_population_harness_reads_a_population_folder(self):
        exporter = subfolders(POPULATION.read_text(encoding="utf-8"))
        harness = subfolders(POPULATION_HARNESS.read_text(encoding="utf-8"))
        self.assertTrue(exporter, "the exporter names no VVFP Logs subfolder")
        self.assertTrue(harness, "the harness names no VVFP Logs subfolder")
        self.assertTrue(
            harness <= exporter,
            "the harness reads %s but the exporter writes %s"
            % (sorted(harness), sorted(exporter)))

    def test_the_parentage_harness_expects_the_current_log_name(self):
        """The file name moved with the folder; the harness must follow.

        Matching on the name's distinctive part rather than the whole string,
        because the harness builds it per game with a format.
        """
        exporter = PARENTAGE.read_text(encoding="utf-8")
        harness = PARENTAGE_HARNESS.read_text(encoding="utf-8")
        stem = "Births and Conceptions Log"
        self.assertIn(stem, exporter, "the exporter's log name changed")
        self.assertIn(
            stem, harness,
            "the harness still expects the previous log name, so every file "
            "it looks for is one the exporter no longer writes")


if __name__ == "__main__":
    unittest.main()
