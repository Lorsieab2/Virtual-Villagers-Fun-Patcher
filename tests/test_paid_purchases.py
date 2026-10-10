"""A bought Barrel of Babies not delivered yet survives a quit (A New Home to The Tree of Life).

The purchase takes the tech points in the village, which are saved with it, but
its pending token lived only in the executable's memory (A New Home 0x48D700 /
0x48D704, The Lost Children 0x49C700 / 0x49C708), so a quit before the delivery
kept the charge and lost the barrel.  native/shared/paid_purchases.h keeps it in
a per-slot file and re-arms it for the same village once its save holds the
charge; Start Over deletes the file with the village.
"""
from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "scripts/build_paid_purchases_harness.ps1"
CL = Path(r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231\bin\Hostx64\x86\cl.exe")
CHECKS = 18


class PaidPurchases(unittest.TestCase):
    @unittest.skipUnless(CL.is_file(), "the 32-bit MSVC toolchain is not installed")
    def test_the_harness_passes(self) -> None:
        result = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(BUILD)],
                                capture_output=True, text=True, timeout=600)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"== {CHECKS} check(s), 0 failure(s) ==", result.stdout)
        self.assertEqual(len(re.findall(r"^  ok ", result.stdout, re.M)), CHECKS, result.stdout)

    def test_both_games_keep_their_barrel(self) -> None:
        vv1 = (ROOT / "native/vv1_origins_icons/vv1_origins_icons.c").read_text(encoding="utf-8")
        vv2 = (ROOT / "native/vv2_origins_icons/vv2_origins_icons.c").read_text(encoding="utf-8")
        self.assertIn("(volatile unsigned char *)0x0048D700, (volatile unsigned int *)0x0048D704, 2,", vv1)
        self.assertIn("    vv1_paid_tick(slot);", vv1)
        self.assertIn("(volatile unsigned char *)0x0049C700, (volatile unsigned int *)0x0049C708, 2,", vv2)
        self.assertIn("    vv2_paid_tick(base);", vv2)
        vv3 = (ROOT / "native/vv3_full_mastery_candidate/vv3_full_mastery_candidate.c").read_text(encoding="utf-8")
        vv4 = (ROOT / "native/vv4_origins_icons/vv4_origins_icons.c").read_text(encoding="utf-8")
        self.assertIn("(volatile unsigned char *)0x006E0058, (volatile unsigned int *)0x006E004C, 1,", vv3)
        self.assertIn("    vv3_paid_tick();", vv3)
        self.assertIn("(volatile unsigned char *)0x00728B04, NULL, 1,", vv4)
        self.assertIn("    vv4_paid_tick();", vv4)
        for line in ("0x00728B00u = 1;", "0x004CCA0Du = 0;", "(world + 0x170E0u) = 0u;"):
            self.assertIn(line, vv4)
        # The same addresses the slot stubs clear on a change of village.
        self.assertIn("BARREL_PENDING_VA = 0x49C700", (ROOT / "scripts/build_vv2_mask_stage2.py").read_text(encoding="utf-8"))

    def test_start_over_deletes_it_with_the_village(self) -> None:
        reset = (ROOT / "native/shared/save_reset.c").read_text(encoding="utf-8")
        self.assertIn('Paid Purchases\\\\Virtual Villagers " n " Paid Purchases - Save %d.dat"', reset)
        for game in range(1, 6):
            self.assertIn(f'/* VV{game} */ {{ PAID_FORMAT("{game}"),', reset)


if __name__ == "__main__":
    unittest.main()
