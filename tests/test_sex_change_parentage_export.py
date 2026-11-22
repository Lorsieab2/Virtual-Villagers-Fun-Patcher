"""A villager's sex changed (native/shared/sex_change.h): "VVFP Parentage Export.dll" keeps their looks' notes.

The "Appearance changed" records written since the game started are noted by the villager's name and sex
(look_notes); VVFP Cause of Death's save-time roster asks them (AppearanceAlreadyLogged) before it writes a look
change "Changed by: the game", so after a change of sex a look change already in the log would be written twice.
VvfpVillagerSexChanged carries them; the change's own record (the four look lines, then "Old sex" / "New sex") is
read as any other.  native/parentage_export/sex_change_harness.c compiles the companion's source and proves it in all
five games' layouts, touching no file.
"""
from __future__ import annotations

import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "native"
DLL = ROOT / "assets" / "parentage" / "VVFP Parentage Export.dll"
VS_TOOLS = Path(r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231")
CL = VS_TOOLS / "bin" / "Hostx64" / "x86" / "cl.exe"
SDK = Path(r"C:\Program Files (x86)\Windows Kits\10")
SDK_VERSION = "10.0.26100.0"
HARNESS_CHECKS = 5 * 7 + 1


@unittest.skipUnless(CL.is_file(), "the 32-bit MSVC toolchain is not installed")
class ParentageExportSexChange(unittest.TestCase):
    def test_the_notes_follow_a_sex_change(self):
        with tempfile.TemporaryDirectory(prefix="vvfp_pe_sex_") as out:
            exe = Path(out) / "sex_change_harness.exe"
            build = subprocess.run(
                [str(CL), "/nologo", f"/Fo{out}\\", "/O2", "/MT",
                 "/I", str(VS_TOOLS / "include"),
                 "/I", str(SDK / "Include" / SDK_VERSION / "um"),
                 "/I", str(SDK / "Include" / SDK_VERSION / "shared"),
                 "/I", str(SDK / "Include" / SDK_VERSION / "ucrt"),
                 "/I", str(NATIVE / "shared"),
                 str(NATIVE / "parentage_export" / "sex_change_harness.c"),
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

    def test_the_dll_exports_it(self):
        try:
            import pefile
        except ImportError:  # pragma: no cover - environment dependent
            self.skipTest("pefile is not installed")
        pe = pefile.PE(str(DLL), fast_load=True)
        pe.parse_data_directories([pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_EXPORT"]])
        self.assertIn(b"VvfpVillagerSexChanged", {e.name for e in pe.DIRECTORY_ENTRY_EXPORT.symbols})


if __name__ == "__main__":
    unittest.main()
