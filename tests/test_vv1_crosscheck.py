"""A New Home's first-load cross-check, run against the real C code.

Before v1.35.57 the parentage table was kept by record index, and A New Home
packs its villager array when a save is loaded, so after a death the parents
drifted onto whoever moved into each record: the owner's Lisha (daughter of
Ghali and Onawa) showed Kito and Chika, and Silko, a grown arrival, showed
Ghali and Onawa.  v1.35.57 makes the parents follow their villagers, but a
table that had already drifted carries the wrong parents faithfully onwards.

native/vv1_parentage/vv1_crosscheck.inc rebuilds each living villager's
parents from the village's Births and Conceptions log, once per village, and
only after asking the player.  native/vv1_parentage/vv1_crosscheck_harness.c
compiles vv1_parentage.c itself into a 32-bit console program with the
Documents folder redirected to a temporary folder and the prompt answered by
the harness, and drives the real tick against a real sidecar and a real log on
disk.  It is built with the same MSVC toolchain the DLL build script uses and
skipped where that toolchain is not installed.
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


def build_and_run(source: Path, work: Path) -> subprocess.CompletedProcess:
    vs, sdk, ver = _toolchain()
    cl = vs / "bin" / "Hostx64" / "x86" / "cl.exe"
    if not cl.exists():
        raise unittest.SkipTest("MSVC x86 toolchain not installed")
    exe = work / "vv1_crosscheck_harness.exe"
    cmd = [str(cl), "/nologo", "/W3", "/MT",
           "/I", str(vs / "include"), "/I", str(sdk / "Include" / ver / "um"),
           "/I", str(sdk / "Include" / ver / "shared"), "/I", str(sdk / "Include" / ver / "ucrt"),
           "/I", str(NATIVE),
           str(source),
           f"/Fe{exe}", f"/Fo{work}\\",
           "/link", "/DYNAMICBASE:NO", "/BASE:0x10000000",
           f"/LIBPATH:{vs / 'lib' / 'x86'}", f"/LIBPATH:{sdk / 'Lib' / ver / 'um' / 'x86'}",
           f"/LIBPATH:{sdk / 'Lib' / ver / 'ucrt' / 'x86'}",
           "kernel32.lib", "user32.lib", "shell32.lib", "advapi32.lib"]
    build = subprocess.run(cmd, capture_output=True, text=True, cwd=work)
    if build.returncode != 0:
        raise AssertionError(build.stdout[-3000:] + build.stderr[-3000:])
    docs = work / "docs"
    docs.mkdir()
    return subprocess.run([str(exe), str(docs)], capture_output=True, text=True, timeout=600)


class Vv1CrossCheckHarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work = Path(tempfile.mkdtemp())
        cls.result = build_and_run(NATIVE / "vv1_crosscheck_harness.c", cls.work)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(getattr(cls, "work", ""), ignore_errors=True)

    def test_every_check_passes(self):
        out = self.result.stdout
        self.assertIn("== 0 failure(s) ==", out, out)
        self.assertEqual(self.result.returncode, 0, out)
        self.assertNotIn("FAIL", out, out)

    def test_the_cases_are_all_run(self):
        out = self.result.stdout
        for case in (
            # the owner's scenario: two deaths below the children, a compacting load
            "the drifted sidecar shows Lisha [13] as Kito and Chika's, as the owner saw",
            "... and Silko, a grown arrival, as Ghali and Onawa's",
            "the player is asked before anything is repaired",
            "... and the scan counts what the prompt will say: Lisha and Kaimi corrected, Nishi and Penyo filled in, Silko set to unknown",
            "... byte for byte",
            "... no marker, no backup, no Repairs log",
            "every living villager now has the parents the Births log names",
            "... Lisha [13] is Ghali and Onawa's again",
            "... and Silko, a grown arrival, has no parents",
            "... and the backup is the file as it was, byte for byte",
            "the marker records that the check ran and repaired",
            "... and lists Lisha's correction",
            "the repaired sidecar on disk loads with every villager's true parents",
            "the next load does not ask again: it runs once per village (the scan answers 'nothing', not 'later')",
            "... and changes nothing, backs nothing up, notes nothing",
            # nothing to repair
            "a table already in step with the log: no prompt",
            "... and the marker records a clean check",
            "no Births log: no prompt, nothing changed",
            "a log with no Birth record clears nobody: treated as no log",
            "another slot's births are never used",
            "a log that goes on to another slot's village still repairs this one from its own section",
            # ambiguity is never guessed at
            "Birth records that disagree for one villager: the parents are set to unknown, never guessed",
            "identical twins whose Birth records agree both get those parents",
            "two identical villagers and one Birth record: both unknown",
            "a villager whose looks changed since birth is left as it is, never cleared",
            # the pregnancy stash
            "an expecting mother's baby gets the father of her last logged conception",
            "a pregnancy the log does not hold keeps its stash",
            # the session the check runs in (the load-time catch-up delivers before anyone is asked)
            "a catch-up birth before the check takes the father the log confirms, not the drifted stash",
            "... and the stash itself is not changed before the player is asked",
            "a villager born this session is never cleared for want of a Birth record the log has not written yet",
            "... and the stash of a pregnancy the catch-up already delivered is corrected too (a crash would deliver it again)",
            "... and keeps both parents through the repair",
            "a villager the old file never knew, with a Birth record, is filled in (not taken for a newborn)",
            "a conception made this session gives its own father",
            "... and its stash is never 'corrected' from an older conception",
            "after the check has run, a birth takes the stash as it always did",
            # failing closed
            "an unreadable Births log: nothing changed, no marker",
            "... and once it can be read, the next load repairs",
            "a repair that cannot be written changes nothing on disk, and says so",
            "... nor in memory (the old parents still show, as on disk)",
            "... and marks nothing done (its own backup removed), so the next load tries again",
            "... and the Repairs log says the repair was not applied",
            "a repair whose note cannot be written is not made at all",
            "a marker left by another village in the slot does not count for this one",
            'a Birth record\'s "(unknown)" father is no father, never the name "(unknown)"',
            "a log naming more villages than can be told apart changes nothing",
            "an existing backup is never replaced: the next free name is used",
            "a damaged marker is set aside and the check runs",
            "numbered log files are read in number order (file 10 after file 2)",
            # Codex on #522, third round
            "a Births log cut off mid-record is unreadable: nothing asked, nothing changed, no marker",
            "... and so is one whose Birth names no child",
            "... and one whose parent has no head or body",
            "a full village of long names, every one corrected twice: repaired",
            "... and every one of the 512 changes is in the Repairs log, past 64 KiB, ending with the backup",
            # stale expected fathers (owner, 2026-10-04)
            "a stale expected father on villagers not expecting is found",
            "... and Repair clears it, and only it",
            "... and the Repairs log says so",
            "a mother the catch-up delivered after the load keeps her stash: it is not stale",
            "without the load's list of expecting mothers, no stash is called stale",
        ):
            with self.subTest(case=case):
                self.assertIn("PASS " + case, out)


if __name__ == "__main__":
    unittest.main()
