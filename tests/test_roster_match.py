"""Village identity for the statistics companion's new-village rollover, run
against the real C code.

native/statistics_export/roster_match_harness.c links roster_match.c (the
pure decision the DLL uses to tell whether a save slot still holds the same
village) into a 32-bit console program. This compiles it with the same MSVC
toolchain the DLL build script uses and runs it; it is skipped where that
toolchain is not installed.

The owner's rule is roster OVERLAP (any shared living villager); Codex (PR
#467) showed a lone same-slot NAME is too weak because names come from fixed
pools. A shared villager therefore means same slot and same fingerprint
(likes, dislikes, parents' names), which also survives renames.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_village_elders import NATIVE, _toolchain

ROOT = Path(__file__).resolve().parents[1]
EXPORTER = (NATIVE / "statistics_export.c").read_text(encoding="utf-8")
BUILD = (ROOT / "scripts" / "build_statistics_export.ps1").read_text(encoding="utf-8")


class RosterMatchHarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        vs, sdk, ver = _toolchain()
        cl = vs / "bin" / "Hostx64" / "x86" / "cl.exe"
        if not cl.exists():
            raise unittest.SkipTest("MSVC x86 toolchain not installed")
        cls.work = Path(tempfile.mkdtemp())
        exe = cls.work / "roster_match_harness.exe"
        cmd = [str(cl), "/nologo", "/W3", "/MT",
               "/I", str(vs / "include"), "/I", str(sdk / "Include" / ver / "um"),
               "/I", str(sdk / "Include" / ver / "shared"), "/I", str(sdk / "Include" / ver / "ucrt"),
               str(NATIVE / "roster_match_harness.c"), str(NATIVE / "roster_match.c"),
               f"/Fe{exe}", f"/Fo{cls.work}\\",
               "/link", f"/LIBPATH:{vs / 'lib' / 'x86'}", f"/LIBPATH:{sdk / 'Lib' / ver / 'um' / 'x86'}",
               f"/LIBPATH:{sdk / 'Lib' / ver / 'ucrt' / 'x86'}"]
        build = subprocess.run(cmd, capture_output=True, text=True, cwd=cls.work)
        if build.returncode != 0:
            raise AssertionError(build.stdout[-2000:] + build.stderr[-2000:])
        cls.result = subprocess.run([str(exe)], capture_output=True, text=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(getattr(cls, "work", ""), ignore_errors=True)

    def test_every_check_passes(self):
        out = self.result.stdout
        self.assertIn("0 failure(s)", out, out)
        self.assertEqual(self.result.returncode, 0, out)
        self.assertNotIn("FAIL", out, out)

    def test_the_decisive_cases_are_run(self):
        out = self.result.stdout
        for case in ("two villagers, one died and one born: still the same village",
                     "one surviving villager keeps a large village the same",
                     "renaming every villager is not a new village",
                     "a new village sharing one founder's name and slot is a new village",
                     "one name-only match in two is not a majority",
                     "no shared villager is a new village",
                     "a death at record 0 and a reload that moves everyone down is still the same village",
                     "a survivor found at her rank in the recorded roster is a shared villager",
                     "a new village sharing one founder's name at a recorded rank is still a new village",
                     "a fingerprint match is found even when a same-name row could be taken first",
                     "two villagers with nothing to fingerprint are not the same by fingerprint",
                     "another village whose villager has nothing to fingerprint is still another village"):
            with self.subTest(case=case):
                self.assertIn("PASS " + case, out)


class RosterMatchIsWhatTheDllUsesTests(unittest.TestCase):
    def test_the_dll_decides_with_roster_match(self):
        self.assertIn('(Join-Path $nativeRoot "roster_match.c")', BUILD)
        check = EXPORTER[EXPORTER.index("static int village_changed("):]
        check = check[:check.index("\n}\n")]
        self.assertIn("return vv_roster_same_village(&g_roster_was[0][0], was, &g_roster_now[0][0], g_roster_now_count,",
                      check)
        self.assertIn("#define ROSTER_MAX VV_ROSTER_MAX", EXPORTER)
        self.assertNotIn("static int same_villager(", EXPORTER)


if __name__ == "__main__":
    unittest.main()
