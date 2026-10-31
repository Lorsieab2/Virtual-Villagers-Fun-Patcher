"""A baby's last name is decided by the Last Names record of the village ON SCREEN.

The owner's Secret City (2026-10-30/31): Save 2 was saved and Save 1 loaded in the same session, three
times.  The parentage companion handed VVFP Last Names the slot of the village header published at the
last SAVE -- " (Save 2)" -- so the load's catch-up births read Save 2's record ("From the father", no
villager lines) instead of Save 1's, where the father Pio Bandele's own rule was 50:50: all 37 of his
children were born Bandele.  The slot is now the game's own (its save manager's field, which the slot
menu sets before it loads a village; native/shared/game_save_slot.h), or 0 -- the DLL then finds the
slot from the parents' names -- never the published header.

A New Home's companion already hands the game's own slot (vv1_parentage.c vv1_slot), checked here too.
native/parentage_export/last_names_slot_harness.c runs the shipped source.
"""
from __future__ import annotations

import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "native"
VS_TOOLS = Path(r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231")
CL = VS_TOOLS / "bin" / "Hostx64" / "x86" / "cl.exe"
SDK = Path(r"C:\Program Files (x86)\Windows Kits\10")
SDK_VERSION = "10.0.26100.0"
HARNESS_CHECKS = 4 * 7


class TheSlotIsTheGames(unittest.TestCase):
    def test_the_parentage_companion_never_takes_the_slot_from_the_published_header(self):
        export = (NATIVE / "parentage_export" / "parentage_export.c").read_text(encoding="utf-8")
        body = export[export.index("static int last_names_slot(int game_id) {"):]
        body = body[:body.index("\n}\n")]
        self.assertNotIn("vv_village_recall", body)
        self.assertIn("return game_slot_now(game_id);", body)
        self.assertIn('#include "game_save_slot.h"', export)
        # Every caller hands its game.
        self.assertEqual(len(re.findall(r"last_names_slot\(\)", export)), 0)
        self.assertIn("last_names_slot(game_id));", export)
        self.assertIn("last_names_slot(game_of_layout(g))", export)

    def test_a_new_home_hands_the_games_own_slot(self):
        vv1 = (NATIVE / "vv1_parentage" / "vv1_parentage.c").read_text(encoding="utf-8")
        self.assertIn("return vv_current_save_slot(1, (slot >= 1u && slot <= 5u) ? (int)slot : 0);", vv1)
        born = vv1[vv1.index("__declspec(dllexport) int __stdcall Vv1ParentageBorn("):]
        born = born[:born.index("\n}\n")]
        self.assertIn("slot = vv1_parents_sync();", born)
        self.assertIn("vv1_rule_last_name((unsigned char *)child_pointer, c, slot);", born)
        self.assertNotIn("vv_village_recall", born)


@unittest.skipUnless(CL.is_file(), "the 32-bit MSVC toolchain is not installed")
class LastNamesSlotHarness(unittest.TestCase):
    def test_a_save_of_another_village_is_never_the_births_slot(self):
        with tempfile.TemporaryDirectory(prefix="vvfp_last_names_slot_") as out:
            exe = Path(out) / "last_names_slot_harness.exe"
            build = subprocess.run(
                [str(CL), "/nologo", f"/Fo{out}\\", "/O2", "/MT",
                 "/I", str(VS_TOOLS / "include"),
                 "/I", str(SDK / "Include" / SDK_VERSION / "um"),
                 "/I", str(SDK / "Include" / SDK_VERSION / "shared"),
                 "/I", str(SDK / "Include" / SDK_VERSION / "ucrt"),
                 "/I", str(NATIVE / "shared"),
                 str(NATIVE / "parentage_export" / "last_names_slot_harness.c"),
                 str(NATIVE / "shared" / "village_identity.c"),
                 str(NATIVE / "shared" / "save_folder.c"),
                 "/link",
                 f"/LIBPATH:{VS_TOOLS / 'lib' / 'x86'}",
                 f"/LIBPATH:{SDK / 'Lib' / SDK_VERSION / 'um' / 'x86'}",
                 f"/LIBPATH:{SDK / 'Lib' / SDK_VERSION / 'ucrt' / 'x86'}",
                 f"/OUT:{exe}", "kernel32.lib", "shell32.lib"],
                capture_output=True, text=True, cwd=out, timeout=600,
            )
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            result = subprocess.run([str(exe)], capture_output=True, text=True, cwd=out, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"== {HARNESS_CHECKS} check(s), 0 failure(s) ==", result.stdout)
        self.assertEqual(len(re.findall(r"^  ok ", result.stdout, re.M)), HARNESS_CHECKS, result.stdout)


if __name__ == "__main__":
    unittest.main()
