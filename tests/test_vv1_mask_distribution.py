"""Compile-and-run the C unit test for the Change Appearance for All mask
distribution algorithms (native/vv1_origins_icons/vv1_mask_distribute.h).

The algorithms are pure (no Windows / game memory), so they are tested here as
a standalone C program built with the same MSVC toolchain the DLL uses. Skips
cleanly where that toolchain isn't present (e.g. non-Windows CI)."""
from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "native" / "vv1_origins_icons"
HARNESS = NATIVE / "test_mask_distribute.c"
HEADER = NATIVE / "vv1_mask_distribute.h"

VS_TOOLS = Path(r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231")
CL = VS_TOOLS / "bin" / "Hostx64" / "x86" / "cl.exe"
SDK = Path(r"C:\Program Files (x86)\Windows Kits\10")
SDK_VER = "10.0.26100.0"


def _toolchain_available() -> bool:
    return CL.exists() and (SDK / "Include" / SDK_VER / "ucrt").exists()


@unittest.skipUnless(_toolchain_available(), "MSVC/Windows SDK not available")
class VV1MaskDistributionTests(unittest.TestCase):
    def test_distribution_algorithms_pass_the_c_harness(self):
        self.assertTrue(HARNESS.exists() and HEADER.exists())
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "test_mask_dist.exe"
            obj = Path(tmp) / "tmd.obj"
            includes = [
                f"/I{VS_TOOLS / 'include'}",
                f"/I{SDK / 'Include' / SDK_VER / 'ucrt'}",
                f"/I{SDK / 'Include' / SDK_VER / 'shared'}",
                f"/I{SDK / 'Include' / SDK_VER / 'um'}",
            ]
            libpaths = [
                f"/LIBPATH:{VS_TOOLS / 'lib' / 'x86'}",
                f"/LIBPATH:{SDK / 'Lib' / SDK_VER / 'ucrt' / 'x86'}",
                f"/LIBPATH:{SDK / 'Lib' / SDK_VER / 'um' / 'x86'}",
            ]
            compile_cmd = (
                [str(CL), "/nologo", "/W3", f"/Fe:{exe}", f"/Fo:{obj}"]
                + includes
                + [str(HARNESS), "/link"]
                + libpaths
            )
            built = subprocess.run(
                compile_cmd, capture_output=True, text=True, cwd=tmp
            )
            self.assertEqual(
                built.returncode, 0,
                f"harness failed to compile:\n{built.stdout}\n{built.stderr}",
            )
            run = subprocess.run([str(exe)], capture_output=True, text=True)
            self.assertEqual(
                run.returncode, 0,
                f"distribution harness reported failures:\n{run.stdout}",
            )
            self.assertIn("ALL PASS", run.stdout)


if __name__ == "__main__":
    unittest.main()
