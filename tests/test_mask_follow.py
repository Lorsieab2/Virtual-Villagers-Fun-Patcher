"""The Origins mask tables follow their villagers when a reload renumbers them.

Every game saves only its occupied villager records, packed, and loads them
into records 0, 1, 2, ...: after a death and a reload everyone behind it is
in a lower record.  The mask tables are kept by record index, so each game's
companion re-keys them by the identity stored beside each entry, through the
pure rule in native/shared/mask_follow.h.  native/shared/mask_follow_harness.c
drives that rule; this builds it with the toolchain the DLL build scripts use
and runs it (skipped where that toolchain is not installed), and pins that each
game's companion actually calls it.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "native" / "shared"
BUILD = (ROOT / "scripts" / "build_vv1_parentage_dll.ps1").read_text(encoding="utf-8")


def _toolchain():
    vs = re.search(r'\$vsTools = "([^"]+)"', BUILD).group(1)
    sdk = re.search(r'\$sdkRoot = "([^"]+)"', BUILD).group(1)
    ver = re.search(r'\$sdkVersion = "([^"]+)"', BUILD).group(1)
    return Path(vs), Path(sdk), ver


class MaskFollowHarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        vs, sdk, ver = _toolchain()
        cl = vs / "bin" / "Hostx64" / "x86" / "cl.exe"
        if not cl.exists():
            raise unittest.SkipTest("MSVC x86 toolchain not installed")
        cls.work = Path(tempfile.mkdtemp())
        exe = cls.work / "mask_follow_harness.exe"
        cmd = [str(cl), "/nologo", "/W4", "/WX", "/MT",
               "/I", str(vs / "include"), "/I", str(sdk / "Include" / ver / "um"),
               "/I", str(sdk / "Include" / ver / "shared"), "/I", str(sdk / "Include" / ver / "ucrt"),
               str(SHARED / "mask_follow_harness.c"), f"/Fe{exe}", f"/Fo{cls.work}\\",
               "/link", f"/LIBPATH:{vs / 'lib' / 'x86'}", f"/LIBPATH:{sdk / 'Lib' / ver / 'um' / 'x86'}",
               f"/LIBPATH:{sdk / 'Lib' / ver / 'ucrt' / 'x86'}"]
        build = subprocess.run(cmd, capture_output=True, text=True, cwd=cls.work)
        if build.returncode != 0:
            raise AssertionError(build.stdout[-3000:] + build.stderr[-3000:])
        cls.result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(getattr(cls, "work", ""), ignore_errors=True)

    def test_every_check_passes(self):
        out = self.result.stdout
        self.assertIn("0 failure(s)", out, out)
        self.assertEqual(self.result.returncode, 0, out)
        self.assertNotIn("FAIL", out, out)

    def test_the_cases_are_all_run(self):
        out = self.result.stdout
        for case in (
            "a death below two masked villagers and a reload: both masks move down with them",
            "... and nothing is left on their old records",
            "nothing moved: the table is unchanged",
            "a masked villager who died: her mask is not given to whoever now holds her record",
            "a masked villager away from an empty record keeps it there",
            "a record taken by a moved villager carries that villager's mask",
            "a record now held by an unmasked stranger drops the old entry",
            "two villagers sharing an identity are left unmasked after a repack",
            "a shared identity is not kept in place once anyone else has moved",
            "two masked entries of one identity and one such villager left: neither is guessed",
            "... but kept at their own records when nothing moved",
            "a masked identity held by two living villagers is not guessed",
            "with only a weak identity, a move UP a record is refused",
            "... while a strong identity may move either way",
            "an entry keeps its own identity when it moves",
            "an entry with no identity on someone's record is dropped",
            "a repack of nothing but duplicates is still a repack: the twin's mask is not kept in place",
            "a birth into an empty record does not unseat an ambiguous identity",
            "with no roster, an ambiguous identity is dropped and a unique one kept",
            "a villager found in another record counts as a move: the twin's mask is not kept",
        ):
            with self.subTest(case=case):
                self.assertIn("PASS " + case, out)


if __name__ == "__main__":
    unittest.main()
