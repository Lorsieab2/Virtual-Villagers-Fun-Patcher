"""The cross-check's prompt, and when it may be shown (native/shared/crosscheck_bridge.h).

v1.35.58 cross-checks a village's records against their sources of truth.
The owner (2026-10-05) wants no repair prompt during gameplay: the game asks
only when the player CLOSES it, after its own quit save, only when the
patcher's "Check logs automatically" setting is on (on by default), and
only when something is confirmed wrong; "Repair Saves & Logs..." in the patcher
window instead approves the repair beforehand, and the game then repairs
without asking.  native/shared/crosscheck_bridge_harness.c runs the real
header with the companions, the slot, the clock, the setting and the save
folder stood in for, and a real prompt thread whose message box answers as
the case says (or not at all), and checks that no box is ever shown while
a village is being played.

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
            "setting off: nothing is scanned, asked or repaired -- not while playing, not at the quit",
            "setting on, nothing wrong: scanned once, silently",
            "... and nothing is asked at the quit",
            "nothing is scanned in the first seconds of a load (past the catch-up)",
            "... and then it is scanned, silently",
            "setting on, parents wrong: no prompt and no change while the village is played",
            "... it is scanned again at the quit and the player is asked, once",
            "... and the prompt says plainly what was found and what will happen",
            "... and says nothing of what was not found",
            "Not now: nothing is repaired or passed on",
            "Repair at the quit: the parents are repaired, once, no notice",
            "... and nothing is left for a save that will not come",
            "all five games: every part found is asked about at the quit and repaired there and then",
            "found at the load but not at the quit: nothing is asked",
            "a scan that cannot tell is retried, then let go, silently",
            "... and the quit looks again, and asks when it finds something",
            "at the quit, a part that cannot tell is left out; the rest is still asked about",
            "a quit that saved another slot asks nothing",
            "a quit with no slot saved asks nothing",
            "what the quit owes is the last village played's (another load replaces it)",
            "quitting from the title screen still asks about the village just played",
            "a village closed before it settled is not asked about",
            "a prompt not answered in time is let go: nothing is repaired and the exit is not held up",
            "... and an answer that comes later changes nothing",
            "a box that cannot be shown changes nothing",
            "a repair that could not be done tells the player, at the quit",
            "with no companion loaded, nothing is asked",
            "without the statistics companion the rest is still asked",
            "a statistics count with no lines to show is never asked about",
            "no village on screen (or no slot): nothing is scanned",
            "approved: the parents are repaired as the village settles, the rest at its next save -- no question",
            "... the quit finds nothing left, so nothing is repaired twice",
            "... and the approval is used up",
            "approved with the setting on: still no question",
            "... what the save left undone is completed at the quit, silently, and the approval used up",
            "approved but nothing wrong: used up, nothing changed",
            "approved, but a repair could not be done: the approval is kept for next time (nothing shown)",
            "a game that never reaches its quit save keeps the approval",
            "an approval is for its own slot only",
            "an approval file that does not say this game and slot is not one",
            "an approval removed before the quit (Start Over) repairs nothing more at the quit",
            "the hook is written over the stock bytes",
            "the hook calls the quit check with the game and the application (esi)",
            "... then runs the displaced instructions, with every register as it was, and returns to the game",
            "... the flags the game's next jump reads are the displaced test's own",
            "a site that does not hold its stock bytes is left alone",
            "the quit hook takes the slot from the save manager, where the shutdown read it",
            "a fault while reading the slot is caught: nothing, and the game goes on closing",
            "NO message box was ever shown while a village was being played",
            "orphan masks, every game: scanned silently at load, asked about at the quit, removed only on Repair",
            "... in the singular for one",
            "masks no longer orphaned at the quit: nothing is asked",
            "a mask scan that cannot tell yet is retried, like the others",
            "a mask repair that could not be made: the player is told",
            "Repair Saves & Logs approval: the masks are removed at load, without asking",
            "... and nothing is left at the quit: the approval is used up",
            "... one that failed at load is completed after the quit save, then the approval is used up",
        ):
            with self.subTest(case=case):
                self.assertIn("PASS " + case, out)


class FirstLoadPromptWiringTests(unittest.TestCase):
    """Every game's Origins companion includes the header, drives it from its
    village-only per-frame entry, and installs the quit hook at game start --
    and nothing in the header can show a box anywhere but at the quit."""

    def test_every_game_calls_the_check_from_its_village_frame(self):
        for game, (path, entry) in COMPANIONS.items():
            with self.subTest(game=game):
                src = (ROOT / path).read_text(encoding="utf-8")
                if game != 2:   # The Lost Children compiles A New Home's companion in, header and all
                    self.assertIn('#include "../shared/crosscheck_bridge.h"', src)
                body = src[re.search(r"__stdcall %s\([^)]*\)\s*\{" % entry, src).start():]
                body = body[:body.index("\n}\n")]
                self.assertRegex(body, r"vvfp_crosscheck_bridge\(%d, " % game)
                self.assertEqual(src.count("vvfp_crosscheck_bridge("), 1, "called from exactly one place")

    def test_every_game_installs_the_quit_hook_at_game_start(self):
        for game, (path, _entry) in COMPANIONS.items():
            with self.subTest(game=game):
                src = (ROOT / path).read_text(encoding="utf-8")
                start = src[src.index("void __stdcall VvfpStartup(int game, unsigned int shipped) {"):]
                start = start[:start.index("\n}\n")]
                self.assertIn("VVFP_STARTUP_GUARDED(vvfp_crosscheck_startup(%d));" % game, start)

    def test_a_box_is_only_ever_shown_from_the_quit(self):
        header = (SHARED / "crosscheck_bridge.h").read_text(encoding="utf-8")
        # MessageBoxA once, in the box thread; the box thread is started only
        # by vvfp_xc_ask, and vvfp_xc_ask is called only by the quit check.
        self.assertEqual(len(re.findall(r"\bMessageBox[AW]?\(", header)), 1)
        self.assertEqual(re.findall(r"CreateThread\([^)]*\)", header),
                         ["CreateThread(NULL, 0, vvfp_xc_box, NULL, 0, NULL)"])
        callers = [m.start() for m in re.finditer(r"\bvvfp_xc_ask\(", header)]
        quit_check = header.index("static void vvfp_crosscheck_quit(int game, int slot) {")
        quit_end = header.index("\n}\n", quit_check)
        definition = header.index("static int vvfp_xc_ask(UINT type) {")
        self.assertEqual([c for c in callers if c != definition + len("static int ")
                          and not quit_check < c < quit_end], [])
        self.assertNotIn("vvfp_crosscheck_quit(", header[:quit_check])
        self.assertEqual(header.count("vvfp_crosscheck_quit("), 2,     # its definition and the hook's call
                         "the quit check runs only from the quit hook")

    def test_the_parentage_companion_exports_the_scan_and_the_repair(self):
        for d in ("vv1_parentage.def", "vv1_parentage_test.def"):
            text = (ROOT / "native" / "vv1_parentage" / d).read_text(encoding="utf-8")
            self.assertIn("Vv1ParentageCrossCheckScan=_Vv1ParentageCrossCheckScan@4", text)
            self.assertIn("Vv1ParentageCrossCheckApply=_Vv1ParentageCrossCheckApply@0", text)

    def test_the_companions_export_the_repairs_at_the_quit(self):
        for d in ("vvfp_cause_of_death.def", "vvfp_cause_of_death_test.def"):
            text = (ROOT / "native" / "vvfp_cause_of_death" / d).read_text(encoding="utf-8")
            for name in ("VvfpCauseRepairGravesNow", "VvfpCauseRepairArrivalsNow", "VvfpCauseRepairBirthsNow"):
                self.assertIn(f"{name}=_{name}@8", text)
        for d in ("statistics_export.def", "statistics_export_test.def"):
            text = (ROOT / "native" / "statistics_export" / d).read_text(encoding="utf-8")
            self.assertIn("VvfpStatisticsRepairReconcileNow=_VvfpStatisticsRepairReconcileNow@8", text)


if __name__ == "__main__":
    unittest.main()
