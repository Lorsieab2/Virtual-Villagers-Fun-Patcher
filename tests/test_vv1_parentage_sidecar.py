"""A New Home's parentage sidecar is never overwritten because it could not
be read, run against the real C code.

A New Home stores no parents on a villager's record, so the sidecar is the
only copy of them.  A sidecar that existed but could not be opened (a
sharing violation, a denied read, a OneDrive or scanner lock) or that was not
a valid sidecar used to be treated exactly like a missing one: after the
strike window the table was committed empty and the next save replaced the
good file with it, for good.

native/vv1_parentage/vv1_parentage_sidecar_harness.c compiles vv1_parentage.c
itself into a 32-bit console program with the Documents folder redirected to
a temporary folder, and drives the real sync, load and save code.  This
builds it with the same MSVC toolchain the DLL build script uses and runs it;
it is skipped where that toolchain is not installed.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "native" / "vv1_parentage"
BUILD = (ROOT / "scripts" / "build_vv1_parentage_dll.ps1").read_text(encoding="utf-8")


def _toolchain():
    vs = re.search(r'\$vsTools = "([^"]+)"', BUILD).group(1)
    sdk = re.search(r'\$sdkRoot = "([^"]+)"', BUILD).group(1)
    ver = re.search(r'\$sdkVersion = "([^"]+)"', BUILD).group(1)
    return Path(vs), Path(sdk), ver


class Vv1ParentageSidecarHarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        vs, sdk, ver = _toolchain()
        cl = vs / "bin" / "Hostx64" / "x86" / "cl.exe"
        if not cl.exists():
            raise unittest.SkipTest("MSVC x86 toolchain not installed")
        cls.work = Path(tempfile.mkdtemp())
        exe = cls.work / "vv1_parentage_sidecar_harness.exe"
        cmd = [str(cl), "/nologo", "/W3", "/MT",
               "/I", str(vs / "include"), "/I", str(sdk / "Include" / ver / "um"),
               "/I", str(sdk / "Include" / ver / "shared"), "/I", str(sdk / "Include" / ver / "ucrt"),
               "/I", str(NATIVE),
               str(NATIVE / "vv1_parentage_sidecar_harness.c"),
               f"/Fe{exe}", f"/Fo{cls.work}\\",
               "/link", f"/LIBPATH:{vs / 'lib' / 'x86'}", f"/LIBPATH:{sdk / 'Lib' / ver / 'um' / 'x86'}",
               f"/LIBPATH:{sdk / 'Lib' / ver / 'ucrt' / 'x86'}",
               "kernel32.lib", "user32.lib", "shell32.lib", "advapi32.lib"]
        build = subprocess.run(cmd, capture_output=True, text=True, cwd=cls.work)
        if build.returncode != 0:
            raise AssertionError(build.stdout[-3000:] + build.stderr[-3000:])
        docs = cls.work / "docs"
        docs.mkdir()
        cls.result = subprocess.run([str(exe), str(docs)], capture_output=True, text=True,
                                    timeout=300)

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
            "an unreadable sidecar leaves the village unknown, never committed empty",
            "an unreadable sidecar is retried each strike window, not every frame",
            "an unreadable sidecar is not set aside",
            "... and the unreadable sidecar is left byte-for-byte unchanged",
            "once readable, the parents are loaded from the file",
            "strangers with an unreadable sidecar leave the village unknown",
            "... and the table on hand is not emptied",
            "... and that sidecar is left byte-for-byte unchanged",
            "a sidecar held open leaves the village unknown",
            "once released, the parents are loaded from the file",
            "a sidecar whose read fails is waited for, not set aside",
            "... and it is left byte-for-byte unchanged",
            "once unlocked, the parents are loaded from the file",
            "an invalid sidecar is set aside byte-for-byte",
            "... never over a file already set aside",
            "... and the village then starts a table of its own",
            "... written as a sound sidecar",
            "a sidecar with a foreign magic is set aside, not overwritten",
            "an invalid sidecar that cannot be set aside leaves the village unknown",
            "... and nothing is written over it",
            "with no sidecar the village starts empty and one is written",
            "a sidecar that appears after an empty start is not replaced",
            "... and it is read on the next frame",
            "another village's sidecar is superseded after the strike window",
            "this village's own sidecar loads at once",
        ):
            with self.subTest(case=case):
                self.assertIn("PASS " + case, out)


if __name__ == "__main__":
    unittest.main()
