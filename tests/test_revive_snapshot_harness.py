"""Revive keeps every detail (the owner, 2026-11-25): the Cause of Death companion's capture and file, every game.

native/vvfp_cause_of_death/revive_snapshot_harness.c compiles the companion's source in with the Documents folder
redirected to a throwaway folder (never the real Documents\\LDW).  For each game, at record 7 of the stock table
and record 200 (the 256-villager table of The Secret City to New Believers; A New Home and The Lost Children have
256 records already): two villagers with every byte set depart in turn from the SAME record (the slot reused at the
population cap); nothing is written before the save; the save writes one valid file holding each one's saved
windows byte for byte, oldest first; the restore (vv_rs_apply) onto a record the creator made gives back every
persistent byte and leaves the age and every transient byte as the creator made them; The Secret City's Chief flag
only with no other Chief, New Believers' faction never flipped raw; a damaged snapshot or file, or another game's,
is never used; another village's departure is never written; the next save adds after the others; Start Over
deletes the file.
"""
from __future__ import annotations

import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CL = Path(
    r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC"
    r"\14.51.36231\bin\Hostx64\x86\cl.exe"
)
# 15 checks a run, 10 runs (two record indexes in each of five games), the Chief's two (two runs) and the
# faction's one (two runs).
CHECKS = 15 * 10 + 2 * 2 + 1 * 2


@unittest.skipUnless(CL.is_file(), "the 32-bit MSVC toolchain is not installed")
class ReviveSnapshotHarness(unittest.TestCase):
    def test_every_game_keeps_and_restores_every_detail(self) -> None:
        with tempfile.TemporaryDirectory(prefix="vvfp_revive_docs_") as docs:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                 str(ROOT / "scripts" / "build_revive_snapshot_harness.ps1"), "-Docs", docs],
                capture_output=True, text=True, timeout=600,
            )
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertIn("== 0 failure(s) ==", output)
        self.assertNotIn("FAIL", output)
        for game in range(1, 6):
            self.assertIn(f"Virtual Villagers {game}, ", output)
        self.assertEqual(len(re.findall(r"^  ok ", output, re.M)), CHECKS, output)


if __name__ == "__main__":
    unittest.main()
