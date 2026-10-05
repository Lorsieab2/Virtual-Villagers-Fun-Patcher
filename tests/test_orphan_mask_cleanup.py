"""The first-load cross-check clears ORPHAN Village Masks entries (v1.35.59, all five games).

An orphan is a mask entry whose stored villager identity no villager in the village carries --
living, or a body still in its record -- on a record nobody holds (The Secret City finds masks by
identity, so there the record does not matter).  The Repair / Not now prompt lists them; Repair
backs the mask file up as "<file>.before-v1.35.59-repair", removes exactly them and lists each in
the Repairs log; an entry some villager carries (one, or several alike) is never touched.

native/shared/orphan_masks_game_harness.c compiles each game's own Origins companion source with
the game's memory stood in for at its own addresses and drives the companion's load, the scan and
the repair against real files.  Built with the toolchain the DLL build scripts use; skipped where
it is not installed.  The wiring is checked from the sources.
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

COMPANIONS = {
    1: "native/vv1_origins_icons/vv1_origins_icons.c",
    2: "native/vv2_origins_icons/vv2_origins_icons.c",
    3: "native/vv3_full_mastery_candidate/vv3_full_mastery_candidate.c",
    4: "native/vv4_origins_icons/vv4_origins_icons.c",
    5: "native/vv5_task9_origins/vv5_task9_origins.c",
}
BUILD_SCRIPTS = {
    1: "scripts/build_vv1_origins_icons.ps1",
    2: "scripts/build_vv2_origins_icons.ps1",
    3: "scripts/build_vv3_full_mastery_candidate_dll.ps1",
    4: "scripts/build_vv4_origins_icons.ps1",
    5: "scripts/build_vv5_task9_origins_dll.ps1",
}

CASES = (
    "ok   it is in the Village Masks folder (the #519 resolver)",
    "ok   the load keeps every entry where it was (nobody moved)",
    "ok   two orphans: Dee's mask and the one with no identity (scan says 2)",
    "ok   the file is byte for byte as it was",
    "ok   no backup",
    "ok   no Repairs log",
    "ok   nothing changed, no backup, no log",
    "ok   this repair's backup is gone again",
    "ok   the entries are back in the table",
    "ok   exactly the two orphans are gone from the table",
    "ok   and from the file",
    "ok   Bo's, the alike pair's and the body's are kept in the file",
    "ok   the backup is the file as it was: ",
    "ok   two removals are listed",
    "ok   and the backup's name",
    "ok   the next scan finds nothing",
    "ok   a Repair then changes nothing more",
    "ok   nor does the next load's",
    "ok   which keeps the alike pair's mask (and the body's)",
    "ok   load after load",
    "ok   only the entry that is still an orphan is removed",
    "ok   backed up again, beside the first backup: ",
)
WEAK_CASES = (
    "ok   one orphan: the name no villager has",
    "ok   the name both Cys carry is kept",
    "ok   and still kept at the next load",
)


def _toolchain():
    vs = re.search(r'\$vsTools = "([^"]+)"', BUILD).group(1)
    sdk = re.search(r'\$sdkRoot = "([^"]+)"', BUILD).group(1)
    ver = re.search(r'\$sdkVersion = "([^"]+)"', BUILD).group(1)
    return Path(vs), Path(sdk), ver


def _source(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


class OrphanMaskHarnessTests(unittest.TestCase):
    """Each game's companion, run."""

    @classmethod
    def setUpClass(cls):
        vs, sdk, ver = _toolchain()
        cl = vs / "bin" / "Hostx64" / "x86" / "cl.exe"
        if not cl.exists():
            raise unittest.SkipTest("MSVC x86 toolchain not installed")
        cls.work = Path(tempfile.mkdtemp())
        cls.results = {}
        for game in COMPANIONS:
            out = cls.work / f"g{game}"
            out.mkdir()
            exe = out / f"vvfp_orphan_masks_harness_vv{game}.exe"
            cmd = [str(cl), "/nologo", "/O2", "/MT", "/W3", "/D_CRT_SECURE_NO_WARNINGS", f"/DOM_GAME={game}",
                   "/I", str(vs / "include"), "/I", str(sdk / "Include" / ver / "um"),
                   "/I", str(sdk / "Include" / ver / "shared"), "/I", str(sdk / "Include" / ver / "ucrt"),
                   str(SHARED / "orphan_masks_game_harness.c"), f"/Fe{exe}", f"/Fo{out}\\",
                   "/link", "/FIXED", "/DYNAMICBASE:NO", "/BASE:0x400000",
                   f"/LIBPATH:{vs / 'lib' / 'x86'}", f"/LIBPATH:{sdk / 'Lib' / ver / 'um' / 'x86'}",
                   f"/LIBPATH:{sdk / 'Lib' / ver / 'ucrt' / 'x86'}",
                   "user32.lib", "gdi32.lib", "shell32.lib", "advapi32.lib", "gdiplus.lib", "ole32.lib"]
            build = subprocess.run(cmd, capture_output=True, text=True, cwd=out)
            if build.returncode != 0:
                raise AssertionError(f"game {game}: " + build.stdout[-3000:] + build.stderr[-3000:])
            cls.results[game] = subprocess.run([str(exe)], capture_output=True, text=True, timeout=600)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(getattr(cls, "work", ""), ignore_errors=True)

    def test_every_check_passes_in_every_game(self):
        for game, result in self.results.items():
            with self.subTest(game=game):
                self.assertIn("== 0 failure(s) ==", result.stdout, result.stdout)
                self.assertNotIn("FAIL", result.stdout)
                self.assertEqual(result.returncode, 0, result.stdout)

    def test_every_case_is_run_in_every_game(self):
        for game, result in self.results.items():
            for case in CASES + (WEAK_CASES if game in (2, 5) else ()):
                with self.subTest(game=game, case=case):
                    self.assertIn(case, result.stdout)


class OrphanMaskWiringTests(unittest.TestCase):
    """The sources: every companion defines the pair, the prompt asks, the builds link the Repairs log."""

    def test_every_companion_defines_the_scan_and_the_repair(self):
        for game, rel in COMPANIONS.items():
            src = _source(rel)
            with self.subTest(game=game):
                # The Lost Children's companion is A New Home's source with its own parts added.
                included = _source(COMPANIONS[1]) if game == 2 else src
                self.assertIn('#include "../shared/orphan_masks.h"', included)
                self.assertRegex(src, r"static int vvfp_xc_masks_scan\(int game, int slot\) \{\n"
                                      rf"    return game == {game} \?")
                self.assertIn("static void vvfp_xc_masks_repair(int game, int slot, int repair) {", src)
                self.assertIn(f"(void)vv_om_commit({game}, slot, path, &gone, &table);", src)
                # Only what the prompt listed AND is still an orphan at the answer is removed.
                self.assertIn("vv_om_still(&", src)

    def test_the_prompt_asks_and_acts_on_the_answer(self):
        bridge = _source("native/shared/crosscheck_bridge.h")
        self.assertIn("masks = vvfp_xc_masks_scan(game, slot);", bridge)
        self.assertIn("|| masks < 0;", bridge)
        self.assertIn("vv_om_describe(vvfp_xc.masks, ", bridge)
        self.assertIn("vvfp_xc_masks_repair(vvfp_xc.asked_game, vvfp_xc.asked_slot, yes);", bridge)
        om = _source("native/shared/orphan_masks.h")
        self.assertIn('"- %d mask entries for villagers who are no longer in the village. "', om)
        self.assertIn('"- 1 mask entry for a villager who is no longer in the village. "', om)
        self.assertIn('#define VV_OM_BACKUP_SUFFIX L".before-v1.35.59-repair"', om)

    def test_every_origins_build_links_the_save_folder_resolver(self):
        for game, rel in BUILD_SCRIPTS.items():
            with self.subTest(game=game):
                self.assertIn('(Join-Path $projectRoot "native\\shared\\save_folder.c")', _source(rel))

    def test_no_marker_is_needed(self):
        # A repaired village's scan finds nothing, so nothing is added to the Repair Logs re-arm list.
        tools = _source("src/vv_log_tools.py")
        block = tools.split("REARM_MARKERS: tuple", 1)[1].split("\n)\n", 1)[0]
        self.assertIn("Graves Logged", block)
        self.assertNotIn("Village Masks", block)


if __name__ == "__main__":
    unittest.main()
