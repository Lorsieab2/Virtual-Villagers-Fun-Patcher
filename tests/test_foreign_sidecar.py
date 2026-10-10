"""Another village's per-slot file is never replaced, in all five games.

Since v1.35.66 every Origins companion keys its mask file by the game's OWN slot field
(native/shared/game_save_slot.h), which names a slot before its village is in the villager array:
at A New Home's title screen it already says the slot about to be loaded while the array holds the
founders the startup slot list seeded.  The owner's A New Home parents were wiped that way
(v1.35.67).  native/shared/foreign_sidecar.h holds the rules every mask table follows now:

  - a table from a file is moved to its villagers only when somebody on screen is in the file;
  - another village's file is never replaced: an empty table is not written over it, and the first
    table with a mask in it moves it aside to "<name>.another-village-<ticks>-<n>".

Runtime: the header against real files (native/shared/foreign_sidecar_harness.c, in a temporary
folder), and the committed A New Home companion over a fake villager array with its Documents
redirected to %TEMP% (scripts/build_vv1_mask_title_harness.ps1).  New Believers' runtime case is in
tests/test_vv5_mask_identity_harness.py.  The Lost Children shares New Believers' load-and-save code
shape; The Tree of Life finds its villager array by parsing the running executable, so both are
checked here at the source.  The Secret City keys its masks by fingerprint and never clears an entry
on its own, so it has nothing to lose this way (checked too).
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


def _source(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


class ForeignSidecarHeaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        vs, sdk, ver = _toolchain()
        cl = vs / "bin" / "Hostx64" / "x86" / "cl.exe"
        if not cl.exists():
            raise unittest.SkipTest("MSVC x86 toolchain not installed")
        cls.work = Path(tempfile.mkdtemp())
        exe = cls.work / "foreign_sidecar_harness.exe"
        cmd = [str(cl), "/nologo", "/W3", "/MT",
               "/I", str(vs / "include"), "/I", str(sdk / "Include" / ver / "um"),
               "/I", str(sdk / "Include" / ver / "shared"), "/I", str(sdk / "Include" / ver / "ucrt"),
               "/I", str(SHARED), str(SHARED / "foreign_sidecar_harness.c"),
               f"/Fe{exe}", f"/Fo{cls.work}\\",
               "/link", f"/LIBPATH:{vs / 'lib' / 'x86'}", f"/LIBPATH:{sdk / 'Lib' / ver / 'um' / 'x86'}",
               f"/LIBPATH:{sdk / 'Lib' / ver / 'ucrt' / 'x86'}", "kernel32.lib", "user32.lib"]
        build = subprocess.run(cmd, capture_output=True, text=True, cwd=cls.work)
        if build.returncode != 0:
            raise AssertionError(build.stdout[-3000:] + build.stderr[-3000:])
        scratch = cls.work / "scratch"
        scratch.mkdir()
        cls.result = subprocess.run([str(exe), str(scratch)], capture_output=True, text=True, timeout=120)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(getattr(cls, "work", ""), ignore_errors=True)

    def test_every_check_passes(self):
        out = self.result.stdout
        self.assertIn("0 failure(s)", out, out)
        self.assertNotIn("FAIL", out, out)
        for case in ("the title screen's founders share nobody with the village",
                     "an empty table is never written over another village's file",
                     "a table with a mask moves the other village's file aside first, byte for byte",
                     "a second set-aside never replaces the first"):
            with self.subTest(case=case):
                self.assertIn("PASS " + case, out)


class AnewHomeMaskTitleScreenTests(unittest.TestCase):
    def test_the_committed_companion_keeps_the_masks_file(self):
        vs, _sdk, _ver = _toolchain()
        if not (vs / "bin" / "Hostx64" / "x86" / "cl.exe").exists():
            self.skipTest("MSVC x86 toolchain not installed")
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
             str(ROOT / "scripts" / "build_vv1_mask_title_harness.ps1")],
            capture_output=True, text=True, timeout=300)
        out = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, out)
        self.assertIn("== 0 failure(s) ==", result.stdout)
        for case in ("ok   the founders never touch village A's mask file",
                     "ok   village A's masks follow Alba and Bram to their new records",
                     "ok   ... and the file holds them"):
            with self.subTest(case=case):
                self.assertIn(case, result.stdout)


class EveryGameSourceTests(unittest.TestCase):
    def test_a_new_home_waits_for_the_files_village(self):
        src = _source("native/vv1_origins_icons/vv1_origins_icons.c")
        self.assertIn('#include "../shared/foreign_sidecar.h"', src)
        follow = src.split("static int vv1_mask_follow_loaded(void) {", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("vv_roster_shares(VV_MASK_SLOTS, vv1_mask_file_roster, live) == 0", follow)
        self.assertLess(follow.index("vv_roster_shares"), follow.index("vv_mask_follow("))
        save = src.split("static int vv1_mask_sidecar_save(void) {", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("vv_table_any(VV_MASK_TABLE, VV_MASK_TABLE_BYTES)", save)
        self.assertLess(save.index("vv_foreign_set_aside(path)"), save.index("vv_sidecar_publish("))

    def test_the_lost_children_and_new_believers_never_replace_another_villages_file(self):
        for rel, flag, table in (
                ("native/vv2_origins_icons/vv2_origins_icons.c", "g_vv2_mask_foreign", "VV2_MASK_TABLE"),
                ("native/vv5_task9_origins/vv5_task9_origins.c", "g_vv5_mask_foreign", "table")):
            with self.subTest(source=rel):
                src = _source(rel)
                self.assertIn(f"{flag} = !", src)            # set by the load from the roster verdict
                self.assertIn(f"{flag} = 0;", src)            # and cleared at every load
                body = src.split("vv_foreign_before_write(&" + flag, 1)[1]
                self.assertIn("vv_table_any(" + table, body.split(";", 1)[0])
                at = src.index("vv_foreign_before_write(&" + flag)
                publish = src.find("vv_sidecar_publish(", at)
                self.assertTrue(0 < publish - at < 1500, "the check comes right before the write")

    def test_the_tree_of_life_keeps_a_table_aside_from_another_array(self):
        src = _source("native/vv4_origins_icons/vv4_origins_icons.c")
        follow = src.split("static int vv_mask_follow_table(void) {", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("vv_roster_shares(slots, g_mask_roster, live) == 0", follow)
        self.assertIn("vv_roster_shares(slots, g_stash_roster, live) == 1", follow)
        self.assertLess(follow.index("g_stash_active = 1;"), follow.index("vv_mask_follow(slots"))
        write = src.split("static int vv_write_mask_sidecar(void) {", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("vv_foreign_before_write(&g_mask_foreign", write)

    def test_the_secret_city_never_clears_a_mask_on_its_own(self):
        src = _source("native/vv3_full_mastery_candidate/vv3_full_mastery_candidate.c")
        # Fingerprint-keyed: nothing but the sanitizer (an invalid value) ever zeroes an entry.
        zeroed = re.findall(r"g_vv3_mask\[[^\]]+\]\s*=\s*0;", src)
        self.assertEqual(len(zeroed), 1, zeroed)
        self.assertNotIn("vv_mask_follow(", src)


if __name__ == "__main__":
    unittest.main()
