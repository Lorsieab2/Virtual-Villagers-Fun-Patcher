"""Village Elders: the owner's mandatory tests A-F (directive XIV) and the
.dat safety cases, run against the real C code.

native/statistics_export/village_elders_harness.c links village_elders.c
into a 32-bit console program that works on synthetic villager and memorial
arrays and writes only inside a temporary folder.  This compiles it with the
same MSVC toolchain the DLL build script uses and runs it; it is skipped
where that toolchain is not installed.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "native" / "statistics_export"
BUILD = (ROOT / "scripts" / "build_statistics_export.ps1").read_text(encoding="utf-8")


def _toolchain():
    vs = re.search(r'\$vsTools = "([^"]+)"', BUILD).group(1)
    sdk = re.search(r'\$sdkRoot = "([^"]+)"', BUILD).group(1)
    ver = re.search(r'\$sdkVersion = "([^"]+)"', BUILD).group(1)
    return Path(vs), Path(sdk), ver


class VillageEldersHarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        vs, sdk, ver = _toolchain()
        cl = vs / "bin" / "Hostx64" / "x86" / "cl.exe"
        if not cl.exists():
            raise unittest.SkipTest("MSVC x86 toolchain not installed")
        cls.work = Path(tempfile.mkdtemp())
        exe = cls.work / "elders_harness.exe"
        cmd = [str(cl), "/nologo", "/W3", "/MT",
               "/I", str(vs / "include"), "/I", str(sdk / "Include" / ver / "um"),
               "/I", str(sdk / "Include" / ver / "shared"), "/I", str(sdk / "Include" / ver / "ucrt"),
               "/I", str(ROOT / "native" / "shared"),
               str(NATIVE / "village_elders_harness.c"), str(NATIVE / "village_elders.c"),
               str(ROOT / "native" / "shared" / "save_folder.c"),
               f"/Fe{exe}", f"/Fo{cls.work}\\",
               "/link", f"/LIBPATH:{vs / 'lib' / 'x86'}", f"/LIBPATH:{sdk / 'Lib' / ver / 'um' / 'x86'}",
               f"/LIBPATH:{sdk / 'Lib' / ver / 'ucrt' / 'x86'}", "shell32.lib", "ole32.lib", "user32.lib", "advapi32.lib"]
        build = subprocess.run(cmd, capture_output=True, text=True, cwd=cls.work)
        if build.returncode != 0:
            raise AssertionError(build.stdout[-2000:] + build.stderr[-2000:])
        data = cls.work / "data"
        data.mkdir()
        cls.result = subprocess.run([str(exe), str(data)], capture_output=True, text=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(getattr(cls, "work", ""), ignore_errors=True)

    def test_every_check_passes(self):
        out = self.result.stdout
        self.assertIn("0 failure(s)", out, out)
        self.assertEqual(self.result.returncode, 0, out)
        self.assertNotIn("FAIL", out, out)

    def test_the_mandatory_cases_are_all_run(self):
        out = self.result.stdout
        for case in ("A: master in exactly two skills is not an elder",
                     "B: a third mastered skill makes one elder",
                     "C: a fourth mastered skill adds no elder",
                     "D: any three distinct skills qualify",
                     "E: great age alone is not an elder",
                     "F: the count survives a reload of the .dat",
                     "a renamed elder is not counted again",
                     "a buried elder is matched to their line, not counted twice",
                     "a new .dat counts the elders the game flagged on existing graves",
                     "a file for another game is not read",
                     "a locked elders file reports nothing",
                     "... and the locked file is left byte-for-byte unchanged",
                     "once readable, the history continues from the file",
                     "a v1 elders file is not read as v2",
                     "a heathen with every skill mastered is not a Village Elder",
                     "the same villager, converted, is one Village Elder",
                     "... and it is kept aside beside the earlier one",
                     "with no reload, an elder whose record is another line's reload record keeps his own line",
                     "a reload that moves both elders down a record still counts two elders",
                     "... each line follows its own elder (Bo does not take over Ana's line)",
                     "a renamed elder moved by a reload keeps his line: still two elders",
                     "... the lines are Ana [1] and Bob [2]"):
            with self.subTest(case=case):
                self.assertIn("PASS " + case, out)


class ReloadRanksReachTheEldersTests(unittest.TestCase):
    """The games load a save packed into records 0, 1, 2, ...; Village Elders
    follows each elder there from the roster the previous save recorded.  The
    harness drives vv_village_elders_file with ranks; this pins that the DLL
    actually hands it the ranks, from the roster village_changed read."""

    def test_the_dll_passes_the_reload_ranks(self):
        source = (NATIVE / "statistics_export.c").read_text(encoding="utf-8")
        calls = re.findall(r"(\n[^\n]*\n)\s*g_elders_value = vv_village_elders\(", source)
        self.assertEqual(len(calls), 2, "both elder layouts (VV1 and VV3-VV5)")
        for before in calls:
            self.assertIn("elders_ranks(&l);", before)
        changed = source[source.index("static int village_changed("):]
        changed = changed[:changed.index("\n}\n")]
        self.assertIn("g_roster_was_count = 0;", changed)
        self.assertIn("g_roster_was_count = was;", changed)
        ranks = source[source.index("static void elders_ranks(struct elders_layout *l) {"):]
        ranks = ranks[:ranks.index("\n}\n")]
        self.assertIn("rank_of_slot[slot] = i;", ranks)
        self.assertIn("l->rank_of_slot = rank_of_slot;", ranks)


if __name__ == "__main__":
    unittest.main()
