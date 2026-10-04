"""The first-load Repair / Not now prompt (native/shared/crosscheck_bridge.h).

v1.35.58 cross-checks a village's records against their sources of truth the
first time it loads a village, and the owner's rule is that "the player should
be notified first before any fix runs".  The header every game's Origins
companion includes decides when to look, asks ONE question for everything
found (A New Home's recorded parents; graves missing from the Deaths log), and
acts on the answer.  native/shared/crosscheck_bridge_harness.c runs the real
header with the companions, the slot and the clock stood in for, and a real
prompt thread whose message box answers as the case says.

The harness is built with the same MSVC toolchain the DLL build scripts use and
skipped where that toolchain is not installed.  The wiring into each game's
companion is checked here too, from the sources.
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

# Each game's Origins companion, and the village-only per-frame entry that
# drives the prompt.
COMPANIONS = {
    1: ("native/vv1_origins_icons/vv1_origins_icons.c", "Vv1MaskTick"),
    2: ("native/vv2_origins_icons/vv2_origins_icons.c", "Vv2MaskSweep"),
    3: ("native/vv3_full_mastery_candidate/vv3_full_mastery_candidate.c", "VV3WorldMaskDrawAt"),
    4: ("native/vv4_origins_icons/vv4_origins_icons.c", "Vv4MaskGetForRecord"),
    5: ("native/vv5_task9_origins/vv5_task9_origins.c", "Vv5MaskSync"),
}


def _toolchain():
    vs = re.search(r'\$vsTools = "([^"]+)"', BUILD).group(1)
    sdk = re.search(r'\$sdkRoot = "([^"]+)"', BUILD).group(1)
    ver = re.search(r'\$sdkVersion = "([^"]+)"', BUILD).group(1)
    return Path(vs), Path(sdk), ver


class FirstLoadPromptHarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        vs, sdk, ver = _toolchain()
        cl = vs / "bin" / "Hostx64" / "x86" / "cl.exe"
        if not cl.exists():
            raise unittest.SkipTest("MSVC x86 toolchain not installed")
        cls.work = Path(tempfile.mkdtemp())
        exe = cls.work / "crosscheck_bridge_harness.exe"
        cmd = [str(cl), "/nologo", "/W3", "/MT",
               "/I", str(vs / "include"), "/I", str(sdk / "Include" / ver / "um"),
               "/I", str(sdk / "Include" / ver / "shared"), "/I", str(sdk / "Include" / ver / "ucrt"),
               "/I", str(SHARED),
               str(SHARED / "crosscheck_bridge_harness.c"),
               f"/Fe{exe}", f"/Fo{cls.work}\\",
               "/link",
               f"/LIBPATH:{vs / 'lib' / 'x86'}", f"/LIBPATH:{sdk / 'Lib' / ver / 'um' / 'x86'}",
               f"/LIBPATH:{sdk / 'Lib' / ver / 'ucrt' / 'x86'}",
               "kernel32.lib", "user32.lib"]
        build = subprocess.run(cmd, capture_output=True, text=True, cwd=cls.work)
        if build.returncode != 0:
            raise AssertionError(build.stdout[-3000:] + build.stderr[-3000:])
        cls.result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=600)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(getattr(cls, "work", ""), ignore_errors=True)

    def test_every_check_passes(self):
        out = self.result.stdout
        self.assertIn("== 0 failure(s) ==", out, out)
        self.assertEqual(self.result.returncode, 0, out)

    def test_the_cases_are_all_run(self):
        out = self.result.stdout
        for case in (
            "nothing to repair: examined once, no prompt",
            "nothing is examined in the first seconds of a load (past the catch-up)",
            "parents found: the player is asked, once",
            "... and the prompt says plainly what was found and what will happen",
            "Not now: nothing is repaired",
            "... and the same load does not ask again",
            "... but the next load does",
            "... and so does one after a gap in the village frames",
            "Repair: the parents are repaired, once",
            "a repair that could not be written tells the player nothing changed",
            "Not now is passed on: nothing will be written",
            "Repair is passed on (New Believers)",
            "parents and graves together: ONE prompt, and Repair repairs both",
            "... it is retried, and the one prompt covers both",
            "a scan that never can tell is let go for this load, without a prompt",
            "an answer given while another village was loaded repairs nothing",
            "with neither companion loaded, nothing is asked",
            "no village on screen (or no slot): nothing is examined",
        ):
            with self.subTest(case=case):
                self.assertIn("PASS " + case, out)


class FirstLoadPromptWiringTests(unittest.TestCase):
    """Every game's Origins companion includes the header and calls it from its
    village-only per-frame entry -- and from nowhere that runs before the
    load-time catch-up or at the menus."""

    def test_every_game_calls_the_prompt_from_its_village_frame(self):
        for game, (path, entry) in COMPANIONS.items():
            with self.subTest(game=game):
                src = (ROOT / path).read_text(encoding="utf-8")
                if game != 2:   # The Lost Children compiles A New Home's companion in, header and all
                    self.assertIn('#include "../shared/crosscheck_bridge.h"', src)
                body = src[re.search(r"__stdcall %s\([^)]*\)\s*\{" % entry, src).start():]
                body = body[:body.index("\n}\n")]
                self.assertRegex(body, r"vvfp_crosscheck_bridge\(%d, " % game)
                self.assertEqual(src.count("vvfp_crosscheck_bridge("), 1, "called from exactly one place")

    def test_the_parentage_companion_exports_the_scan_and_the_repair(self):
        for d in ("vv1_parentage.def", "vv1_parentage_test.def"):
            text = (ROOT / "native" / "vv1_parentage" / d).read_text(encoding="utf-8")
            self.assertIn("Vv1ParentageCrossCheckScan=_Vv1ParentageCrossCheckScan@4", text)
            self.assertIn("Vv1ParentageCrossCheckApply=_Vv1ParentageCrossCheckApply@0", text)


if __name__ == "__main__":
    unittest.main()
