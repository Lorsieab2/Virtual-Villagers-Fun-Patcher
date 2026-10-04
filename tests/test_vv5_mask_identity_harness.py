"""The VV5 mask sidecar harness is BUILT AND RUN, not only kept in the tree.

native/vv5_task9_origins/vv5_mask_identity_harness.c drives the committed VV5
companion over a fake villager array and checks the sidecar it writes. It had
no build script and nothing ran it, so when the companion moved its sidecar to
"Virtual Villagers Fun Patcher Data\\Village Masks - Save <n>.dat" (4c5c2c76)
the harness went on checking the old "vvfp_masks_1.dat" and failed three
checks on every run without anyone seeing it. This test runs
scripts/build_vv5_mask_identity_harness.ps1 whenever the 32-bit MSVC toolchain
is installed, so the harness cannot go stale unseen again.
"""
from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "scripts" / "build_vv5_mask_identity_harness.ps1"
CL = Path(
    r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC"
    r"\14.51.36231\bin\Hostx64\x86\cl.exe"
)


class Vv5MaskIdentityHarnessRunsTests(unittest.TestCase):
    @unittest.skipUnless(CL.is_file(), "the 32-bit MSVC toolchain is not installed")
    def test_the_harness_passes(self) -> None:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(BUILD)],
            capture_output=True,
            text=True,
            timeout=300,
        )
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertIn("== 0 failure(s) ==", result.stdout)
        self.assertNotIn("FAIL", result.stdout)
        for case in (
            # The sidecar is looked for where the companion writes it.
            "ok   chooser write created ",
            "Virtual Villagers Fun Patcher Data\\Village Masks - Save 1.dat",
            "ok   file is magic + 150 roster dwords + 75-byte table",
            "ok   file magic is 'VM05'",
            "ok   back to slot 1: A's masks reload from its file",
        ):
            with self.subTest(case=case):
                self.assertIn(case, result.stdout)


if __name__ == "__main__":
    unittest.main()
