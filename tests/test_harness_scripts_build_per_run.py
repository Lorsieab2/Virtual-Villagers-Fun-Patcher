"""Every harness build script builds into a folder of its own, per run.

The scripts/build_*harness*.ps1 scripts used to compile into one fixed %TEMP%
path each (for example %TEMP%\\vvfp_statistics_store_harness\\
statistics_store_harness.exe), and several dropped their .obj files in
whatever the current directory was. Two test runs at once -- two worktrees,
two suites -- then collided: C1083 "Cannot open compiler generated file" and
LNK1104 "cannot open file ...exe" were measured with three concurrent copies
of the statistics-store, header/slot, select-holes and Deaths-log scripts,
and tests/test_unique_stews.py failed with LNK1104 in a full-suite run while
another suite ran. The two custom-titles scripts also deleted EVERY
%TEMP%\\vvfp_*titles*_harness_* folder when they finished, a concurrent run's
included.

Each script now makes a fresh GUID-named folder under %TEMP%, sends the
objects there with /Fo, and removes it in a finally block. The executable
keeps its basename: native/shared/harness_ldw_tree.h names a harness's
Documents\\LDW folder and its global lock after it. A script that takes
-OutDir builds there instead when a caller passes one, and leaves that folder
to the caller (tests/test_harnesses_leave_ldw_as_found.py runs the Deaths-log
executable again from it). build_save_reset_harness.ps1 was fixed the same
way first (#517) and is held to the same rules.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = sorted((ROOT / "scripts").glob("build_*harness*.ps1"))

GUID_FOLDER = re.compile(
    r'\$(?P<var>\w+) = Join-Path \$env:TEMP \("vvfp_\w+_" \+ \[guid\]::NewGuid\(\)\.ToString\("N"\)\)'
)


class HarnessScriptsBuildPerRun(unittest.TestCase):
    def test_the_set_of_scripts_is_the_measured_one(self) -> None:
        # 17 when this test was written, plus build_vv5_mask_identity_harness.ps1
        # (#518), which landed alongside it and follows the same rules, the
        # two data-folder harnesses (build_data_subfolder_harness.ps1,
        # build_data_writer_paths_harness.ps1),
        # build_grave_backfill_harness.ps1 (the Deaths log's grave backfill)
        # build_arrival_harness.ps1 (the Arrived records),
        # build_reconcile_harness.ps1 (the Elders and Statistics reconcile) and
        # build_patcher_files_harness.ps1 (native/shared/patcher_files.h's
        # path builder, for the "Virtual Villagers Fun Patcher Files" folder) and\n        # build_lost_birth_harness.ps1 (the babies lost with their mother; it follows the same rules).
        self.assertEqual(len(SCRIPTS), 25, [path.name for path in SCRIPTS])

    def test_each_run_builds_in_its_own_folder_and_removes_it(self) -> None:
        for path in SCRIPTS:
            text = path.read_text(encoding="utf-8")
            with self.subTest(script=path.name):
                folder = GUID_FOLDER.search(text)
                self.assertIsNotNone(folder, "no per-run GUID folder under %TEMP%")
                var = folder.group("var")
                self.assertIn(f'("/Fo" + ${var} + "\\")', text, "objects not sent to the run's folder")
                self.assertIn(f'("/OUT:" + ', text)
                finally_block = text[text.rindex("finally {"):]
                self.assertIn(f"Remove-Item -LiteralPath ${var} -Recurse -Force", finally_block)

    def test_no_script_uses_a_fixed_temp_path_or_sweeps_temp(self) -> None:
        for path in SCRIPTS:
            text = path.read_text(encoding="utf-8")
            with self.subTest(script=path.name):
                self.assertNotIn('Join-Path $env:TEMP "', text, "a fixed %TEMP% path")
                self.assertNotRegex(text, r"Join-Path \$env:TEMP \(\"[^\"]+\" \+ \$PID\)", "a $PID folder")
                self.assertNotIn("Get-ChildItem -LiteralPath $env:TEMP", text, "sweeps every run's folders")

    def test_an_out_dir_from_the_caller_is_left_to_the_caller(self) -> None:
        takes_out_dir = [path for path in SCRIPTS if "[string]$OutDir" in path.read_text(encoding="utf-8")]
        # 10, build_arrival_harness.ps1 (the Arrived records) and
        # build_reconcile_harness.ps1 (the Elders and Statistics reconcile) and\n        # build_lost_birth_harness.ps1 (the babies lost with their mother).
        self.assertEqual(len(takes_out_dir), 13)
        for path in takes_out_dir:
            text = path.read_text(encoding="utf-8")
            with self.subTest(script=path.name):
                self.assertIn('[string]$OutDir = ""', text)
                self.assertIn("$ownsOutDir = -not $OutDir", text)
                self.assertRegex(
                    text,
                    r"if \(\$ownsOutDir\) \{\n\s+Remove-Item -LiteralPath \$OutDir -Recurse -Force",
                )

    def test_the_title_harnesses_save_folder_lives_in_the_runs_folder(self) -> None:
        """Those two harnesses make <GetTempPath>\\vvfp_title*_harness_<pid>
        and never remove it; the script points TEMP and TMP at its own folder
        for the run, so the save folder goes with it."""
        for name in ("build_custom_titles_harness.ps1", "build_custom_title_log_harness.ps1"):
            text = (ROOT / "scripts" / name).read_text(encoding="utf-8")
            with self.subTest(script=name):
                run = text.index("& $out")
                self.assertIn("$env:TEMP = $work", text[:run])
                self.assertIn("$env:TMP = $work", text[:run])
                finally_block = text[text.rindex("finally {"):]
                self.assertIn("$env:TEMP = $savedTemp", finally_block)
                self.assertIn("$env:TMP = $savedTmp", finally_block)


if __name__ == "__main__":
    unittest.main()
